# Validación — Etapa 2

## Estado actual — 2026-11-06

Suite local: **72 pruebas correctas**, 3 avisos conocidos; TypeScript/Vite compilan.
El bundle `demo/cache` contiene cinco manifiestos ready con 12 frames cada uno,
60 PNG, 60 FITS, cinco GIF y cinco target.json. Los GIF/target faltaban en el
bundle anterior: se incorporaron durante la corrección de robustez, sin nuevas
consultas a IRSA. No hay verificación nueva de producción ni QA visual automatizada.

## Registro histórico de la validación científica

La ejecución del usuario, registrada el 2026-11-06 a las 01:35 UTC, completó
los cinco presets con el pipeline **0.2.2**. El agente revisó los manifiestos,
la existencia de los artefactos y una muestra de PNG locales. Esta validación
comprueba cobertura y procesamiento; no confirma identidad, movimiento ni
variabilidad de las fuentes.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe build_sequence.py --verify-presets
```

Las **18 pruebas de aquella etapa** pasaron. Incluyen selección temporal, deduplicación,
orientación WCS, alineación de una fuente sintética con detectores rotados,
escala global, transparencia de máscaras, caché, fallos de red SIMBAD,
propagación de movimiento propio y separación de SIP celestial/espectral.

Los avisos de timeout y HTTP 503 dentro de las pruebas de red son simulados.
La resolución sin distancia produce un aviso ERFA; su resultado se registra
como movimiento propio sin paralaje anual ni velocidad radial.

## Resultados reales

| Objeto | Detector | Colecciones en la secuencia | Frames | Centro enmascarado | Intervalo UTC |
| --- | --- | --- | --- | --- | --- |
| Barnard | D3 | QR2, QR3 | 12 | 12/12 | 2025-08-15 a 2026-08-20 |
| Epsilon Indi B | D2 | QR2, QR3 | 12 | 2/12 | 2025-04-24 a 2026-10-02 |
| WISE 0855 | D2 | QR2 | 12 | 0/12 | 2025-05-06 a 2026-05-14 |
| RW Aurigae | D5 | QR2, QR3 | 12 | 12/12 | 2025-09-08 a 2026-09-15 |
| R Draconis | D1 | QR2, QR2 deep, QR3 deep | 12 | 12/12 | 2025-06-06 a 2026-09-27 |

Se comprobaron los **60 PNG y 60 FITS alineados**. La afirmación anterior de que
también se habían comprobado cinco GIF en el bundle era incorrecta: faltaban.
Ahora están incluidos. Todos los frames están ordenados por MJD y
las 60 lecturas espectrales tienen valores sin error registrado.

Los presets se resolvieron en el mirror SIMBAD de Harvard, después de timeouts
en Strasbourg. El resultado y los fallos previos están en cada `target.json`.
Los centros ICRS se propagaron a la época juliana **2026.5**:

| Objeto | RA (grados) | Dec (grados) |
| --- | --- | --- |
| Barnard | 269.44615615 | +4.76964363 |
| Epsilon Indi B | 331.09767931 | −56.80099136 |
| WISE 0855 | 133.75862792 | −7.24208853 |
| RW Aurigae | 76.95658774 | +30.40128852 |
| R Draconis | 248.16722581 | +66.75502468 |

Estas coordenadas sustituyen las aproximaciones del plan inicial para los
presets. No son posiciones recalculadas para cada exposición.

## Límites observados

- **Calidad del centro:** `ready` significa que la secuencia está procesada.
  Los píxeles inválidos continúan enmascarados. Barnard, RW Aur y R Dra no deben
  presentarse como demostraciones de una detección central validada con estos
  frames. Para sus curvas de luz o ejemplos de movimiento habrá que revisar
  otras bandas/exposiciones y la posición del objeto en cada época.
- **WISE 0855:** QR3 y QR3 deep no devolvieron filas; QR2 permitió completar la
  secuencia. Un recorte dio HTTP 503 y se reemplazó por otro candidato. Que su
  centro sea válido en D2 no demuestra que WISE 0855 sea detectable en esa banda.
- **R Dra:** no hubo filas en QR3 general, pero sí en QR3 deep. La consulta
  QR2 deep alcanzó MAXREC=1000; el inventario y la selección no son exhaustivos.
- **Bandas:** la longitud de onda cambia entre exposiciones de un mismo detector.
  No se han validado comparaciones fotométricas entre esos frames.
- **Astrometría:** las pruebas sintéticas y el muestreo visual comprueban el
  funcionamiento de la reproyección; falta validación astrométrica cuantitativa
  con un catálogo para afirmar desplazamientos medidos.

## Artefactos locales

El informe reproducible es `data/cache/preset_verification.json`. Los manifiestos
de esta ejecución están en:

| Preset | Carpeta dentro de `data/cache/` |
| --- | --- |
| barnard | `76e5f3e44ac9db0b035cc43d/` |
| epsilon-indi-b | `900a67b80fd744bca5af4d4a/` |
| wise0855 | `8912e9ce39460d40ab5a8ea1/` |
| rw-aur | `ca9f5467e482348cb3659aac/` |
| r-dra | `47356868d75d0ac3d8abcaf4/` |

Los datos originales permanecen en `data/`; el bundle portable se incluye en `demo/cache`.
Los manifiestos conservan URLs de IRSA, parámetros, fechas de consulta, WCS,
máscaras, intervalos de visualización y versión del pipeline. Consultar
[SCIENCE.md](SCIENCE.md) para la política de procesamiento y sus fuentes.
