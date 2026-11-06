import assert from 'node:assert/strict'
import test from 'node:test'
import { fieldQuery, parseFieldLink } from '../src/fieldLinks.ts'

test('una URL sin campo no lanza una búsqueda', () => {
  assert.equal(parseFieldLink(''), null)
  assert.equal(parseFieldLink('?utm_source=demo'), null)
})

test('enlace por coordenadas conserva valores cero y opciones por defecto', () => {
  assert.deepEqual(parseFieldLink('?ra=0&dec=0').body,
    { ra: '0', dec: '0', fov: 5, frames: 12, detector: null })
})

test('el preset respeta FOV, cantidad y detector del enlace', () => {
  assert.deepEqual(parseFieldLink('?preset=barnard&fov=4&frames=2&detector=SPHEREx-D3').body,
    { preset: 'barnard', fov: 4, frames: 2, detector: 'SPHEREx-D3' })
})

test('compartir reproduce las coordenadas exactas del resultado, no vuelve a resolver el preset', () => {
  const parameters = { ra: 269.44615615, dec: 4.76964363, fov: 4, frames: 2, detector: 'SPHEREx-D3' }
  const query = fieldQuery(parameters, 'barnard')
  const field = parseFieldLink(query)
  assert.equal(field.label, 'Barnard’s Star')
  assert.equal(fieldQuery(parameters, field.preset), query)
  assert.deepEqual(field.body, { ra: String(parameters.ra), dec: String(parameters.dec), fov: 4, frames: 2, detector: 'SPHEREx-D3' })
  assert.equal('preset' in field.body, false)
})

test('serialización conserva precisión, signos y detector automático', () => {
  const parameters = { ra: 133.75862792345678, dec: -7.24208853, fov: 5.1, frames: 16, detector: null }
  const { body } = parseFieldLink(fieldQuery(parameters))
  assert.equal(Number(body.ra), parameters.ra)
  assert.equal(Number(body.dec), parameters.dec)
  assert.equal(body.detector, null)
  assert.equal(body.frames, 16)
  assert.equal(body.fov, 5.1)
})

test('coordenadas sexagesimales con signo se conservan para validación en la API', () => {
  const query = '?' + new URLSearchParams({ ra: '08h55m10.831s', dec: '+07d14m42.53s' })
  assert.equal(parseFieldLink(query).body.dec, '+07d14m42.53s')
})

test('enlaces incompletos, ambiguos o con opciones inválidas se rechazan antes de buscar', () => {
  for (const query of ['?ra=10', '?dec=20', '?ra=&dec=0', '?fov=5', '?preset=unknown',
    '?preset=constructor', '?preset=__proto__', '?preset=barnard&frames=true',
    '?ra=0&dec=0&frames=1.5', '?ra=0&dec=0&frames=17', '?ra=0&dec=0&frames=0',
    '?ra=0&dec=0&fov=Infinity', '?ra=0&dec=0&fov=NaN', '?ra=0&dec=0&fov=',
    '?ra=0&dec=0&fov=31', '?ra=0&dec=0&detector=D1', '?preset=barnard&detector=SPHEREx-D7',
    '?ra=0&ra=1&dec=0', '?preset=barnard&preset=wise0855']) {
    assert.throws(() => parseFieldLink(query), Error, query)
  }
})
