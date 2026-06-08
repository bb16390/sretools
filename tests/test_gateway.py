"""网关控制模块单元测试。

运行方式：
    cd /Users/shun/PythonProject/sretools
    python3 -m pytest tests/test_gateway.py -v
"""
from __future__ import annotations

import json
import os
import stat
import zipfile
from pathlib import Path

import pytest

# 把项目根加入 sys.path，便于 `from master.gateway ...`
BASE_DIR = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(BASE_DIR))

from master.gateway.controllers import (
    GatewayControllerABC,
    registry,
)
from master.gateway.core.config_tools import (
    ConfigError,
    generate_server_list_xml,
    render_config,
    select_mdgw_template,
    select_tgw_template,
)
from master.gateway.core.models import (
    DeployParams,
    GatewayInstance,
    GatewayStatus,
    OperationResult,
    RollbackParams,
    UpgradeParams,
)
from master.gateway.core.process import GatewayProcess, ProcessError
from master.gateway.core.store import InstanceStore


# ---------------------------------------------------------------------------
# 控制器注册
# ---------------------------------------------------------------------------
class TestRegistry:
    def test_list_all_contains_six(self) -> None:
        items = registry.list_all()
        # szse/sse/bjse 各 2 类 = 6 项
        assert len(items) >= 6

    def test_szse_controllers_registered(self) -> None:
        assert registry.get("szse", "mdgw") is not None
        assert registry.get("szse", "tgw") is not None

    def test_missing_exchange_raises(self) -> None:
        with pytest.raises(KeyError):
            registry.get("xxx", "mdgw")


# ---------------------------------------------------------------------------
# 控制器实现
# ---------------------------------------------------------------------------
class TestControllers:
    def _instance(self, tmp_path: Path) -> GatewayInstance:
        return GatewayInstance(
            id="ut-1",
            exchange="szse",
            kind="mdgw",
            name="ut",
            gateway_dir=str(tmp_path / "gw"),
            binary_name="mdgw",
            monitor_port=17501,
            version="1.0.0",
        )

    def test_abc_not_instantiable(self) -> None:
        with pytest.raises(TypeError):
            GatewayControllerABC.__new__(GatewayControllerABC)  # type: ignore[abstract]

    def test_szse_mdgw_controller(self, tmp_path: Path) -> None:
        inst = self._instance(tmp_path)
        ctrl_cls = registry.get("szse", "mdgw")
        ctrl = ctrl_cls(inst, tmp_path / "install", tmp_path / "backup")
        assert ctrl is not None
        assert ctrl.instance.id == "ut-1"

    def test_szse_tgw_controller(self, tmp_path: Path) -> None:
        inst = self._instance(tmp_path)
        inst.kind = "tgw"
        inst.binary_name = "tgw"
        ctrl_cls = registry.get("szse", "tgw")
        ctrl = ctrl_cls(inst, tmp_path / "install", tmp_path / "backup")
        assert ctrl is not None

    @pytest.mark.parametrize("exchange", ["sse", "bjse"])
    def test_placeholder_controllers_raise_not_implemented(self, tmp_path: Path, exchange: str) -> None:
        inst = self._instance(tmp_path)
        inst.exchange = exchange
        for kind in ("mdgw", "tgw"):
            inst.kind = kind
            inst.binary_name = kind
            ctrl_cls = registry.get(exchange, kind)
            ctrl = ctrl_cls(inst, tmp_path / "install", tmp_path / "backup")
            with pytest.raises(NotImplementedError):
                ctrl.deploy("bogus.zip", DeployParams(gwid="GW"))
            with pytest.raises(NotImplementedError):
                ctrl.start()
            with pytest.raises(NotImplementedError):
                ctrl.stop()
            with pytest.raises(NotImplementedError):
                ctrl.status()
            with pytest.raises(NotImplementedError):
                ctrl.upgrade(UpgradeParams(new_archive="x.zip"))
            with pytest.raises(NotImplementedError):
                ctrl.rollback(RollbackParams(manifest_path="/tmp/x.json"))


