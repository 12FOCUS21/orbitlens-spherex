# Entrega del equipo

## Qué se puede reproducir

Tras instalar las dependencias según README, ejecutar desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe verify_demo.py
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe verify_release.py
```

El 6 de noviembre de 2026 pasaron inicialmente 52 pruebas. Tras las correcciones
de robustez y el smoke de entrega pasan 76 pruebas Python y 10 pruebas frontend de enlaces y orden
espectral. Estas últimas se ejecutan con `npm.cmd --prefix frontend test` y
Node.js 22.12+. También pasa la verificación de los cinco ejemplos FITS del
repositorio. En Barnard, intercambiar las imágenes 1 y 7 invierte el signo de la
diferencia y conserva las zonas transparentes. En RW Aur, el 95,13 % del campo
del apilado de las imágenes 1 y 2 tiene dos contribuciones válidas. En la curva
central, WISE 0855 tiene 12 valores válidos, Epsilon Indi B tiene 10 y los otros
tres campos tienen cero. Una muestra enmascarada es un dato ausente. El brillo
del píxel central incluye fondo y fuentes vecinas.

En Edge se ejecutaron los tres análisis desde el visor. A 390 píxeles de ancho el documento cabe en pantalla. Diez pestañas locales cargaron la portada simultáneamente. En el despliegue público se comprobaron la portada, salud, lista de ejemplos y el primer y último PNG de cada una de las cinco secuencias.
Este párrafo registra la revisión previa incluida en el pull, no una repetición
de esas comprobaciones para los cambios actuales. La regresión manual de esta
versión está pendiente en [STAGE6_QA.md](STAGE6_QA.md), igual que la comprobación
de cuotas por visitante tras el proxy descrita en DEPLOYMENT.md.
El smoke de `verify_release.py` cubre HTTP concurrente local y caché, sin ejecutar
un navegador. La matriz de 15 casos y los tres ensayos pendientes están en
[STAGE7_QA.md](STAGE7_QA.md).
Posteriormente se ejecutaron 20 casos E2E con Playwright y Edge headless en
escritorio y viewport móvil de 390 px, incluidos diez tabs reales simultáneos,
los tres análisis y el fallo de CDS. La suite se repite con
`npm.cmd --prefix frontend run test:e2e` y usa caché temporal y cuota elevada solo
para pruebas. No verifica la carga correcta de catálogos externos, un móvil físico
ni el proxy de producción. Los tres ensayos de presentación siguen pendientes.
Una comprobación directa de lectura pública el 2026-11-06 confirmó salud y cinco
presets en 200, frontend JS/CSS idéntico al build local y acceso al primer/último
PNG/FITS de cada secuencia, cinco GIF y cinco target.json. No se hicieron POST ni
se verificaron cuotas entre conexiones. La evidencia y el protocolo operativo
pendiente están en DEPLOYMENT.md.

## Ensayo y reparto para cinco integrantes

1. **Datos**. Mostrar la procedencia de un FITS y documentar detector, fecha, banda y máscara de una comparación. Verificar manualmente WCS con fuentes de referencia antes de interpretar desplazamientos.
2. **Ciencia**. Repetir la verificación anterior y explicar cómo una máscara o una diferencia de banda afecta el resultado. La identificación de un objeto exige validación independiente.
3. **Interfaz**. En la versión desplegada, abrir un enlace compartido en otra ventana, comparar el campo recuperado y verificar que Gaia DR3 y AllWISE muestran fuentes cerca del centro solicitado. El mapa externo depende de CDS.
4. **Pruebas con personas**. Pedir a tres personas que abran Barnard, comparen dos fechas y expliquen un píxel sin datos. Registrar dispositivo, tarea, resultado y dificultad sin sugerir dónde pulsar. Corregir y repetir los pasos donde se atasquen.
5. **Presentación**. Ensayar un minuto. Dedicar 10 segundos al problema, 20 al visor, 20 a una comparación y 10 a las limitaciones. Revisar enlaces públicos desde una ventana privada, añadir créditos y nombres acordados y comprobar las condiciones del evento antes de enviar.

## Borrador de descripción

OrbitLens permite al público comparar imágenes infrarrojas reales de SPHEREx tomadas en fechas distintas. Una persona puede elegir un campo, alternar observaciones y consultar fechas, longitudes de onda y calidad. El equipo muestra cómo una diferencia entre dos imágenes cambia al invertir el orden y cómo las máscaras limitan la interpretación. Los ejemplos empaquetados permiten repetir la demostración aunque el archivo remoto interrumpa una descarga.

**Créditos técnicos**. Misión NASA SPHEREx y archivo NASA/IPAC IRSA para las observaciones. Astropy para FITS y coordenadas. CDS para Aladin Lite y VizieR. Completar los agradecimientos oficiales de Gaia y AllWISE si se incluyen capturas de esos catálogos en la entrega.
