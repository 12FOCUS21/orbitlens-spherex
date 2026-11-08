import { clamp, shortDate, dateLong } from './format.js';
import { wavelengthOrder } from './measurements.js';

const ZOOM_MIN = 1;
const ZOOM_MAX = 12;
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

export class Player {
  constructor({ onChange, onHelp, onNotice } = {}) {
    this.onChange = onChange || (() => {});
    this.onHelp = onHelp || (() => {});
    this.onNotice = onNotice || (() => {});

    this.el = {
      viewer: document.getElementById('viewer'),
      frames: document.getElementById('frames'),
      frameA: document.getElementById('frame-a'),
      frameB: document.getElementById('frame-b'),
      compareDivider: document.getElementById('compare-divider'),
      viewerEmpty: document.getElementById('viewer-empty'),
      emptyTitle: document.getElementById('empty-title'),
      emptyText: document.getElementById('empty-text'),
      hudEpoch: document.getElementById('hud-epoch'),
      hudDate: document.getElementById('hud-date'),
      zoomOut: document.getElementById('zoom-out'),
      zoomValue: document.getElementById('zoom-value'),
      zoomIn: document.getElementById('zoom-in'),
      zoomReset: document.getElementById('zoom-reset'),
      pixelToggle: document.getElementById('pixel-toggle'),
      fullscreen: document.getElementById('fullscreen'),
      openFits: document.getElementById('open-fits'),
      measurementSelect: document.getElementById('measurement-select'),
      timeline: document.getElementById('timeline'),
      timelineLabel: document.getElementById('timeline-label'),
      timelineDate: document.getElementById('timeline-date'),
      epochA: document.getElementById('epoch-a'),
      epochADate: document.getElementById('epoch-a-date'),
      epochB: document.getElementById('epoch-b'),
      epochBDate: document.getElementById('epoch-b-date'),
      prev: document.getElementById('prev'),
      play: document.getElementById('play'),
      next: document.getElementById('next'),
      blink: document.getElementById('blink'),
      compare: document.getElementById('compare'),
      speed: document.getElementById('speed'),
      comparePanel: document.getElementById('compare-panel'),
      reveal: document.getElementById('reveal'),
      revealValue: document.getElementById('reveal-value'),
      stage: document.getElementById('stage'),
      stageNote: document.getElementById('stage-note'),
    };

    this.frames = [];
    this.resultId = null;
    this.index = 0;
    this.compareIndex = 0;
    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
    this.pixelated = true;
    this.compare = false;
    this.blinking = false;
    this.playing = false;
    this.reveal = 50;
    this.playTimer = null;
    this.blinkTimer = null;
    this.showB = false;
    this.ready = false;
    this.loadToken = 0;

    this.bind();
    this.applyTransform();
    this.updateControls();
  }

