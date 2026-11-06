# PLAN — Planet X and SPHEREx (NASA Space Apps 2026)

> **CONTEXTO PARA NUEVA SESIÓN (leer primero):**
> - Estado: ETAPA 1 validado (2026-11-05): FITS real, PNG e informe generados; 4 pruebas pasan.
>   ETAPA 2 implementada: reproject instalado y 15 pruebas pasaron en la terminal del usuario.
>   SIMBAD respondió desde Harvard; la consulta real obtuvo 119 filas QR3 y 240 QR2.
>   Los recortes se descartaron por exigir un centro válido pese a buena cobertura.
>   Corregido en pipeline 0.2.1; 2 pruebas nuevas (17 en total) y secuencia real pendientes.
>   No marcar la etapa completada todavía.
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
> - Siguiente paso concreto: volver a ejecutar unittest y
>   `build_sequence.py --preset barnard`; después `build_sequence.py --verify-presets`.
>   Revisar GIF, manifest.json y preset_verification.json antes de pasar a la API.
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
- FLAGS es distinto de cero en el 100% de los píxeles. **Pendiente interpretar bits**:
  no asumir que todos son inválidos ni aplicar una máscara `FLAGS != 0` sin documentación.
- Coordenadas aproximadas: queda pendiente verificar con SIMBAD y considerar movimiento
  propio/época antes de identificar a Barnard en la imagen.
- La imagen es espacial 2D; no implementar el selector espectral como planos de un
  cubo. Revisar la información de longitud de onda antes de diseñar ese selector.

## ETAPA 2 — Pipeline científico
- [x] Implementación preparada: `spherex_pipeline.py`, `build_sequence.py`, `targets.py`.
- [x] Dependencia reproject e instrucciones de ejecución en README; decisiones en SCIENCE.md.
- [x] Instalar reproject y ejecutar las primeras 13 pruebas: todas pasan.
- [x] Ejecutar las 15 pruebas tras añadir fallback de SIMBAD: todas pasan.
- [ ] Ejecutar las 17 pruebas tras corregir el rechazo por centro enmascarado.
- [ ] Mismo pipeline con 8–12 cutouts del MISMO detector
- [ ] Reproyección a WCS común (`reproject`)
- [ ] Estiramiento GLOBAL (mismos percentiles para todos los frames, asinh)
- [ ] Frames WebP/PNG + `manifest.json` (fecha, MJD, banda, detector, URL IRSA, parámetros, versión pipeline)
- [ ] **Verificar los 5 objetos del reto:** Barnard's Star, Epsilon Indi B, WISE 0855 (QR2), RW Aurigae, R Draconis
- [ ] Anotar en este archivo qué colección y detector funciona para cada uno.

La validación real de esta etapa está pendiente. El pipeline ya implementa selección
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
descargados; no hace falta --refresh. La validación de esta corrección está pendiente.

Se comprobó directamente el mapa FLAGS del primer recorte: SOURCE (21) está activo
en los 2,401 píxeles. También aparecen bits 0, 2, 6, 11, 17 y 28. Se conservan
SOURCE y FULLSAMPLE; los problemas instrumentales documentados se enmascaran por
separado. La política exacta y sus limitaciones se registran en SCIENCE.md.

## ETAPA 3 — API + web mínima (ya con modelo asincrónico de uso masivo)
- [ ] `POST /api/search` encola (semáforo máx. 3) → `job_id`; `GET /api/status/{job_id}` para polling
- [ ] Límite por IP (2 en curso, ~10/min) → HTTP 429 con mensaje amable
- [ ] `GET /api/presets`
- [ ] Frontend: formulario (búsqueda por nombre vía SIMBAD + RA/Dec decimal y sexagesimal + FOV)
- [ ] Player: canvas, play/pausa, slider, velocidad, loop, fecha visible por frame
- [ ] Estados: buscando / en cola (posición) / vacío (+sugerencias) / parcial / listo / errores claros
- [ ] **Entregable:** la web funciona en localhost con datos reales.

