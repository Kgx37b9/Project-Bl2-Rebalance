"""Independent Zer0 skill adjustments for the modern Willow2 Python SDK."""
from __future__ import annotations

import copy
import math
import random
import time
from typing import Any

import unrealsdk  # pyright: ignore[reportMissingModuleSource]
from mods_base import ObjectFlags, build_mod, get_pc, hook
from unrealsdk.hooks import Block, Type  # pyright: ignore[reportMissingModuleSource]
from unrealsdk.unreal import WeakPointer  # pyright: ignore[reportMissingModuleSource]

ZER0_CLASS = "GD_Assassin.Character.CharClass_Assassin"
IRON_HAND = "GD_Assassin_Skills.Bloodshed.IronHand"
HEALTH_ATTRIBUTE = "D_Attributes.HealthResourcePool.HealthMaxValue_Player"
MELEE_ATTRIBUTE = "D_Attributes.DamageSourceModifiers.InstigatedMeleeDamageModifier"
IRON_HAND_RESISTANCE_PER_RANK = .05
GRIM = "GD_Assassin_Skills.Bloodshed.Grim"
GRIM_COOLDOWN_ATTRIBUTE = "D_Attributes.ActiveSkillCooldownResource.ActiveSkillCooldownConsumptionRate"
GRIM_COOLDOWN_PER_RANK = .08
GRIM_SHIELD_REGEN_FACTOR = 1.1 / .7
FEARLESS = "GD_Assassin_Skills.Cunning.Fearless"
FEARLESS_CONDITION = FEARLESS + ":CompoundExpressionEvaluator_0.AttributeExpressionEvaluator_22"
FULL_SHIELD_RATIO = .999999
RESURGENCE = "GD_Assassin_Skills.Bloodshed.Resurgence"
RESURGENCE_SHIELD_PER_RANK = .04
RESURGENCE_HEALTH_PER_RANK = .05
RESURGENCE_HEALTH_ATTRIBUTE = "GD_Assassin_Skills.Misc.Att_Resurgence_HealthRestorePerLevel"
RESURGENCE_PROVIDER = RESURGENCE + ":BehaviorProviderDefinition_0"
SHIELD_MAX_ATTRIBUTE = "D_Attributes.ShieldResourcePool.ShieldMaxValue"
KILL_CONFIRMED = "GD_Assassin_Skills.Sniping.KillConfirmed"
KILL_CONFIRMED_STACK = KILL_CONFIRMED + "_Stack"
KILL_CONFIRMED_GAIN_INTERVAL = .25
KILL_CONFIRMED_DECAY_INTERVAL = 2.
VELOCITY = "GD_Assassin_Skills.Sniping.Velocity"
VELOCITY_GUN_DAMAGE = "D_Attributes.Weapon.WeaponDamage"
VELOCITY_CRITICAL_DAMAGE = "D_Attributes.GameplayAttributes.PlayerCriticalHitBonus"
VELOCITY_PROJECTILE_SPEED = "D_Attributes.Weapon.WeaponProjectileSpeedMultiplier"
VELOCITY_GUN_DAMAGE_PER_RANK = .05
MANY_MUST_FALL = "GD_Assassin_Skills.Bloodshed.ManyMustFall"
TWO_FANG = "GD_Assassin_Skills.Cunning.TwoFang"
DECEPTION = "GD_Assassin_Skills.ActionSkill.Skill_Deception"
ASCENSION = "GD_Assassin_Skills.Sniping.CriticalAscention"
ASCENSION_STACK = ASCENSION + "_Stack"
_ascension_configured = False
OPTICS = "GD_Assassin_Skills.Sniping.Optics"
OPTICS_ACCURACY_ATTRIBUTE = "D_Attributes.Weapon.WeaponSpread"
OPTICS_RECOIL_ATTRIBUTE = "D_Attributes.Weapon.WeaponPerShotAccuracyImpulse"
OPTICS_AIM_ATTRIBUTE = "D_Attributes.GameplayAttributes.PlayerZoomTimeModifier"
OPTICS_BONUSES = ((OPTICS_ACCURACY_ATTRIBUTE, -.20, "Accuracy"),
                 (OPTICS_RECOIL_ATTRIBUTE, -.12, "Recoil Reduction"),
                 (OPTICS_AIM_ATTRIBUTE, -.10, "Aim Speed"))
LIKE_THE_WIND = "GD_Assassin_Skills.Bloodshed.LikeTheWind"
LIKE_THE_WIND_LEGACY = LIKE_THE_WIND + "_Active"
LIKE_THE_WIND_AVOID_PER_RANK = .05
BE_LIKE_WATER = "GD_Assassin_Skills.Bloodshed.BeLikeWater"
WATER_MOVEMENT = BE_LIKE_WATER + ":ZR_Movement"
WATER_LEGACY = (BE_LIKE_WATER + "_Melee_Active", BE_LIKE_WATER + "_Ranged_Active")
WATER_SPEED_ATTRIBUTE = "D_Attributes.GameplayAttributes.FootSpeed"
WATER_BONUS_PER_RANK = .02
WATER_STACK_INTERVAL = .5
WATER_STACK_LIMIT = 5
WATER_HUD_PATHS = (BE_LIKE_WATER + ":ZR_MovementHUD", BE_LIKE_WATER + ":ZR_DamageHUD")
_water_hud_definitions: tuple[Any, ...] = ()
_water_hud_visible: set[int] = set()
_water_hud_counts: tuple[int, int] | None = None
_water_hud_next_check = 0.
WATER_DAMAGE_ATTRIBUTE = "D_Attributes.DamageSourceModifiers.ReceivedBulletDamageModifier"
WATER_DAMAGE_FIELDS = tuple("Received" + name + "DamageModifier" for name in
                           ("Bullet", "Grenade", "Melee", "Rocket", "StatusEffect", "Skill"))
WATER_SOURCE_FIELDS = {"WillowDmgSource_" + name: field for name, field in zip(
    ("Bullet", "Grenade", "Melee", "Rocket", "StatusEffect", "Skill"), WATER_DAMAGE_FIELDS)}
PRECISION = "GD_Assassin_Skills.Sniping.Precision"
INNERVATE = "GD_Assassin_Skills.Cunning.Innervate"
INNERVATE_DAMAGE = "D_Attributes.Weapon.WeaponDamage"
INNERVATE_REGEN_DISPLAY = "D_Attributes.HealthResourcePool.HealthActiveRegenerationRate"
INNERVATE_REGEN = "D_Attributes.HealthResourcePool.HealthPassiveRegenerationRate"
_one_hud_definitions: tuple[Any, ...] = ()
_one_hud_visible: set[int] = set()
_one_hud_counts: tuple[int, ...] | None = None
_one_hud_next_check = 0.
ONE_WITH_GUN = "GD_Assassin_Skills.Sniping.AtOneWithTheGun"
ONE_HIPFIRE = ONE_WITH_GUN + "_IsNotIronsighting"
ONE_AMP_PER_RANK = .20
UNFORSEEN = "GD_Assassin_Skills.Cunning.Unforseen"
UNFORSEEN_BEHAVIOR = "GD_Assassin_Skills.ActionSkill.Skill_Stealth:BehaviorProviderDefinition_0.Behavior_CauseDamage_0"
DEATH_MARK = "GD_Assassin_Skills.Cunning.DeathMark"
DEATH_MARK_EFFECT = DEATH_MARK + "_Marked"
UNFORSEEN_DECEPTION_STACKS = "GD_Assassin_Skills.Misc.Att_NumberOfDamageBuffs"
UNFORSEEN_PULL_RADIUS = 1400.  # Shared pull/damage radius: 14 meters.
UNFORSEEN_PULL_MOMENTUM = -110000.
PRECISION_HELPER = PRECISION + ":ZR_Ricochet"
PRECISION_PROVIDER = PRECISION + ":ZR_RicochetGraph"
PRECISION_CHANCE = "D_Attributes.BulletReflection.BulletReflectionOffEnemyChance"
PRECISION_DAMAGE_ATTRIBUTE = PRECISION + ":ZR_ReflectedDamage"
PRECISION_RICOCHET_RADIUS = 3000  # Native BulletReflectionRadius is int; 100 world units/metre.
RESISTANCE_ATTRIBUTES = tuple("D_Attributes.DamageTypeModifers." + name for name in (
    "NormalImpactDamageModifier", "ExplosiveImpactDamageModifier",
    "CorrosiveImpactDamageModifier", "CorrosiveStatusEffectDamageModifier",
    "IncendiaryImpactDamageModifier", "IncendiaryStatusEffectDamageModifier",
    "ShockImpactDamageModifier", "ShockStatusEffectDamageModifier", "AmpImpactDamageModifier"))

_iron_hand_configured = False
_grim_configured = False
_grim_regen_scales: tuple[tuple[float, float], ...] | None = None
_fearless_configured = False
_resurgence_configured = False
_resurgence_context: tuple[int, int, int, int, int, float] | None = None
_resurgence_restoring = False
_kill_confirmed_configured = False
_kill_confirmed_helper: Any = None
_velocity_configured = False
_many_must_fall_configured = False
_optics_configured = False
_like_the_wind_configured = False
_like_the_wind_context: tuple[int, int, int, int, float] | None = None
_like_the_wind_ref: Any = None  # Weak reference to the current native skill, never an actor cache.
_water_configured = False
_water_movement_definition: Any = None
_water_enemy_opinion: int | None = None
_water_context: tuple[int, int, int, int, float] | None = None
_water_main_ref: Any = None
_water_movement_ref: Any = None
_water_state: dict[str, Any] | None = None
_water_applied_grade = 0
_water_next_check = 0.
_water_mutating = False
_water_needs_sync = False
_water_damage_frames: list[dict[str, Any] | None] = []
_water_damage_attributes: dict[str, Any] = {}
_water_damage_pool: dict[tuple[int, str], Any] = {}
_water_source_cache: dict[str, tuple[str, ...]] = {}
_precision_configured = False
_innervate_configured = False
_one_configured = False
_one_enemy_opinion: int | None = None
_one_source_cache: dict[str, bool] = {}
_one_context: tuple[int, int, int, int, float] | None = None
_one_main_ref: Any = None
_one_state: dict[str, Any] | None = None
_one_frames: list[dict[str, Any] | None] = []
_one_weapons: dict[int, tuple[Any, float, dict[str, Any]]] = {}
_one_projectiles: dict[int, tuple[Any, float, dict[str, Any]]] = {}
_one_amp_modifiers: tuple[Any, ...] = ()
_two_fang_definition: Any = None
_two_fang_frames: list[dict[str, Any] | None] = []
_unforseen_damage_stacks: Any = None  # Static native attribute; no actor retained.
_unforseen_configured = False
_unforseen_address = 0
_unforseen_enemy_opinion: int | None = None
_unforseen_main_ref: Any = None
_unforseen_context: tuple[int, int, int, float] | None = None
_unforseen_pull: Any = None  # Private static behavior, no persistent actor context.
_unforseen_frames: list[dict[str, Any] | None] = []
_precision_context: tuple[int, int, int, int, float] | None = None
_precision_main_ref: Any = None
_precision_arm_address = 0
_precision_helper_definition: Any = None
_precision_pulse_modifiers: tuple[Any, Any] | None = None
_precision_enemy_opinion: int | None = None
_precision_reflection_types: tuple[int, int] | None = None
_precision_frames: list[dict[str, Any] | None] = []
_precision_pending: dict[str, Any] | None = None
_precision_targets: dict[int, tuple[int, float, Any]] = {}
_kill_confirmed_context: tuple[int, int, int, int, float] | None = None
_kill_confirmed_count = 0
_kill_confirmed_aiming: bool | None = None
_kill_confirmed_deadline = 0.
_kill_confirmed_next_check = 0.
_kill_confirmed_updating = False
_owner: tuple[int, int, int] | None = None
_next_check = 0.
_signatures: dict[int, tuple[Any, ...]] = {}
_reported: set[str] = set()


def _path(obj: Any) -> str | None:
    return str(obj._path_name()) if obj is not None else None


def _find(kind: str, path: str) -> Any | None:
    try:
        return unrealsdk.find_object(kind, path)
    except ValueError:
        return None  # Character assets can be streamed after the main menu.


def _report(where: str, error: Exception) -> None:
    key = f"{where} [{type(error).__name__}]"
    if key not in _reported:
        _reported.add(key)
        unrealsdk.logging.error(f"[Zer0Rebalance] {where}: {error}")


def _layout(effect: Any) -> tuple[Any, ...]:
    return tuple(getattr(effect, field, None) for field in (
        "AttributeToModify", "EffectTarget", "ModifierType", "TargetInstanceDataName", "TargetCriteria"))


def _same_effect(old: Any, new: Any) -> bool:
    if (_layout(old) != _layout(new)
            or getattr(old, "GradeToStartApplyingEffect", None) != new.GradeToStartApplyingEffect
            or getattr(old, "PerGradeUpgradeInterval", None) != new.PerGradeUpgradeInterval
            or list(getattr(old, "BonusUpgradeList", ()) or ()) != list(getattr(new, "BonusUpgradeList", ()) or ())):
        return False
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        left, right = getattr(old, field), getattr(new, field)
        if (left.BaseValueAttribute != right.BaseValueAttribute
                or left.InitializationDefinition != right.InitializationDefinition
                or not math.isclose(float(left.BaseValueConstant), float(right.BaseValueConstant), abs_tol=1e-7)
                or not math.isclose(float(left.BaseValueScaleConstant), float(right.BaseValueScaleConstant), abs_tol=1e-7)):
            return False
    return True


def _configure_iron_hand() -> bool:
    global _iron_hand_configured
    definition = _find("SkillDefinition", IRON_HAND)
    attributes = [_find("AttributeDefinition", path) for path in RESISTANCE_ATTRIBUTES]
    if definition is None or any(attribute is None for attribute in attributes):
        return False
    effects = list(definition.SkillEffectDefinitions)
    paths = [_path(effect.AttributeToModify) for effect in effects]
    allowed = (HEALTH_ATTRIBUTE, MELEE_ATTRIBUTE, *RESISTANCE_ATTRIBUTES)
    if (paths.count(HEALTH_ATTRIBUTE) != 1 or any(path not in allowed for path in paths)
            or any(paths.count(path) > 1 for path in allowed)):
        raise ValueError(f"Unexpected Iron Hand effects: {paths}")
    health = effects[paths.index(HEALTH_ATTRIBUTE)]
    template = effects[paths.index(MELEE_ATTRIBUTE)] if MELEE_ATTRIBUTE in paths else effects[0]
    stat = _find("AttributePresentationDefinition", IRON_HAND + ":AttributePresentationDefinition_1")
    health_stat = _find("AttributePresentationDefinition", IRON_HAND + ":AttributePresentationDefinition_0")
    if stat is None or health_stat is None:
        return False
    modes, targets = unrealsdk.find_enum("EModifierType"), unrealsdk.find_enum("EEffectTarget")
    desired = [health]  # Preserve native health coefficients, initializers and class-mod behavior.
    for attribute in attributes:
        effect = copy.copy(template)
        effect.AttributeToModify, effect.EffectTarget, effect.ModifierType = attribute, targets.TARGET_Self, modes.MT_Scale
        effect.GradeToStartApplyingEffect, effect.PerGradeUpgradeInterval, effect.BonusUpgradeList = 1, 1, []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(template, field))
            value.BaseValueConstant, value.BaseValueScaleConstant = -IRON_HAND_RESISTANCE_PER_RANK, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(effect, field, value)
        desired.append(effect)
    changed = len(effects) != len(desired) or any(not _same_effect(old, new) for old, new in zip(effects, desired))
    if changed:
        definition.SkillEffectDefinitions = desired
        _signatures.clear()
    settings = dict(Attribute=attributes[0], Description="Damage Reduction: $NUMBER$",
                    bDisplayAsPercentage=True, bDisplayAsInverse=False,
                    SignStyle=unrealsdk.find_enum("EAttributeValueSignStyle").SIGNSTYLE_Positive,
                    bDontDisplayPlusSign=False, bUseCustomNumberPlacement=True)
    for field, value in settings.items():
        if getattr(stat, field) != value:
            setattr(stat, field, value)
    if list(definition.SkillEffectPresentations) != [stat, health_stat]:
        definition.SkillEffectPresentations = [stat, health_stat]
    description = "Increases your [skill]Maximum Health[-skill] and [skill]Damage Reduction[-skill]."
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    _iron_hand_configured = True
    if "Iron Hand configured" not in _reported:
        _reported.add("Iron Hand configured")
        unrealsdk.logging.info("[Zer0Rebalance] Iron Hand: melee damage removed; native resistance 5% per effective rank; maximum health unchanged")
    return changed


def _configure_grim() -> bool:
    global _grim_configured, _grim_regen_scales
    definition = _find("SkillDefinition", GRIM)
    if definition is None:
        return False
    effects = list(definition.SkillEffectDefinitions)
    paths = [_path(effect.AttributeToModify) for effect in effects]
    if paths != ["D_Attributes.ShieldResourcePool.ShieldPassiveRegenerationRate", None, GRIM_COOLDOWN_ATTRIBUTE]:
        raise ValueError(f"Unexpected Grim effects: {paths}")
    old = effects[2]
    effect = copy.copy(old)
    effect.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    effect.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
    effect.GradeToStartApplyingEffect, effect.PerGradeUpgradeInterval, effect.BonusUpgradeList = 1, 1, []
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(old, field))
        value.BaseValueConstant, value.BaseValueScaleConstant = GRIM_COOLDOWN_PER_RANK, 1.
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(effect, field, value)
    if _grim_regen_scales is None:
        _grim_regen_scales = tuple((float(row.BaseModifierValue.BaseValueScaleConstant),
                                   float(row.PerGradeUpgrade.BaseValueScaleConstant)) for row in effects[:2])
    regeneration = []
    for row, scales in zip(effects[:2], _grim_regen_scales):
        updated = copy.copy(row)
        for field, original_scale in zip(("BaseModifierValue", "PerGradeUpgrade"), scales):
            value = copy.copy(getattr(row, field))
            value.BaseValueScaleConstant = original_scale * GRIM_SHIELD_REGEN_FACTOR
            setattr(updated, field, value)
        regeneration.append(updated)
    desired = [*regeneration, effect]
    changed = any(not _same_effect(a, b) for a, b in zip(effects, desired))
    if changed:
        definition.SkillEffectDefinitions = desired
        _signatures.clear()
    _grim_configured = True
    if "Grim configured" not in _reported:
        _reported.add("Grim configured")
        unrealsdk.logging.info("[Zer0Rebalance] Grim: cooldown rate +8% per effective rank; shield regeneration 1.1% per second per effective rank; kill trigger preserved")
    return changed


def _configure_fearless() -> bool:
    global _fearless_configured
    definition = _find("SkillDefinition", FEARLESS)
    condition = _find("AttributeExpressionEvaluator", FEARLESS_CONDITION)
    maximum = _find("ResourcePoolAttributeDefinition", "D_Attributes.ShieldResourcePool.ShieldMaxValue")
    if definition is None or condition is None or maximum is None:
        return False
    expression = condition.Expression
    if _path(expression.AttributeOperand1) != "D_Attributes.ShieldResourcePool.ShieldCurrentValue":
        raise ValueError("Unexpected Fearless shield condition")
    effects = list(definition.SkillEffectDefinitions)
    amounts = {"D_Attributes.Weapon.WeaponDamage": .04,
               "D_Attributes.Weapon.WeaponFireInterval": -.05}
    paths = [_path(row.AttributeToModify) for row in effects]
    if len(paths) != 2 or set(paths) != set(amounts):
        raise ValueError(f"Unexpected Fearless effects: {paths}")
    desired = []
    for row, path in zip(effects, paths):
        if path is None:
            raise ValueError("Fearless effect has no attribute")
        updated = copy.copy(row)
        updated.GradeToStartApplyingEffect, updated.PerGradeUpgradeInterval, updated.BonusUpgradeList = 1, 1, []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(row, field))
            value.BaseValueConstant, value.BaseValueScaleConstant = amounts[path], 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(updated, field, value)
        desired.append(updated)
    effects_changed = any(not _same_effect(a, b) for a, b in zip(effects, desired))
    comparison = unrealsdk.find_enum("EComparisonOperator").OPERATOR_GreaterThan
    usage = unrealsdk.find_enum("EOperandUsage").OPERAND_Multiply
    changed = (expression.ComparisonOperator != comparison or expression.Operand2Usage != usage
        or expression.AttributeOperand2 != maximum
        or not math.isclose(float(expression.ConstantOperand2), 0., abs_tol=1e-8))
    if changed:
        expression = copy.copy(expression)
        expression.ComparisonOperator, expression.Operand2Usage = comparison, usage
        expression.AttributeOperand2, expression.ConstantOperand2 = maximum, 0.
        condition.Expression = expression
    if effects_changed:
        definition.SkillEffectDefinitions = desired
        _signatures.clear()
    description = ("While you have shields, you gain a bonus to [skill]Gun Damage[-skill] "
                   "and [skill]Fire Rate[-skill].")
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    _fearless_configured = True
    if "Fearless configured" not in _reported:
        _reported.add("Fearless configured")
        unrealsdk.logging.info("[Zer0Rebalance] Fearless: any positive shield value required; fire rate +5% and gun damage +4% per effective rank")
    return changed or effects_changed


