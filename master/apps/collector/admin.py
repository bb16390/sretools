"""采集模块前端管理页。

基于 fastapi_amis_admin 的 AdminApp / ModelAdmin：
- 任务列表（ModelAdmin）：增删改查 + 启停/暂停/手动执行操作按钮
- 执行日志（ModelAdmin）：查询 + 详情
- 仪表盘（PageAdmin）：快速统计与快捷操作
"""
from __future__ import annotations

from typing import Any

from fastapi_amis_admin import admin, amis
from fastapi_amis_admin.admin import AdminApp
from fastapi_amis_admin.amis import (
    ActionType,
    Form,
    Grid,
    LevelEnum,
    Page,
    PageSchema,
    Tabs,
)
from fastapi_amis_admin.amis.components import ColumnOperation, GridColumn, TableCRUD
from fastapi_amis_admin.crud import BaseApiOut
from sqlalchemy import desc, func, select
from starlette.requests import Request

from .core.models import (
    CollectorLog,
    CollectorTask,
    CollectorType,
    ExecStatus,
    ScheduleType,
    StorageType,
    TaskStatus,
)

# 全局调度器引用，在 api.py / main.py 启动时设置
_scheduler_ref: list[Any] = [None]


def set_collector_scheduler(scheduler: Any) -> None:
    _scheduler_ref[0] = scheduler


def _get_scheduler():
    return _scheduler_ref[0]


# ---------------------------------------------------------------------------
# AdminApp 分组
# ---------------------------------------------------------------------------


class CollectorAdminApp(admin.AdminApp):
    """采集分组应用。在 master/main.py 通过 site.register_admin 注册。"""

    page_schema = PageSchema(label="数据采集", icon="fa fa-database")

    def __init__(self, app: "AdminApp") -> None:
        super().__init__(app)
        self.register_admin(CollectorDashboardAdmin)
        self.register_admin(CollectorTaskAdmin)
        self.register_admin(CollectorLogAdmin)


# ---------------------------------------------------------------------------
# 仪表盘
# ---------------------------------------------------------------------------


