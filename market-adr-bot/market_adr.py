"""
코인 시장 ADR 봇
─────────────────────────────────────────────
시총 상위 100개 코인을 두 그룹으로 나눠 지난 6시간 등락 기준 ADR을 계산하고,
비트코인/이더리움 도미넌스와 TOTAL3(알트 시총)를 함께 텔레그램으로 전송.

데이터 흐름:
  1. CoinGecko global → 도미넌스(BTC.D, ETH.D), 전체 시총 (TOTAL3 계산용)
  2. CoinGecko markets → 시총 상위 100개 코인 순위 + 심볼
  3. OKX instruments → OKX에 상장된 USDT 현물 목록
  4. (1~100위 중 OKX에 있는 코인) 각각의 6시간 전/현재 종가 → 6시간 등락 계산
     (ADR은 시장 분위기 측정이므로 현물 가격 사용 — 표본 최대화)
  5. 그룹별 ADR = 상승 개수 / 하락 개수
     - 대형: 시총 1~20위
     - 알트: 시총 21~100위

6시간 간격 실행 (cron-job.org). 측정 기간도 6시간(=15분봉 24개 전과 비교).
"""

import os
import time
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

CG_BASE = "https://api.coingecko.com/api/v3"
OKX_BASE = "https://www.okx.com"

TOP_N = 200          # 시총 상위 몇 개
# 세 그룹 경계 (순위 기준)
LARGE_MAX = 20       # 1~20위 = 대형
MID_MAX = 80         # 21~80위 = 중형
# 81~200위 = 소형
HOURS = 6            # 등락 측정 기간
BARS_BACK = HOURS * 4  # 15분봉 기준 6시간 = 24봉 전


def get_coingecko_global():
    """전체 시총, BTC/ETH 도미넌스 반환"""
    try:
        r = requests.get(f"{CG_BASE}/global", timeout=20)
        d = r.json()["data"]
        total_mcap = d["total_market_cap"]["usd"]
        btc_dom = d["market_cap_percentage"].get("btc", 0)
        eth_dom = d["market_cap_percentage"].get("eth", 0)
        return {
            "total_mcap": total_mcap,
            "btc_dom": btc_dom,
            "eth_dom": eth_dom,
        }
    except Exception as e:
        print(f"  [global 오류] {e}")
        return None


def get_top_coins(n=100):
    """시총 상위 n개 코인의 순위/심볼/시총 반환"""
    coins = []
    try:
        # per_page 최대 250, n=200이면 1페이지로 충분
        r = requests.get(
            f"{CG_BASE}/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": n,
                "page": 1,
            },
            timeout=20,
        )
        data = r.json()
        for i, c in enumerate(data):
            coins.append({
                "rank": i + 1,
                "symbol": c["symbol"].upper(),   # 'btc' → 'BTC'
                "mcap": c.get("market_cap", 0),
                "name": c.get("name", ""),
            })
    except Exception as e:
        print(f"  [markets 오류] {e}")
    return coins


def get_okx_spot_symbols():
    """OKX에 상장된 USDT 현물의 코인 심볼 집합 반환 (예: {'BTC','ETH',...})"""
    symbols = set()
    try:
        r = requests.get(
            f"{OKX_BASE}/api/v5/public/instruments",
            params={"instType": "SPOT"},
            timeout=20,
        )
        for inst in r.json().get("data", []):
            inst_id = inst.get("instId", "")
            # 'BTC-USDT' 형식만 (USDT 현물 페어)
            if inst_id.endswith("-USDT"):
                base = inst_id.split("-")[0]
                symbols.add(base)
    except Exception as e:
        print(f"  [OKX instruments 오류] {e}")
    return symbols


def get_6h_change(symbol):
    """
    OKX에서 해당 코인의 6시간 등락률(%) 반환.
    15분봉 (BARS_BACK+2)개를 가져와 현재 종가 vs 6시간 전(24봉 전) 종가 비교.
    실패 시 None.
    """
    inst_id = f"{symbol}-USDT"   # OKX 현물 페어
    try:
        r = requests.get(
            f"{OKX_BASE}/api/v5/market/candles",
            params={"instId": inst_id, "bar": "15m", "limit": BARS_BACK + 2},
            timeout=15,
        )
        data = r.json().get("data", [])
        # OKX candles는 최신순. data[0]=가장최근, data[BARS_BACK]=24봉 전
        if len(data) < BARS_BACK + 1:
            return None
        now_close = float(data[0][4])
        past_close = float(data[BARS_BACK][4])
        if past_close == 0:
            return None
        return (now_close - past_close) / past_close * 100
    except Exception:
        return None


def compute_group_adr(coins, okx_symbols, low_rank, high_rank):
    """
    지정 순위 범위(low~high위) 코인들의 6시간 등락으로 ADR 계산.
    반환: dict(up, down, flat, adr, checked, missing, not_on_okx, fetch_fail)
    """
    up = down = flat = 0
    checked = 0
    not_on_okx = []   # OKX에 없는 코인
    fetch_fail = []   # OKX엔 있지만 데이터 못 가져온 코인
    for c in coins:
        if not (low_rank <= c["rank"] <= high_rank):
            continue
        if c["symbol"] not in okx_symbols:
            not_on_okx.append(c["symbol"])
            continue
        change = get_6h_change(c["symbol"])
        time.sleep(0.05)   # OKX 호출 간격
        if change is None:
            fetch_fail.append(c["symbol"])
            continue
        checked += 1
        if change > 0:
            up += 1
        elif change < 0:
            down += 1
        else:
            flat += 1
    adr = (up / down) if down > 0 else (up if up > 0 else 0)
    return {
        "up": up, "down": down, "flat": flat,
        "adr": adr, "checked": checked,
        "missing": len(not_on_okx) + len(fetch_fail),
        "not_on_okx": not_on_okx,
        "fetch_fail": fetch_fail,
    }


