# Etapa 4 — Render

Un servicio Python sirve la API y la compilación React. La configuración está en
`render.yaml`; todavía no hay un despliegue público verificado.

Validación local confirmada por el usuario: empaquetado de los cinco presets y
32 pruebas correctas en 1.226 s. El paquete generado ocupa 2,464,219 bytes
(126 archivos). Falta comprobar el arranque de producción y la URL pública.

## Preparación local

Con los cinco presets verificados de la Etapa 2:

```powershell
.\.venv\Scripts\python.exe prepare_deploy.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Revisa e incluye `demo/cache` en tu publicación junto con el código y
`frontend/package-lock.json`. Contiene únicamente manifiestos, PNG y FITS
alineados necesarios para los cinco presets; no incluye los recortes originales.
La excepción de `.gitignore` permite incluir esos FITS. Conserva su atribución
NASA/JPL-Caltech e IRSA y las advertencias científicas de los manifiestos.
El preparador rechaza un destino existente para evitar sobrescribir una demo.

## Publicación

Después de publicar tú los cambios, crea un Blueprint en Render desde este
repositorio y revisa `render.yaml`. Se propone el plan gratuito, sin disco de
pago. El arranque copia los presets empaquetados a la caché e indexa los cinco
sin solicitudes a IRSA ni SIMBAD. Si faltan, el arranque falla explícitamente.

La caché de búsquedas nuevas es temporal; los presets se restauran desde el
paquete en cada arranque. Un solo worker mantiene coherentes los límites y la
cola en memoria. El servicio gratuito puede suspenderse por inactividad: el
primer acceso puede esperar el arranque incluso con presets empaquetados.

## Comprobación pública pendiente

- `/api/health` devuelve 200 y `cached_presets: 5`.
- `/` muestra la aplicación y los cinco presets cargan sus imágenes.
- Reiniciar el servicio y repetir la prueba de presets.
- Comprobar reproducción, slider y tamaño móvil.
- Validar IP recibida tras el proxy antes de dar por verificados los límites
  por visitante; no confiar indiscriminadamente en cabeceras enviadas por clientes.

Quedan pendientes de esta etapa la limpieza de caché con presupuesto de disco,
reintentos IRSA, configuración de colecciones y aviso de frescura. El despliegue
público es el primer hito, no el cierre de toda la etapa.

Fuentes: [FastAPI en Render](https://render.com/docs/deploy-fastapi),
[herramientas del runtime](https://render.com/docs/native-runtimes).
