# PLAN — Planet X and SPHEREx (NASA Space Apps 2026)

## Estado vigente — 2026-11-06

- Interfaz de trabajo: `web/` vanilla, servida por FastAPI. Integra el visor de
  ayer con las funciones de `main`: análisis, selector espectral, enlaces exactos,
  máscaras y vista externa Gaia/AllWISE. `frontend/` conserva la versión React
  histórica; Render ya no la compila. Validación local: 77 pruebas Python,
  10 pruebas Node, `verify_demo.py`, `verify_release.py` y regresión Edge de
  `npm.cmd --prefix frontend run test:web`.

- 77 pruebas Python pasan, avisos conocidos; la versión React histórica compilaba con TypeScript/Vite.
- Etapa 6: enlaces y orden espectral tienen 10 pruebas frontend con runner nativo
  de Node (ahora sobre `web/`). Implementación del MVP aceptada funcionalmente;
  no incluye comparación
  científica conjunta entre detectores. Regresión en STAGE6_QA.md.
- Etapa 7: smoke HTTP local reproducible en `verify_release.py`, con diez visitas
  concurrentes, artefactos completos, dos campos repetidos y cuota local. Matriz
  de 15 casos en STAGE7_QA.md; los tres ensayos de presentación siguen pendientes.
- Regresión funcional local: 20 casos E2E correctos en Edge headless, escritorio
  y viewport móvil de 390 px, incluidos diez tabs reales. El usuario confirmó las
  pruebas operativas manuales de cuotas/proxy, CDS y móvil; no se atribuyen a E2E.
- Lectura pública comprobada el 2026-11-06: salud y cinco presets 200; JS/CSS
  coinciden con el build local; diez PNG/FITS muestreados y cinco GIF/target.json
  accesibles. El agente no hizo POST de producción; aceptación manual posterior
  del usuario documentada en DEPLOYMENT.md.
- Demo: cinco manifiestos ready, 60 PNG, 60 FITS, cinco GIF y cinco target.json.
- Corregidos cachés VOT/FITS defectuosos, errores HTTP de análisis, validación de
  entradas/manifiestos, claves con máscaras, caché negativa de 60 s y limpieza.
- MVP exploratorio aceptado funcionalmente por el usuario. Render solicita proxies
  explícitos; las cuotas entre conexiones y la resistencia a cabeceras falsificadas
  se aceptaron por confirmación manual, sin auditoría independiente de IP/CIDR.
- Las cifras y restricciones de ejecución que siguen son registros históricos,
  no el estado vigente. Identidades, detecciones y movimientos no están validados
  científicamente. Video, ensayos y submission no se consideran terminados.

