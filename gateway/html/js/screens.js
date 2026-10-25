import { request, uuid4, errorText, getLog } from './api.js';
import { state, setCustomer, clearCustomer } from './state.js';
import {
  h, illustration, fmtMoney, fmtDate, fmtTime, nights, nightsLabel, todayISO,
  addDays, shortCode, statusMeta, badge, isStable, flash, setLive,
  skeletonCards, emptyState, errorState, option,
} from './ui.js';
import { add as addRoute, navigate } from './router.js';

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function isISODate(value) {
  if (!ISO_DATE.test(value || '')) return false;
  const date = new Date(`${value}T12:00:00`);
  return !Number.isNaN(date.getTime());
}

function validateRange(checkIn, checkOut) {
  if (!isISODate(checkIn) || !isISODate(checkOut)) return 'Indica fechas de entrada y salida válidas.';
  if (checkIn < todayISO()) return 'La entrada no puede ser anterior a hoy.';
  const count = nights(checkIn, checkOut);
  if (count <= 0) return 'La salida debe ser posterior a la entrada.';
  if (count > 30) return 'El máximo es 30 noches por reserva.';
  return '';
}

function field(id, label, input) {
  return h('div', { class: 'field' }, h('label', { for: id }, label), input);
}

async function loadHotels() {
  if (state.hotels.length) return state.hotels;
  const result = await request('GET', '/hotels', { cache: true });
  if (result.status !== 200) throw result;
  state.hotels = result.data || [];
  return state.hotels;
}

async function loadHotelDetail(hotelId) {
  if (state.hotelDetails.has(hotelId)) return state.hotelDetails.get(hotelId);
  const result = await request('GET', `/hotels/${encodeURIComponent(hotelId)}`, { cache: true });
  if (result.status !== 200) throw result;
  state.hotelDetails.set(hotelId, result.data);
  return result.data;
}

async function loadAvailability(hotelId, checkIn, checkOut) {
  const key = `${hotelId}|${checkIn}|${checkOut}`;
  if (state.availability.has(key)) return state.availability.get(key);
  const query = new URLSearchParams({ hotel_id: hotelId, check_in: checkIn, check_out: checkOut });
  const result = await request('GET', `/availability?${query}`);
  if (result.status !== 200) throw result;
  const map = new Map(((result.data && result.data.rooms) || []).map((room) => [room.room_id, room.available]));
  state.availability.set(key, map);
  return map;
}

function invalidateAvailability() {
  state.availability.clear();
}

function notificationLabel(items) {
  if (!items || !items.length) return 'Aún no hay notificación.';
  const latest = items[items.length - 1];
  const status = latest.status || '—';
  const attempts = latest.attempts == null ? '—' : latest.attempts;
  return `${latest.type || 'notificación'} · ${status} · intentos: ${attempts}` +
    (latest.sent_at ? ` · ${fmtTime(latest.sent_at)}` : '');
}

function timelineList(events) {
  if (!events || !events.length) {
    return h('p', { class: 'muted small' }, 'Esperando eventos de la saga…');
  }
  const first = new Date(events[0].at).getTime();
  return h('ol', { class: 'timeline' }, events.map((event) => {
    const elapsed = Math.max(0, (new Date(event.at).getTime() - first) / 1000);
    return h('li', {},
      h('div', { class: 't-title' }, `${event.from || '—'} → ${event.to}`),
      h('div', { class: 't-meta' }, `${event.reason || 'sin motivo'} · ${fmtTime(event.at)} · +${elapsed.toFixed(1)} s`));
  }));
}

function searchForm({ citySelect, checkIn, checkOut, guests, onSearch }) {
  const inInput = h('input', { id: 'check_in', type: 'date', value: checkIn, min: todayISO(), required: true });
  const outInput = h('input', { id: 'check_out', type: 'date', value: checkOut, min: addDays(checkIn, 1), required: true });
  inInput.addEventListener('change', () => {
    if (!inInput.value) return;
    outInput.min = addDays(inInput.value, 1);
    if (!outInput.value || outInput.value <= inInput.value) outInput.value = addDays(inInput.value, 1);
  });
  const guestsSelect = h('select', { id: 'guests' },
    [1, 2, 3, 4].map((count) => option(String(count), `${count} huésped${count > 1 ? 'es' : ''}`, String(guests) === String(count))));
  const form = h('form', { class: 'search', role: 'search' },
    field('destino', 'Destino', citySelect),
    field('check_in', 'Entrada', inInput),
    field('check_out', 'Salida', outInput),
    field('guests', 'Huéspedes', guestsSelect),
    h('div', { class: 'search-actions' }, h('button', { class: 'btn', type: 'submit' }, 'Buscar')));
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const error = validateRange(inInput.value, outInput.value);
    if (error) { flash('error', error); return; }
    onSearch({
      destino: citySelect.value, check_in: inInput.value,
      check_out: outInput.value, guests: guestsSelect.value,
    });
  });
  return form;
}

