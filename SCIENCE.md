# Decisiones científicas — Etapa 2

## Etapa 5: diferencia, media por época y curva del píxel central

Estos modos leen valores de los FITS alineados en MJy/sr y su máscara VALID,
no intensidades de PNG. Se exige misma forma, WCS y unidad para combinarlos.
La diferencia es A−B en la intersección válida. Su escala asinh es simétrica
respecto a cero: rojo positivo, azul negativo y blanco cero; huecos transparentes.

El apilado es una media aritmética por píxel de las muestras válidas. Requiere
al menos dos contribuciones por píxel; el denominador cambia con la cobertura.
Se limita a una época exploratoria de siete días de extremo a extremo, definida
por el producto. No es una época física universal: puede difuminar movimiento o
variabilidad y no se cuantifica una mejora de señal/ruido sin varianzas propagadas.

Para diferencia y apilado se exige un único detector y compatibilidad entre
todas las parejas: separación de longitudes centrales no mayor que la mitad
del menor ancho espectral. Es una heurística de selección para exploración,
no una calibración ni garantía de equivalencia de filtros. Usa WCS-WAVE en el
centro; no comprueba compatibilidad espectral en cada píxel del campo. Si faltan
longitudes/ancho, se rechaza la combinación en lugar de inventar compatibilidad.

La curva usa el píxel fijo `shape // 2` de la rejilla común (misma convención del
pipeline), conserva MJy/sr, fechas y longitudes de onda y presenta puntos sin
unirlos. Valores enmascarados son null, nunca cero. No sigue el movimiento del
objeto ni mide flujo integrado por apertura; no es fotometría validada. No se
aplican correcciones de PSF, ZODI/fondo ni incertidumbres. La falta de puntos en
Barnard, RW Aur o R Dra refleja sus máscaras y no prueba ausencia de la fuente.

## Alcance

El pipeline produce una secuencia exploratoria de brillo superficial en MJy/sr.
No identifica automáticamente al objeto, no calcula fotometría ni confirma
movimiento. Los ensayos con fuentes sintéticas prueban el procesamiento; las
observaciones reales deben validarse por separado.

## Selección temporal

Se consultan las cuatro colecciones con SIA/VOTable. Las exposiciones duplicadas
se identifican por `obs_id` y detector, prefiriendo QR3 frente a QR2. Se usa un
único detector; en modo automático se priorizan fechas distintas, intervalo
temporal y cantidad de observaciones. La muestra incluye los extremos y después
las fechas más alejadas de las ya elegidas. Si un recorte no es utilizable, se
intentan hasta cuatro candidatos adicionales.

MAXREC limita cada consulta: el manifiesto indica si la lista podría estar
truncada. No se afirma que la selección cubra todo el archivo.

## Coordenadas y épocas

Los presets se resuelven mediante SIMBAD/TAP; se guardan el identificador,
coordenadas J2000, movimiento propio y época de referencia elegida. Cuando hay
movimiento propio, Astropy propaga la posición a esa época (`2026.5` por defecto).
La consulta de identificadores escapa las comillas del nombre.

Si falta el movimiento propio, se conserva la posición J2000 y se registra esa
limitación. No se aplica paralaje anual ni velocidad radial. El centro de la
secuencia permanece fijo: no se desplazan los frames siguiendo al objeto.
Las coordenadas decimales proporcionadas por el usuario se usan directamente.

