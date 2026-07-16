"""Wrapper unico para todas las llamadas a Ollama (chat + embeddings).

Centraliza el manejo de errores: si Ollama esta caido o responde lento, se
levantan excepciones especificas que los endpoints traducen a HTTP 503/504
con un mensaje accionable, en vez de un 500 generico dificil de debuggear
en vivo durante la demo.
"""
import json

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("ollama_client")


class OllamaUnavailableError(Exception):
    """Ollama no responde / no esta corriendo."""


class OllamaTimeoutError(Exception):
    """Ollama tardo mas de lo esperado en responder."""


def _post(path: str, payload: dict) -> dict:
    url = f"{settings.ollama_url}{path}"
    try:
        resp = httpx.post(url, json=payload, timeout=settings.ollama_timeout)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError as e:
        logger.error("No se pudo conectar a Ollama en %s: %s", url, e)
        raise OllamaUnavailableError(
            "Ollama no esta disponible. Verifica que este corriendo (`ollama serve`)."
        ) from e
    except httpx.TimeoutException as e:
        logger.error("Timeout llamando a Ollama en %s: %s", url, e)
        raise OllamaTimeoutError(
            "Ollama tardo demasiado en responder. Intenta nuevamente."
        ) from e
    except httpx.HTTPStatusError as e:
        logger.error("Ollama respondio con error en %s: %s", url, e)
        raise OllamaUnavailableError(f"Ollama respondio con error: {e}") from e


def chat_json(system: str, user: str, temperature: float = 0.15) -> dict:
    """Llama al modelo de chat pidiendo salida JSON estructurada."""
    data = _post(
        "/api/chat",
        {
            "model": settings.ollama_chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature},
        },
    )
    contenido = data.get("message", {}).get("content", "")
    return json.loads(contenido)


def chat_texto(system: str, user: str, temperature: float = 0.2) -> str:
    """Llama al modelo de chat pidiendo una respuesta libre en texto plano."""
    data = _post(
        "/api/chat",
        {
            "model": settings.ollama_chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        },
    )
    return data.get("message", {}).get("content", "").strip()


def embed(texto: str) -> list[float]:
    """Genera el embedding de un texto usando el modelo de embeddings configurado."""
    data = _post(
        "/api/embeddings",
        {"model": settings.ollama_embed_model, "prompt": texto},
    )
    return data["embedding"]
