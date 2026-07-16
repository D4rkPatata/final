"""Modelos Pydantic de request/response compartidos por todos los endpoints."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Categoria = Literal["administrativa", "clinica_personal", "sintomas", "no_se"]
NivelTriage = Literal["rojo", "naranja", "amarillo", "verde", "azul", "humano"]
EtapaTriage = Literal["filtro_emergencia", "seleccion_motivo", "contexto", "arbol"]


class ConsultaTextoRequest(BaseModel):
    texto: str = Field(..., min_length=3, max_length=2000)


class ClasificacionResponse(BaseModel):
    categoria: Categoria
    confianza: float
    razon: str


class OpcionTriage(BaseModel):
    id: str
    texto: str


class ResultadoTriage(BaseModel):
    nivel: NivelTriage
    nombre_nivel: str
    motivo_clasificacion: str
    mensaje: str
    disclaimer: str


class PasoTriageResponse(BaseModel):
    """Forma unica de respuesta para cualquier etapa del arbol de triage (o su
    resultado final), asi el frontend solo necesita entender un shape."""

    session_id: str
    finalizado: bool
    etapa: Optional[EtapaTriage] = None
    pregunta: Optional[str] = None
    advertencia: Optional[str] = None
    opciones: Optional[list[OpcionTriage]] = None
    seleccion_multiple: bool = False
    preguntas_contexto: Optional[list[dict[str, Any]]] = None
    resultado: Optional[ResultadoTriage] = None


class IniciarTriageRequest(BaseModel):
    texto: str = Field(..., min_length=3, max_length=2000)


class FiltroEmergenciaRequest(BaseModel):
    session_id: str
    opciones: list[str] = Field(default_factory=list)


class SeleccionMotivoRequest(BaseModel):
    session_id: str
    motivo: str


class ContextoTriageRequest(BaseModel):
    session_id: str
    edad: int = Field(ge=0, le=120)
    embarazo: Literal["si", "no", "no_aplica", "no_sabe"]
    duracion: str
    empeoramiento: bool


class RespuestaNodoRequest(BaseModel):
    session_id: str
    respuesta: Literal["si", "no", "no_sabe"]


class RagResponse(BaseModel):
    respuesta: str
    fuentes: list[str]
    encontrado: bool


class LoginRequest(BaseModel):
    dni: str = Field(..., min_length=8, max_length=8)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    autenticado: bool
    mensaje: str
    nombre: Optional[str] = None


class RagClinicoRequest(BaseModel):
    texto: str = Field(..., min_length=3, max_length=2000)
    dni: str = Field(..., min_length=8, max_length=8)
    password: str = Field(..., min_length=1)


class ConsultaRequest(BaseModel):
    texto: str = Field(..., min_length=3, max_length=2000)
    dni: Optional[str] = Field(default=None, min_length=8, max_length=8)
    password: Optional[str] = Field(default=None)


class ConsultaResponse(BaseModel):
    categoria: Categoria
    confianza: float
    requiere_autenticacion: bool = False
    mensaje: str
    triage_paso: Optional[PasoTriageResponse] = None
    rag: Optional[RagResponse] = None
