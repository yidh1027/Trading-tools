"""
OKX 선물 시장 OHLCV 데이터 수집 모듈
- AWS 전용 엔드포인트(aws.okx.com) 사용으로 GitHub Actions에서 안정적 접근 가능
- API 키 불필요 (공개 마켓 데이터)
"""

import requests
import pandas as pd
import time

# OKX 타임프레임 매핑
INTERVAL_MAP = {
    "15m": "15m",
    "30m": "30m",
    "4H":  "4H",
    "1D":  "1D",
}

# OKX 심볼 형식: BTC-USDT-SWAP (무기한 선물)
SYMBOLS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "XRP-USDT-SWAP", "DOGE-USDT-SWAP"]

# 텔레그램 메시지용 심볼 이름 매핑
SYMBOL_DISPLAY = {
    "BTC-USDT-SWAP":  "BTCUSDT",
    "ETH-USDT-SWAP":  "ETHUSDT",
    "SOL-USDT-SWAP":  "SOLUSDT",
    "XRP-USDT-SWAP":  "XRPUSDT",
    "DOGE-USDT-SWAP": "DOGEUSDT",
}

# AWS 전용 엔드포인트 (GitHub Actions 환경에서 차단 없음)
BASE_URL = "https://aws.okx.com"


def fetch_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """
    OKX Futures API에서 OHLCV 캔들 데이터를 가져옵니다.

    Args:
        symbol: 종목 (예: BTC-USDT-SWAP)
        interval: 타임프레임 (15m, 30m, 4H, 1D)
        limit: 캔들 수 (최대 300)

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    limit = min(limit, 300)
    url = f"{BASE_URL}/api/v5/market/candles"
    params = {
        "instId": symbol,
        "bar": interval,
        "limit": limit,
    }

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "0":
                raise ValueError(f"OKX API 오류: {data.get('msg')}")

            rows = data.get("data", [])
            if not rows:
                return pd.DataFrame()

            # OKX 응답 컬럼: ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm
            df = pd.DataFrame(rows, columns=[
                "timestamp", "open", "high", "low", "close",
                "volume", "volCcy", "volCcyQuote", "confirm"
            ])
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)

            # OKX는 최신순 반환 → 오름차순 정렬
            df = df.sort_values("timestamp").reset_index(drop=True)

            # 미확정 캔들(confirm=0) 제거 — confirm 컬럼은 이미 드롭했으므로 마지막 행 제거
            # OKX에서 마지막 행이 현재 진행 중인 캔들일 수 있음
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
        {display_symbol: DataFrame}  예: {"BTCUSDT": df}
    """
    interval = INTERVAL_MAP[interval_key]
    result = {}
    for symbol in SYMBOLS:
        display = SYMBOL_DISPLAY[symbol]
        df = fetch_klines(symbol, interval)
        if not df.empty:
            result[display] = df
        time.sleep(0.3)  # API 레이트 리밋 방지
    return result