def _configure_resurgence() -> bool:
    global _resurgence_configured
    definition = _find("SkillDefinition", RESURGENCE)
    maximum = _find("ResourcePoolAttributeDefinition", SHIELD_MAX_ATTRIBUTE)
    template_stat = _find("AttributePresentationDefinition", RESURGENCE+":AttributePresentationDefinition_0")
    per_rank = _find("DesignerAttributeDefinition", RESURGENCE_HEALTH_ATTRIBUTE)
    provider = _find("BehaviorProviderDefinition", RESURGENCE_PROVIDER)
    if definition is None or maximum is None or template_stat is None or per_rank is None or provider is None:
        return False
    # Validate the captured native graph before changing its one integer binding.
    if _path(definition.BehaviorProviderDefinition) != RESURGENCE_PROVIDER or len(provider.BehaviorSequences) != 1:
        raise ValueError("Unexpected Resurgence healing provider")
    sequence = provider.BehaviorSequences[0]
    expected_nodes = ("Behavior_SimpleMath_257", "Behavior_SimpleMath_258", "Behavior_SimpleMath_259",
                      "Behavior_ActivateSkill_62", "Behavior_SimpleMath_260")
    if ([_path(node.Behavior) for node in sequence.BehaviorData2] != [RESURGENCE_PROVIDER + "." + n for n in expected_nodes]
            or len(sequence.ConsolidatedLinkedVariables) != 19 or len(sequence.VariableData) != 9
            or len(sequence.ConsolidatedVariableLinkData) != 14):
        raise ValueError("Unexpected Resurgence healing graph layout")
    binding = sequence.ConsolidatedVariableLinkData[3]
    if (str(binding.PropertyName) != "A" or int(binding.LinkedVariables.ArrayIndexAndLength) != (8 << 16 | 1)
            or int(sequence.ConsolidatedLinkedVariables[8]) not in (4, 6)):
        raise ValueError("Unexpected Resurgence healing amount input")
    graph_changed = int(sequence.ConsolidatedLinkedVariables[8]) != 6
    native_coefficient = copy.copy(per_rank.BaseValue)
    coefficient = copy.copy(native_coefficient)
    coefficient.BaseValueConstant, coefficient.BaseValueScaleConstant = RESURGENCE_HEALTH_PER_RANK, 1.
    coefficient.BaseValueAttribute = coefficient.InitializationDefinition = None
    coefficient_changed = not _same_initialization(native_coefficient, coefficient)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_path(row.AttributeToModify) for row in effects]
    if paths not in (["D_Attributes.HealthResourcePool.HealthPassiveRegenerationRate"],
                    ["D_Attributes.HealthResourcePool.HealthPassiveRegenerationRate", SHIELD_MAX_ATTRIBUTE]):
        raise ValueError(f"Unexpected Resurgence effects: {paths}")
    events = list(definition.KillEvents)
    matches = [index for index, event in enumerate(events) if str(event.EventName) == "KilledEnemyWithMelee"]
    if len(matches) != 1:
        raise ValueError("Resurgence's native healing kill event is unavailable or ambiguous")
    event_index = matches[0]
    constraints = list(events[event_index].EventConstraints)
    if len(constraints) != 1 or _path(constraints[0].DamageSourceConstraint) not in (None, "WillowGame.WillowDmgSource_Melee"):
        raise ValueError("Unexpected Resurgence kill-source constraint")
    kill_changed = constraints[0].DamageSourceConstraint is not None
    display = copy.copy(effects[0])
    display.AttributeToModify = maximum
    display.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_None
    display.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
    display.GradeToStartApplyingEffect, display.PerGradeUpgradeInterval, display.BonusUpgradeList = 1,1,[]
    for field in ("BaseModifierValue","PerGradeUpgrade"):
        value = copy.copy(getattr(display,field))
        value.BaseValueConstant, value.BaseValueScaleConstant = RESURGENCE_SHIELD_PER_RANK,1.
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(display,field,value)
    # This TARGET_None row is metadata only. Gameplay reads the Designer attribute above.
    healing = copy.copy(effects[0])
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(healing, field))
        value.BaseValueConstant, value.BaseValueScaleConstant = RESURGENCE_HEALTH_PER_RANK, 1.
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(healing, field, value)
    changed = (not _same_effect(effects[0], healing)
               or len(effects)==1 or not _same_effect(effects[1],display))
    stat = _find("AttributePresentationDefinition",RESURGENCE+":ZR_CriticalShield")
    if stat is None:
        stat = unrealsdk.construct_object("AttributePresentationDefinition",definition,"ZR_CriticalShield",
            template_obj=template_stat,flags=int(ObjectFlags.KEEP_ALIVE))
    if stat is None:
        return False
    for field,value in dict(Attribute=maximum,Description="Shield Restored per Critical Hit: $NUMBER$",
            bDisplayAsPercentage=True,bDisplayAsInverse=False,bDontDisplayPlusSign=False,
            bUseCustomNumberPlacement=True).items():
        if getattr(stat,field)!=value:
            setattr(stat,field,value)
    if graph_changed:
        # Node258 A: variable4 (missing HP) -> variable6 (maximum HP).
        # Mutate only this integer cell; never replace borrowed graph/sequence arrays.
        sequence.ConsolidatedLinkedVariables[8] = 6
    if coefficient_changed:
        per_rank.BaseValue = coefficient
    template_stat.Description = "Health Restored per Kill: $NUMBER$"
    if changed:
        definition.SkillEffectDefinitions = [healing,display]  # Native health formula and display-only shield row.
        _signatures.clear()
    if list(definition.SkillEffectPresentations)!=[template_stat,stat]:
        definition.SkillEffectPresentations = [template_stat,stat]
    if kill_changed:
        constraint = copy.copy(constraints[0])
        constraint.DamageSourceConstraint = None
        event = copy.copy(events[event_index])
        event.EventConstraints = [constraint]
        events[event_index] = event
        definition.KillEvents = events  # Keep the event name used by the native healing graph.
    definition.SkillDescription = (
        "[skill]Killing an enemy[-skill] restores a portion of your [skill]Maximum Health[-skill]. "

        "Landing a [skill]Critical Hit[-skill] also restores a portion of your [skill]Maximum Shield[-skill].")
    _resurgence_configured = True
    if "Resurgence configured" not in _reported:
        _reported.add("Resurgence configured")
        unrealsdk.logging.info("[Zer0Rebalance] Resurgence: enemy kills restore 6% maximum health per rank; missing-health scaling removed; critical hits restore 4% maximum shield per effective rank")
    return changed or kill_changed or graph_changed or coefficient_changed


def restore_resurgence_shield(stats: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _resurgence_restoring
    cached = _resurgence_context
    if (cached is None or _resurgence_restoring or stats is None or int(stats._get_address())!=cached[3]):
        return
    try:
        controller = get_pc(possibly_loading=True)
        if (controller is None or controller.bDeleteMe or controller.PlayerStats!=stats
                or _path(controller.PlayerClass)!=ZER0_CLASS
                or int(controller.Role)!=int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
            return
        world,pawn = controller.WorldInfo,controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.Controller!=controller or pawn.IsInjuredDead() or _owner!=cached[:3]
                or (int(controller._get_address()),int(world._get_address()),int(pawn._get_address()))!=cached[:3]):
            return
        now = float(world.TimeSeconds)
        if not math.isfinite(now) or not 0.<=now-cached[5]<=1.5:
            return
        current,maximum = float(pawn.GetShieldStrength()),float(pawn.GetMaxShieldStrength())
        if not math.isfinite(current) or not math.isfinite(maximum) or not 0.<=current<maximum:
            return
        restored = min(maximum,current+maximum*RESURGENCE_SHIELD_PER_RANK*cached[4])
        if restored<=current:
            return
        _resurgence_restoring = True
        try:
            pawn.SetShieldStrength(restored)
        finally:
            _resurgence_restoring = False
        # No native actor accesses after the shield write's callbacks.
    except (AttributeError,TypeError,ValueError,RuntimeError) as exc:
        _report("Could not restore Resurgence shield",exc)


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.POST)
def restore_resurgence_on_critical(pipeline: Any, args: Any, _ret: Any, _func: Any) -> None:
    cached = _resurgence_context
    if cached is None or _resurgence_restoring:
        return
    try:
        controller = args.InDamageInstigator
        if controller is None or int(controller._get_address()) != cached[0]:
            return
        summary = pipeline.DamageSummary
        target = args.InDamagedActor
        if (not summary.bWasCrit or target is None or target == controller.Pawn
                or not math.isfinite(float(args.IncomingDamage)) or float(args.IncomingDamage) <= 0.
                or float(summary.FinalDamage) + float(summary.DamageDealtToShields) <= 0.):
            return
        restore_resurgence_shield(controller.PlayerStats, None, None, None)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not process Resurgence critical hit", exc)


def _configure_kill_confirmed() -> bool:
    global _kill_confirmed_configured, _kill_confirmed_helper
    definition = _find("SkillDefinition", KILL_CONFIRMED)
    helper = _find("SkillDefinition", KILL_CONFIRMED_STACK)
    if definition is None or helper is None:
        return False
    # Retain native per-stack damage/COM calculation, constraints, icon and HUD.
    # Replace the original graph that clears every stack immediately on unzoom.
    changed = definition.BehaviorProviderDefinition is not None
    if changed:
        definition.BehaviorProviderDefinition = None
    _kill_confirmed_helper = helper
    _kill_confirmed_configured = True
    return changed


def _change_kill_confirmed_count(controller: Any, desired: int) -> bool:
    global _kill_confirmed_count, _kill_confirmed_updating
    if _kill_confirmed_updating or desired == _kill_confirmed_count:
        return False
    helper = _kill_confirmed_helper
    if helper is None:
        return False
    manager = controller.GetSkillManager()
    identity = _owner
    if manager is None or getattr(manager, "bUpdatingSkills", False):
        return False
    _kill_confirmed_updating = True
    try:
        if desired > _kill_confirmed_count:
            if manager.ActivateSkill(controller, helper, None, 1) is False:
                return True
            delta = 1
        else:
            manager.DeactivateSkill(controller, helper)
            delta = -1
        # Native callbacks may travel, disable the mod or replace the character.
        if _owner == identity and _kill_confirmed_context is not None:
            _kill_confirmed_count = max(0, min(5, _kill_confirmed_count + delta))
        return True
    finally:
        _kill_confirmed_updating = False


def _tick_kill_confirmed(controller: Any) -> bool | None:
    global _kill_confirmed_aiming, _kill_confirmed_deadline, _kill_confirmed_next_check
    cached = _kill_confirmed_context
    if cached is None or _kill_confirmed_updating or controller is None or int(controller._get_address()) != cached[0] or controller.bDeleteMe:
        return
    clock = time.monotonic()
    try:
        world = controller.WorldInfo
        if world is None or world.bDeleteMe:
            return
        if clock < _kill_confirmed_next_check and float(world.TimeSeconds) + 1.e-6 < _kill_confirmed_deadline:
            return
        _kill_confirmed_next_check = clock + .05
        if (controller != get_pc(possibly_loading=True) or controller.bDeleteMe
                or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.Controller != controller or _owner != cached[:3]
                or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != cached[:3]):
            return
        now = float(world.TimeSeconds)
        if not math.isfinite(now) or not 0. <= now - cached[4] <= 1.5:
            return
        if cached[3] <= 0 or pawn.IsInjuredDead():
            _kill_confirmed_aiming = None
            return _change_kill_confirmed_count(controller, 0)
        aiming = bool(controller.IsZoomed())
        interval = KILL_CONFIRMED_GAIN_INTERVAL if aiming else KILL_CONFIRMED_DECAY_INTERVAL
        if aiming != _kill_confirmed_aiming:
            _kill_confirmed_aiming = aiming
            _kill_confirmed_deadline = now + interval
        if now + 1.e-6 < _kill_confirmed_deadline:
            return
        _kill_confirmed_deadline = now + interval
        desired = min(5, _kill_confirmed_count + 1) if aiming else max(0, _kill_confirmed_count - 1)
        return _change_kill_confirmed_count(controller, desired)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not update Kill Confirmed stacks", exc)


def _configure_velocity() -> bool:
    global _velocity_configured
    definition = _find("SkillDefinition", VELOCITY)
    if definition is None:
        return False
    effects = list(definition.SkillEffectDefinitions)
    paths = [_path(row.AttributeToModify) for row in effects]
    allowed = (VELOCITY_GUN_DAMAGE, VELOCITY_PROJECTILE_SPEED, VELOCITY_CRITICAL_DAMAGE)
    if (paths.count(VELOCITY_GUN_DAMAGE) != 1 or paths.count(VELOCITY_PROJECTILE_SPEED) != 1
            or paths.count(VELOCITY_CRITICAL_DAMAGE) > 1 or any(path not in allowed for path in paths)):
        raise ValueError(f"Unexpected Velocity effects: {paths}")
    damage = copy.copy(effects[paths.index(VELOCITY_GUN_DAMAGE)])
    damage.GradeToStartApplyingEffect, damage.PerGradeUpgradeInterval, damage.BonusUpgradeList = 1, 1, []
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(damage, field))
        value.BaseValueConstant, value.BaseValueScaleConstant = VELOCITY_GUN_DAMAGE_PER_RANK, 1.
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(damage, field, value)
    updated = [damage if path == VELOCITY_GUN_DAMAGE else row
               for path, row in zip(paths, effects) if path != VELOCITY_CRITICAL_DAMAGE]
    changed = len(updated) != len(effects) or not _same_effect(effects[paths.index(VELOCITY_GUN_DAMAGE)], damage)
    if changed:
        definition.SkillEffectDefinitions = updated
        _signatures.clear()
    presentations = list(definition.SkillEffectPresentations)
    retained = [stat for stat in presentations if _path(stat.Attribute) != VELOCITY_CRITICAL_DAMAGE]
    if retained != presentations:
        definition.SkillEffectPresentations = retained
    definition.SkillDescription = "Increases [skill]Bullet Speed[-skill] and [skill]Gun Damage[-skill] with all guns."
    _velocity_configured = True
    return changed


def _configure_mmf_weapon_gate() -> bool | None:
    """Use the native end delay, without melee's unavailable Enemy output, for MMF shots."""
    stealth = _find("SkillDefinition", "GD_Assassin_Skills.ActionSkill.Skill_Stealth")
    template = _find("Behavior_Conditional", DECEPTION + ":BehaviorProviderDefinition_0.Behavior_Conditional_121")
    if stealth is None or template is None or stealth.BehaviorProviderDefinition is None:
        return None
    provider = stealth.BehaviorProviderDefinition
    sequences = [copy.copy(row) for row in provider.BehaviorSequences]
    if not sequences:
        return None
    # WrappedArray elements are borrowed views. Detach EVERY row before replacing
    # its array: native assignment clears the destination before converting inputs.
    sequence = sequences[0]
    events = [copy.copy(row) for row in sequence.EventData2]
    by_name = {str(e.UserData.EventName): i for i, e in enumerate(events)}
    if not all(n in by_name for n in ("OnWeaponFired", "Damaged an Enemy with Melee")):
        raise ValueError("MMF native weapon/melee events unavailable")
    fire = copy.copy(events[by_name["OnWeaponFired"]])
    melee = events[by_name["Damaged an Enemy with Melee"]]
    nodes = [copy.copy(row) for row in sequence.BehaviorData2]
    outputs = [copy.copy(row) for row in sequence.ConsolidatedOutputLinkData]
    variables = [copy.copy(row) for row in sequence.ConsolidatedVariableLinkData]
    def sub(value: Any) -> tuple[int, int]:
        packed = int(value.ArrayIndexAndLength)
        return packed >> 16, packed & 65535
    def graph_signature(nodes: Any, outputs: Any, variables: Any, events: Any) -> tuple[Any, ...]:
        return (
            tuple((row.Behavior, int(row.LinkedVariables.ArrayIndexAndLength),
                   int(row.OutputLinks.ArrayIndexAndLength)) for row in nodes),
            tuple((int(row.LinkIdAndLinkedBehavior), float(row.ActivateDelay))
                  for row in outputs),
            tuple((str(row.PropertyName), int(row.ConnectionIndex), int(row.LinkedVariables.ArrayIndexAndLength))
                  for row in variables),
            tuple((str(row.UserData.EventName), int(row.OutputLinks.ArrayIndexAndLength),
                   int(row.OutputVariables.ArrayIndexAndLength)) for row in events),
        )
    fi, fc = sub(fire.OutputLinks)
    mi, mc = sub(melee.OutputLinks)
    fv, fvc = sub(fire.OutputVariables)
    mv, mvc = sub(melee.OutputVariables)
    if (fc != 1 or mc != 1 or fvc < 1 or mvc < 1 or fi >= len(outputs) or mi >= len(outputs)
            or fv + fvc > len(variables) or mv + mvc > len(variables)):
        raise ValueError("Unexpected MMF native event link layout")
    target = int(outputs[fi].LinkIdAndLinkedBehavior) & 0xffffff
    if not 0 <= target < len(nodes):
        raise ValueError("Invalid MMF weapon destination")
    provider_path = _path(provider)
    if provider_path is None:
        return None
    delays = [i for i, node in enumerate(nodes)
              if _path(node.Behavior) == provider_path + ".Behavior_Delay_68"]
    if len(delays) != 1:
        raise ValueError("MMF native end delay unavailable or ambiguous")
    delay_target = delays[0]
    if _path(nodes[target].Behavior) == provider_path + ".ZR_MMFWeaponGate":
        start, count = sub(nodes[target].OutputLinks)
        if count != 2 or start + count > len(outputs):
            raise ValueError("Unexpected MMF weapon gate outputs")
        yes = copy.copy(outputs[start])
        desired = (1 << 24) | delay_target
        if int(yes.LinkIdAndLinkedBehavior) == desired:
            return False
        yes.LinkIdAndLinkedBehavior = desired
        outputs[start] = yes
        expected = graph_signature(nodes, outputs, variables, events)
        sequence.ConsolidatedOutputLinkData = outputs
        sequences[0] = sequence
        provider.BehaviorSequences = sequences
        if graph_signature(provider.BehaviorSequences[0].BehaviorData2,
                           provider.BehaviorSequences[0].ConsolidatedOutputLinkData,
                           provider.BehaviorSequences[0].ConsolidatedVariableLinkData,
                           provider.BehaviorSequences[0].EventData2) != expected:
            raise RuntimeError("MMF graph writeback did not preserve native rows")
        return True
    if (str(variables[fv].PropertyName) != "SkillInstigator"
            or str(variables[mv].PropertyName) != "SkillInstigator"):
        raise ValueError("MMF native event context layout changed")
    gate = _precision_object("Behavior_Conditional", provider, "ZR_MMFWeaponGate", template)
    # Output 1 is the native MMF-running condition; output 2 is its false branch.
    def make_sub(start: int, count: int) -> Any:
        result = copy.copy(fire.OutputLinks)
        result.ArrayIndexAndLength = (start << 16) | count
        return result
    first_output = len(outputs)
    yes, no = copy.copy(outputs[mi]), copy.copy(outputs[fi])
    # OnWeaponFired has no Enemy output. Starting the melee comparison with an
    # unset Enemy can bypass its end branch; start the existing delay directly.
    yes.LinkIdAndLinkedBehavior = (1 << 24) | delay_target
    no.LinkIdAndLinkedBehavior = (2 << 24) | target
    outputs.extend((yes, no))
    gate_node = copy.copy(nodes[target])
    gate_node.Behavior, gate_node.OutputLinks = gate, make_sub(first_output, 2)
    nodes.append(gate_node)
    # Bind the event's one controller output to both original and melee contexts.
    start = len(variables)
    variables.extend(copy.copy(v) for v in variables[fv:fv+fvc])
    variables.append(copy.copy(variables[mv]))
    fire.OutputVariables = make_sub(start, fvc + 1)
    replacement = copy.copy(outputs[fi])
    replacement.LinkIdAndLinkedBehavior = (int(replacement.LinkIdAndLinkedBehavior) & ~0xffffff) | (len(nodes)-1)
    outputs[fi] = replacement
    events[by_name["OnWeaponFired"]] = fire
    expected = graph_signature(nodes, outputs, variables, events)
    sequence.EventData2, sequence.BehaviorData2 = events, nodes
    sequence.ConsolidatedOutputLinkData, sequence.ConsolidatedVariableLinkData = outputs, variables
    sequences[0] = sequence
    provider.BehaviorSequences = sequences
    if graph_signature(provider.BehaviorSequences[0].BehaviorData2,
                           provider.BehaviorSequences[0].ConsolidatedOutputLinkData,
                           provider.BehaviorSequences[0].ConsolidatedVariableLinkData,
                           provider.BehaviorSequences[0].EventData2) != expected:
        raise RuntimeError("MMF graph writeback did not preserve native rows")
    return True


