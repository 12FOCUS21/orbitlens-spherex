import { test as base, expect, type Page } from '@playwright/test'

const test = base.extend<{ browserErrors: string[] }>({
  browserErrors: [async ({ context }, use) => {
    const errors: string[] = []
    context.on('page', page => page.on('pageerror', error => errors.push(error.message)))
    // Ninguna fuente remota se consulta durante esta regresión.
    await context.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1'
      ? route.continue() : route.abort())
    await use(errors)
    expect(errors, 'Excepciones JavaScript no controladas').toEqual([])
  }, { auto: true }],
})

async function ready(page: Page, timeout = 10_000) {
  await expect(page.locator('#viewer-empty')).toBeHidden({ timeout })
  await expect(page.locator('#field-status')).toHaveText('Secuencia lista')
  await expect(page.locator('#timeline')).toBeEnabled()
}

async function fitsOnScreen(page: Page) {
  const size = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }))
  expect(size.scroll, 'Sin desbordamiento horizontal').toBeLessThanOrEqual(size.width + 1)
}

async function preset(page: Page, id: string) {
  await page.locator(`[data-preset="${id}"]`).click()
  await ready(page)
}

async function calculate(page: Page) {
  const response = page.waitForResponse(response => response.url().endsWith('/analysis') && response.request().method() === 'POST')
  await page.locator('#analysis-run').click()
  const result = await response
  expect(result.status()).toBe(200)
  await expect(page.locator('#analysis-status')).toHaveText('Análisis completado.')
  return result.json()
}

test('carga los cinco presets, el visor y sus miniaturas', async ({ page }) => {
  await page.goto('/')
  await ready(page)
  await expect(page.locator('[data-preset]')).toHaveCount(5)
  await expect(page.locator('#timeline')).toHaveAttribute('max', '11')
  await expect(page.locator('#quality-bits .bit-row')).not.toHaveCount(0)
  await expect(page.locator('#catalog-link')).toHaveAttribute('href', /catalogos\.html\?ra=/)
  const thumbnailWidth = await page.locator('.field-thumb').first().evaluate(node => node.getBoundingClientRect().width)
  expect(thumbnailWidth).toBeGreaterThan(150)
  for (const id of ['epsilon-indi-b', 'wise0855', 'rw-aur', 'r-dra']) {
    await preset(page, id)
    await expect(page.locator('#timeline')).toHaveAttribute('max', '11')
    await fitsOnScreen(page)
  }
})

test('el enlace compartido conserva centro, opciones y etiqueta', async ({ page, context }) => {
  await page.goto('/?preset=wise0855')
  await ready(page)
  const link = page.url()
  const params = new URL(link).searchParams
  expect(params.get('preset')).toBe('wise0855')
  expect(params.get('ra')).not.toBeNull()
  expect(params.get('dec')).not.toBeNull()
  const copy = await context.newPage()
  try {
    await copy.goto(link)
    await ready(copy)
    expect(copy.url()).toBe(link)
    await expect(copy.locator('#ra')).toHaveValue(params.get('ra')!)
    await expect(copy.locator('#dec')).toHaveValue(params.get('dec')!)
    await expect(copy.locator('#fov')).toHaveValue(params.get('fov')!)
    await expect(copy.locator('#frame-count')).toHaveValue(params.get('frames')!)
    await expect(copy.locator('#field-title')).toHaveText('WISE 0855')
    await fitsOnScreen(copy)
  } finally { await copy.close() }
})

test('el formulario consulta coordenadas cacheadas y conserva opciones', async ({ page }) => {
  await page.goto('/?preset=barnard')
  await ready(page)
  const parameters = new URL(page.url()).searchParams
  await page.locator('#mode-coords').click()
  await page.locator('#ra').fill(parameters.get('ra')!)
  await page.locator('#dec').fill(parameters.get('dec')!)
  await page.locator('#frame-count').fill('12')
  await page.locator('#fov').fill('5')
  await page.locator('#search').click()
  await ready(page)
  await expect(page.locator('#field-title')).toContainText('Coordenadas')
  expect(new URL(page.url()).searchParams.get('preset')).toBeNull()
  await fitsOnScreen(page)
})

