"""控制器抽象基类与注册中心。

新增交易所控制器：

1. 在 master/gateway/controllers/ 下新建文件。
2. 定义控制器类：

    from .base import GatewayControllerABC, registry

    @registry.register("exchange_code", "mdgw")
    class FooMdgwController(GatewayControllerABC):
        # 实现所有抽象方法

3. 导入即可（包级 __init__.py 会导入该文件触发注册）。
"""
from __future__ import annotations

import logging
import os
import shutil
import stat
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, ClassVar, Type, TypeVar

from ..core.models import (
    DeployParams,
    GatewayInstance,
    GatewayStatus,
    OperationResult,
    RollbackParams,
    UpgradeParams,
)

log = logging.getLogger(__name__)

Controller = TypeVar("Controller", bound="GatewayControllerABC")


class GatewayControllerRegistry:
    """按 (exchange, kind) -> 控制器类 的注册中心。"""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], Type[GatewayControllerABC]] = {}

    def register(
        self,
        exchange: str,
        kind: str,
    ) -> Callable[[Type[Controller]], Type[Controller]]:
        key = (exchange.lower(), kind.lower())

        def _wrap(cls: Type[Controller]) -> Type[Controller]:
            self._store[key] = cls
            log.debug("已注册控制器 %s -> %s", key, cls.__name__)
            return cls

        return _wrap

    def get(self, exchange: str, kind: str) -> Type[GatewayControllerABC]:
        key = (exchange.lower(), kind.lower())
        if key not in self._store:
            raise KeyError(
                f"未注册控制器: exchange={exchange}, kind={kind}; "
                f"已注册: {list(self._store.keys())}"
            )
        return self._store[key]

    def list_all(self) -> list[tuple[str, str, str]]:
        return [(e, k, cls.__name__) for (e, k), cls in self._store.items()]

    def make(
        self,
        instance: GatewayInstance,
        install_root: str | Path,
        backup_root: str | Path,
    ) -> GatewayControllerABC:
        cls = self.get(instance.exchange, instance.kind)
        return cls(instance, install_root, backup_root)


registry: ClassVar[GatewayControllerRegistry] = GatewayControllerRegistry()


class GatewayControllerABC(ABC):
    """网关控制器抽象基类。

    约定：
    - 子类必须实现 8 个抽象方法，并对自身 binary_name / monitor_port 提供默认值。
    - 所有对外操作返回 OperationResult（而不是抛异常），除非是编程错误。
    """

    binary_name: str = ""
    monitor_port_default: int = 0

    def __init__(
        self,
        instance: GatewayInstance,
        install_root: str | Path,
        backup_root: str | Path,
    ) -> None:
        self.instance = instance
        self.install_root = Path(install_root)
        self.backup_root = Path(backup_root)

        self.gateway_dir = Path(instance.gateway_dir)
        self.binary_path = self.gateway_dir / (instance.binary_name or self.binary_name)
        self.cfg_dir = self.gateway_dir / "cfg"
        self.config_path = self.cfg_dir / "config.xml"
        self.server_list_path = self.cfg_dir / "server_list.xml"
        self.ca_cert_path = self.cfg_dir / "ca.crt"

    # ---------- 抽象接口 ----------
    @abstractmethod
    def preflight(self) -> OperationResult: ...

    @abstractmethod
    def deploy(
        self,
        archive_path: str | Path,
        params: DeployParams,
    ) -> OperationResult: ...

    @abstractmethod
    def start(self) -> OperationResult: ...

    @abstractmethod
    def stop(self, force: bool = False) -> OperationResult: ...

    @abstractmethod
    def restart(self) -> OperationResult: ...

    @abstractmethod
    def upgrade(self, params: UpgradeParams) -> OperationResult: ...

    @abstractmethod
    def rollback(self, params: RollbackParams | str | Path) -> OperationResult: ...

    @abstractmethod
    def status(self) -> GatewayStatus: ...

    # ---------- 共享辅助 ----------
    def _ensure_executable(self, path: Path) -> None:
        if not path.exists():
            return
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _merge_zip_contents(
        self,
        archive_path: str | Path,
        dest_dir: Path,
    ) -> None:
        """解压 zip 到 dest_dir，若 zip 内只有一层子目录则扁平化其内容。"""
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # 先解压到临时目录，以避免污染
        import tempfile
        import zipfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(tmp_path)

            # 判断是否只有一层子目录
            entries = [p for p in tmp_path.iterdir()]
            if len(entries) == 1 and entries[0].is_dir():
                src_dir = entries[0]
            else:
                src_dir = tmp_path

            self._copy_tree(src_dir, dest_dir)

    def _copy_tree(self, src: Path, dst: Path) -> None:
        """递归复制 src 到 dst，存在同名文件/目录时覆盖。"""
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            target = dst / item.name
            if item.is_dir():
                self._copy_tree(item, target)
            else:
                if target.exists():
                    target.unlink()
                shutil.copy2(item, target)

    def _current_version_hint(self) -> str:
        if self.instance.version:
            return self.instance.version
        # 读取 .version 文件（如有）
        version_file = self.gateway_dir / ".version"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
        return "unknown"
