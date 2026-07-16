# Historias clinicas (por paciente)

El RAG clinico consulta un indice **separado por paciente**, para garantizar
que el LLM nunca reciba fragmentos de otro paciente.

## Formato esperado

Crea una carpeta por paciente usando su `historia_clinica_id` (el mismo valor
que aparece en `data/usuarios.json`):

```
data/clinico/
├── hc_001/
│   ├── consultas_2025.md
│   └── examenes.md
├── hc_002/
│   └── historia.md
```

Dentro de cada carpeta, uno o mas archivos `.md`/`.txt` con el contenido de la
historia clinica de ese paciente (consultas previas, diagnosticos, examenes,
medicamentos recetados, etc.), en texto plano.

## Como indexar

Despues de agregar o modificar archivos, corre desde la raiz del proyecto:

```
python scripts/ingest_docs.py clinico
```

Esto reconstruye el indice de cada paciente listado en `data/usuarios.json`
a partir de su carpeta correspondiente.
