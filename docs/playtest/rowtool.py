#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把原型页面「复制本局记录」的那三段文字,变成记录表里的一行 CSV。
用法:
  1. 一场试玩结束以后,把第 1、2、3 局各自的记录文字按顺序粘进一个文本文件,
     局与局之间空一行,例如 docs/playtest/raw/场次01.txt
  2. python3 docs/playtest/rowtool.py docs/playtest/raw/场次01.txt --场次 1 --组别 A
  3. 把打印出来的那一行追加到 docs/playtest/playtest-rows.csv:
     python3 docs/playtest/rowtool.py ... >> docs/playtest/playtest-rows.csv

只有能从记录文字里直接读出来的列会被填上(拼装秒、局长秒、冠军、组合签名)。
需要引导者当场看和问的列(误解次数、归因、原话、问卷题 5-7)一律留空,
并在最后列出还缺哪几列,防止漏填。
"""
import argparse
import csv
import io
import re
import sys

表头 = "场次,组别,有录像,第一句问的,误解次数,有人说这台肯定赢,第1局_拼装秒,第1局_首次开局秒,第1局_局长秒,第1局_非预设组合,第1局_能讲因果,第1局_冠军,第2局_拼装秒,第2局_局长秒,第2局_额度反应,第2局_紧张感,第2局_归因,第2局_蹲点不打架,第2局_用过别人的造法,第2局_改过再用,第2局_冠军,第3局_拼装秒,第3局_局长秒,第3局_换想法,第3局_组合签名,第3局_冠军,题5_愿意分享,题6_选择,题7_有新东西,追问B_要停下挑,原话_因果,原话_归因".split(",")

# 引导者必须当场填的列(机器填不了)
人填 = ["第一句问的", "误解次数", "有人说这台肯定赢", "第1局_非预设组合", "第1局_能讲因果",
        "第2局_额度反应", "第2局_紧张感", "第2局_归因", "第2局_蹲点不打架", "第2局_用过别人的造法",
        "第2局_改过再用", "第3局_换想法", "题5_愿意分享", "题6_选择", "题7_有新东西",
        "追问B_要停下挑", "原话_因果", "原话_归因"]

预设名 = {"双矛快刀车", "重铁冲撞车", "火焰长矛车", "锤子重卡", "烟雾逃跑车",
          "三推猛冲车", "盾矛平衡车", "电刺快车", "闪光长矛车", "你的机器"}


def 取(text, 正则):
    m = re.search(正则, text)
    return m.group(1).strip() if m else ""


def 解析块(text):
    局 = 取(text, r"【试玩记录】第\s*(\d+)\s*局")
    拼装 = 取(text, r"本局拼装用时:(\S+) 秒")
    首开 = 取(text, r"从打开页面到第一次开局:(\S+) 秒")
    局长 = 取(text, r"局长:([\d.]+) 秒")
    结果 = 取(text, r"本局结果:(.*)")
    冠军 = 结果.split(" 获胜")[0].strip() if 结果.startswith("第") is False and 结果 else ""
    if 结果.startswith("还没打完") or "还没打完" in 结果:
        冠军 = "没打完"
    名称 = 取(text, r"我的造法名称:(.*)")
    特性 = 取(text, r"特性 (.*)$")
    捡料 = 取(text, r"开局捡到\(我的机器\):(.*)")
    开局次数 = 取(text, r"本页面第\s*(\d+)\s*次开局")
    return {"局": 局, "拼装": 拼装, "首开": 首开, "局长": 局长, "冠军": 冠军,
            "名称": 名称, "特性": 特性.replace("·", "").strip(), "捡料": 捡料, "开局次数": 开局次数}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", help="三段记录文字所在的文本文件")
    ap.add_argument("--场次", required=True)
    ap.add_argument("--组别", required=True, choices=["A", "B"])
    ap.add_argument("--录像", default="是", choices=["是", "否"])
    a = ap.parse_args()

    原文 = open(a.raw, encoding="utf-8").read()
    块们 = [b.strip() for b in re.split(r"\n\s*\n", 原文) if "【试玩记录】" in b]
    if len(块们) != 3:
        print(f"警告:文件里只找到 {len(块们)} 段【试玩记录】,应该是 3 段(第 1、2、3 局)。"
              f"这一行的空格子需要引导者补。", file=sys.stderr)

    行 = {c: "" for c in 表头}
    行["场次"], 行["组别"], 行["有录像"] = a.场次, a.组别, a.录像
    提示 = []
    for i, 块 in enumerate(块们[:3]):
        d = 解析块(块)
        if d["局"] and d["局"] != str(i + 1):
            提示.append(f"第 {i+1} 段记录写的是「第 {d['局']} 局」,顺序可能粘错了")
        前缀 = f"第{i+1}局_"
        if d["拼装"]: 行[前缀 + "拼装秒"] = d["拼装"]
        if d["局长"]: 行[前缀 + "局长秒"] = d["局长"]
        if d["冠军"]: 行[前缀 + "冠军"] = d["冠军"]
        if i == 0:
            if d["首开"]: 行["第1局_首次开局秒"] = d["首开"]
            if d["捡料"].startswith("这一局没有捡料"):
                提示.append("第 1 局用的是「开这一局」按钮,没有捡两块余料 —— 三局规则不一致,报告里要注明")
        if i == 2 and d["名称"]:
            行["第3局_组合签名"] = (d["名称"] + " · " + d["特性"]).strip(" ·")
        if int(d["开局次数"] or 1) > 1:
            提示.append(f"第 {i+1} 局重复开局 {d['开局次数']} 次,拼装秒与局长秒按最后一次记的")

    buf = io.StringIO()
    csv.writer(buf).writerow([行[c] for c in 表头])
    print(buf.getvalue().rstrip("\r\n"))

    缺 = [c for c in 人填 if not 行[c]]
    print(f"# 还缺 {len(缺)} 列(引导者当场看与问,机器填不了):{'、'.join(缺)}", file=sys.stderr)
    for p in 提示:
        print(f"# 注意:{p}", file=sys.stderr)


if __name__ == "__main__":
    main()