function destinationCard(city, hotels, checkIn, checkOut, guests) {
  const href = `#/buscar?${new URLSearchParams({ destino: city, check_in: checkIn, check_out: checkOut, guests }).toString()}`;
  const count = hotels.filter((hotel) => hotel.city === city).length;
  return h('article', { class: 'card' },
    h('a', { href, 'aria-label': `Ver alojamientos en ${city}` }, illustration(city, 2)),
    h('div', { class: 'card-body' },
      h('h3', { class: 'card-title' }, city),
      h('p', { class: 'card-meta' }, `${count} alojamiento${count === 1 ? '' : 's'}`),
      h('a', { class: 'btn small secondary', href }, 'Explorar')));
}

export async function home(ctx) {
  document.title = 'Reservas UCE — alojamientos';
  const app = document.getElementById('app');
  const checkIn = isISODate(ctx.query.get('check_in')) ? ctx.query.get('check_in') : addDays(todayISO(), 1);
  const checkOut = isISODate(ctx.query.get('check_out')) ? ctx.query.get('check_out') : addDays(checkIn, 2);
  const guests = ctx.query.get('guests') || '2';
  const citySelect = h('select', { id: 'destino' }, option('', 'Cualquier destino'));
  const form = searchForm({
    citySelect, checkIn, checkOut, guests,
    onSearch: (params) => navigate('/buscar', params),
  });
  const destinations = h('div', { class: 'cards' }, skeletonCards(3));
  app.replaceChildren(
    h('section', { class: 'hero' },
      h('h1', {}, 'Encuentra tu próximo alojamiento'),
      h('p', {}, 'Busca por destino, compara habitaciones reales y reserva con seguimiento en vivo.'),
      form),
    h('section', {},
      h('div', { class: 'section-head' },
        h('h2', {}, 'Destinos populares'),
        h('span', { class: 'muted small' }, 'Ciudades de los hoteles disponibles')),
      destinations),
  );
  try {
    const hotels = await loadHotels();
    const cities = [...new Set(hotels.map((hotel) => hotel.city))].sort();
    const selected = ctx.query.get('destino') || '';
    citySelect.replaceChildren(option('', 'Cualquier destino'));
    for (const city of cities) citySelect.appendChild(option(city, city, city === selected));
    if (!cities.length) {
      destinations.replaceChildren(emptyState('Sin destinos', 'La API no devolvió hoteles.'));
      return;
    }
    destinations.replaceChildren(...cities.map((city) => destinationCard(city, hotels, checkIn, checkOut, guests)));
  } catch (result) {
    destinations.replaceChildren(errorState(result, () => home(ctx)));
  }
}

function resultCard(item, checkIn, checkOut, guests) {
  const { hotel, detail, from, available, eligibleRooms } = item;
  const count = nights(checkIn, checkOut);
  const href = `#/hotel/${hotel.id}?${new URLSearchParams({ check_in: checkIn, check_out: checkOut, guests }).toString()}`;
  return h('article', { class: 'card' },
    h('a', { href, 'aria-label': `Ver ${hotel.name}` }, illustration(hotel.id, 0)),
    h('div', { class: 'card-body' },
      h('div', { class: 'section-head' },
        h('h3', { class: 'card-title' }, hotel.name),
        h('span', { class: `badge ${eligibleRooms === 0 ? 'neutral' : available > 0 ? 'ok' : 'error'}` },
          eligibleRooms === 0 ? 'Sin capacidad' : available > 0 ? `Quedan ${available}` : 'Agotado')),
      h('p', { class: 'card-meta' }, hotel.city),
      h('p', { class: 'card-meta' }, eligibleRooms === 0
        ? `Sin habitaciones para ${guests} huésped${guests === 1 ? '' : 'es'}`
        : `${eligibleRooms} tipo${eligibleRooms === 1 ? '' : 's'} de habitación`),
      h('div', { class: 'card-foot' },
        h('span', { class: 'price' }, from == null ? 'No disponible' : `Desde ${fmtMoney(from)} `,
          from == null ? null : h('small', {}, '/noche')),
        h('span', { class: 'small muted' },
          from == null ? '' : `Total desde ${fmtMoney(from * count)} · ${nightsLabel(count)}`)),
      h('div', { class: 'actions' },
        h('a', { class: 'btn small', href }, 'Ver habitaciones'))));
}

