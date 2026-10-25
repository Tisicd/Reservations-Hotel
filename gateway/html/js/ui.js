let svgSeq = 0;

export function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'text') {
      node.textContent = String(value);
    } else if (key === 'class') {
      node.className = value;
    } else if (key === 'dataset') {
      Object.assign(node.dataset, value);
    } else if (key === 'html') {
      throw new Error('innerHTML no permitido');
    } else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else {
      node.setAttribute(key, value === true ? '' : String(value));
    }
  }
  append(node, children);
  return node;
}

export function append(parent, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    parent.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, String(value));
  }
  return node;
}

function hashSeed(value) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function pseudo(seed) {
  let value = seed % 2147483647;
  if (value <= 0) value += 2147483646;
  return () => {
    value = (value * 16807) % 2147483647;
    return (value - 1) / 2147483646;
  };
}

export function illustration(seed, variant = 0) {
  const hash = hashSeed(`${seed}:${variant}`);
  const rand = pseudo(hash);
  const hue = hash % 360;
  const hue2 = (hue + 45) % 360;
  const id = `grad-${svgSeq++}`;
  const svg = svgEl('svg', {
    viewBox: '0 0 640 360', role: 'img', 'aria-label': 'Ilustración del alojamiento',
    preserveAspectRatio: 'xMidYMid slice', class: 'card-media',
  });
  const defs = svgEl('defs');
  const gradient = svgEl('linearGradient', { id, x1: '0', y1: '0', x2: '0', y2: '1' });
  gradient.appendChild(svgEl('stop', { offset: '0', 'stop-color': `hsl(${hue} 62% 72%)` }));
  gradient.appendChild(svgEl('stop', { offset: '1', 'stop-color': `hsl(${hue2} 55% 42%)` }));
  defs.appendChild(gradient);
  svg.appendChild(defs);
  svg.appendChild(svgEl('rect', { width: '640', height: '360', fill: `url(#${id})` }));
  svg.appendChild(svgEl('circle', {
    cx: 90 + Math.round(rand() * 460), cy: 60 + Math.round(rand() * 50),
    r: 28 + Math.round(rand() * 18), fill: `hsl(${(hue + 180) % 360} 80% 82%)`,
    opacity: '0.9',
  }));

  if (variant % 3 === 0) {
    for (let index = 0; index < 7; index += 1) {
      const width = 40 + rand() * 55;
      const height = 70 + rand() * 150;
      const x = 20 + index * 88 + rand() * 15;
      const y = 360 - height;
      svg.appendChild(svgEl('rect', {
        x, y, width, height, rx: 5,
        fill: `hsl(${(hue + 15 + index * 4) % 360} 30% ${22 + rand() * 14}%)`,
      }));
      for (let row = 0; row < 3; row += 1) {
        for (let col = 0; col < 2; col += 1) {
          svg.appendChild(svgEl('rect', {
            x: x + 8 + col * 15, y: y + 12 + row * 20, width: 8, height: 10,
            fill: `hsl(${(hue + 180) % 360} 70% 80%)`, opacity: '0.75',
          }));
        }
      }
    }
  } else if (variant % 3 === 1) {
    svg.appendChild(svgEl('path', {
      d: 'M0 290 L120 150 L230 270 L340 120 L470 280 L640 140 L640 360 L0 360 Z',
      fill: `hsl(${(hue + 200) % 360} 32% 30%)`, opacity: '0.85',
    }));
    svg.appendChild(svgEl('path', {
      d: 'M0 320 L140 220 L260 315 L400 200 L520 310 L640 230 L640 360 L0 360 Z',
      fill: `hsl(${(hue + 210) % 360} 35% 22%)`,
    }));
    svg.appendChild(svgEl('path', {
      d: 'M0 340 Q160 320 320 340 T640 340 L640 360 L0 360 Z',
      fill: `hsl(${(hue + 190) % 360} 55% 58%)`, opacity: '0.8',
    }));
  } else {
    svg.appendChild(svgEl('path', {
      d: 'M0 300 Q180 240 360 300 T640 290 L640 360 L0 360 Z',
      fill: `hsl(${(hue + 30) % 360} 42% 46%)`,
    }));
    for (let index = 0; index < 6; index += 1) {
      svg.appendChild(svgEl('path', {
        d: `M${40 + index * 95} 360 q18 -${50 + rand() * 40} 36 0`,
        fill: `hsl(${(hue + 90) % 360} 30% ${25 + index * 3}%)`,
        opacity: '0.8',
      }));
    }
  }
  return svg;
}

const MONEY = new Intl.NumberFormat('es-EC', { style: 'currency', currency: 'USD' });

export function fmtMoney(cents) {
  return MONEY.format((Number(cents) || 0) / 100);
}

