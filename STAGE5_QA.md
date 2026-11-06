# Etapa 5 — comparación exploratoria

Implementada; pendiente ejecutar Python y comprobar los modos con datos reales.
TypeScript/Vite compilan. El agente no puede ejecutar el Python instalado del
usuario y no atribuye a sí mismo una validación científica o visual en navegador.

## Validación local

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000 --workers 1
```

Suite prevista: 51 pruebas, incluidas once nuevas de análisis. Verifican signo
de la diferencia, máscaras, denominador de la media, color y orientación del PNG,
ceros frente a ausentes, incompatibilidad espectral, épocas, duplicados, WCS,
ausencia de cobertura, validación HTTP y límite de solicitudes.

## Revisión manual

- Barnard: diferencia propuesta entre imágenes 1 y 7; comprobar rojo/azul y
  transparencia. Intercambiar el orden de selección debe invertir el signo.
- RW Aurigae: apilar las imágenes 1 y 2 (intervalo aproximado de 2.51 días).
  Mostrar cobertura, número de contribuciones y advertencia científica.
- Curva central: Barnard, RW Aur y R Dra tienen el centro enmascarado en todos
  los frames; debe aparecer un mensaje sin inventar puntos. Epsilon Indi B
  debe conservar dos fechas ausentes; WISE 0855 tiene doce centros válidos.
- Los puntos de la curva no se unen, sus ejes usan MJD real y MJy/sr; consultar
  fechas y longitudes de onda en la tabla. No confundirlos con flujo del objeto.
- Seleccionar bandas incompatibles o fechas separadas por más de siete días
  para apilado: mostrar error legible y conservar la secuencia original.
- Cambiar secuencia durante el cálculo: ningún resultado anterior debe aparecer
  bajo el nuevo objeto. Revisar selección y tabla en ventana móvil.
- Descargar la PNG; es una vista con estiramiento, no un producto fotométrico.

Parejas calculadas a partir de los metadatos reales empaquetados, aún sin
validación del resultado visual de estos nuevos modos. No hace falta regenerar
presets: se leen los FITS alineados existentes, sin consultas a IRSA.

## API

`POST /api/results/{result_id}/analysis` recibe `mode` (`difference`, `stack`,
`lightcurve`) e `indices` (de cero a N−1, distintos, máximo 16). Diferencia usa
exactamente dos índices y conserva su orden A−B. Devuelve PNG en data URL o
puntos numéricos con valores nulos cuando están enmascarados, unidades y avisos.

El cálculo corre en un thread bajo el semáforo compartido de tres operaciones.
Comparte límite de diez solicitudes/minuto y dos operaciones por IP. No crea
archivos ni requiere nuevas descargas. Mientras se analiza, la limpieza no se
inicia; la desconexión del cliente no libera el permiso hasta terminar el thread.
