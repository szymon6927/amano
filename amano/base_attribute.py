from __future__ import annotations

from abc import abstractmethod
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Union, Type, runtime_checkable, Protocol
from typing import (
    AnyStr,
    Dict,
    FrozenSet,
    List,
    Set,
    Tuple,
    TypedDict,
    overload,
    Sequence,
    Mapping,
)

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from chili import HydrationStrategy, is_dataclass
from chili.hydration import StrategyRegistry
from chili.typing import get_origin_type, get_type_args

from .constants import (
    TYPE_MAP,
    TYPE_STRING,
    TYPE_LIST,
    TYPE_NULL,
    TYPE_BINARY,
    TYPE_BINARY_SET,
    TYPE_NUMBER_SET,
    TYPE_BOOLEAN,
    TYPE_NUMBER,
    TYPE_STRING_SET,
)
from .utils import StringEnum

serialize_value = TypeSerializer().serialize
deserialize_value = TypeDeserializer().deserialize


class FloatStrategy(HydrationStrategy):
    def hydrate(self, value: Any) -> float:
        return float(value)

    def extract(
        self, value: Any
    ) -> Decimal:  # decimal is understood by dynamodb
        return Decimal(str(value))


serializer_registry = StrategyRegistry()

# Add support for floats in dynamodb
serializer_registry.add(float, FloatStrategy())

VALID_TYPE_VALUES: Dict[str, Tuple[Type, ...]] = {
    TYPE_STRING: (str, datetime, date, time),
    TYPE_NUMBER: (Decimal, int, float),
    TYPE_LIST: (  # type: ignore
        list,
        List,
        Sequence,
        set,
        Set,
        frozenset,
        FrozenSet,
        tuple,
        Tuple,
    ),
    TYPE_MAP: (dict, Mapping, Dict, TypedDict),  # type: ignore
    TYPE_NULL: (type(None)),  # type: ignore
    TYPE_BINARY: (bytes, bytearray),
    TYPE_BOOLEAN: tuple([bool]),
    TYPE_STRING_SET: tuple([Set[str]]),
    TYPE_NUMBER_SET: tuple([Set[Union[Decimal, int, float]]]),
    TYPE_BINARY_SET: tuple([Set[Union[bytes, bytearray]]]),
}

_SUPPORTED_BASE_TYPES = {
    str: TYPE_STRING,
    AnyStr: TYPE_STRING,
    datetime: TYPE_STRING,
    date: TYPE_STRING,
    time: TYPE_STRING,
    Decimal: TYPE_NUMBER,
    int: TYPE_NUMBER,
    float: TYPE_NUMBER,
    list: TYPE_LIST,
    List: TYPE_LIST,
    Sequence: TYPE_LIST,
    set: TYPE_LIST,
    Set: TYPE_LIST,
    frozenset: TYPE_LIST,
    FrozenSet: TYPE_LIST,
    tuple: TYPE_LIST,
    Tuple: TYPE_LIST,
    dict: TYPE_MAP,
    Dict: TYPE_MAP,
    Mapping: TYPE_MAP,
    TypedDict: TYPE_MAP,
    type(None): TYPE_NULL,
    bytes: TYPE_BINARY,
    bytearray: TYPE_BINARY,
    bool: TYPE_BOOLEAN,
}

_SUPPORTED_GENERIC_TYPES: Dict[type, str] = {
    list: TYPE_LIST,
    tuple: TYPE_LIST,
    set: TYPE_LIST,
    frozenset: TYPE_LIST,
    dict: TYPE_MAP,
}


class AttributeValue(TypedDict, total=False):
    S: str
    N: str
    B: bytes
    SS: Set[str]
    NS: Set[str]
    BS: Set[bytes]
    M: Mapping[str, Any]
    L: Sequence[Any]
    NULL: bool
    BOOl: bool


class AttributeType(StringEnum):
    STRING = TYPE_STRING
    NUMBER = TYPE_NUMBER
    BOOLEAN = TYPE_BOOLEAN
    BINARY = TYPE_BINARY
    NULL = TYPE_NULL
    LIST = TYPE_LIST
    MAP = TYPE_MAP
    NUMBER_SET = TYPE_NUMBER_SET
    STRING_SET = TYPE_STRING_SET
    BINARY_SET = TYPE_BINARY_SET

    @classmethod
    def from_python_type(cls, value_type: type) -> AttributeType:
        if value_type in _SUPPORTED_BASE_TYPES.keys():
            return AttributeType(_SUPPORTED_BASE_TYPES[value_type])

        if is_dataclass(value_type):
            return AttributeType.MAP

        origin_type = get_origin_type(value_type)

        if origin_type not in _SUPPORTED_GENERIC_TYPES:
            raise TypeError(f"Unsupported type {value_type}")

        if origin_type is set or origin_type is frozenset:
            value_subtype = get_type_args(value_type)[0]
            mapped_type = cls.from_python_type(value_subtype)

            if mapped_type == AttributeType.STRING:
                return AttributeType.STRING_SET

            if mapped_type == AttributeType.NUMBER:
                return AttributeType.NUMBER_SET

            if mapped_type == AttributeType.BINARY:
                return AttributeType.BINARY_SET

        return AttributeType(_SUPPORTED_GENERIC_TYPES[origin_type])

    @overload   # type: ignore
    def __eq__(self, other: str) -> bool:
        ...

    @overload
    def __eq__(self, other: AttributeType) -> bool:
        ...

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other

        if isinstance(other, AttributeType):
            return self.value == other.value

        raise NotImplemented(
            f"Comparison between {self.__class__} "
            f"and {type(other)} is not supported."
        )


@runtime_checkable
class AbstractAttribute(Protocol):
    name: str
    type: AttributeType
    default_value: Any
    __attribute_type__: Type

    @abstractmethod
    def extract(self, value: Any, simple: bool = False) -> AttributeValue:
        ...

    def hydrate(self, value: AttributeValue, simple: bool = False) -> Any:
        ...
