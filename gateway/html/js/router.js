const routes = [];
let renderVersion = 0;

function compile(pattern) {
  const names = [];
  const parts = [];
  for (const segment of pattern.split('/')) {
    if (segment.startsWith(':')) {
      names.push(segment.slice(1));
      parts.push('([^/]+)');
    } else {
      parts.push(segment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    }
  }
  return { regex: new RegExp(`^${parts.join('/')}$`), names };
}

export function add(pattern, handler) {
  routes.push({ ...compile(pattern), handler });
}

export function parseHash() {
  const raw = (window.location.hash || '#/').replace(/^#/, '') || '/';
  const [path, search = ''] = raw.split('?');
  return { path: path || '/', query: new URLSearchParams(search) };
}

export function navigate(path, params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  }
  const next = `#${path}${query.toString() ? `?${query.toString()}` : ''}`;
  if (window.location.hash === next) {
    render();
  } else {
    window.location.hash = next;
  }
}

async function render() {
  const version = ++renderVersion;
  const { path, query } = parseHash();
  const match = routes.map((route) => ({ route, result: route.regex.exec(path) }))
    .find((entry) => entry.result);
  const app = document.getElementById('app');
  if (!app) return;
  for (const link of document.querySelectorAll('[data-nav]')) {
    if (link.dataset.nav === 'mine') {
      if (path === '/mis-reservas') link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    } else if (link.dataset.nav === 'explore') {
      if (path !== '/mis-reservas') link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
  }
  window.scrollTo(0, 0);
  if (!match) {
    app.replaceChildren();
    app.appendChild(fallback());
    return;
  }
  const params = {};
  match.route.names.forEach((name, index) => {
    params[name] = decodeURIComponent(match.result[index + 1]);
  });
  try {
    await match.route.handler({ params, query, version, isCurrent: () => version === renderVersion });
  } catch (error) {
    if (version !== renderVersion) return;
    app.replaceChildren();
    app.appendChild(errorPanel(error));
  }
  app.focus({ preventScroll: true });
}

function fallback() {
  const wrap = document.createElement('div');
  wrap.className = 'empty';
  const title = document.createElement('h1');
  title.textContent = 'Página no encontrada';
  const text = document.createElement('p');
  text.className = 'muted';
  text.textContent = 'La ruta no existe. Vuelve al inicio para buscar alojamiento.';
  const link = document.createElement('a');
  link.className = 'btn';
  link.href = '#/';
  link.textContent = 'Ir al inicio';
  wrap.append(title, text, link);
  return wrap;
}

function errorPanel(error) {
  const wrap = document.createElement('div');
  wrap.className = 'error-box';
  const title = document.createElement('h1');
  title.textContent = 'Algo no salió bien';
  const text = document.createElement('p');
  text.textContent = error && error.message ? error.message : 'Error inesperado.';
  wrap.append(title, text);
  return wrap;
}

export function initRouter() {
  if (!window.location.hash) window.location.hash = '#/';
  window.addEventListener('hashchange', render);
  render();
}
