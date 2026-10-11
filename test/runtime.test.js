'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { createServer } = require('../src/server');

async function setup(t) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'jarvis-runtime-'));
  const server = createServer({ storePath: path.join(dir, 'runtime.json') });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;
  t.after(async () => {
    await new Promise((resolve) => server.close(resolve));
    await fs.rm(dir, { recursive: true, force: true });
  });
  async function request(route, method = 'GET', body) {
    const response = await fetch(base + route, {
      method,
      headers: body === undefined ? {} : { 'content-type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    return { status: response.status, body: await response.json() };
  }
  return { request, dir };
}

test('health endpoint reports healthy runtime', async (t) => {
  const { request } = await setup(t);
  const response = await request('/health');
  assert.equal(response.status, 200);
  assert.equal(response.body.status, 'ok');
});

test('task can be created, accepted, progressed, and completed with evidence', async (t) => {
  const { request } = await setup(t);
  const created = await request('/tasks', 'POST', { goal: 'Assess AI-native game feasibility', worker_type: 'research' });
  assert.equal(created.status, 201);
  const id = created.body.task.task_id;
  assert.equal(created.body.task.status, 'queued');

  assert.equal((await request('/tasks/' + id + '/accept', 'POST', { worker_id: 'researcher-1' })).body.task.status, 'accepted');
  assert.equal((await request('/tasks/' + id + '/events', 'POST', {
    event_type: 'progress', summary: 'Reviewing market and technical constraints', progress: 40
  })).body.task.status, 'running');

  const completed = await request('/tasks/' + id + '/events', 'POST', {
    event_type: 'result', summary: 'Assessment complete', result: { verdict: 'promising' },
    artifacts: ['reports/feasibility.md'], evidence: ['market research notes']
  });
  assert.equal(completed.status, 201);
  assert.equal(completed.body.task.status, 'succeeded');
  const detail = await request('/tasks/' + id);
  assert.equal(detail.body.events.length, 4);
});

test('approval-required task cannot succeed before explicit approval', async (t) => {
  const { request } = await setup(t);
  const created = await request('/tasks', 'POST', { goal: 'Prepare external announcement', approval_required: true });
  const id = created.body.task.task_id;
  await request('/tasks/' + id + '/accept', 'POST', { worker_id: 'comms-1' });
  const result = await request('/tasks/' + id + '/events', 'POST', {
    event_type: 'result', summary: 'Draft prepared', result: { draft: 'Ready for review' }
  });
  assert.equal(result.body.task.status, 'awaiting_approval');
  const approved = await request('/tasks/' + id + '/approve', 'POST', { approved: true });
  assert.equal(approved.body.task.status, 'succeeded');
});

test('blocked task can be retried only within attempt limit', async (t) => {
  const { request } = await setup(t);
  const created = await request('/tasks', 'POST', { goal: 'Collect test data', max_attempts: 1 });
  const id = created.body.task.task_id;
  await request('/tasks/' + id + '/accept', 'POST', { worker_id: 'qa-1' });
  const blocked = await request('/tasks/' + id + '/events', 'POST', {
    event_type: 'blocked', summary: 'Dataset access unavailable', blocker: 'Need data access'
  });
  assert.equal(blocked.body.task.status, 'blocked');
  assert.equal((await request('/tasks/' + id + '/retry', 'POST')).body.task.status, 'queued');
  await request('/tasks/' + id + '/accept', 'POST', { worker_id: 'qa-1' });
  await request('/tasks/' + id + '/events', 'POST', { event_type: 'failed', summary: 'Still unavailable' });
  const exhausted = await request('/tasks/' + id + '/retry', 'POST');
  assert.equal(exhausted.status, 409);
});

test('worker ownership is enforced and invalid progress is rejected', async (t) => {
  const { request } = await setup(t);
  const created = await request('/tasks', 'POST', { goal: 'Run QA' });
  const id = created.body.task.task_id;
  await request('/tasks/' + id + '/accept', 'POST', { worker_id: 'qa-1' });
  assert.equal((await request('/tasks/' + id + '/events', 'POST', {
    event_type: 'progress', summary: 'wrong worker', worker_id: 'qa-2', progress: 20
  })).status, 403);
  assert.equal((await request('/tasks/' + id + '/events', 'POST', {
    event_type: 'progress', summary: 'invalid progress', progress: 140
  })).status, 400);
});
