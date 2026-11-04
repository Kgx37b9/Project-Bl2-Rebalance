"""Shared BL2 balance rules, independent of the character skill mods."""

from __future__ import annotations

import copy
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
import json
import math
import struct
import time
from typing import Any


import unrealsdk  # pyright: ignore[reportMissingModuleSource]
from mods_base import BoolOption, DropdownOption, NestedOption, ObjectFlags, RestartToDisable, SliderOption, build_mod, get_pc, hook
from unrealsdk.hooks import Block, Type, prevent_hooking_direct_calls  # pyright: ignore[reportMissingModuleSource]
from unrealsdk.unreal import WrappedStruct, ZNameProperty  # pyright: ignore[reportMissingModuleSource]






# Event-driven level policies; separate internal names preserve independent state.
LEVEL_CHOICES = ["Vanilla", "Player Level", *(f"Player +{n}" for n in range(1, 11))]
LEVEL_RESTART_NOTE = " Restart the game to apply changes."
LEVEL_DEFAULTS = {
    "enemy_minimum": "Player Level", "enemy_maximum": "Vanilla",
    "loot_minimum": "Player Level", "loot_maximum": "Vanilla",
    "mission_minimum": "Player Level", "on_level_vendors": True, "item_cap_80": True,
}


def _level_choice(key: str, title: str) -> DropdownOption:
    return DropdownOption(key, LEVEL_DEFAULTS[key], list(LEVEL_CHOICES), display_name=title,
                          description="Vanilla, effective player level, or player +1 to +10. "
                          "Maximum wins if bounds conflict; the item cap is applied last." + LEVEL_RESTART_NOTE)


LEVEL_OPTIONS = {
    "enemy_minimum": _level_choice("enemy_minimum", "Minimum Enemy Level"),
    "enemy_maximum": _level_choice("enemy_maximum", "Maximum Enemy Level"),
    "loot_minimum": _level_choice("loot_minimum", "Minimum Loot Level"),
    "loot_maximum": _level_choice("loot_maximum", "Maximum Loot Level"),
    "mission_minimum": _level_choice("mission_minimum", "Minimum Mission Level"),
    "on_level_vendors": BoolOption("on_level_vendors", True, display_name="On-Level Vendors",
                                  description="Generate equipment at effective player level; the item cap still applies." + LEVEL_RESTART_NOTE),
    "item_cap_80": BoolOption("item_cap_80", True, display_name="Cap New Items at Level 80",
                             description="Cap new equipment at 80, including OP gear. Existing player gear is not rewritten." + LEVEL_RESTART_NOTE),
}
LEVEL_CATEGORY = NestedOption("level_scaling", list(LEVEL_OPTIONS.values()), display_name="Level Scaling")
_level_settings_provider: Callable[[], dict[str, Any]] = lambda: LEVEL_DEFAULTS
_level_errors: dict[str, str] = {}
_level_notified: set[str] = set()
_level_busy: set[str] = set()
_level_generated_depth = 0
_level_vendor_depth = 0
_level_generation_entries: list[bool] = []


def _level_set_settings_provider(provider: Callable[[], dict[str, Any]]) -> None:
    global _level_settings_provider
    _level_settings_provider = provider


def _level_read_options() -> dict[str, Any]:
    result = {}
    for key, option in LEVEL_OPTIONS.items():
        value = option.value
        result[key] = (value if isinstance(value, bool) else LEVEL_DEFAULTS[key]) if isinstance(LEVEL_DEFAULTS[key], bool) else (value if value in LEVEL_CHOICES else LEVEL_DEFAULTS[key])
    return result


def _level_settings() -> dict[str, Any]:
    return _level_settings_provider()


def _level_bound_level(native: int, player: int, minimum: str = "Vanilla", maximum: str = "Vanilla", *, cap: bool = False) -> int:
    value = int(native)
    def target(choice: str) -> int | None:
        if choice == "Vanilla": return None
        if choice == "Player Level": return player
        return player + int(choice.removeprefix("Player +"))
    low, high = target(minimum), target(maximum)
    if low is not None: value = max(value, low)
    if high is not None: value = min(value, high)
    if cap: value = min(value, 80)
    return value


def _level_context(controller: Any = None) -> tuple[Any, int] | None:
    try:
        pc = get_pc() if controller is None else controller
        if pc is None or pc.bDeleteMe or getattr(pc, "bPendingDelete", False): return None
        world = pc.WorldInfo
        if world is None or world.bDeleteMe or int(world.NetMode) == 3: return None
        pri = pc.PlayerReplicationInfo
        if pri is None: return None
        level = int(pri.ExpLevel)
        if level < 1: return None
        gri = world.GRI
        if gri is None: return None
        op = max(0, int(getattr(gri, "OverpowerLevelModifier", 0)))
        return pc, level + op
    except (AttributeError, IndexError, TypeError, ValueError, RuntimeError):
        return None


def _level_has_class(obj: Any, name: str) -> bool:
    kind = obj.Class
    for _ in range(32):
        if kind is None: return False
        if str(kind.Name) == name: return True
        kind = kind.SuperField
    return False


def _level_alive(obj: Any) -> bool:
    return obj is not None and not obj.bDeleteMe and not getattr(obj, "bPendingDelete", False)


def _level_enemy(pawn: Any, pc: Any) -> bool:
    return (_level_alive(pawn) and _level_has_class(pawn, "WillowAIPawn") and _level_alive(pc.Pawn)
            and not pawn.IsFriendly(pc.Pawn) and not pawn.IsNeutral(pc.Pawn))


def _level_report(label: str, exc: Exception) -> None:
    message = str(exc)
    if _level_errors.get(label) != message:
        _level_errors[label] = message
        unrealsdk.logging.error(f"[EndgameQoLRebalance] Level Scaling {label}: {message}")


def _level_notice(label: str, before: int, after: int) -> None:
    _level_errors.pop(label, None)
    if before != after and label not in _level_notified:
        _level_notified.add(label)
        unrealsdk.logging.info(f"[EndgameQoLRebalance] Level Scaling {label}: {before} -> {after}")


def _level_safe(label: str):
    def decorate(callback):
        @wraps(callback)
        def run(obj, args, ret, func):
            if label in _level_busy: return None
            _level_busy.add(label)
            try: return callback(obj, args, ret, func)
            except Exception as exc:
                _level_report(label, exc)
                return None
            finally:
                _level_busy.discard(label)
        return run
    return decorate


@contextmanager
def _level_generation(vendor: bool = False):
    global _level_generated_depth, _level_vendor_depth
    _level_generated_depth += 1
    _level_vendor_depth += int(vendor)
    try: yield
    finally:
        _level_generated_depth -= 1
        _level_vendor_depth -= int(vendor)


def _level_replay(label: str, func: Any, params: dict[str, Any], *, generate: bool = False, vendor: bool = False):
    owns_guard = label not in _level_busy
    _level_busy.add(label)
    try:
        with prevent_hooking_direct_calls():
            if generate:
                with _level_generation(vendor): result = func(**params)
            else: result = func(**params)
        return Block, result
    except Exception as exc:
        # Every ordinary Python failure after entering a replay must block the
        # original call, including IndexError and errors raised by other hooks.
        # The native call may already have begun: never execute it a second time.
        _level_report(label, exc)
        return Block
    finally:
        if owns_guard:
            _level_busy.discard(label)


def _level_item_level(native: int, player: int) -> int:
    settings = _level_settings()
    if _level_vendor_depth and settings["on_level_vendors"]:
        return min(player, 80) if settings["item_cap_80"] else player
    return _level_bound_level(native, player, settings["loot_minimum"], settings["loot_maximum"], cap=settings["item_cap_80"])


def _level_loot_active() -> bool:
    s = _level_settings()
    return s["item_cap_80"] or s["loot_minimum"] != "Vanilla" or s["loot_maximum"] != "Vanilla" or bool(_level_vendor_depth and s["on_level_vendors"])


@hook("WillowGame.PopulationFactoryBalancedAIPawn:SetupBalancedPopulationActor", Type.PRE)
@_level_safe("enemy spawn")
def _level_prepare_enemy_spawn(_obj: Any, args: Any, _ret: Any, func: Any):
    s = _level_settings()
    if s["enemy_minimum"] == s["enemy_maximum"] == "Vanilla": return None
    context = _level_context()
    if context is None or not _level_enemy(args.SpawnedPawn, context[0]): return None
    value = _level_bound_level(args.GameStage, context[1], s["enemy_minimum"], s["enemy_maximum"])
    if value == args.GameStage: return None
    params = {name: getattr(args, name) for name in ("Master", "BalancedInstigator", "SpawnedPawn", "SpawnLocationContextObject", "GameStage", "AwesomeLevel", "bUseMemento", "AIPawnMemento")}
    params["GameStage"] = value
    _level_notice("enemy spawn", args.GameStage, value)
    return _level_replay("enemy spawn", func, params)


@hook("WillowGame.WillowAIPawn:SetExpLevel", Type.PRE)
@_level_safe("enemy level")
def _level_prepare_enemy_level(pawn: Any, args: Any, _ret: Any, func: Any):
    s = _level_settings()
    if s["enemy_minimum"] == s["enemy_maximum"] == "Vanilla": return None
    context = _level_context()
    if context is None or not _level_enemy(pawn, context[0]): return None
    value = _level_bound_level(args.NewExpLevel, context[1], s["enemy_minimum"], s["enemy_maximum"])
    if value == args.NewExpLevel: return None
    _level_notice("enemy level", args.NewExpLevel, value)
    return _level_replay("enemy level", func, {"NewExpLevel": value})


@hook("WillowGame.WillowWeapon:InitializeInventory", Type.PRE)
@hook("WillowGame.WillowItem:InitializeInventory", Type.PRE)
@_level_safe("new equipment")
def _level_prepare_new_equipment(obj: Any, args: Any, _ret: Any, func: Any):
    if not _level_loot_active() or not _level_alive(obj): return None
    context = _level_context()
    if context is None: return None
    params = {name: getattr(args, name) for name in ("InBalanceDef", "InManufacturer", "InGradeIndex", "InAdditionalQueryInterfaceSource")}
    value = _level_item_level(args.InGradeIndex, context[1])
    params["InGradeIndex"] = value
    _level_notice("new equipment", args.InGradeIndex, value)
    return _level_replay("new equipment", func, params, generate=True)


@hook("WillowGame.WillowWeapon:InitializeFromDefinitionData", Type.PRE)
@hook("WillowGame.WillowItem:InitializeFromDefinitionData", Type.PRE)
@_level_safe("generated item data")
def _level_prepare_generated_item_data(obj: Any, args: Any, _ret: Any, func: Any):
    # Deserializing or rebuilding existing player gear has no generation scope.
    if not _level_generated_depth or not _level_loot_active() or not _level_alive(obj): return None
    context = _level_context()
    if context is None: return None
    original = args.NewDefinitionData
    grade = _level_item_level(original.ManufacturerGradeIndex, context[1])
    stage = _level_item_level(original.GameStage, context[1])
    if (grade, stage) == (original.ManufacturerGradeIndex, original.GameStage): return None
    data = copy.copy(original)
    data.ManufacturerGradeIndex, data.GameStage = grade, stage
    return _level_replay("generated item data", func, {"NewDefinitionData": data,
                   "InAdditionalQueryInterfaceSource": args.InAdditionalQueryInterfaceSource,
                   "bForceSelectNameParts": args.bForceSelectNameParts})


