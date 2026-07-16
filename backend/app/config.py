"""Configuracion central del backend. Todo se puede sobreescribir via .env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ollama_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:3b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout: float = 60.0

    confianza_minima: float = 0.6

    # Con corpus chicos (unos pocos documentos, como en el hackaton) conviene un
    # top_k generoso: la similitud coseno de nomic-embed-text no siempre rankea
    # el fragmento correcto primero, y top_k bajo puede dejarlo justo afuera.
    rag_top_k: int = 6
    rag_similitud_minima: float = 0.3

    data_dir: Path = BASE_DIR / "data"
    storage_dir: Path = BASE_DIR / "storage"
    logs_dir: Path = BASE_DIR / "logs"

    @property
    def usuarios_path(self) -> Path:
        return self.data_dir / "usuarios.json"

    @property
    def arbol_triage_path(self) -> Path:
        return self.data_dir / "arbol_triage.json"

    @property
    def admin_docs_dir(self) -> Path:
        return self.data_dir / "administrativo"

    @property
    def clinico_docs_dir(self) -> Path:
        return self.data_dir / "clinico"

    @property
    def chroma_admin_dir(self) -> Path:
        return self.storage_dir / "chroma_admin"

    @property
    def chroma_clinico_dir(self) -> Path:
        return self.storage_dir / "chroma_clinico"

    @property
    def auditoria_log_path(self) -> Path:
        return self.logs_dir / "auditoria_clinica.log"


settings = Settings()
