# Adding a Channel

This guide explains how to develop a new messaging channel adapter for Echo Agent to integrate with a new IM platform or communication protocol.

## Architecture Overview

```
echo_agent/channels/
├── base.py              # BaseChannel abstract base class
├── manager.py           # ChannelManager — unified management
├── telegram.py          # Reference implementation: Telegram
├── webhook.py           # Reference implementation: Generic Webhook
└── your_channel.py      # ← Your new channel
```

Message flow:

```
User message → Channel.start() listening
             → Construct InboundEvent
             → bus.publish_inbound(InboundEvent)
             → AgentLoop processes
             → OutboundEvent
             → Channel.send(OutboundEvent) → User
```

## BaseChannel Interface

```python
class BaseChannel(ABC):
    # Class attribute declarations
    name: str = "base"                        # Unique channel identifier
    supports_edit: bool = False               # Whether message editing is supported
    supports_reactions: bool = False           # Whether emoji reactions are supported
    is_realtime: bool = True                  # False for async channels (email/cron)
    supports_interactive_choices: bool = False # Whether interactive selections are supported
    supports_files: bool = False              # Whether file uploads are supported

    def __init__(self, config: Any, bus: MessageBus):
        self.config = config
        self.bus = bus

    @abstractmethod
    async def start(self) -> None:
        """Start listening."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop and clean up resources."""

    @abstractmethod
    async def send(self, event: OutboundEvent) -> SendResult | None:
        """Send a message through this channel."""
```

## Step 1: Create the Channel Adapter

Create a new file under `echo_agent/channels/`, e.g., `line.py`:

```python
"""LINE Messaging API channel adapter."""

from __future__ import annotations

import hmac
import hashlib
from typing import Any

import aiohttp
from aiohttp import web
from loguru import logger

from echo_agent.bus.events import InboundEvent, OutboundEvent, ContentBlock, ContentType
from echo_agent.bus.queue import MessageBus
from echo_agent.channels.base import BaseChannel, SendResult


class LineChannel(BaseChannel):
    name = "line"
    supports_edit = False
    supports_reactions = True
    is_realtime = True
    supports_files = True

    def __init__(self, config: Any, bus: MessageBus):
        super().__init__(config, bus)
        self._token: str = config.channel_token or ""
        self._secret: str = config.channel_secret or ""
        self._webhook_path: str = "/webhook/line"
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        """Register webhook route and start listening."""
        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._token}"}
        )
        self._running = True
        logger.info("LINE channel started")

    async def stop(self) -> None:
        """Close HTTP session."""
        self._running = False
        if self._session:
            await self._session.close()
            self._session = None

    async def handle_webhook(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """Handle LINE Webhook callback."""
        body = await request.read()

        # Verify signature
        if not self._verify_signature(body, request.headers.get("X-Line-Signature", "")):
            return aiohttp.web.Response(status=403)

        data = await request.json()
        for event in data.get("events", []):
            if event["type"] == "message" and event["message"]["type"] == "text":
                try:
                    inbound = self._build_event(
                        sender_id=event["source"]["userId"],
                        chat_id=event["source"]["userId"],
                        text=event["message"]["text"],
                        metadata={"message_id": event["message"]["id"]},
                    )
                except PermissionError:
                    continue
                if not await self.bus.publish_inbound(inbound):
                    return web.Response(status=503)


        return aiohttp.web.Response(status=200)

    async def send(self, event: OutboundEvent) -> SendResult | None:
        """Send message via LINE Push API."""
        if not self.should_deliver(event):
            return SendResult(success=True, skipped=True)

        if not self._session:
            return SendResult(success=False, error="Session not initialized")

        payload = {
            "to": event.chat_id,
            "messages": [{"type": "text", "text": event.text}],
        }

        try:
            async with self._session.post(
                "https://api.line.me/v2/bot/message/push",
                json=payload,
            ) as resp:
                if resp.status == 200:
                    return SendResult(success=True)
                else:
                    body = await resp.text()
                    return SendResult(success=False, error=f"LINE API {resp.status}: {body}")
        except Exception as e:
            logger.error("LINE send error: {}", e)
            return SendResult(success=False, error=str(e))

    def _verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify LINE Webhook signature."""
        digest = hmac.new(
            self._secret.encode(),
            body,
            hashlib.sha256,
        ).digest()
        import base64
        expected = base64.b64encode(digest).decode()
        return hmac.compare_digest(signature, expected)
```

## Step 2: Register and configure

