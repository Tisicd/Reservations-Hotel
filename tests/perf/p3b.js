import http from 'k6/http';

const BASE = __ENV.BASE_URL;
const MODE = __ENV.MODE;
const ROOM = __ENV.ROOM_ID;
const ROOMS = (__ENV.ROOMS || '').split(',').filter(Boolean);
const FROM = __ENV.CHECK_IN;
const TO = __ENV.CHECK_OUT;
const RUN = __ENV.RUN_ID;

function hex(value, width) {
  return Number(value).toString(16).padStart(width, '0');
}

function holdId() {
  // UUID 8-4-4-4-12; la ultima parte incluye RUN para no colisionar entre
  // ejecuciones y VU/ITER para que los 200 holds sean distintos.
  const tail = RUN + hex(__VU, 2) + hex(__ITER, 2);
  return `${RUN}-0000-4000-8000-${tail}`;
}

export const options = {
  scenarios: {
    burst: {
      executor: 'shared-iterations',
      vus: 200,
      iterations: 200,
      maxDuration: '120s',
      gracefulStop: '10s',
    },
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  const room = MODE === 'V1' ? ROOM : ROOMS[(__VU - 1) % ROOMS.length];
  const id = holdId();
  http.post(
    `${BASE}/holds`,
    JSON.stringify({
      hold_id: id,
      room_id: room,
      check_in: FROM,
      check_out: TO,
      units: 1,
      ttl_seconds: 30,
    }),
    {
      headers: { 'Content-Type': 'application/json', 'X-Request-ID': id },
      tags: { name: 'hold' },
    },
  );
}

export function handleSummary(data) {
  return { '/out/summary.json': JSON.stringify(data) };
}
