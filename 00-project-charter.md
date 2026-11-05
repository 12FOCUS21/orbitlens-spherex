# Acta del proyecto

## Problema y oportunidad

Las imágenes de SPHEREx cubren el cielo completo y 102 colores infrarrojos. Esa riqueza dificulta responder rápidamente a una pregunta intuitiva: **¿qué cambió aquí y cómo sé que vale la pena mirarlo?** OrbitLens reduce la fricción entre un mapa científico y una observación humana verificable.

SPHEREx ha empezado a publicar datos semanalmente mediante IRSA, tras el procesamiento y control de artefactos; la misión registra el cielo en 102 longitudes de onda. [NASA Science](https://science.nasa.gov/open-science/spherex-universe-map/)

## Hipótesis de impacto

Si una persona puede comparar épocas en menos de 30 segundos y entender la procedencia de cada píxel, podrá explorar cambios reales sin necesitar software astronómico especializado.

**Métrica de demo:** 3 de 3 participantes de prueba completan «seleccionar región → detectar el cambio → abrir la evidencia» en menos de dos minutos, sin instrucciones técnicas.

## Usuarios

| Usuario | Necesidad | Resultado deseado |
| --- | --- | --- |
| Explorador/a curioso/a | Una ventana comprensible al infrarrojo | descubre un cambio y entiende qué significa |
| Educador/a | Material visual con respaldo científico | guía una actividad de aula en cinco minutos |
| Científico/a ciudadano/a | Pistas, coordenadas y procedencia | comparte una observación sin sobreinterpretarla |

## Roles para cinco integrantes

| Rol | Persona | Responsabilidad única | Entregable durante el hackathon |
| --- | --- | --- | --- |
| Product owner y ciencia | Integrante 1 | alcance, veracidad, fuentes y guion | catálogo de regiones + narrativa científica |
| Datos y API | Integrante 2 | ingestión, normalización y caché | endpoint / API con metadatos y ejemplos |
| Visualización frontend | Integrante 3 | mapa, comparador y accesibilidad | flujo explorador completo en navegador |
| Detección y QA | Integrante 4 | registro, diferencia, métricas y pruebas | tarjeta de candidato y pruebas reproducibles |
| Diseño y narrativa | Integrante 5 | interfaz, identidad, video y pitch | demo grabada, presentación y página de entrega |

Todos pueden revisar código; cada área conserva una persona decisora para evitar esperas.

## Principios de producto

1. **La evidencia precede al efecto visual.** Cada vista muestra fuente, época, banda y transformación aplicada.
2. **Comprensible no significa simplista.** Explicar los límites y evitar atribuir un cambio a un planeta o astro sin validación.
3. **Demo profunda, no mapa superficial.** Tres regiones impecables son mejores que un visor mundial incompleto.
4. **Resiliente al internet.** La demo debe correr desde una captura ligera y atribuida si IRSA no responde.
5. **Accesibilidad y bilingüismo.** Interfaz inicialmente ES/EN, navegación por teclado y texto alternativo.

## Objetivos / no objetivos

| Sí haremos | No haremos en 48 horas |
| --- | --- |
| Comparación temporal de regiones seleccionadas | Entrenar un modelo que «descubra» Planet X |
| Vistas de diferencia con explicación | Descargar o servir el mapa total de 102 cubos |
| Pistas visuales con score explicable | Declarar una detección científica nueva |
| Referencias, licencia y demo reproducible | Registro de usuarios ni datos personales |

## Riesgos tempranos

| Riesgo | Mitigación | Dueño |
| --- | --- | --- |
| El endpoint o formato de datos cambia | adaptador con datos de muestra versionados y cita de su procedencia | Datos y API |
| La diferencia es un artefacto | registrar/alinear, marcar calidad y mostrar limitación | Detección y QA |
| Demasiadas funciones | congelar MVP al hito T+18 h | Product owner |
| Demo dependiente de la red | ejecutar ensayo sin internet antes de presentar | Visualización frontend |
