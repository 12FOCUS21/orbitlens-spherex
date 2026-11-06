# Etapa 7 — regresión y ensayo de entrega

## Comprobación automática local

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe verify_demo.py
.\.venv\Scripts\python.exe verify_release.py
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

## Matriz de 15 casos

Los casos con coordenadas nuevas pueden consultar IRSA: ejecutarlos manualmente
de forma secuencial, no desde un script de carga. No asumir cobertura donde no se
ha comprobado. Registrar versión desplegada, fecha, dispositivo y resultado.

| # | Caso | Resultado esperado / evidencia | Estado |
| --- | --- | --- | --- |
| 1 | Barnard, 12 frames | Caché ready; 12 centros enmascarados. Diferencia 1−7 invierte signo al intercambiar A/B. | HTTP y cálculo comprobados; visual pendiente |
| 2 | Epsilon Indi B | Caché ready; curva con 10 valores y 2 ausentes, sin sustituir por cero. | HTTP y cálculo comprobados; visual pendiente |
| 3 | WISE 0855 | Caché ready; curva con 12 valores. No afirmar detectabilidad por tener centro válido. | HTTP y cálculo comprobados; visual pendiente |
| 4 | RW Aurigae, apilado 1 y 2 | Media con dos contribuciones por píxel válido y cobertura aproximada del 95,13 %. | HTTP y cálculo comprobados; visual pendiente |
| 5 | R Draconis, colecciones profundas | Caché ready; advertencia de inventario truncado cuando corresponda; centros ausentes. | HTTP y cálculo comprobados; visual pendiente |
| 6 | `/?ra=0&dec=0&fov=5&frames=3` | Aceptar ceros; mostrar resultado o vacío según cobertura, nunca error por falsedad de cero. | Enlace probado; cobertura real pendiente |
| 7 | Polo norte: RA=0, Dec=90 | Entrada válida; WCS o ausencia de cobertura tratados sin 500. | Validación cubierta; consulta real pendiente |
| 8 | Polo sur: RA=0, Dec=−90 | Entrada válida; no asumir imágenes disponibles. | Validación cubierta; consulta real pendiente |
| 9 | RA=`08h55m10.831s`, Dec=`-07d14m42.53s` | Equivalencia con grados de esa posición; no confundir con el centro propagado del preset WISE. | Conversión probada; visual pendiente |
| 10 | Resultado partial controlado, dos frames de doce solicitados | Preservar estado y máscaras; permitir inspección manual, no animación. No depender de encontrar un campo real partial. | API con fixture probada; visual pendiente |
| 11 | Solicitar y obtener uno o dos frames | Estado ready; animación deshabilitada si hay menos de tres; conservar opciones al compartir. | Pipeline y enlaces probados; visual pendiente |
| 12 | RA=360, Dec=91, booleanos, minutos=60 o frames=17 | Rechazo 422 en API; URL inválida con mensaje legible sin POST cuando falla validación local. | Pruebas automatizadas; visual pendiente |
| 13 | Longitud de onda desconocida / bandas incompatibles | Desconocidas al final del selector; no permitir diferencia/apilado incompatible ni inventar bandas. | Pruebas automatizadas; visual pendiente |
| 14 | Aladin sin CDS disponible | Mantener visor SPHEREx, mostrar error y enlace externo alternativo; no afirmar catálogos cargados. | Manual pendiente |
| 15 | Diez visitas y dos campos repetidos; cuotas | Smoke local correcto. Repetir con diez pestañas; en Render usar dos conexiones y probar cabeceras falsificadas. | HTTP local comprobado; navegador/Render pendientes |

Repetir los controles de enlaces, selector, FLAGS y análisis a **390 px** siguiendo
`STAGE6_QA.md`. Las pruebas HTTP no detectan desbordamientos ni errores visuales.

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
la regresión y revisar su diseño científico. Las cuotas reales y proxies siguen
pendientes de la comprobación de `DEPLOYMENT.md`; no se marcan completados aquí.
