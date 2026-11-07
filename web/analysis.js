import { analyze } from './api.js';
import { esc, num, pct, shortDate } from './format.js';

function compatible(a, b) {
  if (a.detector !== b.detector) return false;
  const x = a.wavelength_at_target || {};
  const y = b.wavelength_at_target || {};
  const values = [x.central_um, y.central_um, x.width_um, y.width_um];
  if (!values.every((value) => value !== null && value !== undefined && Number.isFinite(Number(value)) && Number(value) > 0)) return false;
  return Math.abs(x.central_um - y.central_um) <= Math.min(x.width_um, y.width_um) / 2;
}

function pairs(manifest, mode) {
  const result = [];
  for (let i = 0; i < manifest.frames.length; i++) {
    for (let j = i + 1; j < manifest.frames.length; j++) {
      const a = manifest.frames[i];
      const b = manifest.frames[j];
      if (!compatible(a, b)) continue;
      if (mode === 'stack' && Math.abs(a.mjd - b.mjd) > 7) continue;
      result.push([i, j]);
    }
  }
  return result;
}

function suggested(manifest, mode) {
  return mode === 'lightcurve' ? manifest.frames.map((_, index) => index) : pairs(manifest, mode)[0] || [];
}

export class Analysis {
  constructor() {
    this.el = {
      mode: document.getElementById('analysis-mode'),
      pairs: document.getElementById('analysis-pairs'),
      pairsLabel: document.getElementById('analysis-pairs-label'),
      swap: document.getElementById('analysis-swap'),
      hint: document.getElementById('analysis-hint'),
      fieldset: document.getElementById('analysis-fieldset'),
      selection: document.getElementById('analysis-selection'),
      order: document.getElementById('analysis-order'),
      all: document.getElementById('analysis-all'),
      issue: document.getElementById('analysis-issue'),
      run: document.getElementById('analysis-run'),
      status: document.getElementById('analysis-status'),
      result: document.getElementById('analysis-result'),
    };
    this.manifest = null;
    this.resultId = null;
    this.mode = 'difference';
    this.selected = [];
    this.busy = false;
    this.controller = null;
    this.bind();
    this.clear();
  }

  bind() {
    this.el.mode.addEventListener('change', () => {
      this.mode = this.el.mode.value;
      this.selected = suggested(this.manifest, this.mode);
      this.resetResult();
      this.render();
    });
    this.el.pairs.addEventListener('change', () => {
      if (!this.el.pairs.value) return;
      this.selected = this.el.pairs.value.split(',').map(Number);
      this.resetResult();
      this.render();
    });
    this.el.swap.addEventListener('click', () => {
      this.selected = [...this.selected].reverse();
      this.resetResult();
      this.render();
    });
    this.el.all.addEventListener('click', () => {
      this.selected = this.manifest.frames.map((_, index) => index);
      this.resetResult();
      this.render();
    });
    this.el.run.addEventListener('click', () => this.calculate());
  }

  setManifest(manifest, resultId) {
    this.manifest = manifest;
    this.resultId = resultId;
    this.mode = 'difference';
    this.el.mode.value = this.mode;
    this.selected = suggested(manifest, this.mode);
    this.resetResult();
    this.render();
  }

  clear() {
    this.manifest = null;
    this.resultId = null;
    this.selected = [];
    this.resetResult();
    this.render();
  }

  resetResult() {
    this.controller?.abort();
    this.controller = null;
    this.busy = false;
    this.el.status.textContent = '';
    this.el.status.className = 'query-status';
    this.el.result.innerHTML = '';
    this.el.run.disabled = true;
    this.el.run.textContent = 'Calcular';
  }

  issue() {
    if (!this.manifest) return 'Carga una secuencia para analizarla.';
    if (!this.selected.length) return 'Selecciona al menos una observación.';
    if (this.mode === 'lightcurve') return '';
    if (this.mode === 'difference' && this.selected.length !== 2) return 'La diferencia necesita exactamente dos imágenes. Elige una pareja disponible.';
    if (this.mode === 'stack' && this.selected.length < 2) return 'El apilado necesita al menos dos imágenes.';
    const available = pairs(this.manifest, this.mode);
    for (let i = 0; i < this.selected.length; i++) {
      for (let j = i + 1; j < this.selected.length; j++) {
        if (!available.some((pair) => pair.includes(this.selected[i]) && pair.includes(this.selected[j]))) {
          return this.mode === 'stack'
            ? 'La selección mezcla bandas incompatibles o abarca más de siete días. Elige una pareja disponible.'
            : 'Las bandas de estas imágenes no son compatibles en el centro. Elige una pareja disponible.';
        }
      }
    }
    return '';
  }

