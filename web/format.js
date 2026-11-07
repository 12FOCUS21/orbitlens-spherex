export const MINUS = '\u2212';

export const $ = (id, root = document) => root.getElementById ? root.getElementById(id) : root.querySelector(`#${id}`);
export const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

export const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));

export const num = (value, digits = 4) => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  return Number(value).toLocaleString('es-ES', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).replace('-', MINUS);
};

export const coord = (value, digits = 4) => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  return Number(value).toLocaleString('es-ES', { maximumFractionDigits: digits }).replace('-', MINUS);
};

export const pct = (value, digits = 1) => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  return `${num(Number(value) * 100, digits)} %`;
};

export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const asDate = (iso) => new Date(String(iso).endsWith('Z') ? iso : `${iso}Z`);

export const shortDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('es-ES', {
      day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC',
    }).format(asDate(iso));
  } catch {
    return String(iso).slice(0, 10);
  }
};

export const dateLong = (iso) => {
  if (!iso) return '—';
  try {
    return `${new Intl.DateTimeFormat('es-ES', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
    }).format(asDate(iso))} UTC`;
  } catch {
    return String(iso);
  }
};

export const isoDate = (iso) => String(iso || '').slice(0, 10);

export const pad = (value) => String(value).padStart(2, '0');

export const sexFromDegrees = (ra, dec) => {
  const normalized = ((ra % 360) + 360) % 360;
  const hours = normalized / 15;
  const hh = Math.floor(hours);
  const minutes = (hours - hh) * 60;
  const mm = Math.floor(minutes);
  const ss = (minutes - mm) * 60;
  const sign = dec < 0 ? MINUS : '';
  const absolute = Math.abs(dec);
  const dd = Math.floor(absolute);
  const decMinutes = (absolute - dd) * 60;
  const dm = Math.floor(decMinutes);
  const ds = (decMinutes - dm) * 60;
  return {
    ra: `${pad(hh)} ${pad(mm)} ${ss.toFixed(3)}`,
    dec: `${sign}${pad(dd)} ${pad(dm)} ${ds.toFixed(2)}`,
  };
};

export const parseRaSex = (value) => {
  const tokens = String(value).replace(/[^\d.\s]/g, ' ').replace(/,/g, '.').trim().match(/\d+(?:\.\d+)?/g);
  if (!tokens || tokens.length < 2 || tokens.length > 3) return null;
  const [h, m, s = 0] = tokens.map(Number);
  if (!(h >= 0 && h < 24 && m >= 0 && m < 60 && s >= 0 && s < 60)) return null;
  return ((h + m / 60 + s / 3600) * 15) % 360;
};

export const parseDecSex = (value) => {
  const text = String(value).replace(/[\u2212\u2013\u2014]/g, '-').replace(/,/g, '.').trim();
  const negative = text.startsWith('-');
  const tokens = text.match(/\d+(?:\.\d+)?/g);
  if (!tokens || tokens.length < 2 || tokens.length > 3) return null;
  const [d, m, s = 0] = tokens.map(Number);
  if (!(d >= 0 && d <= 90 && m >= 0 && m < 60 && s >= 0 && s < 60)) return null;
  const dec = (d + m / 60 + s / 3600) * (negative ? -1 : 1);
  return dec >= -90 && dec <= 90 ? dec : null;
};