# ---------------------------------------------------------------------------
# 配置工具
# ---------------------------------------------------------------------------
class TestConfigTools:
    def test_render_config_replaces_placeholders(self, tmp_path: Path) -> None:
        tpl = tmp_path / "tpl.xml"
        tpl.write_text("gwid=__GWID__\nport=__MONITOR_PORT__\n", encoding="utf-8")
        out = render_config(
            tpl,
            {"__GWID__": "GW01", "__MONITOR_PORT__": "7501"},
            tmp_path / "cfg" / "config.xml",
        )
        text = out.read_text(encoding="utf-8")
        assert "gwid=GW01" in text
        assert "port=7501" in text

    def test_render_config_missing_template_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError):
            render_config(tmp_path / "nonexistent", {}, tmp_path / "out.xml")

    def test_select_mdgw_template_finds_level2(self, tmp_path: Path) -> None:
        sample = tmp_path / "生产环境.config.xml.sample.Level2"
        sample.write_text("sample", encoding="utf-8")
        result = select_mdgw_template(tmp_path, env_id=0, level=2, access_mode="TCP", line_type="地面")
        assert result.name == "生产环境.config.xml.sample.Level2"

    def test_select_mdgw_template_finds_udp(self, tmp_path: Path) -> None:
        sample = tmp_path / "生产环境.config.xml.sample.UDP.Level2"
        sample.write_text("udp sample", encoding="utf-8")
        result = select_mdgw_template(tmp_path, env_id=0, level=2, access_mode="UDP", line_type="地面")
        assert result.name == "生产环境.config.xml.sample.UDP.Level2"

    def test_select_mdgw_template_fallback(self, tmp_path: Path) -> None:
        # 没有完全匹配，但目录里有别的 sample
        other = tmp_path / "other.config.xml.sample"
        other.write_text("fallback", encoding="utf-8")
        result = select_mdgw_template(tmp_path, env_id=0, level=2, access_mode="TCP", line_type="地面")
        assert result.name == "other.config.xml.sample"

    def test_select_mdgw_template_missing(self, tmp_path: Path) -> None:
        # 目录中完全没有 sample
        with pytest.raises(ConfigError):
            select_mdgw_template(tmp_path, env_id=0, level=2, access_mode="TCP", line_type="地面")

    def test_select_tgw_template_finds_env(self, tmp_path: Path) -> None:
        target = tmp_path / "生产环境.config.xml.sample"
        target.write_text("tgw sample", encoding="utf-8")
        result = select_tgw_template(tmp_path, env_id=0)
        assert result.name == "生产环境.config.xml.sample"

    def test_generate_server_list_xml(self, tmp_path: Path) -> None:
        out = generate_server_list_xml(
            tmp_path / "server_list.xml",
            groups=[
                {
                    "no": "1",
                    "servers": [
                        {"address": "10.0.0.1:7019", "port": 7019, "description": "主线路1", "knock_offset_time": 0},
                        {"address": "10.0.0.2:7019", "port": 7019, "description": "主线路2", "knock_offset_time": 0},
                    ],
                }
            ],
        )
        text = out.read_text(encoding="utf-8")
        assert "<group" in text
        assert 'no="1"' in text
        assert "10.0.0.1" in text
        assert "10.0.0.2" in text


