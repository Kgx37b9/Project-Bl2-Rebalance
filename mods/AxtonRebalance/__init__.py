"""Axton skill balance adjustments."""

from __future__ import annotations

import copy
import faulthandler
import math
import os
import random
import struct
import tempfile
import time
from typing import Any

import unrealsdk  # pyright: ignore[reportMissingModuleSource]
from mods_base import ObjectFlags, build_mod, get_pc, hook
from unrealsdk.hooks import Block, Type, prevent_hooking_direct_calls  # pyright: ignore[reportMissingModuleSource]
from unrealsdk.unreal import WeakPointer  # pyright: ignore[reportMissingModuleSource]


AXTON_CLASS = "GD_Soldier.Character.CharClass_Soldier"
BEE_RECHARGE_BEHAVIOR = "GD_Shields.A_Item.Shield_Impact_05_Legendary:BehaviorProviderDefinition_5.Behavior_PostAkEvent_95"
BEE_RECHARGE_EVENT = "Ake_UI.UI_Shields.Ak_Play_UI_Shield_Impact_The_Bee_Res"
_bee_recharge_context: tuple[int, int, int, int] | None = None
_bee_recharge_announced = False


def _sync_bee_recharge_state(pawn: Any, context: tuple[int, int, int]) -> None:
    """Reuse the existing maintenance pass; ignore full-shield float jitter."""
    global _bee_recharge_context, _bee_recharge_announced
    if _bee_recharge_context is None:
        return
    if _bee_recharge_context[:3] != context:
        _bee_recharge_context, _bee_recharge_announced = None, False
        return
    current, maximum = float(pawn.GetShieldStrength()), float(pawn.GetMaxShieldStrength())
    if (math.isfinite(current) and math.isfinite(maximum) and maximum > 0.
            and current < maximum - max(1e-4, maximum * 1e-6)):
        _bee_recharge_announced = False


def _rearm_bee_recharge_on_damage(pipeline: Any, args: Any, result: Any) -> None:
    """Final shield damage rearms even when recharge occurs between maintenance passes."""
    global _bee_recharge_announced
    cached = _bee_recharge_context
    if cached is None or not _bee_recharge_announced:
        return
    target = args.InDamagedActor
    if target is None or int(target._get_address()) != cached[2] or target.bDeleteMe:
        return
    world = target.WorldInfo
    owner = target.Controller
    if (world is None or world.bDeleteMe or int(world._get_address()) != cached[1]
            or owner is None or owner.bDeleteMe or int(owner._get_address()) != cached[0]
            or owner.Pawn != target):
        return
    summary = result if result is not None else pipeline.DamageSummary
    damage = float(summary.DamageDealtToShields)
    if math.isfinite(damage) and damage > 0.:
        damage_type = pipeline.GetDamageTypeDef()
        if damage_type is not None and not damage_type.IsHealingDamageType():
            _bee_recharge_announced = False


@hook("GearboxFramework.Behavior_PostAkEvent:ApplyBehaviorToContext", Type.PRE)
def filter_bee_recharge_sound(behavior: Any, args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    """Play Bee's native recharge cue once per local charge cycle, without mutating its graph."""
    global _bee_recharge_context, _bee_recharge_announced
    if str(behavior.Name) != "Behavior_PostAkEvent_95" or _skill_path(behavior) != BEE_RECHARGE_BEHAVIOR:
        return None
    try:
        if behavior.Event is None or _skill_path(behavior.Event) != BEE_RECHARGE_EVENT:
            return None
        pc = get_pc(possibly_loading=True)
        if (pc is None or pc.bDeleteMe or pc.PlayerClass is None
                or _skill_path(pc.PlayerClass) != AXTON_CLASS):
            return None
        world, pawn, shield = pc.WorldInfo, pc.Pawn, args.ContextObject
        if (world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe
                or pawn.Controller != pc or shield is None or shield.bDeleteMe or shield.WorldInfo != world):
            return None
        # Actor ownership/instigator fields are native; never intercept another player's item.
        owner = shield.Owner
        if owner not in (pc, pawn) and shield.Instigator != pawn:
            return None
        identity = (int(pc._get_address()), int(world._get_address()),
                    int(pawn._get_address()), int(shield._get_address()))
        _sync_bee_recharge_state(pawn, identity[:3])
        current, maximum = float(pawn.GetShieldStrength()), float(pawn.GetMaxShieldStrength())
        if (not math.isfinite(current) or not math.isfinite(maximum) or maximum <= 0.
                or current < maximum - max(1e-4, maximum * 1e-6)):
            return None
        if _bee_recharge_context == identity and _bee_recharge_announced:
            return Block  # Only the erroneous duplicate sound leaf; Amp and shield events continue.
        _bee_recharge_context, _bee_recharge_announced = identity, True
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not filter duplicate Bee recharge sound", exc)
    return None


READY = "GD_Soldier_Skills.Guerrilla.Ready"
READY_FIRE_PER_RANK = .05
READY_RELOAD_PER_RANK = -.08
READY_MOVEMENT = READY + ":AR_ReloadMovement"  # Stable legacy path; now reload-triggered Fire Rate.
READY_HUD = READY + ":AR_ReloadMovementHUD"
READY_BUFF_SECONDS = 6.0
_ready_hud_next_check = 0.
_ready_hud_visible = False
_ready_active_state = 0
_ready_definition_address = 0
_ready_movement_address = 0
_ready_reload_frames: list[Any] = []
GUERRILLA_BRANCH = "GD_Soldier_Skills.SkillTree.Branch_Guerrilla"
GUNPOWDER_BRANCH = "GD_Soldier_Skills.SkillTree.Branch_Gunpowder"
SURVIVAL_BRANCH = "GD_Soldier_Skills.SkillTree.Branch_Survival"
CRISIS_MANAGEMENT = "GD_Soldier_Skills.Guerrilla.CrisisManagement"
CRISIS_MELEE_ATTRIBUTE = "D_Attributes.DamageSourceModifiers.InstigatedMeleeDamageModifier"
CRISIS_GUN_ATTRIBUTE = "D_Attributes.Weapon.WeaponDamage"
CRISIS_DAMAGE_PER_RANK = .05
CRISIS_RESISTANCE_PER_RANK = .06
_crisis_definition_address = 0
_crisis_context: tuple[int, int, int, int, float] | None = None
CRISIS_RESISTANCE_ATTRIBUTES = tuple(
    "D_Attributes.DamageTypeModifers." + name for name in (
        "NormalImpactDamageModifier", "ExplosiveImpactDamageModifier",
        "CorrosiveImpactDamageModifier", "CorrosiveStatusEffectDamageModifier",
        "IncendiaryImpactDamageModifier", "IncendiaryStatusEffectDamageModifier",
        "ShockImpactDamageModifier", "ShockStatusEffectDamageModifier",
        "AmpImpactDamageModifier",
    )
)
RESOURCEFUL = "GD_Soldier_Skills.Survival.Resourceful"
RESOURCEFUL_COOLDOWN_ATTRIBUTE = "D_Attributes.ActiveSkillCooldownResource.ActiveSkillCooldownConsumptionRate"
RESOURCEFUL_DAMAGE_SECONDS_PER_RANK = .3
RESOURCEFUL_INTERNAL_COOLDOWN = 1.0
RESOURCEFUL_DURATION_PER_RANK = 1.
RESOURCEFUL_DURATION_ATTRIBUTE = "D_Attributes.SkillAttributes.SkillDuration"
SCORPIO_SKILL = "GD_Soldier_Skills.Scorpio.Skill_Scorpio"
TURRET_COOLDOWN_ATTRIBUTE = "GD_Soldier_Skills.Misc.Cooldown_Turret"
TURRET_BASE_COOLDOWN = 30.
_resourceful_scorpio_address = 0
_resourceful_duration_ref: Any = None  # Weak live Skill only; no retained actor.
_resourceful_duration_state: tuple[tuple[int, int, int, int, float], float] | None = None
_resourceful_last_proc: tuple[tuple[int, int, int], float] | None = None
_resourceful_damage_frames: list[dict[str, Any] | None] = []
_resourceful_context: tuple[int, int, int, int, float] | None = None
PREPARATION = "GD_Soldier_Skills.Survival.Preparation"
PRESSURE = "GD_Soldier_Skills.Survival.Pressure"
PRESSURE_DAMAGE_PER_RANK = .07
PRESSURE_DELAY_PER_RANK = -.24
_pressure_definition_address = 0
_pressure_context: tuple[int, int, int, int, float] | None = None
PRESSURE_MISSING_SHIELD_INIT = PRESSURE + ":AR_MissingShieldFraction"
PRESSURE_DEPLETED_INIT = PRESSURE + ":AR_DepletedShieldDelay"
PRESSURE_SHIELD_DELAY_ATTRIBUTE = "D_Attributes.ShieldResourcePool.ShieldOnIdleRegenerationDelay"
PREPARATION_ACTIVE = PREPARATION + "_Active"
PREPARATION_SHIELD_PER_RANK = .07
PREPARATION_RESISTANCE_PER_RANK = .30
PREPARATION_RESISTANCE_INIT = PREPARATION_ACTIVE + ":AR_FullShieldResistance"
PREPARATION_GRADE_ATTRIBUTE = "GD_Soldier_Skills.SkillGradeModifiers.Preparation"
SHIELD_CAPACITY_ATTRIBUTE = "D_Attributes.ShieldResourcePool.ShieldMaxValue"
SHIELD_REGEN_ATTRIBUTE = "D_Attributes.ShieldResourcePool.ShieldPassiveRegenerationRate"
HEALTH_REGEN_ATTRIBUTE = "D_Attributes.HealthResourcePool.HealthPassiveRegenerationRate"
HEALTH_CURRENT_ATTRIBUTE = "D_Attributes.HealthResourcePool.HealthCurrentValue"
HEALTH_MAX_ATTRIBUTE = "D_Attributes.HealthResourcePool.HealthMaxValue_Player"
LAST_DITCH_EFFORT = "GD_Soldier_Skills.Survival.LastDitchEffort"
LAST_DITCH_DAMAGE_PER_RANK = .08
LAST_DITCH_HEALTH_THRESHOLD = .50
LAST_DITCH_RECEIVED_FIELDS = tuple(
    "Received" + kind + "DamageModifier" for kind in ("Bullet", "Grenade", "Melee", "Rocket", "StatusEffect", "Skill")
)
LAST_DITCH_SOURCE_FIELDS = {
    "WillowDmgSource_" + name: "Received" + kind + "DamageModifier"
    for kind, names in (
        ("Bullet", ("Bullet", "Pistol", "Shotgun", "MachineGun", "SubMachineGun", "Sniper")),
        ("Grenade", ("Grenade",)), ("Melee", ("Melee",)), ("Rocket", ("Rocket",)),
        ("StatusEffect", ("StatusEffect",)), ("Skill", ("Skill", "Skill_IgnoreIOs")),
    ) for name in names
}
SCORCHED_EARTH = "GD_Soldier_Skills.Guerrilla.ScorchedEarth"
DOUBLE_UP = "GD_Soldier_Skills.Guerrilla.DoubleUp"
DOUBLE_UP_COOLDOWN = .25
DOUBLE_UP_DAMAGE_PENALTY = .40
DOUBLE_UP_VULNERABILITY = .25
DOUBLE_UP_DEBUFF_SECONDS = 10.0
NUKE = "GD_Soldier_Skills.Gunpowder.Nuke"
NUKE_TURRET_DAMAGE_BONUS = 2.50
NUKE_FIRE_INTERVAL_PENALTY = .25
NUKE_BONUS_AT_ONE = .30
NUKE_BONUS_AT_OP10 = 2.50
LASER_SIGHT = "GD_Soldier_Skills.Guerrilla.LaserSight"
LASER_SIGHT_DAMAGE_PER_RANK = .06
LASER_SIGHT_FIRE_PER_RANK = .04
GRENADIER = "GD_Soldier_Skills.Guerrilla.Grenadier"
BOOST = "GD_Soldier_Skills.Guerrilla.AR_Boost"
BOOST_LAYOUT = "GD_Soldier_Skills.SkillTree.Layout_Guerrilla"
BOOST_ICON = "UI_Tulip_SharedSkillIcons_Mech.SkillIcon-Mechro20"
BOOST_DURATION_PER_RANK = .10
BOOST_STRENGTH_PER_RANK = .05
KILL_MASTERY_SKILLS = (
    "GD_Soldier_Skills.Guerrilla.Onslaught",
    "GD_Soldier_Skills.Gunpowder.MetalStorm",
    "GD_Soldier_Skills.Survival.QuickCharge",
)
KILL_MASTERY_HELPERS = tuple(BOOST + ":AR_" + path.rsplit(".", 1)[1] + "Bonus"
                            for path in KILL_MASTERY_SKILLS)
_kill_mastery_targets: dict[str, tuple[int, int]] = {}
_kill_mastery_active_state = 0
_kill_mastery_logged: set[str] = set()
_boost_definition_address = 0
_boost_configuring = False
IMPACT = "GD_Soldier_Skills.Gunpowder.Impact"
BATTLEFRONT = "GD_Soldier_Skills.Gunpowder.Battlefront"
BATTLEFRONT_CRITICAL_PER_RANK = .05
HEALTHY = "GD_Soldier_Skills.Survival.HealthY"
HEALTHY_TURRET_HELPER = HEALTHY + ":AR_TurretResistance"  # Stable legacy path; now a regeneration helper.
HEALTHY_REGEN_INIT = HEALTHY + ":AR_HealthRegenPerRank"
HEALTHY_HEALTH_PER_RANK = .05
HEALTHY_REGEN_PER_RANK = .006
HEALTHY_HEALTH_ATTRIBUTE = "D_Attributes.HealthResourcePool.HealthMaxValue"
_healthy_definition_address = 0
_healthy_helper_address = 0
FORBEARANCE = "GD_Soldier_Skills.Survival.Forbearance"
MOVEMENT_ATTRIBUTE = "D_Attributes.GameplayAttributes.FootSpeed"
FORBEARANCE_STEAL_PER_RANK = .01
FORBEARANCE_STATUS_DURATION_PER_RANK = -.08
FORBEARANCE_DURATION_ATTRIBUTES = tuple(
    "D_Attributes.StatusEffectModifiers." + name + "DurationResistanceModifier"
    for name in ("Amp", "Corrosive", "Ignite", "Shock", "Slow"))
_forbearance_explosive_type = -1
_forbearance_radius_frames: list[dict[str, Any] | None] = []
_forbearance_context: tuple[int, int, int, int, float] | None = None
_forbearance_address = 0
_forbearance_legacy_address = 0
_forbearance_restoring = False
DUTY_CALLS = "GD_Soldier_Skills.Gunpowder.DutyCalls"
DUTY_STACK_HELPER = DUTY_CALLS + ":AR_DamageStacks"
DUTY_HUD = DUTY_CALLS + ":AR_StackHUD"
_duty_hud_next_check = 0.
_duty_hud_visible = False
DUTY_RELOAD_PER_RANK = .004
DUTY_CRITICAL_PER_RANK = .005
DUTY_STACK_LIMIT = 20
DUTY_DECAY_DELAY = 3.
DUTY_DECAY_INTERVAL = .25
_duty_definition_address = 0
_duty_helper_address = 0
_duty_active_state = 0
_duty_context: tuple[int, int, int, int, float] | None = None
_duty_main_ref: Any = None
_duty_state: tuple[tuple[int, int, int], int, float] | None = None
_duty_shot_frames: list[dict[str, Any] | None] = []
_duty_weapons: dict[int, tuple[Any, float, dict[str, Any]]] = {}
_duty_projectiles: dict[int, tuple[Any, float, dict[str, Any]]] = {}
EXPERTISE = "GD_Soldier_Skills.Gunpowder.Expertise"
METAL_STORM = "GD_Soldier_Skills.Gunpowder.MetalStorm"
METAL_STORM_AMMO_CHANCE_PER_RANK = .06
_metal_storm_address = 0
_metal_storm_context: dict[str, Any] | None = None
_metal_storm_shots: list[dict[str, Any] | None] = []
STEADY = "GD_Soldier_Skills.Gunpowder.Steady"
STEADY_LAUNCHER = STEADY + ":AR_LauncherBonuses"
_steady_definition_address = 0
_steady_launcher_address = 0
RECOIL_ATTRIBUTE = "D_Attributes.Weapon.WeaponPerShotAccuracyImpulse"
RELOAD_ATTRIBUTE = "D_Attributes.Weapon.WeaponReloadSpeed"
RECOIL_COEFFICIENT = "GD_Soldier_Skills.Misc.Att_MetalStorm_RecoilPerLevel"
QUICK_CHARGE_COEFFICIENT = "GD_Soldier_Skills.Misc.Att_QuickCharge_ShieldRegenPerLvl"
QUICK_CHARGE = "GD_Soldier_Skills.Survival.QuickCharge"
QUICK_CHARGE_REGEN_PER_RANK = .012
QUICK_CHARGE_RELOAD_PER_RANK = .08
PHALANX = "GD_Soldier_Skills.Survival.PhalanxShield"
PHALANX_HEALTH_INITIALIZER = "GD_Scorpio.Shield.Init_TurretShieldHealth"
PHALANX_NATIVE_HEALTH_SCALE = 1.65
PHALANX_HEALTH_FACTOR = 1.70
PHALANX_PLAYER_SHIELD = .20
MAG_LOCK = "GD_Soldier_Skills.Survival.Mag-Lock"
MAG_LOCK_DESCRIPTION = (
    "Your [skill]Sabre Turret[-skill] can attach to [skill]walls and ceilings[-skill] "
    "and draws increased [skill]Enemy Attention[-skill]. Also increases your "
    "[skill]Turret Throw Speed[-skill]. If your turret is destroyed by damage, "
    "part of your [skill]Action Skill Cooldown[-skill] is refunded."
)
MAG_LOCK_DEATH_REFUND = .35
_mag_lock_death_frames: list[Any] = []
_mag_lock_refund: Any = None
_mag_lock_claimed_cycle: Any = None
MAG_LOCK_THREAT_BONUS = 3.0
MAG_LOCK_THREAT_ATTRIBUTE = "GD_Attributes_AI.Threat.Attribute_Threat_Priority"
MAG_LOCK_PRIVATE_THREAT_ATTRIBUTE = MAG_LOCK + ":AR_ThreatPriority"
MAG_LOCK_RANGE_ATTRIBUTE = MAG_LOCK + ":AR_TurretWeaponRange"
MAG_LOCK_SIGHT_ATTRIBUTE = MAG_LOCK + ":AR_TurretSightRadius"
LONG_BOW = "GD_Soldier_Skills.Gunpowder.LongBowTurret"
LONG_BOW_HEALTH_RESOLVER = "GD_Soldier_Skills.Misc.Att_LongBowTurret_TurretHealth:ConstantAttributeValueResolver_0"
LONG_BOW_HEALTH_BONUS = .50
TURRET_HEALTH_CLASS = "GD_Scorpio.Character.CharClass_Scorpio"
TURRET_HEALTH_MULTIPLIER_ATTRIBUTE = "GD_Balance_HealthAndDamage.AIParameters.Attribute_HealthMultiplier"
TURRET_NATIVE_HEALTH_SCALE = 3.
TURRET_BASE_HEALTH_FACTOR = 1.40
_turret_health_checked_context: tuple[int, int] | None = None
_turret_health_checked_until = 0.
GEMINI = "GD_Soldier_Skills.Survival.Gemini"
GEMINI_FIRE = GEMINI + ":AR_TurretFire"
GEMINI_AURA = GEMINI + ":AR_DefensiveAura"
GEMINI_HUD = GEMINI + ":AR_AuraHUD"
GEMINI_DAMAGE_REDUCTION = .50
GEMINI_AURA_RADIUS = 2000.0  # Twenty gameplay metres, using 100 world units/metre.
_gemini_ready = False
_gemini_next_tick = 0.0
_gemini_hud_next_check = 0.0
_gemini_world = 0
_gemini_departing = 0
_gemini_turrets: dict[int, Any] = {}  # Weak pointers only.
_gemini_recipients: dict[int, Any] = {}
TURRET_THROW_ANIMATION = "GD_Soldier_Skills.Misc.SpecialMove_ThrowScorpio_Master"
TURRET_THROW_SPEED_FACTOR = 1.75
RANGER = "GD_Soldier_Skills.Gunpowder.Ranger"
RANGER_BUFF = RANGER + ":AR_PreparedReload"
RANGER_HUD = RANGER + ":AR_RangerHUD"
_ranger_hud_next_check = 0.
_ranger_hud_visible = False
RANGER_AMP_PER_RANK = .10
RANGER_FIRE_PER_RANK = .05
RANGER_AMP_MODIFIER = "AR_RangerShotAmp"
_ranger_definition_address = 0
_ranger_active_state = 0
_ranger_context: tuple[int, int, int, int, float] | None = None
_ranger_state: dict[str, Any] | None = None
_ranger_fire_frames: list[dict[str, Any] | None] = []
CRITICAL_DAMAGE_ATTRIBUTE = "D_Attributes.GameplayAttributes.PlayerCriticalHitBonus"
GRENADE_DAMAGE_ATTRIBUTE = "D_Attributes.DamageSourceModifiers.InstigatedGrenadeDamageModifier"
OVERLOAD = "GD_Soldier_Skills.Gunpowder.Overload"
OVERLOAD_MAGAZINE_PER_RANK = .10
OVERLOAD_RESERVE_REGEN_PER_RANK = .002
OVERLOAD_AMMO_TYPES = (
    "Combat_Rifle", "Combat_Shotgun", "Patrol_SMG", "Repeater_Pistol",
    "Rocket_Launcher", "Sniper_Rifle",
)
OVERLOAD_CLIP_ATTRIBUTE = "D_Attributes.Weapon.WeaponClipSize"
OVERLOAD_REGEN_DISPLAY_ATTRIBUTE = "D_Attributes.GameplayAttributes.PlayerCurrentWeaponAmmoRegenerationMultiplier"
ASSAULT_RIFLE_CONSTRAINT = "GD_PlayerShared.SkillConstraints.SkillConstraint_AssaultRifleOnly"
GRENADE_CAPACITY_ATTRIBUTE = "D_Attributes.Ammo_Grenade_Protean.Ammo_Grenade_ProteanMaxValue"
EXPLOSIVE_DAMAGE_ATTRIBUTE = "D_Attributes.DamageTypeModifers.InstigatedExplosiveDamageModifier"
ABLE = "GD_Soldier_Skills.Guerrilla.Able"
ABLE_ACTIVE = ABLE + "_Active"
ABLE_PROVIDER = ABLE + ":BehaviorProviderDefinition_0"
ABLE_MAX_STACKS = 5
ABLE_REGEN_PER_RANK = 0.004
WEAPON_SPREAD = "D_Attributes.Weapon.WeaponSpread"
WEAPON_FIRE_INTERVAL = "D_Attributes.Weapon.WeaponFireInterval"
TURRET_DAMAGE_TYPE_SELECTOR = "GD_Soldier_Skills.Misc.Att_TurretDamageTypeSelector"
TURRET_BONUS_AT_ONE = 0.30
TURRET_BONUS_AT_OP10 = 2.75
TURRET_OP10_STAGE = 90  # Level 80 + ten Overpower levels.

# Independent damage inputs. The turret's health, shield, fire rate and skills
# are deliberately outside this list. Each input keeps its existing initializer.
TURRET_DAMAGE_INPUTS = (
    (("WeaponTypeDefinition", "Object"),
     "GD_Weap_Scorpio.A_Weapon.WeaponType_Scorpio_Weapon", "InstantHitDamage"),
    (("Object",), "GD_Scorpio.Projectile.TurretNuke_ExplosiveDamage", "Damage"),
    (("Behavior_Explode",),
     "GD_Scorpio.AI.WillowAIDef_Scorpio:AIBehaviorProviderDefinition_1.Behavior_Explode_7", "DamageFormula"),
    (("Behavior_CauseDamage",),
     "GD_Scorpio.AI.WillowAIDef_Scorpio:AIBehaviorProviderDefinition_1.Behavior_CauseDamage_7", "StatusEffectDamage"),
    (("MeleeDefinition", "Object"), "GD_Scorpio.Projectile.TurretNuke_ExplosiveDamage", "StatusEffectDamage"),
    (("Behavior_CauseDamage",),
     "GD_Scorpio.AI.WillowAIDef_Scorpio:AIBehaviorProviderDefinition_1.Behavior_CauseDamage_7", "DamageFormula"),
)

# Only numbers and addresses are cached. Never retain world or pawn objects.
_damage_baselines: dict[tuple[str, str], tuple[int, float, float]] = {}
_next_check = 0.0
_last_reported_state: tuple[int, int] | None = None
_turret_runtime_ready = False  # Native tree initialization must finish before inspecting weapons/ranks.
_startup_fault_file: Any | None = None
_startup_fault_owned = False
_reported_errors: set[str] = set()
_able_behavior_addresses: tuple[int, int] | None = None
_overload_definition_address = 0
_overload_active_state = 0
_overload_authority_role = 0
_overload_reloading_state = 0
_next_overload_check = 0.0
_resourceful_definition_address = 0
_resourceful_active_state = 0
_last_ditch_definition_address = 0
_last_ditch_active_state = 0
_last_ditch_authority_role = 0
_last_ditch_enemy_opinion = 0
_last_ditch_context: tuple[int, int, int, int, float] | None = None
_last_ditch_departing: tuple[int, int] | None = None
# Static, rooted package objects only. Damage recipients/worlds are weak references.
_last_ditch_attributes: dict[str, Any] = {}
_last_ditch_modifiers: dict[tuple[int, str], Any] = {}
_last_ditch_scopes: list[dict[str, Any] | None] = []
_last_ditch_logged_ranks: set[int] = set()
_double_up_definition_address = 0
_double_up_active_state = 0
_double_up_friendly_opinion = 0
_double_up_context: tuple[int, int, int, float] | None = None
# Expiry, owner identity, victim-controller identity: no actor handles survive hits.
_double_up_marks: dict[tuple[int, int], tuple[float, tuple[int, int, int], int]] = {}

# Native Grade already includes equipment points. Cache identities, never ranks
# to add back into the tree, and never retain player/world/skill objects here.
CLASS_MOD_SKILLS = frozenset((
    READY, LASER_SIGHT, CRISIS_MANAGEMENT, ABLE, GRENADIER, BOOST, IMPACT, EXPERTISE,
    DUTY_CALLS, OVERLOAD, BATTLEFRONT, RANGER, RESOURCEFUL, PREPARATION,
    LAST_DITCH_EFFORT, METAL_STORM, STEADY, PHALANX, SCORCHED_EARTH, MAG_LOCK, LONG_BOW,
    NUKE, DOUBLE_UP, HEALTHY, FORBEARANCE, GEMINI, QUICK_CHARGE, PRESSURE, *KILL_MASTERY_SKILLS,
))
CLASS_MOD_PARENTS = {HEALTHY_TURRET_HELPER: HEALTHY, ABLE_ACTIVE: ABLE, PREPARATION_ACTIVE: PREPARATION, STEADY_LAUNCHER: STEADY, READY_MOVEMENT: READY, **dict.fromkeys(KILL_MASTERY_HELPERS, BOOST)}
_class_mod_owner: tuple[int, int, int] | None = None
_class_mod_refresh_at = 0.0
_class_mod_signatures: dict[int, tuple[Any, ...]] = {}


def _invalidate_class_mod_cache() -> None:
    global _class_mod_owner, _class_mod_refresh_at
    _class_mod_owner = None
    _class_mod_refresh_at = 0.0
    _class_mod_signatures.clear()


def _effect_layout(effect: Any) -> tuple[Any, ...]:
    return tuple(getattr(effect, field, None) for field in (
        "AttributeToModify", "EffectTarget", "ModifierType", "TargetInstanceDataName",
        "TargetCriteria",
    ))


def _refresh_class_mod_effects(controller: Any, manager: Any, skills: tuple[Any, ...],
                               context: tuple[int, int, int], now: float) -> bool:
    """Refresh equipment-dependent caches; False invalidates the caller's snapshot."""
    global _class_mod_owner, _class_mod_refresh_at
    if _class_mod_owner != context:
        _invalidate_class_mod_cache()
        _class_mod_owner = context
    if now < _class_mod_refresh_at or getattr(manager, "bUpdatingSkills", False):
        return True
    _class_mod_refresh_at = now + 1.0
    inventory = getattr(controller.Pawn, "InvManager", None)
    equipped = inventory.GetCurrentClassMod() if inventory is not None else None
    equipment_id = int(equipped._get_address()) if equipped is not None else 0
    eligible = []
    grades: dict[str, int] = {}
    for skill in skills:
        if (skill.Definition is None or skill.SkillInstigator != controller
                or not hasattr(skill, "SkillEffects")):
            continue
        path = _skill_path(skill.Definition)
        if path not in CLASS_MOD_SKILLS and path not in CLASS_MOD_PARENTS:
            continue
        grades[path] = max(grades.get(path, 0), int(skill.Grade))
        eligible.append((skill, path))
    seen: set[int] = set()
    for skill, path in eligible:
        address = int(skill._get_address())
        seen.add(address)
        signature = (equipment_id, int(skill.Definition._get_address()), int(skill.Grade),
                     int(skill.SkillState), grades.get(CLASS_MOD_PARENTS.get(path, ""), 0))
        if int(skill.Grade) <= 0:
            _class_mod_signatures.pop(address, None)
            continue
        if _class_mod_signatures.get(address) == signature:
            continue
        none_target = unrealsdk.find_enum("EEffectTarget").TARGET_None
        expected = [data for data in skill.Definition.SkillEffectDefinitions
                    if data.AttributeToModify is not None and data.EffectTarget != none_target]
        current = list(skill.SkillEffects)
        gameplay = [(index, item) for index, item in enumerate(current)
                    if item.EffectData.AttributeToModify is not None
                    and item.EffectData.EffectTarget != none_target]
        # A turret source may not exist yet. Native deployment will create its
        # contexts; do not repeatedly rebuild an empty source-dependent effect.
        source_pending = (not gameplay and bool(getattr(
            skill.Definition, "EffectSourceInstanceDataName", "")))
        if not source_pending and tuple(_effect_layout(item.EffectData) for _, item in gameplay) != tuple(
                _effect_layout(data) for data in expected):
            modes = unrealsdk.find_enum("EAdjustModifierMode")
            active = skill.SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active
            reference = WeakPointer(skill)
            previous = [copy.copy(item) for item in current]
            if active:
                skill.AdjustModifiers(modes.WILLOW_ADJUST_RemoveModifer, True)
            live = reference()
            if live is None:
                return False
            try:
                live.SkillEffects = []
                live.BuildSkillEffects()
            except (AttributeError, TypeError, ValueError, RuntimeError):
                live = reference()
                if live is not None:
                    live.SkillEffects = previous
                raise
            finally:
                live = reference()
                if live is not None and active:
                    live.AdjustModifiers(modes.WILLOW_ADJUST_InitialAddModifer, False)
            live = reference()
            if live is not None:
                live.bForceRefreshModifiersNextTick = True
                _class_mod_signatures[address] = signature
            _class_mod_refresh_at = 0.0
            return False  # Native callbacks can mutate ActiveSkills.
        if gameplay:
            migrated = [copy.copy(item) for item in current]
            for (index, _item), data in zip(gameplay, expected):
                migrated[index].EffectData = copy.copy(data)
            skill.SkillEffects = migrated
        skill.bForceRefreshModifiersNextTick = True
        _class_mod_signatures[address] = signature
    for address in set(_class_mod_signatures) - seen:
        del _class_mod_signatures[address]
    return True


def _skill_path(skill: Any) -> str:
    return str(skill._path_name())


def _configure_turret_cooldown() -> bool:
    """Change the native base; keep pool consumption and cooldown-rate modifiers intact."""
    attribute = unrealsdk.find_object("DesignerAttributeDefinition", TURRET_COOLDOWN_ATTRIBUTE)
    original = attribute.BaseValue
    if original.BaseValueAttribute is not None or original.InitializationDefinition is not None:
        raise ValueError("Unexpected Sabre Turret base cooldown formula")
    if (math.isclose(float(original.BaseValueConstant), TURRET_BASE_COOLDOWN, abs_tol=1e-7)
            and float(original.BaseValueScaleConstant) == 1.):
        return False
    value = copy.copy(original)
    value.BaseValueConstant, value.BaseValueScaleConstant = TURRET_BASE_COOLDOWN, 1.
    attribute.BaseValue = value
    return True


def _configure_skill_positions() -> bool:
    """Apply the three-skill rotation and capstone swap before the live tree copies them."""
    guerrilla = unrealsdk.find_object("Object", GUERRILLA_BRANCH)
    survival = unrealsdk.find_object("Object", SURVIVAL_BRANCH)
    gunpowder = unrealsdk.find_object("Object", GUNPOWDER_BRANCH)
    branches = (guerrilla, survival, gunpowder)
    rows = [[list(tier.Skills) for tier in branch.Tiers] for branch in branches]
    if len(rows[0]) <= 4 or len(rows[1]) <= 3 or len(rows[1]) <= 1:
        raise ValueError("Axton skill tree has fewer tiers than expected")
    if not rows[0][4] or not rows[1][3]:
        raise ValueError("Axton skill tree is missing an occupied swap cell")

    # Last Ditch Effort is in Survival's second tier. After our swap, Crisis
    # Management occupies that same cell; resolve the exact column at runtime.
    last_slot = [index for index, skill in enumerate(rows[1][1])
                 if _skill_path(skill) in (LAST_DITCH_EFFORT, CRISIS_MANAGEMENT)]
    if len(last_slot) != 1:
        raise ValueError("Could not identify the original Last Ditch Effort cell")
    positions = ((0, 4, 0), (1, 3, 0), (1, 1, last_slot[0]))
    original = (CRISIS_MANAGEMENT, RESOURCEFUL, LAST_DITCH_EFFORT)
    expected = (RESOURCEFUL, LAST_DITCH_EFFORT, CRISIS_MANAGEMENT)
    current = tuple(_skill_path(rows[branch][tier][cell]) for branch, tier, cell in positions)
    if current not in (original, expected):
        raise ValueError(f"Axton skill slots differ from the original tree: {current}")
    if any(len(rows[index]) <= 5 or len(rows[index][5]) != 1 for index in (0, 2)):
        raise ValueError("Axton capstone cells are missing or unexpected")
    cap_positions = ((0, 5, 0), (2, 5, 0))
    caps = tuple(_skill_path(rows[branch][tier][cell]) for branch, tier, cell in cap_positions)
    cap_expected = (NUKE, DOUBLE_UP)
    if caps not in ((DOUBLE_UP, NUKE), cap_expected):
        raise ValueError(f"Unexpected Axton capstones: {caps}")
    positions += cap_positions
    current += caps
    expected += cap_expected
    for path in expected:
        occurrences = sum(_skill_path(skill) == path for branch in rows
                          for tier in branch for skill in tier)
        if occurrences != 1:
            raise ValueError(f"Axton skill definition has {occurrences} tree slots: {path}")
    if current == expected:
        return False

    definitions = {path: rows[branch][tier][cell]
                   for path, (branch, tier, cell) in zip(current, positions)}
    changed_positions = [position for position, before, after in zip(positions, current, expected)
                         if before != after]
    for (branch_index, tier_index, cell_index), path in zip(positions, expected):
        rows[branch_index][tier_index][cell_index] = definitions[path]
    for branch_index, branch in enumerate(branches):
        changed_tiers = {tier_index for index, tier_index, _cell in changed_positions
                         if index == branch_index}
        if not changed_tiers:
            continue
        tiers = list(branch.Tiers)
        for tier_index in changed_tiers:
            tier = copy.copy(tiers[tier_index])
            tier.Skills = rows[branch_index][tier_index]
            tiers[tier_index] = tier
        branch.Tiers = tiers
    if tuple(_skill_path(branches[branch].Tiers[tier].Skills[cell])
             for branch, tier, cell in positions) != expected:
        raise ValueError("Axton skill positions did not retain the requested order")
    return True



def _configure_boost() -> bool:
    global _boost_configuring
    if _boost_configuring:
        return False
    _boost_configuring = True
    try:
        return _configure_boost_definition()
    finally:
        _boost_configuring = False


def _boost_tree_snapshot() -> tuple[Any, ...]:
    branch = unrealsdk.find_object("SkillTreeBranchDefinition", GUERRILLA_BRANCH)
    layout = unrealsdk.find_object("SkillTreeBranchLayoutDefinition", BOOST_LAYOUT)
    tiers, cells = list(branch.Tiers), list(layout.Tiers)
    if len(tiers) != 6 or len(cells) != 6:
        raise ValueError("Kill Mastery requires Guerrilla's six-tier layout")
    rows = [tuple(_skill_path(skill) for skill in tier.Skills) for tier in tiers]
    expected = (GRENADIER, BOOST)
    occupied = tuple(bool(value) for value in cells[3].bCellIsOccupied)
    if rows[3] not in ((GRENADIER,), expected) or occupied not in ((False, True, False),(False,True,True)):
        raise ValueError("Kill Mastery's cell to the right of Grenadier is occupied by another layout")
    if any(BOOST in row for index,row in enumerate(rows) if index != 3):
        raise ValueError("Kill Mastery is already assigned to another tier")
    return branch,layout,tiers,cells,rows,occupied


def _configure_kill_mastery_bonuses() -> bool:
    """Add a separate fraction of each current kill-skill effect; never rewrite its source."""
    global _kill_mastery_targets, _kill_mastery_active_state
    if not _boost_definition_address:
        return False
    owner = unrealsdk.find_object("SkillDefinition", BOOST)
    targets, changed = {}, False
    self_target = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    kill_type = unrealsdk.find_enum("ESkillType").SKILL_TYPE_Kill
    for path, helper_path in zip(KILL_MASTERY_SKILLS, KILL_MASTERY_HELPERS):
        source = unrealsdk.find_object("SkillDefinition", path)
        if source is None or source.SkillType != kill_type:
            raise ValueError("Kill Mastery requires a native kill skill: " + path)
        effects = []
        for original in source.SkillEffectDefinitions:
            if original.AttributeToModify is None or original.EffectTarget != self_target:
                continue  # Never amplify tooltip-only effects or foreign target contexts.
            if (original.GradeToStartApplyingEffect != 1 or original.PerGradeUpgradeInterval != 1
                    or list(original.BonusUpgradeList)):
                raise ValueError("Kill Mastery requires linear rank effects: " + path)
            effect = copy.copy(original)
            for field in ("BaseModifierValue", "PerGradeUpgrade"):
                value = copy.copy(getattr(original, field))
                value.BaseValueScaleConstant = float(value.BaseValueScaleConstant) * BOOST_STRENGTH_PER_RANK
                setattr(effect, field, value)
            effects.append(effect)
        if not effects:
            raise ValueError("Kill Mastery found no applicable bonuses: " + path)
        try:
            helper = unrealsdk.find_object("SkillDefinition", helper_path)
        except ValueError:
            helper = None
        created = helper is None
        if created:
            helper = unrealsdk.construct_object("SkillDefinition", owner, helper_path.rsplit(":", 1)[1],
                template_obj=source, flags=int(ObjectFlags.KEEP_ALIVE))
        if helper is None:
            raise ValueError("Could not create Kill Mastery bonus helper: " + path)
        old = list(helper.SkillEffectDefinitions)
        def matches(before: Any, after: Any) -> bool:
            return (_effect_layout(before) == _effect_layout(after)
                and before.GradeToStartApplyingEffect == after.GradeToStartApplyingEffect
                and before.PerGradeUpgradeInterval == after.PerGradeUpgradeInterval
                and list(before.BonusUpgradeList) == list(after.BonusUpgradeList)
                and all(getattr(before, field).BaseValueAttribute == getattr(after, field).BaseValueAttribute
                    and getattr(before, field).InitializationDefinition == getattr(after, field).InitializationDefinition
                    and math.isclose(float(getattr(before, field).BaseValueConstant),
                                     float(getattr(after, field).BaseValueConstant), abs_tol=1e-8)
                    and math.isclose(float(getattr(before, field).BaseValueScaleConstant),
                                     float(getattr(after, field).BaseValueScaleConstant), rel_tol=1e-6, abs_tol=1e-8)
                    for field in ("BaseModifierValue", "PerGradeUpgrade")))
        if created or len(old) != len(effects) or any(not matches(a, b) for a, b in zip(old, effects)):
            helper.SkillEffectDefinitions = effects
            changed = True
        def obtain(kind: str, outer: Any, name: str) -> Any:
            parent = _skill_path(outer)
            child = parent + ("." if ":" in parent else ":") + name
            try:
                obj = unrealsdk.find_object(kind, child)
            except ValueError:
                obj = None
            if obj is None:
                obj = unrealsdk.construct_object(kind, outer, name, flags=int(ObjectFlags.KEEP_ALIVE))
            if obj is None:
                raise ValueError("Could not create Kill Mastery's active-state gate: " + child)
            return obj
        state_attribute = obtain("AttributeDefinition", helper, "SourceState")
        context = obtain("SkillAttributeContextResolver", state_attribute, "SourceSkill")
        resolver = obtain("ObjectPropertyAttributeValueResolver", state_attribute, "StateValue")
        context.AssociatedSkill, resolver.PropertyName = source, "SkillState"
        state_attribute.bIsSimpleAttribute = True
        state_attribute.AttributeDataType = unrealsdk.find_enum("EAttributeDataType").ADT_Int
        state_attribute.ContextResolverChain, state_attribute.ValueResolverChain = [context], [resolver]
        evaluator = obtain("AttributeExpressionEvaluator", helper, "SourceActive")
        evaluator.Expression = unrealsdk.make_struct("Engine.AttributeExpression.AttributeExpressionData",
            AttributeOperand1=state_attribute,
            ComparisonOperator=unrealsdk.find_enum("EComparisonOperator").OPERATOR_EqualTo,
            Operand2Usage=unrealsdk.find_enum("EOperandUsage").OPERAND_PreferAttribute,
            AttributeOperand2=None, ConstantOperand2=float(unrealsdk.find_enum("ESkillState").SKILL_Active))
        constraints = [copy.copy(item) for item in source.SkillConstraints]
        if not constraints:
            raise ValueError("Kill Mastery's source constraint template is unavailable: " + path)
        gate = copy.copy(constraints[0])
        gate.Evaluator, gate.EvaluatorDefinitions = evaluator, []
        gate.OnFailure = unrealsdk.find_enum("ESkillState").SKILL_Paused
        gate.bApplyConstraintOnActivatation = gate.bApplyConstraintWhileActive = gate.bApplyConstraintWhilePaused = True
        helper.SkillConstraints = [*constraints, gate]
        # Passive/untracked avoids duplicate native kill-skill icons. The source's
        # reflected SkillState gates effects immediately, independently of Python maintenance.
        helper.SkillType = unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive
        helper.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite
        helper.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked
        helper.bSubjectToGradeRules, helper.bAutoUpdateContexts = False, True
        helper.SkillEffectPresentations, helper.DamageEvents, helper.KillEvents = [], [], []
        helper.TrackedActiveSkills = []
        helper.TrackedActiveSkill = helper.BehaviorProviderDefinition = helper.CustomStackCount = None
        helper.SkillIcon = None
        helper.SkillName = "Kill Mastery bonus: " + str(source.SkillName)
        targets[path] = (int(source._get_address()), int(helper._get_address()))
    _kill_mastery_targets = targets
    _kill_mastery_active_state = int(unrealsdk.find_enum("ESkillState").SKILL_Active)
    return changed


def _sync_kill_mastery(controller: Any, manager: Any, skills: tuple[Any, ...]) -> bool:
    """Use the shared snapshot; only allocation, active state or grade changes cause native writes."""
    if not _kill_mastery_targets:
        return True
    source_ids = {item[0] for item in _kill_mastery_targets.values()}
    helper_ids = {item[1] for item in _kill_mastery_targets.values()}
    rank, source_ranks, instances = 0, {}, {}
    for skill in skills:
        definition = skill.Definition
        if definition is None or skill.SkillInstigator != controller:
            continue
        address = int(definition._get_address())
        if address == _boost_definition_address and int(skill.SkillState) == _kill_mastery_active_state:
            rank = max(rank, int(skill.Grade))
        elif address in source_ids and int(skill.SkillState) == _kill_mastery_active_state:
            source_ranks[address] = max(source_ranks.get(address, 0), int(skill.Grade))
        elif address in helper_ids:
            instances.setdefault(address, []).append(skill)
    for path, helper_path in zip(KILL_MASTERY_SKILLS, KILL_MASTERY_HELPERS):
        if path not in _kill_mastery_targets:
            continue
        source_id, helper_id = _kill_mastery_targets[path]
        grade = max(0, rank) * max(0, source_ranks.get(source_id, 0))
        current = instances.get(helper_id, [])
        if current and (not grade or len(current) > 1):
            manager.DeactivateSkill(controller, current[0].Definition)
            return False  # Callback may invalidate every Skill in the input snapshot.
        if not grade:
            continue
        if not current:
            helper = unrealsdk.find_object("SkillDefinition", helper_path)
            if manager.ActivateSkill(controller, helper, None, grade) is False:
                raise ValueError("Kill Mastery bonus activation rejected: " + path)
            if path not in _kill_mastery_logged:
                _kill_mastery_logged.add(path)
                unrealsdk.logging.info(
                    f"[AxtonRebalance] Kill Mastery helper activated: source={path}, mastery_rank={rank}, "
                    f"source_rank={source_ranks[source_id]}, helper_grade={grade}")
            return False
        if int(current[0].Grade) != grade:
            current[0].UpdateGrade(grade)
            return False
    return True


def _configure_boost_definition() -> bool:
    """Insert Kill Mastery at its stable saved definition path."""
    global _boost_definition_address
    branch,layout,tiers,cells,rows,occupied = _boost_tree_snapshot()
    expected = (GRENADIER, BOOST)
    try:
        icon = unrealsdk.find_object("SwfMovie", BOOST_ICON)
    except ValueError:
        icon = None
    if icon is None:
        # Load only during tree construction, never from periodic/combat maintenance.
        unrealsdk.load_package("GD_Tulip_Mechro_Streaming_SF")
        icon = unrealsdk.find_object("SwfMovie", BOOST_ICON)
        # Loading can dispatch native callbacks; discard all pre-load array views.
        branch,layout,tiers,cells,rows,occupied = _boost_tree_snapshot()
    if icon is None:
        raise ValueError("Unstoppable Force's menu icon is not loaded: " + BOOST_ICON)
    icon.ObjectFlags = int(icon.ObjectFlags) | int(ObjectFlags.KEEP_ALIVE)
    template = tiers[3].Skills[0]
    try:
        definition = unrealsdk.find_object("SkillDefinition", BOOST)
    except ValueError:
        definition = None
    created = definition is None
    if created:
        definition = unrealsdk.construct_object("SkillDefinition", template.Outer, "AR_Boost",
            template_obj=template, flags=int(ObjectFlags.KEEP_ALIVE))
    if definition is None or _skill_path(definition) != BOOST:
        raise ValueError("Kill Mastery's private definition could not be created at its stable path")

    def obtain(kind: str, outer: Any, name: str, source: Any = None) -> Any:
        parent = _skill_path(outer)
        path = parent + ("." if ":" in parent else ":") + name
        try:
            obj = unrealsdk.find_object(kind,path)
        except ValueError:
            obj = None
        if obj is None:
            obj = unrealsdk.construct_object(kind,outer,name,template_obj=source,
                                             flags=int(ObjectFlags.KEEP_ALIVE))
        if obj is None:
            raise ValueError("Could not create Kill Mastery's private asset: " + path)
        return obj

    # Native class mods add to this controller property with MT_PostAdd; its default is zero.
    attribute = obtain("AttributeDefinition",definition,"KillDuration")
    context = obtain("PlayerControllerAttributeContextResolver",attribute,"OwnerContext")
    resolver = obtain("ObjectPropertyAttributeValueResolver",attribute,"DurationValue")
    resolver.PropertyName = "KillSkillDurationMultiplier"
    attribute.bIsSimpleAttribute = False
    attribute.AttributeDataType = unrealsdk.find_enum("EAttributeDataType").ADT_Float
    attribute.ContextResolverChain, attribute.ValueResolverChain = [context], [resolver]
    data = copy.copy(template.SkillEffectDefinitions[0])
    data.AttributeToModify = attribute
    data.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    data.ModifierType = unrealsdk.find_enum("EModifierType").MT_PostAdd
    data.bIncludeSelfAsTarget = False
    data.GradeToStartApplyingEffect, data.PerGradeUpgradeInterval, data.BonusUpgradeList = 1,1,[]
    for field in ("BaseModifierValue","PerGradeUpgrade"):
        value = copy.copy(getattr(data,field))
        value.BaseValueConstant, value.BaseValueScaleConstant = BOOST_DURATION_PER_RANK,1.
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(data,field,value)
    strength_attribute = obtain("AttributeDefinition",definition,"EffectStrength")
    strength_attribute.bIsSimpleAttribute = False
    strength_attribute.AttributeDataType = attribute.AttributeDataType
    strength_attribute.ContextResolverChain, strength_attribute.ValueResolverChain = [context], [resolver]
    strength = copy.copy(data)
    strength.AttributeToModify = strength_attribute
    strength.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_None  # Tooltip only.
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(data, field))
        value.BaseValueConstant = BOOST_STRENGTH_PER_RANK
        setattr(strength, field, value)
    desired = [data, strength]
    old = list(definition.SkillEffectDefinitions)
    def same_effect(before: Any, after: Any) -> bool:
        return (_effect_layout(before) == _effect_layout(after)
            and before.GradeToStartApplyingEffect == after.GradeToStartApplyingEffect
            and before.PerGradeUpgradeInterval == after.PerGradeUpgradeInterval
            and list(before.BonusUpgradeList) == list(after.BonusUpgradeList)
            and all(math.isclose(float(getattr(before, field).BaseValueConstant),
                                 float(getattr(after, field).BaseValueConstant), rel_tol=0., abs_tol=1e-7)
                and float(getattr(before, field).BaseValueScaleConstant) == 1.
                and getattr(before, field).BaseValueAttribute is None
                and getattr(before, field).InitializationDefinition is None
                for field in ("BaseModifierValue", "PerGradeUpgrade")))
    changed = created or len(old) != len(desired) or any(
        not same_effect(before, after) for before, after in zip(old, desired))
    if changed:
        definition.SkillEffectDefinitions = desired
    stats = []
    for name, attr, text in (("DurationStat", attribute, "Kill Skill Duration: $NUMBER$"),
                             ("StrengthStat", strength_attribute, "Kill Skill Bonus Strength: $NUMBER$")):
        stat = obtain("AttributePresentationDefinition",definition,name,template.SkillEffectPresentations[0])
        stat.Attribute, stat.Description = attr, text
        stat.bDisplayAsPercentage, stat.bDisplayAsInverse = True,False
        stat.bDisplayPercentAsFloat, stat.FloatPrecision = True,0
        stat.RoundingMode = unrealsdk.find_enum("EAttributeInitializationRounding").ATTRROUNDING_Float
        stat.bUseCustomNumberPlacement, stat.bDontDisplayPlusSign = True,False
        stats.append(stat)
    definition.SkillEffectPresentations = stats
    definition.SkillName = "Kill Mastery"
    definition.SkillDescription = (
        "Increases the [skill]duration[-skill] and [skill]bonuses[-skill] of your [skill]Kill Skills[-skill].")
    definition.MaxGrade, definition.DefaultStartingGrade = 5,0
    definition.bSubjectToGradeRules, definition.bAutoUpdateContexts = True,True
    definition.SkillType = unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive
    definition.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite
    definition.InitialDuration = 0.
    definition.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked
    definition.SkillIcon = icon
    definition.BehaviorProviderDefinition = definition.TrackedActiveSkill = None
    definition.ActionSkillArchetype = definition.CustomStackCount = None
    definition.EffectSourceInstanceDataName = ""
    for field in ("SkillConstraints","DamageEvents","KillEvents","TrackedActiveSkills"):
        setattr(definition,field,[])
    if rows[3] != expected:
        # Detach every WrappedStruct before replacing its owning native array.
        detached = [copy.copy(tier) for tier in tiers]
        detached[3].Skills = [template,definition]
        branch.Tiers = detached
        changed = True
    if occupied != (False,True,True):
        detached_cells = [copy.copy(cell) for cell in cells]
        detached_cells[3].bCellIsOccupied = [False,True,True]
        layout.Tiers = detached_cells
        changed = True
    if (tuple(_skill_path(skill) for skill in branch.Tiers[3].Skills) != expected
            or tuple(bool(cell) for cell in layout.Tiers[3].bCellIsOccupied) != (False,True,True)):
        raise ValueError("Kill Mastery's tree insertion did not retain its values")
    _boost_definition_address = int(definition._get_address())
    return changed