  render() {
    const e = this.el;
    const has = Boolean(this.manifest?.frames?.length);
    e.mode.disabled = !has || this.busy;
    e.fieldset.disabled = !has || this.busy;
    e.all.hidden = this.mode !== 'lightcurve';
    e.swap.hidden = !(this.mode === 'difference' && this.selected.length === 2);
    e.pairsLabel.hidden = this.mode === 'lightcurve';
    e.order.textContent = this.selected.map((index) => index + 1).join(', ') || 'ninguna';

    if (!has) {
      e.pairs.innerHTML = '<option value="">Sin secuencia</option>';
      e.selection.innerHTML = '<p class="muted">Carga un campo para seleccionar observaciones.</p>';
      e.issue.hidden = true;
      e.run.disabled = true;
      return;
    }

    const available = pairs(this.manifest, this.mode);
    const current = available.some((pair) => pair.join(',') === this.selected.join(',')) ? this.selected.join(',') : '';
    e.pairs.innerHTML = this.mode === 'lightcurve'
      ? '<option value="">Todas las fechas</option>'
      : `<option value="" disabled${current ? '' : ' selected'}>${available.length ? 'Selección personalizada' : 'Sin parejas compatibles'}</option>` +
        available.map((pair) => {
          const a = this.manifest.frames[pair[0]];
          const b = this.manifest.frames[pair[1]];
          return `<option value="${pair.join(',')}"${current === pair.join(',') ? ' selected' : ''}>Imágenes ${pair[0] + 1} y ${pair[1] + 1} · ${esc(shortDate(a.date_utc))} / ${esc(shortDate(b.date_utc))}</option>`;
        }).join('');
    e.pairs.disabled = this.mode === 'lightcurve' || !available.length || this.busy;

    e.selection.innerHTML = this.manifest.frames.map((frame, index) => {
      const lambda = frame.wavelength_at_target?.central_um;
      return `<label>
        <input type="checkbox" value="${index}"${this.selected.includes(index) ? ' checked' : ''}${this.busy ? ' disabled' : ''}>
        <span><b>${index + 1}</b> · ${esc(frame.date_utc.replace('T', ' ').slice(0, 19))} ·
        ${lambda === null || lambda === undefined ? 'λ no disponible' : `${num(lambda, 3)} µm`} · ${esc(frame.detector)}</span>
      </label>`;
    }).join('');
    e.selection.querySelectorAll('input[type="checkbox"]').forEach((input) => {
      input.addEventListener('change', () => {
        const index = Number(input.value);
        this.selected = input.checked
          ? [...new Set([...this.selected, index])]
          : this.selected.filter((value) => value !== index);
        this.resetResult();
        this.render();
      });
    });

    const message = this.issue();
    e.issue.hidden = !message;
    e.issue.textContent = message;
    e.run.disabled = this.busy || Boolean(message);
    e.run.textContent = this.busy ? 'Calculando…' : 'Calcular';
    e.hint.textContent = this.mode === 'difference'
      ? 'Selecciona dos imágenes. A es la primera seleccionada y B la segunda. Rojo: A mayor; azul: B mayor; blanco: cero. Se requieren bandas compatibles en el centro.'
      : this.mode === 'stack'
        ? 'Selecciona al menos dos imágenes de una época exploratoria (máximo siete días). Se calcula la media de los valores válidos por píxel.'
        : 'Selecciona las fechas a consultar. Los puntos sin medición se muestran como ausentes; no se sustituyen por cero.';
  }

  async calculate() {
    const message = this.issue();
    if (message || !this.resultId) return;
    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    this.busy = true;
    this.el.run.disabled = true;
    this.el.run.textContent = 'Calculando…';
    this.el.status.textContent = 'Leyendo las imágenes alineadas…';
    this.el.status.className = 'query-status';
    this.el.result.innerHTML = '';
    this.render();
    try {
      const value = await analyze(this.resultId, this.mode, this.selected, controller.signal);
      if (controller.signal.aborted) return;
      this.el.status.textContent = 'Análisis completado.';
      this.el.status.className = 'query-status ok';
      this.renderResult(value);
    } catch (error) {
      if (controller.signal.aborted) return;
      this.el.status.textContent = '';
      this.el.result.innerHTML = `<p class="notice error" role="alert">${esc(error.message || 'No se pudo completar el análisis.')}</p>`;
    } finally {
      if (!controller.signal.aborted) {
        this.busy = false;
        this.el.run.textContent = 'Calcular';
        this.render();
      }
    }
  }

