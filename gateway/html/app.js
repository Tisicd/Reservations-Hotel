'use strict';

const API = '/api';
const DEMO_CUSTOMERS = [
  { id: '2e66f9f9-b8e1-40f6-9f21-91348684dbd9', name: 'Cliente Demo Uno' },
  { id: 'ebdc71fc-93a3-4665-979a-36a4020d0ebc', name: 'Cliente Demo Dos' },
];
const STABLE = new Set([
  'CONFIRMED', 'CANCELLED', 'REJECTED_NO_INVENTORY', 'PAYMENT_DECLINED',
  'FAILED_TECHNICAL', 'MANUAL_REVIEW', 'REFUND_REQUIRED',
]);

const state = {
  hotelId: '', hotels: [], hotelRooms: [], room: null,
  key: null, body: null, reservationId: null, polling: false,
};

const byId = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function text(node, value) {
  node.textContent = value == null ? '' : String(value);
}

function setLast(code, requestId) {
  text(byId('lastCode'), code == null ? '—' : code);
  text(byId('lastRequest'), requestId || '—');
}

function clearAlerts() {
  byId('alerts').replaceChildren();
}

function showAlert(kind, message) {
  const box = document.createElement('div');
  box.className = `alert ${kind}`;
  box.textContent = message;
  byId('alerts').appendChild(box);
}

function uuid4() {
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

function todayISO() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

async function request(method, path, { body = null, key = null } = {}) {
  const headers = {};
  if (body !== null) headers['Content-Type'] = 'application/json';
  if (key !== null) headers['Idempotency-Key'] = key;
  const response = await fetch(API + path, {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
  });
  let data = null;
  const type = response.headers.get('content-type') || '';
  if (type.includes('json')) {
    try { data = await response.json(); } catch (_) { data = null; }
  }
  const requestId = response.headers.get('X-Request-ID');
  setLast(response.status, requestId);
  return { status: response.status, headers: response.headers, data, requestId };
}

async function withRetry(fn) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const result = await fn();
    if (result.status !== 429 && result.status !== 503) return result;
    const header = Number.parseInt(result.headers.get('Retry-After') || '', 10);
    const wait = Number.isFinite(header) ? header : [1, 2, 4][attempt];
    if (result.status === 429) {
      showAlert('warn', `Demasiadas solicitudes; reintentando en ${wait} s ` +
        `(request_id ${result.requestId || '—'}).`);
    } else {
      showAlert('warn', `Servicio no disponible, no se perdió nada: se ` +
        `reintenta con la misma clave en ${wait} s ` +
        `(request_id ${result.requestId || '—'}).`);
    }
    await sleep(wait * 1000);
  }
  return fn();
}

function handleResult(result) {
  const error = result.data && result.data.error ? result.data.error : {};
  const message = error.message || `HTTP ${result.status}`;
  const code = error.code || '';
  const requestId = result.requestId || '—';
  if (code === 'SIMULATION_DISABLED') {
    showAlert('error', `Simulación deshabilitada: ${message} ` +
      `(request_id ${requestId}).`);
  } else if (result.status === 429) {
    showAlert('warn', `${message} (request_id ${requestId}).`);
  } else if (result.status === 503) {
    showAlert('warn', `Servicio no disponible: ${message}. No se perdió nada; ` +
      `reintenta con la misma clave (request_id ${requestId}).`);
  } else {
    showAlert('error', `${message} (HTTP ${result.status}, ` +
      `request_id ${requestId}).`);
  }
}

function option(value, label) {
  const node = document.createElement('option');
  node.value = value;
  node.textContent = label;
  return node;
}

function renderRooms(availability) {
  const container = byId('rooms');
  container.replaceChildren();
  state.room = null;
  if (!state.hotelRooms.length) {
    text(container, 'Sin habitaciones para este hotel.');
    return;
  }
  for (const room of state.hotelRooms) {
    const available = availability.get(room.id) || 0;
    const card = document.createElement('div');
    card.className = available > 0 ? 'room' : 'room disabled';
    const label = document.createElement('label');
    const radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = 'room';
    radio.value = room.id;
    radio.disabled = available <= 0;
    radio.addEventListener('change', () => { state.room = room.id; });
    const name = document.createElement('span');
    name.textContent = `${room.name} · ${(room.price_per_night_cents / 100).toFixed(2)} USD/noche`;
    const stock = document.createElement('span');
    stock.textContent = `Disponibles: ${available}`;
    label.append(radio, name, stock);
    card.appendChild(label);
    container.appendChild(card);
  }
}

