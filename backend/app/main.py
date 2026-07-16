"""Punto de entrada FastAPI: registra routers, CORS y manejo global de errores
de Ollama (caido / timeout) para no devolver 500 genericos durante la demo.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import arbol_triage, auth, clasificador, orquestador
from app.config import settings
from app.logging_config import get_logger
from app.ollama_client import OllamaTimeoutError, OllamaUnavailableError
from app.rag import administrativo, clinico

logger = get_logger("main")

app = FastAPI(title="Backend de Triage y Orientacion de Salud (MINSA - Hackaton)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clasificador.router)
app.include_router(arbol_triage.router)
app.include_router(administrativo.router)
app.include_router(clinico.router)
app.include_router(auth.router)
app.include_router(orquestador.router)


@app.exception_handler(OllamaUnavailableError)
def ollama_unavailable_handler(request: Request, exc: OllamaUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": str(exc)})


@app.exception_handler(OllamaTimeoutError)
def ollama_timeout_handler(request: Request, exc: OllamaTimeoutError) -> JSONResponse:
    return JSONResponse(status_code=504, content={"error": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
def log_config_on_startup() -> None:
    logger.info("=" * 60)
    logger.info("Backend de Triage y Orientacion de Salud (MINSA - Hackaton)")
    logger.info("Ollama URL: %s", settings.ollama_url)
    logger.info("Modelo de chat: %s", settings.ollama_chat_model)
    logger.info("Modelo de embeddings: %s", settings.ollama_embed_model)
    logger.info("Umbral de confianza del clasificador: %.2f", settings.confianza_minima)
    logger.info("RAG top_k=%d, similitud_minima=%.2f", settings.rag_top_k, settings.rag_similitud_minima)
    logger.info("=" * 60)
