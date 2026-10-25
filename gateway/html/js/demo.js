import { getLog, subscribeLog, request, errorText } from './api.js';
import { state } from './state.js';
import { h, fmtTime, flash } from './ui.js';

let panel = null;
let toggle = null;
let body = null;

function logTable() {
  const entries = getLog().slice(-25).reverse();
  if (!entries.length) return h('p', { class: 'muted small' }, 'Todavía no hay llamadas.');
  return h('table', { class: 'calllog' },
    h('thead', {}, h('tr', {},
      h('th', {}, 'Hora'), h('th', {}, 'Método'), h('th', {}, 'Ruta'),
      h('th', {}, 'HTTP'), h('th', {}, 'ms'), h('th', {}, 'request_id'), h('th', {}, 'Replay'))),
    h('tbody', {}, entries.map((entry) => h('tr', {},
      h('td', {}, fmtTime(entry.at.toISOString())),
      h('td', {}, entry.method),
      h('td', {}, h('code', {}, entry.path)),
      h('td', {}, String(entry.status || '—')),
      h('td', {}, String(entry.ms)),
      h('td', {}, h('code', {}, entry.requestId || '—')),
      h('td', {}, entry.replayed ? 'sí' : '—')))));
}

function rawTimeline() {
  if (!state.currentReservationId) {
    return h('p', { class: 'muted small' }, 'Abre una reserva para ver su línea de tiempo cruda.');
  }
  const events = state.currentEvents || [];
  return h('div', {},
    h('p', { class: 'small' }, 'Reserva ', h('code', {}, state.currentReservationId)),
    events.length
      ? h('ol', { class: 'timeline' }, events.map((event) => h('li', {},
        h('div', { class: 't-title' }, `${event.from || '—'} → ${event.to}`),
        h('div', { class: 't-meta' }, `${event.reason || 'sin motivo'} · ${fmtTime(event.at)}`))))
      : h('p', { class: 'muted small' }, 'Sin eventos todavía.'));
}

function replayBox() {
  if (!state.lastBooking) {
    return h('p', { class: 'muted small' }, 'No hay una reserva reciente para reenviar.');
  }
  const info = h('p', { class: 'small muted' },
    'Clave: ', h('code', {}, state.lastBooking.key),
    state.lastBooking.reservationId ? ` · reserva ${state.lastBooking.reservationId}` : '');
  const button = h('button', { class: 'btn secondary small', type: 'button' }, 'Reenviar la misma solicitud');
  const resultBox = h('div', { class: 'small' });
  button.addEventListener('click', async () => {
    button.disabled = true;
    resultBox.replaceChildren('Reenviando…');
    const result = await request('POST', state.lastBooking.path, {
      body: state.lastBooking.body, key: state.lastBooking.key, retries: 0,
    });
    button.disabled = false;
    if (result.status === 200) {
      const replayed = result.headers.get('Idempotent-Replayed');
      resultBox.replaceChildren(h('span', { class: 'badge ok' }, `HTTP 200 · Idempotent-Replayed: ${replayed || 'ausente'}`));
      flash('ok', 'Reenvío idempotente: misma reserva, sin duplicar.');
    } else {
      resultBox.replaceChildren(h('span', { class: 'badge error' }, `${errorText(result)} (HTTP ${result.status})`));
    }
  });
  return h('div', {}, info, h('div', { class: 'actions' }, button), resultBox);
}

function render() {
  if (!body || panel.hidden) return;
  const header = h('div', { class: 'section-head' },
    h('h2', {}, 'Llamadas a la API'),
    h('button', { class: 'ghost small', type: 'button', onclick: () => {
      // Limpia solo la vista local; el log se conserva hasta la recarga.
      body.querySelector('.calllog')?.replaceWith(h('p', { class: 'muted small' }, 'Vista limpia; nuevas llamadas aparecerán aquí.'));
    } }, 'Limpiar vista'));
  body.replaceChildren(
    header,
    logTable(),
    h('div', { class: 'panel' }, h('h2', {}, 'Línea de tiempo cruda'), rawTimeline()),
    h('div', { class: 'panel' }, h('h2', {}, 'Idempotencia'), replayBox()),
    h('p', { class: 'muted small' }, 'Las llamadas se registran en memoria; no se envía nada a terceros.'),
  );
}

export function initDemo() {
  panel = document.getElementById('demo-panel');
  toggle = document.getElementById('demo-toggle');
  body = document.getElementById('demo-body');
  const close = document.getElementById('demo-close');
  if (!panel || !toggle || !body) return;
  const open = (visible) => {
    panel.hidden = !visible;
    toggle.setAttribute('aria-expanded', String(visible));
    if (visible) { render(); close?.focus(); }
  };
  toggle.addEventListener('click', () => open(panel.hidden));
  close?.addEventListener('click', () => open(false));
  subscribeLog(() => window.setTimeout(render, 40));
  window.addEventListener('demo:refresh', () => render());
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !panel.hidden) open(false);
  });
}
