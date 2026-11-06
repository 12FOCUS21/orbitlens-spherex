import type { Manifest } from './types'

export const presetLabels: Record<string, string> = {
  barnard: 'Barnard’s Star', 'epsilon-indi-b': 'Epsilon Indi B', wise0855: 'WISE 0855',
  'rw-aur': 'RW Aurigae', 'r-dra': 'R Draconis',
}

type SearchBody = { preset?: string; ra?: string; dec?: string; fov: number; frames: number; detector: string | null }
export interface SharedField { body: SearchBody; label: string; preset?: string }

export function parseFieldLink(search: string): SharedField | null {
  const params = new URLSearchParams(search)
  const keys = ['preset', 'ra', 'dec', 'fov', 'frames', 'detector']
  if (!keys.some(key => params.has(key))) return null
  if (keys.some(key => params.getAll(key).length > 1)) throw new Error('El enlace contiene parámetros repetidos.')
  const preset = params.get('preset')
  if (preset !== null && !Object.hasOwn(presetLabels, preset)) throw new Error('El enlace contiene un preset desconocido.')
  function number(key: string, fallback: number, min: number, max: number, integer = false) {
    const raw = params.get(key)
    const value = raw === null ? fallback : raw.trim() ? Number(raw) : NaN
    if (!Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) {
      throw new Error(`El parámetro ${key} del enlace está fuera de rango.`)
    }
    return value
  }
  const fov = number('fov', 5, 1, 30)
  const frames = number('frames', 12, 1, 16, true)
  const detector = params.get('detector') || null
  if (detector !== null && !/^SPHEREx-D[1-6]$/.test(detector)) throw new Error('El detector del enlace no es válido.')
  const options = { fov, frames, detector }
  // Las coordenadas guardadas reproducen el centro exacto, aunque un preset
  // cambie de posición/época en futuras versiones. El preset conserva su etiqueta.
  if (params.has('ra') || params.has('dec')) {
    const ra = params.get('ra')?.trim(), dec = params.get('dec')?.trim()
    if (!ra || !dec || ra.length > 100 || dec.length > 100) throw new Error('El enlace necesita RA y Dec completas.')
    // La API valida los rangos ICRS y el formato sexagesimal con Astropy.
    return { body: { ra, dec, ...options }, label: preset ? presetLabels[preset] : 'Coordenadas ICRS', preset: preset ?? undefined }
  }
  if (preset) return { body: { preset, ...options }, label: presetLabels[preset], preset }
  throw new Error('El enlace no contiene un campo reconocido.')
}

export function fieldQuery(parameters: Manifest['parameters'], preset?: string): string {
  const params = new URLSearchParams()
  if (preset && Object.hasOwn(presetLabels, preset)) params.set('preset', preset)
  for (const key of ['ra', 'dec', 'fov', 'frames', 'detector'] as const) {
    const value = parameters[key]
    if (value != null) params.set(key, String(value))
  }
  return '?' + params.toString()
}
