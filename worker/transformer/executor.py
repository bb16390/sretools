
from typing import Any, Dict, List, Optional

from .base import TransformScript
from .registry import TaskRegistry


class TransformExecutor:
    """转换执行器"""

    def __init__(self):
        self._last_error: Optional[Exception] = None

    async def execute(
        self,
        task_id: str,
        data: Any,
        config: Optional[Dict[str, Any]] = None
    ) -> Any:
        """执行单个任务转换"""
        task = TaskRegistry.get_task(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")

        script_name = task.get('script_name')
        script = TaskRegistry.get_script(script_name)
        if script is None:
            raise ValueError(f"Script '{script_name}' for task '{task_id}' not registered")

        task_config = task.get('config', {})
        final_config = {**task_config, **(config or {})}

        if not script.validate_config(final_config):
            raise ValueError(f"Invalid config for script '{script.name}'")

        try:
            return await script.transform(data, final_config)
        except Exception as e:
            self._last_error = e
            raise

    async def execute_chain(
        self,
        task_ids: List[str],
        data: Any,
        configs: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Any:
        """执行任务链转换（按顺序）"""
        result = data
        for task_id in task_ids:
            config = configs.get(task_id) if configs else None
            result = await self.execute(task_id, result, config)
        return result

    @property
    def last_error(self) -> Optional[Exception]:
        """获取最后一次错误"""
        return self._last_error