def _configure_many_must_fall() -> bool:
    global _many_must_fall_configured
    action = _find("SkillDefinition", DECEPTION)
    definition = _find("SkillDefinition", MANY_MUST_FALL)
    feedback = _find("SkillDefinition", MANY_MUST_FALL + "_Feedback")
    if action is None or definition is None or feedback is None:
        return False
    events = [copy.copy(row) for row in action.KillEvents]
    matches = [index for index, event in enumerate(events) if str(event.EventName) == "KilledEnemyWithMelee"]
    if len(matches) != 1:
        raise ValueError("Decepti0n's native Many Must Fall kill event is unavailable or ambiguous")
    index = matches[0]
    original = events[index]
    constraints = list(original.EventConstraints)
    if len(constraints) != 1 or _path(constraints[0].DamageSourceConstraint) not in (None, "WillowGame.WillowDmgSource_Melee"):
        raise ValueError("Unexpected Many Must Fall kill-source constraint")
    changed = constraints[0].DamageSourceConstraint is not None
    weapon_changed = _configure_mmf_weapon_gate()
    if weapon_changed is None:
        return False
    if changed:
        constraint = copy.copy(constraints[0])
        constraint.DamageSourceConstraint = None
        event = copy.copy(original)
        event.EventConstraints = [constraint]
        events[index] = event
        action.KillEvents = events
    # Preserve native kill dispatch, duration and decoy behavior; the weapon
    # gate uses the native end delay without evaluating a missing Enemy output.
    description = (
        "[skill]Killing an enemy[-skill] while [skill]Decepti0n[-skill] is active causes you to deploy "
        "another holographic decoy, re-stealth, and adds time to [skill]Decepti0n's[-skill] duration. "
        "This can be done multiple times in succession.")
    if definition.SkillDescription != description:
        definition.SkillDescription = description
    if feedback.SkillDescription != description:
        feedback.SkillDescription = description
    _many_must_fall_configured = True
    if "Many Must Fall weapon gate configured" not in _reported:
        _reported.add("Many Must Fall weapon gate configured")
        unrealsdk.logging.info("[Zer0Rebalance] Many Must Fall configured: native graph readback verified; native end delay for learned MMF; original renewal context preserved")
    return changed or weapon_changed


def _configure_optics() -> bool:
    global _optics_configured
    definition = _find("SkillDefinition", OPTICS)
    template_stat = _find("AttributePresentationDefinition", OPTICS + ":AttributePresentationDefinition_0")
    if definition is None or template_stat is None:
        return False
    attributes = [_find("AttributeDefinition", path) for path, _, _ in OPTICS_BONUSES]
    if attributes[2] is None:
        attributes[2] = _property_attribute(definition, "ZR_AimSpeed", "PawnAttributeContextResolver", "ZoomTimeModifier")
    if any(attribute is None for attribute in attributes):
        return False
    effects = list(definition.SkillEffectDefinitions)
    paths = [_path(row.AttributeToModify) for row in effects]
    native_paths = ["D_Attributes.Weapon.WeaponZoomEndFOV",
                    "D_Attributes.GameplayAttributes.PlayerAimDamageImpulseDuration",
                    "D_Attributes.GameplayAttributes.PlayerAimDamageImpulseMagnitude", OPTICS_RECOIL_ATTRIBUTE]
    native_tuned = [path for path, _, _ in OPTICS_BONUSES]
    private_tuned = native_tuned[:2] + [OPTICS + ":ZR_AimSpeed"]
    if paths not in (native_paths, native_tuned, private_tuned):
        raise ValueError(f"Unexpected Optics effects: {paths}")
    desired, stats = [], []
    for attribute, (_, amount, label) in zip(attributes, OPTICS_BONUSES):
        row = copy.copy(effects[0])
        row.AttributeToModify = attribute
        row.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_Self
        row.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
        row.GradeToStartApplyingEffect, row.PerGradeUpgradeInterval, row.BonusUpgradeList = 1, 1, []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(row, field))
            value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(row, field, value)
        desired.append(row)
        name = "ZR_Optics" + label.replace(" ", "")
        stat = _find("AttributePresentationDefinition", OPTICS + ":" + name)
        if stat is None:
            stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                template_obj=template_stat, flags=int(ObjectFlags.KEEP_ALIVE))
        if stat is None:
            return False
        for field, value in dict(Attribute=attribute, Description=label + ": $NUMBER$",
                bDisplayAsPercentage=True, bDisplayAsInverse=False,
                SignStyle=unrealsdk.find_enum("EAttributeValueSignStyle").SIGNSTYLE_Positive,
                bDontDisplayPlusSign=False, bUseCustomNumberPlacement=True).items():
            if getattr(stat, field) != value:
                setattr(stat, field, value)
        stats.append(stat)
    changed = len(effects) != len(desired) or any(not _same_effect(old, new) for old, new in zip(effects, desired))
    if changed:
        definition.SkillEffectDefinitions = desired
        _signatures.clear()
    if list(definition.SkillEffectPresentations) != stats:
        definition.SkillEffectPresentations = stats
    description = "Increases [skill]Accuracy[-skill] and [skill]Aim Speed[-skill], and reduces [skill]Recoil[-skill]."
    if definition.SkillDescription != description:
        definition.SkillDescription = description
    definition.SkillName = "Pin point"
    _optics_configured = True
    if "Optics configured" not in _reported:
        _reported.add("Optics configured")
        unrealsdk.logging.info("[Zer0Rebalance] Pin point configured: accuracy 20%, recoil reduction 12%, aim speed 10% per rank")
    return changed


def _configure_like_the_wind() -> bool:
    global _like_the_wind_configured
    definition = _find("SkillDefinition", LIKE_THE_WIND)
    legacy = _find("SkillDefinition", LIKE_THE_WIND_LEGACY)
    stat = _find("AttributePresentationDefinition", LIKE_THE_WIND + ":AttributePresentationDefinition_1")
    if definition is None or legacy is None or stat is None:
        return False
    effects = list(definition.SkillEffectDefinitions)
    paths = [_path(row.AttributeToModify) for row in effects]
    if paths not in ([VELOCITY_GUN_DAMAGE, MELEE_ATTRIBUTE], [VELOCITY_GUN_DAMAGE]):
        raise ValueError(f"Unexpected Like the Wind effects: {paths}")
    display = copy.copy(effects[0])
    display.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_None
    display.GradeToStartApplyingEffect, display.PerGradeUpgradeInterval, display.BonusUpgradeList = 1, 1, []
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(display, field))
        value.BaseValueConstant, value.BaseValueScaleConstant = LIKE_THE_WIND_AVOID_PER_RANK, 1.
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(display, field, value)
    changed = len(effects) != 1 or not _same_effect(effects[0], display)
    if changed:
        definition.SkillEffectDefinitions = [display]  # Rank-aware stat only, no gun/melee damage bonus.
        _signatures.clear()
    # The unused legacy melee graph/helper must not retain an old movement bonus.
    if definition.BehaviorProviderDefinition is not None:
        definition.BehaviorProviderDefinition = None
    if legacy.SkillEffectDefinitions:
        legacy.SkillEffectDefinitions = []
        _signatures.clear()
    for field, value in dict(Attribute=display.AttributeToModify, Description="Chance to Ignore Damage: $NUMBER$", bDisplayAsPercentage=True,
            bDisplayAsInverse=False, bDontDisplayPlusSign=False, bUseCustomNumberPlacement=True).items():
        if getattr(stat, field) != value:
            setattr(stat, field, value)
    if list(definition.SkillEffectPresentations) != [stat]:
        definition.SkillEffectPresentations = [stat]
    description = "While [skill]moving[-skill], you have a chance to [skill]completely ignore incoming damage[-skill]."
    if definition.SkillDescription != description:
        definition.SkillDescription = description
    # Keep the native movement/on-foot constraints, menu icon and reserved HUD slot 5.
    _like_the_wind_configured = True
    return changed


@hook("WillowGame.WillowPlayerPawn:TakeDamage", Type.PRE)
def avoid_like_the_wind_damage(pawn: Any, args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    cached, reference = _like_the_wind_context, _like_the_wind_ref
    if cached is None or reference is None:
        return None
    try:
        damage = float(args.Damage)
        if pawn is None or int(pawn._get_address()) != cached[2] or not math.isfinite(damage) or damage <= 0.:
            return None
        speed = float(pawn.CurrentPawnSpeed)  # Exact native Like the Wind movement operand.
        if not math.isfinite(speed) or speed <= 1.:
            return None
        controller = get_pc(possibly_loading=True)
        if (controller is None or controller.bDeleteMe or controller.Pawn != pawn or pawn.bDeleteMe
                or pawn.Controller != controller or pawn.IsInjuredDead()
                or _path(controller.PlayerClass) != ZER0_CLASS
                or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
            return None
        world = controller.WorldInfo
        if (world is None or world.bDeleteMe or world.Pauser or _owner != cached[:3]
                or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != cached[:3]):
            return None
        now = float(world.TimeSeconds)
        if not math.isfinite(now) or not 0. <= now - cached[4] <= 1.5:
            return None
        live = reference()
        if (live is None or live.SkillInstigator != controller or live.Definition is None
                or _path(live.Definition) != LIKE_THE_WIND
                or live.SkillState != unrealsdk.find_enum("ESkillState").SKILL_Active):
            return None
        rank = int(live.Grade)  # Native effective rank includes the current class mod exactly once.
        if rank > 0 and random.random() < min(1., LIKE_THE_WIND_AVOID_PER_RANK * rank):
            return Block
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not avoid Like the Wind damage", exc)
    return None


def _configure_be_like_water() -> bool:
    global _water_configured, _water_enemy_opinion, _water_movement_definition
    definition = _find("SkillDefinition", BE_LIKE_WATER)
    speed = _find("AttributeDefinition", WATER_SPEED_ATTRIBUTE)
    damage = _find("AttributeDefinition", WATER_DAMAGE_ATTRIBUTE)
    legacy = [_find("SkillDefinition", path) for path in WATER_LEGACY]
    stats = [_find("AttributePresentationDefinition", BE_LIKE_WATER + f":AttributePresentationDefinition_{i}") for i in (0, 1)]
    # The removed attack graph no longer keeps its old active skills loaded.
    # They are optional cleanup/icon sources, never dependencies of the new effect.
    if definition is None or any(item is None for item in stats):
        return False
    _water_enemy_opinion = int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)
    if speed is None:
        speed = _property_attribute(definition, "ZR_FootSpeed", "PawnAttributeContextResolver", "GroundSpeed")
    if damage is None:
        damage = _property_attribute(definition, "ZR_DamageDisplay", "ControllerAttributeContextResolver", "ReceivedBulletDamageModifier")
    effects = list(definition.SkillEffectDefinitions)
    paths = [_path(row.AttributeToModify) for row in effects]
    known = ([VELOCITY_GUN_DAMAGE, MELEE_ATTRIBUTE], [WATER_SPEED_ATTRIBUTE, VELOCITY_GUN_DAMAGE],
             *([move, dealt] for move in (WATER_SPEED_ATTRIBUTE, BE_LIKE_WATER+":ZR_FootSpeed")
               for dealt in (WATER_DAMAGE_ATTRIBUTE, BE_LIKE_WATER+":ZR_DamageDisplay")))
    if paths not in known:
        raise ValueError(f"Unexpected Be Like Water effects: {paths}")
    desired = []
    for attribute in (speed, damage):
        row = copy.copy(effects[0])
        row.AttributeToModify = attribute
        row.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
        row.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_None
        row.GradeToStartApplyingEffect, row.PerGradeUpgradeInterval, row.BonusUpgradeList = 1, 1, []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(row, field))
            value.BaseValueConstant, value.BaseValueScaleConstant = WATER_BONUS_PER_RANK, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(row, field, value)
        desired.append(row)
    helper = _find("SkillDefinition", WATER_MOVEMENT)
    if helper is None:
        helper = unrealsdk.construct_object("SkillDefinition", definition, "ZR_Movement",
            template_obj=definition, flags=int(ObjectFlags.KEEP_ALIVE))
    if helper is None:
        return False
    movement = copy.copy(desired[0])
    movement.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    properties = dict(SkillName="Be Like Water movement", bSubjectToGradeRules=False, MaxGrade=255,
        TrackedSkillType=unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked,
        DurationType=unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite,
        InitialDuration=0., BehaviorProviderDefinition=None, TrackedActiveSkill=None, CustomStackCount=None)
    for field, value in properties.items():
        if getattr(helper, field) != value:
            setattr(helper, field, value)
    if len(helper.SkillEffectDefinitions) != 1 or not _same_effect(helper.SkillEffectDefinitions[0], movement):
        helper.SkillEffectDefinitions = [movement]
    for field in ("DamageEvents", "KillEvents", "SkillEffectPresentations", "TrackedActiveSkills"):
        if getattr(helper, field):
            setattr(helper, field, [])
    changed = len(effects) != 2 or any(not _same_effect(old, new) for old, new in zip(effects, desired))
    if changed:
        definition.SkillEffectDefinitions = desired
        _signatures.clear()
    definition.BehaviorProviderDefinition = None
    for field in ("DamageEvents", "TrackedActiveSkills"):
        if getattr(definition, field):
            setattr(definition, field, [])
    for old in legacy:
        if old is not None and old.SkillEffectDefinitions:
            old.SkillEffectDefinitions = []
            _signatures.clear()
    for stat, row, label in zip(stats, desired, ("Movement Speed per Stack", "Damage per Stack")):
        for field, value in dict(Attribute=row.AttributeToModify, Description=label + ": $NUMBER$",
                bDisplayAsPercentage=True, bDisplayAsInverse=False, bDontDisplayPlusSign=False,
                bUseCustomNumberPlacement=True).items():
            if getattr(stat, field) != value:
                setattr(stat, field, value)
    if list(definition.SkillEffectPresentations) != stats:
        definition.SkillEffectPresentations = stats
    definition.SkillDescription = (
        "Moving builds [skill]Movement Speed[-skill] stacks; standing still builds [skill]Damage[-skill] stacks. "
        "Gain a stack every 0.5 seconds, up to 5 of each. Changing state removes one previous-state stack "
        "immediately; remaining previous-state stacks decay every 0.5 seconds as the new stacks build.")
    # These are private static definitions, never cached player/enemy actors.
    for field in WATER_DAMAGE_FIELDS:
        attribute = _precision_object("AttributeDefinition", definition, "ZR_Water_" + field, damage)
        resolver = _precision_object("ObjectPropertyAttributeValueResolver", attribute, "Value", damage.ValueResolverChain[0])
        resolver.PropertyName, resolver.CachedProperty = field, None
        attribute.ValueResolverChain = [resolver]
        _water_damage_attributes[field] = attribute
        for depth in range(8):
            key = (depth, field)
            if key not in _water_damage_pool:
                modifier = _precision_object("AttributeModifier", attribute, f"ZR_WaterDamage_{depth}")
                modifier.Type = unrealsdk.find_enum("EModifierType").MT_PostAdd
                _water_damage_pool[key] = modifier
    _water_movement_definition = helper
    _configure_water_hud(definition, legacy)
    _water_configured = True
    if "Be Like Water configured" not in _reported:
        _reported.add("Be Like Water configured")
        unrealsdk.logging.info("[Zer0Rebalance] Be Like Water configured: independent movement/damage stacks and HUD counters")
    return changed


def _counted_hud_feedback(definition: Any, name: str, label: str, icon: Any, limit: int) -> Any:
    feedback = _precision_object("SkillDefinition", definition, name, definition)
    for field, value in dict(SkillName=label, SkillIcon=icon, bSubjectToGradeRules=False,
            MaxGrade=limit, InitialDuration=0.,
            DurationType=unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite,
            TrackedSkillType=unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered,
            BehaviorProviderDefinition=None, TrackedActiveSkill=None, EffectSourceInstanceDataName="").items():
        setattr(feedback, field, value)
    for field in ("SkillEffectDefinitions", "SkillEffectPresentations", "SkillConstraints", "DamageEvents",
                  "KillEvents", "EventResponses", "CustomEvents", "TrackedActiveSkills"):
        setattr(feedback, field, [])
    count = _precision_object("AttributeDefinition", feedback, "StackCount")
    context = _precision_object("SkillAttributeContextResolver", count, "SkillContext")
    resolver = _precision_object("ObjectPropertyAttributeValueResolver", count, "GradeValue")
    context.AssociatedSkill, resolver.PropertyName = feedback, "Grade"
    count.bIsSimpleAttribute = True
    count.AttributeDataType = unrealsdk.find_enum("EAttributeDataType").ADT_Int
    count.ContextResolverChain, count.ValueResolverChain = [context], [resolver]
    feedback.CustomStackCount = count
    return feedback


def _configure_water_hud(definition: Any, legacy: list[Any]) -> None:
    global _water_hud_definitions
    feedbacks = []
    for name, label, icon in (("ZR_MovementHUD", "Be Like Water: Movement", definition.SkillIcon),
                              ("ZR_DamageHUD", "Be Like Water: Damage", getattr(legacy[0], "SkillIcon", definition.SkillIcon))):
        feedbacks.append(_counted_hud_feedback(definition, name, label, icon, WATER_STACK_LIMIT))
    _water_hud_definitions = tuple(feedbacks)


