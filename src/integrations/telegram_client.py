from __future__ import annotations

import logging

import httpx


# httpx logs full request URLs at INFO; Telegram embeds the bot token in its URL.
logging.getLogger("httpx").setLevel(logging.WARNING)


class TelegramError(RuntimeError):
    pass


def send_telegram_message(bot_token: str, chat_id: str, message: str) -> None:
    if not bot_token or not chat_id:
        raise TelegramError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be configured")
    if not message.strip():
        raise TelegramError("Telegram report cannot be empty")
    chunks = [message[index : index + 4000] for index in range(0, len(message), 4000)]
    with httpx.Client(timeout=20.0) as client:
        for chunk in chunks:
            response = client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
            )
            if response.status_code >= 400:
                raise TelegramError(f"Telegram rejected the report ({response.status_code})")