def _effect_attribute_path(effect: Any) -> str | None:
    attribute = effect.AttributeToModify
    return _skill_path(attribute) if attribute is not None else None


def _native_turret_penalty(effect: Any) -> bool:
    """Match the hidden 15% damage effect without depending on its array index."""
    path = _effect_attribute_path(effect)
    if path is None or "damage" not in path.casefold():
        return False
    for value in (effect.BaseModifierValue, effect.PerGradeUpgrade):
        for field in ("BaseValueConstant", "BaseValueScaleConstant"):
            if math.isclose(abs(float(getattr(value, field))), 0.15,
                            rel_tol=1e-5, abs_tol=1e-5):
                return True
    return False


def _remove_turret_damage_penalties() -> tuple[str, ...]:
    """Keep each augment's native functionality and discard only its penalty."""
    specifications = (
        (SCORCHED_EARTH, (None,)),
    )
    pending: list[tuple[Any, list[Any], str]] = []
    removed: list[str] = []
    for path, core_attributes in specifications:
        definition = unrealsdk.find_object("SkillDefinition", path)
        effects = list(definition.SkillEffectDefinitions)
        def core_path(effect: Any) -> str | None:
            attribute_path = _effect_attribute_path(effect)
            # Native rocket/augment stat uses a reload attribute with TARGET_None.
            if (attribute_path == RELOAD_ATTRIBUTE
                    and effect.EffectTarget == unrealsdk.find_enum("EEffectTarget").TARGET_None):
                return None
            return attribute_path
        core = [effect for effect in effects
                if core_path(effect) in core_attributes]
        passive_attribute = EXPLOSIVE_DAMAGE_ATTRIBUTE
        passive = [effect for effect in effects if _effect_attribute_path(effect) == passive_attribute]
        if len(passive) > 1:
            raise ValueError(f"Duplicate turret augment passive effects: {path}")
        extras = [effect for effect in effects
                  if core_path(effect) not in core_attributes and effect not in passive]
        core_paths = tuple(core_path(effect) for effect in core)
        if len(core_paths) != len(core_attributes) or set(core_paths) != set(core_attributes):
            raise ValueError(f"Unexpected native turret augment effects: {path}")
        if not extras:
            continue  # Already stripped in this process.
        if len(extras) != 1 or not _native_turret_penalty(extras[0]):
            details = tuple(_effect_attribute_path(effect) for effect in extras)
            raise ValueError(f"Turret damage penalty could not be identified: {path}, extras={details}")
        pending.append((definition, [copy.copy(effect) for effect in effects if effect in core or effect in passive], path))
    for definition, retained, path in pending:
        definition.SkillEffectDefinitions = retained
        removed.append(path)
    return tuple(removed)


def _configure_ready() -> bool:
    global _ready_definition_address, _ready_movement_address, _ready_active_state
    definition = unrealsdk.find_object("SkillDefinition", READY)
    if definition is None:
        raise ValueError("Ready definition is unavailable")
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(item) for item in effects]
    desired_paths = [RELOAD_ATTRIBUTE, WEAPON_FIRE_INTERVAL]
    if paths not in ([RELOAD_ATTRIBUTE], [MOVEMENT_ATTRIBUTE, RESOURCEFUL_COOLDOWN_ATTRIBUTE],
                     [RELOAD_ATTRIBUTE, MOVEMENT_ATTRIBUTE], desired_paths):
        raise ValueError(f"Unexpected Ready effects: {paths}")
    fire_rate = unrealsdk.find_object("AttributeDefinition", WEAPON_FIRE_INTERVAL)
    reload = unrealsdk.find_object("AttributeDefinition", RELOAD_ATTRIBUTE)
    presentation = unrealsdk.find_object("AttributePresentationDefinition",
        CRISIS_MANAGEMENT + ":AttributePresentationDefinition_53")
    if fire_rate is None or reload is None or presentation is None:
        raise ValueError("Ready attributes/presentation are unavailable")
    mode = unrealsdk.find_enum("EModifierType").MT_Scale
    targets = unrealsdk.find_enum("EEffectTarget")
    desired = []
    for attribute, amount, target in ((reload, READY_RELOAD_PER_RANK, targets.TARGET_Self),
            (fire_rate, -READY_FIRE_PER_RANK, targets.TARGET_None)):
        effect = copy.copy(effects[0])
        effect.AttributeToModify, effect.ModifierType, effect.EffectTarget = attribute, mode, target
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(effects[0], field))
            value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(effect, field, value)
        desired.append(effect)
    changed = paths != desired_paths
    if not changed:
        changed = any(old.ModifierType != new.ModifierType or old.EffectTarget != new.EffectTarget
            or any(not math.isclose(float(getattr(old, field).BaseValueConstant), float(getattr(new, field).BaseValueConstant), abs_tol=1e-7)
                   or float(getattr(old, field).BaseValueScaleConstant) != 1.
                   or getattr(old, field).BaseValueAttribute is not None
                   or getattr(old, field).InitializationDefinition is not None
                   for field in ("BaseModifierValue", "PerGradeUpgrade"))
            for old, new in zip(effects, desired))
    try:
        helper = unrealsdk.find_object("SkillDefinition", READY_MOVEMENT)
    except ValueError:
        helper = None
    created = helper is None
    if helper is None:
        helper = unrealsdk.construct_object("SkillDefinition", definition, "AR_ReloadMovement",
            template_obj=definition, flags=int(ObjectFlags.KEEP_ALIVE))
    if helper is None:
        raise ValueError("Ready reload fire rate helper could not be created")
    effect = copy.copy(desired[1])
    effect.EffectTarget = targets.TARGET_Self
    effect.GradeToStartApplyingEffect, effect.PerGradeUpgradeInterval, effect.BonusUpgradeList = 1, 1, []
    helper.SkillEffectDefinitions = [effect]
    helper.SkillConstraints = [copy.copy(item) for item in definition.SkillConstraints]
    helper.SkillEffectPresentations = []
    helper.TrackedActiveSkills = []
    helper.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked
    helper.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Timed
    helper.InitialDuration = READY_BUFF_SECONDS
    helper.TrackedActiveSkill = None
    helper.DamageEvents = []
    helper.KillEvents = []
    helper.EventResponses = []
    helper.CustomEvents = []
    helper.EffectSourceInstanceDataName = ""
    helper.bAutoUpdateContexts = True
    helper.bSubjectToGradeRules = False
    helper.BehaviorProviderDefinition = None
    try:
        feedback = unrealsdk.find_object("SkillDefinition", READY_HUD)
    except ValueError:
        feedback = None
    if feedback is None:
        feedback = unrealsdk.construct_object("SkillDefinition", definition, "AR_ReloadMovementHUD",
            template_obj=definition, flags=int(ObjectFlags.KEEP_ALIVE))
        changed = True
    if feedback is None:
        raise ValueError("Ready HUD feedback could not be created")
    feedback.SkillEffectDefinitions = []
    feedback.SkillEffectPresentations = []
    feedback.SkillConstraints = []
    feedback.BehaviorProviderDefinition = None
    feedback.DamageEvents = []
    feedback.KillEvents = []
    feedback.EventResponses = []
    feedback.CustomEvents = []
    feedback.TrackedActiveSkills = []
    feedback.TrackedActiveSkill = None
    feedback.CustomStackCount = None
    feedback.EffectSourceInstanceDataName = ""
    feedback.SkillIcon = definition.SkillIcon
    feedback.SkillName = "Ready fire rate bonus"
    feedback.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered
    feedback.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite
    feedback.bSubjectToGradeRules = False
    feedback.MaxGrade = 1
    _ready_active_state = int(unrealsdk.find_enum("ESkillState").SKILL_Active)
    _ready_definition_address = int(definition._get_address())
    _ready_movement_address = int(helper._get_address())
    changed |= created
    if changed:
        definition.SkillEffectDefinitions = desired
    stats = []
    for name, attribute, description, inverse in (
            ("AR_ReloadSpeed", reload, "Reload Speed: $NUMBER$", True),
            ("AR_MovementSpeed", fire_rate, f"Fire Rate after Reload: $NUMBER$<br>Duration: {READY_BUFF_SECONDS:g} seconds", True)):
        try:
            stat = unrealsdk.find_object("AttributePresentationDefinition", READY + ":" + name)
        except ValueError:
            stat = None
        if stat is None:
            stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                template_obj=presentation, flags=int(ObjectFlags.KEEP_ALIVE))
        if stat is None:
            raise ValueError("Could not construct Ready presentation")
        settings: dict[str, Any] = dict(Attribute=attribute, Description=description, bDisplayAsPercentage=True,
            bDisplayAsInverse=inverse, bDontDisplayPlusSign=False, bUseCustomNumberPlacement=True)
        for field, value in settings.items():
            if getattr(stat, field) != value:
                setattr(stat, field, value)
        stats.append(stat)
    if list(definition.SkillEffectPresentations) != stats:
        definition.SkillEffectPresentations = stats
    description = ("Increases your [skill]Reload Speed[-skill]. Completing a reload temporarily increases "
                   "your [skill]Fire Rate[-skill]. Reloading again refreshes the duration without stacking.")
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    return changed




def _clear_ready_reload_frames() -> None:
    for index in range(len(_ready_reload_frames)):
        _ready_reload_frames[index] = None


@hook("WillowGame.WillowWeapon:ReloadDone", Type.PRE)
def prepare_ready_reload(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _ready_reload_frames.append(None)
    if not _turret_runtime_ready or not (_ready_definition_address or _ranger_definition_address):
        return
    try:
        if (weapon is None or weapon.bDeleteMe or not weapon.bAmmoRefilledDuringReload
                or int(weapon.ReloadCnt) <= int(weapon.AmmoLeftInClipDuringReload)):
            return  # No completed ammo transfer: cancellations/empty-reserve attempts do not proc.
        controller = get_pc(possibly_loading=True)
        if controller is None or controller.bDeleteMe:
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.Controller != controller or pawn.IsInjuredDead() or weapon.Instigator != pawn
                or weapon.WorldInfo != world or pawn.Weapon != weapon
                or controller.PlayerClass is None or _skill_path(controller.PlayerClass) != AXTON_CLASS):
            return
        identity = (int(controller._get_address()), int(world._get_address()), int(pawn._get_address()))
        if _last_ditch_departing in (identity[:2], (identity[0], 0)):
            return
        _ready_reload_frames[-1] = (int(weapon._get_address()), identity, int(weapon.AmmoLeftInClipDuringReload) == 0)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not observe Ready reload completion", exc)


@hook("WillowGame.WillowWeapon:ReloadDone", Type.POST_UNCONDITIONAL)
def grant_ready_reload_movement(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if not _ready_reload_frames:
        return
    frame = _ready_reload_frames.pop()
    if frame is None:
        return
    state = _ranger_state
    if (not frame[2] and state is not None and state["active"]
            and state["identity"] == frame[1] and state["weapon"] is not None
            and state["weapon"]() == weapon):
        # A native/state reload path may bypass StartReload. A partial completion
        # must still retire the previous magazine before any reload buffs run.
        _stop_ranger_buff(clear_context=False)
    _grant_ready_reload_movement(weapon, frame)
    if _ranger_context is None or not frame[2]:
        return
    try:
        controller = _ranger_player()  # Re-resolve after Ready's native activation callbacks.
        cached = _ranger_context
        if (controller is not None and cached is not None and weapon is not None and not weapon.bDeleteMe
                and controller.Pawn.Weapon == weapon and weapon.Instigator == controller.Pawn
                and weapon.WorldInfo == controller.WorldInfo
                and int(weapon._get_address()) == frame[0] and frame[1] == cached[:3]):
            manager = controller.GetSkillManager()
            if manager is not None and not getattr(manager, "bUpdatingSkills", False):
                _activate_ranger_reload(controller, manager, frame[1], weapon, empty_reload=frame[2])
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not activate Ranger magazine bonus", exc)


def _grant_ready_reload_movement(weapon: Any, frame: Any) -> None:
    try:
        controller = get_pc(possibly_loading=True)
        if (controller is None or controller.bDeleteMe or weapon is None or weapon.bDeleteMe
                or int(weapon._get_address()) != frame[0]):
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.Controller != controller or pawn.IsInjuredDead() or weapon.Instigator != pawn
                or weapon.WorldInfo != world or pawn.Weapon != weapon):
            return
        identity = (int(controller._get_address()), int(world._get_address()), int(pawn._get_address()))
        if identity != frame[1] or _last_ditch_departing in (identity[:2], (identity[0], 0)):
            return
        manager = controller.GetSkillManager()
        if manager is None or getattr(manager, "bUpdatingSkills", False):
            return
        rank, existing = 0, None
        for skill in manager.ActiveSkills:
            if skill.Definition is None or skill.SkillInstigator != controller:
                continue
            address = int(skill.Definition._get_address())
            if address == _ready_definition_address:
                rank = max(rank, int(skill.Grade))
            elif address == _ready_movement_address:
                existing = skill.Definition
        if rank <= 0:
            return
        helper = unrealsdk.find_object("SkillDefinition", READY_MOVEMENT)
        if existing is not None:
            owner_ref = WeakPointer(controller)
            manager.DeactivateSkill(controller, existing)
            controller = owner_ref()
            if controller is None or controller.bDeleteMe:
                return
            live_world, live_pawn = controller.WorldInfo, controller.Pawn
            if (live_world is None or live_world.bDeleteMe or live_world.Pauser
                    or live_pawn is None or live_pawn.bDeleteMe or live_pawn.IsInjuredDead()
                    or (int(controller._get_address()), int(live_world._get_address()), int(live_pawn._get_address())) != identity
                    or _last_ditch_departing in (identity[:2], (identity[0], 0))):
                return
            manager = controller.GetSkillManager()
            if manager is None or getattr(manager, "bUpdatingSkills", False):
                return
        if manager.ActivateSkill(controller, helper, None, rank) is False:
            raise ValueError("Ready reload fire rate activation was rejected")
        key = "Ready reload fire rate activated"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(f"[AxtonRebalance] {key}: rank={rank}, bonus={READY_FIRE_PER_RANK*rank:g}, duration={READY_BUFF_SECONDS:g} seconds")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not activate Ready reload fire rate", exc)


def _sync_ready_movement(controller: Any, manager: Any, skills: tuple[Any, ...]) -> bool:
    """Only reconcile an existing timed proc; never create one during maintenance."""
    if not _ready_movement_address:
        return _sync_ready_hud(controller, manager, False)
    rank, instances = 0, []
    for skill in skills:
        if skill.Definition is None or skill.SkillInstigator != controller:
            continue
        address = int(skill.Definition._get_address())
        if address == _ready_definition_address:
            rank = max(rank, int(skill.Grade))
        elif address == _ready_movement_address:
            instances.append(skill)
    if rank <= 0:
        if instances:
            manager.DeactivateSkill(controller, instances[0].Definition)
            return False
        return _sync_ready_hud(controller, manager, False)
    for skill in instances:
        if int(skill.Grade) != rank:
            skill.UpdateGrade(rank)
            return False
    now = float(controller.WorldInfo.TimeSeconds)
    visible = any(int(skill.SkillState) == _ready_active_state
                  and 0. <= now - float(skill.StartTime) < float(skill.Duration)
                  for skill in instances)
    return _sync_ready_hud(controller, manager, visible)


def _sync_ready_hud(controller: Any, manager: Any, visible: bool) -> bool:
    global _ready_hud_next_check, _ready_hud_visible
    if not visible and not _ready_hud_visible:
        return True
    try:
        feedback = unrealsdk.find_object("SkillDefinition", READY_HUD)
        _ready_hud_next_check, changed = _sync_native_feedback(
            controller, manager, feedback, 1 if visible else 0, _ready_hud_next_check)
        _ready_hud_visible = visible
        return not changed
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not update Ready HUD", exc)
        return True  # Visual failure must never change movement or its timer.


def _suspend_ready_hud() -> None:
    """Use only the current live owner; never retain an old HUD/actor across maps."""
    if not _ready_hud_visible:
        return
    try:
        controller = get_pc(possibly_loading=True)
        if controller is None or controller.bDeleteMe:
            return
        world = controller.WorldInfo
        if world is None or world.bDeleteMe:
            return
        manager = controller.GetSkillManager()
        if manager is not None and not getattr(manager, "bUpdatingSkills", False):
            _sync_ready_hud(controller, manager, False)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not suspend Ready HUD", exc)



def _configure_laser_sight() -> bool:
    """Keep native turret targeting for accuracy, fire rate and weapon damage."""
    definition = unrealsdk.find_object("SkillDefinition", LASER_SIGHT)
    effects, stats = list(definition.SkillEffectDefinitions), list(definition.SkillEffectPresentations)
    accuracy = [effect for effect in effects if _effect_attribute_path(effect) == WEAPON_SPREAD]
    if len(accuracy) != 1:
        raise ValueError("Unexpected Laser Sight accuracy effects")
    accuracy_stats = [stat for stat in stats if _effect_attribute_path_for_presentation(stat) == WEAPON_SPREAD]
    allowed = (WEAPON_SPREAD, WEAPON_FIRE_INTERVAL, CRISIS_GUN_ATTRIBUTE)
    if (len(accuracy) != 1 or len(accuracy_stats) != 1
            or any(_effect_attribute_path(effect) not in allowed for effect in effects)
            or any(sum(_effect_attribute_path(effect) == path for effect in effects) > 1 for path in allowed)):
        raise ValueError("Unexpected Laser Sight effects/presentations")
    changed = False
    replacements = [copy.copy(effect) for effect in effects]
    for path, amount, name, description in (
            (WEAPON_FIRE_INTERVAL, -LASER_SIGHT_FIRE_PER_RANK, "AR_LaserSightFireRate", "Turret Fire Rate: $NUMBER$"),
            (CRISIS_GUN_ATTRIBUTE, LASER_SIGHT_DAMAGE_PER_RANK, "AR_LaserSightDamage", "Turret Damage: $NUMBER$")):
        attribute = unrealsdk.find_object("AttributeDefinition", path)
        if attribute is None:
            raise ValueError("Laser Sight turret attribute is unavailable")
        index = next((i for i, effect in enumerate(replacements) if _effect_attribute_path(effect) == path), None)
        # Always inherit the accuracy effect's turret-only target/criteria, never the player.
        effect = copy.copy(accuracy[0])
        effect.AttributeToModify = attribute
        effect.GradeToStartApplyingEffect, effect.PerGradeUpgradeInterval, effect.BonusUpgradeList = 1, 1, []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(effect, field))
            value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(effect, field, value)
        old_effect = replacements[index] if index is not None else None
        differs = (old_effect is None or _effect_layout(old_effect) != _effect_layout(effect)
            or getattr(old_effect, "GradeToStartApplyingEffect", None) != 1
            or getattr(old_effect, "PerGradeUpgradeInterval", None) != 1
            or bool(getattr(old_effect, "BonusUpgradeList", ()))
            or any(not math.isclose(float(getattr(old_effect, field).BaseValueConstant), amount, abs_tol=1e-7)
                   or float(getattr(old_effect, field).BaseValueScaleConstant) != 1.
                   or getattr(old_effect, field).BaseValueAttribute is not None
                   or getattr(old_effect, field).InitializationDefinition is not None
                   for field in ("BaseModifierValue", "PerGradeUpgrade")))
        if differs:
            if index is None:
                replacements.append(effect)
            else:
                replacements[index] = effect
            changed = True
        matches = [stat for stat in stats if _effect_attribute_path_for_presentation(stat) == path]
        if len(matches) > 1:
            raise ValueError("Duplicate Laser Sight stat")
        stat = matches[0] if matches else None
        if stat is None:
            try:
                stat = unrealsdk.find_object("AttributePresentationDefinition", LASER_SIGHT + ":" + name)
            except ValueError:
                stat = None
            if stat is None:
                stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                    template_obj=accuracy_stats[0])
            stat.Attribute = attribute
            stats.append(stat)
            changed = True
        if str(stat.Description) != description:
            stat.Description = description
            changed = True
        stat.bDisplayAsInverse = path == WEAPON_FIRE_INTERVAL
    if changed:
        definition.SkillEffectDefinitions = replacements
    definition.SkillEffectPresentations = stats
    if str(accuracy_stats[0].Description) != "Turret Accuracy: $NUMBER$":
        accuracy_stats[0].Description = "Turret Accuracy: $NUMBER$"
        changed = True
    description = ("Increases your [skill]Sabre Turret's[-skill] [skill]Accuracy[-skill], "
                   "[skill]Fire Rate[-skill] and [skill]Damage[-skill].")
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
        changed = True
    return changed


def _configure_crisis_management() -> bool:
    """Retain native shield gating/resistance; damage uses the shared hit scope."""
    global _crisis_definition_address, _last_ditch_active_state
    global _last_ditch_authority_role, _last_ditch_enemy_opinion
    definition = unrealsdk.find_object("SkillDefinition", CRISIS_MANAGEMENT)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    native = len(effects) == 2 and set(paths) == {CRISIS_GUN_ATTRIBUTE, CRISIS_MELEE_ATTRIBUTE}
    configured = (len(effects) == len(CRISIS_RESISTANCE_ATTRIBUTES) + 1
                  and set(paths) == set(CRISIS_RESISTANCE_ATTRIBUTES) | {CRISIS_GUN_ATTRIBUTE})
    if not (native or configured) or paths.count(CRISIS_GUN_ATTRIBUTE) != 1:
        raise ValueError(f"Unexpected Crisis Management effects: {paths}")
    melee = effects[paths.index(CRISIS_MELEE_ATTRIBUTE if native else CRISIS_RESISTANCE_ATTRIBUTES[0])]
    presentations = list(definition.SkillEffectPresentations)
    melee_presentations = [item for item in presentations
                           if _effect_attribute_path_for_presentation(item) in
                           (CRISIS_MELEE_ATTRIBUTE, CRISIS_RESISTANCE_ATTRIBUTES[0])]
    if len(melee_presentations) != 1:
        raise ValueError("Crisis Management melee stat presentation was not identified")
    attributes = [unrealsdk.find_object("AttributeDefinition", path)
                  for path in CRISIS_RESISTANCE_ATTRIBUTES]
    if any(attribute is None for attribute in attributes):
        raise ValueError("A Crisis Management damage resistance attribute is unavailable")
    replacements = []
    for attribute in attributes:
        effect = copy.copy(melee)
        effect.AttributeToModify = attribute
        effect.BaseModifierValue = copy.copy(melee.BaseModifierValue)
        effect.PerGradeUpgrade = copy.copy(melee.PerGradeUpgrade)
        effect.BaseModifierValue.BaseValueConstant = -CRISIS_RESISTANCE_PER_RANK
        effect.PerGradeUpgrade.BaseValueConstant = -CRISIS_RESISTANCE_PER_RANK
        effect.BaseModifierValue.BaseValueAttribute = effect.PerGradeUpgrade.BaseValueAttribute = None
        effect.BaseModifierValue.InitializationDefinition = effect.PerGradeUpgrade.InitializationDefinition = None
        effect.BaseModifierValue.BaseValueScaleConstant = 1.0
        effect.PerGradeUpgrade.BaseValueScaleConstant = 1.0
        replacements.append(effect)
    gun = effects[paths.index(CRISIS_GUN_ATTRIBUTE)]
    display = copy.copy(gun)
    display.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_None
    display.bIncludeSelfAsTarget = False
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(gun, field))
        value.BaseValueConstant, value.BaseValueScaleConstant = CRISIS_DAMAGE_PER_RANK, 1.0
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(display, field, value)
    desired = [display, *replacements]
    address = int(definition._get_address())
    if _crisis_definition_address != address:
        _prepare_last_ditch_attributes(definition)
        _last_ditch_active_state = int(unrealsdk.find_enum("ESkillState").SKILL_Active)
        _last_ditch_authority_role = int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
        _last_ditch_enemy_opinion = int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)
        _crisis_definition_address = address
    def signature(effect: Any) -> tuple[Any, ...]:
        return (_effect_layout(effect), *(tuple(getattr(getattr(effect, field), name) for name in
                ("BaseValueConstant", "BaseValueScaleConstant", "BaseValueAttribute", "InitializationDefinition"))
                for field in ("BaseModifierValue", "PerGradeUpgrade")))
    changed = [signature(e) for e in effects] != [signature(e) for e in desired]
    if changed:
        definition.SkillEffectDefinitions = desired
    description = (
        "Gain [skill]Damage[-skill] and [skill]Damage Reduction[-skill] "
        "while your shields are depleted."
    )
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
        changed = True
    presentation = melee_presentations[0]
    if presentation.Attribute != attributes[0] or presentation.Description != "Damage Reduction: $NUMBER$":
        presentation.Attribute = attributes[0]
        presentation.Description = "Damage Reduction: $NUMBER$"
        changed = True
    for item in presentations:
        if _effect_attribute_path_for_presentation(item) == CRISIS_GUN_ATTRIBUTE and item.Description != "Damage: $NUMBER$":
            item.Description = "Damage: $NUMBER$"
            changed = True
    return changed


def _effect_attribute_path_for_presentation(presentation: Any) -> str | None:
    attribute = presentation.Attribute
    return _skill_path(attribute) if attribute is not None else None


