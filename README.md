# OrbitLens — SPHEREx Time Atlas

Plan de proyecto para el reto **Planet X and SPHEREx** de NASA Space Apps Challenge 2026.

## La propuesta

**OrbitLens** es una experiencia web abierta para explorar una región del cielo a través del tiempo. En vez de mostrar una imagen estática, permite alternar épocas, superponerlas, observar una diferencia visual y comprender por qué un cambio puede ser relevante. El producto convierte 102 bandas infrarrojas de SPHEREx en tres recorridos claros: **cambio temporal**, **color infrarrojo** y **evidencia científica**.

El reto pide crear una herramienta web pública que muestre imágenes del cielo de SPHEREx y haga fácil observar sus cambios en el tiempo. SPHEREx está construyendo mapas de todo el cielo en 102 longitudes de onda infrarrojas; NASA publica los datos en el archivo IRSA. [Reto oficial](https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=details) · [Datos SPHEREx](https://science.nasa.gov/open-science/spherex-universe-map/)

## Alcance de demostración

1. Elegir una de tres regiones precargadas y una época.
2. Comparar dos épocas con modos *blink*, deslizador y diferencia absoluta.
3. Aplicar presets de color infrarrojo y consultar la banda/longitud de onda mostrada.
4. Mostrar candidatos a cambio con un indicador de confianza explicable, no una afirmación de descubrimiento.
5. Abrir una tarjeta de evidencia con procedencia de datos, limitaciones y enlace a la fuente NASA.

El producto no debe afirmar el descubrimiento de Planet X. Su valor es hacer detectables, comprensibles y verificables posibles cambios para público general, docentes y aficionados.

## Carpeta de decisión

| Documento | Contenido |
| --- | --- |
| [00-project-charter.md](00-project-charter.md) | problema, usuarios, métrica y responsabilidades |
| [01-architecture-and-data.md](01-architecture-and-data.md) | arquitectura, datos, ciencia y riesgos |
| [02-48h-runbook.md](02-48h-runbook.md) | cronograma de hackathon y punto de corte |
| [03-git-workflow.md](03-git-workflow.md) | colaboración, ramas, PR y trazabilidad |
| [04-submission-checklist.md](04-submission-checklist.md) | entrega, demo, referencias y presentación |

## Decisiones bloqueadas

- Confirmar la regla del evento local sobre trabajo previo. Este repositorio contiene planificación; el código original y la demo final deben realizarse de acuerdo con las reglas vigentes y declararse con transparencia.
- Elegir el anfitrión remoto y la visibilidad del repositorio. Para una propuesta Space Apps, la recomendación es un repositorio público bajo licencia MIT, una vez que el equipo confirme su cumplimiento con las condiciones 2026.
- Elegir las tres regiones de la demo tras una prueba de acceso a IRSA; mantener siempre un paquete reducido de respaldo con atribución clara.

## Estado

`PLAN READY` — no contiene código de producto ni datos descargados. Es un punto de partida reproducible para que el equipo acuerde el alcance antes del hackathon.
