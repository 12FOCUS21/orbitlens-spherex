import { useEffect, useRef, useState } from 'react'
import type { Manifest } from './types'
import { wavelengthOrder } from './measurements'

export function Player({ manifest }: { manifest: Manifest }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [images, setImages] = useState<HTMLImageElement[]>([])
  const [error, setError] = useState('')
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(2)
  const [loop, setLoop] = useState(true)
  const frames = manifest.frames
  const frame = frames[index]
  const ready = images.length === frames.length && images.length > 0
  const canPlay = frames.length >= 3 && ready

  useEffect(() => {
    let active = true
    const controllers: HTMLImageElement[] = []
    setImages([]); setError(''); setIndex(0); setPlaying(false)
    Promise.all(frames.map(item => new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image()
      controllers.push(image)
      image.onload = () => resolve(image)
      image.onerror = () => reject(new Error('No se pudo cargar un frame. Repite la búsqueda para volver a intentarlo.'))
      image.src = item.image_url
    }))).then(value => { if (active) setImages(value) })
      .catch((reason: Error) => { if (active) setError(reason.message) })
    return () => { active = false; controllers.forEach(image => { image.onload = null; image.onerror = null }) }
  }, [frames])

  useEffect(() => {
    const element = canvas.current
    if (!element || !ready) return
    const image = images[index]
    if (!image) return
    element.width = image.naturalWidth
    element.height = image.naturalHeight
    const context = element.getContext('2d')
    if (!context) return
    context.clearRect(0, 0, element.width, element.height)
    context.drawImage(image, 0, 0)
  }, [images, index, ready])

  useEffect(() => {
    if (!playing || !canPlay) return
    const timer = window.setInterval(() => {
      setIndex(previous => {
        if (previous + 1 < frames.length) return previous + 1
        return loop ? 0 : previous
      })
    }, 1000 / speed)
    return () => window.clearInterval(timer)
  }, [playing, canPlay, frames.length, speed, loop])

  useEffect(() => {
    if (!loop && index === frames.length - 1) setPlaying(false)
  }, [index, loop, frames.length])

  if (!frame) return null
  return <section className="viewer" aria-label="Reproductor temporal">
    <div className="viewer-top"><span className="eyebrow">CAMPO INFRARROJO · {frame.detector}</span><span>N ↑ &nbsp; E ←</span></div>
    <div className="sky">
      {!ready && !error && <p className="canvas-message" role="status">Cargando imágenes…</p>}
      {error && <p className="canvas-message error" role="alert">{error}</p>}
      <canvas ref={canvas} aria-label={`Imagen SPHEREx del ${frame.date_utc} UTC. Los píxeles transparentes carecen de datos válidos.`} />
      <div className="sky-label">{frame.date_utc.slice(0, 10)} <small>UTC</small></div>
      {!frame.quality.center_pixel_valid && <span className="masked-label">Centro enmascarado</span>}
    </div>
    <label>Ir a una medición por longitud de onda
      <select value={index} disabled={!ready} onChange={event => { setPlaying(false); setIndex(Number(event.target.value)) }}>
        {wavelengthOrder(frames).map(({item, index}) => <option key={index} value={index}>{item.wavelength_at_target.central_um?.toFixed(3) ?? 'Desconocida'} µm · {item.detector} · {item.date_utc.slice(0,10)} · imagen {index+1}</option>)}
      </select></label>
    <p className="muted">Selecciona una medición existente, no una banda sintética. La longitud de onda es aproximada en el centro y las fechas pueden ser distintas.</p>
    <div className="timeline">
      <label className="sr-only" htmlFor="frame">Observación</label>
      <input id="frame" type="range" min="0" max={frames.length - 1} value={index} disabled={!ready}
        onChange={event => { setPlaying(false); setIndex(Number(event.target.value)) }} />
      <div className="timeline-dates"><span>{frames[0].date_utc.slice(0, 10)}</span><span>{frames.at(-1)?.date_utc.slice(0, 10)}</span></div>
      <div className="player-controls">
        <button className="play" disabled={!canPlay} onClick={() => {
          if (!playing && index === frames.length - 1) setIndex(0)
          setPlaying(!playing)
        }}>{playing ? 'Ⅱ Pausar' : '▶ Reproducir'}</button>
        <span>{index + 1} / {frames.length}</span>
        <label>Velocidad <select value={speed} onChange={event => setSpeed(Number(event.target.value))}>
          <option value="1">1 fps</option><option value="2">2 fps</option><option value="4">4 fps</option>
        </select></label>
        <label className="check"><input type="checkbox" checked={loop} onChange={event => setLoop(event.target.checked)} /> Bucle</label>
      </div>
      <p className="muted">Cadencia visual uniforme. Los intervalos reales entre observaciones pueden ser distintos.
        {!canPlay && frames.length < 3 && ' Con menos de tres frames, revisa cada observación con el deslizador.'}</p>
    </div>
    <dl className="frame-data">
      <div><dt>Fecha UTC</dt><dd>{frame.date_utc.replace('T', ' ')}</dd></div>
      <div><dt>MJD</dt><dd>{frame.mjd.toFixed(6)}</dd></div>
      <div><dt>λ en el centro · aprox.</dt><dd>{frame.wavelength_at_target.central_um?.toFixed(3) ?? 'No disponible'} µm</dd></div>
      <div><dt>Campo válido</dt><dd>{(frame.quality.valid_coverage * 100).toFixed(1)} %</dd></div>
    </dl>
    <p className="quality-note">{frame.quality.center_pixel_valid ? 'El píxel central conserva datos válidos.' : 'El píxel central no puede usarse para evaluar la fuente.'}
      {' '}FLAGS del centro: {frame.quality.center_pixel_flag_names.join(', ') || 'ninguno'}.
      {' '}Los huecos transparentes muestran el fondo cuadriculado.</p>
    <details className="evidence"><summary>Máscara de calidad de la exposición</summary>
      <p>Fracción enmascarada en el recorte original: {frame.quality.masked_fraction == null ? 'sin información' : (100*frame.quality.masked_fraction).toFixed(1)+' %'}.</p>
      <p>Estas fracciones describen el recorte original; la cobertura válida anterior corresponde a la rejilla alineada. Los bits desconocidos se conservan sin excluir: no equivalen a calidad validada.</p>
      <ul>{frame.quality.bits?.map(bit => <li key={bit.bit}>Bit {bit.bit} · {bit.name} · {(bit.fraction*100).toFixed(1)} % · {bit.masked ? 'excluida' : bit.name.startsWith('UNDOCUMENTED') ? 'desconocida, no excluida' : 'informativa'}</li>)}</ul></details>
    <div className="source-links"><span>{frame.collection}</span><a href={frame.cutout_url} target="_blank" rel="noreferrer">Recorte original · IRSA ↗</a><a href={frame.fits_url}>FITS alineado ↓</a></div>
  </section>
}
