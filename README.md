# OrbitLens — SPHEREx Time Atlas

Explorador temporal de imágenes SPHEREx para el reto **Planet X and SPHEREx**
de NASA Space Apps Challenge 2026.

## La propuesta

**OrbitLens** será una herramienta web pública para explorar una región del cielo
a través del tiempo. Permitirá ingresar coordenadas RA/Dec en formato decimal o
sexagesimal, o buscar un objeto por nombre, y reproducir imágenes de SPHEREx como
una secuencia temporal para explorar posibles objetos en movimiento.

En vez de mostrar una imagen estática, permitirá alternar épocas, superponerlas
y observar la diferencia visual entre ellas. El producto convertirá 102 bandas
infrarrojas de SPHEREx en tres recorridos claros: **cambio temporal**,
**color infrarrojo** y **evidencia científica**.

El alcance previsto incluye comparación de épocas, modos *blink*, deslizador y
diferencia, apilado, información espectral, superposición de catálogos Gaia/WISE,
enlaces compartibles y metadatos de calidad y procedencia. Las funciones se
incorporarán por etapas; la web todavía no está implementada.

El producto no debe afirmar el descubrimiento de Planet X. Su valor es hacer
detectables, visibles y comprensibles posibles cambios, con evidencia y
limitaciones claras, para público general, docentes y aficionados.

