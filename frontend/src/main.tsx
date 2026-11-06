import { StrictMode, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { createRoot } from 'react-dom/client'
import { api } from './api'
import { Player } from './Player'
import type { Job, Manifest, Preset } from './types'
import './style.css'

const terminal = new Set(['ready', 'partial', 'empty', 'error'])
const labels: Record<string, string> = { barnard: 'Barnard’s Star', 'epsilon-indi-b': 'Epsilon Indi B', wise0855: 'WISE 0855', 'rw-aur': 'RW Aurigae', 'r-dra': 'R Draconis' }

function App() {
  const [presets, setPresets] = useState<Preset[]>([])
  const [mode, setMode] = useState('name')
  const [name, setName] = useState('')
  const [ra, setRa] = useState('')
  const [dec, setDec] = useState('')
  const [fov, setFov] = useState(5)
  const [count, setCount] = useState(12)
  const [detector, setDetector] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [title, setTitle] = useState('')
  const current = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    api<Preset[]>('/api/presets', { signal: controller.signal }).then(setPresets)
      .catch((reason: Error) => { if (!controller.signal.aborted) setError(reason.message) })
    return () => { controller.abort(); current.current?.abort() }
  }, [])

  async function search(body: Record<string, unknown>, label: string) {
    current.current?.abort()
    const controller = new AbortController()
    current.current = controller
    setError(''); setBusy(true); setJob(null); setManifest(null); setTitle(label)
    try {
      let next = await api<Job>('/api/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: controller.signal })
      setJob(next)
      while (!terminal.has(next.status)) {
        await new Promise<void>((resolve, reject) => {
          const abort = () => { window.clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')) }
          const timer = window.setTimeout(() => { controller.signal.removeEventListener('abort', abort); resolve() }, 1200)
          controller.signal.addEventListener('abort', abort, { once: true })
          if (controller.signal.aborted) abort()
        })
        next = await api<Job>(`/api/status/${next.job_id}`, { signal: controller.signal })
        setJob(next)
      }
      if (next.manifest_url) setManifest(await api<Manifest>(next.manifest_url, { signal: controller.signal }))
      else if (next.status === 'error') setError(next.message)
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'La búsqueda no pudo completarse.')
    } finally { if (!controller.signal.aborted) setBusy(false) }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    void search({ ...(mode === 'name' ? { name } : { ra, dec }), fov, frames: count, detector: detector || null }, mode === 'name' ? name : 'Coordenadas ICRS')
  }

  const truncated = manifest && Object.values(manifest.queries).some(query => query.possibly_truncated)
  return <>
    <header className="topbar"><a className="brand" href="/" aria-label="OrbitLens inicio"><span className="orbit-icon" aria-hidden="true">◎</span> OrbitLens <span className="brand-sub">SPHEREx Time Atlas</span></a><a href="https://science.nasa.gov/mission/spherex/" target="_blank" rel="noreferrer">Acerca de SPHEREx ↗</a></header>
    <main>
      <div className="hero"><p className="eyebrow">UN CIELO. DISTINTOS MOMENTOS.</p><h1>El universo también<br /><em>cambia con el tiempo.</em></h1><p>Explora observaciones infrarrojas de SPHEREx. Recorre sus fechas y observa qué cambia en una misma región del cielo.</p></div>
      <div className="workspace">
        <aside className="search-panel">
          <h2>Explorar una región</h2><p className="muted">Elige un campo precargado o busca el tuyo.</p>
          <div className="presets" aria-label="Campos de ejemplo">{presets.map(preset => <button key={preset.id} disabled={busy} onClick={() => void search({ preset: preset.id }, labels[preset.id])}>
            <span>{labels[preset.id] ?? preset.name}</span><small>{preset.cached ? `${preset.frame_count} imágenes · en caché` : 'Consultar archivo'} →</small>
          </button>)}</div>
          <form onSubmit={submit}>
            <label htmlFor="mode">Buscar por</label><select id="mode" value={mode} onChange={event => setMode(event.target.value)}><option value="name">Nombre · SIMBAD</option><option value="coordinates">Coordenadas · ICRS</option></select>
            {mode === 'name' ? <><label htmlFor="name">Nombre del objeto</label><input id="name" value={name} onChange={event => setName(event.target.value)} placeholder="Ej. eps Ind B" required maxLength={200} /><p className="hint">Posición propagada a 2026.5 si SIMBAD dispone de movimiento propio.</p></> : <>
              <label htmlFor="ra">Ascensión recta · RA</label><input id="ra" value={ra} onChange={event => setRa(event.target.value)} placeholder="133.795 o 08h55m10.831s" required maxLength={100} />
              <label htmlFor="dec">Declinación · Dec</label><input id="dec" value={dec} onChange={event => setDec(event.target.value)} placeholder="-7.245 o -07d14m42.53s" required maxLength={100} />
              <p className="hint">Números en grados. RA sexagesimal en horas; Dec en grados. Se explora un centro fijo.</p>
            </>}
            <div className="form-row"><div><label htmlFor="fov">Campo · arcmin</label><input id="fov" type="number" min="1" max="30" step="0.1" value={fov} onChange={event => setFov(Number(event.target.value))} required /></div><div><label htmlFor="count">Imágenes</label><input id="count" type="number" min="1" max="16" value={count} onChange={event => setCount(Number(event.target.value))} required /></div></div>
            <label htmlFor="detector">Detector</label><select id="detector" value={detector} onChange={event => setDetector(event.target.value)}><option value="">Automático · diversidad de fechas</option>{[1, 2, 3, 4, 5, 6].map(value => <option key={value} value={`SPHEREx-D${value}`}>SPHEREx-D{value}</option>)}</select>
            <button className="submit" disabled={busy} type="submit">{busy ? 'Procesando…' : 'Explorar el campo →'}</button><p className="hint">Una búsqueda nueva puede tardar varios minutos. Los ejemplos en caché se abren sin consultar IRSA.</p>
          </form>
        </aside>
        <div className="results">
          {error && <div className="notice error" role="alert">{error}</div>}
          {job && <div className="job-state" role="status"><span className={busy ? 'status-dot working' : 'status-dot'} /><span>{job.message}{job.status === 'queued' && ` Posición en cola: ${job.queue_position}.`}</span>{job.cached && <small>CACHÉ</small>}</div>}
          {!job && !error && <section className="empty-view"><div className="sky-orbit" aria-hidden="true"><span>✦</span></div><p className="eyebrow">TU VENTANA AL INFRARROJO</p><h2>Empieza con un campo de ejemplo</h2><p>Las imágenes se alinean hacia el norte y comparten una misma escala de brillo para recorrer las observaciones.</p><span className="muted">5 campos · datos reales de IRSA · hasta 16 observaciones</span></section>}
          {manifest && <>
            <div className="result-heading"><div><p className="eyebrow">SECUENCIA {manifest.status === 'partial' ? 'PARCIAL' : manifest.status === 'ready' ? 'PROCESADA' : 'SIN SECUENCIA'}</p><h2>{job?.target?.main_id ?? title}</h2></div><span>{manifest.frames.length} imágenes</span></div>
            <p className="muted coordinates">RA {manifest.parameters.ra.toFixed(6)}° · Dec {manifest.parameters.dec.toFixed(6)}° · {manifest.parameters.fov}′{job?.target?.coordinate_epoch_jyear ? ` · centro a época ${job.target.coordinate_epoch_jyear}` : ''}</p>
            {manifest.warnings?.map(warning => <p className="notice" key={warning}>{warning}</p>)}
            {manifest.frames.length > 0 && <>
              <Player key={job?.job_id} manifest={manifest} />
              <p className="notice spectral">Mismo detector no implica misma longitud de onda. Cambios de brillo pueden depender de la banda observada. La longitud de onda indicada es aproximada.</p>
            </>}
            {truncated && <p className="notice">Una consulta alcanzó MAXREC. Esta secuencia es una muestra del archivo; no es un inventario completo.</p>}
            {manifest.requested_count_reached === false && <p className="notice">Hay menos imágenes utilizables de las solicitadas.</p>}
            <details className="evidence"><summary>Procedencia y límites de esta secuencia</summary><p>Procesada: {manifest.created_at_utc}.</p><ul>{manifest.caveats.map(text => <li key={text}>{text}</li>)}</ul><ul>{Object.entries(manifest.queries).map(([collection, query]) => <li key={collection}>{collection}: {query.error ? `consulta fallida · ${query.error}` : `${query.rows} observaciones${query.possibly_truncated ? ' · lista truncada' : ''}`}{query.retrieved_at_utc ? ` · consultada ${query.retrieved_at_utc}` : ''}</li>)}</ul>{manifest.failures.length > 0 && <p>{manifest.failures.length} recortes omitidos por fallos o calidad insuficiente. El manifiesto conserva los detalles.</p>}<a href={job?.manifest_url ?? '#'} target="_blank" rel="noreferrer">Abrir manifiesto JSON ↗</a><p>{manifest.credit}</p></details>
          </>}
        </div>
      </div>
      <p className="science-footer">Herramienta exploratoria. Una secuencia procesada no confirma movimiento ni descubrimientos. La identificación de las fuentes requiere revisión científica.</p>
    </main>
    <footer><span>OrbitLens · Planet X and SPHEREx</span><span>Datos: NASA/JPL-Caltech · Archivo IRSA</span></footer>
  </>
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
