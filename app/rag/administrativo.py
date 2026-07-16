"""RAG administrativo: responde preguntas sobre tramites, horarios, requisitos, etc.
usando SOLO el contenido indexado en data/administrativo/.
"""
from fastapi import APIRouter

from app.config import settings
from app.logging_config import get_logger
from app.ollama_client import OllamaTimeoutError, OllamaUnavailableError, chat_texto
from app.rag.ingesta import query_index
from app.schemas import ConsultaTextoRequest, RagResponse

logger = get_logger("rag.administrativo")

COLLECTION_NAME = "administrativo"

MENSAJE_SIN_INFO = "No tengo esa informacion en los documentos institucionales disponibles."

SYSTEM_PROMPT = """Eres un asistente de informacion administrativa del Ministerio de \
Salud del Peru. Debes responder la pregunta del usuario USANDO UNICAMENTE la \
informacion que se te da como contexto a continuacion. No inventes informacion \
que no este en el contexto. Al final de tu respuesta, indica de que documento(s) \
sale la informacion citando el nombre de archivo entre parentesis. Si el contexto \
no responde la pregunta, dilo explicitamente en vez de inventar.

Contexto:
{contexto}
"""


def responder_administrativo(texto: str) -> RagResponse:
    fragmentos = query_index(
        COLLECTION_NAME,
        settings.chroma_admin_dir,
        texto,
        top_k=settings.rag_top_k,
        min_similarity=settings.rag_similitud_minima,
    )

    if not fragmentos:
        logger.info("RAG administrativo: sin fragmentos relevantes para la consulta.")
        return RagResponse(respuesta=MENSAJE_SIN_INFO, fuentes=[], encontrado=False)

    contexto = "\n\n".join(f"[{f['fuente']}]\n{f['texto']}" for f in fragmentos)
    fuentes = sorted({f["fuente"] for f in fragmentos})

    try:
        respuesta = chat_texto(SYSTEM_PROMPT.format(contexto=contexto), texto, temperature=0.15)
    except (OllamaUnavailableError, OllamaTimeoutError) as e:
        logger.warning("RAG administrativo: Ollama no disponible. %s", e)
        return RagResponse(
            respuesta="El servicio no esta disponible en este momento, intenta nuevamente.",
            fuentes=[],
            encontrado=False,
        )

    return RagResponse(respuesta=respuesta, fuentes=fuentes, encontrado=True)


router = APIRouter()


@router.post("/rag/administrativo", response_model=RagResponse)
def rag_administrativo(request: ConsultaTextoRequest) -> RagResponse:
    return responder_administrativo(request.texto)