@hook("WillowGame.ItemPool:SpawnBalancedInventoryFromPool", Type.PRE)
@hook("WillowGame.ItemPool:SpawnBalancedInventoryFromInventoryBalanceDefinition", Type.PRE)
@hook("WillowGame.MissionDefinition:GetItemRewardsForPlayer", Type.PRE)
def _level_begin_generated_scope(_obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _level_generated_depth
    active = False
    try: active = _level_loot_active() and _level_context() is not None
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc: _level_report("generation context", exc)
    _level_generation_entries.append(active)
    _level_generated_depth += int(active)


@hook("WillowGame.ItemPool:SpawnBalancedInventoryFromPool", Type.POST_UNCONDITIONAL)
@hook("WillowGame.ItemPool:SpawnBalancedInventoryFromInventoryBalanceDefinition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.MissionDefinition:GetItemRewardsForPlayer", Type.POST_UNCONDITIONAL)
def _level_end_generated_scope(_obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _level_generated_depth
    if _level_generation_entries:
        _level_generated_depth = max(0, _level_generated_depth - int(_level_generation_entries.pop()))


@hook("WillowGame.WillowVendingMachine:GenerateInventory", Type.PRE)
@_level_safe("vendor generation")
def _level_prepare_vendor_generation(obj: Any, _args: Any, _ret: Any, func: Any):
    if not _level_settings()["on_level_vendors"] or not _level_alive(obj) or _level_context() is None: return None
    return _level_replay("vendor generation", func, {}, generate=True, vendor=True)


@hook("WillowGame.WillowVendingMachine:GetInventoryList", Type.PRE)
@hook("WillowGame.WillowVendingMachine:GetFeaturedItem", Type.PRE)
@_level_safe("vendor stock")
def _level_prepare_vendor_stock(vendor: Any, args: Any, _ret: Any, _func: Any) -> None:
    if not _level_settings()["on_level_vendors"] or not _level_alive(vendor): return
    context = _level_context(args.WPC)
    if context is None: return
    target = min(context[1], 80) if _level_settings()["item_cap_80"] else context[1]
    stock = list(vendor.ShopInventory)
    if vendor.FeaturedItem is not None: stock.append(vendor.FeaturedItem)
    seen: set[int] = set()
    for item in stock:
        if not _level_alive(item) or not (_level_has_class(item, "WillowWeapon") or _level_has_class(item, "WillowItem")): continue
        address = item._get_address()
        if address in seen: continue
        seen.add(address)
        current = item.DefinitionData
        if (current.ManufacturerGradeIndex, current.GameStage) == (target, target): continue
        before = int(current.GameStage)
        data = copy.copy(current)
        data.ManufacturerGradeIndex = data.GameStage = target
        with prevent_hooking_direct_calls():
            item.InitializeFromDefinitionData(data, item.AdditionalQueryInterfaceSource, False)
        actual = item.DefinitionData
        if (actual.ManufacturerGradeIndex, actual.GameStage) != (target, target):
            raise ValueError("Vendor equipment did not retain the requested level")
        _level_notice("vendor stock", before, target)


@hook("WillowGame.MissionDefinition:SetGameStage", Type.PRE)
@_level_safe("mission stage")
def _level_prepare_mission_stage(mission: Any, args: Any, _ret: Any, func: Any):
    choice = _level_settings()["mission_minimum"]
    if choice == "Vanilla" or mission.bGameStageLocked: return None
    context = _level_context()
    if context is None: return None
    target = _level_bound_level(args.NewGameStage, context[1], choice)
    if target == args.NewGameStage: return None
    _level_notice("mission stage", args.NewGameStage, target)
    return _level_replay("mission stage", func, {"NewGameStage": target})


@hook("WillowGame.MissionDefinition:SetExpLevel", Type.PRE)
@_level_safe("mission level")
def _level_prepare_mission_level(mission: Any, args: Any, _ret: Any, func: Any):
    choice = _level_settings()["mission_minimum"]
    if choice == "Vanilla" or mission.bGameStageLocked: return None
    context = _level_context()
    if context is None: return None
    target = _level_bound_level(args.NewExpLevel, context[1], choice)
    if target == args.NewExpLevel: return None
    return _level_replay("mission level", func, {"NewExpLevel": target})


@hook("WillowGame.WillowPlayerController:ServerAcceptMission", Type.PRE)
@_level_safe("mission acceptance")
def _level_prepare_mission_acceptance(controller: Any, args: Any, _ret: Any, _func: Any) -> None:
    choice = _level_settings()["mission_minimum"]
    if choice == "Vanilla" or args.Mission is None or args.Mission.bGameStageLocked: return
    context = _level_context(controller)
    if context is None: return
    mission = args.Mission
    stage = _level_bound_level(mission.GameStage, context[1], choice)
    level = _level_bound_level(mission.ExpLevel, context[1], choice)
    with prevent_hooking_direct_calls():
        if stage != mission.GameStage: mission.SetGameStage(stage)
        if level != mission.ExpLevel: mission.SetExpLevel(level)


LEVEL_HOOKS = [_level_prepare_enemy_spawn, _level_prepare_enemy_level, _level_prepare_new_equipment,
         _level_prepare_generated_item_data, _level_begin_generated_scope, _level_end_generated_scope,
         _level_prepare_vendor_generation, _level_prepare_vendor_stock,
         _level_prepare_mission_stage, _level_prepare_mission_level, _level_prepare_mission_acceptance]


GROG_MISSION_PATH = "GD_Aster_ClapTrapBeard.M_ClapTrapBeard"
GROG_WEAPON_PATH = "GD_Aster_Weapons.Pistols.Pistol_Maliwan_3_GrogNozzle"
GAME_SCALER_PATH = "GD_Balance_HealthAndDamage.HealthAndDamage.Att_UniversalBalanceScaler:ConstantAttributeValueResolver_0"
MONEY_SCALER_PATH = "GD_Economy.Universal.Att_UniversalPriceIncreasePerLevelScaler:ConstantAttributeValueResolver_1"

RESTART_NOTE = "Changes apply after restarting the game."
GROWTH_DEFAULT_PERCENT = 5
GROWTH_MIN_PERCENT = 1
GROWTH_MAX_PERCENT = 20
UVHM_HEALTH_DEFAULT = 2.0
UVHM_HEALTH_MIN = 1.0
UVHM_HEALTH_MAX = 4.0
UVHM_HEALTH_STEP = 0.25
# Native BalanceMod_PT3 has regular4.0 / badass2.6 at each vanilla threshold.
UVHM_BADASS_HEALTH_RATIO = 2.6 / 4.0
UVHM_PLAYER_VEHICLE_DAMAGE_MULTIPLIER = 3.0
UVHM_AMMO_DROP_DEFAULT = 2
UVHM_AMMO_DROP_MIN = 1
UVHM_AMMO_DROP_MAX = 5
UVHM_COMMON_LOOT_START_LEVEL = 50
UVHM_COMMON_LOOT_LATE_LEVEL = 61
UVHM_COMMON_LOOT_EARLY_WEIGHT = 0.10
UVHM_COMMON_LOOT_LATE_WEIGHT = 0.02
# Own uncommon-chest weights, independent of common-item weights.
UVHM_CHEST_LOOT_WEIGHTS = ((1, 0.15), (61, 0.0625), (71, 0.025))
# Tuning inputs for the UVHM player-wide native status-damage bonus.
# 1.0 is neutral: MT_Scale receives factor - 1, not factor itself.
UVHM_STATUS_DAMAGE_MULTIPLIERS = {
    "Incendiary": 1.0,
    "Shock": 1.0,
    "Corrosive": 1.0,
}
game_growth = SliderOption(
    "growth_percent", GROWTH_DEFAULT_PERCENT, GROWTH_MIN_PERCENT, GROWTH_MAX_PERCENT, step=1, is_integer=True,
    display_name="Growth per Level (%)",
    description="Global health and damage growth per level. 5 means a factor of 1.05. " + RESTART_NOTE,
)
money_growth = SliderOption(
    "growth_percent", GROWTH_DEFAULT_PERCENT, GROWTH_MIN_PERCENT, GROWTH_MAX_PERCENT, step=1, is_integer=True,
    display_name="Growth per Level (%)",
    description="Money and price growth per level. 5 means a factor of 1.05. " + RESTART_NOTE,
)
uvhm_enabled = BoolOption(
    "enabled", True, display_name="Enabled",
    description="Enable UVHM rules with configurable enemy health, no passive enemy regeneration, loot and slag. " + RESTART_NOTE,
)
uvhm_enemy_health = SliderOption(
    "enemy_health_multiplier", UVHM_HEALTH_DEFAULT, UVHM_HEALTH_MIN, UVHM_HEALTH_MAX,
    step=UVHM_HEALTH_STEP, is_integer=False, display_name="Enemy Health and Shield Multiplier",
    description="UVHM regular-enemy health and shield multiplier, from 1.00 to 4.00 in steps of 0.25. "
                "Default: 2.00. Badass health and shields use the native health proportion. "
                "Separate from health growth per level. " + RESTART_NOTE,
)
grog_enabled = BoolOption(
    "enabled", True, display_name="Enabled",
    description="Add the Grog Nozzle to The Beard Makes The Man rewards. Preserves other rewards. Not retroactive. " + RESTART_NOTE,
)
raid_health_enabled = BoolOption(
    "enabled", True, display_name="Enabled",
    description="Use the actual party size for Hyperius, Master Gee, Voracidous and Pyro Pete health "
                "when native effective player count is inflated. Set Master Gee's UVHM health multiplier to 1000 "
                "and Dexiduous' base health multiplier to 2500. Raise Hyperius' health by 75%. "
                "Reduce Voracidous' transferable UVHM shield; preserve other shields, damage and loot. " + RESTART_NOTE,
)
level_resistance_enabled = BoolOption(
    "higher_level_resistance", True, display_name="Higher-Level Enemy Resistance",
    description="Remove the damage reduction enemies gain solely from being above your level. " + RESTART_NOTE,
)
level_enemy_damage_enabled = BoolOption(
    "higher_level_damage", True, display_name="Higher-Level Enemy Damage",
    description="Remove the extra damage enemies deal solely from being above your level. " + RESTART_NOTE,
)
level_status_chance_enabled = BoolOption(
    "higher_level_status_chance", True, display_name="Status Chance by Level",
    description="Remove level-difference penalties to elemental status chance, including UVHM/OP overrides. " + RESTART_NOTE,
)
LEVEL_DIFFERENCE_KEYS = ("higher_level_resistance", "higher_level_damage", "higher_level_status_chance")
loot_stars_enabled = BoolOption(
    "enabled", True, display_name="Enabled",
    description="Show a custom gold star on the minimap for Legendary, Pearlescent, Seraph "
                "and Effervescent equipment on the ground. " + RESTART_NOTE,
)
ammo_drop_multiplier = SliderOption(
    "ammo_drop_multiplier", UVHM_AMMO_DROP_DEFAULT, UVHM_AMMO_DROP_MIN, UVHM_AMMO_DROP_MAX,
    step=1, is_integer=True, display_name="UVHM Ammo Pack Drops (x)",
    description="Multiplier for ammo from UVHM ammo packs. 1 leaves the native value unchanged; "
                "default: 2. Requires UVHM Balance enabled. " + RESTART_NOTE,
)
ammo_capacity_enabled = BoolOption(
    "ammo_capacity", True, display_name="Ammo Capacity",
    description="Sniper reserve: 72 base and +24 per SDU. Shotgun reserve: 140 base and +30 per SDU. "
                "Preserves purchased upgrade counts and magazine sizes. " + RESTART_NOTE,
)
bank_capacity_enabled = BoolOption(
    "bank_capacity", True, display_name="Personal Bank Capacity",
    description="Personal bank: 25 initial slots, then +5, +5, +10, +15 and +20 for each further SDU. "
                "Solo play. Preserves larger existing capacity and stored equipment. " + RESTART_NOTE,
)
backpack_capacity_enabled = BoolOption(
    "backpack_capacity", True, display_name="Backpack Capacity",
    description="Backpack starts with 22 slots; SDUs add +3, +3, +4, +4, +4, +5, +5, +5 and +15. "
                "Solo play; preserves larger existing capacity. " + RESTART_NOTE,
)
eridium_capacity_enabled = BoolOption(
    "eridium_capacity", True, display_name="Eridium Capacity (1000)",
    description="Raise the Eridium carrying limit from 500 to 1000 on compatible Windows BL2 builds. "
                "The executable is checked before a memory-only change. " + RESTART_NOTE,
)
SUPPORT_OPTIONS = [
    LEVEL_CATEGORY,
    NestedOption("resources_storage", [backpack_capacity_enabled, bank_capacity_enabled,
                                       ammo_capacity_enabled, ammo_drop_multiplier, eridium_capacity_enabled],
                 display_name="Resources and Storage"),
    NestedOption("loot_stars", [loot_stars_enabled], display_name="Rare Loot Minimap Stars"),
    NestedOption("game_scaling", [game_growth], display_name="Game Scaling"),
    NestedOption("money_scaling", [money_growth], display_name="Money Scaling"),
    NestedOption("uvhm_rebalance", [uvhm_enabled, uvhm_enemy_health], display_name="UVHM Balance"),
    NestedOption("raid_health", [raid_health_enabled], display_name="Raid Boss Health"),
    NestedOption("grog_quest", [grog_enabled], display_name="Grog Nozzle Mission Reward"),
    NestedOption("level_difference", [level_resistance_enabled, level_enemy_damage_enabled,
                                      level_status_chance_enabled], display_name="Level Difference Corrections"),
]
_OPTION_VALUES = {
    "game_growth_percent": game_growth, "money_growth_percent": money_growth,
    "uvhm_rebalance": uvhm_enabled, "grog_quest": grog_enabled,
    "uvhm_enemy_health_multiplier": uvhm_enemy_health,
    "higher_level_resistance": level_resistance_enabled,
    "higher_level_damage": level_enemy_damage_enabled,
    "higher_level_status_chance": level_status_chance_enabled,
    "loot_stars": loot_stars_enabled,
    "ammo_capacity": ammo_capacity_enabled,
    "ammo_drop_multiplier": ammo_drop_multiplier,
    "bank_capacity": bank_capacity_enabled,
    "backpack_capacity": backpack_capacity_enabled,
    "eridium_capacity": eridium_capacity_enabled,
    "raid_health": raid_health_enabled,
}
_DEFAULT_SETTINGS: dict[str, Any] = {
    key: UVHM_HEALTH_DEFAULT if key == "uvhm_enemy_health_multiplier" else
    UVHM_AMMO_DROP_DEFAULT if key == "ammo_drop_multiplier" else
    GROWTH_DEFAULT_PERCENT if key.endswith("_percent") else True for key in _OPTION_VALUES
}
_DEFAULT_SETTINGS.update(LEVEL_DEFAULTS)
_session_settings: dict[str, Any] | None = None


def _read_menu_settings() -> dict[str, Any]:
    values = {}
    for key, option in _OPTION_VALUES.items():
        if key == "uvhm_enemy_health_multiplier":
            try:
                value = float(option.value)
                if isinstance(option.value, bool) or not math.isfinite(value):
                    raise ValueError("Invalid health multiplier")
                value = max(UVHM_HEALTH_MIN, min(UVHM_HEALTH_MAX, value))
                values[key] = round(value / UVHM_HEALTH_STEP) * UVHM_HEALTH_STEP
            except (TypeError, ValueError, OverflowError):
                values[key] = UVHM_HEALTH_DEFAULT
        elif key == "ammo_drop_multiplier":
            try:
                value = float(option.value)
                if isinstance(option.value, bool) or not math.isfinite(value):
                    raise ValueError("Invalid ammo drop multiplier")
                values[key] = max(UVHM_AMMO_DROP_MIN, min(UVHM_AMMO_DROP_MAX, round(value)))
            except (TypeError, ValueError, OverflowError):
                values[key] = UVHM_AMMO_DROP_DEFAULT
        elif key.endswith("_percent"):
            try:
                value = float(option.value)
                values[key] = max(GROWTH_MIN_PERCENT, min(GROWTH_MAX_PERCENT, round(value))) if math.isfinite(value) else GROWTH_DEFAULT_PERCENT
            except (TypeError, ValueError, OverflowError):
                values[key] = GROWTH_DEFAULT_PERCENT
        else:
            values[key] = option.value if isinstance(option.value, bool) else True
    values.update(_level_read_options())
    return values


def _settings() -> dict[str, Any]:
    return _DEFAULT_SETTINGS if _session_settings is None else _session_settings


_level_set_settings_provider(_settings)


def _freeze_session_settings() -> None:
    global _session_settings, _UVHM_SPECS
    if _session_settings is None:
        # Settings load before on_enable. Never undo native data or hot-swap
        # partially cached balance, rewards, prices or actors in this process.
        _session_settings = _read_menu_settings()
        _UVHM_SPECS = _uvhm_specs(
            health_multiplier=_session_settings["uvhm_enemy_health_multiplier"],
            ammo_drop_multiplier=_session_settings["ammo_drop_multiplier"],
        )

GLOBALS_PATH = "GD_Globals.General.Globals"
UVHM_PATH = "GD_Playthrough3Tuning.Balance.BalanceMod_PT3"
CHECK_INTERVAL = 2.0
REPAIR_LOG_INTERVAL = 30.0
EPSILON = 0.000001


_next_check = 0.0
_rules_suspended = True
_rules_active_context: tuple[int, int] | None = None
_rules_departing_context: tuple[int, int] | None = None
_applying = False
_verified: set[str] = set()
_pending: set[str] = set()
_errors: dict[str, str] = {}
_last_repair_notice: dict[str, float] = {}
_uvhm_signature: tuple[Any, ...] | None = None
_uvhm_audit_cursor = 0
UVHM_AUDIT_BATCH = 8


class AssetPending(Exception):
    """A referenced optional package has not loaded yet."""


def _property(owner: Any, name: str) -> Any:
    schema = getattr(owner, "_type", None)
    return (schema if schema is not None else owner.Class)._find_prop(name)


def _enum_value(prop: Any, name: str) -> Any:
    enum = prop.Enum
    if enum is None:
        raise ValueError(f"No native enum for {name}")
    return getattr(enum._as_py(), name)


def _matches(value: Any, spec: Any, prop: Any) -> bool:
    if isinstance(spec, dict):
        return _matches_fields(value, spec)
    if isinstance(spec, list):
        return len(value) == len(spec) and all(
            _matches(actual, expected, prop.Inner) for actual, expected in zip(value, spec)
        )
    if isinstance(spec, tuple):
        if spec[0] == "object":
            return value is not None and str(value._path_name()).casefold() == spec[2].casefold()
        if spec[0] == "enum":
            return int(value) == int(_enum_value(prop, spec[1]))
        raise ValueError("Unknown embedded reference")
    if isinstance(spec, float):
        return abs(float(value) - spec) <= EPSILON
    if spec == "" and isinstance(prop, ZNameProperty):
        # NAME_None round-trips as "None", even when assigned an empty string.
        return value is None or str(value).casefold() in ("", "none")
    return value == spec


def _matches_fields(owner: Any, spec: dict[str, Any]) -> bool:
    # Scalar equality and nested struct comparisons do not need reflection
    # metadata. Resolve schemas only for arrays, enums and FName semantics.
    return all(_matches(getattr(owner, name), expected,
                        None if isinstance(expected, (dict, int, float)) else _property(owner, name))
               for name, expected in spec.items())


def _materialize(prop: Any, spec: Any, template: Any, refs: dict[Any, Any]) -> Any:
    if isinstance(spec, dict):
        result = copy.copy(template) if template is not None else WrappedStruct(prop.Struct)
        for name, expected in spec.items():
            child = _property(result, name)
            setattr(result, name, _materialize(child, expected, getattr(result, name), refs))
        return result
    if isinstance(spec, list):
        current = list(template) if template is not None else []
        return [_materialize(prop.Inner, item, current[i] if i < len(current) else None, refs)
                for i, item in enumerate(spec)]
    if isinstance(spec, tuple):
        if spec[0] == "enum":
            return _enum_value(prop, spec[1])
        if spec[0] != "object":
            raise ValueError("Unknown embedded reference")
        if spec not in refs:
            try:
                obj = unrealsdk.find_object(spec[1], spec[2])
            except ValueError as exc:
                raise AssetPending(spec[2]) from exc
            if obj is None:
                raise AssetPending(spec[2])
            refs[spec] = obj
        return refs[spec]
    return spec


def _configure_patch(definition: Any, spec: dict[str, Any]) -> bool:
    refs: dict[Any, Any] = {}
    prepared = []
    for name, expected in spec.items():
        current = getattr(definition, name)
        prop = None if isinstance(expected, (dict, int, float)) else _property(definition, name)
        if not _matches(current, expected, prop):
            if prop is None:
                prop = _property(definition, name)  # Writes still require the native schema.
            value = _materialize(prop, expected, current, refs)
            prepared.append((name, value, expected, prop))
    # Resolve every reference before the first write, including sibling fields.
    for name, value, expected, prop in prepared:
        setattr(definition, name, value)
        if not _matches(getattr(definition, name), expected, prop):
            raise ValueError(f"Native data did not retain {name}")
    return bool(prepared)


def _aid(value: float) -> dict[str, Any]:
    return dict(BaseValueConstant=value, BaseValueAttribute=None,
                InitializationDefinition=None, BaseValueScaleConstant=1.0)


SLAG_SKILL_PATH = "GD_Amp.Skills.Skill_AmplifyDamage"
SLAG_STATUS_PATH = "GD_Amp.StatusEffect.Status_Amp"
SLAG_NPC_SKILL_NAME = "VHS_SlagNPCDebuff"
SLAG_NPC_SKILL_PATH = SLAG_SKILL_PATH + ":" + SLAG_NPC_SKILL_NAME
SLAG_PLAYER_FLAG_PATH = "GD_AI_Flags.Misc.Flag_IsPlayer"
SLAG_GUARD_NAME = "VHS_SlagNPCOnly"
SLAG_GUARD_CLASS = "GearboxFramework.FlagExpressionEvaluator"
_slag_guard_owner: tuple[int, int] | None = None
SLAG_AUDIO_STOP_PATH = "Ake_FX_Global.Ak_Stop_FX_Elemental_Slag_StatusEffect_lp"
_slag_audio_type: int | None = None
_slag_audio_pending: tuple[int, int, int] | None = None
_slag_audio_respawn_pending = False
_slag_audio_death_contexts: list[tuple[int, int, int] | None] = []
_slag_audio_check_at = 0.0
_slag_audio_notice_context: tuple[int, int, int] | None = None


def _arm_local_slag_audio_cleanup(component: Any, *, enemy_status_ended: bool = False) -> None:
    global _slag_audio_pending, _slag_audio_respawn_pending, _slag_audio_check_at
    if _rules_suspended or _slag_audio_respawn_pending or not _settings()["uvhm_rebalance"]:
        return  # Preserve the dead-pawn marker until the replacement pawn is ready.
    controller = get_pc()
    if controller is None or controller.bDeleteMe:
        return
    pawn = controller.Pawn
    if pawn is None or pawn.bDeleteMe:
        return
    owner = component.Owner
    if owner is None or getattr(owner, "bDeleteMe", False):
        return
    if owner != pawn and not enemy_status_ended:
        return
    world = controller.WorldInfo
    if world is None or world.bDeleteMe:
        return
    _slag_audio_pending = (controller._get_address(), pawn._get_address(), world._get_address())
    _slag_audio_respawn_pending = False
    # Audio startup can precede insertion into ActiveStatusEffects in this call.
    _slag_audio_check_at = time.monotonic() + 0.25


@hook("WillowGame.StatusEffectsComponent:StartEffectSound", Type.POST)
def observe_local_slag_sound(component: Any, args: Any, _ret: Any, _func: Any) -> None:
    if _slag_audio_type is not None and int(args.StatusEffectType) == _slag_audio_type:
        _arm_local_slag_audio_cleanup(component)


@hook("WillowGame.StatusEffectsComponent:OnStatusEffectEnd", Type.POST)
def observe_local_slag_end(component: Any, args: Any, _ret: Any, _func: Any) -> None:
    if _slag_audio_type is None:
        return
    definition = args.ASE.StatusEffectDefinition
    if definition is not None and int(definition.StatusEffectType) == _slag_audio_type:
        # The loop can remain on the local audio owner after slag ends on an enemy.
        _arm_local_slag_audio_cleanup(component, enemy_status_ended=True)


@hook("WillowGame.WillowPlayerPawn:Died", Type.PRE)
def prepare_slag_audio_after_death(pawn: Any, _args: Any, _ret: Any, _func: Any) -> None:
    candidate = None
    if not _rules_suspended and _settings()["uvhm_rebalance"] and _slag_audio_type is not None:
        controller = get_pc()
        if controller is not None and not controller.bDeleteMe and controller.Pawn == pawn:
            world = controller.WorldInfo
            if world is not None and not world.bDeleteMe:
                candidate = (controller._get_address(), pawn._get_address(), world._get_address())
    # POST must not dereference a pawn that Died may already have detached.
    _slag_audio_death_contexts.append(candidate)


@hook("WillowGame.WillowPlayerPawn:Died", Type.POST_UNCONDITIONAL)
def arm_slag_audio_after_death(_pawn: Any, _args: Any, ret: Any, _func: Any) -> None:
    global _slag_audio_pending, _slag_audio_respawn_pending, _slag_audio_check_at
    if not _slag_audio_death_contexts:
        return
    candidate = _slag_audio_death_contexts.pop()
    if ret is True and candidate is not None and not _rules_suspended:
        _slag_audio_pending = candidate
        _slag_audio_respawn_pending = True
        _slag_audio_check_at = time.monotonic() + 0.25


SLAG_DURATION_SECONDS = 7.0
SLAG_MOVEMENT_REDUCTION = 0.30
SLAG_FIRE_RATE_REDUCTION = 0.25


def _finish_local_slag_audio(controller: Any, now: float) -> None:
    global _slag_audio_pending, _slag_audio_respawn_pending, _slag_audio_notice_context
    pending = _slag_audio_pending
    if _rules_suspended or pending is None or now < _slag_audio_check_at or controller is None:
        return  # No status event armed: no native queries or audio work.
    if not _settings()["uvhm_rebalance"] or _slag_audio_type is None:
        _slag_audio_pending = None
        _slag_audio_respawn_pending = False
        return
    try:
        if controller.bDeleteMe or controller._get_address() != pending[0]:
            _slag_audio_pending = None
            _slag_audio_respawn_pending = False
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if world is None or world.bDeleteMe or world._get_address() != pending[2]:
            _slag_audio_pending = None
            _slag_audio_respawn_pending = False
            return
        if pawn is None or pawn.bDeleteMe:
            if not _slag_audio_respawn_pending:
                _slag_audio_pending = None
            return
        pawn_address = pawn._get_address()
        if _slag_audio_respawn_pending:
            if pawn_address == pending[1]:
                return  # Wait for the new pawn; old status may be torn down without End.
        elif pawn_address != pending[1]:
            _slag_audio_pending = None
            return
        component = pawn.GetStatusEffectsComponent()
        if component is None:
            return
        # Check native type state, including other definitions using slag and
        # replicated status types; never mute an actually active slag effect.
        if (component.IsAffectedWithStatusEffectType(_slag_audio_type)
                or _slag_audio_type in component.GetActiveStatusEffectTypes()):
            return
        try:
            stop = unrealsdk.find_object("AkEvent", SLAG_AUDIO_STOP_PATH)
        except ValueError:
            return  # Never load an audio bank just to perform cleanup.
        if stop is None:
            return
        # End native per-type sound bookkeeping, then post the exact local
        # controller event that stopped the confirmed orphan in the live test.
        if not _slag_audio_respawn_pending:
            component.StopEffectSound(_slag_audio_type, True)
        controller.PostAkEvent(stop, True, False)
        _slag_audio_pending = None
        was_respawn = _slag_audio_respawn_pending
        _slag_audio_respawn_pending = False
        _errors.pop("Local slag audio cleanup", None)
        if _slag_audio_notice_context != pending:
            reason = "respawn" if was_respawn else "status expiration"
            unrealsdk.logging.info("[EndgameQoLRebalance] Local slag audio ended after " + reason)
            _slag_audio_notice_context = pending
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = str(exc)
        if _errors.get("Local slag audio cleanup") != message:
            _errors["Local slag audio cleanup"] = message
            unrealsdk.logging.error("[EndgameQoLRebalance] Could not end local slag audio: " + message)


def _slag_skill_effect(attribute: str, value: float) -> dict[str, Any]:
    """Build a native status-effect modifier."""
    return {
        "AttributeToModify": ("object", "AttributeDefinition", attribute),
        "bIncludeDuelingTargets": False, "bIncludeSelfAsTarget": False,
        "bOnlyEffectTargetsInRange": False, "bExcludeNonPlayerCharacters": False,
        "EffectTarget": ("enum", "TARGET_Self"), "TargetInstanceDataName": "",
        "TargetCriteria": ("enum", "CRITERIA_None"), "ModifierType": ("enum", "MT_Scale"),
        "BaseModifierValue": _aid(value), "GradeToStartApplyingEffect": 1,
        "PerGradeUpgradeInterval": 1, "PerGradeUpgrade": _aid(0.0), "BonusUpgradeList": [],
    }


def _slag_specs() -> tuple[Any, ...]:
    neutral_damage = {field: _aid(1.0) for field in (
        "FleshDamageModifier", "ArmorDamageModifier", "ShieldDamageModifier",
    )}
    text = ("[slag]Slag[-slag] lasts 7 seconds, reduces [skill]Movement Speed[-skill] by 30% "
            "and [skill]Fire Rate[-skill] by 25%. It does not amplify damage.")
    return (
        ("WillowDamageTypeDefinition", "GD_Amp.DamageType.DmgType_Amp_Impact", neutral_damage),
        ("WillowDamageTypeDefinition", "GD_Amp.DamageType.DmgType_Amp_Status", neutral_damage),
        ("StatusEffectDefinition", SLAG_STATUS_PATH, {
            "BaseDuration": _aid(SLAG_DURATION_SECONDS),
            "TargetStatusEffectDurationModifier": _aid(0.0),
            # Preserve native status processing, including expiry/audio cleanup.
            # Native slag uses this flag even though it deals no periodic damage.
            "bDoesDamageOverTime": True,
        }),
        ("SkillDefinition", "GD_Amp.Skills.Skill_AmplifyDamage", {
            "SkillEffectDefinitions": [
                _slag_skill_effect("D_Attributes.DamageSourceModifiers.ReceivedAmplifyDamageModifier", 0.0),
                _slag_skill_effect("D_Attributes.DamageTypeModifers.AmpImpactDamageModifier", 0.0),
            ],
        }),
        ("Behavior_ActivateSkill", "GD_Amp.StatusEffect.Status_Amp:Behavior_ActivateSkill_0", {
            "bNoSkillStacking": False,  # Native status/instigator bookkeeping.
        }),
        ("AttributePresentationDefinition",
         "GD_Amp.DamageType.DmgType_Amp_Impact:AttributePresentationDefinition_1", {"Description": text}),
    )


def _configure_slag_skill(definition: Any, fields: dict[str, Any]) -> bool:
    """Guard only the private, silent NPC skill; never the native visual skill."""
    global _slag_guard_owner
    # TARGET_Self is the slag recipient, which may be a player. Its include-self
    # checkbox does not exclude players. Gate the skill in the native engine,
    # including C++ activations that bypass Python hooks.
    try:
        flag = unrealsdk.find_object("FlagDefinition", SLAG_PLAYER_FLAG_PATH)
    except ValueError as exc:
        raise AssetPending(SLAG_PLAYER_FLAG_PATH) from exc
    if flag is None:
        raise AssetPending(SLAG_PLAYER_FLAG_PATH)
    # The helper is already a subobject (Asset:Helper). Nested children use
    # a dot, Asset:Helper.Guard; another colon fails native path validation.
    guard_path = SLAG_NPC_SKILL_PATH + "." + SLAG_GUARD_NAME
    try:
        evaluator = unrealsdk.find_object(SLAG_GUARD_CLASS, guard_path)
    except ValueError:
        evaluator = None
    if evaluator is None:
        evaluator = unrealsdk.construct_object(
            SLAG_GUARD_CLASS, definition, SLAG_GUARD_NAME, flags=int(ObjectFlags.KEEP_ALIVE),
        )
    if evaluator is None:
        raise ValueError("Could not create the native slag recipient guard")
    # Validate against the actual destination property, not just a short class
    # name. Dynamic evaluators must survive collection while referenced by a
    # native definition across map/character reloads.
    expected_class = _property(definition, "SkillConstraints").Inner.Struct._find_prop("Evaluator").PropertyClass
    if not evaluator.Class._inherits(expected_class):
        raise ValueError("Slag recipient guard is incompatible with the native ExpressionEvaluator property")
    if not int(evaluator.ObjectFlags) & int(ObjectFlags.KEEP_ALIVE):
        evaluator.ObjectFlags = int(evaluator.ObjectFlags) | int(ObjectFlags.KEEP_ALIVE)
    changed = _configure_patch(evaluator, {
        "FlagChain": [{"FlagEvalType": ("enum", "FLAG_IsFalse"),
                       "FlagDefinition": ("object", "FlagDefinition", SLAG_PLAYER_FLAG_PATH),
                       "TimeSeconds": _aid(0.0)}],
        "FlagChainOperator": ("enum", "CEOP_And"),
    })
    guard = {
        "bApplyConstraintOnActivatation": True,
        "bApplyConstraintWhileActive": True,
        "bApplyConstraintWhilePaused": True,
        "OnFailure": ("enum", "SKILL_Deactivated"),
        "Evaluator": ("object", SLAG_GUARD_CLASS, guard_path),
        "EvaluatorDefinitions": [],
    }
    array = definition.SkillConstraints
    owner = (definition._get_address(), evaluator._get_address())
    if owner != _slag_guard_owner or not len(array):
        # Native constraint pointers may already be expired after loading. Never
        # read their Evaluator or call _path_name on it. Preserve detached copies
        # of unrelated records and attach only our known, rooted object.
        retained = [copy.copy(item) for item in array]
        constraint = _materialize(_property(definition, "SkillConstraints").Inner,
                                  guard, None, {guard["Evaluator"]: evaluator})
        # This is a newly created local record, not a pointer read from the old array.
        if not _matches_fields(constraint, guard):
            raise ValueError("Could not prepare the native slag recipient guard")
        definition.SkillConstraints = [*retained, constraint]
        current = definition.SkillConstraints
        if len(current) != len(retained) + 1:
            raise ValueError("Native slag recipient guard did not remain attached")
        # An equivalent native array may be reallocated. Its address/count is
        # not an ownership token: using it here appended a duplicate guard on
        # every relocation. Both owners are rooted; attach once per definition.
        _slag_guard_owner = owner
        unrealsdk.logging.info(f"[EndgameQoLRebalance] Slag recipient guard attached: constraints={len(current)}")
        changed = True
    return _configure_patch(definition, fields) or changed


def _private_definition(cls: str, outer: Any, name: str, template: Any = None) -> Any:
    """Resolve rooted definitions afresh; never cache a UObject wrapper in Python."""
    path = str(outer._path_name()) + ":" + name
    try:
        obj = unrealsdk.find_object(cls, path)
    except ValueError:
        obj = None
    if obj is None:
        obj = unrealsdk.construct_object(
            cls, outer, name, flags=int(ObjectFlags.KEEP_ALIVE), template_obj=template,
        )
    if obj is None:
        raise ValueError("Could not create " + path)
    if not int(obj.ObjectFlags) & int(ObjectFlags.KEEP_ALIVE):
        obj.ObjectFlags = int(obj.ObjectFlags) | int(ObjectFlags.KEEP_ALIVE)
    return obj


def _configure_slag_status(definition: Any, fields: dict[str, Any]) -> bool:
    """Leave native audiovisual callbacks intact and pair a silent NPC debuff."""
    global _slag_audio_type
    try:
        native_skill = unrealsdk.find_object("SkillDefinition", SLAG_SKILL_PATH)
    except ValueError as exc:
        raise AssetPending(SLAG_SKILL_PATH) from exc
    if native_skill is None:
        raise AssetPending(SLAG_SKILL_PATH)
    skill = _private_definition("SkillDefinition", native_skill, SLAG_NPC_SKILL_NAME, native_skill)
    # A player rejection must not dispatch the native OnDeactivated graph: that
    # graph plays Slag_Status_End, including a corrosive-dissolve sound. Repeated
    # rejected activations/constraint checks must remain silent.
    movement = -SLAG_MOVEMENT_REDUCTION / (1.0 - SLAG_MOVEMENT_REDUCTION)
    interval = SLAG_FIRE_RATE_REDUCTION / (1.0 - SLAG_FIRE_RATE_REDUCTION)
    changed = _configure_slag_skill(skill, {
        "BehaviorProviderDefinition": None,
        "TrackedSkillType": ("enum", "TRACKEDSKILL_Untracked"),
        "DurationType": ("enum", "DURATION_Infinite"),
        "SkillEffectDefinitions": [
            _slag_skill_effect("D_Attributes.GameplayAttributes.FootSpeed", movement),
            _slag_skill_effect("D_Attributes.Weapon.WeaponFireInterval", interval),
        ],
    })
    activate = _private_definition("Behavior_ActivateSkill", definition, "VHS_ActivateSlagNPCDebuff")
    deactivate = _private_definition("Behavior_DeactivateSkill", definition, "VHS_DeactivateSlagNPCDebuff")
    reference = ("object", "SkillDefinition", SLAG_NPC_SKILL_PATH)
    changed = _configure_patch(activate, {
        "SkillToActivate": reference, "bNoSkillStacking": True,
    }) or changed
    changed = _configure_patch(deactivate, {
        "SkillToDeactivate": reference, "bIgnoreSkillInstigator": True,
    }) or changed
    # Keep all pre-existing application/end behaviors in their original order,
    # including the native local-player audio start and stop. Append our pair
    # once and repair an externally removed callback without following pointers.
    updated = dict(fields)
    for field, behavior in (("OnApplication", activate), ("OnDurationEnd", deactivate)):
        current = list(getattr(definition, field))
        if behavior not in current:
            updated[field] = [*current, behavior]
    changed = _configure_patch(definition, updated) or changed
    _slag_audio_type = int(definition.StatusEffectType)
    return changed


# Own global slag policy. It is applied whenever the UVHM category is enabled,
# without testing playthrough; native status application/expiry owns its lifetime.
UVHM_PATCHES = _slag_specs()


def _uvhm_health_fields(multiplier: float) -> dict[str, float]:
    """One durability choice for health/shields; no conversion between resource pools."""
    badass = multiplier * UVHM_BADASS_HEALTH_RATIO
    return {
        "EnemyHealthMultiplier": multiplier,
        "BadassEnemyHealthMultiplier": badass,
        "EnemyShieldStrengthMultiplier": multiplier,
        "BadassEnemyShieldStrengthMultiplier": badass,
    }


def _uvhm_player_support_fields(ammo_drop_multiplier: int) -> dict[str, Any]:
    """Leave native ammo-drop settings untouched when the slider is at 1."""
    fields = {"PlayerVehicleWeaponDamageMultiplier": UVHM_PLAYER_VEHICLE_DAMAGE_MULTIPLIER}
    if ammo_drop_multiplier != 1:
        fields["AmmoDropsPerPlayerMultiplier"] = _aid(float(ammo_drop_multiplier))
    return fields


def _uvhm_status_damage_effects() -> list[dict[str, Any]]:
    """Build own UVHM player effects; these use native bonus-stack semantics."""
    effects = []
    for element, setting in UVHM_STATUS_DAMAGE_MULTIPLIERS.items():
        factor = float(setting)
        if not math.isfinite(factor) or factor < 0.0:
            raise ValueError(f"Invalid UVHM {element} status-damage factor")
        effects.append({
            "AttributeToModify": (
                "object", "AttributeDefinition",
                f"D_Attributes.DamageTypeModifers.Instigated{element}StatusDamageModifier",
            ),
            "ModifierType": ("enum", "MT_Scale"),
            "BaseModifierValue": _aid(factor - 1.0),
        })
    return effects


UVHM_PASSIVE_REGEN_ATTRIBUTE = "D_Attributes.HealthResourcePool.HealthPassiveRegenerationRate"


def _uvhm_enemy_effects_without_regeneration(effects: list[Any]) -> list[Any]:
    """Filter only passive health regeneration, preserving unrelated enemy effects."""
    result = []
    for effect in effects:
        if isinstance(effect, dict):
            attribute = effect.get("AttributeToModify")
            path = (str(attribute[2]) if isinstance(attribute, tuple) and len(attribute) == 3
                    and attribute[0] == "object" else "")
        else:
            attribute = effect.AttributeToModify
            path = "" if attribute is None else str(attribute._path_name())
        if path.casefold() != UVHM_PASSIVE_REGEN_ATTRIBUTE.casefold():
            result.append(effect)
    return result


def _floor_key(keys: Any, level: int) -> int:
    return max((key for key in keys if key <= level), default=min(keys))



def _uvhm_common_loot_fields(level: int) -> dict[str, Any]:
    """Own UVHM common-item weights; preserve native values below level 50."""
    if level < UVHM_COMMON_LOOT_START_LEVEL:
        return {}
    weight = (UVHM_COMMON_LOOT_EARLY_WEIGHT if level < UVHM_COMMON_LOOT_LATE_LEVEL
              else UVHM_COMMON_LOOT_LATE_WEIGHT)
    return {"GearDrops_CommonWeightModifier_PT3_BaseValueOverride": _aid(weight)}


def _uvhm_chest_loot_fields(level: int) -> dict[str, Any]:
    weights = dict(UVHM_CHEST_LOOT_WEIGHTS)
    return {"ChestItemPool_Weight_2_Uncommon_PT3_Multiplier": _aid(weights[_floor_key(weights, level)])}


def _uvhm_specs(
    *, health_multiplier: float = UVHM_HEALTH_DEFAULT,
    ammo_drop_multiplier: int = UVHM_AMMO_DROP_DEFAULT,
) -> dict[int, dict[str, Any]]:
    result = {}
    levels = sorted({level for level, _ in UVHM_CHEST_LOOT_WEIGHTS}
                    | {UVHM_COMMON_LOOT_START_LEVEL, UVHM_COMMON_LOOT_LATE_LEVEL})
    for level in levels:
        fields = {
            "MinEffectiveLevel": level,
            "AttributeEffectsForSpawnedEnemies": _uvhm_enemy_effects_without_regeneration([]),
            "AmplifiedDamageMultiplier": 1.0,
        }
        fields.update(_uvhm_health_fields(health_multiplier))
        fields.update(_uvhm_player_support_fields(ammo_drop_multiplier))
        fields["AttributeEffectsForPlayers"] = _uvhm_status_damage_effects()
        fields.update(_uvhm_common_loot_fields(level))
        fields.update(_uvhm_chest_loot_fields(level))
        result[level] = fields
    return result


_UVHM_SPECS = _uvhm_specs()  # Python data only, no native object references.




def _balance_signature(definition: Any) -> tuple[Any, ...]:
    rows = definition.BalanceModifiers
    # Do not use the identity/address of an element wrapper: temporary views
    # must not trigger a full traversal at every maintenance check.
    return (definition._get_address(), len(rows), tuple(int(row.MinEffectiveLevel) for row in rows))


def _uvhm_player_effect_is_managed(effect: Any, wanted: list[dict[str, Any]]) -> bool:
    attribute = effect.AttributeToModify
    if attribute is None:
        return False
    path = str(attribute._path_name()).casefold()
    return any(path == spec["AttributeToModify"][2].casefold() for spec in wanted)


def _uvhm_tier_matches(row: Any, spec: dict[str, Any]) -> bool:
    fields = {key: value for key, value in spec.items()
              if key not in ("AttributeEffectsForPlayers", "AttributeEffectsForSpawnedEnemies")}
    if not _matches_fields(row, fields):
        return False
    enemies = list(row.AttributeEffectsForSpawnedEnemies)
    if len(_uvhm_enemy_effects_without_regeneration(enemies)) != len(enemies):
        return False
    wanted = spec["AttributeEffectsForPlayers"]
    managed = [effect for effect in row.AttributeEffectsForPlayers
               if _uvhm_player_effect_is_managed(effect, wanted)]
    return len(managed) == len(wanted) and all(
        _matches_fields(effect, setting) for effect, setting in zip(managed, wanted)
    )


def _materialize_uvhm_tier(prop: Any, spec: dict[str, Any], template: Any, refs: dict[Any, Any]) -> Any:
    fields = {key: value for key, value in spec.items()
              if key not in ("AttributeEffectsForPlayers", "AttributeEffectsForSpawnedEnemies")}
    result = _materialize(prop, fields, template, refs)
    enemies = list(result.AttributeEffectsForSpawnedEnemies)
    retained_enemies = _uvhm_enemy_effects_without_regeneration(enemies)
    if len(retained_enemies) != len(enemies):
        result.AttributeEffectsForSpawnedEnemies = [copy.copy(effect) for effect in retained_enemies]
    wanted = spec["AttributeEffectsForPlayers"]
    # Preserve unrelated native/other-mod effects without knowing their paths
    # or changing their values. No references escape this maintenance call.
    retained = [copy.copy(effect) for effect in result.AttributeEffectsForPlayers
                if not _uvhm_player_effect_is_managed(effect, wanted)]
    effect_prop = _property(result, "AttributeEffectsForPlayers").Inner
    result.AttributeEffectsForPlayers = retained + [
        _materialize(effect_prop, setting, None, refs) for setting in wanted
    ]
    return result


def _configure_full_uvhm(definition: Any, *, force: bool = False) -> bool:
    global _uvhm_signature, _uvhm_audit_cursor
    rows = list(definition.BalanceModifiers)
    existing = {int(row.MinEffectiveLevel): row for row in rows}
    if len(existing) != len(rows):
        raise ValueError("Duplicate UVHM level thresholds require review")
    # Preserve all native/other-mod thresholds and add only our policy boundaries.
    # Unmanaged fields inherit the nearest live native tier.
    levels = sorted(set(existing) | set(_UVHM_SPECS))
    specs = [dict(_UVHM_SPECS[_floor_key(_UVHM_SPECS, level)], MinEffectiveLevel=level)
             for level in levels]
    same_shape = [int(row.MinEffectiveLevel) for row in rows] == levels
    signature = _balance_signature(definition)
    audit_all = force or not same_shape or _uvhm_signature != signature
    indices = range(len(rows)) if audit_all else [
        (i + _uvhm_audit_cursor) % len(rows) for i in range(min(UVHM_AUDIT_BATCH, len(rows)))
    ]
    if not audit_all:
        indices = set(indices) | {i for i, level in enumerate(levels) if level in (1, 50, 61, 73, 80)} | {len(rows) - 1}
    needs_write = not same_shape or any(not _uvhm_tier_matches(rows[i], specs[i]) for i in indices)
    if needs_write:
        inner = _property(definition, "BalanceModifiers").Inner
        refs: dict[Any, Any] = {}
        updated = []
        for level, spec in zip(levels, specs):
            template = existing[_floor_key(existing, level)] if existing else None
            updated.append(_materialize_uvhm_tier(inner, spec, template, refs))
        definition.BalanceModifiers = updated
        actual = definition.BalanceModifiers
        if len(actual) != len(specs) or any(not _uvhm_tier_matches(row, spec) for row, spec in zip(actual, specs)):
            raise ValueError("Native data did not retain the full UVHM preset")
    _uvhm_signature = _balance_signature(definition) if needs_write else signature
    _uvhm_audit_cursor = (_uvhm_audit_cursor + UVHM_AUDIT_BATCH) % len(levels)
    return needs_write


def _apply_full_rebalance(now: float, *, force: bool) -> None:
    if not _settings()["uvhm_rebalance"]:
        return
    for cls, path, fields in UVHM_PATCHES:
        configure = _configure_slag_status if path == SLAG_STATUS_PATH else _configure_patch
        _check_target("UVHM " + path, cls, path,
                      lambda obj, spec=fields, apply=configure: apply(obj, spec), now)
    _check_target("UVHM balance policy", "BalanceModifierDefinition", UVHM_PATH,
                  lambda obj: _configure_full_uvhm(obj, force=force), now)


# Fields neutralized in the loaded level-difference tables.
LEVEL_GAP_NEUTRAL_FIELDS = {
    "PlayerDamageScaleByLevelDifference": ("LowerLevelAttackerDmgScale",),
    "AIDamageScaleByLevelDifference": ("HigherLevelAttackerDmgScale",),
    "StatusEffectChanceScales": ("HigherLevelChanceScale", "LowerLevelChanceScale"),
}
LEVEL_GAP_TABLE_OPTIONS = {
    "PlayerDamageScaleByLevelDifference": "higher_level_resistance",
    "AIDamageScaleByLevelDifference": "higher_level_damage",
    "StatusEffectChanceScales": "higher_level_status_chance",
}


def _level_gap_edit_plan(owner: Any, *, include_player_damage: bool) -> dict[str, list[Any]]:
    """Prepare detached edits using the live table's own thresholds and metadata."""
    plan = {}
    for name, neutral_fields in LEVEL_GAP_NEUTRAL_FIELDS.items():
        if ((name == "PlayerDamageScaleByLevelDifference" and not include_player_damage)
                or not _settings()[LEVEL_GAP_TABLE_OPTIONS[name]]):
            continue
        original = list(getattr(owner, name))
        dirty = [i for i, row in enumerate(original) if any(
            not math.isclose(float(getattr(row, field)), 1.0, rel_tol=0.0, abs_tol=EPSILON)
            for field in neutral_fields
        )]
        if not dirty:
            continue
        replacement = [copy.copy(row) for row in original]
        for index in dirty:
            for field in neutral_fields:
                setattr(replacement[index], field, 1.0)
        plan[name] = replacement
    return plan


def _level_gap_is_neutral(owner: Any, *, include_player_damage: bool) -> bool:
    for name, fields in LEVEL_GAP_NEUTRAL_FIELDS.items():
        if ((name == "PlayerDamageScaleByLevelDifference" and not include_player_damage)
                or not _settings()[LEVEL_GAP_TABLE_OPTIONS[name]]):
            continue
        if any(not math.isclose(float(getattr(row, field)), 1.0, rel_tol=0.0, abs_tol=EPSILON)
               for row in getattr(owner, name) for field in fields):
            return False
    return True


def _configure_global_level_policy(definition: Any) -> bool:
    # Resolve/prepare all three tables before the first owning-array write.
    plan = _level_gap_edit_plan(definition, include_player_damage=True)
    if not plan:
        return False  # Every requested factor was already checked in this callback.
    for name, rows in plan.items():
        setattr(definition, name, rows)
    if not _level_gap_is_neutral(definition, include_player_damage=True):
        raise ValueError("Global level-difference penalties did not remain neutral")
    return bool(plan)


def _configure_uvhm_level_policy(definition: Any) -> bool:
    native_tiers = list(definition.BalanceModifiers)
    plans = [(index, _level_gap_edit_plan(tier, include_player_damage=False))
             for index, tier in enumerate(native_tiers)]
    changed = [(index, plan) for index, plan in plans if plan]
    if not changed:
        return False  # Avoid re-reading unchanged native tables a second time.
    # One parent-array assignment, with no cached actor or fixed OP index.
    updated = [copy.copy(tier) for tier in native_tiers]
    for index, plan in changed:
        for name, rows in plan.items():
            setattr(updated[index], name, rows)
    definition.BalanceModifiers = updated
    if not all(_level_gap_is_neutral(tier, include_player_damage=False)
               for tier in definition.BalanceModifiers):
        raise ValueError("UVHM level-difference overrides did not remain neutral")
    return bool(changed)


def _invalidate_target(label: str) -> None:
    global _uvhm_signature
    _verified.discard(label)
    if label == "UVHM balance policy":
        _uvhm_signature = None  # Recovery must audit the complete preset again.


def _check_target(label: str, class_name: str, path: str, configure: Any, now: float) -> None:
    try:
        try:
            definition = unrealsdk.find_object(class_name, path)
        except ValueError:
            definition = None
        if definition is None:
            _invalidate_target(label)
            _errors.pop(label, None)
            if label not in _pending:
                _pending.add(label)
                unrealsdk.logging.info(f"[EndgameQoLRebalance] {label} pending: asset not loaded yet")
            return
        changed = configure(definition)
    except AssetPending as exc:
        _invalidate_target(label)
        _errors.pop(label, None)
        if label not in _pending:
            _pending.add(label)
            unrealsdk.logging.info(f"[EndgameQoLRebalance] {label} pending: {exc}")
        return
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _invalidate_target(label)
        _pending.discard(label)
        message = str(exc)
        if _errors.get(label) != message:
            _errors[label] = message
            unrealsdk.logging.error(f"[EndgameQoLRebalance] Could not verify {label}: {message}")
        return
    _pending.discard(label)
    recovered = _errors.pop(label, None) is not None
    if label not in _verified or recovered:
        _verified.add(label)
        _last_repair_notice[label] = now
        unrealsdk.logging.info(f"[EndgameQoLRebalance] {label} verified: native values confirmed")
    elif changed and now - _last_repair_notice.get(label, float("-inf")) >= REPAIR_LOG_INTERVAL:
        _last_repair_notice[label] = now
        unrealsdk.logging.info(f"[EndgameQoLRebalance] {label} restored after balance data changed")


def _configure_growth(resolver: Any, percent: int) -> bool:
    """Set the native per-level factor from a user-selected percentage."""
    if (isinstance(percent, bool) or not isinstance(percent, (int, float))
            or not math.isfinite(percent)
            or not GROWTH_MIN_PERCENT <= percent <= GROWTH_MAX_PERCENT):
        raise ValueError("Growth percentage must be between 1 and 20")
    # Absolute factor: never multiply the already edited value or touch actors.
    return _configure_patch(resolver, {"ConstantValue": 1.0 + percent / 100.0})


def _apply_growth_rules(now: float) -> None:
    settings = _settings()
    for label, path, percent in (
        ("Game growth per level", GAME_SCALER_PATH, settings["game_growth_percent"]),
        ("Money growth per level", MONEY_SCALER_PATH, settings["money_growth_percent"]),
    ):
        _check_target(label, "ConstantAttributeValueResolver", path,
                      lambda resolver, rate=percent: _configure_growth(resolver, rate), now)


# Native base reserve and gain per purchased SDU are independent quantities.
# Absolute targets avoid compounding edited values when assets are checked again.
AMMO_CAPACITY_RULES = (
    ("Sniper", "D_Resourcepools.AmmoPools.Ammo_Sniper_Rifle_Pool", 48.0 * 1.5,
     "GD_BlackMarket.Misc.Att_SniperAmmoPerUpgrade:ConstantAttributeValueResolver_0", 12.0 * 2.0),
    ("Shotgun", "D_Resourcepools.AmmoPools.Ammo_Combat_Shotgun_Pool", 140.0,
     "GD_BlackMarket.Misc.Att_ShotgunAmmoPerUpgrade:ConstantAttributeValueResolver_0", 20.0 * 1.5),
)


def _apply_ammo_capacity(now: float) -> None:
    if not _settings()["ammo_capacity"]:
        return
    for label, pool_path, base, upgrade_path, per_upgrade in AMMO_CAPACITY_RULES:
        _check_target(label + " base ammo capacity", "ResourcePoolDefinition", pool_path,
                      lambda pool, value=base: _configure_patch(pool, {
                          "BaseMaxValue": {"BaseValueConstant": value},
                      }), now)
        _check_target(label + " ammo per SDU", "ConstantAttributeValueResolver", upgrade_path,
                      lambda resolver, value=per_upgrade: _configure_patch(resolver, {
                          "ConstantValue": value,
                      }), now)


ERIDIUM_LIMIT = 1000


def _eridium_cap_rva(executable: bytes) -> tuple[int, int]:
    """Locate the native currency cap in a PE image by its neighboring values."""
    cash, seraph = 99_999_999, 999
    candidates = ((500, struct.pack("<III", cash, 500, seraph)),
                  (999, struct.pack("<III", cash, 999, seraph)),
                  (ERIDIUM_LIMIT, struct.pack("<III", cash, ERIDIUM_LIMIT, seraph)))
    found = [(value, executable.find(pattern)) for value, pattern in candidates
             if executable.count(pattern) == 1]
    if len(found) != 1:
        raise ValueError("Unsupported or ambiguous executable currency-cap layout")
    current, offset = found[0]
    if executable[:2] != b"MZ" or len(executable) < 0x40:
        raise ValueError("Invalid game executable header")
    pe = struct.unpack_from("<I", executable, 0x3C)[0]
    if pe + 24 >= len(executable) or executable[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Invalid PE header")
    sections, optional_size = struct.unpack_from("<HH", executable, pe + 6)[0], struct.unpack_from("<H", executable, pe + 20)[0]
    optional = pe + 24
    if struct.unpack_from("<H", executable, optional)[0] != 0x10B:
        raise ValueError("Expected the 32-bit BL2 executable")
    image_size = struct.unpack_from("<I", executable, optional + 56)[0]
    target = offset + 4
    for index in range(sections):
        header = optional + optional_size + 40 * index
        if header + 40 > len(executable):
            break
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", executable, header + 8)
        characteristics = struct.unpack_from("<I", executable, header + 36)[0]
        if (raw_offset <= target and target + 4 <= raw_offset + raw_size
                and not characteristics & 0x20000000):
            rva = virtual_address + target - raw_offset
            if rva + 4 <= image_size and target - raw_offset + 4 <= virtual_size:
                return rva, current
    raise ValueError("Currency cap was not found in a non-executable PE section")


def _apply_eridium_capacity() -> None:
    """Patch only this process's validated currency cap; never edit the EXE."""
    if not _settings()["eridium_capacity"]:
        return
    try:
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        kernel.GetModuleHandleW.restype = ctypes.c_void_p
        kernel.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
        kernel.GetModuleFileNameW.restype = ctypes.c_uint32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                             ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        kernel.ReadProcessMemory.restype = ctypes.c_int
        kernel.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32,
                                          ctypes.POINTER(ctypes.c_uint32)]
        kernel.VirtualProtect.restype = ctypes.c_int
        kernel.WriteProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                              ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        kernel.WriteProcessMemory.restype = ctypes.c_int
        base = kernel.GetModuleHandleW(None)
        if not base:
            raise ValueError("Could not locate the game executable module")
        path = ctypes.create_unicode_buffer(32768)
        length = kernel.GetModuleFileNameW(base, path, len(path))
        if not 0 < length < len(path):
            raise ValueError("Could not locate the game executable file")
        if path.value.replace("/", "\\").rsplit("\\", 1)[-1].lower() != "borderlands2.exe":
            raise ValueError("Eridium patch is restricted to Borderlands2.exe")
        with open(path.value, "rb") as stream:
            rva, expected = _eridium_cap_rva(stream.read())
        address = base + rva
        process = kernel.GetCurrentProcess()
        observed = ctypes.c_uint32()
        read = ctypes.c_size_t()
        if not kernel.ReadProcessMemory(process, address, ctypes.byref(observed), 4, ctypes.byref(read)) or read.value != 4:
            raise ValueError("Could not read the executable currency cap")
        if observed.value == ERIDIUM_LIMIT:
            return
        if observed.value != expected or expected not in (500, 999):
            raise ValueError("Loaded currency cap differs from the validated executable")
        original_protection = ctypes.c_uint32()
        if not kernel.VirtualProtect(address, 4, 0x04, ctypes.byref(original_protection)):
            raise ValueError("Could not unlock the native currency-cap field")
        try:
            desired = ctypes.c_uint32(ERIDIUM_LIMIT)
            written = ctypes.c_size_t()
            if not kernel.WriteProcessMemory(process, address, ctypes.byref(desired), 4, ctypes.byref(written)) or written.value != 4:
                raise ValueError("Could not update the native currency cap")
        finally:
            restored = ctypes.c_uint32()
            if not kernel.VirtualProtect(address, 4, original_protection.value, ctypes.byref(restored)):
                raise ValueError("Could not restore the currency-cap memory protection")
        observed = ctypes.c_uint32()
        if (not kernel.ReadProcessMemory(process, address, ctypes.byref(observed), 4, ctypes.byref(read))
                or read.value != 4 or observed.value != ERIDIUM_LIMIT):
            raise ValueError("Native currency cap did not retain 1000")
        unrealsdk.logging.info("[EndgameQoLRebalance] Eridium carrying limit set to 1000 for this process")
    except (AttributeError, OSError, OverflowError, RuntimeError, TypeError, ValueError) as exc:
        unrealsdk.logging.info("[EndgameQoLRebalance] Eridium cap unavailable: " + str(exc))


BANK_UPGRADE_BALANCE_PATH = "GD_CustomItems.Items.CustomItem_SDU_Bank"
_bank_capacity_busy = False


def _bank_capacity_for_upgrades(upgrades: int) -> int:
    if isinstance(upgrades, bool) or not isinstance(upgrades, int) or upgrades < 0:
        raise ValueError("Invalid purchased bank upgrade count")
    initial_gains = (5, 5, 10, 15)
    result = 25 + sum(initial_gains[:upgrades]) + max(0, upgrades - len(initial_gains)) * 20
    if result > 2147483647:
        raise ValueError("Bank capacity exceeds the native integer range")
    return result


_storage_status_messages: dict[str, str] = {}


def _storage_status(label: str, message: str) -> None:
    if _storage_status_messages.get(label) != message:
        _storage_status_messages[label] = message
        unrealsdk.logging.info(f"[EndgameQoLRebalance] Storage {label}: {message}")


def _storage_upgrade_count(pc: Any, balance_path: str, label: str) -> int | None:
    """Resolve the purchased SDU count without fixed save-array indices."""
    try:
        balance = unrealsdk.find_object("InventoryBalanceDefinition", balance_path)
    except ValueError:
        balance = None
    index = int(pc.LookupBlackMarketUpgradeIndex(balance)) if balance is not None else -1
    if index < 0:
        # The loaded globals own the native upgrade list and its save-array order.
        # Use their actual references if a standalone balance lookup is unavailable.
        try:
            globals_definition = unrealsdk.find_object("GlobalsDefinition", GLOBALS_PATH)
        except ValueError:
            globals_definition = None
        matches = []
        if globals_definition is not None:
            for position, upgrade in enumerate(globals_definition.BlackMarketUpgrades):
                if upgrade is None:
                    continue
                definition = upgrade.BalanceDefinition
                if definition is not None and str(definition._path_name()).casefold() == balance_path.casefold():
                    matches.append(position)
        if len(matches) > 1:
            raise ValueError("Duplicate storage SDU definitions in native upgrade list")
        index = matches[0] if matches else -1
    if index < 0:
        _storage_status(label, "waiting for the native SDU definition/index")
        return None
    count = int(pc.GetBlackMarketUpgrade(index))
    _storage_status(label, f"SDU count resolved: index={index}, purchased={count}")
    return count


def _capacity_owner_context(controller: Any = None) -> tuple[Any, Any] | None:
    if _rules_suspended:
        return None
    current = get_pc()
    pc = current if controller is None else controller
    if pc is None or pc != current or pc.bDeleteMe or pc.bPendingDelete:
        return None
    world, pawn = pc.WorldInfo, pc.Pawn
    if (world is None or world.bDeleteMe or pawn is None
            or pawn.bDeleteMe or pawn.bPendingDelete):
        return None
    net_mode = int(world.NetMode)
    if net_mode == 2:
        # BL2 can host a listen-server session with no other player connected.
        # Do not equate a network-capable solo host with active co-op.
        game = world.Game
        players = int(game.NumPlayers) if game is not None else 0
        if players != 1:
            _storage_status("session", f"solo host not confirmed: net_mode={net_mode}, players={players}")
            return None
    elif net_mode != 0:
        _storage_status("session", f"non-local-authority session excluded: net_mode={net_mode}")
        return None
    manager = pc.GetPawnInventoryManager()
    if (manager is None or manager.bDeleteMe or manager.bPendingDelete
            or manager.GetOwningPlayerController() != pc):
        _storage_status("session", "waiting for the owning inventory manager")
        return None
    _storage_status("session", f"solo capacity maintenance ready: net_mode={net_mode}")
    return pc, manager


def _bank_capacity_context(controller: Any = None) -> tuple[Any, Any, int] | None:
    if not _settings()["bank_capacity"]:
        return None
    owner = _capacity_owner_context(controller)
    if owner is None:
        return None
    pc, manager = owner
    bank = manager.TheBank
    if bank is None:
        _storage_status("bank", "waiting for personal bank storage")
        return None
    upgrades = _storage_upgrade_count(pc, BANK_UPGRADE_BALANCE_PATH, "bank upgrades")
    if upgrades is None:
        return None
    desired = _bank_capacity_for_upgrades(upgrades)
    current, occupied = int(bank.GetMaxSize()), int(bank.GetSizeIncludingUnloadable())
    if current < 0 or occupied < 0:
        raise ValueError("Invalid personal bank capacity")
    return manager, bank, max(desired, current, occupied)


def _report_bank_capacity_error(exc: Exception) -> None:
    message = str(exc)
    if _errors.get("Bank capacity") != message:
        _errors["Bank capacity"] = message
        unrealsdk.logging.error("[EndgameQoLRebalance] Could not update personal bank capacity: " + message)


def _refresh_bank_capacity(controller: Any = None, *, storage: Any = None) -> None:
    global _bank_capacity_busy
    if _bank_capacity_busy:
        return
    _bank_capacity_busy = True
    try:
        context = _bank_capacity_context(controller)
        if context is None:
            return
        _manager, bank, target = context
        if storage is not None and storage != bank:
            return  # The shared stash and other storage are not this character's bank.
        if int(bank.MaxSlots) < target:
            bank.SetMaxSlots(target)
        if int(bank.GetMaxSize()) < target:
            if not bank.SetSlotCount(target) or int(bank.GetMaxSize()) < target:
                raise ValueError("Native bank did not retain the requested capacity")
            unrealsdk.logging.info(f"[EndgameQoLRebalance] Personal bank capacity increased to {target} slots")
        _errors.pop("Bank capacity", None)
    except Exception as exc:
        _report_bank_capacity_error(exc)
    finally:
        _bank_capacity_busy = False


@hook("WillowGame.WillowInventoryStorage:Open", Type.PRE)
def prepare_personal_bank_capacity(storage: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _refresh_bank_capacity(storage=storage)


@hook("WillowGame.WillowInventoryManager:ClientSetBankSlots", Type.PRE)
def preserve_personal_bank_capacity(manager: Any, args: Any, _ret: Any, func: Any) -> Any:
    """Keep native SDU slot updates from temporarily shrinking an expanded bank."""
    global _bank_capacity_busy
    if _bank_capacity_busy:
        return None
    _bank_capacity_busy = True
    started = False
    try:
        context = _bank_capacity_context()
        if context is None or context[0] != manager:
            return None
        _manager, bank, target = context
        requested = int(args.NewSlotCount)
        target = max(target, requested)
        if int(bank.MaxSlots) < target:
            bank.SetMaxSlots(target)
        if target == requested:
            return None
        started = True
        with prevent_hooking_direct_calls():
            result = func(NewSlotCount=target)
        return Block, result
    except Exception as exc:
        _report_bank_capacity_error(exc)
        return (Block, False) if started else None
    finally:
        _bank_capacity_busy = False


BACKPACK_UPGRADE_BALANCE_PATH = "GD_ItemGrades.StorageDeckUpgrades.ItemGrade_SDU_Backpack"
_backpack_capacity_busy = False


def _backpack_capacity_for_upgrades(upgrades: int) -> int:
    if isinstance(upgrades, bool) or not isinstance(upgrades, int) or upgrades < 0:
        raise ValueError("Invalid purchased backpack upgrade count")
    # The ninth/final native backpack SDU grants +15; intermediate gains stay unchanged.
    gains = (3, 3, 4, 4, 4, 5, 5, 5, 15)
    result = 22 + sum(gains[:upgrades]) + max(0, upgrades - len(gains)) * 5
    if result > 2147483647:
        raise ValueError("Backpack capacity exceeds the native integer range")
    return result


def _backpack_capacity_context(controller: Any = None) -> tuple[Any, int] | None:
    if not _settings()["backpack_capacity"]:
        return None
    owner = _capacity_owner_context(controller)
    if owner is None:
        return None
    pc, manager = owner
    upgrades = _storage_upgrade_count(pc, BACKPACK_UPGRADE_BALANCE_PATH, "backpack upgrades")
    if upgrades is None:
        return None
    desired = _backpack_capacity_for_upgrades(upgrades)
    current, occupied = int(manager.GetUnreadiedInventoryMaxSize()), int(manager.BackpackInventoryCount)
    if current < 0 or occupied < 0:
        raise ValueError("Invalid backpack capacity")
    return manager, max(desired, current, occupied)


def _report_backpack_capacity_error(exc: Exception) -> None:
    message = str(exc)
    if _errors.get("Backpack capacity") != message:
        _errors["Backpack capacity"] = message
        unrealsdk.logging.error("[EndgameQoLRebalance] Could not update backpack capacity: " + message)


def _refresh_backpack_capacity(controller: Any) -> None:
    global _backpack_capacity_busy
    if _backpack_capacity_busy:
        return
    _backpack_capacity_busy = True
    try:
        context = _backpack_capacity_context(controller)
        if context is None:
            return
        manager, target = context
        if int(manager.GetUnreadiedInventoryMaxSize()) < target:
            with prevent_hooking_direct_calls():
                manager.SetInventoryMaxSize(NewSize=target, bOverrideDefaultMin=False)
            if int(manager.GetUnreadiedInventoryMaxSize()) < target:
                raise ValueError("Native backpack did not retain the requested capacity")
            unrealsdk.logging.info(f"[EndgameQoLRebalance] Backpack capacity increased to {target} slots")
        _errors.pop("Backpack capacity", None)
    except Exception as exc:
        _report_backpack_capacity_error(exc)
    finally:
        _backpack_capacity_busy = False


@hook("WillowGame.WillowInventoryManager:SetInventoryMaxSize", Type.PRE)
def preserve_backpack_capacity(manager: Any, args: Any, _ret: Any, func: Any) -> Any:
    global _backpack_capacity_busy
    if _backpack_capacity_busy:
        return None
    _backpack_capacity_busy = True
    started = False
    try:
        context = _backpack_capacity_context()
        if context is None or context[0] != manager:
            return None
        target = max(context[1], int(args.NewSize))
        if target == int(args.NewSize):
            return None
        started = True
        with prevent_hooking_direct_calls():
            result = func(NewSize=target, bOverrideDefaultMin=bool(args.bOverrideDefaultMin))
        return Block, result
    except Exception as exc:
        _report_backpack_capacity_error(exc)
        return Block if started else None
    finally:
        _backpack_capacity_busy = False


def _configure_grog_reward(mission: Any) -> bool:
    """Append one permanent mission reward, preserving the loaded reward data."""
    current = mission.Reward
    items = list(current.RewardItems)
    paths = [None if item is None else str(item._path_name()).casefold() for item in items]
    if GROG_WEAPON_PATH.casefold() in paths:
        return False
    # Resolve first so an unloaded DLC cannot cause a partial reward edit.
    try:
        weapon = unrealsdk.find_object("WeaponBalanceDefinition", GROG_WEAPON_PATH)
    except ValueError as exc:
        raise AssetPending(GROG_WEAPON_PATH) from exc
    if weapon is None:
        raise AssetPending(GROG_WEAPON_PATH)
    reward = copy.copy(current)
    reward.RewardItems = [*items, weapon]
    mission.Reward = reward
    actual = [None if item is None else str(item._path_name()).casefold()
              for item in mission.Reward.RewardItems]
    if actual != [*paths, GROG_WEAPON_PATH.casefold()]:
        raise ValueError("Native mission reward did not retain the added Grog Nozzle")
    return True


def _check_grog_reward(now: float) -> None:
    if _settings()["grog_quest"]:
        _check_target("Grog mission reward", "MissionDefinition", GROG_MISSION_PATH,
                      _configure_grog_reward, now)


def _prepare_grog_mission(mission: Any) -> None:
    if not _settings()["grog_quest"]:
        return
    if mission is None or str(mission._path_name()).casefold() != GROG_MISSION_PATH.casefold():
        return
    _check_grog_reward(time.monotonic())


@hook("WillowGame.WillowPlayerController:ServerAcceptMission", Type.PRE)
def prepare_grog_accept(_obj: Any, args: Any, _ret: Any, _func: Any) -> None:
    _prepare_grog_mission(args.Mission)


@hook("WillowGame.WillowPlayerController:ServerCompleteMission", Type.PRE)
def prepare_grog_completion(_obj: Any, args: Any, _ret: Any, _func: Any) -> None:
    _prepare_grog_mission(args.Mission)








_movement_snapshot: tuple[Any, ...] | None = None
_movement_notice_at = 0.0


def _observe_player_movement(controller: Any, now: float) -> None:
    """Sample existing movement modifiers on the two-second maintenance budget."""
    global _movement_snapshot, _movement_notice_at
    if controller is None or controller != get_pc():
        return
    try:
        pawn = controller.Pawn
        if pawn is None or pawn.bDeleteMe:
            return
        base, current = float(pawn.GroundSpeedBaseValue), float(pawn.GroundSpeed)
        if not math.isfinite(base) or not math.isfinite(current) or base <= 0.0:
            return
        if current >= base * 0.9:
            _movement_snapshot = None
            return
        modifiers = tuple((str(m._path_name()), int(m.Type), float(m.Value))
                          for m in pawn.GroundSpeedModifierStack if m is not None)
        state = (str(pawn._path_name()), modifiers)
        if state == _movement_snapshot or now < _movement_notice_at:
            return
        _movement_snapshot = state  # Only primitive data survives the callback.
        _movement_notice_at = now + 30.0
        unrealsdk.logging.info(
            f"[EndgameQoLRebalance] Player movement diagnostic: speed={current:g}, "
            f"base={base:g}, modifiers={modifiers[:16]!r}; observation only"
        )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = str(exc)
        if _errors.get("Movement diagnostic") != message:
            _errors["Movement diagnostic"] = message
            unrealsdk.logging.error("[EndgameQoLRebalance] Could not inspect player movement: " + message)


RAID_HEALTH_CLASSES = (
    "GD_Orchid_RaidEngineer.Character.CharClass_Orchid_RaidEngineer",
    "GD_Orchid_RaidShaman.Character.CharClass_Orchid_RaidShaman",
    "GD_Sage_Raid_Beast.Character.CharClass_Sage_Raid_Beast",
    "GD_Iris_Raid_PyroPete.Character.CharClass_Iris_Raid_PyroPete",
)
RAID_PLAYER_COUNT_PATH = "D_Attributes.GameProperties.NumberOfPlayers"
RAID_PLAYER_WEIGHT_PATH = "GD_Balance.WeightingPlayerCount.Enemy_HealthBoost_PerPlayerPerPlaythroughByChampion"
RAID_HEALTH_ATTRIBUTE = "GD_Balance_HealthAndDamage.AIParameters.Attribute_HealthMultiplier"
RAID_VORAC_SHIELD_PATH = "MainGameRefs.Attributes.Att_VoracidousShield_PT3"
# Calibrated from the observed 11,004,751,872 shield and 15,078,746 boss HP
# at the default 5% growth and 2x UVHM durability settings. The native
# attribute controls both sides of the transferred shield, without pawn writes.
RAID_VORAC_SHIELD_SCALE = 0.75 * 15_078_746.0 / 11_004_751_872.0
RAID_DEX_CLASS = "GD_DrifterRaid.Character.CharClass_DrifterRaid"
RAID_FIXED_HEALTH_MULTIPLIERS = {
    RAID_HEALTH_CLASSES[0]: 98.0,  # Hyperius: native 56 * 1.75.
    "GD_Gladiolus_Balance.enemies.PawnBalanceModifier_Orchid_RaidShaman": 1000.0,
    RAID_DEX_CLASS: 2500.0,
}
RAID_HEALTH_TARGETS = (
    *(("AIClassDefinition", path) for path in RAID_HEALTH_CLASSES),
    *(("AIPawnBalanceDefinition", path) for path in (
        "GD_Orchid_Pop_RaidEngineer.PawnBalance_Orchid_RaidEngineer",
        "GD_Orchid_Pop_RaidShaman.Balance.PawnBalance_Orchid_RaidShaman",
        "GD_Sage_Raid_Beast.Population.Balance_Sage_Raid_Beast",
        "GD_Iris_Population_RaidPete.Balance.Iris_PawnBalance_RaidPete",
    )),
    *(("AIPawnBalanceModifierDefinition", "GD_Gladiolus_Balance.enemies." + name) for name in (
        "PawnBalanceModifier_Orchid_RaidEngineer", "PawnBalanceModifier_Orchid_RaidEngineer_Lobelia",
        "PawnBalanceModifier_Orchid_RaidShaman", "PawnBalanceModifier_Sage_RaidBeast",
        "PawnBalanceModifier_Iris_RaidPete",
    )),
    ("AIClassDefinition", RAID_DEX_CLASS),
)


def _raid_aid_fields(value: Any) -> dict[str, Any]:
    return {key: getattr(value, key) for key in (
        "BaseValueConstant", "BaseValueAttribute", "InitializationDefinition", "BaseValueScaleConstant",
    )}


def _raid_formula(multiplier: dict[str, Any], level: dict[str, Any], power: float) -> dict[str, Any]:
    return {
        "BaseValueMode": ("enum", "BASEVALUE_InitializationDefSetsBaseValue"),
        "RoundingMode": ("enum", "ATTRROUNDING_Float"),
        "ValueFormula": {"bEnabled": True, "Multiplier": multiplier, "Level": level,
                         "Power": _aid(power), "Offset": _aid(0.0)},
        "ConditionalInitialization": {"bEnabled": False},
        "RandomVariance": {"bEnabled": False},
        "RangeRestriction": {"bEnableMinValueRestriction": False, "bEnableMaxValueRestriction": False},
    }


def _raid_weight_reference(definition: Any) -> dict[str, Any]:
    # The native weight initializer SCALES its input; 0 would erase the weight.
    return {**_aid(1.0), "InitializationDefinition": definition}


def _prepare_raid_health_ratio() -> Any:
    """F(actual players)/F(effective players), retaining native mode/champion weights."""
    def required(cls: str, path: str) -> Any:
        try:
            obj = unrealsdk.find_object(cls, path)
        except ValueError as exc:
            raise AssetPending(path) from exc
        if obj is None:
            raise AssetPending(path)
        return obj

    count = required("AttributeDefinition", RAID_PLAYER_COUNT_PATH)
    weight = required("AttributeInitializationDefinition", RAID_PLAYER_WEIGHT_PATH)
    actual = _private_definition("AttributeDefinition", count, "VHS_ActualRaidPlayers", count)
    resolver = _private_definition("ObjectPropertyAttributeValueResolver", actual, "VHS_ActualRaidPlayersResolver")
    # The new resolver has no copied EffectiveNumPlayers CachedProperty pointer.
    _configure_patch(resolver, {"PropertyName": "NumPlayers"})
    _configure_patch(actual, {"ContextResolverChain": list(count.ContextResolverChain),
                              "ValueResolverChain": [resolver]})
    real_weight = _private_definition("AttributeInitializationDefinition", weight, "VHS_ActualRaidHealthWeight", weight)
    rows = []
    for row in weight.ConditionalInitialization.ConditionalExpressionList:
        expressions = []
        for expression in row.Expressions:
            fields = {key: getattr(expression, key) for key in (
                "AttributeOperand1", "ComparisonOperator", "Operand2Usage", "AttributeOperand2", "ConstantOperand2",
            )}
            for key in ("AttributeOperand1", "AttributeOperand2"):
                if fields[key] == count:
                    fields[key] = actual
            if (fields["AttributeOperand1"] == actual and fields["AttributeOperand2"] is None
                    and fields["ConstantOperand2"] == 1.0):
                comparison = _property(expression, "ComparisonOperator")
                if fields["ComparisonOperator"] == _enum_value(comparison, "OPERATOR_EqualTo"):
                    # Initial map setup may briefly report no joined players.
                    # Use the solo weight rather than the unrelated default row.
                    fields["ComparisonOperator"] = _enum_value(comparison, "OPERATOR_LessThanOrEqual")
            expressions.append(fields)
        rows.append({"BaseValueIfTrue": _raid_aid_fields(row.BaseValueIfTrue), "Expressions": expressions})
    if not rows or not weight.ConditionalInitialization.bEnabled:
        raise ValueError("Raid health player-weight table has no enabled conditional rows")
    _configure_patch(real_weight, {
        "BaseValueMode": weight.BaseValueMode, "RoundingMode": weight.RoundingMode,
        "ConditionalInitialization": {"bEnabled": True, "ConditionalExpressionList": rows,
            "DefaultBaseValue": _raid_aid_fields(weight.ConditionalInitialization.DefaultBaseValue)},
    })
    # Guard the divisor even if another mod supplies a zero/unknown weight.
    divisor = _private_definition("AttributeInitializationDefinition", weight, "VHS_RaidHealthDivisor")
    _configure_patch(divisor, {
        **_raid_formula(_aid(1.0), _raid_weight_reference(weight), 1.0),
        "RangeRestriction": {"bEnableMinValueRestriction": True, "MinValue": _aid(0.000001),
                             "bEnableMaxValueRestriction": False},
    })
    ratio = _private_definition("AttributeInitializationDefinition", weight, "VHS_RaidHealthPlayerRatio")
    _configure_patch(ratio, {
        **_raid_formula(_raid_weight_reference(real_weight), _raid_weight_reference(divisor), -1.0),
        "RangeRestriction": {"bEnableMinValueRestriction": True, "MinValue": _aid(0.0),
                             "bEnableMaxValueRestriction": True, "MaxValue": _aid(1.0)},
    })  # Remove inflation only; never amplify HP if the effective counter lags.
    return ratio


def _raid_health_rows(owner: Any, values: Any, prefix: str, ratio: Any) -> tuple[list[Any], bool]:
    """Apply scoped fixed bases and/or wrap player-count normalization once."""
    updated, changed = [], False
    for index, row in enumerate(values):
        attribute = row.Attribute
        if attribute is None or str(attribute._path_name()) != RAID_HEALTH_ATTRIBUTE:
            updated.append(row)
            continue
        fixed = RAID_FIXED_HEALTH_MULTIPLIERS.get(str(owner._path_name()))
        if ratio is None:
            if fixed is None:
                raise ValueError("Raid health requires a fixed base or a player-count ratio")
            replacement = _aid(fixed)
        else:
            wrapper = _private_definition("AttributeInitializationDefinition", owner,
                                          f"VHS_RaidHealth_{prefix}_{index}")
            original = (wrapper.ValueFormula.Multiplier if row.BaseValue.InitializationDefinition == wrapper
                        else row.BaseValue)
            base = _aid(fixed) if fixed is not None else _raid_aid_fields(original)
            _configure_patch(wrapper, _raid_formula(base, _raid_weight_reference(ratio), 1.0))
            replacement = {**_aid(0.0), "InitializationDefinition": wrapper}
        if _matches_fields(row.BaseValue, replacement):
            updated.append(row)
            continue
        item = copy.copy(row)
        item.BaseValue = _materialize(_property(row, "BaseValue"), replacement, row.BaseValue, {})
        updated.append(item)
        changed = True
    # Native array replacement needs detached rows; stable audits need no copies.
    return ([copy.copy(row) for row in updated] if changed else updated), changed


def _configure_raid_health(definition: Any, ratio: Any, *, playthroughs: bool) -> bool:
    # Keep original pool identities: scripted boss heals/phases may reference
    # those definitions directly. Do not clone pools or rewrite live actor HP.
    def verify(actual: Any, expected: Any) -> None:
        if len(actual) != len(expected) or any(
            a.Attribute != b.Attribute or not _matches_fields(a.BaseValue, _raid_aid_fields(b.BaseValue))
            for a, b in zip(actual, expected)
        ):
            raise ValueError("Native data did not retain raid health multipliers")
    if not playthroughs:
        rows, changed = _raid_health_rows(definition, definition.AttributeStartingValues, "Base", ratio)
        if changed:
            definition.AttributeStartingValues = rows
            verify(definition.AttributeStartingValues, rows)
    else:
        rows, changed = [], False
        for index, tier in enumerate(definition.PlayThroughs):
            values, dirty = _raid_health_rows(definition, tier.AttributeStartingValues, f"PT{index}", ratio)
            if dirty:
                item = copy.copy(tier)
                item.AttributeStartingValues = values
                changed = True
            else:
                item = tier
            rows.append(item)
        if changed:
            definition.PlayThroughs = [copy.copy(tier) for tier in rows]
            actual = definition.PlayThroughs
            if len(actual) != len(rows):
                raise ValueError("Native data did not retain raid playthroughs")
            for a, b in zip(actual, rows):
                verify(a.AttributeStartingValues, b.AttributeStartingValues)
    return changed


def _apply_raid_health_rules(now: float) -> None:
    if not _settings()["raid_health"]:
        return
    _check_target("Raid shield Voracidous", "DesignerAttributeDefinition", RAID_VORAC_SHIELD_PATH,
                  lambda attribute: _configure_patch(attribute, {
                      "BaseValue": {"BaseValueScaleConstant": RAID_VORAC_SHIELD_SCALE},
                  }), now)
    shared: list[Any] = []  # Callback-local only; prepare once for loaded classes.
    def configure(definition: Any, playthroughs: bool) -> bool:
        if str(definition._path_name()) == RAID_DEX_CLASS:
            # Dex receives the requested absolute base, without another party-size correction.
            return _configure_raid_health(definition, None, playthroughs=playthroughs)
        if not shared:
            shared.append(_prepare_raid_health_ratio())
        return _configure_raid_health(definition, shared[0], playthroughs=playthroughs)
    for cls, path in RAID_HEALTH_TARGETS:
        _check_target("Raid health " + path, cls, path,
                      lambda obj, tiers=(cls == "AIPawnBalanceDefinition"): configure(obj, tiers), now)





def _apply_rules(*, force: bool = False, controller: Any = None) -> None:
    global _next_check, _applying
    now = time.monotonic()
    if _applying or (not force and now < _next_check):
        return
    _next_check = now + CHECK_INTERVAL
    _applying = True
    try:
        # Look up definitions afresh; never retain actors, worlds or UObjects.
        if any(_settings()[key] for key in LEVEL_DIFFERENCE_KEYS):
            _check_target("Global tables", "GlobalsDefinition", GLOBALS_PATH, _configure_global_level_policy, now)
        _apply_growth_rules(now)
        _apply_ammo_capacity(now)
        _apply_raid_health_rules(now)
        if controller is not None:
            _refresh_bank_capacity(controller)
            _refresh_backpack_capacity(controller)
        _check_grog_reward(now)
        if _settings()["uvhm_rebalance"]:
            _apply_full_rebalance(now, force=force)
        if _settings()["higher_level_damage"] or _settings()["higher_level_status_chance"]:
            _check_target("UVHM tables", "BalanceModifierDefinition", UVHM_PATH, _configure_uvhm_level_policy, now)
        _observe_player_movement(controller, now)
        _finish_local_slag_audio(controller, now)
    finally:
        _applying = False


# Native BL2 equipment rarity identifiers; neither E-tech nor mission tokens
# become eligible merely because their numeric identifier is large.
LOOT_STAR_RARITIES = frozenset((5, 7, 8, 9, 10, 500, 501, 506))
LOOT_STAR_ROOT = "vhsGoldLootStars"
LOOT_STAR_REFRESH_SECONDS = 0.25
LOOT_STAR_DRAW_SECONDS = 0.05
LOOT_STAR_RECONCILE_SECONDS = 1.0
_loot_star_positions: tuple[tuple[float, float], ...] = ()
_loot_star_render_positions: tuple[tuple[float, float], ...] = ()
_loot_star_overlay_visible: bool | None = None
_loot_star_world: int | None = None
_loot_star_next_scan = 0.0
_loot_star_next_draw = 0.0
_loot_star_next_reconcile = 0.0
_loot_star_retry = 0.0
_loot_star_error = ""
_loot_star_announced = False
_loot_star_driver_notices: set[str] = set()
_loot_star_widget_path = ""
_loot_star_widget_movie = 0
_loot_star_widget_lookup_at = 0.0
_loot_star_scan_announced = False
_loot_star_scale_wait = ""


def _reset_loot_stars() -> None:
    """Only primitive data survives callbacks; never retain pickups or GFx objects."""
    global _loot_star_positions, _loot_star_render_positions, _loot_star_overlay_visible
    global _loot_star_world, _loot_star_next_scan
    global _loot_star_next_draw, _loot_star_next_reconcile, _loot_star_retry, _loot_star_error
    global _loot_star_scan_announced, _loot_star_scale_wait
    global _loot_star_widget_path, _loot_star_widget_movie, _loot_star_widget_lookup_at
    _loot_star_positions = ()
    _loot_star_render_positions = ()
    _loot_star_overlay_visible = None
    _loot_star_world = None
    _loot_star_next_scan = _loot_star_next_draw = _loot_star_next_reconcile = _loot_star_retry = 0.0
    _loot_star_error = ""
    _loot_star_scan_announced = False
    _loot_star_scale_wait = ""
    _loot_star_widget_path = ""
    _loot_star_widget_movie = 0
    _loot_star_widget_lookup_at = 0.0


def _loot_star_vertices() -> tuple[tuple[float, float], ...]:
    return tuple((math.cos(-math.pi / 2 + i * math.pi / 5) * (6.0 if i % 2 == 0 else 2.7),
                  math.sin(-math.pi / 2 + i * math.pi / 5) * (6.0 if i % 2 == 0 else 2.7))
                 for i in range(10))


# Native minimap coordinates have a 96-by-116 local drawing area. WorldRadius
# is its world-space half-width; UnrealUnitsPerPixel scales the map texture,
# and OuterRadius is also a world distance. Neither is a marker pixel scale.
LOOT_STAR_HALF_WIDTH = 48.0
LOOT_STAR_HALF_HEIGHT = 58.0
LOOT_STAR_EDGE_MARGIN = 8.0


def _loot_star_project(dx: float, dy: float, yaw: float, radius: float) -> tuple[float, float]:
    """Project onto the native icon plane, before the shared Flash/HUD transform."""
    angle = yaw * math.tau / 65536.0
    c, sn = math.cos(angle), math.sin(angle)
    scale = LOOT_STAR_HALF_WIDTH / radius
    return ((dy * c - dx * sn) * scale, -(dx * c + dy * sn) * scale)


def _loot_star_invoke(clip: Any, member: str, *numbers: float) -> None:
    clip.Invoke(member, [unrealsdk.make_struct("GFxUI.GFxMoviePlayer.ASValue", Type=2, N=float(n))
                         for n in numbers])


def _loot_star_container(widget: Any) -> Any:
    """Use the arrow's real Flash parent so drawing and coordinates agree."""
    arrow = widget.DirArrowClip
    if arrow is not None:
        parent = arrow.GetObject("_parent", None)
        if parent is not None:
            return parent
    return widget


def _make_loot_star(parent: Any, name: str) -> Any:
    clip = parent.CreateEmptyMovieClip(name, int(parent.GetNextHighestDepth()),
                                      unrealsdk.find_object("Class", "GFxUI.GFxObject"))
    if clip is None:
        raise RuntimeError("Minimap did not create the custom star clip")
    try:
        _loot_star_invoke(clip, "lineStyle", 1.2, 0x49320D, 100)
        _loot_star_invoke(clip, "beginFill", 0xF4C542, 100)
        vertices = _loot_star_vertices()
        _loot_star_invoke(clip, "moveTo", *vertices[0])
        for vertex in (*vertices[1:], vertices[0]):
            _loot_star_invoke(clip, "lineTo", *vertex)
        _loot_star_invoke(clip, "endFill")
        width = float(clip.GetFloat("_width"))
        if not math.isfinite(width) or width <= 0:
            raise RuntimeError("Minimap rejected the vector drawing commands")
        return clip
    except Exception:
        clip.RemoveMovieClip()
        raise


def _equipment_kind(item: Any) -> str | None:
    """Bound equipment metadata traversal for loot markers."""
    cls = item.Class
    for _ in range(32):
        if cls is None:
            return None
        name = str(cls.Name)
        if name in ("WillowWeapon", "WillowItem"):
            return name
        cls = cls.SuperField
    return None


def _scan_loot_star_positions(pc: Any, world: Any, now: float) -> None:
    global _loot_star_positions, _loot_star_next_scan, _loot_star_scan_announced
    if now < _loot_star_next_scan:
        return
    _loot_star_next_scan = now + LOOT_STAR_REFRESH_SECONDS
    globals_instance = pc.GetWillowGlobals()
    if globals_instance is None:
        _loot_star_positions = ()
        return
    positions = []
    # Reconcile the game's existing pickup list, not all UObjects/actors. This
    # also catches replicated drops, moved loot and items present at enable.
    for pickup in globals_instance.PickupList:
        if pickup is None or pickup.bDeleteMe or pickup.bPendingDelete:
            continue
        if pickup.WorldInfo != world or pickup.bIsMissionItem or not pickup.bPickupable:
            continue
        rarity = int(pickup.InventoryRarityLevel)
        if rarity not in LOOT_STAR_RARITIES and rarity != 0:
            continue
        inventory = pickup.Inventory
        if inventory is None or inventory.bDeleteMe or inventory.bPendingDelete:
            continue
        # Ordinary mission tokens/currency must not masquerade as pearl gear.
        if _equipment_kind(inventory) is None:
            continue
        if rarity == 0 and int(inventory.GetRarityLevel()) not in LOOT_STAR_RARITIES:
            continue  # The pickup's replicated rarity may not have arrived yet.
        location = pickup.Location
        xy = (float(location.X), float(location.Y))
        if all(math.isfinite(v) for v in xy):
            positions.append(xy)
    _loot_star_positions = tuple(positions)
    if positions and not _loot_star_scan_announced:
        unrealsdk.logging.info(f"[EndgameQoLRebalance] Loot stars found {len(positions)} eligible ground equipment item(s)")
        _loot_star_scan_announced = True


@hook("WillowGame.HUDWidget_Minimap:Deinit", Type.PRE)
def release_loot_stars(widget: Any, _args: Any, _ret: Any, _func: Any) -> None:
    try:
        root = _loot_star_container(widget).GetObject(LOOT_STAR_ROOT, None)
        if root is not None:
            root.RemoveMovieClip()
    except Exception:
        # The native HUD can already be closing. Do not chase stale UI objects.
        pass
    _reset_loot_stars()


def _repair_loot_star_visibility(clip: Any, visible: bool) -> None:
    """Read back our own clip after native HUD/menu timeline changes."""
    if bool(clip.GetBool("_visible")) != visible:
        clip.SetVisible(visible)
    if visible:
        alpha = float(clip.GetFloat("_alpha"))
        if not math.isfinite(alpha) or alpha <= 0:
            clip.SetFloat("_alpha", 100.0)


def _set_loot_star_visibility(root: Any, visible: bool, *, verify: bool = False) -> None:
    global _loot_star_overlay_visible
    if root is None:
        return
    if verify:
        _repair_loot_star_visibility(root, visible)
    elif _loot_star_overlay_visible != visible:
        root.SetVisible(visible)
    _loot_star_overlay_visible = visible


def update_loot_stars(widget: Any, _args: Any, _ret: Any, _func: Any, *, controller: Any = None) -> None:
    global _loot_star_world, _loot_star_next_draw, _loot_star_next_reconcile, _loot_star_retry
    global _loot_star_error, _loot_star_announced, _loot_star_scale_wait
    global _loot_star_render_positions, _loot_star_overlay_visible
    if not _settings()["loot_stars"]:
        return
    now = time.monotonic()
    if now < max(_loot_star_retry, _loot_star_next_draw):
        return
    _loot_star_next_draw = now + LOOT_STAR_DRAW_SECONDS
    root = None
    try:
        container = _loot_star_container(widget)
        root = container.GetObject(LOOT_STAR_ROOT, None)
        pc = controller if controller is not None else get_pc()
        if pc is None or pc.bDeleteMe or pc.bPendingDelete:
            if root is not None:
                _set_loot_star_visibility(root, False)
            return
        world, pawn, movie = pc.WorldInfo, pc.Pawn, widget.MyHUDMovie
        if world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe or pawn.bPendingDelete:
            if root is not None:
                _set_loot_star_visibility(root, False)
            return
        if movie is None or movie != pc.GetHUDMovie():
            if root is not None:
                _set_loot_star_visibility(root, False)
            return
        address = world._get_address()
        if _loot_star_world != address:
            _reset_loot_stars()
            _loot_star_world = address
        radius = float(widget.WorldRadius)
        arrow = widget.DirArrowClip
        if arrow is None or not math.isfinite(radius) or radius <= 0:
            if not _loot_star_scale_wait:
                _loot_star_scale_wait = "waiting"
                unrealsdk.logging.info(f"[EndgameQoLRebalance] Loot stars waiting for minimap initialization: radius={radius:g}, arrow={arrow is not None}")
            if root is not None:
                _set_loot_star_visibility(root, False)
            return
        _loot_star_scale_wait = ""
        _scan_loot_star_positions(pc, world, now)
        if not _loot_star_positions:
            if root is not None:
                _set_loot_star_visibility(root, False)
            return
        if root is None:
            root = container.CreateEmptyMovieClip(LOOT_STAR_ROOT, int(container.GetNextHighestDepth()),
                                               unrealsdk.find_object("Class", "GFxUI.GFxObject"))
            if root is None:
                raise RuntimeError("Minimap did not create the loot overlay")
            _loot_star_render_positions = ()
            _loot_star_overlay_visible = None
            _loot_star_next_reconcile = 0.0
        # Cached values are only an optimization: menus can hide/clear Flash
        # clips without deleting them or changing pickup positions/counts.
        reconcile = now >= _loot_star_next_reconcile
        if reconcile:
            _loot_star_next_reconcile = now + LOOT_STAR_RECONCILE_SECONDS
        # A child of the arrow's native minimap container inherits visibility and scaling.
        # The owner is reacquired each callback rather than cached across the HUD
        # lifetime. No Canvas overlay, stock icon replacement or radar slots.
        cx, cy = arrow.GetFloat("_x"), arrow.GetFloat("_y")
        # Player-relative mode replaces map north with the cached view yaw.
        # Adding both rotates markers away from their native map positions.
        yaw = float(widget.CachedPlayerYaw if widget.bPlayerRelative else widget.MapYawOffset)
        origin = pawn.Location
        ox, oy = float(origin.X), float(origin.Y)
        if not all(math.isfinite(v) for v in (cx, cy, yaw, ox, oy)):
            _set_loot_star_visibility(root, False)
            return
        half_width = LOOT_STAR_HALF_WIDTH - LOOT_STAR_EDGE_MARGIN
        half_height = LOOT_STAR_HALF_HEIGHT - LOOT_STAR_EDGE_MARGIN
        used = 0
        previous = int(root.GetFloat("vhsUsed"))
        rendered = []
        for x, y in _loot_star_positions:
            sx, sy = _loot_star_project(x - ox, y - oy, yaw, radius)
            if abs(sx) > half_width or abs(sy) > half_height:
                continue
            name = "star" + str(used)
            star = root.GetObject(name, None)
            created = star is None
            if not created and reconcile:
                width = float(star.GetFloat("_width"))
                if not math.isfinite(width) or width <= 0:
                    star.RemoveMovieClip()
                    created = True
            if created:
                star = _make_loot_star(root, name)
            position = (cx + sx, cy + sy)
            position_changed = (created or used >= len(_loot_star_render_positions)
                                or _loot_star_render_positions[used] != position)
            if not position_changed and reconcile:
                actual = (float(star.GetFloat("_x")), float(star.GetFloat("_y")))
                position_changed = any(not math.isfinite(a) or not math.isclose(a, b, abs_tol=0.01)
                                       for a, b in zip(actual, position))
            if position_changed:
                star.SetPosition(*position)
            if created or used >= previous:
                star.SetVisible(True)
            elif reconcile:
                _repair_loot_star_visibility(star, True)
            rendered.append(position)
            used += 1
        for index in range(used, previous):
            star = root.GetObject("star" + str(index), None)
            if star is not None:
                star.SetVisible(False)
        _loot_star_render_positions = tuple(rendered)
        if used != previous:
            root.SetFloat("vhsUsed", float(used))
        _set_loot_star_visibility(root, used > 0, verify=reconcile)
        if used and not _loot_star_announced:
            unrealsdk.logging.info("[EndgameQoLRebalance] Custom gold loot stars initialized with native world-radius projection")
            _loot_star_announced = True
        _loot_star_error = ""
    except Exception as exc:
        _loot_star_retry = now + 5.0
        if root is not None:
            try:
                _set_loot_star_visibility(root, False)
            except Exception:
                pass
        message = str(exc)
        if message != _loot_star_error:
            unrealsdk.logging.error("[EndgameQoLRebalance] Could not update loot minimap stars: " + message)
            _loot_star_error = message


def _loot_driver_notice(stage: str, text: str) -> None:
    if stage not in _loot_star_driver_notices:
        _loot_star_driver_notices.add(stage)
        unrealsdk.logging.info("[EndgameQoLRebalance] Loot stars: " + text)


def _get_loot_minimap(movie: Any, now: float) -> Any:
    """Prefer the native pointer; cache only a path if binding left it unset."""
    global _loot_star_widget_path, _loot_star_widget_movie, _loot_star_widget_lookup_at
    widget = movie.MyMinimapWidget
    if widget is not None and widget.MyHUDMovie == movie:
        return widget
    address = movie._get_address()
    if _loot_star_widget_movie == address and _loot_star_widget_path:
        try:
            widget = unrealsdk.find_object("HUDWidget_Minimap", _loot_star_widget_path)
        except ValueError:
            widget = None
        if widget is not None and widget.MyHUDMovie == movie:
            return widget
        _loot_star_widget_path = ""
    if now < _loot_star_widget_lookup_at:
        return None
    _loot_star_widget_lookup_at = now + 2.0
    # Startup fallback only, never a full actor scan per frame. Once found,
    # native path lookup replaces this search; no UI UObject is retained.
    for candidate in unrealsdk.find_all("HUDWidget_Minimap"):
        if candidate is not None and candidate.MyHUDMovie == movie:
            _loot_star_widget_path = str(candidate._path_name())
            _loot_star_widget_movie = address
            return candidate
    return None


def refresh_loot_stars(controller: Any) -> None:
    """Drive GFx from the PlayerTick already observed in the actual SDK log."""
    global _loot_star_next_draw, _loot_star_error, _loot_star_retry
    if not _settings()["loot_stars"]:
        return
    now = time.monotonic()
    if now < max(_loot_star_next_draw, _loot_star_retry):
        return
    try:
        if controller is None or controller.bDeleteMe or controller.bPendingDelete:
            return
        if not controller.IsLocalPlayerController():
            return
        _loot_driver_notice("tick", "local PlayerTick driver active")
        world, pawn = controller.WorldInfo, controller.Pawn
        if world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe or pawn.bPendingDelete:
            _loot_star_next_draw = now + LOOT_STAR_DRAW_SECONDS
            return
        movie = controller.GetHUDMovie()
        if movie is None:
            _loot_driver_notice("hud", "waiting for GetHUDMovie")
            _loot_star_next_draw = now + LOOT_STAR_DRAW_SECONDS
            return
        widget = _get_loot_minimap(movie, now)
        if widget is None:
            _loot_driver_notice("widget", "waiting for native minimap binding")
            _loot_star_next_draw = now + LOOT_STAR_DRAW_SECONDS
            return
        _loot_driver_notice("bound", "native minimap found through GetHUDMovie")
        # Visibility is inherited from the actual minimap movie. The viewport
        # AreHudMoviesVisible flag is not used as a prerequisite for discovery.
        update_loot_stars(widget, None, None, None, controller=controller)
    except Exception as exc:
        _loot_star_retry = now + 5.0
        message = "PlayerTick driver: " + str(exc)
        if message != _loot_star_error:
            unrealsdk.logging.error("[EndgameQoLRebalance] Could not update loot minimap stars: " + message)
            _loot_star_error = message


def _suspend_rule_maintenance() -> None:
    global _rules_suspended, _rules_departing_context, _slag_audio_pending, _slag_audio_respawn_pending
    _slag_audio_pending = None
    _slag_audio_respawn_pending = False
    _slag_audio_death_contexts.clear()  # Discard primitive state; never play audio during teardown.
    _rules_suspended = True
    _rules_departing_context = _rules_active_context


def _maintenance_controller_ready(controller: Any) -> bool:
    global _rules_suspended, _rules_active_context
    current = get_pc()
    if current is None or current != controller:
        return False
    if current.bDeleteMe:
        return False
    world = current.WorldInfo
    if world is None:
        return False
    context = (current._get_address(), world._get_address())
    if _rules_suspended and context == _rules_departing_context:
        return False  # Do not inspect the old pawn/tree while it is being torn down.
    if world.bDeleteMe or getattr(world, "Pauser", None) is not None:
        return False
    pause_menu_open = getattr(current, "IsPauseMenuOpen", None)
    if pause_menu_open is not None and pause_menu_open():
        return False  # Menu pause also applies off-host, without a world Pauser.
    pawn, tree = current.Pawn, current.PlayerSkillTree
    if (pawn is None or pawn.bDeleteMe or world.bDeleteMe
            or tree is None or not tree.bInitialized):
        return False
    _rules_active_context = context
    _rules_suspended = False
    return True


@hook("WillowGame.WillowPlayerController:PreClientTravel", Type.PRE)
@hook("WillowGame.WillowPlayerController:Destroyed", Type.PRE)
def suspend_rules_for_departing_player(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    # Destroyed must not inspect pawn/world/skill data of a departing actor.
    address = controller._get_address()
    current = get_pc()
    if ((_rules_active_context is not None and address == _rules_active_context[0])
            or (current is not None and current._get_address() == address)):
        _suspend_rule_maintenance()


def on_enable() -> None:
    global _next_check, _uvhm_signature, _uvhm_audit_cursor
    global _movement_snapshot, _movement_notice_at
    global _rules_suspended, _rules_active_context, _rules_departing_context
    global _slag_audio_type, _slag_audio_pending, _slag_audio_respawn_pending
    global _slag_audio_notice_context, _slag_audio_check_at
    _slag_audio_type = _slag_audio_pending = _slag_audio_notice_context = None
    _slag_audio_respawn_pending = False
    _slag_audio_death_contexts.clear()
    _slag_audio_check_at = 0.0
    _movement_snapshot, _movement_notice_at = None, 0.0
    _rules_suspended, _rules_active_context, _rules_departing_context = True, None, None
    _freeze_session_settings()
    _apply_eridium_capacity()
    _reset_loot_stars()
    _next_check = 0.0
    _uvhm_signature = None
    _uvhm_audit_cursor = 0
    _verified.clear()
    _pending.clear()
    _errors.clear()
    _last_repair_notice.clear()
    _storage_status_messages.clear()
    unrealsdk.logging.info(
        "[EndgameQoLRebalance] Loaded 1.0.9: configurable endgame balance, level differences, "
        "storage, ammo, Eridium and loot markers; restart-applied settings; "
        + json.dumps(_settings(), sort_keys=True)
    )
    _apply_rules(force=True)


@hook("WillowGame.FrontendGFxMovie:Start", Type.PRE)
def refresh_frontend(_obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _rules_suspended
    # Frontend/options UI can open while the gameplay world remains alive.
    # Only actual travel/destruction may mark its context as departing.
    # Keep any existing departure marker; resume this world only after unpause.
    _rules_suspended = True
    _reset_loot_stars()
    # Menu startup is not a safe place to inspect departing skill constraints.


@hook("WillowGame.WillowGameInfo:InitGame", Type.PRE)
def prepare_game(_obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _suspend_rule_maintenance()
    _reset_loot_stars()
    _apply_rules(force=True)


@hook("WillowGame.WillowGameInfo:InitGame", Type.POST)
def refresh_game(_obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _apply_rules(force=True)


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def maintain_rules(_obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    now = time.monotonic()
    if not _rules_suspended and now < _next_check:
        if (not _settings()["loot_stars"]
                or now < max(_loot_star_next_draw, _loot_star_retry)):
            return  # No due task: do not inspect pawn/tree/HUD on an idle frame.
    if not _maintenance_controller_ready(_obj):
        return
    _apply_rules(controller=_obj)
    refresh_loot_stars(_obj)


@hook("WillowGame.PlayerSkillTree:Initialize", Type.PRE)
def prepare_class(_obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _apply_rules(force=True)


class EndgameQoLRebalanceMod(RestartToDisable):
    def get_status(self) -> str:
        if self.is_enabled and _session_settings is not None and _read_menu_settings() != _session_settings:
            return "<font color='#ffb347'>Enabled - Restart to Apply Options</font>"
        return super().get_status()

    def load_settings(self) -> None:
        """Migrate existing choices before SDK auto-enable freezes the session."""
        saved: dict[str, Any] = {}
        if self.settings_file is not None:
            try:
                with self.settings_file.open(encoding="utf-8") as stream:
                    data = json.load(stream)
                if isinstance(data, dict):
                    saved = data
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                pass
        groups = saved.get("options", {})
        if isinstance(groups, dict):
            old_gap = groups.get("level_difference", {})
            if isinstance(old_gap, dict) and isinstance(old_gap.get("enabled"), bool):
                for key in LEVEL_DIFFERENCE_KEYS:
                    if key not in old_gap:
                        _OPTION_VALUES[key].value = old_gap["enabled"]
            resources = groups.get("resources_storage", {})
            if not isinstance(resources, dict):
                resources = {}
            for key in ("backpack_capacity", "bank_capacity", "ammo_capacity"):
                legacy = groups.get(key, {})
                if (key not in resources and isinstance(legacy, dict)
                        and isinstance(legacy.get("enabled"), bool)):
                    _OPTION_VALUES[key].value = legacy["enabled"]
        super().load_settings()
        if self.is_enabled or not self.auto_enable or "enabled" in saved:
            return
        self.enable()



mod = build_mod(
    cls=EndgameQoLRebalanceMod,
    auto_enable=True,
    on_enable=on_enable,
    hooks=[refresh_frontend, prepare_game, refresh_game, prepare_class,
           maintain_rules, suspend_rules_for_departing_player,
           observe_local_slag_sound, observe_local_slag_end,
           prepare_slag_audio_after_death, arm_slag_audio_after_death,
           prepare_grog_accept, prepare_grog_completion,
           *LEVEL_HOOKS, release_loot_stars,
           prepare_personal_bank_capacity, preserve_personal_bank_capacity, preserve_backpack_capacity],
    commands=[], keybinds=[], options=SUPPORT_OPTIONS,
)
