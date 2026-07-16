"""Motor de triage por arbol de decision (reemplaza al triage.py anterior, mas simple).

Adaptado de un motor de sesiones aportado para el proyecto, con estas correcciones:
- Encoding: el JSON original venia con mojibake (UTF-8 releido como Latin-1); se
  corrigio al generar data/arbol_triage.json.
- Las "reglas_globales" del JSON (elevar por edad <1 o >=65, por empeoramiento, por
  multiples motivos detectados) estaban documentadas pero nunca se aplicaban: aca si
  se aplican (ver `_resultado_final`).
- "no_sabe" escala a revision humana con una sola respuesta dudosa (mas conservador que
  el umbral de 2 que sugeria el JSON): ante cualquier duda, se prefiere pecar de cauto.
- Se quito la rama tipo_consulta=administrativa/fuera_alcance de /triaje/iniciar: esa
  clasificacion ya la hace clasificador.py + orquestador.py; este modulo solo atiende
  el arbol de sintomas.
- `seleccion_motivo` construye sus opciones desde las claves reales de
  `motivos_consulta` (no desde flujo_inicial.seleccion_motivo.opciones, que lista un id
  "debilidad_neurologica" que no existe como tal en motivos_consulta -> "neurologico").

El arbol nunca le pide al LLM que responda una pregunta clinica: cada nodo lo contesta
explicitamente la persona (via botones en el frontend). El LLM no interviene en esta ruta.
"""
import json
import unicodedata
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.logging_config import get_logger
from app.schemas import (
    ContextoTriageRequest,
    FiltroEmergenciaRequest,
    IniciarTriageRequest,
    PasoTriageResponse,
    RespuestaNodoRequest,
    SeleccionMotivoRequest,
)

logger = get_logger("arbol_triage")

with open(settings.arbol_triage_path, encoding="utf-8") as f:
    CONFIG: dict[str, Any] = json.load(f)

# Sesiones en memoria: valido para el hackaton (proceso unico), se pierden al
# reiniciar el servidor. Igual criterio que el resto del proyecto (log de
# auditoria en archivo plano, etc.).
SESSIONS: dict[str, dict[str, Any]] = {}

# Escala de severidad para "elevar un nivel". "humano" queda fuera de esta escala:
# solo se llega a el por una respuesta "no_sabe" explicita, nunca por elevacion.
NIVEL_ORDEN = ["azul", "verde", "amarillo", "naranja", "rojo"]

OPCIONES_SI_NO_NO_SABE = [
    {"id": "si", "texto": "Sí"},
    {"id": "no", "texto": "No"},
    {"id": "no_sabe", "texto": "No sé"},
]


def _normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _elevar_nivel(nivel: str) -> str:
    if nivel not in NIVEL_ORDEN:
        return nivel
    idx = NIVEL_ORDEN.index(nivel)
    return NIVEL_ORDEN[min(idx + 1, len(NIVEL_ORDEN) - 1)]


def _aplicar_minimo(nivel: str, minimo: Optional[str]) -> str:
    if minimo is None or nivel not in NIVEL_ORDEN or minimo not in NIVEL_ORDEN:
        return nivel
    if NIVEL_ORDEN.index(nivel) < NIVEL_ORDEN.index(minimo):
        return minimo
    return nivel


def _emergency_ids() -> set[str]:
    return {p["id"] for p in CONFIG["filtro_universal_emergencia"]["preguntas"]}


def _detectar_motivos_candidatos(texto: str) -> set[str]:
    """Pre-escaneo determinístico (sin LLM) usando las palabras_clave de cada
    motivo, para sugerir opciones en seleccion_motivo y para la regla global
    'multiples' (si matchean >=2 motivos distintos)."""
    texto_norm = _normalizar(texto)
    detectados = set()
    for motivo_id, motivo in CONFIG["motivos_consulta"].items():
        for palabra in motivo.get("palabras_clave", []):
            if _normalizar(palabra) in texto_norm:
                detectados.add(motivo_id)
                break
    return detectados


def get_session(session_id: str) -> dict[str, Any]:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión de triage no encontrada")
    return session