async function loadHotel() {
  const hotelId = byId('hotel').value;
  if (!hotelId) return;
  state.hotelId = hotelId;
  const result = await withRetry(() => request('GET', `/hotels/${hotelId}`));
  if (result.status !== 200) { handleResult(result); return; }
  state.hotelRooms = (result.data && result.data.rooms) || [];
  await search();
}

async function search() {
  clearAlerts();
  const checkIn = byId('checkin').value;
  const checkOut = byId('checkout').value;
  if (!checkIn || !checkOut) {
    showAlert('error', 'Indica fecha de entrada y salida.');
    return;
  }
  if (checkOut <= checkIn) {
    showAlert('error', 'La salida debe ser posterior a la entrada.');
    return;
  }
  if (checkIn < todayISO()) {
    showAlert('error', 'La entrada no puede ser anterior a hoy.');
    return;
  }
  const query = new URLSearchParams({
    hotel_id: state.hotelId, check_in: checkIn, check_out: checkOut,
  });
  const result = await withRetry(() => request('GET', `/availability?${query}`));
  if (result.status !== 200) { handleResult(result); return; }
  const availability = new Map(
    ((result.data && result.data.rooms) || []).map((r) => [r.room_id, r.available]),
  );
  renderRooms(availability);
}

async function loadHotels() {
  const select = byId('hotel');
  const result = await withRetry(() => request('GET', '/hotels'));
  if (result.status !== 200) { handleResult(result); return; }
  state.hotels = result.data || [];
  select.replaceChildren();
  for (const hotel of state.hotels) {
    select.appendChild(option(hotel.id, `${hotel.name} (${hotel.city})`));
  }
  if (select.value) await loadHotel();
}

function fillCustomers() {
  const select = byId('customer');
  select.replaceChildren();
  for (const customer of DEMO_CUSTOMERS) {
    select.appendChild(option(customer.id, customer.name));
  }
  if (DEMO_CUSTOMERS.length) select.value = DEMO_CUSTOMERS[0].id;
}

async function createCustomer(event) {
  event.preventDefault();
  clearAlerts();
  const name = byId('cname').value.trim();
  const email = byId('cemail').value.trim();
  if (!name || !email) {
    showAlert('error', 'Nombre y email son obligatorios.');
    return;
  }
  const result = await withRetry(() => request('POST', '/customers', {
    body: { name, email },
  }));
  if (result.status !== 201 && result.status !== 200) {
    handleResult(result);
    return;
  }
  const select = byId('customer');
  select.appendChild(option(result.data.id, result.data.name));
  select.value = result.data.id;
  byId('cname').value = '';
  byId('cemail').value = '';
  showAlert('ok', `Cliente creado (request_id ${result.requestId || '—'}).`);
}

function renderReservation(reservation) {
  text(byId('status'), reservation.status || '—');
  text(byId('reason'), reservation.status_reason || '');
  byId('cancelBtn').disabled = reservation.status !== 'CONFIRMED';
  byId('replayBtn').disabled = !state.key;
}

