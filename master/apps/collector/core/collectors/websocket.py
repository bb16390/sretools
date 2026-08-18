"""WebSocket 采集器：建立 WebSocket 长连接采集消息。"""
from __future__ import annotations

import asyncio
from typing import Any

from .base import BaseCollector, CollectorResult

try:
    import websockets  # type: ignore
    HAS_WEBSOCKETS = True
except ImportError:  # pragma: no cover
    HAS_WEBSOCKETS = False


class WebSocketCollector(BaseCollector):
    """通过 WebSocket 连接采集消息。

    config 字段：
        uri (必填): ws:// 或 wss:// 地址
        message (可选): 连接建立后发送的订阅消息（字符串或 JSON 可序列化对象）
        message_count: 采集多少条消息后结束并返回，默认 1
                          设置为 0 表示按 duration 持续收；若都为 0 则收 1 条。
        duration: 最长采集持续时间(秒)，默认 10；超过后停止并返回已收集消息
        headers: 连接握手时的 HTTP 头 dict
        subprotocols: 子协议列表
        timeout: 连接/读取超时秒数，默认 30
        as_json: 是否按 JSON 解析每条消息，默认 True
    """

    type_name = "websocket"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        if "uri" not in config:
            raise ValueError("WebSocketCollector config: 'uri' is required")
        if not HAS_WEBSOCKETS:
            raise ImportError("websockets package is required for WebSocketCollector")

    async def collect(self) -> CollectorResult:
        uri = self.config["uri"]
        subprotocols = self.config.get("subprotocols") or None
        headers = self.config.get("headers") or None
        connect_timeout = self.config.get("timeout", 30)
        duration = float(self.config.get("duration", 10))
        message_count = int(self.config.get("message_count", 1))
        subscribe_msg = self.config.get("message")
        as_json = bool(self.config.get("as_json", True))

        collected: list[Any] = []

        async with websockets.connect(  # type: ignore[union-attr]
            uri,
            subprotocols=subprotocols,
            additional_headers=headers,
            open_timeout=connect_timeout,
            close_timeout=5,
        ) as ws:
            if subscribe_msg is not None:
                if isinstance(subscribe_msg, (dict, list)):
                    import json
                    await ws.send(json.dumps(subscribe_msg))
                else:
                    await ws.send(str(subscribe_msg))

            async def _recv_loop():
                stop_marker = object()
                try:
                    while True:
                        if message_count > 0 and len(collected) >= message_count:
                            return
                        try:
                            msg = await asyncio.wait_for(
                                ws.recv(), timeout=connect_timeout,
                            )
                        except asyncio.TimeoutError:
                            return
                        except Exception:
                            return
                        if as_json and isinstance(msg, str):
                            try:
                                import json
                                collected.append(json.loads(msg))
                            except Exception:
                                collected.append(msg)
                        else:
                            collected.append(msg)
                finally:
                    pass

            try:
                await asyncio.wait_for(_recv_loop(), timeout=duration or None)
            except asyncio.TimeoutError:
                pass

        if message_count == 1 and len(collected) == 1:
            data = collected[0]
        else:
            data = collected
        return CollectorResult(data=data)

    async def close(self) -> None:
        return
