import pytest
from pydantic import BaseModel, ConfigDict

from jsonpatchx.exceptions import PatchConflictError, PatchValidationError
from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.registry import StandardRegistry


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    name: str


class Other(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    title: str


def test_model_validation_failure() -> None:
    UserPatch = JsonPatchFor[User, StandardRegistry]
    patch = UserPatch.model_validate([{"op": "replace", "path": "/name", "value": 123}])
    with pytest.raises(PatchValidationError):
        patch.apply(User(id=1, name="Ada"))


def test_wrong_model_instance() -> None:
    UserPatch = JsonPatchFor[User, StandardRegistry]
    patch = UserPatch.model_validate(
        [{"op": "replace", "path": "/name", "value": "Ada"}]
    )
    with pytest.raises(PatchConflictError):
        patch.apply(Other(id=1, title="Dr."))  # type: ignore[arg-type]