def _pressure_depleted_gate(definition: Any, *, path: str = PRESSURE_DEPLETED_INIT,
                            default: float = 0., depleted: float = 1.) -> tuple[Any, bool]:
    """Native shield-state multiplier; effective rank is applied once outside."""
    source = unrealsdk.find_object("AttributeInitializationDefinition",
        "GD_Soldier_Skills.Misc.Init_Pressure_ShieldDelayCalc_P1")
    shield_current = unrealsdk.find_object("ResourcePoolAttributeDefinition",
        "D_Attributes.ShieldResourcePool.ShieldCurrentValue")
    try:
        gate = unrealsdk.find_object("AttributeInitializationDefinition", path)
    except ValueError:
        gate = None
    created = gate is None
    if gate is None:
        gate = unrealsdk.construct_object("AttributeInitializationDefinition", definition, path.rsplit(":", 1)[1],
            template_obj=source, flags=int(ObjectFlags.KEEP_ALIVE))
    if gate is None or shield_current is None:
        raise ValueError("Native depleted-shield initializer is unavailable")
    scale = unrealsdk.find_enum("EBaseValueMode").BASEVALUE_InitializationDefScalesBaseValue
    comparison = unrealsdk.find_enum("EComparisonOperator").OPERATOR_LessThanOrEqual
    usage = unrealsdk.find_enum("EOperandUsage").OPERAND_PreferAttribute
    def plain(value: Any, amount: float) -> Any:
        value = copy.copy(value)
        value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
        value.BaseValueAttribute = value.InitializationDefinition = None
        return value
    def matches(value: Any, amount: float) -> bool:
        return (math.isclose(float(value.BaseValueConstant), amount, abs_tol=1e-7)
                and float(value.BaseValueScaleConstant) == 1.
                and value.BaseValueAttribute is None and value.InitializationDefinition is None)
    condition = gate.ConditionalInitialization
    rows = list(condition.ConditionalExpressionList)
    same = (bool(condition.bEnabled) and matches(condition.DefaultBaseValue, default) and len(rows) == 1
            and matches(rows[0].BaseValueIfTrue, depleted) and len(rows[0].Expressions) == 1)
    if same:
        expression = rows[0].Expressions[0]
        same = (expression.AttributeOperand1 == shield_current and expression.ComparisonOperator == comparison
                and expression.Operand2Usage == usage and expression.AttributeOperand2 is None
                and float(expression.ConstantOperand2) == 0.)
    changed = (created or gate.BaseValueMode != scale or gate.ValueFormula.bEnabled or not same
               or gate.RandomVariance.bEnabled or gate.RangeRestriction.bEnableMinValueRestriction
               or gate.RangeRestriction.bEnableMaxValueRestriction)
    if changed:
        expression = unrealsdk.make_struct("Engine.AttributeExpression.AttributeExpressionData",
            AttributeOperand1=shield_current, ComparisonOperator=comparison, Operand2Usage=usage,
            AttributeOperand2=None, ConstantOperand2=0.)
        row = unrealsdk.make_struct("Engine.AttributeInitializationDefinition.ConditionalValueExpression",
            BaseValueIfTrue=plain(condition.DefaultBaseValue, depleted), Expressions=[expression])
        condition = copy.copy(condition)
        condition.bEnabled, condition.ConditionalExpressionList = True, [row]
        condition.DefaultBaseValue = plain(condition.DefaultBaseValue, default)
        formula, variance, bounds = copy.copy(gate.ValueFormula), copy.copy(gate.RandomVariance), copy.copy(gate.RangeRestriction)
        formula.bEnabled, variance.bEnabled = False, False
        bounds.bEnableMinValueRestriction, bounds.bEnableMaxValueRestriction = False, False
        gate.BaseValueMode, gate.ValueFormula, gate.ConditionalInitialization = scale, formula, condition
        gate.RandomVariance, gate.RangeRestriction = variance, bounds
    return gate, changed


def _pressure_missing_shield_factor(definition: Any, *, owner_path: str = PRESSURE,
                                    missing: bool = True) -> tuple[Any, bool]:
    """Bounded native shield fraction or complement, isolated under its owner."""
    source = unrealsdk.find_object("AttributeInitializationDefinition",
        "GD_Soldier_Skills.Misc.Init_Pressure_ReloadSpdCalc_P2")
    current = unrealsdk.find_object("ResourcePoolAttributeDefinition",
        "D_Attributes.ShieldResourcePool.ShieldCurrentValue")
    maximum = unrealsdk.find_object("ResourcePoolAttributeDefinition", SHIELD_CAPACITY_ATTRIBUTE)
    modes = unrealsdk.find_enum("EBaseValueMode")
    changed = False

    def value(amount: float = 0., attribute: Any = None, initializer: Any = None,
              scale: float = 1.) -> Any:
        result = copy.copy(source.ValueFormula.Offset)
        result.BaseValueConstant, result.BaseValueScaleConstant = amount, scale
        result.BaseValueAttribute, result.InitializationDefinition = attribute, initializer
        return result

    def same_value(before: Any, after: Any) -> bool:
        return (before.BaseValueAttribute == after.BaseValueAttribute
            and before.InitializationDefinition == after.InitializationDefinition
            and math.isclose(float(before.BaseValueConstant), float(after.BaseValueConstant), rel_tol=1e-6, abs_tol=1e-8)
            and math.isclose(float(before.BaseValueScaleConstant), float(after.BaseValueScaleConstant), rel_tol=1e-6, abs_tol=1e-8))

    def make(name: str, mode: Any, multiplier: Any, level: Any, power: Any,
             offset: Any, lower: float, upper: float | None) -> Any:
        nonlocal changed
        try:
            result = unrealsdk.find_object("AttributeInitializationDefinition", owner_path + ":" + name)
        except ValueError:
            result = None
        created = result is None
        if result is None:
            result = unrealsdk.construct_object("AttributeInitializationDefinition", definition, name,
                template_obj=source, flags=int(ObjectFlags.KEEP_ALIVE))
        if result is None:
            raise ValueError("Pressure missing-shield initializer is unavailable")
        formula, bounds = result.ValueFormula, result.RangeRestriction
        expected = (multiplier, level, power, offset)
        differs = (created or result.BaseValueMode != mode or not formula.bEnabled
            or result.ConditionalInitialization.bEnabled or result.RandomVariance.bEnabled
            or any(not same_value(getattr(formula, field), wanted)
                   for field, wanted in zip(("Multiplier", "Level", "Power", "Offset"), expected))
            or not bounds.bEnableMinValueRestriction or not same_value(bounds.MinValue, value(lower))
            or bool(bounds.bEnableMaxValueRestriction) != (upper is not None)
            or (upper is not None and not same_value(bounds.MaxValue, value(upper))))
        if differs:
            formula, bounds = copy.copy(formula), copy.copy(bounds)
            condition, variance = copy.copy(result.ConditionalInitialization), copy.copy(result.RandomVariance)
            formula.bEnabled, condition.bEnabled, variance.bEnabled = True, False, False
            for field, wanted in zip(("Multiplier", "Level", "Power", "Offset"), expected):
                setattr(formula, field, wanted)
            bounds.bEnableMinValueRestriction, bounds.MinValue = True, value(lower)
            bounds.bEnableMaxValueRestriction = upper is not None
            if upper is not None:
                bounds.MaxValue = value(upper)
            result.BaseValueMode, result.ValueFormula, result.RangeRestriction = mode, formula, bounds
            result.ConditionalInitialization, result.RandomVariance = condition, variance
            changed = True
        return result

    sets = modes.BASEVALUE_InitializationDefSetsBaseValue
    denominator = make("AR_SafeShieldMaximum", sets, value(attribute=maximum), value(1.),
                       value(1.), value(), .0001, None)
    ratio = make("AR_ShieldFraction", sets, value(attribute=current), value(initializer=denominator),
                 value(-1.), value(), 0., 1.)
    if not missing:
        factor = make("AR_FilledShieldFraction", modes.BASEVALUE_InitializationDefScalesBaseValue,
                      value(1.), value(initializer=ratio), value(1.), value(), 0., 1.)
        return factor, changed
    factor = make("AR_MissingShieldFraction", modes.BASEVALUE_InitializationDefScalesBaseValue,
                  value(1.), value(1.), value(1.), value(initializer=ratio, scale=-1.), 0., 1.)
    return factor, changed


def _pressure_damage_fraction(current: float, maximum: float) -> float:
    if not math.isfinite(current) or not math.isfinite(maximum) or maximum <= 0.0:
        return 0.0
    return 1.0 if current > 0.0 else 0.0


def _configure_pressure() -> bool:
    """Native missing-shield delay and display-only shared-bucket damage."""
    global _pressure_definition_address, _last_ditch_active_state
    global _last_ditch_authority_role, _last_ditch_enemy_opinion
    definition = unrealsdk.find_object("SkillDefinition", PRESSURE)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(item) for item in effects]
    native = [RELOAD_ATTRIBUTE, None, PRESSURE_SHIELD_DELAY_ATTRIBUTE, RECOIL_ATTRIBUTE]
    previous = [SHIELD_CAPACITY_ATTRIBUTE, HEALTHY_HEALTH_ATTRIBUTE,
                PRESSURE_SHIELD_DELAY_ATTRIBUTE, RECOIL_ATTRIBUTE]
    movement_layout = [MOVEMENT_ATTRIBUTE, None, PRESSURE_SHIELD_DELAY_ATTRIBUTE, RECOIL_ATTRIBUTE]
    desired = [CRISIS_GUN_ATTRIBUTE, None, PRESSURE_SHIELD_DELAY_ATTRIBUTE, RECOIL_ATTRIBUTE]
    if paths not in (native, previous, movement_layout, desired):
        raise ValueError(f"Unexpected Pressure effects: {paths}")
    targets = unrealsdk.find_enum("EEffectTarget")
    if effects[2].EffectTarget != targets.TARGET_Self or effects[3].EffectTarget != targets.TARGET_None:
        raise ValueError("Unexpected Pressure shield-delay targeting")
    damage = unrealsdk.find_object("AttributeDefinition", CRISIS_GUN_ATTRIBUTE)
    native_stat = unrealsdk.find_object("AttributePresentationDefinition", PRESSURE + ":AttributePresentationDefinition_1")
    if damage is None or native_stat is None:
        raise ValueError("Pressure damage attribute or presentation is unavailable")
    mode = unrealsdk.find_enum("EModifierType").MT_Scale
    factor, changed = _pressure_missing_shield_factor(definition)
    changed |= paths != desired
    specifications = ((damage, PRESSURE_DAMAGE_PER_RANK, targets.TARGET_None, None),
                      (None, PRESSURE_DAMAGE_PER_RANK, targets.TARGET_None, None),
                      (effects[2].AttributeToModify, PRESSURE_DELAY_PER_RANK, targets.TARGET_Self, factor),
                      (effects[3].AttributeToModify, PRESSURE_DELAY_PER_RANK, targets.TARGET_None, None))
    replacements = []
    for old, (attribute, amount, target, initializer) in zip(effects, specifications):
        data = copy.copy(old)
        data.AttributeToModify, data.EffectTarget, data.ModifierType = attribute, target, mode
        data.GradeToStartApplyingEffect, data.PerGradeUpgradeInterval, data.BonusUpgradeList = 1, 1, []
        changed |= (_effect_layout(old) != _effect_layout(data)
                    or getattr(old, "GradeToStartApplyingEffect", None) != 1
                    or getattr(old, "PerGradeUpgradeInterval", None) != 1
                    or bool(getattr(old, "BonusUpgradeList", ())))
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            previous_value = getattr(old, field)
            changed |= (not math.isclose(float(previous_value.BaseValueConstant), amount, abs_tol=1e-7)
                        or float(previous_value.BaseValueScaleConstant) != 1.
                        or previous_value.BaseValueAttribute is not None
                        or previous_value.InitializationDefinition != initializer)
            value = copy.copy(previous_value)
            value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
            value.BaseValueAttribute, value.InitializationDefinition = None, initializer
            setattr(data, field, value)
        replacements.append(data)
    try:
        stat = unrealsdk.find_object("AttributePresentationDefinition", PRESSURE + ":AR_PressureDamage")
    except ValueError:
        stat = None
    if stat is None:
        stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, "AR_PressureDamage",
            template_obj=native_stat, flags=int(ObjectFlags.KEEP_ALIVE))
    stat.Attribute, stat.Description = None, "Damage: $NUMBER$"
    stat.bDisplayAsPercentage, stat.bDisplayAsInverse = True, False
    stat.bDontDisplayPlusSign, stat.bUseCustomNumberPlacement = False, True
    stat.SignStyle = native_stat.SignStyle
    address = int(definition._get_address())
    if _pressure_definition_address != address:
        _prepare_last_ditch_attributes(definition)
        _last_ditch_active_state = int(unrealsdk.find_enum("ESkillState").SKILL_Active)
        _last_ditch_authority_role = int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
        _last_ditch_enemy_opinion = int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)
        _pressure_definition_address = address
    if changed:
        definition.SkillEffectDefinitions = replacements
    native_stat.Description = "Shield Recharge Delay: up to $NUMBER$"
    definition.SkillEffectPresentations = [stat, native_stat]
    description = (
        "Reduces your [skill]Shield Recharge Delay[-skill] as your shield depletes "
        "and increases your [skill]Damage[-skill] while you have shields.")
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    return changed


def _pressure_description_needs_restore(definition: Any) -> bool:
    effects = list(definition.SkillEffectDefinitions)
    paths = [CRISIS_GUN_ATTRIBUTE, None, PRESSURE_SHIELD_DELAY_ATTRIBUTE, RECOIL_ATTRIBUTE]
    if [_effect_attribute_path(item) for item in effects] != paths:
        return True
    for index, (effect, amount) in enumerate(zip(effects, (
            PRESSURE_DAMAGE_PER_RANK, PRESSURE_DAMAGE_PER_RANK,
            PRESSURE_DELAY_PER_RANK, PRESSURE_DELAY_PER_RANK))):
        initializer = PRESSURE_MISSING_SHIELD_INIT if index == 2 else None
        if index in (0, 1) and effect.EffectTarget != unrealsdk.find_enum("EEffectTarget").TARGET_None:
            return True
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = getattr(effect, field)
            actual = _skill_path(value.InitializationDefinition) if value.InitializationDefinition is not None else None
            if (not math.isclose(float(value.BaseValueConstant), amount, abs_tol=1e-7)
                    or float(value.BaseValueScaleConstant) != 1.
                    or value.BaseValueAttribute is not None or actual != initializer):
                return True
    return [_effect_attribute_path_for_presentation(item) for item in definition.SkillEffectPresentations] != [
        None, RECOIL_ATTRIBUTE]


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_pressure(tree: Any, args: Any, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or _skill_path(args.SkillDef) != PRESSURE:
        return None
    try:
        if _pressure_description_needs_restore(args.SkillDef):
            if _configure_pressure():
                _invalidate_class_mod_cache()  # Rebuild existing native modifiers through normal maintenance.
        rank = max(0, int(args.Grade))  # Native tooltip request already includes class-mod points.
        values = [f"{100. * amount * rank:+g}%" if rank else "0%" for amount in (
            PRESSURE_DAMAGE_PER_RANK, PRESSURE_DELAY_PER_RANK)]
        if args.bIncludeHTML:
            owner = getattr(args, "PlayerOwner", None)
            current = int(owner.GetSkillGrade(args.SkillDef)) if owner is not None else 0
            invested = max(0, rank - max(0, int(getattr(args, "GradeModifier", 0))))
            if invested >= 5 and current >= 5:
                values = [f'<font color="#00FF00">{value}</font>' for value in values]
            elif rank > 0 and current > 0:
                color = getattr(tree, "SkillIntermediateGradeColor", None)
                style = str(getattr(tree, "SkillLockedModifierTextHTML", ""))
                if color is not None and "%c" in style and "%s" in style:
                    channels = tuple(int(getattr(color, channel)) for channel in ("R", "G", "B"))
                    if all(0 <= channel <= 255 for channel in channels):
                        rgb = "".join(f"{channel:02X}" for channel in channels)
                        values = [style.replace("%c", rgb).replace("%s", value) for value in values]
        return Block, ("<br>" if args.bIncludeHTML else "\n").join((
            f"Damage: {values[0]}", f"Shield Recharge Delay: up to {values[1]}"))
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not describe Pressure", exc)
        return None


def _configure_able() -> bool:
    """Keep native healing, grade resolution, event timing and stack expiry."""
    global _able_behavior_addresses
    definition = unrealsdk.find_object("SkillDefinition", ABLE)
    active = unrealsdk.find_object("SkillDefinition", ABLE_ACTIVE)
    coefficient = unrealsdk.find_object("ConstantAttributeValueResolver",
        "GD_Soldier_Skills.Misc.Att_Able_HealthRegenerationPerLvl:ConstantAttributeValueResolver_0")
    activate = unrealsdk.find_object("Behavior_ActivateSkill", ABLE_PROVIDER + ".Behavior_ActivateSkill_62")
    deactivate = unrealsdk.find_object("Behavior_DeactivateSkill", ABLE_PROVIDER + ".Behavior_DeactivateSkill_62")
    duration = unrealsdk.find_object("AttributePresentationDefinition", ABLE + ":AttributePresentationDefinition_0")
    if (activate.SkillToActivate != active or deactivate.SkillToDeactivate != active
            or activate.bNoSkillStacking or not math.isclose(float(active.InitialDuration), 3.0)):
        raise ValueError("Unexpected Able activation or duration; stacking was not configured")
    addresses = (int(activate._get_address()), int(deactivate._get_address()))
    changed = _able_behavior_addresses != addresses or float(coefficient.ConstantValue) != ABLE_REGEN_PER_RANK
    if float(coefficient.ConstantValue) != ABLE_REGEN_PER_RANK:
        coefficient.ConstantValue = ABLE_REGEN_PER_RANK
    description = (
        "Damaging an enemy grants a stack of [skill]Health Regeneration[-skill]. "
        "Each stack lasts a few seconds. Stacks up to [skill]5 times[-skill]."
    )
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    footer = "Duration per Stack: $NUMBER$ seconds<br>Maximum Stacks: 5"
    if str(duration.Description) != footer:
        duration.Description = footer
    _able_behavior_addresses = addresses
    return changed


def _configure_grenadier() -> bool:
    """Add explosive damage using native skill grades and stat presentation."""
    definition = unrealsdk.find_object("SkillDefinition", GRENADIER)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    if (paths.count(GRENADE_CAPACITY_ATTRIBUTE) != 1
            or paths.count(EXPLOSIVE_DAMAGE_ATTRIBUTE) > 1
            or any(path not in (GRENADE_CAPACITY_ATTRIBUTE, EXPLOSIVE_DAMAGE_ATTRIBUTE) for path in paths)):
        raise ValueError(f"Unexpected Grenadier effects: {paths}")
    presentations = list(definition.SkillEffectPresentations)
    original = [item for item in presentations
                if _effect_attribute_path_for_presentation(item) == GRENADE_CAPACITY_ATTRIBUTE]
    if len(original) != 1:
        raise ValueError("Grenadier capacity presentation was not identified")
    attribute = unrealsdk.find_object("AttributeDefinition", EXPLOSIVE_DAMAGE_ATTRIBUTE)
    if attribute is None:
        raise ValueError("Grenadier explosive damage attribute is unavailable")
    mode = unrealsdk.find_enum("EModifierType").MT_Scale
    template = effects[paths.index(GRENADE_CAPACITY_ATTRIBUTE)]
    current = effects[paths.index(EXPLOSIVE_DAMAGE_ATTRIBUTE)] if EXPLOSIVE_DAMAGE_ATTRIBUTE in paths else None
    changed = current is None or current.ModifierType != mode
    if current is not None:
        changed |= any(
            not math.isclose(float(value.BaseValueConstant), 0.04)
            or value.BaseValueAttribute is not None or value.InitializationDefinition is not None
            or float(value.BaseValueScaleConstant) != 1.0
            for value in (current.BaseModifierValue, current.PerGradeUpgrade)
        )
    added = copy.copy(template)
    added.AttributeToModify = attribute
    added.ModifierType = mode
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(template, field))
        value.BaseValueConstant = 0.04
        value.BaseValueAttribute = None
        value.InitializationDefinition = None
        value.BaseValueScaleConstant = 1.0
        setattr(added, field, value)
    name = "AR_GrenadierExplosiveDamage"
    own = next((item for item in presentations if _skill_path(item) == GRENADIER + ":" + name), None)
    if own is None:
        try:
            own = unrealsdk.find_object("AttributePresentationDefinition", GRENADIER + ":" + name)
        except ValueError:
            own = None
        if own is None:
            own = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                                             template_obj=original[0])
    for field, value in (("Attribute", attribute), ("Description", "Explosive Damage: $NUMBER$"),
                         ("bDisplayAsPercentage", True), ("bDisplayPercentAsFloat", False)):
        if getattr(own, field) != value:
            setattr(own, field, value)
    if changed:
        definition.SkillEffectDefinitions = [copy.copy(template), added]
    if own not in presentations:
        definition.SkillEffectPresentations = [*presentations, own]
    description = (
        "Increases your [skill]Grenade Capacity[-skill] and [skill]Explosive Damage[-skill]."
    )
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    return changed


def _configure_impact() -> bool:
    """Replace the native melee effect with accuracy; keep gun damage intact."""
    definition = unrealsdk.find_object("SkillDefinition", IMPACT)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    replacement_paths = (CRISIS_MELEE_ATTRIBUTE, WEAPON_SPREAD)
    candidates = [index for index, path in enumerate(paths) if path in replacement_paths]
    if len(effects) != 2 or paths.count(CRISIS_GUN_ATTRIBUTE) != 1 or len(candidates) != 1:
        raise ValueError(f"Unexpected Impact effects: {paths}")
    presentations = [item for item in definition.SkillEffectPresentations
                     if _effect_attribute_path_for_presentation(item) in replacement_paths]
    if len(presentations) != 1:
        raise ValueError("Impact melee/accuracy presentation was not identified")
    attribute = unrealsdk.find_object("AttributeDefinition", WEAPON_SPREAD)
    accuracy_style = unrealsdk.find_object("AttributePresentationDefinition",
                                          LASER_SIGHT + ":AttributePresentationDefinition_0")
    if attribute is None or accuracy_style is None:
        raise ValueError("Impact accuracy attribute or presentation style is unavailable")
    original = effects[candidates[0]]
    changed = paths[candidates[0]] != WEAPON_SPREAD or any(
        not math.isclose(float(value.BaseValueConstant), -0.05)
        or value.BaseValueAttribute is not None or value.InitializationDefinition is not None
        or float(value.BaseValueScaleConstant) != 1.0
        for value in (original.BaseModifierValue, original.PerGradeUpgrade)
    )
    if changed:
        owned = copy.copy(original)
        owned.AttributeToModify = attribute
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(original, field))
            value.BaseValueConstant = -0.05
            value.BaseValueAttribute = None
            value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0
            setattr(owned, field, value)
        definition.SkillEffectDefinitions = [owned if index == candidates[0] else copy.copy(effect)
                                            for index, effect in enumerate(effects)]
    presentation = presentations[0]
    for field, value in (("Attribute", attribute), ("Description", "Accuracy: $NUMBER$"),
                         ("SignStyle", accuracy_style.SignStyle), ("bDisplayAsInverse", False)):
        if getattr(presentation, field) != value:
            setattr(presentation, field, value)
    description = "Increases [skill]Gun Damage[-skill] and [skill]Accuracy[-skill]."
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    return changed


def _configure_battlefront() -> bool:
    """Replace melee with critical damage while retaining the turret condition."""
    definition = unrealsdk.find_object("SkillDefinition", BATTLEFRONT)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    replacement_paths = (CRISIS_MELEE_ATTRIBUTE, CRITICAL_DAMAGE_ATTRIBUTE)
    candidates = [index for index, path in enumerate(paths) if path in replacement_paths]
    if (len(effects) != 3 or paths.count(CRISIS_GUN_ATTRIBUTE) != 1
            or paths.count(GRENADE_DAMAGE_ATTRIBUTE) != 1 or len(candidates) != 1):
        raise ValueError(f"Unexpected Battlefront effects: {paths}")
    presentations = [item for item in definition.SkillEffectPresentations
                     if _effect_attribute_path_for_presentation(item) in replacement_paths]
    if len(presentations) != 1:
        raise ValueError("Battlefront melee/critical presentation was not identified")
    attribute = unrealsdk.find_object("AttributeDefinition", CRITICAL_DAMAGE_ATTRIBUTE)
    if attribute is None:
        raise ValueError("Battlefront critical damage attribute is unavailable")
    original = effects[candidates[0]]
    changed = paths[candidates[0]] != CRITICAL_DAMAGE_ATTRIBUTE or any(
        not math.isclose(float(value.BaseValueConstant), BATTLEFRONT_CRITICAL_PER_RANK)
        or value.BaseValueAttribute is not None or value.InitializationDefinition is not None
        or float(value.BaseValueScaleConstant) != 1.0
        for value in (original.BaseModifierValue, original.PerGradeUpgrade)
    )
    if changed:
        owned = copy.copy(original)
        owned.AttributeToModify = attribute
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(original, field))
            value.BaseValueConstant = BATTLEFRONT_CRITICAL_PER_RANK
            value.BaseValueAttribute = None
            value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0
            setattr(owned, field, value)
        definition.SkillEffectDefinitions = [owned if index == candidates[0] else copy.copy(effect)
                                            for index, effect in enumerate(effects)]
    presentation = presentations[0]
    for field, value in (("Attribute", attribute), ("Description", "Critical Hit Damage: $NUMBER$")):
        if getattr(presentation, field) != value:
            setattr(presentation, field, value)
    description = (
        "While your [skill]Sabre Turret[-skill] is deployed, you gain [skill]Gun Damage[-skill], "
        "[skill]Grenade Damage[-skill] and [skill]Critical Hit Damage[-skill]."
    )
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    return changed


def _configure_healthy() -> bool:
    """Passive maximum health and regeneration, doubled with depleted shields."""
    global _healthy_definition_address, _healthy_helper_address
    definition = unrealsdk.find_object("SkillDefinition", HEALTHY)
    battlefront = unrealsdk.find_object("SkillDefinition", BATTLEFRONT)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    if paths not in ([HEALTHY_HEALTH_ATTRIBUTE],
                     [HEALTHY_HEALTH_ATTRIBUTE, CRISIS_RESISTANCE_ATTRIBUTES[0]],
                     [HEALTHY_HEALTH_ATTRIBUTE, HEALTH_REGEN_ATTRIBUTE]):
        raise ValueError(f"Unexpected Healthy effects: {paths}")
    regen_attribute = unrealsdk.find_object("ResourcePoolAttributeDefinition", HEALTH_REGEN_ATTRIBUTE)
    max_health = unrealsdk.find_object("ResourcePoolAttributeDefinition", HEALTH_MAX_ATTRIBUTE)
    source_init = unrealsdk.find_object("AttributeInitializationDefinition",
        "GD_Soldier_Skills.Misc.Init_Preparation_HealthRegeneration_Part2")
    if regen_attribute is None or max_health is None or source_init is None:
        raise ValueError("Healthy regeneration inputs are unavailable")
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = getattr(effects[0], field)
        if value.BaseValueAttribute is not None or value.InitializationDefinition is not None:
            raise ValueError("Unexpected Healthy maximum-health formula")
    targets, modes = unrealsdk.find_enum("EEffectTarget"), unrealsdk.find_enum("EModifierType")
    untracked = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked

    def plain(template: Any, amount: float, initializer: Any = None) -> Any:
        value = copy.copy(template)
        value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
        value.BaseValueAttribute, value.InitializationDefinition = None, initializer
        return value

    def same_value(old: Any, new: Any) -> bool:
        return (old.BaseValueAttribute == new.BaseValueAttribute and old.InitializationDefinition == new.InitializationDefinition
                and math.isclose(float(old.BaseValueConstant), float(new.BaseValueConstant), rel_tol=1e-6, abs_tol=1e-7)
                and math.isclose(float(old.BaseValueScaleConstant), float(new.BaseValueScaleConstant), rel_tol=1e-6, abs_tol=1e-7))

    try:
        initializer = unrealsdk.find_object("AttributeInitializationDefinition", HEALTHY_REGEN_INIT)
    except ValueError:
        initializer = None
    created_init = initializer is None
    if initializer is None:
        initializer = unrealsdk.construct_object("AttributeInitializationDefinition", definition, "AR_HealthRegenPerRank",
            template_obj=source_init, flags=int(ObjectFlags.KEEP_ALIVE))
    if initializer is None:
        raise ValueError("Healthy regeneration initializer could not be created")
    gate, gate_changed = _pressure_depleted_gate(definition,
        path=HEALTHY + ":AR_DepletedRegenMultiplier", default=1., depleted=2.)
    formula = copy.copy(source_init.ValueFormula)
    formula.bEnabled = True
    formula.Multiplier = plain(source_init.ValueFormula.Multiplier, 1.)
    formula.Multiplier.BaseValueAttribute = max_health
    formula.Level = plain(source_init.ValueFormula.Level, HEALTHY_REGEN_PER_RANK, gate)
    formula.Power = plain(source_init.ValueFormula.Power, 1.)
    formula.Offset = plain(source_init.ValueFormula.Offset, 0.)
    init_changed = (created_init or initializer.ValueFormula.bEnabled != formula.bEnabled
                    or any(not same_value(getattr(initializer.ValueFormula, field), getattr(formula, field))
                           for field in ("Multiplier", "Level", "Power", "Offset")))
    if init_changed:
        initializer.ValueFormula = formula
    health = copy.copy(effects[0])
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        setattr(health, field, plain(getattr(effects[0], field), HEALTHY_HEALTH_PER_RANK))
    display = copy.copy(health)
    display.AttributeToModify, display.EffectTarget, display.ModifierType = regen_attribute, targets.TARGET_None, modes.MT_PostAdd
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        setattr(display, field, plain(getattr(health, field), HEALTHY_REGEN_PER_RANK))
    regen = copy.copy(health)
    regen.AttributeToModify, regen.EffectTarget, regen.ModifierType = regen_attribute, targets.TARGET_Self, modes.MT_PostAdd
    regen.GradeToStartApplyingEffect, regen.PerGradeUpgradeInterval, regen.BonusUpgradeList = 1, 1, []
    regen.BaseModifierValue = plain(health.BaseModifierValue, 1., initializer)
    regen.PerGradeUpgrade = plain(health.PerGradeUpgrade, 1., initializer)
    try:
        helper = unrealsdk.find_object("SkillDefinition", HEALTHY_TURRET_HELPER)
    except ValueError:
        helper = None
    created = helper is None
    if helper is None:
        helper = unrealsdk.construct_object("SkillDefinition", definition, "AR_TurretResistance",
            template_obj=battlefront, flags=int(ObjectFlags.KEEP_ALIVE))
    if helper is None:
        raise ValueError("Healthy passive regeneration helper could not be created")

    def same_effect(old: Any, new: Any) -> bool:
        return (_effect_layout(old) == _effect_layout(new)
                and all(getattr(old, field, None) == getattr(new, field, None)
                        for field in ("GradeToStartApplyingEffect", "PerGradeUpgradeInterval"))
                and list(getattr(old, "BonusUpgradeList", ()) or ()) == list(getattr(new, "BonusUpgradeList", ()) or ())
                and same_value(old.BaseModifierValue, new.BaseModifierValue)
                and same_value(old.PerGradeUpgrade, new.PerGradeUpgrade))
    old_helper = list(helper.SkillEffectDefinitions)
    helper_changed = created or len(old_helper) != 1 or not same_effect(old_helper[0], regen)
    if helper_changed:
        helper.SkillEffectDefinitions = [regen]  # Replace all previous resistance channels.
    helper.SkillConstraints = []  # Regeneration is passive; shield state is evaluated natively.
    helper.TrackedSkillType = untracked
    helper.bSubjectToGradeRules = False  # Parent effective rank is supplied once by the synchronizer.
    helper.bAutoUpdateContexts = True
    helper.SkillEffectPresentations = []
    helper.BehaviorProviderDefinition = None
    helper.TrackedActiveSkill = None
    helper.TrackedActiveSkills = []
    helper.DamageEvents = []
    helper.KillEvents = []
    helper.CustomStackCount = None
    helper.EffectSourceInstanceDataName = ""
    helper.SkillName = "Healthy passive health regeneration"
    try:
        stat = unrealsdk.find_object("AttributePresentationDefinition", HEALTHY + ":AR_TurretResistanceStat")
    except ValueError:
        stat = None
    if stat is None:
        template = unrealsdk.find_object("AttributePresentationDefinition", CRISIS_MANAGEMENT + ":AttributePresentationDefinition_53")
        stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, "AR_TurretResistanceStat", template_obj=template)
    stat.Attribute = regen_attribute
    stat.Description = "Health Regeneration: $NUMBER$ / sec"
    stat.bDisplayAsPercentage, stat.bDisplayAsInverse = True, False
    stat.bDisplayPercentAsFloat = True
    stat.RoundingMode = unrealsdk.find_enum("EAttributeInitializationRounding").ATTRROUNDING_Float
    stat.FloatPrecision = 2
    stat.bDontDisplayPlusSign, stat.bUseCustomNumberPlacement = False, True
    changed = created or init_changed or gate_changed or helper_changed or len(effects) != 2 or any(
        not same_effect(old, new) for old, new in zip(effects, (health, display)))
    if changed:
        definition.SkillEffectDefinitions = [health, display]
    presentations = list(definition.SkillEffectPresentations)
    if stat not in presentations:
        definition.SkillEffectPresentations = [*presentations, stat]
    description = ("Increases your [skill]Maximum Health[-skill] and passively "
                   "[skill]regenerates health[-skill]. Health regeneration is doubled while your shields are depleted.")
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    _healthy_definition_address, _healthy_helper_address = int(definition._get_address()), int(helper._get_address())
    return changed


def _sync_healthy_turret_bonus(controller: Any, manager: Any, skills: tuple[Any, ...]) -> bool:
    """Only change our helper on rank/allocation changes; callbacks invalidate skills."""
    if not _healthy_helper_address:
        return True
    rank, instances = 0, []
    for skill in skills:
        if skill.Definition is None or skill.SkillInstigator != controller:
            continue
        address = int(skill.Definition._get_address())
        if address == _healthy_definition_address:
            rank = max(rank, int(skill.Grade))
        elif address == _healthy_helper_address:
            instances.append(skill)
    if rank <= 0:
        if instances:
            manager.DeactivateSkill(controller, instances[0].Definition)
            return False
        return True
    if len(instances) > 1:
        manager.DeactivateSkill(controller, instances[0].Definition)
        return False  # Reconcile from a fresh native snapshot, without duplicate healing.
    if instances:
        for skill in instances:
            if int(skill.Grade) != rank:
                skill.UpdateGrade(rank)
                return False
        return True
    helper = unrealsdk.find_object("SkillDefinition", HEALTHY_TURRET_HELPER)
    if manager.ActivateSkill(controller, helper, None, rank) is False:
        raise ValueError("Healthy passive regeneration activation was rejected")
    return False


def _configure_forbearance() -> bool:
    global _forbearance_address, _forbearance_legacy_address, _forbearance_explosive_type
    definition = unrealsdk.find_object("SkillDefinition", FORBEARANCE)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(item) for item in effects]
    native = [*FORBEARANCE_DURATION_ATTRIBUTES, HEALTH_MAX_ATTRIBUTE]
    desired_paths = [*FORBEARANCE_DURATION_ATTRIBUTES, SHIELD_CAPACITY_ATTRIBUTE]
    if paths not in (native, desired_paths,
            ["GD_SkagShared.Skills.Att_PlayerIsSlowed", WEAPON_FIRE_INTERVAL, MOVEMENT_ATTRIBUTE],
            [WEAPON_FIRE_INTERVAL, MOVEMENT_ATTRIBUTE], [SHIELD_CAPACITY_ATTRIBUTE]):
        raise ValueError(f"Unexpected Forbearance effects: {paths}")
    duration = [unrealsdk.find_object("AttributeDefinition", path) for path in FORBEARANCE_DURATION_ATTRIBUTES]
    display_attribute = unrealsdk.find_object("ResourcePoolAttributeDefinition", SHIELD_CAPACITY_ATTRIBUTE)
    if any(item is None for item in duration) or display_attribute is None:
        raise ValueError("Forbearance status-duration or presentation attributes are unavailable")
    targets, modes = unrealsdk.find_enum("EEffectTarget"), unrealsdk.find_enum("EModifierType")
    explosive_type = int(unrealsdk.find_enum("EDamageType").DAMAGE_TYPE_Explosive)
    desired = []
    for attribute, amount, target in [*(
            (attribute, FORBEARANCE_STATUS_DURATION_PER_RANK, targets.TARGET_Self) for attribute in duration),
            (display_attribute, FORBEARANCE_STEAL_PER_RANK, targets.TARGET_None)]:
        data = copy.copy(effects[0])
        data.AttributeToModify, data.EffectTarget, data.ModifierType = attribute, target, modes.MT_Scale
        data.GradeToStartApplyingEffect, data.PerGradeUpgradeInterval, data.BonusUpgradeList = 1, 1, []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(data, field))
            value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(data, field, value)
        desired.append(data)
    def same(before: Any, after: Any) -> bool:
        return (_effect_layout(before) == _effect_layout(after)
            and getattr(before, "GradeToStartApplyingEffect", None) == 1
            and getattr(before, "PerGradeUpgradeInterval", None) == 1
            and not getattr(before, "BonusUpgradeList", ())
            and all(getattr(before, field).BaseValueAttribute is None
                and getattr(before, field).InitializationDefinition is None
                and math.isclose(float(getattr(before, field).BaseValueScaleConstant), 1., abs_tol=1e-7)
                and math.isclose(float(getattr(before, field).BaseValueConstant),
                                 float(getattr(after, field).BaseValueConstant), rel_tol=1e-6, abs_tol=1e-7)
                for field in ("BaseModifierValue", "PerGradeUpgrade")))
    changed = len(effects) != len(desired) or any(not same(a, b) for a, b in zip(effects, desired))
    stats = []
    for name, attribute, text, inverse in (
            ("AR_StatusDuration", duration[0], "Status Effect Duration: $NUMBER$", False),
            ("AR_AreaLifeSteal", display_attribute, "Explosive and Area Damage Life Steal: $NUMBER$", False)):
        try:
            stat = unrealsdk.find_object("AttributePresentationDefinition", FORBEARANCE + ":" + name)
        except ValueError:
            stat = None
        if stat is None:
            template = unrealsdk.find_object("AttributePresentationDefinition",
                CRISIS_MANAGEMENT + ":AttributePresentationDefinition_53")
            stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                template_obj=template, flags=int(ObjectFlags.KEEP_ALIVE))
        if stat is None:
            raise ValueError("Forbearance presentation could not be created")
        stat.Attribute, stat.Description = attribute, text
        stat.bDisplayAsPercentage, stat.bDisplayAsInverse = True, inverse
        stat.bDisplayPercentAsFloat, stat.FloatPrecision = True, 1
        stat.RoundingMode = unrealsdk.find_enum("EAttributeInitializationRounding").ATTRROUNDING_Float
        stat.SignStyle = unrealsdk.find_enum("EAttributeValueSignStyle").SIGNSTYLE_AsIs
        stat.bDontDisplayPlusSign, stat.bUseCustomNumberPlacement = True, True
        stats.append(stat)
    if changed:
        definition.SkillEffectDefinitions = desired
    definition.SkillEffectPresentations = stats
    definition.DamageEvents, definition.KillEvents = [], []
    definition.BehaviorProviderDefinition = None
    definition.TrackedActiveSkills, definition.TrackedActiveSkill = [], None
    definition.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked
    definition.SkillDescription = (
        "Reduces the duration of enemy [skill]Elemental Status Effects[-skill] on you. "
        "Your [skill]Explosive Damage[-skill] and [skill]Area Damage[-skill] steal [skill]Health[-skill]. "
        "Your [skill]Sabre Turret's Explosive Damage[-skill] also steals Health for you.")
    _forbearance_address = int(definition._get_address())
    _forbearance_explosive_type = explosive_type
    try:
        legacy = unrealsdk.find_object("SkillDefinition", FORBEARANCE + ":AR_StatusResponse")
    except ValueError:
        legacy = None
    _forbearance_legacy_address = int(legacy._get_address()) if legacy is not None else 0
    return changed


def _clear_forbearance_radius() -> None:
    for index in range(len(_forbearance_radius_frames)):
        _forbearance_radius_frames[index] = None  # Preserve pending native POST pairing.


@hook("WillowGame.WillowPawn:TakeRadiusDamage", Type.PRE)
@hook("WillowGame.WillowPawn:BigBoyTakeRadiusDamage", Type.PRE)
@hook("WillowGame.WillowPawn:TakeRadiusDamageOnBones", Type.PRE)
def begin_forbearance_radius(target: Any, args: Any, _ret: Any, _func: Any) -> None:
    _forbearance_radius_frames.append(None)
    cached = _forbearance_context
    if cached is None:
        return
    try:
        instigator = args.InstigatedBy
        radius = float(args.DamageRadius)
        if (target is None or target.bDeleteMe or instigator is None or instigator.bDeleteMe
                or int(instigator._get_address()) != cached[0] or not math.isfinite(radius) or radius <= 0.):
            return
        world = target.WorldInfo
        if (world is None or world.bDeleteMe or world.Pauser or instigator.WorldInfo != world
                or int(world._get_address()) != cached[1]):
            return
        pipeline = args.Pipeline
        _forbearance_radius_frames[-1] = dict(target=WeakPointer(target), owner=WeakPointer(instigator),
            world=WeakPointer(world), pipeline=WeakPointer(pipeline) if pipeline is not None else None)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not track Forbearance area damage", exc)