> **REGISTRO HISTÓRICO de etapas previas (el estado vigente está arriba):**
> - Estado: ETAPAS 1, 2 y 3 completadas: datos, pipeline y web local.
>   Pipeline 0.2.2: 18 pruebas pasan; cinco presets con 12 frames cada uno.
>   Datos revisados: 60 PNG, 60 FITS alineados y cinco GIF; sin artefactos faltantes.
>   Barnard, RW Aur y R Dra: centro enmascarado en 12/12; Epsilon Indi B: 2/12;
>   WISE 0855: 0/12. Esto no confirma detectabilidad ni movimiento de las fuentes.
>   Resultado completo en VALIDATION.md; pendientes científicos documentados allí.
>   Python solo se ejecuta desde la terminal del usuario por restricciones del entorno del agente.
> - Lo que se verificó en vivo (fecha 2026-11-05): endpoint SIA2 de IRSA funciona,
>   filas reales con access_url/detector/MJD; cutouts vía `access_url?center=RA,Dec&size=grados`;
>   WISE 0855 tiene datos en qr2 pero CERO en qr3 → fallback entre 4 colecciones OBLIGATORIO.
> - Decisión de alcance: cubrir TODAS las consideraciones del enunciado (8/8) + extras
>   funcionales. El enunciado NO pide "escalabilidad" literal; robustez = semáforo +
>   límites por IP + caché compartida + presets cálidos (todo sin Redis/Postgres).
> - Stack: React+Vite servido por FastAPI (UN servicio en Render). Deploy temprano (etapa 4).
> - Equipo: el usuario programa solo etapas 1–7; etapas 8–9 (14–15 nov, hackathon) los 5 juntos
>   (QA fantasma, video, pitch, submission). Compañeros SIN experiencia técnica.
> - ETAPA 3 aceptada funcionalmente: api.py, coordinates.py y frontend React/Vite/TypeScript.
>   El usuario confirmó las 30 pruebas correctas, compilación TypeScript/Vite,
>   arranque de Uvicorn y entrega de los 12 PNG de Barnard con HTTP 200.
>   El usuario confirmó manualmente «Todo está funcional» tras probar controles.
>   El agente no realizó QA visual automatizada por error interno `timeoutMs`.
>   Comandos en README.md y lista de revisión en STAGE3_QA.md.
> - ETAPA 4 completada: 40 pruebas pasan en 1.241 s; frontend compilado.
>   El usuario confirmó «Listo, funciona todo» tras la lista de validación pública.
>   La validación de producción es manual del usuario; el agente no pudo conectar.
> - Siguiente paso concreto: ETAPA 5, diferencia, apilado y curva de luz. Conservar la regresión
>   ampliada/móvil de STAGE3_QA.md para producción. Los presets se cargan desde
>   data/cache/preset_verification.json sin consultas externas al arrancar.
> - Consultar SIA en VOTABLE con Astropy: el CSV remoto contiene JSON sin escapar.
>   IMAGE es 2D (49×49 en el recorte probado); no es un cubo espectral.
> - Fuentes contextuales del reto en esta carpeta: `chat.md` (conversación previa con otra
>   IA; el enunciado ahí estaba TRUNCADO — el plan ya lo corrijo con las consideraciones 5–8).

> Estrategia: 7 días de build en solitario + 2 días oficiales de hackathon con el equipo
> (integración, QA, video, pitch y submission). Objetivo: máxima funcionalidad,
> no complejidad — cubrir todo lo pedido, todo lo sugerido, y algo extra.

## Verificado (datos reales de IRSA)

- Endpoint SIA2: `https://irsa.ipac.caltech.edu/SIA?COLLECTION=<coleccion>&POS=circle+RA+DEC+RADIO&RESPONSEFORMAT=VOTABLE`
  - Colecciones: `spherex_qr3`, `spherex_qr3_deep`, `spherex_qr2`, `spherex_qr2_deep`
  - `MAXREC=n` funciona; `limit` NO (usar MAXREC).
- Cada fila devuelve `access_url` (un FITS de ~60–72 MB por imagen), `energy_bandpassname`
  (SPHEREx-D1…D6), `t_min`/`t_max` (MJD), `s_region` (polígono), `t_exptime` (≈113.6 s).
- Cutouts: `access_url?center=RA,Dec&size=grados` (IRSA cutout service, sobre la copia on-prem).
- HUECO EN DATOS: WISE 0855 (133.795, -7.245) tiene datos en `spherex_qr2` pero CERO en
  `spherex_qr3` en radio 0.5°. **El fallback automático entre las 4 colecciones es obligatorio.**
- Datos se ingieren semanalmente; SIA2 se retrasa ~1 día. Mensaje de frescura en la UI.

## Alcance ampliado (lectura COMPLETA del enunciado — no estaba en chat.md)

El enunciado NO exige "escalabilidad" literal, pero cita que proyectos previos con esta
técnica tuvieron **cientos de miles de voluntarios** y pide "ayudar a que **tantas personas
como sea posible** hagan descubrimientos". Conclusión: robustez de uso masivo sí, reparto
de carga tipo Netflix no.