def _water_hud_slot(controller: Any, manager: Any, movie: Any, feedback: Any) -> int | None:
    occupied: set[int] = set()
    visited: set[int] = set()
    def reserve(definition: Any) -> None:
        if definition is None or definition == feedback:
            return
        address = int(definition._get_address())
        if address in visited:
            return
        if len(visited) >= 512:
            raise RuntimeError("Be Like Water HUD tracked-skill graph exceeded its limit")
        visited.add(address)
        if int(definition.TrackedSkillType) in (2, 3, 5, 6):
            occupied.add(int(definition.TrackedSkillHUDSlot))
            mapped = int(movie.GetRemappedSlot(definition))
            if mapped >= 0:
                occupied.add(mapped)
        reserve(definition.TrackedActiveSkill)
        for child in definition.TrackedActiveSkills:
            reserve(child)
    for entry in movie.AvailableTrackedSkills:
        reserve(entry.SkillDef)
        if (entry.SkillDef is not None and entry.SkillDef != feedback
                and int(entry.SkillDef.TrackedSkillType) in (2, 3, 5, 6) and int(entry.RemappedSlot) >= 0):
            occupied.add(int(entry.RemappedSlot))
    tree = controller.PlayerSkillTree
    if tree is not None:
        for skill in tree.Skills:
            if int(skill.Grade) > 0:
                reserve(skill.Definition)
    for skill in manager.ActiveSkills:
        reserve(skill.Definition)
    active = manager.IsSkillActive(controller, feedback)
    mapped = int(movie.GetRemappedSlot(feedback))
    for slot, entry in enumerate(movie.CachedTSkillIcon_TrigResp):
        if entry.Icon is not None and not (active and slot == mapped and entry.Icon == feedback.SkillIcon):
            occupied.add(slot)
    capacity = min(11, len(movie.CachedTSkillIcon_TrigResp))
    preferred = int(feedback.TrackedSkillHUDSlot)
    return preferred if 0 <= preferred < capacity and preferred not in occupied else next(
        (slot for slot in range(capacity) if slot not in occupied), None)


def _sync_water_hud(controller: Any, *, clear: bool = False) -> bool:
    """Visual-only counters; return after every callback that can invalidate native snapshots."""
    global _water_hud_counts, _water_hud_next_check
    if not _water_hud_definitions or controller is None or _owner is None:
        return False
    if int(controller._get_address()) != _owner[0]:
        return False
    state = _water_state
    desired = ((state["move"], state["amp"]) if state is not None and not clear else (0, 0))
    clock = time.monotonic()
    if desired == _water_hud_counts and clock < _water_hud_next_check:
        return False
    _water_hud_counts, _water_hud_next_check = desired, clock + 1.
    try:
        world, pawn = controller.WorldInfo, controller.Pawn
        if (controller.bDeleteMe or world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe
                or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != _owner):
            return False
        manager = controller.GetSkillManager()
        if manager is None or getattr(manager, "bUpdatingSkills", False):
            _water_hud_counts = None
            return False
        for index, (feedback, count) in enumerate(zip(_water_hud_definitions, desired)):
            if count <= 0 and index not in _water_hud_visible:
                continue
            active = manager.IsSkillActive(controller, feedback)
            movie = controller.GetHUDMovie()
            def hide() -> bool:
                _water_hud_visible.discard(index)
                _water_hud_counts_reset()
                player = WeakPointer(controller)
                expected = _owner
                manager.DeactivateSkill(controller, feedback)
                live = player()
                if live is not None and not live.bDeleteMe and live.WorldInfo is not None and not live.WorldInfo.bDeleteMe:
                    current_pawn = live.Pawn
                    if (_owner == expected and current_pawn is not None and not current_pawn.bDeleteMe
                            and (int(live._get_address()), int(live.WorldInfo._get_address()), int(current_pawn._get_address())) == expected
                            and not live.WorldInfo.Pauser and not live.IsPauseMenuOpen()):
                        current_movie = live.GetHUDMovie()
                        if current_movie is not None:
                            current_movie.UpdateSkillIcons()
                return True
            if count <= 0:
                if active:
                    return hide()
                _water_hud_visible.discard(index)
                continue
            if controller.IsPauseMenuOpen() or movie is None:
                continue
            if active:
                for skill in manager.ActiveSkills:
                    if skill.Definition == feedback and skill.SkillInstigator == controller and int(skill.Grade) != count:
                        _water_hud_counts_reset()
                        skill.UpdateGrade(count)
                        return True
            slot = _water_hud_slot(controller, manager, movie, feedback)
            if slot is None:
                if active:
                    return hide()
                continue  # A full HUD must never remove gameplay bonuses.
            if active and (int(feedback.TrackedSkillHUDSlot) != slot or int(movie.GetRemappedSlot(feedback)) != slot):
                return hide()
            if int(feedback.TrackedSkillHUDSlot) != slot:
                feedback.TrackedSkillHUDSlot = slot
            if not any(entry.SkillDef == feedback for entry in movie.AvailableTrackedSkills):
                _water_hud_counts_reset()
                movie.AddTrackedSkill(feedback)
                return True
            if int(movie.GetRemappedSlot(feedback)) != slot:
                entries = [copy.copy(entry) for entry in movie.AvailableTrackedSkills]
                for entry in entries:
                    if entry.SkillDef == feedback:
                        entry.RemappedSlot = slot
                movie.AvailableTrackedSkills = entries
            if int(movie.NumPurchasedTrigRespSlots) < slot + 1:
                movie.NumPurchasedTrigRespSlots = slot + 1
            if not active:
                _water_hud_counts_reset()
                if manager.ActivateSkill(controller, feedback, None, count) is not False:
                    _water_hud_visible.add(index)
                else:
                    _water_hud_counts, _water_hud_next_check = desired, clock + 1.
                return True
            _water_hud_visible.add(index)
            if movie.CachedTSkillIcon_TrigResp[slot].Icon != feedback.SkillIcon:
                _water_hud_counts_reset()
                movie.UpdateSkillIcons()
                return True
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _water_hud_counts, _water_hud_next_check = desired, clock + 1.
        _report("Could not display Be Like Water counters", exc)
    return False


def _water_hud_counts_reset() -> None:
    global _water_hud_counts, _water_hud_next_check
    _water_hud_counts, _water_hud_next_check = None, 0.


def _sync_one_hud(controller: Any, *, clear: bool = False) -> bool:
    """Visual-only counters; return after every callback that can invalidate native snapshots."""
    global _one_hud_counts, _one_hud_next_check
    if not _one_hud_definitions or controller is None or _owner is None:
        return False
    if int(controller._get_address()) != _owner[0]:
        return False
    state = _one_state
    desired = ((min(10, max(0, int(state["stacks"]))),) if state is not None and _one_context is not None and not clear else (0,))
    clock = time.monotonic()
    if desired == _one_hud_counts and clock < _one_hud_next_check:
        return False
    _one_hud_counts, _one_hud_next_check = desired, clock + 1.
    try:
        world, pawn = controller.WorldInfo, controller.Pawn
        if (controller.bDeleteMe or world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe
                or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != _owner):
            return False
        if pawn.IsInjuredDead():
            desired = (0,)
        manager = controller.GetSkillManager()
        if manager is None or getattr(manager, "bUpdatingSkills", False):
            _one_hud_counts = None
            return False
        for index, (feedback, count) in enumerate(zip(_one_hud_definitions, desired)):
            if count <= 0 and index not in _one_hud_visible:
                continue
            active = manager.IsSkillActive(controller, feedback)
            movie = controller.GetHUDMovie()
            def hide() -> bool:
                _one_hud_visible.discard(index)
                _one_hud_counts_reset()
                player = WeakPointer(controller)
                expected = _owner
                manager.DeactivateSkill(controller, feedback)
                live = player()
                if live is not None and not live.bDeleteMe and live.WorldInfo is not None and not live.WorldInfo.bDeleteMe:
                    current_pawn = live.Pawn
                    if (_owner == expected and current_pawn is not None and not current_pawn.bDeleteMe
                            and (int(live._get_address()), int(live.WorldInfo._get_address()), int(current_pawn._get_address())) == expected
                            and not live.WorldInfo.Pauser and not live.IsPauseMenuOpen()):
                        current_movie = live.GetHUDMovie()
                        if current_movie is not None:
                            current_movie.UpdateSkillIcons()
                return True
            if count <= 0:
                if active:
                    return hide()
                _one_hud_visible.discard(index)
                continue
            if controller.IsPauseMenuOpen() or movie is None:
                continue
            if active:
                for skill in manager.ActiveSkills:
                    if skill.Definition == feedback and skill.SkillInstigator == controller and int(skill.Grade) != count:
                        _one_hud_counts_reset()
                        skill.UpdateGrade(count)
                        return True
            slot = _water_hud_slot(controller, manager, movie, feedback)
            if slot is None:
                if active:
                    return hide()
                continue  # A full HUD must never remove gameplay bonuses.
            if active and (int(feedback.TrackedSkillHUDSlot) != slot or int(movie.GetRemappedSlot(feedback)) != slot):
                return hide()
            if int(feedback.TrackedSkillHUDSlot) != slot:
                feedback.TrackedSkillHUDSlot = slot
            if not any(entry.SkillDef == feedback for entry in movie.AvailableTrackedSkills):
                _one_hud_counts_reset()
                movie.AddTrackedSkill(feedback)
                return True
            if int(movie.GetRemappedSlot(feedback)) != slot:
                entries = [copy.copy(entry) for entry in movie.AvailableTrackedSkills]
                for entry in entries:
                    if entry.SkillDef == feedback:
                        entry.RemappedSlot = slot
                movie.AvailableTrackedSkills = entries
            if int(movie.NumPurchasedTrigRespSlots) < slot + 1:
                movie.NumPurchasedTrigRespSlots = slot + 1
            if not active:
                _one_hud_counts_reset()
                if manager.ActivateSkill(controller, feedback, None, count) is not False:
                    _one_hud_visible.add(index)
                else:
                    _one_hud_counts, _one_hud_next_check = desired, clock + 1.
                return True
            _one_hud_visible.add(index)
            if movie.CachedTSkillIcon_TrigResp[slot].Icon != feedback.SkillIcon:
                _one_hud_counts_reset()
                movie.UpdateSkillIcons()
                return True
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _one_hud_counts, _one_hud_next_check = desired, clock + 1.
        _report("Could not display At One with the Gun counter", exc)
    return False


def _one_hud_counts_reset() -> None:
    global _one_hud_counts, _one_hud_next_check
    _one_hud_counts, _one_hud_next_check = None, 0.


def _water_player(controller: Any) -> tuple[Any, Any, float] | None:
    cached = _water_context
    if cached is None or controller is None or _owner != cached[:3]:
        return None
    if (int(controller._get_address()) != cached[0] or controller.bDeleteMe
            or _path(controller.PlayerClass) != ZER0_CLASS
            or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
        return None
    world, pawn = controller.WorldInfo, controller.Pawn
    if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
            or pawn.Controller != controller
            or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != cached[:3]):
        return None
    now = float(world.TimeSeconds)
    if not math.isfinite(now) or not 0. <= now - cached[4] <= 1.5:
        return None
    return world, pawn, now


def _apply_water_movement(controller: Any, grade: int) -> bool:
    """Write only on a changed stack/rank; return after any native skill callback."""
    global _water_applied_grade, _water_mutating, _water_needs_sync, _next_check, _water_next_check
    if grade == _water_applied_grade or _water_mutating:
        return False
    helper = _water_movement_definition
    manager = controller.GetSkillManager()
    if helper is None or manager is None or getattr(manager, "bUpdatingSkills", False):
        return False
    live = _water_movement_ref() if _water_movement_ref is not None else None
    _water_applied_grade, _water_mutating = grade, True
    _water_needs_sync, _next_check = True, 0.
    try:
        if grade <= 0:
            manager.DeactivateSkill(controller, helper)
        elif live is not None:
            live.UpdateGrade(grade)
        elif manager.ActivateSkill(controller, helper, None, grade) is False:
            _water_applied_grade = -1
            _water_next_check = time.monotonic() + WATER_STACK_INTERVAL
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _water_applied_grade = -1
        _water_next_check = time.monotonic() + WATER_STACK_INTERVAL
        _report("Could not apply Be Like Water movement", exc)
    finally:
        _water_mutating = False
    return True


