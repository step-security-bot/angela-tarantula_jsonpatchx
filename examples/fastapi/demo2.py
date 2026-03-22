"""
Demo 2: Player and guild progression using custom registries per model.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import HTTPException, Path

from examples.fastapi.shared import (
    AppendOp,
    AppendUniqueOp,
    EnforceMaxLenOp,
    Guild,
    GuildId,
    IncrementOp,
    Player,
    PlayerId,
    RemoveValueOp,
    RequireMinimumOp,
    ToggleBoolOp,
    create_app,
    get_guild,
    get_player,
    save_guild,
    save_player,
)
from jsonpatchx import (
    AddOp,
    CopyOp,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
)
from jsonpatchx.fastapi import JsonPatchRoute
from jsonpatchx.pydantic import JsonPatchFor

STRICT_JSON_PATCH = True

type PlayerRegistry = (
    AddOp
    | CopyOp
    | MoveOp
    | RemoveOp
    | ReplaceOp
    | TestOp
    | IncrementOp
    | ToggleBoolOp
    | RequireMinimumOp
    | AppendUniqueOp
    | RemoveValueOp
)
type GuildRegistry = (
    AddOp
    | CopyOp
    | MoveOp
    | RemoveOp
    | ReplaceOp
    | TestOp
    | AppendOp
    | IncrementOp
    | EnforceMaxLenOp
)

PlayerPatch = JsonPatchFor[Player, PlayerRegistry]
GuildPatch = JsonPatchFor[Guild, GuildRegistry]
player_patch = JsonPatchRoute(
    PlayerPatch,
    examples={
        "glitter-boost": {
            "summary": "Bump XP and toggle premium",
            "value": [
                {"op": "increment", "path": "/xp", "value": 50},
                {"op": "toggle", "path": "/premium"},
            ],
        },
        "sparkle-unlock": {
            "summary": "Require level, then add a perk",
            "value": [
                {"op": "require_min", "path": "/level", "min_value": 5},
                {"op": "append_unique", "path": "/perks", "value": "storm-dash"},
            ],
        },
        "snack-quest": {
            "summary": "Consume an item and earn XP",
            "value": [
                {"op": "remove_value", "path": "/inventory", "value": "healing_potion"},
                {"op": "increment", "path": "/xp", "value": 25},
            ],
        },
    },
    strict_content_type=STRICT_JSON_PATCH,
)
guild_patch = JsonPatchRoute(
    GuildPatch,
    examples={
        "owl-parade": {
            "summary": "Add badge and raise cap",
            "value": [
                {"op": "append", "path": "/badges", "value": "raid-ready"},
                {"op": "increment", "path": "/max_members", "value": 5},
            ],
        },
        "cozy-welcome": {
            "summary": "Trim members to cap and add a badge",
            "value": [
                {
                    "op": "enforce_max_len",
                    "path": "/members",
                    "max_path": "/max_members",
                },
                {"op": "append", "path": "/badges", "value": "candle-lit"},
            ],
        },
        "snug-fit": {
            "summary": "Add a member, then trim to max size",
            "value": [
                {"op": "append", "path": "/members", "value": "Nova"},
                {
                    "op": "enforce_max_len",
                    "path": "/members",
                    "max_path": "/max_members",
                },
            ],
        },
    },
    strict_content_type=STRICT_JSON_PATCH,
)

app = create_app(
    title="Demo 2: Player and guild progression",
    description="Custom registries per model (players vs guilds) using `JsonPatchFor[Model, CustomRegistry]`.",
)


@app.get(
    "/players/{player_id}",
    response_model=Player,
    tags=["players"],
    summary="Get a player",
    description="Fetch a player by id.",
)
def get_player_endpoint(
    player_id: Annotated[
        PlayerId,
        Path(...),
    ],
) -> Player:
    player = get_player(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="player not found")
    return player


@app.patch(
    "/players/{player_id}",
    response_model=Player,
    tags=["players"],
    summary="Patch a player",
    description="Apply custom ops to a Player model.",
    **player_patch.route_kwargs(),
)
def patch_player(
    player_id: Annotated[
        PlayerId,
        Path(...),
    ],
    patch: Annotated[PlayerPatch, player_patch.Body()],
) -> Player:
    player = get_player(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="player not found")
    updated = patch.apply(player)
    save_player(player_id, updated)
    return updated


@app.get(
    "/guilds/{guild_id}",
    response_model=Guild,
    tags=["guilds"],
    summary="Get a guild",
    description="Fetch a guild by id.",
)
def get_guild_endpoint(
    guild_id: Annotated[
        GuildId,
        Path(...),
    ],
) -> Guild:
    guild = get_guild(guild_id)
    if guild is None:
        raise HTTPException(status_code=404, detail="guild not found")
    return guild


@app.patch(
    "/guilds/{guild_id}",
    response_model=Guild,
    tags=["guilds"],
    summary="Patch a guild",
    description="Apply custom ops to a Guild model.",
    **guild_patch.route_kwargs(),
)
def patch_guild(
    guild_id: Annotated[
        GuildId,
        Path(...),
    ],
    patch: Annotated[GuildPatch, guild_patch.Body()],
) -> Guild:
    guild = get_guild(guild_id)
    if guild is None:
        raise HTTPException(status_code=404, detail="guild not found")
    updated = patch.apply(guild)
    save_guild(guild_id, updated)
    return updated
