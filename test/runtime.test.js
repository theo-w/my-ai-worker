'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { createServer } = require('../src/server');

async function setup(t) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'jarvis-runtime-'));
  const server = createServer({ storePath: path.join(dir, 'runtime.json'), adminToken: 'test-admin-secret', workerToken: 'test-worker-secret', workerId: 'worker-1' });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;
  t.after(async () => {
    await new Promise((resolve) => server.close(resolve));
    await fs.rm(dir, { recursive: true, force: true });
  });
  async function request(route, method = 'GET', body, token = 'test-admin-secret') {
    const response = await fetch(base + route, {
      method,
      headers: { ...(body === undefined ? {} : { 'content-type': 'application/json' }), ...(token ? { authorization: 'Bearer ' + token } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    return { status: response.status, body: await response.json() };
  }
  return { request };
}

test('health endpoint is public for deployment probes', async (t) => {
  const { request } = await setup(t);
  const response = await request('/health', 'GET', undefined, null);
  assert.equal(response.status, 200);
});

test('task can be created, accepted, progressed, and completed', async (t) => {
  const { request } = await setup(t);
  const created = await request('/tasks', 'POST', { goal: 'Assess AI-native game feasibility' });
  assert.equal(created.status, 201);
  const id = created.body.task.task_id;
  assert.equal((await request('/tasks/' + id + '/accept', 'POST', {}, 'test-worker-secret')).body.task.status, 'accepted');
  assert.equal((await request('/tasks/' + id + '/events', 'POST', { event_type: 'progress', summary: 'Researching', progress: 40 }, 'test-worker-secret')).body.task.status, 'running');
  const result = await request('/tasks/' + id + '/events', 'POST', { event_type: 'result', summary: 'Done', result: { verdict: 'promising' }, evidence: ['research notes'] }, 'test-worker-secret');
  assert.equal(result.body.task.status, 'awaiting_validation');
  assert.equal((await request('/tasks/' + id + '/validate', 'POST', { validated: true, summary: 'Acceptance criteria checked', evidence: ['test://acceptance-check-1'] })).body.task.status, 'succeeded');
  const detail = await request('/tasks/' + id);
  assert.equal(detail.body.events.length, 5);
  assert.ok(detail.body.events.some((event) => event.event_type === 'validation'));
});

test('approval-required task needs explicit admin approval', async (t) => {
  const { request } = await setup(t);
  const created = await request('/tasks', 'POST', { goal: 'Prepare announcement', approval_required: true });
  const id = created.body.task.task_id;
  await request('/tasks/' + id + '/accept', 'POST', {}, 'test-worker-secret');
  const result = await request('/tasks/' + id + '/events', 'POST', { event_type: 'result', summary: 'Draft ready', result: { draft: 'Review me' } }, 'test-worker-secret');
  assert.equal(result.body.task.status, 'awaiting_validation');
  assert.equal((await request('/tasks/' + id + '/validate', 'POST', { validated: true, summary: 'Draft reviewed', evidence: ['test://draft-review'] }, 'test-worker-secret')).status, 403);
  assert.equal((await request('/tasks/' + id + '/validate', 'POST', { validated: true, summary: 'Draft reviewed', evidence: ['test://draft-review'] })).body.task.status, 'awaiting_approval');
  assert.equal((await request('/tasks/' + id + '/approve', 'POST', { approved: true }, 'test-worker-secret')).status, 403);
  assert.equal((await request('/tasks/' + id + '/approve', 'POST', { approved: true })).body.task.status, 'succeeded');
});


test('result cannot succeed without admin validation and validation requires evidence', async (t) => {
  const { request } = await setup(t);
  const created = await request('/tasks', 'POST', { goal: 'Verify a claim' });
  const id = created.body.task.task_id;
  await request('/tasks/' + id + '/accept', 'POST', {}, 'test-worker-secret');
  const result = await request('/tasks/' + id + '/events', 'POST', { event_type: 'result', summary: 'Claim drafted', result: { claim: 'works' } }, 'test-worker-secret');
  assert.equal(result.body.task.status, 'awaiting_validation');
  assert.equal((await request('/tasks/' + id + '/validate', 'POST', { validated: true, summary: 'No evidence supplied', evidence: [] })).status, 400);
  assert.equal((await request('/tasks/' + id + '/validate', 'POST', { validated: true, summary: 'Worker self-approval', evidence: ['test://evidence'] }, 'test-worker-secret')).status, 403);
  const rejected = await request('/tasks/' + id + '/validate', 'POST', { validated: false, summary: 'Evidence does not support claim', evidence: ['test://contradicting-evidence'] });
  assert.equal(rejected.body.task.status, 'blocked');
});

test('blocked task retries only within attempt limit', async (t) => {
  const { request } = await setup(t);
  const created = await request('/tasks', 'POST', { goal: 'Collect test data', max_attempts: 1 });
  const id = created.body.task.task_id;
  await request('/tasks/' + id + '/accept', 'POST', {}, 'test-worker-secret');
  assert.equal((await request('/tasks/' + id + '/events', 'POST', { event_type: 'blocked', summary: 'Dataset unavailable', blocker: 'Need access' }, 'test-worker-secret')).body.task.status, 'blocked');
  assert.equal((await request('/tasks/' + id + '/retry', 'POST')).body.task.status, 'queued');
  await request('/tasks/' + id + '/accept', 'POST', {}, 'test-worker-secret');
  await request('/tasks/' + id + '/events', 'POST', { event_type: 'failed', summary: 'Still unavailable' }, 'test-worker-secret');
  assert.equal((await request('/tasks/' + id + '/retry', 'POST')).status, 409);
});

test('missing and invalid credentials are rejected', async (t) => {
  const { request } = await setup(t);
  assert.equal((await request('/tasks', 'GET', undefined, null)).status, 401);
  assert.equal((await request('/tasks', 'GET', undefined, 'wrong-secret')).status, 401);
});

test('worker cannot create tasks, impersonate another worker, or approve', async (t) => {
  const { request } = await setup(t);
  assert.equal((await request('/tasks', 'POST', { goal: 'forbidden' }, 'test-worker-secret')).status, 403);
  const created = await request('/tasks', 'POST', { goal: 'Run QA', approval_required: true });
  const id = created.body.task.task_id;
  assert.equal((await request('/tasks/' + id + '/accept', 'POST', { worker_id: 'other-worker' }, 'test-worker-secret')).status, 403);
  await request('/tasks/' + id + '/accept', 'POST', {}, 'test-worker-secret');
  await request('/tasks/' + id + '/events', 'POST', { event_type: 'result', summary: 'Result ready', result: { ok: true } }, 'test-worker-secret');
  assert.equal((await request('/tasks/' + id + '/approve', 'POST', { approved: true }, 'test-worker-secret')).status, 403);
});

test('server fails closed when no tokens are configured', async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'jarvis-no-auth-'));
  const server = createServer({ storePath: path.join(dir, 'runtime.json'), adminToken: '', workerToken: '' });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const response = await fetch('http://127.0.0.1:' + server.address().port + '/tasks');
  assert.equal(response.status, 503);
  await new Promise((resolve) => server.close(resolve));
  await fs.rm(dir, { recursive: true, force: true });
});
