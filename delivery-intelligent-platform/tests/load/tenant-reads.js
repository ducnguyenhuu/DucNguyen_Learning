// Verifies spec 001 SC-003 against the deployed environment: 95% of tenant reads under 1 s at
// 50 concurrent users across 20 tenants (specs/006-ci-cd/contracts/load-test.md).
//
// Run: k6 run -e BASE_URL=https://<frontdoor> -e TOKEN=<bearer> -e TENANTS_FILE=tenants.json tenant-reads.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';

const tenants = JSON.parse(open(__ENV.TENANTS_FILE));
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
    'http_req_duration{phase:steady,kind:tenant-read}': ['p(95)<1000'],
    'http_req_failed{phase:steady}': ['rate<0.01'],
    // No limit: declaring it makes k6 export the steady-phase request count for the job summary.
    'http_reqs{phase:steady}': ['count>=0'],
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export function read() {
  // Virtual user n always reads tenant n mod 20, so every tenant gets the same load.
  const tenantId = tenants[(exec.vu.idInTest - 1) % tenants.length];
  const tags = { kind: 'tenant-read' };

  const tenant = http.get(`${baseUrl}/tenants/${tenantId}`, { headers, tags });
  const members = http.get(`${baseUrl}/tenants/${tenantId}/members`, { headers, tags });

  check(tenant, { 'tenant read is 200': (r) => r.status === 200 });
  check(members, { 'members read is 200': (r) => r.status === 200 });

  sleep(1);
}
