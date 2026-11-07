export function wavelengthOrder(frames) {
  const wavelength = (frame) => {
    const value = frame.wavelength_at_target?.central_um;
    return value !== null && Number.isFinite(value) && value > 0 ? value : Infinity;
  };
  // Conservar índices originales: el selector no cambia el orden temporal.
  return frames.map((item, index) => ({ item, index })).sort((a, b) =>
    wavelength(a.item) - wavelength(b.item) || a.index - b.index);
}
