import inspect
from collections import defaultdict
from copy import deepcopy
from types import UnionType
from typing import (
    Any,
    NotRequired,
    TypedDict,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import ConfigDict
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase, Mapped


class TypeInfo(TypedDict):
    name: str
    import_from: NotRequired[str]
    alias: NotRequired[str]
    list: NotRequired[bool]
    optional: NotRequired[bool]


class FieldDefinition(TypedDict):
    name: str
    type: TypeInfo
    default: NotRequired[str]


class ModelDefinition(TypedDict):
    name: str
    description: NotRequired[str]
    fields: list[FieldDefinition]
    base: NotRequired[TypeInfo]
    config: ConfigDict


def build_model_definitions(models: list[ModelDefinition]) -> str:
    def type_ref(t: TypeInfo) -> str:
        ref = t.get("alias", t["name"])
        if t.get("list"):
            ref = f"list[{ref}]"
        if t.get("optional"):
            ref = f"{ref} | None"
        return ref

    # Collect imports: module -> {(name, alias)}
    imports: dict[str, set[tuple[str, str | None]]] = defaultdict(set)

    for m in models:
        # base type import (e.g., BaseModel from pydantic)
        base = m.get("base")
        if base and (import_from := base.get("import_from")):
            imports[import_from].add((base["name"], base.get("alias")))

        # field type imports
        for field in m["fields"]:
            _type = field["type"]
            if import_from := _type.get("import_from"):
                imports[import_from].add((_type["name"], _type.get("alias")))

    # Render imports in a deterministic order
    import_lines: list[str] = []
    for module in sorted(imports.keys()):
        items = sorted(imports[module], key=lambda x: (x[0], x[1] or ""))
        parts = []
        for name, alias in items:
            parts.append(f"{name} as {alias}" if alias else name)
        import_lines.append(f"from {module} import {', '.join(parts)}")

    # Render classes
    class_lines: list[str] = []
    for m in models:
        base = m.get("base")
        base_name = type_ref(base) if base else "BaseModel"

        # Add BaseModel import if base is not specified
        if not base:
            imports.setdefault("pydantic", set()).add(("BaseModel", None))

        class_lines.append(f"class {m['name']}({base_name}):")

        # Add description as docstring if present
        description = m.get("description")
        if description:
            class_lines.append(f'    """{description}"""')
            class_lines.append("")

        # Add config
        config_items = []
        for key, value in m["config"].items():
            if isinstance(value, str):
                config_items.append(f"{key}='{value}'")
            else:
                config_items.append(f"{key}={value!r}")
        if len(config_items) > 0:
            config_str = ", ".join(config_items)
            class_lines.append(f"    model_config = ConfigDict({config_str})")
            class_lines.append("")
            # Add ConfigDict import
            imports.setdefault("pydantic", set()).add(("ConfigDict", None))

        # Add fields
        for field in m["fields"]:
            line = f"    {field['name']}: {type_ref(field['type'])}"
            if default := field.get("default"):
                line += f" = {default}"
            class_lines.append(line)

        class_lines.append("")  # blank line after each class

    # Re-render imports if ConfigDict or BaseModel was added
    import_lines = []
    for module in sorted(imports.keys()):
        items = sorted(imports[module], key=lambda x: (x[0], x[1] or ""))
        parts = []
        for name, alias in items:
            parts.append(f"{name} as {alias}" if alias else name)
        import_lines.append(f"from {module} import {', '.join(parts)}")

    # Join (imports, blank line, classes). Match the sample formatting.
    out: list[str] = []
    out.extend(import_lines)
    if import_lines:
        out.append("")  # blank line between imports and first class
    out.extend(class_lines)

    # Avoid extra blank lines at the very end (sample ends without an extra blank line)
    while out and out[-1] == "":
        out.pop()

    return "\n".join(out)


def detect_typeinfo(t: Any) -> TypeInfo:
    """型オブジェクトから型情報 (TypeInfo) を抽出する"""
    origin = get_origin(t)
    args = get_args(t)

    if origin is Mapped:
        inner_type = args[0]
        return detect_typeinfo(inner_type)

    # Union
    if origin is Union or origin is UnionType:
        non_none_args = [arg for arg in args if arg is not type(None)]
        optional = type(None) in args

        # None 以外の型が複数ある Union は未対応
        if len(non_none_args) > 1:
            raise NotImplementedError

        result = detect_typeinfo(non_none_args[0])
        if optional:
            result["optional"] = True
        return result

    if t is type(None):
        return {"name": "None"}

    if origin is list:
        t = detect_typeinfo(args[0])
        t["list"] = True
        return t

    # TypedDict
    if hasattr(t, "__annotations__"):
        module = t.__module__
        name = t.__qualname__ if hasattr(t, "__qualname__") else t.__name__

        if module in ("builtins", "__builtin__"):
            return {"name": name}
        return {"name": name, "import_from": module}

    if origin is dict:
        return {"name": "dict"}

    if inspect.isclass(t):
        module = t.__module__
        name = t.__qualname__

        if module in ("builtins", "__builtin__"):
            return {"name": name}

        if name == "UUID" and module == "uuid":
            return {"name": "UUID", "import_from": "uuid"}

        if module == "datetime":
            return {"name": name, "import_from": "datetime"}

        return {"name": name, "import_from": module}

    return {"name": str(t)}


def sqlalchemy_model_to_pydantic_model_definition(
    cls: type[DeclarativeBase],
    name: str | None = None,
) -> ModelDefinition:
    mapper = sa_inspect(cls)
    fields: list[FieldDefinition] = []

    if name is None:
        name = getattr(cls, "__pydantic_model__")
    if type(name) is not str:
        raise ValueError("name is not specified")

    type_hints = get_type_hints(cls)
    for col in mapper.columns:
        t = detect_typeinfo(type_hints.get(col.name, col.type.python_type))
        if col.nullable:
            t["optional"] = True
        fields.append({"name": col.name, "type": t})

    for rel in mapper.relationships:
        rel_cls = rel.mapper.class_
        t: TypeInfo = {
            "name": getattr(rel_cls, "__pydantic_model__", rel_cls.__name__),
            "list": rel.uselist or False,
            "optional": True,
        }
        fields.append({"name": rel.key, "type": t, "default": "None"})

    return {
        "name": name,
        "fields": fields,
        "config": {"extra": "forbid"},
    }


def create_partial(
    base: ModelDefinition,
    name: str | None = None,
    *,
    map: dict[str, str | FieldDefinition] = {},  # フィールドを変更する
    include: set[str] | None = None,  # 指定したフィールドのみに絞り込む
    exclude: set[str] | None = None,  # 指定したフィールドを除外する
    required: set[str] | None = None,  # 指定したフィールドの Optional を外す
    optional: set[str] | None = None,  # 指定したフィールドを Optional にする
) -> ModelDefinition:
    model = deepcopy(base)

    if name:
        model["name"] = name

    for idx, field in enumerate(model["fields"]):
        if field["name"] in map:
            val = map[field["name"]]
            if type(val) is str:
                field["name"] = val
            if type(val) is FieldDefinition:
                model["fields"][idx] = val

    if include and exclude:
        raise ValueError

    if include:
        model["fields"] = [f for f in model["fields"] if f["name"] in include]

    if exclude:
        model["fields"] = [f for f in model["fields"] if f["name"] not in exclude]

    for field in model["fields"]:
        if required and field["name"] in required:
            field["type"]["optional"] = False
        if optional and field["name"] in optional:
            field["type"]["optional"] = True

    return model