def _resultado_final(session: dict[str, Any], nivel: str, motivo_clasificacion: str) -> PasoTriageResponse:
    nivel_final = nivel
    if nivel_final in NIVEL_ORDEN:
        # Regla "empeora": eleva el minimo a amarillo.
        nivel_final = _aplicar_minimo(nivel_final, session.get("nivel_minimo"))
        # Reglas "menor_1"/"mayor_65": elevan un nivel (mutuamente excluyentes).
        if session.get("elevar_por_edad"):
            nivel_final = _elevar_nivel(nivel_final)
        # Regla "multiples": >=2 motivos detectados en el texto inicial.
        if len(session.get("candidatos_motivo", set())) >= 2:
            nivel_final = _elevar_nivel(nivel_final)

    session["finalizado"] = True
    session["etapa"] = "finalizado"
    session["nivel"] = nivel_final

    nivel_data = CONFIG["niveles_orientacion"][nivel_final]
    return PasoTriageResponse(
        session_id=session["session_id"],
        finalizado=True,
        resultado={
            "nivel": nivel_final,
            "nombre_nivel": nivel_data["nombre"],
            "motivo_clasificacion": motivo_clasificacion,
            "mensaje": nivel_data["mensaje"],
            "disclaimer": CONFIG["salida_estandar"]["disclaimer"],
        },
    )


def _paso_filtro_emergencia(session: dict[str, Any]) -> PasoTriageResponse:
    filtro = CONFIG["filtro_universal_emergencia"]
    opciones = [{"id": p["id"], "texto": p["texto"]} for p in filtro["preguntas"]]
    opciones.append({"id": filtro["opcion_ninguna"]["id"], "texto": filtro["opcion_ninguna"]["texto"]})
    return PasoTriageResponse(
        session_id=session["session_id"],
        finalizado=False,
        etapa="filtro_emergencia",
        pregunta=filtro["pregunta_principal"],
        advertencia=CONFIG["flujo_inicial"]["etapas"][1]["texto"],
        opciones=opciones,
        seleccion_multiple=True,
    )


def _paso_seleccion_motivo(session: dict[str, Any]) -> PasoTriageResponse:
    candidatos = session.get("candidatos_motivo", set())
    opciones = [
        {"id": motivo_id, "texto": motivo["nombre"]}
        for motivo_id, motivo in CONFIG["motivos_consulta"].items()
    ]
    # Los motivos sugeridos por el pre-escaneo de keywords aparecen primero.
    opciones.sort(key=lambda o: 0 if o["id"] in candidatos else 1)
    return PasoTriageResponse(
        session_id=session["session_id"],
        finalizado=False,
        etapa="seleccion_motivo",
        pregunta="¿Cuál es el principal síntoma o problema de salud?",
        opciones=opciones,
        seleccion_multiple=False,
    )


def iniciar_sesion(texto_inicial: str) -> PasoTriageResponse:
    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "etapa": "filtro_emergencia",
        "finalizado": False,
        "candidatos_motivo": _detectar_motivos_candidatos(texto_inicial),
        "motivo": None,
        "nodo_actual": None,
        "nivel_minimo": None,
        "elevar_por_edad": False,
        "respuestas": {},
    }
    SESSIONS[session_id] = session
    logger.info("Triage: nueva sesión %s (candidatos por keyword: %s)", session_id, session["candidatos_motivo"])
    return _paso_filtro_emergencia(session)


def procesar_filtro_emergencia(session_id: str, opciones: list[str]) -> PasoTriageResponse:
    session = get_session(session_id)
    if session["etapa"] != "filtro_emergencia":
        raise HTTPException(status_code=409, detail="La sesión no está en esta etapa")

    seleccionadas = set(opciones)
    none_id = CONFIG["filtro_universal_emergencia"]["opcion_ninguna"]["id"]
    critical = _emergency_ids()

    invalidas = seleccionadas - critical - {none_id}
    if invalidas:
        raise HTTPException(status_code=400, detail=f"Opciones no válidas: {sorted(invalidas)}")

    # "Ninguna" es exclusiva: si viene junto con una señal crítica, se ignora
    # "ninguna" y se procesa la señal crítica (regla_seleccion "priorizar_senal_critica").
    seleccionadas.discard(none_id)
    detectadas = seleccionadas & critical

    if detectadas:
        motivos = [p["si"]["motivo"] for p in CONFIG["filtro_universal_emergencia"]["preguntas"] if p["id"] in detectadas]
        logger.info("Triage %s: bandera(s) roja(s) del filtro: %s", session_id, detectadas)
        return _resultado_final(session, "rojo", "; ".join(motivos))

    session["etapa"] = "seleccion_motivo"
    return _paso_seleccion_motivo(session)


def seleccionar_motivo(session_id: str, motivo: str) -> PasoTriageResponse:
    session = get_session(session_id)
    if session["etapa"] != "seleccion_motivo":
        raise HTTPException(status_code=409, detail="La sesión no está en esta etapa")
    if motivo not in CONFIG["motivos_consulta"]:
        raise HTTPException(status_code=400, detail="Motivo no válido")

    session["motivo"] = motivo
    session["etapa"] = "contexto"
    return PasoTriageResponse(
        session_id=session["session_id"],
        finalizado=False,
        etapa="contexto",
        preguntas_contexto=CONFIG["preguntas_contexto"],
    )