Consideraciones adicionales del enunciado (la versión de chat.md estaba truncada):
- #5 Superponer catálogos de otros telescopios (Gaia, WISE) sobre las imágenes
- #6 Coordenadas en la URL → enlaces compartibles/embeddable: `/?ra=133.795&dec=-7.245&fov=10`
- #7 Mostrar metadatos de FLAGS (contaminación/calidad) por frame
- #8 Usar herramientas existentes: Astropy (✓ ya en el stack) y Aladin (CDS) como opción

## Estabilidad para uso masivo (sin Redis ni infra extra)

1. **Semáforo de cómputo**: máx. 3 búsquedas pesadas simultáneas en el proceso
   (`asyncio.Semaphore`). El resto espera su turno con estado en la UI ("en cola: 2 delante").
   Esto protege IRSA y al servidor — y es responsabilidad ante datos compartidos, que puntúa.
2. **Límite por IP**: máx. 2 búsquedas pesadas en curso y ~10 por minuto por IP → HTTP 429
   con mensaje amable. Evita que un script de un solo usuario sature la cola.
3. **Caché primero**: si la cache_key ya existe, respuesta instantánea sin tocar IRSA.
   La mayoría de usuarios reales repite coords de los presets → el 80% del tráfico ni computa.
4. **Presets pre-calculados al despegar** (warm-up al arrancar el servidor).
5. **Status separado del cómputo**: `POST /api/search` encola y devuelve `job_id` en menos de
   100 ms; un `GET /api/status/{job_id}` barato hace polling. El cómputo corre en
   `BackgroundTasks` bajo el semáforo. Nada de procesar nada sincrónicamente en la request.
6. **Protección de límites**: FOV 1–30 arcmin, ≤16 frames, tamaño de frames web por medir
   (el FITS de 5 arcmin probado pesa 3.99 MB; no asumir ≤100 KB), disco con
   limpieza LRU (menu de la cache > 2 GB → borrar los más viejos).
7. **Enunciado #6**: leer coords de la URL también sirve a la estabilidad — las demos
   de los jueces golpean URLs compartidas que YA están en caché.
8. Documentar estas decisiones en el README ("listo para uso público").

## Stack

- Frontend: React + Vite + TypeScript → `npm run build` → servido por FastAPI (StaticFiles).
- Backend: Python + FastAPI + Astropy + NumPy + reproject + Pillow.
- Despliegue: UN servicio en Render/Fly.io (backend + frontend juntos, cero CORS).
- Persistencia: cache_key → archivo JSON/PNG/WebP en disco temporal. Sin Postgres, sin Redis.

---

## ETAPA 1 — Prueba de datos
- [x] Entorno Python (venv) + dependencias mínimas de `requirements.txt`.
  `reproject`, FastAPI y uvicorn se incorporarán cuando se necesiten.
- [x] Script `test_data.py`:
  - [x] Consulta las 4 colecciones para Barnard's Star (RA≈269.452, Dec≈+4.693)
  - [x] Lista resultados ordenados por fecha, muestra detector/banda/MJD/access_url
  - [x] Descarga UN cutout real con `?center=&size=`
  - [x] Abre con `astropy.io.fits` e imprime estructura de extensiones: IMAGE es 2D.
  - [x] Exporta una PNG
- [x] **Entregable:** tu primera imagen real de SPHEREx en el disco.

Validación del 2026-11-05, ejecutada por el usuario y revisada en disco por el agente:
- Cuatro pruebas del lector VOTable pasan; consultas sin errores (200 filas en total,
  QR3 y QR2 truncadas a 100 cada una; ambas colecciones profundas vacías).
- Recorte QR3/D6 del 2026-08-16, MJD 61268.630812, de 5 arcmin: 3,985,920 bytes.
- Extensiones: PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI, EPSF y WCS-WAVE.
  IMAGE: 49×49, float32, MJy/sr; todos sus píxeles son finitos.
- Centro dentro del WCS: (24.0061, 23.6466). PNG revisada visualmente, 2,426 bytes.
- FLAGS es distinto de cero en el 100% de los píxeles. La Etapa 2 confirmó SOURCE
  en todos ellos y añadió una máscara por bits; no usar `FLAGS != 0` como máscara global.