export async function results(ctx) {
  document.title = 'Resultados — Reservas UCE';
  const app = document.getElementById('app');
  const checkIn = ctx.query.get('check_in') || addDays(todayISO(), 1);
  const checkOut = ctx.query.get('check_out') || addDays(checkIn, 2);
  const guests = Math.max(1, Number(ctx.query.get('guests') || 2) || 2);
  const destino = ctx.query.get('destino') || '';
  const error = validateRange(checkIn, checkOut);
  if (error) {
    app.replaceChildren(emptyState('Revisa las fechas', error,
      [h('a', { class: 'btn', href: '#/' }, 'Volver al inicio')]));
    return;
  }
  const list = h('div', { class: 'cards', 'aria-busy': 'true' }, skeletonCards(3));
  const filterBox = h('div');
  app.replaceChildren(
    h('div', { class: 'section-head' },
      h('div', {},
        h('h1', {}, destino ? `Alojamientos en ${destino}` : 'Alojamientos disponibles'),
        h('p', { class: 'muted' }, `${fmtDate(checkIn)} → ${fmtDate(checkOut)} · ${nightsLabel(nights(checkIn, checkOut))} · ${guests} huésped${guests === 1 ? '' : 'es'}`)),
      h('a', { class: 'btn secondary small', href: `#/?${new URLSearchParams({ check_in: checkIn, check_out: checkOut, guests })}` }, 'Editar búsqueda')),
    filterBox,
    list,
  );
  try {
    const hotels = await loadHotels();
    const candidates = destino
      ? hotels.filter((hotel) => hotel.city.toLowerCase() === destino.toLowerCase())
      : hotels;
    const items = [];
    for (const hotel of candidates) {
      try {
        const detail = await loadHotelDetail(hotel.id);
        const availability = await loadAvailability(hotel.id, checkIn, checkOut);
        const allRooms = detail.rooms || [];
        const rooms = allRooms.filter((room) => room.capacity >= guests);
        const from = rooms.length ? Math.min(...rooms.map((room) => room.price_per_night_cents)) : null;
        const available = rooms.reduce((sum, room) => sum + (availability.get(room.id) || 0), 0);
        const capacity = rooms.length ? Math.max(...rooms.map((room) => room.capacity)) : 0;
        items.push({ hotel, detail, from, available, capacity, eligibleRooms: rooms.length });
      } catch (_) {
        /* un hotel con error no bloquea el resto */
      }
    }
    if (!items.length) {
      filterBox.replaceChildren();
      list.replaceChildren(emptyState('Sin alojamientos', 'No hay hoteles que coincidan con el destino y las fechas.'));
      return;
    }
    const cityFilter = h('select', { id: 'filter-city' }, option('', 'Todas'), [...new Set(items.map((item) => item.hotel.city))].sort().map((city) => option(city, city, city === destino)));
    const maxFilter = h('input', { id: 'filter-max', type: 'number', min: '0', step: '10', placeholder: 'Sin límite (USD)' });
    const capacityFilter = h('select', { id: 'filter-capacity' }, option('', 'Cualquiera'), [1, 2, 3, 4].map((n) => option(String(n), `${n}+ personas`)));
    const sortFilter = h('select', { id: 'filter-sort' }, option('price-asc', 'Precio: menor'), option('price-desc', 'Precio: mayor'));
    const draw = () => {
      const city = cityFilter.value.toLowerCase();
      const max = maxFilter.value ? Number(maxFilter.value) * 100 : null;
      const capacity = capacityFilter.value ? Number(capacityFilter.value) : 0;
      let visible = items.filter((item) =>
        (!city || item.hotel.city.toLowerCase() === city)
        && (!max || (item.from != null && item.from <= max))
        && (!capacity || item.capacity >= capacity));
      visible = visible.slice().sort((a, b) => {
        const priceA = a.from == null ? Number.MAX_SAFE_INTEGER : a.from;
        const priceB = b.from == null ? Number.MAX_SAFE_INTEGER : b.from;
        return sortFilter.value === 'price-desc' ? priceB - priceA : priceA - priceB;
      });
      if (!visible.length) {
        list.replaceChildren(emptyState('Sin resultados con esos filtros', 'Prueba a ampliar el precio o la capacidad.'));
        return;
      }
      list.replaceChildren(...visible.map((item) => resultCard(item, checkIn, checkOut, guests)));
      setLive(`${visible.length} alojamientos encontrados`);
    };
    for (const control of [cityFilter, maxFilter, capacityFilter, sortFilter]) {
      control.addEventListener('input', draw);
      control.addEventListener('change', draw);
    }
    filterBox.replaceChildren(h('div', { class: 'filters' },
      field('filter-city', 'Ciudad', cityFilter),
      field('filter-max', 'Precio máximo', maxFilter),
      field('filter-capacity', 'Capacidad', capacityFilter),
      field('filter-sort', 'Ordenar por', sortFilter)));
    list.removeAttribute('aria-busy');
    draw();
  } catch (result) {
    list.replaceChildren(errorState(result, () => results(ctx)));
  }
}