Register the class in `_CHANNEL_REGISTRY` in `channels/manager.py`. Add a matching nested field to `ChannelsConfig`; `start_all()` looks up that exact name. There is no automatic plugin-channel discovery or flat `line_enabled` configuration.

```python
class LineChannelConfig(_Base):
    enabled: bool = False
    channel_token: str = ""
    channel_secret: str = ""
    allow_from: list[str] = Field(default_factory=list)

class ChannelsConfig(_Base):
    line: LineChannelConfig = Field(default_factory=LineChannelConfig)
```

This hypothetical adapter also needs its webhook route wired to an owned aiohttp server, validated configuration, diagnostics and tests before it can be used. `start()` creating a ClientSession alone does not register an inbound HTTP endpoint.

## Step 3: Optional capabilities

Declare `supports_edit` only when implementing the actual `edit_message(chat_id, message_id, text, *, metadata=None, finalize=False) -> SendResult` contract. Reactions use `send_reaction`/`remove_reaction`, not `add_reaction`. File support is implemented inside `send(event)` and declared with `supports_files`; there is no BaseChannel `send_file` method to override.

Keep all allocated sessions, listeners, tasks and subprocesses under explicit ownership; `stop()` cancels and joins tasks before closing their connections. A failed start must release partially allocated resources.

## should_deliver Mechanism

`BaseChannel` has built-in message filtering logic:

- Channels with `supports_edit=True`: receive all messages (intermediate results can be overwritten)
- Channels with `supports_edit=False`: only receive `is_final=True` messages + heartbeat + approval_prompt

You don't need to override this logic unless you have special requirements.

## SendResult Specification

```python
@dataclass
class SendResult:
    success: bool               # Whether delivery succeeded
    message_id: str = ""        # Platform-returned message ID (for subsequent editing)
    error: str = ""             # Error message
    skipped: bool = False       # Whether skipped by should_deliver
```

## Step 5: Write Tests

```python
"""tests/test_line_channel.py"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from echo_agent.channels.line import LineChannel
from echo_agent.bus.events import OutboundEvent


@pytest.fixture
def channel():
    config = MagicMock()
    config.channel_token = "test-token"
    config.channel_secret = "test-secret"
    config.transcription_api_key = ""
    bus = MagicMock()
    return LineChannel(config, bus)


@pytest.mark.asyncio
async def test_send_success(channel):
    channel._session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 200
    channel._session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp)))

    event = OutboundEvent.text_reply(channel="line", chat_id="user123", text="Hello")
    result = await channel.send(event)
    assert result.success


@pytest.mark.asyncio
async def test_send_skipped_non_final(channel):
    event = OutboundEvent.text_reply(channel="line", chat_id="user123", text="thinking...", is_final=False)
    result = await channel.send(event)
    assert result.skipped  # supports_edit=False skips non-final
```

## Adapter example boundaries

Use `_build_event` for sender admission and internal-metadata stripping. Authenticated native ingress should use `_native_event_id` and declare `authenticated_ingress` so durable turns identify redelivery; acknowledge only after Runtime admission. Timeouts, server errors and missing receipts must use the existing delivery ledger's UNKNOWN/partial outcomes rather than blind replay. Keep confirmed multipart receipts. Stop cancels and joins owned tasks before closing connections.

## Checklist

- [ ] Inherit `BaseChannel`, implement `start()`, `stop()`, `send()`
- [ ] Set `name` (unique identifier)
- [ ] Correctly declare `supports_edit` / `supports_files` / `is_realtime`
- [ ] Webhook signature verification (security)
- [ ] Correctly construct `InboundEvent` and publish to bus
- [ ] Call `self.should_deliver()` in `send()` for filtering
- [ ] Return proper `SendResult` (include message_id to support editing)
- [ ] Register in ChannelManager
- [ ] Add configuration fields
- [ ] Resource cleanup (close sessions in stop)
- [ ] Write unit tests

## On out-of-tree channel packages

`echo_agent.channels.manager` exports `register_channel_type(name, cls)`, which inserts a channel type into the registry at runtime. The plugin system is not wired to it: nothing in the repository calls it, and a plugin's entry point does not register channels automatically.

In practice, then, adding a channel means changing this repository — adding the class to `_CHANNEL_REGISTRY` and its fields to the configuration schema. Shipping a channel as a separate package would require calling `register_channel_type()` from the package's own initialisation and arranging for its configuration fields yourself. That path is neither supported nor covered by tests.