class CollectorDashboardAdmin(admin.PageAdmin):
    """采集仪表盘：总览 + 快捷操作。"""

    page_schema = PageSchema(label="仪表盘", icon="fa fa-tachometer-alt")

    async def get_page(self, request: Request) -> Page:  # type: ignore[override]
        # 统计数
        async with self.db.async_session() as sess:
            total_tasks = (await sess.execute(
                select(func.count(CollectorTask.id))
            )).scalar_one()
            enabled_tasks = (await sess.execute(
                select(func.count(CollectorTask.id)).where(CollectorTask.enabled.is_(True))
            )).scalar_one()
            total_logs = (await sess.execute(
                select(func.count(CollectorLog.id))
            )).scalar_one()
            success_logs_24h = (await sess.execute(
                select(func.count(CollectorLog.id)).where(
                    CollectorLog.status == ExecStatus.SUCCESS,
                )
            )).scalar_one()
            # 最近 10 条日志
            recent = (await sess.execute(
                select(CollectorLog).order_by(desc(CollectorLog.started_at)).limit(10)
            )).scalars().all()
            # 最近任务
            tasks = (await sess.execute(
                select(CollectorTask).order_by(desc(CollectorTask.updated_at)).limit(5)
            )).scalars().all()

        recent_rows = [
            {
                "id": item.id,
                "task_id": item.task_id,
                "trigger": item.trigger,
                "status": item.status.value if hasattr(item.status, "value") else str(item.status),
                "started_at": item.started_at.strftime("%Y-%m-%d %H:%M:%S") if item.started_at else "",
                "duration_ms": item.duration_ms,
                "rows_count": item.rows_count,
                "error": (item.error_message or "")[:80],
            }
            for item in recent
        ]
        task_rows = [
            {
                "id": t.id,
                "name": t.name,
                "collector_type": t.collector_type.value if hasattr(t.collector_type, "value") else str(t.collector_type),
                "storage_type": t.storage_type.value if hasattr(t.storage_type, "value") else str(t.storage_type),
                "enabled": t.enabled,
                "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                "success": t.total_success_count,
                "failed": t.total_failed_count,
                "last_run": t.last_run_at.strftime("%m-%d %H:%M:%S") if t.last_run_at else "-",
            }
            for t in tasks
        ]

        def stat_card(label, value, icon, color):
            return amis.Card(
                    header=amis.CardHeader(title=label),
                    body=[
                        amis.Tpl(
                            tpl=(
                                f'<div style="display:flex;align-items:center;gap:12px">'
                                f'<i class="fa {icon} fa-3x" style="color:{color}"></i>'
                                f'<span style="font-size:32px;font-weight:700">{value}</span>'
                                f'</div>'
                            ),
                        ),
                    ],
                )

        return amis.Page(
            title="采集仪表盘",
            body=[
                Grid(
                    columns=[
                        GridColumn(body=stat_card("任务总数", total_tasks, "fa-tasks", "#2f54eb"), md=3),
                        GridColumn(body=stat_card("已启用", enabled_tasks, "fa-check-circle", "#52c41a"), md=3),
                        GridColumn(body=stat_card("总执行次数", total_logs, "fa-list-alt", "#1890ff"), md=3),
                        GridColumn(body=stat_card("成功次数", success_logs_24h, "fa-smile", "#faad14"), md=3),
                    ],
                ),
                amis.Divider(),
                Tabs(
                    tabs=[
                        amis.Tab(
                            title="最近任务",
                            tab=amis.Table(
                                columns=[
                                    amis.TableColumn(name="name", label="名称"),
                                    amis.TableColumn(name="collector_type", label="采集"),
                                    amis.TableColumn(name="storage_type", label="存储"),
                                    amis.TableColumn(name="enabled", label="启用", type="mapping",
                                                     map={"true": "是", "false": "否"}),
                                    amis.TableColumn(name="status", label="状态"),
                                    amis.TableColumn(name="success", label="成功"),
                                    amis.TableColumn(name="failed", label="失败"),
                                    amis.TableColumn(name="last_run", label="上次运行"),
                                ],
                                source="${tasks}",
                            ),
                        ),
                        amis.Tab(
                            title="最近执行",
                            tab=amis.Table(
                                columns=[
                                    amis.TableColumn(name="id", label="ID"),
                                    amis.TableColumn(name="task_id", label="任务ID"),
                                    amis.TableColumn(name="trigger", label="触发"),
                                    amis.TableColumn(name="status", label="状态", type="mapping",
                                                     map={
                                                         "success": '<span class="label label-success">成功</span>',
                                                         "failed": '<span class="label label-danger">失败</span>',
                                                         "running": '<span class="label label-info">运行中</span>',
                                                     }),
                                    amis.TableColumn(name="started_at", label="开始时间"),
                                    amis.TableColumn(name="duration_ms", label="耗时(ms)"),
                                    amis.TableColumn(name="rows_count", label="行数"),
                                    amis.TableColumn(name="error", label="错误"),
                                ],
                                source="${logs}",
                            ),
                        ),
                    ],
                ),
            ],
            data={"tasks": task_rows, "logs": recent_rows},
        )


# ---------------------------------------------------------------------------
# 任务管理
# ---------------------------------------------------------------------------


_SCHEDULE_TYPE_OPTIONS = [
    {"label": "Cron 表达式", "value": ScheduleType.CRON.value},
    {"label": "固定间隔", "value": ScheduleType.INTERVAL.value},
    {"label": "单次执行", "value": ScheduleType.DATE.value},
]

_COLLECTOR_TYPE_OPTIONS = [
    {"label": "数据库 (SQL)", "value": CollectorType.DATABASE.value},
    {"label": "HTTP 请求", "value": CollectorType.HTTP.value},
    {"label": "WebSocket", "value": CollectorType.WEBSOCKET.value},
]

