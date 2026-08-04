"""进程管理：GatewayProcess 负责网关二进制启动/停止/重启。

策略：
- subprocess.Popen(cwd=gateway_dir, start_new_session=True)
- PID 文件位于 {gateway_dir}/.{binary_name}.pid
- psutil 可选，不可用时回退到 os.kill(pid, 0)
"""
from __future__ import annotations

import logging
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

from .errors import ProcessError

log = logging.getLogger(__name__)

# psutil 可选
try:
    import psutil  # type: ignore
except Exception:  # noqa: BLE001
    psutil = None


class GatewayProcess:
    """网关进程管理器。"""

    def __init__(
        self,
        gateway_dir: str | Path,
        binary_name: str,
        monitor_port: int,
        *,
        start_timeout: int = 30,
        stop_timeout: int = 30,
    ) -> None:
        self.gateway_dir = Path(gateway_dir)
        self.binary_name = binary_name
        self.monitor_port = int(monitor_port)
        self.start_timeout = int(start_timeout)
        self.stop_timeout = int(stop_timeout)

        self.binary_path = self.gateway_dir / binary_name
        self.config_path = self.gateway_dir / "cfg" / "config.xml"
        self.pid_file = self.gateway_dir / f".{binary_name}.pid"
        self._proc: subprocess.Popen | None = None

    # ---------- 生命周期 ----------
    def start(self) -> None:
        if self.is_running():
            raise ProcessError(
                "E4001",
                f"{self.binary_name} 已在运行 (pid={self.get_pid()})",
            )
        if not self.binary_path.exists():
            raise ProcessError("E4002", f"二进制文件不存在: {self.binary_path}")
        if not os.access(self.binary_path, os.X_OK):
            raise ProcessError("E4003", f"二进制无执行权限: {self.binary_path}")
        if not self.config_path.exists():
            raise ProcessError("E4004", f"配置文件不存在: {self.config_path}")

        log.info("启动 %s (cwd=%s)", self.binary_name, self.gateway_dir)

        try:
            proc = subprocess.Popen(
                [f"./{self.binary_name}"],
                cwd=str(self.gateway_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise ProcessError("E4005", f"启动进程失败: {exc}") from exc

        self._proc = proc
        # 写入 PID
        try:
            self.pid_file.parent.mkdir(parents=True, exist_ok=True)
            self.pid_file.write_text(str(proc.pid), encoding="utf-8")
        except OSError as exc:
            proc.terminate()
            raise ProcessError("E4006", f"写入 PID 文件失败: {exc}") from exc

        log.info("%s 已启动 pid=%s，等待监控端口就绪", self.binary_name, proc.pid)

        try:
            self.wait_for_monitor(self.start_timeout)
        except ProcessError:
            # 端口超时：清理
            try:
                self.stop(force=True)
            except Exception:  # noqa: BLE001
                log.exception("停止失败的启动进程时再次失败")
            raise

    def stop(self, force: bool = False) -> None:
        pid = self.get_pid()
        if pid is None:
            log.info("%s 未在运行")
            self._cleanup_pid_file()
            return

        if not self._pid_exists(pid):
            log.info("进程 %s 不存在，清理 PID 文件", pid)
            self._cleanup_pid_file()
            return

        if force:
            log.warning("强制终止 %s (pid=%s)", self.binary_name, pid)
            self._send_signal(pid, signal.SIGKILL)
            self._wait_exit(pid, timeout=5)
        else:
            log.info("优雅停止 %s (pid=%s)", self.binary_name, pid)
            self._send_signal(pid, signal.SIGTERM)
            exited = self._wait_exit(pid, timeout=self.stop_timeout)
            if not exited:
                log.warning("%s 优雅停止超时，发送 SIGKILL")
                self._send_signal(pid, signal.SIGKILL)
                self._wait_exit(pid, timeout=5)

        self._cleanup_pid_file()

    def restart(self) -> None:
        self.stop()
        time.sleep(1)
        self.start()

    # ---------- 状态 ----------
    def is_running(self) -> bool:
        pid = self.get_pid()
        if pid is None:
            return False
        return self._pid_exists(pid)

    def get_pid(self) -> int | None:
        if not self.pid_file.exists():
            return None
        try:
            raw = self.pid_file.read_text(encoding="utf-8").strip()
            if not raw:
                return None
            return int(raw)
        except (OSError, ValueError):
            return None

    def wait_for_monitor(self, max_wait: int = 30) -> None:
        deadline = time.time() + max(0, max_wait)
        while time.time() < deadline:
            if self._check_monitor_port():
                return
            time.sleep(0.5)
        raise ProcessError(
            "E5001",
            f"监控端口 {self.monitor_port} 在 {max_wait}s 内未就绪",
        )

    # ---------- 内部工具 ----------
    def _check_monitor_port(self) -> bool:
        try:
            with socket.create_connection(
                ("127.0.0.1", self.monitor_port),
                timeout=1,
            ):
                return True
        except OSError:
            return False

    def _pid_exists(self, pid: int) -> bool:
        if psutil is not None:
            return psutil.pid_exists(pid)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def _send_signal(self, pid: int, sig: int) -> None:
        try:
            if psutil is not None:
                psutil.Process(pid).send_signal(sig)
            else:
                os.kill(pid, sig)
        except ProcessLookupError:
            log.debug("进程 %s 已不存在", pid)
        except OSError as exc:
            log.warning("向 %s 发送信号失败: %s", pid, exc)

    def _wait_exit(self, pid: int, timeout: int) -> bool:
        deadline = time.time() + max(0, timeout)
        while time.time() < deadline:
            if not self._pid_exists(pid):
                return True
            time.sleep(0.3)
        return False

    def _cleanup_pid_file(self) -> None:
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except OSError:
            pass
