"""Collector HTTP API 路由。

本模块挂载在 ``apps.collector`` 下，路由前缀为 ``/api/collector``，
提供采集相关的对外 HTTP 接口。

已注册路由：
    - ``GET /api/collector/workers``：返回当前通过 gRPC 注册到 master 的
      worker 列表快照。每项含 ``worker_id`` / ``host`` / ``port`` /
      ``status`` / ``last_heartbeat`` / ``version``。若 gRPC 模块不可用
      则返回空列表，避免抛出 500。
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collector")


def _get_list_workers():
    """懒导入 ``grpc_server.server.list_workers``。

    master 运行时 ``master/`` 已加入 ``sys.path``，可直接
    ``from grpc_server.server import list_workers``；若 gRPC 模块不可用
    （例如仅启动 HTTP 子集时），返回 None 并记日志。
    """
    try:
        from grpc_server.server import list_workers  # type: ignore
    except ImportError:
        logger.warning("grpc_server.server 不可用，无法读取已注册 worker 列表")
        return None
    return list_workers


@router.get("/workers")
async def list_registered_workers():
    """返回当前已注册的 worker 列表。

    Returns:
        dict: ``{"workers": [...]}``，每项含 ``worker_id`` / ``host`` /
        ``port`` / ``status`` / ``last_heartbeat`` / ``version``。
        若 gRPC 模块不可用则返回 ``{"workers": []}``。
    """
    list_workers = _get_list_workers()
    if list_workers is None:
        return {"workers": []}
    try:
        workers = list_workers()
    except Exception as exc:  # noqa: BLE001
        logger.error("读取已注册 worker 列表失败: %s", exc, exc_info=True)
        return {"workers": []}
    return {"workers": workers}
