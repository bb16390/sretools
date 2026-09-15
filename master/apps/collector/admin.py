from typing import Annotated, Any, Literal, Optional, Union

from apps.collector.models import CollectorTask, DataSource, Opsteam, Subsystem
from core.globals import site
from fastapi import Body
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

    def register_router(self):
        @self.router.post("/control/{item_id}", include_in_schema=True)
        async def control(
            item_id: ItemIdListDepend,
            action: Literal["start", "stop"],
            data: Annotated[self.schema_update, Body()] = None,
        ): ...

        @self.router.post("/preview", include_in_schema=True)
        async def preview(
            form_type: str = "preview",
            data: Annotated[self.schema_update, Body()] = None,
        ):
            import orjson

            data = self.schema_create(**data)
            conf = orjson.loads(data.conf)

            src_db_ids = conf["src_database"].split(",")

            stmt = select(DataSource.node, DataSource.description).where(
                DataSource.id.in_(src_db_ids)
            )
            rows = await self.db.async_execute(stmt)
            rows = rows.all()

            src_databases = [n._asdict() for n in rows]

            preview_data = []

            for item in src_databases:
                preview_data.append(item)
            return preview_data

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