- Coordenadas de esta primera prueba aproximadas. La Etapa 2 resolvió los presets
  con SIMBAD y propagó el movimiento propio; la identificación visual sigue pendiente.
- La imagen es espacial 2D; no implementar el selector espectral como planos de un
  cubo. Revisar la información de longitud de onda antes de diseñar ese selector.

## ETAPA 2 — Pipeline científico
- [x] Implementación preparada: `spherex_pipeline.py`, `build_sequence.py`, `targets.py`.
- [x] Dependencia reproject e instrucciones de ejecución en README; decisiones en SCIENCE.md.
- [x] Instalar reproject y ejecutar las primeras 13 pruebas: todas pasan.
- [x] Ejecutar las 15 pruebas tras añadir fallback de SIMBAD: todas pasan.
- [x] Ejecutar las 17 pruebas tras corregir el rechazo por centro enmascarado: todas pasan.
- [x] Ejecutar las 18 pruebas tras corregir SIP en la WCS espectral y regenerar datos: pasan.
- [x] Mismo pipeline con 8–12 cutouts del MISMO detector: 12 frames por preset (0.2.2).
- [x] Reproyección a WCS común (`reproject`)
- [x] Estiramiento GLOBAL (mismos percentiles para todos los frames, asinh)
- [x] Frames WebP/PNG + `manifest.json` (fecha, MJD, banda, detector, URL IRSA, parámetros, versión pipeline)
- [x] **Verificar cobertura y procesamiento de los campos de los 5 objetos:**
  Barnard's Star, Epsilon Indi B, WISE 0855 (QR2), RW Aurigae, R Draconis.
- [x] Anotar en este archivo qué colección y detector permitió procesar cada campo.

La validación real del procesamiento está completada (informe UTC 2026-11-06).
La identidad, detectabilidad y movimiento de las fuentes no se han confirmado.
El pipeline implementa selección
temporal de un detector, deduplicación de exposiciones, margen espacial de recorte,
reproyección bilineal, máscara conservadora por bits, escala global, PNG RGBA,
FITS alineados, GIF de QA y manifiesto. Los recortes y consultas se reutilizan en
disco; una secuencia lista se identifica por parámetros y versión del pipeline.

SIMBAD/TAP resuelve los presets con movimiento propio hacia una época de referencia
cuando hay datos. Esto no confirma identificación ni detectabilidad. Los presets
no usan silenciosamente las coordenadas aproximadas antiguas si SIMBAD falla.
`--verify-presets` genera el informe reproducible para revisar los cinco objetos.
Tras el timeout de SIMBAD reportado por el usuario, el resolver intenta Strasbourg
y después Harvard, con 10 s para conectar y 30 s para las demás fases de red.
Registra el servidor que respondió y los fallos anteriores en target.json.

En la ejecución real posterior, Harvard respondió y se obtuvieron 119 filas QR3
y 240 QR2 sin truncamiento. El detector automático fue D3. Los recortes descargados
tenían entre 70.8% y 95.7% de cobertura válida, pero la condición adicional de centro
válido los rechazó; dos solicitudes acabaron en HTTP 503. Se corrigió esa condición
en 0.2.1: se conserva el campo si cumple la cobertura mínima y se registra el centro
inválido, que sigue enmascarado. El GIF lo señala. Se reutilizan los recortes ya
descargados; no hace falta --refresh. El usuario validó esta corrección con 17
pruebas y una secuencia de 12 frames. PNG inicial revisada y artefactos comprobados.

El aviso SIP repetido provenía de la WCS espectral W: el tutorial oficial de IRSA
indica que debe excluir la distorsión SIP del WCS celestial. Se corrige en 0.2.2
mediante una copia de la cabecera sin coeficientes SIP, conservando intacta la
transformación celestial. Las longitudes de onda del manifiesto 0.2.1 deben
regenerarse; no usar esos valores como calibración científica.

