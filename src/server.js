'use strict';

const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const { randomUUID, timingSafeEqual } = require('node:crypto');

const TASK_STATES = new Set([
  'queued', 'accepted', 'running', 'blocked', 'failed',
  'awaiting_validation', 'awaiting_approval', 'succeeded', 'cancelled'
]);
const TERMINAL_STATES = new Set(['succeeded', 'cancelled']);
const EVENT_TYPES = new Set(['progress', 'result', 'blocked', 'failed']);
const MAX_BODY_BYTES = 1024 * 1024;

function httpError(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function json(res, status, value) {
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store'
  });
  res.end(JSON.stringify(value));
}

async function readJson(req) {
  let raw = '';
  for await (const chunk of req) {
    raw += chunk;
    if (Buffer.byteLength(raw) > MAX_BODY_BYTES) throw httpError(413, 'Request body exceeds 1 MiB');
  }
  if (!raw.trim()) return {};
  try {
    return JSON.parse(raw);
  } catch {
    throw httpError(400, 'Request body must be valid JSON');
  }
}

function validateText(value, name, max = 5000) {
  if (typeof value !== 'string' || !value.trim()) throw httpError(400, name + ' must be a non-empty string');
  if (value.length > max) throw httpError(400, name + ' is too long');
  return value.trim();
}

