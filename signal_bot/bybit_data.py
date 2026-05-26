"""
Bybit 선물 시장 OHLCV 데이터 수집 모듈
"""

import requests
import pandas as pd
import time

# Bybit 타임프레임 매핑
INTERVAL_MAP = {
    "15m": "15",
    "30m": "30",
    "4H": "240",
    "1D": "D",
}

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]


def fetch_klines(symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
    """
    Bybit v5 API에서 OHLCV 캔들 데이터를 가져옵니다.

    Args:
        symbol: 종목 (예: BTCUSDT)
        interval: 타임프레임 (15, 30, 240, D)
        limit: 캔들 수 (최대 200, 기본 300→200으로 제한)

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    limit = min(limit, 200)
    url = "https://api.bybit.com/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get("retCode") != 0:
                raise ValueError(f"Bybit API 오류: {data.get('retMsg')}")

            rows = data["result"]["list"]
            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
            df = df.drop(columns=["turnover"])
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)

            # Bybit는 최신순으로 반환 → 오름차순 정렬
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df

        except Exception as e:
            print(f"[{symbol}][{interval}] 데이터 수집 실패 ({attempt+1}/3): {e}")
            time.sleep(2)

    return pd.DataFrame()


def fetch_all(interval_key: str) -> dict:
    """
    모든 종목의 데이터를 한 번에 수집합니다.

    Args:
        interval_key: "15m", "30m", "4H", "1D"

    Returns:
        {symbol: DataFrame}
    """
    interval = INTERVAL_MAP[interval_key]
    result = {}
    for symbol in SYMBOLS:
        df = fetch_klines(symbol, interval)
        if not df.empty:
            result[symbol] = df
        time.sleep(0.2)  # API 레이트 리밋 방지
    return result
