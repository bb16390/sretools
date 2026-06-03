# 数据转换处理系统设计方案

## 1. 项目现状分析

### 现有架构
- Worker 端已实现适配器模块，包含 HTTP、SQL、ClickHouse、InfluxDB、Redis 五种数据源适配器
- 所有适配器继承自 `AsyncBaseAdapter` 抽象类
- `AdapterManager` 提供单例管理，支持配置相同的适配器复用
- 适配器采用异步实现，数据获取方法各不相同（SQL 用 execute/fetch_all，HTTP 用 get/post，Redis 用 get/set 等）

### 现有问题
- 适配器直接返回原始数据，缺乏统一的数据处理机制
- 不同适配器返回的数据格式差异大，难以统一处理
- 缺乏基于任务 ID 的数据转换脚本执行能力

---

## 2. 设计方案

### 2.1 核心目标
- 为每个适配器增加数据转换能力
- 支持通过任务 ID 指定数据处理脚本
- 支持**内置脚本**（代码中定义）和**外部脚本**（文件系统落地）两种模式
- 处理脚本独立管理，可复用、可扩展

### 2.2 模块结构

```
worker/
├── transformer/                  # 转换器模块
│   ├── __init__.py
│   ├── base.py                  # 转换器基类和任务注册表
│   ├── registry.py              # 处理脚本注册表
│   ├── loader.py                # 外部脚本加载器
│   ├── executor.py              # 转换执行器
│   └── scripts/                 # 内置处理脚本
│       ├── __init__.py
│       ├── json_parser.py       # JSON 解析脚本
│       ├── filter.py            # 数据过滤脚本
│       ├── aggregator.py        # 数据聚合脚本
│       └── formatter.py         # 格式化脚本
├── scripts/                     # 外部落地的转换脚本目录（用户自定义）
│   ├── __init__.py
│   ├── my_transform.py          # 用户自定义转换脚本示例
│   └── another_transform.py
```

### 2.3 核心设计

#### 双模式脚本支持
1. **内置脚本**：在 `transformer/scripts/` 中定义，系统自带
2. **外部脚本**：在 `worker/scripts/` 目录下的 `.py` 文件，动态加载

#### 脚本接口统一
所有脚本（内置/外部）均实现统一接口：
```python
class TransformScript(ABC):
    @abstractmethod
    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        """执行数据转换"""
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置参数"""
        pass

    @property
    def name(self) -> str:
        """脚本名称（唯一标识）"""
        pass
```

#### 任务注册机制
- 每个任务 ID 对应一个脚本名称（内置或外部）
- 任务配置存储在 `TaskRegistry` 中
- 支持内置脚本和外部脚本的混合使用

---

## 3. 详细设计

### 3.1 transformer/base.py - 转换器基类

**核心类：**
- `TransformScript` - 所有转换脚本的抽象基类
- 定义标准接口：`transform(data, config)`、`validate_config(config)`、`name` 属性

### 3.2 transformer/registry.py - 任务注册表

**核心类：**
- `TaskRegistry` - 单例模式的任务注册表
- 管理任务 ID 到转换脚本的映射
- 支持任务动态注册和查询

**功能：**
- `register(task_id, script_name, config)` - 注册任务
- `get_script(task_id)` - 获取任务对应的脚本
- `unregister(task_id)` - 取消注册
- `list_tasks()` - 列出所有已注册任务

### 3.3 transformer/loader.py - 外部脚本加载器

**核心类：**
- `ScriptLoader` - 外部脚本加载器
- 支持从指定目录动态加载 `.py` 脚本
- 支持脚本热加载（可选）

**功能：**
- `load_script(script_path)` - 加载单个脚本文件
- `load_all(directory)` - 加载目录下所有脚本
- `reload(script_name)` - 重新加载指定脚本
- 自动发现并实例化实现了 `TransformScript` 接口的类

**外部脚本示例：**
```python
# worker/scripts/my_transform.py
from worker.transformer.base import TransformScript
from typing import Any, Dict

class MyTransformScript(TransformScript):
    @property
    def name(self) -> str:
        return "my_transform"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return "factor" in config

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        factor = config["factor"]
        return data * factor
```

### 3.4 transformer/executor.py - 转换执行器

**核心类：**
- `TransformExecutor` - 转换执行器

**功能：**
- `execute(task_id, data, config)` - 执行单个任务转换
- `execute_chain(task_ids, data)` - 执行任务链转换（按顺序）
- 集成到 `AsyncBaseAdapter` 的数据获取流程中

### 3.5 transformer/scripts/ - 内置处理脚本

#### json_parser.py
- 解析 JSON 字符串为字典
- 支持 JSONPath 提取

#### filter.py
- 根据条件过滤数据
- 支持字段比较、模糊匹配

#### aggregator.py
- 数据聚合计算（求和、平均、计数等）
- 支持分组聚合

#### formatter.py
- 数据格式化（日期格式、数值格式）
- 字段重命名、类型转换

### 3.6 适配器集成

为 `AsyncBaseAdapter` 增加方法：

