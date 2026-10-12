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

test('monitoring excludes results awaiting validation because worker execution has ended', async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'jarvis-monitor-state-'));
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
  const created = await (await fetch(base + '/tasks', { method: 'POST', headers: admin, body: JSON.stringify({ goal: 'Return a result' }) })).json();
  const id = created.task.task_id;
  await fetch(base + '/tasks/' + id + '/accept', { method: 'POST', headers: worker, body: '{}' });
  const result = await fetch(base + '/tasks/' + id + '/events', {
    method: 'POST', headers: worker,
    body: JSON.stringify({ event_type: 'result', summary: 'Result ready', result: { ok: true } })
  });
  assert.equal((await result.json()).task.status, 'awaiting_validation');
  const monitoring = await (await fetch(base + '/monitoring/workers', { headers: admin })).json();
  assert.equal(monitoring.workers.length, 0);
});


test('worker cannot mutate a result after it enters independent validation', async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'jarvis-validation-guard-'));
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
  const created = await (await fetch(base + '/tasks', {
    method: 'POST', headers: admin, body: JSON.stringify({ goal: 'Protect validation boundary' })
  })).json();
  const id = created.task.task_id;
  assert.equal((await fetch(base + '/tasks/' + id + '/accept', {
    method: 'POST', headers: worker, body: '{}'
  })).status, 200);

  const firstResult = { verdict: 'original' };
  const submitted = await fetch(base + '/tasks/' + id + '/events', {
    method: 'POST', headers: worker,
    body: JSON.stringify({ event_type: 'result', summary: 'Original result', result: firstResult })
  });
  assert.equal(submitted.status, 201);

  const progressAfterResult = await fetch(base + '/tasks/' + id + '/events', {
    method: 'POST', headers: worker,
    body: JSON.stringify({ event_type: 'progress', summary: 'Try to reopen work', progress: 90 })
  });
  assert.equal(progressAfterResult.status, 409);

  const replacementResult = await fetch(base + '/tasks/' + id + '/events', {
    method: 'POST', headers: worker,
    body: JSON.stringify({ event_type: 'result', summary: 'Replacement result', result: { verdict: 'overwritten' } })
  });
  assert.equal(replacementResult.status, 409);

  const lateHeartbeat = await fetch(base + '/tasks/' + id + '/heartbeat', {
    method: 'POST', headers: worker, body: JSON.stringify({ summary: 'Still working' })
  });
  assert.equal(lateHeartbeat.status, 409);

  const adminHeartbeat = await fetch(base + '/tasks/' + id + '/heartbeat', {
    method: 'POST', headers: admin, body: JSON.stringify({})
  });
  assert.equal(adminHeartbeat.status, 409);

  const detail = await (await fetch(base + '/tasks/' + id, { headers: admin })).json();
  assert.equal(detail.task.status, 'awaiting_validation');
  assert.deepEqual(detail.task.result, firstResult);
  assert.equal(detail.events.filter((event) => event.event_type === 'result').length, 1);
});

test('admin monitoring marks an active task stale when its heartbeat expires', async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'jarvis-stale-heartbeat-'));
  const storePath = path.join(dir, 'runtime.json');
  const server = createServer({
    storePath,
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
  const created = await (await fetch(base + '/tasks', {
    method: 'POST', headers: admin, body: JSON.stringify({ goal: 'Detect a stale worker' })
  })).json();
  const id = created.task.task_id;
  await fetch(base + '/tasks/' + id + '/accept', { method: 'POST', headers: worker, body: '{}' });

  const store = JSON.parse(await fs.readFile(storePath, 'utf8'));
  store.tasks[id].last_heartbeat_at = new Date(Date.now() - 10 * 60 * 1000).toISOString();
  await fs.writeFile(storePath, JSON.stringify(store, null, 2));

  const response = await fetch(base + '/monitoring/workers', { headers: admin });
  assert.equal(response.status, 200);
  const monitoring = await response.json();
  assert.equal(monitoring.stale_count, 1);
  assert.equal(monitoring.workers[0].task_id, id);
  assert.equal(monitoring.workers[0].heartbeat_stale, true);
});
