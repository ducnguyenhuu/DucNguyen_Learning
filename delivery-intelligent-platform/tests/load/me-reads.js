// Verifies spec 001 SC-003, as reinterpreted by ADR-025, against the deployed environment: 95% of
// GET /me calls under 1 s at 50 concurrent callers. GET /me needs no seeded data, so there is no
// seeding step.
//
// Run: k6 run -e BASE_URL=https://<frontdoor> -e TOKEN=<bearer> me-reads.js
import http from 'k6/http';
import { check, sleep } from 'k6';

const baseUrl = __ENV.BASE_URL;
const headers = { Authorization: `Bearer ${__ENV.TOKEN}` };

export const options = {
  scenarios: {
    warmup: {
      executor: 'constant-vus',
      vus: 50,
      duration: '30s',
      tags: { phase: 'warmup' },
      exec: 'read',
    },
    steady: {
      executor: 'constant-vus',
      vus: 50,
      duration: '2m',
      startTime: '30s',
      tags: { phase: 'steady' },
      exec: 'read',
    },
  },
  thresholds: {
    'http_req_duration{phase:steady,kind:me-read}': ['p(95)<1000'],
    'http_req_failed{phase:steady}': ['rate<0.01'],
    // No limit: declaring it makes k6 export the steady-phase request count for the job summary.
    'http_reqs{phase:steady}': ['count>=0'],
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export function read() {
  const me = http.get(`${baseUrl}/me`, { headers, tags: { kind: 'me-read' } });

  check(me, { 'me read is 200': (r) => r.status === 200 });

  sleep(1);
}