@hook("WillowGame.WillowPawn:TakeRadiusDamage", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowPawn:BigBoyTakeRadiusDamage", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowPawn:TakeRadiusDamageOnBones", Type.POST_UNCONDITIONAL)
def finish_forbearance_radius(_target: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if _forbearance_radius_frames:
        _forbearance_radius_frames.pop()


def _bind_forbearance_radius_pipeline(pipeline: Any, args: Any) -> None:
    if _forbearance_context is None or not _forbearance_radius_frames or pipeline is None:
        return
    try:
        for frame in reversed(_forbearance_radius_frames):
            if (frame is not None and frame["pipeline"] is None
                    and frame["target"]() == args.InDamagedActor
                    and frame["owner"]() == args.InDamageInstigator):
                frame["pipeline"] = WeakPointer(pipeline)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not bind Forbearance area pipeline", exc)


def _forbearance_eligible_damage(pipeline: Any, args: Any, damage_type: Any) -> bool:
    if int(damage_type.DamageType) == _forbearance_explosive_type:
        return True
    if not _forbearance_radius_frames:
        return False
    target, owner = args.InDamagedActor, args.InDamageInstigator
    for frame in reversed(_forbearance_radius_frames):
        if (frame is not None and frame["pipeline"] is not None and frame["pipeline"]() == pipeline
                and frame["target"]() == target and frame["owner"]() == owner):
            world = frame["world"]()
            if world is not None and not world.bDeleteMe and target.WorldInfo == owner.WorldInfo == world:
                return True
    return False


def _forbearance_controller() -> Any | None:
    controller = get_pc(possibly_loading=True)
    if (controller is None or controller.bDeleteMe or controller.PlayerClass is None
            or _skill_path(controller.PlayerClass) != AXTON_CLASS):
        return None
    world, pawn = controller.WorldInfo, controller.Pawn
    if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
            or pawn.Controller != controller or pawn.IsInjuredDead()):
        return None
    identity = (int(controller._get_address()), int(world._get_address()))
    if _last_ditch_departing in (identity, (identity[0], 0)):
        return None
    return controller


def _restore_forbearance_from_player(pipeline: Any, args: Any, result: Any) -> None:
    """Own explosive/radial hits and owned turret explosive hits heal health."""
    global _forbearance_restoring
    cached = _forbearance_context
    if cached is None or _forbearance_restoring:
        return
    try:
        instigator = args.InDamageInstigator
        if instigator is None or instigator.bDeleteMe:
            return
        turret = None
        if int(instigator._get_address()) != cached[0]:
            turret = getattr(instigator, "Pawn", None)
            if (turret is None or turret.bDeleteMe
                    or _skill_path(getattr(turret, "Class", None)) != "WillowGame.DeployableTurretActor"):
                return
            owner = getattr(turret, "PlayerMaster", None)
            if owner is None or owner.bDeleteMe or int(owner._get_address()) != cached[0]:
                return  # Foreign turret/ally/AI damage never needs a local-player query.
        summary = result if result is not None else pipeline.DamageSummary
        health_damage, shield_damage = float(summary.FinalDamage), float(summary.DamageDealtToShields)
        if (not math.isfinite(health_damage) or not math.isfinite(shield_damage)
                or max(health_damage, shield_damage) <= 0.):
            return
        controller = _forbearance_controller()
        if controller is None or int(controller.Role) != _overload_authority_role:
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if instigator.WorldInfo != world:
            return
        if turret is not None:
            if turret.WorldInfo != world or turret.PlayerMaster != controller:
                return
        elif instigator != controller:
            return
        now = float(world.TimeSeconds)
        identity = (int(controller._get_address()), int(world._get_address()), int(pawn._get_address()))
        if identity != cached[:3] or not math.isfinite(now) or not 0. <= now-cached[4] <= 1.:
            return
        health, maximum = float(pawn.GetHealth()), float(pawn.GetMaxHealth())
        if (not math.isfinite(health) or not math.isfinite(maximum)
                or health <= 0. or maximum <= health):
            return  # No recovery needed: skip enemy opinion and damage-type calls.
        target = args.InDamagedActor
        if (target is None or target.bDeleteMe or target == pawn or target.WorldInfo != world
                or int(target.GetOpinion(pawn)) != _last_ditch_enemy_opinion):
            return
        damage_type = pipeline.GetDamageTypeDef()
        if damage_type is None or damage_type.IsHealingDamageType():
            return
        if turret is not None:
            if int(damage_type.DamageType) != _forbearance_explosive_type:
                return
        elif not _forbearance_eligible_damage(pipeline, args, damage_type):
            return
        budget = (max(0., health_damage) + max(0., shield_damage)) * FORBEARANCE_STEAL_PER_RANK * cached[3]
        if not math.isfinite(budget) or budget <= 0.:
            return
        _forbearance_restoring = True  # Reentrancy guard, not a time-based cooldown.
        try:
            pawn.SetHealth(min(maximum, health+budget))
        finally:
            _forbearance_restoring = False
        # No further actor accesses after SetHealth's native callbacks.
        key = "Forbearance player life steal"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(f"[AxtonRebalance] {key}: rank={cached[3]}, final_damage={health_damage+shield_damage:g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not apply Forbearance player life steal", exc)


def _sync_forbearance(controller: Any, manager: Any, skills: tuple[Any, ...],
                     context: tuple[int, int, int], now: float) -> bool:
    """Cache the effective native grade during the existing shared quarter-second pass."""
    global _forbearance_legacy_address, _forbearance_context
    _forbearance_context = None
    rank = 0
    for skill in skills:
        if skill.Definition is None or skill.SkillInstigator != controller:
            continue
        address = int(skill.Definition._get_address())
        if _forbearance_legacy_address and address == _forbearance_legacy_address:
            manager.DeactivateSkill(controller, skill.Definition)
            return False  # Never inspect the snapshot after a native callback.
        if address == _forbearance_address and skill.SkillState == _overload_active_state:
            rank = max(rank, int(skill.Grade))
    _forbearance_legacy_address = 0
    if rank > 0 and math.isfinite(now):
        _forbearance_context = (*context, rank, now)
    return True


def _configure_expertise() -> bool:
    """Own passive recoil formulas independently of Metal Storm's current effect array."""
    definition = unrealsdk.find_object("SkillDefinition", EXPERTISE)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    original_paths = ["D_Attributes.Weapon.WeaponSwapTimeMultiplier",
                      "D_Attributes.GameplayAttributes.PlayerZoomTimeModifier",
                      "D_Attributes.GameplayAttributes.FootSpeed"]
    if paths not in (original_paths, [*original_paths, None, RECOIL_ATTRIBUTE]):
        raise ValueError(f"Unexpected Expertise effects: {paths}")
    recoil_attribute = unrealsdk.find_object("AttributeDefinition", RECOIL_ATTRIBUTE)
    coefficient = unrealsdk.find_object("AttributeDefinition", RECOIL_COEFFICIENT)
    if recoil_attribute is None or coefficient is None:
        raise ValueError("Expertise recoil attributes are unavailable")
    templates = [item for item in definition.SkillEffectPresentations
                 if _effect_attribute_path_for_presentation(item) == original_paths[0]]
    if len(templates) != 1:
        raise ValueError("Expertise swap presentation was not identified")
    name = "AR_ExpertiseRecoil"
    try:
        presentation = unrealsdk.find_object("AttributePresentationDefinition", EXPERTISE + ":" + name)
    except ValueError:
        presentation = None
    if presentation is None:
        presentation = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                                                  template_obj=templates[0])
    changed = len(effects) == 3
    if changed:
        added = []
        targets = unrealsdk.find_enum("EEffectTarget")
        for display in (True, False):
            owned = copy.copy(effects[0])
            owned.AttributeToModify = None if display else recoil_attribute
            owned.EffectTarget = targets.TARGET_None if display else targets.TARGET_Self
            owned.bIncludeSelfAsTarget = False
            for field in ("BaseModifierValue", "PerGradeUpgrade"):
                value = copy.copy(getattr(effects[0], field))
                value.BaseValueConstant = -.15 if display else 0.0
                value.BaseValueAttribute = None if display else coefficient
                value.InitializationDefinition = None
                value.BaseValueScaleConstant = 1.0
                setattr(owned, field, value)
            added.append(owned)
        definition.SkillEffectDefinitions = [copy.copy(effect) for effect in effects] + added
    for field, value in (("Attribute", None), ("Description", "Recoil Reduction: $NUMBER$"),
                         ("bDisplayAsPercentage", True), ("bDisplayAsInverse", False)):
        if getattr(presentation, field) != value:
            setattr(presentation, field, value)
    presentations = list(definition.SkillEffectPresentations)
    if presentation not in presentations:
        definition.SkillEffectPresentations = [*presentations, presentation]
    description = (
        "Increases your [skill]Weapon Swap Speed[-skill] and [skill]Aim Speed[-skill], "
        "and reduces [skill]Recoil[-skill]. Also, your [skill]Movement Speed[-skill] "
        "is increased while aiming."
    )
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    return changed


def _configure_nuke() -> bool:
    """Keep the deployment blast and add native turret-only weapon effects."""
    definition = unrealsdk.find_object("SkillDefinition", NUKE)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    if paths not in ([None], [None, CRISIS_GUN_ATTRIBUTE, WEAPON_FIRE_INTERVAL]):
        raise ValueError(f"Unexpected Nuke effects: {paths}")
    if str(definition.EffectSourceInstanceDataName) != "Scorpio":
        raise ValueError("Nuke turret instance-data context was not identified")
    attributes = [unrealsdk.find_object("AttributeDefinition", path)
                  for path in (CRISIS_GUN_ATTRIBUTE, WEAPON_FIRE_INTERVAL)]
    if any(attribute is None for attribute in attributes):
        raise ValueError("Nuke turret weapon attributes are unavailable")
    target = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    mode = unrealsdk.find_enum("EModifierType").MT_Scale
    updated, changed = [copy.copy(effects[0])], len(effects) != 3
    for index, (attribute, amount) in enumerate(zip(attributes, (NUKE_TURRET_DAMAGE_BONUS, NUKE_FIRE_INTERVAL_PENALTY)),1):
        original = effects[index] if len(effects) == 3 else None
        owned = copy.copy(effects[0])
        owned.AttributeToModify, owned.EffectTarget, owned.ModifierType = attribute, target, mode
        owned.bIncludeSelfAsTarget = False
        changed |= original is None or original.EffectTarget != target or original.ModifierType != mode
        for field, coefficient in (("BaseModifierValue", amount), ("PerGradeUpgrade", 0.)):
            value = copy.copy(getattr(effects[0], field))
            value.BaseValueConstant, value.BaseValueScaleConstant = coefficient, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(owned, field, value)
            if original is not None:
                current = getattr(original, field)
                changed |= (not math.isclose(float(current.BaseValueConstant),coefficient)
                            or current.BaseValueAttribute is not None or current.InitializationDefinition is not None
                            or float(current.BaseValueScaleConstant) != 1.)
        updated.append(owned)
    if changed:
        definition.SkillEffectDefinitions = updated
    description = (
        "Deploying your [skill]Sabre Turret[-skill] sets off a small [skill]Nuclear Blast[-skill]. "
        "Increases your turret's [skill]Damage[-skill] but reduces its [skill]Fire Rate[-skill]."
    )
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    _disable_nuke_knockback()
    return changed


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_nuke(_tree: Any, args: Any, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or _skill_path(args.SkillDef) != NUKE:
        return None
    learned = int(args.Grade) > 0
    values = (f"+{100 * NUKE_TURRET_DAMAGE_BONUS if learned else 0:g}%",
              f"-{100 * NUKE_FIRE_INTERVAL_PENALTY if learned else 0:g}%")
    owner = getattr(args,"PlayerOwner",None)
    if args.bIncludeHTML and learned and owner is not None and int(owner.GetSkillGrade(args.SkillDef)) > 0:
        values = tuple(f'<font color="#00FF00">{value}</font>' for value in values)
    return Block, ("<br>" if args.bIncludeHTML else "\n").join(
        (f"Turret Damage: {values[0]}",f"Turret Fire Rate: {values[1]}"))


def _configure_double_up() -> bool:
    global _double_up_definition_address, _double_up_active_state, _double_up_friendly_opinion
    global _last_ditch_authority_role, _last_ditch_enemy_opinion
    definition = unrealsdk.find_object("SkillDefinition", DOUBLE_UP)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    allowed = (None, RELOAD_ATTRIBUTE, TURRET_DAMAGE_TYPE_SELECTOR, CRISIS_GUN_ATTRIBUTE,
               RESOURCEFUL_COOLDOWN_ATTRIBUTE)
    if (any(path not in allowed for path in paths) or paths.count(TURRET_DAMAGE_TYPE_SELECTOR) != 1
            or sum(path in (None, RELOAD_ATTRIBUTE) for path in paths) != 1
            or paths.count(RESOURCEFUL_COOLDOWN_ATTRIBUTE) > 1):
        raise ValueError(f"Unexpected Double Up effects: {paths}")
    damage = unrealsdk.find_object("AttributeDefinition", CRISIS_GUN_ATTRIBUTE)
    cooldown = unrealsdk.find_object("AttributeDefinition", RESOURCEFUL_COOLDOWN_ATTRIBUTE)
    template = unrealsdk.find_object("AttributePresentationDefinition",
        RESOURCEFUL + ":AttributePresentationDefinition_0")
    templates = [template] if template is not None else []
    if cooldown is None or damage is None or len(templates) != 1:
        raise ValueError("Double Up cooldown attribute/presentation is unavailable")
    target = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    mode = unrealsdk.find_enum("EModifierType").MT_Scale
    active = int(unrealsdk.find_enum("ESkillState").SKILL_Active)
    authority = int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
    opinions = unrealsdk.find_enum("EOpinion")
    _prepare_last_ditch_attributes(definition)
    current = next((effect for effect in effects
                    if _effect_attribute_path(effect) == RESOURCEFUL_COOLDOWN_ATTRIBUTE), None)
    added = copy.copy(effects[0])
    added.AttributeToModify, added.EffectTarget, added.ModifierType = cooldown, target, mode
    added.bIncludeSelfAsTarget = False
    for field, amount in (("BaseModifierValue", DOUBLE_UP_COOLDOWN), ("PerGradeUpgrade", 0.)):
        value = copy.copy(getattr(effects[0], field))
        value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.0
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(added, field, value)
    changed = current is None or current.EffectTarget != target or current.ModifierType != mode
    if current is not None:
        changed |= any(not math.isclose(float(getattr(current, field).BaseValueConstant), amount)
                       or getattr(current, field).BaseValueAttribute is not None
                       or getattr(current, field).InitializationDefinition is not None
                       or float(getattr(current, field).BaseValueScaleConstant) != 1.0
                       for field, amount in (("BaseModifierValue", DOUBLE_UP_COOLDOWN), ("PerGradeUpgrade", 0.)))
    name = "AR_DoubleUpCooldown"
    try:
        stat = unrealsdk.find_object("AttributePresentationDefinition", DOUBLE_UP + ":" + name)
    except ValueError:
        stat = None
    if stat is None:
        stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                                          template_obj=templates[0])
    if str(stat.Description) != "Cooldown Rate: $NUMBER$":
        stat.Description = "Cooldown Rate: $NUMBER$"
    current_penalties = [effect for effect in effects if _effect_attribute_path(effect) == CRISIS_GUN_ATTRIBUTE]
    if len(current_penalties) > 1:
        raise ValueError("Duplicate Double Up turret damage penalties")
    penalty = copy.copy(current_penalties[0] if current_penalties else effects[0])
    penalty.AttributeToModify, penalty.EffectTarget, penalty.ModifierType = damage, target, mode
    penalty.TargetInstanceDataName = "Scorpio"  # Native per-effect target, never the player's gun.
    penalty.bIncludeSelfAsTarget = False
    for field, amount in (("BaseModifierValue", -DOUBLE_UP_DAMAGE_PENALTY), ("PerGradeUpgrade", 0.)):
        value = copy.copy(getattr(penalty, field))
        value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(penalty, field, value)
    if not current_penalties:
        changed = True
    else:
        old = current_penalties[0]
        changed |= (old.EffectTarget != target or old.ModifierType != mode
                    or str(old.TargetInstanceDataName) != "Scorpio" or any(
            not math.isclose(float(getattr(old, field).BaseValueConstant), amount, abs_tol=1e-7)
            or float(getattr(old, field).BaseValueScaleConstant) != 1.
            or getattr(old, field).BaseValueAttribute is not None
            or getattr(old, field).InitializationDefinition is not None
            for field, amount in (("BaseModifierValue", -DOUBLE_UP_DAMAGE_PENALTY), ("PerGradeUpgrade", 0.))))
    if changed:
        definition.SkillEffectDefinitions = [copy.copy(effect) for effect in effects
            if _effect_attribute_path(effect) not in (RESOURCEFUL_COOLDOWN_ATTRIBUTE, CRISIS_GUN_ATTRIBUTE)] + [penalty, added]
    presentations = list(definition.SkillEffectPresentations)
    if stat not in presentations:
        definition.SkillEffectPresentations = [*presentations, stat]
    description = (
        "Adds a second gun to your [skill]Sabre Turret[-skill] and both guns fire [skill]Slag bullets[-skill]. "
        "Reduces your [skill]Turret Damage[-skill] and increases your [skill]Cooldown Rate[-skill]. Enemies hit by your turret take "
        "[skill]increased damage from you and your allies[-skill] for a short time. "
        "Further turret hits refresh this effect."
    )
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    _double_up_definition_address = int(definition._get_address())
    _double_up_active_state = active
    _double_up_friendly_opinion = int(opinions.OPINION_Friendly)
    _last_ditch_authority_role, _last_ditch_enemy_opinion = authority, int(opinions.OPINION_Enemy)
    return changed


def _configure_gemini() -> bool:
    global _gemini_ready
    definition = unrealsdk.find_object("SkillDefinition", GEMINI)
    laser = unrealsdk.find_object("SkillDefinition", LASER_SIGHT)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(item) for item in effects]
    if (paths not in ([None], [None, WEAPON_FIRE_INTERVAL, CRISIS_RESISTANCE_ATTRIBUTES[0]])
            or float(effects[0].BaseModifierValue.BaseValueConstant) != 2.):
        raise ValueError("Unexpected Gemini turret-count effect")
    template = next(item for item in laser.SkillEffectDefinitions
                    if _effect_attribute_path(item) == WEAPON_SPREAD)
    fire = unrealsdk.find_object("AttributeDefinition", WEAPON_FIRE_INTERVAL)
    resistance = [unrealsdk.find_object("AttributeDefinition", path)
                  for path in CRISIS_RESISTANCE_ATTRIBUTES]
    if fire is None or any(attribute is None for attribute in resistance):
        raise ValueError("Gemini fire-rate/resistance attributes are unavailable")
    scale = unrealsdk.find_enum("EModifierType").MT_Scale
    targets = unrealsdk.find_enum("EEffectTarget")
    tracked = unrealsdk.find_enum("ETrackedSkillType")
    def data(attribute: Any, display: bool = False, amount: float = .20) -> Any:
        item = copy.copy(template)
        item.AttributeToModify, item.ModifierType = attribute, scale
        item.EffectTarget = targets.TARGET_None if display else targets.TARGET_Self
        for field, value_amount in (("BaseModifierValue", -amount), ("PerGradeUpgrade", 0.)):
            value = copy.copy(getattr(item, field))
            value.BaseValueConstant, value.BaseValueScaleConstant = value_amount, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(item, field, value)
        return item
    def private(name: str, source: Any, gameplay: list[Any]) -> Any:
        try:
            helper = unrealsdk.find_object("SkillDefinition", GEMINI + ":" + name)
        except ValueError:
            helper = None
        if helper is None:
            helper = unrealsdk.construct_object("SkillDefinition", definition, name,
                template_obj=source, flags=int(ObjectFlags.KEEP_ALIVE))
        helper.SkillEffectDefinitions = gameplay
        helper.SkillEffectPresentations = []
        helper.BehaviorProviderDefinition = None
        helper.DamageEvents = []
        helper.KillEvents = []
        helper.TrackedActiveSkills = []
        helper.TrackedActiveSkill = None
        helper.CustomStackCount = None
        helper.TrackedSkillType = tracked.TRACKEDSKILL_Untracked
        helper.bSubjectToGradeRules = False
        helper.MaxGrade = 1
        return helper
    turret = private("AR_TurretFire", laser, [data(fire)])
    turret.EffectSourceInstanceDataName = "Scorpio"
    private("AR_DefensiveAura", definition, [data(attribute, amount=GEMINI_DAMAGE_REDUCTION) for attribute in resistance])
    hud = private("AR_AuraHUD", definition, [])
    hud.SkillConstraints = []
    hud.SkillIcon = definition.SkillIcon
    hud.SkillName = "Gemini defensive aura"
    hud.TrackedSkillType = tracked.TRACKEDSKILL_Triggered
    stats = list(definition.SkillEffectPresentations[:1])
    presentation = unrealsdk.find_object("AttributePresentationDefinition",
        CRISIS_MANAGEMENT + ":AttributePresentationDefinition_53")
    for name, attribute, text in (
        ("AR_GeminiFireRate", fire, "Turret Fire Rate: $NUMBER$"),
        ("AR_GeminiResistance", resistance[0], f"Aura Damage Reduction: $NUMBER$<br>Aura Radius: {GEMINI_AURA_RADIUS/100.:g} meters")):
        try:
            stat = unrealsdk.find_object("AttributePresentationDefinition", GEMINI + ":" + name)
        except ValueError:
            stat = None
        if stat is None:
            stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                template_obj=presentation)
        stat.Attribute, stat.Description = attribute, text
        stats.append(stat)
    changed = (not _gemini_ready or len(effects) != 3 or not math.isclose(
        float(effects[2].BaseModifierValue.BaseValueConstant), -GEMINI_DAMAGE_REDUCTION, abs_tol=1e-7))
    if changed:
        definition.SkillEffectDefinitions = [copy.copy(effects[0]), data(fire, True), data(resistance[0], True, GEMINI_DAMAGE_REDUCTION)]
    definition.SkillEffectPresentations = stats
    definition.SkillDescription = (
        "Allows you to deploy [skill]two Sabre Turrets[-skill]. Once the first turret is deployed, "
        "press <StringAliasMap:Action.ActionSkill> again to deploy the second. Your turrets gain "
        "[skill]Fire Rate[-skill] and project a [skill]defensive aura[-skill] that reduces damage "
        "taken by you and allies nearby. Overlapping auras do not stack.")
    _gemini_ready = True
    return changed



def _configure_turret_health() -> bool:
    """Redistribute native Longbow health into the turret base without compounding."""
    character = unrealsdk.find_object("AIClassDefinition", TURRET_HEALTH_CLASS)
    resolver = unrealsdk.find_object("ConstantAttributeValueResolver", LONG_BOW_HEALTH_RESOLVER)
    rows = list(character.AttributeStartingValues)
    matches = [index for index,row in enumerate(rows) if row.Attribute is not None
               and _skill_path(row.Attribute) == TURRET_HEALTH_MULTIPLIER_ATTRIBUTE]
    if len(matches) != 1:
        raise ValueError("Sabre Turret base health starting value is missing or duplicated")
    index = matches[0]
    base = rows[index].BaseValue
    scale, constant, longbow = float(base.BaseValueScaleConstant), float(base.BaseValueConstant), float(resolver.ConstantValue)
    desired = TURRET_NATIVE_HEALTH_SCALE * TURRET_BASE_HEALTH_FACTOR
    if (not all(math.isfinite(value) for value in (scale,constant,longbow))
            or not math.isclose(constant,1.,rel_tol=0.,abs_tol=1e-7)
            or base.BaseValueAttribute is not None or base.InitializationDefinition is not None
            or not any(math.isclose(scale,value,rel_tol=1e-6) for value in (TURRET_NATIVE_HEALTH_SCALE,desired))):
        raise ValueError("Unexpected Sabre Turret base health formula; no partial Longbow change applied")
    health_dirty = not math.isclose(scale,desired,rel_tol=1e-6)
    longbow_dirty = not math.isclose(longbow,LONG_BOW_HEALTH_BONUS,rel_tol=0.,abs_tol=1e-7)
    original_base = copy.copy(base)
    try:
        if health_dirty:
            detached = [copy.copy(row) for row in rows]
            value = copy.copy(base)
            value.BaseValueScaleConstant = desired
            detached[index].BaseValue = value
            character.AttributeStartingValues = detached
        if not math.isclose(float(character.AttributeStartingValues[index].BaseValue.BaseValueScaleConstant),desired,rel_tol=1e-6):
            raise ValueError("Sabre Turret base health did not retain its value; Longbow was not reduced")
        if longbow_dirty:
            resolver.ConstantValue = LONG_BOW_HEALTH_BONUS
        if (not math.isclose(float(character.AttributeStartingValues[index].BaseValue.BaseValueScaleConstant),desired,rel_tol=1e-6)
                or not math.isclose(float(resolver.ConstantValue),LONG_BOW_HEALTH_BONUS,rel_tol=0.,abs_tol=1e-7)):
            raise ValueError("Sabre Turret/Longbow health values were not retained")
    except (AttributeError, TypeError, ValueError, RuntimeError):
        scalar_restored = not longbow_dirty
        if longbow_dirty:
            try:
                if math.isclose(float(resolver.ConstantValue),LONG_BOW_HEALTH_BONUS,rel_tol=0.,abs_tol=1e-7):
                    resolver.ConstantValue = longbow
                scalar_restored = math.isclose(float(resolver.ConstantValue),longbow,rel_tol=0.,abs_tol=1e-7)
                if not scalar_restored:
                    raise ValueError("Longbow health rollback was rejected or changed externally")
            except (AttributeError, TypeError, ValueError, RuntimeError) as cleanup:
                _last_ditch_error("Could not roll back Longbow health", cleanup)
        if health_dirty and scalar_restored:
            try:
                fresh = list(character.AttributeStartingValues)
                for at,row in enumerate(fresh):
                    if row.Attribute is None or _skill_path(row.Attribute) != TURRET_HEALTH_MULTIPLIER_ATTRIBUTE:
                        continue
                    current = row.BaseValue
                    if (math.isclose(float(current.BaseValueScaleConstant),desired,rel_tol=1e-6)
                            and math.isclose(float(current.BaseValueConstant),constant,rel_tol=0.,abs_tol=1e-7)
                            and current.BaseValueAttribute is None and current.InitializationDefinition is None):
                        rollback = [copy.copy(item) for item in fresh]
                        rollback[at].BaseValue = copy.copy(original_base)
                        character.AttributeStartingValues = rollback
                        restored = character.AttributeStartingValues[at].BaseValue
                        if (not math.isclose(float(restored.BaseValueScaleConstant),scale,rel_tol=1e-6)
                                or not math.isclose(float(restored.BaseValueConstant),constant,rel_tol=0.,abs_tol=1e-7)
                                or restored.BaseValueAttribute is not None or restored.InitializationDefinition is not None):
                            raise ValueError("Sabre Turret health rollback was rejected")
                    break
            except (AttributeError, TypeError, ValueError, RuntimeError) as cleanup:
                _last_ditch_error("Could not roll back turret base health", cleanup)
        raise
    return health_dirty or longbow_dirty


def _prepare_turret_health(controller: Any = None) -> None:
    global _turret_health_checked_context, _turret_health_checked_until
    world = getattr(controller, "WorldInfo", None) if controller is not None else None
    context: tuple[int, int] | None = None
    if controller is not None and world is not None and not world.bDeleteMe and not controller.bDeleteMe:
        context = (int(controller._get_address()),int(world._get_address()))
    now = time.monotonic()
    if context is not None and context == _turret_health_checked_context and now < _turret_health_checked_until:
        return  # ServerStartActionSkill and OnActionSkillStarted can describe the same deployment.
    try:
        if _configure_turret_health():
            unrealsdk.logging.info("[AxtonRebalance] Sabre Turret base health +40%; Longbow health +50%; combined factor 2.1 preserved")
        _turret_health_checked_context, _turret_health_checked_until = context,now + .25
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _turret_health_checked_context, _turret_health_checked_until = None,0.
        _last_ditch_error("Could not configure Sabre Turret/Longbow health", exc)


def _configure_turret_throw_descriptions() -> bool:
    longbow = unrealsdk.find_object("SkillDefinition", LONG_BOW)
    mag_lock = unrealsdk.find_object("SkillDefinition", MAG_LOCK)
    description = (
        "Your [skill]Sabre Turret[-skill] can be deployed using [skill]Longbow[-skill] technology, "
        "allowing you to deploy it much further away. Also increases the [skill]Maximum Health[-skill] "
        "of your [skill]Sabre Turret[-skill]."
    )
    changed = False
    # Presentation must not depend on the availability of gameplay attributes.
    for skill, text in ((longbow, description), (mag_lock, MAG_LOCK_DESCRIPTION)):
        if str(skill.SkillDescription) != text:
            skill.SkillDescription = text
            changed = True
    return changed


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_turret_upgrades(_tree: Any, args: Any, _ret: Any, func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None:
        return None
    path = _skill_path(args.SkillDef)
    if path not in (DOUBLE_UP, MAG_LOCK):
        return None
    original = ""
    if path != MAG_LOCK:
        with prevent_hooking_direct_calls():
            original = func(args)  # Retain native lines for the unchanged upgrades.
    learned = int(args.Grade) > 0
    bonus = {DOUBLE_UP: DOUBLE_UP_VULNERABILITY, MAG_LOCK: TURRET_THROW_SPEED_FACTOR - 1.}[path]
    value = f"+{100. * bonus if learned else 0.:g}%"
    penalty_value = f"-{100. * DOUBLE_UP_DAMAGE_PENALTY if learned else 0.:g}%"
    refund_value = f"{100. * MAG_LOCK_DEATH_REFUND if learned else 0.:g}%"
    owner = args.PlayerOwner
    if args.bIncludeHTML and learned and owner is not None and int(owner.GetSkillGrade(args.SkillDef)) > 0:
        value = f'<font color="#00FF00">{value}</font>'
        penalty_value = f'<font color="#00FF00">{penalty_value}</font>'
        refund_value = f'<font color="#00FF00">{refund_value}</font>'
    rows = ([f"Marked Enemy Damage Taken: {value}", f"Mark Duration: {DOUBLE_UP_DEBUFF_SECONDS:g} seconds",
             f"Turret Damage: {penalty_value}"]
            if path == DOUBLE_UP else [f"Turret Throw Speed: {value}",
                                      f"Cooldown Refund on Turret Destruction: {refund_value}"])
    separator = "<br>" if args.bIncludeHTML else "\n"
    return Block, separator.join([*([original] if original else []), *rows])



def _mag_lock_threat_attribute(definition: Any) -> Any:
    try:
        attribute = unrealsdk.find_object("AttributeDefinition", MAG_LOCK_PRIVATE_THREAT_ATTRIBUTE)
    except ValueError:
        attribute = None
    if attribute is None:
        try:
            native = unrealsdk.find_object("AttributeDefinition", MAG_LOCK_THREAT_ATTRIBUTE)
        except ValueError:
            native = None
        if native is not None:
            return native
        attribute = unrealsdk.construct_object("AttributeDefinition",definition,"AR_ThreatPriority",
                                              flags=int(ObjectFlags.KEEP_ALIVE))
    if attribute is None:
        raise ValueError("Mag-Lock private threat attribute could not be created")
    def obtain(kind: str, name: str) -> Any:
        path = MAG_LOCK_PRIVATE_THREAT_ATTRIBUTE + "." + name
        try:
            obj = unrealsdk.find_object(kind,path)
        except ValueError:
            obj = None
        if obj is None:
            obj = unrealsdk.construct_object(kind,attribute,name,flags=int(ObjectFlags.KEEP_ALIVE))
        if obj is None:
            raise ValueError("Mag-Lock threat resolver could not be created: " + path)
        return obj
    context = obtain("PawnAttributeContextResolver","PawnContext")
    resolver = obtain("ObjectPropertyAttributeValueResolver","PriorityValue")
    resolver.PropertyName = "TargetPriority"  # Verified native threat attribute's property.
    attribute.bIsSimpleAttribute = False
    attribute.AttributeDataType = unrealsdk.find_enum("EAttributeDataType").ADT_Float
    attribute.ContextResolverChain, attribute.ValueResolverChain = [context],[resolver]
    return attribute


def _configure_mag_lock() -> bool:
    definition = unrealsdk.find_object("SkillDefinition", MAG_LOCK)
    if definition is None:
        raise ValueError("Mag-Lock definition is unavailable")
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(item) for item in effects]
    if paths not in ([None], [None, RESOURCEFUL_COOLDOWN_ATTRIBUTE],
                     [MAG_LOCK_RANGE_ATTRIBUTE, MAG_LOCK_SIGHT_ATTRIBUTE, MAG_LOCK_THREAT_ATTRIBUTE], [MAG_LOCK_THREAT_ATTRIBUTE], [MAG_LOCK_PRIVATE_THREAT_ATTRIBUTE]):
        raise ValueError("Unexpected Mag-Lock effects")
    laser = unrealsdk.find_object("SkillDefinition", LASER_SIGHT)
    if laser is None:
        raise ValueError("Mag-Lock turret effect template is unavailable")
    templates = [item for item in laser.SkillEffectDefinitions if _effect_attribute_path(item) == WEAPON_SPREAD]
    if len(templates) != 1:
        raise ValueError("Mag-Lock turret effect template was not uniquely identified")
    template = templates[0]
    threat = _mag_lock_threat_attribute(definition)
    if threat is None:
        raise ValueError("Mag-Lock native threat attribute is unavailable")
    desired_paths = [_skill_path(threat)]
    modes = unrealsdk.find_enum("EModifierType")
    desired = []
    for attribute, amount, mode in ((threat, MAG_LOCK_THREAT_BONUS, modes.MT_PostAdd),):
        data = copy.copy(template)
        data.AttributeToModify, data.ModifierType = attribute, mode
        for field, value in (("BaseModifierValue", amount), ("PerGradeUpgrade", 0.)):
            owned = copy.copy(getattr(template, field))
            owned.BaseValueConstant, owned.BaseValueScaleConstant = value, 1.
            owned.BaseValueAttribute = owned.InitializationDefinition = None
            setattr(data, field, owned)
        desired.append(data)
    changed = paths != desired_paths or str(definition.EffectSourceInstanceDataName) != "Scorpio"
    if not changed:
        changed = any(old.ModifierType != new.ModifierType or old.EffectTarget != new.EffectTarget
            or any(float(getattr(old, field).BaseValueConstant) != float(getattr(new, field).BaseValueConstant)
                   or float(getattr(old, field).BaseValueScaleConstant) != 1.
                   or getattr(old, field).BaseValueAttribute is not None
                   or getattr(old, field).InitializationDefinition is not None
                   for field in ("BaseModifierValue", "PerGradeUpgrade"))
            for old, new in zip(effects, desired))
    if changed:
        definition.SkillEffectDefinitions = desired
    if str(definition.EffectSourceInstanceDataName) != "Scorpio":
        definition.EffectSourceInstanceDataName = "Scorpio"
    if definition.SkillEffectPresentations:
        definition.SkillEffectPresentations = []
        changed = True
    description = MAG_LOCK_DESCRIPTION
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
        changed = True
    return changed



@hook("WillowGame.DeployableTurretActor:PostBeginPlay", Type.POST)
def observe_gemini_turret(turret: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if turret is not None and not turret.bDeleteMe:
        if len(_gemini_turrets) >= 64:
            _gemini_turrets.pop(next(iter(_gemini_turrets)))
        _gemini_turrets[int(turret._get_address())] = WeakPointer(turret)


def _gemini_aura_covers(location: Any, centers: tuple[Any, ...]) -> bool:
    return any(sum((float(getattr(location, axis)) - float(getattr(center, axis))) ** 2
                   for axis in ("X", "Y", "Z")) <= GEMINI_AURA_RADIUS ** 2 for center in centers)


def _gemini_hud_slot(controller: Any, manager: Any, movie: Any, feedback: Any) -> int | None:
    occupied: set[int] = set()
    visited: set[int] = set()
    def reserve(definition: Any) -> None:
        if definition is None or definition == feedback:
            return
        address = int(definition._get_address())
        if address in visited:
            return
        if len(visited) >= 512:
            raise RuntimeError("Gemini HUD tracked-skill graph exceeded its limit")
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
                and int(entry.SkillDef.TrackedSkillType) in (2, 3, 5, 6)
                and int(entry.RemappedSlot) >= 0):
            occupied.add(int(entry.RemappedSlot))
    tree = controller.PlayerSkillTree
    if tree is not None:
        for item in tree.Skills:
            if int(item.Grade) > 0:
                reserve(item.Definition)
    for skill in manager.ActiveSkills:
        reserve(skill.Definition)
    own_active = manager.IsSkillActive(controller, feedback)
    own_slot = int(movie.GetRemappedSlot(feedback))
    for slot, entry in enumerate(movie.CachedTSkillIcon_TrigResp):
        if entry.Icon is not None and not (own_active and slot == own_slot and entry.Icon == feedback.SkillIcon):
            occupied.add(slot)
    capacity = min(11, len(movie.CachedTSkillIcon_TrigResp))
    preferred = int(feedback.TrackedSkillHUDSlot)
    if 0 <= preferred < capacity and preferred not in occupied:
        return preferred
    return next((slot for slot in range(capacity) if slot not in occupied), None)


def _hide_gemini_hud(controller: Any, manager: Any, feedback: Any) -> None:
    reference = WeakPointer(controller)
    manager.DeactivateSkill(controller, feedback)
    live = reference()
    if live is None or live.bDeleteMe:
        return
    world = live.WorldInfo
    if world is None or world.bDeleteMe or world.Pauser or live.IsPauseMenuOpen():
        return
    movie = live.GetHUDMovie()
    if movie is not None:
        movie.UpdateSkillIcons()