export async function hotelScreen(ctx) {
  document.title = 'Alojamiento — Reservas UCE';
  const app = document.getElementById('app');
  const checkIn = ctx.query.get('check_in') || addDays(todayISO(), 1);
  const checkOut = ctx.query.get('check_out') || addDays(checkIn, 2);
  const guests = Math.max(1, Number(ctx.query.get('guests') || 2) || 2);
  const error = validateRange(checkIn, checkOut);
  if (error) {
    app.replaceChildren(emptyState('Revisa las fechas', error, [h('a', { class: 'btn', href: '#/' }, 'Volver')]));
    return;
  }
  app.replaceChildren(skeletonCards(1));
  try {
    const detail = await loadHotelDetail(ctx.params.id);
    const availability = await loadAvailability(detail.id, checkIn, checkOut);
    const rooms = detail.rooms || [];
    const eligible = rooms.filter((room) => room.capacity >= guests);
    const from = eligible.length
      ? Math.min(...eligible.map((room) => room.price_per_night_cents))
      : null;
    const count = nights(checkIn, checkOut);
    const backHref = `#/buscar?${new URLSearchParams({ destino: detail.city, check_in: checkIn, check_out: checkOut, guests }).toString()}`;
    const gallery = h('div', { class: 'cards' },
      [0, 1, 2].map((index) => h('div', { class: 'card' }, illustration(`${detail.id}-${index}`, index))));
    const roomList = rooms.map((room) => {
      const fits = room.capacity >= guests;
      const available = fits ? (availability.get(room.id) || 0) : 0;
      const canBook = available > 0;
      const total = room.price_per_night_cents * count;
      const bookHref = `#/reservar?${new URLSearchParams({
        hotel: detail.id, room: room.id, check_in: checkIn, check_out: checkOut, guests,
      }).toString()}`;
      return h('div', { class: 'room' },
        h('div', {},
          h('h3', {}, room.name),
          h('p', { class: 'card-meta' }, fits
            ? `Para ${room.capacity} persona${room.capacity === 1 ? '' : 's'}`
            : `Capacidad ${room.capacity}: no alcanza para ${guests} huésped${guests === 1 ? '' : 'es'}`),
          h('p', { class: 'price' }, `${fmtMoney(room.price_per_night_cents)} /noche `,
            h('span', { class: 'muted small' }, `· total ${fmtMoney(total)} por ${nightsLabel(count)}`))),
        h('div', { class: 'actions' },
          h('span', { class: `badge ${!fits ? 'neutral' : available > 0 ? 'ok' : 'error'}` },
            !fits ? 'No apta' : available > 0 ? `Quedan ${available}` : 'Agotado'),
          canBook
            ? h('a', { class: 'btn small', href: bookHref }, 'Reservar')
            : h('button', { class: 'btn small', type: 'button', disabled: true },
              !fits ? 'No apta' : 'Sin cupo')));
    });
    app.replaceChildren(
      h('p', {}, h('a', { class: 'muted small', href: backHref }, '← Volver a resultados')),
      h('div', { class: 'section-head' },
        h('div', {},
          h('h1', {}, detail.name),
          h('p', { class: 'muted' }, `${detail.city} · ${fmtDate(checkIn)} → ${fmtDate(checkOut)} · ${nightsLabel(count)}`)),
        h('span', { class: 'price' }, from == null ? '' : `Desde ${fmtMoney(from)} `, h('small', {}, '/noche'))),
      gallery,
      h('div', { class: 'layout' },
        h('section', { class: 'panel' },
          h('h2', {}, 'Habitaciones'),
          rooms.length ? roomList : h('p', { class: 'muted' }, 'Este alojamiento no tiene habitaciones publicadas.')),
        h('aside', { class: 'summary' },
          h('h2', {}, 'Tu estancia'),
          h('dl', {},
            h('dt', {}, 'Entrada'), h('dd', {}, fmtDate(checkIn)),
            h('dt', {}, 'Salida'), h('dd', {}, fmtDate(checkOut)),
            h('dt', {}, 'Noches'), h('dd', {}, String(count)),
            h('dt', {}, 'Huéspedes'), h('dd', {}, String(guests)))),
      ));
  } catch (result) {
    app.replaceChildren(errorState(result, () => hotelScreen(ctx)));
  }
}