El resolver intenta primero Strasbourg y después el mirror de Harvard ante
errores de red o HTTP. Guarda el servidor que respondió y los fallos previos;
si ningún servidor responde, no asigna unas coordenadas aproximadas al objeto.
Los dos servidores están enumerados en la
[configuración oficial de Astroquery](https://docs.astropy.org/projects/astroquery/en/latest/api/astroquery.simbad.Conf.html).

Referencias: [SIMBAD, coordenadas y épocas](https://simbad.u-strasbg.fr/Pages/guide/sim-fsam.htx)
y [propagación de movimiento con Astropy](https://docs.astropy.org/en/stable/coordinates/apply_space_motion.html).

## Máscara de calidad

Se decodifican los bits de FLAGS, nunca se usa `FLAGS != 0` como máscara global.
Se conservan los bits informativos SOURCE (21) y FULLSAMPLE (12). Los otros bits
públicos enumerados en `FLAG_NAMES` se enmascaran de manera conservadora antes
de interpolar. Es una política de visualización, no una selección universal de
calidad científica. Los bits desconocidos se registran y no se enmascaran.

El manifiesto guarda la máscara aplicada, fracción de píxeles por bit y fracción
de cobertura válida. El frame se omite si menos del 50% de la rejilla es válido.
Un píxel central inválido se conserva como NaN/transparente y se señala en el
manifiesto y en el GIF; no obliga a descartar el resto del campo. Una secuencia
puede ser procesable aunque la fuente central no sea evaluable en algunos frames.
Los FLAGS se reproyectan con vecino más
cercano; el mapa VALID del FITS alineado identifica los píxeles utilizables.

En el recorte real de la Etapa 1, SOURCE está presente en los 2,401 píxeles.
También se detectaron los bits 0, 2, 6, 11, 17 y 28 en subconjuntos de píxeles.

Fuente de las definiciones: [IRSA, flags de SPHEREx](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html).

## Alineación y escala visual

La rejilla común es TAN/ICRS, centrada en las coordenadas solicitadas, con píxeles
de 6.15 arcsec y norte arriba/este a la izquierda al mostrar los PNG. Los FITS
conservan su origen convencional; los PNG se invierten verticalmente.
Las nuevas rejillas tienen un número impar de píxeles: el objetivo coincide con
el píxel central usado por calidad y curva de luz. La clave de caché distingue
esta política de las rejillas previas; no se alteran los FITS de los presets históricos.

Se pide un recorte con margen para poder rotar las esquinas del detector. La
reproyección es bilineal y trabaja con la WCS celestial, incluida la distorsión
SIP si existe. Los valores sin cobertura permanecen NaN en FITS y transparentes
en PNG. No se registran imágenes siguiendo una estrella concreta.

Se calculan los percentiles 1 y 99 sobre todos los píxeles válidos de todos los
frames aceptados, y se aplica el mismo asinh a toda la secuencia. No hay
normalización por frame ni sustracción de ZODI. El producto alineado no incluye
incertidumbres propagadas; aún no es apto para curvas de luz cuantitativas.

Referencia: [reproject_interp](https://reproject.readthedocs.io/en/stable/api/reproject.reproject_interp.html).

## Información espectral

Usar el mismo detector no garantiza la misma longitud de onda. Cada frame
intenta obtener longitud de onda y ancho en la posición solicitada mediante la
WCS alternativa `W` y su tabla WCS-WAVE. Si no se puede evaluar, se guarda el
error y valores nulos; no se inventa una banda. Este muestreo en el centro no
reemplaza un mapa espectral ni sigue la posición cambiante de una fuente.

La WCS espectral se construye desde una copia de la cabecera sin coeficientes
SIP y con `sip = None`, siguiendo el
[tutorial de IRSA, sección Spectral WCS](https://github.com/Caltech-IPAC/irsa-tutorials/blob/main/tutorials/spherex/spherex_intro.md).
La transformación celestial conserva SIP. WCS-WAVE proporciona una aproximación
para visualización; para análisis espectral cuantitativo se necesitarán los
productos de calibración CWAVE y CBAND, como indica la documentación de productos.

La variación de banda, PSF, fondo, calibración y máscaras puede producir cambios
visuales. El GIF de QA usa 500 ms por frame, independientemente del intervalo
astronómico real, y no sustituye la inspección de las fechas del manifiesto.

Fuentes: [productos SPHEREx](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/)
y [recortes oficiales de IRSA](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html).
