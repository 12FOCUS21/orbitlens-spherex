# Arquitectura y plan de datos

## Arquitectura de MVP

```text
IRSA / recursos NASA ──> adaptador de datos ──> manifiesto de regiones ──> API ligera
                                  │                        │                    │
                                  └── validación ──> caché de demo               ▼
                                                                         Web OrbitLens
                                                                       ┌───────────────┐
                                                                       │ comparador    │
                                                                       │ slider/blink  │
                                                                       │ diferencia    │
                                                                       │ evidencia     │
                                                                       └───────────────┘
```

**Stack recomendado:** TypeScript, React/Vite, mapa con Canvas/WebGL (OpenLayers o deck.gl solo si acelera), API mínima en Python/FastAPI o servidor de funciones, `astropy` para inspección y WCS si se usan FITS. Adoptar una sola ruta de despliegue: frontend estático + API/serverless.

## Contrato de datos mínimo

Cada región debe tener un registro versionado:

```json
{
  "id": "vela-ridge",
  "label": "Vela Molecular Ridge",
  "raDeg": 135.0,
  "decDeg": -45.0,
  "epochs": ["2025-05", "2025-12"],
  "bandsUm": [1.0, 2.0, 4.0],
  "assets": {"epochA": "…", "epochB": "…"},
  "sourceUrl": "https://irsa.ipac.caltech.edu/…",
  "licenseOrCredit": "NASA/JPL-Caltech",
  "processing": ["registered", "normalized percentile 1–99"],
  "caveats": ["visualization only; not a scientific detection"]
}
```

No incorporar datos sin URL de origen, fecha/época, transformación documentada y texto de crédito.

## Ciencia responsable

NASA indica que SPHEREx observa el cielo completo con 102 longitudes de onda infrarrojas y que el primer mapa de todo el cielo se completó en 2025. La misión combinará múltiples sondeos; lo visible como cambio puede provenir de variabilidad, movimiento, diferencias de sensibilidad, alineación o procesado. [Misión y técnica](https://www.jpl.nasa.gov/press-kits/spherex/mission-overview/science/) · [primer mapa](https://www.nasa.gov/missions/spherex/nasas-spherex-observatory-completes-first-cosmic-map-like-no-other/)

Por ello, el panel se titula **«candidato a cambio visual»** y su score es una ayuda de exploración:

```text
score = área coherente × intensidad normalizada × consistencia entre vistas
```

Debe mostrarse como tal, junto con banderas de calidad. Nunca como probabilidad de Planet X ni de una clase astronómica.

## Proceso de prueba de datos

1. Localizar el producto público en IRSA y registrar URL, fecha y crédito.
2. Descargar un recorte pequeño de dos épocas; no clonar archivos globales.
3. Inspeccionar dimensiones, WCS, unidades, valor nulo y orientación en un notebook de exploración.
4. Alinear las épocas a la misma cuadrícula; normalizar de manera explícita.
5. Generar PNG/WebP solo para la demo y conservar los parámetros de generación.
6. Verificar a ojo con vista alternada; registrar si el cambio coincide con bordes, zonas saturadas o máscaras.
7. Entregar el manifiesto y una página `DATA_SOURCES.md` con todas las referencias.

## Plan B de datos y demostración

| Situación | Respuesta |
| --- | --- |
| IRSA disponible | consulta/recorte en vivo y caché local para no repetir llamadas |
| IRSA lento o caído | paquete reducido ya atribuido, visible como «modo demo con datos en caché» |
| No hay dos épocas útiles | usar una secuencia educativa con contenido marcado claramente como simulación; no presentarla como observación |
| Falla WebGL | comparador Canvas/HTML de dos imágenes con el mismo flujo narrativo |

## Seguridad y ética

- No recopilar cuentas, ubicación precisa ni telemetría personal.
- Mantener las claves solo en variables de entorno y excluir `.env` del repositorio.
- Incluir créditos NASA/JPL-Caltech y licencias de bibliotecas, imágenes y datos.
- Publicar únicamente artefactos que el equipo pueda compartir bajo las condiciones del evento.