  renderResult(value) {
    const parts = [];
    if (value.image) {
      const imageAlt = value.mode === 'difference'
        ? 'Diferencia A menos B, norte arriba y este a la izquierda'
        : 'Media de las imágenes seleccionadas, norte arriba y este a la izquierda';
      const limits = Array.isArray(value.limits) ? value.limits.map((limit) => num(limit, 4)).join(' a ') : '—';
      parts.push(`<div class="analysis-image"><img src="${value.image}" alt="${esc(imageAlt)}"></div>
        <p class="analysis-caption">Escala asinh: ${esc(limits)} ${esc(value.unit)}. Cobertura válida: ${pct(value.valid_fraction)}.
        Contribuciones por píxel: ${value.contributors_min ?? '—'}–${value.contributors_max ?? '—'}.
        <a href="${value.image}" download="orbitlens-${esc(value.mode)}.png">Descargar vista PNG ↓</a></p>`);
    }
    if (value.mode === 'lightcurve') {
      parts.push(this.renderLightcurve(value));
    }
    if (Array.isArray(value.warnings)) {
      parts.push(value.warnings.map((warning) => `<p class="notice">${esc(warning)}</p>`).join(''));
    }
    this.el.result.innerHTML = parts.join('');
  }

  renderLightcurve(value) {
    const valid = value.points.filter((point) => point.value !== null && Number.isFinite(point.value));
    const table = `<div class="analysis-table"><table>
      <thead><tr><th>UTC</th><th>MJD</th><th>λ µm</th><th>MJy/sr</th><th>Estado</th></tr></thead>
      <tbody>${value.points.map((point) => `<tr>
        <td>${esc(point.date_utc)}</td>
        <td>${num(point.mjd, 5)}</td>
        <td>${point.wavelength_um === null || point.wavelength_um === undefined ? '—' : num(point.wavelength_um, 3)}</td>
        <td>${point.value === null ? '—' : num(point.value, 6)}</td>
        <td>${point.value === null ? esc(point.reason || 'Sin medición') : 'Medición válida'}</td>
      </tr>`).join('')}</tbody></table></div>`;
    if (!valid.length) {
      return `<p class="notice">No hay píxeles centrales válidos en las fechas seleccionadas. La curva conserva las fechas, pero no inventa valores.</p>${table}`;
    }
    const xMin = Math.min(...valid.map((point) => point.mjd));
    const xMax = Math.max(...valid.map((point) => point.mjd));
    const yMin = Math.min(...valid.map((point) => point.value));
    const yMax = Math.max(...valid.map((point) => point.value));
    const x = (mjd) => (xMax === xMin ? 330 : 65 + 535 * (mjd - xMin) / (xMax - xMin));
    const y = (valueY) => (yMax === yMin ? 110 : 200 - 175 * (valueY - yMin) / (yMax - yMin));
    const circles = valid.map((point) => `<circle cx="${x(point.mjd).toFixed(2)}" cy="${y(point.value).toFixed(2)}" r="5" fill="#0f4240">
      <title>${esc(point.date_utc)}: ${num(point.value, 6)} MJy/sr · ${point.wavelength_um === null ? 'λ —' : num(point.wavelength_um, 3) + ' µm'}</title>
    </circle>`).join('');
    const legend = valid.map((point) => `<li><span>${esc(point.date_utc.slice(0, 10))}</span><b>${num(point.value, 5)}</b><small>${point.wavelength_um === null ? 'λ —' : `${num(point.wavelength_um, 3)} µm`}</small></li>`).join('');
    return `<h3>Brillo superficial del píxel central · MJy/sr</h3>
      <svg class="lightcurve" viewBox="0 0 620 250" role="img" aria-label="Puntos de brillo superficial frente a MJD; valores exactos en la tabla">
        <path d="M65 20 V205 H600" fill="none" stroke="currentColor"></path>
        <text x="65" y="228">${xMin.toFixed(2)}</text><text x="600" y="228" text-anchor="end">${xMax.toFixed(2)} MJD</text>
        <text x="60" y="25" text-anchor="end">${yMax.toPrecision(3)}</text><text x="60" y="200" text-anchor="end">${yMin.toPrecision(3)}</text>
        ${circles}
      </svg>
      <ul class="lightcurve-legend">${legend}</ul>
      <p class="hint">Píxel fijo del cielo; no sigue al objeto ni mide flujo integrado. Los puntos de distintas bandas no se conectan.</p>
      ${table}`;
  }
}
