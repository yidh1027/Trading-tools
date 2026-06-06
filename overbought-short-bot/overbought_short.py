"""
과매수 구간 숏 신호 봇
─────────────────────────────────────────────
OKX 15분봉에서 5개 조건을 모두 충족하는 과매수 숏 신호를 검사하고
조건 충족 시 텔레그램으로 알림 전송.

신호 조건 (5개 모두 충족 시 다음 캔들 시초가 숏 진입):
  ① 종가 ≥ 볼린저밴드 상단 (BB: SMA20, 2σ)
  ② 시초가 > 선행스팬1 AND 시초가 > 선행스팬2 (구름대 위)
  ③ 저가 > SMA7
  ④ RSI14 ≥ 70 AND CRSI ≥ 85 (종가 기준)
  ⑤ 이격도 = (종가-SMA7)/SMA7×100 ≥ 0.5%

종목: BTC, ETH, XRP, SOL, SUI, DOGE / 15분봉 / 15분마다 실행
"""

import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from indicators import (
    wilder_rsi, connors_rsi, sma, bollinger_upper, ichimoku_spans
)

# ── 설정 ──────────────────────────────────────
COINS = [
    ("BTC-USDT-SWAP", "BTC"),
    ("ETH-USDT-SWAP", "ETH"),
    ("XRP-USDT-SWAP", "XRP"),
    ("SOL-USDT-SWAP", "SOL"),
    ("SUI-USDT-SWAP", "SUI"),
    ("DOGE-USDT-SWAP", "DOGE"),
]
BAR = "15m"
KST = timezone(timedelta(hours=9))

# 신호 조건 임계값
RSI_THRESHOLD = 70
CRSI_THRESHOLD = 85
DISPARITY_MIN = 0.5   # %

# 텔레그램 (GitHub Secrets에서 주입)
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

# 헬스체크: 한국시간 9시대에 실행되면 상태 메시지 전송
HEALTHCHECK_HOUR = 9


def fetch_candles(symbol, bar, total=400):
    """OKX history-candles로 최근 total개 캔들 수집 (오름차순, 확정봉만)"""
    all_rows, after = [], None
    while len(all_rows) < total:
        url = f"https://www.okx.com/api/v5/market/history-candles?instId={symbol}&bar={bar}&limit=100"
        if after:
            url += f"&after={after}"
        try:
            j = requests.get(url, timeout=15).json()
        except Exception as e:
            print(f"  [{symbol}] 수집 오류: {e}")
            break
        if j.get("code") != "0" or not j.get("data"):
            break
        rows = j["data"]
        all_rows.extend(rows)
        after = rows[-1][0]
        if len(rows) < 100:
            break
        time.sleep(0.1)
    if not all_rows:
        return None
    seen = {r[0]: r for r in all_rows}
    rows = sorted(seen.values(), key=lambda x: int(x[0]))
    df = pd.DataFrame(rows, columns=["ts","o","h","l","c","v","vc","vcq","confirm"])
    df["ts"] = df["ts"].astype(np.int64)
    for col in ["o","h","l","c"]:
        df[col] = df[col].astype(float)
    # confirm==1 인 확정봉만 사용 (미확정 현재봉 제외)
    df = df[df["confirm"] == "1"].reset_index(drop=True)
    return df


def check_signal(df):
    """
    가장 최근 확정봉이 5개 조건을 모두 충족하는지 검사.
    충족하면 신호 정보 dict 반환, 아니면 None.
    """
    if df is None or len(df) < 250:
        return None

    close = df["c"]
    high = df["h"]
    low = df["l"]
    open_ = df["o"]

    rsi14 = wilder_rsi(close, 14)
    crsi = connors_rsi(close)
    ma7 = sma(close, 7)
    bb_up = bollinger_upper(close, 20, 2.0)
    span1, span2 = ichimoku_spans(high, low)

    i = len(df) - 1   # 가장 최근 확정봉

    # 값이 비어있으면 검사 불가
    if any(pd.isna(x.iloc[i]) for x in [rsi14, crsi, ma7, bb_up, span1, span2]):
        return None

    c = close.iloc[i]
    o = open_.iloc[i]
    h = high.iloc[i]
    lo = low.iloc[i]
    m7 = ma7.iloc[i]
    disparity = (c - m7) / m7 * 100

    # 5개 조건
    cond1 = c >= bb_up.iloc[i]                          # 종가 ≥ BB 상단
    cond2 = o > span1.iloc[i] and o > span2.iloc[i]     # 구름대 위
    cond3 = lo > m7                                      # 저가 > MA7
    cond4 = rsi14.iloc[i] >= RSI_THRESHOLD and crsi.iloc[i] >= CRSI_THRESHOLD
    cond5 = disparity >= DISPARITY_MIN                  # 이격도 ≥ 0.5%

    if cond1 and cond2 and cond3 and cond4 and cond5:
        return {
            "ts": int(df["ts"].iloc[i]),
            "close": c,
            "rsi14": rsi14.iloc[i],
            "crsi": crsi.iloc[i],
            "disparity": disparity,
        }
    return None


def send_telegram(text):
    """텔레그램 메시지 전송"""
    if not TG_TOKEN or not TG_CHAT:
        print("  [경고] 텔레그램 토큰/chat_id 미설정. 메시지 출력만:")
        print(text)
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TG_CHAT,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=15)
        if r.status_code != 200:
            print(f"  [텔레그램 오류] {r.status_code}: {r.text}")
    except Exception as e:
        print(f"  [텔레그램 전송 실패] {e}")


def format_signal(name, sig):
    """신호 메시지 포맷"""
    t = datetime.fromtimestamp(sig["ts"]/1000, KST).strftime("%Y-%m-%d %H:%M")
    return (
        f"🔴 <b>숏 신호 발생</b>\n\n"
        f"종목: <b>{name}/USDT</b>\n"
        f"시각: {t} (KST)\n"
        f"종가: {sig['close']:,.4f}\n"
        f"RSI(14): {sig['rsi14']:.1f}\n"
        f"CRSI: {sig['crsi']:.1f}\n"
        f"이격도: {sig['disparity']:.2f}%"
    )


def main():
    now_kst = datetime.now(KST)
    print(f"=== 과매수 숏 신호 검사 시작 {now_kst.strftime('%Y-%m-%d %H:%M')} KST ===")

    signals_found = []
    checked = 0

    for symbol, name in COINS:
        print(f"[{name}] 검사 중...")
        df = fetch_candles(symbol, BAR, total=400)
        if df is None:
            print(f"  [{name}] 데이터 수집 실패")
            continue
        checked += 1
        sig = check_signal(df)
        if sig:
            print(f"  ★ [{name}] 신호 발생! CRSI={sig['crsi']:.1f} 이격={sig['disparity']:.2f}%")
            msg = format_signal(name, sig)
            send_telegram(msg)
            signals_found.append(name)
        else:
            print(f"  [{name}] 신호 없음")

    # 헬스체크: 지정 시각대(9시)에 실행되면 상태 메시지 전송
    if now_kst.hour == HEALTHCHECK_HOUR:
        health = (
            f"✅ <b>신호봇 정상 작동 중</b>\n\n"
            f"시각: {now_kst.strftime('%Y-%m-%d %H:%M')} (KST)\n"
            f"검사한 코인: {checked}/{len(COINS)}개\n"
            f"현재 신호: {'없음' if not signals_found else ', '.join(signals_found)}"
        )
        send_telegram(health)
        print("  [헬스체크] 상태 메시지 전송")

    print(f"=== 검사 완료. 신호 {len(signals_found)}건 ===")


if __name__ == "__main__":
    main()