```python
# 在 AsyncBaseAdapter 中新增
async def fetch_and_transform(
    self,
    task_id: str,
    *args,
    transform_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Any:
    """获取数据并执行转换"""
    # 调用子类具体的 fetch 方法（由子类实现）
    data = await self._fetch(*args, **kwargs)
    if task_id:
        executor = TransformExecutor()
        return await executor.execute(task_id, data, transform_config or {})
    return data
```

**注意**：`AsyncBaseAdapter` 需要定义 `_fetch` 抽象方法，由各子类实现具体的数据获取逻辑。

---

## 4. 文件修改清单

### 新增文件
1. `/workspace/worker/transformer/__init__.py` - 模块入口，导出核心类
2. `/workspace/worker/transformer/base.py` - 转换器基类 `TransformScript`
3. `/workspace/worker/transformer/registry.py` - 任务注册表 `TaskRegistry`
4. `/workspace/worker/transformer/loader.py` - 外部脚本加载器 `ScriptLoader`
5. `/workspace/worker/transformer/executor.py` - 转换执行器 `TransformExecutor`
6. `/workspace/worker/transformer/scripts/__init__.py` - 脚本包入口
7. `/workspace/worker/transformer/scripts/json_parser.py` - JSON 解析脚本
8. `/workspace/worker/transformer/scripts/filter.py` - 数据过滤脚本
9. `/workspace/worker/transformer/scripts/aggregator.py` - 数据聚合脚本
10. `/workspace/worker/transformer/scripts/formatter.py` - 格式化脚本
11. `/workspace/worker/scripts/__init__.py` - 外部脚本目录入口（空文件，用于包标识）

### 修改文件
1. `/workspace/worker/adapter/base.py` - 增加 `fetch_and_transform` 方法和 `_fetch` 抽象方法
2. `/workspace/worker/adapter/__init__.py` - 导出新的转换器模块

---

## 5. 实现步骤

### 步骤 1：创建 transformer 模块基础结构
- 创建目录和 `__init__.py`
- 实现 `TransformScript` 抽象基类

### 步骤 2：实现任务注册表
- 实现 `TaskRegistry` 单例类
- 实现任务注册、查询、注销功能

### 步骤 3：实现外部脚本加载器
- 实现 `ScriptLoader` 类
- 实现目录扫描、动态加载、热加载功能

### 步骤 4：实现转换执行器
- 实现 `TransformExecutor` 类
- 实现 `execute` 和 `execute_chain` 方法

### 步骤 5：实现内置转换脚本
- 实现 `JsonParserScript`
- 实现 `FilterScript`
- 实现 `AggregatorScript`
- 实现 `FormatterScript`

### 步骤 6：集成到适配器
- 在 `AsyncBaseAdapter` 中增加 `fetch_and_transform` 和 `_fetch` 方法
- 更新所有适配器的导出

### 步骤 7：测试验证
- 编写单元测试
- 验证内置脚本和外部脚本的加载与执行

---

## 6. 使用示例

### 示例 1：使用内置脚本

```python
# 注册任务（使用内置脚本）
registry = TaskRegistry()
registry.register(
    task_id="parse_json",
    script_name="json_parser",
    config={"path": "$.data"}
)

registry.register(
    task_id="filter_errors",
    script_name="filter",
    config={"field": "level", "operator": "eq", "value": "ERROR"}
)

# 使用适配器获取并转换数据
adapter = AdapterManager.get_or_create(SqlAdapter, {"url": "..."})
result = await adapter.fetch_and_transform(
    task_id="parse_json",
    sql="SELECT payload FROM logs WHERE id = 1",
    transform_config={"path": "$.data"}
)
```

### 示例 2：使用外部自定义脚本

```python
# worker/scripts/multiply_transform.py
from worker.transformer.base import TransformScript
from typing import Any, Dict

class MultiplyTransform(TransformScript):
    @property
    def name(self) -> str:
        return "multiply"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return "factor" in config

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        return data * config["factor"]
```

```python
# 注册并使用外部脚本
loader = ScriptLoader()
loader.load_all("/workspace/worker/scripts")

registry.register(
    task_id="double_value",
    script_name="multiply",
    config={"factor": 2}
)

result = await adapter.fetch_and_transform(
    task_id="double_value",
    sql="SELECT value FROM metrics",
    transform_config={"factor": 2}
)
```

### 示例 3：链式转换

```python
# 链式执行多个转换
result = await adapter.fetch_and_transform_chain(
    task_ids=["parse_json", "filter_errors", "format_output"],
    sql="SELECT * FROM logs"
)
```

---

## 7. 风险和注意事项

### 风险点
1. **脚本执行安全** - 外部脚本可能执行危险操作
2. **性能开销** - 大量数据转换可能影响性能
3. **错误处理** - 转换脚本出错需要统一处理
4. **外部脚本依赖** - 外部脚本可能依赖未安装的包

### 解决方案
1. 外部脚本目录可配置，限制加载范围
2. 支持批量处理和流式处理
3. 统一的异常处理和错误日志记录
4. 启动时验证外部脚本的依赖完整性
