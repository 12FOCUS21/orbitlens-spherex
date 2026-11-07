import { api, health, presets as fetchPresets, search, poll } from './api.js';
import { Player } from './player.js';
import { Analysis } from './analysis.js';
import { presetLabels, parseFieldLink, fieldQuery } from './fieldLinks.js';
import {
  esc, num, coord, pct, shortDate, dateLong, sexFromDegrees, parseRaSex, parseDecSex,
} from './format.js';

const state = {
  presets: [],
  current: null,
  controller: null,
  busy: false,
  queryMode: 'name',
  coordMode: 'deg',
  progressTimer: null,
  elapsedTimer: null,
  startedAt: 0,
  toastTimer: null,
};

const el = {
  connection: document.getElementById('connection'),
  connectionText: document.getElementById('connection-text'),
  helpOpen: document.getElementById('help-open'),
  helpDialog: document.getElementById('help-dialog'),
  fieldKicker: document.getElementById('field-kicker'),
  fieldTitle: document.getElementById('field-title'),
  fieldCoords: document.getElementById('field-coords'),
  fieldStatus: document.getElementById('field-status'),
  catalogLink: document.getElementById('catalog-link'),
  share: document.getElementById('share'),
  summary: document.getElementById('summary'),
  metricCoverage: document.getElementById('metric-coverage'),
  metricWavelength: document.getElementById('metric-wavelength'),
  metricCadence: document.getElementById('metric-cadence'),
  metricFrames: document.getElementById('metric-frames'),
  currentCard: document.getElementById('current-card'),
  compareCard: document.getElementById('compare-card'),
  noPairNote: document.getElementById('no-pair-note'),
  qualitySummary: document.getElementById('quality-summary'),
  qualityDetails: document.getElementById('quality-details'),
  qualityBits: document.getElementById('quality-bits'),
  qualityNote: document.getElementById('quality-note'),
  provenance: document.getElementById('provenance'),
  objectNote: document.getElementById('object-note'),
  stageNote: document.getElementById('stage-note'),
  fieldGrid: document.getElementById('field-grid'),
  query: document.getElementById('query'),
  modeName: document.getElementById('mode-name'),
  modeCoords: document.getElementById('mode-coords'),
  nameFields: document.getElementById('name-fields'),
  coordFields: document.getElementById('coord-fields'),
  name: document.getElementById('name'),
  ra: document.getElementById('ra'),
  dec: document.getElementById('dec'),
  raSex: document.getElementById('ra-sex'),
  decSex: document.getElementById('dec-sex'),
  coordDeg: document.getElementById('coord-deg'),
  coordSex: document.getElementById('coord-sex'),
  degFields: document.getElementById('deg-fields'),
  sexFields: document.getElementById('sex-fields'),
  fov: document.getElementById('fov'),
  frames: document.getElementById('frame-count'),
  detector: document.getElementById('detector'),
  search: document.getElementById('search'),
  queryStatus: document.getElementById('query-status'),
  progress: document.getElementById('progress'),
  progressText: document.getElementById('progress-text'),
  elapsed: document.getElementById('elapsed'),
  toast: document.getElementById('toast'),
};

const player = new Player({
  onChange: (value) => renderInspector(value),
  onHelp: () => el.helpDialog.showModal(),
  onNotice: (message) => showToast(message),
});

const analysis = new Analysis();

function showToast(message) {
  el.toast.textContent = message;
  el.toast.classList.add('show');
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => el.toast.classList.remove('show'), 2800);
}

async function copyText(value, message = 'Copiado') {
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const area = document.createElement('textarea');
    area.value = value;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.append(area);
    area.select();
    try { document.execCommand('copy'); } catch { /* no-op */ }
    area.remove();
  }
  showToast(message);
}

function setConnection(kind) {
  const labels = {
    offline: ['offline', 'API no disponible'],
    online: ['online', 'Servidor listo'],
    busy: ['busy', 'Consultando…'],
  };
  const [name, text] = labels[kind] || labels.online;
  el.connection.dataset.state = name;
  el.connectionText.textContent = text;
}