def interpret_adr(adr):
    """ADR 값을 간단한 해석으로"""
    if adr >= 2.0:
        return "강한 상승 우위 🔥"
    elif adr >= 1.2:
        return "상승 우위 📈"
    elif adr >= 0.83:   # 1/1.2
        return "중립 ⚖️"
    elif adr >= 0.5:
        return "하락 우위 📉"
    else:
        return "강한 하락 우위 🧊"


def send_telegram(text):
    if not TG_TOKEN or not TG_CHAT:
        print("  [경고] 텔레그램 미설정. 출력만:")
        print(text)
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        if r.status_code != 200:
            print(f"  [텔레그램 오류] {r.status_code}: {r.text}")
    except Exception as e:
        print(f"  [텔레그램 전송 실패] {e}")


def main():
    now = datetime.now(KST)
    print(f"=== 시장 ADR 검사 시작 {now.strftime('%Y-%m-%d %H:%M')} KST ===")

    # 1. 도미넌스 + 전체 시총
    g = get_coingecko_global()
    if g is None:
        print("  global 데이터 실패. 종료.")
        return
    # TOTAL3 = 전체 시총 - 비트코인 - 이더리움 (도미넌스로 역산)
    alt_dom = 100 - g["btc_dom"] - g["eth_dom"]
    total3 = g["total_mcap"] * alt_dom / 100

    # 2. 시총 상위 코인
    coins = get_top_coins(TOP_N)
    if not coins:
        print("  코인 목록 실패. 종료.")
        return
    print(f"  시총 상위 {len(coins)}개 수집")

    # 3. OKX 상장 목록
    okx_symbols = get_okx_spot_symbols()
    print(f"  OKX USDT 현물 {len(okx_symbols)}개")

    # 4. 그룹별 ADR (세 그룹)
    print("  대형 그룹(1~20위) 계산 중...")
    large = compute_group_adr(coins, okx_symbols, 1, LARGE_MAX)
    print("  중형 그룹(21~80위) 계산 중...")
    mid = compute_group_adr(coins, okx_symbols, LARGE_MAX + 1, MID_MAX)
    print("  소형 그룹(81~200위) 계산 중...")
    small = compute_group_adr(coins, okx_symbols, MID_MAX + 1, TOP_N)

    # 진단: 빠진 코인 목록 출력 (로그 전용, 텔레그램엔 안 보냄)
    print("\n  --- 진단: 빠진 코인 (OKX 현물에 없음) ---")
    print(f"  [대형] ({len(large['not_on_okx'])}개): {', '.join(large['not_on_okx']) or '없음'}")
    print(f"  [중형] ({len(mid['not_on_okx'])}개): {', '.join(mid['not_on_okx']) or '없음'}")
    print(f"  [소형] ({len(small['not_on_okx'])}개): {', '.join(small['not_on_okx']) or '없음'}")
    fail_all = large['fetch_fail'] + mid['fetch_fail'] + small['fetch_fail']
    print(f"  [데이터 실패] ({len(fail_all)}개): {', '.join(fail_all) or '없음'}")
    print("  ----------------------\n")

    # 5. 메시지 작성
    def fmt_mcap(v):
        if v >= 1e12:
            return f"${v/1e12:.2f}T"
        elif v >= 1e9:
            return f"${v/1e9:.0f}B"
        return f"${v:,.0f}"

    msg = (
        f"📊 <b>코인 시장 ADR (지난 {HOURS}시간)</b>\n"
        f"{now.strftime('%Y-%m-%d %H:%M')} KST\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>대형 (1~20위)</b>\n"
        f"  ADR: <b>{large['adr']:.2f}</b> — {interpret_adr(large['adr'])}\n"
        f"  ↑{large['up']}  ↓{large['down']}  →{large['flat']} (집계 {large['checked']}개)\n"
        f"\n"
        f"<b>중형 (21~80위)</b>\n"
        f"  ADR: <b>{mid['adr']:.2f}</b> — {interpret_adr(mid['adr'])}\n"
        f"  ↑{mid['up']}  ↓{mid['down']}  →{mid['flat']} (집계 {mid['checked']}개)\n"
        f"\n"
        f"<b>소형 (81~200위)</b>\n"
        f"  ADR: <b>{small['adr']:.2f}</b> — {interpret_adr(small['adr'])}\n"
        f"  ↑{small['up']}  ↓{small['down']}  →{small['flat']} (집계 {small['checked']}개)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>도미넌스</b>\n"
        f"  BTC: {g['btc_dom']:.1f}%   ETH: {g['eth_dom']:.1f}%\n"
        f"  ALT(TOTAL3): {fmt_mcap(total3)}\n"
        f"  전체 시총: {fmt_mcap(g['total_mcap'])}"
    )

    send_telegram(msg)
    print("  메시지 전송 완료")
    print(f"=== 완료 ===")


if __name__ == "__main__":
    main()