test('selector espectral detiene reproducción y la calidad distingue máscaras', async ({ page }) => {
  await page.goto('/?preset=barnard')
  await ready(page)
  await page.locator('#play').click()
  await expect(page.locator('#play')).toHaveText('Pausar')
  await page.locator('#measurement-select').selectOption('6')
  await expect(page.locator('#timeline')).toHaveValue('6')
  await expect(page.locator('#play')).toHaveText('Reproducir')
  await expect(page.locator('#quality-summary')).toContainText('rejilla alineada')
  await expect(page.locator('#quality-summary')).toContainText('recorte original')
  await expect(page.locator('#quality-bits')).toContainText('SOURCE')
  await expect(page.locator('#quality-bits')).toContainText('informativo')
  await fitsOnScreen(page)
})

test('diferencia A−B invierte colores al intercambiar observaciones', async ({ page }) => {
  await page.goto('/?preset=barnard')
  await ready(page)
  const first = await calculate(page)
  await expect(page.locator('#analysis-result img')).toBeVisible()
  await page.locator('#analysis-swap').click()
  const second = await calculate(page)
  expect(second.indices).toEqual([...first.indices].reverse())
  const inverse = await page.evaluate(async ([a, b]) => {
    async function pixels(url: string) {
      const image = new Image(); image.src = url; await image.decode()
      const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height
      const context = canvas.getContext('2d')!
      context.drawImage(image, 0, 0)
      return context.getImageData(0, 0, image.width, image.height).data
    }
    const [x, y] = await Promise.all([pixels(a), pixels(b)])
    return x.length === y.length && x.every((value, index) => value === y[index % 4 === 0 ? index + 2 : index % 4 === 2 ? index - 2 : index])
  }, [first.image, second.image])
  expect(inverse).toBe(true)
  await fitsOnScreen(page)
})

test('apilado y curvas conservan puntos válidos y ausentes', async ({ page }) => {
  await page.goto('/?preset=rw-aur')
  await ready(page)
  await page.locator('#analysis-mode').selectOption('stack')
  const stack = await calculate(page)
  expect(stack.contributors_min).toBe(2)
  expect(stack.contributors_max).toBe(2)
  await expect(page.locator('#analysis-result img')).toBeVisible()
  for (const [id, count] of [['wise0855', 12], ['epsilon-indi-b', 10], ['barnard', 0]] as const) {
    await preset(page, id)
    await page.locator('#analysis-mode').selectOption('lightcurve')
    const curve = await calculate(page)
    expect(curve.points.filter((point: { value: number | null }) => point.value !== null)).toHaveLength(count)
    await expect(page.locator('#analysis-result tbody tr')).toHaveCount(12)
    await fitsOnScreen(page)
  }
})

test('enlaces inválidos no inician búsquedas', async ({ page }) => {
  const posts: string[] = []
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/api/search')) posts.push(request.url()) })
  for (const query of ['?ra=10', '?preset=unknown', '?ra=0&dec=0&frames=17', '?preset=barnard&ra=0&ra=1&dec=0']) {
    await page.goto('/' + query)
    await expect(page.locator('#field-status')).toHaveText('Error de secuencia')
    await expect(page.locator('#query-status')).not.toBeEmpty()
    await fitsOnScreen(page)
  }
  expect(posts).toEqual([])
})

test('Aladin sin CDS conserva mensaje y enlace alternativo', async ({ page }) => {
  await page.goto('/catalogos.html?ra=133.75862792&dec=-7.24208853&fov=5')
  await expect(page.getByRole('status')).toContainText('Mapa externo no disponible')
  await expect(page.locator('#external')).toBeVisible()
  expect(new URL((await page.locator('#external').getAttribute('href'))!).searchParams.get('target')).toBe('133.75862792 -7.24208853')
  await fitsOnScreen(page)
})

