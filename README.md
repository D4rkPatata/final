# HospitalCheck — Triage y Orientación de Salud

Prototipo de asistente virtual para orientación administrativa y de salud:
clasifica consultas de texto libre y las enruta a un árbol de decisión clínico
multi-turno (síntomas), un RAG sobre documentos institucionales, o un RAG sobre
la historia clínica del paciente autenticado. Corre 100% local con
[Ollama](https://ollama.com) (Qwen 3B + nomic-embed-text) — sin APIs externas
de pago.

```
HospitalCheck-backend/
├── backend/    # API FastAPI (clasificador, arbol de triage, RAG, auth)
└── frontend/   # SPA estatica (HTML/CSS/JS) que consume la API por fetch
```

## 1. Requisitos previos

- Python 3.12+
- [Ollama](https://ollama.com) instalado y corriendo

## 2. Instalar Ollama y los modelos

**Windows**: descarga el instalador desde [ollama.com/download](https://ollama.com/download)
y ejecútalo (o, si tienes `winget`: `winget install Ollama.Ollama`). Al
terminar, Ollama queda corriendo como servicio en `localhost:11434`.

Verifica que está activo:

```powershell
curl http://localhost:11434/api/tags
```

Descarga los dos modelos que usa el proyecto (una sola vez, ~2-4 GB en total):

```powershell
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

## 3. Levantar el backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env

uvicorn app.main:app --reload
```

Confirma que quedó arriba en `http://localhost:8000/health` (debe responder
`{"status":"ok"}`). Docs interactivas de la API en `http://localhost:8000/docs`.

Detalle de endpoints, ejemplos `curl`, usuarios de prueba y notas de diseño
(qué reglas son duras en código vs. qué usa el LLM) en
**[backend/README.md](backend/README.md)**.

## 4. Levantar el frontend

En otra terminal (deja el backend corriendo en la primera):

```powershell
cd frontend
python -m http.server 8080
```

Abre `http://localhost:8080` en el navegador. El frontend llama directamente
a `http://localhost:8000` (constante `API_BASE_URL` en `frontend/app.js`) —
si cambias el puerto o el host del backend, ajusta esa constante.

## 5. Cargar documentos propios (opcional)

- Documentos institucionales → `backend/data/administrativo/` (`.md`, `.txt`
  o `.docx`; ver `backend/data/administrativo/README.md`).
- Historias clínicas por paciente → `backend/data/clinico/<historia_clinica_id>/`
  (ver `backend/data/clinico/README.md`) y agrega el paciente en
  `backend/data/usuarios.json`.

Después de agregar o cambiar documentos, reindexa:

```powershell
cd backend
python scripts/ingest_docs.py todo
```

## 6. Primer uso

1. Abre el frontend, entra como invitado o con un usuario de
   `backend/data/usuarios.json`.
2. Prueba una pregunta administrativa, una de síntomas (te va a guiar con
   botones paso a paso) y, si estás logueado, una sobre tu historia clínica.
3. Si algo no responde, revisa la consola del backend — loguea cada paso
   (clasificación, si llamó o no a Ollama, errores) para facilitar el debug.

Más detalle de endpoints y diseño en [backend/README.md](backend/README.md).
