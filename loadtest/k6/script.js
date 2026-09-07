// SnapTrack load test — auth + photo CRUD traffic.
//
//   docker run --rm --network snaptrack_default \
//     -e BASE_URL=http://api:8000 \
//     -v "$PWD/loadtest/k6:/scripts" grafana/k6 run /scripts/script.js
//
// See loadtest/README.md. Thresholds encode the SLO in docs/perf_slo.md.

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Trend, Counter } from 'k6/metrics';
import { b64decode } from 'k6/encoding';
import { textSummary } from './vendor/k6-summary.js';
import { htmlReport } from './vendor/k6-reporter.js';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const USER_POOL = Number(__ENV.USER_POOL || 40);
const RESULTS_DIR = __ENV.RESULTS_DIR || 'loadtest/results';
const SLEEP_MAX = Number(__ENV.SLEEP_MAX || 0.6);
const HOLD = __ENV.HOLD || '60s';
// SMOKE=1: shared CI runners are ~2 cores, so only assert correctness
// (no 5xx, checks pass), not the single-node latency SLO.
const SMOKE = __ENV.SMOKE === '1';
const PASSWORD = 'loadtest-password-123';

// 1x1 PNG (67 bytes) — keeps upload payload tiny so we measure the API, not the wire.
const PNG_1PX = b64decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
);

const errorRate = new Counter('snaptrack_business_errors');
const cacheReadTrend = new Trend('snaptrack_photo_read_ms', true);
const uploadTrend = new Trend('snaptrack_photo_upload_ms', true);
const listTrend = new Trend('snaptrack_photo_list_ms', true);

const SLO_THRESHOLDS = {
  http_req_failed: ['rate<0.001'], // < 0.1% errors
  'http_req_duration{expected_response:true}': ['p(95)<400'],
  snaptrack_photo_read_ms: ['p(95)<250'], // cache-hit read
  snaptrack_photo_list_ms: ['p(95)<300'],
  snaptrack_photo_upload_ms: ['p(95)<600'], // sync Pillow probe in-request
  checks: ['rate>0.99'],
};
const SMOKE_THRESHOLDS = {
  http_req_failed: ['rate<0.01'],
  checks: ['rate>0.98'],
};

export const options = {
  scenarios: {
    crud: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '15s', target: Number(__ENV.VUS || 50) },
        { duration: HOLD, target: Number(__ENV.VUS || 50) },
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
  // Thresholds == the SLO in docs/perf_slo.md, checked at the reference load
  // (VUS=50, ~0.3s think time, ~125-145 req/s on a 12-core single node).
  thresholds: SMOKE ? SMOKE_THRESHOLDS : SLO_THRESHOLDS,
};

function authHeaders(token) {
  return { headers: { Authorization: `Bearer ${token}` } };
}

// Register the user pool once; hand each VU a { email, token, photoId }.
export function setup() {
  const users = [];
  for (let i = 0; i < USER_POOL; i++) {
    const email = `k6-${Date.now()}-${i}@example.com`;
    http.post(`${BASE_URL}/auth/register`, JSON.stringify({ email, password: PASSWORD }), {
      headers: { 'Content-Type': 'application/json' },
    });
    const login = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({ email, password: PASSWORD }),
      { headers: { 'Content-Type': 'application/json' } },
    );
    const token = login.json('access_token');

    // Seed one photo per user so read/list/patch paths have a real target.
    const up = http.post(
      `${BASE_URL}/photos`,
      { file: http.file(PNG_1PX, 'seed.png', 'image/png'), caption: 'seed' },
      authHeaders(token),
    );
    users.push({ email, token, photoId: up.json('id') });
  }
  return { users };
}

export default function (data) {
  const user = data.users[(__VU + __ITER) % data.users.length];
  const auth = authHeaders(user.token);
  const roll = Math.random();

  if (roll < 0.4) {
    group('read photo (cache-aside)', () => {
      const res = http.get(`${BASE_URL}/photos/${user.photoId}`, auth);
      cacheReadTrend.add(res.timings.duration);
      check(res, { 'read 200': (r) => r.status === 200 }) || errorRate.add(1);
    });
  } else if (roll < 0.65) {
    group('list photos', () => {
      const res = http.get(`${BASE_URL}/photos?limit=20&offset=0`, auth);
      listTrend.add(res.timings.duration);
      check(res, { 'list 200': (r) => r.status === 200 }) || errorRate.add(1);
    });
  } else if (roll < 0.8) {
    group('upload photo', () => {
      const res = http.post(
        `${BASE_URL}/photos`,
        { file: http.file(PNG_1PX, 'pic.png', 'image/png'), caption: `vu${__VU}` },
        auth,
      );
      uploadTrend.add(res.timings.duration);
      check(res, { 'upload 201': (r) => r.status === 201 }) || errorRate.add(1);
    });
  } else if (roll < 0.92) {
    group('patch caption', () => {
      const res = http.patch(
        `${BASE_URL}/photos/${user.photoId}`,
        JSON.stringify({ caption: `edited ${Date.now()}` }),
        { headers: { ...auth.headers, 'Content-Type': 'application/json' } },
      );
      check(res, { 'patch 200': (r) => r.status === 200 }) || errorRate.add(1);
    });
  } else {
    group('thumbnail status', () => {
      const res = http.get(`${BASE_URL}/photos/${user.photoId}/thumbnail`, auth);
      check(res, { 'thumb 200': (r) => r.status === 200 }) || errorRate.add(1);
    });
  }

  sleep(Math.random() * SLEEP_MAX);
}

export function handleSummary(data) {
  return {
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
    [`${RESULTS_DIR}/summary.html`]: htmlReport(data),
    [`${RESULTS_DIR}/summary.json`]: JSON.stringify(data, null, 2),
  };
}