test('partial y secuencias de dos frames no habilitan animación', async ({ page }) => {
  const response = await page.request.post('/api/search', { data: { preset: 'barnard' } })
  const job = await response.json()
  const source = await (await page.request.get(job.manifest_url)).json()
  let status = 'partial', requested = 12
  await page.route('**/api/search', route => {
    expect(route.request().postDataJSON().frames).toBe(requested)
    return route.fulfill({ status: 202, json: { ...job, status } })
  })
  await page.route('**/api/results/*/manifest', route => route.fulfill({ json: {
    ...source, status, frames: source.frames.slice(0, 2), parameters: { ...source.parameters, frames: requested },
  } }))
  for (const value of ['partial', 'ready']) {
    status = value; requested = status === 'partial' ? 12 : 2
    await page.goto(`/?preset=barnard&frames=${requested}`)
    await expect(page.locator('#field-status')).toHaveText(status === 'partial' ? 'Secuencia parcial' : 'Secuencia lista')
    await expect(page.locator('#timeline')).toBeEnabled()
    await expect(page.locator('#timeline')).toHaveAttribute('max', '1')
    await expect(page.locator('#play')).toBeDisabled()
    await fitsOnScreen(page)
  }
})

test('diez pestañas abren Barnard desde caché sin errores', async ({ context }) => {
  test.setTimeout(90_000)
  const pages = await Promise.all(Array.from({ length: 10 }, () => context.newPage()))
  try {
    await Promise.all(pages.map(async page => {
      await page.goto('/?preset=barnard')
      await ready(page, 45_000)
      await expect(page.locator('#analysis-selection input')).toHaveCount(12)
    }))
  } finally { await Promise.all(pages.map(page => page.close())) }
})

const runningInfinite = () => document.getAnimations().filter(animation =>
  animation.playState === 'running' && animation.effect?.getTiming().iterations === Infinity).length

test('reduce elimina el movimiento y conserva ambas órbitas inclinadas incluso al cambiar en vivo', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/?motion=full&preset=barnard')
  await ready(page)
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'off')
  const snapshot = await page.evaluate(() => {
    const angle = (selector: string) => {
      const matrix = new DOMMatrixReadOnly(getComputedStyle(document.querySelector(selector)!).transform)
      return Math.atan2(matrix.b, matrix.a) * 180 / Math.PI
    }
    return { outer: angle('.cosmos-orbit-outer'), inner: angle('.cosmos-orbit-inner'), running: document.getAnimations().filter(animation => animation.playState === 'running').length }
  })
  expect(snapshot.outer).toBeCloseTo(-24, 0)
  expect(snapshot.inner).toBeCloseTo(55, 0)
  expect(snapshot.running).toBe(0)
  await page.locator('#blink').click()
  await expect(page.locator('#blink')).toHaveAttribute('aria-pressed', 'true')
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'full')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'off')
  await expect(page.locator('#blink')).toHaveAttribute('aria-pressed', 'true')
  expect(await page.evaluate(runningInfinite)).toBe(0)
  await page.locator('#blink').click()
})

test('lite a 390 px respeta el presupuesto, elimina desenfoques y no desborda', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/?motion=lite&preset=barnard')
  await ready(page)
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'lite')
  expect(await page.evaluate(runningInfinite)).toBeLessThanOrEqual(4)
  expect(await page.locator('.site-header').evaluate(node => getComputedStyle(node).backdropFilter)).toBe('none')
  for (const viewport of [{ width: 360, height: 800 }, { width: 390, height: 844 },
    { width: 414, height: 896 }, { width: 844, height: 390 }]) {
    await page.setViewportSize(viewport)
    await fitsOnScreen(page)
  }
})