_STORAGE_TYPE_OPTIONS = [
    {"label": "数据库", "value": StorageType.DATABASE.value},
    {"label": "HTTP 回调", "value": StorageType.HTTP.value},
    {"label": "文件", "value": StorageType.FILE.value},
    {"label": "Kafka", "value": StorageType.KAFKA.value},
]


_STATUS_TPL = (
    '<% if (this.status === "running") { %>'
    '<span class="label label-success">运行中</span>'
    '<% } else if (this.status === "paused") { %>'
    '<span class="label label-warning">已暂停</span>'
    '<% } else if (this.status === "stopped") { %>'
    '<span class="label label-default">已停止</span>'
    '<% } else if (this.status === "error") { %>'
    '<span class="label label-danger">异常</span>'
    '<% } else { %>'
    '<span class="label label-info">等待调度</span>'
    '<% } %>'
)


class CollectorTaskAdmin(admin.ModelAdmin):
    """采集任务的 CRUD 管理。"""

    page_schema = PageSchema(label="任务管理", icon="fa fa-tasks")
    model = CollectorTask
    list_per_page = 20

    list_display = [
        CollectorTask.id,
        CollectorTask.name,
        CollectorTask.collector_type,
        CollectorTask.schedule_type,
        CollectorTask.storage_type,
        CollectorTask.enabled,
        amis.TableColumn(type="tpl", label="状态", tpl=_STATUS_TPL),
        CollectorTask.total_success_count,
        CollectorTask.total_failed_count,
        CollectorTask.last_run_at,
        CollectorTask.last_run_status,
        CollectorTask.last_run_duration_ms,
        CollectorTask.created_at,
        CollectorTask.updated_at,
    ]
    ordering = [desc(CollectorTask.updated_at)]

    list_filter = [
        CollectorTask.collector_type,
        CollectorTask.schedule_type,
        CollectorTask.storage_type,
        CollectorTask.enabled,
        CollectorTask.status,
    ]
    search_fields = [CollectorTask.name, CollectorTask.description, CollectorTask.id]

    create_fields = [
        CollectorTask.name,
        CollectorTask.description,
        CollectorTask.collector_type,
        CollectorTask.collector_config,
        CollectorTask.schedule_type,
        CollectorTask.schedule_config,
        CollectorTask.storage_type,
        CollectorTask.storage_config,
        CollectorTask.timeout,
        CollectorTask.enabled,
    ]
    update_fields = create_fields

    def __init__(self, app: AdminApp) -> None:
        super().__init__(app)
        # 自定义操作按钮 API
        self.register_router()

    async def get_list_table(self, request: Request) -> TableCRUD:
        table = await super().get_list_table(request)
        # 操作列：启用/禁用 / 暂停 / 恢复 / 立即执行 / 查看日志
        table.operations = ColumnOperation(
            label="操作",
            buttons=[
                # 启用/禁用
                amis.Button(
                    label="启用",
                    level=LevelEnum.success,
                    size="xs",
                    actionType=ActionType.Ajax,
                    confirmText="确认启用此任务？",
                    api=f"POST:{self.router_path}/${{id}}/enable",
                    visibleOn="!this.enabled",
                ),
                amis.Button(
                    label="禁用",
                    level=LevelEnum.warning,
                    size="xs",
                    actionType=ActionType.Ajax,
                    confirmText="确认禁用此任务？",
                    api=f"POST:{self.router_path}/${{id}}/disable",
                    visibleOn="this.enabled",
                ),
                # 暂停
                amis.Button(
                    label="暂停",
                    level=LevelEnum.warning,
                    size="xs",
                    actionType=ActionType.Ajax,
                    api=f"POST:{self.router_path}/${{id}}/pause",
                    visibleOn='this.status === "running"',
                ),
                # 恢复
                amis.Button(
                    label="恢复",
                    level=LevelEnum.success,
                    size="xs",
                    actionType=ActionType.Ajax,
                    api=f"POST:{self.router_path}/${{id}}/resume",
                    visibleOn='this.status === "paused"',
                ),
                # 立即执行
                amis.Button(
                    label="立即执行",
                    level=LevelEnum.primary,
                    size="xs",
                    actionType=ActionType.Ajax,
                    confirmText="确认立即手动执行一次？",
                    api=f"POST:{self.router_path}/${{id}}/run",
                ),
            ],
        )
        return table

    async def get_create_form(self, request: Request, bulk: bool = False) -> Form:
        form = await super().get_create_form(request, bulk)
        # 给用户一些默认 JSON，避免完全空
        form.body.append(
            amis.Service(
                type="service",
                api=f"get:{self.router_path}/form_templates",
                body=[
                    # 隐藏的 form 赋值器：通过 change 事件设置默认值
                ],
            )
        )
        # 直接把映射放进 data 中，用前端 JS 来应用（amis 的 onChange 方式）
        return form

    # ---------- 生命周期钩子：写入/修改后同步调度器 ----------

    async def on_create_after(self, request: Request, obj, data):
        scheduler = _get_scheduler()
        if scheduler is not None:
            try:
                await scheduler.add_or_update_job(obj)
            except Exception:  # noqa: BLE001
                import logging as _log
                _log.getLogger(__name__).exception("schedule task created failed")
                async with self.db.async_session() as sess:
                    obj.status = TaskStatus.ERROR
                    sess.add(obj)
                    await sess.commit()
        return await super().on_create_after(request, obj, data)

    async def on_update_after(self, request: Request, obj, data):
        scheduler = _get_scheduler()
        if scheduler is not None:
            try:
                await scheduler.add_or_update_job(obj)
            except Exception:  # noqa: BLE001
                import logging as _log
                _log.getLogger(__name__).exception("schedule task updated failed")
                async with self.db.async_session() as sess:
                    obj.status = TaskStatus.ERROR
                    sess.add(obj)
                    await sess.commit()
        return await super().on_update_after(request, obj, data)

    async def on_delete_after(self, request: Request, obj):
        scheduler = _get_scheduler()
        if scheduler is not None:
            try:
                await scheduler.remove_job(obj)
            except Exception:  # noqa: BLE001
                pass
        return await super().on_delete_after(request, obj)

    # ---------- 自定义路由 ----------

    def register_router(self):
        @self.router.post("/{task_id}/enable")
        async def enable_task(task_id: str):
            async with self.db.async_session() as sess:
                task = (await sess.execute(
                    select(CollectorTask).where(CollectorTask.id == task_id)
                )).scalar_one_or_none()
                if task is None:
                    return BaseApiOut(status=-1, msg="task not found")
                task.enabled = True
                sess.add(task)
                await sess.commit()
                await sess.refresh(task)
            sched = _get_scheduler()
            if sched is not None:
                await sched.add_or_update_job(task)
            return BaseApiOut(msg="enabled")

        @self.router.post("/{task_id}/disable")
        async def disable_task(task_id: str):
            async with self.db.async_session() as sess:
                task = (await sess.execute(
                    select(CollectorTask).where(CollectorTask.id == task_id)
                )).scalar_one_or_none()
                if task is None:
                    return BaseApiOut(status=-1, msg="task not found")
                task.enabled = False
                sess.add(task)
                await sess.commit()
                await sess.refresh(task)
            sched = _get_scheduler()
            if sched is not None:
                await sched.remove_job(task)
            return BaseApiOut(msg="disabled")

        @self.router.post("/{task_id}/pause")
        async def pause_task(task_id: str):
            async with self.db.async_session() as sess:
                task = (await sess.execute(
                    select(CollectorTask).where(CollectorTask.id == task_id)
                )).scalar_one_or_none()
                if task is None:
                    return BaseApiOut(status=-1, msg="task not found")
            sched = _get_scheduler()
            if sched is None:
                return BaseApiOut(status=-1, msg="scheduler not ready")
            await sched.pause_job(task)
            return BaseApiOut(msg="paused")

        @self.router.post("/{task_id}/resume")
        async def resume_task(task_id: str):
            async with self.db.async_session() as sess:
                task = (await sess.execute(
                    select(CollectorTask).where(CollectorTask.id == task_id)
                )).scalar_one_or_none()
                if task is None:
                    return BaseApiOut(status=-1, msg="task not found")
            sched = _get_scheduler()
            if sched is None:
                return BaseApiOut(status=-1, msg="scheduler not ready")
            await sched.resume_job(task)
            return BaseApiOut(msg="resumed")

        @self.router.post("/{task_id}/run")
        async def run_task(task_id: str):
            async with self.db.async_session() as sess:
                task = (await sess.execute(
                    select(CollectorTask).where(CollectorTask.id == task_id)
                )).scalar_one_or_none()
                if task is None:
                    return BaseApiOut(status=-1, msg="task not found")
            sched = _get_scheduler()
            if sched is None:
                return BaseApiOut(status=-1, msg="scheduler not ready")
            log_rec = await sched.run_task_manually(task_id)
            return BaseApiOut(data={
                "log_id": log_rec.id,
                "status": log_rec.status.value if hasattr(log_rec.status, "value") else str(log_rec.status),
                "duration_ms": log_rec.duration_ms,
                "rows_count": log_rec.rows_count,
                "error_message": log_rec.error_message,
            }, msg="manual run triggered")

        @self.router.get("/form_templates")
        async def get_form_templates():
            return BaseApiOut(data={
                "collector": {
                    CollectorType.DATABASE.value: {"url": "", "query": ""},
                    CollectorType.HTTP.value: {"url": "", "method": "GET"},
                    CollectorType.WEBSOCKET.value: {"uri": "", "message_count": 1, "duration": 10},
                },
                "storage": {
                    StorageType.DATABASE.value: {"url": "", "table": ""},
                    StorageType.HTTP.value: {"url": "", "method": "POST"},
                    StorageType.FILE.value: {"path": "", "format": "jsonl"},
                    StorageType.KAFKA.value: {"bootstrap_servers": "", "topic": ""},
                },
                "schedule": {
                    ScheduleType.CRON.value: {"expression": "*/5 * * * *"},
                    ScheduleType.INTERVAL.value: {"seconds": 60},
                    ScheduleType.DATE.value: {"run_date": ""},
                },
            })

        return super().register_router()