def _sync_native_feedback(controller: Any, manager: Any, feedback: Any, count: int,
                          next_check: float) -> tuple[float, bool]:
    """A visual-only skill; return whether native callbacks invalidated the snapshot."""
    active = manager.IsSkillActive(controller, feedback)
    if count <= 0:
        next_check = 0.0
        if active:
            _hide_gemini_hud(controller, manager, feedback)
            return next_check, True
        return next_check, False
    if controller.IsPauseMenuOpen():
        return next_check, False
    movie = controller.GetHUDMovie()
    if movie is None:
        return next_check, False
    if active:
        for skill in manager.ActiveSkills:
            if skill.Definition == feedback and skill.SkillInstigator == controller and int(skill.Grade) != count:
                skill.UpdateGrade(count)
                return next_check, True
    mapped = int(movie.GetRemappedSlot(feedback))
    now = time.monotonic()
    if (active and now < next_check and mapped == int(feedback.TrackedSkillHUDSlot)
            and 0 <= mapped < len(movie.CachedTSkillIcon_TrigResp)
            and movie.CachedTSkillIcon_TrigResp[mapped].Icon == feedback.SkillIcon):
        return next_check, False
    next_check = now + 1.0
    slot = _gemini_hud_slot(controller, manager, movie, feedback)
    if slot is None:
        if active:
            _hide_gemini_hud(controller, manager, feedback)
            return next_check, True
        return next_check, False
    if active and (int(feedback.TrackedSkillHUDSlot) != slot or int(movie.GetRemappedSlot(feedback)) != slot):
        _hide_gemini_hud(controller, manager, feedback)
        return next_check, True  # Re-register next pass after native callbacks.
    if int(feedback.TrackedSkillHUDSlot) != slot:
        feedback.TrackedSkillHUDSlot = slot
    if not any(entry.SkillDef == feedback for entry in movie.AvailableTrackedSkills):
        movie.AddTrackedSkill(feedback)
        slot = _gemini_hud_slot(controller, manager, movie, feedback)
        if slot is None:
            return next_check, False
        feedback.TrackedSkillHUDSlot = slot
    if int(movie.GetRemappedSlot(feedback)) != slot:
        entries = [copy.copy(item) for item in movie.AvailableTrackedSkills]
        for entry in entries:
            if entry.SkillDef == feedback:
                entry.RemappedSlot = slot
        movie.AvailableTrackedSkills = entries
        if int(movie.GetRemappedSlot(feedback)) != slot:
            raise RuntimeError("Skill HUD slot remapping was not retained")
    purchased = max(int(movie.NumPurchasedTrigRespSlots), slot + 1)
    if int(movie.NumPurchasedTrigRespSlots) != purchased:
        movie.NumPurchasedTrigRespSlots = purchased
    if not active:
        if manager.ActivateSkill(controller, feedback, None, count) is False:
            raise RuntimeError("Skill HUD activation was rejected")
        return next_check, True
    if movie.CachedTSkillIcon_TrigResp[slot].Icon != feedback.SkillIcon:
        movie.UpdateSkillIcons()

    return next_check, False


def _sync_gemini_hud(controller: Any, manager: Any, inside: bool) -> None:
    global _gemini_hud_next_check
    feedback = unrealsdk.find_object("SkillDefinition", GEMINI_HUD)
    _gemini_hud_next_check, _ = _sync_native_feedback(
        controller, manager, feedback, 1 if inside else 0, _gemini_hud_next_check)


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def maintain_gemini_aura(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _gemini_next_tick, _gemini_world
    if not _gemini_ready or controller is None:
        return
    now = time.monotonic()
    if now < _gemini_next_tick or controller != get_pc(possibly_loading=True):
        return
    _gemini_next_tick = now + .25
    try:
        world, pawn = controller.WorldInfo, controller.Pawn
        if (controller.bDeleteMe or world is None or world.bDeleteMe or world.Pauser
                or pawn is None or pawn.bDeleteMe or pawn.Controller != controller):
            return
        world_id = int(world._get_address())
        if world_id == _gemini_departing:
            return
        manager = controller.GetSkillManager()
        if manager is None or manager.bUpdatingSkills:
            return
        aura = unrealsdk.find_object("SkillDefinition", GEMINI_AURA)
        fire = unrealsdk.find_object("SkillDefinition", GEMINI_FIRE)
        if int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority):
            _sync_gemini_hud(controller, manager, manager.IsSkillActive(controller, aura))
            return
        players = {int(controller._get_address()): controller}
        gri = world.GRI
        if gri is not None:
            for pri in tuple(gri.PRIArray)[:16]:
                owner = pri.Owner if pri is not None else None
                if owner is not None and not owner.bDeleteMe and hasattr(owner, "PlayerClass") and owner.WorldInfo == world:
                    players[int(owner._get_address())] = owner
        for address, reference in tuple(_gemini_recipients.items()):
            owner = reference()
            if owner is None or owner.bDeleteMe or owner.WorldInfo != world:
                _gemini_recipients.pop(address, None)
            else:
                players.setdefault(address, owner)
        definition = unrealsdk.find_object("SkillDefinition", GEMINI)
        owners = {address for address, owner in players.items()
                  if owner.PlayerClass is not None and _skill_path(owner.PlayerClass) == AXTON_CLASS
                  and int(owner.GetSkillGrade(definition)) > 0}
        # Snapshot contains only primitive owner identities once callbacks can run.
        applied = {(int(skill.SkillInstigator._get_address()), int(skill.Definition._get_address()))
                   for skill in manager.ActiveSkills
                   if skill.Definition in (aura, fire) and skill.SkillInstigator is not None}
        if not owners and not applied:
            _gemini_next_tick = now + 1.0
            _sync_gemini_hud(controller, manager, False)
            return
        if _gemini_world != world_id:
            _gemini_world = world_id
            _gemini_recipients.clear()
            # One bootstrap walk per relevant world, not a global scan each tick.
            current, visited = world.PawnList, set()
            while current is not None and len(visited) < 1024:
                address = int(current._get_address())
                if address in visited:
                    break
                visited.add(address)
                if not current.bDeleteMe and _skill_path(current.Class) == "WillowGame.DeployableTurretActor":
                    _gemini_turrets[address] = WeakPointer(current)
                current = current.NextPawn
        for address, owner in players.items():
            wanted, present = address in owners, (address, int(fire._get_address())) in applied
            if wanted != present:
                if wanted:
                    _gemini_recipients[address] = WeakPointer(owner)
                    if manager.ActivateSkill(owner, fire, None, 1) is False:
                        raise RuntimeError("Gemini turret fire-rate activation was rejected")
                else:
                    manager.DeactivateSkill(owner, fire)
                return
        centers: list[tuple[Any, Any]] = []
        for address, reference in tuple(_gemini_turrets.items()):
            turret = reference()
            if turret is None or turret.bDeleteMe or turret.WorldInfo != world or turret.IsInjuredDead():
                _gemini_turrets.pop(address, None)
                continue
            owner = turret.PlayerMaster
            if (owner is not None and int(owner._get_address()) in owners and owner.Pawn is not None
                    and not owner.Pawn.bDeleteMe):
                centers.append((owner, turret.Location))
        friendly = int(unrealsdk.find_enum("EOpinion").OPINION_Friendly)
        for address, recipient in players.items():
            target = recipient.Pawn
            covered = False
            if target is not None and not target.bDeleteMe and not target.IsInjuredDead():
                allowed = tuple(location for owner, location in centers
                                if owner == recipient or int(target.GetOpinion(owner.Pawn)) == friendly)
                covered = _gemini_aura_covers(target.Location, allowed)
            present = (address, int(aura._get_address())) in applied
            if covered != present:
                if covered:
                    _gemini_recipients[address] = WeakPointer(recipient)
                    if manager.ActivateSkill(recipient, aura, None, 1) is False:
                        raise RuntimeError("Gemini defensive aura activation was rejected")
                else:
                    manager.DeactivateSkill(recipient, aura)
                return
        try:
            _sync_gemini_hud(controller, manager, manager.IsSkillActive(controller, aura))
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _last_ditch_error("Could not update Gemini HUD", exc)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not update Gemini aura", exc)


def _configure_scorched_earth() -> bool:
    """Add fixed passive explosive damage without changing the turret rocket marker."""
    definition = unrealsdk.find_object("SkillDefinition", SCORCHED_EARTH)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    allowed = (None, RELOAD_ATTRIBUTE, CRISIS_GUN_ATTRIBUTE, EXPLOSIVE_DAMAGE_ATTRIBUTE)
    if (paths.count(EXPLOSIVE_DAMAGE_ATTRIBUTE) > 1
            or any(path not in allowed for path in paths)
            or sum(path in (None, RELOAD_ATTRIBUTE) for path in paths) != 1):
        raise ValueError(f"Unexpected Scorched Earth effects: {paths}")
    attribute = unrealsdk.find_object("AttributeDefinition", EXPLOSIVE_DAMAGE_ATTRIBUTE)
    grenadier = unrealsdk.find_object("SkillDefinition", GRENADIER)
    templates = [item for item in grenadier.SkillEffectPresentations
                 if _effect_attribute_path_for_presentation(item) == EXPLOSIVE_DAMAGE_ATTRIBUTE]
    if attribute is None or len(templates) != 1:
        raise ValueError("Scorched Earth explosive attribute/presentation is unavailable")
    targets = unrealsdk.find_enum("EEffectTarget")
    scale = unrealsdk.find_enum("EModifierType").MT_Scale
    current = next((effect for effect in effects if _effect_attribute_path(effect) == EXPLOSIVE_DAMAGE_ATTRIBUTE), None)
    added = copy.copy(effects[0])
    added.AttributeToModify, added.ModifierType, added.EffectTarget = attribute, scale, targets.TARGET_Self
    added.bIncludeSelfAsTarget = False
    for field, amount in (("BaseModifierValue", .10), ("PerGradeUpgrade", 0.)):
        value = copy.copy(getattr(effects[0], field))
        value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.0
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(added, field, value)
    changed = current is None or current.ModifierType != scale or current.EffectTarget != targets.TARGET_Self
    if current is not None:
        changed |= any(not math.isclose(float(getattr(current, field).BaseValueConstant), amount)
                       or getattr(current, field).BaseValueAttribute is not None
                       or getattr(current, field).InitializationDefinition is not None
                       or float(getattr(current, field).BaseValueScaleConstant) != 1.0
                       for field, amount in (("BaseModifierValue", .10), ("PerGradeUpgrade", 0.)))
    name = "AR_ScorchedExplosiveDamage"
    try:
        stat = unrealsdk.find_object("AttributePresentationDefinition", SCORCHED_EARTH + ":" + name)
    except ValueError:
        stat = None
    if stat is None:
        stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                                          template_obj=templates[0])
    if changed:
        definition.SkillEffectDefinitions = [copy.copy(effect) for effect in effects
                                             if _effect_attribute_path(effect) != EXPLOSIVE_DAMAGE_ATTRIBUTE] + [added]
    presentations = list(definition.SkillEffectPresentations)
    if stat not in presentations:
        definition.SkillEffectPresentations = [*presentations, stat]
    description = (
        "Adds [skill]Multi-Rocket Pods[-skill] to your [skill]Sabre Turret[-skill]. "
        "Also increases your [skill]Explosive Damage[-skill]."
    )
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    return changed


def _configure_phalanx() -> bool:
    """Strengthen the level-scaled barrier and add a separate passive player shield bonus."""
    definition = unrealsdk.find_object("SkillDefinition", PHALANX)
    initializer = unrealsdk.find_object("AttributeInitializationDefinition", PHALANX_HEALTH_INITIALIZER)
    attribute = unrealsdk.find_object("ResourcePoolAttributeDefinition", SHIELD_CAPACITY_ATTRIBUTE)
    preparation = unrealsdk.find_object("SkillDefinition", PREPARATION)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    if paths not in ([None], [None, SHIELD_CAPACITY_ATTRIBUTE]):
        raise ValueError(f"Unexpected Phalanx Shield effects: {paths}")
    templates = [item for item in preparation.SkillEffectPresentations
                 if _effect_attribute_path_for_presentation(item) == SHIELD_CAPACITY_ATTRIBUTE]
    if attribute is None or len(templates) != 1:
        raise ValueError("Phalanx Shield capacity attribute/presentation is unavailable")
    formula = initializer.ValueFormula
    multiplier = formula.Multiplier
    if (not formula.bEnabled or multiplier.BaseValueAttribute is None
            or _skill_path(multiplier.BaseValueAttribute) !=
                "GD_Balance_HealthAndDamage.HealthAndDamage.Att_UniversalBalanceMultiplier_HealthShields"
            or multiplier.InitializationDefinition is not None or float(multiplier.BaseValueConstant) != 0.):
        raise ValueError("Unexpected Phalanx Shield health multiplier")
    targets = unrealsdk.find_enum("EEffectTarget")
    mode = unrealsdk.find_enum("EModifierType").MT_Scale
    added = copy.copy(effects[0])
    added.AttributeToModify = attribute
    added.EffectTarget = targets.TARGET_Self
    added.bIncludeSelfAsTarget = False
    added.ModifierType = mode
    for field, amount in (("BaseModifierValue", PHALANX_PLAYER_SHIELD), ("PerGradeUpgrade", 0.)):
        value = copy.copy(getattr(effects[0], field))
        value.BaseValueConstant = amount
        value.BaseValueAttribute = value.InitializationDefinition = None
        value.BaseValueScaleConstant = 1.0
        setattr(added, field, value)
    current = effects[1] if len(effects) == 2 else None
    effect_changed = current is None or current.EffectTarget != targets.TARGET_Self or current.ModifierType != mode
    if current is not None:
        effect_changed |= any(
            not math.isclose(float(getattr(current, field).BaseValueConstant), amount)
            or getattr(current, field).BaseValueAttribute is not None
            or getattr(current, field).InitializationDefinition is not None
            or float(getattr(current, field).BaseValueScaleConstant) != 1.
            for field, amount in (("BaseModifierValue", PHALANX_PLAYER_SHIELD), ("PerGradeUpgrade", 0.)))
    name = "AR_PhalanxPlayerShield"
    try:
        stat = unrealsdk.find_object("AttributePresentationDefinition", PHALANX + ":" + name)
    except ValueError:
        stat = None
    if stat is None:
        stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                                          template_obj=templates[0])
    if str(stat.Description) != "Shield Capacity: $NUMBER$":
        stat.Description = "Shield Capacity: $NUMBER$"
    desired = PHALANX_NATIVE_HEALTH_SCALE * PHALANX_HEALTH_FACTOR
    health_changed = not math.isclose(float(multiplier.BaseValueScaleConstant), desired)
    if health_changed:
        owned_formula = copy.copy(formula)
        owned_formula.Multiplier = copy.copy(multiplier)
        owned_formula.Multiplier.BaseValueScaleConstant = desired
        initializer.ValueFormula = owned_formula
    if effect_changed:
        definition.SkillEffectDefinitions = [copy.copy(effects[0]), added]
    presentations = list(definition.SkillEffectPresentations)
    if stat not in presentations:
        definition.SkillEffectPresentations = [*presentations, stat]
    description = (
        "Your [skill]Sabre Turret[-skill] projects a [skill]protective shield[-skill]. "
        "The shield attempts to block enemy ranged attacks, but lets friendly ranged attacks pass through. "
        "Enemy movement and melee attacks are not affected. "
        "Also increases your [skill]Maximum Shield Capacity[-skill]."
    )
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    return health_changed or effect_changed


def _configure_quick_charge() -> bool:
    """One native coefficient feeds shield regeneration and the rank stat alike."""
    coefficient = unrealsdk.find_object("DesignerAttributeDefinition", QUICK_CHARGE_COEFFICIENT)
    original = coefficient.BaseValue
    if original.BaseValueAttribute is not None or original.InitializationDefinition is not None:
        raise ValueError("Unexpected Quick Charge coefficient formula")
    presentation = unrealsdk.find_object("AttributePresentationDefinition",
                                         "GD_Soldier_Skills.Survival.QuickCharge:AttributePresentationDefinition_0")
    rounding = unrealsdk.find_enum("EAttributeInitializationRounding").ATTRROUNDING_Float
    changed = (not math.isclose(float(original.BaseValueConstant), QUICK_CHARGE_REGEN_PER_RANK)
               or float(original.BaseValueScaleConstant) != 1.0)
    if changed:
        value = copy.copy(original)
        value.BaseValueConstant = QUICK_CHARGE_REGEN_PER_RANK
        value.BaseValueScaleConstant = 1.0
        coefficient.BaseValue = value
    for field, value in (("bDisplayPercentAsFloat",True),("RoundingMode",rounding),("FloatPrecision",1)):
        if getattr(presentation,field) != value:
            setattr(presentation,field,value)
            changed = True
    return changed


def _configure_quick_charge_reload() -> bool:
    """Native kill-skill lifetime gates shield regeneration and reload speed."""
    definition = unrealsdk.find_object("SkillDefinition", QUICK_CHARGE)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    desired = [SHIELD_REGEN_ATTRIBUTE, None, RELOAD_ATTRIBUTE]
    if paths not in ([SHIELD_REGEN_ATTRIBUTE, None],
                     [SHIELD_REGEN_ATTRIBUTE, None, OVERLOAD_REGEN_DISPLAY_ATTRIBUTE],
                     [SHIELD_REGEN_ATTRIBUTE, None, RESOURCEFUL_COOLDOWN_ATTRIBUTE],
                     [SHIELD_REGEN_ATTRIBUTE, None, *CRISIS_RESISTANCE_ATTRIBUTES], desired):
        raise ValueError(f"Unexpected Quick Charge effects: {paths}")
    attributes = [unrealsdk.find_object("AttributeDefinition", RELOAD_ATTRIBUTE)]
    if any(attribute is None for attribute in attributes):
        raise ValueError("Quick Charge reload attribute is unavailable")
    target = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    mode = unrealsdk.find_enum("EModifierType").MT_Scale
    added = []
    for attribute in attributes:
        data = copy.copy(effects[1])
        data.AttributeToModify, data.EffectTarget, data.ModifierType = attribute, target, mode
        data.GradeToStartApplyingEffect, data.PerGradeUpgradeInterval, data.BonusUpgradeList = 1, 1, []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(data, field))
            value.BaseValueConstant, value.BaseValueScaleConstant = -QUICK_CHARGE_RELOAD_PER_RANK, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(data, field, value)
        added.append(data)
    changed = paths != desired
    if not changed:
        for previous, data in zip(effects[2:], added):
            changed |= (_effect_layout(previous) != _effect_layout(data)
                        or getattr(previous, "GradeToStartApplyingEffect", None) != 1
                        or getattr(previous, "PerGradeUpgradeInterval", None) != 1
                        or bool(getattr(previous, "BonusUpgradeList", ())))
            for field in ("BaseModifierValue", "PerGradeUpgrade"):
                value = getattr(previous, field)
                changed |= (not math.isclose(float(value.BaseValueConstant), -QUICK_CHARGE_RELOAD_PER_RANK, abs_tol=1e-7)
                            or float(value.BaseValueScaleConstant) != 1.
                            or value.BaseValueAttribute is not None or value.InitializationDefinition is not None)
    try:
        stat = unrealsdk.find_object("AttributePresentationDefinition", QUICK_CHARGE + ":AR_ReloadSpeed")
    except ValueError:
        stat = None
    if stat is None:
        template = unrealsdk.find_object("AttributePresentationDefinition",
            QUICK_CHARGE + ":AttributePresentationDefinition_0")
        stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, "AR_ReloadSpeed",
            template_obj=template)
    stat.Attribute, stat.Description = attributes[0], "Reload Speed: $NUMBER$"
    stat.bDisplayAsPercentage, stat.bDisplayAsInverse = True, True
    stat.bDontDisplayPlusSign, stat.bUseCustomNumberPlacement = False, True
    stat.SignStyle = unrealsdk.find_enum("EAttributeValueSignStyle").SIGNSTYLE_Positive
    # Retain only unrelated/native rows; remove previous ammo, cooldown and resistance rows.
    obsolete = (OVERLOAD_REGEN_DISPLAY_ATTRIBUTE, RESOURCEFUL_COOLDOWN_ATTRIBUTE, RELOAD_ATTRIBUTE, *CRISIS_RESISTANCE_ATTRIBUTES)
    presentations = [item for item in definition.SkillEffectPresentations
                     if _effect_attribute_path_for_presentation(item) not in obsolete]
    definition.SkillEffectPresentations = [*presentations, stat]
    if changed:
        definition.SkillEffectDefinitions = [copy.copy(item) for item in effects[:2]] + added
    definition.SkillDescription = (
        "[skill]Kill Skill[-skill]. Killing an enemy causes your [skill]shields[-skill] to regenerate "
        "and increases your [skill]Reload Speed[-skill] for a short time.")
    return changed


def _configure_steady() -> bool:
    """Passive grenade damage; only reload and weapon damage require a launcher."""
    global _steady_definition_address, _steady_launcher_address
    definition = unrealsdk.find_object("SkillDefinition", STEADY)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    native = [RECOIL_ATTRIBUTE, GRENADE_DAMAGE_ATTRIBUTE, CRISIS_GUN_ATTRIBUTE, None]
    desired = [CRISIS_GUN_ATTRIBUTE, RELOAD_ATTRIBUTE, GRENADE_DAMAGE_ATTRIBUTE]
    previous_layout = [CRISIS_GUN_ATTRIBUTE, RELOAD_ATTRIBUTE, MOVEMENT_ATTRIBUTE]
    if paths not in (native, previous_layout, desired):
        raise ValueError(f"Unexpected Steady effects: {paths}")
    constraints = list(definition.SkillConstraints)
    if not constraints:
        raise ValueError("Steady native on-foot constraint is unavailable")
    attributes = [unrealsdk.find_object("AttributeDefinition", path) for path in desired]
    if any(attribute is None for attribute in attributes):
        raise ValueError("Steady damage/reload/grenade attributes are unavailable")
    try:
        evaluator = unrealsdk.find_object("WeaponEquippedExpressionEvaluator", STEADY + ":AR_HoldingLauncher")
    except ValueError:
        evaluator = None
    if evaluator is None:
        shared = unrealsdk.find_object("SkillExpressionEvaluatorDefinition", ASSAULT_RIFLE_CONSTRAINT)
        evaluator = unrealsdk.construct_object("WeaponEquippedExpressionEvaluator", definition, "AR_HoldingLauncher",
            template_obj=shared.Evaluator, flags=int(ObjectFlags.KEEP_ALIVE))
    evaluator.WeaponType = unrealsdk.find_enum("EWeaponType").WT_RocketLauncher
    passive_constraints = [copy.copy(item) for item in constraints if item.Evaluator != evaluator]
    if not passive_constraints:
        raise ValueError("Steady native passive constraint was not found")
    gate = copy.copy(passive_constraints[0])
    gate.Evaluator, gate.EvaluatorDefinitions = evaluator, []
    gate.OnFailure = unrealsdk.find_enum("ESkillState").SKILL_Paused
    gate.bApplyConstraintOnActivatation = True
    gate.bApplyConstraintWhileActive = gate.bApplyConstraintWhilePaused = True
    try:
        helper = unrealsdk.find_object("SkillDefinition", STEADY_LAUNCHER)
    except ValueError:
        helper = None
    created = helper is None
    if helper is None:
        helper = unrealsdk.construct_object("SkillDefinition", definition, "AR_LauncherBonuses",
            template_obj=definition, flags=int(ObjectFlags.KEEP_ALIVE))
    if helper is None:
        raise ValueError("Steady launcher helper could not be created")
    none_target = unrealsdk.find_enum("EEffectTarget").TARGET_None
    self_target = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    template = effects[paths.index(CRISIS_GUN_ATTRIBUTE)]
    updated = []
    changed = created or paths != desired
    for attribute, amount in zip(attributes, (.06, -.08, .05)):
        data = copy.copy(template)
        data.AttributeToModify = attribute
        data.EffectTarget = self_target if len(updated) == 2 else none_target
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(template, field))
            value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(data, field, value)
        if not changed:
            previous = effects[len(updated)]
            changed |= previous.EffectTarget != data.EffectTarget or any(not math.isclose(float(getattr(previous, field).BaseValueConstant), amount, abs_tol=1e-7)
                or getattr(previous, field).BaseValueAttribute is not None
                or getattr(previous, field).InitializationDefinition is not None
                or float(getattr(previous, field).BaseValueScaleConstant) != 1.
                for field in ("BaseModifierValue", "PerGradeUpgrade"))
        updated.append(data)
    launcher_effects = [copy.copy(item) for item in updated[:2]]
    for item in launcher_effects:
        item.EffectTarget = self_target
    # Copy every constraint before replacing native arrays; preserve the passive gate.
    helper.SkillConstraints = [copy.copy(item) for item in passive_constraints] + [gate]
    helper.SkillEffectDefinitions = launcher_effects
    helper.SkillEffectPresentations = []
    helper.TrackedActiveSkills = []
    helper.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked
    helper.bSubjectToGradeRules = False  # Receive the parent's effective grade exactly once.
    helper.BehaviorProviderDefinition = None
    if len(constraints) != len(passive_constraints):
        definition.SkillConstraints = passive_constraints
        changed = True
    if changed:
        definition.SkillEffectDefinitions = updated
    template_stat = unrealsdk.find_object("AttributePresentationDefinition",
        CRISIS_MANAGEMENT + ":AttributePresentationDefinition_53")
    stats = []
    for name, attribute, text in zip(("AR_LauncherDamage", "AR_LauncherReload", "AR_GrenadeDamage"),
            attributes, ("Rocket Launcher Damage: $NUMBER$", "Reload Speed: $NUMBER$", "Grenade Damage: $NUMBER$")):
        try:
            stat = unrealsdk.find_object("AttributePresentationDefinition", STEADY + ":" + name)
        except ValueError:
            stat = None
        if stat is None:
            stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                template_obj=template_stat)
        stat.Attribute, stat.Description = attribute, text
        stats.append(stat)
    definition.SkillEffectPresentations = stats
    definition.SkillDescription = (
        "Increases your [skill]Grenade Damage[-skill]. While holding a [skill]Rocket Launcher[-skill], "
        "also increases your [skill]Rocket Launcher Damage[-skill] and [skill]Reload Speed[-skill].")
    _steady_definition_address = int(definition._get_address())
    _steady_launcher_address = int(helper._get_address())
    return changed



def _sync_steady_launcher(controller: Any, manager: Any, skills: tuple[Any, ...]) -> bool:
    """Only change our helper on rank/allocation changes; callbacks invalidate skills."""
    if not _steady_launcher_address:
        return True
    rank, instances = 0, []
    for skill in skills:
        if skill.Definition is None or skill.SkillInstigator != controller:
            continue
        address = int(skill.Definition._get_address())
        if address == _steady_definition_address:
            rank = max(rank, int(skill.Grade))
        elif address == _steady_launcher_address:
            instances.append(skill)
    if rank <= 0:
        if instances:
            manager.DeactivateSkill(controller, instances[0].Definition)
            return False
        return True
    if instances:
        for skill in instances:
            if int(skill.Grade) != rank:
                skill.UpdateGrade(rank)
                return False
        return True
    helper = unrealsdk.find_object("SkillDefinition", STEADY_LAUNCHER)
    if manager.ActivateSkill(controller, helper, None, rank) is False:
        raise ValueError("Steady launcher activation was rejected")
    return False


def _configure_metal_storm() -> bool:
    """Keep native fire rate and kill activation; replace reload with ammo saving."""
    global _metal_storm_address
    definition = unrealsdk.find_object("SkillDefinition", METAL_STORM)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    if paths not in ([WEAPON_FIRE_INTERVAL, None, RECOIL_ATTRIBUTE], [WEAPON_FIRE_INTERVAL, RELOAD_ATTRIBUTE],
                     [WEAPON_FIRE_INTERVAL, OVERLOAD_REGEN_DISPLAY_ATTRIBUTE]):
        raise ValueError(f"Unexpected Metal Storm effects: {paths}")
    presentations = list(definition.SkillEffectPresentations)
    stats = [p for p in presentations if _effect_attribute_path_for_presentation(p) in (None, RELOAD_ATTRIBUTE, OVERLOAD_REGEN_DISPLAY_ATTRIBUTE)]
    if len(stats) != 1:
        raise ValueError("Metal Storm recoil/reload presentation was not identified")
    reload = unrealsdk.find_object("AttributeDefinition", OVERLOAD_REGEN_DISPLAY_ATTRIBUTE)
    if reload is None:
        raise ValueError("Metal Storm ammo-chance display attribute is unavailable")
    original = effects[-1]
    changed = (paths != [WEAPON_FIRE_INTERVAL, OVERLOAD_REGEN_DISPLAY_ATTRIBUTE]
               or original.EffectTarget != unrealsdk.find_enum("EEffectTarget").TARGET_None) or any(
        not math.isclose(float(value.BaseValueConstant), METAL_STORM_AMMO_CHANCE_PER_RANK, rel_tol=1e-6)
        or value.BaseValueAttribute is not None or value.InitializationDefinition is not None
        or float(value.BaseValueScaleConstant) != 1.0
        for value in (original.BaseModifierValue, original.PerGradeUpgrade))
    if changed:
        owned = copy.copy(effects[0])
        owned.AttributeToModify = reload
        owned.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_None
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(effects[0], field))
            value.BaseValueConstant = METAL_STORM_AMMO_CHANCE_PER_RANK
            value.BaseValueAttribute = value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0
            setattr(owned, field, value)
        definition.SkillEffectDefinitions = [copy.copy(effects[0]), owned]
    for field, value in (("Attribute", reload), ("Description", "Chance to Not Consume Ammo: $NUMBER$")):
        if getattr(stats[0], field) != value:
            setattr(stats[0], field, value)
    stats[0].bDisplayAsInverse = False
    stats[0].bDontDisplayPlusSign = True
    stats[0].SignStyle = unrealsdk.find_enum("EAttributeValueSignStyle").SIGNSTYLE_AsIs
    description = "Kill Skill. Killing an enemy increases your [skill]Fire Rate[-skill] and grants a chance to [skill]not consume ammo[-skill] for a short time."
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    _metal_storm_address = int(definition._get_address())
    return changed


def _metal_storm_weapon(frame: dict[str, Any]) -> Any | None:
    weapon = frame["weapon"]()
    if weapon is None or weapon.bDeleteMe:
        return None
    world = frame["world"]()
    if (world is None or world.bDeleteMe or weapon.WorldInfo != world
            or int(world._get_address()) != frame["identity"][1]):
        return None
    return weapon


def _restore_metal_storm_cost(frame: dict[str, Any]) -> None:
    if frame["saved"]:
        weapon = _metal_storm_weapon(frame)
        if weapon is not None and int(weapon.ShotCost) == 0:
            weapon.ShotCost = frame["cost"]


