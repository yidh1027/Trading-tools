"""
기술 지표 계산 모듈
- MA7, MA280
- 일목균형표 선행스팬2 (Ichimoku Span B)
- ATR (트레일링 스탑용)
"""

import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame에 MA7, MA280, 일목균형표 선행스팬2, ATR을 추가합니다.

    일목균형표 기간 설정 (표준):
        전환선: 9봉
        기준선: 26봉
        선행스팬2: (전환선 + 기준선) / 2, 26봉 앞에 플롯
                   실제로는 52봉 최고/최저의 중간값
    """
    df = df.copy()

    # ── MA ──────────────────────────────────────────
    df["ma7"] = df["close"].rolling(7).mean()
    df["ma280"] = df["close"].rolling(280).mean()

    # ── 일목균형표 선행스팬2 ─────────────────────────
    # 선행스팬2 = 과거 52봉의 (최고가 + 최저가) / 2 를 26봉 앞에 플롯
    # 신호 감지 목적: 현재 캔들이 구름(Span2) 위/아래 판단을 위해
    # 현재 시점의 구름 = 26봉 전에 계산된 Span2 원값 → shift(+26)으로 현재에 맞춤
    period_b = 52
    span2_raw = (df["high"].rolling(period_b).max() + df["low"].rolling(period_b).min()) / 2
    df["span2"] = span2_raw.shift(26)

    # ── ATR (14봉) ───────────────────────────────────
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    return df


def is_valid(df: pd.DataFrame, min_rows: int = 300) -> bool:
    """지표 계산에 충분한 데이터가 있는지 확인"""
    return len(df) >= min_rows and not df[["ma7", "ma280", "span2"]].iloc[-3:].isnull().any().any()
