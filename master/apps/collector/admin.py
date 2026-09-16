import time
import uuid
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

# 优先 orjson（spec 推荐），未安装时回退到标准库 json，保证模块可被 import。
# spec 允许 ``orjson.loads`` 或 ``json.loads`` 二选一。
try:
    import orjson

    _json_loads = orjson.loads
except ImportError:  # pragma: no cover - 部署环境通常装了 orjson
    import json

    _json_loads = json.loads

from apps.collector import jobs
from apps.collector.models import CollectorTask, DataSource, Opsteam, Subsystem
from common.transform_runner import apply_transform
from core.globals import site
from fastapi import Body, HTTPException
from libs.fastapi_amis_admin import admin
from libs.fastapi_amis_admin.admin import AdminAction, AdminApp
from libs.fastapi_amis_admin.amis import (
    Action,
    ActionType,
    AmisAPI,
    Dialog,
    Form,
    Picker,
    Remark,
    SchemaNode,
    Service,
    TableCRUD,
)
from libs.fastapi_amis_admin.amis.components import PageSchema
from libs.fastapi_amis_admin.crud import BaseApiOut
from libs.fastapi_amis_admin.crud.utils import ItemIdListDepend
from libs.fastapi_amis_admin.utils.pydantic import ModelField
from sqlalchemy import event, select
from sqlmodel.sql.expression import Select
from starlette.requests import Request


def _get_grpc_helpers():
    """懒导入 ``grpc_server.server`` 的下发辅助函数。

    master 运行时 ``master/`` 已在 ``sys.path`` 上，可直接 import；
    若 gRPC 模块不可用（例如仅启动 HTTP 子集），返回 ``(None, None)``，
    由调用方决定回退策略。apis.py 采用同样的懒导入模式。
    """
    try:
        from grpc_server.server import get_servicer, list_workers  # type: ignore
    except ImportError:
        return None, None
    return get_servicer, list_workers


def _load_sql_adapter():
    """懒导入 worker 端 ``SqlAdapter`` 供 master 本地预览回退使用。

    master 启动时通常 ``/workspace`` 在 ``sys.path``，可直接
    ``from worker.adapter.sql_adapter import SqlAdapter``；若 worker 包
    不可用则返回 None，预览将无法走本地回退（需提供 worker_id）。
    """
    try:
        from worker.adapter.sql_adapter import SqlAdapter  # type: ignore
    except ImportError:
        return None
    return SqlAdapter


@site.register_admin
class CollectorApp(admin.AdminApp):
    page_schema = PageSchema(label="数据采集", icon="fa fa-bolt")
    router_prefix = "/collector"

    def __init__(self, app: "AdminApp"):
        super().__init__(app)
        self.register_admin(DataSourceAdmin)
        self.register_admin(CollectorTaskAdmin)


class DataSourceAdmin(admin.ModelAdmin):
    """
    数据源管理
    """

    group_schema = None
    page_schema = PageSchema(label="数据源", icon="fa fa-database")
    model = DataSource
    list_display = [
        DataSource.node,
        DataSource.name,
        DataSource.collector_type,
        DataSource.database_type,
        DataSource.url,
        DataSource.username,
        DataSource.status,
    ]
    exclude = [DataSource.password]

    async def get_form_item_on_foreign_key(
        self, request: Request, modelfield: ModelField, is_filter: bool = False
    ) -> Union[Service, SchemaNode, None]:
        column = self.parser.get_column(modelfield.alias)
        if column is None:
            return None
        foreign_keys = list(column.foreign_keys) or None
        if foreign_keys is None:
            return None
        admin = self.app.site.get_model_admin(foreign_keys[0].column.table.name)
        if not admin:
            return None
        url = admin.router_path + admin.page_path
        label = modelfield.field_info.title or modelfield.name
        remark = (
            Remark(content=modelfield.field_info.description)
            if modelfield.field_info.description
            else None
        )
        picker = Picker(
            name=modelfield.alias,
            label=label,
            labelField="subsystem",
            valueField="id",
            required=(modelfield.field_info.is_required() and not is_filter),
            modalMode="dialog",
            inline=is_filter,
            size="full",
            labelRemark=remark,
            pickerSchema="${body}",
            source="${body.api}",
        )
        return Service(
            name=modelfield.alias,
            schemaApi=AmisAPI(
                method="post",
                url=url,
                data={},
                cache=300000,
                responseData={"controls": [picker]},
            ),
        )

    async def on_update_pre(
        self, request: Request, obj, item_id: list[int], **kwargs
    ) -> dict[str, Any]:
        data = await super().on_update_pre(request, obj, item_id, **kwargs)
        password = data.get("password", None)
        if password is not None:
            decrypt_password = password.get_secret_value()
            if decrypt_password == "**********":
                password = await self.db.async_scalar(
                    Select(DataSource.password).where(DataSource.id == item_id[0])
                )
                data["password"] = password.get_secret_value()
        return data

    def register_router(self):
        @self.router.post("/database_options", include_in_schema=True)
        async def database_options():
            stmt = Select(
                DataSource.node,
                DataSource.id,
                DataSource.name,
                DataSource.collector_type,
                DataSource.database_type,
                DataSource.url,
                DataSource.username,
            )

            result = await self.db.async_execute(stmt)
            options = self.parser.conv_row_to_dict(result.all())
            options = [
                dict(t) for t in {tuple(sorted(t.items())): t for t in options}.values()
            ]

            # 拼接label字段
            options = [
                {**item, "label": f"{item['node']}_{item['name']}"} for item in options
            ]

            return BaseApiOut(msg="", data={"options": options})

        return super().register_router()


