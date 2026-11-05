# Flujo de Git y colaboración

## Repositorio

- **Nombre sugerido:** `orbitlens-spherex`
- **Visibilidad sugerida:** público, solo después de confirmar las condiciones de Space Apps 2026 y la licencia de cada recurso.
- **Licencia de código sugerida:** MIT (`LICENSE`). No sustituye los créditos/licencias de datos NASA ni de terceros.
- **Rama protegida:** `main`; nunca se fuerza un push sobre ella.

## Estructura cuando comience la implementación

```text
apps/web/                # interfaz pública
services/data/           # adaptador/API de datos
packages/shared/         # tipos y utilidades compartidas
data/manifests/          # metadatos versionados; no datos pesados
notebooks/               # exploración reproducible y anotada
docs/                    # ciencia, fuentes, arquitectura, pitch
tests/                   # pruebas unitarias y smoke test
```

Los datos grandes, archivos FITS, secretos, dependencias generadas y builds no se versionan. Se citan y se provee un mecanismo reproducible para obtenerlos.

## Ciclo por tarea

1. Crear un issue con resultado, criterio de aceptación y responsable.
2. Crear una rama corta: `feat/compare-epochs`, `fix/wcs-alignment`, `docs/data-credits`.
3. Hacer cambios pequeños, ejecutar las comprobaciones pertinentes y abrir un PR enlazado al issue.
4. Obtener una revisión de otra persona; el dueño de área verifica ciencia/diseño según corresponda.
5. Fusionar con *squash merge* cuando CI y revisión estén en verde; cerrar el issue.

### Convención de commits

```text
feat(viewer): add epoch blink control
fix(data): preserve observation timestamp
docs(sources): cite IRSA cutout endpoint
test(diff): cover empty quality mask
chore(ci): add web smoke test
```

Un commit debe hacer una cosa verificable y no incluir secretos ni archivos binarios pesados.

## Acuerdo de pull request

| Regla | Acuerdo |
| --- | --- |
| Tamaño | Idealmente menos de 300 líneas netas; dividir si mezcla funciones |
| Revisión | 1 aprobación; cambios de ciencia/datos también revisados por Ciencia |
| CI mínima | formato, tipo/lint, test unitario y build del frontend |
| Evidencia UI | captura o GIF corto para cada cambio visual |
| Fuentes | cualquier dato/imagen/fragmento externo va a `docs/DATA_SOURCES.md` |
| Urgencia | hotfix directo solo si el equipo lo anuncia y se revisa después |

## Tablero mínimo

`Backlog → Ready → In progress → Review → Done`

Etiquetas: `frontend`, `data`, `science`, `design`, `qa`, `blocker`, `demo-critical`, `good-first-task`.

Cada issue demo-crítico debe tener un plan B escrito. No abrir nuevas funciones después de T+18 horas sin retirar otra de igual coste.

## CI de mínimo valor

En cada PR: instalar de forma limpia, ejecutar lint/tipo, tests, build y un smoke test que cargue la página. Para una app con datos, agregar una prueba de contrato que valide los campos del manifiesto (`sourceUrl`, `epoch`, `bandsUm`, `credit`, `caveats`).

## Publicación remota

1. Crear el repositorio remoto vacío con README desactivado para evitar conflicto inicial.
2. Añadir `origin` por SSH o HTTPS y subir `main`.
3. Habilitar Issues, protección de `main`, plantilla de PR y CI.
4. Añadir colaboradores con el rol mínimo necesario; no compartir tokens.
5. Probar que una persona puede clonar el repositorio y seguir el README.
