"""Clasificador de intencion: enruta texto libre a una de 4 categorias.

No usa entrenamiento propio: le pide a Qwen 3B (via Ollama) que clasifique
con few-shot examples, y el backend nunca confia ciegamente en el LLM: si la
confianza reportada es baja, o si el JSON viene mal formado / Ollama falla,
se fuerza en codigo la categoria segura "no_se".
"""
from fastapi import APIRouter

from app.config import settings
from app.logging_config import get_logger
from app.ollama_client import OllamaTimeoutError, OllamaUnavailableError, chat_json
from app.schemas import ClasificacionResponse, ConsultaTextoRequest

logger = get_logger("clasificador")

CATEGORIAS_VALIDAS = {"administrativa", "clinica_personal", "sintomas", "no_se"}

SYSTEM_PROMPT = """Eres un clasificador de intencion para un sistema de orientacion \
de salud del Ministerio de Salud del Peru. Tu unica tarea es leer la consulta de un \
usuario y clasificarla en UNA de estas 4 categorias:

- "administrativa": preguntas sobre tramites, horarios, requisitos, citas, ubicacion \
de establecimientos, documentos necesarios, costos de atencion, procesos institucionales.
- "clinica_personal": preguntas sobre la propia historia clinica, resultados de examenes, \
diagnosticos previos, medicamentos recetados, tratamientos en curso del paciente.
- "sintomas": el usuario describe sintomas o malestares que esta sintiendo actualmente \
y busca orientacion sobre que hacer.
- "no_se": la consulta es ambigua, no tiene relacion con salud, o no encaja claramente \
en ninguna categoria anterior.

Responde SIEMPRE con un JSON con exactamente este esquema, sin texto adicional:
{"categoria": "administrativa|clinica_personal|sintomas|no_se", "confianza": 0.0, "razon": "..."}

"confianza" es un numero entre 0.0 y 1.0 que refleja que tan seguro estas de la categoria.

Ejemplos:

Usuario: "Cual es el horario de atencion del area de pediatria?"
{"categoria": "administrativa", "confianza": 0.95, "razon": "Pregunta por horario de atencion, es un tramite/informacion institucional."}

Usuario: "Que documentos necesito para sacar una cita en el hospital?"
{"categoria": "administrativa", "confianza": 0.93, "razon": "Pregunta por requisitos para un tramite."}

Usuario: "Cuanto cuesta una consulta de cardiologia particular?"
{"categoria": "administrativa", "confianza": 0.88, "razon": "Pregunta sobre costos de atencion."}

Usuario: "Cuales fueron los resultados de mi analisis de sangre del mes pasado?"
{"categoria": "clinica_personal", "confianza": 0.95, "razon": "Pide resultados de examenes propios."}

Usuario: "Que medicamentos me recetaron en mi ultima consulta?"
{"categoria": "clinica_personal", "confianza": 0.93, "razon": "Pregunta sobre su propio tratamiento/receta."}

Usuario: "Quiero ver mi historia clinica completa"
{"categoria": "clinica_personal", "confianza": 0.96, "razon": "Pide acceso directo a su historia clinica."}

Usuario: "Tengo dolor de cabeza y un poco de fiebre desde ayer"
{"categoria": "sintomas", "confianza": 0.92, "razon": "Describe sintomas actuales que esta sintiendo."}

Usuario: "Me duele el estomago y tengo nauseas hace 2 horas"
{"categoria": "sintomas", "confianza": 0.9, "razon": "Describe sintomas actuales."}

Usuario: "Siento mucho cansancio y me falta el aire al caminar"
{"categoria": "sintomas", "confianza": 0.85, "razon": "Describe sintomas que esta sintiendo actualmente."}

Usuario: "Hola"
{"categoria": "no_se", "confianza": 0.9, "razon": "Saludo generico, no hay consulta clara."}

Usuario: "Necesito ayuda"
{"categoria": "no_se", "confianza": 0.85, "razon": "Consulta demasiado ambigua para clasificar."}

Usuario: "Cual es la capital de Francia?"
{"categoria": "no_se", "confianza": 0.9, "razon": "No tiene relacion con salud."}
"""

FALLBACK_SEGURO = {"categoria": "no_se", "confianza": 0.0, "razon": ""}


def clasificar_intencion(texto: str) -> dict:
    """Clasifica el texto en una de las 4 categorias. Nunca lanza excepcion:
    ante cualquier fallo (Ollama caido, timeout, JSON invalido, esquema invalido
    o confianza baja) retorna un fallback seguro con categoria 'no_se'.
    """
    try:
        resultado = chat_json(SYSTEM_PROMPT, texto, temperature=0.15)
    except (OllamaUnavailableError, OllamaTimeoutError) as e:
        logger.warning("Clasificador: Ollama no disponible, usando fallback. %s", e)
        return {**FALLBACK_SEGURO, "razon": "Servicio de clasificacion no disponible."}
    except Exception as e:
        # Incluye json.JSONDecodeError (el modelo a veces no respeta el formato)
        # y cualquier otro fallo inesperado de parseo/esquema.
        logger.warning("Clasificador: error inesperado al interpretar la respuesta. %s", e)
        return {**FALLBACK_SEGURO, "razon": "Error inesperado al clasificar."}

    categoria = resultado.get("categoria")
    try:
        confianza = float(resultado.get("confianza", 0.0))
    except (TypeError, ValueError):
        confianza = 0.0
    razon = str(resultado.get("razon", ""))

    if categoria not in CATEGORIAS_VALIDAS:
        logger.warning("Clasificador: categoria invalida del LLM: %r", categoria)
        return {"categoria": "no_se", "confianza": confianza, "razon": razon or "Categoria no reconocida."}

    if confianza < settings.confianza_minima:
        logger.info(
            "Clasificador: confianza %.2f por debajo del umbral %.2f, forzando 'no_se'",
            confianza,
            settings.confianza_minima,
        )
        return {"categoria": "no_se", "confianza": confianza, "razon": razon}

    return {"categoria": categoria, "confianza": confianza, "razon": razon}


router = APIRouter()


@router.post("/clasificar", response_model=ClasificacionResponse)
def clasificar(request: ConsultaTextoRequest) -> ClasificacionResponse:
    return ClasificacionResponse(**clasificar_intencion(request.texto))
