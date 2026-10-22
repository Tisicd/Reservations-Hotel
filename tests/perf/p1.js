import http from 'k6/http';

const BASE = __ENV.BASE_URL;
const HOTEL = __ENV.HOTEL_ID;
const FROM = __ENV.CHECK_IN;
const TO = __ENV.CHECK_OUT;
const TARGET = Number(__ENV.TARGET_RATE || 400);
const RAMP = __ENV.RAMP || '60s';

export const options = {
  scenarios: {
    load: {
      executor: 'ramping-arrival-rate',
      startRate: 20,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 1500,
      stages: [
        { target: 20, duration: '20s' },
        { target: TARGET, duration: RAMP },
      ],
      gracefulStop: '10s',
    },
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  http.get(
    `${BASE}/api/availability?hotel_id=${HOTEL}&check_in=${FROM}&check_out=${TO}`,
    { tags: { name: 'availability' } },
  );
}

export function handleSummary(data) {
  return { '/out/summary.json': JSON.stringify(data) };
}
