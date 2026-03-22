from __future__ import annotations

import copy
import os
from collections.abc import Iterable, MutableMapping, Sequence
from enum import Enum, IntEnum
from typing import Any, Literal, Self, override

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from jsonpatchx import (
    AddOp,
    JSONValue,
    OperationSchema,
    OperationValidationError,
    PatchConflictError,
    RemoveOp,
    ReplaceOp,
)
from jsonpatchx.backend import PointerBackend
from jsonpatchx.exceptions import InvalidJSONPointer
from jsonpatchx.fastapi import install_jsonpatch_error_handlers
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.types import (
    JSONArray,
    JSONBoolean,
    JSONNull,
    JSONNumber,
    JSONObject,
    JSONString,
)

DEMO_UNEXPECTED_ERRORS = os.getenv("JSONPATCH_DEMO_UNEXPECTED_ERRORS", "1") != "0"


def create_app(*, title: str, description: str, version: str = "0.1.0") -> FastAPI:
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        separate_input_output_schemas=False,
    )
    install_jsonpatch_error_handlers(app)

    @app.get("/", include_in_schema=False)
    def _root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


class CustomerId(IntEnum):
    one = 1
    two = 2


class PlayerId(IntEnum):
    one = 1
    two = 2


class GuildId(IntEnum):
    one = 1
    two = 2


class ApprenticeId(IntEnum):
    one = 1
    two = 2


class ConfigId(str, Enum):
    service = "service"


class SpellbookId(str, Enum):
    grimoire = "grimoire"
    coven = "coven"


class Customer(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    address: str
    tags: list[str] = Field(default_factory=list)
    marketing_opt_in: bool = False
    status: str = "active"


class Player(BaseModel):
    id: int
    name: str
    xp: int = 0
    level: int = 1
    inventory: list[str] = Field(default_factory=list)
    perks: list[str] = Field(default_factory=list)
    premium: bool = False


class Guild(BaseModel):
    id: int
    name: str
    motto: str
    badges: list[str] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)
    max_members: int = 0


class Apprentice(BaseModel):
    id: int
    name: str
    mana: int = 0
    sigils: list[str] = Field(default_factory=list)
    rank: str = "novice"


_SEED_CUSTOMERS: dict[int, Customer] = {
    1: Customer(
        id=1,
        name="Morgan Lee",
        email="morgan@example.com",
        phone="+1-555-0101",
        address="123 Maple St, Portland, OR",
        tags=["vip", "newsletter"],
        marketing_opt_in=True,
    ),
    2: Customer(
        id=2,
        name="Jules Park",
        email="jules@example.com",
        phone="+1-555-0189",
        address="58 Cedar Ave, Austin, TX",
        tags=["new", "trial"],
        marketing_opt_in=False,
    ),
}

_SEED_PLAYERS: dict[int, Player] = {
    1: Player(
        id=1,
        name="Avery",
        xp=1200,
        level=8,
        inventory=["iron_sword", "healing_potion"],
        perks=["double_xp"],
        premium=True,
    ),
    2: Player(
        id=2,
        name="Jules",
        xp=350,
        level=3,
        inventory=["wooden_shield"],
        perks=[],
        premium=False,
    ),
}

_SEED_GUILDS: dict[int, Guild] = {
    1: Guild(
        id=1,
        name="Moonlit Owls",
        motto="Leave no quest behind.",
        badges=["founders", "raid-ready"],
        members=["Avery", "Rowan", "Juniper"],
        max_members=5,
    ),
    2: Guild(
        id=2,
        name="Pixel Bears",
        motto="Cozy but unstoppable.",
        badges=["crafting", "casual"],
        members=["Jules", "Morgan"],
        max_members=4,
    ),
}

_SEED_APPRENTICES: dict[int, Apprentice] = {
    1: Apprentice(
        id=1,
        name="Rowan",
        mana=120,
        sigils=["ember", "ward"],
        rank="adept",
    ),
    2: Apprentice(
        id=2,
        name="Juniper",
        mana=45,
        sigils=["mist"],
        rank="novice",
    ),
}

