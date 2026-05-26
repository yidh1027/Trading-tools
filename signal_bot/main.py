"""
MA 전략 신호 봇 — 메인 진입점
실행: GitHub Actions에서 15분마다 자동 실행

종목: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT
타임프레임: 15m, 30m, 4H, 1D
패턴: Pattern1 (눌림목 재진입), Pattern2 (추세 전환), Pattern3 (MA280 지지 재상승)
"""

import sys
import traceback
from datetime import datetime, timezone

from bybit_data import fetch_all, SYMBOLS, INTERVAL_MAP
from indicators import add_indicators, is_valid
from pattern1 import check_pattern1
from pattern2 import check_pattern2
from pattern3 import check_pattern3
from telegram_notify import send_message, build_signal_message, build_summary_message


PATTERNS = {
    "pattern1": check_pattern1,
    "pattern2": check_pattern2,
    "pattern3": check_pattern3,
}

TIMEFRAMES = list(INTERVAL_MAP.keys())  # ["15m", "30m", "4H", "1D"]


def run():
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*50}")
    print(f"  MA 전략 신호 봇 실행 — {now_utc}")
    print(f"{'='*50}")

    all_signals = []
    errors = []

    for tf in TIMEFRAMES:
        print(f"\n[타임프레임: {tf}] 데이터 수집 중...")
        data_map = fetch_all(tf)

        for symbol in SYMBOLS:
            if symbol not in data_map:
                print(f"  [{symbol}] 데이터 없음, 건너뜀")
                continue

            df_raw = data_map[symbol]
            df = add_indicators(df_raw)

            if not is_valid(df):
                print(f"  [{symbol}][{tf}] 지표 계산 불충분 (캔들 수: {len(df)})")
                continue

            current_price = df.iloc[-1]["close"]

            for pattern_name, check_fn in PATTERNS.items():
                try:
                    result = check_fn(df)

                    if result["signal"]:
                        print(f"  ✅ [{symbol}][{tf}][{pattern_name}] 신호 발생!")
                        msg = build_signal_message(
                            symbol=symbol,
                            interval=tf,
                            pattern=pattern_name,
                            reason=result["reason"],
                            atr=result.get("atr", 0.0),
                            current_price=current_price,
                        )
                        success = send_message(msg)
                        if success:
                            print(f"     텔레그램 발송 완료")
                        else:
                            print(f"     텔레그램 발송 실패")

                        all_signals.append({
                            "symbol": symbol,
                            "interval": tf,
                            "pattern": pattern_name,
                        })
                    else:
                        print(f"  — [{symbol}][{tf}][{pattern_name}]: {result['reason']}")

                except Exception as e:
                    err_msg = f"[{symbol}][{tf}][{pattern_name}] 오류: {e}"
                    print(f"  ❌ {err_msg}")
                    traceback.print_exc()
                    errors.append(err_msg)

    # ── 실행 요약 ──────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  스캔 완료 — 신호: {len(all_signals)}개 | 오류: {len(errors)}개")
    print(f"{'='*50}\n")

    # 신호가 없을 때도 요약 메시지 (선택: 주석 해제 시 매 실행마다 알림)
    # if not all_signals:
    #     send_message(build_summary_message(0, []))

    if errors:
        err_text = "⚠️ 오류 발생:\n" + "\n".join(errors[:5])  # 최대 5개만
        send_message(err_text)

    return len(all_signals)


if __name__ == "__main__":
    count = run()
    sys.exit(0)
