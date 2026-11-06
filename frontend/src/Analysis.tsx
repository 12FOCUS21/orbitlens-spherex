import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { Manifest } from './types'

type Mode = 'difference' | 'stack' | 'lightcurve'
interface Point { index: number; mjd: number; date_utc: string; value: number | null; wavelength_um: number | null; reason: string | null }
interface Result { mode: Mode; indices: number[]; unit: string; image?: string; limits?: number[]; valid_fraction?: number; contributors_min?: number; contributors_max?: number; points: Point[]; warnings: string[] }

function suggested(manifest: Manifest, mode: Mode): number[] {
  if (mode === 'lightcurve') return manifest.frames.map((_, i) => i)
  for (let i = 0; i < manifest.frames.length; i++) for (let j = i + 1; j < manifest.frames.length; j++) {
    const a = manifest.frames[i], b = manifest.frames[j]
    const x = a.wavelength_at_target, y = b.wavelength_at_target
    if (a.detector === b.detector && x.central_um && y.central_um && x.width_um && y.width_um &&
      Math.abs(x.central_um - y.central_um) <= Math.min(x.width_um, y.width_um) / 2 &&
      (mode !== 'stack' || Math.abs(a.mjd - b.mjd) <= 7)) return [i, j]
  }
  return []
}

export function Analysis({ manifest, manifestUrl }: { manifest: Manifest; manifestUrl: string }) {
  const [mode, setMode] = useState<Mode>('difference')
  const [selected, setSelected] = useState<number[]>(() => suggested(manifest, 'difference'))
  const [value, setValue] = useState<Result | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  function reset() { controller.current?.abort(); setValue(null); setError(''); setBusy(false) }
  async function calculate() {
    reset()
    const next = new AbortController(); controller.current = next; setBusy(true)
    try {
      const result = await api<Result>(manifestUrl.replace(/\/manifest$/, '/analysis'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, indices: selected }), signal: next.signal,
      })
      if (!next.signal.aborted) setValue(result)
    } catch (reason) { if (!next.signal.aborted) setError(reason instanceof Error ? reason.message : 'Error de análisis') }
    finally { if (!next.signal.aborted) setBusy(false) }
  }
  const points = value?.points.filter(p => p.value !== null) ?? []
  const xMin = Math.min(...points.map(p => p.mjd)), xMax = Math.max(...points.map(p => p.mjd))
  const yMin = Math.min(...points.map(p => p.value!)), yMax = Math.max(...points.map(p => p.value!))
  return <section className="analysis-panel" aria-label="Modos de análisis exploratorio">
    <h2>Comparar observaciones</h2>
    <label>Modo <select value={mode} disabled={busy} onChange={event => { reset(); const next = event.target.value as Mode; setMode(next); setSelected(suggested(manifest, next)) }}>
      <option value="difference">Diferencia A − B</option><option value="stack">Apilado de una época</option><option value="lightcurve">Curva del píxel central</option>
    </select></label>
    <p className="muted">{mode === 'difference' ? 'Selecciona dos imágenes. A es la primera seleccionada y B la segunda. Rojo: A mayor; azul: B mayor; blanco: cero.' : mode === 'stack' ? 'Selecciona al menos dos imágenes de una época exploratoria (máximo siete días). Se calcula la media de valores válidos.' : 'Selecciona las fechas a consultar. Los puntos ausentes no se sustituyen por cero.'} Diferencia y apilado requieren bandas compatibles en el centro. Se propone una pareja compatible cuando existe.</p>
    {mode !== 'lightcurve' && !suggested(manifest, mode).length && <p className="notice">Esta muestra no contiene una pareja compatible para este modo. Prueba otra secuencia; RW Aurigae incluye un ejemplo de apilado en los presets actuales.</p>}
    <fieldset disabled={busy}><legend>Observaciones · orden de selección: {selected.map(i => i + 1).join(', ') || 'ninguna'}</legend>
      <div className="analysis-selection">{manifest.frames.map((frame, i) => <label key={i}>
        <input type="checkbox" checked={selected.includes(i)} onChange={() => { reset(); setSelected(previous => previous.includes(i) ? previous.filter(n => n !== i) : [...previous, i]) }} />
        {i + 1}. {frame.date_utc.replace('T', ' ')} · {frame.wavelength_at_target.central_um?.toFixed(3) ?? '?'} µm
      </label>)}</div>
      {mode === 'lightcurve' && <button type="button" onClick={() => { reset(); setSelected(manifest.frames.map((_, i) => i)) }}>Seleccionar todas</button>}
    </fieldset>
    <button type="button" disabled={busy || !selected.length} onClick={() => void calculate()}>{busy ? 'Calculando…' : 'Calcular'}</button>
    {busy && <p role="status">Leyendo las imágenes alineadas…</p>}
    {error && <p className="notice error" role="alert">{error}</p>}
    {value && <>
      {value.image && <><div className="analysis-image"><img src={value.image} alt={value.mode === 'difference' ? 'Diferencia A menos B, norte arriba y este a la izquierda' : 'Media de las imágenes seleccionadas, norte arriba y este a la izquierda'} /></div>
        <p>Escala asinh: {value.limits?.map(n => n.toPrecision(4)).join(' a ')} {value.unit}. Cobertura válida: {((value.valid_fraction ?? 0) * 100).toFixed(1)} %. Contribuciones: {value.contributors_min}–{value.contributors_max}.</p>
        <a href={value.image} download={`orbitlens-${value.mode}.png`}>Descargar vista PNG</a></>}
      {value.mode === 'lightcurve' && <>
        <h3>Brillo superficial del píxel central · MJy/sr</h3>
        {points.length ? <svg className="lightcurve" viewBox="0 0 620 250" role="img" aria-label="Puntos de brillo superficial frente a MJD; valores exactos en la tabla">
          <path d="M65 20 V205 H600" fill="none" stroke="currentColor" />
          <text x="65" y="228">{xMin.toFixed(2)}</text><text x="600" y="228" textAnchor="end">{xMax.toFixed(2)} MJD</text>
          <text x="60" y="25" textAnchor="end">{yMax.toPrecision(3)}</text><text x="60" y="200" textAnchor="end">{yMin.toPrecision(3)}</text>
          {points.map(p => <circle key={p.index} cx={xMax === xMin ? 330 : 65 + 535 * (p.mjd - xMin) / (xMax - xMin)} cy={yMax === yMin ? 110 : 200 - 175 * (p.value! - yMin) / (yMax - yMin)} r="5" fill="#8ce6d4"><title>{p.date_utc}: {p.value} MJy/sr · {p.wavelength_um} µm</title></circle>)}
        </svg> : <p className="notice">No hay píxeles centrales válidos en las imágenes seleccionadas.</p>}
        <div className="analysis-table"><table><thead><tr><th>UTC</th><th>MJD</th><th>λ µm</th><th>MJy/sr</th></tr></thead><tbody>{value.points.map(p => <tr key={p.index}><td>{p.date_utc}</td><td>{p.mjd.toFixed(5)}</td><td>{p.wavelength_um?.toFixed(3) ?? '—'}</td><td>{p.value === null ? p.reason : p.value.toPrecision(6)}</td></tr>)}</tbody></table></div>
      </>}
      {value.warnings.map(text => <p className="notice" key={text}>{text}</p>)}
    </>}
  </section>
}
