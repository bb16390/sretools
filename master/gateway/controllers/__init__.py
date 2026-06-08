"""交易所控制器注册表。

本文件 import-time 时会把包内各控制器模块 load 一遍，触发装饰器注册。
要新增交易所控制器：

1. 在 controllers/ 目录下创建 xx_mdgw.py / xx_tgw.py
2. 使用 `@registry.register("xx", "mdgw")` 装饰器装饰控制器类
3. 在本文件下方 import 对应模块即可

注意：不要在各控制器模块内 import 本文件（避免循环 import）。
"""
from __future__ import annotations

from . import bjse_mdgw as _bjse_mdgw  # noqa: F401
from . import bjse_tgw as _bjse_tgw  # noqa: F401
from . import sse_mdgw as _sse_mdgw  # noqa: F401
from . import sse_tgw as _sse_tgw  # noqa: F401
from . import szse_mdgw as _szse_mdgw  # noqa: F401
from . import szse_tgw as _szse_tgw  # noqa: F401
from .base import GatewayControllerABC, GatewayControllerRegistry, registry  # noqa: F401

__all__ = [
    "GatewayControllerABC",
    "GatewayControllerRegistry",
    "registry",
]