function summaryBlock(title, rows) {
  return h('aside', { class: 'summary' },
    h('h2', {}, title),
    h('dl', {}, rows.flatMap(([label, value]) => [h('dt', {}, label), h('dd', {}, value)])));
}

async function demoGuest() {
  // Los IDs de la semilla no se listan por API; creamos un huésped demo
  // temporal con email único para que el flujo funcione sin datos fijos.
  const result = await request('POST', '/customers', {
    body: { name: 'Huésped Demo', email: `demo-${uuid4()}@example.com` },
  });
  if (![200, 201].includes(result.status)) {
    flash('error', `${errorText(result)} (request_id ${result.requestId || '—'})`);
    return null;
  }
  setCustomer(result.data);
  return result.data;
}

export async function booking(ctx) {
  document.title = 'Reservar — Reservas UCE';
  const app = document.getElementById('app');
  const hotelId = ctx.query.get('hotel');
  const roomId = ctx.query.get('room');
  const checkIn = ctx.query.get('check_in');
  const checkOut = ctx.query.get('check_out');
  const guests = Math.max(1, Number(ctx.query.get('guests') || 2) || 2);
  const error = validateRange(checkIn, checkOut);
  if (!hotelId || !roomId || error) {
    app.replaceChildren(emptyState('Reserva incompleta', error || 'Faltan datos del alojamiento.',
      [h('a', { class: 'btn', href: '#/' }, 'Volver a buscar')]));
    return;
  }
  const signature = `${hotelId}|${roomId}|${checkIn}|${checkOut}`;
  if (state.bookingSignature !== signature) {
    state.bookingSignature = signature;
    state.bookingKey = null;
    state.lastBooking = null;
  }
  app.replaceChildren(skeletonCards(1));
  try {
    const detail = await loadHotelDetail(hotelId);
    const availability = await loadAvailability(hotelId, checkIn, checkOut);
    const room = (detail.rooms || []).find((item) => item.id === roomId);
    if (!room) {
      app.replaceChildren(emptyState('Habitación no encontrada', 'Vuelve a elegir una habitación.',
        [h('a', { class: 'btn', href: '#/' }, 'Volver')]));
      return;
    }
    const count = nights(checkIn, checkOut);
    const fits = room.capacity >= guests;
    const available = fits ? (availability.get(roomId) || 0) : 0;
    const total = room.price_per_night_cents * count;
    const summary = summaryBlock('Resumen', [
      ['Alojamiento', detail.name],
      ['Ciudad', detail.city],
      ['Habitación', room.name],
      ['Entrada', fmtDate(checkIn)],
      ['Salida', fmtDate(checkOut)],
      ['Noches', String(count)],
      ['Huéspedes', String(guests)],
      ['Total', fmtMoney(total)],
    ]);
    const render = () => {
      const customerPanel = state.customer
        ? h('div', { class: 'panel' },
          h('h2', {}, 'Huésped'),
          h('p', {}, state.customer.name),
          h('p', { class: 'muted small' }, state.customer.email),
          h('button', { class: 'ghost', type: 'button', onclick: () => { clearCustomer(); mount(); } }, 'Cambiar huésped'))
        : (() => {
          const name = h('input', { id: 'guest-name', autocomplete: 'name', required: true });
          const email = h('input', { id: 'guest-email', type: 'email', autocomplete: 'email', required: true });
          const create = h('button', { class: 'btn secondary', type: 'button' }, 'Crear y continuar');
          create.addEventListener('click', async () => {
            if (!name.value.trim() || !email.value.trim()) { flash('error', 'Nombre y email son obligatorios.'); return; }
            create.disabled = true;
            const result = await request('POST', '/customers', { body: { name: name.value.trim(), email: email.value.trim() } });
            create.disabled = false;
            if (result.status === 201 || result.status === 200) {
              setCustomer(result.data);
              mount();
            } else if (result.status === 409) {
              flash('warn', 'Ese email ya está registrado; usa otro o el usuario de demostración.');
            } else {
              flash('error', `${errorText(result)} (request_id ${result.requestId || '—'})`);
            }
          });
          const demo = h('button', { class: 'ghost', type: 'button', onclick: async () => {
            const customer = await demoGuest();
            if (customer) mount();
          } }, 'Usar usuario de demostración');
          return h('div', { class: 'panel' },
            h('h2', {}, 'Huésped'),
            h('div', { class: 'form-grid' },
              field('guest-name', 'Nombre', name),
              field('guest-email', 'Email', email)),
            h('div', { class: 'actions' }, create, demo),
            h('p', { class: 'muted small' }, 'Se crea el cliente con POST /api/customers; no se guardan datos sensibles.'));
        })();
      const payment = h('select', { id: 'payment-sim' },
        option('ok', 'Tarjeta aprobada (simulación)'),
        option('decline', 'Tarjeta rechazada'),
        option('process_then_drop_response', 'Banco sin respuesta'),
        option('slow', 'Pago lento'));
      const confirm = h('button', { class: 'btn block', type: 'button' }, 'Confirmar reserva');
      confirm.disabled = !state.customer || available <= 0 || !fits;
      confirm.addEventListener('click', async () => {
        if (!state.customer) { flash('error', 'Elige o crea un huésped.'); return; }
        if (!fits) { flash('error', `La habitación no tiene capacidad para ${guests} huésped${guests === 1 ? '' : 'es'}.`); return; }
        if (available <= 0) { flash('error', 'No hay cupo para estas fechas.'); return; }
        if (!state.bookingKey) state.bookingKey = uuid4();
        const body = {
          customer_id: state.customer.id,
          hotel_id: hotelId,
          room_id: roomId,
          check_in: checkIn,
          check_out: checkOut,
          payment: { method: 'card', token: 'tok_demo', simulate: payment.value },
        };
        state.lastBooking = { key: state.bookingKey, body, path: '/reservations' };
        confirm.disabled = true;
        confirm.textContent = 'Procesando…';
        const result = await request('POST', '/reservations', { body, key: state.bookingKey });
        if ([200, 201, 202].includes(result.status)) {
          invalidateAvailability();
          state.lastBooking.reservationId = result.data.id;
          // Nueva reserva => nueva clave en el próximo intento; el replay usa lastBooking.
          state.bookingKey = null;
          navigate(`/reserva/${result.data.id}`);
        } else {
          confirm.disabled = false;
          confirm.textContent = 'Confirmar reserva';
          // Si hubo respuesta de negocio, el próximo clic es un intento nuevo.
          // Si fue red/429/503, se conserva la clave para reintentar sin duplicar.
          if (![0, 429, 503].includes(result.status)) state.bookingKey = null;
          const requestId = result.requestId ? ` (request_id ${result.requestId})` : '';
          flash('error', `${errorText(result)}${requestId}`);
        }
      });
      return h('div', { class: 'layout' },
        h('div', {},
          customerPanel,
          h('div', { class: 'panel' },
            h('h2', {}, 'Pago'),
            h('p', { class: 'note' }, 'Modo demostración: no ingreses datos reales de tarjeta.'),
            field('payment-sim', 'Método (simulado)', payment),
            !fits
              ? h('p', { class: 'badge error' },
                `Esta habitación es para ${room.capacity}; no alcanza para ${guests} huésped${guests === 1 ? '' : 'es'}.`)
              : available <= 0
                ? h('p', { class: 'badge error' }, 'Sin cupo para estas fechas')
                : null,
            h('div', { class: 'actions' }, confirm))),
        summary);
    };
    const backLink = h('p', {}, h('a', { class: 'muted small', href: `#/hotel/${hotelId}?${new URLSearchParams({ check_in: checkIn, check_out: checkOut, guests }).toString()}` }, '← Volver al alojamiento'));
    const heading = h('h1', {}, 'Reserva y pago');
    const mount = () => app.replaceChildren(backLink, heading, render());
    mount();
  } catch (result) {
    app.replaceChildren(errorState(result, () => booking(ctx)));
  }
}