def _clear_metal_storm_shots() -> None:
    global _metal_storm_context
    _metal_storm_context = None
    for index, frame in enumerate(_metal_storm_shots):
        if frame is not None:
            try:
                _restore_metal_storm_cost(frame)
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _last_ditch_error("Could not clear Metal Storm shot cost", exc)
            _metal_storm_shots[index] = None  # Keep pending POST callbacks balanced.


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.PRE)
def begin_metal_storm_shot(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _metal_storm_shots.append(None)
    cached = _metal_storm_context
    if cached is None:
        return
    try:
        if weapon is None or weapon.bDeleteMe:
            return
        pawn = weapon.Instigator
        if pawn is None or pawn.bDeleteMe or int(pawn._get_address()) != cached["identity"][2]:
            return
        address = int(weapon._get_address())
        if any(f is not None and f["address"] == address for f in _metal_storm_shots[:-1]):
            return  # Root shot owns the roll, even when it failed.
        pc = get_pc(possibly_loading=True)
        if pc is None or pc.bDeleteMe or int(pc.Role) != _overload_authority_role:
            return
        world = pc.WorldInfo
        if (world is None or world.bDeleteMe or world.Pauser or pc.Pawn != pawn
                or pawn.Controller != pc or pawn.IsInjuredDead() or pawn.Weapon != weapon
                or weapon.WorldInfo != world):
            return
        identity = (int(pc._get_address()), int(world._get_address()), int(pawn._get_address()))
        now = float(world.TimeSeconds)
        if (identity != cached["identity"] or not math.isfinite(now) or not 0. <= now-cached["time"] <= 1.
                or _last_ditch_departing in (identity[:2], (identity[0], 0))):
            return
        skill = cached["skill"]()
        if skill is None or skill.SkillInstigator != pc or int(skill.SkillState) != _overload_active_state:
            return
        rank = max(0, int(skill.Grade))
        mastery = cached["mastery"]() if cached["mastery"] is not None else None
        strength = (max(0, int(mastery.Grade)) * BOOST_STRENGTH_PER_RANK
                    if mastery is not None and mastery.SkillInstigator == pc
                    and int(mastery.SkillState) == _overload_active_state else 0.)
        chance = min(1., METAL_STORM_AMMO_CHANCE_PER_RANK * rank * (1.+strength))
        cost, before = int(weapon.ShotCost), int(weapon.ReloadCnt)
        if rank <= 0 or cost <= 0 or before <= 0:
            return
        frame = dict(weapon=WeakPointer(weapon), world=WeakPointer(world), address=address, identity=identity,
                     cost=cost, before=before, executed=False,
                     saved=chance >= 1. or random.random() < chance)
        _metal_storm_shots[-1] = frame
        if frame["saved"]:
            weapon.ShotCost = 0
            if int(weapon.ShotCost) != 0:
                raise ValueError("Metal Storm zero shot cost was not retained")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not prepare Metal Storm ammo saving", exc)


@hook("WillowGame.WillowWeapon:ConsumeAmmo", Type.PRE)
def preserve_metal_storm_ammo(weapon: Any, _args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    if not _metal_storm_shots or weapon is None:
        return None
    try:
        address = int(weapon._get_address())
        frame = next((f for f in reversed(_metal_storm_shots) if f is not None and f["address"] == address), None)
        if frame is not None and frame["saved"] and _metal_storm_weapon(frame) == weapon:
            if int(weapon.ShotCost) != 0:
                frame["cost"] = int(weapon.ShotCost)
                weapon.ShotCost = 0
            return Block
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not preserve Metal Storm ammo", exc)
    return None


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.POST)
def mark_metal_storm_shot(_weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    frame = _metal_storm_shots[-1] if _metal_storm_shots else None
    if frame is not None:
        frame["executed"] = True


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.POST_UNCONDITIONAL)
def finish_metal_storm_shot(_weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    frame = _metal_storm_shots.pop() if _metal_storm_shots else None
    if frame is None:
        return
    try:
        weapon = _metal_storm_weapon(frame)
        if weapon is not None and frame["saved"] and frame["executed"]:
            after = int(weapon.ReloadCnt)
            if 0 <= after < frame["before"]:
                weapon.ReloadCnt = frame["before"]
                weapon.LastReloadCnt = frame["before"]
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not finish Metal Storm saved shot", exc)
    finally:
        try:
            _restore_metal_storm_cost(frame)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _last_ditch_error("Could not restore Metal Storm shot cost", exc)


def _configure_duty_calls() -> bool:
    """Display per-stack ranks; a private helper applies only the current stack total."""
    global _duty_definition_address, _duty_helper_address, _duty_active_state
    definition = unrealsdk.find_object("SkillDefinition", DUTY_CALLS)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    damage_paths = (CRISIS_GUN_ATTRIBUTE, CRITICAL_DAMAGE_ATTRIBUTE)
    speed_paths = (WEAPON_FIRE_INTERVAL, RELOAD_ATTRIBUTE)
    candidates = [i for i, path in enumerate(paths) if path in damage_paths]
    if len(effects) != 2 or sum(paths.count(path) for path in speed_paths) != 1 or len(candidates) != 1:
        raise ValueError(f"Unexpected Duty Calls effects: {paths}")
    for effect in effects:
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = getattr(effect, field)
            if value.BaseValueAttribute is not None or value.InitializationDefinition is not None:
                raise ValueError("Unexpected Duty Calls rank formula")
    attributes = [unrealsdk.find_object("AttributeDefinition", path)
                  for path in (CRITICAL_DAMAGE_ATTRIBUTE, RELOAD_ATTRIBUTE)]
    if any(item is None for item in attributes):
        raise ValueError("Duty Calls stack attributes are unavailable")
    constraints = list(definition.SkillConstraints)
    elemental = {DUTY_CALLS + f":AttributeExpressionEvaluator_{i}" for i in range(20,25)}
    kept = [copy.copy(item) for item in constraints
            if item.Evaluator is None or _skill_path(item.Evaluator) not in elemental]
    if not kept:
        raise ValueError("Duty Calls native passive constraints are unavailable")
    presentations = list(definition.SkillEffectPresentations)
    templates = [next((item for item in presentations
        if _effect_attribute_path_for_presentation(item) in selected), None)
        for selected in (damage_paths, speed_paths)]
    if any(item is None for item in templates):
        raise ValueError("Duty Calls native stat templates are unavailable")
    none_target = unrealsdk.find_enum("EEffectTarget").TARGET_None
    self_target = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    updated,changed = [],len(kept)!=len(constraints)
    for attribute,amount in zip(attributes,(DUTY_CRITICAL_PER_RANK,-DUTY_RELOAD_PER_RANK)):
        template = next((item for item in effects if item.AttributeToModify==attribute),effects[0])
        data = copy.copy(template)
        data.AttributeToModify,data.EffectTarget = attribute,none_target
        for field in ("BaseModifierValue","PerGradeUpgrade"):
            value = copy.copy(getattr(template,field))
            value.BaseValueConstant,value.BaseValueScaleConstant = amount,1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(data,field,value)
        old = effects[len(updated)]
        changed |= (old.AttributeToModify!=attribute or old.EffectTarget!=none_target or any(
            not math.isclose(float(getattr(old,field).BaseValueConstant),amount,abs_tol=1e-8)
            or float(getattr(old,field).BaseValueScaleConstant)!=1.
            for field in ("BaseModifierValue","PerGradeUpgrade")))
        updated.append(data)
    try:
        helper = unrealsdk.find_object("SkillDefinition",DUTY_STACK_HELPER)
    except ValueError:
        helper = None
    created = helper is None
    if helper is None:
        helper = unrealsdk.construct_object("SkillDefinition",definition,"AR_DamageStacks",
            template_obj=definition,flags=int(ObjectFlags.KEEP_ALIVE))
    if helper is None:
        raise ValueError("Duty Calls stack helper could not be created")
    active = [copy.copy(item) for item in updated]
    for item in active:item.EffectTarget=self_target
    helper.SkillEffectDefinitions=active
    helper.SkillConstraints=[copy.copy(item) for item in kept]
    helper.bSubjectToGradeRules=False  # Grade is effective parent rank multiplied by stacks.
    helper.TrackedSkillType=unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked
    helper.DurationType=unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite
    helper.SkillEffectPresentations=[]
    helper.TrackedActiveSkills=[]
    helper.BehaviorProviderDefinition=None
    stats=[]
    for name,attribute,template,text,inverse in zip(
            ("AR_StackCritical","AR_StackReloadSpeed"),attributes,templates,
            ("Critical Hit Damage per Stack: $NUMBER$", f"Reload Speed per Stack: $NUMBER$<br>Maximum Stacks: {DUTY_STACK_LIMIT}"),
            (False,True)):
        try:
            stat=unrealsdk.find_object("AttributePresentationDefinition",DUTY_CALLS+":"+name)
        except ValueError:
            stat=None
        if stat is None:
            stat=unrealsdk.construct_object("AttributePresentationDefinition",definition,name,template_obj=template)
        stat.Attribute,stat.Description=attribute,text
        stat.bDisplayAsPercentage,stat.bDisplayPercentAsFloat=True,True
        stat.bDisplayAsInverse=inverse
        stat.bDontDisplayPlusSign=False
        stat.bUseCustomNumberPlacement=True
        stat.RoundingMode=unrealsdk.find_enum("EAttributeInitializationRounding").ATTRROUNDING_Float
        stat.FloatPrecision=2
        stats.append(stat)
    changed |= created
    if changed:definition.SkillEffectDefinitions=updated
    if len(kept)!=len(constraints):definition.SkillConstraints=kept
    definition.SkillEffectPresentations=stats
    definition.SkillDescription=(
        "Hitting an enemy with a weapon shot while [skill]aiming down sights[-skill] grants a stack that increases your "
        "[skill]Critical Hit Damage[-skill] and [skill]Reload Speed[-skill]. Each shot grants at most one stack. "
        f"Stacks start decaying after {DUTY_DECAY_DELAY:g} seconds without aiming, losing one stack every "
        f"{DUTY_DECAY_INTERVAL:g} seconds. Aiming pauses decay.")
    try:
        _configure_duty_hud(definition)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not configure Duty Calls HUD", exc)
    _duty_definition_address=int(definition._get_address())
    _duty_helper_address=int(helper._get_address())
    _duty_active_state=int(unrealsdk.find_enum("ESkillState").SKILL_Active)
    return changed


def _configure_duty_hud(definition: Any) -> None:
    _configure_stack_hud(definition, DUTY_HUD, "AR_StackHUD", "Duty Calls stacks", DUTY_STACK_LIMIT)


def _configure_stack_hud(definition: Any, path: str, name: str, label: str, limit: int) -> None:
    def obtain(kind: str, outer: Any, name: str, path: str, template: Any = None) -> Any:
        try:
            obj = unrealsdk.find_object(kind, path)
        except ValueError:
            obj = None
        if obj is None:
            kwargs: dict[str, Any] = {"flags": int(ObjectFlags.KEEP_ALIVE)}
            if template is not None:
                kwargs["template_obj"] = template
            obj = unrealsdk.construct_object(kind, outer, name, **kwargs)
        if obj is None:
            raise ValueError("Stack HUD object is unavailable: " + path)
        return obj
    feedback = obtain("SkillDefinition", definition, name, path, definition)
    feedback.SkillEffectDefinitions = []
    feedback.SkillEffectPresentations = []
    feedback.SkillConstraints = []
    feedback.DamageEvents = []
    feedback.KillEvents = []
    feedback.EventResponses = []
    feedback.CustomEvents = []
    feedback.EffectSourceInstanceDataName = ""
    feedback.BehaviorProviderDefinition = None
    feedback.TrackedActiveSkill = None
    feedback.TrackedActiveSkills = []
    feedback.bSubjectToGradeRules = False
    feedback.MaxGrade = limit
    feedback.InitialDuration = 0.
    feedback.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite
    feedback.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered
    feedback.SkillIcon = definition.SkillIcon
    feedback.SkillName = label
    count = obtain("AttributeDefinition", feedback, "StackCount", path + ".StackCount")
    context = obtain("SkillAttributeContextResolver", count, "SkillContext", path + ".StackCount.SkillContext")
    resolver = obtain("ObjectPropertyAttributeValueResolver", count, "GradeValue", path + ".StackCount.GradeValue")
    context.AssociatedSkill = feedback
    resolver.PropertyName = "Grade"
    count.bIsSimpleAttribute = True
    count.AttributeDataType = unrealsdk.find_enum("EAttributeDataType").ADT_Int
    count.ContextResolverChain = [context]
    count.ValueResolverChain = [resolver]
    feedback.CustomStackCount = count


def _sync_duty_hud(controller: Any, manager: Any, count: int) -> bool:
    global _duty_hud_next_check, _duty_hud_visible
    if count <= 0 and not _duty_hud_visible:
        return True
    try:
        feedback = unrealsdk.find_object("SkillDefinition", DUTY_HUD)
        _duty_hud_next_check, changed = _sync_native_feedback(
            controller, manager, feedback, count, _duty_hud_next_check)
        _duty_hud_visible = count > 0
        return not changed
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not update Duty Calls HUD", exc)
        return True  # A visual failure must not disable gameplay bonuses.


def _advance_duty_stacks(now: float, aiming: bool) -> int:
    """Use game time and the shared quarter-second maintenance, without a new timer."""
    global _duty_state
    if _duty_state is None:
        return 0
    owner, count, expiry = _duty_state
    if not math.isfinite(now):
        _duty_state = None
        return 0
    count = max(0, min(DUTY_STACK_LIMIT, int(count)))
    if aiming:
        expiry = math.inf
    elif math.isinf(expiry):
        expiry = now + DUTY_DECAY_DELAY
    elif now >= expiry:
        lost = int((now - expiry) / DUTY_DECAY_INTERVAL) + 1
        count = max(0, count - lost)
        expiry += lost * DUTY_DECAY_INTERVAL
    _duty_state = (owner, count, expiry) if count else None
    return count


def _clear_duty_tracking() -> None:
    for frame in _duty_shot_frames:
        if frame is not None:
            frame["token"]["counted"] = True
    _duty_weapons.clear()
    _duty_projectiles.clear()


def _duty_player(controller: Any) -> Any | None:
    cached = _duty_context
    if (not _turret_runtime_ready or cached is None or controller is None or controller.bDeleteMe
            or int(controller._get_address()) != cached[0]):
        return None
    world, pawn = controller.WorldInfo, controller.Pawn
    main = _duty_main_ref() if _duty_main_ref is not None else None
    if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
            or pawn.Controller != controller or pawn.IsInjuredDead()
            or int(controller.Role) != _overload_authority_role
            or _skill_path(controller.PlayerClass) != AXTON_CLASS
            or (cached[0], int(world._get_address()), int(pawn._get_address())) != cached[:3]
            or _last_ditch_departing in (cached[:2], (cached[0], 0))
            or not 0. <= float(world.TimeSeconds) - cached[4] <= .75
            or main is None or main.SkillInstigator != controller or int(main.Grade) <= 0
            or int(main.SkillState) != _duty_active_state):
        return None
    return pawn


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.PRE)
def begin_duty_shot(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _duty_shot_frames.append(None)
    if _duty_context is None:
        return
    try:
        if weapon is None or weapon.bDeleteMe:
            return
        address = int(weapon._get_address())
        if any(frame is not None and frame["address"] == address for frame in _duty_shot_frames[:-1]):
            return
        pawn = weapon.Instigator
        controller = getattr(pawn, "Controller", None) if pawn is not None else None
        if (controller is None or _duty_player(controller) != pawn or pawn is None or pawn.Weapon != weapon
                or weapon.WorldInfo != controller.WorldInfo or int(weapon.ReloadCnt) <= 0):
            return
        # Even a hipfire miss retires the weapon's previous association. Its
        # later impacts cannot be credited to an older aimed shot.
        token = dict(identity=_duty_context[:3], counted=not bool(controller.IsZoomed()))
        frame = dict(address=address, token=token, executed=False, previous=_duty_weapons.get(address))
        _duty_shot_frames[-1] = frame
        if len(_duty_weapons) >= 16 and address not in _duty_weapons:
            _duty_weapons.pop(next(iter(_duty_weapons)))
        _duty_weapons[address] = (WeakPointer(weapon), float(controller.WorldInfo.TimeSeconds), token)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not track Duty Calls shot", exc)


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.POST)
def confirm_duty_shot(_weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    frame = _duty_shot_frames[-1] if _duty_shot_frames else None
    if frame is not None:
        frame["executed"] = True


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.POST_UNCONDITIONAL)
def finish_duty_shot(_weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    frame = _duty_shot_frames.pop() if _duty_shot_frames else None
    if frame is not None and not frame["executed"]:
        frame["token"]["counted"] = True
        current = _duty_weapons.get(frame["address"])
        if current is not None and current[2] is frame["token"]:
            if frame["previous"] is None:
                _duty_weapons.pop(frame["address"], None)
            else:
                _duty_weapons[frame["address"]] = frame["previous"]


@hook("WillowGame.WillowProjectile:InitStats", Type.POST)
def bind_duty_projectile(projectile: Any, args: Any, _ret: Any, _func: Any) -> None:
    if _duty_context is None or not _duty_shot_frames:
        return
    try:
        weapon = args.InstigatorWeapon
        if weapon is None or projectile is None or projectile.bDeleteMe:
            return
        address = int(weapon._get_address())
        frame = next((item for item in reversed(_duty_shot_frames)
                      if item is not None and item["address"] == address), None)
        if frame is None:
            return
        if len(_duty_projectiles) >= 512:
            _duty_projectiles.pop(next(iter(_duty_projectiles)))
        _duty_projectiles[int(projectile._get_address())] = (WeakPointer(projectile), time.monotonic(), frame["token"])
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not associate Duty Calls projectile", exc)


@hook("WillowGame.WillowPawn:TookDamageFromEnemy", Type.POST)
def count_duty_hit(target: Any, args: Any, _ret: Any, _func: Any) -> None:
    global _duty_state
    if _duty_context is None:
        return
    try:
        causer = args.DamageCauser
        if causer is None:
            return
        address = int(causer._get_address())
        entry = _duty_projectiles.get(address)
        projectile = entry is not None
        if entry is None:
            entry = _duty_weapons.get(address)
        if entry is None or entry[2]["counted"] or entry[0]() != causer:
            return
        # DamageCauser can be a definition, not an Actor. Only registered
        # weapon/projectile instances have Actor lifecycle fields.
        if causer.bDeleteMe:
            return
        controller = args.InstigatedBy
        pawn = _duty_player(controller)
        if pawn is None or not controller.IsZoomed():
            return
        now = float(controller.WorldInfo.TimeSeconds)
        age = time.monotonic() - entry[1] if projectile else now - entry[1]
        if (not 0. <= age <= 30. or entry[2]["identity"] != _duty_context[:3]
                or target is None or target.bDeleteMe or target == pawn or target.WorldInfo != controller.WorldInfo
                or int(target.GetOpinion(pawn)) != _last_ditch_enemy_opinion):
            return
        pipeline = args.Pipeline
        if pipeline is None:
            return
        summary, source = pipeline.DamageSummary, pipeline.DamageSource
        dealt = float(summary.FinalDamage) + float(summary.DamageDealtToShields)
        if not math.isfinite(dealt) or dealt <= 0. or source is None:
            return
        names = {str(source.Name)}
        accepted = {"WillowDmgSource_Bullet", "WillowDmgSource_Rocket"}
        if not names.intersection(accepted):
            for index, base in enumerate(source._superfields()):
                if index >= 16:
                    break
                names.add(str(base.Name))
        if not names.intersection(accepted):
            return  # Grenades, DoT, melee and turret damage do not count as aimed weapon shots.
        entry[2]["counted"] = True
        if _duty_state is not None and _duty_state[0] != _duty_context[:3]:
            _duty_state = None
        count = _advance_duty_stacks(now, True)
        _duty_state = (_duty_context[:3], min(DUTY_STACK_LIMIT, count + 1), math.inf)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not count Duty Calls aimed hit", exc)


def _sync_duty_stacks(controller: Any, manager: Any, skills: tuple[Any,...], identity: tuple[int,int,int], now: float) -> bool:
    global _duty_context,_duty_state,_duty_main_ref
    _duty_context=None
    _duty_main_ref=None
    if not _duty_definition_address:return True
    reference = WeakPointer(controller)
    def update_feedback_after_callback(count: int) -> bool:
        # Effect callbacks can invalidate the incoming ActiveSkills view. Start
        # from a fresh controller/manager before touching visual-only skills.
        live = reference()
        if live is not None and not live.bDeleteMe:
            world, pawn = live.WorldInfo, live.Pawn
            if (world is not None and not world.bDeleteMe and pawn is not None and not pawn.bDeleteMe
                    and (int(live._get_address()), int(world._get_address()), int(pawn._get_address())) == identity):
                refreshed = live.GetSkillManager()
                if refreshed is not None and not getattr(refreshed, "bUpdatingSkills", False):
                    _sync_duty_hud(live, refreshed, count)
        return False
    rank,instances=0,[]
    for skill in skills:
        if skill.Definition is None or skill.SkillInstigator!=controller:continue
        address=int(skill.Definition._get_address())
        if address==_duty_definition_address and int(skill.SkillState)==_duty_active_state:
            rank=max(rank,int(skill.Grade))
            if int(skill.Grade)==rank:_duty_main_ref=WeakPointer(skill)
        elif address==_duty_helper_address:instances.append(skill)
    if rank<=0 or (_duty_state is not None and _duty_state[0]!=identity):
        _duty_state=None
        _clear_duty_tracking()
    if rank>0:_duty_context=(*identity,rank,now)
    count=_advance_duty_stacks(now, bool(controller.IsZoomed())) if rank>0 else 0
    if count<=0:
        if instances:
            manager.DeactivateSkill(controller,instances[0].Definition)
            return update_feedback_after_callback(0)
        return _sync_duty_hud(controller, manager, count)
    grade=rank*count
    if instances:
        for skill in instances:
            if int(skill.Grade)!=grade:
                skill.UpdateGrade(grade)
                return update_feedback_after_callback(count)
        return _sync_duty_hud(controller, manager, count)
    helper=unrealsdk.find_object("SkillDefinition",DUTY_STACK_HELPER)
    if helper is None:
        raise ValueError("Duty Calls stack helper is unavailable")
    if manager.ActivateSkill(controller,helper,None,grade) is False:
        raise ValueError("Duty Calls stack activation was rejected")
    key="Duty Calls stack helper activated"
    if key not in _reported_errors:
        _reported_errors.add(key)
        unrealsdk.logging.info(f"[AxtonRebalance] {key}: rank={rank}, stacks={count}, helper_grade={grade}")
    return update_feedback_after_callback(count)


def _prepare_last_ditch_attributes(definition: Any) -> None:
    template = unrealsdk.find_object("AttributeDefinition", "D_Attributes.DamageSourceModifiers.ReceivedBulletDamageModifier")
    if template is None:
        raise ValueError("Received damage attribute template is unavailable")
    for field in LAST_DITCH_RECEIVED_FIELDS:
        if field in _last_ditch_attributes:
            continue
        name = "AR_LastDitch_" + field
        attribute = None
        for owner_path in (LAST_DITCH_EFFORT, DOUBLE_UP, CRISIS_MANAGEMENT, PRESSURE):
            try:
                attribute = unrealsdk.find_object("AttributeDefinition", owner_path + ":" + name)
            except ValueError:
                continue
            if attribute is not None:
                break
        if attribute is None:
            attribute = unrealsdk.construct_object("AttributeDefinition", definition, name,
                template_obj=template, flags=int(ObjectFlags.KEEP_ALIVE))
            if attribute is None:
                raise ValueError(f"Could not construct Last Ditch Effort attribute: {field}")
            resolver = unrealsdk.construct_object("ObjectPropertyAttributeValueResolver", attribute, "ReceivedValue",
                template_obj=template.ValueResolverChain[0], flags=int(ObjectFlags.KEEP_ALIVE))
            if resolver is None:
                raise ValueError(f"Could not construct Last Ditch Effort resolver: {field}")
            resolver.PropertyName = field
            resolver.CachedProperty = None
            attribute.ValueResolverChain = [resolver]
        _last_ditch_attributes[field] = attribute


def _configure_last_ditch_effort() -> bool:
    """Remove FFYL effects; retain a native rank stat for a per-hit multiplier."""
    global _last_ditch_definition_address, _last_ditch_active_state
    global _last_ditch_authority_role, _last_ditch_enemy_opinion
    definition = unrealsdk.find_object("SkillDefinition", LAST_DITCH_EFFORT)
    if definition is None:
        raise ValueError("Last Ditch Effort definition is unavailable")
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    speed_path = "D_Attributes.GameplayAttributes.FootSpeed"
    if paths.count(CRISIS_GUN_ATTRIBUTE) != 1 or any(path not in (CRISIS_GUN_ATTRIBUTE, speed_path) for path in paths):
        raise ValueError(f"Unexpected Last Ditch Effort effects: {paths}")
    gun = effects[paths.index(CRISIS_GUN_ATTRIBUTE)]
    presentations = [item for item in definition.SkillEffectPresentations
                     if _effect_attribute_path_for_presentation(item) == CRISIS_GUN_ATTRIBUTE]
    if len(presentations) != 1:
        raise ValueError("Last Ditch Effort damage presentation was not identified")
    none_target = unrealsdk.find_enum("EEffectTarget").TARGET_None
    untracked = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked
    active_state = int(unrealsdk.find_enum("ESkillState").SKILL_Active)
    authority = int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
    enemy = int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)
    owned = copy.copy(gun)
    owned.EffectTarget, owned.bIncludeSelfAsTarget = none_target, False
    changed = len(effects) != 1 or gun.EffectTarget != none_target
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        original = getattr(gun, field)
        value = copy.copy(original)
        value.BaseValueConstant = LAST_DITCH_DAMAGE_PER_RANK
        value.BaseValueAttribute = None
        value.InitializationDefinition = None
        value.BaseValueScaleConstant = 1.0
        setattr(owned, field, value)
        changed |= (float(original.BaseValueConstant) != LAST_DITCH_DAMAGE_PER_RANK
                    or original.BaseValueAttribute is not None or original.InitializationDefinition is not None
                    or float(original.BaseValueScaleConstant) != 1.0)
    _prepare_last_ditch_attributes(definition)
    constraints = [copy.copy(item) for item in definition.SkillConstraints
                   if item.Evaluator is None or _skill_path(item.Evaluator) !=
                   LAST_DITCH_EFFORT + ":AttributeExpressionEvaluator_20"]
    if changed:
        definition.SkillEffectDefinitions = [owned]
    if len(constraints) != len(definition.SkillConstraints):
        definition.SkillConstraints = constraints
    if len(definition.SkillEffectPresentations) != 1:
        definition.SkillEffectPresentations = presentations
    if definition.TrackedSkillType != untracked:
        definition.TrackedSkillType = untracked
    description = "Deal increased [skill]Damage[-skill] to enemies with less than [skill]50% Health[-skill] remaining."
    if str(definition.SkillDescription) != description:
        definition.SkillDescription = description
    if str(presentations[0].Description) != "Damage: $NUMBER$":
        presentations[0].Description = "Damage: $NUMBER$"
    _last_ditch_definition_address = int(definition._get_address())
    _last_ditch_active_state, _last_ditch_authority_role = active_state, authority
    _last_ditch_enemy_opinion = enemy
    return changed


def _configure_preparation() -> bool:
    """Fixed shield capacity and native resistance proportional to filled shields."""
    definition = unrealsdk.find_object("SkillDefinition", PREPARATION)
    active = unrealsdk.find_object("SkillDefinition", PREPARATION_ACTIVE)
    if definition is None or active is None:
        raise ValueError("Preparation skill definitions are unavailable")
    effects, child_effects = list(definition.SkillEffectDefinitions), list(active.SkillEffectDefinitions)
    paths = [_effect_attribute_path(item) for item in effects]
    child_paths = [_effect_attribute_path(item) for item in child_effects]
    previous = (HEALTH_REGEN_ATTRIBUTE, SHIELD_REGEN_ATTRIBUTE, CRISIS_RESISTANCE_ATTRIBUTES[0])
    secondary = [i for i, path in enumerate(paths) if path in previous]
    if (len(effects) != 2 or paths.count(SHIELD_CAPACITY_ATTRIBUTE) != 1 or len(secondary) != 1
            or not (len(child_paths) == 1 and child_paths[0] in previous[:2]
                    or len(child_paths) == len(CRISIS_RESISTANCE_ATTRIBUTES)
                    and set(child_paths) == set(CRISIS_RESISTANCE_ATTRIBUTES))):
        raise ValueError("Unexpected Preparation parent/active effects")
    presentations = [stat for stat in definition.SkillEffectPresentations
                     if _effect_attribute_path_for_presentation(stat) in previous]
    if len(presentations) != 1:
        raise ValueError("Preparation secondary presentation was not identified")
    shield_max = unrealsdk.find_object("ResourcePoolAttributeDefinition", SHIELD_CAPACITY_ATTRIBUTE)
    shield_current = unrealsdk.find_object("ResourcePoolAttributeDefinition",
        "D_Attributes.ShieldResourcePool.ShieldCurrentValue")
    condition = unrealsdk.find_object("AttributeExpressionEvaluator",
        PREPARATION_ACTIVE + ":AttributeExpressionEvaluator_26")
    source_init = unrealsdk.find_object("AttributeInitializationDefinition",
        "GD_Soldier_Skills.Misc.Init_Preparation_HealthRegeneration")
    resistance = [unrealsdk.find_object("AttributeDefinition", path) for path in CRISIS_RESISTANCE_ATTRIBUTES]
    if (shield_max is None or shield_current is None or condition is None or source_init is None
            or any(attribute is None for attribute in resistance)):
        raise ValueError("Preparation resistance inputs are unavailable")
    if not any(constraint.Evaluator == condition for constraint in active.SkillConstraints):
        raise ValueError("Preparation full-resource condition was not found in its active child")
    expression = condition.Expression
    if (expression.AttributeOperand1 is None or expression.AttributeOperand2 is None
            or _skill_path(expression.AttributeOperand1) not in (
                "D_Attributes.ShieldResourcePool.ShieldCurrentValue", HEALTH_CURRENT_ATTRIBUTE)
            or _skill_path(expression.AttributeOperand2) not in (SHIELD_CAPACITY_ATTRIBUTE, HEALTH_MAX_ATTRIBUTE)):
        raise ValueError("Unexpected Preparation full-resource condition")
    native_formula = source_init.ValueFormula
    if not native_formula.bEnabled or _skill_path(native_formula.Multiplier.BaseValueAttribute) != PREPARATION_GRADE_ATTRIBUTE:
        raise ValueError("Unexpected Preparation native parent-grade formula")
    capacity_index = paths.index(SHIELD_CAPACITY_ATTRIBUTE)
    capacity = effects[capacity_index]
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = getattr(capacity, field)
        if value.BaseValueAttribute is not None or value.InitializationDefinition is not None:
            raise ValueError("Unexpected Preparation shield capacity formula")
    modes, targets = unrealsdk.find_enum("EModifierType"), unrealsdk.find_enum("EEffectTarget")
    comparison = unrealsdk.find_enum("EComparisonOperator").OPERATOR_GreaterThan
    multiply = unrealsdk.find_enum("EOperandUsage").OPERAND_Multiply

    def plain(template: Any, amount: float, initializer: Any = None) -> Any:
        value = copy.copy(template)
        value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
        value.BaseValueAttribute, value.InitializationDefinition = None, initializer
        return value

    def same_value(old: Any, new: Any) -> bool:
        return (old.BaseValueAttribute == new.BaseValueAttribute
                and old.InitializationDefinition == new.InitializationDefinition
                and math.isclose(float(old.BaseValueConstant), float(new.BaseValueConstant), rel_tol=1e-6, abs_tol=1e-7)
                and math.isclose(float(old.BaseValueScaleConstant), float(new.BaseValueScaleConstant), rel_tol=1e-6, abs_tol=1e-7))

    fraction, fraction_changed = _pressure_missing_shield_factor(
        definition, owner_path=PREPARATION, missing=False)
    try:
        initializer = unrealsdk.find_object("AttributeInitializationDefinition", PREPARATION_RESISTANCE_INIT)
    except ValueError:
        initializer = None
    created = initializer is None
    if initializer is None:
        initializer = unrealsdk.construct_object("AttributeInitializationDefinition", active, "AR_FullShieldResistance",
            template_obj=source_init, flags=int(ObjectFlags.KEEP_ALIVE))
    if initializer is None:
        raise ValueError("Preparation resistance initializer could not be created")
    formula = copy.copy(native_formula)
    formula.Multiplier = copy.copy(native_formula.Multiplier)  # Native effective parent grade, including COM.
    formula.Level = plain(native_formula.Level, -PREPARATION_RESISTANCE_PER_RANK, fraction)
    formula.Power = plain(native_formula.Power, 1.)
    formula.Offset = plain(native_formula.Offset, 0.)
    changed = fraction_changed or created or initializer.ValueFormula.bEnabled != formula.bEnabled or any(not same_value(getattr(initializer.ValueFormula, field), getattr(formula, field))
                            for field in ("Multiplier", "Level", "Power", "Offset"))
    if changed:
        initializer.ValueFormula = formula
    updated = [copy.copy(item) for item in effects]
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        setattr(updated[capacity_index], field, plain(getattr(capacity, field), PREPARATION_SHIELD_PER_RANK))
    display = copy.copy(effects[secondary[0]])
    display.AttributeToModify, display.EffectTarget, display.ModifierType = resistance[0], targets.TARGET_None, modes.MT_Scale
    display.GradeToStartApplyingEffect, display.PerGradeUpgradeInterval, display.BonusUpgradeList = 1, 1, []
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        setattr(display, field, plain(getattr(capacity, field), PREPARATION_RESISTANCE_PER_RANK))
    updated[secondary[0]] = display
    desired = []
    for attribute in resistance:
        data = copy.copy(child_effects[0])
        data.AttributeToModify, data.EffectTarget, data.ModifierType = attribute, targets.TARGET_Self, modes.MT_Scale
        data.GradeToStartApplyingEffect, data.PerGradeUpgradeInterval, data.BonusUpgradeList = 0, 0, []
        data.BaseModifierValue = plain(capacity.BaseModifierValue, 1., initializer)
        data.PerGradeUpgrade = plain(capacity.PerGradeUpgrade, 0.)
        desired.append(data)

    def same_effect(old: Any, new: Any) -> bool:
        return (_effect_layout(old) == _effect_layout(new)
                and all(getattr(old, field, None) == getattr(new, field, None)
                        for field in ("GradeToStartApplyingEffect", "PerGradeUpgradeInterval"))
                and list(getattr(old, "BonusUpgradeList", ()) or ()) == list(getattr(new, "BonusUpgradeList", ()) or ())
                and same_value(old.BaseModifierValue, new.BaseModifierValue)
                and same_value(old.PerGradeUpgrade, new.PerGradeUpgrade))
    if any(not same_effect(old, new) for old, new in zip(effects, updated)):
        definition.SkillEffectDefinitions = updated
        changed = True
    if len(child_effects) != len(desired) or any(not same_effect(old, new) for old, new in zip(child_effects, desired)):
        active.SkillEffectDefinitions = desired  # No regeneration remains; never multiply by child grade again.
        changed = True
    if (expression.AttributeOperand1 != shield_current or expression.AttributeOperand2 != shield_max
            or expression.ComparisonOperator != comparison or expression.Operand2Usage != multiply
            or not math.isclose(float(expression.ConstantOperand2), 0., abs_tol=1e-7)):
        expression = copy.copy(expression)
        expression.AttributeOperand1, expression.AttributeOperand2 = shield_current, shield_max
        expression.ComparisonOperator, expression.Operand2Usage = comparison, multiply
        expression.ConstantOperand2 = 0.
        condition.Expression = expression
        changed = True
    for field, value in (("Attribute", resistance[0]),
            ("Description", "Damage Resistance at Full Shields: $NUMBER$"), ("bDisplayAsPercentage", True),
            ("bDisplayAsInverse", False), ("bDontDisplayPlusSign", False), ("bUseCustomNumberPlacement", True)):
        if getattr(presentations[0], field, None) != value:
            setattr(presentations[0], field, value)
    description = ("Increases your [skill]Shield Capacity[-skill]. You gain [skill]Damage Resistance[-skill] "
                   "as your shield fills, reaching the full bonus at full shields.")
    for target in (definition, active):
        if str(target.SkillDescription) != description:
            target.SkillDescription = description
    return changed


def _configure_resourceful() -> bool:
    """Ranked display-only coefficients; gameplay callbacks change live time only."""
    global _resourceful_definition_address, _resourceful_active_state, _overload_authority_role
    global _resourceful_scorpio_address, _last_ditch_enemy_opinion
    definition = unrealsdk.find_object("SkillDefinition", RESOURCEFUL)
    scorpio = unrealsdk.find_object("SkillDefinition", SCORPIO_SKILL)
    duration_attribute = unrealsdk.find_object("AttributeDefinition", RESOURCEFUL_DURATION_ATTRIBUTE)
    if scorpio is None or duration_attribute is None:
        raise ValueError("Resourceful duration inputs are unavailable")
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    if (paths.count(RESOURCEFUL_COOLDOWN_ATTRIBUTE) != 1 or paths.count(CRISIS_GUN_ATTRIBUTE) > 1
            or paths.count(RESOURCEFUL_DURATION_ATTRIBUTE) > 1 or paths.count((RESOURCEFUL + ":AR_MaxExtraDuration")) > 1
            or any(path not in (RESOURCEFUL_COOLDOWN_ATTRIBUTE, CRISIS_GUN_ATTRIBUTE, RESOURCEFUL_DURATION_ATTRIBUTE,
                               (RESOURCEFUL + ":AR_MaxExtraDuration")) for path in paths)):
        raise ValueError(f"Unexpected Resourceful effects: {paths}")
    template = effects[paths.index(RESOURCEFUL_COOLDOWN_ATTRIBUTE)]
    none_target = unrealsdk.find_enum("EEffectTarget").TARGET_None
    desired = []
    for attribute, amount in ((template.AttributeToModify, RESOURCEFUL_DAMAGE_SECONDS_PER_RANK),
                              (duration_attribute, RESOURCEFUL_DURATION_PER_RANK)):
        display = copy.copy(template)
        display.AttributeToModify, display.EffectTarget = attribute, none_target
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(template, field))
            value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
            value.BaseValueAttribute = value.InitializationDefinition = None
            setattr(display, field, value)
        desired.append(display)
    changed = len(effects) != len(desired) or any(
        old.AttributeToModify != new.AttributeToModify or old.EffectTarget != none_target or any(
            not math.isclose(float(getattr(old, field).BaseValueConstant), float(getattr(new, field).BaseValueConstant), abs_tol=1e-7)
            or float(getattr(old, field).BaseValueScaleConstant) != 1.
            or getattr(old, field).BaseValueAttribute is not None
            or getattr(old, field).InitializationDefinition is not None
            for field in ("BaseModifierValue", "PerGradeUpgrade")) for old, new in zip(effects, desired))
    original = unrealsdk.find_object("AttributePresentationDefinition", RESOURCEFUL + ":AttributePresentationDefinition_0")
    stats = []
    for name, attribute, text in (
            ("AR_DamageCooldownSeconds", template.AttributeToModify, "Cooldown Reduction on Damage: $NUMBER$ seconds"),
            ("AR_KillDurationSeconds", duration_attribute, "Turret Duration per Kill: $NUMBER$ seconds")):
        try:
            stat = unrealsdk.find_object("AttributePresentationDefinition", RESOURCEFUL + ":" + name)
        except ValueError:
            stat = None
        if stat is None:
            stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name, template_obj=original)
        stat.Attribute, stat.Description = attribute, text
        stat.bDisplayAsPercentage, stat.bDisplayAsInverse = False, False
        stat.bDontDisplayPlusSign, stat.bUseCustomNumberPlacement = False, True
        stat.RoundingMode = unrealsdk.find_enum("EAttributeInitializationRounding").ATTRROUNDING_Float
        stat.FloatPrecision = 1
        stats.append(stat)
    if changed:
        definition.SkillEffectDefinitions = desired
    if list(definition.SkillEffectPresentations) != stats:
        definition.SkillEffectPresentations = stats
    definition.SkillDescription = (
        "Taking damage reduces your remaining [skill]Sabre Turret Cooldown[-skill]. "
        "Killing an enemy extends your active [skill]Sabre Turret Duration[-skill].")
    _resourceful_definition_address = int(definition._get_address())
    _resourceful_scorpio_address = int(scorpio._get_address())
    _resourceful_active_state = int(unrealsdk.find_enum("ESkillState").SKILL_Active)
    _overload_authority_role = int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
    _last_ditch_enemy_opinion = int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)
    return changed


def _clear_resourceful_duration() -> None:
    global _resourceful_duration_ref, _resourceful_duration_state
    _resourceful_duration_ref = _resourceful_duration_state = None


def _sync_resourceful_duration(controller: Any, action_skill: Any, identity: tuple[int, int, int]) -> None:
    """Called from the existing skill snapshot; never read a world actor list."""
    global _resourceful_duration_ref, _resourceful_duration_state
    if action_skill is None:
        _clear_resourceful_duration()
        return
    activated = float(action_skill.ActivatedTime)
    if not math.isfinite(activated):
        _clear_resourceful_duration()
        return
    key = (*identity, int(action_skill._get_address()), activated)
    if _resourceful_duration_state is None or _resourceful_duration_state[0] != key:
        _resourceful_duration_state = (key, 0.)
    _resourceful_duration_ref = WeakPointer(action_skill)


def _resourceful_later_start(start: float, seconds: float) -> float:
    """Round down to a float32 timestamp so the duration budget never rounds up."""
    packed = struct.pack('<f', start + seconds)
    target = struct.unpack('<f', packed)[0]
    if target - start > seconds:
        bits = struct.unpack('<I', packed)[0]
        target = struct.unpack('<f', struct.pack('<I', bits - 1))[0]
    return max(start, target)


def _extend_resourceful_duration(controller: Any) -> None:
    global _resourceful_duration_state, _mag_lock_refund
    cached, state, reference = _resourceful_context, _resourceful_duration_state, _resourceful_duration_ref
    if cached is None or cached[3] <= 0 or state is None or reference is None:
        return
    try:
        world, pawn = controller.WorldInfo, controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.Controller != controller or pawn.IsInjuredDead() or int(controller.Role) != _overload_authority_role
                or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != cached[:3]
                or state[0][:3] != cached[:3] or _last_ditch_departing in (cached[:2], (cached[0], 0))):
            return
        now = float(world.TimeSeconds)
        if not math.isfinite(now) or not 0. <= now - cached[4] <= .75:
            return
        live = reference()
        if (live is None or live.Definition is None or int(live.Definition._get_address()) != _resourceful_scorpio_address
                or live.SkillInstigator != controller or int(live.SkillState) != _resourceful_active_state
                or (int(live._get_address()), float(live.ActivatedTime)) != state[0][3:]):
            return
        # USkill.CachedActionSkill is empty for live Scorpio in captured gameplay.
        # The pawn owns the actual action actor; never fall back to a stale cached actor.
        action = getattr(pawn, "MyActionSkill", None)
        if (action is None or action.bDeleteMe or action.WorldInfo != world or action.MyController != controller
                or action.bWantsDeactivate or action.bWantsDestroy):
            return
        turrets = (getattr(action, "ScorpioSpawnedActor", None), getattr(action, "GeminiSpawnedActor", None))
        if not any(turret is not None and not turret.bDeleteMe and turret.WorldInfo == world
                   and turret.PlayerMaster == controller and not turret.IsInjuredDead() for turret in turrets):
            return
        start, duration = float(live.StartTime), float(live.Duration)
        if (not math.isfinite(start) or start < 0. or not math.isfinite(duration) or duration <= 0.
                or duration - (now - start) <= 0.):
            return  # Never revive an expired/ending action skill.
        added = RESOURCEFUL_DURATION_PER_RANK * int(cached[3])
        if added <= 0.:
            return
        new_start = _resourceful_later_start(start, added)
        total = state[1] + (new_start - start)
        _resourceful_duration_state = (state[0], total)
        pending = _mag_lock_refund
        if pending is not None and pending[0] == state[0]:
            _mag_lock_refund = (pending[0], max(pending[1], new_start + duration + 5.))
        if new_start > start:
            live.StartTime = new_start  # Duration/Sentry's initializer and modifiers remain untouched.
        key = "Resourceful turret duration extended on kill"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(f"[AxtonRebalance] {key}: rank={cached[3]}, added={new_start-start:g}, extra_total={total:g}, native_duration={duration:g}")
    except (AttributeError, TypeError, ValueError, RuntimeError, OverflowError) as exc:
        _last_ditch_error("Could not extend Resourceful turret duration", exc)


@hook("WillowGame.WillowPlayerPawn:KilledEnemy", Type.POST)
def extend_resourceful_on_kill(pawn: Any, args: Any, _ret: Any, _func: Any) -> None:
    cached = _resourceful_context
    if cached is None or _resourceful_duration_ref is None:
        return
    try:
        if pawn is None or int(pawn._get_address()) != cached[2]:
            return  # AI, pets and other players must not dispatch a second local proc.
        if args.aTargetPawn is None or args.aTargetPawn == pawn:
            return
        controller = get_pc(possibly_loading=True)
        if controller is None or controller.bDeleteMe or controller.Pawn != pawn:
            return
        _extend_resourceful_duration(controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not process Resourceful kill", exc)


@hook("WillowGame.WillowPlayerPawn:TakeDamage", Type.PRE)
def begin_resourceful_damage(pawn: Any, args: Any, _ret: Any, _func: Any) -> None:
    frame = None
    cached = _resourceful_context
    try:
        if (cached is not None and pawn is not None and int(pawn._get_address()) == cached[2]
                and math.isfinite(float(args.Damage)) and float(args.Damage) > 0.):
            controller = get_pc(possibly_loading=True)
            if (controller is not None and not controller.bDeleteMe and controller.Pawn == pawn
                    and pawn.Controller == controller and int(controller.Role) == _overload_authority_role):
                world = controller.WorldInfo
                if (world is not None and not world.bDeleteMe and not world.Pauser and not pawn.bDeleteMe
                        and int(world._get_address()) == cached[1] and not pawn.IsInjuredDead()
                        and _last_ditch_departing not in (cached[:2], (cached[0], 0))
                        and controller.IsActionSkillCoolingDown() and len(_resourceful_damage_frames) < 16):
                    now = float(world.TimeSeconds)
                    previous = _resourceful_last_proc
                    if (math.isfinite(now) and 0. <= now-cached[4] <= .75
                            and not (previous is not None and previous[0] == cached[:3]
                                     and 0. <= now-previous[1] < RESOURCEFUL_INTERNAL_COOLDOWN)):
                        health, shield = float(pawn.GetHealth()), float(pawn.GetShieldStrength())
                        if math.isfinite(health) and math.isfinite(shield):
                            frame = dict(context=cached[:3],rank=cached[3],
                                         health=max(0.,health),shield=max(0.,shield))
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not observe Resourceful damage", exc)
    _resourceful_damage_frames.append(frame)


@hook("WillowGame.WillowPlayerPawn:TakeDamage", Type.POST_UNCONDITIONAL)
def finish_resourceful_damage(_pawn: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _resourceful_last_proc
    if not _resourceful_damage_frames:
        return
    frame = _resourceful_damage_frames.pop()
    if frame is None or _resourceful_context is None:
        return
    try:
        controller = get_pc(possibly_loading=True)
        if controller is None or controller.bDeleteMe or int(controller.Role) != _overload_authority_role:
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.Controller != controller or pawn.IsInjuredDead()
                or (int(controller._get_address()),int(world._get_address()),int(pawn._get_address())) != frame['context']
                or _resourceful_context[:3] != frame['context']
                or _last_ditch_departing in (frame['context'][:2],(frame['context'][0],0))
                or not controller.IsActionSkillCoolingDown()):
            return
        now = float(world.TimeSeconds)
        previous = _resourceful_last_proc
        if (not math.isfinite(now) or not 0. <= now-_resourceful_context[4] <= .75
                or (previous is not None and previous[0] == frame['context']
                    and 0. <= now-previous[1] < RESOURCEFUL_INTERNAL_COOLDOWN)):
            return
        health, shield = float(pawn.GetHealth()), float(pawn.GetShieldStrength())
        if not math.isfinite(health) or not math.isfinite(shield):
            return
        loss = max(0.,frame['health']-max(0.,health)) + max(0.,frame['shield']-max(0.,shield))
        if loss <= 0.:
            return
        pool = controller.SkillCooldownPool.Data
        if pool is None:
            return
        remaining, rate = float(pool.CurrentValue), float(pool.ConsumptionRate)
        if not math.isfinite(remaining) or not math.isfinite(rate) or remaining <= 0. or rate <= 0.:
            return
        seconds = RESOURCEFUL_DAMAGE_SECONDS_PER_RANK * frame['rank']
        # Claim before writing the pool: nested callbacks share the same interval.
        _resourceful_last_proc = (frame['context'],now)
        pool.SetCurrentValue(max(0.,remaining-seconds*rate))
        key = "Resourceful incoming-damage cooldown reduction"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(f"[AxtonRebalance] {key}: rank={frame['rank']}, seconds={seconds:g}, rate={rate:g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not reduce Resourceful cooldown", exc)


def _sync_ranger_hud(controller: Any, manager: Any, active: bool) -> bool:
    global _ranger_hud_next_check, _ranger_hud_visible
    if not active and not _ranger_hud_visible:
        return True
    try:
        feedback = unrealsdk.find_object("SkillDefinition", RANGER_HUD)
        _ranger_hud_next_check, changed = _sync_native_feedback(
            controller, manager, feedback, int(active), _ranger_hud_next_check)
        _ranger_hud_visible = active
        return not changed
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not update Ranger HUD", exc)
        return True


def _suspend_ranger_hud() -> None:
    if not _ranger_hud_visible:
        return
    try:
        controller = get_pc(possibly_loading=True)
        if controller is None or controller.bDeleteMe:
            return
        world = controller.WorldInfo
        if world is None or world.bDeleteMe:
            return
        manager = controller.GetSkillManager()
        if manager is not None and not getattr(manager, "bUpdatingSkills", False):
            _sync_ranger_hud(controller, manager, False)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not suspend Ranger HUD", exc)


def _maintain_ranger_hud() -> None:
    if not _ranger_hud_visible and not (_ranger_state and _ranger_state["active"]):
        return
    try:
        controller = _ranger_player()
        if controller is None:
            _suspend_ranger_hud()
            return
        if controller.IsPauseMenuOpen():
            return
        manager = controller.GetSkillManager()
        if manager is not None and not getattr(manager, "bUpdatingSkills", False):
            active = bool(_ranger_state and _ranger_state["active"])
            _sync_ranger_hud(controller, manager, active)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not maintain Ranger HUD", exc)


def _clear_ranger() -> None:
    global _ranger_context, _ranger_state
    _ranger_context = _ranger_state = None
    for frame in _ranger_fire_frames:
        if frame is not None:
            _remove_ranger_amp(frame)


def _remove_ranger_amp(frame: dict[str, Any]) -> None:
    reference, frame["modifier"] = frame["modifier"], None
    if reference is None:
        return
    try:
        weapon, modifier = frame["reference"](), reference()
        if (weapon is not None and modifier is not None and not weapon.bDeleteMe
                and weapon.WorldInfo is not None and not weapon.WorldInfo.bDeleteMe):
            weapon.RemoveModifier(modifier, "InstantHitDamage", False)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not finish Ranger shot", exc)


def _stop_ranger_buff(*, clear_context: bool = True) -> bool:
    had_state = _ranger_state is not None
    if clear_context:
        _clear_ranger()
    elif _ranger_state is not None:
        _ranger_state.update(active=False, weapon=None)
    _suspend_ranger_hud()
    if not had_state:
        return False
    try:
        controller = get_pc(possibly_loading=True)
        if controller is None or controller.bDeleteMe:
            return False
        world = controller.WorldInfo
        if world is None or world.bDeleteMe:
            return False
        manager = controller.GetSkillManager()
        if manager is None or getattr(manager, "bUpdatingSkills", False):
            return False
        helper = unrealsdk.find_object("SkillDefinition", RANGER_BUFF)
        if manager.IsSkillActive(controller, helper) or manager.IsSkillPaused(controller, helper):
            manager.DeactivateSkill(controller, helper)
            return True
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not stop Ranger magazine bonus", exc)
    return False


def _ranger_player() -> Any | None:
    cached = _ranger_context
    if not _turret_runtime_ready or cached is None:
        return None
    controller = get_pc(possibly_loading=True)
    if controller is None or controller.bDeleteMe:
        return None
    world, pawn = controller.WorldInfo, controller.Pawn
    if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
            or pawn.Controller != controller or pawn.IsInjuredDead()
            or int(controller.Role) != _last_ditch_authority_role
            or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != cached[:3]
            or _last_ditch_departing in (cached[:2], (cached[0], 0))
            or not 0. <= float(world.TimeSeconds) - cached[4] <= .75):
        return None
    return controller


