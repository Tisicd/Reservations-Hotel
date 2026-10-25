export const API = '/api';
const MAX_CONCURRENT = 2;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let active = 0;
const queue = [];

function acquire() {
  if (active < MAX_CONCURRENT) {
    active += 1;
    return Promise.resolve();
  }
  return new Promise((resolve) => queue.push(resolve));
}

function release() {
  // Transferir el turno sin decrementar: el slot sigue ocupado por el waiter.
  const next = queue.shift();
  if (next) {
    next();
    return;
  }
  active = Math.max(0, active - 1);
}

const cache = new Map();
const log = [];
const listeners = new Set();

export function subscribeLog(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getLog() {
  return log.slice();
}

function record(entry) {
  log.push(entry);
  if (log.length > 250) log.shift();
  for (const listener of listeners) {
    try { listener(entry); } catch (_) { /* no romper la UI */ }
  }
}

export function uuid4() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-` +
    `${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function errorText(result) {
  const err = result && result.data && result.data.error;
  if (err && err.message) return err.message;
  if (result && result.error) return 'No se pudo conectar con el servidor.';
  return `HTTP ${result ? result.status : '?'}`;
}

export async function request(method, path, options = {}) {
  const { body = null, key = null, cache: useCache = false, retries = 3 } = options;
  const cacheKey = method === 'GET' ? path : null;
  if (useCache && cacheKey && cache.has(cacheKey)) return cache.get(cacheKey);

  await acquire();
  try {
    for (let attempt = 0; attempt <= retries; attempt += 1) {
      const headers = {};
      if (body !== null) headers['Content-Type'] = 'application/json';
      if (key) headers['Idempotency-Key'] = key;

      const started = performance.now();
      let response = null;
      let networkError = null;
      try {
        response = await fetch(API + path, {
          method,
          headers,
          body: body === null ? undefined : JSON.stringify(body),
        });
      } catch (err) {
        networkError = err;
      }
      const ms = Math.max(0, Math.round(performance.now() - started));

      if (networkError) {
        record({ at: new Date(), method, path, status: 0, ms,
                 requestId: null, replayed: null, key });
        if (attempt < retries) {
          await sleep([500, 1000, 2000][attempt] || 2000);
          continue;
        }
        window.dispatchEvent(new CustomEvent('api:notice', {
          detail: { status: 0, wait: 0, requestId: null },
        }));
        return { status: 0, ok: false, data: null, headers: new Headers(),
                 requestId: null, error: networkError };
      }

      let data = null;
      const type = response.headers.get('content-type') || '';
      if (type.includes('json')) {
        try { data = await response.json(); } catch (_) { data = null; }
      }
      const entry = {
        at: new Date(), method, path, status: response.status, ms,
        requestId: response.headers.get('X-Request-ID'),
        replayed: response.headers.get('Idempotent-Replayed'),
        key,
      };
      record(entry);

      if ((response.status === 429 || response.status === 503) && attempt < retries) {
        const header = Number.parseInt(response.headers.get('Retry-After') || '', 10);
        const wait = Number.isFinite(header)
          ? header : ([1, 2, 4][attempt] || 4);
        window.dispatchEvent(new CustomEvent('api:notice', {
          detail: { status: response.status, wait, requestId: entry.requestId },
        }));
        await sleep(wait * 1000);
        continue;
      }

      const result = {
        status: response.status, ok: response.ok, data, headers: response.headers,
        requestId: entry.requestId,
      };
      if (useCache && cacheKey && response.status === 200) {
        cache.set(cacheKey, result);
      }
      return result;
    }
  } finally {
    release();
  }
  return { status: 0, ok: false, data: null, headers: new Headers(),
           requestId: null, error: new Error('sin respuesta') };
}
