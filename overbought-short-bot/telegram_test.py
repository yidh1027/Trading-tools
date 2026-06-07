"""
텔레그램 전송 테스트 스크립트
─────────────────────────────────────────────
신호 조건과 무관하게, 토큰과 chat_id가 제대로 작동하는지만 확인한다.
무조건 테스트 메시지를 보내고, 성공/실패와 그 이유를 자세히 출력한다.

GitHub Actions에서 실행하면 Secrets의 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID를 사용.
"""

import os
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")


def main():
    print("=== 텔레그램 전송 테스트 ===")

    # 1. Secret이 비어있는지 확인
    print(f"\n[1] Secret 존재 여부 확인")
    if not TG_TOKEN:
        print("  ❌ TELEGRAM_BOT_TOKEN 이 비어있음! Secret 등록 확인 필요")
    else:
        # 토큰 일부만 출력 (보안)
        masked = TG_TOKEN[:8] + "..." + TG_TOKEN[-4:] if len(TG_TOKEN) > 12 else "너무짧음"
        print(f"  ✅ TELEGRAM_BOT_TOKEN 존재 (형식: {masked}, 길이: {len(TG_TOKEN)})")
    if not TG_CHAT:
        print("  ❌ TELEGRAM_CHAT_ID 가 비어있음! Secret 등록 확인 필요")
    else:
        print(f"  ✅ TELEGRAM_CHAT_ID 존재 (값: {TG_CHAT})")

    if not TG_TOKEN or not TG_CHAT:
        print("\n→ Secret이 비어있습니다. GitHub Settings에서 등록하세요.")
        return

    # 2. 봇 토큰이 유효한지 확인 (getMe API)
    print(f"\n[2] 봇 토큰 유효성 확인 (getMe)")
    try:
        r = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=15)
        data = r.json()
        if data.get("ok"):
            bot_name = data["result"].get("username", "?")
            print(f"  ✅ 토큰 유효. 봇 이름: @{bot_name}")
        else:
            print(f"  ❌ 토큰 무효! 응답: {data}")
            print("  → 봇 토큰이 잘못되었습니다. BotFather에서 토큰 재확인 필요.")
            return
    except Exception as e:
        print(f"  ❌ 요청 실패: {e}")
        return

    # 3. 실제 메시지 전송
    print(f"\n[3] 테스트 메시지 전송 (chat_id: {TG_CHAT})")
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    text = (
        f"🧪 <b>텔레그램 연결 테스트</b>\n\n"
        f"이 메시지가 보이면 봇 설정이 정상입니다.\n"
        f"시각: {now} (KST)"
    )
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        data = r.json()
        if data.get("ok"):
            print(f"  ✅ 전송 성공! 텔레그램을 확인하세요.")
        else:
            print(f"  ❌ 전송 실패! HTTP {r.status_code}")
            print(f"  응답: {data}")
            # 흔한 원인 안내
            desc = data.get("description", "")
            if "chat not found" in desc.lower():
                print("  → 원인: chat_id가 잘못되었습니다.")
                print("     봇과 먼저 대화를 시작했는지, chat_id 값이 정확한지 확인하세요.")
            elif "bot was blocked" in desc.lower():
                print("  → 원인: 사용자가 봇을 차단했습니다. 차단 해제 필요.")
            elif "unauthorized" in desc.lower():
                print("  → 원인: 봇 토큰이 잘못되었습니다.")
    except Exception as e:
        print(f"  ❌ 전송 중 예외 발생: {e}")

    print("\n=== 테스트 완료 ===")


if __name__ == "__main__":
    main()
