# Etapa 3 — Validación local

## Estado de las comprobaciones

Implementados `api.py`, `coordinates.py`, `frontend/` y 12 pruebas nuevas en
`tests/test_api.py` (30 pruebas en total con las 18 de la Etapa 2). Estas nuevas
pruebas no usan SIMBAD ni IRSA: comprueban validación de entrada, caché,
respuesta antes del cómputo, polling, deduplicación, tres trabajos simultáneos,
posición de cola, límites 429, resolución cacheada, estados y acceso a archivos.

La ejecución en la terminal del usuario confirmó:

- **30 pruebas correctas**, en 1.036 s.
- `npm install`: 22 paquetes auditados, sin vulnerabilidades reportadas.
- TypeScript sin errores y Vite 7.3.7: compilación correcta en 680 ms.
- Uvicorn arrancó con un worker; la página, JavaScript, CSS y `/api/presets`
  respondieron HTTP 200.
- Barnard respondió HTTP 202 a la búsqueda y HTTP 200 al manifiesto y a sus
  12 PNG del resultado `76e5f3e44ac9db0b035cc43d`.

Estas evidencias proceden de la salida compartida por el usuario; no verifican
por sí solas los controles visuales. Al intentar la revisión de navegador, la
herramienta informó `No browser is available` y la lista de navegadores estaba
vacía. La revisión visual permanece pendiente hasta conectar un navegador o
recibir la comprobación manual del usuario.

Mensajes revisados de esa ejecución:

- El traceback `Private C:/some/path` es deliberado en una prueba de errores;
  esa prueba pasó. El mensaje real al cliente no incluye la ruta simulada.
- Los resultados `b09a4a82676bca049d0566a5` y `be9921f19bf9a58c2aab6d44`
  se omiten por incompatibilidad o falta de artefactos; no impiden el arranque.
- La ruta de salud es **`/api/health`**, no `/health`. El comprobador que consulta
  repetidamente `/health` debe usar la ruta correcta.
- Falta `favicon.ico`; su HTTP 404 no afecta al reproductor.
- Los avisos de deprecación de Starlette y de distancia de ERFA no hicieron
  fallar las pruebas. No se cambiaron dependencias ni se ocultaron avisos.

La evidencia de los datos reales de la Etapa 2 sigue en `VALIDATION.md`. La API
indexa esos resultados al arrancar; no debe redescargarlos para abrir los presets.

Comprobado con Node en este entorno: los JSON de configuración del frontend
se leen correctamente, y las cinco rutas del informe apuntan a manifiestos
`ready` del pipeline 0.2.2 con 12 frames cada uno. Existen los 60 PNG y los 60
FITS referenciados. Esto comprueba los archivos de entrada, sin sustituir la
revisión interactiva de los controles.

## Arranque

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm.cmd install
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000 --workers 1
```

Abrir http://127.0.0.1:8000. En otra terminal se puede comprobar:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/presets
```

La salud debería informar `cached_presets: 5` con el informe y los archivos
de la última validación de Etapa 2 presentes. `npm install` genera el lockfile
de dependencias para que el usuario lo incluya con el código.

## Comprobaciones manuales pendientes

- [ ] Los cinco presets muestran «12 imágenes · en caché» y abren sin consultas
  externas. Revisar Epsilon Indi B y WISE 0855 primero; su centro es menos afectado.
- [ ] Barnard, RW Aurigae y R Draconis avisan que el centro está enmascarado
  en 12/12; Epsilon Indi B en 2/12. Los huecos conservan transparencia.
- [ ] Play/pausa, deslizador, 1/2/4 fps y bucle funcionan. Al desactivar el bucle,
  la reproducción se detiene en la última imagen; volver a reproducir reinicia.
- [ ] La fecha UTC/MJD y la longitud de onda cambian con el frame mostrado.
  Las imágenes mantienen norte arriba, este a la izquierda y escala global.
- [ ] Se muestra que igual detector no implica igual banda y que `ready`
  describe procesamiento, no detectabilidad.
- [ ] El aviso de MAXREC aparece para R Draconis; el manifiesto conserva
  consultas y fallos.
- [ ] El enlace al PNG, al FITS alineado y al manifiesto responde; `data/raw/`
  no es público. La API desconocida devuelve 404.
- [ ] RA/Dec decimal y sexagesimal equivalentes abren el mismo campo. RA=360,
  Dec=91, texto inválido o campos vacíos dan error comprensible.
- [ ] Una búsqueda por nombre usa SIMBAD y conserva la época de referencia.
  Si falla el servicio, aparece un error recuperable sin inventar coordenadas.
- [ ] Una búsqueda nueva no bloquea `/api/health` ni el polling. Muestra
  resolución, procesamiento y, si corresponde, posición de cola.
- [ ] Un resultado `empty` ofrece otro detector o un preset; `partial` mantiene
  inspección con deslizador y no activa reproducción.
- [ ] Revisar ventana estrecha (~390 px), navegación con teclado, etiquetas
  de campos, foco y contraste de avisos.
- [ ] Repetir una búsqueda terminada usa caché; tras reiniciar Uvicorn se
  recuperan las secuencias y los presets desde disco.

La carga de 10 pestañas y el despliegue público corresponden a etapas siguientes.
Medir el objetivo de POST <100 ms en la máquina/servidor real; no se ha medido aquí.