| Objeto | Colecciones en secuencia | Detector | Frames | Centro enmascarado |
| --- | --- | --- | --- | --- |
| Barnard | QR2, QR3 | D3 | 12 | 12/12 |
| Epsilon Indi B | QR2, QR3 | D2 | 12 | 2/12 |
| WISE 0855 | QR2 | D2 | 12 | 0/12; detectabilidad en esta banda no confirmada |
| RW Aurigae | QR2, QR3 | D5 | 12 | 12/12 |
| R Draconis | QR2, QR2 deep, QR3 deep | D1 | 12 | 12/12 |

Las 60 lecturas espectrales se calcularon sin error registrado. Un HTTP 503 en
WISE 0855 se recuperó mediante otro candidato. R Dra depende de colecciones
profundas: QR3 general no devolvió filas y QR2 deep alcanzó MAXREC=1000.
La muestra de R Dra no es exhaustiva. Evidencia y límites: VALIDATION.md.

Se comprobó directamente el mapa FLAGS del primer recorte: SOURCE (21) está activo
en los 2,401 píxeles. También aparecen bits 0, 2, 6, 11, 17 y 28. Se conservan
SOURCE y FULLSAMPLE; los problemas instrumentales documentados se enmascaran por
separado. La política exacta y sus limitaciones se registran en SCIENCE.md.

## ETAPA 3 — API + web mínima (ya con modelo asincrónico de uso masivo)
- [x] Implementado `POST /api/search` con semáforo máx. 3 → `job_id`; `GET /api/status/{job_id}` para polling
- [x] Implementado límite por IP (2 en curso, 10/min) → HTTP 429 con mensaje amable
- [x] Implementado `GET /api/presets`, índice local de resultados y caché primero
- [x] Frontend preparado: formulario (SIMBAD + RA/Dec decimal y sexagesimal + FOV)
- [x] Player preparado: canvas, play/pausa, slider, velocidad, loop y fecha por frame
- [x] Implementados avisos de centro enmascarado y variación espectral del manifiesto;
  `ready` no debe presentarse como detección del objeto.
- [x] Implementados estados: resolución / búsqueda / cola con posición / vacío / parcial / listo / error
- [x] Preparadas 12 pruebas de API sin red y guía STAGE3_QA.md
- [x] Ejecutar las 30 pruebas Python y compilar React/Vite en la terminal del usuario
- [x] Funcionamiento de controles confirmado manualmente por el usuario
- [x] **Entregable:** la web funciona en localhost con datos reales.

La regresión detallada de los cinco presets y ventana móvil se conserva en
STAGE3_QA.md para revisión previa al despliegue y Etapa 7; sin fallos reportados.

Ejecución confirmada por el usuario: 30 pruebas pasan en 1.036 s, Vite compila
en 680 ms, Uvicorn arranca y sirve la web y los 12 PNG de Barnard correctamente.
El usuario confirmó después «Todo está funcional» al solicitarle probar los
controles con Epsilon Indi B. Se cierra la aceptación funcional local con esa
comprobación manual. La herramienta falló con `timeoutMs`; no se atribuye QA
visual automatizada al agente ni revisión individual de toda la lista ampliada.

`api.py` ejecuta
SIMBAD y el pipeline síncrono mediante `asyncio.to_thread`, bajo el semáforo.
Las búsquedas iguales comparten trabajo; las escrituras para un mismo centro
se serializan en disco. Cola máxima: 32 trabajos activos. Los resultados y sus
archivos se validan antes de exponer enlaces por índice, sin servir data/raw.
FastAPI sirve frontend/dist en el mismo origen. Requiere un solo worker porque
cola y límites son por proceso. Al arrancar se indexan los datos existentes,
sin warm-up de red. La generación y distribución de presets para despliegue
nuevo sigue pendiente en Etapa 4. Las restricciones iniciales del agente no
sustituyen la evidencia de ejecución posterior del usuario, registrada arriba.

## ETAPA 4 — Despliegue + robustez (PRIMERO El deploy)
- [x] Subir a Render. **URL pública viva**, confirmada por el usuario:
  https://orbitlens-spherex.onrender.com (verificación HTTP independiente del agente pendiente por conectividad).
