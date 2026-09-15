from datetime import datetime

from fastapi_amis_admin.amis import (
    Editor,
    FieldSet,
    InputDatetime,
    InputText,
    Select,
    Switch,
    TableColumn,
    Validation,
)
from fastapi_amis_admin.models import Field, IntegerChoices
from fastapi_user_auth.mixins.models import PkMixin
from fastapi_user_auth.utils.sqltypes import SecretStrType
from pydantic import SecretStr
from sqlalchemy import func


class DatabaseType(IntegerChoices):
    """
    数据库类型
    """

    oracle = 0, "Oracle"
    mysql = 1, "MySQL"
    postgresql = 2, "PostgreSQL"
    sqlite = 3, "SQLite"
    influxdb = 4, "InfluxDB"
    redis = 5, "Redis"
    sqlserver = 6, "SQL Server"
    elasticsearch = 7, "Elasticsearch"
    clickhouse = 8, "ClickHouse"


class TaskStatus(IntegerChoices):
    """
    任务状态
    """

    confirmed = 0, "已确认"
    pending = 1, "待确认"
    running = 2, "运行中"
    paused = 3, "暂停"
    stopped = 4, "停止"
    error = 5, "错误"


class ExecStatus(IntegerChoices):
    """
    执行状态
    """

    success = 0, "成功"
    failed = 1, "失败"
    running = 2, "运行中"


class CollectorType(IntegerChoices):
    """
    数据采集器类型
    """

    database = 0, "数据库"
    kafka = 1, "Kafka"
    http = 2, "HTTP"
    websocket = 3, "WebSocket"


class DataSourceStatus(IntegerChoices):
    """
    数据源状态
    """

    confirmed = 0, "已确认"
    pending = 1, "待确认"
    error = 2, "错误"


class Opsteam(PkMixin, table=True):
    """
    团队
    """

    __tablename__ = "t_opsteam"
    name: str = Field(nullable=False, title="团队名称")
    manager: str = Field(nullable=False, title="负责人")
    members_en: list[str] = Field(nullable=False, title="成员英文名称")
    members_cn: list[str] = Field(nullable=False, title="成员中文名称")


class Subsystem(PkMixin, table=True):
    """
    系统
    """

    __tablename__ = "t_subsystem"
    subsystem: str = Field(nullable=False, title="系统")
    description: str = Field(nullable=False, title="描述")
    team_id: int = Field(nullable=False, title="团队ID", foreign_key="t_opsteam.id")


class DataSource(PkMixin, table=True):
    """
    数据源
    """

    __tablename__ = "t_data_source"
    node: str = Field(nullable=False, title="节点")
    name: str = Field(nullable=False, title="数据源名称")
    collector_type: int = Field(
        CollectorType.database, nullable=False, title="采集器类型"
    )
    database_type: int = Field(DatabaseType.oracle, nullable=False, title="数据库类型")
    status: int = Field(DataSourceStatus.pending, nullable=False, title="数据源状态")
    url: str = Field(nullable=False, title="连接串")
    username: str = Field(nullable=False, title="用户名")
    password: SecretStr = Field(
        nullable=False,
        title="密码",
        sa_type=SecretStrType,
        max_length=128,
        amis_form_item="input-password",
    )


