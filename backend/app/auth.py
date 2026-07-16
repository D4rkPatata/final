"""Autenticacion mock para el RAG clinico: DNI + contraseña.

Para el hackaton los usuarios se precargan en data/usuarios.json (seed fijo,
sin endpoint de registro). Las contraseñas se guardan hasheadas con bcrypt
para no meter malos habitos de seguridad, aunque el resto del flujo sea
deliberadamente simple.
"""
import json
from typing import Optional

import bcrypt
from fastapi import APIRouter

from app.config import settings
from app.logging_config import get_logger
from app.schemas import LoginRequest, LoginResponse

logger = get_logger("auth")


class CredencialesInvalidasError(Exception):
    """DNI no registrado o contraseña incorrecta."""


def _cargar_usuarios() -> list[dict]:
    if not settings.usuarios_path.exists():
        logger.warning("No existe %s, no hay usuarios registrados.", settings.usuarios_path)
        return []
    with open(settings.usuarios_path, "r", encoding="utf-8") as f:
        return json.load(f)


def verificar_credenciales(dni: str, password: str) -> Optional[dict]:
    """Verifica DNI + contraseña contra el seed de usuarios.

    Retorna el registro del usuario (sin el hash de la contraseña) si son
    validas, o None si el DNI no existe o la contraseña no coincide.
    """
    usuarios = _cargar_usuarios()
    usuario = next((u for u in usuarios if u.get("dni") == dni), None)

    if usuario is None:
        logger.info("Intento de login con DNI no registrado: %s", dni)
        return None

    password_hash = usuario.get("password_hash", "").encode("utf-8")
    if not bcrypt.checkpw(password.encode("utf-8"), password_hash):
        logger.info("Intento de login con contraseña incorrecta para DNI: %s", dni)
        return None

    return {
        "dni": usuario["dni"],
        "correo": usuario.get("correo"),
        "nombre": usuario.get("nombre"),
        "historia_clinica_id": usuario["historia_clinica_id"],
    }


router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    """Endpoint utilitario para probar credenciales sueltas durante la demo."""
    usuario = verificar_credenciales(request.dni, request.password)
    if usuario is None:
        return LoginResponse(autenticado=False, mensaje="DNI o contraseña incorrectos.")
    return LoginResponse(autenticado=True, mensaje="Autenticacion exitosa.", nombre=usuario.get("nombre"))