def guardar_contexto(session_id: str, edad: int, embarazo: str, duracion: str, empeoramiento: bool) -> PasoTriageResponse:
    session = get_session(session_id)
    if session["etapa"] != "contexto":
        raise HTTPException(status_code=409, detail="La sesión no está en esta etapa")

    motivo_id = session["motivo"]

    # El motivo elegido puede no calzar con la edad real (ej. "fiebre en adulto"
    # para un hijo menor de edad): se corrige antes de recorrer el árbol.
    if motivo_id == "fiebre_adulto" and edad < 18:
        motivo_id = "fiebre_nino"
        session["motivo"] = motivo_id
    elif motivo_id == "fiebre_nino" and edad >= 18:
        motivo_id = "fiebre_adulto"
        session["motivo"] = motivo_id

    motivo = CONFIG["motivos_consulta"][motivo_id]

    # Reglas globales "empeora" (eleva el mínimo a amarillo) y "menor_1"/"mayor_65"
    # (elevan un nivel el resultado final del árbol); se aplican en _resultado_final.
    session["nivel_minimo"] = "amarillo" if empeoramiento else None
    session["elevar_por_edad"] = edad < 1 or edad >= 65

    node_id = motivo["nodo_inicial"]
    session["nodo_actual"] = node_id
    session["etapa"] = "arbol"

    return PasoTriageResponse(
        session_id=session["session_id"],
        finalizado=False,
        etapa="arbol",
        pregunta=motivo["nodos"][node_id]["pregunta"],
        opciones=OPCIONES_SI_NO_NO_SABE,
        seleccion_multiple=False,
    )


def responder_nodo(session_id: str, respuesta: str) -> PasoTriageResponse:
    session = get_session(session_id)
    if session["etapa"] != "arbol":
        raise HTTPException(status_code=409, detail="La sesión no está en esta etapa")

    motivo = CONFIG["motivos_consulta"][session["motivo"]]
    node_id = session["nodo_actual"]
    node = motivo["nodos"][node_id]
    session["respuestas"][node_id] = respuesta

    # Ante cualquier duda ("no sé") se escala a revisión humana en vez de asumir
    # "no": mas conservador que el umbral de 2 respuestas dudosas que sugería el
    # JSON original, mismo criterio de "ante duda, escalar" del propio documento.
    if respuesta == "no_sabe":
        logger.info("Triage %s: 'no sé' en nodo %s, escalando a revisión humana", session_id, node_id)
        return _resultado_final(session, "humano", f"No se pudo responder con seguridad la pregunta {node_id}")

    branch = node["si"] if respuesta == "si" else node["no"]

    if "resultado" in branch:
        return _resultado_final(session, branch["resultado"], branch.get("motivo", "Resultado del árbol"))

    next_node_id = branch["siguiente"]
    session["nodo_actual"] = next_node_id
    next_node = motivo["nodos"][next_node_id]

    return PasoTriageResponse(
        session_id=session["session_id"],
        finalizado=False,
        etapa="arbol",
        pregunta=next_node["pregunta"],
        opciones=OPCIONES_SI_NO_NO_SABE,
        seleccion_multiple=False,
    )


router = APIRouter()


@router.post("/triaje/iniciar", response_model=PasoTriageResponse)
def triaje_iniciar(request: IniciarTriageRequest) -> PasoTriageResponse:
    return iniciar_sesion(request.texto)


@router.post("/triaje/filtro-emergencia", response_model=PasoTriageResponse)
def triaje_filtro_emergencia(request: FiltroEmergenciaRequest) -> PasoTriageResponse:
    return procesar_filtro_emergencia(request.session_id, request.opciones)


@router.post("/triaje/motivo", response_model=PasoTriageResponse)
def triaje_motivo(request: SeleccionMotivoRequest) -> PasoTriageResponse:
    return seleccionar_motivo(request.session_id, request.motivo)


@router.post("/triaje/contexto", response_model=PasoTriageResponse)
def triaje_contexto(request: ContextoTriageRequest) -> PasoTriageResponse:
    return guardar_contexto(request.session_id, request.edad, request.embarazo, request.duracion, request.empeoramiento)


@router.post("/triaje/responder", response_model=PasoTriageResponse)
def triaje_responder(request: RespuestaNodoRequest) -> PasoTriageResponse:
    return responder_nodo(request.session_id, request.respuesta)


@router.get("/triaje/sesion/{session_id}")
def triaje_ver_sesion(session_id: str) -> dict:
    session = get_session(session_id)
    return {**session, "candidatos_motivo": sorted(session.get("candidatos_motivo", set()))}
