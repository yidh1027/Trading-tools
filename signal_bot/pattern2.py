"""
패턴2: 하락 추세 전환 포착
조건:
  - 기본 상태: MA7 < MA280, Span2 < MA280 (하락 추세 확인)
  - 1단계: MA7이 Span2를 상향 돌파
  - 2단계: 그 후 7캔들 이내에 캔들 종가가 MA280을 상향 돌파하며 마감
  - 진입: 그 다음 캔들 시가 롱 진입
"""

import pandas as pd


MA280_CROSS_WINDOW = 7  # MA7이 Span2 돌파 후 MA280 돌파까지 허용 봉 수


def check_pattern2(df: pd.DataFrame) -> dict:
    """
    패턴2 감지

    Returns:
        {
            "signal": bool,
            "reason": str,
            ...
        }
    """
    result = {"signal": False, "reason": "", "entry_candle": "next_open",
              "stop_loss": "MA280 하향 돌파 시", "take_profit": "ATR 트레일링 스탑", "atr": 0.0}

    if len(df) < 30:
        result["reason"] = "데이터 부족"
        return result

    # 확정 캔들 인덱스 (-2: 마지막 확정 캔들)
    confirmed_idx = len(df) - 2

    # 확정 캔들 기준으로 역방향 탐색
    c = df.iloc[confirmed_idx]

    # ── 2단계 확인: 현재 확정 캔들이 MA280 상향 돌파 마감인가 ──
    # 조건: close > MA280 (현재), close_prev < MA280 (이전)
    prev = df.iloc[confirmed_idx - 1]

    if not (c["close"] > c["ma280"] and prev["close"] < prev["ma280"]):
        result["reason"] = "현재 캔들이 MA280 상향 돌파 마감 아님"
        return result

    # ── 1단계 확인: 최근 7봉 이내에 MA7이 Span2를 상향 돌파한 봉이 있는가 ──
    window_start = max(0, confirmed_idx - MA280_CROSS_WINDOW)
    window = df.iloc[window_start : confirmed_idx + 1]

    ma7_cross_found = False
    cross_idx = -1

    for j in range(1, len(window)):
        row_cur = window.iloc[j]
        row_pre = window.iloc[j - 1]
        # MA7이 Span2 상향 돌파
        if row_pre["ma7"] < row_pre["span2"] and row_cur["ma7"] > row_cur["span2"]:
            ma7_cross_found = True
            cross_idx = j
            break

    if not ma7_cross_found:
        result["reason"] = f"최근 {MA280_CROSS_WINDOW}봉 내 MA7의 Span2 상향 돌파 없음"
        return result

    # ── 기본 상태 확인: MA7 돌파 시점 이전 봉에서 MA7 < MA280, Span2 < MA280 ──
    # cross_idx 이전 시점 (창 내에서)
    pre_cross = window.iloc[cross_idx - 1]
    if not (pre_cross["ma7"] < pre_cross["ma280"] and pre_cross["span2"] < pre_cross["ma280"]):
        result["reason"] = "MA7 돌파 시점에 하락 추세 상태 불충족 (MA7 또는 Span2 >= MA280)"
        return result

    # ✅ 패턴2 신호 확정
    result["signal"] = True
    result["reason"] = (
        f"패턴2 신호: MA7의 Span2 돌파 후 {MA280_CROSS_WINDOW}봉 이내 "
        f"종가({c['close']:.4f})가 MA280({c['ma280']:.4f}) 상향 돌파 마감"
    )
    result["atr"] = round(c["atr"], 6) if not pd.isna(c["atr"]) else 0.0
    return result