def _tick_be_like_water(controller: Any) -> bool:
    global _water_state, _water_next_check
    cached = _water_context
    if cached is None:
        return _sync_water_hud(controller, clear=True) if _water_hud_visible else False
    if cached is None or _water_mutating or _water_needs_sync or controller is None or int(controller._get_address()) != cached[0]:
        return False
    clock = time.monotonic()
    if clock < _water_next_check:
        return False
    _water_next_check = clock + .05
    try:
        valid = _water_player(controller)
        if valid is None:
            return False
        _, pawn, now = valid
        main = _water_main_ref() if _water_main_ref is not None else None
        rank = int(main.Grade) if main is not None else 0
        if (main is None or rank <= 0 or pawn.IsInjuredDead() or main.SkillInstigator != controller
                or main.SkillState != unrealsdk.find_enum("ESkillState").SKILL_Active):
            _water_state = None
            if _apply_water_movement(controller, 0):
                return True
            return _sync_water_hud(controller, clear=True)
        speed = float(pawn.CurrentPawnSpeed)
        if not math.isfinite(speed):
            return False
        moving = speed > 1.
        if _water_state is None or _water_state["identity"] != cached[:3]:
            _water_state = dict(identity=cached[:3], moving=moving, move=0, amp=0, next_at=now + WATER_STACK_INTERVAL)
        state = _water_state
        if state["moving"] != moving:
            previous = "move" if state["moving"] else "amp"
            state[previous] = max(0, state[previous] - 1)
            state["moving"], state["next_at"] = moving, now + WATER_STACK_INTERVAL
        elif now + 1.e-6 >= state["next_at"]:
            steps = max(1, int((now + 1.e-6 - state["next_at"]) / WATER_STACK_INTERVAL) + 1)
            active, fading = ("move", "amp") if moving else ("amp", "move")
            state[active] = min(WATER_STACK_LIMIT, state[active] + steps)
            state[fading] = max(0, state[fading] - steps)
            state["next_at"] += steps * WATER_STACK_INTERVAL
        if _apply_water_movement(controller, state["move"] * rank):
            return True
        return _sync_water_hud(controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not update Be Like Water", exc)
    return False


def _remove_shot_amp(frame: dict[str, Any]) -> None:
    modifier_ref, frame["modifier"] = frame["modifier"], None
    if modifier_ref is None:
        return
    try:
        weapon, modifier = frame["weapon"](), modifier_ref()
        if (weapon is not None and modifier is not None and not weapon.bDeleteMe
                and weapon.WorldInfo is not None and not weapon.WorldInfo.bDeleteMe):
            weapon.RemoveModifier(modifier, "InstantHitDamage", False)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not remove temporary shot Amp", exc)


def _set_water_damage(frame: dict[str, Any], enabled: bool) -> None:
    """Scale the recipient's current source coefficient, preserving other mods and immunities."""
    frame["added"] = False
    errors = []
    for field, attribute, modifier in frame["rows"]:
        try:
            recipient, world = frame["recipient"](), frame["world"]()
            if (recipient is None or recipient.bDeleteMe or world is None or world.bDeleteMe
                    or recipient.WorldInfo != world):
                return
            stack = field + "ModifierStack"
            present = modifier in getattr(recipient, stack)
            if enabled and not present:
                before = float(getattr(recipient, field))
                if not math.isfinite(before) or before <= 0.:
                    continue
                if attribute.ResolveContext(recipient) != recipient:
                    raise RuntimeError("Be Like Water damage context mismatch")
                modifier.Value = before * frame["bonus"]
                frame["added"] = True  # Cleanup is owed even if the native call raises after adding.
                accepted = attribute.AddAttributeModifier(recipient, modifier, False)
                if (not accepted or modifier not in getattr(recipient, stack)
                        or not math.isclose(float(getattr(recipient, field)), before * (1. + frame["bonus"]), rel_tol=1.e-5)):
                    raise RuntimeError("Be Like Water damage multiplier was not accepted")
            elif not enabled and present:
                attribute.RemoveAttributeModifier(recipient, modifier, False)
                if modifier in getattr(recipient, stack):
                    raise RuntimeError("Be Like Water damage cleanup failed")
            elif enabled:
                frame["added"] = True
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            errors.append(str(exc))
    if errors:
        frame["added"] = True
        raise RuntimeError("; ".join(errors))


def _water_damage_rows(depth: int, source: Any) -> tuple[tuple[str, Any, Any], ...]:
    name = str(source.Name) if source is not None else ""
    fields = _water_source_cache.get(name)
    if fields is None:
        field = WATER_SOURCE_FIELDS.get(name)
        if field is None and source is not None:
            for index, base in enumerate(source._superfields()):
                if index >= 16:
                    break
                field = WATER_SOURCE_FIELDS.get(str(base.Name))
                if field is not None:
                    break
        fields = (field,) if field is not None else WATER_DAMAGE_FIELDS
        if len(_water_source_cache) >= 64:
            _water_source_cache.clear()
        _water_source_cache[name] = fields
    rows = []
    for field in fields:
        attribute = _water_damage_attributes[field]
        key = (depth, field)
        modifier = _water_damage_pool.get(key)
        if modifier is None:
            raise RuntimeError("Be Like Water damage pool is unavailable")
        rows.append((field, attribute, modifier))
    return tuple(rows)


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.PRE)
def begin_water_damage(_pipeline: Any, args: Any, _ret: Any, _func: Any) -> None:
    _water_damage_frames.append(None)
    state = _water_state
    if (state is None or state["amp"] <= 0) and not any(
            item is not None and item["added"] for item in _water_damage_frames[:-1]):
        return
    frame: dict[str, Any] | None = None
    try:
        target = args.InDamagedActor
        if target is None or target.bDeleteMe:
            return
        recipient, world = getattr(target, "Controller", None), target.WorldInfo
        if recipient is None or recipient.bDeleteMe or world is None or world.bDeleteMe:
            return
        address = int(recipient._get_address())
        parent = next((item for item in reversed(_water_damage_frames[:-1])
                       if item is not None and item["added"] and item["address"] == address), None)
        frame = dict(recipient=WeakPointer(recipient), world=WeakPointer(world), address=address,
                     parent=parent, rows=(), added=False, bonus=0., identity=_owner)
        _water_damage_frames[-1] = frame
        if parent is not None:
            _set_water_damage(parent, False)  # Nested foreign hits must not inherit this player's multiplier.
        if len(_water_damage_frames) > 8 or state is None or state["amp"] <= 0:
            return
        controller = args.InDamageInstigator
        valid = _water_player(controller)
        if valid is None:
            return
        own_world, pawn, _ = valid
        main = _water_main_ref() if _water_main_ref is not None else None
        incoming = float(args.IncomingDamage)
        if (world != own_world or world.Pauser or target == pawn or pawn.IsInjuredDead()
                or not math.isfinite(incoming) or incoming <= 0. or not hasattr(target, "GetOpinion")
                or _water_enemy_opinion is None or int(target.GetOpinion(pawn)) != _water_enemy_opinion
                or main is None or main.SkillInstigator != controller
                or int(main.Grade) <= 0 or main.SkillState != unrealsdk.find_enum("ESkillState").SKILL_Active
                or state["identity"] != _owner):
            return
        frame["bonus"] = WATER_BONUS_PER_RANK * int(main.Grade) * min(WATER_STACK_LIMIT, state["amp"])
        frame["rows"] = _water_damage_rows(len(_water_damage_frames) - 1, args.InDamageSource)
        _set_water_damage(frame, True)
    except (AttributeError, TypeError, ValueError, RuntimeError, KeyError) as exc:
        if frame is not None:
            try:
                _set_water_damage(frame, False)
            except (AttributeError, TypeError, ValueError, RuntimeError) as cleanup_error:
                _report("Could not clean failed Be Like Water damage", cleanup_error)
        _report("Could not apply Be Like Water generic damage", exc)


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.POST_UNCONDITIONAL)
def finish_water_damage(_pipeline: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if not _water_damage_frames:
        return
    frame = _water_damage_frames.pop()
    if frame is None:
        return
    try:
        _set_water_damage(frame, False)
        parent = frame["parent"]
        if parent is not None and parent["identity"] == _owner and _water_context is not None:
            _set_water_damage(parent, True)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not finish Be Like Water generic damage", exc)


def _cleanup_water_damage() -> None:
    for frame in reversed(tuple(_water_damage_frames)):
        if frame is not None:
            frame["parent"] = None
            try:
                _set_water_damage(frame, False)
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _report("Could not clean Be Like Water damage on travel/disable", exc)


def _cleanup_water(controller: Any) -> None:
    global _water_state
    _water_state = None
    _cleanup_water_damage()
    try:
        # Cleanup must also work in pause menus or after a stale gameplay cache.
        if controller is None or controller.bDeleteMe or _owner is None:
            return
        world = controller.WorldInfo
        if (world is None or world.bDeleteMe
                or (int(controller._get_address()), int(world._get_address())) != _owner[:2]):
            return
        player = WeakPointer(controller)
        _apply_water_movement(controller, 0)
        for _ in range(2):
            live = player()
            if live is None or not _sync_water_hud(live, clear=True):
                break
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not clean up Be Like Water", exc)


def _property_attribute(outer: Any, name: str, context_kind: str, property_name: str) -> Any:
    """Private resolver for a verified native property, independent of optional D_Attributes exports."""
    attribute = _precision_object("AttributeDefinition", outer, name)
    context = _precision_object(context_kind, attribute, "Context")
    resolver = _precision_object("ObjectPropertyAttributeValueResolver", attribute, "Value")
    attribute.bIsSimpleAttribute = False
    attribute.AttributeDataType = unrealsdk.find_enum("EAttributeDataType").ADT_Float
    resolver.PropertyName, resolver.CachedProperty = property_name, None
    attribute.ContextResolverChain, attribute.ValueResolverChain = [context], [resolver]
    return attribute


def _precision_object(kind: str, outer: Any, name: str, template: Any = None) -> Any:
    path = _path(outer)
    if path is None:
        raise ValueError("Precision asset owner is unavailable")
    path += ("." if ":" in path else ":") + name
    result = _find(kind, path)
    if result is None:
        result = unrealsdk.construct_object(kind, outer, name, template_obj=template, flags=int(ObjectFlags.KEEP_ALIVE))
    if result is None:
        raise ValueError("Could not construct Precision asset: " + path)
    return result


def _precision_graph(provider: Any, helper: Any) -> Any:
    """Native bullet event -> clear old pulse -> actual crit bool -> reflection pulse."""
    reset = _precision_object("Behavior_DeactivateSkill", provider, "Reset")
    compare = _precision_object("Behavior_CompareBool", provider, "Critical")
    arm = _precision_object("Behavior_ActivateSkill", provider, "Reflect")
    stop = _precision_object("Behavior_DeactivateSkill", provider, "Stop")
    reset.SkillToDeactivate = stop.SkillToDeactivate = helper
    arm.SkillToActivate, arm.bNoSkillStacking = helper, True
    existing = list(provider.BehaviorSequences)
    if len(existing) == 1 and [row.Behavior for row in existing[0].BehaviorData2] == [reset, compare, arm, stop]:
        return arm
    make = unrealsdk.make_struct
    sub = lambda start, count: make("SubarrayData", ArrayIndexAndLength=(start << 16) | count)
    var_types = unrealsdk.find_enum("EBehaviorVariableType")
    link_types = unrealsdk.find_enum("EBehaviorVariableLinkType")
    links = []
    specifications = (("Context", link_types.BVARLINK_Context, 0, 0),
        ("BoolValue", link_types.BVARLINK_Input, 0, 1), ("Context", link_types.BVARLINK_Context, 0, 0),
        ("Context", link_types.BVARLINK_Context, 0, 0), ("SkillInstigator", link_types.BVARLINK_Output, 0, 0),
        ("bWasCrit", link_types.BVARLINK_Output, 2, 1), ("SkillInstigator", link_types.BVARLINK_Output, 0, 0),
        ("SkillInstigator", link_types.BVARLINK_Output, 0, 0))
    for index, (name, kind, connection, _) in enumerate(specifications):
        links.append(make("BehaviorVariableLinkData2", PropertyName=name, VariableLinkType=kind,
            ConnectionIndex=connection, LinkedVariables=sub(index, 1), CachedProperty=None))
    nodes = [make("BehaviorSequenceActionData2", Behavior=behavior, LinkedVariables=sub(index, 1),
        OutputLinks=sub(index, 1) if index < 2 else sub(0, 0))
        for index, behavior in enumerate((reset, compare, arm, stop))]
    events = []
    for name, variables, output in (("ZR_PrecisionHit", sub(4, 2), 2),
            ("OnPaused", sub(6, 1), 3), ("OnDeactivated", sub(7, 1), 4)):
        events.append(make("BehaviorEventData2", UserData=make("BehaviorEventUserData",
            EventName=name, bEnabled=True), OutputVariables=variables, OutputLinks=sub(output, 1)))
    # CompareBool output 0 is true, as used by native Critical Ascension.
    outputs = [make("BehaviorOutputLinkData2", LinkIdAndLinkedBehavior=target, ActivateDelay=0.)
               for target in (-16777215, 2, 0, 3, 3)]
    sequence = make("BehaviorSequenceData", BehaviorSequenceName="Default", bEnabledOnSpawn=True,
        EventData2=events, BehaviorData2=nodes,
        VariableData=[make("BehaviorVariableData", Type=var_types.BVAR_Object),
                      make("BehaviorVariableData", Type=var_types.BVAR_Bool)],
        ConsolidatedOutputLinkData=outputs, ConsolidatedVariableLinkData=links,
        ConsolidatedLinkedVariables=[item[3] for item in specifications])
    provider.CurrentVersion, provider.BehaviorSequences = 10, [sequence]
    return arm


def _configure_precision() -> bool:
    global _precision_reflection_types
    global _precision_configured, _precision_arm_address, _precision_enemy_opinion, _precision_helper_definition, _precision_pulse_modifiers
    definition = _find("SkillDefinition", PRECISION)
    chance = _find("AttributeDefinition", PRECISION_CHANCE)
    grade = _find("InventoryAttributeDefinition", "GD_Assassin_Skills.SkillGradeModifiers.Precision")
    bullet = _find("Class", "WillowGame.WillowDmgSource_Bullet")
    stat = _find("AttributePresentationDefinition", PRECISION + ":AttributePresentationDefinition_2")
    if definition is None or grade is None or bullet is None or stat is None:
        return False
    _precision_enemy_opinion = int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)
    reflection_types = unrealsdk.find_enum("EReflectionType")
    _precision_reflection_types = (int(reflection_types.REFLT_None), int(reflection_types.REFLT_Instigator))
    if chance is None:
        chance = _property_attribute(definition, "ZR_ReflectionChance", "PawnAttributeContextResolver", "BulletReflectionOffEnemyChance")
    effects = list(definition.SkillEffectDefinitions)
    paths = [_path(row.AttributeToModify) for row in effects]
    native = ["D_Attributes.AccuracyResourcePool.AccuracyMinValue", OPTICS_ACCURACY_ATTRIBUTE,
              "D_Attributes.AccuracyResourcePool.AccuracyMaxValue", "D_Attributes.AccuracyResourcePool.AccuracyOnIdleRegenerationRate"]
    if paths not in (native, [PRECISION_DAMAGE_ATTRIBUTE]):
        raise ValueError(f"Unexpected Precision effects: {paths}")
    damage = _precision_object("AttributeDefinition", definition, "ZR_ReflectedDamage", chance)
    resolver = _precision_object("ObjectPropertyAttributeValueResolver", damage, "Value")
    resolver.PropertyName = "BulletReflectedOffEnemyDamageScale"
    damage.ContextResolverChain, damage.ValueResolverChain = list(chance.ContextResolverChain), [resolver]
    initializer = _precision_object("AttributeInitializationDefinition", definition, "ZR_ReflectionDelta")
    aid = lambda constant, attribute=None: unrealsdk.make_struct("AttributeInitializationData",
        BaseValueConstant=constant, BaseValueAttribute=attribute, BaseValueScaleConstant=1.)
    initializer.BaseValueMode = unrealsdk.find_enum("EBaseValueMode").BASEVALUE_InitializationDefSetsBaseValue
    initializer.RoundingMode = unrealsdk.find_enum("EAttributeInitializationRounding").ATTRROUNDING_Float
    initializer.ValueFormula = unrealsdk.make_struct("BalanceFormula", bEnabled=True,
        Multiplier=aid(.1), Level=aid(0., grade), Power=aid(1.), Offset=aid(-.5))
    helper = _precision_object("SkillDefinition", definition, "ZR_Ricochet", definition)
    for field, value in dict(SkillName="Precision ricochet pulse", bSubjectToGradeRules=False, MaxGrade=1,
            DefaultStartingGrade=1, TrackedSkillType=unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked,
            BehaviorProviderDefinition=None, TrackedActiveSkill=None).items():
        if getattr(helper, field) != value:
            setattr(helper, field, value)
    for field in ("DamageEvents", "KillEvents", "SkillEffectPresentations", "TrackedActiveSkills"):
        if getattr(helper, field):
            setattr(helper, field, [])
    rows = []
    for attribute, amount, init in ((chance, 1., None), (damage, 0., initializer)):
        row = copy.copy(effects[0])
        row.AttributeToModify, row.EffectTarget = attribute, unrealsdk.find_enum("EEffectTarget").TARGET_Self
        row.ModifierType = unrealsdk.find_enum("EModifierType").MT_PostAdd
        row.BaseModifierValue = aid(amount)
        row.BaseModifierValue.InitializationDefinition = init
        row.PerGradeUpgrade = aid(0.)
        row.GradeToStartApplyingEffect, row.PerGradeUpgradeInterval, row.BonusUpgradeList = 1, 1, []
        rows.append(row)
    helper.SkillEffectDefinitions = rows
    pulse_modifiers = tuple(_precision_object("AttributeModifier", definition, name)
        for name in ("ZR_ChancePulseModifier", "ZR_DamagePulseModifier"))
    for modifier in pulse_modifiers:
        modifier.Type = unrealsdk.find_enum("EModifierType").MT_PostAdd
    _precision_pulse_modifiers = (pulse_modifiers[0], pulse_modifiers[1])
    provider = _precision_object("BehaviorProviderDefinition", definition, "ZR_RicochetGraph")
    arm = _precision_graph(provider, helper)
    event = unrealsdk.make_struct("SkillDamageEventData", EventType=unrealsdk.find_enum("ESkillDamageEvents").SDE_DamagedEnemy,
        EventConstraints=[unrealsdk.make_struct("SkillDamagedEventConstraintData", DamageSourceConstraint=bullet)],
        EventName="ZR_PrecisionHit")
    display = copy.copy(effects[0])
    display.AttributeToModify, display.EffectTarget = damage, unrealsdk.find_enum("EEffectTarget").TARGET_None
    display.BaseModifierValue, display.PerGradeUpgrade = aid(-.4), aid(.1)
    display.GradeToStartApplyingEffect, display.PerGradeUpgradeInterval, display.BonusUpgradeList = 1, 1, []
    changed = len(effects) != 1 or not _same_effect(effects[0], display)
    if changed:
        definition.SkillEffectDefinitions = [display]
        _signatures.clear()
    stat.Attribute, stat.Description = damage, "Ricochet Damage: $NUMBER$"
    stat.bDisplayAsPercentage, stat.bDisplayAsInverse = True, False
    stat.SignStyle = unrealsdk.find_enum("EAttributeValueSignStyle").SIGNSTYLE_AsIs
    stat.bDontDisplayPlusSign = False
    definition.SkillEffectPresentations = [stat]
    definition.DamageEvents, definition.BehaviorProviderDefinition = [event], provider
    definition.SkillDescription = (
        "[skill]Critical Hits[-skill] with bullets can [skill]ricochet[-skill] toward another nearby enemy. "
        "Ricochet damage increases with skill rank.")
    _precision_arm_address = int(arm._get_address())
    _precision_helper_definition = helper  # Rooted definition only, never a live skill/actor.
    _precision_configured = True
    if "Precision configured" not in _reported:
        _reported.add("Precision configured")
        unrealsdk.logging.info(f"[Zer0Rebalance] Precision configured: native critical-bullet reflection graph; enemy_opinion={_precision_enemy_opinion}; scoped reflection guards")
    return changed


@hook("WillowGame.WillowAIPawn:TakeDamage", Type.PRE)
@hook("WillowGame.WillowPawn:TakeDamage", Type.PRE)
def begin_precision_damage(target: Any, args: Any, _ret: Any, _func: Any) -> None:
    if not _precision_frames:
        _flush_precision_pending()  # A new impact must not inherit the preceding critical's pulse.
    _precision_frames.append(None)
    cached = _precision_context
    if cached is None or len(_precision_frames) > 32:
        return
    try:
        instigator = args.InstigatedBy
        damage = float(args.Damage)
        if (instigator is None or int(instigator._get_address()) != cached[0]
                or not math.isfinite(damage) or damage <= 0.):
            return
        # Native bActorReflected/SetCanReflect policy excludes already-reflected impacts.
        if any(item is not None and item["armed"] for item in _precision_frames[:-1]):
            return  # Do not arm a second Precision pulse inside another reflection callback.
        if target is None or target.bDeleteMe:
            return
        parent = _precision_frames[-2] if len(_precision_frames) > 1 else None
        if (parent is not None and parent["target"]() == target
                and parent["controller"]() == instigator and parent["identity"] == cached[:3]):
            # AIPawn.TakeDamage may call its WillowPawn superclass. One native
            # impact owns one pulse, which stays alive until the outer call ends.
            _precision_frames[-1] = parent
        else:
            _precision_frames[-1] = dict(pipeline=None, controller=WeakPointer(instigator),
                target=WeakPointer(target), identity=cached[:3], hit=copy.copy(args.HitLocation), armed=False)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not scope Precision hit", exc)


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.PRE)
def begin_precision_hit(pipeline: Any, args: Any, _ret: Any, _func: Any) -> None:
    """Bind the pipeline; critical skill events arrive after AdjustDamage returns."""
    frame = _precision_frames[-1] if _precision_frames else None
    if frame is None or frame["armed"]:
        return
    try:
        if (args.InDamageInstigator == frame["controller"]()
                and args.InDamagedActor == frame["target"]()):
            frame["pipeline"] = WeakPointer(pipeline)
            frame["hit"] = copy.copy(args.InHitLocation)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not bind Precision damage pipeline", exc)


def _precision_has_target(world: Any, pawn: Any, hit_actor: Any, center: Any, radius: float, now: float) -> bool:
    """Only on a confirmed critical event; bounded, short negative/positive cache."""
    key, world_id = int(hit_actor._get_address()), int(world._get_address())
    xyz = tuple(float(getattr(center, axis)) for axis in ("X", "Y", "Z"))
    if not all(math.isfinite(value) for value in xyz) or not math.isfinite(radius) or radius <= 0.:
        return False
    def eligible(candidate: Any) -> bool:
        if (candidate is None or candidate == hit_actor or candidate == pawn or candidate.bDeleteMe
                or getattr(candidate, "bPendingDelete", False) or candidate.WorldInfo != world):
            return False
        point = candidate.Location
        distance = sum((float(getattr(point, axis)) - value) ** 2 for axis, value in zip(("X", "Y", "Z"), xyz))
        if not math.isfinite(distance) or distance <= 1. or distance > radius * radius:
            return False
        if (_precision_enemy_opinion is None or not hasattr(candidate, "GetOpinion")
                or int(candidate.GetOpinion(pawn)) != _precision_enemy_opinion
                or float(candidate.GetHealth()) <= 0. or candidate.IsInjuredDead()):
            return False
        # Native reflection chooses the actual destination. A separate FastTrace
        # here can reject every nearby pawn before native selection runs.
        return True
    cached = _precision_targets.get(key)
    if cached is not None and cached[0] == world_id and 0. <= now - cached[1] <= .1:
        if cached[2] is None:
            return False
        if eligible(cached[2]()):
            return True
    if len(_precision_targets) >= 64 and key not in _precision_targets:
        _precision_targets.clear()
    candidate, seen = world.PawnList, set()
    while candidate is not None and len(seen) < 256:
        address = int(candidate._get_address())
        if address in seen:
            break
        seen.add(address)
        following = candidate.NextPawn
        if eligible(candidate):
            _precision_targets[key] = (world_id, now, WeakPointer(candidate))
            return True
        candidate = following
    _precision_targets[key] = (world_id, now, None)
    return False