function setQueryStatus(message, tone = '') {
  el.queryStatus.textContent = message;
  el.queryStatus.className = `query-status${tone ? ` ${tone}` : ''}`;
}

function setBusyUi(busy) {
  state.busy = busy;
  el.search.disabled = busy;
  el.search.textContent = busy ? 'Consultando…' : 'Consultar IRSA';
  el.fieldGrid.querySelectorAll('button').forEach((button) => { button.disabled = busy; });
}

function setBadge(status) {
  const labels = {
    ready: ['Secuencia lista', 'ok'],
    partial: ['Secuencia parcial', 'warn'],
    empty: ['Sin secuencia', 'muted'],
    error: ['Error de secuencia', 'warn'],
  };
  const [text, tone] = labels[status] || ['Sin cargar', 'muted'];
  el.fieldStatus.textContent = text;
  el.fieldStatus.className = `badge ${tone}`;
}

function startProgress() {
  const messages = [
    'Consultando IRSA…',
    'Resolviendo el campo y las fechas…',
    'Descargando y alineando recortes…',
    'Preparando la secuencia…',
  ];
  state.startedAt = Date.now();
  let index = 0;
  el.progress.hidden = false;
  el.progressText.textContent = messages[0];
  el.elapsed.textContent = '0 s';
  clearInterval(state.progressTimer);
  clearInterval(state.elapsedTimer);
  state.progressTimer = setInterval(() => {
    index = (index + 1) % messages.length;
    el.progressText.textContent = messages[index];
  }, 9000);
  state.elapsedTimer = setInterval(() => {
    el.elapsed.textContent = `${Math.round((Date.now() - state.startedAt) / 1000)} s`;
  }, 1000);
}

function stopProgress() {
  clearInterval(state.progressTimer);
  clearInterval(state.elapsedTimer);
  state.progressTimer = null;
  state.elapsedTimer = null;
  el.progress.hidden = true;
}

function presetLabel(preset) {
  return presetLabels[preset.id] || preset.target?.name || preset.name || preset.id;
}

function renderGallery() {
  if (!state.presets.length) {
    el.fieldGrid.innerHTML = '<p class="gallery-note">No se pudieron cargar los campos precargados.</p>';
    return;
  }
  el.fieldGrid.innerHTML = state.presets.map((preset) => {
    const active = state.current?.presetId === preset.id;
    const label = presetLabel(preset);
    const preview = preset.preview_url
      ? `<img src="${esc(preset.preview_url)}" alt="" loading="lazy">`
      : `<div class="thumb-placeholder">SPHEREx</div>`;
    return `<button class="field-card" type="button" data-preset="${esc(preset.id)}" aria-pressed="${active}" ${state.busy ? 'disabled' : ''}>
      <div class="field-thumb">${preview}<span class="badge ${preset.cached ? 'ok' : 'warn'} thumb-badge">${preset.cached ? 'En caché' : 'Consultar'}</span></div>
      <h3>${esc(label)}</h3>
      <p class="field-sub">${preset.target?.main_id ? esc(preset.target.main_id) : 'Secuencia SPHEREx'}</p>
      <div class="field-meta"><span>${preset.frame_count || 0} imágenes</span><span>${preset.target?.ra_deg != null ? `RA ${coord(preset.target.ra_deg, 3)}°` : 'IRSA'}</span>${active ? '<span class="active-mark">En el visor</span>' : ''}</div>
    </button>`;
  }).join('');
}

async function loadPresets() {
  try {
    state.presets = await fetchPresets();
    renderGallery();
  } catch (error) {
    state.presets = [];
    renderGallery();
    setQueryStatus(error.message, 'error');
  }
}

