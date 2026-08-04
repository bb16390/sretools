"""北交所 tgw 网关控制器（预留实现）。"""
from __future__ import annotations

from pathlib import Path

from ..core.models import (
    DeployParams,
    GatewayStatus,
    OperationResult,
    RollbackParams,
    UpgradeParams,
)
from .base import GatewayControllerABC, registry


@registry.register("bjse", "tgw")
class BjseTgwController(GatewayControllerABC):
    binary_name = "tgw"
    monitor_port_default = 7500

    def preflight(self) -> OperationResult:
        raise NotImplementedError("bjse tgw 控制器待实现")

    def deploy(self, archive_path: str | Path, params: DeployParams) -> OperationResult:
        raise NotImplementedError("bjse tgw 控制器待实现")

    def start(self) -> OperationResult:
        raise NotImplementedError("bjse tgw 控制器待实现")

    def stop(self, force: bool = False) -> OperationResult:
        raise NotImplementedError("bjse tgw 控制器待实现")

    def restart(self) -> OperationResult:
        raise NotImplementedError("bjse tgw 控制器待实现")

    def upgrade(self, params: UpgradeParams) -> OperationResult:
        raise NotImplementedError("bjse tgw 控制器待实现")

    def rollback(self, params: RollbackParams | str | Path) -> OperationResult:
        raise NotImplementedError("bjse tgw 控制器待实现")

    def status(self) -> GatewayStatus:
        raise NotImplementedError("bjse tgw 控制器待实现")
