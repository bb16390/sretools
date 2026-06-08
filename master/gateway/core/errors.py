"""网关控制异常体系。

错误码区间：
- E1001-E1099: 配置相关 (ConfigError)
- E2001-E2099: 二进制/依赖相关 (BinaryError)
- E3001-E3099: 端口/资源相关 (PortError，归类于 BinaryError)
- E4001-E4099: 进程启停相关 (ProcessError)
- E5001-E5099: 监控/探测相关 (ProcessError)
- E6001-E6099: 升级/回滚相关 (UpgradeError)
"""
from __future__ import annotations

from typing import Any


class GatewayError(Exception):
    """网关管理基础异常。"""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ConfigError(GatewayError):
    """配置解析/生成/校验错误 (E1001-E1099)。"""


class BinaryError(GatewayError):
    """二进制文件或动态依赖缺失/权限错误 (E2001-E3099)。"""


class ProcessError(GatewayError):
    """进程启停/状态相关错误 (E4001-E5099)。"""


class UpgradeError(GatewayError):
    """升级/回滚相关错误 (E6001-E6099)。"""