test('full en escritorio no supera ocho animaciones infinitas', async ({ page }) => {
  await page.setViewportSize({ width: 1360, height: 860 })
  await page.goto('/?motion=full&preset=barnard')
  await ready(page)
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'full')
  expect(await page.evaluate(runningInfinite)).toBeLessThanOrEqual(8)
})

test('la escena orbital se pausa al quedar fuera de pantalla', async ({ page }) => {
  await page.setViewportSize({ width: 1360, height: 860 })
  await page.goto('/?motion=full&preset=barnard')
  await ready(page)
  await page.locator('#campos').scrollIntoViewIfNeeded()
  await expect.poll(() => page.evaluate(() => document.querySelector('.hero')!.getAnimations({ subtree: true }).filter(animation =>
    animation.playState === 'running' && animation.effect?.getTiming().iterations === Infinity).length)).toBe(0)
  await expect(page.locator('.hero')).toHaveAttribute('data-motion-paused', '')
})

test('sin JavaScript el título y la escena permanecen visibles', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } })
  try {
    const page = await context.newPage()
    await page.goto('/')
    await expect(page.locator('#hero-title')).toBeVisible()
    await expect(page.locator('.hero-cosmos')).toBeVisible()
    await expect(page.locator('html')).toHaveAttribute('data-motion', 'off')
    await fitsOnScreen(page)
  } finally { await context.close() }
})

test('la profundidad y el parallax solo se activan en full con puntero preciso', async ({ page }) => {
  await page.setViewportSize({ width: 1360, height: 860 })
  await page.goto('/?motion=full&preset=barnard')
  await ready(page)
  await expect(page.locator('.cosmos-stars-depth')).toBeVisible()
  await page.waitForTimeout(1200)
  const entrance = await page.locator('.hero').evaluate(node => ({
    label: Number(getComputedStyle(node.querySelector('.cosmos-label')!).opacity),
    running: node.getAnimations({ subtree: true }).filter(animation =>
      animation.playState === 'running' && animation.effect?.getTiming().iterations === 1).length,
  }))
  expect(entrance.label).toBe(1)
  expect(entrance.running).toBe(0)
  const fine = await page.evaluate(() => matchMedia('(hover: hover) and (pointer: fine)').matches)
  const bounds = await page.locator('.hero-cosmos').boundingBox()
  expect(bounds).not.toBeNull()
  await page.mouse.move(bounds!.x + bounds!.width * .9, bounds!.y + bounds!.height * .8)
  const offset = await page.locator('.hero-cosmos').evaluate(node => node.style.getPropertyValue('--px'))
  if (fine) {
    await expect.poll(() => page.locator('.hero-cosmos').evaluate(node => node.style.getPropertyValue('--px'))).not.toBe('')
    const x = await page.locator('.hero-cosmos').evaluate(node => parseFloat(node.style.getPropertyValue('--px')))
    expect(Math.abs(x)).toBeGreaterThan(1)
    expect(Math.abs(x)).toBeLessThanOrEqual(3)
    await page.locator('.brand').hover()
    await expect.poll(() => page.locator('.brand-mark').evaluate(node => Math.round(Math.atan2(
      new DOMMatrixReadOnly(getComputedStyle(node).transform).b,
      new DOMMatrixReadOnly(getComputedStyle(node).transform).a) * 180 / Math.PI))).toBe(-13)
  } else expect(offset).toBe('')
  await page.mouse.move(0, 0)
  await expect.poll(() => page.locator('.hero-cosmos').evaluate(node => node.style.getPropertyValue('--px'))).toBe('')
  await page.goto('/?motion=lite&preset=barnard')
  await ready(page)
  await expect(page.locator('.cosmos-stars-depth')).toBeHidden()
  expect(await page.locator('.hero-cosmos').evaluate(node => node.style.getPropertyValue('--px'))).toBe('')
})
