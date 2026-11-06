import { test as base, expect, type Page } from '@playwright/test'

const test = base.extend<{ browserErrors: string[] }>({
  browserErrors: [async ({ context }, use) => {
    const errors: string[] = []
    context.on('page', page => page.on('pageerror', error => errors.push(error.message)))
    // Aislar también las fuentes/CDS: ninguna dependencia externa se consulta.
    await context.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1'
      ? route.continue() : route.abort())
    await use(errors)
    expect(errors, 'Excepciones JavaScript no controladas').toEqual([])
  }, { auto: true }],
})

async function ready(page: Page) {
  await expect(page.getByRole('region', { name: 'Reproductor temporal' })).toBeVisible()
  await expect(page.getByRole('button', { name: '▶ Reproducir', exact: true })).toBeEnabled()
}

async function preset(page: Page, index: number) {
  await page.locator('.presets button').nth(index).click()
  await ready(page)
}

async function fitsOnScreen(page: Page) {
  const sizes = await page.evaluate(() => ({ width: window.innerWidth, scroll: document.documentElement.scrollWidth }))
  expect(sizes.scroll, 'El documento no debe desbordar horizontalmente').toBeLessThanOrEqual(sizes.width + 1)
}

async function calculate(page: Page) {
  const response = page.waitForResponse(response => response.url().endsWith('/analysis') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Calcular', exact: true }).click()
  const result = await response
  expect(result.status()).toBe(200)
  await expect(page.getByRole('button', { name: 'Calcular', exact: true })).toBeEnabled()
  return result.json()
}

test('los cinco presets cargan imágenes y caben en pantalla', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.presets button')).toHaveCount(5)
  for (let index = 0; index < 5; index++) {
    await preset(page, index)
    await expect(page.getByRole('slider', { name: 'Observación', exact: true })).toHaveAttribute('max', '11')
    await expect(page.locator('.viewer canvas')).toHaveJSProperty('width', 49)
    await expect(page.locator('.notice.error')).toHaveCount(0)
    await fitsOnScreen(page)
  }
})

test('un enlace abre el mismo centro, opciones y etiqueta en otra página', async ({ page, context }) => {
  await page.goto('/?preset=wise0855')
  await ready(page)
  const link = page.url()
  const copy = await context.newPage()
  try {
    await copy.goto(link)
    await ready(copy)
    expect(copy.url()).toBe(link)
    const params = new URL(link).searchParams
    await expect(copy.locator('#ra')).toHaveValue(params.get('ra')!)
    await expect(copy.locator('#dec')).toHaveValue(params.get('dec')!)
    await expect(copy.locator('#fov')).toHaveValue(params.get('fov')!)
    await expect(copy.locator('#count')).toHaveValue(params.get('frames')!)
    await expect(copy.locator('#detector')).toHaveValue(params.get('detector') ?? '')
    await expect(copy.locator('.result-heading h2')).toHaveText('WISE 0855')
  } finally { await copy.close() }
})

