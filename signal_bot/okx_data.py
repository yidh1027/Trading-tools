"""
OKX 선물 시장 OHLCV 데이터 수집 모듈
- API 키 불필요 (공개 마켓 데이터)
"""

import requests
import pandas as pd
import time
import traceback

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

# OKX 공개 API 엔드포인트
BASE_URL = "https://www.okx.com"


def fetch_klines(symbol: str, interval: str, limit: int = 400) -> pd.DataFrame:
    """
    OKX Futures API에서 OHLCV 캔들 데이터를 가져옵니다.
    OKX는 1회 최대 300봉 제한이 있어 2회 호출로 400봉을 수집합니다.
    """
    url = f"{BASE_URL}/api/v5/market/candles"

    def _fetch_once(after: str = None) -> list:
        params = {"instId": symbol, "bar": interval, "limit": 300}
        if after:
            params["after"] = after  # 해당 타임스탬프 이전 데이터 요청
        for attempt in range(3):
            try:
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != "0":
                    raise ValueError(f"OKX API 오류: code={data.get('code')}, msg={data.get('msg')}")
                return data.get("data", [])
            except Exception as e:
                print(f"[{symbol}][{interval}] 데이터 수집 실패 ({attempt+1}/3): {e}")
                traceback.print_exc()
                time.sleep(2)
        return []

    # 1차 호출: 최신 300봉
    rows1 = _fetch_once()
    if not rows1:
        return pd.DataFrame()

    # 2차 호출: 1차의 가장 오래된 타임스탬프 이전 100봉
    oldest_ts = rows1[-1][0]  # OKX는 최신순 반환이므로 마지막이 가장 오래됨
    rows2 = _fetch_once(after=oldest_ts)

    all_rows = rows1 + rows2  # 합치기

    try:
        df = pd.DataFrame(all_rows)
        df = df.iloc[:, [0, 1, 2, 3, 4, 5]].copy()
        df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        # 중복 제거 후 오름차순 정렬
        df = df.drop_duplicates(subset=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        print(f"[{symbol}][{interval}] 수집 완료: {len(df)}봉")
        return df
    except Exception as e:
        print(f"[{symbol}][{interval}] 파싱 실패: {e}")
        traceback.print_exc()
        return pd.DataFrame()


def fetch_all(interval_key: str) -> dict:
    interval = INTERVAL_MAP[interval_key]
    result = {}
    for symbol in SYMBOLS:
        display = SYMBOL_DISPLAY[symbol]
        df = fetch_klines(symbol, interval)
        if not df.empty:
            result[display] = df
        time.sleep(0.3)
    return result
