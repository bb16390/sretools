# 修复 master/libs 兼容 fastapi==0.141.0

## 目标
使 `master/libs` 下的两个 vendored 库（`fastapi_amis_admin`、`fastapi_user_auth`）完全兼容 `fastapi==0.141.0`（要求 `pydantic>=2.9.0`）。范围：彻底清理——既修复硬报错，也清理所有过时/脆弱的 pydantic-v1 模式与私有导入，做向前兼容加固。

## 现状分析（Phase 1 探索结论）
- 依赖：`/workspace/pyproject.toml` 锁定 `fastapi==0.141.0`，传递依赖 `pydantic>=2.9.0`、`pydantic-settings>=2.13.1`、`sqlmodel==0.0.19`。沙箱为 Python 3.12.13，当前未安装 fastapi。
- 已部分修补：`utils/pydantic.py` 中 `create_cloned_field` 已替换被 0.141.0 移除的 `fastapi.utils.create_cloned_field`；存在 `PYDANTIC_V2` 分支。
- 仍可用的 fastapi 内部导入（0.141.0 验证）：`fastapi._compat` 在 0.141.0 是包，`__init__.py` 重新导出 `ModelField / Undefined / copy_field_info / field_annotation_is_scalar / field_annotation_is_scalar_sequence / field_annotation_is_sequence / sequence_types / lenient_issubclass`；`fastapi.types.IncEx` 存在；`fastapi.utils.create_model_field` 存在。→ 这些**无需改动**。
- 待修复的过时/脆弱模式：
  1. **`pydantic.v1.*` 私有命名空间导入**（`utils/pydantic.py:19-26`）：`pydantic.v1` 在 Python 3.14+ 不再支持，属脆弱依赖。
  2. **pydantic v1 已弃用方法**（约 30 处）：`.dict()` / `.json()` / `parse_obj()` / `from_orm()` / `update_forward_refs()` / `BaseModel.copy(exclude=,update=,deep=)`。在当前 pydantic v2.x 多为弃用警告，但部分版本可能已移除，且向前不兼容。
  3. **死代码 pydantic-v1 `else` 分支**：`utils/pydantic.py:119-184`、`admin/settings.py:55-59`、`crud/_sqlalchemy.py:305-310 else 子句`、`crud/parser.py:305-309 else 子句`。fastapi 0.141.0 强制 pydantic v2，这些分支永不执行。
- 沙箱无 libs 专用测试；`/workspace/tests/` 覆盖 server/gateway/worker，不直接覆盖 libs。验证将以自建冒烟测试为准。

## 设计决策
- `fastapi._compat` / `fastapi.types.IncEx` / `fastapi.utils.create_model_field` 导入保持不变（0.141.0 验证可用）。
- `pydantic.v1.*` 导入 → 替换为本地 vendored 等价实现（纯函数，无 pydantic.v1 依赖），消除 py3.14 隐患。
- `pydantic._internal._utils.ValueItems`：保留（v2 原生内部 API，`ValueItems.merge` 语义复杂、自行实现风险高；该路径不随 py3.14 消失）。此为显式取舍。
- `PYDANTIC_V2` 常量保留定义（其他模块仍 import），但删除所有 `else`（v1）死分支；`if PYDANTIC_V2:` 守卫因恒真而保留以降低改动风险（不做整体去缩进重构）。
- 方法替换对照表：
  - `.dict(**kw)` → `.model_dump(**kw)`（kw 兼容：exclude/exclude_none/exclude_unset/by_alias 等）
  - `.json(**kw)` → `.model_dump_json(**kw)`
  - `Model.parse_obj(o)` → `Model.model_validate(o)`
  - `Model.from_orm(o)` → `Model.model_validate(o)`
  - `Model.update_forward_refs()` → `Model.model_rebuild()`
  - `Model.copy()` / `.copy(deep=True)` → `.model_copy()` / `.model_copy(deep=True)`
  - `.copy(exclude=e)` → `type(obj).model_validate(obj.model_dump(exclude=e))`
  - `.copy(exclude=e, update=u)` → `type(obj).model_validate({**obj.model_dump(exclude=e), **u})`
- 列表 `.copy()`（`_sqlalchemy.py:125`、`admin/admin.py:641,644`）属 `list.copy()`，**不动**。