## ETAPA 4 — Despliegue + robustez (PRIMERO El deploy)
- [ ] Subir a Render/Fly.io. **URL pública viva.**
- [ ] Parser RA/Dec sexagesimal (Astropy) — aceptar `08h55m10.831s`/`-07d14m42.53s`
- [ ] Caché por cache_key (RA+Dec redondeados + FOV + colecciones + versión pipeline)
- [ ] Presets pre-cacheados al desplegar (la demo nunca depende de IRSA en vivo)
- [ ] Config de colecciones/versión → "fácil actualización con nuevos lanzamientos"
- [ ] Banner de frescura de datos (ingesta semanal + desfase ~1 día).
- [ ] Timeouts y reintentos con IRSA.

## ETAPA 5 — Modos de visualización
- [ ] Modo Diferencia (frame A − frame B, etiqueta "exploratorio, no confirma descubrimiento")
- [ ] Modo Pila: suma de frames por época y por detector (mejora señal/ruido, lo que pide el enunciado)
- [ ] Curva de luz (brillo vs. fecha del píxel central) — probar con RW Aurigae y R Draconis

## ETAPA 6 — Bandas + compartir + producción
- [ ] Selector espectral basado en la longitud de onda real de cada medición; IMAGE no es un cubo.
- [ ] Comparación por detector y apilado de mediciones espectralmente compatibles,
  sin sumar indiscriminadamente los seis detectores; pares simultáneos 1–4, 2–5, 3–6.
- [ ] **Overlay Gaia/WISE** (consideración #5): consulta de catálogo y marcadores
  sobre el WCS común, o vista Aladin Lite para explorar.
- [ ] **Coordenadas en la URL** (consideración #6): `/?ra=&dec=&fov=` carga directo el resultado
- [ ] **Panel de FLAGS/calidad** por frame (consideración #7): flags aplicados, % de píxeles enmascarados
- [ ] Repositorio GitHub público + README + licencia + sección "fuentes de datos" (puntúa en el registro)
- [ ] Sección educativa mínima: ¿qué es el infrarrojo? ¿qué es una enana marrón? ¿por qué se mueve la estrella?
- [ ] En README: decisiones de estabilidad (semáforo, límites por IP, caché) listas para uso público

## ETAPA 7 — Margen
- [ ] Espectros al vuelo (solo si TODO lo demás está done; si no, se traslada a etapas 8–9)
- [ ] Pulido de UI, ensayo completo de la demo 3 veces
- [ ] Prueba de carga casera: 10 pestañas abiertas + 2 coordenadas repetidas por donde validar caché
- [ ] Lista de 10–15 casos de prueba (coordenadas variadas: vacía, parcial, profunda, polos)
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

## Coordenadas de referencia (verifica con SIMBAD el etapa 1)

- Barnard's Star: RA≈269.452, Dec≈+4.693 (verificado QR3 dentro de 0.3°)
- WISE 0855: RA 08h55m10.831s = 133.795, Dec -07d14m42.53s = -7.245 (verificado QR2; QR3 sin datos)
- Epsilon Indi B: RA≈331.0, Dec≈-56.8 (verificar)
- RW Aurigae: RA≈76.96, Dec≈+30.44 (verificar)
- R Draconis: RA≈263.2, Dec≈+56.9 (verificar)

## Historial de implementación — 2026-11-05 (superado por la validación de Etapa 1)

- Preparado `test_data.py`: consulta las cuatro colecciones, ordena por MJD,
  descarga un recorte, inspecciona IMAGE y extensiones, valida el centro con WCS
  y exporta PNG más CSV e informe JSON de procedencia.
- Dependencias mínimas del Etapa 1 en `requirements.txt`; instrucciones en README.
- Pendiente de validación: en el entorno de ejecución del agente no se encontró
  Python ni los lanzadores py/uv, y la solicitud directa a IRSA desde PowerShell
  falló por conectividad. No se ha ejecutado el script ni generado el primer FITS/PNG.
  Las casillas del Etapa 1 siguen pendientes hasta comprobarlo en un entorno con Python.
- Corrección de alcance: overlay Gaia/WISE (#5) es obligatorio para el objetivo
  8/8 aunque figure arriba como bonus. Programarlo en el Etapa 6; Aladin es una opción.
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
