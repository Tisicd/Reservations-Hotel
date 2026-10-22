import http from 'k6/http';

const BASE = __ENV.BASE_URL;
const MODE = __ENV.MODE;
const ROOM = __ENV.ROOM_ID;
const ROOMS = (__ENV.ROOMS || '').split(',').filter(Boolean);
const HOTEL = __ENV.HOTEL_ID;
const CUSTOMER = __ENV.CUSTOMER_ID;
const FROM = __ENV.CHECK_IN;
const TO = __ENV.CHECK_OUT;
const RUN = __ENV.RUN_ID;

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
  const key = `${RUN}-${__VU}-${__ITER}`;
  http.post(
    `${BASE}/api/reservations`,
    JSON.stringify({
      customer_id: CUSTOMER,
      hotel_id: HOTEL,
      room_id: room,
      check_in: FROM,
      check_out: TO,
      payment: { method: 'card', token: 'tok_demo', simulate: 'ok' },
    }),
    {
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': key,
        'X-Request-ID': key,
      },
      tags: { name: 'reservation' },
    },
  );
}

export function handleSummary(data) {
  return { '/out/summary.json': JSON.stringify(data) };
}