function safeTokenMatch(candidate, expected) {
  if (typeof candidate !== 'string' || typeof expected !== 'string' || !expected) return false;
  const a = Buffer.from(candidate);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

function authenticate(req, auth) {
  if (!auth.adminToken && !auth.workerToken) throw httpError(503, 'Authentication is not configured; set server-side tokens before using the API');
  const header = req.headers.authorization || '';
  const match = header.match(/^Bearer\s+(.+)$/i);
  if (!match) throw httpError(401, 'Bearer token required');
  const token = match[1];
  if (safeTokenMatch(token, auth.adminToken)) return { role: 'admin', id: 'admin' };
  if (safeTokenMatch(token, auth.workerToken)) return { role: 'worker', id: auth.workerId };
  throw httpError(401, 'Invalid bearer token');
}

function createRuntimeStore(filePath) {
  let chain = Promise.resolve();

  async function ensureFile() {
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    try {
      await fs.access(filePath);
    } catch {
      await fs.writeFile(filePath, JSON.stringify({ tasks: {}, events: [] }, null, 2), { mode: 0o600 });
    }
  }

  async function read() {
    await ensureFile();
    const data = JSON.parse(await fs.readFile(filePath, 'utf8'));
    if (!data || typeof data.tasks !== 'object' || !Array.isArray(data.events)) throw new Error('Store file has an invalid shape');
    return data;
  }

  function mutate(fn) {
    const operation = chain.then(async () => {
      const data = await read();
      const result = await fn(data);
      const tempPath = filePath + '.' + randomUUID() + '.tmp';
      await fs.writeFile(tempPath, JSON.stringify(data, null, 2), { mode: 0o600 });
      await fs.rename(tempPath, filePath);
      return result;
    });
    chain = operation.catch(() => {});
    return operation;
  }

  return {
    listTasks: () => chain.then(async () => Object.values((await read()).tasks)),
    getTask: (id) => chain.then(async () => (await read()).tasks[id] || null),
    listEvents: (id) => chain.then(async () => (await read()).events.filter((event) => event.task_id === id)),
    createTask: (input, actor) => mutate((data) => {
      const now = new Date().toISOString();
      const task = {
        task_id: randomUUID(),
        goal: validateText(input.goal, 'goal', 2000),
        instructions: typeof input.instructions === 'string' ? input.instructions.slice(0, 10000) : '',
        worker_type: typeof input.worker_type === 'string' && input.worker_type.trim() ? input.worker_type.trim() : 'general',
        priority: ['low', 'normal', 'high', 'urgent'].includes(input.priority) ? input.priority : 'normal',
        status: 'queued',
        created_at: now,
        updated_at: now,
        created_by: actor.id,
        deadline_at: typeof input.deadline_at === 'string' ? input.deadline_at : null,
        input_refs: Array.isArray(input.input_refs) ? input.input_refs : [],
        constraints: input.constraints && typeof input.constraints === 'object' && !Array.isArray(input.constraints) ? input.constraints : {},
        approval_required: input.approval_required === true,
        attempt: 0,
        max_attempts: Number.isInteger(input.max_attempts) ? Math.min(10, Math.max(1, input.max_attempts)) : 3,
        worker_id: null,
        last_heartbeat_at: null,
        result: null,
        blocker: null
      };
      data.tasks[task.task_id] = task;
      data.events.push({ event_id: randomUUID(), task_id: task.task_id, actor_id: actor.id, event_type: 'created', summary: 'Task added to queue', timestamp: now });
      return task;
    }),
    acceptTask: (id, workerId, actor) => mutate((data) => {
      const task = data.tasks[id];
      if (!task) throw httpError(404, 'Task not found');
      if (actor.role !== 'admin' && workerId !== actor.id) throw httpError(403, 'Worker can only accept tasks as its configured identity');
      if (!['queued', 'blocked'].includes(task.status)) throw httpError(409, 'Task cannot be accepted from status ' + task.status);
      const now = new Date().toISOString();
      task.status = 'accepted';
      task.worker_id = validateText(workerId, 'worker_id', 200);
      task.last_heartbeat_at = now;
      task.blocker = null;
      task.updated_at = now;
      data.events.push({ event_id: randomUUID(), task_id: id, actor_id: actor.id, worker_id: task.worker_id, event_type: 'accepted', summary: 'Worker accepted task', timestamp: now });
      return task;
    }),
    heartbeat: (id, input, actor) => mutate((data) => {
      const task = data.tasks[id];
      if (!task) throw httpError(404, 'Task not found');
      if (TERMINAL_STATES.has(task.status)) throw httpError(409, 'Task is already terminal');
      if (!task.worker_id) throw httpError(409, 'Task must be accepted before sending a heartbeat');
      if (actor.role === 'worker' && task.worker_id !== actor.id) throw httpError(403, 'Worker does not own this task');
      if (input.worker_id && input.worker_id !== task.worker_id) throw httpError(403, 'Worker does not own this task');
      const now = new Date().toISOString();
      task.last_heartbeat_at = now;
      if (task.status === 'accepted') task.status = 'running';
      task.updated_at = now;
      data.events.push({ event_id: randomUUID(), task_id: id, actor_id: actor.id, worker_id: task.worker_id, event_type: 'heartbeat', summary: typeof input.summary === 'string' ? input.summary.slice(0, 1000) : 'Worker heartbeat received', timestamp: now });
      return task;
    }),
    addEvent: (id, input, actor) => mutate((data) => {
      const task = data.tasks[id];
      if (!task) throw httpError(404, 'Task not found');
      if (TERMINAL_STATES.has(task.status)) throw httpError(409, 'Task is already terminal');
      const eventType = validateText(input.event_type, 'event_type', 40);
      if (!EVENT_TYPES.has(eventType)) throw httpError(400, 'event_type must be progress, result, blocked, or failed');
      if (!task.worker_id) throw httpError(409, 'Task must be accepted by a worker before reporting events');
      if (actor.role === 'worker' && task.worker_id !== actor.id) throw httpError(403, 'Worker does not own this task');
      if (input.worker_id && input.worker_id !== task.worker_id) throw httpError(403, 'Worker does not own this task');
      const now = new Date().toISOString();
      const event = {
        event_id: randomUUID(),
        task_id: id,
        actor_id: actor.id,
        worker_id: task.worker_id,
        event_type: eventType,
        summary: validateText(input.summary, 'summary', 5000),
        timestamp: now
      };
      if (input.progress !== undefined) {
        if (!Number.isFinite(input.progress) || input.progress < 0 || input.progress > 100) throw httpError(400, 'progress must be between 0 and 100');
        event.progress = input.progress;
      }
      if (input.artifacts !== undefined) event.artifacts = Array.isArray(input.artifacts) ? input.artifacts : [];
      if (input.evidence !== undefined) event.evidence = Array.isArray(input.evidence) ? input.evidence : [];
      if (input.next_action !== undefined) event.next_action = String(input.next_action).slice(0, 2000);
      if (eventType === 'blocked') {
        event.blocker = validateText(input.blocker || input.summary, 'blocker', 3000);
        task.status = 'blocked';
        task.blocker = event.blocker;
      } else if (eventType === 'failed') {
        task.status = 'failed';
      } else if (eventType === 'result') {
        if (input.result === undefined || input.result === null) throw httpError(400, 'result event requires a result payload');
        event.result = input.result;
        task.result = input.result;
        task.status = 'awaiting_validation';
      } else {
        task.status = 'running';
      }
      task.updated_at = now;
      data.events.push(event);
      return { task, event };
    }),
    validateTask: (id, input, actor) => mutate((data) => {
      const task = data.tasks[id];
      if (!task) throw httpError(404, 'Task not found');
      if (task.status !== 'awaiting_validation') throw httpError(409, 'Task is not awaiting validation');
      if (typeof input.validated !== 'boolean') throw httpError(400, 'validated must be a boolean');
      const summary = validateText(input.summary, 'summary', 3000);
      const evidence = Array.isArray(input.evidence) ? input.evidence.filter((item) => typeof item === 'string' && item.trim()).map((item) => item.trim()).slice(0, 50) : [];
      if (input.validated && evidence.length === 0) throw httpError(400, 'A successful validation requires at least one evidence reference');
      const now = new Date().toISOString();
      task.validation = { validated: input.validated, summary, evidence, validated_by: actor.id, validated_at: now };
      task.status = input.validated ? (task.approval_required ? 'awaiting_approval' : 'succeeded') : 'blocked';
      task.blocker = input.validated ? null : summary;
      task.updated_at = now;
      data.events.push({
        event_id: randomUUID(), task_id: id, actor_id: actor.id, event_type: 'validation',
        validated: input.validated, summary, evidence, timestamp: now
      });
      return task;
    }),
    approveTask: (id, input, actor) => mutate((data) => {
      const task = data.tasks[id];
      if (!task) throw httpError(404, 'Task not found');
      if (task.status !== 'awaiting_approval') throw httpError(409, 'Task is not awaiting approval');
      if (typeof input.approved !== 'boolean') throw httpError(400, 'approved must be a boolean');
      const now = new Date().toISOString();
      task.status = input.approved ? 'succeeded' : 'blocked';
      task.blocker = input.approved ? null : (typeof input.reason === 'string' ? input.reason.slice(0, 3000) : 'Human approval rejected');
      task.updated_at = now;
      data.events.push({
        event_id: randomUUID(), task_id: id, actor_id: actor.id, event_type: 'approval',
        approved: input.approved, summary: input.approved ? 'Human approval granted' : 'Human approval rejected',
        reason: typeof input.reason === 'string' ? input.reason.slice(0, 3000) : null,
        timestamp: now
      });
      return task;
    }),
    retryTask: (id, actor) => mutate((data) => {
      const task = data.tasks[id];
      if (!task) throw httpError(404, 'Task not found');
      if (!['failed', 'blocked'].includes(task.status)) throw httpError(409, 'Only failed or blocked tasks can be retried');
      if (task.attempt >= task.max_attempts) throw httpError(409, 'Maximum attempts reached');
      const now = new Date().toISOString();
      task.attempt += 1;
      task.status = 'queued';
      task.worker_id = null;
      task.blocker = null;
      task.updated_at = now;
      data.events.push({ event_id: randomUUID(), task_id: id, actor_id: actor.id, event_type: 'retried', summary: 'Task requeued', attempt: task.attempt, timestamp: now });
      return task;
    })
  };
}

function createServer(options = {}) {
  const store = createRuntimeStore(options.storePath || process.env.JARVIS_STORE_PATH || path.join(process.cwd(), 'data', 'runtime.json'));
  const auth = {
    adminToken: options.adminToken ?? process.env.JARVIS_ADMIN_TOKEN,
    workerToken: options.workerToken ?? process.env.JARVIS_WORKER_TOKEN,
    workerId: options.workerId || process.env.JARVIS_WORKER_ID || 'worker-1'
  };

  return http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      const pathname = url.pathname.replace(/\/+$/, '') || '/';

      if (req.method === 'GET' && pathname === '/health') {
        return json(res, 200, { status: 'ok', service: 'jarvis-digital-employee-runtime', timestamp: new Date().toISOString() });
      }

      const actor = authenticate(req, auth);
      if (req.method === 'GET' && pathname === '/tasks') {
        const tasks = await store.listTasks();
        return json(res, 200, { tasks: actor.role === 'admin' ? tasks : tasks.filter((task) => task.status === 'queued' || task.worker_id === actor.id) });
      }
      if (req.method === 'GET' && pathname === '/monitoring/workers') {
        if (actor.role !== 'admin') throw httpError(403, 'Admin role required');
        const timeoutMs = Math.max(5000, Number(process.env.JARVIS_HEARTBEAT_TIMEOUT_MS) || 60000);
        const tasks = (await store.listTasks()).filter((task) => task.worker_id && ['accepted', 'running'].includes(task.status));
        const now = Date.now();
        const workers = tasks.map((task) => {
          const last = task.last_heartbeat_at ? Date.parse(task.last_heartbeat_at) : NaN;
          return { task_id: task.task_id, goal: task.goal, worker_id: task.worker_id, status: task.status, last_heartbeat_at: task.last_heartbeat_at || null, heartbeat_stale: !Number.isFinite(last) || now - last > timeoutMs, heartbeat_timeout_ms: timeoutMs, blocker: task.blocker };
        });
        return json(res, 200, { workers, stale_count: workers.filter((worker) => worker.heartbeat_stale).length, timestamp: new Date().toISOString() });
      }
      if (req.method === 'POST' && pathname === '/tasks') {
        if (actor.role !== 'admin') throw httpError(403, 'Admin role required');
        const body = await readJson(req);
        const task = await store.createTask(body, actor);
        return json(res, 201, { task });
      }

      const taskRoute = pathname.match(/^\/tasks\/([^/]+)(?:\/(accept|heartbeat|events|validate|approve|retry))?$/);
      if (taskRoute) {
        const id = decodeURIComponent(taskRoute[1]);
        const action = taskRoute[2] || '';
        if (req.method === 'GET' && !action) {
          const task = await store.getTask(id);
          if (!task) throw httpError(404, 'Task not found');
          if (actor.role === 'worker' && task.status !== 'queued' && task.worker_id !== actor.id) throw httpError(403, 'Worker may only inspect queued or assigned tasks');
          return json(res, 200, { task, events: await store.listEvents(id) });
        }
        if (req.method === 'POST' && action === 'accept') {
          const body = await readJson(req);
          return json(res, 200, { task: await store.acceptTask(id, body.worker_id || actor.id, actor) });
        }
        if (req.method === 'POST' && action === 'heartbeat') {
          const body = await readJson(req);
          return json(res, 200, { task: await store.heartbeat(id, body, actor) });
        }
        if (req.method === 'POST' && action === 'events') {
          const body = await readJson(req);
          const result = await store.addEvent(id, body, actor);
          return json(res, 201, result);
        }
        if (req.method === 'POST' && action === 'validate') {
          if (actor.role !== 'admin') throw httpError(403, 'Admin role required');
          const body = await readJson(req);
          return json(res, 200, { task: await store.validateTask(id, body, actor) });
        }
        if (req.method === 'POST' && action === 'approve') {
          if (actor.role !== 'admin') throw httpError(403, 'Admin role required');
          const body = await readJson(req);
          return json(res, 200, { task: await store.approveTask(id, body, actor) });
        }
        if (req.method === 'POST' && action === 'retry') {
          if (actor.role !== 'admin') throw httpError(403, 'Admin role required');
          return json(res, 200, { task: await store.retryTask(id, actor) });
        }
      }
      return json(res, 404, { error: 'Route not found' });
    } catch (error) {
      const status = Number.isInteger(error.status) ? error.status : 500;
      if (status >= 500) console.error(error);
      return json(res, status, { error: status >= 500 ? 'Internal server error' : error.message });
    }
  });
}

if (require.main === module) {
  const port = Number(process.env.PORT) || 10000;
  const host = process.env.HOST || '0.0.0.0';
  const server = createServer();
  server.listen(port, host, () => console.log('JARVIS runtime listening on ' + host + ':' + port));
  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => server.close(() => process.exit(0)));
  }
}

module.exports = { createServer, TASK_STATES };
