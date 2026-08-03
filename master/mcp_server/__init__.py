"""MCP Server（阶段一 POC）。

在管控中心 master 内挂载一个 MCP（Model Context Protocol）服务端，
通过 Streamable HTTP 传输暴露只读工具，供外部 AI Agent 调用。

当前暴露的工具：
- gateway_list_instances  列出所有网关实例
- gateway_status          查询指定网关实例的运行状态

挂载方式：在 master/main.py 中通过 app.mount("/mcp", mcp_http_app()) 集成，
与现有 FastAPI / gRPC 并行运行，零业务侵入。

客户端连接地址示例：http://<master-host>:5500/mcp/mcp
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from gateway.controllers import registry
from gateway.core.errors import GatewayError
from gateway.core.store import get_default_store

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP 实例
# ---------------------------------------------------------------------------
mcp = FastMCP("sre-tools-master")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _instance_to_dict(inst) -> dict[str, Any]:
    """将 GatewayInstance dataclass 转为可序列化字典。"""
    return {
        "id": inst.id,
        "exchange": inst.exchange,
        "kind": inst.kind,
        "name": inst.name,
        "gateway_dir": inst.gateway_dir,
        "binary_name": inst.binary_name,
        "monitor_port": inst.monitor_port,
        "version": inst.version,
    }


def _resolve_controller(instance_id: str):
    """根据实例 ID 解析控制器。

    复用 master/gateway/api 的逻辑，但不依赖 FastAPI HTTPException，
    失败时抛 ValueError，由 MCP 层转为标准错误响应。
    """
    inst = get_default_store().get(instance_id)
    if inst is None:
        raise ValueError(f"网关实例不存在: {instance_id}")
    try:
        cls = registry.get(inst.exchange, inst.kind)
    except KeyError as exc:
        raise ValueError(
            f"未注册控制器: exchange={inst.exchange}, kind={inst.kind}"
        ) from exc

    install_root = Path(inst.gateway_dir).parent
    backup_root = (
        install_root.parent / "backup" / inst.id
        if install_root
        else Path("data/gateways/backup") / inst.id
    )
    return inst, cls(inst, install_root, backup_root)


# ---------------------------------------------------------------------------
# MCP Tools（只读）
# ---------------------------------------------------------------------------
@mcp.tool()
async def gateway_list_instances() -> list[dict[str, Any]]:
    """列出所有已注册的交易所网关实例。

    返回每个实例的 id / exchange / kind / name / gateway_dir /
    binary_name / monitor_port / version 字段。
    该工具为只读，不会对网关产生任何副作用。
    """
    store = get_default_store()
    # store.list() 是同步方法（读 JSON 文件 + threading.Lock），
    # 用 to_thread 避免阻塞事件循环
    instances = await asyncio.to_thread(store.list)
    return [_instance_to_dict(i) for i in instances]


@mcp.tool()
async def gateway_status(instance_id: str) -> dict[str, Any]:
    """查询指定网关实例的实时运行状态。

    参数:
        instance_id: 网关实例 ID

    返回 running / pid / monitor_port / monitor_accessible /
    gateway_dir / version / memory_mb / uptime_seconds 等字段。
    该工具为只读，不会对网关产生任何副作用。
    """
    _inst, controller = _resolve_controller(instance_id)

    try:
        # controller.status() 是同步方法（可能涉及子进程/端口探测），
        # 用 to_thread 避免阻塞事件循环
        status = await asyncio.to_thread(controller.status)
    except GatewayError as exc:
        raise ValueError(f"网关状态查询失败: {exc.message}") from exc
    except NotImplementedError:
        raise ValueError("该控制器未实现 status 操作") from None
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"网关状态查询异常: {exc}") from exc

    return status.as_dict()


# ---------------------------------------------------------------------------
# ASGI 应用工厂
# ---------------------------------------------------------------------------
def mcp_http_app(path: str = "/mcp"):
    """返回 MCP Streamable HTTP ASGI 应用，供 FastAPI 挂载。

    用法（在 master/main.py 中）:
        from mcp_server import mcp_http_app
        app.mount("/mcp", mcp_http_app())

    挂载后客户端端点为: http://<host>:<port>/mcp/mcp
    （外层 /mcp 来自 FastAPI mount，内层 /mcp 来自 streamable_http_app 路由）
    """
    return mcp.streamable_http_app(path)
