"""共享 transform_script 执行器模块。

供 master 预览阶段与 worker 正式任务执行阶段复用。在一个受限的命名空间中
安全地 exec 用户提供的 Python 源码字符串, 并调用其中定义的 ``transform`` 函数
(签名 ``transform(data, config) -> Any``) 对采集到的数据进行转换。

受限 ``__builtins__`` 仅保留白名单内置函数, 禁用 ``open`` / ``eval`` / ``exec``
等危险调用, 防止用户脚本访问文件系统或执行任意代码。
"""

import builtins
from typing import Any, Optional


# 受限 __builtins__ 白名单: 仅允许以下名字
_BUILTINS_WHITELIST = (
    # 基础
    "len", "str", "int", "float", "bool", "list", "dict", "tuple", "set",
    "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "min", "max", "sum", "abs", "round", "isinstance", "issubclass",
    "type", "print",
    # 异常
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "StopIteration",
    # 常量
    "True", "False", "None",
)

# 禁用名单: 即使脚本引用这些名字, 也视为 "blocked_call" 而非普通运行时错误
_BLOCKED_NAMES = frozenset({
    "open", "eval", "exec", "__import__", "compile", "getattr",
    "setattr", "delattr", "globals", "locals", "vars", "dir",
    "__builtins__", "input",
})


def _build_safe_builtins() -> dict:
    """构造受限的 ``__builtins__`` 字典, 仅包含白名单内的名字。"""
    safe: dict = {}
    for name in _BUILTINS_WHITELIST:
        obj = getattr(builtins, name, None)
        if obj is not None:
            safe[name] = obj
    return safe


def apply_transform(
    script_src: str,
    data: Any,
    config: dict,
) -> tuple[bool, Any, Optional[str]]:
    """在受限命名空间中执行用户脚本并调用 ``transform`` 函数。

    返回三元组 ``(ok, data, err)``:

    - 成功: ``(True, 转换后数据, None)``
    - 失败: ``(False, 错误信息字符串, 错误类型字符串)``

    若 ``script_src`` 为空字符串或 ``None``, 直接返回原数据 (即不转换)。

    错误类型枚举:
      ``"syntax_error"`` / ``"missing_transform"`` / ``"runtime_error"``
      / ``"blocked_call"`` / ``"invalid_signature"``
    """
    if not script_src:  # None 或空字符串
        return (True, data, None)

    safe_builtins = _build_safe_builtins()
    globals_dict: dict = {
        "__builtins__": safe_builtins,
        "__name__": "__transform_script__",
    }

    # 1. exec 源码, 提取 transform
    try:
        exec(script_src, globals_dict)
    except SyntaxError as e:
        return (False, f"SyntaxError: {e}", "syntax_error")
    except NameError as e:
        missing = getattr(e, "name", None)
        if missing in _BLOCKED_NAMES:
            return (False, f"blocked call: {missing}", "blocked_call")
        return (False, f"runtime error: {e}", "runtime_error")
    except Exception as e:  # noqa: BLE001
        return (False, f"runtime error: {e}", "runtime_error")

    # 2. 提取 transform
    transform = globals_dict.get("transform")
    if transform is None:
        return (False, "transform not defined", "missing_transform")
    if not callable(transform):
        return (False, "transform is not callable", "invalid_signature")

    # 3. 调用 transform, 不在受限命名空间外抛出异常
    try:
        result = transform(data, config)
    except NameError as e:
        missing = getattr(e, "name", None)
        if missing in _BLOCKED_NAMES:
            return (False, f"blocked call: {missing}", "blocked_call")
        return (False, f"runtime error: {e}", "runtime_error")
    except Exception as e:  # noqa: BLE001
        return (False, f"runtime error: {e}", "runtime_error")

    return (True, result, None)