## 实施步骤

### 步骤 0：建立可运行环境（执行阶段）
- 在沙箱安装依赖：`cd /workspace && pip install -e .`（或 `uv sync`），使 `fastapi==0.141.0` + 对应 pydantic 可用。仅用于验证，不改依赖声明。
- 记录解析到的 `pydantic` 版本，确认 `.dict()` 等是否仍存在（决定是否“仅警告”还是“已移除”）。

### 步骤 1：替换脆弱导入与死分支 — `master/libs/fastapi_amis_admin/utils/pydantic.py`
- 删除 `from pydantic._internal._utils import ValueItems` 之外的 `pydantic.v1.*` 导入（行 20-21、26）。
  - 保留：行 19 `from pydantic._internal._utils import ValueItems`。
- 在模块内新增本地 vendored 实现（替代 pydantic.v1）：
  - `deep_update(main, update)`：标准字典深合并。
  - `lenient_issubclass(cls, class_or_tuple)`：try/except issubclass。
  - `smart_deepcopy(obj)`：`copy.deepcopy(obj)`。
  - `is_literal_type(tp)`：`get_origin(tp) is Literal`。
  - `is_none_type(tp)`：`tp is None or tp is type(None)`。
  - `is_union(tp)`：`get_origin(tp) in (Union, getattr(types,"UnionType",None))`。
  - `parse_date(value)` / `parse_datetime(value)`：`TypeAdapter(date/datetime).validate_python(value)`。
- 删除 `else:` 死分支（约行 119-184），仅保留 `if PYDANTIC_V2:` 真分支（恒真）。保留 `PYDANTIC_V2 = True` 常量与 `from fastapi._compat import (...)`。
- 注意：`deep_update / lenient_issubclass / smart_deepcopy / is_literal_type / is_none_type / is_union / parse_date / parse_datetime` 被 `admin/parser.py`、`crud/parser.py` 经 `from ...utils.pydantic import` 引用，命名需保持一致。

### 步骤 2：替换死分支 — 其余文件
- `master/libs/fastapi_amis_admin/admin/settings.py`：删除 `else:` 分支（行 55-59），保留 `if PYDANTIC_V2:` 内 `field_validator/model_validator` 注册。
- `master/libs/fastapi_amis_admin/crud/_sqlalchemy.py`：`_create_schema_filter` 中删除 v1 `else` 子句（行 307-310：`modelfield.type_=`/`outer_type_=`/`validators=[]`），仅保留 `modelfield.field_info.annotation = str`。
- `master/libs/fastapi_amis_admin/crud/parser.py`：`PropertyField.__init__` 删除 v1 `else` 子句（行 305-309），仅保留 v2 分支。

### 步骤 3：机械替换弃用方法（按文件）
对以下精确位置执行对照表替换（kw 保持原样）：

- `master/libs/fastapi_user_auth/utils/sqlachemy_adapter.py`：L133,149 `.dict()`→`.model_dump()`
- `master/libs/fastapi_user_auth/auth/auth.py`：L294 `parse_obj`→`model_validate`；L317 `parse_obj`→`model_validate`；L318 `.dict()`→`.model_dump()`
- `master/libs/fastapi_user_auth/auth/exceptions.py`：L61 `.dict()`→`.model_dump()`
- `master/libs/fastapi_user_auth/auth/backends/db.py`：L41 `parse_obj`→`model_validate`；L43 `.json()`→`.model_dump_json()`
- `master/libs/fastapi_user_auth/auth/backends/redis.py`：L21 `parse_obj`→`model_validate`；L23 `.json()`→`.model_dump_json()`
- `master/libs/fastapi_user_auth/auth/backends/jwt.py`：L24,29 `parse_obj`→`model_validate`；L30 `.dict()`→`.model_dump()`
- `master/libs/fastapi_user_auth/admin/admin.py`：L163,176,236,249,255 `.dict()`→`.model_dump()`；L165,175 `parse_obj`→`model_validate`
- `master/libs/fastapi_amis_admin/crud/_sqlalchemy.py`：L392 `parse_obj`→`model_validate`；L450,462,467 `.dict()`→`.model_dump()`
- `master/libs/fastapi_amis_admin/admin/admin.py`：L675 `.dict()`→`.model_dump()`
- `master/libs/fastapi_amis_admin/amis/types.py`：L15 `.json()`→`.model_dump_json()`；L18 `.dict()`→`.model_dump()`
- `master/libs/fastapi_amis_admin/admin/handlers.py`：L54 `.dict()`→`.model_dump()`
- `master/libs/fastapi_amis_admin/admin/extensions/admin.py`：L206 `.dict()`→`.model_dump()`
- `master/libs/fastapi_amis_admin/amis/components.py`：
  - L420,423,436,440 `X.parse_obj(self.dict(...))` / `X.parse_obj(item.dict(...))` → `X.model_validate(self.model_dump(...))` / `X.model_validate(item.model_dump(...))`
  - L2907-2915 `Model.update_forward_refs()` → `Model.model_rebuild()`（共 9 处：PageSchema, ActionType.Dialog, ActionType.Drawer, TableCRUD, Form, Tpl, InputText, InputNumber, Picker）
