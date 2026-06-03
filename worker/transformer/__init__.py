
from .base import TransformScript
from .registry import TaskRegistry
from .loader import ScriptLoader
from .executor import TransformExecutor

from .scripts.json_parser import JsonParserScript, JsonDumpsScript
from .scripts.filter import FilterScript, ExcludeFieldsScript, PickFieldsScript
from .scripts.aggregator import AggregatorScript, FlattenScript, UniqueScript
from .scripts.formatter import FormatterScript, RenameFieldsScript, DateFormatScript

TaskRegistry.register_script(JsonParserScript())
TaskRegistry.register_script(JsonDumpsScript())
TaskRegistry.register_script(FilterScript())
TaskRegistry.register_script(ExcludeFieldsScript())
TaskRegistry.register_script(PickFieldsScript())
TaskRegistry.register_script(AggregatorScript())
TaskRegistry.register_script(FlattenScript())
TaskRegistry.register_script(UniqueScript())
TaskRegistry.register_script(FormatterScript())
TaskRegistry.register_script(RenameFieldsScript())
TaskRegistry.register_script(DateFormatScript())

__all__ = [
    'TransformScript',
    'TaskRegistry',
    'ScriptLoader',
    'TransformExecutor',
]