- [x] Parser RA/Dec sexagesimal (Astropy) implementado en Etapa 3 y probado con la suite
- [x] Caché por parámetros exactos, FOV, colecciones y versión pipeline; se conserva precisión de coordenadas.
- [x] Presets empaquetados al desplegar, confirmados funcionando por el usuario.
- [x] Configuración de colecciones mediante ORBITLENS_COLLECTIONS; regenerar presets si cambia.
- [x] Aviso de frescura con fechas de consulta y procesamiento; frontend compilado por el agente.
- [x] Timeouts de conexión/lectura y reintentos selectivos con IRSA implementados.
- [x] Limpieza por último uso, presupuesto blando conjunto de 2 GiB y protección de presets.
- [x] Ejecutar suite Python ampliada y volver a desplegar las mejoras de robustez: 40 pruebas pasan en 1.241 s.
- [x] Validación pública aceptada por el usuario tras solicitar presets, reinicio y límites entre conexiones distintas: «Listo, funciona todo». Sin verificación independiente del agente.

Implementación de robustez validada: el usuario ejecutó las 40 pruebas correctamente
y confirmó el funcionamiento público. El agente compiló TypeScript/Vite correctamente. La limpieza no
interrumpe constructores activos y retiene archivos recientes; por eso el presupuesto
no es un límite duro. Configuración y validación pública detalladas en DEPLOYMENT.md.

## ETAPA 5 — Modos de visualización
- Implementación preparada en `analysis_modes.py`, endpoint de análisis y panel
  React. Diferencia sobre FITS, media por época de hasta siete días y curva del
  píxel central con null para máscaras. Compatibilidad espectral aproximada
  comprobada entre todas las parejas. Decisiones en SCIENCE.md.
- Implementación y cálculos comprobados: 76 pruebas Python y `verify_demo.py`.
  El informe traído por el pull en ENTREGA.md registra una revisión previa en Edge;
  la aceptación funcional manual posterior está en DEPLOYMENT.md. Los detalles de
  regresión se conservan en STAGE5_QA.md/STAGE6_QA.md.
  Las casillas siguientes describen implementación, no validación científica.
- [x] Modo Diferencia (frame A − frame B, etiqueta "exploratorio, no confirma descubrimiento")
- [x] Modo Pila: media de valores válidos por píxel, por detector y época (máximo siete días, al menos dos contribuciones; mejora de señal/ruido no cuantificada)
- [x] Curva del píxel central: WISE 0855 tiene 12 puntos válidos y Epsilon Indi B 10;
  Barnard, RW Aurigae y R Draconis tienen 0. No se inventan valores para máscaras.

## ETAPA 6 — Bandas + compartir + producción
- [x] Selector espectral basado en la longitud de onda real de cada medición; IMAGE no es un cubo.
- [ ] Comparación por detector y apilado de mediciones espectralmente compatibles,
  sin sumar indiscriminadamente los seis detectores; pares simultáneos 1–4, 2–5, 3–6.
  El apilado compatible del mismo detector está implementado. Comparación conjunta
  entre detectores pendiente de diseño/validación científica; no se suman pares por número.