_SEED_CONFIGS: MutableMapping[str, JSONValue] = {
    "service": {
        "service_name": "Atlas",
        "features": {"chat": True, "beta": False},
        "limits": {"max_users": 250, "retry_budget": 3},
        "tags": ["internal", "staff"],
    },
}

_CUSTOMERS: dict[int, Customer] = copy.deepcopy(_SEED_CUSTOMERS)
_PLAYERS: dict[int, Player] = copy.deepcopy(_SEED_PLAYERS)
_GUILDS: dict[int, Guild] = copy.deepcopy(_SEED_GUILDS)
_APPRENTICES: dict[int, Apprentice] = copy.deepcopy(_SEED_APPRENTICES)
_CONFIGS: MutableMapping[str, JSONValue] = copy.deepcopy(_SEED_CONFIGS)
_SPELLBOOKS: MutableMapping[str, JSONValue] = {
    "grimoire": {
        "wards": {"protection": {"level": 2}},
        "rituals": {"summon": {"enabled": False}},
        "familiars": ["owl", "cat"],
        "ingredients": {"moon_salt": 3},
    },
    "coven": {
        "wards": {"protection": {"level": 1}},
        "rituals": {"harvest": {"enabled": True}},
        "familiars": ["raven"],
        "ingredients": {"lavender": 5},
    },
}


def reset_store() -> None:
    _CUSTOMERS.clear()
    _CUSTOMERS.update(copy.deepcopy(_SEED_CUSTOMERS))
    _PLAYERS.clear()
    _PLAYERS.update(copy.deepcopy(_SEED_PLAYERS))
    _GUILDS.clear()
    _GUILDS.update(copy.deepcopy(_SEED_GUILDS))
    _APPRENTICES.clear()
    _APPRENTICES.update(copy.deepcopy(_SEED_APPRENTICES))
    _CONFIGS.clear()
    _CONFIGS.update(copy.deepcopy(_SEED_CONFIGS))
    _SPELLBOOKS.clear()
    _SPELLBOOKS.update(
        {
            "grimoire": {
                "wards": {"protection": {"level": 2}},
                "rituals": {"summon": {"enabled": False}},
                "familiars": ["owl", "cat"],
                "ingredients": {"moon_salt": 3},
            },
            "coven": {
                "wards": {"protection": {"level": 1}},
                "rituals": {"harvest": {"enabled": True}},
                "familiars": ["raven"],
                "ingredients": {"lavender": 5},
            },
        }
    )


def get_customer(customer_id: int) -> Customer | None:
    return _CUSTOMERS.get(customer_id)


def save_customer(customer_id: int, customer: Customer) -> None:
    _CUSTOMERS[customer_id] = customer


def get_player(player_id: int) -> Player | None:
    return _PLAYERS.get(player_id)


def save_player(player_id: int, player: Player) -> None:
    _PLAYERS[player_id] = player


def get_guild(guild_id: int) -> Guild | None:
    return _GUILDS.get(guild_id)


def save_guild(guild_id: int, guild: Guild) -> None:
    _GUILDS[guild_id] = guild


def get_apprentice(apprentice_id: int) -> Apprentice | None:
    return _APPRENTICES.get(apprentice_id)


def save_apprentice(apprentice_id: int, apprentice: Apprentice) -> None:
    _APPRENTICES[apprentice_id] = apprentice


def get_config(config_id: str) -> JSONValue | None:
    return _CONFIGS.get(config_id)


def save_config(config_id: str, doc: JSONValue) -> None:
    _CONFIGS[config_id] = doc


def get_spellbook(spellbook_id: str) -> JSONValue | None:
    return _SPELLBOOKS.get(spellbook_id)


