"""深交所 mdgw（行情网关）控制器。"""
from __future__ import annotations

import json
import logging
import socket
from datetime import datetime
from pathlib import Path

from ..core.config_tools import (
    extract_version_from_archive,
    find_binary_in_zip,
    render_config,
    select_mdgw_template,
)
from ..core.errors import BinaryError, ConfigError, ProcessError, UpgradeError
from ..core.models import (
    DeployParams,
    GatewayStatus,
    OperationResult,
    RollbackParams,
    UpgradeParams,
)
from ..core.process import GatewayProcess
from .base import GatewayControllerABC, registry

log = logging.getLogger(__name__)


@registry.register("szse", "mdgw")
class SzseMdgwController(GatewayControllerABC):
    binary_name = "mdgw"
    monitor_port_default = 7501

    # ---------- 基础 ----------
    def _process(self) -> GatewayProcess:
        return GatewayProcess(
            gateway_dir=self.gateway_dir,
            binary_name=self.instance.binary_name or self.binary_name,
            monitor_port=self.instance.monitor_port or self.monitor_port_default,
        )

    # ---------- 接口实现 ----------
    def preflight(self) -> OperationResult:
        issues: list[str] = []
        if not self.binary_path.exists():
            issues.append(f"二进制文件不存在: {self.binary_path}")
        elif not _is_executable(self.binary_path):
            issues.append(f"二进制文件没有执行权限: {self.binary_path}")
        if not self.ca_cert_path.exists():
            issues.append(f"CA 证书不存在: {self.ca_cert_path}")
        if not self.config_path.exists():
            issues.append(f"配置文件不存在: {self.config_path}")
        if _port_in_use(self.instance.monitor_port or self.monitor_port_default):
            issues.append(
                f"监控端口 {self.instance.monitor_port or self.monitor_port_default} 被占用"
            )
        if issues:
            return OperationResult(
                success=False,
                message="; ".join(issues),
                details={"issues": issues},
            )
        return OperationResult(success=True, message="preflight ok")

    def deploy(
        self,
        archive_path: str | Path,
        params: DeployParams,
    ) -> OperationResult:
        try:
            archive_path = Path(archive_path)
            if not archive_path.exists():
                raise ConfigError("E1004", f"部署包不存在: {archive_path}")

            self.gateway_dir.mkdir(parents=True, exist_ok=True)
            self._merge_zip_contents(archive_path, self.gateway_dir)

            # 选模板并渲染
            cfg_dir = self.cfg_dir
            cfg_dir.mkdir(parents=True, exist_ok=True)
            template = select_mdgw_template(
                cfg_dir,
                params.env_id,
                params.level,
                params.access_mode,
                params.line_type,
            )
            replacements = {
                "__GWID__": params.gwid,
                "__PASSWORD__": params.password or "",
                "__RE_LOCAL_IP__": params.local_ip or "",
            }
            if params.overrides:
                for k, v in params.overrides.items():
                    replacements[str(k)] = str(v)

            render_config(template, replacements, self.config_path)

            # 确保二进制可执行
            self._ensure_executable(self.binary_path)

            version = extract_version_from_archive(archive_path)
            try:
                (self.gateway_dir / ".version").write_text(
                    version, encoding="utf-8"
                )
            except OSError:
                pass

            log.info(
                "mdgw 部署完成 dir=%s version=%s",
                self.gateway_dir,
                version,
            )
            return OperationResult(
                success=True,
                message="deploy ok",
                details={"version": version, "config_path": str(self.config_path)},
            )
        except ConfigError as exc:
            return OperationResult(success=False, message=exc.message, details={"code": exc.code})
        except Exception as exc:  # noqa: BLE001
            log.exception("mdgw 部署失败")
            return OperationResult(success=False, message=str(exc))

    def start(self) -> OperationResult:
        try:
            self._process().start()
            return OperationResult(success=True, message="start ok")
        except ProcessError as exc:
            return OperationResult(
                success=False, message=exc.message, details={"code": exc.code}
            )

    def stop(self, force: bool = False) -> OperationResult:
        try:
            self._process().stop(force=force)
            return OperationResult(success=True, message="stop ok")
        except Exception as exc:  # noqa: BLE001
            return OperationResult(success=False, message=str(exc))

    def restart(self) -> OperationResult:
        try:
            proc = self._process()
            proc.stop()
            proc.start()
            return OperationResult(success=True, message="restart ok")
        except ProcessError as exc:
            return OperationResult(
                success=False, message=exc.message, details={"code": exc.code}
            )

    def upgrade(self, params: UpgradeParams) -> OperationResult:
        try:
            archive_path = Path(params.new_archive)
            if not archive_path.exists():
                raise UpgradeError("E6001", f"升级包不存在: {archive_path}")

            # 1) 备份
            manifest_path = self._backup_current()

            # 2) 停进程
            try:
                self._process().stop(force=False)
            except Exception:  # noqa: BLE001
                log.warning("升级前停止网关失败，将继续替换二进制")

            # 3) 替换二进制
            binary_member = find_binary_in_zip(
                archive_path, self.instance.binary_name or self.binary_name
            )
            if not binary_member:
                raise UpgradeError(
                    "E6002",
                    f"升级包中未找到 {self.binary_name}",
                )
            import zipfile

            with zipfile.ZipFile(archive_path) as zf:
                self.binary_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(binary_member) as src, open(
                    self.binary_path, "wb"
                ) as dst:
                    dst.write(src.read())
            self._ensure_executable(self.binary_path)

            version = params.version or extract_version_from_archive(archive_path)
            try:
                (self.gateway_dir / ".version").write_text(
                    version, encoding="utf-8"
                )
            except OSError:
                pass

            # 4) 启动验证
            try:
                self._process().start()
            except ProcessError as exc:
                log.warning("升级后启动失败，尝试回滚: %s", exc)
                self.rollback(RollbackParams(manifest_path=str(manifest_path)))
                return OperationResult(
                    success=False,
                    message=f"upgrade failed and rolled back: {exc.message}",
                    details={"manifest_path": str(manifest_path)},
                )

            log.info("mdgw 升级成功 -> %s", version)
            return OperationResult(
                success=True,
                message="upgrade ok",
                details={"version": version, "manifest_path": str(manifest_path)},
                manifest_path=str(manifest_path),
            )
        except UpgradeError as exc:
            return OperationResult(
                success=False, message=exc.message, details={"code": exc.code}
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("mdgw 升级失败")
            return OperationResult(success=False, message=str(exc))

    def rollback(
        self, params: RollbackParams | str | Path
    ) -> OperationResult:
        try:
            manifest_path = (
                Path(params.manifest_path)
                if isinstance(params, RollbackParams)
                else Path(params)
            )
            if not manifest_path.exists():
                raise UpgradeError("E6003", f"清单文件不存在: {manifest_path}")

            manifest = json.loads(
                Path(manifest_path).read_text(encoding="utf-8")
            )
            backup_binary = Path(manifest.get("binary_backup", ""))
            backup_config = Path(manifest.get("config_backup", ""))
            if not backup_binary.exists():
                raise UpgradeError("E6004", f"备份二进制不存在: {backup_binary}")

            try:
                self._process().stop(force=True)
            except Exception:  # noqa: BLE001
                log.warning("回滚前停止网关失败，继续恢复文件")

            # 恢复二进制
            import shutil

            if backup_binary.exists():
                shutil.copy2(backup_binary, self.binary_path)
                self._ensure_executable(self.binary_path)
            if backup_config.exists() and backup_config != self.config_path:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_config, self.config_path)

            # 可选 server_list
            backup_server_list = manifest.get("server_list_backup")
            if backup_server_list:
                src = Path(backup_server_list)
                if src.exists():
                    shutil.copy2(src, self.server_list_path)
                elif self.server_list_path.exists():
                    self.server_list_path.unlink()

            # 启动
            try:
                self._process().start()
            except ProcessError as exc:
                return OperationResult(
                    success=False,
                    message=f"rollback restart failed: {exc.message}",
                    details={"code": exc.code},
                )

            return OperationResult(
                success=True,
                message="rollback ok",
                details={"manifest_path": str(manifest_path)},
            )
        except UpgradeError as exc:
            return OperationResult(
                success=False, message=exc.message, details={"code": exc.code}
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("mdgw 回滚失败")
            return OperationResult(success=False, message=str(exc))

    def status(self) -> GatewayStatus:
        proc = self._process()
        running = proc.is_running()
        pid = proc.get_pid() if running else None
        monitor_accessible = (
            _port_reachable(proc.monitor_port) if running else False
        )
        return GatewayStatus(
            running=running,
            pid=pid,
            monitor_port=proc.monitor_port,
            monitor_accessible=monitor_accessible,
            gateway_dir=str(self.gateway_dir),
            version=self._current_version_hint(),
        )

    # ---------- 备份 ----------
    def _backup_current(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backup_root / self.instance.id / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        import shutil

        binary_backup = backup_dir / self.binary_path.name
        if self.binary_path.exists():
            shutil.copy2(self.binary_path, binary_backup)

        config_backup = backup_dir / "config.xml"
        if self.config_path.exists():
            shutil.copy2(self.config_path, config_backup)

        server_list_backup = None
        if self.server_list_path.exists():
            server_list_backup = backup_dir / "server_list.xml"
            shutil.copy2(self.server_list_path, server_list_backup)

        manifest = {
            "timestamp": timestamp,
            "gateway_type": "mdgw",
            "gateway_dir": str(self.gateway_dir),
            "binary_backup": str(binary_backup),
            "config_backup": str(config_backup),
            "server_list_backup": str(server_list_backup)
            if server_list_backup
            else None,
            "version": self._current_version_hint(),
        }
        manifest_path = backup_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return manifest_path


# ---------------- 工具 ----------------
def _is_executable(path: Path) -> bool:
    import os

    try:
        return os.access(path, os.X_OK)
    except OSError:
        return False


def _port_in_use(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", int(port)))
        return False
    except OSError:
        return True


def _port_reachable(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=1):
            return True
    except OSError:
        return False


# 避免 lint 报未使用 BinaryError（保留以备将来扩展）
_ = BinaryError
