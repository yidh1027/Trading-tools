"""
텔레그램 알림 발송 모듈
"""

import os
import requests


def send_message(text: str) -> bool:
    """
    텔레그램 봇으로 메시지를 발송합니다.

    환경변수:
        TELEGRAM_BOT_TOKEN
        TELEGRAM_CHAT_ID
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[텔레그램] 환경변수 TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 미설정")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[텔레그램] 발송 실패: {e}")
        return False


def build_signal_message(
    symbol: str,
    interval: str,
    pattern: str,
    reason: str,
    atr: float,
    current_price: float,
) -> str:
    """
    신호 알림 메시지를 포맷팅합니다.
    """
    # 종목 이모지
    emoji_map = {
        "BTCUSDT": "₿",
        "ETHUSDT": "Ξ",
        "SOLUSDT": "◎",
        "XRPUSDT": "✕",
        "DOGEUSDT": "🐶",
    }
    emoji = emoji_map.get(symbol, "💹")

    # 패턴 설명
    pattern_desc = {
        "pattern1": "📈 눌림목 재진입 (Pattern 1)",
        "pattern2": "🔄 추세 전환 포착 (Pattern 2)",
        "pattern3": "🛡️ MA280 지지 재상승 (Pattern 3)",
    }
    pattern_name = pattern_desc.get(pattern, pattern)

    # 손절/익절 설명
    stop_desc = "MA280 하향 돌파 시 손절"
    tp_desc = f"ATR 트레일링 스탑 (ATR: {atr:.4f})" if atr > 0 else "ATR 트레일링 스탑"

    msg = (
        f"🚨 <b>MA 전략 신호 발생</b>\n"
        f"{'─' * 28}\n"
        f"{emoji} <b>{symbol}</b>  |  ⏱ {interval}\n"
        f"{pattern_name}\n\n"
        f"💰 현재가: <b>{current_price:,.4f}</b>\n"
        f"🎯 진입: 다음 캔들 시가 <b>롱</b>\n\n"
        f"🛑 손절: {stop_desc}\n"
        f"✅ 익절: {tp_desc}\n\n"
        f"📋 <i>{reason}</i>"
    )
    return msg


def build_summary_message(total: int, signals: list) -> str:
    """
    실행 요약 메시지 (신호 없을 때도 주기적으로 발송 가능)
    """
    if total == 0:
        return "🔍 MA 전략 스캔 완료 — 신호 없음"

    lines = [f"📊 <b>MA 전략 스캔 결과: {total}개 신호</b>\n"]
    for s in signals:
        lines.append(f"• {s['symbol']} [{s['interval']}] {s['pattern']}")
    return "\n".join(lines)
