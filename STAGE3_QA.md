# Etapa 3 — Validación local

## Estado de las comprobaciones

Implementados `api.py`, `coordinates.py`, `frontend/` y 12 pruebas nuevas en
`tests/test_api.py` (30 pruebas en total con las 18 de la Etapa 2). Estas nuevas
pruebas no usan SIMBAD ni IRSA: comprueban validación de entrada, caché,
respuesta antes del cómputo, polling, deduplicación, tres trabajos simultáneos,
posición de cola, límites 429, resolución cacheada, estados y acceso a archivos.

La ejecución sigue pendiente en la terminal del usuario. El entorno del agente
no tiene acceso al Python instalado y el intento de instalar paquetes web falló
con `EACCES` al acceder a `registry.npmjs.org`. Esto es una limitación del entorno
del agente; no demuestra un fallo en la instalación del usuario. No se han
ejecutado las 30 pruebas ni la compilación de Vite ni una sesión real de navegador.

La evidencia de los datos reales de la Etapa 2 sigue en `VALIDATION.md`. La API
indexa esos resultados al arrancar; no debe redescargarlos para abrir los presets.

Comprobado con Node en este entorno: los JSON de configuración del frontend
se leen correctamente, y las cinco rutas del informe apuntan a manifiestos
`ready` del pipeline 0.2.2 con 12 frames cada uno. Existen los 60 PNG y los 60
FITS referenciados. Esto comprueba los archivos de entrada, sin sustituir la
ejecución de la API ni la compilación de TypeScript.

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