- `master/libs/fastapi_amis_admin/admin/parser.py`：L101 `.dict(...)`→`.model_dump(...)`
- `master/libs/fastapi_amis_admin/crud/parser.py`：L335 `parse_obj_to_schema` 简化为 `return schema.model_validate(obj)`（`from_orm` 与 `parse_obj` 在 v2 均为 `model_validate`）

### 步骤 4：替换 `BaseModel.copy(...)` 调用
- `master/libs/fastapi_amis_admin/admin/admin.py`：
  - L326 `self.page_schema.copy(deep=True)` → `.model_copy(deep=True)`
  - L1180 `self.action.copy()` → `.model_copy()`
  - L1221 `self.action and self.action.copy()` → `.model_copy()`
  - L1303 `child.page_schema.copy(deep=True)` → `.model_copy(deep=True)`
- `master/libs/fastapi_amis_admin/admin/extensions/admin.py`：
  - L219,227,237 `item.copy(exclude=exclude)` / `obj.copy(exclude=exclude)` → `type(obj).model_validate(obj.model_dump(exclude=exclude))`
- `master/libs/fastapi_amis_admin/admin/parser.py`：
  - L71 `formitem.copy(exclude={"maxLength","receiver"}, update={"type":"textarea"})` → `type(formitem).model_validate({**formitem.model_dump(exclude={"maxLength","receiver"}), "type":"textarea"})`

### 步骤 5：验证
1. **导入冒烟**：`python -c "import fastapi_amis_admin, fastapi_user_auth"` 无报错。
2. **功能冒烟**（临时脚本，验证后删除）：构建最小 `AdminSite(Settings(database_url_async='sqlite+aiosqlite:///:memory:'))`，注册一个含主键的 `SQLModel`/SQLAlchemy 模型为 `ModelAdmin`，`mount_app` 到 `FastAPI()`，触发 `register_router()` 与 schema 生成（`schema_create/filter/list/update`、`create_model_by_fields`、`model_fields`、`create_cloned_field`、`parse_obj_to_schema`）。确认无异常。
3. **弃用扫描**：`python -W error::DeprecationWarning -c "<上述脚本>"` 并过滤 pydantic 相关，确认无残留 pydantic 弃用警告（`pydantic._internal._utils.ValueItems` 导入本身不触发警告，可接受）。
4. **既有测试回归**：`cd /workspace && pytest -q`（跑 `/workspace/tests`），确认未引入回归。
5. 用 `ruff check master/libs` 确认无语法/导入层面 lint 报错。

## 假设与边界
- 不改动 `pyproject.toml` 依赖声明（保持 `fastapi==0.141.0` 锁定）。
- 不改动 `fastapi_amis_admin` / `fastapi_user_auth` 的对外 API 行为，仅做内部兼容性迁移。
- `pydantic._internal._utils.ValueItems` 保留为显式取舍（见设计决策）。
- 不引入新第三方依赖；vendored 实现仅用标准库 + pydantic v2 公共 API（`TypeAdapter`）。
- 列表 `.copy()`、`request.json()`（starlette）等非 pydantic 调用不动。
- `amis/components.py` 中 `model_rebuild()` 调用需在所有前向引用模型定义完成后执行（原 `update_forward_refs` 即此位置，保持不变）。
