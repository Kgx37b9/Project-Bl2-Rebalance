"""Salvador skill adjustments using native skill grades and presentations."""

from __future__ import annotations

import copy
import math
import time
from typing import Any

import unrealsdk  # pyright: ignore[reportMissingModuleSource]
from mods_base import ObjectFlags, RestartToDisable, build_mod, get_pc, hook
from unrealsdk.hooks import Block, Type, prevent_hooking_direct_calls  # pyright: ignore[reportMissingModuleSource]
from unrealsdk.unreal import WeakPointer  # pyright: ignore[reportMissingModuleSource]

GET_SOME_PATH = "GD_Mercenary_Skills.Rampage.GetSome"
GET_SOME_ACTIVE_PATH = GET_SOME_PATH + "_Active"
GET_SOME_SECONDS_PER_RANK = 0.8
GET_SOME_NATIVE_DURATION = 3.0
GET_SOME_GRADE_ATTRIBUTE = "GD_Mercenary_Skills.SkillGradeModifiers.GetSome"
HARD_TO_KILL_PATH = "GD_Mercenary_Skills.Brawn.Diehard"
HEALTH_ATTRIBUTE = "D_Attributes.HealthResourcePool.HealthMaxValue_Player"
ROUGH_RIDER_DEFINITION = "GD_Sage_Shields.A_Item_Custom.Shield_Buckler"
REGEN_ATTRIBUTE = "D_Attributes.HealthResourcePool.HealthPassiveRegenerationRate"
REGEN_PRESENTATION_ATTRIBUTE = "GD_Mercenary_Skills.Misc.Att_DieHard_HealthRegen"
REGEN_PRESENTATION = HARD_TO_KILL_PATH + ":AttributePresentationDefinition_0"
PLAYER_CLASS = "GD_Mercenary.Character.CharClass_Mercenary"
SKILL_TREE = "GD_Mercenary_Streaming.SkillTree.SkillTree_Mercenary"
JUGGERNAUT_PATH = "GD_Mercenary_Skills.Brawn.ImTheJuggernaut"
JUGGERNAUT_REDUCTION_PER_RANK = 0.12
JUGGERNAUT_ATTRIBUTES = frozenset(
    "D_Attributes.DamageTypeModifers." + name for name in (
        "NormalImpactDamageModifier", "ExplosiveImpactDamageModifier",
        "CorrosiveImpactDamageModifier", "CorrosiveStatusEffectDamageModifier",
        "IncendiaryImpactDamageModifier", "IncendiaryStatusEffectDamageModifier",
        "ShockImpactDamageModifier", "ShockStatusEffectDamageModifier",
    )
)
JUST_GOT_REAL_PATH = "GD_Mercenary_Skills.Brawn.JustGotReal"
JUST_GOT_REAL_INITIALIZER = "GD_Mercenary_Skills.Misc.Init_JustGotReal_DamageCalc_P1"
JUST_GOT_REAL_COEFFICIENT = "GD_Mercenary_Skills.Misc.Att_JustGotReal_DamagePerLvl"
JUST_GOT_REAL_DAMAGE_PER_RANK = 0.12
BLEED_PATH = "GD_Mercenary_Skills.Brawn.AintGotTimeToBleed"
BLEED_INITIALIZER = "GD_Mercenary_Skills.Misc.Init_AintGotTimeToBleed_RegenFormula_P1"
BLEED_COEFFICIENT = "GD_Mercenary_Skills.Misc.Att_AintGotTimeToBleed_HealthRegenPerLvl"
BLEED_REGEN_PER_RANK = 0.03
BLEED_STAT_DESCRIPTION = "Regenerates $NUMBER$ of your missing Health / sec."
READY_ALREADY_PATH = "GD_Mercenary_Skills.Rampage.ImReadyAlready"
COOLDOWN_RATE_ATTRIBUTE = "D_Attributes.ActiveSkillCooldownResource.ActiveSkillCooldownConsumptionRate"
READY_ALREADY_RATE_PER_RANK = 0.10
DIVERGENT_PATH = "GD_Mercenary_Skills.Gun_Lust.DivergentLikness"
DIVERGENT_FIRE_INTERVALS = {
    "D_Attributes.Weapon.WeaponSpread": "D_Attributes.Weapon.WeaponFireInterval",
    "D_Attributes.OffHandWeapon.WeaponSpread_Offhand": "D_Attributes.OffHandWeapon.WeaponFireInterval_Offhand",
}
DIVERGENT_ACCURACY_MINIMUMS = frozenset((
    "D_Attributes.AccuracyResourcePool.AccuracyMinValue",
    "D_Attributes.OffHandAccuracyResourcePool.OffHandAccuracyMinValue",
))
DIVERGENT_DESCRIPTION = (
    "When [skill]Gunzerking[-skill] with two guns of the same type, you deal "
    "[skill]Bonus Damage[-skill].  When [skill]Gunzerking[-skill] with two different "
    "types of guns you gain [skill]Bonus Fire Rate[-skill]."
)
REFLEXES_PATH = "GD_Mercenary_Skills.Rampage.AllInTheReflexes"
REFLEXES_MELEE_ATTRIBUTE = "D_Attributes.DamageSourceModifiers.InstigatedMeleeDamageModifier"
REFLEXES_RELOAD_PER_RANK = 0.05
REFLEXES_MODIFIER_NAME = "SR_ReflexesEmptyReload"
REFLEXES_DESCRIPTION = (
    "Increases [skill]Reload Speed[-skill]. This bonus is [skill]doubled[-skill] "
    "when reloading an [skill]empty magazine[-skill]."
)
TYRANNOSAURUS_PATH = "GD_Mercenary_Skills.Brawn.SexualTyrannosaurus"
TYRANNOSAURUS_OLD_ACTIVE = TYRANNOSAURUS_PATH + "_Active"
TYRANNOSAURUS_LIFE_STEAL_ATTRIBUTE = "D_Attributes.DamageEnhancementModifiers.PlayerConvertDamageToHealingPercent"
TYRANNOSAURUS_CRIT_ATTRIBUTE = "D_Attributes.GameplayAttributes.PlayerCriticalHitBonus"
TYRANNOSAURUS_VALUES = {
    TYRANNOSAURUS_LIFE_STEAL_ATTRIBUTE: 0.04,
    "D_Attributes.Weapon.WeaponFireInterval": 0.03,
    "D_Attributes.OffHandWeapon.WeaponFireInterval_Offhand": 0.03,
    TYRANNOSAURUS_CRIT_ATTRIBUTE: -0.05,
}
TYRANNOSAURUS_DESCRIPTION = (
    "While [skill]Gunzerking[-skill], you gain [skill]Life Steal[-skill], "
    "but your [skill]Fire Rate[-skill] and [skill]Critical Hit Damage[-skill] are reduced."
)
OFFHAND_PAIRS = {
    JUST_GOT_REAL_PATH: ("D_Attributes.Weapon.WeaponDamage", "D_Attributes.OffHandWeapon.WeaponDamage_Offhand"),
    "GD_Mercenary_Skills.Gun_Lust.LayWaste": ("D_Attributes.Weapon.WeaponFireInterval", "D_Attributes.OffHandWeapon.WeaponFireInterval_Offhand"),
    "GD_Mercenary_Skills.Brawn.Incite_Active": ("D_Attributes.Weapon.WeaponReloadSpeed", "D_Attributes.OffHandWeapon.WeaponReloadSpeed_Offhand"),
    "GD_Mercenary_Skills.Rampage.5Shotsor6": ("D_Attributes.Weapon.WeaponShotCost", "D_Attributes.OffHandWeapon.WeaponShotCost_Offhand"),
}
HUCKLEBERRY_PATH = "GD_Mercenary_Skills.Gun_Lust.ImYourHuckleberry"
HUCKLEBERRY_OLD_OFFHAND = HUCKLEBERRY_PATH + "_Offhand"
HUCKLEBERRY_PISTOL_ATTRIBUTES = (
    "D_Attributes.WeaponType.Weapon_Is_Pistol", "D_Attributes.WeaponType.OffhandWeapon_Is_Pistol",
)
HUCKLEBERRY_COEFFICIENTS = (
    "GD_Mercenary_Skills.Misc.Att_ImYourHuckleberry_DamagePerLvl",
    "GD_Mercenary_Skills.Misc.Att_ImYourHuckleberry_ReloadSpeedPerLvl",
)
HUCKLEBERRY_TARGETS = (
    "D_Attributes.Weapon.WeaponDamage", "D_Attributes.Weapon.WeaponReloadSpeed",
    "D_Attributes.OffHandWeapon.WeaponDamage_Offhand", "D_Attributes.OffHandWeapon.WeaponReloadSpeed_Offhand",
)
QUICK_DRAW_PATH = "GD_Mercenary_Skills.Gun_Lust.QuickDraw"
QUICK_DRAW_CRIT_PER_RANK = 0.04
QUICK_DRAW_SWAP_ATTRIBUTE = "D_Attributes.Weapon.WeaponSwapTimeMultiplier"
QUICK_DRAW_SWAP_PER_RANK = 0.10
BUS_PATH = "GD_Mercenary_Skills.Brawn.BusThatCantSlowDown"
BRAWN_BRANCH_PATH = "GD_Mercenary_Skills.SkillTree.Branch_Brawn"
BRAWN_LAYOUT_PATH = "GD_Mercenary_Skills.SkillTree.Layout_Brawn"
_bus_position_configured: tuple[int, int] | None = None
AUTO_LOADER_PATH = "GD_Mercenary_Skills.Gun_Lust.AutoLoader"
AUTO_LOADER_RELOAD_ATTRIBUTES = (
    "D_Attributes.Weapon.WeaponReloadSpeed", "D_Attributes.OffHandWeapon.WeaponReloadSpeed_Offhand",
)
AUTO_LOADER_RELOAD_BONUS = 0.15
AUTO_LOADER_DESCRIPTION = (
    "Killing an enemy [skill]instantly reloads[-skill] all of the guns you have equipped "
    "that are not currently in your hands. Swapping guns after [skill]Auto-Loader[-skill] "
    "has reloaded a gun triggers [skill]Locked & Loaded[-skill]. "
    "Also increases your [skill]Reload Speed[-skill]."
)
PIPING_HOT_PATH = "GD_Mercenary_Skills.Gun_Lust.KeepItPipingHot"
PIPING_HOT_HELPER = PIPING_HOT_PATH + ":SR_PipingHotStacks"
PIPING_HOT_HUD = PIPING_HOT_PATH + ":SR_PipingHotHUD"
GUNZERKING_PATH = "GD_Mercenary_Skills.ActionSkill.Skill_Gunzerking"
YIPPEE_PATH = "GD_Mercenary_Skills.Rampage.YippeeKiYay"
YIPPEE_CRIT_SECONDS_PER_RANK = 0.3
YIPPEE_CRIT_COOLDOWN = 0.5
YIPPEE_DESCRIPTION = (
    "Killing an enemy while [skill]Gunzerking[-skill] increases the amount of "
    "[skill]time you can Gunzerk[-skill]. Landing a [skill]Critical Hit[-skill] "
    "while Gunzerking also [skill]extends its duration[-skill]."
)
PIPING_HOT_PER_RANK = 0.0014
PIPING_HOT_STACK_LIMIT = 50
PIPING_HOT_TARGETS = {
    "D_Attributes.Weapon.WeaponDamage": PIPING_HOT_PER_RANK,
    "D_Attributes.OffHandWeapon.WeaponDamage_Offhand": PIPING_HOT_PER_RANK,
    "D_Attributes.Weapon.WeaponSpread": -PIPING_HOT_PER_RANK,
    "D_Attributes.OffHandWeapon.WeaponSpread_Offhand": -PIPING_HOT_PER_RANK,
}
PIPING_HOT_DESCRIPTION = (
    "Gain a stack each second while [skill]Gunzerking[-skill], up to 50 stacks. "
    "Each stack increases [skill]Gun Damage[-skill] and [skill]Accuracy[-skill]. "
    "All stacks are lost when Gunzerking ends."
)
ASBESTOS_PATH = "GD_Mercenary_Skills.Brawn.Asbestos"
ASBESTOS_BONUS = ASBESTOS_PATH + ":SR_AsbestosFireRate"
ASBESTOS_FIRE_RATE_PER_RANK = 0.03
ASBESTOS_FIRE_ATTRIBUTES = ("D_Attributes.Weapon.WeaponFireInterval",
                            "D_Attributes.OffHandWeapon.WeaponFireInterval_Offhand")
ASBESTOS_HUD = ASBESTOS_PATH + ":SR_AsbestosHUD"
ASBESTOS_BUFF_DURATION = 10.0
ASBESTOS_DESCRIPTION = (
    "Reduces the duration of enemy [skill]Elemental Status Effects[-skill] on you. "
    "Whenever an [skill]Elemental Status Effect[-skill] is applied to you, "
    "you briefly gain [skill]Fire Rate[-skill]. New applications refresh the duration."
)
OVERKILL_PATH = "GD_Mercenary_Skills.Gun_Lust.NoKillLikeOverkill"
OVERKILL_ACTIVE_PATH = OVERKILL_PATH + "_Active"
OVERKILL_BONUS_SCALE = 0.5
OVERKILL_DAMAGE_ATTRIBUTES = (
    "D_Attributes.Weapon.WeaponDamage", "D_Attributes.OffHandWeapon.WeaponDamage_Offhand",
)
OVERKILL_DESCRIPTION = (
    "Killing an enemy grants [skill]Bonus Damage[-skill] to your next shot based on the "
    "excess damage you dealt, up to [skill]+200% Bonus Damage[-skill]."
)
MONEY_SHOT_PATH = "GD_Mercenary_Skills.Gun_Lust.MoneyShot"
MONEY_SHOT_DAMAGE_ATTRIBUTE = "D_Attributes.DamageEnhancementModifiers.LastShotInClipBonusModifier"
MONEY_SHOT_BONUS_SCALE = 0.75  # Native 0.8 * (12 / 10) * 0.75 = 0.72 per rank.
MONEY_SHOT_MAX_DAMAGE_PER_RANK = 0.72
FIST_HURT_PATH = "GD_Mercenary_Skills.Brawn.FistfulOfHurt"
FIST_HURT_MELEE = "GD_Mercenary_Skills.Misc.MeleeDefinition_FistfulOfHurt"
FIST_SHOCK_PATH = FIST_HURT_PATH + ":SR_SelfShock"
FIST_SHOCK_PROVIDER = FIST_HURT_PATH + ":BehaviorProviderDefinition_6"
FIST_SHOCK_MOVE = FIST_SHOCK_PROVIDER + ".Behavior_SpecialMove_6"
FIST_SHOCK_DESCRIPTION = "Using this skill applies [skill]Shock[-skill] to you, even if the punch misses."
_fist_shock_configured: tuple[int, int] | None = None
FIST_HURT_BONUS = 0.10
FIST_HURT_SECONDS = 8.0
FIST_HURT_TEAM = False
FIST_HURT_DESCRIPTION_EXTRA = (
    "Enemies hit by [skill]Fistful of Hurt[-skill] take [skill]increased damage from you[-skill] "
    "for [skill]8 seconds[-skill]."
)
FIST_RECEIVED_FIELDS = (
    "ReceivedBulletDamageModifier", "ReceivedGrenadeDamageModifier", "ReceivedMeleeDamageModifier",
    "ReceivedRocketDamageModifier", "ReceivedStatusEffectDamageModifier", "ReceivedSkillDamageModifier",
)
FIST_SOURCE_FIELDS = {
    "WillowGame.WillowDmgSource_" + name: "Received" + kind + "DamageModifier"
    for kind, names in (
        ("Bullet", ("Bullet", "Pistol", "Shotgun", "MachineGun", "SubMachineGun", "Sniper")),
        ("Grenade", ("Grenade",)), ("Melee", ("Melee",)), ("Rocket", ("Rocket",)),
        ("StatusEffect", ("StatusEffect",)), ("Skill", ("Skill", "Skill_IgnoreIOs")),
    ) for name in names
}
BERZERK_PATH = "GD_Mercenary_Skills.Brawn.ComeAtMeBro"
BERZERK_LEGACY_PATH = BERZERK_PATH + "_Active"
BERZERK_HEALTH_COST = 0.20
BERZERK_GUN_BONUS = 0.85
BERZERK_DAMAGE_REDUCTION = 0.5
BERZERK_DAMAGE_MODIFIER = "SR_BerzerkPostAddDamage"
BERZERK_SHIELD_BLOCK = "D_Attributes.ShieldResourcePool.ShieldRegenerationDisabled"
BERZERK_RESISTANCE_ATTRIBUTES = tuple(sorted(JUGGERNAUT_ATTRIBUTES)) + (
    "D_Attributes.DamageTypeModifers.AmpImpactDamageModifier",
)
BERZERK_DESCRIPTION = (
    "While [skill]Gunzerking[-skill], your [skill]Shield cannot regenerate[-skill] and you gain "
    "[skill]Damage Reduction[-skill] and [skill]Amp Damage[-skill]. "
    "Each shot costs some [skill]Health[-skill]."
)
HEALTH_PER_RANK = 0.04
HARD_TO_KILL_RESISTANCE_PER_RANK = 0.04
HARD_TO_KILL_RESISTANCE_ATTRIBUTES = BERZERK_RESISTANCE_ATTRIBUTES
DESCRIPTION = "Increases your [skill]Maximum Health[-skill] and [skill]Damage Resistance[-skill]."
MAINTENANCE_SECONDS = 1.0

_next_maintenance = 0.0
_hud_allocation_checks: dict[str, tuple[tuple[int, int, int], float, int]] = {}
_live_context: tuple[int, int] | None = None
_departing_context: tuple[int, int] | None = None
_live_skill_ranks: dict[int, tuple[int, int, int, int, int]] = {}
_rough_rider_slots: dict[str, tuple[int, int, int]] = {}
_reported_errors: set[str] = set()
_configuration_logged = False
_yippee_crit_last: tuple[int, int, int, int, float, float] | None = None
_just_got_real_revision = 0
_bleed_revision = 0
_reflexes_pending: set[int] = set()
_huckleberry_revision = 0
# Only primitive identities/times survive callbacks; no cached live UObject handles.
_piping_hot_session: tuple[int, int, int, float] | None = None
_piping_hot_hud_ready = False
_piping_hot_logged: set[tuple[int, int]] = set()
_asbestos_window: tuple[int, int, int, float] | None = None
_asbestos_hud_ready = False
_asbestos_hud_last: tuple[int, int, int, float] | None = None
_next_asbestos_hud_sync = 0.0
_asbestos_status_frames: list[dict[str, Any] | None] = []
_asbestos_bonus_ready = False
# Marks contain primitive actor identities only; modifier pools contain rooted assets, never actors.
_fist_marks: dict[tuple[int, int], tuple[float, str, int, float]] = {}
_fist_scopes: list[dict[str, Any] | None] = []
_fist_modifier_pool: dict[tuple[int, str], tuple[Any, Any]] = {}
_berzerk_context: tuple[int, int, int] | None = None
_berzerk_weapons: set[int] = set()
_berzerk_fire_frames: list[dict[str, Any] | None] = []


