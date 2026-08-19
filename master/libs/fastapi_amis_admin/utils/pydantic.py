from enum import Enum
from functools import lru_cache
from typing import Any, Dict, Optional, Sequence, Set, Type, Union

from fastapi._compat import (  # noqa: F401
    ModelField,
    Undefined,
    copy_field_info,
    field_annotation_is_scalar_sequence,
    sequence_types,
)
from pydantic import BaseModel, ConfigDict, create_model
from pydantic.version import VERSION as PYDANTIC_VERSION
from typing_extensions import Annotated, get_args, get_origin

PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")
# fastapi>=0.128 requires pydantic v2. The `else` (v1) branch below is kept only
# as a defensive guard and is effectively dead code under fastapi 0.141.0.
if PYDANTIC_V2:
    from pydantic._internal._utils import ValueItems  # noqa: F401
    from pydantic_settings import BaseSettings as _BaseSettings  # noqa: F401

    GenericModel = BaseModel
    from pydantic import model_validator

    # --- vendored replacements for pydantic.v1.* helpers ---
    # pydantic.v1 is unsupported on Python 3.14+, so reimplement these utilities
    # locally using the public pydantic v2 API / stdlib instead of importing them
    # from the pydantic.v1 compatibility namespace.
    import copy as _copy
    import types as _types
    from datetime import date as _date, datetime as _datetime
    from typing import Literal as _Literal

    from pydantic import TypeAdapter as _TypeAdapter

    def smart_deepcopy(obj):
        return _copy.deepcopy(obj)

    def lenient_issubclass(cls, class_or_tuple):
        try:
            return isinstance(cls, type) and issubclass(cls, class_or_tuple)
        except TypeError:
            return False

    def deep_update(mapping, update):
        updated_mapping = smart_deepcopy(mapping)
        for k, v in update.items():
            if k in updated_mapping and isinstance(updated_mapping[k], dict) and isinstance(v, dict):
                updated_mapping[k] = deep_update(updated_mapping[k], v)
            else:
                updated_mapping[k] = v
        return updated_mapping

    def is_literal_type(tp):
        return get_origin(tp) is _Literal

    def is_none_type(tp):
        return tp is None or tp is type(None)

    def is_union(tp):
        origin = get_origin(tp)
        return origin is Union or origin is getattr(_types, "UnionType", None)

    _parse_date_adapter = _TypeAdapter(_date)
    _parse_datetime_adapter = _TypeAdapter(_datetime)

    def parse_date(value):
        return _parse_date_adapter.validate_python(value)

    def parse_datetime(value):
        return _parse_datetime_adapter.validate_python(value)

    class AllowExtraModelMixin(BaseModel):
        model_config = ConfigDict(extra="allow")

    class ORMModelMixin(BaseModel):
        model_config = ConfigDict(from_attributes=True)

    class BaseSettings(_BaseSettings):
        model_config = ConfigDict(extra="ignore")

    def create_model_by_fields(
        name: str,
        fields: Sequence[ModelField],
        *,
        set_none: bool = False,
        extra: str = "ignore",
        **kwargs,
    ) -> Type[BaseModel]:
        if kwargs.pop("orm_mode", False):
            kwargs.setdefault("from_attributes", True)
        __config__ = marge_model_config(AllowExtraModelMixin, {"extra": extra, **kwargs})
        __validators__ = None

        if set_none:
            __validators__ = {"root_validator_skip_blank": model_validator(mode="before")(root_validator_skip_blank)}
            for f in fields:
                f.field_info.annotation = Optional[f.field_info.annotation]
                f.field_info.default = None
                # Pydantic v2 中 FieldInfo 用 `default_factory is None` 判断"无工厂",
                # 哨兵值是 None 而非 PydanticUndefined(Undefined)。
                # 若设为 Undefined,get_default(call_default_factory=True) 会走到
                # call_default_factory 分支并调用 PydanticUndefined(),引发
                # "PydanticUndefinedType object is not callable"。
                # 同时同步 _attributes_set:对 _final=False 的 FieldInfo,create_model
                # 会从 _attributes_set 重建字段;且 ModelField.__post_init__ 亦通过
                # Field(**_attributes_set) 构建 _type_adapter,需移除 default_factory
                # 以免与 default=None 触发 "cannot specify both default and default_factory"。
                f.field_info.default_factory = None
                # _attributes_set 经 copy_field_info 浅拷贝后与源 FieldInfo 共享同一 dict,
                # 且 model_fields 有 lru_cache,直接修改会污染原始模型字段。故先复制再改。
                # 移除 default_factory 并将 default 置 None,以兼容 create_model 从
                # _attributes_set 重建字段(_final=False)及 ModelField.__post_init__ 通过
                # Field(**_attributes_set) 构建 _type_adapter 的路径,避免
                # "cannot specify both default and default_factory"。
                attrs = dict(f.field_info._attributes_set)
                attrs.pop("default_factory", None)
                attrs["default"] = None
                f.field_info._attributes_set = attrs
        field_params = {f.name: (f.field_info.annotation, f.field_info) for f in fields}
        model: Type[BaseModel] = create_model(name, __config__=__config__, __validators__=__validators__, **field_params)
        return model

    def model_update_forward_refs(model: Type[BaseModel]):
        model.model_rebuild()

    def field_json_schema_extra(field: ModelField) -> Dict[str, Any]:
        return field.field_info.json_schema_extra or {}

    def field_outer_type(field: ModelField) -> Any:
        return field.field_info.annotation

    def field_allow_none(field: ModelField) -> bool:
        ann = field.field_info.annotation
        if not is_union(ann):
            origin = get_origin(ann)
            if origin is None:
                return False
            elif origin is Annotated:
                return field_allow_none(get_args(ann)[0])
            elif not is_union(origin):
                return False
        for t in get_args(ann):
            if is_none_type(t):
                return True
        return False

    @lru_cache(maxsize=512)
    def model_fields(model: Type[BaseModel]) -> Dict[str, ModelField]:
        fields = {}
        for field_name, field in model.model_fields.items():
            fields[field_name] = ModelField(field_info=field, name=field_name)
        return fields

    def model_config(model: Type[BaseModel]) -> Union[type, Dict[str, Any]]:
        return model.model_config

    def marge_model_config(model: Type[BaseModel], update: Dict[str, Any]) -> Union[type, Dict[str, Any]]:
        return {**model.model_config, **update}

    def model_config_attr(model: Type[BaseModel], name: str, default: Any = None) -> Any:
        return model.model_config.get(name, default)


