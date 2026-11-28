#!/usr/bin/env node
// 背面判定与搜尸这两条规则自己有没有被用上(补充轮十五)。
// 背击:占命中次数的比例、占伤害的比例、至少吃到一次背击的机器占比、哪些造法最容易露背后。
// 搜尸:掉了几堆零件、被捡走多少、捡了但额度超了焊不上多少、三秒到点没人来而消失多少、
//       至少焊上一个零件的机器占比(零件清单因此中途会变,所以造法身份要按名字统计)。
// 参与度照旧:整局一分没拿到 / 没打掉任何一台。
// 用法:node docs/playtest/back-loot-probe.js <原型html路径> [批号列表]
const fs = require('fs');
const path = process.argv[2] || 'prototypes/fuse-royale-prototype.html';
const html = fs.readFileSync(path, 'utf8');
const i = html.indexOf('const FUSE = (() => {');
const j = html.indexOf('\n})();', i);
if (i < 0 || j < 0) { console.error('没在 ' + path + ' 里找到逻辑模块'); process.exit(1); }
const crypto = require('crypto');
const tmp = '/tmp/jarvis-backloot-module-' + crypto.createHash('md5').update(html).digest('hex').slice(0, 10) + '.js';
fs.writeFileSync(tmp, html.slice(i, j + 6) + '\nmodule.exports = FUSE;\n');
const F = require(tmp);

function mul(s) { return function () { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; }; }
const 批号 = process.argv[3] ? process.argv[3].split(',').map(Number) : [50, 51, 52, 53, 54];
const N = F.PRESET_NAMES.length;
const 每批 = 400;
const c = { 局: 0, 机器: 0, 命中: 0, 背击: 0, 背击伤害: 0, 正面伤害: 0, 掉料: 0, 捡起: 0, 拒焊: 0, 过期: 0,
  吃到背击的机器: 0, 捡到过的机器: 0, 焊上的机器: 0, 零分: 0, 零杀: 0, 局长和: 0, 淘汰和: 0 };
const 按造法 = {};   // 名称 -> {局, 吃背击, 焊上, 捡到}

for (const 批 of 批号) {
  for (let r = 0; r < 每批; r++) {
    // 组局方式与 winner-rule-baseline.js 完全一致,这样两边的数能一对一对上
    const rnd = mul((批 * 1000 + r) * 7919 + 13), idx = [...Array(N).keys()];
    for (let k = N - 1; k > 0; k--) { const s2 = Math.floor(rnd() * (k + 1)); [idx[k], idx[s2]] = [idx[s2], idx[k]]; }
    const pick = []; for (let x = 0; x < 10; x++) pick.push(idx[x % N]);
    const m = F.newMatch(F.preset(pick[0]), pick.slice(1).map(F.preset), (批 * 1000 + r) * 17 + 3, 0, 2);
    F.runAll(m, 420);
    c.局++; c.命中 += m.统计.命中; c.背击 += m.统计.背击;
    c.背击伤害 += m.统计.背击伤害; c.正面伤害 += m.统计.正面伤害;
    c.掉料 += m.统计.掉料; c.捡起 += m.统计.捡起; c.拒焊 += m.统计.拒焊; c.过期 += m.统计.过期;
    c.局长和 += m.tick / 10; c.淘汰和 += m.淘汰顺序.length;
    for (const a of m.机器) {
      c.机器++;
      if (a.背击吃 > 0) c.吃到背击的机器++;
      if (a.搜到 > 0) c.捡到过的机器++;
      if (a.焊上 > 0) c.焊上的机器++;
      if (a.分杀 + a.分点 === 0) c.零分++;
      if (a.击杀 === 0) c.零杀++;
      const k = (按造法[a.名称] = 按造法[a.名称] || { 局: 0, 吃背击: 0, 焊上: 0, 捡到: 0, 零分: 0 });
      k.局++; k.吃背击 += a.背击吃; k.焊上 += a.焊上; k.捡到 += a.搜到;
      if (a.分杀 + a.分点 === 0) k.零分++;
    }
  }
}
const pct = (n, d) => (100 * n / d).toFixed(1) + '%';
const 没人来 = c.掉料 - c.捡起 - c.拒焊 - c.过期;
console.log('文件:' + path + '   批号:' + 批号.join(',') + '   ' + c.局 + ' 局 / ' + c.机器 + ' 台机器');
console.log('背击:命中 ' + c.命中 + ' 次,其中背面 ' + c.背击 + ' 次(' + pct(c.背击, c.命中) + ')');
console.log('伤害:背面 ' + c.背击伤害 + ' / 合计 ' + (c.背击伤害 + c.正面伤害) + '(' + pct(c.背击伤害, c.背击伤害 + c.正面伤害) + ')');
console.log('至少吃到一次背击的机器:' + pct(c.吃到背击的机器, c.机器));
console.log('搜尸:掉料 ' + c.掉料 + ' 堆 → 焊上 ' + c.捡起 + '(' + pct(c.捡起, c.掉料) + ')'
  + ' / 捡了但额度超了 ' + c.拒焊 + '(' + pct(c.拒焊, c.掉料) + ')'
  + ' / 三秒到点没人来 ' + c.过期 + '(' + pct(c.过期, c.掉料) + ')'
  + ' / 局结束时还在地上 ' + 没人来);
console.log('至少捡到过一次零件的机器:' + pct(c.捡到过的机器, c.机器) + '   至少焊上一个的:' + pct(c.焊上的机器, c.机器));
console.log('参与度:整局一分没拿到 ' + pct(c.零分, c.机器) + '   一台都没打掉 ' + pct(c.零杀, c.机器));
console.log('平均局长 ' + (c.局长和 / c.局).toFixed(1) + ' 秒   每局平均淘汰 ' + (c.淘汰和 / c.局).toFixed(1) + ' 台');
console.log('按造法(每台平均):吃背击 / 焊上零件 / 整局零分');
for (const n of Object.keys(按造法).sort((a, b) => 按造法[b].吃背击 / 按造法[b].局 - 按造法[a].吃背击 / 按造法[a].局)) {
  const k = 按造法[n];
  console.log('  ' + n + ':' + (k.吃背击 / k.局).toFixed(2) + ' / ' + (k.焊上 / k.局).toFixed(2) + ' / ' + pct(k.零分, k.局));
}