def _path(obj: Any) -> str:
    return str(obj._path_name()) if obj is not None else ""


def _effect_target_value(effect: Any, skill_path: str = HARD_TO_KILL_PATH) -> float | None:
    path = _path(effect.AttributeToModify)
    if skill_path == JUGGERNAUT_PATH:
        return -JUGGERNAUT_REDUCTION_PER_RANK if path in JUGGERNAUT_ATTRIBUTES else None
    if skill_path == JUST_GOT_REAL_PATH:
        if not path and any(_path(value.BaseValueAttribute) == JUST_GOT_REAL_COEFFICIENT
                            for value in (effect.BaseModifierValue, effect.PerGradeUpgrade)):
            return JUST_GOT_REAL_DAMAGE_PER_RANK
        return None  # Keep the gun-damage initializer and its health condition intact.
    if skill_path == BLEED_PATH:
        if not path and any(_path(value.BaseValueAttribute) == BLEED_COEFFICIENT
                            for value in (effect.BaseModifierValue, effect.PerGradeUpgrade)):
            return BLEED_REGEN_PER_RANK
        return None  # Preserve the native missing-health regeneration initializer.
    if skill_path == READY_ALREADY_PATH:
        return READY_ALREADY_RATE_PER_RANK if path == COOLDOWN_RATE_ATTRIBUTE else None
    if skill_path == DIVERGENT_PATH:
        return 0.0 if path in DIVERGENT_ACCURACY_MINIMUMS else None
    if skill_path == REFLEXES_PATH:
        return 0.0 if path == REFLEXES_MELEE_ATTRIBUTE else None
    if skill_path == TYRANNOSAURUS_PATH:
        return TYRANNOSAURUS_VALUES.get(path)
    if skill_path == TYRANNOSAURUS_OLD_ACTIVE:
        return 0.0 if path == REGEN_ATTRIBUTE else None
    if skill_path == HUCKLEBERRY_OLD_OFFHAND:
        return 0.0 if path in HUCKLEBERRY_TARGETS[2:] else None
    if skill_path == QUICK_DRAW_PATH:
        if path == QUICK_DRAW_SWAP_ATTRIBUTE:
            return -QUICK_DRAW_SWAP_PER_RANK
        return QUICK_DRAW_CRIT_PER_RANK if path == TYRANNOSAURUS_CRIT_ATTRIBUTE else None
    if skill_path == AUTO_LOADER_PATH:
        return -AUTO_LOADER_RELOAD_BONUS if path in AUTO_LOADER_RELOAD_ATTRIBUTES else None
    if skill_path in (PIPING_HOT_PATH, PIPING_HOT_HELPER):
        return PIPING_HOT_TARGETS.get(path)
    if skill_path == MONEY_SHOT_PATH:
        if not path:
            return MONEY_SHOT_MAX_DAMAGE_PER_RANK  # Native display-only damage stat.
        if path == "D_Attributes.Weapon.WeaponPerShotAccuracyImpulse" and effect.EffectTarget == unrealsdk.find_enum("EEffectTarget").TARGET_None:
            return 12.0  # Actual native clip governor cap, not its misleading divisor of 10.
        return None
    if skill_path == BERZERK_PATH:
        if path == BERZERK_SHIELD_BLOCK:
            return 1.0
        if path in BERZERK_RESISTANCE_ATTRIBUTES:
            return -BERZERK_DAMAGE_REDUCTION / (1.0 - BERZERK_DAMAGE_REDUCTION)
        return None
    if skill_path == GET_SOME_PATH:
        return -GET_SOME_SECONDS_PER_RANK if not path else None
    if skill_path != HARD_TO_KILL_PATH:
        return None
    if path in HARD_TO_KILL_RESISTANCE_ATTRIBUTES:
        return -HARD_TO_KILL_RESISTANCE_PER_RANK
    if path == HEALTH_ATTRIBUTE:
        return HEALTH_PER_RANK
    if path == REGEN_ATTRIBUTE:
        return 0.0
    if not path and any(_path(value.BaseValueAttribute) == REGEN_PRESENTATION_ATTRIBUTE
                        for value in (effect.BaseModifierValue, effect.PerGradeUpgrade)):
        return 0.0  # Native helper used only to present regeneration.
    return None


def _tuned_effect(effect: Any, skill_path: str = HARD_TO_KILL_PATH) -> Any | None:
    if (skill_path == GET_SOME_ACTIVE_PATH
            and _path(effect.AttributeToModify) == COOLDOWN_RATE_ATTRIBUTE):
        target = GET_SOME_SECONDS_PER_RANK / GET_SOME_NATIVE_DURATION
        if math.isclose(float(effect.BaseModifierValue.BaseValueScaleConstant), target,
                        rel_tol=1e-6, abs_tol=1e-7):
            return None
        result = copy.copy(effect)
        value = copy.copy(effect.BaseModifierValue)
        value.BaseValueScaleConstant = target
        result.BaseModifierValue = value
        return result
    """Return an owned replacement only when native data differs."""
    if (skill_path == OVERKILL_ACTIVE_PATH
            or (skill_path == MONEY_SHOT_PATH and _path(effect.AttributeToModify) == MONEY_SHOT_DAMAGE_ATTRIBUTE)):
        if skill_path == OVERKILL_ACTIVE_PATH and _path(effect.AttributeToModify) not in OVERKILL_DAMAGE_ATTRIBUTES:
            return None
        # Scale only the completed native bonus, retaining its initializer and conditions.
        scale = OVERKILL_BONUS_SCALE if skill_path == OVERKILL_ACTIVE_PATH else MONEY_SHOT_BONUS_SCALE
        fields = ("BaseModifierValue", "PerGradeUpgrade")
        if all(math.isclose(float(getattr(effect, field).BaseValueScaleConstant),
                            scale, rel_tol=1e-6, abs_tol=1e-7) for field in fields):
            return None
        result = copy.copy(effect)
        for field in fields:
            value = copy.copy(getattr(result, field))
            value.BaseValueScaleConstant = scale
            setattr(result, field, value)
        return result
    if skill_path == DIVERGENT_PATH:
        target = DIVERGENT_FIRE_INTERVALS.get(_path(effect.AttributeToModify))
        if target is not None:
            result = copy.copy(effect)
            result.AttributeToModify = unrealsdk.find_object("AttributeDefinition", target)
            # Keep AccuracyCalc's native different-weapon-type gate and its
            # negative scale, appropriate for the native fire-interval attribute.
            return result
    expected = _effect_target_value(effect, skill_path)
    if expected is None:
        return None
    matches = (int(effect.GradeToStartApplyingEffect) == 1
               and int(effect.PerGradeUpgradeInterval) == 1
               and not effect.BonusUpgradeList)
    fixed = (skill_path in (AUTO_LOADER_PATH, BERZERK_PATH)
             or (skill_path == MONEY_SHOT_PATH and _path(effect.AttributeToModify)
                 == "D_Attributes.Weapon.WeaponPerShotAccuracyImpulse"))
    expected_values = (expected, 0.0 if fixed else expected)
    for value, coefficient in zip((effect.BaseModifierValue, effect.PerGradeUpgrade), expected_values):
        matches = (matches and math.isclose(float(value.BaseValueConstant), coefficient,
                                           rel_tol=1e-6, abs_tol=1e-7)
                   and value.BaseValueAttribute is None
                   and value.InitializationDefinition is None
                   and math.isclose(float(value.BaseValueScaleConstant), 1.0,
                                    rel_tol=1e-6, abs_tol=1e-7))
    mode: Any = None
    force_target = (skill_path in (TYRANNOSAURUS_PATH, AUTO_LOADER_PATH, PIPING_HOT_PATH, PIPING_HOT_HELPER, BERZERK_PATH)
                    or (skill_path == HARD_TO_KILL_PATH
                        and _path(effect.AttributeToModify) in HARD_TO_KILL_RESISTANCE_ATTRIBUTES))
    if force_target:
        mode = (unrealsdk.find_enum("EModifierType").MT_PostAdd
                if _path(effect.AttributeToModify) in (TYRANNOSAURUS_LIFE_STEAL_ATTRIBUTE, BERZERK_SHIELD_BLOCK)
                else unrealsdk.find_enum("EModifierType").MT_Scale)
        matches = (matches and effect.ModifierType == mode
                   and effect.EffectTarget == (unrealsdk.find_enum("EEffectTarget").TARGET_None
                       if skill_path == PIPING_HOT_PATH else unrealsdk.find_enum("EEffectTarget").TARGET_Self))
    if matches:
        return None
    result = copy.copy(effect)
    if force_target:
        result.ModifierType = mode
        result.EffectTarget = (unrealsdk.find_enum("EEffectTarget").TARGET_None
                               if skill_path == PIPING_HOT_PATH else unrealsdk.find_enum("EEffectTarget").TARGET_Self)
    for field, coefficient in zip(("BaseModifierValue", "PerGradeUpgrade"), expected_values):
        value = copy.copy(getattr(result, field))
        value.BaseValueConstant = coefficient
        value.BaseValueAttribute = None
        value.InitializationDefinition = None
        value.BaseValueScaleConstant = 1.0
        setattr(result, field, value)
    result.GradeToStartApplyingEffect = 1
    result.PerGradeUpgradeInterval = 1
    result.BonusUpgradeList = []
    return result


def _configure_hard_to_kill() -> Any | None:
    global _configuration_logged
    try:
        definition = unrealsdk.find_object("SkillDefinition", HARD_TO_KILL_PATH)
    except ValueError:
        return None  # Streamed character data may not be loaded yet.
    if definition is None:
        return None
    resistance = [_find_piping_object("AttributeDefinition", path) for path in HARD_TO_KILL_RESISTANCE_ATTRIBUTES]
    if any(attribute is None for attribute in resistance):
        return None
    effects = list(definition.SkillEffectDefinitions)
    health = [row for row in effects if _path(row.AttributeToModify) == HEALTH_ATTRIBUTE]
    if len(health) != 1:
        raise ValueError("Hard to Kill must have one maximum-health effect")
    desired = []
    changed = False
    for row in effects:
        if _path(row.AttributeToModify) in HARD_TO_KILL_RESISTANCE_ATTRIBUTES:
            continue  # Replace only our named resistance targets, preserving other effects.
        tuned = _tuned_effect(row)
        desired.append(copy.copy(tuned if tuned is not None else row))
        changed |= tuned is not None
    for attribute in resistance:
        matches = [row for row in effects if row.AttributeToModify == attribute]
        row = copy.copy(matches[0] if matches else health[0])
        row.AttributeToModify = attribute
        tuned = _tuned_effect(row)
        desired.append(copy.copy(tuned if tuned is not None else row))
        changed |= tuned is not None or len(matches) != 1
    if changed or tuple(_path(row.AttributeToModify) for row in effects) != tuple(
            _path(row.AttributeToModify) for row in desired):
        definition.SkillEffectDefinitions = desired
    if str(definition.SkillDescription) != DESCRIPTION:
        definition.SkillDescription = DESCRIPTION
    presentations = list(definition.SkillEffectPresentations)
    kept = [item for item in presentations if _path(item) != REGEN_PRESENTATION]
    if len(kept) != len(presentations):
        definition.SkillEffectPresentations = kept
    # Native health presentation owns COM ranks, previews and the game's colors.
    if not _configuration_logged:
        _configuration_logged = True
        unrealsdk.logging.info(
            "[SalvadorRebalance] Hard to Kill configured: maximum health and native resistance 4% per rank; regeneration removed")
    return definition


def _configure_juggernaut() -> Any | None:
    try:
        definition = unrealsdk.find_object("SkillDefinition", JUGGERNAUT_PATH)
    except ValueError:
        return None
    if definition is None:
        return None
    effects = list(definition.SkillEffectDefinitions)
    for attribute in JUGGERNAUT_ATTRIBUTES:
        if sum(_path(effect.AttributeToModify) == attribute for effect in effects) != 1:
            raise ValueError(f"I'm the Juggernaut must have one effect for {attribute}")
    updated = [_tuned_effect(effect, JUGGERNAUT_PATH) for effect in effects]
    if any(effect is not None for effect in updated):
        definition.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                            for old, new in zip(effects, updated)]
    # Preserve the native kill trigger, duration, presentation and COM rules.
    return definition


def _configure_just_got_real() -> Any | None:
    global _just_got_real_revision
    try:
        definition = unrealsdk.find_object("SkillDefinition", JUST_GOT_REAL_PATH)
        initializer = unrealsdk.find_object("AttributeInitializationDefinition", JUST_GOT_REAL_INITIALIZER)
    except ValueError:
        return None
    if definition is None or initializer is None:
        return None
    # Replace only the coefficient source. Native Level/Power/Offset still
    # calculate the missing-health condition; full health receives no bonus.
    formula = initializer.ValueFormula
    value = formula.Multiplier
    if (not math.isclose(float(value.BaseValueConstant), JUST_GOT_REAL_DAMAGE_PER_RANK,
                         rel_tol=1e-6, abs_tol=1e-7)
            or value.BaseValueAttribute is not None or value.InitializationDefinition is not None
            or not math.isclose(float(value.BaseValueScaleConstant), 1.0, rel_tol=1e-6, abs_tol=1e-7)):
        formula, value = copy.copy(formula), copy.copy(value)
        value.BaseValueConstant = JUST_GOT_REAL_DAMAGE_PER_RANK
        value.BaseValueAttribute = value.InitializationDefinition = None
        value.BaseValueScaleConstant = 1.0
        formula.Multiplier = value
        initializer.ValueFormula = formula
        _just_got_real_revision += 1
    effects = list(definition.SkillEffectDefinitions)
    updated = [_tuned_effect(effect, JUST_GOT_REAL_PATH) for effect in effects]
    if any(effect is not None for effect in updated):
        definition.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                            for old, new in zip(effects, updated)]
    _ensure_offhand_pair(definition, *OFFHAND_PAIRS[JUST_GOT_REAL_PATH])
    return definition


def _configure_bleed() -> Any | None:
    global _bleed_revision
    try:
        definition = unrealsdk.find_object("SkillDefinition", BLEED_PATH)
        initializer = unrealsdk.find_object("AttributeInitializationDefinition", BLEED_INITIALIZER)
    except ValueError:
        return None
    if definition is None or initializer is None:
        return None
    # P1 multiplies the native missing-health P2 by its Level coefficient.
    # Do not replace P2 or the live regen effect with a flat health value.
    formula = initializer.ValueFormula
    value = formula.Level
    if (not math.isclose(float(value.BaseValueConstant), BLEED_REGEN_PER_RANK,
                         rel_tol=1e-6, abs_tol=1e-7)
            or value.BaseValueAttribute is not None or value.InitializationDefinition is not None
            or not math.isclose(float(value.BaseValueScaleConstant), 1.0, rel_tol=1e-6, abs_tol=1e-7)):
        formula, value = copy.copy(formula), copy.copy(value)
        value.BaseValueConstant = BLEED_REGEN_PER_RANK
        value.BaseValueAttribute = value.InitializationDefinition = None
        value.BaseValueScaleConstant = 1.0
        formula.Level = value
        initializer.ValueFormula = formula
        _bleed_revision += 1
    effects = list(definition.SkillEffectDefinitions)
    updated = [_tuned_effect(effect, BLEED_PATH) for effect in effects]
    if any(effect is not None for effect in updated):
        definition.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                            for old, new in zip(effects, updated)]
    for presentation in definition.SkillEffectPresentations:
        if (_path(presentation) == BLEED_PATH + ":AttributePresentationDefinition_0"
                and str(presentation.Description) != BLEED_STAT_DESCRIPTION):
            presentation.Description = BLEED_STAT_DESCRIPTION
    return definition


def _configure_ready_already() -> Any | None:
    try:
        definition = unrealsdk.find_object("SkillDefinition", READY_ALREADY_PATH)
    except ValueError:
        return None
    if definition is None:
        return None
    effects = list(definition.SkillEffectDefinitions)
    if sum(_path(effect.AttributeToModify) == COOLDOWN_RATE_ATTRIBUTE for effect in effects) != 1:
        raise ValueError("I'm Ready Already must have one cooldown-rate effect")
    updated = [_tuned_effect(effect, READY_ALREADY_PATH) for effect in effects]
    if any(effect is not None for effect in updated):
        definition.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                            for old, new in zip(effects, updated)]
    return definition


def _configure_divergent() -> Any | None:
    try:
        definition = unrealsdk.find_object("SkillDefinition", DIVERGENT_PATH)
        # Resolve both targets before modifying any native skill data.
        for path in DIVERGENT_FIRE_INTERVALS.values():
            if unrealsdk.find_object("AttributeDefinition", path) is None:
                return None
    except ValueError:
        return None
    if definition is None:
        return None
    effects = list(definition.SkillEffectDefinitions)
    for original, replacement in DIVERGENT_FIRE_INTERVALS.items():
        if sum(_path(effect.AttributeToModify) in (original, replacement) for effect in effects) != 1:
            raise ValueError("Divergent Likeness must have one main/off-hand accuracy or fire-rate effect")
    updated = [_tuned_effect(effect, DIVERGENT_PATH) for effect in effects]
    if any(effect is not None for effect in updated):
        definition.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                            for old, new in zip(effects, updated)]
    if str(definition.SkillDescription) != DIVERGENT_DESCRIPTION:
        definition.SkillDescription = DIVERGENT_DESCRIPTION
    for presentation in definition.SkillEffectPresentations:
        if (_path(presentation) == DIVERGENT_PATH + ":AttributePresentationDefinition_1"
                and str(presentation.Description) != "Fire Rate: $NUMBER$"):
            presentation.Description = "Fire Rate: $NUMBER$"
    return definition


def _configure_reflexes() -> Any | None:
    try:
        definition = unrealsdk.find_object("SkillDefinition", REFLEXES_PATH)
    except ValueError:
        return None
    if definition is None:
        return None
    effects = list(definition.SkillEffectDefinitions)
    updated = [_tuned_effect(effect, REFLEXES_PATH) for effect in effects]
    if any(effect is not None for effect in updated):
        definition.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                            for old, new in zip(effects, updated)]
    if str(definition.SkillDescription) != REFLEXES_DESCRIPTION:
        definition.SkillDescription = REFLEXES_DESCRIPTION
    presentations = list(definition.SkillEffectPresentations)
    kept = [item for item in presentations
            if _path(item) != REFLEXES_PATH + ":AttributePresentationDefinition_2"]
    if len(kept) != len(presentations):
        definition.SkillEffectPresentations = kept
    return definition


