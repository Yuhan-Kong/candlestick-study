"""下载股票清单的日线数据，供学习页在浏览器里现场计算。

输出（相对 --out 目录）：
  market/index.json         [{s, name, zh, as_of}]
  market/{SYMBOL}.json      {s, name, zh, as_of, rows: [[date, o, h, l, c, v], ...]}（近 2 年）

美股当天未收盘时去掉当天未完成的 K 线（只用到 T-1）。
本地运行：/opt/homebrew/bin/python3 fetch_data.py --out _site
线上：GitHub Actions 每个交易日收盘后运行（_site/.github/workflows/market-data.yml）。只用标准库。
"""
import argparse
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?range=2y&interval=1d"

# 美股大盘股 + 两只指数 ETF（不是严格的市值排名，够练习用）
TICKERS = [
    ("MSFT", "微软"), ("AAPL", "苹果"), ("NVDA", "英伟达"), ("GOOGL", "谷歌"), ("AMZN", "亚马逊"),
    ("META", "Meta"), ("AVGO", "博通"), ("TSLA", "特斯拉"), ("BRK-B", "伯克希尔"), ("LLY", "礼来"),
    ("JPM", "摩根大通"), ("V", "Visa"), ("MA", "万事达"), ("WMT", "沃尔玛"), ("ORCL", "甲骨文"),
    ("XOM", "埃克森美孚"), ("UNH", "联合健康"), ("COST", "开市客"), ("NFLX", "奈飞"), ("HD", "家得宝"),
    ("PG", "宝洁"), ("JNJ", "强生"), ("ABBV", "艾伯维"), ("BAC", "美国银行"), ("KO", "可口可乐"),
    ("CRM", "Salesforce"), ("AMD", "AMD"), ("PLTR", "Palantir"), ("CVX", "雪佛龙"), ("MRK", "默沙东"),
    ("CSCO", "思科"), ("PEP", "百事"), ("TMO", "赛默飞"), ("WFC", "富国银行"), ("ADBE", "Adobe"),
    ("LIN", "林德"), ("MCD", "麦当劳"), ("IBM", "IBM"), ("GE", "通用电气"), ("ACN", "埃森哲"),
    ("QCOM", "高通"), ("TXN", "德州仪器"), ("INTU", "Intuit"), ("AMAT", "应用材料"), ("DIS", "迪士尼"),
    ("CAT", "卡特彼勒"), ("NOW", "ServiceNow"), ("ISRG", "直觉外科"), ("GS", "高盛"), ("UBER", "优步"),
    ("SPY", "标普 500 ETF"), ("QQQ", "纳指 100 ETF"),
]


def fetch(sym):
    req = urllib.request.Request(URL.format(s=sym), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        res = json.load(r)["chart"]["result"][0]
    q, meta = res["indicators"]["quote"][0], res["meta"]
    rows = []
    period = meta["currentTradingPeriod"]["regular"]
    closed_today = time.time() >= period["end"]
    for i, ts in enumerate(res["timestamp"]):
        o, h, l, c, v = (q[k][i] for k in ("open", "high", "low", "close", "volume"))
        # Yahoo 有时收盘几个小时后当天日线仍缺收盘价：当天已收盘时，用行情摘要里的当日数据补齐
        if i == len(res["timestamp"]) - 1 and closed_today and ts >= period["start"] - 3600 and None in (h, l, c):
            h = h if h is not None else meta.get("regularMarketDayHigh")
            l = l if l is not None else meta.get("regularMarketDayLow")
            c = c if c is not None else meta.get("regularMarketPrice")
            v = v if v is not None else meta.get("regularMarketVolume")
            o = o if o is not None else c
        if None in (o, h, l, c):
            continue
        rows.append([datetime.fromtimestamp(ts, NY).strftime("%Y-%m-%d"), round(o, 2), round(h, 2), round(l, 2), round(c, 2), int(v or 0)])
    if rows and rows[-1][0] == datetime.now(NY).strftime("%Y-%m-%d") and period["start"] <= time.time() < period["end"]:
        rows.pop()
    return meta.get("longName") or meta.get("shortName") or sym, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site")
    out = Path(ap.parse_args().out) / "market"
    out.mkdir(parents=True, exist_ok=True)
    index, failed = [], []
    for sym, zh in TICKERS:
        try:
            name, rows = fetch(sym)
        except Exception as e:                      # 单只失败不影响其他；保留上次的文件
            failed.append(f"{sym}: {e}")
            old = out / f"{sym}.json"
            if old.exists():
                d = json.loads(old.read_text())
                index.append({k: d[k] for k in ("s", "name", "zh", "as_of")})
            continue
        doc = {"s": sym, "name": name, "zh": zh, "as_of": rows[-1][0], "rows": rows}
        (out / f"{sym}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
        index.append({k: doc[k] for k in ("s", "name", "zh", "as_of")})
        time.sleep(0.4)
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=0))
    print(f"{len(index)} 只，失败 {len(failed)}", *failed, sep="\n")
    if len(failed) > len(TICKERS) // 2:
        raise SystemExit("超过一半下载失败，可能是数据源出了问题")


if __name__ == "__main__":
    main()
