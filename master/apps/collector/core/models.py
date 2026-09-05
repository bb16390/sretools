"""采集模块数据模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, Column, Text, func

from master.libs.fastapi_amis_admin.models import ChoiceType, Field, SQLModel


class CollectorType(str, Enum):
    DATABASE = "database"
    HTTP = "http"
    WEBSOCKET = "websocket"


class StorageType(str, Enum):
    DATABASE = "database"
    HTTP = "http"
    FILE = "file"
    KAFKA = "kafka"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class ExecStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"


class ScheduleType(str, Enum):
    CRON = "cron"
    INTERVAL = "interval"
    DATE = "date"


def _uuid_str() -> str:
    return str(uuid.uuid4()).replace("-", "")


# ---------- 采集任务表 ----------


class _CollectorTaskBase(SQLModel):
    name: str = Field(..., title="任务名称", max_length=100)
    description: str = Field(
        default="",
        title="任务描述",
        max_length=500,
        amis_form_item="textarea",
    )
    collector_type: CollectorType = Field(
        CollectorType.HTTP,
        title="采集方式",
        sa_type=ChoiceType(CollectorType, impl=str),
    )
    collector_config: dict[str, Any] = Field(
        default_factory=dict,
        title="采集配置",
        sa_column=Column(JSON, nullable=False),
        amis_form_item={"type": "input-json"},
        amis_table_column={"type": "json"},
    )
    schedule_type: ScheduleType = Field(
        ScheduleType.CRON,
        title="调度类型",
        sa_type=ChoiceType(ScheduleType, impl=str),
    )
    schedule_config: dict[str, Any] = Field(
        default_factory=dict,
        title="调度配置",
        description="cron: {day_of_week, hour, minute, second} 或 {expression}; "
        "interval: {weeks, days, hours, minutes, seconds}; "
        "date: {run_date}",
        sa_column=Column(JSON, nullable=False),
        amis_form_item={"type": "input-json"},
        amis_table_column={"type": "json"},
    )
    storage_type: StorageType = Field(
        StorageType.DATABASE,
        title="存储类型",
        sa_type=ChoiceType(StorageType, impl=str),
    )
    storage_config: dict[str, Any] = Field(
        default_factory=dict,
        title="存储配置",
        sa_column=Column(JSON, nullable=False),
        amis_form_item={"type": "input-json"},
        amis_table_column={"type": "json"},
    )
    enabled: bool = Field(True, title="是否启用")
    timeout: int = Field(30, title="超时时间(秒)", ge=1, le=3600)


class CollectorTask(_CollectorTaskBase, table=True):
    __tablename__ = "collector_task"

    id: Optional[str] = Field(
        default_factory=_uuid_str,
        primary_key=True,
        title="任务ID",
        max_length=32,
    )
    status: TaskStatus = Field(
        TaskStatus.PENDING,
        title="任务状态",
        sa_type=ChoiceType(TaskStatus, impl=str),
    )
    apscheduler_job_id: Optional[str] = Field(
        None,
        title="APScheduler Job ID",
        max_length=64,
    )
    last_run_at: Optional[datetime] = Field(None, title="上次执行时间")
    last_run_status: Optional[ExecStatus] = Field(
        None,
        title="上次执行结果",
        sa_type=ChoiceType(ExecStatus, impl=str),
    )
    last_run_duration_ms: Optional[int] = Field(None, title="上次执行耗时(ms)")
    total_success_count: int = Field(0, title="总成功次数")
    total_failed_count: int = Field(0, title="总失败次数")
    created_at: datetime = Field(
        default_factory=datetime.now,
        title="创建时间",
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        title="更新时间",
        sa_column_kwargs={"onupdate": func.now(), "server_default": func.now()},
    )


# ---------- 采集执行日志表 ----------


class _CollectorLogBase(SQLModel):
    task_id: str = Field(
        ..., title="任务ID", max_length=32, foreign_key="collector_task.id"
    )
    trigger: str = Field(
        "scheduler",
        title="触发方式",
        max_length=20,
        description="scheduler / manual",
    )
    status: ExecStatus = Field(
        ExecStatus.RUNNING,
        title="执行状态",
        sa_type=ChoiceType(ExecStatus, impl=str),
    )
    started_at: datetime = Field(default_factory=datetime.now, title="开始时间")
    finished_at: Optional[datetime] = Field(None, title="结束时间")
    duration_ms: Optional[int] = Field(None, title="耗时(ms)")
    rows_count: Optional[int] = Field(None, title="采集行数")
    error_message: Optional[str] = Field(
        None,
        title="错误信息",
        sa_column=Column(Text, nullable=True),
    )
    storage_result: Optional[dict[str, Any]] = Field(
        None,
        title="存储结果",
        sa_column=Column(JSON, nullable=True),
        amis_table_column={"type": "json"},
    )


class CollectorLog(_CollectorLogBase, table=True):
    __tablename__ = "collector_log"

    id: Optional[int] = Field(default=None, primary_key=True, title="日志ID")
    sample_data: Optional[dict[str, Any]] = Field(
        None,
        title="采集样例数据",
        sa_column=Column(JSON, nullable=True),
        amis_table_column={"type": "json"},
    )
    raw_data_size: Optional[int] = Field(None, title="原始数据大小(bytes)")


# ---------- Pydantic Schemas ----------


class CollectorTaskCreate(_CollectorTaskBase):
    pass


class CollectorTaskUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    collector_type: Optional[CollectorType] = None
    collector_config: Optional[dict[str, Any]] = None
    schedule_type: Optional[ScheduleType] = None
    schedule_config: Optional[dict[str, Any]] = None
    storage_type: Optional[StorageType] = None
    storage_config: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None
    timeout: Optional[int] = None


class CollectorTaskOut(_CollectorTaskBase):
    id: str
    status: TaskStatus
    apscheduler_job_id: Optional[str] = None
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[ExecStatus] = None
    last_run_duration_ms: Optional[int] = None
    total_success_count: int = 0
    total_failed_count: int = 0
    created_at: datetime
    updated_at: datetime