  bind() {
    const e = this.el;
    e.zoomOut.addEventListener('click', () => this.setZoom(this.zoom / 1.25));
    e.zoomIn.addEventListener('click', () => this.setZoom(this.zoom * 1.25));
    e.zoomReset.addEventListener('click', () => this.resetView());
    e.pixelToggle.addEventListener('click', () => this.setPixelated(!this.pixelated));

    e.fullscreen.addEventListener('click', async () => {
      try {
        if (!document.fullscreenElement) await e.stage.requestFullscreen();
        else await document.exitFullscreen();
      } catch {
        this.onNotice('La pantalla completa no está disponible en este navegador.');
      }
    });
    document.addEventListener('fullscreenchange', () => {
      e.fullscreen.textContent = document.fullscreenElement ? 'Salir de pantalla completa' : 'Pantalla completa';
    });

    e.timeline.addEventListener('input', () => {
      this.stopPlay();
      this.stopBlink();
      this.setIndex(Number(e.timeline.value), true);
    });
    e.measurementSelect.addEventListener('change', () => {
      this.stopPlay();
      this.stopBlink();
      this.setIndex(Number(e.measurementSelect.value), true);
    });
    e.prev.addEventListener('click', () => { this.stopPlay(); this.stopBlink(); this.step(-1); });
    e.next.addEventListener('click', () => { this.stopPlay(); this.stopBlink(); this.step(1); });
    e.epochA.addEventListener('click', () => { this.stopPlay(); this.stopBlink(); this.setIndex(0, true); });
    e.epochB.addEventListener('click', () => {
      this.stopPlay();
      this.stopBlink();
      this.compareIndex = this.index;
      this.render();
    });

    e.play.addEventListener('click', () => this.setPlay(!this.playing));
    e.blink.addEventListener('click', () => this.setBlink(!this.blinking));
    e.compare.addEventListener('click', () => this.setCompare(!this.compare));
    e.speed.addEventListener('change', () => {
      if (this.playing) {
        clearInterval(this.playTimer);
        this.playTimer = setInterval(() => this.step(1), Number(e.speed.value) || 1000);
      }
    });
    e.reveal.addEventListener('input', () => this.setReveal(e.reveal.value));

    e.viewer.addEventListener('wheel', (event) => {
      if (!this.hasFrames) return;
      event.preventDefault();
      const rect = e.viewer.getBoundingClientRect();
      const centerX = event.clientX - rect.left - rect.width / 2;
      const centerY = event.clientY - rect.top - rect.height / 2;
      this.setZoom(this.zoom * (event.deltaY < 0 ? 1.18 : 1 / 1.18), centerX, centerY);
    }, { passive: false });

    let drag = null;
    e.viewer.addEventListener('pointerdown', (event) => {
      if (!this.hasFrames || event.button !== 0) return;
      drag = { x: event.clientX, y: event.clientY, panX: this.panX, panY: this.panY };
      e.viewer.classList.add('dragging');
      try { e.viewer.setPointerCapture(event.pointerId); } catch { /* no-op */ }
    });
    e.viewer.addEventListener('pointermove', (event) => {
      if (!drag) return;
      this.panX = drag.panX + (event.clientX - drag.x);
      this.panY = drag.panY + (event.clientY - drag.y);
      this.clampPan();
      this.applyTransform();
    });
    const endDrag = (event) => {
      if (!drag) return;
      drag = null;
      e.viewer.classList.remove('dragging');
      try { e.viewer.releasePointerCapture(event.pointerId); } catch { /* no-op */ }
    };
    e.viewer.addEventListener('pointerup', endDrag);
    e.viewer.addEventListener('pointercancel', endDrag);

    e.viewer.addEventListener('dblclick', (event) => {
      if (!this.hasFrames) return;
      if (this.zoom > 1) {
        this.resetView();
        return;
      }
      const rect = e.viewer.getBoundingClientRect();
      this.setZoom(3, event.clientX - rect.left - rect.width / 2, event.clientY - rect.top - rect.height / 2);
    });

    document.addEventListener('keydown', (event) => {
      const tag = (event.target.tagName || '').toLowerCase();
      if (['input', 'select', 'textarea'].includes(tag) || event.target.isContentEditable) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (document.getElementById('help-dialog')?.open) return;
      if (event.key === ' ' && event.target.closest('button, a')) return;

      switch (event.key) {
        case ' ':
          event.preventDefault();
          this.setPlay(!this.playing);
          break;
        case 'ArrowLeft':
          event.preventDefault();
          this.stopPlay();
          this.stopBlink();
          this.step(-1);
          break;
        case 'ArrowRight':
          event.preventDefault();
          this.stopPlay();
          this.stopBlink();
          this.step(1);
          break;
        case 'b': case 'B':
          event.preventDefault();
          this.setBlink(!this.blinking);
          break;
        case 'c': case 'C':
          event.preventDefault();
          this.setCompare(!this.compare);
          break;
        case '+': case '=':
          event.preventDefault();
          this.setZoom(this.zoom * 1.25);
          break;
        case '-': case '_':
          event.preventDefault();
          this.setZoom(this.zoom / 1.25);
          break;
        case '0':
          this.resetView();
          break;
        case '?':
          event.preventDefault();
          this.onHelp();
          break;
        case 'Escape':
          if (this.compare) this.setCompare(false);
          break;
        default:
          break;
      }
    });

    window.addEventListener('resize', () => {
      this.clampPan();
      this.applyTransform();
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.stopPlay();
        this.stopBlink();
      }
    });
    reduceMotion.addEventListener('change', () => { if (this.blinking) this.setBlink(true); });
  }

  get hasFrames() {
    return this.frames.length > 0;
  }

  get frame() {
    return this.frames[this.index] || null;
  }

  get compareFrame() {
    return this.frames[this.compareIndex] || null;
  }

  setManifest(manifest, resultId) {
    this.frames = Array.isArray(manifest?.frames) ? manifest.frames : [];
    this.resultId = resultId;
    this.index = 0;
    this.compareIndex = Math.max(0, this.frames.length - 1);
    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
    this.compare = false;
    this.blinking = false;
    this.playing = false;
    this.showB = false;
    this.ready = false;
    this.resetTimers();
    this.el.viewer.classList.remove('compare', 'blink', 'show-b');
    this.el.comparePanel.hidden = true;
    this.el.compare.setAttribute('aria-pressed', 'false');
    this.el.compare.textContent = 'Comparar A/B';
    this.el.blink.setAttribute('aria-pressed', 'false');
    this.el.blink.textContent = 'Parpadear';

    this.el.measurementSelect.innerHTML = wavelengthOrder(this.frames).map(({ item, index }) => {
      const lambda = item.wavelength_at_target?.central_um;
      const label = `${Number.isFinite(lambda) && lambda > 0 ? lambda.toFixed(3) : 'Desconocida'} µm · ${item.detector} · ${item.date_utc.slice(0, 10)} · imagen ${index + 1}`;
      const option = document.createElement('option');
      option.value = index;
      option.textContent = label;
      return option.outerHTML;
    }).join('');

    if (!this.frames.length) {
      this.clear('Sin fotogramas', 'La secuencia no contiene imágenes utilizables.');
      return;
    }

    const token = ++this.loadToken;
    this.el.viewerEmpty.hidden = false;
    this.el.emptyTitle.textContent = 'Cargando imágenes…';
    this.el.emptyText.textContent = `Preparando ${this.frames.length} fotogramas de SPHEREx.`;
    let loaded = 0;
    let failed = 0;
    this.frames.forEach((frame) => {
      const image = new Image();
      image.decoding = 'async';
      image.onload = () => {
        if (token !== this.loadToken) return;
        loaded += 1;
        if (loaded + failed === this.frames.length) this.finishLoad(failed);
      };
      image.onerror = () => {
        if (token !== this.loadToken) return;
        failed += 1;
        if (loaded + failed === this.frames.length) this.finishLoad(failed);
      };
      image.src = frame.image_url;
    });
    this.render();
  }

  finishLoad(failed) {
    if (failed) {
      this.ready = false;
      this.clear('No se pudieron cargar las imágenes', 'Una o más imágenes fallaron. Repite la búsqueda o revisa la conexión.');
      return;
    }
    this.ready = true;
    this.el.viewerEmpty.hidden = true;
    this.render();
  }

  clear(title, text) {
    this.loadToken += 1;
    this.frames = [];
    this.ready = false;
    this.resetTimers();
    this.el.viewer.classList.remove('compare', 'blink', 'show-b');
    this.el.frameA.removeAttribute('src');
    this.el.frameB.removeAttribute('src');
    this.el.viewerEmpty.hidden = false;
    this.el.emptyTitle.textContent = title;
    this.el.emptyText.textContent = text;
    this.el.compareDivider.hidden = true;
    this.el.comparePanel.hidden = true;
    this.el.openFits.href = '#';
    this.el.openFits.classList.add('is-disabled');
    this.el.openFits.setAttribute('aria-disabled', 'true');
    this.el.timeline.disabled = true;
    this.el.measurementSelect.disabled = true;
    this.el.measurementSelect.innerHTML = '<option>Sin mediciones</option>';
    this.el.timeline.max = 0;
    this.el.timeline.value = 0;
    this.el.zoomOut.disabled = true;
    this.el.zoomIn.disabled = true;
    this.el.zoomReset.disabled = true;
    this.el.pixelToggle.disabled = true;
    this.el.fullscreen.disabled = true;
    this.el.prev.disabled = true;
    this.el.next.disabled = true;
    this.el.play.disabled = true;
    this.el.blink.disabled = true;
    this.el.compare.disabled = true;
    this.el.epochA.disabled = true;
    this.el.epochB.disabled = true;
    this.el.timelineLabel.textContent = 'Fotograma — de —';
    this.el.timelineDate.textContent = '—';
    this.el.epochADate.textContent = '—';
    this.el.epochBDate.textContent = '—';
    this.el.zoomValue.textContent = '100 %';
    this.onChange(null);
  }

  updateControls() {
    const active = this.hasFrames && this.ready;
    this.el.timeline.disabled = !active;
    this.el.measurementSelect.disabled = !active;
    this.el.prev.disabled = !active;
    this.el.next.disabled = !active;
    this.el.play.disabled = !active || this.frames.length < 3;
    this.el.blink.disabled = !active || this.frames.length < 2;
    this.el.compare.disabled = !active || this.frames.length < 2;
    this.el.pixelToggle.disabled = !active;
    this.el.fullscreen.disabled = !active;
    this.el.epochA.disabled = !active;
    this.el.epochB.disabled = !active;
    this.el.zoomOut.disabled = !active || this.zoom <= ZOOM_MIN;
    this.el.zoomIn.disabled = !active || this.zoom >= ZOOM_MAX;
    this.el.zoomReset.disabled = !active;
  }

  render() {
    const e = this.el;
    if (!this.frames.length) {
      this.updateControls();
      return;
    }
    const frame = this.frame;
    const compare = this.compareFrame;
    e.frameA.src = frame.image_url;
    e.frameB.src = compare?.image_url || '';
    e.frameA.alt = `Fotograma A de ${frame.date_utc}, ${frame.detector}`;
    e.frameB.alt = compare ? `Fotograma B de ${compare.date_utc}, ${compare.detector}` : '';
    e.openFits.href = frame.fits_url || '#';
    e.openFits.classList.toggle('is-disabled', !frame.fits_url);
    e.openFits.setAttribute('aria-disabled', String(!frame.fits_url));

    e.timeline.max = Math.max(0, this.frames.length - 1);
    e.timeline.value = this.index;
    e.measurementSelect.value = this.index;
    this.setFill(e.timeline);
    e.timelineLabel.textContent = `Fotograma ${this.index + 1} de ${this.frames.length}`;
    e.timelineDate.textContent = dateLong(frame.date_utc);
    e.epochADate.textContent = shortDate(frame.date_utc);
    e.epochBDate.textContent = shortDate(compare?.date_utc);
    e.epochA.setAttribute('aria-pressed', String(!this.compare));
    e.epochB.setAttribute('aria-pressed', String(this.compare));

    if (this.blinking) {
      e.hudEpoch.textContent = this.showB ? 'B' : 'A';
      e.hudDate.textContent = shortDate((this.showB ? compare : frame)?.date_utc);
    } else if (this.compare) {
      e.hudEpoch.textContent = 'A/B';
      e.hudDate.textContent = 'comparación';
    } else {
      e.hudEpoch.textContent = 'A';
      e.hudDate.textContent = shortDate(frame.date_utc);
    }

    e.viewer.classList.toggle('compare', this.compare);
    e.viewer.classList.toggle('blink', this.blinking);
    e.viewer.classList.toggle('show-b', this.blinking && this.showB);
    e.comparePanel.hidden = !this.compare;
    e.compareDivider.hidden = !this.compare;
    if (this.compare) this.setReveal(this.reveal);
    else e.frameB.style.clipPath = '';
    e.viewer.setAttribute('aria-label', `Visor de ${this.frames.length} fotogramas SPHEREx. Fotograma ${this.index + 1}: ${dateLong(frame.date_utc)}.`);
    e.stageNote.textContent = 'Las imágenes comparten encuadre y escala. Los píxeles transparentes carecen de datos válidos; los recuadros indican el fondo.';
    this.updateControls();
    this.onChange({ frame, compareFrame: compare, index: this.index, compareIndex: this.compareIndex, frames: this.frames });
  }

  setIndex(value, render = true) {
    if (!this.frames.length) return;
    this.index = clamp(Number(value) || 0, 0, this.frames.length - 1);
    if (this.index === this.compareIndex && this.frames.length > 1) {
      this.compareIndex = this.index === 0 ? 1 : this.index - 1;
    }
    if (render) this.render();
  }

  step(delta) {
    if (!this.frames.length) return;
    this.setIndex((this.index + delta + this.frames.length) % this.frames.length, true);
  }

  setPlay(on) {
    if (on && (!this.ready || this.frames.length < 3)) return;
    this.stopBlink();
    if (this.compare) this.setCompare(false);
    if (!on) {
      this.stopPlay();
      this.render();
      return;
    }
    this.stopPlay();
    if (this.index === this.frames.length - 1) this.setIndex(0, false);
    this.playing = true;
    this.el.play.setAttribute('aria-pressed', 'true');
    this.el.play.textContent = 'Pausar';
    this.playTimer = setInterval(() => {
      if (this.index + 1 >= this.frames.length) this.setIndex(0, true);
      else this.setIndex(this.index + 1, true);
    }, Number(this.el.speed.value) || 1000);
    this.render();
  }

  stopPlay() {
    clearInterval(this.playTimer);
    this.playTimer = null;
    this.playing = false;
    this.el.play.setAttribute('aria-pressed', 'false');
    this.el.play.textContent = 'Reproducir';
  }

  setBlink(on) {
    if (on && (!this.hasFrames || !this.ready || this.frames.length < 2)) return;
    this.stopPlay();
    if (this.compare) this.setCompare(false);
    if (!on) {
      this.stopBlink();
      this.render();
      return;
    }
    this.stopBlink();
    this.blinking = true;
    this.showB = false;
    this.el.blink.setAttribute('aria-pressed', 'true');
    this.el.blink.textContent = 'Detener parpadeo';
    this.blinkTimer = setInterval(() => {
      this.showB = !this.showB;
      this.render();
    }, reduceMotion.matches ? 1100 : 520);
    this.render();
  }

  stopBlink() {
    clearInterval(this.blinkTimer);
    this.blinkTimer = null;
    this.blinking = false;
    this.showB = false;
    this.el.blink.setAttribute('aria-pressed', 'false');
    this.el.blink.textContent = 'Parpadear';
    this.el.viewer.classList.remove('blink', 'show-b');
  }

  setCompare(on) {
    if (on && (!this.hasFrames || !this.ready || this.frames.length < 2)) return;
    if (on) {
      this.stopPlay();
      this.stopBlink();
    }
    this.compare = on;
    this.el.compare.setAttribute('aria-pressed', String(on));
    this.el.compare.textContent = on ? 'Cerrar comparación' : 'Comparar A/B';
    this.render();
  }

  setReveal(value) {
    this.reveal = clamp(Number(value) || 0, 0, 100);
    this.el.reveal.value = this.reveal;
    this.el.revealValue.textContent = `${Math.round(this.reveal)} %`;
    this.el.frameB.style.clipPath = `inset(0 0 0 ${this.reveal}%)`;
    this.el.compareDivider.style.left = `${this.reveal}%`;
    this.setFill(this.el.reveal);
  }

  setZoom(value, centerX = 0, centerY = 0) {
    if (!this.hasFrames) return;
    const next = clamp(value, ZOOM_MIN, ZOOM_MAX);
    if (next === this.zoom) return;
    if (centerX || centerY) {
      const ratio = next / this.zoom;
      this.panX = centerX - (centerX - this.panX) * ratio;
      this.panY = centerY - (centerY - this.panY) * ratio;
    }
    this.zoom = next;
    this.clampPan();
    this.applyTransform();
    this.updateControls();
  }

  clampPan() {
    const rect = this.el.viewer.getBoundingClientRect();
    const maxX = rect.width * (this.zoom - 1) / 2;
    const maxY = rect.height * (this.zoom - 1) / 2;
    this.panX = clamp(this.panX, -maxX, maxX);
    this.panY = clamp(this.panY, -maxY, maxY);
  }

  applyTransform() {
    this.el.frames.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.zoom})`;
    this.el.zoomValue.textContent = `${Math.round(this.zoom * 100)} %`;
  }

  resetView() {
    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
    this.applyTransform();
    this.updateControls();
  }

  setPixelated(on) {
    this.pixelated = on;
    this.el.frames.classList.toggle('smooth', !on);
    this.el.pixelToggle.setAttribute('aria-pressed', String(on));
    this.el.pixelToggle.textContent = on ? 'Píxeles' : 'Suave';
  }

  setFill(input) {
    const min = Number(input.min) || 0;
    const max = Number(input.max) || 100;
    const value = Number(input.value) || 0;
    const percent = max > min ? ((value - min) / (max - min)) * 100 : 0;
    input.style.setProperty('--fill', `${percent}%`);
  }

  resetTimers() {
    clearInterval(this.playTimer);
    clearInterval(this.blinkTimer);
    this.playTimer = null;
    this.blinkTimer = null;
  }
}