class CollectorTaskAdmin(admin.ModelAdmin):
    """
    采集任务管理
    """

    group_schema = None
    page_schema = PageSchema(label="采集任务", icon="fa fa-clock-o")
    model = CollectorTask
    list_filter = [
        Subsystem.subsystem,
        CollectorTask.id,
        CollectorTask.name,
        CollectorTask.collector_type,
        CollectorTask.status,
    ]

    search_fields = [
        Subsystem.subsystem,
        CollectorTask.name,
        CollectorTask.collector_type,
        CollectorTask.status,
    ]

    # 创建时排除的字段
    create_exclude = {
        "job_id",
        "last_run_time",
        "last_run_status",
        "last_run_duration_ms",
        "total_failed_count",
        "total_run_count",
        "create_time",
        "update_time",
    }

    # 更新时排除的字段
    update_exclude = {
        "id",
        "job_id",
        "last_run_time",
        "last_run_status",
        "last_run_duration_ms",
        "total_failed_count",
        "total_run_count",
        "create_time",
        "update_time",
    }

    # 读取时显示的字段
    read_fields = [
        CollectorTask.name,
        CollectorTask.collector_type,
        CollectorTask.status,
        CollectorTask.timeout,
        CollectorTask.transform_script,
        CollectorTask.conf,
        CollectorTask.job_id,
        CollectorTask.subsystem_id,
        CollectorTask.create_time,
        CollectorTask.update_time,
    ]

    admin_action_maker = [
        lambda admin: AdminAction(
            admin=admin,
            name="暂停",
            action=ActionType.Ajax(
                icon="fa fa-pause",
                tooltip="暂停",
                confirmText="确认暂停选中任务?",
                api="/admin/collector/CollectorTaskAdmin/control/${ids || id|raw}?actio=pause",
            ),
            flags=["item", "bulk"],
        ),
        lambda admin: AdminAction(
            admin=admin,
            name="恢复",
            action=ActionType.Ajax(
                icon="fa fa-play",
                tooltip="恢复",
                confirmText="确认恢复选中任务?",
                api="/admin/collector/CollectorTaskAdmin/control/${ids || id|raw}?actio=resume",
            ),
            flags=["item", "bulk"],
        ),
        lambda admin: AdminAction(
            admin=admin,
            name="预览",
            action=ActionType.Dialog(
                label="预览",
                dialog=Dialog(
                    title="预览",
                    id="preview-dialog",
                    size="lg",
                    body=Service(
                        schemaApi=AmisAPI(
                            method="post",
                            url="/admin/collector/CollectorTaskAdmin/preview?form_type=list",
                            data={
                                "name": "${name}",
                                "collector_type": "${collector_type}",
                                "timeout": "${timeout}",
                                "transform_script": "${transform_script}",
                                "status": "${status}",
                                "conf": "${conf}",
                                "subsystem_id": "${subsystem_id}",
                            },
                        ),
                    ),
                    actions=[],
                ),
                hiddenOnHover=True,
            ),
            flags=["item"],
        ),
    ]

    def __init__(self, app: "AdminApp"):
        super().__init__(app)

    async def get_select(self, request: Request) -> Select:
        sel = await super().get_select(request)
        return sel.outerjoin(
            Subsystem, CollectorTask.subsystem_id == Subsystem.id
        ).outerjoin(Opsteam, Subsystem.team_id == Opsteam.id)

    async def get_create_action(
        self, request: Request, bulk: bool = False
    ) -> Optional[Action]:
        action = await super().get_create_action(request, bulk)
        action.dialog.body.id = "create"

        action.dialog.actions = [
            Action(
                label="预览",
                actionType="button",
                onEvent={
                    "click": {
                        "actions": [
                            {
                                "actionType": "dialog",
                                "dialog": {
                                    "id": "preview_dialog",
                                    "size": "lg",
                                    "body": {
                                        "type": "service",
                                        "schemaApi": {
                                            "method": "post",
                                            "url": "/admin/collector/CollectorTaskAdmin/preview",
                                            "data": {
                                                "name": "${name}",
                                                "collector_type": "${collector_type}",
                                                "timeout": "${timeout}",
                                                "transform_script": "${transform_script}",
                                                "status": "${status}",
                                                "conf": "${conf}",
                                                "subsystem_id": "${subsystem_id}",
                                            },
                                        },
                                        "onEvent": {
                                            "fetchSchemaInited": {
                                                "actions": [
                                                    {
                                                        "actionType": "setValue",
                                                        "componentId": "create",
                                                        "args": {
                                                            "value": {
                                                                "status": "${event.data.responseStatus}"
                                                            }
                                                        },
                                                    },
                                                ],
                                            },
                                        },
                                    },
                                    "actions": [],
                                },
                            }
                        ]
                    }
                },
            ),
            Action(label="取消", actionType="cancel"),
            Action(label="提交", actionType="submit", primary=True),
        ]
        action.dialog.body.api = AmisAPI(
            method="post",
            url=f"{self.router_path}/item",
            data={
                "name": "${name}",
                "collector_type": "${collector_type}",
                "timeout": "${timeout}",
                "transform_script": "${transform_script}",
                "status": "${status}",
                "conf": "${ENCODEJSON(conf)}",
                "subsystem_id": "${subsystem_id}",
            },
        )
        return action

    async def get_update_form(self, request: Request, bulk: bool = False) -> Form:
        form = await super().get_update_form(request, bulk)
        if not bulk:
            if self.schema_read:
                form.initApi = AmisAPI(
                    method="get",
                    url=f"{self.router_path}/item/${self.pk_name}",
                    responseData={
                        "name": "${name}",
                        "collector_type": "${collector_type}",
                        "timeout": "${timeout}",
                        "transform_script": "${transform_script}",
                        "status": "${status}",
                        "conf": "${DECODERJSON(conf)}",
                        "subsystem_id": "${subsystem_id}",
                    },
                )
                form.api = AmisAPI(
                    method="put",
                    url=f"{self.router_path}/item/${self.pk_name}",
                    data={
                        "name": "${name}",
                        "collector_type": "${collector_type}",
                        "timeout": "${timeout}",
                        "transform_script": "${transform_script}",
                        "status": "${status}",
                        "conf": "${ENCODEJSON(conf)}",
                        "subsystem_id": "${subsystem_id}",
                    },
                )
        return form

    async def get_read_form(self, request: Request) -> Form:
        form = await super().get_read_form(request)
        form.initApi = AmisAPI(
            method="get",
            url=f"{self.router_path}/item/${self.pk_name}",
            responseData={
                "name": "${name}",
                "collector_type": "${collector_type}",
                "timeout": "${timeout}",
                "transform_script": "${transform_script}",
                "status": "${status}",
                "conf": "${DECODERJSON(conf)}",
                "job_id": "${job_id}",
                "worker_id": "${worker_id}",
                "subsystem_id": "${subsystem_id}",
                "update_time": "${update_time}",
                "create_time": "${create_time}",
            },
        )
        return form

    async def get_list_table(self, request: Request) -> TableCRUD:
        table = await super().get_list_table(request)

        table.selectable = True

        table.id = "crud"

        table.columns = [
            column.model_copy(update={"quickEdit": None})
            if (column.name in ["status", "conf", "worker_id"])
            else column
            for column in table.columns
        ]

        table.quickSaveItemApi = AmisAPI(
            method="put",
            url=f"{self.router_path}/item/${self.pk_name}",
            data={
                "name": "${name}",
                "collector_type": "${collector_type}",
                "timeout": "${timeout}",
                "transform_script": "${transform_script}",
                "status": "${status}",
                "conf": "${ENCODEJSON(conf)}",
                "subsystem_id": "${subsystem_id}",
            },
        )
        return table

    async def get_form_item_on_foreign_key(
        self, request: Request, modelfield: ModelField, is_filter: bool = False
    ) -> Union[Service, SchemaNode, None]:
        column = self.parser.get_column(modelfield.alias)
        if column is None:
            return None
        foreign_keys = list(column.foreign_keys) or None
        if foreign_keys is None:
            return None
        admin = self.app.site.get_model_admin(foreign_keys[0].column.table.name)
        if not admin:
            return None
        url = admin.router_path + admin.page_path
        label = modelfield.field_info.title or modelfield.name
        remark = (
            Remark(content=modelfield.field_info.description)
            if modelfield.field_info.description
            else None
        )
        picker = Picker(
            name=modelfield.alias,
            label=label,
            labelField="subsystem",
            valueField="id",
            required=(modelfield.field_info.is_required() and not is_filter),
            modalMode="dialog",
            inline=is_filter,
            size="full",
            labelRemark=remark,
            pickerSchema="${body}",
            source="${body.api}",
        )
        return Service(
            name=modelfield.alias,
            schemaApi=AmisAPI(
                method="post",
                url=url,
                data={},
                cache=300000,
                responseData={"controls": [picker]},
            ),
        )

    async def on_create_pre(
        self, request: Request, obj, **kwargs
    ) -> Dict[str, Any]:
        """创建任务前置校验：必须携带有效的 ``preview_token``。

        从原始请求体读取 ``preview_token``，通过
        ``jobs.consume_preview_token`` 校验：token 有效且 payload 中
        ``success==True`` 才放行；否则抛 ``HTTPException(400)``，
        fastapi_amis_admin 会将其包装为 ``BaseApiOut(status=-1)``。
        校验通过后正常走默认创建流程，``transform_script`` 已在 schema
        中，会随任务保存到 ``CollectorTask.transform_script``，供下发时
        携带到 worker。本步骤不下发任务（下发由 dispatch 路由触发）。
        """
        token = ""
        try:
            body = await request.json()
            if isinstance(body, dict):
                token = body.get("preview_token", "") or ""
        except Exception:  # noqa: BLE001
            token = ""
        payload = jobs.consume_preview_token(token) if token else None
        if payload is None or not payload.get("success"):
            raise HTTPException(
                status_code=400, detail="preview required or preview failed"
            )
        return await super().on_create_pre(request, obj, **kwargs)

    def register_router(self):
        @self.router.post("/control/{item_id}", include_in_schema=True)
        async def control(
            item_id: ItemIdListDepend,
            action: Literal["start", "stop"],
            data: Annotated[self.schema_update, Body()] = None,
        ): ...

        @self.router.post("/preview", include_in_schema=True)
        async def preview(form_type: str = "preview", payload: dict = Body(...)):
            """采集任务预览：执行试采 + 应用 ``transform_script`` 转换 + 签发 preview_token。

            接受 AMIS schemaApi 提交的 JSON body（name / collector_type /
            timeout / transform_script / status / conf / subsystem_id，
            以及可选的 ``worker_id``）。返回::

                {success, rows, raw_rows_count, rows_count, duration_ms,
                 worker_id, preview_token}
            或失败时::

                {success:false, error, duration_ms, error_kind}
            """
            conf_raw = payload.get("conf")
            # conf 在 AMIS 提交时通常为 JSON 字符串；也兼容已解析的 dict
            if isinstance(conf_raw, str):
                try:
                    conf = _json_loads(conf_raw) if conf_raw else {}
                except Exception:
                    return {
                        "success": False,
                        "error": "invalid conf json",
                        "duration_ms": 0,
                        "error_kind": "conf_error",
                    }
            elif isinstance(conf_raw, dict):
                conf = conf_raw
            elif conf_raw is None:
                conf = {}
            else:
                return {
                    "success": False,
                    "error": "invalid conf json",
                    "duration_ms": 0,
                    "error_kind": "conf_error",
                }

            worker_id = payload.get("worker_id", "") or ""
            transform_script = payload.get("transform_script", "") or ""
            sql = conf.get("sql", "") or ""
            is_trading_day = bool(
                conf.get("is_trading_day", conf.get("trade_day_only", False))
            )

            # 源数据源 ID 列表：优先 src_datasource（list[int]），回退 src_database
            src_ids_raw = conf.get("src_datasource")
            if src_ids_raw is None:
                src_ids_raw = conf.get("src_database")
            src_ids: List[int] = []
            if isinstance(src_ids_raw, (list, tuple)):
                src_ids = [int(i) for i in src_ids_raw if i not in (None, "")]
            elif isinstance(src_ids_raw, str) and src_ids_raw.strip():
                src_ids = [
                    int(p)
                    for p in src_ids_raw.split(",")
                    if p.strip() not in ("", None)
                ]
            if not src_ids:
                return {
                    "success": False,
                    "error": "no src_datasource configured",
                    "duration_ms": 0,
                    "error_kind": "conf_error",
                }

            # 查询源数据源行（含 url / username / password 供本地试采）
            ds_stmt = select(DataSource).where(DataSource.id.in_(src_ids))
            ds_rows = (await self.db.async_execute(ds_stmt)).scalars().all()
            if not ds_rows:
                return {
                    "success": False,
                    "error": "src datasource not found",
                    "duration_ms": 0,
                    "error_kind": "conf_error",
                }

            SqlAdapter = _load_sql_adapter()
            if SqlAdapter is None:
                return {
                    "success": False,
                    "error": "sql adapter unavailable on master; please provide a worker_id",
                    "duration_ms": 0,
                    "error_kind": "no_adapter",
                }

            if not sql:
                return {
                    "success": False,
                    "error": "sql is empty",
                    "duration_ms": 0,
                    "error_kind": "conf_error",
                }

            start = time.time()
            rows: Any = []
            collect_error: Optional[str] = None
            # 取第一个源数据源执行试采作为预览样例（spec：first is fine）。
            # 即便请求体携带了 worker_id 且该 worker 在线，本实现也只做
            # master 本地 SqlAdapter 一次性执行，不真正向 worker 推送长
            # 周期任务，以保证预览原子、可回滚。worker_id 仅用于响应中
            # 标记预期下发目标。
            target_ds = ds_rows[0]
            try:
                adapter = SqlAdapter(url=target_ds.url)
                rows = await adapter.execute(sql)
                if not isinstance(rows, list):
                    rows = list(rows) if rows is not None else []
            except Exception as exc:  # noqa: BLE001
                collect_error = str(exc)
            duration_ms = int((time.time() - start) * 1000)

            if collect_error is not None:
                return {
                    "success": False,
                    "error": collect_error,
                    "duration_ms": duration_ms,
                    "error_kind": "collect_error",
                }

            raw_rows_count = len(rows) if isinstance(rows, list) else 0

            # 应用 transform_script 转换
            if transform_script:
                ok, transformed, err_type = apply_transform(
                    transform_script, rows, conf
                )
                if not ok:
                    return {
                        "success": False,
                        "error": transformed,
                        "duration_ms": duration_ms,
                        "error_kind": err_type,
                    }
                rows = transformed
                if isinstance(rows, list):
                    rows_count = len(rows)
                else:
                    rows_count = raw_rows_count
            else:
                rows_count = raw_rows_count

            preview_rows = rows[:10] if isinstance(rows, list) else rows
            token = jobs.issue_preview_token(
                {
                    "success": True,
                    "raw_rows_count": raw_rows_count,
                    "rows_count": rows_count,
                    "worker_id": worker_id,
                    "conf_snapshot": conf,
                    "transform_script": transform_script,
                    "is_trading_day": is_trading_day,
                }
            )

            return {
                "success": True,
                "rows": preview_rows,
                "raw_rows_count": raw_rows_count,
                "rows_count": rows_count,
                "duration_ms": duration_ms,
                "worker_id": worker_id,
                "preview_token": token,
            }

        @self.router.post("/dispatch", include_in_schema=True)
        async def dispatch(payload: dict = Body(...)):
            """将采集任务下发到指定 worker。

            请求体: ``{task_id, worker_id}``。校验 worker 在线后，从
            ``CollectorTask`` + 关联 ``DataSource`` + ``conf`` 派生 worker
            config，通过 gRPC ``push_task_update`` 推送
            ``action="task_create"``，并回写 ``CollectorTask.worker_id`` 与
            ``job_id``（master 分配的 UUID）。
            """
            task_id = payload.get("task_id")
            worker_id = payload.get("worker_id")
            if not task_id or not worker_id:
                return BaseApiOut(status=-1, msg="task_id and worker_id required")

            get_servicer, list_workers = _get_grpc_helpers()
            if get_servicer is None or list_workers is None:
                return BaseApiOut(status=-1, msg="gRPC server not started")
            servicer = get_servicer()
            if servicer is None:
                return BaseApiOut(status=-1, msg="gRPC server not started")

            try:
                workers = list_workers()
            except Exception as exc:  # noqa: BLE001
                return BaseApiOut(status=-1, msg=f"list workers failed: {exc}")
            online = any(
                w.get("worker_id") == worker_id and w.get("status") == "online"
                for w in (workers or [])
            )
            if not online:
                return BaseApiOut(status=-1, msg="worker not found or offline")

            # 使用独立 session 加载并更新任务，避免与请求作用域 session 事务状态耦合
            async with self.db.session_maker() as sess:
                task = (
                    (
                        await sess.execute(
                            select(CollectorTask).where(
                                CollectorTask.id == int(task_id)
                            )
                        )
                    )
                    .scalars()
                    .first()
                )
                if task is None:
                    return BaseApiOut(status=-1, msg="task not found")

                ds_stmt = select(DataSource).where(
                    DataSource.id == task.data_source_id
                )
                ds = (await sess.execute(ds_stmt)).scalars().first()
                if ds is None:
                    return BaseApiOut(status=-1, msg="data source not found")

                # collector_type -> worker task_type
                type_map = {
                    0: "database_collector",
                    1: "kafka_collector",
                    2: "database_collector",
                    3: "database_collector",
                }
                task_type = type_map.get(task.collector_type, "database_collector")

                try:
                    conf = _json_loads(task.conf) if task.conf else {}
                except Exception:  # noqa: BLE001
                    conf = {}

                password_val = ""
                if ds.password is not None:
                    password_val = ds.password.get_secret_value()
                worker_config = {
                    "cron_expression": conf.get(
                        "trigger_expr", "interval(seconds=60)"
                    ),
                    "adapter_type": "sql",
                    "adapter_config": {
                        "url": ds.url,
                        "username": ds.username,
                        "password": password_val,
                    },
                    "query": conf.get("sql", ""),
                    "trade_day_only": bool(conf.get("is_trading_day", False)),
                    "transform_script": task.transform_script or "",
                    "timeout": task.timeout,
                    "master_task_id": str(task.id),
                }

                job_id = str(uuid.uuid4())
                ok = servicer.push_task_update(
                    worker_id,
                    {
                        "task_id": str(task.id),
                        "action": "task_create",
                        "task_type": task_type,
                        "config": worker_config,
                        "timestamp": time.time(),
                    },
                )
                if not ok:
                    return BaseApiOut(
                        status=-1, msg="failed to push task to worker"
                    )

                task.worker_id = worker_id
                task.job_id = job_id
                await sess.commit()

            return BaseApiOut(data={"worker_id": worker_id, "job_id": job_id})

        return super().register_router()

    def _register_db_events(self):
        """注册数据库事件"""

        @event.listens_for(CollectorTask, "after_insert")
        async def after_insert(mapper, connection, target):
            await self.db.commit()

        @event.listens_for(CollectorTask, "after_update")
        async def after_update(mapper, connection, target): ...

        @event.listens_for(CollectorTask, "after_delete")
        async def after_delete(mapper, connection, target): ...
