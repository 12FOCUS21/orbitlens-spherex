# Etapa 7 — regresión y ensayo de entrega

## Comprobación automática local

Tras instalar las dependencias Python, restaurar también las dependencias de
desarrollo frontend con `npm.cmd --prefix frontend ci`.

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe verify_demo.py
.\.venv\Scripts\python.exe verify_release.py
npm.cmd --prefix frontend run test:e2e
```

`verify_release.py` comprueba la aplicación mediante HTTP en proceso, sobre una
copia temporal de `demo/cache`. No inicia Uvicorn, no consulta IRSA/SIMBAD/CDS y
no modifica los archivos ni los mtimes del bundle original. No ejecuta JavaScript.

Comprueba:

- Diez visitantes simulados mediante solicitudes HTTP concurrentes a portada,
  salud y presets, sin errores. Los recursos JS/CSS de la portada también sirven.
- Los cinco presets `ready` se recuperan de caché sin construir trabajos nuevos.
- Las rutas de los 60 PNG y 60 FITS responden con sus firmas de archivo esperadas;
  los cinco GIF y cinco target.json existen y conservan el centro del manifiesto.
- Dos campos consultados dos veces por sus coordenadas/opciones devuelven los
  mismos resultados que sus presets, sin nuevas resoluciones ni descargas.
- Diez búsquedas de una misma IP se aceptan y la undécima devuelve 429 con
  `Retry-After`. Los GET no consumen esa cuota.

**Límite de esta evidencia:** no son diez pestañas reales, no mide capacidad de
Render ni verifica separación de IP tras su proxy. La lectura científica de los
FITS se verifica por separado con `verify_demo.py`. Aladin requiere QA con red.

## Regresión funcional en navegador — 2026-11-06

**20 casos correctos en Edge 156.0.4314.58 headless en Windows**: diez pruebas
en escritorio (1365×900) y las mismas diez a 390×844 con emulación móvil.
No se detectaron excepciones JavaScript no controladas ni desbordamiento horizontal
del documento en los estados comprobados. No es una prueba en un móvil físico.

La suite está en `frontend/e2e/viewer.spec.ts` y usa Playwright como dependencia
de desarrollo. `npm.cmd --prefix frontend run test:e2e` recompila primero la app
mediante el hook `pretest:e2e`, arranca un Uvicorn exclusivo en `127.0.0.1:8765`,
y comprueba:

- Carga de los cinco presets y de sus canvas.
- Enlace de WISE 0855 abierto en otra página, con centro, opciones y etiqueta.
- Cambio espectral que pausa la reproducción y conserva el índice temporal;
  apertura del detalle de FLAGS y distinción entre máscara y cobertura alineada.
- Diferencia A−B con inversión de colores verificada píxel a píxel en navegador.
- Media de RW Aur y curvas centrales con 12, 10 y 0 valores válidos.
- Enlaces inválidos y parejas incompatibles rechazados sin enviar el POST correspondiente.
- Fallo de CDS con mensaje y enlace alternativo.
- Estados partial y ready de dos frames, con animación deshabilitada. Estos dos
  estados usan respuestas controladas; no son búsquedas nuevas en IRSA.
- Diez pestañas reales del navegador cargando Barnard simultáneamente.

El servidor de `tests/browser_server.py` copia el bundle a un directorio temporal
y prohíbe resolver nombres o construir secuencias nuevas. Su cuota es 500/minuto
**solo para estas pruebas**; no modifica los límites del servidor normal. Los
límites de producción no se validan con esta suite. Las fuentes remotas y CDS
se bloquean deliberadamente: no se verifica carga correcta de catálogos ni la
tipografía descargada. Las trazas/capturas de fallos se guardan en
`frontend/test-results/`, excluido del repositorio.

En Windows se usa Edge o Chrome instalado. Para otro ejecutable:

```powershell
$env:ORBITLENS_BROWSER = 'C:\ruta\al\navegador.exe'
npm.cmd --prefix frontend run test:e2e
```

Sin un navegador detectado se usa Chromium de Playwright; instalarlo con
`npm.cmd --prefix frontend exec -- playwright install chromium`. El Python por
defecto es el de `.venv`; `ORBITLENS_TEST_PYTHON` permite indicar otro ejecutable.
`ORBITLENS_E2E_PORT` cambia el puerto local. No se reutiliza un servidor existente.

## Lectura pública posterior — 2026-11-06

Salud, cinco presets, frontend y auxiliares respondieron 200. El JS/CSS coincide
con el build local y se comprobó el primer y último PNG/FITS de cada preset;
los diez FITS coinciden por SHA-256 con el bundle local. Detalle en DEPLOYMENT.md.
El agente no envió POST de producción ni probó cuotas. La biblioteca de CDS
agotó el tiempo de conexión desde este entorno; no se considera prueba de una
caída global ni de un defecto del visor. Posteriormente el usuario confirmó el
funcionamiento esperado de las pruebas operativas indicadas: cuotas/proxy, CDS
y móvil. Es aceptación manual, sin trazas o dispositivos adjuntos; no se atribuye
a la automatización local. Detalle y límites en DEPLOYMENT.md.

## Matriz de 15 casos

Los casos con coordenadas nuevas pueden consultar IRSA: ejecutarlos manualmente
de forma secuencial, no desde un script de carga. No asumir cobertura donde no se
ha comprobado. Registrar versión desplegada, fecha, dispositivo y resultado.

| # | Caso | Resultado esperado / evidencia | Estado |
| --- | --- | --- | --- |
| 1 | Barnard, 12 frames | Caché ready; 12 centros enmascarados. Diferencia 1−7 invierte signo al intercambiar A/B. | HTTP, cálculo y navegador local comprobados |
| 2 | Epsilon Indi B | Caché ready; curva con 10 valores y 2 ausentes, sin sustituir por cero. | HTTP, cálculo y navegador local comprobados |
| 3 | WISE 0855 | Caché ready; curva con 12 valores. No afirmar detectabilidad por tener centro válido. | HTTP, cálculo y navegador local comprobados |
| 4 | RW Aurigae, apilado 1 y 2 | Media con dos contribuciones por píxel válido y cobertura aproximada del 95,13 %. | HTTP, cálculo y navegador local comprobados |
| 5 | R Draconis, colecciones profundas | Caché ready; advertencia de inventario truncado cuando corresponda; centros ausentes. | Carga en navegador y cálculo comprobados; revisión del aviso pendiente |
| 6 | `/?ra=0&dec=0&fov=5&frames=3` | Aceptar ceros; mostrar resultado o vacío según cobertura, nunca error por falsedad de cero. | Enlace probado; cobertura real pendiente |
| 7 | Polo norte: RA=0, Dec=90 | Entrada válida; WCS o ausencia de cobertura tratados sin 500. | Validación cubierta; consulta real pendiente |
| 8 | Polo sur: RA=0, Dec=−90 | Entrada válida; no asumir imágenes disponibles. | Validación cubierta; consulta real pendiente |
| 9 | RA=`08h55m10.831s`, Dec=`-07d14m42.53s` | Equivalencia con grados de esa posición; no confundir con el centro propagado del preset WISE. | Conversión probada; visual pendiente |
| 10 | Resultado partial controlado, dos frames de doce solicitados | Preservar estado y máscaras; permitir inspección manual, no animación. No depender de encontrar un campo real partial. | API y navegador con fixture comprobados |
| 11 | Solicitar y obtener uno o dos frames | Estado ready; animación deshabilitada si hay menos de tres; conservar opciones al compartir. | Pipeline y enlaces probados; navegador con dos frames controlados comprobado |
| 12 | RA=360, Dec=91, booleanos, minutos=60 o frames=17 | Rechazo 422 en API; URL inválida con mensaje legible sin POST cuando falla validación local. | API y rechazo de enlaces inválidos en navegador comprobados |
| 13 | Longitud de onda desconocida / bandas incompatibles | Desconocidas al final del selector; no permitir diferencia/apilado incompatible ni inventar bandas. | Orden espectral probado; bloqueo de pareja incompatible en navegador comprobado |
| 14 | Aladin sin CDS disponible | Mantener visor SPHEREx, mostrar error y enlace externo alternativo; no afirmar catálogos cargados. | Fallo controlado automatizado; funcionamiento con CDS aceptado manualmente por el usuario |
| 15 | Diez visitas y dos campos repetidos; cuotas | Smoke local correcto. Repetir con diez pestañas; en Render usar dos conexiones y probar cabeceras falsificadas. | HTTP y diez pestañas locales comprobados; pruebas operativas en Render aceptadas por el usuario |

Repetir los controles de enlaces, selector, FLAGS y análisis a **390 px** siguiendo
`STAGE6_QA.md`. La suite de navegador comprueba esos controles y el ancho del
documento; el usuario aceptó el funcionamiento manual en móvil. No se registraron
modelos o tamaños físicos concretos ni una auditoría exhaustiva de diseño/tipografía.

## Tres ensayos de demo

1. Abrir Barnard y explicar por qué ready no significa detección. Mostrar fecha,
   banda y máscara antes de interpretar la diferencia.
2. Mostrar la media de RW Aur y la curva de WISE 0855; señalar fondo, bandas,
   ausencia de incertidumbres y límites de interpretación.
3. Copiar un enlace, abrirlo en ventana privada y revisar Gaia/AllWISE en Aladin.
   Si CDS falla, continuar con los datos locales sin atribuir identificaciones.

| Ensayo | Versión / dispositivo | Resultado | Incidencias |
| --- | --- | --- | --- |
| 1 | Pendiente | Pendiente | — |
| 2 | Pendiente | Pendiente | — |
| 3 | Pendiente | Pendiente | — |

No se añaden espectros al vuelo ni combinaciones de detectores antes de cerrar
la regresión y revisar su diseño científico. Las pruebas operativas de cuotas y
proxy se aceptaron manualmente por el usuario según DEPLOYMENT.md. Eso no completa
los tres ensayos ni convierte el MVP en una validación científica o auditoría de seguridad.