function jobProgress(job) {
  if (job.status === 'queued') return `En cola${job.queue_position ? ` · posición ${job.queue_position}` : ''}…`;
  if (job.status === 'resolving') return 'Resolviendo el nombre con SIMBAD…';
  if (job.status === 'searching') return 'Consultando y alineando observaciones…';
  return job.message || 'Procesando…';
}

function onJobUpdate(job) {
  el.progressText.textContent = jobProgress(job);
  setQueryStatus(job.message || jobProgress(job), job.status === 'error' ? 'error' : '');
}

async function runSearch(body, options = {}) {
  const { presetId = null, title = '' } = options;
  state.controller?.abort();
  const controller = new AbortController();
  state.controller = controller;
  state.current = null;
  setBusyUi(true);
  setConnection('busy');
  setQueryStatus('');
  startProgress();
  player.clear('Consultando el archivo', 'La consulta puede tardar varios minutos. Los presets en caché se abren sin descargar.');
  analysis.clear();
  el.catalogLink.classList.add('is-disabled');
  el.catalogLink.setAttribute('aria-disabled', 'true');
  el.catalogLink.href = '#';
  el.fieldKicker.textContent = 'Secuencia SPHEREx';
  el.fieldTitle.textContent = title || 'Consultando campo';
  el.fieldCoords.textContent = 'RA — · Dec —';
  setBadge('queued');
  try {
    let job = await search(body, controller.signal);
    onJobUpdate(job);
    job = await poll(job, { signal: controller.signal, onUpdate: onJobUpdate });
    if (job.status === 'error') {
      player.clear('No se pudo completar la búsqueda', job.message || 'Revisa el nombre o las coordenadas y vuelve a intentarlo.');
      setQueryStatus(job.message || 'La búsqueda falló.', 'error');
      setBadge('error');
      return;
    }
    if (!job.manifest_url) {
      player.clear('Sin secuencia', job.message || 'No hay imágenes utilizables para este campo.');
      setQueryStatus(job.message || 'No se encontró una secuencia.', 'error');
      setBadge(job.status);
      return;
    }
    const manifest = await api(job.manifest_url, { signal: controller.signal });
    showResult(job, manifest, { presetId, title });
  } catch (error) {
    if (controller.signal.aborted) return;
    player.clear('No se pudo cargar el campo', error.message || 'Comprueba la conexión y vuelve a intentarlo.');
    setQueryStatus(error.message || 'La búsqueda falló.', 'error');
    setConnection(navigator.onLine ? 'online' : 'offline');
    setBadge('error');
  } finally {
    if (!controller.signal.aborted) {
      setBusyUi(false);
      stopProgress();
      setConnection(navigator.onLine ? 'online' : 'offline');
    }
  }
}

function showResult(job, manifest, { presetId = null, title = '' } = {}) {
  const target = job.target || null;
  state.current = {
    job,
    manifest,
    resultId: job.result_id,
    target,
    presetId,
    title: title || target?.main_id || target?.name || 'Campo SPHEREx',
  };
  el.fieldKicker.textContent = `Secuencia SPHEREx · ${manifest.detector || 'detector automático'}`;
  el.fieldTitle.textContent = presetId
    ? state.current.title
    : target?.main_id || target?.name || state.current.title;
  const parameters = manifest.parameters || {};
  el.fieldCoords.textContent = `RA ${num(parameters.ra, 4)}° · Dec ${num(parameters.dec, 4)}° · campo ${num(parameters.fov, 1)}′`;
  el.ra.value = String(parameters.ra);
  el.dec.value = String(parameters.dec);
  el.fov.value = String(parameters.fov);
  el.frames.value = String(parameters.frames);
  el.detector.value = parameters.detector || '';
  const catalog = new URLSearchParams({ ra: String(parameters.ra), dec: String(parameters.dec), fov: String(parameters.fov) });
  el.catalogLink.href = `/catalogos.html?${catalog}`;
  el.catalogLink.classList.remove('is-disabled');
  el.catalogLink.setAttribute('aria-disabled', 'false');
  setBadge(manifest.status);
  player.setManifest(manifest, job.result_id);
  analysis.setManifest(manifest, job.result_id);
  renderInspector({
    frame: manifest.frames[0] || null,
    compareFrame: manifest.frames[manifest.frames.length - 1] || null,
    index: 0,
    compareIndex: Math.max(0, manifest.frames.length - 1),
    frames: manifest.frames,
  });
  writeUrl();
  renderGallery();
  const statusText = manifest.status === 'ready'
    ? 'Secuencia lista. Recorre las fechas o abre el análisis exploratorio.'
    : manifest.status === 'partial'
      ? 'Secuencia parcial: faltan algunas observaciones. La evidencia disponible sigue siendo revisable.'
      : manifest.status === 'empty'
        ? 'No hay imágenes utilizables para este campo.'
        : 'La secuencia terminó con un estado no listo.';
  setQueryStatus(statusText, manifest.status === 'ready' ? 'ok' : '');
}

