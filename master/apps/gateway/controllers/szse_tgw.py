"""深交所 tgw（交易网关）控制器。

与 mdgw 差异：
- 模板选择简化为按环境名匹配
- 支持 server_list.xml（tgw 20240823+ 独立文件）
- 升级时同时备份 server_list.xml
"""
from __future__ import annotations

import json
import logging
import socket
from datetime import datetime
from pathlib import Path

from ..core.config_tools import (
    extract_version_from_archive,
    find_binary_in_zip,
    generate_server_list_xml,
    render_config,
    select_tgw_template,
)
from ..core.errors import ProcessError, UpgradeError
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


@registry.register("szse", "tgw")
class SzseTgwController(GatewayControllerABC):
    binary_name = "tgw"
    monitor_port_default = 7500

    def _process(self) -> GatewayProcess:
        return GatewayProcess(
            gateway_dir=self.gateway_dir,
            binary_name=self.instance.binary_name or self.binary_name,
            monitor_port=self.instance.monitor_port or self.monitor_port_default,
        )

    # ---------- 接口 ----------
    def preflight(self) -> OperationResult:
        issues: list[str] = []
        if not self.binary_path.exists():
            issues.append(f"二进制文件不存在: {self.binary_path}")
        if not self.config_path.exists():
            issues.append(f"配置文件不存在: {self.config_path}")
        if not self.ca_cert_path.exists():
            issues.append(f"CA 证书不存在: {self.ca_cert_path}")
        if issues:
            return OperationResult(
                success=False, message="; ".join(issues), details={"issues": issues}
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
                return OperationResult(
                    success=False, message=f"部署包不存在: {archive_path}"
                )

            self.gateway_dir.mkdir(parents=True, exist_ok=True)
            self._merge_zip_contents(archive_path, self.gateway_dir)

            cfg_dir = self.cfg_dir
            cfg_dir.mkdir(parents=True, exist_ok=True)

            template = select_tgw_template(cfg_dir, params.env_id)
            replacements = {
                "__GWID__": params.gwid,
                "__PASSWORD__": params.password or "",
                "__RE_LOCAL_IP__": params.local_ip or "",
            }
            if params.overrides:
                for k, v in params.overrides.items():
                    replacements[str(k)] = str(v)
            render_config(template, replacements, self.config_path)

            # server_list.xml（可选）
            if params.server_list_groups:
                generate_server_list_xml(self.server_list_path, params.server_list_groups)

            self._ensure_executable(self.binary_path)

            version = extract_version_from_archive(archive_path)
            try:
                (self.gateway_dir / ".version").write_text(
                    version, encoding="utf-8"
                )
            except OSError:
                pass

            return OperationResult(
                success=True,
                message="deploy ok",
                details={
                    "version": version,
                    "config_path": str(self.config_path),
                    "server_list_path": str(self.server_list_path),
                },
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("tgw 部署失败")
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

            manifest_path = self._backup_current()
            try:
                self._process().stop(force=False)
            except Exception:  # noqa: BLE001
                log.warning("升级前停止网关失败，将继续替换二进制")

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

            return OperationResult(
                success=True,
                message="upgrade ok",
                details={"version": version},
                manifest_path=str(manifest_path),
            )
        except UpgradeError as exc:
            return OperationResult(
                success=False, message=exc.message, details={"code": exc.code}
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("tgw 升级失败")
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

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            backup_binary = Path(manifest.get("binary_backup", ""))
            backup_config = Path(manifest.get("config_backup", ""))
            if not backup_binary.exists():
                raise UpgradeError("E6004", f"备份二进制不存在: {backup_binary}")

            try:
                self._process().stop(force=True)
            except Exception:  # noqa: BLE001
                log.warning("回滚前停止网关失败，继续恢复文件")

            import shutil

            shutil.copy2(backup_binary, self.binary_path)
            self._ensure_executable(self.binary_path)

            if backup_config.exists() and backup_config != self.config_path:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_config, self.config_path)

            backup_server_list = manifest.get("server_list_backup")
            if backup_server_list:
                src = Path(backup_server_list)
                if src.exists():
                    shutil.copy2(src, self.server_list_path)
                elif self.server_list_path.exists():
                    self.server_list_path.unlink()

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
            log.exception("tgw 回滚失败")
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
            "gateway_type": "tgw",
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


def _port_reachable(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=1):
            return True
    except OSError:
        return False
