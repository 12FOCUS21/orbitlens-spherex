const TERMINAL = new Set(['ready', 'partial', 'empty', 'error']);

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function api(path, options = {}) {
  const { headers, ...rest } = options;
  const response = await fetch(path, {
    ...rest,
    headers: { Accept: 'application/json', ...(headers || {}) },
  });
  const type = response.headers.get('content-type') || '';
  const body = type.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text().catch(() => '');
  if (!response.ok) {
    const detail = body && typeof body === 'object' ? body.detail || body.message : body;
    const message = Array.isArray(detail) ? detail.map((item) => item.msg).filter(Boolean).join(' ') : detail;
    throw new ApiError(typeof message === 'string' && message ? message : `La API respondió ${response.status}.`, response.status);
  }
  return body;
}

export const health = () => api('/api/health');
export const presets = (signal) => api('/api/presets', { signal });
export const search = (body, signal) => api('/api/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
  signal,
});
export const status = (jobId, signal) => api(`/api/status/${encodeURIComponent(jobId)}`, { signal });
export const manifest = (url, signal) => api(url, { signal });
export const analyze = (resultId, mode, indices, signal) => api(`/api/results/${encodeURIComponent(resultId)}/analysis`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ mode, indices }),
  signal,
});

export const isTerminal = (state) => TERMINAL.has(state);

export async function poll(job, options = {}) {
  const { signal, onUpdate, interval = 900 } = options;
  let current = job;
  onUpdate?.(current);
  while (!isTerminal(current.status)) {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        signal?.removeEventListener('abort', abort);
        resolve();
      }, interval);
      const abort = () => {
        clearTimeout(timer);
        reject(new DOMException('Solicitud cancelada', 'AbortError'));
      };
      if (signal?.aborted) abort();
      else signal?.addEventListener('abort', abort, { once: true });
    });
    current = await status(current.job_id, signal);
    onUpdate?.(current);
  }
  return current;
}
