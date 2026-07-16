"""RAG clinico: responde preguntas sobre la propia historia clinica del paciente
ya autenticado. El LLM SOLO recibe fragmentos de la historia clinica de ESE
paciente (coleccion Chroma fisicamente separada por paciente) y cada acceso
queda registrado en el log de auditoria.
"""
from fastapi import APIRouter, HTTPException

from app.auth import CredencialesInvalidasError, verificar_credenciales
from app.config import settings
from app.logging_config import get_logger, registrar_auditoria_clinica
from app.ollama_client import OllamaTimeoutError, OllamaUnavailableError, chat_texto
from app.rag.ingesta import query_index
from app.schemas import RagClinicoRequest, RagResponse

logger = get_logger("rag.clinico")

MENSAJE_SIN_INFO = "No encuentro esa informacion en tu historia clinica disponible."

SYSTEM_PROMPT = """Eres un asistente que ayuda a un paciente a consultar SU PROPIA \
historia clinica en un sistema del Ministerio de Salud del Peru. Debes responder \
UNICAMENTE con base en el fragmento de historia clinica que se te da como contexto. \
No inventes datos que no esten en el contexto, no dediques diagnosticos nuevos ni \
sugieras tratamientos: limitate a reportar lo que dice el fragmento. Si el contexto \
no responde la pregunta, dilo explicitamente.

Contexto (historia clinica del paciente):
{contexto}
"""


def _collection_dir(historia_clinica_id: str):
    # Una coleccion (y carpeta) separada por paciente: el LLM nunca recibe
    # fragmentos de otro paciente porque fisicamente no se abre esa coleccion.
    return settings.chroma_clinico_dir / historia_clinica_id


def responder_clinico(texto: str, dni: str, password: str) -> RagResponse:
    usuario = verificar_credenciales(dni, password)
    if usuario is None:
        raise CredencialesInvalidasError("DNI o contraseña incorrectos.")

    registrar_auditoria_clinica(dni, texto)

    historia_clinica_id = usuario["historia_clinica_id"]
    fragmentos = query_index(
        "historia",
        _collection_dir(historia_clinica_id),
        texto,
        top_k=settings.rag_top_k,
        min_similarity=settings.rag_similitud_minima,
    )

    if not fragmentos:
        logger.info("RAG clinico: sin fragmentos relevantes para DNI %s.", dni)
        return RagResponse(respuesta=MENSAJE_SIN_INFO, fuentes=[], encontrado=False)

    contexto = "\n\n".join(f["texto"] for f in fragmentos)

    try:
        respuesta = chat_texto(SYSTEM_PROMPT.format(contexto=contexto), texto, temperature=0.15)
    except (OllamaUnavailableError, OllamaTimeoutError) as e:
        logger.warning("RAG clinico: Ollama no disponible. %s", e)
        return RagResponse(
            respuesta="El servicio no esta disponible en este momento, intenta nuevamente.",
            fuentes=[],
            encontrado=False,
        )

    return RagResponse(respuesta=respuesta, fuentes=["historia clinica del paciente"], encontrado=True)


router = APIRouter()


@router.post("/rag/clinico", response_model=RagResponse)
def rag_clinico(request: RagClinicoRequest) -> RagResponse:
    try:
        return responder_clinico(request.texto, request.dni, request.password)
    except CredencialesInvalidasError as e:
        raise HTTPException(status_code=401, detail=str(e))