def _reflexes_controller(weapon: Any) -> Any | None:
    if weapon is None or weapon.bDeleteMe:
        return None
    controller = get_pc(possibly_loading=True)
    if controller is None or controller.bDeleteMe or _path(controller.PlayerClass) != PLAYER_CLASS:
        return None
    world, pawn = controller.WorldInfo, controller.Pawn
    if world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe:
        return None
    context = (controller._get_address(), world._get_address())
    if _departing_context in (context, (context[0], 0)):
        return None
    if (pawn.Controller != controller or weapon.Instigator != pawn
            or weapon.WorldInfo != world):
        return None
    return controller


def _reflexes_rank(controller: Any) -> int:
    manager = controller.GetSkillManager()
    if manager is None or manager.bUpdatingSkills:
        return 0
    active = unrealsdk.find_enum("ESkillState").SKILL_Active
    return max((int(skill.Grade) for skill in manager.ActiveSkills
                if skill.SkillInstigator == controller and skill.SkillState == active
                and _path(skill.Definition) == REFLEXES_PATH), default=0)


def _reflexes_modifiers(weapon: Any) -> list[Any]:
    return [modifier for modifier in weapon.ReloadTimeModifierStack
            if modifier is not None and str(modifier.Name) == REFLEXES_MODIFIER_NAME]


def _clear_reflexes_reload(weapon: Any) -> None:
    for modifier in _reflexes_modifiers(weapon):
        if not weapon.RemoveModifier(modifier, "ReloadTime", False):
            raise RuntimeError("Could not remove Reflexes empty-reload modifier")
    _reflexes_pending.discard(weapon._get_address())


def _set_reflexes_reload(weapon: Any, rank: int, empty: bool) -> None:
    existing = _reflexes_modifiers(weapon)
    if rank <= 0 or not empty:
        _clear_reflexes_reload(weapon)
        return
    expected = -REFLEXES_RELOAD_PER_RANK * rank
    if len(existing) > 1:
        _clear_reflexes_reload(weapon)
        existing = []
    if existing:
        modifier = existing[0]
    else:
        # Nested Unreal object paths use a dot after the first subobject colon.
        outer_path = _path(weapon)
        path = outer_path + ("." if ":" in outer_path else ":") + REFLEXES_MODIFIER_NAME
        try:
            modifier = unrealsdk.find_object("AttributeModifier", path)
        except ValueError:
            modifier = None
        if modifier is None:
            modifier = unrealsdk.construct_object("AttributeModifier", weapon, REFLEXES_MODIFIER_NAME)
        modifier.Type = unrealsdk.find_enum("EModifierType").MT_Scale
        modifier.Value = expected
        if not weapon.AddModifier(modifier, "ReloadTime", False):
            raise RuntimeError("Could not attach Reflexes empty-reload modifier")
    if not math.isclose(float(modifier.Value), expected, rel_tol=1e-6, abs_tol=1e-7):
        # Reattach so the native cached ReloadTime is recalculated after a COM swap.
        _clear_reflexes_reload(weapon)
        modifier.Value = expected
        if not weapon.AddModifier(modifier, "ReloadTime", False):
            raise RuntimeError("Could not refresh Reflexes empty-reload modifier")
    _reflexes_pending.add(weapon._get_address())


