"""网关控制核心数据模型。

全部使用 dataclass，避免在 core 层引入 FastAPI/pydantic 依赖。
API 层需要时可自行转换为 pydantic BaseModel。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class GatewayInstance:
    id: str
    exchange: str
    kind: str
    name: str
    gateway_dir: str
    binary_name: str
    monitor_port: int
    version: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DeployParams:
    gwid: str
    password: str = ""
    env_id: int = 0
    level: int = 2
    access_mode: str = "TCP"
    line_type: str = "地面"
    local_ip: str = "127.0.0.1"
    overrides: dict[str, Any] | None = None
    server_list_groups: list[dict[str, Any]] | None = None


@dataclass
class UpgradeParams:
    new_archive: str
    version: str | None = None
    timeout: int = 300


@dataclass
class RollbackParams:
    manifest_path: str


@dataclass
class OperationResult:
    success: bool
    message: str
    details: dict[str, Any] | None = None
    manifest_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "details": self.details,
            "manifest_path": self.manifest_path,
        }


@dataclass
class GatewayStatus:
    running: bool
    pid: int | None
    monitor_port: int
    monitor_accessible: bool = False
    gateway_dir: str = ""
    version: str | None = None
    memory_mb: float | None = None
    uptime_seconds: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "pid": self.pid,
            "monitor_port": self.monitor_port,
            "monitor_accessible": self.monitor_accessible,
            "gateway_dir": self.gateway_dir,
            "version": self.version,
            "memory_mb": self.memory_mb,
            "uptime_seconds": self.uptime_seconds,
        }