function frameCard(frame, letter, label) {
  if (!frame) return '<p class="muted">No hay un fotograma seleccionado.</p>';
  const lambda = frame.wavelength_at_target || {};
  const quality = frame.quality || {};
  const exposure = frame.exposure_seconds ? `${num(frame.exposure_seconds, 1)} s` : '—';
  return `<div class="epoch-head">
      <span class="epoch-letter">${letter}</span>
      <strong>${esc(label)}</strong>
      <span class="epoch-date">${esc(shortDate(frame.date_utc))}</span>
    </div>
    <dl>
      <div><dt>Producto</dt><dd>${esc(frame.obs_id || '—')}</dd></div>
      <div><dt>Fecha UTC</dt><dd>${esc(dateLong(frame.date_utc))}</dd></div>
      <div><dt>Detector</dt><dd>${esc(frame.detector || '—')}</dd></div>
      <div><dt>Longitud de onda</dt><dd>${lambda.central_um == null ? '—' : `${esc(num(lambda.central_um, 4))} µm`}${lambda.width_um == null ? '' : ` · ancho ${esc(num(lambda.width_um, 4))} µm`}</dd></div>
      <div><dt>Exposición</dt><dd>${esc(exposure)}</dd></div>
      <div><dt>Cobertura alineada</dt><dd>${pct(quality.valid_coverage)}</dd></div>
      <div><dt>Máscara original</dt><dd>${pct(quality.masked_fraction)}</dd></div>
      <div><dt>Flags centrales</dt><dd>${esc((quality.center_pixel_flag_names || []).join(', ') || 'ninguno')} ${quality.center_pixel_valid ? '· válido' : '· enmascarado'}</dd></div>
      <div><dt>Recorte</dt><dd>${frame.cutout_url ? `<a href="${esc(frame.cutout_url)}" target="_blank" rel="noopener">IRSA ↗</a>` : '—'}</dd></div>
      <div><dt>FITS</dt><dd>${frame.fits_url ? `<a href="${esc(frame.fits_url)}">Alineado ↓</a>` : '—'}</dd></div>
      <div><dt>Original</dt><dd>${frame.access_url ? `<a href="${esc(frame.access_url)}" target="_blank" rel="noopener">Acceso ↗</a>` : '—'}</dd></div>
    </dl>`;
}

