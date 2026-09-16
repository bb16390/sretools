"""采集任务预览 token 签发与校验辅助模块。

master 端预览接口（``CollectorTaskAdmin.preview``）在完成试采 +
``transform_script`` 转换后，调用 :func:`issue_preview_token` 签发一个
短期 token；创建任务接口（``on_create_pre`` 钩子）通过
:func:`consume_preview_token` 校验该 token，确保任务创建前已成功预览。

token 缓存为进程内字典（``_tokens``），30 分钟 TTL，由一个 daemon 线程
定期清理过期项。多协程并发消费同一 token 时，仅有一个消费成功（通过
``_lock`` 保证 pop 的原子性），符合 "preview -> create" 的一次性使用语义。
"""

import logging
import secrets
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_TOKEN_TTL = 1800  # 30 分钟

# token -> {"payload": {...}, "expires_at": float}
_tokens: Dict[str, dict] = {}
_lock = threading.Lock()
_cleaner_started = False


def _ensure_cleaner() -> None:
    """启动后台 daemon 线程定期清理过期 token。

    使用模块级 ``_cleaner_started`` 标志 + ``_lock`` 保证只启动一次；
    即便标志读取与设置之间存在竞态，最坏情况也只是多启动一个 daemon
    线程，不影响正确性。
    """
    global _cleaner_started
    with _lock:
        if _cleaner_started:
            return
        _cleaner_started = True

    def _purge_loop():
        while True:
            try:
                now = time.time()
                with _lock:
                    expired = [t for t, v in _tokens.items() if v["expires_at"] <= now]
                    for t in expired:
                        _tokens.pop(t, None)
            except Exception as exc:  # noqa: BLE001
                logger.warning("preview token cleaner error: %s", exc)
            time.sleep(300)

    threading.Thread(target=_purge_loop, daemon=True, name="preview-token-cleaner").start()
    logger.debug("preview token cleaner started")


def issue_preview_token(payload: dict) -> str:
    """签发一个预览 token，携带预览结果 payload。

    Args:
        payload: 预览结果快照，应包含 ``success`` / ``raw_rows_count`` /
            ``rows_count`` / ``worker_id`` / ``conf_snapshot`` /
            ``transform_script`` 等字段。

    Returns:
        生成的 token 字符串（``secrets.token_urlsafe(16)``）。
    """
    token = secrets.token_urlsafe(16)
    expires_at = time.time() + _TOKEN_TTL
    with _lock:
        _tokens[token] = {"payload": payload, "expires_at": expires_at}
    _ensure_cleaner()
    logger.debug("issued preview token, ttl=%ss", _TOKEN_TTL)
    return token


def consume_preview_token(token: str) -> Optional[dict]:
    """消费一个预览 token，返回其 payload。

    一次性语义：token 有效且未过期时，原子地 pop 并返回 payload；
    否则返回 None。空 token 直接返回 None。
    """
    if not token:
        return None
    now = time.time()
    with _lock:
        entry = _tokens.pop(token, None)
        if entry is None:
            return None
        if entry["expires_at"] <= now:
            return None
        return entry["payload"]
