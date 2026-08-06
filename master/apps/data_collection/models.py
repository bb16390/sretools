"""数据采集模块的 Pydantic 数据模型。

这些模型同时服务于：
- HTTP REST API 的请求 / 响应体
- 内部 ``TaskStore`` 持久化记录
- 转换为 gRPC ``TaskUpdate`` 消息时的中间表达
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------
class TaskKind(str, enum.Enum):
    """worker 端可执行的任务类型。"""

    DATABASE_COLLECTOR = "database_collector"
    PREFECT_DATABASE_COLLECTOR = "prefect_database_collector"
    LOG_COLLECTOR = "log_collector"
    KAFKA_COLLECTOR = "kafka_collector"
    METRIC_CONVERTER = "metric_converter"


class TaskAction(str, enum.Enum):
    """通过 Communicate 流下发给 worker 的动作。"""

    CREATE = "task_create"
    STOP = "task_stop"
    PAUSE = "task_pause"
    RESUME = "task_resume"


class DispatchStatus(str, enum.Enum):
    """任务在 master 端的下发状态。"""

    PENDING = "pending"        # 已创建但 worker 离线，等待上线后下发
    DISPATCHED = "dispatched"  # 已通过 Communicate 流推送给 worker
    STOPPED = "stopped"        # 已主动停止


# ---------------------------------------------------------------------------
# 配置模型
# ---------------------------------------------------------------------------
class ScheduledTaskConfig(BaseModel):
    """定时数据采集任务配置，对应 proto 的 ScheduledTaskConfig。"""

    cron_expression: str = Field(..., description="cron 调度表达式，如 '0 9 * * *'")
    adapter_type: str = Field(
        ...,
        description="数据源适配器类型: sql / clickhouse / influxdb / http / redis / kafka",
    )
    adapter_config: Dict[str, Any] = Field(
        default_factory=dict, description="适配器构造参数"
    )
    query: Optional[str] = Field(None, description="单条 SQL（与 queries 二选一）")
    queries: Optional[List[str]] = Field(None, description="多条 SQL")
    trade_day_only: bool = Field(False, description="仅在交易日执行")
    execution_mode: Optional[str] = Field(
        None, description="执行模式: thread / process；留空使用任务默认值"
    )
    task_kind: TaskKind = Field(
        TaskKind.DATABASE_COLLECTOR,
        description="worker 端任务类型，可选择 prefect 实现",
    )
    extra: Dict[str, str] = Field(default_factory=dict, description="预留扩展字段")

    def to_worker_config(self) -> Dict[str, Any]:
        """转换为 worker 端 ``TaskScheduler.create_task`` 接收的 config 字典。"""
        cfg: Dict[str, Any] = {
            "cron_expression": self.cron_expression,
            "adapter_type": self.adapter_type,
            "adapter_config": self.adapter_config,
            "trade_day_only": self.trade_day_only,
        }
        if self.queries:
            cfg["queries"] = self.queries
        elif self.query:
            cfg["query"] = self.query
        if self.execution_mode:
            cfg["execution_mode"] = self.execution_mode
        if self.extra:
            cfg.update(self.extra)
        return cfg


class LogTaskConfig(BaseModel):
    """实时日志采集任务配置，对应 proto 的 LogTaskConfig。"""

    source_type: str = Field("file", description="日志源类型: file / syslog / tcp / udp")
    source_config: Dict[str, Any] = Field(
        default_factory=dict, description="日志源配置（如文件路径）"
    )
    collect_interval: int = Field(5, ge=1, description="采集间隔（秒）")
    batch_size: int = Field(1000, ge=1, description="批次大小")
    report_interval: int = Field(30, ge=1, description="状态上报间隔（秒）")
    extra: Dict[str, str] = Field(default_factory=dict, description="预留扩展字段")

    def to_worker_config(self) -> Dict[str, Any]:
        """转换为 worker 端 ``LogCollectorTask`` 接收的 config 字典。"""
        cfg: Dict[str, Any] = {
            "source_type": self.source_type,
            "source_config": self.source_config,
            "collect_interval": self.collect_interval,
            "batch_size": self.batch_size,
            "report_interval": self.report_interval,
        }
        if self.extra:
            cfg.update(self.extra)
        return cfg


# ---------------------------------------------------------------------------
# 任务记录
# ---------------------------------------------------------------------------
class TaskRecord(BaseModel):
    """master 端维护的任务下发记录。"""

    task_id: str
    worker_id: str
    task_kind: TaskKind
    config: Dict[str, Any]
    status: DispatchStatus = DispatchStatus.PENDING
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_dispatch_error: Optional[str] = None

    def touch(self) -> None:
        self.updated_at = time.time()


def new_task_id() -> str:
    """生成新的任务 ID。"""
    return f"task-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# API 请求 / 响应模型
# ---------------------------------------------------------------------------
class CreateScheduledTaskRequest(BaseModel):
    worker_id: str = Field(..., description="目标 worker ID")
    task_id: Optional[str] = Field(None, description="自定义任务 ID，留空自动生成")
    config: ScheduledTaskConfig


class CreateLogTaskRequest(BaseModel):
    worker_id: str = Field(..., description="目标 worker ID")
    task_id: Optional[str] = Field(None, description="自定义任务 ID，留空自动生成")
    config: LogTaskConfig


class ControlTaskRequest(BaseModel):
    worker_id: str
    task_id: str
    action: TaskAction


class TaskOut(BaseModel):
    task_id: str
    worker_id: str
    task_kind: TaskKind
    status: DispatchStatus
    config: Dict[str, Any]
    created_at: float
    updated_at: float
    last_dispatch_error: Optional[str] = None


class DispatchResult(BaseModel):
    """下发结果，同时作为 HTTP 与 gRPC 响应的统一表达。"""

    success: bool
    message: str
    worker_id: str
    task_id: str
    worker_online: bool
    timestamp: float = Field(default_factory=time.time)


class WorkerOut(BaseModel):
    worker_id: str
    status: str
    host: str
    port: int
    version: str
    last_heartbeat: float
    online: bool