test('selector espectral detiene reproducción y FLAGS muestra la política', async ({ page }) => {
  await page.goto('/?preset=barnard')
  await ready(page)
  await page.getByRole('button', { name: '▶ Reproducir', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Ⅱ Pausar', exact: true })).toBeVisible()
  await page.getByLabel('Ir a una medición por longitud de onda').selectOption('6')
  await expect(page.getByRole('slider', { name: 'Observación', exact: true })).toHaveValue('6')
  await expect(page.getByRole('button', { name: '▶ Reproducir', exact: true })).toBeVisible()
  await page.getByText('Máscara de calidad de la exposición', { exact: true }).click()
  const quality = page.locator('.viewer details')
  await expect(quality).toHaveAttribute('open', '')
  await expect(quality).toContainText('SOURCE')
  await expect(quality).toContainText('informativa')
  await expect(quality).toContainText('rejilla alineada')
  await fitsOnScreen(page)
})

test('diferencia A−B invierte colores al intercambiar las imágenes', async ({ page }) => {
  await page.goto('/?preset=barnard')
  await ready(page)
  const first = await calculate(page)
  await expect(page.getByRole('img', { name: /Diferencia A menos B/ })).toBeVisible()
  await page.getByRole('button', { name: 'Intercambiar A y B', exact: true }).click()
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

test('apilado y curvas centrales conservan valores válidos y ausentes', async ({ page }) => {
  await page.goto('/?preset=rw-aur')
  await ready(page)
  const mode = page.getByRole('combobox', { name: 'Modo', exact: true })
  await mode.selectOption('stack')
  const stack = await calculate(page)
  expect(stack.contributors_min).toBe(2)
  expect(stack.contributors_max).toBe(2)
  await expect(page.getByRole('img', { name: /Media de las imágenes seleccionadas/ })).toBeVisible()
  await fitsOnScreen(page)
  for (const [index, valid] of [[2, 12], [1, 10], [0, 0]]) {
    await preset(page, index)
    await page.getByRole('combobox', { name: 'Modo', exact: true }).selectOption('lightcurve')
    const curve = await calculate(page)
    expect(curve.points.filter((point: { value: number | null }) => point.value !== null)).toHaveLength(valid)
    await expect(page.locator('.analysis-table tbody tr')).toHaveCount(12)
    await fitsOnScreen(page)
  }
})

test('enlaces inválidos muestran error sin iniciar búsquedas', async ({ page }) => {
  const posts: string[] = []
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/api/search')) posts.push(request.url()) })
  for (const query of ['?ra=10', '?preset=unknown', '?ra=0&dec=0&frames=17']) {
    await page.goto('/' + query)
    await expect(page.getByRole('alert')).toBeVisible()
  }
  expect(posts).toEqual([])
})

test('bandas incompatibles bloquean el cálculo antes de enviar análisis', async ({ page }) => {
  const loaded = page.waitForResponse(response => response.url().endsWith('/manifest'))
  await page.goto('/?preset=barnard')
  await ready(page)
  const source = await (await loaded).json()
  let pair: number[] | undefined
  for (let i = 0; i < source.frames.length && !pair; i++) {
    for (let j = i + 1; j < source.frames.length && !pair; j++) {
      const a = source.frames[i].wavelength_at_target, b = source.frames[j].wavelength_at_target
      if (a.central_um && b.central_um && a.width_um && b.width_um &&
          Math.abs(a.central_um - b.central_um) > Math.min(a.width_um, b.width_um) / 2) pair = [i, j]
    }
  }
  expect(pair, 'El bundle debe ofrecer una pareja incompatible para esta prueba').toBeDefined()
  const posts: string[] = []
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/analysis')) posts.push(request.url()) })
  const boxes = page.locator('.analysis-selection input[type="checkbox"]')
  for (const box of await boxes.all()) if (await box.isChecked()) await box.uncheck()
  for (const index of pair!) await boxes.nth(index).check()
  await expect(page.getByRole('button', { name: 'Calcular', exact: true })).toBeDisabled()
  await expect(page.locator('.analysis-panel [role="status"]')).toContainText('no son compatibles')
  expect(posts).toEqual([])
  await fitsOnScreen(page)
})

test('Aladin sin CDS conserva mensaje y enlace alternativo', async ({ page }) => {
  await page.goto('/catalogos.html?ra=133.75862792&dec=-7.24208853&fov=5')
  await expect(page.getByRole('status')).toContainText('Mapa externo no disponible')
  const link = page.getByRole('link', { name: 'Consultar este campo directamente en Aladin' })
  await expect(link).toBeVisible()
  expect(new URL((await link.getAttribute('href'))!).searchParams.get('target')).toBe('133.75862792 -7.24208853')
  await fitsOnScreen(page)
})

test('partial y solicitud completa de dos frames no habilitan animación', async ({ page }) => {
  const response = await page.request.post('/api/search', { data: { preset: 'barnard' } })
  expect(response.status()).toBe(202)
  const job = await response.json()
  const manifestResponse = await page.request.get(job.manifest_url)
  const source = await manifestResponse.json()
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
    await expect(page.locator('.result-heading')).toContainText(status === 'partial' ? 'PARCIAL' : 'PROCESADA')
    await expect(page.getByRole('slider', { name: 'Observación', exact: true })).toBeEnabled()
    await expect(page.getByRole('button', { name: '▶ Reproducir', exact: true })).toBeDisabled()
    await expect(page.getByRole('slider', { name: 'Observación', exact: true })).toHaveAttribute('max', '1')
    await fitsOnScreen(page)
  }
})

test('diez pestañas cargan un preset simultáneamente', async ({ context }) => {
  const pages = await Promise.all(Array.from({ length: 10 }, () => context.newPage()))
  try {
    await Promise.all(pages.map(async page => {
      await page.goto('/?preset=barnard')
      await ready(page)
      await expect(page.locator('.notice.error')).toHaveCount(0)
    }))
  } finally { await Promise.all(pages.map(page => page.close())) }
})
