import { errorText, request } from './api.js';
import { clearSession, setSession, state } from './state.js';
import { flash, h, setLive } from './ui.js';
import { add as addRoute, navigate } from './router.js';

function field(id, label, input) {
  return h('div', { class: 'field' }, h('label', { for: id }, label), input);
}

function passwordInput(id, autocomplete) {
  const input = h('input', {
    id, type: 'password', autocomplete, required: true, minlength: '10',
    maxlength: '128',
  });
  const toggle = h('button', {
    class: 'ghost small password-toggle', type: 'button',
    'aria-label': 'Mostrar contraseña', 'aria-pressed': 'false',
  }, 'Mostrar');
  toggle.addEventListener('click', () => {
    const visible = input.type === 'text';
    input.type = visible ? 'password' : 'text';
    toggle.textContent = visible ? 'Mostrar' : 'Ocultar';
    toggle.setAttribute('aria-label', visible ? 'Mostrar contraseña' : 'Ocultar contraseña');
    toggle.setAttribute('aria-pressed', String(!visible));
  });
  return h('div', { class: 'password-wrap' }, input, toggle);
}

function returnTo(ctx) {
  const raw = (ctx.query.get('returnTo') || '/').replace(/^#/, '');
  return raw.startsWith('/') ? raw : '/';
}

export function renderAuthNav() {
  const box = document.getElementById('auth-nav');
  if (!box) return;
  box.replaceChildren();
  if (state.token && state.customer) {
    box.append(h('span', { class: 'small muted auth-name' }, state.customer.name));
    box.append(h('a', { class: 'ghost small', href: '#/mis-reservas' }, 'Mis reservas'));
    box.append(h('button', {
      class: 'ghost small', type: 'button', onclick: () => logout(),
    }, 'Cerrar sesión'));
  } else {
    box.append(h('a', { class: 'ghost small', href: '#/login' }, 'Iniciar sesión'));
    box.append(h('a', { class: 'btn small', href: '#/registro' }, 'Crear cuenta'));
  }
}

export async function logout() {
  await request('POST', '/auth/logout', { retries: 0 });
  clearSession();
  renderAuthNav();
  flash('ok', 'Sesión cerrada.');
  navigate('/');
}

export async function loginScreen(ctx) {
  document.title = 'Iniciar sesión — Reservas UCE';
  const app = document.getElementById('app');
  const to = returnTo(ctx);
  if (state.token) { navigate(to); return; }
  const email = h('input', {
    id: 'login-email', type: 'email', autocomplete: 'email', required: true,
  });
  const password = passwordInput('login-password', 'current-password');
  const submit = h('button', { class: 'btn block', type: 'submit' }, 'Iniciar sesión');
  const form = h('form', { class: 'auth-card' },
    h('h1', {}, 'Iniciar sesión'),
    h('p', { class: 'muted' }, 'Necesitas una cuenta para reservar.'),
    field('login-email', 'Correo', email),
    field('login-password', 'Contraseña', password),
    h('div', { class: 'actions' }, submit),
    h('p', { class: 'small muted' },
      '¿No tienes cuenta? ', h('a', { href: `#/registro?${new URLSearchParams({ returnTo: to })}` }, 'Crear cuenta')));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    submit.disabled = true;
    const result = await request('POST', '/auth/login', {
      body: { email: email.value.trim(), password: password.querySelector('input').value },
    });
    submit.disabled = false;
    if (result.status === 200) {
      const data = result.data;
      setSession(data.access_token, data.customer);
      renderAuthNav();
      setLive(`Sesión iniciada como ${data.customer.name}`);
      navigate(to);
      return;
    }
    if (result.status === 429) {
      const wait = Number.parseInt(result.headers.get('Retry-After') || '', 10);
      flash('warn', `Demasiadas solicitudes; espera ${Number.isFinite(wait) ? wait : 2} s e inténtalo de nuevo.`);
    } else if (result.status === 503) {
      flash('warn', 'Servicio no disponible; inténtalo de nuevo en unos segundos.');
    } else {
      // Mismo mensaje para usuario inexistente, clave errónea o bloqueo.
      flash('error', 'Correo o contraseña incorrectos.');
    }
  });
  app.replaceChildren(form);
}

export async function registerScreen(ctx) {
  document.title = 'Crear cuenta — Reservas UCE';
  const app = document.getElementById('app');
  const to = returnTo(ctx);
  if (state.token) { navigate(to); return; }
  const name = h('input', {
    id: 'register-name', autocomplete: 'name', required: true,
  });
  const email = h('input', {
    id: 'register-email', type: 'email', autocomplete: 'email', required: true,
  });
  const password = passwordInput('register-password', 'new-password');
  const submit = h('button', { class: 'btn block', type: 'submit' }, 'Crear cuenta');
  const form = h('form', { class: 'auth-card' },
    h('h1', {}, 'Crear cuenta'),
    h('p', { class: 'muted' }, 'Una cuenta para reservar y ver tus reservas.'),
    field('register-name', 'Nombre', name),
    field('register-email', 'Correo', email),
    field('register-password', 'Contraseña', password),
    h('p', { class: 'small muted' }, 'Mínimo 10 caracteres; no uses tu correo ni una clave común.'),
    h('div', { class: 'actions' }, submit),
    h('p', { class: 'small muted' },
      '¿Ya tienes cuenta? ', h('a', { href: `#/login?${new URLSearchParams({ returnTo: to })}` }, 'Iniciar sesión')));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const pass = password.querySelector('input').value;
    if (pass.length < 10) {
      flash('error', 'La contraseña debe tener al menos 10 caracteres.');
      return;
    }
    submit.disabled = true;
    const created = await request('POST', '/auth/register', {
      body: { name: name.value.trim(), email: email.value.trim(), password: pass },
    });
    if (created.status === 201 || created.status === 200) {
      const logged = await request('POST', '/auth/login', {
        body: { email: email.value.trim(), password: pass },
      });
      submit.disabled = false;
      if (logged.status === 200) {
        setSession(logged.data.access_token, logged.data.customer);
        renderAuthNav();
        setLive('Cuenta creada y sesión iniciada');
        navigate(to);
        return;
      }
      flash('warn', 'Cuenta creada. Inicia sesión para continuar.');
      navigate('/login', { returnTo: to });
      return;
    }
    submit.disabled = false;
    if (created.status === 409) {
      flash('error', 'Ese correo ya está registrado. Inicia sesión.');
    } else if (created.status === 422) {
      flash('error', errorText(created));
    } else if (created.status === 429) {
      const wait = Number.parseInt(created.headers.get('Retry-After') || '', 10);
      flash('warn', `Demasiadas solicitudes; espera ${Number.isFinite(wait) ? wait : 2} s.`);
    } else {
      flash('error', errorText(created));
    }
  });
  app.replaceChildren(form);
}

export function initAuth() {
  addRoute('/login', loginScreen);
  addRoute('/registro', registerScreen);
  window.addEventListener('auth:expired', () => {
    if (!state.token) return;
    const current = (window.location.hash || '#/').replace(/^#/, '');
    if (current.startsWith('/login') || current.startsWith('/registro')) return;
    clearSession();
    renderAuthNav();
    flash('warn', 'Tu sesión expiró. Inicia sesión de nuevo.');
    navigate('/login', { returnTo: current });
  });
  window.addEventListener('hashchange', renderAuthNav);
  renderAuthNav();
}