[Reto oficial](https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=details)
· [Datos SPHEREx](https://science.nasa.gov/open-science/spherex-universe-map/)

## Estado

**Etapas 1 y 2 completadas: acceso a datos y pipeline temporal.** Las 18 pruebas
pasan y se generaron cinco secuencias reales de 12 frames con PNG, FITS alineados,
GIF y manifiestos. La validación cubre el procesamiento de los campos; no
confirma movimiento ni detectabilidad de los objetos. Los resultados y las
limitaciones de calidad están en [VALIDATION.md](VALIDATION.md).

El recorte validado corresponde a QR3/D6, con IMAGE de 49 × 49 píxeles y unidades
MJy/sr. El archivo FITS completo del recorte ocupa 3,985,920 bytes e incluye
extensiones auxiliares. Falta verificar la identidad del objeto en la imagen e
interpretar los bits de FLAGS antes de aplicar máscaras de calidad.

La siguiente etapa es la API de trabajos con polling y el reproductor web local.

## Documentación del proyecto

[PLAN.md](PLAN.md) contiene el plan de trabajo vigente y los resultados
verificados. Los documentos iniciales siguientes conservan el contexto de
planificación; sus propuestas de alcance, arquitectura y cronograma deben
contrastarse con el plan vigente.

| Documento | Contenido |
| --- | --- |
| [00-project-charter.md](00-project-charter.md) | problema, usuarios, métricas y responsabilidades |
| [01-architecture-and-data.md](01-architecture-and-data.md) | arquitectura, datos, ciencia y riesgos |
| [02-48h-runbook.md](02-48h-runbook.md) | cronograma de hackathon y punto de corte |
| [03-git-workflow.md](03-git-workflow.md) | colaboración, ramas, PR y trazabilidad |
| [04-submission-checklist.md](04-submission-checklist.md) | entrega, demo, referencias y presentación |

## Pendientes de preparación y entrega

- Confirmar las reglas del evento local sobre trabajo previo y declarar con
  transparencia la planificación y el desarrollo realizados antes del hackathon.
  Este repositorio contiene planificación; el código original y la demo final
  deben realizarse de acuerdo con las reglas vigentes.
- Concretar el despliegue público y la visibilidad del repositorio. Para una
  propuesta Space Apps, la recomendación es un repositorio público bajo licencia
  MIT una vez confirmado el cumplimiento de las condiciones 2026.
- Elegir las regiones de la demo a partir de la prueba de acceso a IRSA y
  validar los objetos de demostración; mantener siempre un paquete reducido de
  respaldo con atribución clara.

## Etapa 1: prueba de datos

En PowerShell, con Python 3.11 o posterior instalado:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe test_data.py
```

Si Windows ofrece el lanzador `py`, usar `py -3 -m venv .venv` en el primer paso.
No es necesario activar el entorno virtual.

El script consulta las cuatro colecciones para las coordenadas aproximadas de
Barnard's Star (269.452°, +4.693°), lista las filas por MJD y descarga un único
recorte de 5 arcmin. Son coordenadas de exploración, aún pendientes de verificar
con SIMBAD y de considerar el movimiento propio para cada época.

Guarda en `data/raw/day1/` (excluido de los archivos de código):

- `query_results.csv`: metadatos devueltos por las cuatro consultas.
- `query_spherex_*.vot`: respuestas VOTable originales de IRSA.
- `cutout.fits`: recorte original, con sus extensiones.
- `preview.png`: imagen exploratoria de IMAGE, con percentiles 1–99 y asinh.
- `inspection.json`: procedencia, parámetros, errores por colección, estructura
  FITS, unidades, WCS del centro y estadísticas de FLAGS si existe.

```powershell
.\.venv\Scripts\python.exe test_data.py --help
.\.venv\Scripts\python.exe test_data.py --ra 133.795 --dec -7.245 --output data/raw/wise0855
```

La lista puede quedar truncada al alcanzar `--maxrec` (100 por colección por
defecto); no se interpreta como un inventario completo. Si falla una colección,
se consultan las demás y el informe registra el error. Una respuesta vacía se
distingue de una consulta fallida. Se prefiere QR3 para el recorte y se recurre a
las otras colecciones cuando no hay candidatos allí.

Se consulta SIA con `RESPONSEFORMAT=VOTABLE` y se lee con Astropy. En las
respuestas CSV observadas, `cloud_access` contiene JSON con comas sin escapar;
VOTable permite conservar ese campo sin desplazar el resto de columnas.
El CSV local se genera con el escapado correcto mediante `csv.DictWriter`.
Los antiguos `query_*.csv`, si existen, corresponden a intentos anteriores.

Pruebas del lector de respuestas (sin acceder a IRSA):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La PNG conserva los ejes del detector, con inversión vertical para mostrar el
origen FITS abajo. No está reproyectada al norte ni tiene máscara de calidad
aplicada; no sirve por sí sola para afirmar movimiento o descubrimientos.
Si IMAGE no es 2D o el centro queda fuera del recorte, el script se detiene para
revisar los datos antes de asumir una estructura científica.

Fuentes: [servicio oficial de recortes de IRSA](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html)
y [acceso a datos SPHEREx](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/).
Créditos: NASA/JPL-Caltech; datos SPHEREx alojados por IRSA.

## Etapa 2: pipeline científico

Pipeline **0.2.2 validado** con 18 pruebas y 12 frames reales para cada uno de
los cinco presets. La WCS celestial conserva SIP y la WCS espectral lo excluye.
Barnard, RW Aur y R Dra tienen el centro enmascarado en los 12 frames; Epsilon
Indi B, en 2 de 12; WISE 0855, en ninguno. Estos resultados validan cobertura y
procesamiento; la identificación y visibilidad de las fuentes siguen pendientes.
Python debe ejecutarse desde tu terminal.

Actualizar dependencias y ejecutar todas las pruebas, sin consultas externas:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Construir una secuencia de hasta 12 observaciones del mismo detector:

```powershell
.\.venv\Scripts\python.exe build_sequence.py --preset barnard
```

Los presets disponibles son `barnard`, `epsilon-indi-b`, `wise0855`, `rw-aur` y
`r-dra`. Se consultan en SIMBAD, con propagación de movimiento propio a la época
de referencia cuando está disponible. También se puede introducir un nombre
con `--name`, o coordenadas fijas con `--ra` y `--dec`.

Si SIMBAD Strasbourg no responde, se intenta el mirror de Harvard. Cada servidor
tiene 10 s para conectar y 30 s para las demás fases de red. Se registra qué
servidor proporcionó las coordenadas. Si ambos fallan, el proceso lo informa sin
sustituir las coordenadas del objeto por otras aproximadas. Las resoluciones
exitosas se guardan en `data/raw/targets/` para reutilizarlas.

```powershell
.\.venv\Scripts\python.exe build_sequence.py --preset wise0855 --frames 8
.\.venv\Scripts\python.exe build_sequence.py --ra 269.452 --dec 4.693 --detector SPHEREx-D1
.\.venv\Scripts\python.exe build_sequence.py --verify-presets
```

El ejemplo con coordenadas explora el campo de referencia de la Etapa 1; no
identifica a Barnard en esa época. `--verify-presets` procesa los cinco objetos
secuencialmente y escribe `data/cache/preset_verification.json`. La existencia
de cobertura no demuestra que el objeto sea visible ni que se haya movido.

Cada ejecución indica la carpeta de salida en `data/cache/`, con:

- `manifest.json`: fechas UTC/MJD, detector, colecciones, fuentes, WCS común,
  escala global, longitud de onda del centro y calidad por frame.
- `frames/*.png`: imágenes RGBA, alineadas y con escala visual compartida.
- `aligned/*.fits`: brillo superficial reproyectado, FLAGS y mapa VALID.
- `preview.gif`: animación auxiliar de QA, con fecha y detector.
- `target.json`: coordenadas de referencia y procedencia de la resolución.

Los recortes originales y las respuestas de consulta se conservan en
`data/raw/`. Las secuencias listas se reutilizan por clave de parámetros y
versión del pipeline; `--refresh` vuelve a consultar y descargar conservando las
secuencias previas. Las fechas de consulta quedan registradas. Aún no se aplica
limpieza LRU ni caducidad automática de caché.

Opciones: `--fov` (1–30 arcmin), `--frames` (1–16), `--maxrec` (hasta 10000 por
colección), `--epoch` (año juliano), `--detector`, `--raw-root` y `--cache-root`.
El detector automático prioriza diversidad de fechas; la lista podría estar
truncada por MAXREC. Si quedan menos de tres frames, se informa `partial`.
Una secuencia `ready` puede tener menos frames de los solicitados si no hay
suficientes recortes válidos; el manifiesto conserva los fallos.
Un centro enmascarado no descarta todo el frame: sus píxeles permanecen
transparentes, se registra su calidad y el GIF muestra `CENTER MASKED`.
`ready` describe una secuencia procesada, no la detectabilidad de la fuente central.

Las decisiones de máscara, reproyección y limitaciones se documentan en
[SCIENCE.md](SCIENCE.md). La información espectral no es un cubo de IMAGE:
se consulta la WCS de longitud de onda, y no se mezclan detectores en la secuencia.
