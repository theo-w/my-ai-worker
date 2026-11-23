const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");
const assert = require("node:assert/strict");

test("dashboard inline JavaScript parses and includes the JARVIS start handler", () => {
  const htmlPath = path.join(__dirname, "..", "mvp", "dashboard.html");
  const html = fs.readFileSync(htmlPath, "utf8");
  const match = html.match(/<script\b[^>]*>([\s\S]*?)<\/script>/i);

  assert.ok(match, "dashboard must contain an inline script");
  assert.match(html, /<button\b[^>]*id="run"[^>]*>\s*启动 JARVIS\s*<\/button>/,
    "dashboard must contain the JARVIS start button");
  assert.match(match[1], /document\.getElementById\(["']run["']\)\.onclick\s*=/,
    "start button must have a click handler");

  assert.doesNotThrow(() => new vm.Script(match[1], { filename: "mvp/dashboard.html inline script" }),
    "dashboard inline JavaScript must parse without syntax errors");
});