def _sync_ranger(controller: Any, manager: Any, skills: tuple[Any, ...],
                 identity: tuple[int, int, int], now: float, *, update_hud: bool = True) -> bool:
    global _ranger_context, _ranger_state
    if not _ranger_definition_address:
        return True
    rank, helpers = 0, []
    for skill in skills:
        if skill.Definition is None or skill.SkillInstigator != controller:
            continue
        if int(skill.Definition._get_address()) == _ranger_definition_address:
            if int(skill.SkillState) == _ranger_active_state:
                rank = max(rank, int(skill.Grade))
        elif _skill_path(skill.Definition) == RANGER_BUFF:
            helpers.append(skill)
    if rank <= 0 or (_ranger_state is not None and _ranger_state["identity"] != identity):
        _clear_ranger()
    if rank > 0:
        if _ranger_state is None:
            _ranger_state = dict(identity=identity, weapon=None, active=False)
        _ranger_context = (*identity, rank, now)
        if _ranger_state["active"]:
            reference = _ranger_state["weapon"]
            weapon = reference() if reference is not None else None
            if (weapon is None or weapon.bDeleteMe or weapon != controller.Pawn.Weapon
                    or weapon.WorldInfo != controller.WorldInfo or weapon.Instigator != controller.Pawn
                    or int(weapon.ReloadCnt) <= 0 or len(helpers) != 1
                    or int(helpers[0].SkillState) != _ranger_active_state):
                _ranger_state.update(active=False, weapon=None)
    active = bool(_ranger_state and _ranger_state["active"])
    if helpers and (not active or len(helpers) > 1):
        manager.DeactivateSkill(controller, helpers[0].Definition)
        return False
    if active and int(helpers[0].Grade) != rank:
        helpers[0].UpdateGrade(rank)
        return False
    return _sync_ranger_hud(controller, manager, active) if update_hud else True


@hook("WillowGame.WillowWeapon:BeginReload", Type.PRE)
@hook("WillowGame.WillowWeapon:StartReload", Type.PRE)
@hook("WillowGame.WillowWeapon:PlayWeaponPutDown", Type.PRE)
def end_ranger_magazine(weapon: Any, args: Any, _ret: Any, func: Any) -> None:
    state = _ranger_state
    if state is None or not state["active"] or state["weapon"] is None or state["weapon"]() != weapon:
        return
    if str(func.func.Name) == "PlayWeaponPutDown" and not args.bSwappingWeapons:
        return  # Do not cancel for a grenade/melee holster animation.
    _stop_ranger_buff(clear_context=False)


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.PRE)
def begin_ranger_shot(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _ranger_fire_frames.append(None)
    state, context = _ranger_state, _ranger_context
    if state is None or not state["active"] or context is None:
        return
    frame: dict[str, Any] | None = None
    try:
        controller = _ranger_player()
        reference = state["weapon"]
        if (controller is None or weapon is None or weapon.bDeleteMe or reference is None or reference() != weapon
                or weapon != controller.Pawn.Weapon or weapon.Instigator != controller.Pawn
                or weapon.WorldInfo != controller.WorldInfo or int(weapon.ReloadCnt) <= 0):
            return
        address = int(weapon._get_address())
        if any(item is not None and item["weapon"] == address for item in _ranger_fire_frames[:-1]):
            return  # Paired nested firing wrappers must not apply Amp twice.
        damage = float(weapon.InstantHitDamage)
        if not math.isfinite(damage) or damage <= 0.:
            return
        frame = dict(weapon=address, reference=WeakPointer(weapon), modifier=None)
        _ranger_fire_frames[-1] = frame
        cached_modifier = state.get("amp_modifier")
        modifier = cached_modifier() if cached_modifier is not None else None
        if modifier is None:
            path = _skill_path(weapon)
            path += ("." if ":" in path else ":") + RANGER_AMP_MODIFIER
            try:
                modifier = unrealsdk.find_object("AttributeModifier", path)
            except ValueError:
                modifier = None
            if modifier is None:
                modifier = unrealsdk.construct_object("AttributeModifier", weapon, RANGER_AMP_MODIFIER)
            if modifier is None:
                raise ValueError("Ranger Amp modifier could not be created")
            modifier.Type = unrealsdk.find_enum("EModifierType").MT_PostAdd
            state["amp_modifier"] = WeakPointer(modifier)
        modifier.Value = damage * RANGER_AMP_PER_RANK * context[3]
        frame["modifier"] = WeakPointer(modifier)
        accepted = weapon.AddModifier(modifier, "InstantHitDamage", False)
        live_weapon, live_modifier = frame["reference"](), frame["modifier"]()
        if (live_weapon is None or live_modifier is None or live_weapon.bDeleteMe or not accepted
                or not math.isclose(float(live_weapon.InstantHitDamage), damage + float(live_modifier.Value), rel_tol=1e-5)):
            raise ValueError("Ranger Post-Add Gun Damage could not be verified")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        if frame is not None:
            _remove_ranger_amp(frame)
        _last_ditch_error("Could not prepare Ranger shot", exc)


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:ExtraFireAmmunition", Type.POST_UNCONDITIONAL)
def finish_ranger_shot(weapon: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if not _ranger_fire_frames:
        return
    frame = _ranger_fire_frames.pop()
    if frame is not None:
        _remove_ranger_amp(frame)  # Last round retains its Amp before the magazine bonus ends.
    state = _ranger_state
    if (state is not None and state["active"] and state["weapon"] is not None
            and state["weapon"]() == weapon and not weapon.bDeleteMe and int(weapon.ReloadCnt) <= 0
            and not any(item is not None and item["weapon"] == int(weapon._get_address())
                        for item in _ranger_fire_frames)):
        _stop_ranger_buff(clear_context=False)


def _activate_ranger_reload(controller: Any, manager: Any, identity: tuple[int, int, int], weapon: Any, *, empty_reload: bool) -> None:
    global _ranger_state
    if (not empty_reload or weapon is None or weapon.bDeleteMe or int(weapon.ReloadCnt) <= 0
            or controller.Pawn.Weapon != weapon or weapon.Instigator != controller.Pawn
            or weapon.WorldInfo != controller.WorldInfo):
        return
    if (_ranger_state is not None and _ranger_state["active"] and _ranger_state["weapon"] is not None
            and _ranger_state["weapon"]() == weapon):
        return  # Duplicate ReloadDone notifications must never stack/restart the same magazine.
    rank = max((int(skill.Grade) for skill in manager.ActiveSkills
                if skill.Definition is not None and skill.SkillInstigator == controller
                and int(skill.Definition._get_address()) == _ranger_definition_address
                and int(skill.SkillState) == _ranger_active_state), default=0)
    if rank <= 0:
        return
    helper = unrealsdk.find_object("SkillDefinition", RANGER_BUFF)
    reference = WeakPointer(controller)
    weapon_reference = WeakPointer(weapon)
    state: dict[str, Any] = dict(identity=identity, weapon=weapon_reference, active=True)
    _ranger_state = state
    if manager.ActivateSkill(controller, helper, None, rank) is False:
        state.update(active=False, weapon=None)
        raise ValueError("Ranger magazine bonus activation was rejected")
    live, current_weapon = reference(), weapon_reference()
    if (live is None or live.bDeleteMe or live.WorldInfo is None or live.Pawn is None
            or current_weapon is None or current_weapon.bDeleteMe or _ranger_state is not state
            or live.Pawn.Weapon != current_weapon
            or (int(live._get_address()), int(live.WorldInfo._get_address()), int(live.Pawn._get_address())) != identity):
        if _ranger_state is state:
            state.update(active=False, weapon=None)
        return
    key = "Ranger magazine bonus activated"
    if key not in _reported_errors:
        _reported_errors.add(key)
        unrealsdk.logging.info(f"[AxtonRebalance] {key}: rank={rank}, amp={RANGER_AMP_PER_RANK*rank:g}, "
                              f"fire_rate={RANGER_FIRE_PER_RANK*rank:g}; until the reloaded magazine ends")


def _configure_ranger() -> bool:
    """The parent exposes rank-scaled values; an empty completed reload empowers the next magazine."""
    global _ranger_definition_address, _ranger_active_state
    definition = unrealsdk.find_object("SkillDefinition", RANGER)
    effects = list(definition.SkillEffectDefinitions)
    if not effects:
        raise ValueError("Ranger effect templates are unavailable")
    allowed = {CRISIS_GUN_ATTRIBUTE, WEAPON_FIRE_INTERVAL, CRITICAL_DAMAGE_ATTRIBUTE,
               "D_Attributes.AccuracyResourcePool.AccuracyMinValue", OVERLOAD_CLIP_ATTRIBUTE,
               "D_Attributes.Weapon.WeaponReloadSpeed", HEALTH_MAX_ATTRIBUTE}
    if any(_effect_attribute_path(effect) not in allowed for effect in effects):
        raise ValueError("Unexpected Ranger effects")
    if any(getattr(effect, field).BaseValueAttribute is not None
           or getattr(effect, field).InitializationDefinition is not None
           for effect in effects for field in ("BaseModifierValue", "PerGradeUpgrade")):
        raise ValueError("Unexpected Ranger rank formula")
    attributes = [unrealsdk.find_object("AttributeDefinition", path)
                  for path in (CRISIS_GUN_ATTRIBUTE, WEAPON_FIRE_INTERVAL)]
    targets = unrealsdk.find_enum("EEffectTarget")
    updated = []
    for attribute, amount in zip(attributes, (RANGER_AMP_PER_RANK, -RANGER_FIRE_PER_RANK)):
        effect = copy.copy(effects[0])
        effect.AttributeToModify, effect.EffectTarget = attribute, targets.TARGET_None
        effect.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
        effect.GradeToStartApplyingEffect, effect.PerGradeUpgradeInterval, effect.BonusUpgradeList = 1, 1, []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(effect, field))
            value.BaseValueAttribute = value.InitializationDefinition = None
            value.BaseValueConstant, value.BaseValueScaleConstant = amount, 1.
            setattr(effect, field, value)
        updated.append(effect)
    try:
        helper = unrealsdk.find_object("SkillDefinition", RANGER_BUFF)
    except ValueError:
        helper = None
    created = helper is None
    if helper is None:
        helper = unrealsdk.construct_object("SkillDefinition", definition, "AR_PreparedReload",
            template_obj=definition, flags=int(ObjectFlags.KEEP_ALIVE))
    if helper is None:
        raise ValueError("Ranger reload helper could not be created")
    cadence = copy.copy(updated[1])
    cadence.EffectTarget = targets.TARGET_Self
    helper.SkillEffectDefinitions = [cadence]
    helper.SkillConstraints = [copy.copy(item) for item in definition.SkillConstraints]
    helper.SkillEffectPresentations = []
    helper.TrackedActiveSkills = []
    helper.TrackedActiveSkill = None
    helper.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked
    helper.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite
    helper.InitialDuration = 0.
    helper.SkillType = unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive
    helper.SkillIcon = None
    helper.bSubjectToGradeRules = False
    helper.bAutoUpdateContexts = True
    helper.BehaviorProviderDefinition = None
    helper.DamageEvents, helper.KillEvents, helper.EventResponses, helper.CustomEvents = [], [], [], []
    helper.EffectSourceInstanceDataName = ""
    stats = []
    for name, attribute, text, inverse in (
            ("AR_ReloadAmp", attributes[0], "Amp Damage: $NUMBER$", False),
            ("AR_ReloadFireRate", attributes[1],
             "Fire Rate: $NUMBER$", True)):
        try:
            stat = unrealsdk.find_object("AttributePresentationDefinition", RANGER + ":" + name)
        except ValueError:
            template = next((item for item in definition.SkillEffectPresentations
                             if item.Attribute == attribute), None)
            if template is None:
                raise ValueError("Ranger presentation template is unavailable")
            stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, name,
                template_obj=template, flags=int(ObjectFlags.KEEP_ALIVE))
        if stat is None:
            raise ValueError("Ranger presentation could not be created")
        stat.Attribute, stat.Description = attribute, text
        stat.bDisplayAsPercentage, stat.bDisplayAsInverse = True, inverse
        stat.bDontDisplayPlusSign, stat.bUseCustomNumberPlacement = False, True
        stats.append(stat)
    changed = created or len(effects) != 2 or any(
        _effect_attribute_path(old) != _effect_attribute_path(new)
        or old.EffectTarget != targets.TARGET_None
        or any(not math.isclose(float(getattr(old, field).BaseValueConstant),
                                float(getattr(new, field).BaseValueConstant), abs_tol=1e-8)
               for field in ("BaseModifierValue", "PerGradeUpgrade"))
        for old, new in zip(effects, updated))
    if changed:
        definition.SkillEffectDefinitions = updated
    definition.SkillEffectPresentations = stats
    definition.SkillDescription = (
        "Reloading an [skill]empty magazine[-skill] increases your [skill]Amp Damage[-skill] and "
        "[skill]Fire Rate[-skill] for the reloaded magazine. The bonus ends when the magazine is empty, "
        "you reload again, or you switch weapons.")
    try:
        feedback = unrealsdk.find_object("SkillDefinition", RANGER_HUD)
    except ValueError:
        feedback = None
    if feedback is None:
        feedback = unrealsdk.construct_object("SkillDefinition", definition, "AR_RangerHUD",
            flags=int(ObjectFlags.KEEP_ALIVE))
    if feedback is None:
        raise ValueError("Ranger HUD helper could not be created")
    feedback.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite
    feedback.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered
    feedback.SkillType = unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive
    feedback.SkillIcon, feedback.SkillName = definition.SkillIcon, "Ranger empowered magazine"
    feedback.MaxGrade, feedback.bSubjectToGradeRules = 1, False
    feedback.CustomStackCount = feedback.TrackedActiveSkill = feedback.BehaviorProviderDefinition = None
    for field in ("SkillEffectDefinitions", "SkillConstraints", "SkillEffectPresentations", "DamageEvents", "KillEvents", "TrackedActiveSkills", "EventResponses", "CustomEvents"):
        setattr(feedback, field, [])
    _ranger_definition_address = int(definition._get_address())
    _ranger_active_state = int(unrealsdk.find_enum("ESkillState").SKILL_Active)
    return changed


def _configure_overload() -> bool:
    """Native magazine capacity and additive reserve regeneration; no ammo polling."""
    global _overload_definition_address, _overload_active_state
    global _overload_authority_role, _overload_reloading_state
    definition = unrealsdk.find_object("SkillDefinition", OVERLOAD)
    effects = list(definition.SkillEffectDefinitions)
    paths = [_effect_attribute_path(effect) for effect in effects]
    reserve_paths = [f"D_Attributes.AmmoResource_{ammo}.Ammo_{ammo}_RegenerationRate"
                     for ammo in OVERLOAD_AMMO_TYPES]
    if (paths.count(OVERLOAD_CLIP_ATTRIBUTE) != 1
            or any(path not in (OVERLOAD_CLIP_ATTRIBUTE, OVERLOAD_REGEN_DISPLAY_ATTRIBUTE, *reserve_paths) for path in paths)):
        raise ValueError(f"Unexpected Overload effects: {paths}")
    template = effects[paths.index(OVERLOAD_CLIP_ATTRIBUTE)]
    stats = [stat for stat in definition.SkillEffectPresentations
             if _effect_attribute_path_for_presentation(stat) == OVERLOAD_CLIP_ATTRIBUTE]
    if len(stats) != 1:
        raise ValueError("Overload magazine presentation was not identified")
    reserve_inputs = []
    for path in reserve_paths:
        rate = unrealsdk.find_object("ResourcePoolAttributeDefinition", path)
        capacity = unrealsdk.find_object("ResourcePoolAttributeDefinition", path.replace("_RegenerationRate", "_MaxValue"))
        if rate is None or capacity is None:
            raise ValueError("Overload reserve regeneration attributes are unavailable")
        reserve_inputs.append((rate, capacity))
    display_attribute = unrealsdk.find_object("AttributeDefinition", OVERLOAD_REGEN_DISPLAY_ATTRIBUTE)
    if display_attribute is None:
        raise ValueError("Overload reserve regeneration presentation attribute is unavailable")
    owned = copy.copy(template)
    owned.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    owned.GradeToStartApplyingEffect, owned.PerGradeUpgradeInterval, owned.BonusUpgradeList = 1, 1, []
    changed = (len(effects) != 1 or template.EffectTarget != owned.EffectTarget
               or getattr(template, "GradeToStartApplyingEffect", None) != 1
               or getattr(template, "PerGradeUpgradeInterval", None) != 1
               or bool(getattr(template, "BonusUpgradeList", ())))
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        original = getattr(template, field)
        value = copy.copy(original)
        value.BaseValueConstant, value.BaseValueScaleConstant = OVERLOAD_MAGAZINE_PER_RANK, 1.
        value.BaseValueAttribute = value.InitializationDefinition = None
        setattr(owned, field, value)
        changed |= (not math.isclose(float(original.BaseValueConstant), OVERLOAD_MAGAZINE_PER_RANK, abs_tol=1e-7)
                    or float(original.BaseValueScaleConstant) != 1.
                    or original.BaseValueAttribute is not None or original.InitializationDefinition is not None)
    desired = [owned]
    for rate, capacity in reserve_inputs:
        regen = copy.copy(owned)
        regen.AttributeToModify = rate
        regen.ModifierType = unrealsdk.find_enum("EModifierType").MT_PostAdd
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(owned, field))
            value.BaseValueConstant, value.BaseValueAttribute = 0., capacity
            value.BaseValueScaleConstant = OVERLOAD_RESERVE_REGEN_PER_RANK
            setattr(regen, field, value)
        desired.append(regen)
    display = copy.copy(owned)
    display.AttributeToModify = display_attribute
    display.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_None
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(owned, field))
        value.BaseValueConstant = OVERLOAD_RESERVE_REGEN_PER_RANK
        setattr(display, field, value)
    desired.append(display)
    def same_effect(before: Any, after: Any) -> bool:
        return (_effect_layout(before) == _effect_layout(after)
            and getattr(before, "GradeToStartApplyingEffect", None) == after.GradeToStartApplyingEffect
            and getattr(before, "PerGradeUpgradeInterval", None) == after.PerGradeUpgradeInterval
            and list(getattr(before, "BonusUpgradeList", ())) == list(after.BonusUpgradeList)
            and all(old.BaseValueAttribute == new.BaseValueAttribute
                and old.InitializationDefinition == new.InitializationDefinition
                and math.isclose(float(old.BaseValueConstant), float(new.BaseValueConstant), rel_tol=1e-6, abs_tol=1e-7)
                and math.isclose(float(old.BaseValueScaleConstant), float(new.BaseValueScaleConstant), rel_tol=1e-6, abs_tol=1e-7)
                for old, new in ((getattr(before, field), getattr(after, field))
                                 for field in ("BaseModifierValue", "PerGradeUpgrade"))))
    changed = len(effects) != len(desired) or any(not same_effect(a, b) for a, b in zip(effects, desired))
    if changed:
        definition.SkillEffectDefinitions = desired
    constraints = []
    for original in definition.SkillConstraints:
        evaluators = [item for item in original.EvaluatorDefinitions
                      if _skill_path(item) != ASSAULT_RIFLE_CONSTRAINT]
        if len(evaluators) == len(original.EvaluatorDefinitions):
            constraints.append(copy.copy(original))
        elif evaluators or original.Evaluator is not None:
            owned = copy.copy(original)
            owned.EvaluatorDefinitions = evaluators
            constraints.append(owned)
    if len(constraints) != len(definition.SkillConstraints) or any(
            len(new.EvaluatorDefinitions) != len(old.EvaluatorDefinitions)
            for new, old in zip(constraints, definition.SkillConstraints)):
        definition.SkillConstraints = constraints
        changed = True
    try:
        stat = unrealsdk.find_object("AttributePresentationDefinition", OVERLOAD + ":AR_ReserveRegenStat")
    except ValueError:
        stat = None
    if stat is None:
        stat = unrealsdk.construct_object("AttributePresentationDefinition", definition, "AR_ReserveRegenStat", template_obj=stats[0])
    if stat is None:
        raise ValueError("Overload reserve regeneration presentation could not be created")
    stat.Attribute, stat.Description = display_attribute, "Reserve Ammo Regeneration: $NUMBER$ per second"
    stat.bDisplayAsPercentage, stat.bDisplayAsInverse = True, False
    stat.bDisplayPercentAsFloat, stat.FloatPrecision = True, 1
    stat.RoundingMode = unrealsdk.find_enum("EAttributeInitializationRounding").ATTRROUNDING_Float
    stat.bUseCustomNumberPlacement, stat.bDontDisplayPlusSign = True, False
    definition.SkillEffectPresentations = [stats[0], stat]
    definition.SkillDescription = ("Increases your [skill]Magazine Size[-skill] for all weapons "
        "and regenerates [skill]reserve ammunition[-skill].")
    _overload_definition_address = int(definition._get_address())
    _overload_active_state = int(unrealsdk.find_enum("ESkillState").SKILL_Active)
    _overload_authority_role = int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
    _overload_reloading_state = int(unrealsdk.find_enum("EWeaponReloadState").RELOADSTATE_Reloading)
    return changed