function renderQuality(frame) {
  if (!frame) {
    el.qualitySummary.textContent = 'No hay un fotograma activo.';
    el.qualityBits.innerHTML = '';
    el.qualityNote.textContent = '';
    return;
  }
  const quality = frame.quality || {};
  const bits = Array.isArray(quality.bits) ? [...quality.bits].sort((a, b) => b.fraction - a.fraction) : [];
  el.qualitySummary.textContent = `Cobertura válida en rejilla alineada ${pct(quality.valid_coverage)} · máscara en recorte original ${pct(quality.masked_fraction)} · señal original ${pct(quality.nonzero_fraction)}.`;
  el.qualityBits.innerHTML = bits.length
    ? bits.map((bit) => `<div class="bit-row ${bit.masked ? 'is-masked' : bit.name.startsWith('UNDOCUMENTED') ? 'is-unknown' : 'is-info'}">
        <span class="bit-name">${esc(bit.name)}</span>
        <span class="bit-index">bit ${bit.bit}</span>
        <span class="bit-fraction">${pct(bit.fraction, 2)}</span>
        <span class="bit-state">${bit.masked ? 'enmascara' : bit.name.startsWith('UNDOCUMENTED') ? 'desconocido · no excluido' : 'informativo'}</span>
      </div>`).join('')
    : '<p class="muted">No hay bits de calidad detallados para este fotograma.</p>';
  const center = quality.center_pixel_valid
    ? 'El píxel central conserva datos válidos.'
    : 'El píxel central está enmascarado; la curva central no puede medirlo.';
  el.qualityNote.textContent = `${center} Las fracciones de FLAGS describen el recorte original; la cobertura válida corresponde a la rejilla alineada. SOURCE es informativo. Un bit desconocido sin excluir no equivale a calidad validada.`;
  el.qualityDetails.open = !quality.center_pixel_valid;
}

function renderProvenance(manifest, job) {
  const queries = Object.entries(manifest.queries || {}).map(([collection, query]) => {
    const details = query.error
      ? `error: ${query.error}`
      : `${query.rows ?? '—'} filas${query.possibly_truncated ? ' · truncada' : ''}${query.retrieved_at_utc ? ` · consultada ${query.retrieved_at_utc}` : ''}`;
    return `<li><b>${esc(collection)}</b>: ${esc(details)}</li>`;
  }).join('');
  const caveats = (manifest.caveats || []).map((text) => `<li>${esc(text)}</li>`).join('');
  const warnings = (manifest.warnings || []).map((text) => `<li>${esc(text)}</li>`).join('');
  const failures = (manifest.failures || []).map((item) => `<li>${esc(item.error || String(item))}</li>`).join('');
  const resultId = job?.result_id;
  const products = resultId
    ? `<div class="prov-item"><b>Productos</b> · <a href="${esc(job.manifest_url)}" target="_blank" rel="noopener">Manifiesto JSON ↗</a> · <a href="/api/results/${esc(resultId)}/target.json" target="_blank" rel="noopener">Objetivo JSON ↗</a>${manifest.preview?.image_url ? ` · <a href="${esc(manifest.preview.image_url)}" target="_blank" rel="noopener">Secuencia GIF ↗</a>` : ''}</div>`
    : '';
  el.provenance.innerHTML = `<div class="prov-item">
      <b>Resultado</b> · ${esc(manifest.status)} · ${esc(manifest.created_at_utc || 'fecha no disponible')}<br>
      <b>Pipeline</b> · ${esc(manifest.pipeline_version || '—')} · ${esc(manifest.detector || '—')}<br>
      <b>Parámetros</b> · RA ${esc(num(manifest.parameters?.ra, 6))}° · Dec ${esc(num(manifest.parameters?.dec, 6))}° · ${esc(num(manifest.parameters?.fov, 1))}′ · ${esc(manifest.parameters?.frames ?? '—')} imágenes<br>
      <b>Disponibles</b> · ${esc(manifest.available_observations ?? '—')} observaciones · ${esc(manifest.requested_count_reached ? 'se alcanzó el número solicitado' : 'menos imágenes de las solicitadas')}<br>
      <b>Fuente</b> · ${esc(manifest.credit || 'NASA/IPAC IRSA')}<br>
      <b>Política de máscara</b> · ${esc((manifest.quality_policy?.mask_bits || []).join(', ') || 'no disponible')}
      ${job?.result_id ? `<br><b>Resultado</b> · ${esc(job.result_id)}` : ''}
    </div>
    ${warnings ? `<div class="prov-item"><b>Avisos</b><ul>${warnings}</ul></div>` : ''}
    ${caveats ? `<div class="prov-item"><b>Límites</b><ul>${caveats}</ul></div>` : ''}
    ${queries ? `<div class="prov-item"><b>Consultas</b><ul>${queries}</ul></div>` : ''}
    ${failures ? `<div class="prov-item"><b>Recortes omitidos</b><ul>${failures}</ul></div>` : ''}
    ${products}`;
}