# ---------------------------------------------------------------------------
# 进程管理
# ---------------------------------------------------------------------------
class TestProcess:
    def test_start_stop_cycle(self, tmp_path: Path) -> None:
        import socket as _socket

        # 占用监控端口，模拟进程监听
        srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        srv.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        monitor_port = srv.getsockname()[1]

        try:
            # 准备 gateway_dir + 伪二进制
            gw_dir = tmp_path / "gw"
            gw_dir.mkdir()
            cfg_dir = gw_dir / "cfg"
            cfg_dir.mkdir()
            (cfg_dir / "config.xml").write_text("<x/>", encoding="utf-8")
            # 用 shell 脚本 sleep 作为伪二进制
            binary = gw_dir / "fake-gw"
            binary.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
            os.chmod(binary, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

            gw = GatewayProcess(
                gateway_dir=str(gw_dir),
                binary_name="fake-gw",
                monitor_port=monitor_port,
                start_timeout=5,
                stop_timeout=5,
            )
            gw.start()
            assert gw.is_running()
            pid = gw.get_pid()
            assert pid is not None and pid > 0
            gw.stop()
            assert not gw.is_running()
        finally:
            srv.close()

    def test_start_missing_binary_raises(self, tmp_path: Path) -> None:
        gw = GatewayProcess(
            gateway_dir=str(tmp_path),
            binary_name="no-such-bin",
            monitor_port=17500,
        )
        with pytest.raises(ProcessError):
            gw.start()

    def test_start_without_config_raises(self, tmp_path: Path) -> None:
        # 构造 binary 但缺少 cfg/config.xml
        binary = tmp_path / "x"
        binary.write_text("#!/bin/sh\nsleep 5\n", encoding="utf-8")
        os.chmod(binary, stat.S_IRWXU)
        gw = GatewayProcess(
            gateway_dir=str(tmp_path),
            binary_name="x",
            monitor_port=17500,
        )
        with pytest.raises(ProcessError):
            gw.start()


# ---------------------------------------------------------------------------
# 实例存储
# ---------------------------------------------------------------------------
class TestInstanceStore:
    def test_crud_roundtrip(self, tmp_path: Path) -> None:
        store = InstanceStore(tmp_path / "store.json")
        inst = GatewayInstance(
            id="g1", exchange="szse", kind="mdgw", name="网关A",
            gateway_dir="/opt/gw", binary_name="mdgw", monitor_port=7501, version="1.0.0",
        )
        store.upsert(inst)
        assert len(store.list()) == 1
        got = store.get("g1")
        assert got is not None
        assert got.name == "网关A"
        assert got.monitor_port == 7501
        assert store.delete("g1")
        assert store.list() == []
        assert not store.delete("g1")

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        path = tmp_path / "store.json"
        store1 = InstanceStore(path)
        store1.upsert(
            GatewayInstance(
                id="g2", exchange="szse", kind="mdgw", name="P",
                gateway_dir="/x", binary_name="mdgw", monitor_port=1,
            )
        )
        store2 = InstanceStore(path)
        assert store2.get("g2") is not None
        assert store2.get("g2").name == "P"


# ---------------------------------------------------------------------------
# API 路由
# ---------------------------------------------------------------------------
class TestGatewayAPI:
    @pytest.fixture()
    def app(self, tmp_path: Path):
        from fastapi import FastAPI
        from master.gateway.api import router as gateway_router
        import master.gateway.core.store as _store_mod_core
        import master.gateway.api as _store_mod_api

        original = _store_mod_core.get_default_store
        store_path = tmp_path / "api_store.json"

        def patched(root=None):
            return InstanceStore(store_path)

        # core 模块里的函数引用
        _store_mod_core.get_default_store = patched
        # api 模块里 from ..core.store import get_default_store 已在导入时复制，需覆盖其可见名称
        _store_mod_api.get_default_store = patched
        try:
            _app = FastAPI()
            _app.include_router(gateway_router)
            patched().upsert(
                GatewayInstance(
                    id="api-test", exchange="szse", kind="mdgw", name="api测试网关",
                    gateway_dir=str(tmp_path / "gw-api"), binary_name="mdgw",
                    monitor_port=17502, version="0.1",
                )
            )
            yield _app
        finally:
            _store_mod_core.get_default_store = original
            _store_mod_api.get_default_store = original

    def test_controllers_endpoint(self, app) -> None:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/api/gateway/controllers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 6
        assert any(x["exchange"] == "szse" and x["kind"] == "mdgw" for x in data)

    def test_instances_list(self, app) -> None:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/api/gateway/instances")
        assert resp.status_code == 200
        assert resp.json()[0]["id"] == "api-test"

    def test_instances_create_then_delete(self, app) -> None:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/api/gateway/instances",
            json={
                "id": "new-gw",
                "exchange": "szse",
                "kind": "mdgw",
                "name": "新建",
                "gateway_dir": "/tmp/new",
                "binary_name": "mdgw",
                "monitor_port": 7503,
            },
        )
        assert resp.status_code == 200
        resp = client.delete("/api/gateway/instances/new-gw")
        assert resp.status_code == 200

    def test_status_endpoint(self, app) -> None:
        from unittest import mock
        from fastapi.testclient import TestClient

        client = TestClient(app)
        ctrl_cls = registry.get("szse", "mdgw")
        with mock.patch.object(
            ctrl_cls,
            "status",
            return_value=GatewayStatus(
                running=True, pid=1234, monitor_port=17502,
                monitor_accessible=True, gateway_dir="/tmp/gw", version="1.0",
            ),
        ):
            resp = client.get("/api/gateway/instances/api-test/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is True
        assert data["pid"] == 1234

    def test_start_endpoint(self, app) -> None:
        from unittest import mock
        from fastapi.testclient import TestClient

        client = TestClient(app)
        ctrl_cls = registry.get("szse", "mdgw")
        with mock.patch.object(
            ctrl_cls,
            "start",
            return_value=OperationResult(success=True, message="started"),
        ):
            resp = client.post("/api/gateway/instances/api-test/start")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
class TestModels:
    def test_operation_result_as_dict(self) -> None:
        r = OperationResult(success=True, message="ok", details={"x": 1}, manifest_path="/tmp/m.json")
        d = r.as_dict()
        assert d["success"] is True
        assert d["message"] == "ok"
        assert d["details"] == {"x": 1}
        assert d["manifest_path"] == "/tmp/m.json"

    def test_gateway_status_as_dict(self) -> None:
        s = GatewayStatus(running=True, pid=1, monitor_port=7501, gateway_dir="/x")
        d = s.as_dict()
        assert d["running"] is True
        assert d["pid"] == 1
        assert d["monitor_port"] == 7501


# ---------------------------------------------------------------------------
# 端到端：构造 zip -> deploy -> 配置正确落盘
# ---------------------------------------------------------------------------
class TestEndToEnd:
    def test_deploy_writes_binary_and_config(self, tmp_path: Path) -> None:
        import socket as _socket

        # 占住 monitor_port，使 start 前的等待可通过（我们不实际启动网关）
        srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        srv.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 17511))
        srv.listen(1)

        gw_dir = tmp_path / "gw"
        gw_dir.mkdir()
        install_root = tmp_path / "install"
        install_root.mkdir()
        backup_root = tmp_path / "backup"
        backup_root.mkdir()

        # 构造部署 zip：一个叫 mdgw 的脚本 + 一个 sample 模板
        pkg_zip = tmp_path / "pkg.zip"
        with zipfile.ZipFile(pkg_zip, "w") as z:
            z.writestr("mdgw", "#!/bin/sh\nsleep 30\n")
            z.writestr("cfg/生产环境.config.xml.sample.Level2",
                       "<cfg>\ngwid=__GWID__\nport=__MONITOR_PORT__\n</cfg>\n")

        inst = GatewayInstance(
            id="e2e", exchange="szse", kind="mdgw", name="e2e",
            gateway_dir=str(gw_dir), binary_name="mdgw", monitor_port=17511,
            version="1.0.0",
        )

        try:
            ctrl_cls = registry.get("szse", "mdgw")
            ctrl = ctrl_cls(inst, install_root, backup_root)
            result = ctrl.deploy(
                str(pkg_zip),
                DeployParams(gwid="GW-E2E", env_id=0, level=2, access_mode="TCP", line_type="地面"),
            )
            assert result.success, f"deploy failed: {result.message}"
            # 二进制 + 配置文件必须存在
            assert (gw_dir / "mdgw").exists()
            cfg_file = gw_dir / "cfg" / "config.xml"
            assert cfg_file.exists()
            text = cfg_file.read_text(encoding="utf-8")
            assert "GW-E2E" in text
        finally:
            srv.close()
