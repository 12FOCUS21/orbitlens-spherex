# Etapa 4 — Render

Un servicio Python sirve la API y la compilación React. La configuración está en
`render.yaml`. Despliegue público confirmado funcionando por el usuario:
https://orbitlens-spherex.onrender.com

**Validación local actual (2026-11-06): 76 pruebas Python pasan, con 3 avisos;
TypeScript/Vite compilan.** Bundle completo: cinco manifiestos, 60 PNG, 60 FITS,
cinco GIF, cinco target.json y el informe portable. La comprobación pública de
lectura del 2026-11-06 confirmó los recursos indicados a continuación; no acredita
el despliegue de archivos de pruebas que no se sirven por HTTP.

## Comprobación pública de lectura — 2026-11-06, aproximadamente 17:01 UTC

Se consultó `https://orbitlens-spherex.onrender.com` directamente con HTTPX,
sin POST, resoluciones de nombres, búsquedas nuevas ni cambios de configuración:

| Recurso | Resultado observado |
| --- | --- |
| `/api/health` | 200; pipeline 0.2.2; cinco presets cacheados |
| `/api/presets` | 200; los cinco presets cacheados con 12 frames cada uno |
| `/` y JS/CSS referenciados | 200; archivos JS/CSS idénticos por SHA-256 al build local |
| `/catalogos.html` | 200; mismo contenido tras normalizar CRLF/LF |
| Cinco manifiestos | 200; esquema mínimo válido, estado ready y 12 frames |
| Primer y último PNG de cada preset | Diez respuestas 200 con firma PNG |
| Primer y último FITS de cada preset | Diez respuestas 200, SHA-256 idéntico al bundle local; imagen primaria 49×49, FLAGS/VALID compatibles y unidad MJy/sr |
| Cinco GIF referenciados | 200 y firma GIF válida |
| Cinco target.json | 200; coordenadas coincidentes con sus manifiestos |

Esto es un muestreo de artefactos públicos, no una descarga de los 60 FITS/PNG ni
una validación científica o de capacidad del servicio. No se ejecutaron análisis
ni se consumió intencionadamente la cuota de búsquedas de producción.

La herramienta de lectura web devolvió inicialmente 503; una petición directa
confirmó 200. No se atribuye una caída del servicio a ese resultado aislado.
El acceso directo a la biblioteca de CDS agotó el tiempo de conexión desde este
entorno. La página de catálogos sí está publicada, pero la carga real de Gaia/
AllWISE no pudo comprobarse desde el entorno del agente: ese timeout no demuestra
una caída global de CDS. La aceptación manual posterior del usuario está debajo.

## Aceptación operativa manual — 2026-11-06

El usuario confirmó: **«Ya he hecho esas pruebas y funciona como debe.»**, tras
la lista de comprobaciones operativas de cuotas/proxy, CDS y móvil físico.
Se registra la aceptación funcional manual del MVP, separada de los GET realizados
por el agente y de la suite automatizada local.

Se aceptan las pruebas indicadas de límite en una conexión, independencia de otra
conexión y ausencia de evasión mediante `X-Forwarded-For`, junto con el funcionamiento
manual de CDS/móvil. No se adjuntaron capturas, trazas HTTP, modelos de dispositivo
ni valores de IP/CIDR; no se inventan esos detalles. La confirmación no equivale
a una auditoría independiente de la infraestructura ni garantiza ausencia de bugs.
El protocolo siguiente se conserva para futuras regresiones.

Registro histórico de Etapa 4: el usuario confirmó 32 pruebas y un bundle de
126 archivos (anterior a la inclusión de GIF y target.json). El agente intentó consultar la web, `/api/health` y
`/api/presets`, pero sus herramientas no pudieron conectar con el servicio.
La confirmación funcional pública procede del usuario; las comprobaciones
detalladas se aceptaron posteriormente con la confirmación del usuario
«Listo, funciona todo». Entonces pasaban 40 pruebas en la suite ampliada.
Etapa 4 completada; verificación pública manual del usuario.

## Preparación local

Con los cinco presets verificados de la Etapa 2:

```powershell
.\.venv\Scripts\python.exe prepare_deploy.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Revisa e incluye `demo/cache` en tu publicación junto con el código y
`frontend/package-lock.json`. Contiene manifiestos, PNG, FITS alineados,
GIF y target.json para los cinco presets; no incluye los recortes originales.
La excepción de `.gitignore` permite incluir esos FITS. Conserva su atribución
NASA/JPL-Caltech e IRSA y las advertencias científicas de los manifiestos.
El preparador es repetible: completa archivos ausentes y acepta archivos idénticos.
Si encuentra diferencias, aborta antes de copiar. Usa `--output demo/cache-new`
para revisar otra versión o `--force` para actualizar archivos diferentes de forma
explícita; no borra archivos ajenos al bundle. Puede reconstruir GIF faltantes
desde PNG sin consultar IRSA.

## Publicación

Después de publicar tú los cambios, crea un Blueprint en Render desde este
repositorio y revisa `render.yaml`. Se propone el plan gratuito, sin disco de
pago. El arranque copia los presets empaquetados a la caché e indexa los cinco
sin solicitudes a IRSA ni SIMBAD. Si faltan, el arranque falla explícitamente.

La caché de búsquedas nuevas es temporal; los presets se restauran desde el
paquete en cada arranque. Un solo worker mantiene coherentes los límites y la
cola en memoria. El servicio gratuito puede suspenderse por inactividad: el
primer acceso puede esperar el arranque incluso con presets empaquetados.

## Comprobación pública histórica aceptada por el usuario

- `/api/health` devuelve 200 y `cached_presets: 5`.
- `/` muestra la aplicación y los cinco presets cargan sus imágenes.
- Reiniciar el servicio y repetir la prueba de presets.
- Comprobar reproducción, slider y tamaño móvil.
- Validar IP recibida tras el proxy antes de dar por verificados los límites
  por visitante; no confiar indiscriminadamente en cabeceras enviadas por clientes.

## Robustez implementada y validada

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
  cuatro colecciones verificadas. La identidad de caché incluye colecciones,
  versión, máscaras y política de rejilla. Si cambias la lista o las máscaras,
  regenera los cinco presets antes de desplegar:
  el arranque de producción exige presets compatibles con esa configuración.
- Las consultas almacenadas se reutilizan hasta siete días cuando se construye
  una secuencia nueva. Las secuencias listas y presets permanecen como muestras
  reproducibles; no se actualizan automáticamente. La interfaz muestra fechas de
  procesamiento y consulta, distintas de la fecha de observación.
- `ORBITLENS_TRUSTED_PROXIES`: direcciones del proxy que Uvicorn puede aceptar
  para interpretar cabeceras reenviadas, como lista de IP/CIDR separada por comas.
  El Blueprint solicita este valor en Render (`sync: false`): configura las
  direcciones reales observadas/confirmadas para ese despliegue, no las IP de
  salida del servicio. Fuera de Render, el valor por defecto sigue siendo
  `127.0.0.1`. No se activa `*`: confiar toda la cadena puede permitir falsificar
  la cuota si el proxy conserva cabeceras del cliente. El comportamiento operativo
  entre visitantes fue aceptado manualmente por el usuario; la configuración
  concreta de IP/CIDR no fue inspeccionada independientemente por el agente.
  Personas detrás de una misma IP pública comparten el límite.

Para comprobar los límites, usa dos conexiones distintas (por ejemplo Wi-Fi y
datos móviles). Desde la primera, once POST seguidos de un preset en menos de
un minuto deben producir 429; desde la segunda, la primera búsqueda debe seguir
respondiendo 202. Espera un minuto antes de repetir. Si ambas comparten el límite,
revisa el proxy y su configuración antes de cambiar direcciones de confianza.
Repite desde una sola conexión enviando diferentes valores falsos de
`X-Forwarded-For`: no deben permitir superar la cuota. Verifica también que el
puerto de Uvicorn no sea accesible directamente fuera del proxy de confianza.

### Protocolo manual de cuota (requiere dos conexiones)

Hacerlo sobre presets cacheados, no sobre coordenadas nuevas. Esperar al menos
60 segundos desde la última búsqueda o análisis de esa IP, cerrar otras pestañas
que hagan POST y no ejecutar un ensayo de carga al mismo tiempo.

1. Desde Wi-Fi, abrir la demo. En las herramientas de desarrollo, pestaña Red,
   conservar el registro y pulsar Barnard once veces, esperando a que termine
   cada petición antes de la siguiente, dentro de un minuto.
2. Comprobar que las primeras diez peticiones son 202 y recuperan caché; la
   undécima debe devolver 429 con `Retry-After`. Si ya había tráfico de esa IP,
   puede agotarse antes: repetir después de un minuto sin POST desde esa IP.
3. Inmediatamente, desde un teléfono con Wi-Fi **desactivado** y datos móviles,
   abrir Barnard una vez. Debe cargar de caché sin compartir el bloqueo. Para
   acreditar HTTP 202, registrar también la respuesta mediante las herramientas
   de red disponibles en el dispositivo; no confundir un estado visual con el código HTTP.
4. Mientras la primera conexión siga limitada, enviar desde ella otra petición
   del mismo preset con `X-Forwarded-For: 203.0.113.123`. Debe seguir devolviendo
   429; cambiar esa cabecera no debe restablecer la cuota. Puede repetirse con
   otro valor, sin generar bucles de carga.
5. Si la segunda conexión también está bloqueada, comprobar primero que tiene
   otra IP pública. Si la cabecera falsa permite eludir la cuota, revisar la
   cadena y la configuración del proxy, no aumentar los límites ni activar `*`.

Para el paso 4, desde la consola de la demo en la conexión A, enviar una única
petición del preset ya cacheado (solo mientras se está comprobando el bloqueo):

```javascript
fetch('/api/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-Forwarded-For': '203.0.113.123' },
  body: JSON.stringify({ preset: 'barnard' }),
}).then(async response => console.log({
  status: response.status,
  retryAfter: response.headers.get('Retry-After'),
  body: await response.json(),
}));
```

La comprobación directa de IP/CIDR y del acceso al puerto corresponde al operador
en Render. No publicar un endpoint que exponga IP o cabeceras internas para esta
prueba. Registrar fecha UTC, versión y resultados sin incluir credenciales.

| Evidencia | Estado |
| --- | --- |
| Límite en conexión A según el protocolo de 202/429 | Funcionamiento esperado confirmado por el usuario; sin traza adjunta |
| Conexión B independiente del bloqueo de A | Confirmado por el usuario |
| Cabeceras falsificadas desde A no eluden el límite | Confirmado por el usuario |
| CDS disponible y uso en móvil físico | Aceptación manual del usuario |
| IP/CIDR concretas y acceso directo al puerto | Sin inspección independiente ni valores registrados; responsabilidad del operador |

Ejecuta las pruebas tras estos cambios y recompila el frontend:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd --prefix frontend run build
```

Los PNG/FITS científicos existentes se conservan. El bundle de este repositorio
ya incorpora los auxiliares faltantes; `prepare_deploy.py` puede completarlos en
otros bundles antiguos. La versión científica sigue siendo 0.2.2; las nuevas
rejillas impares tienen una política propia en la clave de caché.

Fuentes: [FastAPI en Render](https://render.com/docs/deploy-fastapi),
[herramientas del runtime](https://render.com/docs/native-runtimes).
