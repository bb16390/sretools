"""网关实例存储（JSON 文件）。

API 与 amis-admin 共用该模块不直接依赖 FastAPI / pydantic。
"""
from __future__ import annotations

import json
import threading
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import GatewayInstance


class InstanceStore:
    """简单的 JSON 文件持久化。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")
        self._lock = threading.Lock()

    def _read(self) -> dict[str, dict[str, Any]]:
        try:
            raw = self.path.read_text(encoding="utf-8").strip() or "{}"
            return json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        tmp = Path(str(self.path) + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(str(tmp), str(self.path))

    # --- CRUD ---
    def list(self) -> list[GatewayInstance]:
        with self._lock:
            data = self._read()
        result: list[GatewayInstance] = []
        for key, payload in data.items():
            try:
                result.append(
                    GatewayInstance(
                        id=key,
                        exchange=payload["exchange"],
                        kind=payload["kind"],
                        name=payload["name"],
                        gateway_dir=payload["gateway_dir"],
                        binary_name=payload["binary_name"],
                        monitor_port=int(payload["monitor_port"]),
                        version=payload.get("version"),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return result

    def get(self, instance_id: str) -> GatewayInstance | None:
        with self._lock:
            data = self._read()
        payload = data.get(instance_id)
        if not payload:
            return None
        return GatewayInstance(
            id=instance_id,
            exchange=payload["exchange"],
            kind=payload["kind"],
            name=payload["name"],
            gateway_dir=payload["gateway_dir"],
            binary_name=payload["binary_name"],
            monitor_port=int(payload["monitor_port"]),
            version=payload.get("version"),
        )

    def upsert(self, instance: GatewayInstance) -> None:
        with self._lock:
            data = self._read()
            data[instance.id] = asdict(instance)
            # 用 default=str 处理 datetime
            self._write(data)

    def delete(self, instance_id: str) -> bool:
        with self._lock:
            data = self._read()
            if instance_id not in data:
                return False
            data.pop(instance_id)
            self._write(data)
            return True


# 全局默认实例。
_default_store: InstanceStore | None = None


def get_default_store(root: str | Path | None = None) -> InstanceStore:
    global _default_store
    if _default_store is None:
        root = root or (Path(__file__).resolve().parent.parent.parent / "data" / "gateway_instances.json")
        _default_store = InstanceStore(root)
    return _default_store
