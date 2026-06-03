
import importlib.util
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import TransformScript
from .registry import TaskRegistry


class ScriptLoader:
    """外部脚本加载器"""
    _loaded_modules: Dict[str, Any] = {}
    _lock = threading.Lock()

    @classmethod
    def _discover_scripts(cls, directory: str) -> List[str]:
        """发现目录下所有 Python 脚本"""
        scripts = []
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return scripts

        for file_path in path.glob("*.py"):
            if file_path.name != "__init__.py":
                scripts.append(str(file_path))
        return scripts

    @classmethod
    def _load_module_from_path(cls, script_path: str) -> Optional[Any]:
        """从文件路径加载模块"""
        script_name = Path(script_path).stem
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[script_name] = module
        spec.loader.exec_module(module)
        return module

    @classmethod
    def _find_transform_classes(cls, module: Any) -> List[TransformScript]:
        """从模块中发现 TransformScript 子类"""
        scripts = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, TransformScript)
                and attr is not TransformScript
            ):
                try:
                    instance = attr()
                    scripts.append(instance)
                except Exception:
                    pass
        return scripts

    @classmethod
    def load_script(cls, script_path: str) -> List[TransformScript]:
        """加载单个脚本文件"""
        loaded_scripts = []
        with cls._lock:
            try:
                module = cls._load_module_from_path(script_path)
                if module:
                    cls._loaded_modules[script_path] = module
                    scripts = cls._find_transform_classes(module)
                    for script in scripts:
                        TaskRegistry.register_script(script)
                        loaded_scripts.append(script)
            except Exception as e:
                print(f"Error loading script {script_path}: {e}")
        return loaded_scripts

    @classmethod
    def load_all(cls, directory: str) -> List[TransformScript]:
        """加载目录下所有脚本"""
        all_scripts = []
        script_paths = cls._discover_scripts(directory)
        for script_path in script_paths:
            scripts = cls.load_script(script_path)
            all_scripts.extend(scripts)
        return all_scripts

    @classmethod
    def reload(cls, script_name: str) -> Optional[TransformScript]:
        """重新加载指定脚本"""
        with cls._lock:
            if script_name in sys.modules:
                del sys.modules[script_name]

            for path, module in list(cls._loaded_modules.items()):
                if Path(path).stem == script_name:
                    del cls._loaded_modules[path]
                    scripts = cls.load_script(path)
                    return scripts[0] if scripts else None
        return None

    @classmethod
    def get_loaded_modules(cls) -> Dict[str, Any]:
        """获取已加载模块"""
        return cls._loaded_modules.copy()
