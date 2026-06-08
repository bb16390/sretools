"""网关实例管理页。

使用 fastapi-amis-admin 的 PageAdmin 提供：
- 实例列表：表格 + 新增/删除/操作按钮
- 运维面板：选择实例后 start / stop / restart / status / deploy / upgrade / rollback

不依赖数据库（使用 JSON 文件存储）。
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi_amis_admin import admin, amis
from fastapi_amis_admin.admin import AdminApp
from fastapi_amis_admin.amis import Page, PageSchema
from fastapi_amis_admin.amis.components import (
    ActionType,
    Column,
    Form,
    Grid,
    InputNumber,
    InputText,
    Select,
    Service,
    TableColumn,
)
from fastapi_amis_admin.crud.schema import BaseApiOut

from ..controllers import registry
from ..core.models import GatewayInstance
from ..core.store import get_default_store

log = logging.getLogger(__name__)


class GatewayInstanceAdmin(admin.PageAdmin):
    """网关实例管理：列表 + 创建/删除/状态查询/启停"""

    page_schema = PageSchema(label="网关实例管理", icon="fa fa-server")

    async def get_page(self, request) -> Page:  # type: ignore[override]
        store = get_default_store()
        instances = store.list()

        rows: list[dict[str, Any]] = [
            {
                "id": inst.id,
                "exchange": inst.exchange,
                "kind": inst.kind,
                "name": inst.name,
                "gateway_dir": inst.gateway_dir,
                "binary_name": inst.binary_name,
                "monitor_port": inst.monitor_port,
                "version": inst.version,
            }
            for inst in instances
        ]

        return amis.Page(
            title="网关实例",
            body=[
                amis.Form(
                    title="新增实例",
                    mode="horizontal",
                    api="POST:/api/gateway/instances",
                    body=[
                        amis.InputText(name="id", label="实例 ID", required=True),
                        amis.Select(
                            name="exchange",
                            label="交易所",
                            required=True,
                            options=[
                                {"label": "深交所(szse)", "value": "szse"},
                                {"label": "上交所(sse)", "value": "sse"},
                                {"label": "北交所(bjse)", "value": "bjse"},
                            ],
                        ),
                        amis.Select(
                            name="kind",
                            label="网关类型",
                            required=True,
                            options=[
                                {"label": "行情 mdgw", "value": "mdgw"},
                                {"label": "交易 tgw", "value": "tgw"},
                            ],
                        ),
                        amis.InputText(name="name", label="名称", required=True),
                        amis.InputText(name="gateway_dir", label="安装目录", required=True),
                        amis.InputText(name="binary_name", label="二进制名", required=True),
                        amis.InputNumber(name="monitor_port", label="监控端口", required=True, min=1, max=65535),
                        amis.InputText(name="version", label="版本（可选）", value=""),
                    ],
                ),
                amis.Divider(),
                amis.Table(
                    title="实例列表",
                    columns=[
                        amis.TableColumn(name="id", label="ID"),
                        amis.TableColumn(name="exchange", label="交易所"),
                        amis.TableColumn(name="kind", label="类型"),
                        amis.TableColumn(name="name", label="名称"),
                        amis.TableColumn(name="gateway_dir", label="安装目录"),
                        amis.TableColumn(name="binary_name", label="二进制"),
                        amis.TableColumn(name="monitor_port", label="监控端口"),
                        amis.TableColumn(name="version", label="版本"),
                        amis.TableColumn(
                            type="tpl",
                            label="状态",
                            tpl=(
                                "[查看状态](post:/api/gateway/instances/${id}/status "
                                "btn:default)"
                            ),
                        ),
                        amis.TableColumn(
                            type="tpl",
                            label="操作",
                            tpl=(
                                "[启动](post:/api/gateway/instances/${id}/start btn:primary) "
                                "[停止](post:/api/gateway/instances/${id}/stop btn:warning) "
                                "[重启](post:/api/gateway/instances/${id}/restart btn:warning) "
                                "[删除](delete:/api/gateway/instances/${id} btn:danger)"
                            ),
                        ),
                    ],
                    source="${ rows }",
                    data={"rows": rows},
                ),
            ],
        )


class GatewayOpsAdmin(admin.PageAdmin):
    """网关运维面板。"""

    page_schema = PageSchema(label="网关运维", icon="fa fa-cogs")

    async def get_page(self, request) -> Page:  # type: ignore[override]
        store = get_default_store()
        instances = store.list()
        options = [{"label": f"{i.id} ({i.exchange}/{i.kind})", "value": i.id} for i in instances]

        return amis.Page(
            title="网关运维",
            body=[
                amis.Form(
                    title="批量操作",
                    body=[
                        amis.Select(
                            name="instance_id",
                            label="目标实例",
                            required=True,
                            options=options or [],
                        ),
                    ],
                    actions=[
                        amis.Action(
                            actionType=ActionType.Ajax,
                            label="启动",
                            level="primary",
                            api="POST:/api/gateway/instances/${instance_id}/start",
                        ),
                        amis.Action(
                            actionType=ActionType.Ajax,
                            label="停止",
                            level="warning",
                            api="POST:/api/gateway/instances/${instance_id}/stop",
                        ),
                        amis.Action(
                            actionType=ActionType.Ajax,
                            label="重启",
                            level="warning",
                            api="POST:/api/gateway/instances/${instance_id}/restart",
                        ),
                        amis.Action(
                            actionType=ActionType.Ajax,
                            label="查看状态",
                            level="default",
                            api="GET:/api/gateway/instances/${instance_id}/status",
                        ),
                    ],
                ),
                amis.Divider(),
                amis.Form(
                    title="部署",
                    api="POST:/api/gateway/instances/${instance_id}/deploy",
                    body=[
                        amis.Select(name="instance_id", label="目标实例", required=True, options=options or []),
                        amis.InputFile(name="file", label="部署包 (zip)", required=True, accept=".zip"),
                        amis.InputText(name="gwid", label="网关 ID (gwid)", required=True, value="GW01"),
                        amis.InputText(name="password", label="密码"),
                        amis.InputNumber(name="env_id", label="环境(env_id)", value=0),
                        amis.InputNumber(name="level", label="Level", value=2),
                        amis.Select(
                            name="access_mode",
                            label="接入模式",
                            value="TCP",
                            options=[{"label": "TCP", "value": "TCP"}, {"label": "UDP", "value": "UDP"}],
                        ),
                        amis.InputText(name="line_type", label="线路类型", value="地面"),
                        amis.InputText(name="local_ip", label="本机 IP", value="127.0.0.1"),
                    ],
                ),
                amis.Divider(),
                amis.Form(
                    title="升级",
                    api="POST:/api/gateway/instances/${instance_id}/upgrade",
                    body=[
                        amis.Select(name="instance_id", label="目标实例", required=True, options=options or []),
                        amis.InputFile(name="file", label="新版本 zip", required=True, accept=".zip"),
                        amis.InputText(name="version", label="版本号（可选）", value=""),
                        amis.InputNumber(name="timeout", label="超时(秒)", value=300),
                    ],
                ),
                amis.Divider(),
                amis.Form(
                    title="回滚",
                    api="POST:/api/gateway/instances/${instance_id}/rollback",
                    body=[
                        amis.Select(name="instance_id", label="目标实例", required=True, options=options or []),
                        amis.InputText(name="manifest_path", label="manifest.json 路径", required=True),
                    ],
                ),
                amis.Divider(),
                amis.Service(
                    api="GET:/api/gateway/controllers",
                    body=[
                        amis.Table(
                            columns=[
                                amis.TableColumn(name="exchange", label="交易所"),
                                amis.TableColumn(name="kind", label="类型"),
                                amis.TableColumn(name="controller", label="控制器"),
                            ],
                            title="已注册控制器",
                        )
                    ],
                ),
            ],
        )


class GatewayAdminApp(AdminApp):
    """网关分组应用。在 master/main.py 中使用 site.register_admin(GatewayAdminApp) 注册。"""

    page_schema = PageSchema(label="网关控制", icon="fa fa-network-wired")

    def __init__(self, app: "AdminApp") -> None:
        super().__init__(app)
        self.register_admin(GatewayInstanceAdmin)
        self.register_admin(GatewayOpsAdmin)
