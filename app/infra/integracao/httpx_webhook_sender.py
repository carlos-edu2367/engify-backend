"""Sender de webhook baseado em httpx."""
import httpx

from app.application.services.webhook_dispatcher import WebhookSender

_TIMEOUT = httpx.Timeout(10.0)


class HttpxWebhookSender(WebhookSender):
    async def post(self, url: str, body: str, headers: dict) -> int:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, content=body.encode("utf-8"), headers=headers)
            return resp.status_code
