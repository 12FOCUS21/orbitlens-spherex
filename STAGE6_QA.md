# Etapa 6 — bandas, enlaces y calidad

## Implementado y comprobable localmente

- Selector de mediciones ordenado por longitud de onda aproximada en el centro.
  Conserva los índices originales y no modifica el orden temporal de los FITS.
  No crea bandas nuevas ni convierte IMAGE en un cubo espectral.
- Enlaces que conservan RA/Dec sin redondear, FOV, cantidad solicitada y detector.
  Un enlace con coordenadas y etiqueta de preset usa las coordenadas guardadas,
  sin volver a resolver la posición del preset. La etiqueta se conserva al compartir.
  Un enlace con solo preset puede especificar FOV, frames y detector.
- Validación local de opciones: parámetros repetidos, presets desconocidos,
  campos incompletos y opciones fuera de rango no generan búsquedas.
  Astropy sigue siendo la autoridad para coordenadas decimales/sexagesimales.
- Desglose de FLAGS por exposición: bit, nombre, fracción y política aplicada.
  Los bits desconocidos sin excluir no se presentan como calidad validada.
  Se distingue el recorte original de la cobertura de la rejilla alineada.
- Vista externa `/catalogos.html`: Aladin Lite, Gaia DR3 y AllWISE en el mismo
  centro. No es una superposición sobre los píxeles SPHEREx ni valida identidades.
  Requiere red y disponibilidad de CDS; muestra un enlace externo alternativo.
- Comparación/apilado de mediciones compatibles del mismo detector. Combinar
  detectores distintos sigue fuera del producto actual: no se presupone
  equivalencia espectral ni una mejora de señal/ruido cuantificada.

## Pruebas automatizadas

Desde la raíz, con Node.js 22.12+ (las pruebas usan eliminación de tipos nativa):

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe verify_demo.py
```

Las 10 pruebas frontend cubren enlaces y orden espectral, sin nuevas dependencias
ni consultas remotas. No ejecutan React en un navegador. La suite Python y
`verify_demo.py` cubren cálculos, máscaras y datos reales empaquetados.

## Guía de regresión manual

La regresión funcional automatizada en Edge de `STAGE7_QA.md` ya comprueba
enlaces, controles, análisis, calidad y ausencia de desbordamiento a 390 px.
La lista siguiente conserva tareas manuales: no sustituye pruebas en dispositivo
real ni la comprobación de catálogos disponibles y cuotas en producción.

- [ ] Abrir Barnard, copiar su enlace y abrirlo en una ventana privada. Comparar
  coordenadas, FOV, cantidad solicitada, detector y etiqueta.
- [ ] Abrir `/?preset=barnard&fov=4&frames=2&detector=SPHEREx-D3` y comprobar que
  no se ignoran las opciones. Puede requerir construir una secuencia nueva.
- [ ] Abrir `/?ra=0&dec=0&fov=5&frames=3`; comprobar búsqueda o estado vacío,
  sin asumir cobertura ni detectabilidad.
- [ ] Abrir `/?ra=10`, `/?preset=unknown` y `/?ra=0&dec=0&frames=17`:
  mensaje legible y ninguna nueva petición POST de búsqueda.
- [ ] Elegir una medición por longitud de onda; debe cambiar imagen, fecha y
  metadatos, detener la reproducción y conservar el orden del deslizador temporal.
- [ ] Revisar FLAGS y distinguir fracción enmascarada original de cobertura
  alineada. Verificar que SOURCE/FULLSAMPLE no se confunden con bits excluidos.
- [ ] Abrir Gaia/AllWISE en Aladin: centro y campo correctos. Bloquear CDS para
  comprobar mensaje y enlace alternativo, sin romper el visor principal.
- [ ] Repetir enlace, selector y panel de calidad en una ventana de 390 px.
- [ ] Repetir diferencia, apilado y curva central de `STAGE5_QA.md`.

El usuario confirmó el funcionamiento esperado de las pruebas operativas manuales
de cuotas/proxy, CDS y móvil, según `DEPLOYMENT.md`. La lista se conserva para
repetir la regresión; no se dan por ejecutadas una a una todas sus variantes por
esa confirmación global. No confundir esta aceptación con pruebas locales de
proxy simulado ni con una auditoría independiente de la infraestructura.
