"""master/apps/data_collection: 数据采集模块。

本模块在 Master 端提供向 worker 下发数据采集任务的能力，覆盖两类任务：

1. **定时数据采集任务（ScheduledTask）**
   - 基于 cron 表达式周期性触发
   - 通过 worker 端的 ``DatabaseCollectorTask`` / ``PrefectDatabaseCollectorTask`` 执行
   - 适配 sql / clickhouse / influxdb / http / redis / kafka 等数据源

2. **实时日志采集任务（LogTask）**
   - 持续运行，按指定间隔采集日志
   - 通过 worker 端的 ``LogCollectorTask`` 执行

下发链路::

    外部调用方 ──HTTP──> master.apps.data_collection.api
                          │
                          ▼
                    dispatcher.TaskDispatcher
                          │  (gRPC Communicate 流的 TaskUpdate 消息)
                          ▼
                    master.grpc.server.WorkerServiceServicer
                          │  (per-worker message queue)
                          ▼
                    worker.grpc.client.CentralGrpcClient._handle_task_update
                          │
                          ▼
                    worker.scheduler.TaskScheduler

同时本模块在 gRPC 层暴露四个 RPC 接口供其他 gRPC 客户端直接调用：
``DispatchScheduledTask`` / ``DispatchLogTask`` / ``ControlTask`` / ``ListWorkerTasks``。
"""

from __future__ import annotations

from fastapi import FastAPI


def setup(app: FastAPI) -> None:
    """将数据采集模块的 HTTP 路由挂载到 FastAPI 应用上。

    在 ``master/main.py`` 中调用：
        from master.apps.data_collection import setup as setup_data_collection
        setup_data_collection(app)
    """
    from .api import router

    app.include_router(router)


__all__ = ["setup"]
