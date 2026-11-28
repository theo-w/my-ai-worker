#!/usr/bin/env node
// 赢家口径修好以后的基线读数:额度版、每局 10 台、5 批不重叠种子各 400 局共 2000 局。
// 修的是两处口径错误:冠军原先按全场分数排(出局机器也能被判赢,2000 局里 19.6%),
// 而且局判完以后灼烧还会把冠军烧死;名次也有 off-by-one(第一台出局的算第 9 名)。
// 用法:node docs/playtest/winner-rule-baseline.js [原型html路径]   # 想对照旧版本就传旧文件
// 原型页面在一次性分支 prototype/fuse-royale 上;本地有 prototypes/ 时直接跑即可。
// 复现要求:每次随机数都走每局固定种子,批号 50~54 与所有调参和探针不重叠;连跑两遍逐字相同。
const fs = require('fs');
const path = process.argv[2] || 'prototypes/fuse-royale-prototype.html';
const html = fs.readFileSync(path, 'utf8');
const i = html.indexOf('const FUSE = (() => {');
const j = html.indexOf('\n})();', i);
if (i < 0 || j < 0) { console.error('没在 ' + path + ' 里找到逻辑模块'); process.exit(1); }
const tmp = '/tmp/jarvis-winner-baseline-module.js';
fs.writeFileSync(tmp, html.slice(i, j + 6) + '\nmodule.exports = FUSE;\n');
const F = require(tmp);

function mul(s) { return function () { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; }; }
function wilson(k, n, z) {
  z = z || 1.96; if (!n) return [0, 0];
  const p = k / n, d = 1 + z * z / n;
  const c = (p + z * z / (2 * n)) / d;
  const h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d;
  return [c - h, c + h];
}

const N = F.PRESET_NAMES.length;
const 批号 = [50, 51, 52, 53, 54], 每批 = 400;
const 上场 = {}, 夺冠 = {}, 批内最高 = [];
let 局 = 0, 占点胜 = 0, 站着胜 = 0, 同归于尽 = 0, 死人冠军 = 0, 局长和 = 0, 淘汰和 = 0;
const 每批占点 = [];

for (const 批 of 批号) {
  let 本批局 = 0, 本批占点 = 0, 本批最高 = 0;
  const 本批夺冠 = {};
  for (let r = 0; r < 每批; r++) {
    const rnd = mul((批 * 1000 + r) * 7919 + 13), idx = [...Array(N).keys()];
    for (let k = N - 1; k > 0; k--) { const m = Math.floor(rnd() * (k + 1)); [idx[k], idx[m]] = [idx[m], idx[k]]; }
    const pick = []; for (let x = 0; x < 10; x++) pick.push(idx[x % N]);
    const mt = F.newMatch(F.preset(pick[0]), pick.slice(1).map(F.preset), (批 * 1000 + r) * 17 + 3, 0, 2);
    mt.机器[0].名称 = F.PRESET_NAMES[pick[0]];
    F.runAll(mt, 420);
    本批局++; 局++; 局长和 += mt.tick / 10; 淘汰和 += mt.淘汰顺序.length;
    for (const x of mt.机器) 上场[x.名称] = (上场[x.名称] || 0) + 1;   // 按机器真名统计:9 个预设进 10 台,必有一个预设这一局出现两台
    const 活 = mt.机器.filter(x => x.活);
    if (mt.冠军 === "无人存活") 同归于尽++;
    else if (!活.find(x => x.名称 === mt.冠军)) 死人冠军++;
    if (mt.胜因.includes('攒满')) { 占点胜++; 本批占点++; }
    else if (!mt.胜因.includes('同归于尽')) 站着胜++;
    if (mt.冠军 !== "无人存活") {
      夺冠[mt.冠军] = (夺冠[mt.冠军] || 0) + 1;
      本批夺冠[mt.冠军] = (本批夺冠[mt.冠军] || 0) + 1;
    }
  }
  每批占点.push((本批占点 / 本批局 * 100).toFixed(0) + '%');
  for (const nm in 本批夺冠) 本批最高 = Math.max(本批最高, 本批夺冠[nm] / 本批局 * 100);
  批内最高.push(本批最高.toFixed(1) + '%');
}

const 行 = Object.keys(上场).map(nm => ({ 名: nm, 台: 上场[nm], 赢: 夺冠[nm] || 0, 率: (夺冠[nm] || 0) / 上场[nm] }))
  .sort((a, b) => b.率 - a.率);
console.log(`文件:${path}`);
console.log(`2000 局(每局 10 台,种子批号 ${批号.join('~')})| 平均局长 ${(局长和 / 局).toFixed(1)} 秒 | 每局平均淘汰 ${(淘汰和 / 局).toFixed(1)} 台`);
console.log(`靠攒满分赢 ${(占点胜 / 局 * 100).toFixed(0)}% | 靠场上只剩一台赢 ${(站着胜 / 局 * 100).toFixed(0)}% | 同归于尽 ${同归于尽} 局(${(同归于尽 / 局 * 100).toFixed(1)}%) | 冠军已出局 ${死人冠军} 局`);
console.log(`每个预设都赢过场:${行.every(r => r.赢 > 0) ? '是' : '否(赢过 0 场的:' + 行.filter(r => !r.赢).map(r => r.名).join(',') + ')'}`);
console.log('');
for (const r of 行) {
  const [lo, hi] = wilson(r.赢, r.台);
  console.log(`  ${r.名.padEnd(12)} 上场 ${r.台} 台 | 夺冠 ${r.赢} 次 | 每台胜率 ${(r.率 * 100).toFixed(1)}%(区间 ${(lo * 100).toFixed(1)}~${(hi * 100).toFixed(1)}%)`);
}
const 最强 = 行[0], 最弱 = 行[行.length - 1];
console.log('');
console.log(`最强 ${最强.名} ${(最强.率 * 100).toFixed(1)}%(公平基线 10%,即 ${(最强.率 / 0.1).toFixed(2)} 倍) | 最弱 ${最弱.名} ${(最弱.率 * 100).toFixed(1)}% | 差距 ${(最强.率 / 最弱.率).toFixed(2)} 倍`);
console.log(`批内最高胜率 ${批内最高.join(' / ')}(阈值 15%)| 批内占点赢 ${每批占点.join(' / ')}`);