@hook("WillowGame.WillowWeapon:StartReload", Type.PRE)
def start_reflexes_reload(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    try:
        controller = _reflexes_controller(weapon)
        if controller is None:
            return
        if weapon not in (controller.Pawn.Weapon, controller.Pawn.OffHandWeapon):
            return
        _set_reflexes_reload(weapon, _reflexes_rank(controller), int(weapon.ReloadCnt) <= 0)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not start Reflexes empty reload", exc)


@hook("WillowGame.WillowWeapon:TimeWeaponReload", Type.PRE)
def time_reflexes_reload(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    try:
        controller = _reflexes_controller(weapon)
        if controller is None:
            return
        if weapon not in (controller.Pawn.Weapon, controller.Pawn.OffHandWeapon):
            return
        _set_reflexes_reload(weapon, _reflexes_rank(controller),
                             int(weapon.AmmoLeftInClipDuringReload) <= 0)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not time Reflexes empty reload", exc)


@hook("WillowGame.WillowWeapon:ReloadDone", Type.POST)
@hook("WillowGame.WillowWeapon:StopReloading", Type.POST)
@hook("WillowGame.WillowWeapon:OnAbortReload", Type.POST)
@hook("WillowGame.WillowWeapon:OnUnequip", Type.PRE)
@hook("WillowGame.WillowWeapon:ItemRemovedFromInvManager", Type.PRE)
def finish_reflexes_reload(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    try:
        if weapon is None or weapon._get_address() not in _reflexes_pending:
            return
        if _reflexes_controller(weapon) is not None:
            _clear_reflexes_reload(weapon)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not finish Reflexes empty reload", exc)


def _maintain_reflexes_reload(controller: Any, rank: int) -> None:
    if not _reflexes_pending:
        return  # No per-tick ammo checks or scans when the bonus is not attached.
    equipped = [weapon for weapon in (controller.Pawn.Weapon, controller.Pawn.OffHandWeapon)
                if weapon is not None and not weapon.bDeleteMe]
    seen: set[int] = set()
    for weapon in equipped:
        address = weapon._get_address()
        if address not in _reflexes_pending:
            continue
        seen.add(address)
        if (rank <= 0 or weapon.GetReplicatedReloadState()
                != unrealsdk.find_enum("EWeaponReloadState").RELOADSTATE_Reloading):
            _clear_reflexes_reload(weapon)
        else:
            _set_reflexes_reload(weapon, rank, True)
    _reflexes_pending.intersection_update(seen)


def _configure_tyrannosaurus() -> tuple[Any, ...] | None:
    try:
        definition = unrealsdk.find_object("SkillDefinition", TYRANNOSAURUS_PATH)
        attributes = [unrealsdk.find_object("AttributeDefinition", path)
                      for path in TYRANNOSAURUS_VALUES]
    except ValueError:
        return None
    if definition is None or any(attribute is None for attribute in attributes):
        return None
    effects = list(definition.SkillEffectDefinitions)
    originals = list(definition.SkillEffectPresentations)
    if not originals:
        raise ValueError("Sexual Tyrannosaurus has no native presentation template")
    if not effects:
        raise ValueError("Sexual Tyrannosaurus has no native effect template")
    new_effects = None
    expected_paths = tuple(TYRANNOSAURUS_VALUES)
    if tuple(_path(effect.AttributeToModify) for effect in effects) != expected_paths:
        desired = []
        for attribute in attributes:
            item = copy.copy(effects[0])
            item.AttributeToModify = attribute
            tuned = _tuned_effect(item, TYRANNOSAURUS_PATH)
            desired.append(copy.copy(tuned if tuned is not None else item))
        new_effects = desired
    else:
        replacements = [_tuned_effect(effect, TYRANNOSAURUS_PATH) for effect in effects]
        if any(item is not None for item in replacements):
            new_effects = [copy.copy(new if new is not None else old)
                           for old, new in zip(effects, replacements)]
    current = {_path(item): item for item in originals}
    specs = (
        ("SR_LifeSteal", attributes[0], "Life Steal: $NUMBER$", False),
        ("SR_FireRate", attributes[1], "Fire Rate: -$NUMBER$", True),
        ("SR_CriticalDamage", attributes[3], "Critical Hit Damage: $NUMBER$", False),
    )
    presentations = []
    for name, attribute, text, inverse in specs:
        path = TYRANNOSAURUS_PATH + ":" + name
        presentation = current.get(path)
        if presentation is None:
            try:
                presentation = unrealsdk.find_object("AttributePresentationDefinition", path)
            except ValueError:
                presentation = None
            if presentation is None:
                presentation = unrealsdk.construct_object(
                    "AttributePresentationDefinition", definition, name, template_obj=originals[0])
        for field, value in (
            ("Attribute", attribute), ("Description", text),
            ("bDisplayAsPercentage", True), ("bDisplayPercentAsFloat", False),
            ("bDisplayAsInverse", inverse), ("bDontDisplayPlusSign", name == "SR_FireRate"),
            ("bEnableTextColor", True), ("bUseCustomNumberPlacement", True),
        ):
            if getattr(presentation, field) != value:
                setattr(presentation, field, value)
        presentations.append(presentation)
    # A legacy damage-triggered instance must not keep regenerating after enable.
    try:
        old_active = unrealsdk.find_object("SkillDefinition", TYRANNOSAURUS_OLD_ACTIVE)
    except ValueError:
        old_active = None
    if old_active is not None:
        old_effects = list(old_active.SkillEffectDefinitions)
        replacements = [_tuned_effect(effect, TYRANNOSAURUS_OLD_ACTIVE) for effect in old_effects]
        if any(item is not None for item in replacements):
            old_active.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                                for old, new in zip(old_effects, replacements)]
    # Commit gameplay only after all attributes/effects/presentations are ready.
    if new_effects is not None:
        definition.SkillEffectDefinitions = new_effects
    # The native skill-tree/action manager owns Gunzerking activation and grades.
    for field, value in (
        ("SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_ActionAugment),
        ("BehaviorProviderDefinition", None), ("TrackedActiveSkill", None),
        ("SkillDescription", TYRANNOSAURUS_DESCRIPTION),
    ):
        if getattr(definition, field) != value:
            setattr(definition, field, value)
    for field in ("DamageEvents", "TrackedActiveSkills"):
        if getattr(definition, field):
            setattr(definition, field, [])
    if originals != presentations:
        definition.SkillEffectPresentations = presentations
    return (definition, old_active) if old_active is not None else (definition,)


def _ensure_offhand_pair(definition: Any, primary_path: str, offhand_path: str) -> bool:
    """Copy only a missing context; never evaluate formulas or replace a valid pair."""
    effects = list(definition.SkillEffectDefinitions)
    offhand = [effect for effect in effects if _path(effect.AttributeToModify) == offhand_path]
    if len(offhand) > 1:
        raise ValueError(f"Duplicate off-hand effects in {_path(definition)}")
    if offhand:
        return False
    primary = [effect for effect in effects if _path(effect.AttributeToModify) == primary_path]
    if len(primary) != 1:
        raise ValueError(f"Expected one primary weapon effect in {_path(definition)}")
    try:
        attribute = unrealsdk.find_object("AttributeDefinition", offhand_path)
    except ValueError:
        return False
    if attribute is None:
        return False
    paired = copy.copy(primary[0])
    paired.AttributeToModify = attribute
    # Keep the initializer/random resolver, modifier mode, grade and conditions.
    definition.SkillEffectDefinitions = [copy.copy(effect) for effect in effects] + [paired]
    return True


def _configure_offhand_pairs() -> tuple[Any, ...]:
    definitions = []
    for path, pair in OFFHAND_PAIRS.items():
        if path == JUST_GOT_REAL_PATH:
            continue  # Its numeric tuning already performs this repair.
        try:
            definition = unrealsdk.find_object("SkillDefinition", path)
        except ValueError:
            continue
        if definition is None:
            continue
        try:
            _ensure_offhand_pair(definition, *pair)
            definitions.append(definition)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _report_error(f"Could not pair off-hand effects for {path}", exc)
    return tuple(definitions)


def _owned_initializer(owner: Any, name: str) -> Any:
    outer_path = _path(owner)
    path = outer_path + ("." if ":" in outer_path else ":") + name
    try:
        result = unrealsdk.find_object("AttributeInitializationDefinition", path)
    except ValueError:
        result = None
    if result is None:
        result = unrealsdk.construct_object("AttributeInitializationDefinition", owner, name)
    return result


def _pistol_initializer(owner: Any, name: str, pistol: Any, coefficient: Any) -> tuple[Any, bool]:
    initializer = _owned_initializer(owner, name)
    formula = initializer.ValueFormula
    values = (("Multiplier", 0.0, pistol), ("Level", 0.0, coefficient),
              ("Power", 1.0, None), ("Offset", 0.0, None))
    matches = bool(formula.bEnabled)
    for field, constant, attribute in values:
        value = getattr(formula, field)
        matches = (matches and math.isclose(float(value.BaseValueConstant), constant, abs_tol=1e-7)
                   and value.BaseValueAttribute == attribute and value.InitializationDefinition is None
                   and math.isclose(float(value.BaseValueScaleConstant), 1.0, abs_tol=1e-7))
    changed = not matches
    if changed:
        formula = copy.copy(formula)
        formula.bEnabled = True
        for field, constant, attribute in values:
            value = copy.copy(getattr(formula, field))
            value.BaseValueConstant = constant
            value.BaseValueAttribute = attribute
            value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0
            setattr(formula, field, value)
        initializer.ValueFormula = formula
    # A new native definition defaults to no randomization or range clamp.
    return initializer, changed


def _huckleberry_effect(template: Any, attribute: Any, initializer: Any,
                        coefficient: Any, display_only: bool) -> Any | None:
    target = (unrealsdk.find_enum("EEffectTarget").TARGET_None if display_only
              else unrealsdk.find_enum("EEffectTarget").TARGET_Self)
    mode = unrealsdk.find_enum("EModifierType").MT_Scale
    matches = (template.AttributeToModify == attribute and template.EffectTarget == target
               and template.ModifierType == mode and int(template.GradeToStartApplyingEffect) == 1
               and int(template.PerGradeUpgradeInterval) == 1 and not template.BonusUpgradeList)
    for value in (template.BaseModifierValue, template.PerGradeUpgrade):
        matches = (matches and math.isclose(float(value.BaseValueConstant), 0.0, abs_tol=1e-7)
                   and value.BaseValueAttribute == coefficient
                   and value.InitializationDefinition == initializer
                   and math.isclose(float(value.BaseValueScaleConstant), 1.0, abs_tol=1e-7))
    if matches:
        return None
    result = copy.copy(template)
    result.AttributeToModify, result.EffectTarget, result.ModifierType = attribute, target, mode
    result.GradeToStartApplyingEffect = result.PerGradeUpgradeInterval = 1
    result.BonusUpgradeList = []
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(result, field))
        value.BaseValueConstant = 0.0
        value.BaseValueAttribute = coefficient
        value.InitializationDefinition = initializer
        value.BaseValueScaleConstant = 1.0
        setattr(result, field, value)
    return result


def _configure_huckleberry() -> tuple[Any, ...] | None:
    global _huckleberry_revision
    try:
        definition = unrealsdk.find_object("SkillDefinition", HUCKLEBERRY_PATH)
        targets = [unrealsdk.find_object("AttributeDefinition", path) for path in HUCKLEBERRY_TARGETS]
        pistols = [unrealsdk.find_object("AttributeDefinition", path) for path in HUCKLEBERRY_PISTOL_ATTRIBUTES]
        coefficients = [unrealsdk.find_object("AttributeDefinition", path) for path in HUCKLEBERRY_COEFFICIENTS]
    except ValueError:
        return None
    if definition is None or any(item is None for item in targets + pistols + coefficients):
        return None
    originals = list(definition.SkillEffectDefinitions)
    if not originals:
        raise ValueError("I'm Your Huckleberry has no native effect template")
    initializers = []
    formula_changed = False
    for hand, pistol in enumerate(pistols):
        for stat, coefficient in enumerate(coefficients):
            initializer, changed = _pistol_initializer(definition, f"SR_Pistol_{hand}_{stat}",
                                                       pistol, coefficient)
            initializers.append(initializer)
            formula_changed |= changed
    managed_paths = set(HUCKLEBERRY_TARGETS + HUCKLEBERRY_COEFFICIENTS)
    # Own four gated effects; keep unrelated effects from other integrations.
    desired = [effect for effect in originals
               if _path(effect.AttributeToModify) not in managed_paths]
    specs: list[tuple[Any, Any | None, Any | None, bool]] = [(attribute, initializer, None, False)
             for attribute, initializer in zip(targets, initializers)]
    specs.extend((attribute, None, attribute, True) for attribute in coefficients)
    effect_changed = False
    for attribute, initializer, coefficient, display_only in specs:
        matches = [effect for effect in originals if effect.AttributeToModify == attribute]
        candidate = matches[0] if matches else originals[0]
        replacement = _huckleberry_effect(candidate, attribute, initializer, coefficient, display_only)
        desired.append(replacement if replacement is not None else candidate)
        effect_changed |= replacement is not None or len(matches) != 1
    paths_changed = (tuple(_path(effect.AttributeToModify) for effect in originals)
                     != tuple(_path(effect.AttributeToModify) for effect in desired))
    constraints = list(definition.SkillConstraints)
    kept = []
    for constraint in constraints:
        evaluator = constraint.Evaluator
        expression = getattr(evaluator, "Expression", None) if evaluator is not None else None
        if expression is not None and _path(expression.AttributeOperand1) in HUCKLEBERRY_PISTOL_ATTRIBUTES:
            continue  # Gate each weapon in its own effect instead of pausing the whole skill.
        kept.append(constraint)
    try:
        legacy = unrealsdk.find_object("SkillDefinition", HUCKLEBERRY_OLD_OFFHAND)
    except ValueError:
        legacy = None
    if legacy is not None:
        old = list(legacy.SkillEffectDefinitions)
        replacements = [_tuned_effect(effect, HUCKLEBERRY_OLD_OFFHAND) for effect in old]
        if any(item is not None for item in replacements):
            legacy.SkillEffectDefinitions = [copy.copy(new if new is not None else previous)
                                            for previous, new in zip(old, replacements)]
    if effect_changed or paths_changed:
        definition.SkillEffectDefinitions = [copy.copy(effect) for effect in desired]
    if len(kept) != len(constraints):
        definition.SkillConstraints = [copy.copy(item) for item in kept]
    if definition.BehaviorProviderDefinition is not None:
        definition.BehaviorProviderDefinition = None  # Retire native parent-to-child activation.
    children = list(definition.TrackedActiveSkills)
    remaining = [child for child in children if _path(child) != HUCKLEBERRY_OLD_OFFHAND]
    if children != remaining:
        definition.TrackedActiveSkills = remaining
    if _path(definition.TrackedActiveSkill) == HUCKLEBERRY_OLD_OFFHAND:
        definition.TrackedActiveSkill = None
    # Ungated helpers keep both native stat lines correct even with no pistol held.
    for presentation in definition.SkillEffectPresentations:
        path = _path(presentation)
        attribute = (coefficients[1] if path.endswith(":AttributePresentationDefinition_0")
                     else coefficients[0] if path.endswith(":AttributePresentationDefinition_1") else None)
        if attribute is not None and presentation.Attribute != attribute:
            presentation.Attribute = attribute
    if formula_changed or effect_changed or paths_changed:
        _huckleberry_revision += 1
    return (definition, legacy) if legacy is not None else (definition,)


def _configure_bus_position() -> Any | None:
    global _bus_position_configured
    branch = _find_piping_object("SkillTreeBranchDefinition", BRAWN_BRANCH_PATH)
    layout = _find_piping_object("SkillTreeBranchLayoutDefinition", BRAWN_LAYOUT_PATH)
    if branch is None or layout is None:
        return None
    signature = (branch._get_address(), layout._get_address())
    if _bus_position_configured == signature:
        return _find_piping_object("SkillDefinition", BUS_PATH)
    if len(branch.Tiers) != 6 or len(layout.Tiers) != 6:
        raise ValueError("Brawn skill tree must have six tiers")
    rows = [tuple(_path(skill) for skill in tier.Skills) for tier in branch.Tiers]
    neighbors = (ASBESTOS_PATH, JUGGERNAUT_PATH)
    native = (neighbors, (BUS_PATH, JUST_GOT_REAL_PATH))
    moved = ((neighbors[0], BUS_PATH, neighbors[1]), (JUST_GOT_REAL_PATH,))
    cells = (tuple(bool(cell) for cell in layout.Tiers[1].bCellIsOccupied),
             tuple(bool(cell) for cell in layout.Tiers[3].bCellIsOccupied))
    if ((rows[1], rows[3]) not in (native, moved)
            or cells[0] not in ((True, False, True), (True, True, True))
            or cells[1] not in ((True, True, False), (False, True, False))
            or any(BUS_PATH in row for i, row in enumerate(rows) if i not in (1, 3))):
        raise ValueError("Brawn positions conflict with the Bus relocation")
    if (rows[1], rows[3]) == native:
        tiers = [copy.copy(tier) for tier in branch.Tiers]
        bus, just_got_real = list(tiers[3].Skills)
        asbestos, juggernaut = list(tiers[1].Skills)
        tiers[1].Skills = [asbestos, bus, juggernaut]
        tiers[3].Skills = [just_got_real]
        branch.Tiers = tiers
    desired_cells = ((True, True, True), (False, True, False))
    if cells != desired_cells:
        tiers = [copy.copy(tier) for tier in layout.Tiers]
        tiers[1].bCellIsOccupied = list(desired_cells[0])
        tiers[3].bCellIsOccupied = list(desired_cells[1])
        layout.Tiers = tiers
    actual = (tuple(_path(skill) for skill in branch.Tiers[1].Skills),
              tuple(_path(skill) for skill in branch.Tiers[3].Skills))
    if actual != moved:
        raise RuntimeError("Bus relocation did not retain the requested skill positions")
    _bus_position_configured = signature
    return branch.Tiers[1].Skills[1]


def _configure_quick_draw() -> Any | None:
    try:
        definition = unrealsdk.find_object("SkillDefinition", QUICK_DRAW_PATH)
    except ValueError:
        return None
    if definition is None:
        return None
    effects = list(definition.SkillEffectDefinitions)
    if sum(_path(effect.AttributeToModify) == TYRANNOSAURUS_CRIT_ATTRIBUTE for effect in effects) != 1:
        raise ValueError("Quick Draw must have one native critical-hit damage effect")
    if sum(_path(effect.AttributeToModify) == QUICK_DRAW_SWAP_ATTRIBUTE for effect in effects) != 1:
        raise ValueError("Quick Draw must have one native weapon-swap effect")
    updated = [_tuned_effect(effect, QUICK_DRAW_PATH) for effect in effects]
    if any(effect is not None for effect in updated):
        definition.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                            for old, new in zip(effects, updated)]
    return definition


def _configure_auto_loader() -> Any | None:
    try:
        definition = unrealsdk.find_object("SkillDefinition", AUTO_LOADER_PATH)
        attributes = [unrealsdk.find_object("AttributeDefinition", path)
                      for path in AUTO_LOADER_RELOAD_ATTRIBUTES]
    except ValueError:
        return None
    if definition is None or any(attribute is None for attribute in attributes):
        return None
    effects = list(definition.SkillEffectDefinitions)
    presentations = list(definition.SkillEffectPresentations)
    if not effects or not presentations:
        raise ValueError("Auto-Loader native effect/presentation template is missing")
    # Preserve the original display effect and reload-on-kill behavior unchanged.
    kept = [effect for effect in effects
            if _path(effect.AttributeToModify) not in AUTO_LOADER_RELOAD_ATTRIBUTES]
    desired = list(kept)
    changed = False
    for attribute in attributes:
        existing = [effect for effect in effects if effect.AttributeToModify == attribute]
        candidate = existing[0] if existing else copy.copy(effects[0])
        if not existing:
            candidate.AttributeToModify = attribute
        tuned = _tuned_effect(candidate, AUTO_LOADER_PATH)
        desired.append(tuned if tuned is not None else candidate)
        changed |= tuned is not None or len(existing) != 1
    path = AUTO_LOADER_PATH + ":SR_AutoLoaderReload"
    # The negative native reload-time coefficient is gameplay data. Display a
    # positive speed bonus in the footer without changing that coefficient.
    kept_presentations = [item for item in presentations
                          if _path(item.Attribute) not in AUTO_LOADER_RELOAD_ATTRIBUTES
                          and _path(item) != path]
    if changed or tuple(_path(item.AttributeToModify) for item in effects) != tuple(
            _path(item.AttributeToModify) for item in desired):
        definition.SkillEffectDefinitions = [copy.copy(item) for item in desired]
    if presentations != kept_presentations:
        definition.SkillEffectPresentations = kept_presentations
    if str(definition.SkillDescription) != AUTO_LOADER_DESCRIPTION:
        definition.SkillDescription = AUTO_LOADER_DESCRIPTION
    return definition


def _configure_piping_hot() -> tuple[Any, ...] | None:
    try:
        definition = unrealsdk.find_object("SkillDefinition", PIPING_HOT_PATH)
        attributes = [unrealsdk.find_object("AttributeDefinition", path)
                      for path in PIPING_HOT_TARGETS]
    except ValueError:
        return None
    if definition is None or any(attribute is None for attribute in attributes):
        return None
    effects = list(definition.SkillEffectDefinitions)
    originals = list(definition.SkillEffectPresentations)
    if not effects or not originals:
        raise ValueError("Keep It Piping Hot native templates are missing")
    try:
        helper = unrealsdk.find_object("SkillDefinition", PIPING_HOT_HELPER)
    except ValueError:
        helper = None
    if helper is None:
        helper = unrealsdk.construct_object("SkillDefinition", definition, "SR_PipingHotStacks")
    # Parent has display-only rank coefficients. Only the private helper applies damage/spread.
    for target_definition, path, selected in (
        (definition, PIPING_HOT_PATH, attributes[::2]),
        (helper, PIPING_HOT_HELPER, attributes),
    ):
        current = list(target_definition.SkillEffectDefinitions)
        desired = []
        changed = False
        for attribute in selected:
            matches = [effect for effect in current if effect.AttributeToModify == attribute]
            candidate = copy.copy(matches[0] if matches else effects[0])
            candidate.AttributeToModify = attribute
            tuned = _tuned_effect(candidate, path)
            desired.append(tuned if tuned is not None else candidate)
            changed |= tuned is not None or len(matches) != 1
        if changed or len(current) != len(desired):
            target_definition.SkillEffectDefinitions = [copy.copy(item) for item in desired]
    # Remove the two native cooldown constraints, preserving on-foot/custom constraints.
    constraints = list(definition.SkillConstraints)
    kept = [copy.copy(item) for item in constraints if _path(item.Evaluator) not in (
        PIPING_HOT_PATH + ":AttributeExpressionEvaluator_20",
        PIPING_HOT_PATH + ":AttributeExpressionEvaluator_21",
    )]
    if len(kept) != len(constraints):
        definition.SkillConstraints = kept
    for obj, values in (
        (definition, (("SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_ActionAugment),
                      ("SkillDescription", PIPING_HOT_DESCRIPTION))),
        (helper, (("SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive),
                  ("DurationType", unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite),
                  ("bSubjectToGradeRules", False), ("bAutoUpdateContexts", True),
                  ("SkillEffectUpdateIterval", 0.5), ("SkillName", "Keep It Piping Hot - stacks"))),
    ):
        for field, value in (*values,
                             ("TrackedSkillType", unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked),
                             ("BehaviorProviderDefinition", None), ("TrackedActiveSkill", None)):
            if getattr(obj, field) != value:
                setattr(obj, field, value)
        for field in ("DamageEvents", "KillEvents", "TrackedActiveSkills"):
            if getattr(obj, field):
                setattr(obj, field, [])
    if helper.SkillConstraints:
        helper.SkillConstraints = []
    if helper.SkillEffectPresentations:
        helper.SkillEffectPresentations = []
    presentations = []
    for name, attribute, text, inverse in (
        ("SR_PipingHotDamage", attributes[0], "Gun Damage per stack: $NUMBER$", False),
        ("SR_PipingHotAccuracy", attributes[2], "Accuracy per stack: $NUMBER$", True),
    ):
        try:
            presentation = unrealsdk.find_object("AttributePresentationDefinition", PIPING_HOT_PATH + ":" + name)
        except ValueError:
            presentation = None
        if presentation is None:
            presentation = unrealsdk.construct_object(
                "AttributePresentationDefinition", definition, name, template_obj=originals[0])
        for field, value in (
            ("Attribute", attribute), ("Description", text), ("bDisplayAsPercentage", True),
            ("bDisplayPercentAsFloat", True), ("bDisplayAsInverse", inverse),
            ("bDontDisplayNumber", False), ("bDontDisplayPlusSign", False),
            ("bEnableTextColor", True), ("bUseCustomNumberPlacement", True),
        ):
            if getattr(presentation, field) != value:
                setattr(presentation, field, value)
        presentations.append(presentation)
    if originals != presentations:
        definition.SkillEffectPresentations = presentations
    return definition, helper


def _format_salvador_rank_value(tree: Any, args: Any, value: str) -> str:
    if not args.bIncludeHTML:
        return value
    rank = max(0, int(args.Grade))
    owner = getattr(args, "PlayerOwner", None)
    invested = max(0, rank - max(0, int(args.GradeModifier)))
    current_invested = int(owner.GetSkillGrade(args.SkillDef)) if owner is not None else 0
    if invested >= 5 and current_invested >= 5:
        return f'<font color="#00FF00">{value}</font>'
    color = getattr(tree, "SkillIntermediateGradeColor", None)
    style = str(getattr(tree, "SkillLockedModifierTextHTML", ""))
    if rank > 0 and current_invested > 0 and color is not None:
        channels = tuple(int(getattr(color, channel)) for channel in ("R", "G", "B"))
        if all(0 <= channel <= 255 for channel in channels) and "%c" in style and "%s" in style:
            rgb = "".join(f"{channel:02X}" for channel in channels)
            return style.replace("%c", rgb).replace("%s", value)
    return value


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_piping_hot(tree: Any, args: Any, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or _path(args.SkillDef) != PIPING_HOT_PATH:
        return None
    # The queried Grade already contains COM points; never add GradeModifier again.
    rank = max(0, int(args.Grade))
    value = _format_salvador_rank_value(tree, args, f"+{100 * PIPING_HOT_PER_RANK * rank:g}%")
    separator = "<br>" if args.bIncludeHTML else "\n"
    return Block, separator.join((f"Gun Damage per Stack: {value}", f"Accuracy per Stack: {value}"))



def _find_piping_object(kind: str, path: str) -> Any | None:
    try:
        return unrealsdk.find_object(kind, path)
    except ValueError:
        return None


def _set_piping_property(obj: Any, field: str, value: Any) -> None:
    if getattr(obj, field) != value:
        setattr(obj, field, value)


def _piping_hot_hud_definition(definition: Any) -> Any | None:
    global _piping_hot_hud_ready
    if definition.SkillIcon is None:
        return None
    feedback = _find_piping_object("SkillDefinition", PIPING_HOT_HUD)
    if feedback is None:
        _piping_hot_hud_ready = False
        feedback = unrealsdk.construct_object(
            "SkillDefinition", definition, "SR_PipingHotHUD", template_obj=definition)
    if _piping_hot_hud_ready:
        return feedback
    for field, value in (
        ("SkillName", "Keep It Piping Hot stacks"), ("SkillIcon", definition.SkillIcon),
        ("SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive),
        ("DurationType", unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite),
        ("TrackedSkillType", unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered),
        ("bSubjectToGradeRules", False), ("MaxGrade", PIPING_HOT_STACK_LIMIT),
        ("InitialDuration", 0.0), ("BehaviorProviderDefinition", None), ("TrackedActiveSkill", None),
    ):
        _set_piping_property(feedback, field, value)
    for field in ("SkillEffectDefinitions", "SkillEffectPresentations", "SkillConstraints",
                  "DamageEvents", "KillEvents", "TrackedActiveSkills"):
        if getattr(feedback, field):
            setattr(feedback, field, [])
        if getattr(feedback, field):
            raise RuntimeError(f"Keep It Piping Hot HUD retained gameplay data: {field}")
    count = _find_piping_object("AttributeDefinition", PIPING_HOT_HUD + ".StackCount")
    if count is None:
        count = unrealsdk.construct_object("AttributeDefinition", feedback, "StackCount")
    context = _find_piping_object("SkillAttributeContextResolver", PIPING_HOT_HUD + ".StackCount.SkillContext")
    if context is None:
        context = unrealsdk.construct_object("SkillAttributeContextResolver", count, "SkillContext")
    resolver = _find_piping_object("ObjectPropertyAttributeValueResolver", PIPING_HOT_HUD + ".StackCount.GradeValue")
    if resolver is None:
        resolver = unrealsdk.construct_object("ObjectPropertyAttributeValueResolver", count, "GradeValue")
    _set_piping_property(context, "AssociatedSkill", feedback)
    _set_piping_property(resolver, "PropertyName", "Grade")
    _set_piping_property(count, "bIsSimpleAttribute", True)
    _set_piping_property(count, "AttributeDataType", unrealsdk.find_enum("EAttributeDataType").ADT_Int)
    if list(count.ContextResolverChain) != [context]:
        count.ContextResolverChain = [context]
    if list(count.ValueResolverChain) != [resolver]:
        count.ValueResolverChain = [resolver]
    _set_piping_property(feedback, "CustomStackCount", count)
    if list(count.ContextResolverChain) != [context] or list(count.ValueResolverChain) != [resolver]:
        raise RuntimeError("Keep It Piping Hot HUD counter resolvers were not retained")
    _piping_hot_hud_ready = True
    return feedback


def _piping_hot_hud_free_slot(controller: Any, movie: Any, feedback: Any) -> int | None:
    occupied: set[int] = set()
    visited: set[str] = set()
    native_row_types = {2, 3, 5, 6}  # Triggered/Respond/MeleeOverride/TriggeredNotSkillTree.

    def reserve(definition: Any) -> None:
        if definition is None or definition == feedback:
            return
        path = str(definition._path_name())
        if path in visited:
            return
        if len(visited) >= 512:
            raise RuntimeError("Unexpectedly large tracked-skill graph; HUD allocation cancelled")
        visited.add(path)
        if int(definition.TrackedSkillType) in native_row_types:
            occupied.add(int(definition.TrackedSkillHUDSlot))
            mapped = int(movie.GetRemappedSlot(definition))
            if mapped >= 0:
                occupied.add(mapped)
        reserve(definition.TrackedActiveSkill)
        for child in definition.TrackedActiveSkills:
            reserve(child)

    for entry in movie.AvailableTrackedSkills:
        if entry.SkillDef is not None and entry.SkillDef != feedback:
            reserve(entry.SkillDef)  # Includes inactive and grade-zero registered children.
            if int(entry.SkillDef.TrackedSkillType) in native_row_types and int(entry.RemappedSlot) >= 0:
                occupied.add(int(entry.RemappedSlot))
    for item in controller.PlayerSkillTree.Skills:
        if int(item.Grade) > 0:
            reserve(item.Definition)
    own_active = False
    for skill in controller.GetSkillManager().ActiveSkills:
        reserve(skill.Definition)
        if skill.Definition == feedback and skill.SkillInstigator == controller:
            own_active = True
    own_slot = int(movie.GetRemappedSlot(feedback))
    for index, state in enumerate(movie.CachedTSkillIcon_TrigResp):
        if state.Icon is not None and not (own_active and index == own_slot and state.Icon == feedback.SkillIcon):
            occupied.add(index)
    capacity = min(11, len(movie.CachedTSkillIcon_TrigResp))
    preferred = int(feedback.TrackedSkillHUDSlot)
    if 0 <= preferred < capacity and preferred not in occupied:
        return preferred
    return next((slot for slot in range(capacity) if slot not in occupied), None)


def _prepare_piping_hot_hud_slot(
    controller: Any, movie: Any, feedback: Any, label: str = "Keep It Piping Hot",
) -> bool:
    manager = controller.GetSkillManager()
    active = any(s.Definition == feedback and s.SkillInstigator == controller for s in manager.ActiveSkills)
    path = _path(feedback)
    identity = (int(controller._get_address()), int(controller.WorldInfo._get_address()), int(movie._get_address()))
    now = time.monotonic()
    cached = _hud_allocation_checks.get(path)
    if active and cached is not None and cached[0] == identity and 0. <= cached[1] - now <= 1.:
        slot = cached[2]
        conflicting = any(entry.SkillDef is not None and entry.SkillDef != feedback
            and int(entry.SkillDef.TrackedSkillType) in (2, 3, 5, 6) and int(entry.RemappedSlot) == slot
            for entry in movie.AvailableTrackedSkills)
        if (not conflicting and int(movie.GetRemappedSlot(feedback)) == slot
                and int(feedback.TrackedSkillHUDSlot) == slot
                and 0 <= slot < len(movie.CachedTSkillIcon_TrigResp)
                and movie.CachedTSkillIcon_TrigResp[slot].Icon == feedback.SkillIcon):
            return True
    _hud_allocation_checks.pop(path, None)
    slot = _piping_hot_hud_free_slot(controller, movie, feedback)
    if slot is None or (active and (int(feedback.TrackedSkillHUDSlot) != slot
                                   or int(movie.GetRemappedSlot(feedback)) != slot)):
        if active:
            reference = WeakPointer(controller)
            owner = (identity[0], identity[1], int(controller.Pawn._get_address()))
            manager.DeactivateSkill(controller, feedback)  # Never the gameplay helper.
            recovered = _recover_skill_owner(reference, owner)
            if recovered is None:
                return False
            controller, manager = recovered
            movie = controller.GetHUDMovie()
            if movie is None or int(movie._get_address()) != identity[2]:
                return False
            movie.UpdateSkillIcons()
            slot = _piping_hot_hud_free_slot(controller, movie, feedback)
        if slot is None:
            key = f"{label} HUD full"
            if key not in _reported_errors:
                _reported_errors.add(key)
                unrealsdk.logging.info(f"[SalvadorRebalance] {label} HUD hidden: no free native slot; bonuses unchanged")
            return False
    _set_piping_property(feedback, "TrackedSkillHUDSlot", slot)
    if not any(entry.SkillDef == feedback for entry in movie.AvailableTrackedSkills):
        movie.AddTrackedSkill(feedback)
        # Native registration may remap other entries. Re-evaluate the ACTUAL
        # post-registration state, not a stale list of free slots.
        slot = _piping_hot_hud_free_slot(controller, movie, feedback)
        if slot is None:
            return False
        _set_piping_property(feedback, "TrackedSkillHUDSlot", slot)
    if int(movie.GetRemappedSlot(feedback)) != slot:
        entries = [copy.copy(entry) for entry in movie.AvailableTrackedSkills]
        for entry in entries:
            if entry.SkillDef == feedback:
                entry.RemappedSlot = slot
                movie.AvailableTrackedSkills = entries
                break
        else:
            raise RuntimeError(f"{label} HUD feedback has no native registration")
        if int(movie.GetRemappedSlot(feedback)) != slot:
            raise RuntimeError(f"{label} HUD did not retain its non-overlapping slot")
    # Native rendering ignores registered slots outside this purchased prefix.
    # Increase it only as needed; never shrink/reassign another skill's range.
    purchased = max(int(movie.NumPurchasedTrigRespSlots), slot + 1)
    if purchased > len(movie.CachedTSkillIcon_TrigResp):
        raise RuntimeError(f"{label} HUD purchased range exceeds native capacity")
    _set_piping_property(movie, "NumPurchasedTrigRespSlots", purchased)
    _hud_allocation_checks[path] = (identity, now + 1., slot)
    return True


def _sync_piping_hot_hud(controller: Any, count: int) -> None:
    """Visual failure must never interrupt gameplay, grades or end-of-action cleanup."""
    if controller is None:
        return
    try:
        feedback = _find_piping_object("SkillDefinition", PIPING_HOT_HUD)
        if count <= 0 and feedback is None:
            return
        manager = controller.GetSkillManager()
        if manager is None or manager.bUpdatingSkills:
            return
        reference = WeakPointer(controller)
        identity = (int(controller._get_address()), int(controller.WorldInfo._get_address()), int(controller.Pawn._get_address()))
        instances = [s for s in manager.ActiveSkills
                     if s.Definition == feedback and s.SkillInstigator == controller]
        if count <= 0:
            if instances:
                manager.DeactivateSkill(controller, feedback)
                recovered = _recover_skill_owner(reference, identity)
                if recovered is None:
                    return
                controller, manager = recovered
                movie = controller.GetHUDMovie()
                if movie is not None:
                    movie.UpdateSkillIcons()
            return
        # Show the count that was actually applied, not just the requested elapsed time.
        gameplay = next((s for s in manager.ActiveSkills if s.SkillInstigator == controller
                         and _path(s.Definition) == PIPING_HOT_HELPER), None)
        if gameplay is None or int(gameplay.Grade) <= 0:
            return
        movie = controller.GetHUDMovie()
        if movie is None:
            return
        if feedback is None or not _piping_hot_hud_ready:
            definition = unrealsdk.find_object("SkillDefinition", PIPING_HOT_PATH)
            feedback = _piping_hot_hud_definition(definition)
        if feedback is None or not _prepare_piping_hot_hud_slot(controller, movie, feedback):
            return
        instances = [s for s in manager.ActiveSkills
                     if s.Definition == feedback and s.SkillInstigator == controller]
        changed = False
        if not instances:
            if manager.ActivateSkill(controller, feedback, None, count) is False:
                raise RuntimeError("Keep It Piping Hot HUD activation was rejected")
            changed = True
        elif len(instances) != 1:
            raise RuntimeError("Keep It Piping Hot HUD has duplicate instances")
        elif int(instances[0].Grade) != count:
            instances[0].UpdateGrade(count)
            changed = True
        if changed:
            recovered = _recover_skill_owner(reference, identity)
            if recovered is None:
                return
            controller, manager = recovered
            movie = controller.GetHUDMovie()
            if movie is None:
                return
        slot = int(movie.GetRemappedSlot(feedback))
        if changed or not (0 <= slot < len(movie.CachedTSkillIcon_TrigResp)
                           and movie.CachedTSkillIcon_TrigResp[slot].Icon == feedback.SkillIcon):
            movie.UpdateSkillIcons()
        key = "Keep It Piping Hot native HUD"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(f"[SalvadorRebalance] {key}: slot={slot}, stacks={count}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not update Keep It Piping Hot HUD", exc)


def _sync_piping_hot(controller: Any, manager: Any, rank: int, parent: Any,
                     helpers: list[Any]) -> None:
    global _piping_hot_session
    world, pawn = controller.WorldInfo, controller.Pawn
    context = (controller._get_address(), world._get_address(), pawn._get_address())
    reference = WeakPointer(controller)
    now = float(world.TimeSeconds)
    if parent is None or rank <= 0 or pawn.IsInjuredDead():
        _piping_hot_session = None
        combined = 0
    else:
        if _piping_hot_session is None or _piping_hot_session[:3] != context:
            # Recovery if enabled mid-Gunzerking; ActivatedTime belongs to the active parent.
            start = min(now, max(0.0, float(parent.ActivatedTime)))
            _piping_hot_session = (*context, start)
        elapsed = max(0.0, now - _piping_hot_session[3])
        combined = min(PIPING_HOT_STACK_LIMIT, int(elapsed + 1e-6)) * rank
    if combined <= 0:
        if helpers:
            manager.DeactivateSkill(controller, helpers[0].Definition)
            recovered = _recover_skill_owner(reference, context)
            if recovered is None:
                return
            controller, manager = recovered
        _sync_piping_hot_hud(controller, 0)
        return
    if len(helpers) > 1:
        manager.DeactivateSkill(controller, helpers[0].Definition)
        return  # Reconcile duplicates from a fresh snapshot next maintenance.
    mutated = False
    if not helpers:
        helper = unrealsdk.find_object("SkillDefinition", PIPING_HOT_HELPER)
        if manager.ActivateSkill(controller, helper, None, combined) is False:
            raise RuntimeError("Keep It Piping Hot stack activation was rejected")
        mutated = True
    elif int(helpers[0].Grade) != combined:
        helpers[0].UpdateGrade(combined)
        mutated = True
    if mutated:
        recovered = _recover_skill_owner(reference, context)
        if recovered is None:
            return
        controller, manager = recovered
        helpers = [s for s in manager.ActiveSkills if s.SkillInstigator == controller
                   and _path(s.Definition) == PIPING_HOT_HELPER]
    if len(helpers) != 1 or int(helpers[0].Grade) != combined:
        raise RuntimeError("Keep It Piping Hot did not retain its requested stack grade")
    count = combined // rank
    if count in (1, 10, 25, 50) and (rank, count) not in _piping_hot_logged:
        _piping_hot_logged.add((rank, count))
        unrealsdk.logging.info(
            f"[SalvadorRebalance] Keep It Piping Hot applied: rank={rank}, stacks={count}, "
            f"combined_grade={combined}, gun_damage={combined * PIPING_HOT_PER_RANK:g}, "
            f"spread_modifier={-combined * PIPING_HOT_PER_RANK:g}")
    _sync_piping_hot_hud(controller, count)


@hook("WillowGame.WillowPlayerController:ActionSkillCallback", Type.POST)
def piping_hot_action_changed(controller: Any, args: Any, _ret: Any, _func: Any) -> None:
    global _piping_hot_session, _next_maintenance, _yippee_crit_last
    try:
        if (controller is None or controller != get_pc(possibly_loading=True) or controller.bDeleteMe
                or _path(controller.PlayerClass) != PLAYER_CLASS
                or args.ActivatedSkill is None or _path(args.ActivatedSkill.Definition) != GUNZERKING_PATH):
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe:
            return
        context = (controller._get_address(), world._get_address())
        if _departing_context in (context, (context[0], 0)) or pawn.Controller != controller:
            return
        _next_maintenance = 0.0
        if args.bActivated:
            # Repeated activation notifications must not restart the same session.
            identity = (*context, pawn._get_address())
            if _piping_hot_session is None or _piping_hot_session[:3] != identity:
                _piping_hot_session = (*identity, float(world.TimeSeconds))
                _yippee_crit_last = None
        else:
            _yippee_crit_last = None
            _piping_hot_session = None
            manager = controller.GetSkillManager()
            if manager is not None and not manager.bUpdatingSkills:
                helpers = [s for s in manager.ActiveSkills if s.SkillInstigator == controller
                           and _path(s.Definition) == PIPING_HOT_HELPER]
                if helpers:
                    reference = WeakPointer(controller)
                    identity = (*context, int(pawn._get_address()))
                    manager.DeactivateSkill(controller, helpers[0].Definition)
                    recovered = _recover_skill_owner(reference, identity)
                    if recovered is None:
                        return
                    controller, manager = recovered
                _sync_piping_hot_hud(controller, 0)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not update Keep It Piping Hot session", exc)


def _configure_asbestos() -> Any | None:
    definition = _find_piping_object("SkillDefinition", ASBESTOS_PATH)
    if definition is not None and str(definition.SkillDescription) != ASBESTOS_DESCRIPTION:
        definition.SkillDescription = ASBESTOS_DESCRIPTION
    return definition  # Native resistance effects, constraints and presentations are untouched.


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_asbestos(tree: Any, args: Any, _ret: Any, func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or _path(args.SkillDef) != ASBESTOS_PATH:
        return None
    with prevent_hooking_direct_calls():
        original = func(args)
    rank = max(0, int(args.Grade))  # Already includes class-mod points.
    value = f"{ASBESTOS_BUFF_DURATION:g} seconds"
    rate = _format_salvador_rank_value(tree, args, f"+{100 * ASBESTOS_FIRE_RATE_PER_RANK * rank:g}%")
    separator = "<br>" if args.bIncludeHTML else "\n"
    return Block, separator.join(text for text in (original, f"Fire Rate: {rate}", f"Duration: {value}") if text)


def _asbestos_controller(*, allow_dead: bool = False) -> Any | None:
    controller = get_pc(possibly_loading=True)
    if controller is None or controller.bDeleteMe or _path(controller.PlayerClass) != PLAYER_CLASS:
        return None
    world, pawn = controller.WorldInfo, controller.Pawn
    if world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe or pawn.Controller != controller:
        return None
    context = (controller._get_address(), world._get_address())
    if _departing_context in (context, (context[0], 0)) or (not allow_dead and pawn.IsInjuredDead()):
        return None
    return controller


def _asbestos_snapshot(component: Any, definition_id: int) -> dict[tuple[Any, ...], int]:
    result: dict[tuple[Any, ...], int] = {}
    for effect in component.ActiveStatusEffects:
        if effect.StatusEffectDefinition is None or effect.StatusEffectDefinition._get_address() != definition_id:
            continue
        signature = (definition_id, float(effect.Duration), float(effect.TotalElapsedTime),
                     effect.EventInstigator._get_address() if effect.EventInstigator else 0,
                     effect.HitRegion._get_address() if effect.HitRegion else 0)
        result[signature] = result.get(signature, 0) + 1
    return result


@hook("WillowGame.StatusEffectsComponent:ApplyStatusEffect", Type.PRE)
def prepare_asbestos_status(component: Any, args: Any, _ret: Any, _func: Any) -> None:
    _asbestos_status_frames.append(None)  # Pair ignored/blocked/nested applications too.
    try:
        if component is None:
            return
        target = component.OwnerTarget
        candidate = getattr(target, "Controller", None)
        if candidate is None or _path(getattr(candidate, "PlayerClass", None)) != PLAYER_CLASS:
            return  # Enemy/world statuses must not query the local player or skill manager.
        controller = _asbestos_controller()
        status_definition = args.StatusEffectDefinition
        if controller is None or target != controller.Pawn or status_definition is None:
            return
        kinds = unrealsdk.find_enum("EStatusEffectType")
        if int(status_definition.StatusEffectType) not in (
            int(kinds.STATUS_EFFECT_Ignite), int(kinds.STATUS_EFFECT_Corrosive),
            int(kinds.STATUS_EFFECT_Shock), int(kinds.STATUS_EFFECT_Amp), int(kinds.STATUS_EFFECT_Slow),
        ):
            return  # Healing/unknown statuses are not elemental afflictions.
        definition = _find_piping_object("SkillDefinition", ASBESTOS_PATH)
        if definition is None or int(controller.GetSkillGrade(definition)) <= 0:
            return
        manager = controller.GetSkillManager()
        if manager is None or manager.bUpdatingSkills:
            return
        active = unrealsdk.find_enum("ESkillState").SKILL_Active
        rank = max((int(skill.Grade) for skill in manager.ActiveSkills
                    if skill.SkillInstigator == controller and skill.Definition == definition
                    and skill.SkillState == active), default=0)
        if rank <= 0:
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if world is None or pawn is None:
            return
        key = (controller._get_address(), world._get_address(), pawn._get_address())
        address = status_definition._get_address()
        _asbestos_status_frames[-1] = dict(component=component._get_address(), context=key,
                                          definition=address, rank=rank,
                                          before=_asbestos_snapshot(component, address))
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not observe Asbestos status application", exc)


@hook("WillowGame.StatusEffectsComponent:ApplyStatusEffect", Type.POST_UNCONDITIONAL)
def finish_asbestos_status(component: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _asbestos_window
    if not _asbestos_status_frames:
        return
    frame = _asbestos_status_frames.pop()
    if frame is None:
        return
    try:
        controller = _asbestos_controller()
        if controller is None or frame["component"] != component._get_address():
            return
        context = (controller._get_address(), controller.WorldInfo._get_address(), controller.Pawn._get_address())
        if context != frame["context"] or component.OwnerTarget != controller.Pawn:
            return
        after = _asbestos_snapshot(component, frame["definition"])
        if not any(count > frame["before"].get(key, 0) for key, count in after.items()):
            return  # A resisted/blocked attempt or a DoT tick grants nothing.
        for parent in _asbestos_status_frames:
            if parent is not None and parent["component"] == frame["component"]:
                parent["before"].update(after)
        duration = ASBESTOS_BUFF_DURATION
        _asbestos_window = (*context, float(controller.WorldInfo.TimeSeconds) + duration)
        _sync_asbestos_bonus(controller, frame["rank"])
        _maintain_asbestos_hud(controller)  # Coalesce only visual maintenance.
        key = "Asbestos fire-rate window confirmed"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(f"[SalvadorRebalance] {key}: rank={frame['rank']}, duration={duration:g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not finish Asbestos status application", exc)


def _asbestos_hud_definition() -> Any | None:
    global _asbestos_hud_ready
    definition = _find_piping_object("SkillDefinition", ASBESTOS_PATH)
    if definition is None or definition.SkillIcon is None:
        return None
    feedback = _find_piping_object("SkillDefinition", ASBESTOS_HUD)
    if feedback is None:
        _asbestos_hud_ready = False
        feedback = unrealsdk.construct_object(
            "SkillDefinition", definition, "SR_AsbestosHUD", template_obj=definition)
    if _asbestos_hud_ready:
        return feedback
    for field, value in (
        ("SkillName", "Asbestos fire-rate window"), ("SkillIcon", definition.SkillIcon),
        ("SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive),
        ("TrackedSkillType", unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered),
        ("DurationType", unrealsdk.find_enum("EEffectDurationType").DURATION_Timed),
        ("bSubjectToGradeRules", False), ("MaxGrade", 1), ("CustomStackCount", None),
        ("BehaviorProviderDefinition", None), ("TrackedActiveSkill", None),
    ):
        _set_piping_property(feedback, field, value)
    for field in ("SkillEffectDefinitions", "SkillEffectPresentations", "SkillConstraints",
                  "DamageEvents", "KillEvents", "TrackedActiveSkills"):
        if getattr(feedback, field):
            setattr(feedback, field, [])
        if getattr(feedback, field):
            raise RuntimeError(f"Asbestos HUD retained gameplay data: {field}")
    _asbestos_hud_ready = True
    return feedback


def _sync_asbestos_hud(controller: Any) -> None:
    global _asbestos_hud_last, _asbestos_window
    try:
        if controller is None or controller != get_pc(possibly_loading=True):
            return
        if _asbestos_controller(allow_dead=True) != controller:
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if world.Pauser or controller.IsPauseMenuOpen():
            return  # Native rendering owns pause visibility; never extend the gameplay window.
        context = (controller._get_address(), world._get_address(), pawn._get_address())
        reference = WeakPointer(controller)
        identity = context
        remaining = (_asbestos_window[3] - float(world.TimeSeconds)
                     if _asbestos_window is not None and _asbestos_window[:3] == context
                     and not pawn.IsInjuredDead() else 0.0)
        if remaining <= 0:
            _asbestos_window = None
        feedback = _find_piping_object("SkillDefinition", ASBESTOS_HUD)
        if remaining <= 0 and feedback is None:
            _asbestos_hud_last = None
            return
        manager = controller.GetSkillManager()
        if manager is None or manager.bUpdatingSkills:
            return
        instances = [s for s in manager.ActiveSkills if s.Definition == feedback and s.SkillInstigator == controller]
        if remaining <= 0:
            if instances:
                manager.DeactivateSkill(controller, feedback)
                recovered = _recover_skill_owner(reference, identity)
                if recovered is None:
                    return
                controller, manager = recovered
                movie = controller.GetHUDMovie()
                if movie is not None:
                    movie.UpdateSkillIcons()
            _asbestos_hud_last = None
            return
        movie = controller.GetHUDMovie()
        if movie is None:
            return
        if feedback is None or not _asbestos_hud_ready:
            feedback = _asbestos_hud_definition()
        if feedback is None or not _prepare_piping_hot_hud_slot(controller, movie, feedback, "Asbestos"):
            return
        instances = [s for s in manager.ActiveSkills if s.Definition == feedback and s.SkillInstigator == controller]
        changed = False
        if instances and _asbestos_hud_last != _asbestos_window:
            manager.DeactivateSkill(controller, feedback)  # Refresh only the visual's native timer.
            recovered = _recover_skill_owner(reference, identity)
            if recovered is None:
                return
            controller, manager = recovered
            movie = controller.GetHUDMovie()
            if movie is None:
                return
            instances = []
        if not instances:
            feedback.InitialDuration = remaining
            if manager.ActivateSkill(controller, feedback, None, 1) is False:
                raise RuntimeError("Asbestos HUD activation was rejected")
            changed = True
        _asbestos_hud_last = _asbestos_window
        if changed:
            recovered = _recover_skill_owner(reference, identity)
            if recovered is None:
                return
            controller, manager = recovered
            movie = controller.GetHUDMovie()
            if movie is None:
                return
        slot = int(movie.GetRemappedSlot(feedback))
        if changed or not (0 <= slot < len(movie.CachedTSkillIcon_TrigResp)
                           and movie.CachedTSkillIcon_TrigResp[slot].Icon == feedback.SkillIcon):
            movie.UpdateSkillIcons()
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not update Asbestos HUD", exc)


def _maintain_asbestos_hud(controller: Any) -> None:
    global _next_asbestos_hud_sync
    state = _asbestos_window if _asbestos_window is not None else _asbestos_hud_last
    if state is None:
        return  # No native queries while this short-lived indicator is unused.
    if controller is None or controller._get_address() != state[0]:
        return  # A remote controller tick must not consume the local retry deadline.
    now = time.monotonic()
    if now < _next_asbestos_hud_sync:
        return
    _next_asbestos_hud_sync = now + 0.1
    try:
        _sync_asbestos_bonus(controller)
        controller = _asbestos_controller(allow_dead=True)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not update Asbestos fire-rate bonus", exc)
    _sync_asbestos_hud(controller)


def _asbestos_bonus_definition() -> Any | None:
    global _asbestos_bonus_ready
    parent = _find_piping_object("SkillDefinition", ASBESTOS_PATH)
    attributes = [_find_piping_object("AttributeDefinition", path) for path in ASBESTOS_FIRE_ATTRIBUTES]
    if parent is None or any(item is None for item in attributes):
        return None
    helper = _find_piping_object("SkillDefinition", ASBESTOS_BONUS)
    if helper is not None and _asbestos_bonus_ready:
        return helper
    if not parent.SkillEffectDefinitions:
        raise ValueError("Asbestos native effect template is missing")
    if helper is None:
        helper = unrealsdk.construct_object("SkillDefinition", parent, "SR_AsbestosFireRate", template_obj=parent)
    effects = []
    for attribute in attributes:
        effect = copy.copy(parent.SkillEffectDefinitions[0])
        effect.AttributeToModify = attribute
        effect.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_Self
        effect.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(effect, field))
            value.BaseValueConstant = -ASBESTOS_FIRE_RATE_PER_RANK
            value.BaseValueScaleConstant = 1.0
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(effect, field, value)
        effect.GradeToStartApplyingEffect = effect.PerGradeUpgradeInterval = 1
        effect.BonusUpgradeList = []
        effects.append(effect)
    helper.SkillEffectDefinitions = effects
    for field, value in (
        ("SkillName", "Asbestos fire-rate bonus"), ("SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive),
        ("TrackedSkillType", unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked),
        ("DurationType", unrealsdk.find_enum("EEffectDurationType").DURATION_Timed),
        ("bSubjectToGradeRules", False), ("MaxGrade", 11), ("bAutoUpdateContexts", True),
        ("BehaviorProviderDefinition", None), ("TrackedActiveSkill", None), ("CustomStackCount", None),
    ):
        _set_piping_property(helper, field, value)
    for field in ("SkillConstraints", "SkillEffectPresentations", "DamageEvents", "KillEvents", "TrackedActiveSkills"):
        if getattr(helper, field):
            setattr(helper, field, [])
    _asbestos_bonus_ready = True
    return helper


def _sync_asbestos_bonus(controller: Any, rank: int | None = None) -> None:
    global _asbestos_window
    if controller is None or _asbestos_controller(allow_dead=True) != controller:
        return
    world, pawn = controller.WorldInfo, controller.Pawn
    if world.Pauser or controller.IsPauseMenuOpen():
        return
    context = (controller._get_address(), world._get_address(), pawn._get_address())
    remaining = (_asbestos_window[3] - float(world.TimeSeconds)
                 if _asbestos_window is not None and _asbestos_window[:3] == context else 0.0)
    parent = _find_piping_object("SkillDefinition", ASBESTOS_PATH)
    manager = controller.GetSkillManager()
    if manager is None or manager.bUpdatingSkills:
        return
    skills = tuple(manager.ActiveSkills)
    if rank is None:
        active = unrealsdk.find_enum("ESkillState").SKILL_Active
        rank = max((int(s.Grade) for s in skills if s.Definition == parent
                    and s.SkillInstigator == controller and s.SkillState == active), default=0)
    if parent is None or int(controller.GetSkillGrade(parent)) <= 0:
        rank = 0
    helper = _find_piping_object("SkillDefinition", ASBESTOS_BONUS)
    instances = [s for s in skills if s.Definition == helper and s.SkillInstigator == controller]
    if remaining <= 0 or rank <= 0 or pawn.IsInjuredDead():
        _asbestos_window = None
        if instances:
            manager.DeactivateSkill(controller, helper)
        return
    helper = helper if helper is not None and _asbestos_bonus_ready else _asbestos_bonus_definition()
    if helper is None:
        return
    if len(instances) > 1:
        manager.DeactivateSkill(controller, helper)
        return  # Recover with a fresh native snapshot on the next bounded pass.
    if not instances:
        helper.InitialDuration = remaining
        if manager.ActivateSkill(controller, helper, None, rank) is False:
            raise RuntimeError("Asbestos fire-rate activation was rejected")
        return  # Do not inspect an old native snapshot after activation.
    skill = instances[0]
    # Native timed skill expires independently of the HUD; reapplications renew, not stack.
    start = _asbestos_window[3] - float(skill.Duration)
    if not math.isclose(float(skill.StartTime), start, rel_tol=0.0, abs_tol=1e-5):
        skill.StartTime = start
    if int(skill.Grade) != rank:
        skill.UpdateGrade(rank)


def _configure_overkill() -> tuple[Any, ...] | None:
    definition = _find_piping_object("SkillDefinition", OVERKILL_PATH)
    active = _find_piping_object("SkillDefinition", OVERKILL_ACTIVE_PATH)
    if definition is None or active is None:
        return None
    effects = list(active.SkillEffectDefinitions)
    if any(sum(_path(effect.AttributeToModify) == path for effect in effects) != 1
           for path in OVERKILL_DAMAGE_ATTRIBUTES):
        raise ValueError("No Kill Like Overkill must have one damage effect per hand")
    replacements = [_tuned_effect(effect, OVERKILL_ACTIVE_PATH) for effect in effects]
    if any(item is not None for item in replacements):
        active.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                         for old, new in zip(effects, replacements)]
    if str(definition.SkillDescription) != OVERKILL_DESCRIPTION:
        definition.SkillDescription = OVERKILL_DESCRIPTION
    return definition, active


def _configure_money_shot() -> Any | None:
    definition = _find_piping_object("SkillDefinition", MONEY_SHOT_PATH)
    if definition is None:
        return None
    effects = list(definition.SkillEffectDefinitions)
    if sum(_path(effect.AttributeToModify) == MONEY_SHOT_DAMAGE_ATTRIBUTE for effect in effects) != 1:
        raise ValueError("Money Shot must have one native last-round damage effect")
    if sum(effect.AttributeToModify is None for effect in effects) != 1:
        raise ValueError("Money Shot must have one native damage presentation helper")
    replacements = [_tuned_effect(effect, MONEY_SHOT_PATH) for effect in effects]
    if any(item is not None for item in replacements):
        definition.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                             for old, new in zip(effects, replacements)]
    return definition  # Native grade, firing effect, small-magazine calculation and graph remain intact.


def _wire_fist_self_shock(provider: Any, move: Any, shock: Any) -> None:
    """Append a player-targeted activation leaf without copying native variable payload."""
    for sequence in provider.BehaviorSequences:
        event_index = next((i for i, event in enumerate(sequence.EventData2)
                            if str(event.UserData.EventName) == "OnMeleeOverrideSkillActivated"), None)
        if event_index is None:
            continue
        event = sequence.EventData2[event_index]
        packed = int(event.OutputLinks.ArrayIndexAndLength) & 0xFFFFFFFF
        start, count = packed >> 16, packed & 0xFFFF
        links = list(sequence.ConsolidatedOutputLinkData)
        nodes = list(sequence.BehaviorData2)
        matches = [i for i, node in enumerate(nodes) if node.Behavior == shock]
        if not count or start + count > len(links) or len(matches) > 1:
            raise ValueError("Fistful of Hurt activation graph is unexpected")
        if matches and any((int(link.LinkIdAndLinkedBehavior) & 0xFFFFFF) == matches[0]
                           for link in links[start:start + count]):
            return
        variables = list(sequence.ConsolidatedVariableLinkData)
        if matches:
            node_index = matches[0]
        else:
            template = next((node for node in nodes if node.Behavior == move), None)
            if template is None:
                raise ValueError("Fistful of Hurt native player-context node is missing")
            packed_context = int(template.LinkedVariables.ArrayIndexAndLength) & 0xFFFFFFFF
            index, length = packed_context >> 16, packed_context & 0xFFFF
            if length != 1 or index >= len(variables) or str(variables[index].PropertyName) != "Context":
                raise ValueError("Fistful of Hurt player-context link is unexpected")
            context = copy.copy(variables[index])
            context.CachedProperty = None
            target = copy.copy(context)
            target.PropertyName, target.ConnectionIndex = "TargetContext", 0
            target.VariableLinkType = unrealsdk.find_enum("EBehaviorVariableLinkType").BVARLINK_Input
            node = copy.copy(template)
            node.Behavior = shock
            binding = copy.copy(node.LinkedVariables)
            binding.ArrayIndexAndLength = (len(variables) << 16) | 2
            node.LinkedVariables = binding
            outputs = copy.copy(node.OutputLinks)
            outputs.ArrayIndexAndLength = 0
            node.OutputLinks = outputs
            variables = [copy.copy(row) for row in variables] + [context, target]
            node_index = len(nodes)
            nodes = [copy.copy(row) for row in nodes] + [node]
        if len(variables) > 0xFFFF or len(links) > 0xFFFF or count >= 0xFFFF or node_index > 0x7FFFFF:
            raise ValueError("Fistful of Hurt graph exceeds native index limits")
        activation = [copy.copy(row) for row in links[start:start + count]]
        link = copy.copy(activation[0])
        link.LinkIdAndLinkedBehavior, link.ActivateDelay = node_index, 0.0
        activation.append(link)
        outputs = copy.copy(event.OutputLinks)
        outputs.ArrayIndexAndLength = (len(links) << 16) | len(activation)
        # Never replace BehaviorSequences/VariableData: they contain opaque native data.
        if not matches:
            sequence.ConsolidatedVariableLinkData = variables
            sequence.BehaviorData2 = nodes
        sequence.ConsolidatedOutputLinkData = [copy.copy(row) for row in links] + activation
        sequence.EventData2[event_index].OutputLinks = outputs
        return
    raise ValueError("Fistful of Hurt activation event is missing")


def _configure_fist_shock(parent: Any = None) -> Any | None:
    global _fist_shock_configured
    if parent is None:
        parent = _find_piping_object("SkillDefinition", FIST_HURT_PATH)
    if parent is None:
        return None
    provider = _find_piping_object("BehaviorProviderDefinition", FIST_SHOCK_PROVIDER)
    move = _find_piping_object("Behavior_SpecialMove", FIST_SHOCK_MOVE)
    status = _find_piping_object("StatusEffectDefinition", "GD_Shock.StatusEffect.Status_Shock")
    template = _find_piping_object("Behavior_AttemptStatusEffect", "WillowGame.Default__Behavior_AttemptStatusEffect")
    if provider is None or move is None or status is None or template is None:
        return None
    shock = _find_piping_object("Behavior_AttemptStatusEffect", FIST_SHOCK_PATH)
    if shock is not None and _fist_shock_configured == (provider._get_address(), shock._get_address()):
        return parent
    if shock is None:
        shock = unrealsdk.construct_object("Behavior_AttemptStatusEffect", parent, "SR_SelfShock", template_obj=template)
    _set_piping_property(shock, "StatusEffect", status)
    shock.Context = copy.copy(move.Context)
    target = copy.copy(template.Context)
    target.BehaviorContext = unrealsdk.find_enum("EBehaviorContext").BCONTEXT_UseContextObject
    target.bSupportsDefaultOutputLink = 0
    target.ContextObject = None
    shock.TargetContext = [target]
    for field, amount in (("InstigatorChanceModifier", 1.0), ("StatusEffectDamage", 1.0),
                          ("StatusEffectChance", 1000.0)):
        value = copy.copy(getattr(template, field))
        value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.0
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(shock, field, value)
    _wire_fist_self_shock(provider, move, shock)
    if FIST_SHOCK_DESCRIPTION not in str(parent.SkillDescription):
        parent.SkillDescription = str(parent.SkillDescription).rstrip() + " " + FIST_SHOCK_DESCRIPTION
    _fist_shock_configured = (provider._get_address(), shock._get_address())
    return parent


def _configure_fist_hurt() -> Any | None:
    definition = _find_piping_object("SkillDefinition", FIST_HURT_PATH)
    if definition is not None and FIST_HURT_DESCRIPTION_EXTRA not in str(definition.SkillDescription):
        description = str(definition.SkillDescription)
        for previous in (
                FIST_HURT_DESCRIPTION_EXTRA.replace("[skill]increased", "[skill]15% increased"),
                FIST_HURT_DESCRIPTION_EXTRA.replace("[skill]increased", "[skill]15% increased").replace(
                    "damage from you[-skill]", "damage[-skill]")):
            description = description.replace(previous, "").rstrip()
        definition.SkillDescription = description + " " + FIST_HURT_DESCRIPTION_EXTRA
    if definition is not None:
        _configure_fist_shock(definition)
    return definition  # Original punch damage, cooldown, animation and knockback are preserved.


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_fixed_bonuses(_tree: Any, args: Any, _ret: Any, func: Any) -> tuple[type[Block], str] | None:
    path = _path(args.SkillDef)
    if path == HARD_TO_KILL_PATH:
        with prevent_hooking_direct_calls():
            original = func(args)
        rank = max(0, int(args.Grade))
        value = _format_salvador_rank_value(_tree, args, f"+{100 * HARD_TO_KILL_RESISTANCE_PER_RANK * rank:g}%")
        separator = "<br>" if args.bIncludeHTML else "\n"
        return Block, separator.join(text for text in (original, f"Damage Resistance: {value}") if text)
    if path not in (AUTO_LOADER_PATH, FIST_HURT_PATH):
        return None
    with prevent_hooking_direct_calls():
        original = func(args)  # Preserve native punch stats or Auto-Loader's quote.
    owner = getattr(args, "PlayerOwner", None)
    capped = bool(args.bIncludeHTML and int(args.Grade) > 0 and owner is not None
                  and int(owner.GetSkillGrade(args.SkillDef)) > 0)
    bonus = AUTO_LOADER_RELOAD_BONUS if path == AUTO_LOADER_PATH else FIST_HURT_BONUS
    value = f"+{bonus * 100:g}%"
    if capped:
        value = f'<font color="#00FF00">{value}</font>'
    label = "Reload Speed" if path == AUTO_LOADER_PATH else "Damage Taken from You"
    separator = "<br>" if args.bIncludeHTML else "\n"
    return Block, separator.join(text for text in (original, f"{label}: {value}") if text)


@hook("WillowGame.WillowAIPawn:TakeDamage", Type.POST)
def mark_fist_hurt_target(target: Any, args: Any, _ret: Any, _func: Any) -> None:
    try:
        if _path(args.DamageCauser) != FIST_HURT_MELEE or args.Pipeline is None:
            return  # An ordinary melee hit, a miss or an attack activation is not this punch.
        controller = _asbestos_controller()
        if controller is None or args.InstigatedBy != controller:
            return
        world = controller.WorldInfo
        if (int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
                or target is None or target.bDeleteMe or target.WorldInfo != world
                or target.Controller is None or target.Controller.bDeleteMe
                or float(target.GetHealth()) <= 0.0
                or int(target.GetOpinion(controller.Pawn)) != int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)):
            return
        definition = _find_piping_object("SkillDefinition", FIST_HURT_PATH)
        if definition is None or int(controller.GetSkillGrade(definition)) <= 0:
            return
        summary = args.Pipeline.DamageSummary
        dealt = max(0.0, float(summary.FinalDamage)) + max(0.0, float(summary.DamageDealtToShields))
        if not math.isfinite(dealt) or dealt <= 0.0:
            return
        now, world_id = float(world.TimeSeconds), world._get_address()
        for key, mark in tuple(_fist_marks.items()):
            if key[0] != world_id or mark[3] <= now:
                del _fist_marks[key]
        key = (world_id, target._get_address())
        if len(_fist_marks) >= 256 and key not in _fist_marks:
            del _fist_marks[next(iter(_fist_marks))]
        _fist_marks[key] = (float(target.CreationTime), _path(target),
                            target.Controller._get_address(), now + FIST_HURT_SECONDS)
        log_key = "Fistful of Hurt vulnerability confirmed"
        if log_key not in _reported_errors:
            _reported_errors.add(log_key)
            unrealsdk.logging.info(
                f"[SalvadorRebalance] {log_key}: target={_path(target)}, factor={1 + FIST_HURT_BONUS:g}, duration={FIST_HURT_SECONDS:g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not mark Fistful of Hurt target", exc)


def _fist_modifier_rows(depth: int, source: Any) -> tuple[tuple[str, Any, Any], ...]:
    field = FIST_SOURCE_FIELDS.get(_path(source))
    fields = (field,) if field is not None else FIST_RECEIVED_FIELDS
    result = []
    for name in fields:
        key = (depth, name)
        if key not in _fist_modifier_pool:
            outer = unrealsdk.find_object("SkillDefinition", FIST_HURT_PATH)
            path = FIST_HURT_PATH + ":SR_" + name
            attribute = _find_piping_object("AttributeDefinition", path)
            if attribute is None:
                template = unrealsdk.find_object(
                    "AttributeDefinition", "D_Attributes.DamageSourceModifiers.ReceivedBulletDamageModifier")
                attribute = unrealsdk.construct_object(
                    "AttributeDefinition", outer, "SR_" + name, template_obj=template, flags=ObjectFlags.KEEP_ALIVE)
                resolver = unrealsdk.construct_object(
                    "ObjectPropertyAttributeValueResolver", attribute, "ReceivedValue",
                    template_obj=template.ValueResolverChain[0], flags=ObjectFlags.KEEP_ALIVE)
                resolver.PropertyName, resolver.CachedProperty = name, None
                attribute.ValueResolverChain = [resolver]
            if len(attribute.ValueResolverChain) != 1 or str(attribute.ValueResolverChain[0].PropertyName) != name:
                raise RuntimeError(f"Fistful of Hurt resolver mismatch: {name}")
            modifier_name = f"SR_Fist_{depth}_{name}"
            modifier = _find_piping_object("AttributeModifier", FIST_HURT_PATH + ":" + modifier_name)
            if modifier is None:
                modifier = unrealsdk.construct_object(
                    "AttributeModifier", outer, modifier_name, flags=ObjectFlags.KEEP_ALIVE)
            modifier.Type = unrealsdk.find_enum("EModifierType").MT_PostAdd
            _fist_modifier_pool[key] = attribute, modifier
        attribute, modifier = _fist_modifier_pool[key]
        result.append((name, attribute, modifier))
    return tuple(result)


def _set_fist_scope(scope: dict[str, Any], active: bool) -> None:
    recipient = scope["recipient"]
    if recipient is None or recipient.bDeleteMe:
        scope["added"] = False
        return
    scope["added"] = False
    errors = []
    for field, attribute, modifier in scope["rows"]:
        try:
            stack = field + "ModifierStack"
            present = modifier in getattr(recipient, stack)
            if active and not present:
                before = float(getattr(recipient, field))
                if not math.isfinite(before) or before <= 0.0:
                    continue  # Preserve immunity/zero factors.
                if attribute.ResolveContext(recipient) != recipient:
                    raise RuntimeError(f"Fistful of Hurt context mismatch: {field}")
                modifier.Value = before * FIST_HURT_BONUS
                accepted = attribute.AddAttributeModifier(recipient, modifier, False)
                present = modifier in getattr(recipient, stack)
                scope["added"] |= present
                if not accepted or not present or not math.isclose(
                        float(getattr(recipient, field)), before * (1 + FIST_HURT_BONUS), rel_tol=1e-5, abs_tol=1e-5):
                    raise RuntimeError(f"Fistful of Hurt multiplier rejected: {field}")
            elif not active and present:
                attribute.RemoveAttributeModifier(recipient, modifier, False)
                if modifier in getattr(recipient, stack):
                    raise RuntimeError(f"Fistful of Hurt cleanup failed: {field}")
            elif active:
                scope["added"] = True
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            errors.append(str(exc))
    if errors:
        scope["added"] = True  # A partial installation still owes cleanup.
        raise RuntimeError("; ".join(errors))


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.PRE)
def begin_fist_vulnerability(pipeline: Any, args: Any, _ret: Any, _func: Any) -> None:
    _fist_scopes.append(None)
    if not _fist_marks and not any(scope and scope["added"] for scope in _fist_scopes):
        return  # No actor/attribute lookups when the debuff is unused.
    scope = None
    try:
        target = args.InDamagedActor
        if target is None or target.bDeleteMe:
            return
        world = target.WorldInfo
        if world is None or world.bDeleteMe:
            return
        key: tuple[int, int] = (world._get_address(), target._get_address())
        mark = _fist_marks.get(key)
        if mark is None and not any(parent and parent["added"] for parent in _fist_scopes[:-1]):
            return  # A marked enemy elsewhere must not slow down unrelated damage.
        recipient = getattr(target, "Controller", None)
        if recipient is None or recipient.bDeleteMe:
            return
        scope = dict(recipient=recipient, rows=(), added=False, parent=None,
                     pipeline=pipeline._get_address())
        _fist_scopes[-1] = scope
        for parent in reversed(_fist_scopes[:-1]):
            if parent is not None and parent["added"] and parent["recipient"] == recipient:
                scope["parent"] = parent
                _set_fist_scope(parent, False)
                break
        if mark is None:
            return
        if (float(world.TimeSeconds) >= mark[3]
                or (float(target.CreationTime), _path(target), recipient._get_address()) != mark[:3]):
            _fist_marks.pop(key, None)
            return
        controller = _asbestos_controller(allow_dead=True)
        attacker = args.InDamageInstigator
        if (controller is None or controller.WorldInfo != world or attacker is None or attacker.bDeleteMe
                or attacker.WorldInfo != world or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
            return
        source_pawn = getattr(attacker, "Pawn", None)
        opinions = unrealsdk.find_enum("EOpinion")
        if int(target.GetOpinion(controller.Pawn)) != int(opinions.OPINION_Enemy):
            return
        if attacker != controller:
            if (not FIST_HURT_TEAM or source_pawn is None or source_pawn.bDeleteMe
                    or int(controller.Pawn.GetOpinion(source_pawn)) != int(opinions.OPINION_Friendly)):
                return
        damage_type = pipeline.GetDamageTypeDef()
        if (damage_type is None or damage_type.IsHealingDamageType()
                or not math.isfinite(float(args.IncomingDamage)) or float(args.IncomingDamage) <= 0.0
                or len(_fist_scopes) > 16):
            return
        scope["rows"] = _fist_modifier_rows(len(_fist_scopes) - 1, args.InDamageSource)
        _set_fist_scope(scope, True)
        log_key = "Fistful of Hurt native damage multiplier"
        if scope["added"] and log_key not in _reported_errors:
            _reported_errors.add(log_key)
            unrealsdk.logging.info(f"[SalvadorRebalance] {log_key}: factor={1 + FIST_HURT_BONUS:g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        if scope is not None and scope["added"]:
            try:
                _set_fist_scope(scope, False)
            except (AttributeError, TypeError, ValueError, RuntimeError) as cleanup:
                _report_error("Could not roll back Fistful of Hurt multiplier", cleanup)
        _report_error("Could not apply Fistful of Hurt multiplier", exc)


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.POST_UNCONDITIONAL)
def finish_fist_vulnerability(pipeline: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if not _fist_scopes:
        return
    scope = _fist_scopes.pop()
    if scope is None or scope["recipient"] is None:
        return
    try:
        _set_fist_scope(scope, False)
        if scope["pipeline"] != pipeline._get_address():
            raise RuntimeError("Fistful of Hurt pipeline hooks were not paired")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not finish Fistful of Hurt multiplier", exc)
    finally:
        if scope["parent"] is not None and scope["parent"]["recipient"] is not None:
            try:
                _set_fist_scope(scope["parent"], True)
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _report_error("Could not restore enclosing Fistful of Hurt multiplier", exc)


def _suspend_fist_vulnerability(*, cleanup: bool = True) -> None:
    _fist_marks.clear()
    for scope in reversed(_fist_scopes):
        if scope is not None and scope["recipient"] is not None:
            if cleanup:
                try:
                    _set_fist_scope(scope, False)
                except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                    _report_error("Could not suspend Fistful of Hurt multiplier", exc)
            scope["recipient"] = None
            scope["parent"] = None  # Delayed POST cannot touch a departing actor.


def _configure_berzerk() -> tuple[Any, ...] | None:
    definition = _find_piping_object("SkillDefinition", BERZERK_PATH)
    shield = _find_piping_object("ResourcePoolAttributeDefinition", BERZERK_SHIELD_BLOCK)
    resistance = [_find_piping_object("AttributeDefinition", path) for path in BERZERK_RESISTANCE_ATTRIBUTES]
    if definition is None or shield is None or any(attribute is None for attribute in resistance):
        return None
    effects = list(definition.SkillEffectDefinitions)
    if not effects:
        raise ValueError("Berzerk native effect template is missing")
    desired, changed = [], False
    for attribute in [shield, *resistance]:
        matches = [effect for effect in effects if effect.AttributeToModify == attribute]
        item = copy.copy(matches[0] if matches else effects[0])
        item.AttributeToModify = attribute
        tuned = _tuned_effect(item, BERZERK_PATH)
        desired.append(tuned if tuned is not None else item)
        changed |= tuned is not None or len(matches) != 1
    if changed or tuple(_path(effect.AttributeToModify) for effect in effects) != tuple(
            _path(effect.AttributeToModify) for effect in desired):
        definition.SkillEffectDefinitions = [copy.copy(effect) for effect in desired]
    for field, value in (
        ("SkillName", "Berzerk"), ("SkillDescription", BERZERK_DESCRIPTION),
        ("SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_ActionAugment),
        ("BehaviorProviderDefinition", None), ("TrackedActiveSkill", None),
    ):
        _set_piping_property(definition, field, value)
    for field in ("DamageEvents", "KillEvents", "TrackedActiveSkills", "SkillEffectPresentations"):
        if getattr(definition, field):
            setattr(definition, field, [])
    legacy = _find_piping_object("SkillDefinition", BERZERK_LEGACY_PATH)
    if legacy is not None:
        for field in ("SkillEffectDefinitions", "SkillEffectPresentations", "DamageEvents", "KillEvents", "TrackedActiveSkills"):
            if getattr(legacy, field):
                setattr(legacy, field, [])
        _set_piping_property(legacy, "BehaviorProviderDefinition", None)
        _set_piping_property(legacy, "TrackedActiveSkill", None)
        _set_piping_property(legacy, "TrackedSkillType", unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked)
    return (definition, legacy) if legacy is not None else (definition,)


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_berzerk(tree: Any, args: Any, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or _path(args.SkillDef) != BERZERK_PATH:
        return None
    separator = "<br>" if args.bIncludeHTML else "\n"
    owner = getattr(args, "PlayerOwner", None)
    capped = bool(args.bIncludeHTML and int(args.Grade) > 0 and owner is not None
                  and int(owner.GetSkillGrade(args.SkillDef)) > 0)
    values = tuple(f'<font color="#00FF00">{value}</font>' if capped else value
                   for value in (f"{BERZERK_DAMAGE_REDUCTION * 100:g}%", f"+{BERZERK_GUN_BONUS * 100:g}%",
                                 f"{BERZERK_HEALTH_COST * 100:g}%"))
    return Block, separator.join((f"Damage Reduction: {values[0]}", f"Amp Damage: {values[1]}",
                                  f"Current Health Cost per Shot: {values[2]}"))


def _berzerk_modifiers(weapon: Any) -> list[Any]:
    return [modifier for modifier in weapon.InstantHitDamageModifierStack
            if modifier is not None and str(modifier.Name) == BERZERK_DAMAGE_MODIFIER]


def _clear_berzerk_weapon(weapon: Any) -> None:
    for modifier in _berzerk_modifiers(weapon):
        if not weapon.RemoveModifier(modifier, "InstantHitDamage", False):
            raise RuntimeError("Could not remove Berzerk Amp Damage")
    _berzerk_weapons.discard(weapon._get_address())


def _set_berzerk_weapon(weapon: Any) -> None:
    modifiers = _berzerk_modifiers(weapon)
    if len(modifiers) > 1:
        _clear_berzerk_weapon(weapon)
        modifiers = []
    own = modifiers[0] if modifiers else None
    # MT_PostAdd is an absolute amount added after native scale modifiers.
    # Subtract our own existing contribution before evaluating the underlying gun damage.
    underlying = float(weapon.InstantHitDamage) - (float(own.Value) if own is not None else 0.0)
    if not math.isfinite(underlying) or underlying <= 0.0:
        _clear_berzerk_weapon(weapon)
        return
    expected = underlying * BERZERK_GUN_BONUS
    if own is not None and math.isclose(float(own.Value), expected, rel_tol=1e-6, abs_tol=1e-6):
        _berzerk_weapons.add(weapon._get_address())
        return
    if own is not None:
        _clear_berzerk_weapon(weapon)
        # Removing our modifier asks native code to recalculate, preserving other mods' changes.
        expected = max(0.0, float(weapon.InstantHitDamage)) * BERZERK_GUN_BONUS
    else:
        outer = _path(weapon)
        path = outer + ("." if ":" in outer else ":") + BERZERK_DAMAGE_MODIFIER
        own = _find_piping_object("AttributeModifier", path)
        if own is None:
            own = unrealsdk.construct_object("AttributeModifier", weapon, BERZERK_DAMAGE_MODIFIER)
    own.Type = unrealsdk.find_enum("EModifierType").MT_PostAdd
    own.Value = expected
    accepted = weapon.AddModifier(own, "InstantHitDamage", False)
    present = own in _berzerk_modifiers(weapon)
    if present:
        _berzerk_weapons.add(weapon._get_address())
    expected_final = expected * (1.0 + BERZERK_GUN_BONUS) / BERZERK_GUN_BONUS
    actual = float(weapon.InstantHitDamage)
    if not accepted or not present or not math.isclose(actual, expected_final, rel_tol=1e-5, abs_tol=1e-5):
        if present:
            _clear_berzerk_weapon(weapon)
        raise RuntimeError("Could not apply Berzerk Amp Damage")
    key = "Berzerk Amp Damage verified"
    if key not in _reported_errors:
        _reported_errors.add(key)
        unrealsdk.logging.info(f"[SalvadorRebalance] {key}: added={expected:g}, final={actual:g}, type=MT_PostAdd")


def _berzerk_owned_weapons(controller: Any) -> list[Any]:
    pawn = controller.Pawn
    weapons = [weapon for weapon in (pawn.Weapon, pawn.OffHandWeapon)
               if weapon is not None and not weapon.bDeleteMe]
    wanted = _berzerk_weapons - {weapon._get_address() for weapon in weapons}
    if wanted:
        manager = pawn.InvManager
        item = manager.ItemChain if manager is not None else None
        for _ in range(40):
            if item is None:
                break
            if item._get_address() in wanted and not item.bDeleteMe:
                weapons.append(item)
                wanted.discard(item._get_address())
            if not wanted:
                break
            item = item.Inventory
    return weapons


def _sync_berzerk(controller: Any, active: bool) -> None:
    global _berzerk_context
    if not active and not _berzerk_weapons:
        _berzerk_context = None
        return
    pawn, world = controller.Pawn, controller.WorldInfo
    context = (controller._get_address(), world._get_address(), pawn._get_address())
    _berzerk_context = context if active and not pawn.IsInjuredDead() else None
    equipped = (pawn.Weapon, pawn.OffHandWeapon)
    seen: set[int] = set()
    for weapon in _berzerk_owned_weapons(controller):
        seen.add(weapon._get_address())
        if _berzerk_context is not None and weapon in equipped and weapon.Instigator == pawn and weapon.WorldInfo == world:
            _set_berzerk_weapon(weapon)
        else:
            _clear_berzerk_weapon(weapon)
    _berzerk_weapons.intersection_update(seen)


@hook("WillowGame.WillowPlayerController:ActionSkillCallback", Type.POST)
def berzerk_action_changed(controller: Any, args: Any, _ret: Any, _func: Any) -> None:
    try:
        if args.ActivatedSkill is None or _path(args.ActivatedSkill.Definition) != GUNZERKING_PATH:
            return
        if controller != _asbestos_controller(allow_dead=True):
            return
        definition = _find_piping_object("SkillDefinition", BERZERK_PATH)
        active = bool(args.bActivated and definition is not None and int(controller.GetSkillGrade(definition)) > 0)
        _sync_berzerk(controller, active)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not update Berzerk action lifecycle", exc)


@hook("WillowGame.WillowWeapon:OnUnequip", Type.PRE)
@hook("WillowGame.WillowWeapon:ItemRemovedFromInvManager", Type.PRE)
def unequip_berzerk_weapon(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if weapon is None or weapon._get_address() not in _berzerk_weapons:
        return
    try:
        controller = _asbestos_controller(allow_dead=True)
        if (controller is not None and not weapon.bDeleteMe and weapon.Instigator == controller.Pawn
                and weapon.WorldInfo == controller.WorldInfo):
            _clear_berzerk_weapon(weapon)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not clear unequipped Berzerk weapon", exc)


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.PRE)
def prepare_berzerk_fire(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _berzerk_fire_frames.append(None)
    if _berzerk_context is None:
        return
    try:
        controller = _asbestos_controller()
        if controller is None or weapon is None or weapon.bDeleteMe:
            return
        pawn, world = controller.Pawn, controller.WorldInfo
        context = (controller._get_address(), world._get_address(), pawn._get_address())
        if (context != _berzerk_context or weapon not in (pawn.Weapon, pawn.OffHandWeapon)
                or weapon.Instigator != pawn or weapon.WorldInfo != world or int(weapon.ReloadCnt) <= 0):
            return
        address = weapon._get_address()
        if any(frame is not None and frame["weapon"] == address for frame in _berzerk_fire_frames[:-1]):
            return
        _set_berzerk_weapon(weapon)
        _berzerk_fire_frames[-1] = dict(weapon=address, context=context, executed=False)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not prepare Berzerk shot", exc)


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST)
def mark_berzerk_fire(_weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if _berzerk_fire_frames and _berzerk_fire_frames[-1] is not None:
        _berzerk_fire_frames[-1]["executed"] = True


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST_UNCONDITIONAL)
def finish_berzerk_fire(_weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if not _berzerk_fire_frames:
        return
    frame = _berzerk_fire_frames.pop()
    if frame is None or not frame["executed"]:
        return
    try:
        controller = _asbestos_controller()
        if controller is None:
            return
        pawn = controller.Pawn
        context = (controller._get_address(), controller.WorldInfo._get_address(), pawn._get_address())
        if context != frame["context"]:
            return
        health = float(pawn.GetHealth())
        if not math.isfinite(health) or health <= 1.0:
            return
        remaining = max(min(1.0, health), health * (1.0 - BERZERK_HEALTH_COST))
        pawn.SetHealth(remaining)
        key = "Berzerk health cost verified"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(f"[SalvadorRebalance] {key}: health_before={health:g}, health_after={float(pawn.GetHealth()):g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not charge Berzerk shot health", exc)


def _configure_get_some() -> tuple[Any, Any] | None:
    definition = _find_piping_object("SkillDefinition", GET_SOME_PATH)
    active = _find_piping_object("SkillDefinition", GET_SOME_ACTIVE_PATH)
    if definition is None or active is None:
        return None
    display_effects, active_effects = (list(definition.SkillEffectDefinitions),
                                       list(active.SkillEffectDefinitions))
    if (len(display_effects) != 1 or display_effects[0].AttributeToModify is not None
            or len(active_effects) != 1
            or _path(active_effects[0].AttributeToModify) != COOLDOWN_RATE_ATTRIBUTE
            or _path(active_effects[0].BaseModifierValue.BaseValueAttribute) != GET_SOME_GRADE_ATTRIBUTE
            or not math.isclose(float(active.InitialDuration), GET_SOME_NATIVE_DURATION,
                                rel_tol=1e-6, abs_tol=1e-7)):
        raise ValueError("Get Some native cooldown effect or duration is unexpected")
    # Resolve and validate both definitions before changing either display or gameplay.
    updates = [(target, [_tuned_effect(row, path) for row in effects], effects)
               for target, path, effects in ((definition, GET_SOME_PATH, display_effects),
                                             (active, GET_SOME_ACTIVE_PATH, active_effects))]
    for target, updated, effects in updates:
        if any(row is not None for row in updated):
            target.SkillEffectDefinitions = [copy.copy(new if new is not None else old)
                                            for old, new in zip(effects, updated)]
    return definition, active


def _configure_yippee() -> Any | None:
    definition = _find_piping_object("SkillDefinition", YIPPEE_PATH)
    if definition is not None and definition.SkillDescription != YIPPEE_DESCRIPTION:
        definition.SkillDescription = YIPPEE_DESCRIPTION
    return definition


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_yippee(tree: Any, args: Any, _ret: Any, func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or _path(args.SkillDef) != YIPPEE_PATH:
        return None
    with prevent_hooking_direct_calls():
        original = func(args)
    # Native queried Grade already includes COM points and next-rank adjustments.
    seconds = YIPPEE_CRIT_SECONDS_PER_RANK * max(0, int(args.Grade))
    value = _format_salvador_rank_value(tree, args, f"+{seconds:g}")
    separator = "<br>" if args.bIncludeHTML else "\n"
    return Block, separator.join(text for text in (
        original, f"Gunzerking Duration per Critical Hit: {value} seconds") if text)


@hook("WillowGame.WillowPlayerStats:IncrementPlayerCriticalHitStat", Type.POST)
def extend_yippee_on_critical(stats: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _yippee_crit_last
    try:
        controller = _asbestos_controller()
        if controller is None or stats is None or controller.PlayerStats != stats:
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if world.Pauser or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority):
            return
        now = float(world.TimeSeconds)
        if not math.isfinite(now):
            return
        identity = (controller._get_address(), world._get_address(), pawn._get_address())
        previous = _yippee_crit_last
        # Cheap rejection before reading skills: pellets and both hands share one cooldown.
        if previous is not None and previous[:3] == identity and 0 <= now - previous[5] < YIPPEE_CRIT_COOLDOWN:
            return
        manager = controller.GetSkillManager()
        if manager is None or manager.bUpdatingSkills:
            return
        active = unrealsdk.find_enum("ESkillState").SKILL_Active
        parent, rank = None, 0
        for skill in manager.ActiveSkills:
            if skill.SkillInstigator != controller or skill.SkillState != active:
                continue
            path = _path(skill.Definition)
            if path == GUNZERKING_PATH:
                parent = skill
            elif path == YIPPEE_PATH:
                rank = max(rank, int(skill.Grade))
        if parent is None or rank <= 0:
            return
        start, activated = float(parent.StartTime), float(parent.ActivatedTime)
        if not math.isfinite(start) or not math.isfinite(activated):
            return
        # The native kill effect modifies this same live StartTime property.
        parent.StartTime = start + YIPPEE_CRIT_SECONDS_PER_RANK * rank
        _yippee_crit_last = (*identity, parent._get_address(), activated, now)
        key = "Yippee Ki Yay critical extension verified"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(
                f"[SalvadorRebalance] {key}: rank={rank}, added={YIPPEE_CRIT_SECONDS_PER_RANK * rank:g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not extend Yippee Ki Yay on critical hit", exc)


def _configure_skills() -> tuple[Any, ...]:
    definitions = []
    for name, configure in (("Bus That Cannot Slow Down position", _configure_bus_position),
                            ("Get Some cooldown reduction", _configure_get_some),
                            ("Yippee Ki Yay critical extension", _configure_yippee),
                            ("Hard to Kill", _configure_hard_to_kill),
                            ("I'm the Juggernaut", _configure_juggernaut),
                            ("Just Got Real", _configure_just_got_real),
                            ("Ain't Got Time to Bleed", _configure_bleed),
                            ("I'm Ready Already", _configure_ready_already),
                            ("Divergent Likeness", _configure_divergent),
                            ("All in the Reflexes", _configure_reflexes),
                            ("Sexual Tyrannosaurus", _configure_tyrannosaurus),
                            ("Missing off-hand skill contexts", _configure_offhand_pairs),
                            ("I'm Your Huckleberry per-hand pistol bonuses", _configure_huckleberry),
                            ("Quick Draw critical-hit damage", _configure_quick_draw),
                            ("Auto-Loader passive reload speed", _configure_auto_loader),
                            ("Keep It Piping Hot Gunzerking stacks", _configure_piping_hot),
                            ("Asbestos temporary fire rate", _configure_asbestos),
                            ("No Kill Like Overkill half bonus", _configure_overkill),
                            ("Money Shot maximum damage 72% per rank", _configure_money_shot),
                            ("Fistful of Hurt vulnerability", _configure_fist_hurt),
                            ("Berzerk Gunzerking rework", _configure_berzerk)):
        try:
            definition = configure()
            if definition is not None:
                definitions.extend(definition if isinstance(definition, tuple) else (definition,))
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _report_error(f"Could not configure {name}", exc)
    return tuple(definitions)


def _recover_skill_owner(reference: Any, identity: tuple[int, int, int]) -> tuple[Any, Any] | None:
    live = reference()
    if live is None or live.bDeleteMe:
        return None
    world, pawn = live.WorldInfo, live.Pawn
    if (world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe or pawn.Controller != live
            or (int(live._get_address()), int(world._get_address()), int(pawn._get_address())) != identity):
        return None
    manager = live.GetSkillManager()
    if manager is None or manager.bUpdatingSkills:
        return None
    return live, manager


def _rebind_live_effects(skill: Any) -> None:
    """Changing an attribute needs native context rebuilding, not just new values."""
    modes = unrealsdk.find_enum("EAdjustModifierMode")
    active = skill.SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active
    previous = [copy.copy(item) for item in skill.SkillEffects]
    reference = WeakPointer(skill)
    if active:
        skill.AdjustModifiers(modes.WILLOW_ADJUST_RemoveModifer, True)
    skill = reference()
    if skill is None:
        return
    try:
        skill.SkillEffects = []
        skill = reference()
        if skill is not None:
            skill.BuildSkillEffects()
    except (AttributeError, TypeError, ValueError, RuntimeError):
        skill = reference()
        if skill is not None:
            skill.SkillEffects = previous
        raise
    finally:
        skill = reference()
        if active and skill is not None:
            skill.AdjustModifiers(modes.WILLOW_ADJUST_InitialAddModifer, False)


def _maintain_rough_rider_health(controller: Any, manager: Any, skills: tuple[Any, ...]) -> bool:
    """Preserve native shield health scaling; clean only known unequipped slots."""
    pawn = controller.Pawn
    equipment = getattr(pawn, "EquippedItems", ())
    if not equipment and not _rough_rider_slots:
        return True
    context = (controller._get_address(), controller.WorldInfo._get_address(), pawn._get_address())
    equipped_slots = set()
    for item in equipment:
        if item is None or item.bDeleteMe:
            continue
        if _path(item.DefinitionData.ItemDefinition) == ROUGH_RIDER_DEFINITION:
            slot = _path(item.RuntimeAttributeSlotSkill)
            if slot:
                equipped_slots.add(slot)
                _rough_rider_slots[slot] = context
    if not _rough_rider_slots:
        return True
    seen = set()
    stale = {}
    for skill in skills:
        slot = _path(skill.Definition)
        if skill.SkillInstigator != controller or _rough_rider_slots.get(slot) != context:
            continue
        seen.add(slot)
        if slot not in equipped_slots:
            stale[slot] = skill.Definition
            continue
    # Do not mutate ActiveSkills while iterating it. Remove only a previously
    # identified local shield slot that survived its own unequip lifecycle.
    for definition in stale.values():
        manager.DeactivateSkill(controller, definition, False)
        unrealsdk.logging.info("[SalvadorRebalance] Removed unequipped Rough Rider slot bonus")
        return False  # Process any other stale slots from a fresh snapshot next pass.
    for slot, owner in tuple(_rough_rider_slots.items()):
        if owner != context or slot not in equipped_slots and slot not in seen:
            del _rough_rider_slots[slot]

    return True


@hook("WillowGame.WillowPlayerController:ToggleEquipInventory", Type.POST)
@hook("WillowGame.WillowPlayerController:ServerToggleEquipInventory", Type.POST)
def update_rough_rider_equipment(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    try:
        if controller is None or controller != _asbestos_controller(allow_dead=True):
            return
        manager = controller.GetSkillManager()
        if manager is not None and not manager.bUpdatingSkills:
            _maintain_rough_rider_health(controller, manager, tuple(manager.ActiveSkills))
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not update Rough Rider equipment cleanup", exc)


def _refresh_live_effects(controller: Any, definition: Any, context: tuple[int, int]) -> None:
    reference = WeakPointer(controller)
    owner = (int(controller._get_address()), int(controller.WorldInfo._get_address()), int(controller.Pawn._get_address()))
    manager = controller.GetSkillManager()
    if manager is None or manager.bUpdatingSkills:
        return
    skills = tuple(manager.ActiveSkills)
    definitions = definition if isinstance(definition, tuple) else (definition,)
    seen: set[int] = set()
    reflexes_rank = 0
    berzerk_active = False
    piping_rank, piping_parent = 0, None
    piping_helpers = []
    for skill in skills:
        if skill.Definition not in definitions or skill.SkillInstigator != controller:
            continue
        if _path(skill.Definition) == PIPING_HOT_HELPER:
            piping_helpers.append(skill)
            continue  # Combined grade is private; never treat it as a learned skill rank.
        address = skill._get_address()
        seen.add(address)
        current = list(skill.SkillEffects)
        skill_path = _path(skill.Definition)
        if (skill_path == REFLEXES_PATH
                and skill.SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active):
            reflexes_rank = max(reflexes_rank, int(skill.Grade))
        if (skill_path == PIPING_HOT_PATH
                and skill.SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active):
            if int(skill.Grade) > piping_rank:
                piping_rank, piping_parent = int(skill.Grade), skill
        if skill_path == BERZERK_PATH and skill.SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active:
            berzerk_active = berzerk_active or int(skill.Grade) > 0
        replacements = [_tuned_effect(item.EffectData, skill_path) for item in current]
        changed = any(item is not None for item in replacements)
        rebind = any(data is not None and data.AttributeToModify != old.EffectData.AttributeToModify
                     for old, data in zip(current, replacements))
        if skill_path in OFFHAND_PAIRS or skill_path in (HARD_TO_KILL_PATH, TYRANNOSAURUS_PATH, HUCKLEBERRY_PATH, AUTO_LOADER_PATH, PIPING_HOT_PATH, BERZERK_PATH, BERZERK_LEGACY_PATH):
            # Added/replaced contexts need a native rebuild without resetting skill timers.
            rebind = rebind or (tuple(_path(item.EffectData.AttributeToModify) for item in current)
                               != tuple(_path(item.AttributeToModify)
                                        for item in skill.Definition.SkillEffectDefinitions))
        if rebind:
            skill_reference = WeakPointer(skill)
            _rebind_live_effects(skill)
            recovered = _recover_skill_owner(reference, owner)
            live = skill_reference()
            if recovered is not None and live is not None and live.SkillInstigator == recovered[0]:
                revision = (_just_got_real_revision if skill_path == JUST_GOT_REAL_PATH
                            else _bleed_revision if skill_path == BLEED_PATH
                            else _huckleberry_revision if skill_path == HUCKLEBERRY_PATH else 0)
                live.bForceRefreshModifiersNextTick = True
                _live_skill_ranks[address] = (*context, live._get_address(), int(live.Grade), revision)
            return  # A native callback can invalidate every item in skills.
        elif changed:
            migrated = [copy.copy(item) for item in current]
            for item, data in zip(migrated, replacements):
                if data is not None:
                    item.EffectData = data
            skill.SkillEffects = migrated
        # Grade already includes the equipped COM. Never add its bonus again,
        # cache its maximum as a rank, or overwrite the tree's invested points.
        revision = (_just_got_real_revision if skill_path == JUST_GOT_REAL_PATH
                    else _bleed_revision if skill_path == BLEED_PATH
                    else _huckleberry_revision if skill_path == HUCKLEBERRY_PATH else 0)
        signature = (*context, skill._get_address(), int(skill.Grade), revision)
        if changed or signature != _live_skill_ranks.get(address):
            skill.bForceRefreshModifiersNextTick = True
        _live_skill_ranks[address] = signature
    for address in set(_live_skill_ranks) - seen:
        del _live_skill_ranks[address]
    _maintain_reflexes_reload(controller, reflexes_rank)
    try:
        if not _maintain_rough_rider_health(controller, manager, skills):
            return
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not maintain Rough Rider equipment cleanup", exc)
    if any(_path(item) == PIPING_HOT_PATH for item in definitions):
        _sync_piping_hot(controller, manager, piping_rank, piping_parent, piping_helpers)
    if any(_path(item) == BERZERK_PATH for item in definitions):
        recovered = _recover_skill_owner(reference, owner)
        if recovered is not None:
            _sync_berzerk(recovered[0], berzerk_active)


def _report_error(key: str, exc: Exception) -> None:
    if key not in _reported_errors:
        _reported_errors.add(key)
        unrealsdk.logging.error(f"[SalvadorRebalance] {key}: {exc}")


@hook("WillowGame.PlayerSkillTree:Initialize", Type.PRE)
def prepare_salvador_skills(_tree: Any, args: Any, _ret: Any, _func: Any) -> None:
    global _bus_position_configured
    if _path(args.SkillTreeDef) != SKILL_TREE:
        return
    _bus_position_configured = None
    _hud_allocation_checks.clear()
    _configure_skills()


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def maintain_salvador_skills(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _next_maintenance, _live_context
    _maintain_asbestos_hud(controller)
    now = time.monotonic()
    if now < _next_maintenance:
        return
    try:
        if controller is None or controller != get_pc(possibly_loading=True) or controller.bDeleteMe:
            return
        _next_maintenance = now + MAINTENANCE_SECONDS
        world = controller.WorldInfo
        if world is None or world.bDeleteMe:
            return
        context = (controller._get_address(), world._get_address())
        if _departing_context in (context, (context[0], 0)):
            return
        if (world.Pauser or controller.IsPauseMenuOpen()
                or _path(controller.PlayerClass) != PLAYER_CLASS):
            return
        pawn, tree = controller.Pawn, controller.PlayerSkillTree
        if (pawn is None or pawn.bDeleteMe or pawn.Controller != controller
                or tree is None or not tree.bInitialized):
            return
        if _live_context != context:
            _live_skill_ranks.clear()
        _live_context = context
        if _fist_marks:
            for key, mark in tuple(_fist_marks.items()):
                if key[0] != context[1] or mark[3] <= float(world.TimeSeconds):
                    del _fist_marks[key]
        definitions = _configure_skills()
        if definitions:
            _refresh_live_effects(controller, definitions, context)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report_error("Could not maintain Salvador skills", exc)


@hook("WillowGame.WillowPlayerController:PreClientTravel", Type.PRE)
def suspend_before_travel(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _departing_context, _piping_hot_session, _asbestos_window, _asbestos_hud_last, _berzerk_context
    if controller is not None and controller == get_pc(possibly_loading=True):
        try:
            if _berzerk_weapons:
                _sync_berzerk(controller, False)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _report_error("Could not suspend Berzerk weapon damage", exc)
        _berzerk_context = None
        _berzerk_weapons.clear()
        _suspend_fist_vulnerability()
        world = controller.WorldInfo
        _departing_context = (controller._get_address(), world._get_address() if world else 0)
        _piping_hot_session = None
        _asbestos_window = None
        _asbestos_hud_last = None
        _live_skill_ranks.clear()
        _rough_rider_slots.clear()
        _hud_allocation_checks.clear()


@hook("WillowGame.WillowPlayerController:Destroyed", Type.PRE)
def suspend_before_destroy(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _departing_context, _live_context, _piping_hot_session, _asbestos_window, _asbestos_hud_last, _berzerk_context
    # Destruction reads only identity, never an old pawn, world or skill manager.
    if _live_context is not None and controller._get_address() == _live_context[0]:
        _berzerk_context = None
        _berzerk_weapons.clear()
        _suspend_fist_vulnerability(cleanup=False)
        _departing_context = (_live_context[0], 0)
        _live_context = None
        _piping_hot_session = None
        _asbestos_window = None
        _asbestos_hud_last = None
        _live_skill_ranks.clear()
        _rough_rider_slots.clear()
        _hud_allocation_checks.clear()


def on_enable() -> None:
    global _bus_position_configured
    _bus_position_configured = None
    _hud_allocation_checks.clear()
    global _fist_shock_configured
    _fist_shock_configured = None
    global _yippee_crit_last
    _yippee_crit_last = None
    global _next_maintenance, _live_context, _departing_context
    global _configuration_logged, _piping_hot_session, _piping_hot_hud_ready, _asbestos_window
    global _asbestos_hud_ready, _asbestos_hud_last, _next_asbestos_hud_sync, _asbestos_bonus_ready, _berzerk_context
    _berzerk_context = None
    _berzerk_weapons.clear()
    _berzerk_fire_frames.clear()
    _fist_marks.clear()
    _fist_scopes.clear()
    _asbestos_hud_ready = False
    _asbestos_hud_last = None
    _next_asbestos_hud_sync = 0.0
    _asbestos_window = None
    _asbestos_status_frames.clear()
    _asbestos_bonus_ready = False
    _piping_hot_hud_ready = False
    _piping_hot_logged.clear()
    _piping_hot_session = None
    _next_maintenance = 0.0
    _live_context = _departing_context = None
    _live_skill_ranks.clear()
    _configuration_logged = False
    _rough_rider_slots.clear()
    _reflexes_pending.clear()
    _reported_errors.clear()
    _configure_skills()


mod = build_mod(
    cls=RestartToDisable,
    hooks=[prepare_salvador_skills, maintain_salvador_skills, update_rough_rider_equipment,
           suspend_before_travel, suspend_before_destroy, start_reflexes_reload,
           time_reflexes_reload, finish_reflexes_reload, piping_hot_action_changed, describe_piping_hot,
           mark_fist_hurt_target, begin_fist_vulnerability, finish_fist_vulnerability,
           describe_berzerk, describe_fixed_bonuses, berzerk_action_changed, unequip_berzerk_weapon,
           prepare_berzerk_fire, mark_berzerk_fire, finish_berzerk_fire,
           describe_asbestos, prepare_asbestos_status, finish_asbestos_status,
           describe_yippee, extend_yippee_on_critical,
           ],
    commands=[], keybinds=[], options=[], on_enable=on_enable,
)