function renderInspector(value) {
  const current = state.current;
  if (!current?.manifest) {
    el.summary.textContent = 'Cargando la secuencia y sus metadatos.';
    el.metricCoverage.textContent = '—';
    el.metricWavelength.textContent = '—';
    el.metricCadence.textContent = '—';
    el.metricFrames.textContent = '—';
    el.currentCard.innerHTML = '';
    el.compareCard.innerHTML = '';
    el.qualitySummary.textContent = 'No hay un fotograma activo.';
    el.qualityBits.innerHTML = '';
    el.qualityNote.textContent = '';
    el.provenance.innerHTML = '';
    return;
  }
  const manifest = current.manifest;
  const frames = manifest.frames || [];
  const frame = value?.frame || frames[0] || null;
  const compare = value?.compareFrame || frames[frames.length - 1] || null;
  const first = frames[0];
  const last = frames[frames.length - 1];
  const days = first && last ? Math.abs(last.mjd - first.mjd) : 0;
  const target = current.target;
  const displayTarget = current.presetId
    ? current.title
    : target?.main_id || target?.name || current.title;
  el.summary.textContent = frames.length
    ? `${displayTarget} reúne ${frames.length} exposiciones de ${manifest.detector || 'SPHEREx'} entre ${shortDate(first.date_utc)} y ${shortDate(last.date_utc)}. La secuencia está alineada y normalizada para revisar cambios aparentes.`
    : 'La secuencia no contiene imágenes utilizables.';
  el.metricCoverage.textContent = frame ? pct(frame.quality?.valid_coverage) : '—';
  el.metricWavelength.textContent = frame?.wavelength_at_target?.central_um == null
    ? '—'
    : `${num(frame.wavelength_at_target.central_um, 3)} µm`;
  el.metricCadence.textContent = frames.length > 1 ? `${num(days, 0)} días` : '—';
  el.metricFrames.textContent = `${frames.length} / ${manifest.parameters?.frames ?? manifest.requested_frames ?? '—'}`;
  el.currentCard.innerHTML = frameCard(frame, 'A', 'Fotograma actual');
  el.compareCard.innerHTML = frameCard(compare, 'B', 'Comparación');
  renderQuality(frame);
  renderProvenance(manifest, current.job);
  const notes = [];
  if (manifest.warnings?.length) notes.push(...manifest.warnings);
  if (manifest.failures?.length) notes.push(`${manifest.failures.length} recortes omitidos por fallos o calidad insuficiente.`);
  if (Object.values(manifest.queries || {}).some((query) => query.possibly_truncated)) notes.push('Una consulta alcanzó MAXREC. Esta muestra no es un inventario completo del archivo.');
  if (manifest.requested_count_reached === false) notes.push('Hay menos imágenes utilizables de las solicitadas.');
  el.noPairNote.hidden = !notes.length;
  el.noPairNote.textContent = notes.join(' ');
  el.objectNote.textContent = target?.caveat
    ? `${target.caveat} Una secuencia procesada no demuestra movimiento ni detección.`
    : 'Una secuencia procesada no demuestra movimiento ni detección. La identificación de fuentes y la interpretación física requieren revisión científica.';
  el.stageNote.textContent = `${manifest.warnings?.[0] || 'Las imágenes comparten encuadre y escala.'} Los recuadros transparentes indican píxeles sin datos válidos.`;
}

function writeUrl() {
  const current = state.current;
  if (!current) return;
  try {
    const url = new URL(window.location.href);
    url.search = fieldQuery(current.manifest.parameters || {}, current.presetId);
    window.history.replaceState(null, '', url);
  } catch {
    /* file:// puede rechazar history */
  }
}

