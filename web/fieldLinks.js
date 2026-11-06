export const presetLabels = {
  barnard: "Barnard's Star",
  'epsilon-indi-b': 'Epsilon Indi B',
  wise0855: 'WISE 0855',
  'rw-aur': 'RW Aurigae',
  'r-dra': 'R Draconis',
};

const KEYS = ['preset', 'ra', 'dec', 'fov', 'frames', 'detector'];

export function parseFieldLink(search) {
  const params = new URLSearchParams(search);
  if (!KEYS.some((key) => params.has(key))) return null;
  if (KEYS.some((key) => params.getAll(key).length > 1)) {
    throw new Error('El enlace contiene parámetros repetidos.');
  }

  const preset = params.get('preset');
  if (preset !== null && !Object.hasOwn(presetLabels, preset)) {
    throw new Error('El enlace contiene un preset desconocido.');
  }

  function number(key, fallback, min, max, integer = false) {
    const raw = params.get(key);
    const value = raw === null ? fallback : raw.trim() ? Number(raw) : NaN;
    if (!Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) {
      throw new Error(`El parámetro ${key} del enlace está fuera de rango.`);
    }
    return value;
  }

  const fov = number('fov', 5, 1, 30);
  const frames = number('frames', 12, 1, 16, true);
  const detector = params.get('detector') || null;
  if (detector !== null && !/^SPHEREx-D[1-6]$/.test(detector)) {
    throw new Error('El detector del enlace no es válido.');
  }
  const options = { fov, frames, detector };

  // Las coordenadas compartidas fijan el centro exacto. El preset conserva su
  // etiqueta sin volver a resolver posición o movimiento propio con SIMBAD.
  if (params.has('ra') || params.has('dec')) {
    const ra = params.get('ra')?.trim();
    const dec = params.get('dec')?.trim();
    if (!ra || !dec || ra.length > 100 || dec.length > 100) {
      throw new Error('El enlace necesita RA y Dec completas.');
    }
    return {
      body: { ra, dec, ...options },
      label: preset ? presetLabels[preset] : 'Coordenadas ICRS',
      preset: preset ?? undefined,
    };
  }
  if (preset) return { body: { preset, ...options }, label: presetLabels[preset], preset };
  throw new Error('El enlace no contiene un campo reconocido.');
}

export function fieldQuery(parameters, preset) {
  const params = new URLSearchParams();
  if (preset && Object.hasOwn(presetLabels, preset)) params.set('preset', preset);
  for (const key of ['ra', 'dec', 'fov', 'frames', 'detector']) {
    const value = parameters[key];
    if (value != null) params.set(key, String(value));
  }
  return `?${params.toString()}`;
}
