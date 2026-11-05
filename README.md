# orbitlens-spherex

Explorador temporal de imágenes SPHEREx para Planet X and SPHEREx.

## Día 1: prueba de datos

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
