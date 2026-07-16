# Documentos administrativos

Coloca aca los documentos institucionales que quieres que el RAG administrativo
pueda consultar: horarios de atencion, requisitos para citas, procesos de
tramites, costos, ubicaciones, etc.

## Formato esperado

- Un archivo `.md` o `.txt` por documento (o por tema).
- El nombre del archivo se usa como referencia al citar la fuente en las
  respuestas (ej. `horarios_pediatria.md`), asi que usa nombres descriptivos.
- Texto plano en español, sin necesidad de formato especial. Parrafos y
  saltos de linea normales; el sistema se encarga de dividir el contenido en
  fragmentos automaticamente.

## Como indexar

Despues de agregar o modificar archivos aca, corre desde la raiz del proyecto:

```
python scripts/ingest_docs.py admin
```

Esto reconstruye el indice desde cero con el contenido actual de esta carpeta.