export async function statusScreen(ctx) {
  document.title = 'Tu reserva — Reservas UCE';
  const app = document.getElementById('app');
  const reservationId = ctx.params.id;
  state.currentReservationId = reservationId;
  state.currentEvents = [];
  state.currentNotifications = [];
  app.replaceChildren(h('div', { class: 'panel' },
    h('h1', {}, 'Procesando tu reserva…'),
    h('p', { class: 'muted' }, 'Estamos siguiendo la saga en vivo.'),
    h('div', { class: 'skeleton line' })));
  let attempt = 0;
  const deadline = Date.now() + 90000;

  const cancel = async () => {
    const result = await request('POST', `/reservations/${reservationId}/cancel`);
    if ([200, 202].includes(result.status)) {
      invalidateAvailability();
      flash('ok', 'Cancelación solicitada.');
      tick();
    } else {
      flash('error', `${errorText(result)} (request_id ${result.requestId || '—'})`);
    }
  };

  const render = (reservation, events, notifications) => {
    const meta = statusMeta(reservation.status, reservation.status_reason);
    const count = reservation.nights || nights(reservation.check_in, reservation.check_out);
    const details = h('dl', {},
      h('dt', {}, 'Código'), h('dd', {}, shortCode(reservation.id)),
      h('dt', {}, 'Entrada'), h('dd', {}, fmtDate(reservation.check_in)),
      h('dt', {}, 'Salida'), h('dd', {}, fmtDate(reservation.check_out)),
      h('dt', {}, 'Noches'), h('dd', {}, String(count)),
      h('dt', {}, 'Total'), h('dd', {}, fmtMoney(reservation.amount_cents)),
      h('dt', {}, 'Pago'), h('dd', {}, (reservation.payment && reservation.payment.status) || '—'));
    const actions = h('div', { class: 'actions' });
    if (reservation.status === 'CONFIRMED') {
      actions.appendChild(h('button', { class: 'btn danger small', type: 'button', onclick: cancel }, 'Cancelar reserva'));
      actions.appendChild(h('a', { class: 'btn secondary small', href: '#/mis-reservas' }, 'Mis reservas'));
    } else if (['PAYMENT_DECLINED', 'REJECTED_NO_INVENTORY', 'FAILED_TECHNICAL', 'CANCELLED'].includes(reservation.status)) {
      actions.appendChild(h('a', { class: 'btn', href: '#/' }, 'Volver a buscar'));
    }
    app.replaceChildren(
      h('section', { class: 'panel', 'aria-live': 'polite' },
        h('span', { class: `badge ${meta.tone}` }, meta.label),
        h('h1', {}, meta.title),
        h('p', { class: 'muted' }, meta.text),
        reservation.status === 'CONFIRMED' ? h('p', { class: 'price' }, shortCode(reservation.id)) : null,
        details,
        actions),
      h('div', { class: 'layout' },
        h('section', { class: 'panel' },
          h('h2', {}, 'Línea de tiempo'),
          timelineList(events)),
        h('aside', { class: 'panel' },
          h('h2', {}, 'Notificación'),
          h('p', { class: 'small muted' }, notificationLabel(notifications)),
          h('p', { class: 'small muted' }, 'Datos reales de GET /api/notifications.'))),
    );
    setLive(`${meta.title}. ${meta.text}`);
  };

  let lastReservation = null;
  let notifPoll = 0;
  const refreshNotifications = async () => {
    if (!window.location.hash.startsWith(`#/reserva/${reservationId}`)) return;
    if (notifPoll >= 6) return;
    notifPoll += 1;
    const result = await request(
      'GET', `/notifications?reservation_id=${encodeURIComponent(reservationId)}`);
    if (result.status === 200) {
      const list = result.data || [];
      state.currentNotifications = list;
      window.dispatchEvent(new Event('demo:refresh'));
      if (lastReservation) render(lastReservation, state.currentEvents, list);
      const latest = list[list.length - 1];
      if (latest && ['SENT', 'FAILED'].includes(latest.status)) return;
    }
    window.setTimeout(refreshNotifications, 2000);
  };

  const tick = async () => {
    if (!window.location.hash.startsWith(`#/reserva/${reservationId}`)) return;
    const result = await request('GET', `/reservations/${reservationId}`);
    if (result.status === 404) {
      app.replaceChildren(emptyState('Reserva no encontrada', 'El identificador no existe.',
        [h('a', { class: 'btn', href: '#/' }, 'Volver al inicio')]));
      return;
    }
    if (result.status !== 200) {
      app.replaceChildren(errorState(result, () => tick()));
      return;
    }
    const [events, notifications] = await Promise.all([
      request('GET', `/reservations/${reservationId}/events`),
      request('GET', `/notifications?reservation_id=${encodeURIComponent(reservationId)}`),
    ]);
    const eventItems = events.status === 200 ? (events.data || []) : [];
    const notificationItems = notifications.status === 200 ? (notifications.data || []) : [];
    state.currentEvents = eventItems;
    state.currentNotifications = notificationItems;
    lastReservation = result.data;
    window.dispatchEvent(new Event('demo:refresh'));
    render(result.data, eventItems, notificationItems);
    if (isStable(result.data.status)) {
      // La confirmación es estable, pero la notificación puede llegar después.
      window.setTimeout(refreshNotifications, 1200);
      return;
    }
    if (Date.now() > deadline) {
      flash('warn', 'La reserva sigue procesándose; puedes consultarla en Mis reservas.');
      return;
    }
    attempt += 1;
    window.setTimeout(tick, Math.min(5000, 1000 * Math.pow(1.5, attempt)));
  };

  tick();
}

