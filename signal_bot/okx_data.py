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


def fetch_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
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
                raise ValueError(f"OKX API 오류: code={data.get('code')}, msg={data.get('msg')}")

            rows = data.get("data", [])
            if not rows:
                print(f"[{symbol}][{interval}] 빈 데이터 응답")
                return pd.DataFrame()

            # 인덱스로 파싱 (컬럼 수 변동 대응)
            # OKX 응답: [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
            df = pd.DataFrame(rows)
            df = df.iloc[:, [0, 1, 2, 3, 4, 5]].copy()
            df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)

            # OKX는 최신순 반환 → 오름차순 정렬
            df = df.sort_values("timestamp").reset_index(drop=True)

            print(f"[{symbol}][{interval}] 수집 완료: {len(df)}봉")
            return df

        except Exception as e:
            print(f"[{symbol}][{interval}] 데이터 수집 실패 ({attempt+1}/3): {e}")
            traceback.print_exc()
            time.sleep(2)

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
