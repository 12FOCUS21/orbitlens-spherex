import type { Frame } from './types'

export function wavelengthOrder(frames: Frame[]): { item: Frame; index: number }[] {
  const wavelength = (frame: Frame) => {
    const value = frame.wavelength_at_target.central_um
    return value !== null && Number.isFinite(value) && value > 0 ? value : Infinity
  }
  // Devolver índices originales: nunca reordenar el timeline ni los índices FITS.
  return frames.map((item, index) => ({ item, index })).sort((a, b) =>
    wavelength(a.item) - wavelength(b.item) || a.index - b.index)
}
