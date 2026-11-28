#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真人试玩读数汇总:按 docs/jarvis-playtest-plan.md 的通过线/失败线逐条打印判定。
用法:python3 docs/playtest/tally.py docs/playtest/playtest-rows.csv
10 人样本只能判方向,不能判达标 —— 每条读数都带上 95% 波动区间。
"""
import csv
import sys

def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (c - h, c + h)

def pct(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k/n*100:.0f}%(区间 {lo*100:.0f}~{hi*100:.0f}%)"

def yes(rows, col):
    return sum(1 for r in rows if (r.get(col) or "").strip() == "是")

def count(rows, col, val):
    return sum(1 for r in rows if (r.get(col) or "").strip() == val)

def num(rows, col):
    out = []
    for r in rows:
        v = (r.get(col) or "").strip()
        if v:
            try: out.append(float(v))
            except ValueError: pass
    return out

def verdict(k, n, pass_at, fail_at):
    """按分数线判,不用绝对人数:目标样本 10 人,不足 10 人时只算方向。"""
    tag = "" if n >= 10 else "(样本不足,只算方向)"
    if n == 0: return "无数据"
    if k >= pass_at * n: return "通过" + tag
    if k <= fail_at * n: return "失败" + tag
    return "方向不明(小样本)"

def main(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    全部 = len(rows)
    rows = [r for r in rows if (r.get("有录像") or "是").strip() != "否"]
    n = len(rows)
    print(f"记录 {全部} 行,有录像的 {n} 行(没有录像的行不参与判定)")
    if n == 0:
        print("没有可用行。")
        return
    print(f"组别分布:A {count(rows,'组别','A')} 人 / B {count(rows,'组别','B')} 人"
          f"(两类各 5 人才测得到假设 4 那条入口)")
    if n < 10: print(f"注意:目标样本是 10 人,现在只有 {n} 人。下面每条判定都只算方向,不能当过关。")
    print()

    def line(假设, 读数, 通过线, 判定):
        print(f"{假设}\n  读数:{读数}\n  通过线:{通过线} → {判定}")

    # 假设 1
    k1 = sum(1 for r in rows if (r.get("第1局_非预设组合") or "").strip() == "是"
             and (r.get("第1局_能讲因果") or "").strip() == "是")
    c1 = yes(rows, "第1局_能讲因果")
    line("假设 1 自己能想到非预设组合并讲清因果", pct(k1, n), "通过线 60% 以上;失败线 能讲因果的不到 40%",
         verdict(k1, n, 0.6, -1) if c1 > 0.4 * n else verdict(k1, n, 0.6, 0.4))

    # 假设 2 真人场次平衡
    冠军 = []
    for r in rows:
        for col in ("第1局_冠军", "第2局_冠军", "第3局_冠军"):
            v = (r.get(col) or "").strip()
            if v: 冠军.append(v)
    if 冠军:
        c = {}
        for v in 冠军: c[v] = c.get(v, 0) + 1
        top = max(c.items(), key=lambda x: x[1])
        share = top[1] / len(冠军)
        说话 = yes(rows, "有人说这台肯定赢")
        line("假设 2 优势能被平衡住(真人侧)",
             f"{len(冠军)} 场,最高是 {top[0]} 赢 {top[1]} 场 = {share*100:.0f}%(10 台同场基线 10%);说「这台肯定赢」的 {说话} 人",
             "最高不超过基线 2.5 倍(25%)且没人说这台肯定赢",
             "通过" if share <= 0.25 and 说话 == 0 else "失败或需复核")
    else:
        print("假设 2 真人场次平衡\n  读数:没有填冠军列,算不出胜率")

    # 假设 3
    k3 = count(rows, "第3局_换想法", "换")
    k7 = yes(rows, "题7_有新东西")
    line("假设 3 第 3 局还在试新想法", f"换组合 {pct(k3, n)};题 7 说还有新东西 {pct(k7, n)}",
         "通过线 60% 以上;失败线 20% 以下(多数回到同一套)", verdict(k3, n, 0.6, 0.2))

    # 假设 4
    误解 = sum(int(x) for x in (num(rows, "误解次数") or [0]))
    捡枪 = count(rows, "题6_选择", "捡枪")
    判定4 = "通过" if (误解 <= 0.2 * n and 捡枪 < 0.5 * n) else ("失败" if (捡枪 > 0.5 * n or 误解 > 0.4 * n) else "方向不明(小样本)")
    line("假设 4 配件语言能当入口", f"误解合计 {误解} 人次;要求直接捡枪 {pct(捡枪, n)}",
         "误解不超过 20% 人次且要捡枪的不到一半", 判定4 + ("" if n >= 10 else "(样本不足,只算方向)"))

    # 假设 5 观战版
    k5 = count(rows, "第2局_紧张感", "有")
    line("假设 5 淘汰结构撑住紧张感(观战版,不是操作版)", pct(k5, n), "通过线 60% 以上;失败线 20% 以下",
         verdict(k5, n, 0.6, 0.2))

    # 假设 6
    k6 = yes(rows, "题5_愿意分享")
    改过 = yes(rows, "第2局_改过再用")
    line("假设 6 愿意分享、别人改过再用", f"愿意分享 {pct(k6, n)};拿别人方案改过再用 {pct(改过, n)}",
         "通过线 60% 以上;失败线 40% 以下", verdict(k6, n, 0.6, 0.4))

    # 假设 10 归因
    k10 = count(rows, "第2局_归因", "机器")
    蹲点 = yes(rows, "第2局_蹲点不打架")
    判定10 = "通过" if (k10 >= 0.6 * n and 蹲点 <= 0.2 * n) else ("失败" if (k10 <= 0.4 * n or 蹲点 > 0.5 * n) else "方向不明(小样本)")
    line("假设 10 占点赢仍归因给自己的机器", f"{pct(k10, n)};明显蹲点不打架 {蹲点} 人",
         "通过线 60% 以上归因给机器,且蹲点的不到 20%", 判定10 + ("" if n >= 10 else "(样本不足,只算方向)"))

    # 假设 11 额度
    合理 = count(rows, "第2局_额度反应", "合理")
    带不上 = count(rows, "第2局_额度反应", "带不上")
    签名 = {(r.get("第3局_组合签名") or "").strip() for r in rows if (r.get("第3局_组合签名") or "").strip()}
    判定11 = "通过" if (合理 >= 0.6 * n and len(签名) >= 0.4 * n) else ("失败" if (带不上 >= 0.5 * n or len(签名) <= 0.2 * n) else "方向不明(小样本)")
    line("假设 11 额度会不会砍掉自由度",
         f"判「合理的限制」{pct(合理, n)};说「想带的带不上」{带不上} 人;第 3 局出现的不同组合 {len(签名)} 种",
         "通过线 60% 判合理且第 3 局组合种类不少于 40%;失败线 一半以上说带不上或种类不超过 20%",
         判定11 + ("" if n >= 10 else "(样本不足,只算方向)"))

    # 旁证,不作判定
    冷启动 = num(rows, "第1局_首次开局秒")
    拼装 = num(rows, "第1局_拼装秒") + num(rows, "第2局_拼装秒") + num(rows, "第3局_拼装秒")
    局长 = num(rows, "第1局_局长秒") + num(rows, "第2局_局长秒") + num(rows, "第3局_局长秒")
    if 冷启动: print(f"\n旁证:打开页面到第一次开局中位 {sorted(冷启动)[len(冷启动)//2]:.0f} 秒(全程没有教程)")
    if 拼装 and 局长:
        比 = sum(拼装) / sum(局长)
        print(f"旁证:拼装用时合计占局长合计的 {比*100:.0f}%——超过 100% 就说明花在拼上的时间比看一局还长,"
              f"正是「局前慢慢拼」那个坑;假设 7 要等一键焊改完才算测过")
    停 = yes(rows, "追问B_要停下挑")
    print(f"旁证:要求停下来慢慢挑的 {停} 人")
    print("\n本轮不测:假设 7(一键焊)、假设 8(合并顶替三选一)——要先改原型;假设 9(留存)——要软发布。")
    print("停止条件照旧:假设 1 与假设 2 同时失败 → 停止这个方向,转为只做装备升级线。")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法:python3 docs/playtest/tally.py docs/playtest/playtest-rows.csv")
        sys.exit(1)
    main(sys.argv[1])
