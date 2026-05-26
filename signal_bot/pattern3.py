"""
패턴3: MA280 지지 확인 재상승
조건:
  - 기본 상태: MA7 > MA280, Span2 > MA280 (상승 추세 확인)
  - 음봉: 시가 > MA280, 종가 < MA280 (MA280을 하향 돌파하는 음봉)
  - 양봉: 시가 < MA280, 종가 > MA280 (MA280을 상향 돌파하며 마감하는 양봉)
  - 음봉 직후 양봉이 나와야 함 (연속)
  - 진입: 양봉 확정 후 다음 캔들 시가 롱 진입
"""

import pandas as pd


def check_pattern3(df: pd.DataFrame) -> dict:
    """
    패턴3 감지

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

    # 확정 캔들 기준
    confirmed_idx = len(df) - 2
    c = df.iloc[confirmed_idx]        # 양봉 (가장 최근 확정)
    p = df.iloc[confirmed_idx - 1]    # 음봉 (그 직전)

    # ── 기본 상태 확인 (양봉 기준): MA7 > MA280, Span2 > MA280 ──
    if not (c["ma7"] > c["ma280"] and c["span2"] > c["ma280"]):
        result["reason"] = f"기본 상태 불충족 (MA7={c['ma7']:.4f}, MA280={c['ma280']:.4f}, Span2={c['span2']:.4f})"
        return result

    # ── 음봉 조건: 시가 > MA280, 종가 < MA280 ──
    bearish_candle = (p["open"] > p["ma280"]) and (p["close"] < p["ma280"])
    if not bearish_candle:
        result["reason"] = (
            f"직전 음봉 조건 불충족 (open={p['open']:.4f}, close={p['close']:.4f}, MA280={p['ma280']:.4f})"
        )
        return result

    # ── 양봉 조건: 시가 < MA280, 종가 > MA280 ──
    bullish_candle = (c["open"] < c["ma280"]) and (c["close"] > c["ma280"])
    if not bullish_candle:
        result["reason"] = (
            f"현재 양봉 조건 불충족 (open={c['open']:.4f}, close={c['close']:.4f}, MA280={c['ma280']:.4f})"
        )
        return result

    # ✅ 패턴3 신호 확정
    result["signal"] = True
    result["reason"] = (
        f"패턴3 신호: MA280({c['ma280']:.4f}) 지지 확인 - "
        f"음봉(시가{p['open']:.4f}→종가{p['close']:.4f}) 직후 "
        f"양봉(시가{c['open']:.4f}→종가{c['close']:.4f}) 출현"
    )
    result["atr"] = round(c["atr"], 6) if not pd.isna(c["atr"]) else 0.0
    return result
