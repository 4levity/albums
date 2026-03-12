import json
from typing import Any, override

from sqlalchemy import Dialect, Integer, Text, TypeDecorator

from ..picture.info import LoadIssuesType

NO_DEFAULT_VALUE_LIST_STR = ["".join(["!", "NO DEFAULT VALUE"])]  # generate string at runtime and use special characters, so it won't be interned


class IntEnumAsInt[EnumType](TypeDecorator[EnumType]):
    impl = Integer

    def __init__(self, enum_type: type, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._enum_type = enum_type

    @override
    def process_bind_param(self, value: EnumType | None, dialect: Dialect):  # pyright: ignore[reportUnknownParameterType]
        return None if value is None else value.value  # type: ignore

    @override
    def process_result_value(self, value: int | None, dialect: Dialect):
        return self._enum_type(value)


class SerializableValueAsJson[_VT](TypeDecorator[_VT]):
    impl = Text

    cache_ok = True

    @override
    def process_bind_param(self, value: _VT | None, dialect: Dialect):
        return json.dumps(value)

    @override
    def process_result_value(self, value: str | None, dialect: Dialect) -> _VT | None:
        return None if value is None else json.loads(value)

    @override
    def copy(self, **kw: dict[str, Any]) -> TypeDecorator[_VT]:
        return SerializableValueAsJson[_VT]()


class LoadIssuesAsJson(TypeDecorator[LoadIssuesType]):
    impl = Text

    cache_ok = True

    @override
    def process_bind_param(self, value: LoadIssuesType | None, dialect: Dialect):
        return json.dumps(value) if value else "[]"

    @override
    def process_result_value(self, value: str | None, dialect: Dialect) -> LoadIssuesType:
        if not value:
            return ()
        load_issue: list[list[str | int]] | dict[str, str | int] = json.loads(value)
        kv = load_issue if isinstance(load_issue, list) else load_issue.items()  # old versions stored a dict instead of list of pairs, load either
        return tuple([(str(k), v) for [k, v] in kv])

    @override
    def copy(self, **kw: dict[str, Any]):
        return LoadIssuesAsJson()
