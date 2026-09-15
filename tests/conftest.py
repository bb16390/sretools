"""pytest 配置：将 master/ 与 master/libs/ 加入 sys.path。

使测试中可以直接使用 ``from apps.gateway...`` / ``from core...`` 等
不带 ``master.`` 前缀的导入，与 master 运行时保持一致。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_MASTER_DIR = os.path.join(_PROJECT_ROOT, "master")
_LIBS_DIR = os.path.join(_MASTER_DIR, "libs")

for _p in (_LIBS_DIR, _MASTER_DIR, _PROJECT_ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