def save_spellbook(spellbook_id: str, doc: JSONValue) -> None:
    _SPELLBOOKS[spellbook_id] = doc


class IncrementOp(OperationSchema):
    model_config = ConfigDict(
        title="Increment operation",
        json_schema_extra={"description": "Increments a numeric field by a value."},
    )

    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    value: JSONNumber = Field(gt=0, multiple_of=5)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        total = current + self.value
        return AddOp(path=self.path, value=total).apply(doc)


class AppendOp(OperationSchema):
    model_config = ConfigDict(
        title="Append operation",
        json_schema_extra={"description": "Appends a value to an array."},
    )

    op: Literal["append"] = "append"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=[*current, self.value]).apply(doc)


class ExtendOp(OperationSchema):
    model_config = ConfigDict(
        title="Extend operation",
        json_schema_extra={"description": "Extends an array with a list of values."},
    )

    op: Literal["extend"] = "extend"
    path: JSONPointer[JSONArray[JSONValue]]
    values: list[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=[*current, *self.values]).apply(doc)


class ToggleBoolOp(OperationSchema):
    model_config = ConfigDict(
        title="Toggle operation",
        json_schema_extra={"description": "Toggles a boolean value at a path."},
    )

    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=not current).apply(doc)


class RequireMinimumOp(OperationSchema):
    model_config = ConfigDict(
        title="Require minimum operation",
        json_schema_extra={"description": "Ensures a numeric value meets a minimum."},
    )

    op: Literal["require_min"] = "require_min"
    path: JSONPointer[JSONNumber]
    min_value: JSONNumber = Field(gt=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if current < self.min_value:
            raise PatchConflictError(
                f"value {current} is below required minimum {self.min_value}"
            )
        return doc


class AppendUniqueOp(OperationSchema):
    model_config = ConfigDict(
        title="Append unique operation",
        json_schema_extra={
            "description": "Appends a value if it is not already present."
        },
    )

    op: Literal["append_unique"] = "append_unique"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.value in current:
            return doc
        return AddOp(path=self.path, value=[*current, self.value]).apply(doc)


class RemoveValueOp(OperationSchema):
    model_config = ConfigDict(
        title="Remove value operation",
        json_schema_extra={"description": "Removes a value from an array."},
    )

    op: Literal["remove_value"] = "remove_value"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.value not in current:
            raise PatchConflictError(f"value {self.value!r} not found")
        remaining = []
        removed = False
        for item in current:
            if not removed and item == self.value:
                removed = True
                continue
            remaining.append(item)
        return AddOp(path=self.path, value=remaining).apply(doc)


class EnforceMaxLenOp(OperationSchema):
    model_config = ConfigDict(
        title="Enforce max length operation",
        json_schema_extra={
            "description": "Trims a list from the front until it fits a max size."
        },
    )

    op: Literal["enforce_max_len"] = "enforce_max_len"
    path: JSONPointer[JSONArray[JSONValue]]
    max_path: JSONPointer[JSONNumber]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = list(self.path.get(doc))
        max_size_raw = self.max_path.get(doc)
        max_size = int(max_size_raw)
        if max_size <= 0:
            return doc
        while len(current) > max_size:
            current.pop(0)
        return AddOp(path=self.path, value=current).apply(doc)


class EnsureObjectOp(OperationSchema):
    model_config = ConfigDict(
        title="Ensure object operation",
        json_schema_extra={
            "description": "Ensures the target path resolves to an object, creating one if missing."
        },
    )

    op: Literal["ensure_object"] = "ensure_object"
    path: JSONPointer[JSONObject[JSONValue]]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        try:
            current = self.path.ptr.resolve(doc)
        except Exception:
            return AddOp(path=self.path, value={}).apply(doc)
        if not isinstance(current, dict):
            raise PatchConflictError(
                f"expected object at {str(self.path)!r}, got {type(current).__name__}"
            )
        return doc


class SwapOp(OperationSchema):
    model_config = ConfigDict(
        title="Swap operation",
        json_schema_extra={
            "description": (
                "Swaps the values at paths a and b. "
                "Paths a and b may not be proper prefixes of each other."
            )
        },
    )

    op: Literal["swap"] = "swap"
    a: JSONPointer[JSONValue]
    b: JSONPointer[JSONValue]

    @model_validator(mode="after")
    def _reject_proper_prefixes(self) -> Self:
        if self.a.is_parent_of(self.b):
            raise OperationValidationError(
                "pointer 'b' cannot be a child of pointer 'a'"
            )
        if self.b.is_parent_of(self.a):
            raise OperationValidationError(
                "pointer 'a' cannot be a child of pointer 'b'"
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value_a = self.a.get(doc)
        value_b = self.b.get(doc)
        if DEMO_UNEXPECTED_ERRORS and value_a == value_b:
            raise RuntimeError("boom")
        doc = AddOp(path=self.a, value=value_b).apply(doc)
        return AddOp(path=self.b, value=value_a).apply(doc)


class RemoveNumberOp(OperationSchema):
    model_config = ConfigDict(
        title="Remove number operation",
        json_schema_extra={"description": "Removes a numeric value at a path."},
    )

    op: Literal["remove_number"] = "remove_number"
    path: JSONPointer[JSONNumber]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return RemoveOp(path=self.path).apply(doc)


class SetMessageOp(OperationSchema):
    model_config = ConfigDict(
        title="Set message operation",
        json_schema_extra={"description": "Sets a string field to text or null."},
    )

    op: Literal["set_message"] = "set_message"
    path: JSONPointer[JSONString | JSONNull]
    message: JSONString | JSONNull

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return AddOp(path=self.path, value=self.message).apply(doc)


class RunePointer(PointerBackend):
    """
    Demonstrative pointer backend using dot-separated rune paths ("a.b.c").

    Notes:
    - Root pointer is the empty string.
    - No escaping is supported; empty segments are rejected.
    """

    _parts: tuple[str, ...]

    def __init__(self, pointer: str) -> None:
        if pointer == "":
            self._parts = tuple()
            return
        if "." not in pointer:
            self._parts = (pointer,)
        else:
            self._parts = tuple(pointer.split("."))
        if any(part == "" for part in self._parts):
            raise InvalidJSONPointer("invalid dot pointer")

    @property
    @override
    def parts(self) -> Sequence[str]:
        return self._parts

    @classmethod
    @override
    def from_parts(cls, parts: Iterable[Any]) -> Self:
        tokens = [str(p) for p in parts]
        if not tokens:
            return cls("")
        return cls(".".join(tokens))

    @override
    def resolve(self, data: Any) -> Any:
        cur = data
        for part in self._parts:
            if isinstance(cur, dict):
                cur = cur[part]
            elif isinstance(cur, list):
                if not part.isdigit():
                    raise KeyError("invalid list index")
                idx = int(part)
                cur = cur[idx]
            else:
                raise KeyError("non-container")
        return cur

    @override
    def __str__(self) -> str:
        return ".".join(self._parts)

    @override
    def __hash__(self) -> int:
        return hash(self._parts)


__all__ = [
    "AddOp",
    "AppendOp",
    "AppendUniqueOp",
    "EnsureObjectOp",
    "EnforceMaxLenOp",
    "ExtendOp",
    "IncrementOp",
    "RemoveNumberOp",
    "RemoveValueOp",
    "RequireMinimumOp",
    "SetMessageOp",
    "SwapOp",
    "ToggleBoolOp",
    "create_app",
    "get_config",
    "get_customer",
    "get_player",
    "get_guild",
    "get_apprentice",
    "get_spellbook",
    "save_config",
    "save_customer",
    "save_player",
    "save_guild",
    "save_apprentice",
    "save_spellbook",
    "RunePointer",
    "Apprentice",
    "Customer",
    "Guild",
    "Player",
]