export function fmtDate(iso) {
  if (!iso) return '—';
  const date = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('es-EC', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function fmtTime(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleTimeString('es-EC');
}

export function nights(checkIn, checkOut) {
  const start = new Date(`${checkIn}T00:00:00`);
  const end = new Date(`${checkOut}T00:00:00`);
  return Math.max(0, Math.round((end - start) / 86400000));
}

export function nightsLabel(count) {
  return `${count} ${count === 1 ? 'noche' : 'noches'}`;
}

export function todayISO() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

export function addDays(iso, days) {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export function shortCode(id) {
  return `RES-${String(id || '').slice(0, 6).toUpperCase()}`;
}

const STATUS = {
  RECEIVED: { label: 'Recibida', tone: 'warn', title: 'Procesando tu reserva…', text: 'Estamos verificando disponibilidad.' },
  HELD: { label: 'Cupo retenido', tone: 'warn', title: 'Procesando tu reserva…', text: 'El cupo está retenido mientras se procesa el pago.' },
  PAYMENT_PENDING: { label: 'Pago pendiente', tone: 'warn', title: 'Procesando tu reserva…', text: 'Estamos esperando la confirmación del pago.' },
  PAYMENT_UNKNOWN: { label: 'Pago en revisión', tone: 'warn', title: 'Estamos revisando el pago…', text: 'El banco no respondió; se reconciliará automáticamente.' },
  PAID: { label: 'Pagado', tone: 'warn', title: 'Confirmando tu reserva…', text: 'El pago se aprobó; falta confirmar el cupo.' },
  CONFIRMED: { label: 'Confirmada', tone: 'ok', title: '¡Reserva confirmada!', text: 'Tu alojamiento está reservado.' },
  PAYMENT_DECLINED: { label: 'Pago rechazado', tone: 'error', title: 'El pago fue rechazado', text: 'No se realizó ningún cargo. Puedes intentar con otro método.' },
  REJECTED_NO_INVENTORY: { label: 'Sin cupo', tone: 'error', title: 'No quedó cupo', text: 'Otra persona tomó la última unidad mientras reservabas. No se realizó ningún cargo.' },
  FAILED_TECHNICAL: { label: 'Error técnico', tone: 'error', title: 'No pudimos completar la reserva', text: 'No se realizó ningún cargo. Intenta de nuevo.' },
  CANCELLED: { label: 'Cancelada', tone: 'neutral', title: 'Reserva cancelada', text: 'La reserva quedó cancelada.' },
  CANCELLING: { label: 'Cancelando', tone: 'warn', title: 'Cancelando tu reserva…', text: 'Estamos liberando el cupo y el pago.' },
  MANUAL_REVIEW: { label: 'En revisión', tone: 'warn', title: 'Reserva en revisión', text: 'Un operador revisará el caso; no se cobrará dos veces.' },
  REFUND_REQUIRED: { label: 'Reembolso', tone: 'warn', title: 'Reserva en revisión', text: 'Se requiere revisar el reembolso; no se asume completado.' },
};

export function statusMeta(status, reason) {
  const base = STATUS[status] || {
    label: status || 'Desconocido', tone: 'neutral', title: 'Estado desconocido', text: '',
  };
  if (status === 'PAYMENT_DECLINED' && reason) {
    return { ...base, text: 'No se realizó ningún cargo. Puedes intentar de nuevo.' };
  }
  return base;
}

export function badge(status, reason) {
  const meta = statusMeta(status, reason);
  return h('span', { class: `badge ${meta.tone}` }, meta.label);
}

const STABLE = new Set([
  'CONFIRMED', 'CANCELLED', 'REJECTED_NO_INVENTORY', 'PAYMENT_DECLINED',
  'FAILED_TECHNICAL', 'MANUAL_REVIEW', 'REFUND_REQUIRED',
]);

export function isStable(status) {
  return STABLE.has(status);
}

export function flash(kind, message) {
  const box = document.getElementById('flash');
  if (!box) return;
  const node = h('div', { class: `alert ${kind}`, role: 'status' }, message);
  const close = h('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Cerrar aviso', onclick: () => node.remove() }, '×');
  node.appendChild(close);
  box.replaceChildren(node);
  window.setTimeout(() => { if (node.isConnected) node.remove(); }, 9000);
}

export function setLive(message) {
  const live = document.getElementById('live');
  if (live) live.textContent = message;
}

export function skeletonCards(count = 3) {
  return h('div', { class: 'cards', 'aria-busy': 'true' },
    Array.from({ length: count }, () => h('article', { class: 'card' },
      h('div', { class: 'skeleton media' }),
      h('div', { class: 'card-body' },
        h('div', { class: 'skeleton line' }),
        h('div', { class: 'skeleton line short' })))));
}

export function emptyState(title, text, actions = []) {
  return h('div', { class: 'empty' },
    h('h2', { text: title }),
    h('p', { class: 'muted', text }),
    actions.length ? h('div', { class: 'actions' }, actions) : null);
}

export function errorState(result, retry) {
  const err = result && result.data && result.data.error;
  const message = (err && err.message) || `No se pudo completar la solicitud${result && result.status ? ` (HTTP ${result.status})` : ''}.`;
  return h('div', { class: 'error-box', role: 'alert' },
    h('h2', { text: 'Algo no salió bien' }),
    h('p', { text: message }),
    result && result.requestId ? h('p', { class: 'small muted' }, 'request_id: ', h('code', {}, result.requestId)) : null,
    retry ? h('button', { class: 'btn secondary', type: 'button', onclick: retry }, 'Reintentar') : null);
}

export function option(value, label, selected = false) {
  return h('option', { value, selected: selected ? '' : null }, label);
}