# ---------------------------------------------------------------------------
# 日志查询
# ---------------------------------------------------------------------------


class CollectorLogAdmin(admin.ModelAdmin):
    """执行日志查询。"""

    page_schema = PageSchema(label="执行日志", icon="fa fa-history")
    model = CollectorLog
    list_per_page = 30

    list_display = [
        CollectorLog.id,
        CollectorLog.task_id,
        CollectorLog.trigger,
        amis.TableColumn(
            type="tpl",
            label="状态",
            tpl=(
                '<% if (this.status === "success") { %>'
                '<span class="label label-success">成功</span>'
                '<% } else if (this.status === "failed") { %>'
                '<span class="label label-danger">失败</span>'
                '<% } else { %>'
                '<span class="label label-info">运行中</span>'
                '<% } %>'
            ),
        ),
        CollectorLog.started_at,
        CollectorLog.finished_at,
        CollectorLog.duration_ms,
        CollectorLog.rows_count,
        CollectorLog.raw_data_size,
    ]
    ordering = [desc(CollectorLog.started_at)]

    list_filter = [
        CollectorLog.task_id,
        CollectorLog.trigger,
        CollectorLog.status,
        CollectorLog.started_at,
    ]

    # 不允许增删改，只允许查询
    can_create = False
    can_update = False
    can_delete = False
