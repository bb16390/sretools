
import threading
from typing import Any, Dict, List, Optional

from .base import TransformScript


class TaskRegistry:
    """任务注册表 - 单例模式"""
    _instance: Optional['TaskRegistry'] = None
    _lock = threading.Lock()

    _tasks: Dict[str, Dict[str, Any]] = {}
    _scripts: Dict[str, TransformScript] = {}

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register_script(cls, script: TransformScript) -> None:
        """注册转换脚本"""
        with cls._lock:
            cls._scripts[script.name] = script

    @classmethod
    def get_script(cls, script_name: str) -> Optional[TransformScript]:
        """获取转换脚本"""
        return cls._scripts.get(script_name)

    @classmethod
    def list_scripts(cls) -> List[str]:
        """列出所有已注册脚本"""
        return list(cls._scripts.keys())

    @classmethod
    def register(
        cls,
        task_id: str,
        script_name: str,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """注册任务"""
        with cls._lock:
            cls._tasks[task_id] = {
                'script_name': script_name,
                'config': config or {}
            }

    @classmethod
    def get_task(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务配置"""
        return cls._tasks.get(task_id)

    @classmethod
    def get_script_for_task(cls, task_id: str) -> Optional[TransformScript]:
        """获取任务对应的脚本"""
        task = cls._tasks.get(task_id)
        if task:
            return cls._scripts.get(task['script_name'])
        return None

    @classmethod
    def unregister(cls, task_id: str) -> bool:
        """取消注册任务"""
        with cls._lock:
            if task_id in cls._tasks:
                del cls._tasks[task_id]
                return True
            return False

    @classmethod
    def list_tasks(cls) -> List[Dict[str, Any]]:
        """列出所有已注册任务"""
        return [
            {'task_id': task_id, **task}
            for task_id, task in cls._tasks.items()
        ]

    @classmethod
    def clear(cls) -> None:
        """清空所有注册"""
        with cls._lock:
            cls._tasks.clear()
            cls._scripts.clear()
