"""
패턴1: 상승 추세 눌림목 재진입
조건:
  - 기본 상태: MA7 > MA280, Span2 > MA280 (상승 추세 확인)
  - 눌림 발생: MA7이 Span2 아래로 내려간 상태 (직전 N봉 내)
  - 돌파 신호: 가장 최근 확정 캔들에서 MA7이 Span2를 상향 돌파
  - 진입: 다음 캔들 시가 롱 진입
"""

import pandas as pd


# 눌림 확인 lookback (몇 봉 이내에 눌림이 있었는지)
PULLBACK_LOOKBACK = 10


def check_pattern1(df: pd.DataFrame) -> dict:
    """
    패턴1 감지

    Returns:
        {
            "signal": bool,
            "reason": str,
            "entry_candle": str (다음 캔들 시가에 진입),
            "stop_loss": "MA280 하향 돌파 시",
            "take_profit": "ATR 트레일링 스탑",
            "atr": float,
        }
    """
    result = {"signal": False, "reason": "", "entry_candle": "next_open",
              "stop_loss": "MA280 하향 돌파 시", "take_profit": "ATR 트레일링 스탑", "atr": 0.0}

    if len(df) < 30:
        result["reason"] = "데이터 부족"
        return result

    # 확정 캔들 기준 (마지막 캔들은 미확정일 수 있으므로 -2 사용)
    i = -2  # 확정 캔들
    c = df.iloc[i]

    # ── 기본 상태 확인: MA7 > MA280, Span2 > MA280 ──
    if not (c["ma7"] > c["ma280"] and c["span2"] > c["ma280"]):
        result["reason"] = f"기본 상태 불충족 (MA7={c['ma7']:.4f}, MA280={c['ma280']:.4f}, Span2={c['span2']:.4f})"
        return result

    # ── 돌파 신호: 현재 MA7 > Span2 ──
    if not (c["ma7"] > c["span2"]):
        result["reason"] = "MA7이 Span2 위에 있지 않음 (돌파 없음)"
        return result

    # ── 직전 N봉 내 눌림 확인: 이전에 MA7 < Span2 구간이 있었는가 ──
    lookback_slice = df.iloc[max(0, i - PULLBACK_LOOKBACK) : i]
    was_below = (lookback_slice["ma7"] < lookback_slice["span2"]).any()

    if not was_below:
        result["reason"] = f"최근 {PULLBACK_LOOKBACK}봉 내 눌림(MA7<Span2) 없음"
        return result

    # ── 돌파 확인: 바로 직전 봉에서는 MA7 < Span2 였는가 ──
    prev = df.iloc[i - 1]
    if not (prev["ma7"] < prev["span2"]):
        result["reason"] = "직전 봉에서 MA7이 Span2 아래 있지 않음 (이미 돌파된 상태)"
        return result

    # ✅ 패턴1 신호 확정
    result["signal"] = True
    result["reason"] = (
        f"패턴1 신호: MA7({c['ma7']:.4f}) > Span2({c['span2']:.4f}) 상향 돌파, "
        f"MA280({c['ma280']:.4f}) 위 상승 추세 유지"
    )
    result["atr"] = round(df.iloc[i]["atr"], 6) if not pd.isna(df.iloc[i]["atr"]) else 0.0
    return result