@hook("WillowGame.Behavior_ActivateSkill:ApplyBehaviorToContext", Type.PRE)
def guard_precision_reflection(behavior: Any, args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    if not _precision_arm_address or behavior is None or int(behavior._get_address()) != _precision_arm_address:
        return None
    cached = _precision_context
    frame = _precision_frames[-1] if _precision_frames else None
    if cached is None or frame is None or frame["armed"]:
        return Block
    try:
        controller = frame["controller"]()
        pipeline = frame["pipeline"]() if frame["pipeline"] is not None else None
        target = frame["target"]()
        # bCanReflect is false on ordinary critical sniper hits in live captures.
        # Leave native projectile reflection flags intact; do not use this transient
        # pipeline field as a precondition for supplying the critical-hit bonus.
        if controller is None or pipeline is None or target is None or controller.bDeleteMe:
            return Block
        context = args.ContextObject
        if context not in (controller, controller.Pawn):
            return Block
        world, pawn = controller.WorldInfo, controller.Pawn
        if (controller != get_pc(possibly_loading=True) or _owner != cached[:3] or frame["identity"] != cached[:3]
                or world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.Controller != controller or pawn.IsInjuredDead()
                or _path(controller.PlayerClass) != ZER0_CLASS
                or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
                or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != cached[:3]):
            return Block
        now = float(world.TimeSeconds)
        main = _precision_main_ref() if _precision_main_ref is not None else None
        if (not math.isfinite(now) or not 0. <= now - cached[4] <= 1.5 or main is None
                or main.SkillInstigator != controller or int(main.Grade) <= 0
                or main.SkillState != unrealsdk.find_enum("ESkillState").SKILL_Active
                or target.bDeleteMe or target.WorldInfo != world or target == pawn):
            return Block
        globals_def = pipeline.GlobalsDef
        if globals_def is None:
            return Block
        previous_radius = int(globals_def.BulletReflectionRadius)
        if not math.isfinite(previous_radius) or previous_radius <= 0.:
            return Block
        modifiers = _precision_pulse_modifiers
        if modifiers is None or _precision_reflection_types is None:
            return Block
        summary = copy.copy(pipeline.DamageSummary)
        reflection = copy.copy(summary.ReflectionData)
        if int(reflection.ReflectionType) != _precision_reflection_types[0]:
            return Block  # Preserve an existing native/external reflection decision.
        if not summary.bWasCrit:
            return Block
        if not _precision_has_target(world, pawn, target, frame["hit"], PRECISION_RICOCHET_RADIUS, now):
            return Block
        frame["armed"] = True
        frame["pulse_pawn"], frame["pulse_world"] = WeakPointer(pawn), WeakPointer(world)
        frame["pulse_rows"] = []
        frame["radius_scope"] = (WeakPointer(globals_def), previous_radius)
        if not math.isclose(previous_radius, PRECISION_RICOCHET_RADIUS, abs_tol=1e-6):
            globals_def.BulletReflectionRadius = PRECISION_RICOCHET_RADIUS
        for field, modifier, amount in (
                ("BulletReflectionOffEnemyChance", modifiers[0], 1.),
                ("BulletReflectedOffEnemyDamageScale", modifiers[1], .1 * int(main.Grade) - .5)):
            current = _precision_pulse_pawn(frame)
            if current is None:
                raise ValueError("Precision pulse owner changed during activation")
            modifier.Value = amount
            frame["pulse_rows"].append((modifier, field))  # Cleanup even if AddModifier partially applies then raises.
            if current.AddModifier(modifier, field, False) is False:
                raise RuntimeError("Precision temporary modifier was rejected")
        # AdjustDamage has already returned before this critical skill event.
        # Attribute changes alone cannot rebuild its ReflectionData. Publish the
        # verified native result consumed by the caller through the pipeline.
        if _owner != frame["identity"] or _precision_pulse_pawn(frame) is None or not frame["armed"]:
            raise ValueError("Precision impact invalidated before publishing reflection")
        reflection.ReflectionType = _precision_reflection_types[1]
        reflection.ReflectedDamageScale = .5 + .1 * int(main.Grade)
        reflection.ReflectedDamageToReflector = 1.
        reflection.bReflectTowardAttacker = False
        reflection.ReflectedInaccuracyModifier = 0.
        reflection.bReflectProjectiles = False
        summary.ReflectionData = reflection
        pipeline.DamageSummary = summary
        message = "Precision native reflection result published"
        if message not in _reported:
            _reported.add(message)
            unrealsdk.logging.info(f"[Zer0Rebalance] {message}: rank={int(main.Grade)}, type={int(reflection.ReflectionType)}, damage_scale={float(reflection.ReflectedDamageScale):g}, radius={PRECISION_RICOCHET_RADIUS}")
        # Native reflection uses these pawn attributes directly. Never invoke the
        # graph's skill activation: the live manager rejects it in this callback.
        return Block
    except (AttributeError, TypeError, ValueError, RuntimeError, OverflowError) as exc:
        if frame is not None and frame.get("armed"):
            _stop_precision_pulse(frame)
        _report("Could not validate Precision reflection", exc)
        return Block


def _precision_pulse_pawn(frame: dict[str, Any]) -> Any | None:
    pawn = frame["pulse_pawn"]()
    world = frame["pulse_world"]()
    if (pawn is None or pawn.bDeleteMe or world is None or world.bDeleteMe
            or pawn.WorldInfo != world or int(world._get_address()) != frame["identity"][1]):
        return None
    return pawn


def _stop_precision_pulse(frame: dict[str, Any]) -> None:
    if not frame["armed"]:
        return
    frame["armed"] = False
    for modifier, field in reversed(frame.pop("pulse_rows", [])):
        try:
            pawn = _precision_pulse_pawn(frame)
            if pawn is not None:
                pawn.RemoveModifier(modifier, field, False)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _report("Could not stop Precision reflection pulse", exc)
    radius_scope = frame.pop("radius_scope", None)
    if radius_scope is not None:
        try:
            definition, previous = radius_scope[0](), radius_scope[1]
            if (definition is not None and math.isclose(float(definition.BulletReflectionRadius),
                    PRECISION_RICOCHET_RADIUS, abs_tol=1e-6)
                    and not math.isclose(previous, PRECISION_RICOCHET_RADIUS, abs_tol=1e-6)):
                definition.BulletReflectionRadius = previous
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _report("Could not restore Precision reflection radius", exc)


@hook("WillowGame.WillowAIPawn:TakeDamage", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowPawn:TakeDamage", Type.POST_UNCONDITIONAL)
def finish_precision_hit(_pipeline: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _precision_pending
    if _precision_frames:
        frame = _precision_frames.pop()
        if frame is not None and not any(item is frame for item in _precision_frames):
            if frame["armed"]:
                # TakeDamage's caller has not returned yet. Keep the attributes
                # through that return, then remove before the next impact/tick.
                _precision_pending = frame


def _flush_precision_pending(controller: Any = None) -> None:
    global _precision_pending
    frame = _precision_pending
    if frame is None:
        return
    if controller is not None and int(controller._get_address()) != frame["identity"][0]:
        return
    _precision_pending = None  # Clear before native callbacks can reenter.
    _stop_precision_pulse(frame)


def _cleanup_precision(*, disabling: bool = False) -> None:
    _flush_precision_pending()
    for frame in tuple(_precision_frames):
        if frame is not None:
            _stop_precision_pulse(frame)
    if disabling:
        try:
            definition = _find("SkillDefinition", PRECISION)
            if definition is not None:
                definition.DamageEvents = []  # A native graph must not keep proccing after its guard hooks are disabled.
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _report("Could not disable Precision events", exc)


def _configure_one_with_gun() -> bool:
    global _one_configured, _one_enemy_opinion, _one_hud_definitions, _one_amp_modifiers
    definition = _find("SkillDefinition", ONE_WITH_GUN)
    legacy = _find("SkillDefinition", ONE_HIPFIRE)
    damage = _find("AttributeDefinition", VELOCITY_GUN_DAMAGE)
    stats = [_find("AttributePresentationDefinition", ONE_WITH_GUN + f":AttributePresentationDefinition_{i}")
             for i in (0, 1, 2)]
    if definition is None or damage is None or any(stat is None for stat in stats):
        return False
    _one_enemy_opinion = int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)
    effects = list(definition.SkillEffectDefinitions)
    hip = {"D_Attributes.AccuracyResourcePool.AccuracyMinValue",
           "D_Attributes.AccuracyResourcePool.AccuracyMaxValue", OPTICS_ACCURACY_ATTRIBUTE}
    retained = {"D_Attributes.Weapon.WeaponReloadSpeed", "D_Attributes.Weapon.WeaponClipSize"}
    paths = [_path(row.AttributeToModify) for row in effects]
    if len(paths) != len(set(paths)) or set(paths) not in (hip | retained, retained | {VELOCITY_GUN_DAMAGE}):
        raise ValueError(f"Unexpected At One with the Gun effects: {paths}")
    row = copy.copy(effects[0])
    row.AttributeToModify, row.EffectTarget = damage, unrealsdk.find_enum("EEffectTarget").TARGET_None
    row.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
    row.GradeToStartApplyingEffect, row.PerGradeUpgradeInterval, row.BonusUpgradeList = 1, 1, []
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(row, field))
        value.BaseValueConstant, value.BaseValueScaleConstant = ONE_AMP_PER_RANK, 1.
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(row, field, value)
    updated = [item for item in effects if _path(item.AttributeToModify) in retained] + [row]
    changed = len(effects) != len(updated) or any(not _same_effect(a, b) for a, b in zip(effects, updated))
    if changed:
        definition.SkillEffectDefinitions = updated
        _signatures.clear()
    # Keep the sniper-only parent constraint: its real passive bonuses must not affect other guns.
    # The shot mechanic reads its learned grade even when that parent is paused with a non-sniper.
    definition.BehaviorProviderDefinition = None
    if legacy is not None and legacy.SkillEffectDefinitions:
        legacy.SkillEffectDefinitions = []
        _signatures.clear()
    stat = stats[0]
    if stat is not None:
        stat.Attribute, stat.Description = damage, "Empowered Shot Amp Damage: $NUMBER$"
        stat.bDisplayAsPercentage, stat.bDisplayAsInverse = True, False
        stat.bDontDisplayPlusSign, stat.bUseCustomNumberPlacement = False, True
    definition.SkillEffectPresentations = [stats[1], stats[2], stat]
    definition.SkillDescription = (
        "Increases [skill]Reload Speed[-skill] and [skill]Magazine Size[-skill] with Sniper Rifles. "
        "Hitting enemies builds stacks that empower your [skill]next shot[-skill] at 10 stacks with "
        "[skill]Amp Damage[-skill], using any weapon. Each shot grants one stack, or two if any projectile critically hits. "
        "Stacks have no time limit and reset when traveling or returning to the main menu.")
    # Root only static helpers under the static skill; never keep a weapon/world alive via its Outer.
    _one_amp_modifiers = tuple(_precision_object("AttributeModifier", definition, f"ZR_OneShotAmp_{depth}")
                               for depth in range(8))
    _one_hud_definitions = (_counted_hud_feedback(definition, "ZR_ChargeHUD", "At One with the Gun", definition.SkillIcon, 10),)
    _one_configured = True
    return changed


def _one_player(controller: Any) -> tuple[Any, Any, int] | None:
    cached = _one_context
    if cached is None or controller is None or _owner != cached[:3] or controller.bDeleteMe:
        return None
    world, pawn = controller.WorldInfo, controller.Pawn
    if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
            or pawn.Controller != controller or _path(controller.PlayerClass) != ZER0_CLASS
            or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
            or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != cached[:3]
            or not 0. <= float(world.TimeSeconds) - cached[4] <= 1.5):
        return None
    main = _one_main_ref() if _one_main_ref is not None else None
    if main is None or main.SkillInstigator != controller or int(main.Grade) <= 0:
        return None
    return world, pawn, int(main.Grade)


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.PRE)
def begin_one_shot(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _one_state
    _one_frames.append(None)
    if _one_context is None:
        return
    frame: dict[str, Any] | None = None
    try:
        if weapon is None or weapon.bDeleteMe:
            return
        address = int(weapon._get_address())
        if any(item is not None and item["address"] == address for item in _one_frames[:-1]):
            return  # Fire/Shared/Extra wrappers and their pellets share the outer shot.
        pc = get_pc(possibly_loading=True)
        valid = _one_player(pc)
        if valid is None:
            return
        world, pawn, rank = valid
        if (pawn.IsInjuredDead() or pawn.Weapon != weapon or weapon.Instigator != pawn
                or weapon.WorldInfo != world or int(weapon.ReloadCnt) <= 0):
            return
        if _one_state is None or _one_state["identity"] != _owner:
            _one_state = dict(identity=_owner, stacks=0, cycle=0)
        state = _one_state
        token = dict(identity=_owner, cycle=state["cycle"], counted=False, credited=0, empowered=state["stacks"] >= 10)
        damage = float(weapon.InstantHitDamage)
        basis = damage
        frame = dict(address=address, weapon=WeakPointer(weapon), modifier=None, base_damage=basis,
                     token=token, executed=False, previous=_one_weapons.get(address))
        _one_frames[-1] = frame
        if len(_one_weapons) >= 16 and address not in _one_weapons:
            _one_weapons.pop(next(iter(_one_weapons)))
        _one_weapons[address] = (WeakPointer(weapon), float(world.TimeSeconds), token)
        if not token["empowered"]:
            return
        if not math.isfinite(damage) or damage <= 0. or not math.isfinite(basis) or basis <= 0.:
            raise ValueError("Invalid empowered shot damage")
        depth = sum(item is not None for item in _one_frames) - 1
        if not 0 <= depth < len(_one_amp_modifiers):
            raise RuntimeError("Empowered shot nesting limit exceeded")
        modifier = _one_amp_modifiers[depth]
        modifier.Type = unrealsdk.find_enum("EModifierType").MT_PostAdd
        modifier.Value = basis * ONE_AMP_PER_RANK * rank
        frame["modifier"] = WeakPointer(modifier)
        accepted = weapon.AddModifier(modifier, "InstantHitDamage", False)
        if frame["modifier"] is None:
            return
        live = frame["weapon"]()
        if (live is None or live.bDeleteMe or not accepted
                or not math.isclose(float(live.InstantHitDamage), damage + float(modifier.Value), rel_tol=1.e-5)):
            raise RuntimeError("Empowered shot Amp modifier was not accepted")
        message = "At One with the Gun empowered shot verified"
        if message not in _reported:
            _reported.add(message)
            unrealsdk.logging.info(f"[Zer0Rebalance] {message}: rank={rank}, amp={ONE_AMP_PER_RANK * rank:g}, base={basis:g}, final={float(live.InstantHitDamage):g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        if frame is not None:
            _remove_shot_amp(frame)
            frame["token"]["empowered"] = False  # Failed Amp must not consume a prepared shot.
            frame["token"]["counted"] = True
        _report("Could not prepare At One with the Gun shot", exc)


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.POST)
def record_one_shot(_weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    frame = _one_frames[-1] if _one_frames else None
    if frame is None:
        return
    frame["executed"] = True
    token, state = frame["token"], _one_state
    if (token["empowered"] and state is not None and state["identity"] == token["identity"]
            and state["cycle"] == token["cycle"]):
        state["stacks"], state["cycle"] = 0, state["cycle"] + 1


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.POST_UNCONDITIONAL)
def finish_one_shot(_weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if not _one_frames:
        return
    frame = _one_frames.pop()
    if frame is None:
        return
    _remove_shot_amp(frame)
    if not frame["executed"]:
        token = frame["token"]
        token["counted"] = True
        current = _one_weapons.get(frame["address"])
        if current is not None and current[2] is token:
            if frame["previous"] is None:
                _one_weapons.pop(frame["address"], None)
            else:
                _one_weapons[frame["address"]] = frame["previous"]


@hook("WillowGame.WillowProjectile:InitStats", Type.POST)
def bind_one_projectile(projectile: Any, args: Any, _ret: Any, _func: Any) -> None:
    if _one_context is None:
        return
    try:
        weapon = args.InstigatorWeapon
        if weapon is None or projectile is None or projectile.bDeleteMe:
            return
        address = int(weapon._get_address())
        frame = next((item for item in reversed(_one_frames) if item is not None and item["address"] == address), None)
        if frame is None:
            return  # Unknown/child projectiles are not silently credited to another shot.
        if len(_one_projectiles) >= 512:
            _one_projectiles.pop(next(iter(_one_projectiles)))
        _one_projectiles[int(projectile._get_address())] = (WeakPointer(projectile), time.monotonic(), frame["token"])
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not associate At One with the Gun projectile", exc)


@hook("WillowGame.WillowPawn:TookDamageFromEnemy", Type.POST)
def count_one_hit(target: Any, args: Any, _ret: Any, _func: Any) -> None:
    if _one_context is None or _one_state is None or _one_state["stacks"] >= 10:
        return
    try:
        causer = args.DamageCauser
        if causer is None:
            return
        key = int(causer._get_address())
        entry = _one_projectiles.get(key)
        projectile_entry = entry is not None
        if entry is None:
            entry = _one_weapons.get(key)
        if entry is None or entry[2]["counted"] or entry[2]["empowered"]:
            return  # Critical credit or a cancelled/empowered shot is already final.
        pipeline = args.Pipeline
        if pipeline is None:
            return
        summary = pipeline.DamageSummary
        credit = 2 if summary.bWasCrit else 1
        if entry[2]["credited"] >= credit:
            return  # Repeated normal pellets need no owner, enemy or skill reads.
        pc = args.InstigatedBy
        if pc is None or int(pc._get_address()) != _one_context[0]:
            return
        valid = _one_player(pc)
        if valid is None:
            return
        world, pawn, _ = valid
        if (target is None or target == pawn or target.bDeleteMe or target.WorldInfo != world
                or _one_enemy_opinion is None or int(target.GetOpinion(pawn)) != _one_enemy_opinion):
            return
        source = pipeline.DamageSource
        dealt = float(summary.FinalDamage) + float(summary.DamageDealtToShields)
        if not math.isfinite(dealt) or dealt <= 0. or source is None:
            return
        name = str(source.Name)
        allowed = _one_source_cache.get(name)
        if allowed is None:
            allowed = name in ("WillowDmgSource_Bullet", "WillowDmgSource_Rocket") or any(
                str(base.Name) in ("WillowDmgSource_Bullet", "WillowDmgSource_Rocket") for base in source._superfields())
            if len(_one_source_cache) >= 64:
                _one_source_cache.clear()
            _one_source_cache[name] = allowed
        if not allowed:
            return
        if causer.bDeleteMe:
            return
        if projectile_entry:
            if entry[0]() != causer or not 0. <= time.monotonic() - entry[1] <= 30.:
                return
        else:
            if entry[0]() != causer or not 0. <= float(world.TimeSeconds) - entry[1] <= 30.:
                return
        token, state = entry[2], _one_state
        if (state is None or token["counted"] or token["empowered"] or token["identity"] != _owner
                or state["identity"] != _owner or state["cycle"] != token["cycle"]):
            return
        previous_credit = token["credited"]
        token["credited"] = credit
        token["counted"] = credit == 2
        state["stacks"] = min(10, state["stacks"] + credit - previous_credit)
        message = "At One with the Gun prepared"
        if state["stacks"] == 10 and message not in _reported:
            _reported.add(message)
            unrealsdk.logging.info(f"[Zer0Rebalance] {message}: 10 charges; next shot empowered")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not count At One with the Gun hit", exc)


def _cleanup_one() -> None:
    global _one_state, _one_context, _one_main_ref
    _one_state, _one_context, _one_main_ref = None, None, None
    _one_weapons.clear()
    _one_projectiles.clear()
    for frame in tuple(_one_frames):
        if frame is not None:
            _remove_shot_amp(frame)
    if _one_hud_visible:
        try:
            _sync_one_hud(get_pc(possibly_loading=True), clear=True)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _report("Could not clean up At One with the Gun HUD", exc)


def _configure_two_fang() -> bool:
    global _two_fang_definition
    definition = _find("SkillDefinition", TWO_FANG)
    if definition is None:
        return False
    if (len(definition.SkillEffectDefinitions) != 1 or
            _path(definition.SkillEffectDefinitions[0].AttributeToModify) != "D_Attributes.Weapon.WeaponExtraShotChance"):
        raise ValueError("Unexpected Two Fang native effect")
    definition.SkillDescription = (
        "Every time you [skill]fire a gun[-skill], you have a chance to [skill]fire twice[-skill]. "
        "The extra shot [skill]does not consume ammo[-skill].")
    _two_fang_definition = definition
    return True


def _two_fang_weapon(frame: dict[str, Any]) -> Any:
    # Validate the current world before resolving the weak weapon; never restore
    # an actor left behind by travel, respawn or a character change.
    pc = get_pc(possibly_loading=True)
    if pc is None or pc.bDeleteMe:
        return None
    world, pawn = pc.WorldInfo, pc.Pawn
    if (world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe or
            (int(pc._get_address()), int(world._get_address()), int(pawn._get_address())) != frame["identity"]):
        return None
    weapon = frame["weapon"]()
    if weapon is None or weapon.bDeleteMe or weapon.WorldInfo != world or weapon.Instigator != pawn:
        return None
    return weapon


def _restore_two_fang_cost(frame: dict[str, Any]) -> None:
    weapon = _two_fang_weapon(frame)
    if weapon is not None and int(weapon.ShotCost) == 0:
        weapon.ShotCost = frame["cost"]


@hook("WillowGame.WillowWeapon:WeaponFiring.ExtraFireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.PRE)
def begin_two_fang_extra(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _two_fang_frames.append(None)
    if _two_fang_definition is None or len(_two_fang_frames) > 8 or _owner is None:
        return
    try:
        if weapon is None or weapon.bDeleteMe:
            return
        address = int(weapon._get_address())
        if any(f is not None and f["address"] == address for f in _two_fang_frames[:-1]):
            return  # A nested wrapper must not own or restore the same cost twice.
        pc = get_pc(possibly_loading=True)
        if (pc is None or pc.bDeleteMe or _path(pc.PlayerClass) != ZER0_CLASS or
                int(pc.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
            return
        world, pawn = pc.WorldInfo, pc.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe or
                pawn.Controller != pc or pawn.Weapon != weapon or pawn.IsInjuredDead() or
                weapon.Instigator != pawn or weapon.WorldInfo != world):
            return
        identity = (int(pc._get_address()), int(world._get_address()), int(pawn._get_address()))
        if identity != _owner or int(pc.GetSkillGrade(_two_fang_definition)) <= 0:
            return
        cost, clip = int(weapon.ShotCost), int(weapon.ReloadCnt)
        if cost <= 0 or clip <= 0:
            return
        frame = dict(weapon=WeakPointer(weapon), address=address, identity=identity,
                     cost=cost)
        _two_fang_frames[-1] = frame
        weapon.ShotCost = 0
        if int(weapon.ShotCost) != 0:
            raise ValueError("Two Fang zero shot cost was not retained")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        frame = _two_fang_frames[-1]
        if frame is not None:
            try:
                _restore_two_fang_cost(frame)
            except (AttributeError, TypeError, ValueError, RuntimeError) as cleanup_exc:
                _report("Could not unwind Two Fang rejected cost", cleanup_exc)
            _two_fang_frames[-1] = None
        _report("Could not prepare Two Fang free extra shot", exc)


@hook("WillowGame.WillowWeapon:ConsumeAmmo", Type.PRE)
def preserve_two_fang_ammo(weapon: Any, _args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    if not _two_fang_frames or weapon is None:
        return None
    try:
        address = int(weapon._get_address())
        frame = next((f for f in reversed(_two_fang_frames) if f is not None and f["address"] == address), None)
        if frame is not None and _two_fang_weapon(frame) == weapon:
            if int(weapon.ShotCost) != 0:
                return None  # Another modifier changed the cost; do not overwrite it.
            return Block
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not preserve Two Fang ammo", exc)
    return None


@hook("WillowGame.WillowWeapon:WeaponFiring.ExtraFireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.POST_UNCONDITIONAL)
def finish_two_fang_extra(_weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    frame = _two_fang_frames.pop() if _two_fang_frames else None
    if frame is None:
        return
    try:
        _restore_two_fang_cost(frame)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not restore Two Fang shot cost", exc)


def _cleanup_two_fang() -> None:
    for index in reversed(range(len(_two_fang_frames))):
        frame = _two_fang_frames[index]
        if frame is not None:
            try:
                _restore_two_fang_cost(frame)
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _report("Could not clean up Two Fang shot cost", exc)
            _two_fang_frames[index] = None  # Pending unconditional POST callbacks remain balanced.


def _configure_unforseen() -> bool:
    global _unforseen_configured, _unforseen_address, _unforseen_pull, _unforseen_enemy_opinion, _unforseen_damage_stacks
    definition = _find("SkillDefinition", UNFORSEEN)
    behavior = _find("Behavior_CauseDamage", UNFORSEEN_BEHAVIOR)
    stacks = _find("DesignerAttributeDefinition", UNFORSEEN_DECEPTION_STACKS)
    if definition is None or behavior is None or stacks is None:
        return False
    presentations = list(definition.SkillEffectPresentations)
    if not presentations or presentations[-1] is None:
        return False
    _unforseen_enemy_opinion = int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)
    if (_path(behavior.DamageSource) != "WillowGame.WillowDmgSource_Skill"
            or _path(behavior.DamageTypeDefinition) != "GD_Shock.DamageType.DmgType_Shock_Impact"
            or not behavior.bInflictRadiusDamage):
        raise ValueError("Unexpected Unf0reseen native explosion layout")
    radius = copy.copy(behavior.RadiusFormula)
    radius.BaseValueConstant, radius.BaseValueScaleConstant = UNFORSEEN_PULL_RADIUS, 1.
    radius.BaseValueAttribute = radius.InitializationDefinition = None
    behavior.RadiusFormula = radius
    pull = _precision_object("Behavior_CauseDamage", definition, "ZR_DecoyPull", behavior)
    # Reuse the verified native negative-momentum mechanism, not a teleport or a pawn scan.
    for field, value in (("DamageFormula", 0.), ("RadiusFormula", UNFORSEEN_PULL_RADIUS),
                         ("MomentumFormula", UNFORSEEN_PULL_MOMENTUM),
                         ("StatusEffectDamage", 0.), ("StatusEffectChance", 0.)):
        row = copy.copy(getattr(pull, field))
        row.BaseValueConstant, row.BaseValueScaleConstant = value, 1.
        row.BaseValueAttribute = row.InitializationDefinition = None
        setattr(pull, field, row)
    pull.DamageTypeDefinition, pull.InstigatorSelfDamageScale = None, 0.
    pull.bCanDamageFriendlies, pull.bInflictRadiusDamage = False, True
    pull.bDisableRadiusDamageFalloff, pull.bSkipTraceTest = False, False
    # Native graph variable binding has populated the source behavior at execution time.
    # Copy its resolved contexts only during the synchronous pull, then remove actor references.
    for field in ("Context", "TargetContext"):
        context = copy.copy(getattr(pull, field))
        context.ContextObject = None
        setattr(pull, field, context)
    pull.SelfActor = None
    _unforseen_pull, _unforseen_address = pull, int(behavior._get_address())
    _unforseen_damage_stacks = stacks
    definition.SkillDescription = (
        "Your holographic decoy [skill]pulls nearby enemies[-skill] inward before exploding, "
        "dealing increased [skill]Shock Damage[-skill]. The longer you remain in "
        "[skill]Decepti0n[-skill], the greater the explosion damage. "
        "If [skill]Death Mark[-skill] is learned, enemies damaged by the explosion are marked for death.")
    stat = presentations[-1]
    footer = str(stat.Description).split("<br>Damage Radius:", 1)[0]
    description = footer + f"<br>Damage Radius: {UNFORSEEN_PULL_RADIUS / 100.:g} meters"
    if str(stat.Description) != description:
        stat.Description = description
    _unforseen_configured = True
    return True


def _unforseen_factor(stacks: float) -> float:
    stacks = float(stacks)
    if not math.isfinite(stacks):
        raise ValueError("Invalid native Decepti0n damage stacks")
    # Native Skill_Deception grants five timed damage-buff stacks. Its stealth
    # OnDeactivated graph explodes BEFORE removing them, including MMF renewals.
    return 1.5 * (1. + .4 * min(5., max(0., stacks)))


def _unforseen_player(controller: Any) -> tuple[Any, Any, int] | None:
    cached = _unforseen_context
    if cached is None or controller is None or controller.bDeleteMe or _owner != cached[:3]:
        return None
    world, pawn = controller.WorldInfo, controller.Pawn
    if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
            or pawn.Controller != controller or _path(controller.PlayerClass) != ZER0_CLASS
            or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
            or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != cached[:3]
            or not 0. <= float(world.TimeSeconds) - cached[3] <= 1.5):
        return None
    main = _unforseen_main_ref() if _unforseen_main_ref is not None else None
    if (main is None or main.SkillInstigator != controller or int(main.Grade) <= 0
            or main.SkillState != unrealsdk.find_enum("ESkillState").SKILL_Active):
        return None
    return world, pawn, int(main.Grade)


def _restore_unforseen_formula(frame: dict[str, Any]) -> None:
    reference, frame["behavior"] = frame["behavior"], None
    if reference is None:
        return
    behavior = reference()
    if behavior is not None:
        for field, scaled in frame["scaled"].items():
            if _same_initialization(getattr(behavior, field), scaled):
                setattr(behavior, field, copy.copy(frame["original"][field]))


def _same_initialization(left: Any, right: Any) -> bool:
    return (left.BaseValueAttribute == right.BaseValueAttribute
        and left.InitializationDefinition == right.InitializationDefinition
        and math.isclose(float(left.BaseValueConstant), float(right.BaseValueConstant), rel_tol=1.e-6, abs_tol=1.e-7)
        and math.isclose(float(left.BaseValueScaleConstant), float(right.BaseValueScaleConstant), rel_tol=1.e-6, abs_tol=1.e-7))


@hook("WillowGame.Behavior_CauseDamage:ApplyBehaviorToContext", Type.PRE)
def begin_unforseen(behavior: Any, args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    if behavior is None or not _unforseen_address or int(behavior._get_address()) != _unforseen_address:
        return None
    _unforseen_frames.append(None)
    if len(_unforseen_frames) > 8:
        return Block
    if not _unforseen_configured or _unforseen_context is None or _unforseen_pull is None or _unforseen_damage_stacks is None:
        return None
    frame: dict[str, Any] | None = None
    try:
        controller = args.ContextObject
        valid = _unforseen_player(controller)
        if valid is None or controller != get_pc(possibly_loading=True):
            return None
        world, pawn, rank = valid
        clone = behavior.GetBehaviorContext(SelfObject=args.SelfObject,
            MyInstigatorObject=args.MyInstigatorObject,
            OtherEventParticipantObject=args.OtherEventParticipantObject,
            ContextData=copy.copy(behavior.TargetContext), EventData=args.EventData)
        if isinstance(clone, tuple):
            clone = clone[0]  # SDK versions may return updated out-parameters alongside the context.
        if (clone is None or clone in (controller, pawn) or clone.bDeleteMe or clone.WorldInfo != world):
            raise ValueError("Could not resolve Unf0reseen decoy center")
        if not all(math.isfinite(float(getattr(clone.Location, axis))) for axis in ("X", "Y", "Z")):
            raise ValueError("Invalid Unf0reseen decoy location")
        value = _unforseen_damage_stacks.GetValue(controller)
        stacks = float(value[0] if isinstance(value, tuple) else value)
        factor = _unforseen_factor(stacks)
        original, scaled = {}, {}
        for field in ("DamageFormula", "StatusEffectDamage"):
            value = copy.copy(getattr(behavior, field))
            if not all(math.isfinite(float(getattr(value, key))) for key in ("BaseValueConstant", "BaseValueScaleConstant")):
                raise ValueError("Invalid native Unf0reseen damage formula")
            original[field] = value
            parent = next((item for item in reversed(_unforseen_frames[:-1]) if item is not None
                           and item["behavior"] is not None), None)
            if parent is not None and _same_initialization(value, parent["scaled"][field]):
                value = parent["original"][field]
            value = copy.copy(value)
            value.BaseValueScaleConstant *= factor  # Preserve global scaling/grade exactly once, including DoT.
            scaled[field] = value
        mark = _find("SkillDefinition", DEATH_MARK)
        has_mark = mark is not None and int(controller.GetSkillGrade(mark)) > 0
        frame = dict(behavior=WeakPointer(behavior), original=original, scaled=scaled,
            controller=WeakPointer(controller), identity=_owner, hits={}, mark=has_mark, executed=False)
        _unforseen_frames[-1] = frame
        for field, value in scaled.items():
            setattr(behavior, field, copy.copy(value))
        pull = _unforseen_pull
        previous_context, previous_target = copy.copy(pull.Context), copy.copy(pull.TargetContext)
        try:
            pull.Context, pull.TargetContext = copy.copy(behavior.Context), copy.copy(behavior.TargetContext)
            pull.ApplyBehaviorToContext(ContextObject=args.ContextObject, SelfObject=args.SelfObject,
                MyInstigatorObject=args.MyInstigatorObject,
                OtherEventParticipantObject=args.OtherEventParticipantObject,
                EventData=args.EventData, KernelInfo=args.KernelInfo)
        finally:
            # Never retain the resolved clone in a private static behavior after this call.
            pull.Context, pull.TargetContext, pull.SelfActor = previous_context, previous_target, None
        if not _unforseen_frames or _unforseen_frames[-1] is not frame:
            return Block  # Travel/disable during the pull invalidated the original native call.
        key = "Unf0reseen scaling and pull prepared"
        if key not in _reported:
            _reported.add(key)
            unrealsdk.logging.info(f"[Zer0Rebalance] {key}: deception_stacks={stacks:g}, rank={rank}, factor={factor:g}, pull_radius={UNFORSEEN_PULL_RADIUS:g}, death_mark={has_mark}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        if frame is not None:
            _restore_unforseen_formula(frame)
            frame["mark"] = False
        _report("Could not prepare Unf0reseen explosion", exc)
    return None


@hook("WillowGame.Behavior_CauseDamage:ApplyBehaviorToContext", Type.POST)
def confirm_unforseen(behavior: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if behavior is not None and int(behavior._get_address()) == _unforseen_address and _unforseen_frames:
        frame = _unforseen_frames[-1]
        if frame is not None:
            frame["executed"] = True


@hook("WillowGame.WillowPawn:TookDamageFromEnemy", Type.POST)
def collect_unforseen_hit(target: Any, args: Any, _ret: Any, _func: Any) -> None:
    frame = _unforseen_frames[-1] if _unforseen_frames else None
    if frame is None or not frame["mark"] or len(frame["hits"]) >= 128:
        return
    try:
        causer = args.DamageCauser
        if (causer is None or int(causer._get_address()) != _unforseen_address
                or args.InstigatedBy is None or int(args.InstigatedBy._get_address()) != frame["identity"][0]
                or target is None or target.bDeleteMe):
            return
        pipeline = args.Pipeline
        if pipeline is None:
            return
        summary = pipeline.DamageSummary
        dealt = float(summary.FinalDamage) + float(summary.DamageDealtToShields)
        if math.isfinite(dealt) and dealt > 0.:
            frame["hits"][int(target._get_address())] = WeakPointer(target)
            key = "Unf0reseen native explosion hit verified"
            if key not in _reported:
                _reported.add(key)
                unrealsdk.logging.info(f"[Zer0Rebalance] {key}: health={float(summary.FinalDamage):g}, shield={float(summary.DamageDealtToShields):g}; Death Mark target recorded")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not collect Unf0reseen Death Mark target", exc)


@hook("WillowGame.Behavior_CauseDamage:ApplyBehaviorToContext", Type.POST_UNCONDITIONAL)
def finish_unforseen(behavior: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if behavior is None or int(behavior._get_address()) != _unforseen_address or not _unforseen_frames:
        return
    frame = _unforseen_frames.pop()
    if frame is None:
        return
    try:
        _restore_unforseen_formula(frame)
        if not frame["executed"] or not frame["mark"]:
            return
        marked = _find("SkillDefinition", DEATH_MARK_EFFECT)
        learned = _find("SkillDefinition", DEATH_MARK)
        if marked is None or learned is None:
            if frame["hits"]:
                raise ValueError("Native Death Mark definition is not loaded")
            return
        for reference in tuple(frame["hits"].values()):
            controller, target = frame["controller"](), reference()
            if (controller is None or frame["identity"] != _owner or _unforseen_player(controller) is None
                    or int(controller.GetSkillGrade(learned)) <= 0):
                return
            if (target is None or target.bDeleteMe or target.WorldInfo != controller.WorldInfo
                    or target == controller.Pawn or float(target.GetHealth()) <= 0.
                    or _unforseen_enemy_opinion is None
                    or int(target.GetOpinion(controller.Pawn)) != _unforseen_enemy_opinion):
                continue
            recipient = getattr(target, "Controller", None)
            if recipient is None or recipient.bDeleteMe:
                continue
            recipient.Behavior_DeactivateSkill(marked, False)
            # The native removal can run callbacks: reacquire target/context before applying.
            target, controller = reference(), frame["controller"]()
            if target is None or target.bDeleteMe or _unforseen_player(controller) is None:
                continue
            recipient = getattr(target, "Controller", None)
            if (recipient is not None and not recipient.bDeleteMe and target.WorldInfo == controller.WorldInfo
                    and int(controller.GetSkillGrade(learned)) > 0):
                recipient.Behavior_ActivateSkill(marked, None, 1)
                key = "Unf0reseen native Death Mark activation requested"
                if key not in _reported:
                    _reported.add(key)
                    unrealsdk.logging.info(f"[Zer0Rebalance] {key}: target={_path(target)}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not finish Unf0reseen Death Mark", exc)


def _cleanup_unforseen() -> None:
    for frame in reversed(tuple(_unforseen_frames)):
        if frame is not None:
            try:
                _restore_unforseen_formula(frame)
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _report("Could not clean Unf0reseen damage scope", exc)
            frame["mark"] = False
            frame["hits"].clear()


def _configure_critical_ascension() -> bool:
    global _ascension_configured
    main = _find("SkillDefinition", ASCENSION)
    stack = _find("SkillDefinition", ASCENSION_STACK)
    sniper = _find("AttributeDefinition", "D_Attributes.WeaponType.Weapon_Is_Sniper_Rifle")
    on_foot = _find("SkillExpressionEvaluatorDefinition", "GD_PlayerShared.SkillConstraints.SkillConstraint_OnFootOrRidingInBack")
    sources = [_find("Class", "WillowGame.WillowDmgSource_" + name) for name in ("Bullet", "Rocket")]
    if main is None or stack is None or sniper is None or on_foot is None or any(s is None for s in sources):
        return False
    provider = main.BehaviorProviderDefinition
    if provider is None or not provider.BehaviorSequences:
        return False
    sequence = copy.copy(provider.BehaviorSequences[0])
    links = list(sequence.ConsolidatedOutputLinkData)
    decay = [i for i, link in enumerate(links) if int(link.LinkIdAndLinkedBehavior) == -16777214
             and float(link.ActivateDelay) in (1., 2.5, 5.)]
    rows = list(stack.SkillEffectDefinitions)
    if len(decay) != 1 or [_path(r.AttributeToModify) for r in rows] != [
            "D_Attributes.GameplayAttributes.PlayerCriticalHitBonus", "D_Attributes.Weapon.WeaponDamage"]:
        raise ValueError("Unexpected Critical Ascensi0n stack/decay layout")
    events = list(main.DamageEvents)
    matches = [i for i, event in enumerate(events) if str(event.EventName) == "ShotEnemy"]
    if len(matches) != 1 or not events[matches[0]].EventConstraints:
        raise ValueError("Critical Ascensi0n native shot event unavailable")
    changed = False
    if float(links[decay[0]].ActivateDelay) != 2.5:
        link = copy.copy(links[decay[0]])
        link.ActivateDelay = 2.5
        links[decay[0]] = link
        sequence.ConsolidatedOutputLinkData = links
        sequences = list(provider.BehaviorSequences)
        sequences[0] = sequence
        provider.BehaviorSequences = sequences
        changed = True
    # Each coefficient becomes original * (0.5 + 0.5 * Weapon_Is_Sniper_Rifle).
    # Keep native modifier/context updates; no Python weapon scan or per-hit write.
    updated = []
    for index, original in enumerate(rows):
        row = copy.copy(original)
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(original, field))
            name = f"ZR_Ascension_{index}_{field}"
            path = ASCENSION_STACK + ":" + name
            if _path(value.InitializationDefinition) == path:
                continue
            initializer = _precision_object("AttributeInitializationDefinition", stack, name)
            half = copy.copy(value)
            half.BaseValueScaleConstant *= .5
            initializer.BaseValueMode = unrealsdk.find_enum("EBaseValueMode").BASEVALUE_InitializationDefSetsBaseValue
            initializer.RoundingMode = unrealsdk.find_enum("EAttributeInitializationRounding").ATTRROUNDING_Float
            aid = lambda constant, attribute=None: unrealsdk.make_struct("AttributeInitializationData",
                BaseValueConstant=constant, BaseValueAttribute=attribute, BaseValueScaleConstant=1.)
            initializer.ValueFormula = unrealsdk.make_struct("BalanceFormula", bEnabled=True,
                Multiplier=copy.copy(half), Level=aid(0., sniper), Power=aid(1.), Offset=copy.copy(half))
            value.BaseValueConstant, value.BaseValueScaleConstant = 0., 1.
            value.BaseValueAttribute, value.InitializationDefinition = None, initializer
            setattr(row, field, value)
            changed = True
        updated.append(row)
    if changed:
        stack.SkillEffectDefinitions = updated
        _signatures.clear()
    for definition in (main, stack):
        constraints = []
        for original in definition.SkillConstraints:
            row = copy.copy(original)
            evaluator = row.Evaluator
            if evaluator is not None and _path(evaluator) == ASCENSION + ":AttributeExpressionEvaluator_20":
                row.Evaluator = None
            row.EvaluatorDefinitions = [d for d in row.EvaluatorDefinitions
                if _path(d) != "GD_PlayerShared.SkillConstraints.SkillConstraint_SniperRifleOnly"]
            if row.Evaluator is not None or row.EvaluatorDefinitions:
                constraints.append(row)
        if not any(on_foot in row.EvaluatorDefinitions for row in constraints):
            row = copy.copy(definition.SkillConstraints[0])
            row.Evaluator, row.EvaluatorDefinitions = None, [on_foot]
            constraints.append(row)
        definition.SkillConstraints = constraints
    event = copy.copy(events[matches[0]])
    constraints = []
    for source in sources:
        constraint = copy.copy(event.EventConstraints[0])
        constraint.DamageSourceConstraint, constraint.DamageTypeConstraint = source, None
        constraints.append(constraint)
    event.EventConstraints = constraints
    events[matches[0]] = event
    main.DamageEvents = events
    main.SkillDescription = (
        "Scoring a [skill]Critical Hit[-skill] with a [skill]Sniper Rifle[-skill] increases your "
        "[skill]Gun Damage[-skill] and [skill]Critical Hit Damage[-skill] with [skill]Sniper Rifles[-skill].  "
        "This effect can stack up to 999 times.  Stacks slowly decay if you haven't scored a critical hit in awhile. "
        "Other gun types receive half of these bonuses.")
    _ascension_configured = True
    if "Critical Ascensi0n configured" not in _reported:
        _reported.add("Critical Ascensi0n configured")
        unrealsdk.logging.info("[Zer0Rebalance] Critical Ascensi0n configured: all guns build stacks; sniper bonuses full, other guns half; native decay interval 2.5 seconds")
    return changed


def _configure_innervate() -> bool:
    global _innervate_configured
    definition = _find("SkillDefinition", INNERVATE)
    if definition is None:
        return False
    effects = list(definition.SkillEffectDefinitions)
    paths = [_path(row.AttributeToModify) for row in effects]
    expected = ["D_Attributes.GameplayAttributes.FootSpeed", INNERVATE_REGEN_DISPLAY,
                INNERVATE_REGEN, INNERVATE_DAMAGE]
    if sorted(paths, key=str) != sorted(expected):
        raise ValueError(f"Unexpected Innervate effects: {paths}")
    regen = effects[paths.index(INNERVATE_REGEN)]
    if any(_path(getattr(regen, field).BaseValueAttribute) != "D_Attributes.HealthResourcePool.HealthMaxValue"
           for field in ("BaseModifierValue", "PerGradeUpgrade")):
        raise ValueError("Innervate regeneration no longer uses maximum health")
    updated = []
    for path, original in zip(paths, effects):
        if path not in (INNERVATE_REGEN_DISPLAY, INNERVATE_REGEN, INNERVATE_DAMAGE):
            updated.append(original)
            continue
        row = copy.copy(original)
        row.GradeToStartApplyingEffect, row.PerGradeUpgradeInterval, row.BonusUpgradeList = 1, 1, []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(row, field))
            value.InitializationDefinition = None
            if path == INNERVATE_REGEN:
                value.BaseValueConstant, value.BaseValueScaleConstant = 0., .016
            else:
                value.BaseValueAttribute = None
                value.BaseValueConstant = .04 if path == INNERVATE_DAMAGE else .016
                value.BaseValueScaleConstant = 1.
            setattr(row, field, value)
        updated.append(row)
    changed = any(not _same_effect(old, new) for old, new in zip(effects, updated))
    if changed:
        definition.SkillEffectDefinitions = updated
        _signatures.clear()
        unrealsdk.logging.info("[Zer0Rebalance] Innervate: gun damage 4% and maximum-health regeneration 1.6% per effective rank; native movement and Decepti0n condition preserved")
    _innervate_configured = True
    return changed


def _configure_skills(*, force: bool = False) -> None:
    for name, pending, configure in (
            ("Iron Hand", not _iron_hand_configured, _configure_iron_hand),
            ("Grim", not _grim_configured, _configure_grim),
            ("Fearless", not _fearless_configured, _configure_fearless),
            ("Resurgence", not _resurgence_configured, _configure_resurgence),
            ("Kill Confirmed", not _kill_confirmed_configured, _configure_kill_confirmed),
            ("Velocity", not _velocity_configured, _configure_velocity),
            ("Many Must Fall", not _many_must_fall_configured, _configure_many_must_fall),
            ("Optics", not _optics_configured, _configure_optics),
            ("Like the Wind", not _like_the_wind_configured, _configure_like_the_wind),
            ("Be Like Water", not _water_configured, _configure_be_like_water),
            ("Precision", not _precision_configured, _configure_precision),
            ("Innervate", not _innervate_configured, _configure_innervate),
            ("Critical Ascensi0n", not _ascension_configured, _configure_critical_ascension),
            ("At One with the Gun", not _one_configured, _configure_one_with_gun),
            ("Two Fang", _two_fang_definition is None, _configure_two_fang),
            ("Unf0reseen", not _unforseen_configured, _configure_unforseen)):
        if pending or force:
            try:
                configure()
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _report("Could not configure " + name, exc)


def _refresh_skill_effects(controller: Any, identity: tuple[int, int, int]) -> None:
    """One local skill snapshot per second; no repeated writes while equipment/rank are stable."""
    global _resurgence_context
    global _kill_confirmed_context, _kill_confirmed_count
    global _like_the_wind_context, _like_the_wind_ref
    global _water_context, _water_main_ref, _water_movement_ref, _water_applied_grade, _water_needs_sync
    global _precision_context, _precision_main_ref
    global _one_context, _one_main_ref, _one_state
    global _unforseen_context, _unforseen_main_ref
    _unforseen_context, _unforseen_main_ref = None, None
    _one_context, _one_main_ref = None, None
    _resurgence_context = None
    _kill_confirmed_context = None
    _like_the_wind_context, _like_the_wind_ref = None, None
    _water_context, _water_main_ref, _water_movement_ref = None, None, None
    _precision_context, _precision_main_ref = None, None
    manager = controller.GetSkillManager()
    if manager is None or getattr(manager, "bUpdatingSkills", False):
        return
    inventory = getattr(controller.Pawn, "InvManager", None)
    equipment = inventory.GetCurrentClassMod() if inventory is not None else None
    equipment_id = int(equipment._get_address()) if equipment is not None else 0
    configured_paths = tuple(path for ready, path in (
        (_iron_hand_configured, IRON_HAND), (_grim_configured, GRIM),
        (_velocity_configured, VELOCITY), (_optics_configured, OPTICS),
        (_like_the_wind_configured, LIKE_THE_WIND), (_like_the_wind_configured, LIKE_THE_WIND_LEGACY),
        (_water_configured, BE_LIKE_WATER), *tuple((_water_configured, path) for path in WATER_LEGACY),
        (_precision_configured, PRECISION), (_innervate_configured, INNERVATE),
        (_one_configured, ONE_WITH_GUN), (_one_configured, ONE_HIPFIRE)) if ready)
    eligible = []
    resurgence_rank = 0
    kill_confirmed_rank, kill_confirmed_count = 0, 0
    water_main, water_movement = None, None
    active_state = unrealsdk.find_enum("ESkillState").SKILL_Active
    definition_paths: dict[int, str | None] = {}
    for skill in tuple(manager.ActiveSkills):
        definition = skill.Definition
        if definition is None or skill.SkillInstigator!=controller:
            continue
        definition_id = int(definition._get_address())
        if definition_id not in definition_paths:
            definition_paths[definition_id] = _path(definition)
        path = definition_paths[definition_id]
        if path == UNFORSEEN and _unforseen_configured and int(skill.Grade) > 0:
            _unforseen_context = (*identity, float(controller.WorldInfo.TimeSeconds))
            _unforseen_main_ref = WeakPointer(skill)
        if path == ONE_WITH_GUN and _one_configured and int(skill.Grade) > 0:
            _one_context = (*identity, int(skill.Grade), float(controller.WorldInfo.TimeSeconds))
            _one_main_ref = WeakPointer(skill)
        if path == PRECISION and _precision_configured and int(skill.Grade) > 0 and skill.SkillState == active_state:
            _precision_context = (*identity, int(skill.Grade), float(controller.WorldInfo.TimeSeconds))
            _precision_main_ref = WeakPointer(skill)
        if _water_configured and path == BE_LIKE_WATER:
            water_main = skill
        elif _water_configured and path == WATER_MOVEMENT:
            water_movement = skill
        if path == LIKE_THE_WIND and _like_the_wind_configured and int(skill.Grade) > 0:
            _like_the_wind_context = (*identity, int(skill.Grade), float(controller.WorldInfo.TimeSeconds))
            _like_the_wind_ref = WeakPointer(skill)
        if path == KILL_CONFIRMED and _kill_confirmed_configured and skill.SkillState == active_state:
            kill_confirmed_rank = max(kill_confirmed_rank, int(skill.Grade))
        if path == KILL_CONFIRMED_STACK:
            kill_confirmed_count += 1
        if path==RESURGENCE and _resurgence_configured and skill.SkillState==active_state:
            resurgence_rank = max(resurgence_rank,int(skill.Grade))
        if path in configured_paths:
            eligible.append(skill)
    if _one_context is None or (_one_state is not None and _one_state["identity"] != identity):
        _one_state = None
        _one_weapons.clear()
        _one_projectiles.clear()
    _water_main_ref = WeakPointer(water_main) if water_main is not None else None
    _water_movement_ref = WeakPointer(water_movement) if water_movement is not None else None
    _water_applied_grade = int(water_movement.Grade) if water_movement is not None else 0
    water_rank = int(water_main.Grade) if water_main is not None else 0
    if _water_configured and (water_rank > 0 or water_movement is not None or _water_state is not None):
        _water_context = (*identity, water_rank, float(controller.WorldInfo.TimeSeconds))
    _water_needs_sync = False
    if resurgence_rank>0 and controller.PlayerStats is not None:
        _resurgence_context = (*identity,int(controller.PlayerStats._get_address()),resurgence_rank,
                              float(controller.WorldInfo.TimeSeconds))
    _kill_confirmed_count = kill_confirmed_count
    if _kill_confirmed_configured and (kill_confirmed_rank > 0 or kill_confirmed_count > 0):
        _kill_confirmed_context = (*identity, kill_confirmed_rank, float(controller.WorldInfo.TimeSeconds))
    seen: set[int] = set()
    for skill in eligible:
        definition = skill.Definition
        address = int(skill._get_address())
        seen.add(address)
        if int(skill.Grade) <= 0:
            _signatures.pop(address, None)
            continue
        signature = (equipment_id, int(definition._get_address()), int(skill.Grade), int(skill.SkillState))
        if _signatures.get(address) == signature:
            continue
        none_target = unrealsdk.find_enum("EEffectTarget").TARGET_None
        expected = [row for row in definition.SkillEffectDefinitions
                    if row.AttributeToModify is not None and row.EffectTarget != none_target]
        current = list(skill.SkillEffects)
        gameplay = [(index, item) for index, item in enumerate(current)
                    if item.EffectData.AttributeToModify is not None and item.EffectData.EffectTarget != none_target]
        if tuple(_layout(item.EffectData) for _, item in gameplay) != tuple(_layout(row) for row in expected):
            modes = unrealsdk.find_enum("EAdjustModifierMode")
            active = skill.SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active
            reference, player = WeakPointer(skill), WeakPointer(controller)

            def resolve() -> Any | None:
                owner, live = player(), reference()
                if (owner is None or owner.bDeleteMe or live is None or _owner != identity
                        or owner.WorldInfo is None or owner.WorldInfo.bDeleteMe
                        or owner.Pawn is None or owner.Pawn.bDeleteMe
                        or (int(owner._get_address()), int(owner.WorldInfo._get_address()),
                            int(owner.Pawn._get_address())) != identity or live.SkillInstigator != owner):
                    return None
                return live

            previous = [copy.copy(item) for item in current]
            if active:
                skill.AdjustModifiers(modes.WILLOW_ADJUST_RemoveModifer, True)
            live = resolve()
            if live is None:
                return
            try:
                live.SkillEffects = []
                live.BuildSkillEffects()
            except (AttributeError, TypeError, ValueError, RuntimeError):
                live = resolve()
                if live is not None:
                    live.SkillEffects = previous
                raise
            finally:
                live = resolve()
                if live is not None and active and live.SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active:
                    live.AdjustModifiers(modes.WILLOW_ADJUST_InitialAddModifer, False)
            live = resolve()
            if live is not None:
                live.bForceRefreshModifiersNextTick = True
                _signatures[address] = signature
            return  # Never reuse the skill snapshot after native callbacks.
        if current:
            updated = [copy.copy(item) for item in current]
            for (index, _), data in zip(gameplay, expected):
                updated[index].EffectData = copy.copy(data)
            skill.SkillEffects = updated
        skill.bForceRefreshModifiersNextTick = True
        _signatures[address] = signature
    for address in set(_signatures)-seen:
        del _signatures[address]


def _reset() -> None:
    global _two_fang_definition
    _cleanup_two_fang()
    _two_fang_definition = None
    global _kill_confirmed_helper, _water_movement_definition
    _kill_confirmed_helper, _water_movement_definition = None, None
    _one_source_cache.clear()
    global _ascension_configured
    _ascension_configured = False
    global _precision_pending
    _precision_pending = None  # Departing-world actors must not be inspected here.
    global _unforseen_configured, _unforseen_context, _unforseen_main_ref, _unforseen_damage_stacks
    _unforseen_configured, _unforseen_context, _unforseen_main_ref = False, None, None
    _unforseen_damage_stacks = None
    for index in reversed(range(len(_unforseen_frames))):
        frame = _unforseen_frames[index]
        if frame is not None:
            try:
                _restore_unforseen_formula(frame)  # Static damage data only; never inspect departing actors.
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _report("Could not restore Unf0reseen definition during reset", exc)
            frame["mark"] = False
            frame["hits"].clear()
        _unforseen_frames[index] = None
    global _one_configured, _one_context, _one_main_ref, _one_state, _one_amp_modifiers
    _one_configured, _one_context, _one_main_ref, _one_state, _one_amp_modifiers = False, None, None, None, ()
    _one_weapons.clear()
    _one_projectiles.clear()
    _one_hud_visible.clear()
    _one_hud_counts_reset()
    for index in range(len(_one_frames)):
        _one_frames[index] = None
    global _innervate_configured
    _innervate_configured = False
    global _precision_configured, _precision_context, _precision_main_ref
    _precision_configured, _precision_context, _precision_main_ref = False, None, None
    _precision_targets.clear()
    for index in range(len(_precision_frames)):
        _precision_frames[index] = None
    global _water_configured, _water_context, _water_main_ref, _water_movement_ref, _water_state
    global _water_applied_grade, _water_next_check, _water_mutating, _water_needs_sync
    _water_configured, _water_context, _water_main_ref, _water_movement_ref, _water_state = False, None, None, None, None
    _water_applied_grade, _water_next_check, _water_mutating, _water_needs_sync = 0, 0., False, False
    _water_hud_visible.clear()
    _water_hud_counts_reset()
    for index in range(len(_water_damage_frames)):
        frame = _water_damage_frames[index]
        if frame is not None:
            frame["added"] = False
            frame["parent"] = None
        _water_damage_frames[index] = None
    _water_source_cache.clear()
    global _like_the_wind_configured, _like_the_wind_context, _like_the_wind_ref
    _like_the_wind_configured, _like_the_wind_context, _like_the_wind_ref = False, None, None
    global _optics_configured
    _optics_configured = False
    global _many_must_fall_configured
    _many_must_fall_configured = False
    global _velocity_configured
    _velocity_configured = False
    global _kill_confirmed_configured, _kill_confirmed_context, _kill_confirmed_count
    global _kill_confirmed_aiming, _kill_confirmed_deadline, _kill_confirmed_next_check, _kill_confirmed_updating
    _kill_confirmed_configured, _kill_confirmed_context, _kill_confirmed_count = False, None, 0
    _kill_confirmed_aiming, _kill_confirmed_deadline, _kill_confirmed_next_check = None, 0., 0.
    _kill_confirmed_updating = False
    global _iron_hand_configured, _grim_configured, _fearless_configured, _resurgence_configured, _owner, _next_check
    global _resurgence_context, _resurgence_restoring
    _iron_hand_configured, _grim_configured, _fearless_configured, _resurgence_configured = False, False, False, False
    _owner, _next_check, _resurgence_context, _resurgence_restoring = None, 0., None, False
    _signatures.clear()


def _enable() -> None:
    _reset()
    _configure_skills()
    unrealsdk.logging.info("[Zer0Rebalance] 1.0.7 enabled; At One with the Gun native HUD counter; stability and maintenance optimizations; restart to remove native changes")


def _disable() -> None:
    _cleanup_unforseen()
    _cleanup_one()
    try:
        _cleanup_precision(disabling=True)
        _cleanup_water(get_pc(possibly_loading=True))
    finally:
        _reset()


@hook("WillowGame.PlayerSkillTree:Initialize", Type.PRE)
def prepare_skills(_tree: Any, args: Any, _ret: Any, _func: Any) -> None:
    definition = getattr(args, "SkillTreeDef", None)
    if definition is None or not str(_path(definition)).startswith("GD_Assassin_"):
        return
    _configure_skills(force=True)


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def maintain_skills(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _ascension_configured
    _flush_precision_pending(controller)
    if _sync_one_hud(controller):
        return  # Native HUD callbacks invalidate controller/skill snapshots.
    global _unforseen_configured, _unforseen_context, _unforseen_main_ref
    global _one_configured, _one_context, _one_main_ref
    global _precision_configured, _precision_context, _precision_main_ref
    global _water_configured, _water_context, _water_state
    if _tick_be_like_water(controller):
        return
    global _like_the_wind_configured, _like_the_wind_context, _like_the_wind_ref
    global _optics_configured, _innervate_configured
    global _many_must_fall_configured
    global _velocity_configured
    global _kill_confirmed_configured, _kill_confirmed_context, _kill_confirmed_aiming
    if _tick_kill_confirmed(controller):
        return  # Native skill callbacks invalidate the current controller/skill snapshot.
    global _next_check, _owner, _iron_hand_configured, _grim_configured, _fearless_configured, _resurgence_configured
    global _resurgence_context
    now = time.monotonic()
    if controller is None or now < _next_check or controller != get_pc(possibly_loading=True):
        return
    _next_check = now+1.
    try:
        if controller.bDeleteMe or _path(controller.PlayerClass) != ZER0_CLASS:
            _unforseen_context, _unforseen_main_ref = None, None
            _one_context, _one_main_ref = None, None
            _precision_context, _precision_main_ref = None, None
            _water_context, _water_state = None, None
            _like_the_wind_context, _like_the_wind_ref = None, None
            _kill_confirmed_context, _kill_confirmed_aiming = None, None
            _owner, _resurgence_context = None, None
            _signatures.clear()
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.Controller != controller):
            return
        identity = (int(controller._get_address()), int(world._get_address()), int(pawn._get_address()))
        if _owner != identity:
            _ascension_configured = False
            _unforseen_configured, _unforseen_context, _unforseen_main_ref = False, None, None
            _precision_configured, _precision_context, _precision_main_ref = False, None, None
            _precision_targets.clear()
            _water_configured, _water_context, _water_state = False, None, None
            _like_the_wind_configured, _like_the_wind_context, _like_the_wind_ref = False, None, None
            _optics_configured, _innervate_configured, _one_configured = False, False, False
            _many_must_fall_configured = False
            _velocity_configured = False
            _kill_confirmed_configured, _kill_confirmed_context, _kill_confirmed_aiming = False, None, None
            _owner, _iron_hand_configured, _grim_configured, _fearless_configured, _resurgence_configured = identity, False, False, False, False
            _resurgence_context = None
            _signatures.clear()
        if _two_fang_definition is None or not _ascension_configured or not _iron_hand_configured or not _grim_configured or not _fearless_configured or not _resurgence_configured or not _kill_confirmed_configured or not _velocity_configured or not _many_must_fall_configured or not _optics_configured or not _like_the_wind_configured or not _water_configured or not _precision_configured or not _innervate_configured or not _one_configured or not _unforseen_configured:
            _configure_skills()
        if _iron_hand_configured or _grim_configured or _resurgence_configured or _kill_confirmed_configured or _velocity_configured or _optics_configured or _like_the_wind_configured or _water_configured or _precision_configured or _innervate_configured or _one_configured or _unforseen_configured:
            _refresh_skill_effects(controller, identity)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _report("Could not maintain Zer0 skills", exc)


@hook("WillowGame.WillowPlayerController:PreClientTravel", Type.PRE)
@hook("WillowGame.WillowPlayerController:Destroyed", Type.PRE)
def suspend_skills(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if (_owner is not None and int(controller._get_address()) == _owner[0]) or controller == get_pc(possibly_loading=True):
        if str(getattr(getattr(_func, "func", None), "Name", "")) == "PreClientTravel":
            _cleanup_unforseen()
            _cleanup_one()
            _cleanup_precision()
            _cleanup_water(controller)
        _reset()  # Forget identities; never inspect or mutate actors from the departing world.


mod = build_mod(hooks=[prepare_skills, maintain_skills, suspend_skills, restore_resurgence_on_critical, avoid_like_the_wind_damage,
    begin_water_damage, finish_water_damage, begin_precision_damage, begin_precision_hit, finish_precision_hit, guard_precision_reflection,
    begin_one_shot, record_one_shot, finish_one_shot, bind_one_projectile, count_one_hit,
    begin_unforseen, confirm_unforseen, finish_unforseen, collect_unforseen_hit,
    begin_two_fang_extra, preserve_two_fang_ammo, finish_two_fang_extra],
    on_enable=_enable, on_disable=_disable)