class CollectorTask(PkMixin, table=True):
    """
    数据采集任务
    """

    __tablename__ = "t_collector_task"
    name: str = Field(nullable=False, title="任务名称")
    status: int = Field(TaskStatus.pending, nullable=False, title="任务状态")
    exec_status: int = Field(ExecStatus.running, nullable=False, title="执行状态")
    data_source_id: int = Field(nullable=False, title="数据源ID")
    collector_type: int = Field(
        CollectorType.database, nullable=False, title="采集器类型"
    )
    url: str = Field(nullable=False, title="连接串")
    username: str = Field(nullable=False, title="用户名")
    password: SecretStr = Field(
        nullable=False,
        title="密码",
        sa_type=SecretStrType,
        max_length=128,
        amis_form_item="input-password",
    )
    job_id: str = Field(nullable=False, title="任务ID")
    worker_id: str = Field(nullable=False, title="工作节点")
    last_run_time: str = Field(nullable=False, title="上次执行时间")
    last_run_status: int = Field(
        ExecStatus.running, nullable=False, title="上次执行状态"
    )
    last_run_duration_ms: int = Field(0, nullable=False, title="上次执行耗时（毫秒）")
    total_run_count: int = Field(0, nullable=False, title="总执行次数")
    total_failed_count: int = Field(0, nullable=False, title="总失败次数")
    timeout: int = Field(30, nullable=False, title="超时时间（秒）")
    transform_script: str = Field(
        default=None,
        nullable=False,
        title="转换脚本",
        amis_form_item=Editor(language="python"),
    )
    conf: str = Field(
        title="配置项",
        amis_table_column=TableColumn(
            type="json", label="配置项", field="conf", sortable=True, levelExpand=0
        ),
        amis_form_item=FieldSet(
            title="配置项",
            body=[
                Switch(label="交易日", name="conf.is_trading_day", value=False),
                InputText(
                    label="触发表达式",
                    name="conf.trigger_expr",
                    visibleOn="this.collector_type == 0",
                    value="cron(0-59 8-16 * * 0-4)",
                    labelRemark={
                        "type": "remark",
                        "title": "提示",
                        "content": "<pre>cron(0-59 8-16 * * 0-4)\ninterval(seconds=30)\n</pre>",
                    },
                ),
                Select(
                    label="源数据库",
                    name="conf.src_datasource",
                    source="post:/admin/collector/DataSourceAdmin/datasource_options",
                    selectMode="table",
                    columns=[
                        {"name": "id", "label": "ID"},
                        {"name": "t_subsystem__subsystem", "label": "子系统"},
                        {"name": "node", "label": "节点"},
                        {"name": "name", "label": "名称"},
                        {"name": "url", "label": "连接串"},
                        {"name": "username", "label": "用户名"},
                    ],
                    searchable=True,
                    valueField="id",
                    filterOption="return options.filter(({label}) => label?.includes(inputValue));",
                    checkAll=True,
                    multiple=True,
                    clearable=True,
                ),
                InputText(
                    label="SQL语句",
                    name="conf.sql",
                    visibleOn="this.collector_type ==0",
                    requireOn="this.collector_type ==0",
                ),
                Select(
                    label="目标数据库",
                    name="conf.dst_datasource",
                    source="post:/admin/collector/DataSourceAdmin/database_options",
                    selectMode="table",
                    columns=[
                        {"name": "id", "label": "ID"},
                        {"name": "t_subsystem__subsystem", "label": "子系统"},
                        {"name": "node", "label": "节点"},
                        {"name": "name", "label": "名称"},
                        {"name": "url", "label": "连接串"},
                        {"name": "username", "label": "用户名"},
                    ],
                    searchable=True,
                    valueField="id",
                    filterOption="return options.filter(({label}) => label?.includes(inputValue));",
                ),
                InputText(
                    label="目标表",
                    name="conf.dst_table",
                    visibleOn="this.collector_type ==0",
                    requireOn="this.collector_type ==0",
                ),
                InputText(
                    label="数据键值",
                    name="conf.data_key",
                    validations=Validation(matchRegexp="^(?!pre).*$"),
                    validationErrors={"matchRegexp": "数据键值不能以pre开头"},
                    visibleOn="this.collector_type ==0",
                    labelRemark="数据键值不能以pre开头,加上pre可以获取上一交易日采集数据",
                ),
            ],
        ),
    )
    create_time: datetime = Field(
        default_factory=datetime.now, title="创建时间", index=True
    )
    update_time: datetime = Field(
        default_factory=datetime.now,
        title="更新时间",
        index=True,
        sa_column_kwargs={"onupdate": func.now(), "server_default": func.now()},
    )
    subsytem_id: int = Field(
        default=0, nullable=False, title="子系统", foreign_key="t_subsystem.id"
    )