function setSearchMode(mode) {
  state.queryMode = mode;
  const names = mode === 'name';
  el.modeName.setAttribute('aria-pressed', String(names));
  el.modeCoords.setAttribute('aria-pressed', String(!names));
  el.nameFields.hidden = !names;
  el.coordFields.hidden = names;
}

function setCoordMode(mode, convert = true) {
  if (convert) {
    if (mode === 'sex') {
      const degrees = readDegrees();
      if (degrees) {
        const sex = sexFromDegrees(degrees.ra, degrees.dec);
        el.raSex.value = sex.ra;
        el.decSex.value = sex.dec;
      }
    } else {
      const ra = parseRaSex(el.raSex.value);
      const dec = parseDecSex(el.decSex.value);
      if (ra != null && dec != null) {
        el.ra.value = ra.toFixed(6);
        el.dec.value = dec.toFixed(6);
      }
    }
  }
  state.coordMode = mode;
  const degrees = mode === 'deg';
  el.coordDeg.setAttribute('aria-pressed', String(degrees));
  el.coordSex.setAttribute('aria-pressed', String(!degrees));
  el.degFields.hidden = !degrees;
  el.sexFields.hidden = degrees;
}

function readDegrees() {
  const raText = String(el.ra.value).replace(',', '.').trim();
  const decText = String(el.dec.value).replace(',', '.').trim();
  if (!raText || !decText) return null;
  const ra = Number(raText);
  const dec = Number(decText);
  if (!Number.isFinite(ra) || !Number.isFinite(dec)) return null;
  if (ra < 0 || ra >= 360 || dec < -90 || dec > 90) return null;
  return { ra, dec };
}

function readCoordinates() {
  if (state.coordMode === 'deg') return readDegrees();
  const ra = parseRaSex(el.raSex.value);
  const dec = parseDecSex(el.decSex.value);
  if (ra == null || dec == null) return null;
  return { ra, dec };
}

function readRequest() {
  const fov = Number(el.fov.value);
  const frames = Number(el.frames.value);
  const detector = el.detector.value || null;
  if (!Number.isFinite(fov) || fov < 1 || fov > 30) {
    setQueryStatus('El campo debe estar entre 1 y 30 arcmin.', 'error');
    return null;
  }
  if (!Number.isInteger(frames) || frames < 1 || frames > 16) {
    setQueryStatus('El número de imágenes debe ser un entero entre 1 y 16.', 'error');
    return null;
  }
  if (state.queryMode === 'name') {
    const name = el.name.value.trim();
    if (!name) {
      setQueryStatus('Introduce un nombre SIMBAD o cambia a coordenadas.', 'error');
      return null;
    }
    return { body: { name, fov, frames, detector }, title: name };
  }
  const coordinates = readCoordinates();
  if (!coordinates) {
    setQueryStatus(
      state.coordMode === 'deg'
        ? 'Usa RA entre 0° y menos de 360°, y Dec entre −90° y +90°.'
        : 'No pude interpretar las coordenadas sexagesimales. Usa horas, minutos y segundos para RA; grados, minutos y segundos para Dec.',
      'error',
    );
    return null;
  }
  return { body: { ...coordinates, fov, frames, detector }, title: `Coordenadas ${coord(coordinates.ra, 4)}°, ${coord(coordinates.dec, 4)}°` };
}

function setExample(example) {
  if (example === 'wise') {
    setSearchMode('name');
    el.name.value = 'WISE J085510.83-071442.5';
    setQueryStatus('Ejemplo WISE 0855 cargado. Pulsa Consultar IRSA.');
  } else if (example === 'barnard') {
    setSearchMode('name');
    el.name.value = "Barnard's Star";
    setQueryStatus('Ejemplo Barnard cargado. Pulsa Consultar IRSA.');
  } else if (example === 'r-dra') {
    setSearchMode('name');
    el.name.value = 'R Dra';
    setQueryStatus('Ejemplo R Dra cargado. Pulsa Consultar IRSA.');
  } else if (example === 'free') {
    setSearchMode('coords');
    setCoordMode('deg', false);
    el.ra.value = '5';
    el.dec.value = '-4';
    setQueryStatus('Ejemplo 5°, −4° cargado. Pulsa Consultar IRSA.');
  }
}

