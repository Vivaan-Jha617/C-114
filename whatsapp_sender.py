"""
Sends the wildlife sighting summary to a WhatsApp number via Twilio.
"""

import logging

from twilio.rest import Client

logger = logging.getLogger(__name__)


class WhatsAppSender:
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        to_number: str,
    ):
        self.client = Client(account_sid, auth_token)
        # Twilio requires numbers in E.164 format prefixed with "whatsapp:"
        self.from_whatsapp = f"whatsapp:{from_number}"
        self.to_whatsapp = f"whatsapp:{to_number}"

    def send(self, message: str) -> str:
        """Send a WhatsApp message and return the Twilio message SID."""
        # WhatsApp messages are capped at ~4096 chars; Twilio recommends ≤1600.
        # Split if the summary is unusually long.
        chunks = _split_message(message, max_len=1500)
        sids: list[str] = []
        for chunk in chunks:
            msg = self.client.messages.create(
                from_=self.from_whatsapp,
                to=self.to_whatsapp,
                body=chunk,
            )
            logger.info("WhatsApp message sent — SID: %s", msg.sid)
            sids.append(msg.sid)
        return ", ".join(sids)


def _split_message(text: str, max_len: int = 1500) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    return parts
