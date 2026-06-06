"""
지표 계산 모듈
─────────────────────────────────────────────
RSI(Wilder), CRSI(검증 완료), SMA, 볼린저밴드, 일목균형표 선행스팬
모든 계산은 OKX 차트(트레이딩뷰)와 일치하도록 검증됨.

CRSI 핵심: PercentRank는 "현재 봉 포함 100개 윈도우에서
현재 1봉 변동률보다 작은(미만<) 값의 개수 ÷ 100 × 100"
→ 6/5~6/6 7개 시점 OKX와 소수점까지 정확히 일치 확인됨.
"""

import numpy as np
import pandas as pd


def wilder_rsi(series: pd.Series, length: int) -> pd.Series:
    """Wilder RSI = 트레이딩뷰 ta.rsi 와 동일 (ewm alpha=1/length)"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1/length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - 100 / (1 + rs)
    return rsi.where(avg_loss != 0, 100.0)


def updown_streak(close: pd.Series) -> pd.Series:
    """연속 상승/하락 누적. 동일가는 0. 상승=양수, 하락=음수."""
    s = np.zeros(len(close))
    c = close.values
    for i in range(1, len(c)):
        if c[i] > c[i-1]:
            s[i] = s[i-1] + 1 if s[i-1] > 0 else 1
        elif c[i] < c[i-1]:
            s[i] = s[i-1] - 1 if s[i-1] < 0 else -1
        else:
            s[i] = 0
    return pd.Series(s, index=close.index)


def percentrank_incl_lt(series: pd.Series, length: int = 100) -> pd.Series:
    """
    검증된 PercentRank:
    현재 봉 포함 length개 윈도우(직전 99 + 현재 1)에서
    현재값보다 작은(<) 값의 개수 ÷ length × 100
    """
    out = pd.Series(np.nan, index=series.index)
    v = series.values
    for i in range(length, len(v)):
        window = v[i-length+1:i+1]   # 현재 포함 length개
        out.iloc[i] = np.sum(window < v[i]) / length * 100
    return out


def connors_rsi(close: pd.Series,
                rsi_len: int = 3,
                updown_len: int = 2,
                roc_len: int = 100) -> pd.Series:
    """
    CRSI = (RSI(close,3) + RSI(streak,2) + PercentRank(1봉변동률,100)) / 3
    검증 완료된 정확한 계산법.
    """
    rsi_price = wilder_rsi(close, rsi_len)
    streak_rsi = wilder_rsi(updown_streak(close), updown_len)
    roc1 = (close / close.shift(1) - 1) * 100   # 1봉 변동률(%)
    pr = percentrank_incl_lt(roc1, roc_len)
    return (rsi_price + streak_rsi + pr) / 3


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length).mean()


def bollinger_upper(close: pd.Series, length: int = 20, mult: float = 2.0) -> pd.Series:
    """볼린저밴드 상단 = SMA(length) + mult * 표준편차. 트레이딩뷰는 모집단 표준편차(ddof=0)."""
    mid = close.rolling(window=length).mean()
    std = close.rolling(window=length).std(ddof=0)
    return mid + mult * std


def ichimoku_spans(high: pd.Series, low: pd.Series):
    """
    일목균형표 선행스팬1, 2 (현재 캔들에 표시되는 구름).
    전환선=(9기간 고저 평균), 기준선=(26기간 고저 평균)
    선행스팬1=(전환+기준)/2 를 26봉 앞으로
    선행스팬2=(52기간 고저 평균) 를 26봉 앞으로
    → 현재 캔들 기준 구름은 26봉 전 데이터로 계산된 값.
    """
    h, l = high.values, low.values
    n = len(h)
    conv = np.full(n, np.nan)
    base = np.full(n, np.nan)
    for i in range(n):
        if i >= 8:
            conv[i] = (np.max(h[i-8:i+1]) + np.min(l[i-8:i+1])) / 2
        if i >= 25:
            base[i] = (np.max(h[i-25:i+1]) + np.min(l[i-25:i+1])) / 2
    span1 = np.full(n, np.nan)
    span2 = np.full(n, np.nan)
    for i in range(n):
        if i >= 26 and not np.isnan(conv[i-26]) and not np.isnan(base[i-26]):
            span1[i] = (conv[i-26] + base[i-26]) / 2
        if i >= 26 + 51:
            span2[i] = (np.max(h[i-26-51:i-26+1]) + np.min(l[i-26-51:i-26+1])) / 2
    return pd.Series(span1, index=high.index), pd.Series(span2, index=high.index)