function renderTimeline(events) {
  const body = byId('timeline').querySelector('tbody');
  body.replaceChildren();
  if (!events.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 4;
    cell.textContent = 'Sin eventos todavía.';
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  const first = new Date(events[0].at).getTime();
  for (const event of events) {
    const row = document.createElement('tr');
    const transition = document.createElement('td');
    transition.textContent = `${event.from || '—'} → ${event.to}`;
    const reason = document.createElement('td');
    reason.textContent = event.reason || '—';
    const when = document.createElement('td');
    when.textContent = new Date(event.at).toLocaleTimeString();
    const elapsed = document.createElement('td');
    const seconds = (new Date(event.at).getTime() - first) / 1000;
    elapsed.textContent = seconds <= 0 ? '0' : seconds.toFixed(1);
    row.append(transition, reason, when, elapsed);
    body.appendChild(row);
  }
}

function renderNotifications(items) {
  const box = byId('notification');
  box.replaceChildren();
  if (!items.length) {
    text(box, 'Sin notificación todavía.');
    return;
  }
  const latest = items[items.length - 1];
  text(box, `Tipo: ${latest.type || '—'} · estado: ${latest.status || '—'} · ` +
    `intentos: ${latest.attempts == null ? '—' : latest.attempts}` +
    (latest.sent_at ? ` · enviada: ${new Date(latest.sent_at).toLocaleTimeString()}` : ''));
}

async function poll() {
  if (state.polling || !state.reservationId) return;
  state.polling = true;
  const deadline = Date.now() + 90000;
  let attempt = 0;
  try {
    while (Date.now() < deadline) {
      const current = await request('GET', `/reservations/${state.reservationId}`);
      if (current.status !== 200) {
        if (current.status === 429 || current.status === 503) {
          attempt += 1;
          await sleep(Math.min(5000, 1000 * Math.pow(1.4, attempt)));
          continue;
        }
        handleResult(current);
        break;
      }
      renderReservation(current.data);
      const [events, notifications] = await Promise.all([
        request('GET', `/reservations/${state.reservationId}/events`),
        request('GET', `/notifications?reservation_id=${state.reservationId}`),
      ]);
      if (events.status === 200) renderTimeline(events.data || []);
      if (notifications.status === 200) renderNotifications(notifications.data || []);
      if (STABLE.has(current.data.status)) break;
      attempt += 1;
      await sleep(Math.min(5000, 1000 * Math.pow(1.4, attempt)));
    }
  } finally {
    state.polling = false;
  }
}

async function reserve() {
  clearAlerts();
  const customer = byId('customer').value;
  const checkIn = byId('checkin').value;
  const checkOut = byId('checkout').value;
  if (!state.room) { showAlert('error', 'Elige una habitación.'); return; }
  if (!customer) { showAlert('error', 'Elige o crea un cliente.'); return; }
  if (!checkIn || !checkOut || checkOut <= checkIn) {
    showAlert('error', 'Fechas inválidas.');
    return;
  }
  state.key = uuid4();
  state.body = {
    customer_id: customer,
    hotel_id: state.hotelId,
    room_id: state.room,
    check_in: checkIn,
    check_out: checkOut,
    payment: {
      method: 'card', token: 'tok_demo', simulate: byId('simulate').value,
    },
  };
  const result = await withRetry(() => request('POST', '/reservations', {
    body: state.body, key: state.key,
  }));
  if (![200, 201, 202].includes(result.status)) { handleResult(result); return; }
  state.reservationId = result.data.id;
  renderReservation(result.data);
  showAlert('ok', `Reserva ${result.data.id} creada (HTTP ${result.status}, ` +
    `request_id ${result.requestId || '—'}).`);
  await poll();
}

async function replay() {
  clearAlerts();
  if (!state.body || !state.key) return;
  const result = await withRetry(() => request('POST', '/reservations', {
    body: state.body, key: state.key,
  }));
  if (result.status !== 200) { handleResult(result); return; }
  const replayed = result.headers.get('Idempotent-Replayed');
  const same = state.reservationId && result.data.id === state.reservationId;
  if (replayed && same) {
    showAlert('ok', `Reenvío con la misma clave: HTTP 200, ` +
      `Idempotent-Replayed: ${replayed}; misma reserva (no se duplicó).`);
  } else {
    showAlert('warn', `HTTP 200 sin replay esperado (cabecera ` +
      `${replayed || 'ausente'}, misma reserva: ${same ? 'sí' : 'no'}).`);
  }
  renderReservation(result.data);
  const list = await request('GET', `/reservations?customer_id=${result.data.customer_id}`);
  if (list.status === 200) {
    const ids = new Set((list.data || []).map((item) => item.id));
    if (ids.size !== 1 || !ids.has(result.data.id)) {
      showAlert('warn', `Hay ${ids.size} reservas para el cliente; revisa duplicados.`);
    }
  }
}

async function cancel() {
  clearAlerts();
  if (!state.reservationId) return;
  const result = await withRetry(() => request(
    'POST', `/reservations/${state.reservationId}/cancel`,
  ));
  if (![200, 202].includes(result.status)) { handleResult(result); return; }
  renderReservation(result.data);
  showAlert('ok', `Cancelación solicitada (HTTP ${result.status}).`);
  await poll();
}

function init() {
  fillCustomers();
  const today = new Date();
  const checkIn = new Date(today.getTime() + 86400000);
  const checkOut = new Date(today.getTime() + 3 * 86400000);
  byId('checkin').value = checkIn.toISOString().slice(0, 10);
  byId('checkout').value = checkOut.toISOString().slice(0, 10);
  byId('checkin').min = todayISO();
  byId('checkout').min = todayISO();
  byId('hotel').addEventListener('change', loadHotel);
  byId('buscarBtn').addEventListener('click', search);
  byId('customerForm').addEventListener('submit', createCustomer);
  byId('reservarBtn').addEventListener('click', reserve);
  byId('replayBtn').addEventListener('click', replay);
  byId('cancelBtn').addEventListener('click', cancel);
  loadHotels();
}

document.addEventListener('DOMContentLoaded', init);
