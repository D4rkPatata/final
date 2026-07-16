#!/usr/bin/env python
"""CLI para (re)construir los indices Chroma desde /data.

Uso:
    python scripts/ingest_docs.py admin      # reconstruye el indice administrativo
    python scripts/ingest_docs.py clinico    # reconstruye el indice de cada paciente
    python scripts/ingest_docs.py todo       # ambos
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.rag.ingesta import build_index  # noqa: E402


def ingestar_administrativo() -> None:
    n = build_index("administrativo", settings.chroma_admin_dir, settings.admin_docs_dir)
    print(f"[administrativo] {n} fragmentos indexados desde {settings.admin_docs_dir}")


def ingestar_clinico() -> None:
    if not settings.usuarios_path.exists():
        print(f"No existe {settings.usuarios_path}, no hay pacientes que indexar.")
        return

    usuarios = json.loads(settings.usuarios_path.read_text(encoding="utf-8"))
    for usuario in usuarios:
        historia_clinica_id = usuario["historia_clinica_id"]
        docs_dir = settings.clinico_docs_dir / historia_clinica_id
        persist_dir = settings.chroma_clinico_dir / historia_clinica_id
        n = build_index("historia", persist_dir, docs_dir)
        print(f"[clinico:{historia_clinica_id}] {n} fragmentos indexados desde {docs_dir}")


if __name__ == "__main__":
    objetivo = sys.argv[1] if len(sys.argv) > 1 else "todo"

    if objetivo in ("admin", "administrativo", "todo"):
        ingestar_administrativo()
    if objetivo in ("clinico", "todo"):
        ingestar_clinico()
    if objetivo not in ("admin", "administrativo", "clinico", "todo"):
        print(__doc__)
        sys.exit(1)