def create_cloned_field(modelfield: ModelField) -> ModelField:
    """Clone a fastapi ``ModelField``.

    Replaces ``fastapi.utils.create_cloned_field`` which was removed in
    fastapi 0.141.0. Uses ``fastapi._compat.copy_field_info`` to copy the
    underlying ``FieldInfo`` and rewraps it into a new ``ModelField``,
    preserving ``name`` and ``mode``.
    """
    return ModelField(
        field_info=copy_field_info(
            field_info=modelfield.field_info,
            annotation=modelfield.field_info.annotation,
        ),
        name=modelfield.name,
        mode=getattr(modelfield, "mode", "validation"),
    )


def annotation_outer_type(tp: Any) -> Any:
    """Get the base type of the annotation."""
    if tp is Ellipsis:
        return Any
    origin = get_origin(tp)
    if origin is None:
        return tp
    elif is_union(origin) or origin is Annotated:
        pass
    elif origin in sequence_types:
        return origin
    elif origin in {Dict, dict}:
        return dict
    elif lenient_issubclass(origin, BaseModel):
        return origin
    args = get_args(tp)
    for arg in args:
        if is_literal_type(tp):
            arg = type(arg)
        if is_none_type(arg):
            continue
        return annotation_outer_type(arg)
    return tp


def scalar_sequence_inner_type(tp: Any) -> Any:
    origin = get_origin(tp)
    if origin is None:
        return Any
    elif is_union(origin) or origin is Annotated:  # Return the type of the first element
        return scalar_sequence_inner_type(get_args(tp)[0])
    args = get_args(tp)
    return annotation_outer_type(args[0]) if args else Any


def validator_skip_blank(v, type_: type):
    if isinstance(v, str):
        if not v:
            if issubclass(type_, Enum):
                if "" not in type_._value2member_map_:
                    return None
                return ""
            if not issubclass(type_, str):
                return None
            return ""
        if issubclass(type_, int):
            v = int(v)
    elif isinstance(v, int) and issubclass(type_, str):
        v = str(v)
    return v


def root_validator_skip_blank(cls, values: Dict[str, Any]):
    fields = model_fields(cls)

    def get_field_by_alias(alias: str) -> Optional[ModelField]:
        for f in fields.values():
            if f.alias == alias:
                return f
        return None

    for k, v in values.items():
        field = get_field_by_alias(k)
        if field:
            values[k] = validator_skip_blank(v, annotation_outer_type(field.field_info.annotation))
    return values


def create_model_by_model(
    model: Type[BaseModel],
    name: str,
    *,
    include: Set[str] = None,
    exclude: Set[str] = None,
    set_none: bool = False,
    **kwargs,
) -> Type[BaseModel]:
    """Create a new model by the BaseModel."""
    fields = model_fields(model)
    keys = set(fields.keys())
    if include:
        keys &= include
    if exclude:
        keys -= exclude
    fields = {name: create_cloned_field(field) for name, field in fields.items() if name in keys}
    return create_model_by_fields(name, list(fields.values()), set_none=set_none, **kwargs)
