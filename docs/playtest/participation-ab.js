#!/usr/bin/env node
// 「有没有攒分点」的参与度对照:每局里每台机器到底有没有碰上东西。
// 两个变体在同一进程里跑,但各自写出不同路径的模块文件 —— Node 对同一个路径只 require 一次,
// 第二次拿到的是第一次那份模块,直接用同一份代码改参数会读到同一组读数。
// 用法:node docs/playtest/participation-ab.js <有点原型> <无点变体> [批号,逗号分隔]
//   node docs/playtest/participation-ab.js prototypes/fuse-royale-prototype.html \
//     prototypes/fuse-royale-no-point.html 50,51,52,53,54
// 无点变体 prototypes/fuse-royale-no-point.html 在一次性分支 prototype/fuse-royale 上。
const fs = require('fs');
const crypto = require('crypto');
const 路径A = process.argv[2] || 'prototypes/fuse-royale-prototype.html';
const 路径B = process.argv[3] || '/tmp/jarvis-patch/nopoint.html';
const 批号 = process.argv[4] ? process.argv[4].split(',').map(Number) : [50, 51, 52, 53, 54];

function 造模块(源) {
  const html = fs.readFileSync(源, 'utf8');
  const i = html.indexOf('const FUSE = (() => {'), j = html.indexOf('\n})();', i);
  if (i < 0 || j < 0) { console.error('没在 ' + 源 + ' 里找到逻辑模块'); process.exit(1); }
  const 目标 = `/tmp/jarvis-ab-module-${crypto.createHash('md5').update(源).digest('hex')}.js`;
  fs.writeFileSync(目标, html.slice(i, j + 6) + '\nmodule.exports = FUSE;\n');
  return require(目标);
}
function mul(s) { return function () { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; }; }

function 跑(F, 标签) {
  const N = F.PRESET_NAMES.length;
  let 局 = 0, 机器数 = 0, 零分 = 0, 零杀 = 0, 零站 = 0, 局长和 = 0, 淘汰和 = 0, 站点和 = 0;
  const 局长列 = [], 每台杀 = [];
  for (const 批 of 批号) {
    for (let r = 0; r < 400; r++) {
      const rnd = mul((批 * 1000 + r) * 7919 + 13), idx = [...Array(N).keys()];
      for (let k = N - 1; k > 0; k--) { const m = Math.floor(rnd() * (k + 1)); [idx[k], idx[m]] = [idx[m], idx[k]]; }
      const pick = []; for (let x = 0; x < 10; x++) pick.push(idx[x % N]);
      const mt = F.newMatch(F.preset(pick[0]), pick.slice(1).map(F.preset), (批 * 1000 + r) * 17 + 3, 0, 2);
      mt.机器[0].名称 = F.PRESET_NAMES[pick[0]];
      const 站过 = new Set();
      // runAll 没有逐步回调这个口子,所以照着它自己跑,每跳记一次谁在点里
      let n = 0;
      while (!mt.结束 && n < 420) {
        F.step(mt); F.burnTick(mt); n++;
        for (const x of mt.机器) if (x.活 && Math.hypot(x.x - mt.点[0], x.y - mt.点[1]) <= F.点位半径) 站过.add(x);
      }
      局++; 局长和 += mt.tick / 10; 局长列.push(mt.tick / 10); 淘汰和 += mt.淘汰顺序.length; 站点和 += 站过.size;
      for (const x of mt.机器) {
        机器数++; 每台杀.push(x.击杀);
        if (x.分杀 + x.分点 === 0) 零分++;
        if (x.击杀 === 0) 零杀++;
        if (!站过.has(x)) 零站++;
      }
    }
  }
  局长列.sort((a, b) => a - b);
  return { 标签, 局, 机器数, 局长: (局长和 / 局).toFixed(1), 局长中位: 局长列[Math.floor(局 / 2)].toFixed(1),
    局长P90: 局长列[Math.floor(局 * 0.9)].toFixed(1), 淘汰: (淘汰和 / 局).toFixed(1),
    站点中位: (站点和 / 局).toFixed(1), 零分: (零分 / 机器数 * 100).toFixed(0),
    零杀: (零杀 / 机器数 * 100).toFixed(0), 零站: (零站 / 机器数 * 100).toFixed(0),
    打掉过一台: (每台杀.filter(v => v > 0).length / 机器数 * 100).toFixed(0) };
}

const A = 跑(造模块(路径A));
const B = 跑(造模块(路径B));
const 行名 = { 局: '局数', 机器数: '机器总数', 局长: '平均局长(秒)', 局长中位: '局长中位(秒)', 局长P90: '局长 P90(秒)',
  淘汰: '每局淘汰台数', 站点中位: '每局站进过点的台数', 零分: '整局一分没拿到的机器 %',
  零杀: '整局没打掉任何一台的机器 %', 零站: '整局没站进过点的机器 %', 打掉过一台: '打掉过至少一台的机器 %' };
console.log(`批号 ${批号.join('~')} | A=${路径A} | B=${路径B}`);
for (const k in 行名) console.log(`  ${行名[k].padEnd(24)} A ${String(A[k]).padStart(6)} | B ${String(B[k]).padStart(6)}`);