- [x] **Gaia/WISE** (consideración #5): vista Aladin Lite del mismo campo, con
  catálogos Gaia DR3/AllWISE; funcionamiento aceptado manualmente por el usuario,
  no overlay SPHEREx ni validación de identidad de fuentes.
- [x] **Coordenadas en la URL** (consideración #6): `/?ra=&dec=&fov=` carga directo el resultado;
  conserva frames y detector, y respeta opciones de enlaces de preset.
- [x] **Panel de FLAGS/calidad** por frame (consideración #7): flags aplicados, % de píxeles enmascarados
- [ ] Repositorio GitHub público + README + licencia + sección "fuentes de datos" (puntúa en el registro)
- [x] Sección educativa mínima sobre infrarrojo, enanas marrones y comparación de fechas.
- [x] En README: decisiones de estabilidad (semáforo, límites por IP, caché);
  comportamiento de cuotas/proxy aceptado manualmente por el usuario, sin
  atribuir al agente una inspección de configuración o auditoría independiente.

Detalle y regresión manual de Etapa 6: [STAGE6_QA.md](STAGE6_QA.md).

## ETAPA 7 — Margen
- [ ] Espectros al vuelo (solo si TODO lo demás está done; si no, se traslada a etapas 8–9)
- [ ] Pulido de UI, ensayo completo de la demo 3 veces
- [x] Regresión local: diez pestañas reales simultáneas con Playwright y dos
  coordenadas repetidas mediante `verify_release.py`, con resultados en caché.
  No mide capacidad de Render: el servidor E2E tiene cuota elevada exclusivamente
  para pruebas. Configuración, límites y casos en STAGE7_QA.md.
- [x] Comprobar cuotas reales en Render desde dos conexiones y con cabeceras
  falsificadas, más revisión manual en dispositivo real y CDS disponible.
  Aceptación manual del usuario: «Ya he hecho esas pruebas y funciona como debe.»
  Sin trazas/dispositivos/IP concretas adjuntas; protocolo y límites en DEPLOYMENT.md.
- [x] Matriz de 15 casos de prueba: presets, ceros, partial controlado, colecciones
  profundas, polos, entradas inválidas y dependencias externas; ejecución manual pendiente.
- [ ] Descansar.

---

## ETAPAS 8–9 — Hackathon con el equipo

- [ ] 2 personas: grabar y editar video de presentación (~1–2 min) — narrar la demo
- [ ] 2 personas: QA fantasma — usar la web toda la noche con coordenadas al azar, reportar bugs (tú corriges)
- [ ] 1 persona: pitch/presentación + contenido educativo + **página de submission oficial** (equipo, challenge, enlaces código/demo/video, preguntas de uso de datos)
- [ ] Ensayo final, verificación del deploy en producción, submission.

## Bonus (si sobra tiempo, orden por impacto/esfuerzo)

- [ ] Espectro al vuelo (apertura fotométrica vs. banda)
- [ ] Descarga del FITS recortado original (enlace en el manifiesto)
- [ ] Link-out a páginas externas (SIMBAD, NASA/WISE) por cada frame
- [ ] Traducir UI a ES/EN

## Contingencias (diseñadas ya)

| Situación | Respuesta |
|---|---|
| Coordenadas sin cobertura en la colección principal | Fallback automático a las 4 colecciones → estado `empty` con sugerencias |
| 1–2 frames solo | Estado `partial`, no reproducir, mostrar aviso |
| IRSA lento/caído | Timeout 30s, reintento x2, usar caché si existe, mensaje claro |
| Datos muy recientes no en SIA2 | Banner de desfase (~1 día) + ofrecer colección alternativa |
| FITS de 70 MB | NUNCA bajar completo: siempre cutout + límite de FOV |
| CORS | El navegador JAMÁS habla con IRSA: todo vía FastAPI |
| WCS/ángulos distintos entre frames | Reproyección a rejilla común obligatoria |
| Escala visual distinta por frame | Estiramiento global, no por-frame |
| Tu equipo en demo no sabe explicar | El pitch está en la memoria de cada persona; ensayar 3 veces antes |
| 20+ usuarios de golpe (hackathon global) | Semáforo 3 cómputos + cola con posición en UI + 429 informal + caché compartida |
| Un script/spammer golpea la API | Límite por IP (2 en curso, ~10/min) → 429 con mensaje amable |
| Disco del servidor se llena | Caché con límite 2 GB y limpieza LRU de resultados viejos |
| Deploy frío (Render free tier) | Presets cálidos al arrancar; ping de keep-alive; delante en el pitch, la demo pega a URLs cacheadas |

---

## Coordenadas de referencia verificadas — SIMBAD, época juliana 2026.5

Coordenadas ICRS usadas en los presets, propagadas desde J2000 con movimiento
propio. No incluyen paralaje anual ni se recalculan para cada exposición.

| Objeto | RA (grados) | Dec (grados) |
| --- | --- | --- |
| Barnard's Star | 269.44615615 | +4.76964363 |
| WISE 0855 | 133.75862792 | −7.24208853 |
| Epsilon Indi B | 331.09767931 | −56.80099136 |
| RW Aurigae | 76.95658774 | +30.40128852 |
| R Draconis | 248.16722581 | +66.75502468 |

Las aproximaciones originales de R Draconis (263.2, +56.9) eran incorrectas para
este objeto y no deben reutilizarse. Las coordenadas de WISE 0855 proporcionadas
por el reto (08h55m10.831s, −07d14m42.53s) son una referencia histórica de época
no especificada; no equivalen al centro propagado a 2026.5.

## Historial de implementación — 2026-11-05 (superado por la validación de Etapa 1)

- Preparado `test_data.py`: consulta las cuatro colecciones, ordena por MJD,
  descarga un recorte, inspecciona IMAGE y extensiones, valida el centro con WCS
  y exporta PNG más CSV e informe JSON de procedencia.
- Dependencias mínimas de la Etapa 1 en `requirements.txt`; instrucciones en README.
- Pendiente de validación: en el entorno de ejecución del agente no se encontró
  Python ni los lanzadores py/uv, y la solicitud directa a IRSA desde PowerShell
  falló por conectividad. No se ha ejecutado el script ni generado el primer FITS/PNG.
  En ese momento las casillas de la Etapa 1 seguían pendientes; la validación posterior está arriba.
- Corrección de alcance: overlay Gaia/WISE (#5) es obligatorio para el objetivo
  8/8. Ya se movió al alcance de la Etapa 6; Aladin es una opción.
- El límite de 100 KB por cutout es una hipótesis pendiente de medir; los MEF
  incluyen extensiones auxiliares. El script limita la descarga a 100 MiB por
  seguridad; ese límite no representa el tamaño esperado ni el límite de la web.

### Corrección de consulta SIA — 2026-11-05

- La ejecución local confirmó 100 filas de QR3 y QR2 y cero de las dos
  colecciones profundas para la consulta de Barnard; todavía no hay imagen validada.
- Las respuestas originales guardadas mostraron JSON sin escapar en la columna
  cloud_access del CSV, que desplazaba las columnas siguientes. Se cambia la
  consulta a RESPONSEFORMAT=VOTABLE y se usa el lector de Astropy. El endpoint
  documenta ese formato: https://irsa.ipac.caltech.edu/ibe/sia.html
- Se mantienen query_results.csv (generado con escapado correcto) e inspection.json.
  Las nuevas respuestas originales se guardan como query_spherex_*.vot.
- Añadidas cuatro pruebas de regresión del lector: JSON con comas y exportación
  CSV, resultado vacío, error SIA y respuesta no XML. Pendientes de ejecutar en la
  terminal del usuario junto al script; el agente no tiene acceso al Python instalado.

## Etapa 4 — preparación de despliegue
Se añadieron render.yaml, start_server.py, prepare_deploy.py y DEPLOYMENT.md.
El usuario ejecutó el empaquetado de los cinco presets y las 32 pruebas: todas pasan en 1.226 s. Paquete demo/cache: 126 archivos y 2,464,219 bytes. Publicado en https://orbitlens-spherex.onrender.com y confirmado funcionando por el usuario. El agente no pudo conectar para comprobar los endpoints. La etapa sigue abierta: faltan las mejoras de robustez y la regresión pública detallada.


Cierre posterior de Etapa 4: las mejoras de robustez y la regresión pública indicadas como pendientes en el historial anterior se completaron. Suite: 40 pruebas correctas en 1.241 s. Confirmación pública del usuario: Listo, funciona todo. Próximo trabajo: Etapa 5.


## Actualización del 6 de noviembre de 2026
Resultados reproducibles, alcance de las pruebas públicas y reparto del cierre entre cinco integrantes en [ENTREGA.md](ENTREGA.md).
