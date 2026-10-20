#!/usr/bin/env python3
"""증시·유가·환율 시세를 가져와 data.json 으로 저장합니다. (표준 라이브러리만 사용)

GitHub Actions 가 주기적으로 실행하고, index.html 이 data.json 을 읽어 보여줍니다.
일부 종목이 실패하면 이전 data.json 의 값을 유지하고, 전부 실패하면 오류로 종료합니다.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (compatible; daily-board/1.0)"
OUT = "data.json"

# 이름 -> 야후 파이낸스 심볼
MARKETS = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "SPX": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "WTI": "CL=F",
    "BRENT": "BZ=F",
}
# 원화 환율 (1단위 외화당 원). USD 는 KRW=X, 나머지는 {코드}KRW=X
CURRENCIES = ["USD", "JPY", "EUR", "CNY", "GBP", "AUD", "CAD", "CHF", "HKD",
              "SGD", "NZD", "THB", "VND", "TWD", "PHP", "MYR", "IDR", "INR"]


def fx_symbol(code):
    return "KRW=X" if code == "USD" else code + "KRW=X"


def fetch_json(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def parse_chart(data):
    """차트 응답에서 (현재가, 전일 종가, 기준 시각) 추출"""
    res = data["chart"]["result"][0]
    meta = res.get("meta", {})
    ts = res.get("timestamp") or []
    closes = res["indicators"]["quote"][0]["close"]
    pairs = [(t, c) for t, c in zip(ts, closes) if c is not None]
    if len(pairs) < 2:
        raise ValueError("데이터 부족")
    price = meta.get("regularMarketPrice")
    if price is None:
        price = pairs[-1][1]
    prev = pairs[-2][1]
    when = meta.get("regularMarketTime") or pairs[-1][0]
    return {"price": round(float(price), 6), "prev": round(float(prev), 6), "time": int(when)}


def get_quote(symbol):
    path = "/v8/finance/chart/" + urllib.parse.quote(symbol) + "?range=5d&interval=1d"
    last = None
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        try:
            return parse_chart(fetch_json("https://" + host + path))
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def load_old():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def main():
    old = load_old()
    markets, fx, failed = {}, {}, []

    for name, sym in MARKETS.items():
        try:
            markets[name] = get_quote(sym)
        except Exception as e:  # noqa: BLE001
            failed.append(name + ": " + str(e))
            if name in old.get("markets", {}):
                markets[name] = old["markets"][name]
        time.sleep(0.4)

    for code in CURRENCIES:
        try:
            fx[code] = get_quote(fx_symbol(code))
        except Exception as e:  # noqa: BLE001
            failed.append(code + ": " + str(e))
            if code in old.get("fx", {}):
                fx[code] = old["fx"][code]
        time.sleep(0.4)

    got = len(markets) + len(fx)
    if got == 0:
        print("모든 시세 조회에 실패했습니다:", *failed, sep="\n  ", file=sys.stderr)
        sys.exit(1)

    out = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "markets": markets,
        "fx": fx,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("저장 완료: 시장 %d개, 환율 %d개" % (len(markets), len(fx)))
    if failed:
        print("일부 실패:", *failed, sep="\n  ")


if __name__ == "__main__":
    main()
