"""gateway 模块冒烟检查。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from master.gateway.controllers import registry, GatewayControllerABC
from master.gateway.core.config_tools import (
    extract_version_from_archive,
    generate_server_list_xml,
    render_config,
    select_mdgw_template,
    select_tgw_template,
)
from master.gateway.core.errors import ConfigError, ProcessError
from master.gateway.core.models import (
    DeployParams,
    GatewayInstance,
    GatewayStatus,
    OperationResult,
    RollbackParams,
    UpgradeParams,
)

_ = (GatewayStatus, RollbackParams)
from master.gateway.core.process import GatewayProcess

print("registry:")
for item in registry.list_all():
    print(" ", item)

print("szse/mdgw:", registry.get("szse", "mdgw").__name__)
print("szse/tgw:", registry.get("szse", "tgw").__name__)
print("sse/mdgw:", registry.get("sse", "mdgw").__name__)
print("sse/tgw:", registry.get("sse", "tgw").__name__)
print("bjse/mdgw:", registry.get("bjse", "mdgw").__name__)
print("bjse/tgw:", registry.get("bjse", "tgw").__name__)

# 验证占位类抛 NotImplementedError
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    inst = GatewayInstance(
        id="test",
        exchange="sse",
        kind="mdgw",
        name="x",
        gateway_dir=str(root / "gw"),
        binary_name="mdgw",
        monitor_port=7501,
        version="1",
    )
    ctrl = registry.get("sse", "mdgw")(inst, root / "install", root / "backup")
    try:
        ctrl.status()
    except NotImplementedError as exc:
        print("placeholder raises NotImplementedError as expected:", exc)

# 验证 config_tools
with tempfile.TemporaryDirectory() as tmp:
    sample = Path(tmp) / "生产环境.config.xml.sample"
    sample.write_text("gwid=__GWID__\nip=__RE_LOCAL_IP__\n", encoding="utf-8")
    out = Path(tmp) / "cfg" / "config.xml"
    render_config(sample, {"__GWID__": "GW01", "__RE_LOCAL_IP__": "1.2.3.4"}, out)
    assert "GW01" in out.read_text(encoding="utf-8"), out.read_text()
    print("render_config OK")

    mdgw_sample = Path(tmp) / "生产环境.config.xml.sample.Level2"
    mdgw_sample.write_text("<config></config>", encoding="utf-8")
    picked = select_mdgw_template(Path(tmp), 0, 2, "TCP")
    assert picked == mdgw_sample
    print("select_mdgw_template OK")

    sl_path = Path(tmp) / "server_list.xml"
    generate_server_list_xml(
        sl_path,
        [{"no": "1", "servers": [{"description": "主", "address": "10.0.0.1", "port": 7019, "knock_offset_time": 0}]}],
    )
    assert sl_path.exists()
    print("generate_server_list_xml OK")

# 验证 GatewayProcess pid 文件生成
with tempfile.TemporaryDirectory() as tmp:
    gw = Path(tmp)
    binary = gw / "mdgw"
    binary.write_bytes(b"#!/bin/sh\nsleep 30\n")
    import os

    try:
        os.chmod(binary, 0o755)
    except Exception:
        pass
    (gw / "cfg").mkdir(parents=True, exist_ok=True)
    (gw / "cfg" / "config.xml").write_text("<config/>", encoding="utf-8")

    import unittest.mock as mock

    proc = GatewayProcess(gateway_dir=gw, binary_name="mdgw", monitor_port=17654, start_timeout=1)
    with mock.patch("subprocess.Popen") as popen_mock, mock.patch.object(
        proc, "wait_for_monitor", return_value=None
    ):
        popen_mock.return_value.pid = 12345
        proc.start()
        assert proc.get_pid() == 12345
        pid_file = gw / ".mdgw.pid"
        assert pid_file.exists()
        print("GatewayProcess start/pid_file OK, pid_file:", pid_file)

print("ALL OK")
