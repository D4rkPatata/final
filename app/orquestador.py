"""Orquestador /consulta: clasifica la intencion y enruta al flujo correspondiente.

Reutiliza directamente las funciones planas de cada modulo (sin saltos HTTP
internos): clasificador.clasificar_intencion, arbol_triage.iniciar_sesion,
rag.administrativo.responder_administrativo y rag.clinico.responder_clinico.
"""
from fastapi import APIRouter

from app.arbol_triage import iniciar_sesion as iniciar_sesion_triage
from app.auth import CredencialesInvalidasError
from app.clasificador import clasificar_intencion
from app.logging_config import get_logger
from app.rag.administrativo import responder_administrativo
from app.rag.clinico import responder_clinico
from app.schemas import ConsultaRequest, ConsultaResponse

logger = get_logger("orquestador")

MENSAJE_NO_SE = (
    "No estoy seguro de haber entendido tu consulta. ¿Podrias reformularla, o "
    "prefieres elegir manualmente entre: tramites administrativos, tu historia "
    "clinica, o describir sintomas que estas sintiendo?"
)

MENSAJE_REQUIERE_AUTH = (
    "Para consultar tu historia clinica necesito verificar tu identidad. "
    "Por favor envia tu DNI y contraseña."
)


def procesar_consulta(request: ConsultaRequest) -> ConsultaResponse:
    clasificacion = clasificar_intencion(request.texto)
    categoria = clasificacion["categoria"]
    confianza = clasificacion["confianza"]

    if categoria == "no_se":
        return ConsultaResponse(
            categoria=categoria,
            confianza=confianza,
            mensaje=MENSAJE_NO_SE,
        )

    if categoria == "sintomas":
        paso = iniciar_sesion_triage(request.texto)
        mensaje = paso.pregunta or ""
        if paso.advertencia:
            mensaje = f"{paso.advertencia}\n\n{mensaje}"
        return ConsultaResponse(
            categoria=categoria,
            confianza=confianza,
            mensaje=mensaje,
            triage_paso=paso,
        )

    if categoria == "administrativa":
        resultado_rag = responder_administrativo(request.texto)
        return ConsultaResponse(
            categoria=categoria,
            confianza=confianza,
            mensaje=resultado_rag.respuesta,
            rag=resultado_rag,
        )

    # categoria == "clinica_personal"
    if not request.dni or not request.password:
        return ConsultaResponse(
            categoria=categoria,
            confianza=confianza,
            requiere_autenticacion=True,
            mensaje=MENSAJE_REQUIERE_AUTH,
        )

    try:
        resultado_rag = responder_clinico(request.texto, request.dni, request.password)
    except CredencialesInvalidasError:
        return ConsultaResponse(
            categoria=categoria,
            confianza=confianza,
            requiere_autenticacion=True,
            mensaje="DNI o contraseña incorrectos. Intenta nuevamente.",
        )

    return ConsultaResponse(
        categoria=categoria,
        confianza=confianza,
        mensaje=resultado_rag.respuesta,
        rag=resultado_rag,
    )


router = APIRouter()


@router.post("/consulta", response_model=ConsultaResponse)
def consulta(request: ConsultaRequest) -> ConsultaResponse:
    return procesar_consulta(request)