export async function myReservations(ctx) {
  document.title = 'Mis reservas — Reservas UCE';
  const app = document.getElementById('app');
  if (!state.customer) {
    app.replaceChildren(emptyState('Aún no has reservado',
      'Crea un huésped y reserva; después podrás ver y cancelar tus reservas aquí.',
      [h('a', { class: 'btn', href: '#/' }, 'Buscar alojamiento')]));
    return;
  }
  app.replaceChildren(h('div', { class: 'section-head' },
    h('div', {}, h('h1', {}, 'Mis reservas'), h('p', { class: 'muted small' }, state.customer.email)),
    h('button', { class: 'ghost', type: 'button', onclick: () => { clearCustomer(); myReservations(ctx); } }, 'Cambiar usuario')));
  const list = h('div', { class: 'cards' }, skeletonCards(2));
  app.appendChild(list);
  try {
    const result = await request('GET', `/reservations?customer_id=${encodeURIComponent(state.customer.id)}`);
    if (result.status !== 200) throw result;
    const reservations = (result.data || []).slice().sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
    if (!reservations.length) {
      list.replaceChildren(emptyState('Sin reservas', 'Cuando reserves, aparecerán aquí.',
        [h('a', { class: 'btn', href: '#/' }, 'Buscar alojamiento')]));
      return;
    }
    let hotels = [];
    try { hotels = await loadHotels(); } catch (_) { hotels = []; }
    const hotelNames = new Map(hotels.map((hotel) => [hotel.id, hotel.name]));
    const details = new Map();
    for (const hotelId of [...new Set(reservations.map((item) => item.hotel_id))]) {
      try { details.set(hotelId, await loadHotelDetail(hotelId)); } catch (_) { /* opcional */ }
    }
    const cards = reservations.map((reservation) => {
      const meta = statusMeta(reservation.status, reservation.status_reason);
      const detail = details.get(reservation.hotel_id);
      const room = detail && detail.rooms ? detail.rooms.find((item) => item.id === reservation.room_id) : null;
      const name = (detail && detail.name) || hotelNames.get(reservation.hotel_id) || 'Alojamiento reservado';
      const card = h('article', { class: 'card' },
        h('div', { class: 'card-body' },
          h('div', { class: 'section-head' }, h('h2', { class: 'card-title' }, name), h('span', { class: `badge ${meta.tone}` }, meta.label)),
          h('p', { class: 'card-meta' }, room ? room.name : 'Habitación reservada'),
          h('p', { class: 'card-meta' }, `${fmtDate(reservation.check_in)} → ${fmtDate(reservation.check_out)} · ${nightsLabel(reservation.nights || nights(reservation.check_in, reservation.check_out))}`),
          h('div', { class: 'card-foot' },
            h('span', { class: 'price' }, fmtMoney(reservation.amount_cents)),
            h('span', { class: 'small muted' }, shortCode(reservation.id))),
          h('div', { class: 'actions' },
            h('a', { class: 'btn small secondary', href: `#/reserva/${reservation.id}` }, 'Ver estado'),
            reservation.status === 'CONFIRMED'
              ? h('button', { class: 'btn small danger', type: 'button', onclick: async () => {
                const cancelResult = await request('POST', `/reservations/${reservation.id}/cancel`);
                if ([200, 202].includes(cancelResult.status)) {
                  invalidateAvailability();
                  flash('ok', 'Cancelación solicitada.');
                  myReservations(ctx);
                } else {
                  flash('error', `${errorText(cancelResult)} (request_id ${cancelResult.requestId || '—'})`);
                }
              } }, 'Cancelar')
              : null)));
      return card;
    });
    list.replaceChildren(...cards);
  } catch (result) {
    list.replaceChildren(errorState(result, () => myReservations(ctx)));
  }
}

export function boot() {
  window.addEventListener('api:notice', (event) => {
    const detail = event.detail || {};
    if (detail.status === 429) {
      flash('warn', `Demasiadas solicitudes; reintentando en ${detail.wait} s.`);
    } else if (detail.status === 503) {
      flash('warn', `Servicio no disponible; se reintenta en ${detail.wait} s con la misma clave.`);
    } else {
      flash('warn', 'Sin conexión con el servidor; reintentando.');
    }
  });
  addRoute('/', home);
  addRoute('/buscar', results);
  addRoute('/hotel/:id', hotelScreen);
  addRoute('/reservar', booking);
  addRoute('/reserva/:id', statusScreen);
  addRoute('/mis-reservas', myReservations);
}

export { getLog };
