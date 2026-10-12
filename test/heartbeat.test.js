const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { createServer } = require('../src/server');

test('worker heartbeat is persisted, visible to admin monitoring, and access-controlled', async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'jarvis-heartbeat-'));
  const server = createServer({
    storePath: path.join(dir, 'runtime.json'),
    adminToken: 'test-admin-secret',
    workerToken: 'test-worker-secret',
    workerId: 'worker-alpha'
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    await fs.rm(dir, { recursive: true, force: true });
  });

  const base = 'http://127.0.0.1:' + server.address().port;
  const admin = { authorization: 'Bearer test-admin-secret', 'content-type': 'application/json' };
  const worker = { authorization: 'Bearer test-worker-secret', 'content-type': 'application/json' };

  const createdResponse = await fetch(base + '/tasks', {
    method: 'POST', headers: admin, body: JSON.stringify({ goal: 'Check a game concept' })
  });
  assert.equal(createdResponse.status, 201);
  const { task: created } = await createdResponse.json();

  const acceptedResponse = await fetch(base + '/tasks/' + created.task_id + '/accept', {
    method: 'POST', headers: worker, body: JSON.stringify({})
  });
  assert.equal(acceptedResponse.status, 200);
  const accepted = (await acceptedResponse.json()).task;
  assert.ok(accepted.last_heartbeat_at);

  const heartbeatResponse = await fetch(base + '/tasks/' + created.task_id + '/heartbeat', {
    method: 'POST', headers: worker, body: JSON.stringify({ summary: 'Still working' })
  });
  assert.equal(heartbeatResponse.status, 200);
  const heartbeatTask = (await heartbeatResponse.json()).task;
  assert.ok(Date.parse(heartbeatTask.last_heartbeat_at) >= Date.parse(accepted.last_heartbeat_at));

  const monitoringResponse = await fetch(base + '/monitoring/workers', { headers: admin });
  assert.equal(monitoringResponse.status, 200);
  const monitoring = await monitoringResponse.json();
  assert.equal(monitoring.workers.length, 1);
  assert.equal(monitoring.workers[0].task_id, created.task_id);
  assert.equal(monitoring.workers[0].worker_id, 'worker-alpha');
  assert.equal(monitoring.workers[0].heartbeat_stale, false);

  const detailResponse = await fetch(base + '/tasks/' + created.task_id, { headers: admin });
  const detail = await detailResponse.json();
  assert.ok(detail.events.some((event) => event.event_type === 'heartbeat'));

  const forbiddenResponse = await fetch(base + '/monitoring/workers', { headers: worker });
  assert.equal(forbiddenResponse.status, 403);
});