@hook("WillowGame.Behavior_DeactivateSkill:ApplyBehaviorToContext", Type.PRE)
def retain_able_stacks(behavior: Any, _args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    if _able_behavior_addresses is not None and int(behavior._get_address()) == _able_behavior_addresses[1]:
        # The hit graph normally removes Able before adding it. Native timed
        # expiry, respec and death cleanup do not use this graph behavior.
        return Block
    return None


@hook("WillowGame.Behavior_ActivateSkill:ApplyBehaviorToContext", Type.PRE)
def limit_able_stacks(behavior: Any, args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    if _able_behavior_addresses is None or int(behavior._get_address()) != _able_behavior_addresses[0]:
        return None
    try:
        context = args.ContextObject
        controller = getattr(context, "Controller", None)
        if controller is None:
            controller = context
        if controller is None or controller.bDeleteMe:
            return Block
        if _last_ditch_departing is not None or _travel_buff_reset_pending is not None:
            owner_id = int(controller._get_address())
            world = getattr(controller, "WorldInfo", None)
            if (_travel_buff_reset_pending == owner_id
                    or _last_ditch_departing == (owner_id, 0)
                    or (world is not None and _last_ditch_departing == (owner_id, int(world._get_address())))):
                return Block  # A delayed old-map damage event cannot recreate an Able stack.
        manager = controller.GetSkillManager()
        if manager is None:
            return Block
        # Read at most once per native damage event (0.5 s debounce). Let the
        # engine create, heal and expire each independent three-second stack.
        count = sum(skill.Definition == behavior.SkillToActivate and skill.SkillInstigator == controller
                    for skill in manager.ActiveSkills)
        if count >= ABLE_MAX_STACKS:
            return Block
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not enforce Able stack limit: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
        return Block
    return None


@hook("WillowGame.PlayerSkillTree:Initialize", Type.PRE)
def prepare_skill_positions(_tree: Any, args: Any, _ret: Any, _func: Any) -> None:
    global _turret_runtime_ready, _resourceful_context, _resourceful_last_proc, _duty_context, _duty_state, _forbearance_restoring, _forbearance_context
    definition = getattr(args, "SkillTreeDef", None)
    if definition is None or not _skill_path(definition).startswith("GD_Soldier_"):
        return
    _suspend_ready_hud()
    _turret_runtime_ready = False
    _suspend_ranger_hud()
    _clear_ranger()
    _forbearance_restoring = False
    _forbearance_context = None
    _resourceful_context = _resourceful_last_proc = None
    _clear_resourceful_duration()
    _clear_mag_lock_refund()
    _clear_ready_reload_frames()
    for index in range(len(_resourceful_damage_frames)):
        _resourceful_damage_frames[index] = None
    _duty_context = _duty_state = None
    _clear_duty_tracking()
    _clear_metal_storm_shots()
    _clear_forbearance_radius()
    _invalidate_class_mod_cache()
    try:
        if _configure_boost():
            unrealsdk.logging.info("[AxtonRebalance] Kill Mastery: Guerrilla tier 4, right of Grenadier; kill-skill duration +10% and bonus strength +5% per rank")
    except (AttributeError, IndexError, TypeError, ValueError, RuntimeError, OSError) as exc:
        _last_ditch_error("Could not configure Kill Mastery", exc)
    _prepare_turret_health()
    try:
        if _configure_turret_cooldown():
            unrealsdk.logging.info("[AxtonRebalance] Sabre Turret base cooldown: 30 seconds")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not configure Sabre Turret base cooldown", exc)
    try:
        if _configure_pressure():
            unrealsdk.logging.info("[AxtonRebalance] Pressure: damage +7% per rank while shields are positive, additive with Crisis Management; recharge delay up to -24% per rank with missing shields")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not configure Pressure", exc)
    try:
        if _configure_ready():
            unrealsdk.logging.info("[AxtonRebalance] Ready: reload speed +8% per rank; fire rate +5% per rank for 6 seconds after reloading, no stacking")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not configure Ready", exc)
    try:
        if _configure_gemini():
            unrealsdk.logging.info(f"[AxtonRebalance] Gemini: turret fire rate +20%; {GEMINI_AURA_RADIUS/100.:g}-meter allied defensive aura, 50% damage reduction; no stacking")
    except (AttributeError, StopIteration, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Gemini: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_forbearance():
            unrealsdk.logging.info("[AxtonRebalance] Forbearance: status duration -8% per rank; own explosive/area and owned turret explosive damage steal 1% health per rank")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Forbearance: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_healthy():
            unrealsdk.logging.info("[AxtonRebalance] Healthy: health +5% per rank; passive health regeneration 0.6% max health per second per rank, doubled while shields are depleted")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Healthy: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_skill_positions():
            unrealsdk.logging.info(
                "[AxtonRebalance] Skill tree positions set: Resourceful -> Guerrilla tier 5; "
                "Last Ditch Effort -> Survival tier 4; Crisis Management -> Survival tier 2; "
                "Nuke -> Guerrilla capstone; Double Up -> Gunpowder capstone"
            )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not rotate Axton skill tree positions: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        removed = _remove_turret_damage_penalties()
        if removed:
            unrealsdk.logging.info(
                "[AxtonRebalance] Removed native turret bullet damage penalties: "
                + ", ".join(path.rsplit(".", 1)[-1] for path in removed)
            )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not remove turret damage penalties: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_laser_sight():
            unrealsdk.logging.info("[AxtonRebalance] Laser Sight: turret damage +6% and fire rate +4% per rank")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Laser Sight: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_crisis_management():
            unrealsdk.logging.info(
                "[AxtonRebalance] Crisis Management: multiplicative damage +5% and native resistance 6% per rank while shields are depleted"
            )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Crisis Management: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_able():
            unrealsdk.logging.info("[AxtonRebalance] Able: regeneration 0.4% per rank per stack; maximum 5; duration 3 seconds")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Able: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_grenadier():
            unrealsdk.logging.info("[AxtonRebalance] Grenadier: explosive damage +4% per rank; native grenade capacity retained")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Grenadier: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_impact():
            unrealsdk.logging.info("[AxtonRebalance] Impact: melee replaced with accuracy +5% per rank; gun damage retained")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Impact: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_overload():
            unrealsdk.logging.info("[AxtonRebalance] Overload: all-weapon magazine size +10% and reserve ammo regeneration 0.2% per second per rank")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Overload: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_expertise():
            unrealsdk.logging.info("[AxtonRebalance] Expertise: passive native recoil reduction 15% per rank; existing bonuses retained")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Expertise: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_turret_throw_descriptions():
            unrealsdk.logging.info("[AxtonRebalance] Longbow: native deployment retained; turret health bonus uses the adjusted base-health configuration")
        if _configure_mag_lock():
            unrealsdk.logging.info("[AxtonRebalance] Mag-Lock: native wall/ceiling attachment; threat priority +3; throw speed +75%")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Longbow/Mag-Lock: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_scorched_earth():
            unrealsdk.logging.info("[AxtonRebalance] Scorched Earth: passive explosive damage +10%; turret rockets retained")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Scorched Earth: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_phalanx():
            unrealsdk.logging.info("[AxtonRebalance] Phalanx Shield: barrier capacity +70%; passive player shield capacity +20%")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Phalanx Shield: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_quick_charge():
            unrealsdk.logging.info("[AxtonRebalance] Quick Charge: shield regeneration 1.2% per second per rank; native kill behavior retained")
        if _configure_quick_charge_reload():
            unrealsdk.logging.info("[AxtonRebalance] Quick Charge: reload speed +8% per rank while active; damage resistance removed")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Quick Charge: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_steady():
            unrealsdk.logging.info("[AxtonRebalance] Steady: passive grenade damage 5%; launcher damage 6% and reload speed 8% per rank while holding a launcher; old recoil/grenade bonuses removed")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Steady: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_metal_storm():
            unrealsdk.logging.info("[AxtonRebalance] Metal Storm: native fire rate retained; chance to not consume ammo +6% per rank while active")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Metal Storm: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_duty_calls():
            unrealsdk.logging.info(f"[AxtonRebalance] Duty Calls: aimed weapon hits grant up to {DUTY_STACK_LIMIT} stacks; {100*DUTY_CRITICAL_PER_RANK:g}% critical damage and {100*DUTY_RELOAD_PER_RANK:g}% reload speed per rank per stack; decay starts after {DUTY_DECAY_DELAY:g} seconds without aiming, then one stack every {DUTY_DECAY_INTERVAL:g} seconds")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Duty Calls: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_battlefront():
            unrealsdk.logging.info("[AxtonRebalance] Battlefront: melee replaced with critical hit damage +5% per rank")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Battlefront: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_ranger():
            unrealsdk.logging.info(
                "[AxtonRebalance] Ranger: completed empty reload empowers the next magazine; Amp Damage +10% and Fire Rate +5% per rank; no stacks or time limit")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Ranger: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_resourceful():
            unrealsdk.logging.info("[AxtonRebalance] Resourceful: taking damage reduces cooldown by 0.3 seconds per rank; kills add 1 second per rank to active turret duration, without an extension cap; Sentry is unchanged")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Resourceful: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_preparation():
            unrealsdk.logging.info("[AxtonRebalance] Preparation: fixed shield capacity +7% per rank; native damage resistance scales with shield fullness up to +30% per effective parent rank; zero at empty shields")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Preparation: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_nuke():
            unrealsdk.logging.info("[AxtonRebalance] Nuke: turret damage +250%, fire rate -25%; independent blast scaling and no knockback")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Nuke: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_double_up():
            unrealsdk.logging.info("[AxtonRebalance] Double Up: turret weapon damage -40%; cooldown rate +25%; turret hits mark enemies for team damage x1.25 for 10 seconds")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Double Up: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")
    try:
        if _configure_last_ditch_effort():
            unrealsdk.logging.info("[AxtonRebalance] Last Ditch Effort: all owned damage +8% per rank against enemies below 50% health; FFYL effects removed")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not configure Last Ditch Effort: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")

    try:
        if _configure_kill_mastery_bonuses():
            unrealsdk.logging.info("[AxtonRebalance] Kill Mastery bonus helpers configured: Onslaught, Metal Storm, Quick Charge")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not configure Kill Mastery bonuses", exc)


@hook("WillowGame.PlayerSkillTree:Initialize", Type.POST)
def finish_skill_initialization(_tree: Any, args: Any, _ret: Any, _func: Any) -> None:
    global _turret_runtime_ready
    definition = getattr(args, "SkillTreeDef", None)
    if definition is None or not _skill_path(definition).startswith("GD_Soldier_"):
        return
    _turret_runtime_ready = True
    if _boost_definition_address:
        try:
            present = any(skill.Definition is not None
                          and int(skill.Definition._get_address()) == _boost_definition_address
                          for skill in _tree.Skills)
            if not present:
                raise ValueError("Kill Mastery was not copied into the live skill tree; reload Axton from the main menu")
            unrealsdk.logging.info("[AxtonRebalance] Kill Mastery live skill tree verified: present=True")
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _last_ditch_error("Could not verify Kill Mastery live tree", exc)


def _enable_startup_fault_capture() -> None:
    """Temporary native-fault diagnostics; never replace another tool's handler."""
    global _startup_fault_file, _startup_fault_owned
    if _startup_fault_owned:
        return
    if faulthandler.is_enabled():
        unrealsdk.logging.info("[AxtonRebalance] Startup fault capture: existing Python fault handler preserved")
        return
    handle = None
    try:
        path = os.path.join(tempfile.gettempdir(), "AxtonRebalance-native-crash.log")
        handle = open(path, "a", encoding="ascii")
        handle.write(f"\nAxtonRebalance 1.1 startup | {time.strftime('%Y-%m-%d %H:%M:%S')} | PID {os.getpid()}\n")
        handle.flush()
        faulthandler.enable(file=handle, all_threads=True, c_stack=False)
    except (OSError, RuntimeError, TypeError) as exc:
        if handle is not None:
            handle.close()
        unrealsdk.logging.error(f"[AxtonRebalance] Could not enable startup fault capture: {exc}")
        return
    _startup_fault_file, _startup_fault_owned = handle, True
    unrealsdk.logging.info(f"[AxtonRebalance] Startup fault capture enabled: {path}")


def _disable_startup_fault_capture() -> None:
    global _startup_fault_file, _startup_fault_owned
    global _forbearance_restoring, _forbearance_context
    _forbearance_restoring = False
    _forbearance_context = None
    _clear_metal_storm_shots()
    _clear_forbearance_radius()
    _clear_mag_lock_refund()
    _clear_ready_reload_frames()
    _stop_ranger_buff()
    _suspend_ready_hud()
    if not _startup_fault_owned:
        return
    # The descriptor must remain open until the native handler is unregistered.
    faulthandler.disable()
    handle, _startup_fault_file = _startup_fault_file, None
    _startup_fault_owned = False
    if handle is not None:
        handle.close()


def _bonus_for_stage(stage: int) -> float:
    """Linear author bonus over the existing level-scaled damage input."""
    if stage < 1:
        return 0.0
    progress = (min(stage, TURRET_OP10_STAGE) - 1) / (TURRET_OP10_STAGE - 1)
    return TURRET_BONUS_AT_ONE + (TURRET_BONUS_AT_OP10 - TURRET_BONUS_AT_ONE) * progress


def _find_damage_object(classes: tuple[str, ...], path: str,
                        resolved: dict[str, Any] | None = None) -> Any | None:
    if resolved is not None and path in resolved:
        return resolved[path]
    for class_name in classes:
        try:
            found = unrealsdk.find_object(class_name, path)
        except ValueError:
            continue  # A late streamed turret asset can be retried next pass.
        if found is not None:
            if resolved is not None:
                resolved[path] = found
            return found
    if resolved is not None:
        resolved[path] = None  # Retry missing streamed objects on the next pass.
    return None


def _nuke_bonus_for_stage(stage: int) -> float:
    if stage < 1:
        return 0.
    progress = (min(stage, TURRET_OP10_STAGE) - 1) / (TURRET_OP10_STAGE - 1)
    return NUKE_BONUS_AT_ONE + (NUKE_BONUS_AT_OP10 - NUKE_BONUS_AT_ONE) * progress


def _disable_nuke_knockback(resolved: dict[str, Any] | None = None) -> None:
    specifications = (
        (("MeleeDefinition","Object"),TURRET_DAMAGE_INPUTS[1][1],"Knockback"),
        (("Behavior_Explode",),TURRET_DAMAGE_INPUTS[2][1],"MomentumFormula"),
        (("Behavior_CauseDamage",),TURRET_DAMAGE_INPUTS[3][1],"MomentumFormula"),
    )
    for classes, path, field in specifications:
        target = _find_damage_object(classes,path,resolved)
        if target is None:
            continue
        current = getattr(target,field)
        if (float(current.BaseValueConstant) == 0. and current.BaseValueAttribute is None
                and current.InitializationDefinition is None):
            continue
        owned = copy.copy(current)
        owned.BaseValueConstant = 0.
        owned.BaseValueAttribute = owned.InitializationDefinition = None
        owned.BaseValueScaleConstant = 1.
        setattr(target,field,owned)


def _apply_turret_damage(stage: int) -> tuple[str, ...]:
    applied: list[str] = []
    resolved: dict[str, Any] = {}  # One pass only; no native object survives travel in this cache.
    _disable_nuke_knockback(resolved)
    for index, (classes, path, field) in enumerate(TURRET_DAMAGE_INPUTS):
        factor = 1.0 + (_bonus_for_stage(stage) if index == 0 else _nuke_bonus_for_stage(stage))
        target = _find_damage_object(classes, path, resolved)
        if target is None:
            continue
        address = int(target._get_address())
        current = getattr(target, field)
        key = (path,field)
        baseline = _damage_baselines.get(key)
        if baseline is None or baseline[0] != address:
            constant = float(current.BaseValueConstant)
            scale = float(current.BaseValueScaleConstant)
            if not math.isfinite(constant) or not math.isfinite(scale):
                raise ValueError(f"Non-finite native turret damage input: {path}.{field}")
            baseline = (address, constant, scale)
            _damage_baselines[key] = baseline
        # Nuke's plain constants must not receive the same factor twice through
        # both BVC and BVSC. Its level initializers/attributes remain untouched.
        desired_constant = baseline[1] * factor if index == 0 else baseline[1]
        desired_scale = baseline[2] * factor
        if (not math.isclose(float(current.BaseValueConstant), desired_constant, rel_tol=1e-6, abs_tol=1e-6)
                or not math.isclose(float(current.BaseValueScaleConstant), desired_scale, rel_tol=1e-6, abs_tol=1e-6)):
            owned = copy.copy(current)
            owned.BaseValueConstant = desired_constant
            owned.BaseValueScaleConstant = desired_scale
            setattr(target, field, owned)
        applied.append(path)
    return tuple(applied)


def _sync_turret_damage(controller: Any) -> None:
    global _last_reported_state
    if not _turret_runtime_ready:
        return
    try:
        if controller is None or controller != get_pc(possibly_loading=True) or controller.bDeleteMe:
            return
        world = controller.WorldInfo
        pawn = controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser
                or pawn is None or pawn.bDeleteMe or pawn.Controller != controller
                or controller.PlayerClass is None
                or str(controller.PlayerClass._path_name()) != AXTON_CLASS):
            return
        stage = max(1, int(pawn.GetGameStage()))
        applied = _apply_turret_damage(stage)
        state = (stage, len(applied))
        if applied and state != _last_reported_state:
            _last_reported_state = state
            unrealsdk.logging.info(
                f"[AxtonRebalance] Sabre Turret damage: game_stage={stage}, "
                f"additional_bonus={_bonus_for_stage(stage):.4f}, nuke_bonus={_nuke_bonus_for_stage(stage):.4f}, "
                f"inputs={len(applied)}/{len(TURRET_DAMAGE_INPUTS)}"
            )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        message = f"Could not apply Sabre Turret damage scaling: {exc}"
        if message not in _reported_errors:
            _reported_errors.add(message)
            unrealsdk.logging.error(f"[AxtonRebalance] {message}")


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def maintain_turret_damage(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _next_check
    if not _turret_runtime_ready:
        return
    if controller is None:
        return
    now = time.monotonic()
    if now < _next_check or controller != get_pc(possibly_loading=True):
        return
    _next_check = now + 1.0
    _sync_turret_damage(controller)


@hook("WillowGame.WillowPlayerController:ServerStartActionSkill", Type.PRE)
def prepare_turret_damage(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if (_turret_runtime_ready and controller is not None and not controller.bDeleteMe
            and controller == get_pc(possibly_loading=True) and controller.PlayerClass is not None
            and _skill_path(controller.PlayerClass) == AXTON_CLASS):
        _prepare_turret_health(controller)  # Retry late definitions before deployment, never from PlayerTick.
    _sync_turret_damage(controller)  # Refresh rank before deployment, without waiting for the tick.


def _clear_mag_lock_refund() -> None:
    global _mag_lock_refund, _mag_lock_claimed_cycle
    _mag_lock_refund = _mag_lock_claimed_cycle = None
    for index in range(len(_mag_lock_death_frames)):
        _mag_lock_death_frames[index] = None


@hook("WillowGame.ScorpioActionSkill:OnActionSkillStarted", Type.PRE)
def reset_mag_lock_refund(action: Any, args: Any, _ret: Any, _func: Any) -> None:
    if args.TheController is not None and args.TheController == get_pc(possibly_loading=True):
        _clear_mag_lock_refund()
        _prepare_turret_health(args.TheController)  # The action's assets may only have become resident at this event.


@hook("WillowGame.DeployableTurretActor:Died", Type.PRE)
def begin_mag_lock_death(turret: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _mag_lock_death_frames.append(None)
    try:
        if _args.Pipeline is None:
            return  # Scripted cleanup/recall is not a damage-pipeline death.
        pc = get_pc(possibly_loading=True)
        if pc is None or pc.bDeleteMe or int(pc.Role) != _overload_authority_role:
            return
        world, pawn = pc.WorldInfo, pc.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.IsInjuredDead() or turret.bDeleteMe or turret.WorldInfo != world
                or getattr(turret, "PlayerMaster", None) != pc):
            return
        identity = (int(pc._get_address()), int(world._get_address()), int(pawn._get_address()))
        if _last_ditch_departing in (identity[:2], (identity[0], 0)):
            return
        health = float(turret.GetHealth())
        if not math.isfinite(health) or health > 0.:
            return
        action = pawn.MyActionSkill
        if (action is None or action.bDeleteMe or action.MyController != pc
                or action.WorldInfo != world
                or turret not in (action.ScorpioSpawnedActor, action.GeminiSpawnedActor)):
            return
        definition = unrealsdk.find_object("SkillDefinition", MAG_LOCK)
        if int(pc.GetSkillGrade(definition)) <= 0:
            return
        manager = pc.GetSkillManager()
        if manager is None or getattr(manager, "bUpdatingSkills", False):
            return
        now = float(world.TimeSeconds)
        # Read the native deployment once, only at the death event. Expiry/recall are excluded.
        for skill in manager.ActiveSkills:
            if (skill.SkillInstigator != pc or skill.Definition is None
                    or _skill_path(skill.Definition) != SCORPIO_SKILL
                    or getattr(skill, "CachedActionSkill", None) not in (None, action)):
                continue
            if skill.SkillState != unrealsdk.find_enum("ESkillState").SKILL_Active:
                return
            start, duration, activated = float(skill.StartTime), float(skill.Duration), float(skill.ActivatedTime)
            if (not all(math.isfinite(value) for value in (now, start, duration, activated))
                    or now < activated or now >= start+duration):
                return
            cycle = (*identity, int(skill._get_address()), activated)
            if cycle == _mag_lock_claimed_cycle:
                return
            _mag_lock_death_frames[-1] = (cycle, max(now,start+duration) + 5.)
            return
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not observe Mag-Lock turret death", exc)


@hook("WillowGame.DeployableTurretActor:Died", Type.POST_UNCONDITIONAL)
def finish_mag_lock_death(_turret: Any, _args: Any, result: Any, _func: Any) -> None:
    global _mag_lock_refund, _mag_lock_claimed_cycle
    if not _mag_lock_death_frames:
        return
    frame = _mag_lock_death_frames.pop()
    if frame is None or not result or frame[0] == _mag_lock_claimed_cycle:
        return
    _mag_lock_claimed_cycle = frame[0]
    _mag_lock_refund = frame  # Only primitives survive the native death callbacks.


def _apply_mag_lock_refund(pc: Any, world: Any, pawn: Any) -> bool | None:
    global _mag_lock_refund
    pending = _mag_lock_refund
    if pending is None:
        return
    identity = (int(pc._get_address()), int(world._get_address()), int(pawn._get_address()))
    now = float(world.TimeSeconds)
    if (identity != pending[0][:3] or not math.isfinite(now) or now > pending[1]
            or pawn.IsInjuredDead()):
        _mag_lock_refund = None
        return
    if not pc.IsActionSkillCoolingDown():
        return  # Gemini may still have a surviving turret; the native cooldown starts later.
    definition = unrealsdk.find_object("SkillDefinition", MAG_LOCK)
    if int(pc.GetSkillGrade(definition)) <= 0:
        _mag_lock_refund = None
        return
    pool = pc.SkillCooldownPool.Data
    if pool is None:
        return
    remaining, maximum = float(pool.CurrentValue), float(pool.MaxValue)
    if not math.isfinite(remaining) or not math.isfinite(maximum) or maximum <= 0.:
        _mag_lock_refund = None
        return
    _mag_lock_refund = None  # Claim before the native write, including reentrant callbacks.
    if remaining > 0.:
        pool.SetCurrentValue(max(0., remaining - maximum * MAG_LOCK_DEATH_REFUND))
        unrealsdk.logging.info("[AxtonRebalance] Mag-Lock turret destroyed: 35% cooldown refunded")
        return True  # Do not continue the driver's native snapshot after the pool callback.


@hook("GearboxFramework.SpecialMoveComponent:Play", Type.PRE)
def accelerate_mag_lock_throw(component: Any, args: Any, _ret: Any, _func: Any) -> None:
    if not _turret_runtime_ready:
        return
    try:
        if args.NewSMD is None or _skill_path(args.NewSMD) != TURRET_THROW_ANIMATION:
            return  # First-person children, grenades and turret-opening moves are untouched.
        controller = get_pc(possibly_loading=True)
        if (controller is None or controller.bDeleteMe or controller.PlayerClass is None
                or _skill_path(controller.PlayerClass) != AXTON_CLASS):
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.Controller != controller or pawn.SMComponent != component or pawn.IsInjuredDead()):
            return
        identity = (int(controller._get_address()), int(world._get_address()))
        if _last_ditch_departing in (identity, (identity[0], 0)):
            return
        definition = unrealsdk.find_object("SkillDefinition", MAG_LOCK)
        if definition is None or int(controller.GetSkillGrade(definition)) <= 0:
            return
        rate = float(args.PlayRateScale)
        if not math.isfinite(rate) or rate <= 0:
            return
        # Native Play carries this per-call scale through animation/notify processing.
        # Scale only the master; its first-person child inherits the native move data.
        args.PlayRateScale = rate * TURRET_THROW_SPEED_FACTOR
        key = "Mag-Lock accelerated throw"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(f"[AxtonRebalance] {key}: play_rate_scale={float(args.PlayRateScale):g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not accelerate Mag-Lock throw", exc)


@hook("WillowGame.WillowWeapon:InitializeFromDefinitionData", Type.PRE)
def prepare_turret_weapon_damage(_weapon: Any, args: Any, _ret: Any, _func: Any) -> None:
    if not _turret_runtime_ready:
        return
    definition = args.NewDefinitionData.WeaponTypeDefinition
    if definition is not None and _skill_path(definition) == TURRET_DAMAGE_INPUTS[0][1]:
        # The type may stream in during deployment. Tune it before the new
        # weapon copies its damage; ordinary player weapons bypass this work.
        _sync_turret_damage(get_pc(possibly_loading=True))


def _last_ditch_error(where: str, error: Exception) -> None:
    # Native errors may contain a different transient actor path on every hit.
    # Keep the first full detail per operation/type without growing a per-actor log cache.
    key = f"{where} [{type(error).__name__}]"
    if key not in _reported_errors:
        _reported_errors.add(key)
        unrealsdk.logging.error(f"[AxtonRebalance] {where}: {error}")


def _last_ditch_rows(depth: int, source: Any) -> tuple[tuple[str, Any, Any], ...]:
    field = LAST_DITCH_SOURCE_FIELDS.get(str(source.Name)) if source is not None else None
    if field is None and source is not None:
        for base in source._superfields():
            field = LAST_DITCH_SOURCE_FIELDS.get(str(base.Name))
            if field is not None:
                break
    fields = (field,) if field is not None else LAST_DITCH_RECEIVED_FIELDS
    rows = []
    for name in fields:
        key = (depth, name)
        if key not in _last_ditch_modifiers:
            attribute = _last_ditch_attributes[name]
            modifier = unrealsdk.construct_object("AttributeModifier", attribute, f"AR_Execution_{depth}",
                                                   flags=int(ObjectFlags.KEEP_ALIVE))
            if modifier is None:
                raise ValueError(f"Could not construct Last Ditch Effort modifier: {name}")
            modifier.Type = unrealsdk.find_enum("EModifierType").MT_PostAdd
            _last_ditch_modifiers[key] = modifier
        rows.append((name, _last_ditch_attributes[name], _last_ditch_modifiers[key]))
    return tuple(rows)


def _set_last_ditch_scope(scope: dict[str, Any], active: bool) -> None:
    recipient = scope["recipient"]() if scope["recipient"] is not None else None
    world = scope["world"]() if scope["world"] is not None else None
    scope["added"] = False
    if recipient is None or world is None or recipient.bDeleteMe or world.bDeleteMe:
        return
    errors = []
    for field, attribute, modifier in scope["rows"]:
        try:
            stack = field + "ModifierStack"
            present = modifier in getattr(recipient, stack)
            if active and not present:
                before = float(getattr(recipient, field))
                if not math.isfinite(before) or before <= 0.0:
                    continue  # Do not turn immunity into positive damage.
                if attribute.ResolveContext(recipient) != recipient:
                    raise RuntimeError(f"Last Ditch Effort context mismatch: {field}")
                modifier.Value = before * scope["bonus"]
                accepted = attribute.AddAttributeModifier(recipient, modifier, False)
                present = modifier in getattr(recipient, stack)
                scope["added"] |= present
                if not accepted or not present or not math.isclose(
                        float(getattr(recipient, field)), before * (1.0 + scope["bonus"]),
                        rel_tol=1e-5, abs_tol=1e-5):
                    raise RuntimeError(f"Last Ditch Effort multiplier rejected: {field}")
            elif not active and present:
                attribute.RemoveAttributeModifier(recipient, modifier, False)
                if modifier in getattr(recipient, stack):
                    raise RuntimeError(f"Last Ditch Effort cleanup failed: {field}")
            elif active:
                scope["added"] = True
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            errors.append(str(exc))
    if errors:
        scope["added"] = True  # A partially installed scope still owes cleanup.
        raise RuntimeError("; ".join(errors))


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.POST)
def mark_double_up_target(pipeline: Any, args: Any, result: Any, _func: Any) -> None:
    if _bee_recharge_context is not None:
        try:
            _rearm_bee_recharge_on_damage(pipeline, args, result)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _last_ditch_error("Could not rearm Bee recharge sound", exc)
    cached = _double_up_context
    if cached is None and _forbearance_context is None:
        return
    try:
        if cached is None:
            return  # The finally block handles player life steal with its own ownership filter.
        owner_context = cached
        attacker = args.InDamageInstigator
        if owner_context is not None:
            attacker_id = int(attacker._get_address()) if attacker is not None and hasattr(attacker, "_get_address") else 0
            pet = getattr(attacker, "Pawn", None) if attacker is not None else None
            owner = getattr(pet, "PlayerMaster", None) if pet is not None else None
            if attacker_id != owner_context[0] and (owner is None or int(owner._get_address()) != owner_context[0]):
                return  # Enemy/ally-only hits cannot trigger these locally-owned features.
        controller = get_pc(possibly_loading=True)
        if controller is None or controller.bDeleteMe:
            return
        if cached is None:
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or (int(controller._get_address()), int(world._get_address()), int(pawn._get_address())) != cached[:3]
                or int(controller.Role) != _last_ditch_authority_role
                or not 0.0 <= float(world.TimeSeconds) - cached[3] <= 1.0):
            return
        instigator = args.InDamageInstigator
        turret = getattr(instigator, "Pawn", None) if instigator is not None else None
        if (instigator is None or instigator.bDeleteMe or turret is None or turret.bDeleteMe
                or turret.WorldInfo != world or getattr(turret, "PlayerMaster", None) != controller
                or _skill_path(turret.Class) != "WillowGame.DeployableTurretActor"):
            return
        source = args.InDamageSource
        if source is not None and LAST_DITCH_SOURCE_FIELDS.get(str(source.Name)) == "ReceivedStatusEffectDamageModifier":
            return  # Burn ticks are not new direct turret hits.
        target = args.InDamagedActor
        recipient = getattr(target, "Controller", None) if target is not None else None
        if (target is None or target.bDeleteMe or target.WorldInfo != world
                or recipient is None or recipient.bDeleteMe or float(target.GetHealth()) <= 0
                or int(target.GetOpinion(pawn)) != _last_ditch_enemy_opinion):
            return
        damage_type = pipeline.GetDamageTypeDef()
        if damage_type is None or damage_type.IsHealingDamageType():
            return
        summary = result if result is not None else pipeline.DamageSummary
        health_damage, shield_damage = float(summary.FinalDamage), float(summary.DamageDealtToShields)
        if (not math.isfinite(health_damage) or not math.isfinite(shield_damage)
                or max(health_damage, shield_damage) <= 0):
            return
        now = float(world.TimeSeconds)
        key = (int(world._get_address()), int(target._get_address()))
        if key not in _double_up_marks and len(_double_up_marks) >= 256:
            stale = [key for key, mark in _double_up_marks.items() if mark[0] <= now]
            for old in stale:
                _double_up_marks.pop(old, None)
            if len(_double_up_marks) >= 256:
                _double_up_marks.pop(min(_double_up_marks, key=lambda old: _double_up_marks[old][0]))
        _double_up_marks[key] = (now + DOUBLE_UP_DEBUFF_SECONDS, cached[:3], int(recipient._get_address()))
        log = "Double Up turret debuff applied"
        if log not in _reported_errors:
            _reported_errors.add(log)
            unrealsdk.logging.info(f"[AxtonRebalance] {log}: factor={1.+DOUBLE_UP_VULNERABILITY:g}, duration={DOUBLE_UP_DEBUFF_SECONDS:g}, target={_skill_path(target)}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not mark Double Up turret hit", exc)

    finally:
        # Heal only after every other consumer has finished reading the damage snapshot.
        if _forbearance_context is not None:
            _restore_forbearance_from_player(pipeline, args, result)


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.PRE)
def begin_last_ditch_damage(pipeline: Any, args: Any, _ret: Any, _func: Any) -> None:
    _last_ditch_scopes.append(None)
    _bind_forbearance_radius_pipeline(pipeline, args)
    if (_last_ditch_context is None and _crisis_context is None and _pressure_context is None and not _double_up_marks
            and not any(item and item["added"] for item in _last_ditch_scopes)):
        return
    scope: dict[str, Any] | None = None
    try:
        target = args.InDamagedActor
        if target is None or target.bDeleteMe:
            return
        world = target.WorldInfo
        recipient = getattr(target, "Controller", None)
        if world is None or world.bDeleteMe or recipient is None or recipient.bDeleteMe:
            return
        recipient_id = int(recipient._get_address())
        parent = next((item for item in reversed(_last_ditch_scopes[:-1])
                       if item and item["added"] and item["recipient_id"] == recipient_id), None)
        if parent is not None:
            scope = dict(recipient=WeakPointer(recipient), world=WeakPointer(world), recipient_id=recipient_id,
                         pipeline=int(pipeline._get_address()), rows=(), added=False, parent=parent, bonus=0.0)
            _last_ditch_scopes[-1] = scope
            _set_last_ditch_scope(parent, False)
        cached = _last_ditch_context
        crisis_cached = _crisis_context
        pressure_cached = _pressure_context
        double_cached = _double_up_context
        if cached is None and crisis_cached is None and pressure_cached is None and double_cached is None:
            return
        controller = get_pc(possibly_loading=True)
        if (controller is None or controller.bDeleteMe or controller.WorldInfo != world or world.Pauser
                or int(controller.Role) != _last_ditch_authority_role):
            return
        pawn = controller.Pawn
        if pawn is None or pawn.bDeleteMe or target == pawn:
            return
        identity = (int(controller._get_address()), int(world._get_address()), int(pawn._get_address()))
        now = float(world.TimeSeconds)
        execution_live = cached is not None and identity == cached[:3] and 0.0 <= now - cached[4] <= 1.0
        crisis_live = (crisis_cached is not None and identity == crisis_cached[:3]
                       and 0.0 <= now - crisis_cached[4] <= 1.0)
        pressure_live = (pressure_cached is not None and identity == pressure_cached[:3]
                         and 0.0 <= now - pressure_cached[4] <= 1.0)
        double_live = double_cached is not None and identity == double_cached[:3] and 0.0 <= now - double_cached[3] <= 1.0
        if not execution_live and not crisis_live and not pressure_live and not double_live:
            return
        attacker = args.InDamageInstigator
        if attacker is None or attacker.bDeleteMe or attacker.WorldInfo != world:
            return
        source_pawn = getattr(attacker, "Pawn", None)
        owned = attacker == controller or (source_pawn is not None and not source_pawn.bDeleteMe
                                           and getattr(source_pawn, "PlayerMaster", None) == controller)
        ally = owned
        if not ally and double_live and source_pawn is not None and not source_pawn.bDeleteMe:
            ally = hasattr(source_pawn, "GetOpinion") and int(source_pawn.GetOpinion(pawn)) == _double_up_friendly_opinion
        if not owned and not ally:
            return
        incoming = float(args.IncomingDamage)
        if not math.isfinite(incoming) or incoming <= 0.0 or not hasattr(target, "GetHealth"):
            return
        health, maximum = float(target.GetHealth()), float(target.GetMaxHealth())
        if not (math.isfinite(health) and math.isfinite(maximum) and health > 0.0 and maximum > 0.0):
            return
        if not hasattr(target, "GetOpinion") or int(target.GetOpinion(pawn)) != _last_ditch_enemy_opinion:
            return
        damage_type = pipeline.GetDamageTypeDef()
        if damage_type is None or damage_type.IsHealingDamageType() or len(_last_ditch_scopes) > 16:
            return
        execution_bonus = (LAST_DITCH_DAMAGE_PER_RANK * cached[3]
                           if cached is not None and execution_live and owned
                           and health < maximum * LAST_DITCH_HEALTH_THRESHOLD else 0.0)
        marked = False
        if double_live and ally and _double_up_marks:
            key = (int(world._get_address()), int(target._get_address()))
            mark = _double_up_marks.get(key)
            if mark is not None:
                marked = now < mark[0] and mark[1] == identity and mark[2] == recipient_id
                if not marked:
                    _double_up_marks.pop(key, None)
        shield = float(pawn.GetShieldStrength()) if owned and (crisis_live or pressure_live) else 0.0
        crisis_bonus = (CRISIS_DAMAGE_PER_RANK * crisis_cached[3]
                        if crisis_live and crisis_cached is not None and owned
                        and math.isfinite(shield) and shield <= 0.0 else 0.0)
        pressure_bonus = (PRESSURE_DAMAGE_PER_RANK * pressure_cached[3]
                          * _pressure_damage_fraction(shield, float(pawn.GetMaxShieldStrength()))
                          if pressure_live and pressure_cached is not None and owned else 0.0)
        bonus = ((1.0 + execution_bonus) * (1.0 + crisis_bonus + pressure_bonus)
                 * (1.0 + DOUBLE_UP_VULNERABILITY if marked else 1.0) - 1.0)
        if bonus <= 0:
            return
        if scope is None:
            scope = dict(recipient=WeakPointer(recipient), world=WeakPointer(world), recipient_id=recipient_id,
                         pipeline=int(pipeline._get_address()), rows=(), added=False, parent=None, bonus=0.0)
            _last_ditch_scopes[-1] = scope
        scope["rows"] = _last_ditch_rows(len(_last_ditch_scopes) - 1, args.InDamageSource)
        scope["bonus"] = bonus
        _set_last_ditch_scope(scope, False)  # Remove a stranded modifier at this target/depth before reuse.
        _set_last_ditch_scope(scope, True)
        if scope["added"] and execution_bonus > 0 and cached is not None and cached[3] not in _last_ditch_logged_ranks:
            _last_ditch_logged_ranks.add(cached[3])
            unrealsdk.logging.info(
                f"[AxtonRebalance] Last Ditch Effort multiplier verified: rank={cached[3]}, "
                f"factor={1.0 + scope['bonus']:g}, target_health={health / maximum:g}, owned_turret={attacker != controller}"
            )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        if scope is not None:
            try:
                _set_last_ditch_scope(scope, False)
            except (AttributeError, TypeError, ValueError, RuntimeError) as cleanup:
                _last_ditch_error("Could not roll back Last Ditch Effort", cleanup)
        _last_ditch_error("Could not apply Last Ditch Effort", exc)


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.POST_UNCONDITIONAL)
def finish_last_ditch_damage(pipeline: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if not _last_ditch_scopes:
        return
    scope = _last_ditch_scopes.pop()
    if scope is None:
        return
    try:
        _set_last_ditch_scope(scope, False)
        if scope["pipeline"] != int(pipeline._get_address()):
            raise RuntimeError("Last Ditch Effort damage scopes were not paired")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not finish Last Ditch Effort", exc)
    finally:
        if scope["parent"] is not None:
            try:
                _set_last_ditch_scope(scope["parent"], True)
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _last_ditch_error("Could not restore enclosing Last Ditch Effort", exc)


_travel_buff_reset_pending: int | None = None


def _reset_axton_travel_buffs(controller: Any) -> bool:
    """End owned transient skills through the live manager, never retained snapshots."""
    try:
        if (controller is None or controller.bDeleteMe or getattr(controller, "PlayerClass", None) is None
                or _skill_path(controller.PlayerClass) != AXTON_CLASS):
            return True
        world, pawn = controller.WorldInfo, controller.Pawn
        if world is None or world.bDeleteMe or pawn is None or pawn.bDeleteMe:
            return False
        identity = (int(controller._get_address()), int(world._get_address()), int(pawn._get_address()))
        reference = WeakPointer(controller)
        paths = {READY_MOVEMENT, READY_HUD, RANGER_BUFF, RANGER_HUD, DUTY_STACK_HELPER, DUTY_HUD,
                 ABLE_ACTIVE, HEALTHY_TURRET_HELPER, GEMINI_AURA, GEMINI_FIRE, GEMINI_HUD, *KILL_MASTERY_HELPERS}
        attempted: set[int] = set()
        kill_skills_reset = False
        for _ in range(64):
            live = reference()
            if live is None or live.bDeleteMe or live.WorldInfo is None or live.Pawn is None:
                return False
            current_world, current_pawn = live.WorldInfo, live.Pawn
            if (current_world.bDeleteMe or current_pawn.bDeleteMe
                    or (int(live._get_address()), int(current_world._get_address()),
                        int(current_pawn._get_address())) != identity):
                return False
            manager = live.GetSkillManager()
            if manager is None or getattr(manager, "bUpdatingSkills", False):
                return False  # Retry using only the new world's live context, never the old manager.
            if not kill_skills_reset:
                force_off = getattr(live, "ForceKillSkillsOff", None)
                if force_off is not None:
                    live.KillSkillTimeRemaining = 0.
                    force_off()  # Verified native WillowPlayerController API; preserves allocated skills.
                    kill_skills_reset = True
                    continue  # Native callbacks invalidate the manager snapshot.
                kill_skills_reset = True
            candidate = next((skill for skill in manager.ActiveSkills
                if skill.SkillInstigator == live and skill.Definition is not None
                and _skill_path(skill.Definition) in paths), None)
            if candidate is None:
                return True
            address = int(candidate._get_address())
            if address in attempted:
                return False  # No progress: never spin on a refused deactivation.
            attempted.add(address)
            manager.DeactivateSkill(live, candidate.Definition)
            # Next iteration reacquires player/world/manager and the current skill list.
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not reset Axton travel buffs", exc)
    return False


@hook("WillowGame.WillowPlayerController:PreClientTravel", Type.PRE)
@hook("WillowGame.WillowPlayerController:Destroyed", Type.PRE)
def suspend_last_ditch(controller: Any, _args: Any, _ret: Any, func: Any) -> None:
    global _crisis_context, _pressure_context
    global _bee_recharge_context, _bee_recharge_announced
    global _last_ditch_context, _last_ditch_departing, _double_up_context, _forbearance_restoring, _forbearance_context
    global _gemini_departing, _gemini_world, _resourceful_context, _resourceful_last_proc, _duty_context, _duty_state
    global _ready_hud_visible, _ready_hud_next_check
    global _ranger_hud_visible, _ranger_hud_next_check
    global _travel_buff_reset_pending, _duty_hud_visible, _duty_hud_next_check
    address = int(controller._get_address())
    if (controller != get_pc(possibly_loading=True)
            and (_crisis_context is None or _crisis_context[0] != address)
            and (_pressure_context is None or _pressure_context[0] != address)
            and (_last_ditch_context is None or _last_ditch_context[0] != address)
            and (_double_up_context is None or _double_up_context[0] != address)
            and (_last_ditch_departing is None or _last_ditch_departing[0] != address)
            and (_class_mod_owner is None or _class_mod_owner[0] != address)):
        return
    before_travel = str(func.func.Name) == "PreClientTravel"
    _bee_recharge_context, _bee_recharge_announced = None, False
    departing_world = controller.WorldInfo if before_travel else None
    _last_ditch_departing = (address, int(departing_world._get_address()) if departing_world is not None else 0)
    _travel_buff_reset_pending = address if before_travel else None
    _invalidate_class_mod_cache()
    _clear_mag_lock_refund()
    _clear_ready_reload_frames()
    if str(func.func.Name) == "PreClientTravel":
        _suspend_ranger_hud()
    else:
        _ranger_hud_visible, _ranger_hud_next_check = False, 0.
    _clear_ranger()
    _resourceful_context = _resourceful_last_proc = None
    _clear_resourceful_duration()
    for index in range(len(_resourceful_damage_frames)):
        _resourceful_damage_frames[index] = None
    _duty_context = _duty_state = None
    _clear_duty_tracking()
    _clear_metal_storm_shots()
    _clear_forbearance_radius()
    _forbearance_restoring = False
    _forbearance_context = None
    before_travel = str(func.func.Name) == "PreClientTravel"
    world = controller.WorldInfo if before_travel else None
    if before_travel and _duty_hud_visible and world is not None and not world.bDeleteMe:
        manager = controller.GetSkillManager()
        if manager is not None and not getattr(manager, "bUpdatingSkills", False):
            _sync_duty_hud(controller, manager, 0)
    _gemini_departing = int(world._get_address()) if world is not None else _gemini_world
    _gemini_world = 0
    _gemini_turrets.clear()
    if before_travel and _gemini_ready and world is not None and not world.bDeleteMe:
        world_reference = WeakPointer(world)
        for reference in tuple(_gemini_recipients.values()):
            for path in (GEMINI_AURA, GEMINI_FIRE, GEMINI_HUD):
                try:
                    recipient, live_world = reference(), world_reference()
                    if (recipient is None or recipient.bDeleteMe or live_world is None
                            or live_world.bDeleteMe or recipient.WorldInfo != live_world):
                        break
                    manager = recipient.GetSkillManager()
                    if manager is not None and not manager.bUpdatingSkills:
                        definition = unrealsdk.find_object("SkillDefinition", path)
                        if manager.IsSkillActive(recipient, definition) or manager.IsSkillPaused(recipient, definition):
                            manager.DeactivateSkill(recipient, definition)
                except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                    _last_ditch_error("Could not suspend Gemini aura", exc)
    _gemini_recipients.clear()
    _last_ditch_context = _crisis_context = _pressure_context = None
    _double_up_context = None
    _double_up_marks.clear()
    _last_ditch_departing = (address, int(world._get_address()) if world is not None else 0)
    for scope in reversed(_last_ditch_scopes):
        if scope is not None:
            if before_travel:
                try:
                    _set_last_ditch_scope(scope, False)
                except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                    _last_ditch_error("Could not suspend Last Ditch Effort", exc)
            scope["recipient"], scope["world"], scope["parent"] = None, None, None
            scope["added"] = False
    if before_travel:
        _suspend_ready_hud()
    else:
        _ready_hud_visible, _ready_hud_next_check = False, 0.
    _duty_hud_visible, _duty_hud_next_check = False, 0.
    if before_travel and _reset_axton_travel_buffs(controller):
        _travel_buff_reset_pending = None


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def regenerate_overload_magazine(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    """Shared quarter-second skill maintenance; no manual ammunition operations."""
    global _next_overload_check, _last_ditch_context, _double_up_context, _resourceful_context, _duty_context, _duty_state, _forbearance_context
    global _travel_buff_reset_pending, _metal_storm_context
    global _crisis_context, _pressure_context
    if not (_overload_definition_address or _travel_buff_reset_pending is not None or _forbearance_address or _kill_mastery_targets
            or _pressure_definition_address or _crisis_definition_address or _last_ditch_definition_address or _double_up_definition_address or _steady_definition_address or _ready_definition_address or _resourceful_definition_address or _duty_definition_address or _ranger_definition_address):
        return
    # Filter other controllers before consuming the local timer.
    if controller is None:
        return
    wall_time = time.monotonic()
    if wall_time < _next_overload_check or controller != get_pc(possibly_loading=True):
        return
    _next_overload_check = wall_time + .25
    _last_ditch_context = _crisis_context = _pressure_context = None
    _double_up_context = None
    _resourceful_context = None
    _duty_context = None
    _forbearance_context = None
    _metal_storm_context = None
    try:
        authority = _last_ditch_authority_role if (_pressure_definition_address or _crisis_definition_address or _last_ditch_definition_address or _double_up_definition_address) else _overload_authority_role
        if controller.bDeleteMe or int(controller.Role) != authority:
            return
        world, pawn = controller.WorldInfo, controller.Pawn
        if (world is None or world.bDeleteMe or world.Pauser or pawn is None or pawn.bDeleteMe
                or pawn.Controller != controller or pawn.IsInjuredDead()
                or controller.PlayerClass is None or _skill_path(controller.PlayerClass) != AXTON_CLASS):
            if (world is not None and not world.bDeleteMe and pawn is not None and not pawn.bDeleteMe
                    and pawn.Controller == controller and pawn.IsInjuredDead()):
                _clear_resourceful_duration()
                _clear_mag_lock_refund()
                if _stop_ranger_buff():
                    return
                if _ready_hud_visible:
                    _suspend_ready_hud()
                    return  # Native UI callbacks may invalidate the player/manager snapshot.
            if ((_duty_state is not None or _duty_hud_visible) and world is not None and not world.bDeleteMe
                    and not world.Pauser and pawn is not None and not pawn.bDeleteMe
                    and pawn.Controller == controller and pawn.IsInjuredDead()):
                _duty_state = None
                _clear_duty_tracking()
                _clear_metal_storm_shots()
                _clear_forbearance_radius()
                manager = controller.GetSkillManager()
                if manager is not None and not getattr(manager,"bUpdatingSkills",False):
                    reference = WeakPointer(controller)
                    manager.DeactivateSkill(controller,unrealsdk.find_object("SkillDefinition",DUTY_STACK_HELPER))
                    live = reference()
                    if live is not None and not live.bDeleteMe and live.WorldInfo == world:
                        refreshed = live.GetSkillManager()
                        if refreshed is not None and not getattr(refreshed, "bUpdatingSkills", False):
                            _sync_duty_hud(live, refreshed, 0)
            return
        if _apply_mag_lock_refund(controller, world, pawn):
            return
        context_ids = (int(controller._get_address()), int(world._get_address()), int(pawn._get_address()))
        _sync_bee_recharge_state(pawn, context_ids)
        if _last_ditch_departing in (context_ids[:2], (context_ids[0], 0)):
            return
        if _travel_buff_reset_pending is not None:
            if _travel_buff_reset_pending == context_ids[0]:
                if _reset_axton_travel_buffs(controller):
                    _travel_buff_reset_pending = None
                return  # No stale skill snapshot after cleanup callbacks.
            _travel_buff_reset_pending = None  # A new controller cannot inherit the old owner's buffs.
        manager = controller.GetSkillManager()
        if manager is None:
            return
        if getattr(manager, "bUpdatingSkills", False):
            return
        skills = tuple(manager.ActiveSkills)
        if not _sync_forbearance(controller, manager, skills, context_ids, float(world.TimeSeconds)):
            return
        if not _sync_kill_mastery(controller, manager, skills):
            return
        if not _sync_healthy_turret_bonus(controller, manager, skills):
            return
        if not _sync_steady_launcher(controller, manager, skills):
            return
        if not _sync_ready_movement(controller, manager, skills):
            return
        if not _refresh_class_mod_effects(controller, manager, skills, context_ids, wall_time):
            return
        if not _sync_ranger(controller, manager, skills, context_ids, float(world.TimeSeconds), update_hud=False):
            return
        execution_rank, double_rank, resourceful_rank, crisis_rank, pressure_rank = 0, 0, 0, 0, 0
        scorpio = None
        metal_storm = mastery = None
        for skill in skills:
            if skill.Definition is None or skill.SkillInstigator != controller:
                continue
            address = int(skill.Definition._get_address())
            if address == _metal_storm_address and int(skill.SkillState) == _overload_active_state:
                metal_storm = skill
            elif address == _boost_definition_address and int(skill.SkillState) == _overload_active_state:
                mastery = skill
            if address == _crisis_definition_address and int(skill.SkillState) == _last_ditch_active_state:
                crisis_rank = max(crisis_rank, int(skill.Grade))
            elif address == _pressure_definition_address and int(skill.SkillState) == _last_ditch_active_state:
                pressure_rank = max(pressure_rank, int(skill.Grade))
            elif address == _last_ditch_definition_address and int(skill.SkillState) == _last_ditch_active_state:
                execution_rank = max(execution_rank, int(skill.Grade))
            elif address == _double_up_definition_address and int(skill.SkillState) == _double_up_active_state:
                double_rank = max(double_rank, int(skill.Grade))
            elif address == _resourceful_definition_address and int(skill.SkillState) == _resourceful_active_state:
                resourceful_rank = max(resourceful_rank, int(skill.Grade))
            elif address == _resourceful_scorpio_address and int(skill.SkillState) == _resourceful_active_state:
                scorpio = skill
        if metal_storm is not None:
            _metal_storm_context = dict(identity=context_ids, time=float(world.TimeSeconds),
                skill=WeakPointer(metal_storm), mastery=WeakPointer(mastery) if mastery is not None else None)
        _sync_resourceful_duration(controller, scorpio, context_ids)
        if resourceful_rank > 0:
            _resourceful_context = (*context_ids, resourceful_rank, float(world.TimeSeconds))
        if execution_rank > 0:
            _last_ditch_context = (*context_ids, execution_rank, float(world.TimeSeconds))
        if crisis_rank > 0:
            _crisis_context = (*context_ids, crisis_rank, float(world.TimeSeconds))
        if pressure_rank > 0:
            _pressure_context = (*context_ids, pressure_rank, float(world.TimeSeconds))
        if double_rank > 0:
            _double_up_context = (*context_ids, float(world.TimeSeconds))
        if not _sync_duty_stacks(controller,manager,skills,context_ids,float(world.TimeSeconds)):
            return
        if _double_up_marks:
            now = float(world.TimeSeconds)
            stale = [key for key, mark in _double_up_marks.items()
                     if double_rank <= 0 or mark[1] != context_ids or mark[0] <= now]
            for key in stale:
                _double_up_marks.pop(key, None)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _last_ditch_error("Could not update Axton combat passives", exc)
    finally:
        _maintain_ranger_hud()


mod = build_mod(hooks=[begin_forbearance_radius, finish_forbearance_radius, begin_metal_storm_shot, preserve_metal_storm_ammo, mark_metal_storm_shot, finish_metal_storm_shot, begin_duty_shot, confirm_duty_shot, finish_duty_shot, bind_duty_projectile, count_duty_hit, extend_resourceful_on_kill, filter_bee_recharge_sound, begin_mag_lock_death, finish_mag_lock_death, reset_mag_lock_refund, begin_resourceful_damage, finish_resourceful_damage, prepare_ready_reload, grant_ready_reload_movement, prepare_skill_positions, finish_skill_initialization, maintain_turret_damage, retain_able_stacks, limit_able_stacks,
                       describe_turret_upgrades, describe_pressure,
                       observe_gemini_turret, maintain_gemini_aura,
                       
                       begin_ranger_shot, finish_ranger_shot, end_ranger_magazine,
                       regenerate_overload_magazine, prepare_turret_damage, prepare_turret_weapon_damage,
                       begin_last_ditch_damage, finish_last_ditch_damage, suspend_last_ditch,
                       accelerate_mag_lock_throw, mark_double_up_target, describe_nuke],
                 commands=[], keybinds=[], options=[],
                 on_enable=_enable_startup_fault_capture, on_disable=_disable_startup_fault_capture)
