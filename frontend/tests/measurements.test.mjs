import assert from 'node:assert/strict'
import test from 'node:test'
import { wavelengthOrder } from '../src/measurements.ts'

const frame = (wave, mjd) => ({ wavelength_at_target: { central_um: wave }, mjd })

test('orden espectral conserva índices originales y no reordena el tiempo', () => {
  const frames = [frame(4, 61000), frame(1, 61001), frame(2, 61002)]
  const ordered = wavelengthOrder(frames)
  assert.deepEqual(ordered.map(value => value.index), [1, 2, 0])
  assert.deepEqual(frames.map(value => value.mjd), [61000, 61001, 61002])
  assert.equal(ordered[0].item, frames[1])
})

test('mediciones sin longitud de onda utilizable quedan al final', () => {
  const frames = [frame(null), frame(2), frame(NaN), frame(Infinity), frame(0), frame(-1), frame(1)]
  assert.deepEqual(wavelengthOrder(frames).map(value => value.index), [6, 1, 0, 2, 3, 4, 5])
})

test('longitudes iguales mantienen orden original y una lista vacía es válida', () => {
  assert.deepEqual(wavelengthOrder([frame(1), frame(1)]).map(value => value.index), [0, 1])
  assert.deepEqual(wavelengthOrder([]), [])
})
