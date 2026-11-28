// 描述性探针:一局里到底有几台机器真的站进过余料点、拿到的余料都带来什么。
// 不测平衡,只测「第二条赢法有多少人体验到」。逻辑模块直接从原型页面里切出来,保证和页面用的是同一份代码。
// 用法:node docs/playtest/loot-point-probe.js [原型html路径]
// 原型页面在一次性分支 prototype/fuse-royale 上;本地有 prototypes/ 时直接跑即可。
const fs = require('fs');
const path = process.argv[2] || 'prototypes/fuse-royale-prototype.html';
const html = fs.readFileSync(path, 'utf8');
const i = html.indexOf('const FUSE = (() => {');
const j = html.indexOf('\n})();', i);
if (i < 0 || j < 0) {
  console.error('没在 ' + path + ' 里找到逻辑模块(它在 prototype/fuse-royale 分支上)');
  process.exit(1);
}
const tmp = '/tmp/jarvis-loot-probe-module.js';
fs.writeFileSync(tmp, html.slice(i, j + 6) + '\nmodule.exports = FUSE;\n');
const F = require(tmp);

const N = F.PRESET_NAMES.length;
const 局数 = 300, 批号 = 700;   // 种子放在 700 段,与所有调参和额度读数不重叠
function mul(s) { return function () { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; }; }

let 局 = 0, 总台 = 0, 进过点的台 = 0, 进点秒合计 = 0, 有分台 = 0, 占点胜 = 0, 换点合计 = 0, 从未靠近 = 0;
const 每局进过点台数 = [];
for (let r = 0; r < 局数; r++) {
  const rnd = mul((批号 * 1000 + r) * 7919 + 13), idx = [...Array(N).keys()];
  for (let k = N - 1; k > 0; k--) { const m = Math.floor(rnd() * (k + 1)); [idx[k], idx[m]] = [idx[m], idx[k]]; }
  const pick = []; for (let x = 0; x < 10; x++) pick.push(idx[x % N]);
  const mt = F.newMatch(F.preset(pick[0]), pick.slice(1).map(F.preset), (批号 * 1000 + r) * 17 + 3, 0, 2);
  mt.机器[0].名称 = F.PRESET_NAMES[pick[0]];
  局++;
  const 进点秒 = mt.机器.map(() => 0), 最近 = mt.机器.map(() => 1e9);
  let 换点 = 0, 上个点 = JSON.stringify(mt.点);
  while (!mt.结束 && mt.tick < 420) {
    F.step(mt); F.burnTick(mt);
    const 现点 = JSON.stringify(mt.点);
    if (现点 !== 上个点) { 换点++; 上个点 = 现点; }
    for (let k = 0; k < mt.机器.length; k++) {
      const b = mt.机器[k]; if (!b.活) continue;
      const d = Math.hypot(b.x - mt.点[0], b.y - mt.点[1]);
      if (d <= F.点位半径) 进点秒[k] += 0.1;
      if (d < 最近[k]) 最近[k] = d;
    }
  }
  换点合计 += 换点;
  let 本局进过 = 0;
  for (let k = 0; k < mt.机器.length; k++) {
    总台++; 进点秒合计 += 进点秒[k];
    if (进点秒[k] > 0) { 进过点的台++; 本局进过++; }
    if (mt.机器[k].分数 > 0) 有分台++;
    if (最近[k] > F.点位半径 + 120) 从未靠近++;
  }
  每局进过点台数.push(本局进过);
  if (/攒满/.test(mt.胜因)) 占点胜++;
}
每局进过点台数.sort((a, b) => a - b);
console.log('逻辑模块来自 ' + path);
console.log('局数 ' + 局 + ' | 每局 10 台 | 批号 ' + 批号);
console.log('每局"站进过点"的台数:中位 ' + 每局进过点台数[Math.floor(局数 / 2)] + ' 台 | 最少 ' +
  每局进过点台数[0] + ' 台 | 最多 ' + 每局进过点台数[局数 - 1] + ' 台');
console.log('整局没站进过点的机器占比 ' + Math.round((1 - 进过点的台 / 总台) * 100) + '%(按台算,共 ' + 总台 + ' 台)');
console.log('连靠近(点位半径 ' + F.点位半径 + ' 外加 120)都没有过的机器占比 ' + Math.round(从未靠近 / 总台 * 100) + '%');
console.log('每台平均站进点的时长 ' + (进点秒合计 / 总台).toFixed(1) + ' 秒');
console.log('攒到过分(>0)的机器占比 ' + Math.round(有分台 / 总台 * 100) + '% | 靠占点赢的局占比 ' +
  Math.round(占点胜 / 局 * 100) + '%');
console.log('一局内余料点平均换位置 ' + (换点合计 / 局).toFixed(2) + ' 次(周期 ' + F.点移动周期 / 10 + ' 秒)');
