# Etapa 4 — Render

Un servicio Python sirve la API y la compilación React. La configuración está en
`render.yaml`. Despliegue público confirmado funcionando por el usuario:
https://orbitlens-spherex.onrender.com

Validación local confirmada por el usuario: empaquetado de los cinco presets y
32 pruebas correctas en 1.226 s. El paquete generado ocupa 2,464,219 bytes
(126 archivos). El agente intentó consultar la web, `/api/health` y
`/api/presets`, pero sus herramientas no pudieron conectar con el servicio.
La confirmación funcional pública procede del usuario; las comprobaciones
detalladas siguientes siguen pendientes.

## Preparación local

Con los cinco presets verificados de la Etapa 2:

```powershell
.\.venv\Scripts\python.exe prepare_deploy.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Revisa e incluye `demo/cache` en tu publicación junto con el código y
`frontend/package-lock.json`. Contiene únicamente manifiestos, PNG y FITS
alineados necesarios para los cinco presets; no incluye los recortes originales.
La excepción de `.gitignore` permite incluir esos FITS. Conserva su atribución
NASA/JPL-Caltech e IRSA y las advertencias científicas de los manifiestos.
El preparador rechaza un destino existente para evitar sobrescribir una demo.

## Publicación

Después de publicar tú los cambios, crea un Blueprint en Render desde este
repositorio y revisa `render.yaml`. Se propone el plan gratuito, sin disco de
pago. El arranque copia los presets empaquetados a la caché e indexa los cinco
sin solicitudes a IRSA ni SIMBAD. Si faltan, el arranque falla explícitamente.

La caché de búsquedas nuevas es temporal; los presets se restauran desde el
paquete en cada arranque. Un solo worker mantiene coherentes los límites y la
cola en memoria. El servicio gratuito puede suspenderse por inactividad: el
primer acceso puede esperar el arranque incluso con presets empaquetados.

## Comprobación pública pendiente

- `/api/health` devuelve 200 y `cached_presets: 5`.
- `/` muestra la aplicación y los cinco presets cargan sus imágenes.
- Reiniciar el servicio y repetir la prueba de presets.
- Comprobar reproducción, slider y tamaño móvil.
- Validar IP recibida tras el proxy antes de dar por verificados los límites
  por visitante; no confiar indiscriminadamente en cabeceras enviadas por clientes.

## Robustez implementada; validación Python y pública pendiente

- `ORBITLENS_CACHE_BYTES`: presupuesto conjunto de `data/raw` y `data/cache`,
  por defecto 2 GiB. Se limpia al arrancar y cada minuto cuando no hay búsquedas
  activas, por antigüedad del último uso. Se conservan los cinco presets, los
  resultados de trabajos aún vigentes y los archivos usados en la última hora.
  El presupuesto es blando: las descargas en curso pueden superarlo. Si la
  limpieza no libera espacio, nuevas búsquedas reciben 429; la demo sigue disponible.
  Durante la limpieza, los resultados que no son presets pueden responder 503
  brevemente para evitar servir archivos que están siendo eliminados.
- IRSA: máximo tres intentos con pausas de 1 y 2 segundos para transporte y
  HTTP 408/429/500/502/503/504. Las consultas nuevas usan conexión de 10 s y
  lectura de 30 s. Son límites por fase de red, no un plazo total del trabajo.
  Los errores 4xx permanentes no se reintentan. Respuestas FITS inválidas se
  vuelven a descargar antes de descartar el candidato.
- `ORBITLENS_COLLECTIONS`: lista ordenada, separada por comas; por defecto las
  cuatro colecciones verificadas. La identidad de caché incluye colecciones y
  versión. Si cambias la lista, regenera los cinco presets antes de desplegar:
  el arranque de producción exige presets compatibles con esa configuración.
- Las consultas almacenadas se reutilizan hasta siete días cuando se construye
  una secuencia nueva. Las secuencias listas y presets permanecen como muestras
  reproducibles; no se actualizan automáticamente. La interfaz muestra fechas de
  procesamiento y consulta, distintas de la fecha de observación.
- `ORBITLENS_TRUSTED_PROXIES`: direcciones del proxy que Uvicorn puede aceptar
  para interpretar cabeceras reenviadas. Por defecto `127.0.0.1`. No se establece
  `*` automáticamente. La configuración efectiva de Render y la separación de
  visitantes deben comprobarse en producción antes de declarar verificados los
  límites por IP. Personas detrás de una misma IP pública comparten el límite.

Para comprobar los límites, usa dos conexiones distintas (por ejemplo Wi-Fi y
datos móviles). Desde la primera, once POST seguidos de un preset en menos de
un minuto deben producir 429; desde la segunda, la primera búsqueda debe seguir
respondiendo 202. Espera un minuto antes de repetir. Si ambas comparten el límite,
revisa el proxy y su configuración antes de cambiar direcciones de confianza.

Ejecuta las pruebas tras estos cambios y recompila el frontend:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd --prefix frontend run build
```

No hace falta regenerar el paquete de presets si conservas las cuatro colecciones
por defecto: el formato científico y la versión del pipeline siguen siendo 0.2.2.

Fuentes: [FastAPI en Render](https://render.com/docs/deploy-fastapi),
[herramientas del runtime](https://render.com/docs/native-runtimes).