function bind() {
  el.fieldGrid.addEventListener('click', (event) => {
    const card = event.target.closest('[data-preset]');
    if (!card || state.busy) return;
    const preset = state.presets.find((item) => item.id === card.dataset.preset);
    if (!preset) return;
    runSearch({ preset: preset.id }, { presetId: preset.id, title: presetLabel(preset) });
  });

  el.modeName.addEventListener('click', () => setSearchMode('name'));
  el.modeCoords.addEventListener('click', () => setSearchMode('coords'));
  el.coordDeg.addEventListener('click', () => setCoordMode('deg'));
  el.coordSex.addEventListener('click', () => setCoordMode('sex'));

  el.query.addEventListener('submit', (event) => {
    event.preventDefault();
    if (state.busy) return;
    const request = readRequest();
    if (!request) return;
    runSearch(request.body, { title: request.title });
  });

  document.querySelectorAll('[data-example]').forEach((button) => {
    button.addEventListener('click', () => setExample(button.dataset.example));
  });

  el.helpOpen.addEventListener('click', () => el.helpDialog.showModal());
  el.helpDialog.addEventListener('click', (event) => {
    if (event.target === el.helpDialog) el.helpDialog.close();
  });
  el.share.addEventListener('click', () => copyText(window.location.href, 'Enlace copiado'));

  el.fieldGrid.addEventListener('error', (event) => {
    if (event.target.tagName === 'IMG') event.target.replaceWith(Object.assign(document.createElement('div'), {
      className: 'thumb-placeholder',
      textContent: 'SPHEREx',
    }));
  }, true);
}

async function initFromUrl() {
  try {
    const field = parseFieldLink(window.location.search);
    if (field) {
      const { body, label, preset } = field;
      el.fov.value = String(body.fov);
      el.frames.value = String(body.frames);
      el.detector.value = body.detector || '';
      if (body.ra !== undefined && body.dec !== undefined) {
        setSearchMode('coords');
        setCoordMode('deg', false);
        const ra = Number(body.ra);
        const dec = Number(body.dec);
        el.ra.value = String(Number.isFinite(ra) ? ra : parseRaSex(body.ra) ?? '');
        el.dec.value = String(Number.isFinite(dec) ? dec : parseDecSex(body.dec) ?? '');
      }
      await runSearch(body, { presetId: preset || null, title: label });
      return;
    }
  } catch (error) {
    player.clear('Enlace inválido', error.message);
    setQueryStatus(error.message, 'error');
    setBadge('error');
    return;
  }
  const first = state.presets.find((preset) => preset.cached) || state.presets[0];
  if (first) {
    await runSearch({ preset: first.id }, { presetId: first.id, title: presetLabel(first) });
  } else {
    player.clear('Sin campos precargados', 'La API no devolvió secuencias. Revisa el servidor o consulta por coordenadas.');
    setQueryStatus('No hay presets disponibles. Puedes buscar un nombre o coordenadas.', 'error');
  }
}

async function init() {
  bind();
  setSearchMode('name');
  setCoordMode('deg', false);
  setBusyUi(false);
  setConnection('busy');
  el.fieldGrid.innerHTML = '<p class="gallery-note">Cargando los campos precargados…</p>';

  const [healthResult] = await Promise.allSettled([health(), loadPresets()]);
  setConnection(healthResult.status === 'fulfilled' ? 'online' : 'offline');
  if (healthResult.status === 'rejected') {
    setQueryStatus('La API no responde. Comprueba que Uvicorn esté iniciado.', 'error');
  }
  await initFromUrl();
}

init();
