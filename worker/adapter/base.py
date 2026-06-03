
import asyncio
import atexit
import hashlib
import json
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from worker.transformer import TaskRegistry, TransformExecutor

T = TypeVar('T', bound='AsyncBaseAdapter')


class AsyncBaseAdapter(ABC):
    def __init__(self):
        self._closed = False

    @abstractmethod
    async def close(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def transform(
        self,
        data: Any,
        task_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Any:
        """使用任务ID对数据进行转换"""
        executor = TransformExecutor()
        return await executor.execute(task_id, data, config)

    async def transform_chain(
        self,
        data: Any,
        task_ids: List[str],
        configs: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Any:
        """使用任务链对数据进行顺序转换"""
        executor = TransformExecutor()
        return await executor.execute_chain(task_ids, data, configs)


class AdapterManager(Generic[T]):
    _instances: Dict[str, T] = {}
    _lock = threading.Lock()
    _loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    def _generate_key(cls, adapter_type: Type[T], config: Dict[str, Any]) -> str:
        key_data = {
            'type': adapter_type.__name__,
            'config': config
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()

    @classmethod
    def get_or_create(cls, adapter_type: Type[T], config: Dict[str, Any]) -> T:
        key = cls._generate_key(adapter_type, config)
        
        with cls._lock:
            if key not in cls._instances:
                instance = adapter_type(**config)
                cls._instances[key] = instance
            return cls._instances[key]

    @classmethod
    async def close_all(cls):
        with cls._lock:
            for instance in cls._instances.values():
                if not instance._closed:
                    try:
                        await instance.close()
                    except Exception as e:
                        print(f"Error closing adapter: {e}")
            cls._instances.clear()

    @classmethod
    def _setup_atexit(cls):
        def cleanup():
            if cls._loop is None:
                try:
                    cls._loop = asyncio.get_event_loop()
                except RuntimeError:
                    cls._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(cls._loop)
            
            if cls._loop.is_running():
                asyncio.create_task(cls.close_all())
            else:
                cls._loop.run_until_complete(cls.close_all())
        
        atexit.register(cleanup)


AdapterManager._setup_atexit()
