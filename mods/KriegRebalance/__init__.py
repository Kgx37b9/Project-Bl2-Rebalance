"""Krieg skill and gameplay adjustments, isolated from MayaRebalance hooks."""

from __future__ import annotations

import copy
import json
import math
import random
import time
from typing import Any

import unrealsdk  # pyright: ignore[reportMissingModuleSource]
from mods_base import RestartToDisable, build_mod, command, get_pc, hook
from unrealsdk.hooks import Block, Type, prevent_hooking_direct_calls  # pyright: ignore[reportMissingModuleSource]
from unrealsdk.unreal import WrappedArray, WrappedStruct  # pyright: ignore[reportMissingModuleSource]


# Temporary opt-in audio observation. All diagnostic hooks stay disabled normally.
_audio_trace: dict[str, Any] = {}


def _stop_audio_trace() -> None:
    if not _audio_trace:
        return
    trace_krieg_actor_audio.disable()
    trace_krieg_audio_state.disable()
    events = _audio_trace.get("events", {})
    unrealsdk.logging.info(f"[KriegRebalance] Audio trace stopped: {events}")
    _audio_trace.clear()


@hook("Engine.PlayerController:WwiseClientHearSound", Type.PRE)
@hook("Engine.PlayerController:WwiseClientHearSoundReliable", Type.PRE)
@hook("Engine.PlayerController:ClientPlayAkEvent", Type.PRE)
@hook("Engine.Actor:PlayAkEvent", Type.PRE)
@hook("Engine.Actor:PostAkEvent", Type.PRE)
@hook("Engine.Actor:Behavior_PostAkEvent", Type.PRE)
def trace_krieg_actor_audio(actor: Any, args: Any, _ret: Any, _func: Any) -> None:
    if not _audio_trace:
        return
    if time.monotonic() >= _audio_trace["until"]:
        _stop_audio_trace()
        return
    try:
        if actor is None or actor._get_address() not in _audio_trace["owners"]:
            return
        event = next((getattr(args, name, None) for name in ("InSoundCue", "InAkEvent", "Event", "ASound")
                      if getattr(args, name, None) is not None), None)
        if event is None:
            return
        path = str(event._path_name())
        events = _audio_trace["events"]
        if path not in events and len(events) >= 64:
            return
        count = events.get(path, 0) + 1
        events[path] = count
        # First occurrence plus a few repeat milestones, never log each footstep/hit.
        if count in (1, 2, 8, 32):
            unrealsdk.logging.info(
                f"[KriegRebalance] Audio trace event call: event={path}, count={count}, "
                f"actor={actor._get_address()}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _stop_audio_trace()
        unrealsdk.logging.error(f"[KriegRebalance] Audio trace unavailable: {exc}")


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def trace_krieg_audio_state(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if not _audio_trace or controller._get_address() != _audio_trace["owners"][0]:
        return
    now = time.monotonic()
    if now >= _audio_trace["until"]:
        _stop_audio_trace()
        return
    if now < _audio_trace["next_sample"]:
        return
    _audio_trace["next_sample"] = now + 0.5
    try:
        world = controller.WorldInfo
        if controller.bDeleteMe or world is None or world.bDeleteMe or _world_is_departing(controller, world):
            _stop_audio_trace()
            return
        pawn = controller.GetWillowPlayerPawn()
        if pawn is None or pawn.bDeleteMe or pawn._get_address() != _audio_trace["owners"][1]:
            _stop_audio_trace()
            return
        velocity = pawn.Velocity
        moving = float(velocity.X) ** 2 + float(velocity.Y) ** 2 > 1.0
        component = pawn.GetStatusEffectsComponent()
        statuses = tuple(sorted({str(effect.StatusEffectDefinition._path_name())
                                 for effect in list(component.ActiveStatusEffects)[:32]
                                 if effect.StatusEffectDefinition is not None})) if component is not None else ()
        state = (moving, statuses)
        if _audio_trace.get("last_state") != state:
            _audio_trace["last_state"] = state
            unrealsdk.logging.info(
                f"[KriegRebalance] Audio trace state: moving={moving}, statuses={statuses}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _stop_audio_trace()
        unrealsdk.logging.error(f"[KriegRebalance] Audio trace state unavailable: {exc}")


@command("krieg_audio_trace", description="Toggle a temporary 90-second local-player audio diagnostic.")
def toggle_krieg_audio_trace(_args: Any) -> None:
    if _audio_trace:
        _stop_audio_trace()
        return
    controller = get_pc(possibly_loading=True)
    if controller is None or controller.bDeleteMe:
        return
    pawn = controller.GetWillowPlayerPawn()
    if pawn is None or pawn.bDeleteMe:
        return
    _audio_trace.update(owners=(controller._get_address(), pawn._get_address()),
                        until=time.monotonic() + 90.0, next_sample=0.0, events={})
    try:
        trace_krieg_actor_audio.enable()
        trace_krieg_audio_state.enable()
    except (AttributeError, TypeError, ValueError, RuntimeError):
        _stop_audio_trace()
        raise
    unrealsdk.logging.info(
        "[KriegRebalance] Audio trace started for 90 seconds; reproduce the noise, "
        "walk, stop, then wait for the fire to expire. Run krieg_audio_trace again to stop.")


SALT_STACKS_PATH = "GD_Lilac_Skills_Mania.Skills.SalttheWound_Stacks"
ELATION_STACKS_PATH = "GD_Lilac_Skills_Hellborn.Skills.ElementalElation_Stacks"
SALT_HUD_SLOT = 3  # Native Salt slot; slot 1 belongs to Bloodlust's counter.
SALT_DECAY_PROVIDER_PATH = "GD_Lilac_Skills_Mania.Skills.SaltTheWound:BehaviorProviderDefinition_14"
SALT_DECAY_INTERVAL = 1.5
ELATION_HUD_SLOT = 2
SILENCE_PATH = "GD_Lilac_Skills_Mania.Skills.SilenceTheVoices"
SILENCE_PROVIDER_PATH = f"{SILENCE_PATH}:BehaviorProviderDefinition_14"
SILENCE_SELF_DAMAGE_PATH = f"{SILENCE_PROVIDER_PATH}.Behavior_CauseDamage_25"
SILENCE_SELF_DAMAGE_COOLDOWN = 3.0
SILENCE_DESCRIPTION_LINE = "Self-Attack Damage is affected by [skill]Grenade Damage[-skill]."
SILENCE_CAMERA_PATHS = tuple(
    f"{SILENCE_PROVIDER_PATH}.PlayerBehavior_CameraAnim_{index}" for index in (75, 76, 77)
)
SILENCE_PARTICLE_PATHS = tuple(
    f"{SILENCE_PROVIDER_PATH}.Behavior_ScreenParticle_{index}" for index in (106, 107, 108, 109)
)
BLOOD_INITIALIZER_PATH = "GD_Lilac_Skills_Bloodlust.Attributes.Init_BloodOverdrive_MeleeDamageModifier"
BLOOD_BONUS_PATH = "GD_Lilac_Skills_Bloodlust.Attributes.Att_BloodOverdrive_PerBloodlustStackMeleeDmgBonus"
BLOOD_GRADE_PATH = "GD_Lilac_Skills_Bloodlust.SkillGrades.SkillGrade_BloodOverdrive"
BLOOD_OVERDRIVE_PATH = "GD_Lilac_Skills_Bloodlust.Skills.BloodOverdrive"
BLOOD_OVERDRIVE_CHILD_PATH = "GD_Lilac_Skills_Bloodlust.Skills.BloodOverdriveChild"
OVERCHARGE_THRESHOLD = 60
BLOOD_OVERDRIVE_SPEED_PER_RANK = 0.05
BLOOD_OVERDRIVE_FIRE_RATE_PER_RANK = 0.04
NERVOUS_BLOOD_PATH = "GD_Lilac_Skills_Bloodlust.Skills.NervousBlood"
BLOOD_OVERDRIVE_EXTRA_STACK_CHANCE_PER_RANK = 0.10
BLOODLUST_GAIN_PATH = "GD_Lilac_Skills_Bloodlust.Skills._Bloodlust:BehaviorProviderDefinition_0.Behavior_SimpleMath_154"
BLOODLUST_CAP_PATH = "GD_Lilac_Skills_Bloodlust.Skills._Bloodlust:BehaviorProviderDefinition_0.Behavior_SimpleMath_155"
BLOODLUST_STACKS_PATH = "GD_Lilac_Skills_Bloodlust.Skills.Bloodlust_Stacks"
BLOOD_FILLED_GUNS_PATH = "GD_Lilac_Skills_Bloodlust.Skills.BloodfilledGuns"
BLOOD_FILLED_MAGAZINE_PER_RANK_STACK = 0.0025
BLOOD_FILLED_DAMAGE_PER_RANK_STACK = 0.004
BLOOD_BATH_PATH = "GD_Lilac_Skills_Bloodlust.Skills.BloodBath"
BLOOD_BATH_DAMAGE_PER_RANK_STACK = 0.003
_blood_filled_tuning_revision = 0
# Verified in the original HUD.gfx: image and stackingText are sibling clips.
BLOODLUST_IMAGE_PATH = "_root.p1.triggeredSkills.rush{slot}.placeholderTexture"
BLOODLUST_RED_RGB = (1.6, 0.06, 0.06, 0.3, 0.0, 0.0)
OVERCHARGE_TARGETS = (
    ("BloodfilledGuns", "Init_BandityGuns_MagSizeModifier"),
    ("BloodyTwitch", "Init_BloodyTwitch_WeapSwapModifier"),
    ("BloodBathChild", "Init_BloodBath_DamageModifier"),
    ("FuelTheBloodChild", "Init_FuelTheFrenzy_GrenadeDamageModifier"),
    ("NervousBlood", "Init_NervousEnergy_ReloadModifier"),
)
OVERCHARGE_DESCRIPTION = (
    "[skill]Kill Skill[-skill]. While active, your normal Bloodlust gains have a chance to grant an "
    "[skill]additional Bloodlust stack[-skill]. At [skill]60 or more Bloodlust stacks[-skill], "
    "your [skill]Movement Speed[-skill] and [skill]Fire Rate[-skill] are also increased."
)
BLOOD_TWITCH_PATH = "GD_Lilac_Skills_Bloodlust.Skills.BloodyTwitch"
BLOOD_TWITCH_INITIALIZER_PATH = "GD_Lilac_Skills_Bloodlust.Attributes.Init_BloodyTwitch_WeapSwapModifier"
BLOOD_TWITCH_MELEE_PER_RANK_STACK = 0.0015
BLOOD_TWITCH_AMMO_REGEN_PER_RANK_STACK = 0.00005
BLOOD_TWITCH_AMMO_TYPES = (
    "Combat_Rifle", "Combat_Shotgun", "Patrol_SMG", "Repeater_Pistol",
    "Rocket_Launcher", "Sniper_Rifle",
)
BASE_SKILL_RANK_LIMIT = 5
BLOOD_TWITCH_DESCRIPTION = (
    "[skill]Kill Skill[-skill]. Killing an enemy increases your "
    "[skill]Weapon Swap Speed[-skill] and [skill]Melee Damage[-skill], "
    "and regenerates [skill]Reserve Ammo[-skill] every second, "
    "for each stack of [skill]Bloodlust[-skill]."
)
BLOODY_REVIVAL_PATH = "GD_Lilac_Skills_Bloodlust.Skills.BloodyRevival"
BLOODY_REVIVAL_HUD_PATH = f"{BLOODY_REVIVAL_PATH}:KriegRebalance_BloodyRevivalHUD"
BLOODY_REVIVAL_BONUS_PATH = f"{BLOODY_REVIVAL_PATH}:KriegRebalance_RevivalBonuses"
BLOODY_REVIVAL_HEALTH_PATH = f"{BLOODY_REVIVAL_PATH}:HealthStateExpressionEvaluator_1"
ON_FOOT_CONSTRAINT_PATH = "GD_PlayerShared.SkillConstraints.SkillConstraint_OnFootOrRidingInBack"
BLOODY_REVIVAL_DAMAGE_PER_RANK = 0.10
BLOODY_REVIVAL_DAMAGE_PER_SECOND_WIND = 0.02
BLOODY_REVIVAL_REDUCTION_PER_SECOND_WIND = 0.03
BLOODY_REVIVAL_MAX_SECOND_WINDS = 5
BLOODY_REVIVAL_DESCRIPTION = (
    "[skill]Gun Damage[-skill] during [skill]Fight For Your Life[-skill] is increased. "
    "Each time you get a [skill]Second Wind[-skill] gain [skill]Gun Damage[-skill] and "
    "[skill]Damage Reduction[-skill] up to 5 stacks until you die."
)
FLAME_FLARE_PATH = "GD_Lilac_Skills_Hellborn.Skills.FlameFlare"
FLAME_DURATION_ATTRIBUTE = "D_Attributes.StatusEffectModifiers.IgniteDurationResistanceModifier"
FLAME_RESISTANCE_ATTRIBUTE = "D_Attributes.DamageTypeModifers.IncendiaryStatusEffectDamageModifier"
FLAME_RESISTANCE_PER_RANK = -0.15
FLAME_FLARE_DESCRIPTION = (
    "Increases the duration of all [incendiary]Burn Effects[-incendiary] on you. "
    "Each time you apply a [incendiary]Burn Effect[-incendiary] to an enemy there's a chance "
    "another [incendiary]Burn Effect[-incendiary] will be applied after a short time. "
    "You also gain burn damage resistance."
)
FLAME_FLARE_STAT = "Reignite Chance: $NUMBER$<br>Burn Damage Resistance: $NUMBER$"
BURN_BABY_BURN_PATH = "GD_Lilac_Skills_Hellborn.Skills.BurnBabyBurn"
BURN_BABY_BURN_CHILD_PATH = "GD_Lilac_Skills_Hellborn.Skills.BurnBabyBurnChild"
STRIP_THE_FLESH_PATH = "GD_Lilac_Skills_Mania.Skills.StripTheFlesh"
STRIP_THE_FLESH_ATTRIBUTE = "D_Attributes.DamageTypeModifers.InstigatedExplosiveDamageModifier"
STRIP_THE_FLESH_BONUS_PER_RANK = 0.05
FUEL_THE_FIRE_PATH = "GD_Lilac_Skills_Hellborn.Skills.FuelTheFire"
# VERIFICAR no Object Explorer: atributo de dano incendiario direto, lado de quem causa o dano.
FUEL_THE_FIRE_DAMAGE_ATTRIBUTE = "D_Attributes.DamageTypeModifers.InstigatedIncindiaryDamageModifier"
FUEL_THE_FIRE_DAMAGE_PER_RANK = 0.04
FUEL_THE_FIRE_DESCRIPTION = (
    "[skill]Kill Skill[-skill]. Killing an enemy increases your [skill]Status Effect Chance[-skill] "
    f"and your direct [incendiary]Incendiary Damage[-incendiary]. "
    "Igniting an enemy has a chance to also light you on fire."
)
ELEMENTAL_EMPATHY_PATH = "GD_Lilac_Skills_Hellborn.Skills.ElementalEmpathy"
ELEMENTAL_EMPATHY_HEALING_PATH = (
    "GD_Lilac_Skills_Hellborn.Attributes.Att_ElementalEmpathy_HealingPerGrade:ConstantAttributeValueResolver_0"
)
ELEMENTAL_EMPATHY_HEALING_PER_RANK = 0.10
NUMBED_NERVES_PATH = "GD_Lilac_Skills_Hellborn.Skills.NumbedNerves"
NUMBED_INITIALIZER_PATH = "GD_Lilac_Skills_Hellborn.Attributes.Init_NumbedNerves_DamageReduction"
NUMBED_REDUCTION_PER_RANK = 0.075
NUMBED_DESCRIPTION = (
    "All [skill]damage received[-skill] is reduced. This [skill]Damage Reduction[-skill] "
    "is doubled [incendiary]while you are on fire[-incendiary]."
)
RAVING_RETRIBUTION_PATH = "GD_Lilac_Skills_Hellborn.Skills.RavingRetribution"
RAVING_NEUTRAL_TYPE_NAME = "KriegRebalance_RavingNeutral"
RAVING_DESCRIPTION_LINE = (
    "Your [incendiary]Incendiary Damage[-incendiary], including [incendiary]Burn Damage[-incendiary], "
    "no longer suffers damage penalties against [skill]Shields[-skill] and [skill]Armor[-skill]. "
    "The damage bonus against [skill]Flesh[-skill] is unchanged."
)
HELLFIRE_PATH = "GD_Lilac_Skills_Hellborn.Skills.HellfireHalitosis"
HELLFIRE_MELEE_PATH = "GD_Lilac_Skills_Hellborn.MeleeOverride.Melee_HellfireHalitosis"
HELLFIRE_PROVIDER_PATH = f"{HELLFIRE_PATH}:BehaviorProviderDefinition_0"
HELLFIRE_ATTACK_PATH = f"{HELLFIRE_PROVIDER_PATH}.Behavior_MeleeAttack_0"
HELLFIRE_IGNITION_PATH = f"{HELLFIRE_PATH}:KriegRebalance_HellfireIgnition"
HELLFIRE_SPEED_PATH = f"{HELLFIRE_PATH}:KriegRebalance_HellfireSpeed"
HELLFIRE_SPEED_BONUS = 0.15
HELLFIRE_DESCRIPTION = (
    "[skill]Melee Override Skill[-skill]. Pressing <StringAliasMap:Action.Melee> causes you to "
    "[incendiary]breathe fire[-incendiary] in a cone in front of you. "
    "This skill benefits from [skill]Melee Damage bonuses[-skill] and "
    "[incendiary]sets you on fire[-incendiary] when used. "
    "While [incendiary]on fire[-incendiary], gain [skill]15% Movement Speed[-skill]."
)
FUEL_RAMPAGE_PATH = "GD_Lilac_Skills_Mania.Skills.FuelTheRampage"
FUEL_SPEED_PATH = f"{FUEL_RAMPAGE_PATH}:KriegRebalance_FuelSpeed"
FUEL_HUD_PATH = f"{FUEL_RAMPAGE_PATH}:KriegRebalance_FuelHUD"
FUEL_SPEED_ATTRIBUTE = "D_Attributes.GameplayAttributes.FootSpeed"
FUEL_REDUCTION_PER_RANK = 0.09
FUEL_SPEED_PER_RANK = 0.10
FUEL_SPEED_DURATION = 12.0
FUEL_DESCRIPTION = (
    "Reduces [skill]Self-Damage[-skill] from your own direct attacks. "
    "Taking direct self-damage also increases your [skill]Movement Speed[-skill] "
    "for 12 seconds. Further hits refresh the duration; this bonus does not stack. "
    "[skill]Status Effect Damage[-skill] neither receives this reduction nor activates the speed bonus."
)
LIGHT_FUSE_PATH = "GD_Lilac_Skills_Mania.Skills.LightTheFuse"
LIGHT_FUSE_SPEED_PATH = "GD_Lilac_Skills_Mania.Skills.LightTheFuseSpeedBoost"
LIGHT_FUSE_OVERRIDE_BEHAVIOR = f"{LIGHT_FUSE_PATH}:BehaviorProviderDefinition_0.Behavior_AttributeEffect_4"
LIGHT_FUSE_INJURED_PATH = "GD_Lilac_Psycho_Streaming.Character.PsychoInjuredDefinitionOverride"
GRENADE_REGEN_ATTRIBUTE = "D_Attributes.Ammo_Grenade_Protean.Ammo_Grenade_ProteanActiveRegenerationRate"
LIGHT_FUSE_GRENADE_INTERVAL = 10.0
LIGHT_FUSE_DESCRIPTION = (
    "Passively [skill]regenerate grenades[-skill], gaining one grenade every 10 seconds. "
    "This regeneration stacks with other sources of [skill]Grenade Regeneration[-skill]."
)
PAIN_IS_POWER_PATH = "GD_Lilac_Skills_Hellborn.Skills.PainIsPower"
PAIN_STACK_EFFECT_PATH = f"{PAIN_IS_POWER_PATH}:KriegRebalance_PainStacks"
PAIN_HUD_PATH = f"{PAIN_IS_POWER_PATH}:KriegRebalance_PainHUD"
PAIN_CRIT_ATTRIBUTE = "D_Attributes.GameplayAttributes.PlayerCriticalHitBonus"
PAIN_SPREAD_ATTRIBUTE = "D_Attributes.Weapon.WeaponSpread"
PAIN_MELEE_ATTRIBUTE = "D_Attributes.DamageSourceModifiers.InstigatedMeleeDamageModifier"
PAIN_CRIT_PER_RANK = 0.02
PAIN_SPREAD_PER_RANK = 0.025
PAIN_MELEE_PER_RANK = 0.02
PAIN_STACK_LIMIT = 5
PAIN_DECAY_DELAY = 5.0
PAIN_DECAY_INTERVAL = 2.0
PAIN_DESCRIPTION = (
    "Taking [skill]Health Damage[-skill] grants a stack of [skill]Pain is Power[-skill], "
    "increasing [skill]Critical Hit Damage[-skill] and [skill]Melee Damage[-skill] "
    "but reducing [skill]Accuracy[-skill]. "
    "Maximum stacks: 5.<br><br>After 5 seconds without taking health damage, "
    "lose one stack, then one more every 2 seconds."
)
BURN_BABY_BURN_VALUES = (
    ("GD_Lilac_Skills_Hellborn.Attributes.Att_BurnBabyBurn_BurnModifierBonus:ConstantAttributeValueResolver_0", 0.20),
    ("GD_Lilac_Skills_Hellborn.Attributes.Att_BurnBabyBurn_BurnModifierBonusWhileOnFire:ConstantAttributeValueResolver_0", 0.10),
)
BLOOD_EUPHORIA_PATH = "GD_Lilac_Skills_Bloodlust.Skills.BloodEuphoria"
BLOOD_EUPHORIA_RESOLVER_PATH = (
    "GD_Lilac_Skills_Bloodlust.Attributes.Att_BloodEuphoria_PerGradeHealthModifier:ConstantAttributeValueResolver_0"
)
BLOODLUST_STACK_ATTRIBUTE = "GD_Lilac_Skills_Bloodlust.Attributes.Att_Bloodlust_StackCount"
BLOOD_EUPHORIA_REGEN_PER_STACK = 0.001
BLOOD_EUPHORIA_DESCRIPTION = (
    "Regenerate a portion of your [skill]Maximum Health[-skill] every second "
    "for each stack of [skill]Bloodlust[-skill]."
)
BLOODLUST_LAYOUT_PATH = "GD_Lilac_SkillsBase.SkillTree.Layout_Bloodlust"
BLOODLUST_BRANCH_PATH = "GD_Lilac_SkillsBase.SkillTree.Branch_Bloodlust"
BLOOD_EUPHORIA_NEIGHBORS = (
    "GD_Lilac_Skills_Bloodlust.Skills.BloodTrance",
    "GD_Lilac_Skills_Bloodlust.Skills.BoilingBlood",
)
PULL_THE_PIN_PATH = "GD_Lilac_Skills_Mania.Skills.PullThePin"
PULL_THE_PIN_XP_PATH = "GD_Lilac_Skills_Mania.Skills.PullThePinXPBonus"
PULL_THE_PIN_OLD_SPAWN = (
    f"{PULL_THE_PIN_PATH}:BehaviorProviderDefinition_14.PlayerBehavior_SpawnCurrentProjectile_0"
)
FFYL_GRENADE_ATTRIBUTE = "D_Attributes.SkillAttributes.CanThrowGrenadesWhileInDownState"
PULL_THE_PIN_DESCRIPTION = (
    "You can throw [skill]grenades[-skill] while in [skill]Fight For Your Life[-skill]."
)
SPECIAL_MELEE_INITIALIZER_PATH = "GD_Lilac_SkillsBase.ActionSkill.Init_RampageBonusDamagePerLevel"
SPECIAL_MELEE_GAME_STAGE_PATH = "GD_Lobelia_GameStages.Attributes.GameStageViaGetGameStage"
SPECIAL_MELEE_FORMULA_TERMS = (
    ("Multiplier", 1.0, 1.0), ("Level", 0.0, 0.02),
    ("Power", 1.0, 1.0), ("Offset", 1.0, 1.0),
)
CLASS_MOD_SKILL_PATHS = {
    "bloodfilledguns": BLOOD_FILLED_GUNS_PATH,
    "bloodoverdrive": BLOOD_OVERDRIVE_PATH,
    "bloodtwitch": BLOOD_TWITCH_PATH,
    "bloodytwitch": BLOOD_TWITCH_PATH,
    "bloodyrevival": BLOODY_REVIVAL_PATH,
    "flameflare": FLAME_FLARE_PATH,
    "fuelthefire": FUEL_THE_FIRE_PATH,
    "burnbabyburn": BURN_BABY_BURN_PATH,
    "painispower": PAIN_IS_POWER_PATH,
    "firefiend": STRIP_THE_FLESH_PATH,  
    "elementalempathy": ELEMENTAL_EMPATHY_PATH,
    "numbednerves": NUMBED_NERVES_PATH,
    "fueltherampage": FUEL_RAMPAGE_PATH,
}
CLASS_MOD_RANK_LIMIT = 6
EFFECTIVE_SKILL_RANK_LIMIT = 11
CLASS_MOD_REFRESH_INTERVAL = 1.0
MAINTENANCE_INTERVAL = 2.0
_next_apply_at = 0.0
_configured_skill_steps: set[str] = set()
_configuration_world: int | None = None
_next_live_sync: dict[int, float] = {}
_next_pull_sync: dict[int, float] = {}
_fuel_speed_until: dict[int, tuple[int, int, float]] = {}
_next_fuel_sync: dict[int, float] = {}
_fuel_hud_owners: set[int] = set()
_next_light_fuse_sync: dict[int, float] = {}
_silence_self_damage_at: dict[tuple[int, int], float] = {}
_pain_stacks: dict[tuple[int, int], tuple[int, float]] = {}
_pain_damage_frames: list[dict[str, Any] | None] = []
_next_pain_sync: dict[int, float] = {}
_pain_owner_keys: dict[int, tuple[int, int]] = {}
_next_pain_hud_sync: dict[int, float] = {}
_next_bloody_revival_sync: dict[int, float] = {}
_next_bloody_revival_hud_sync: dict[int, float] = {}
_pain_hud_context: tuple[int, int] | None = None
_pain_hud_departing_context: tuple[int, int] | None = None
_burn_tuning_revision = 0
_hellborn_tuning_revision = 0
_blood_twitch_tuning_revision = 0
_overcharge_revision = 0
_overcharge_refreshed: dict[tuple[int, int, int], int] = {}
_overcharge_restore_paths: set[str] = set()
_blood_overdrive_configured = False
_bloodlust_gain_address = 0
_blood_overdrive_gain_scopes: list[dict[str, Any]] = []
_bloodlust_tint_state: dict[int, tuple[int, int, int, tuple[float, ...]]] = {}
_next_bloodlust_tint: dict[int, float] = {}
_burn_refreshed: dict[tuple[int, int, int], int] = {}
_class_mod_cache: dict[int, tuple[int, int, float, dict[str, int]]] = {}
_class_mod_effect_cache: dict[tuple[int, int], tuple[int, int, int, int, int]] = {}
_verified_fixes: set[str] = set()
_reported_errors: set[str] = set()
_bloody_revival_state: dict[int, dict[str, Any]] = {}
_bloody_revival_recovery_frames: list[tuple[int, int, int] | None] = []
_bloody_revival_ffyl_watch: dict[int, dict[str, int]] = {}
_prepared_runtime_leaves: set[str] = set()  # Private paths only; never UObject references.


def _find(class_name: str, path: str) -> Any | None:
    """Missing streamed DLC assets are pending, not an error or a reason to force-load."""
    try:
        return unrealsdk.find_object(class_name, path)
    except ValueError:
        return None



def _world_is_departing(controller: Any, world: Any) -> bool:
    if _pain_hud_departing_context is None:
        return False  # Normal gameplay does not need any native identity reads.
    owner = controller._get_address()
    return _pain_hud_departing_context in ((owner, world._get_address()), (owner, 0))


def _set_property(obj: Any, field: str, value: Any) -> None:
    if getattr(obj, field) == value:
        return  # One native read for unchanged fields; read back only a real write.
    setattr(obj, field, value)
    if getattr(obj, field) != value:
        raise RuntimeError(f"Native field did not retain its value: {field}")


def _native_data_matches(actual: Any, expected: Any) -> bool:
    """Opt-in structural comparison for Raving/Numbed; never traverse UObjects."""
    if isinstance(actual, WrappedStruct) or isinstance(expected, WrappedStruct):
        if not isinstance(actual, WrappedStruct) or not isinstance(expected, WrappedStruct):
            return False
        if actual._type._get_address() != expected._type._get_address():
            return False
        return all(_native_data_matches(getattr(actual, str(prop.Name)), getattr(expected, str(prop.Name)))
                   for prop in actual._type._properties())
    if isinstance(actual, (WrappedArray, list, tuple)) or isinstance(expected, (WrappedArray, list, tuple)):
        return (isinstance(actual, (WrappedArray, list, tuple))
                and isinstance(expected, (WrappedArray, list, tuple))
                and len(actual) == len(expected)
                and all(_native_data_matches(left, right) for left, right in zip(actual, expected)))
    if isinstance(actual, float) and isinstance(expected, float):
        return math.isclose(actual, expected, rel_tol=0.000001, abs_tol=0.0000001)
    return actual == expected  # Scalars and UObject references retain normal equality.


def _copy_native_data(value: Any) -> Any:
    if isinstance(value, WrappedStruct):
        return copy.copy(value)  # Owned native copy, including nested arrays.
    if isinstance(value, (WrappedArray, list, tuple)):
        return [_copy_native_data(item) for item in value]
    return value


def _set_native_data(obj: Any, field: str, expected: Any) -> bool:
    if _native_data_matches(getattr(obj, field), expected):
        return False
    # Replacing an array may invalidate the element views used to build it.
    # Readback must compare against owned data, not the previous native buffer.
    expected = _copy_native_data(expected)
    setattr(obj, field, expected)
    if not _native_data_matches(getattr(obj, field), expected):
        raise RuntimeError(f"Native data did not retain its fields: {field}")
    return True


def _class_mod_skill_ranks(controller: Any) -> dict[str, int]:
    """Maya's invested/bonus model, using Krieg names and only the equipped COM."""
    if controller is None or controller.bDeleteMe:
        return {}
    world = controller.WorldInfo
    if world is None or world.bDeleteMe:
        return {}
    pawn = controller.GetWillowPlayerPawn()
    if pawn is None or pawn.bDeleteMe or pawn.Controller != controller:
        return {}
    address, pawn_address = controller._get_address(), pawn._get_address()
    inventory = pawn.InvManager
    equipped = inventory.GetCurrentClassMod() if inventory is not None else None
    equipped_address = equipped._get_address() if equipped is not None else 0
    now = time.monotonic()
    previous = _class_mod_cache.get(address)
    if (previous is not None and previous[:2] == (pawn_address, equipped_address)
            and now < previous[2]):
        return previous[3]
    bonuses: dict[str, int] = {}
    if equipped is not None:
        stats = equipped.ItemCardModifierStats
        if len(stats) > 64:
            raise ValueError("Equipped class mod has more than 64 item-card stats")
        for stat in stats:
            presentation = stat.AttributePresentation
            if presentation is None:
                continue
            name = str(presentation.Name)
            if not name.startswith("AttrPresent_"):
                continue
            # Lilac COMs use AttrPresent_FlameFlare; Lobelia COMs use
            # AttrPresent_Lobelia_FlameFlare, not Maya's .Skills_ namespace.
            name = name.removeprefix("AttrPresent_").removeprefix("Lobelia_").casefold()
            path = CLASS_MOD_SKILL_PATHS.get(name)
            value = float(stat.ModifierValue)
            if path is None or not math.isfinite(value) or value <= 0 or not value.is_integer():
                continue
            bonuses[path] = min(CLASS_MOD_RANK_LIMIT, bonuses.get(path, 0) + int(value))
    if len(_class_mod_cache) >= 16 and address not in _class_mod_cache:
        _class_mod_cache.clear()
    _class_mod_cache[address] = (pawn_address, equipped_address, now + CLASS_MOD_REFRESH_INTERVAL, bonuses)
    if previous is None or previous[3] != bonuses:
        summary = ", ".join(f"{path.rsplit('.', 1)[-1]}=+{rank}" for path, rank in sorted(bonuses.items())) or "none"
        unrealsdk.logging.info(f"[KriegRebalance] Detected class-mod skill bonuses: {summary}")
    return bonuses


def _class_mod_skill_rank(controller: Any, skill_path: str) -> int:
    return min(CLASS_MOD_RANK_LIMIT, _class_mod_skill_ranks(controller).get(skill_path, 0))


def _effective_skill_rank(controller: Any, skill_path: str, invested_rank: int) -> int:
    if invested_rank <= 0:
        return 0  # Equipment alone must not enable a skill.
    return min(EFFECTIVE_SKILL_RANK_LIMIT,
               invested_rank + _class_mod_skill_rank(controller, skill_path))


def _refresh_class_mod_skill_caches(controller: Any) -> None:
    """Invalidate native effect caches, never add COM points to an already boosted Grade."""
    if controller is None or controller.bDeleteMe:
        return
    world = controller.WorldInfo
    if world is None or world.bDeleteMe:
        return
    pawn = controller.GetWillowPlayerPawn()
    if pawn is None or pawn.bDeleteMe or pawn.Controller != controller:
        return
    manager = controller.GetSkillManager()
    if manager is None:
        return
    active = unrealsdk.find_enum("ESkillState").SKILL_Active
    for skill in list(manager.ActiveSkills):
        if (skill.SkillInstigator != controller or skill.Definition is None
                or int(skill.Grade) <= 0 or skill.SkillState != active):
            continue
        path = str(skill.Definition._path_name())
        parent_path = {BURN_BABY_BURN_CHILD_PATH: BURN_BABY_BURN_PATH,
                       BLOOD_OVERDRIVE_CHILD_PATH: BLOOD_OVERDRIVE_PATH}.get(path, path)
        if parent_path not in CLASS_MOD_SKILL_PATHS.values():
            continue  # One-point gamechangers and unrelated skills retain their own logic.
        parent = (_find("SkillDefinition", parent_path) if path != parent_path else skill.Definition)
        if parent is None:
            continue
        invested = int(controller.GetSkillGrade(parent))
        effective = _effective_skill_rank(controller, parent_path, invested)
        if effective <= 0:
            continue
        address = controller._get_address()
        snapshot = _class_mod_cache.get(address)
        pawn_address, equipped_address = snapshot[:2] if snapshot is not None else (0, 0)
        key = (address, skill._get_address())
        signature = (int(skill.Grade), effective, pawn_address, equipped_address,
                     _burn_tuning_revision if parent_path == BURN_BABY_BURN_PATH else
                     _hellborn_tuning_revision if parent_path in (
                          NUMBED_NERVES_PATH, ELEMENTAL_EMPATHY_PATH) else
                     _blood_twitch_tuning_revision if parent_path == BLOOD_TWITCH_PATH else
                     _blood_filled_tuning_revision if parent_path == BLOOD_FILLED_GUNS_PATH else 0)
        if _class_mod_effect_cache.get(key) == signature:
            continue
        if len(_class_mod_effect_cache) >= 64:
            _class_mod_effect_cache.clear()
        # Child Grade may stay at 1 while its formulas read the parent's COM-
        # boosted rank. The parent's effective rank must also invalidate this cache.
        skill.bForceRefreshModifiersNextTick = True
        _class_mod_effect_cache[key] = signature


def _hellfire_value(template: Any, constant: float, initializer: Any = None) -> Any:
    value = copy.copy(template)
    value.BaseValueConstant = constant
    value.BaseValueAttribute = None
    value.InitializationDefinition = initializer
    value.BaseValueScaleConstant = 1.0
    return value


def _wire_hellfire_ignition(provider: Any, attack: Any, ignition: Any) -> bool:
    """Append one native activation leaf, preserving existing links and indices."""
    # Behavior VariableData can contain non-reflected native payload. Never copy
    # or replace the whole sequence: SDK struct copies only reflected properties.
    for sequence in provider.BehaviorSequences:
        events = list(sequence.EventData2)
        event_index = next((i for i, event in enumerate(events)
                            if str(event.UserData.EventName) == "OnMeleeOverrideSkillActivated"), None)
        if event_index is None:
            continue
        nodes = list(sequence.BehaviorData2)
        original = next((node for node in nodes if node.Behavior == attack), None)
        if original is None:
            raise ValueError("Hellfire Halitosis native attack node is missing")
        matches = [i for i, node in enumerate(nodes) if node.Behavior == ignition]
        if len(matches) > 1:
            raise ValueError("Hellfire Halitosis has duplicate ignition nodes")
        event = events[event_index]
        packed = int(event.OutputLinks.ArrayIndexAndLength) & 0xFFFFFFFF
        start, count = packed >> 16, packed & 0xFFFF
        links = list(sequence.ConsolidatedOutputLinkData)
        variable_links = list(sequence.ConsolidatedVariableLinkData)
        if not count or start + count > len(links):
            raise ValueError("Hellfire Halitosis activation links are invalid")
        if matches:
            node_index = matches[0]
            if any((int(link.LinkIdAndLinkedBehavior) & 0xFFFFFF) == node_index
                   for link in links[start:start + count]):
                return False  # Already connected; do not grow the graph every maintenance pass.
        else:
            node_index = len(nodes)
            node = copy.copy(original)
            context_packed = int(original.LinkedVariables.ArrayIndexAndLength) & 0xFFFFFFFF
            context_start, context_count = context_packed >> 16, context_packed & 0xFFFF
            if context_count != 1 or context_start >= len(variable_links):
                raise ValueError("Hellfire Halitosis Player context link is invalid")
            # Use the existing native INPUT link type, but point TargetContext[0]
            # explicitly at Player as the vanilla Hellborn self-ignite graph does.
            input_template = next((entry for entry in variable_links
                                   if str(entry.PropertyName) == "InstanceData Context"), None)
            if input_template is None or len(variable_links) > 0xFFFF:
                raise ValueError("Hellfire Halitosis native input link template is missing")
            context = copy.copy(variable_links[context_start])
            if str(context.PropertyName) != "Context":
                raise ValueError("Hellfire Halitosis attack does not resolve the Player context")
            context.CachedProperty = None
            target = copy.copy(input_template)
            target.PropertyName, target.ConnectionIndex, target.CachedProperty = "TargetContext", 0, None
            target.LinkedVariables = copy.copy(context.LinkedVariables)
            linked = copy.copy(node.LinkedVariables)
            linked.ArrayIndexAndLength = (len(variable_links) << 16) | 2
            node.LinkedVariables = linked
            variable_links += [context, target]
            node.Behavior = ignition
            outputs = copy.copy(node.OutputLinks)
            outputs.ArrayIndexAndLength = 0
            node.OutputLinks = outputs
            nodes.append(node)
        if len(links) > 0xFFFF or count >= 0xFFFF or node_index > 0x7FFFFF:
            raise ValueError("Hellfire Halitosis activation graph exceeds native index limits")
        activation = [copy.copy(link) for link in links[start:start + count]]
        link = copy.copy(activation[0])
        link.LinkIdAndLinkedBehavior, link.ActivateDelay = node_index, 0.0
        activation.append(link)
        outputs = copy.copy(event.OutputLinks)
        outputs.ArrayIndexAndLength = (len(links) << 16) | len(activation)
        # Publish new nodes/links first, then their entry point. All old indices,
        # event data and native variable payload remain at their original sites.
        if not matches:
            _set_native_data(sequence, "ConsolidatedVariableLinkData", variable_links)
        _set_native_data(sequence, "BehaviorData2", nodes)
        _set_native_data(sequence, "ConsolidatedOutputLinkData", links + activation)
        _set_native_data(event, "OutputLinks", outputs)
        return True
    raise ValueError("Hellfire Halitosis activation event is missing")


def _configure_hellfire_halitosis() -> bool:
    definition = _find("SkillDefinition", HELLFIRE_PATH)
    melee = _find("MeleeDefinition", HELLFIRE_MELEE_PATH)
    provider = _find("BehaviorProviderDefinition", HELLFIRE_PROVIDER_PATH)
    attack = _find("Behavior_MeleeAttack", HELLFIRE_ATTACK_PATH)
    source = _find("Class", "WillowGame.WillowDmgSource_Melee")
    foot = _find("AttributeDefinition", FUEL_SPEED_ATTRIBUTE)
    fire = _find("AttributeExpressionEvaluator", f"{NUMBED_NERVES_PATH}:AttributeExpressionEvaluator_0")
    template = _find("AttributeInitializationDefinition", NUMBED_INITIALIZER_PATH)
    status = _find("StatusEffectDefinition", "GD_Incendiary.StatusEffect.Status_Incendiary")
    attempt = _find("Behavior_AttemptStatusEffect", "WillowGame.Default__Behavior_AttemptStatusEffect")
    self_burn = _find("Behavior_CauseDamage", "GD_Lilac_Skills_Hellborn.Skills.AppliedStatusEffectListener:"
                      "BehaviorProviderDefinition_0.Behavior_CauseDamage_2")
    if (definition is None or melee is None or provider is None or attack is None or source is None
            or foot is None or fire is None or template is None or status is None
            or attempt is None or self_burn is None):
        return False
    rows = list(template.ConditionalInitialization.ConditionalExpressionList)
    effects = list(definition.SkillEffectDefinitions)
    if not rows or not effects:
        raise ValueError("Hellfire Halitosis speed templates are unavailable")
    ignition = _find("Behavior_AttemptStatusEffect", HELLFIRE_IGNITION_PATH)
    if ignition is None:
        ignition = unrealsdk.construct_object("Behavior_AttemptStatusEffect", definition,
                                               "KriegRebalance_HellfireIgnition", template_obj=attempt)
    _set_property(ignition, "StatusEffect", status)
    _set_native_data(ignition, "Context", copy.copy(attack.Context))
    _set_native_data(ignition, "TargetContext", [copy.copy(self_burn.TargetContext)])
    # A real native burn, without a direct self-hit or weapon-scaled self-damage.
    # Standard duration/resistance/FireStatusDetector remain owned by the engine.
    for field, amount in (("InstigatorChanceModifier", 1.0), ("StatusEffectDamage", 1.0),
                          ("StatusEffectChance", 1000.0)):
        _set_native_data(ignition, field, _hellfire_value(getattr(attempt, field), amount))
    speed = _find("AttributeInitializationDefinition", HELLFIRE_SPEED_PATH)
    if speed is None:
        speed = unrealsdk.construct_object("AttributeInitializationDefinition", definition,
                                            "KriegRebalance_HellfireSpeed", template_obj=template)
    row = copy.copy(rows[0])
    row.Expressions = [copy.copy(fire.Expression)]  # Any source of actual fire, not last Halitosis use.
    row.BaseValueIfTrue = _hellfire_value(row.BaseValueIfTrue, HELLFIRE_SPEED_BONUS)
    conditional = copy.copy(template.ConditionalInitialization)
    conditional.bEnabled = True
    conditional.ConditionalExpressionList = [row]
    conditional.DefaultBaseValue = _hellfire_value(conditional.DefaultBaseValue, 0.0)
    _set_native_data(speed, "ConditionalInitialization", conditional)
    formula = copy.copy(speed.ValueFormula)
    formula.bEnabled = False
    _set_native_data(speed, "ValueFormula", formula)
    random = copy.copy(speed.RandomVariance)
    random.bEnabled = False
    _set_native_data(speed, "RandomVariance", random)
    bounds = copy.copy(speed.RangeRestriction)
    bounds.bEnableMinValueRestriction = bounds.bEnableMaxValueRestriction = False
    _set_native_data(speed, "RangeRestriction", bounds)
    movement = copy.copy(effects[0])
    movement.AttributeToModify = foot
    movement.EffectTarget = unrealsdk.find_enum("EEffectTarget").TARGET_Self
    movement.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
    movement.BaseModifierValue = _hellfire_value(movement.BaseModifierValue, 1.0, speed)
    movement.PerGradeUpgrade = _hellfire_value(movement.PerGradeUpgrade, 0.0)
    movement.GradeToStartApplyingEffect = movement.PerGradeUpgradeInterval = 1
    movement.BonusUpgradeList = []
    _set_native_data(definition, "SkillEffectDefinitions",
                     [effect for effect in effects if effect.BaseModifierValue.InitializationDefinition != speed]
                     + [movement])
    _set_property(definition, "bAutoUpdateContexts", True)
    _set_property(melee, "DamageSource", source)
    _set_property(definition, "SkillDescription", HELLFIRE_DESCRIPTION)
    _wire_hellfire_ignition(provider, attack, ignition)
    return True


def _refresh_hellfire_speed_cache(controller: Any) -> None:
    """Handle assets arriving after tree initialization without reactivating the skill."""
    definition = _find("SkillDefinition", HELLFIRE_PATH)
    speed = _find("AttributeInitializationDefinition", HELLFIRE_SPEED_PATH)
    if definition is None or speed is None or controller is None or controller.bDeleteMe:
        return
    if get_pc(possibly_loading=True) != controller:
        return
    world = controller.WorldInfo
    if world is None or world.bDeleteMe or world.Pauser:
        return
    owner = (controller._get_address(), world._get_address())
    if _pain_hud_departing_context in (owner, (owner[0], 0)):
        return
    pawn, tree = controller.GetWillowPlayerPawn(), controller.PlayerSkillTree
    if (pawn is None or pawn.bDeleteMe or pawn.Controller != controller
            or tree is None or not tree.bInitialized or controller.IsPauseMenuOpen()):
        return
    manager = controller.GetSkillManager()
    if manager is None:
        return
    for skill in list(manager.ActiveSkills):
        if (skill.SkillInstigator != controller or skill.Definition != definition
                or int(skill.Grade) <= 0
                or skill.SkillState != unrealsdk.find_enum("ESkillState").SKILL_Active):
            continue
        expected = [effect for effect in definition.SkillEffectDefinitions if effect.AttributeToModify is not None]
        current = list(skill.SkillEffects)
        real = [effect for effect in current if effect.EffectData.AttributeToModify is not None]
        if [effect.EffectData.AttributeToModify for effect in real] != [effect.AttributeToModify for effect in expected]:
            modes = unrealsdk.find_enum("EAdjustModifierMode")
            skill.AdjustModifiers(modes.WILLOW_ADJUST_RemoveModifer, True)
            skill.SkillEffects = []
            skill.BuildSkillEffects()
            skill.AdjustModifiers(modes.WILLOW_ADJUST_InitialAddModifer, False)
            skill.bForceRefreshModifiersNextTick = True
        elif any(not _native_data_matches(applied.EffectData, data) for applied, data in zip(real, expected)):
            for applied, data in zip(real, expected):
                applied.EffectData = copy.copy(data)
            skill.SkillEffects = current
            skill.bForceRefreshModifiersNextTick = True


def _configure_raving_retribution() -> bool:
    definition = _find("SkillDefinition", RAVING_RETRIBUTION_PATH)
    if definition is None:
        return False
    description = str(definition.SkillDescription)
    if RAVING_DESCRIPTION_LINE not in description:
        _set_property(definition, "SkillDescription", description.rstrip() + "<br><br>" + RAVING_DESCRIPTION_LINE)
    return True  # Do not touch its fireball provider, events, constraints or timers.


def _raving_neutral_damage_type(original: Any) -> Any:
    """Private native variant, never change the shared elemental definitions."""
    path = f"{original._path_name()}:{RAVING_NEUTRAL_TYPE_NAME}"
    neutral = _find("WillowDamageTypeDefinition", path)
    if neutral is None:
        neutral = unrealsdk.construct_object(
            "WillowDamageTypeDefinition", original, RAVING_NEUTRAL_TYPE_NAME, template_obj=original)
    # Keep live flesh tuning and character resistances from the source, including
    # other mods. All other template properties are copied on construction.
    _set_native_data(neutral, "FleshDamageModifier", original.FleshDamageModifier)
    for field in ("CharacterDamageTypeModifierAttribute",
                  "bUseStatusEffectInstigatorModifiersForDamage", "StatusEffect", "DamageType"):
        _set_property(neutral, field, getattr(original, field))
    for field in ("ArmorDamageModifier", "ShieldDamageModifier"):
        current = getattr(neutral, field)
        if (float(current.BaseValueConstant) == 1.0 and float(current.BaseValueScaleConstant) == 1.0
                and current.BaseValueAttribute is None and current.InitializationDefinition is None):
            continue  # Repeated impacts/DoTs do not allocate copies of neutral formulas.
        value = copy.copy(current)
        value.BaseValueConstant = value.BaseValueScaleConstant = 1.0
        value.BaseValueAttribute = value.InitializationDefinition = None
        _set_native_data(neutral, field, value)
    return neutral


def _raving_error(exc: Exception) -> None:
    key = "Raving Retribution elemental efficacy"
    if key not in _reported_errors:
        _reported_errors.add(key)
        unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.PRE)
def apply_raving_elemental_efficacy(pipeline: Any, args: Any, _ret: Any, func: Any) -> tuple[type[Block], Any] | None:
    """Run native damage once with a scoped type, preserving native shield overflow."""
    original = pipeline.GetDamageTypeDef()
    if original is None:
        return None
    # A nested hit can reuse a pipeline while its caller holds the private type.
    # Recover the shared source so unrelated inner hits do not inherit the bonus.
    nested_neutral = str(original.Name) == RAVING_NEUTRAL_TYPE_NAME
    if nested_neutral:
        original = original.Outer
    desired = original
    controller = args.InDamageInstigator
    try:
        # The spelling Incindiary is the actual EDamageType member in BL2.
        incendiary = int(unrealsdk.find_enum("EDamageType").DAMAGE_TYPE_Incindiary)
        if int(getattr(original, "DamageType", -1)) != incendiary:
            return None
        target = args.InDamagedActor
        eligible = False
        if controller is not None and not controller.bDeleteMe:
            world = controller.WorldInfo
            get_pawn = getattr(controller, "GetWillowPlayerPawn", None)
            pawn = get_pawn() if get_pawn is not None else None
            if (world is not None and not world.bDeleteMe and pawn is not None
                    and not pawn.bDeleteMe and pawn.Controller == controller
                    and target is not None and not target.bDeleteMe and target != pawn
                    and target.WorldInfo == world and hasattr(target, "GetOpinion")
                    and int(controller.Role) == int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
                    and int(target.GetOpinion(pawn)) == int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)):
                definition = _find("SkillDefinition", RAVING_RETRIBUTION_PATH)
                eligible = definition is not None and int(controller.GetSkillGrade(definition)) > 0
        if eligible:
            desired = _raving_neutral_damage_type(original)
        elif not nested_neutral:
            return None
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _raving_error(exc)
        if not nested_neutral:
            return None  # Preparation failed before executing any native damage.
        desired = original  # Still isolate an unrelated/rejected nested hit.

    saved_base = pipeline.GetDamageTypeDef()
    saved_cached = pipeline.WillowDamageTypeDef
    try:
        pipeline.SetDamageTypeDef(desired)
        pipeline.WillowDamageTypeDef = desired
        if pipeline.GetDamageTypeDef() != desired or pipeline.WillowDamageTypeDef != desired:
            raise RuntimeError("Raving Retribution pipeline did not retain its scoped damage type")
        # BoundFunction calls trigger hooks too. Bypass this direct call only;
        # genuine secondary native damage events must still run their hooks.
        with prevent_hooking_direct_calls():
            summary = func(args)
    finally:
        # Both references are synchronous locals only, including on native exceptions.
        # Nested calls restore their caller's type; outer calls restore the shared type.
        pipeline.SetDamageTypeDef(saved_base)
        pipeline.WillowDamageTypeDef = saved_cached
    if desired != original:
        try:
            attribute = original.CharacterDamageTypeModifierAttribute
            kind = ("burn" if attribute is not None and str(attribute._path_name()).endswith(
                ".IncendiaryStatusEffectDamageModifier") else "impact")
            key = f"Raving Retribution native {kind} efficacy"
            if key not in _verified_fixes:
                # DMGSURFACE_Armor=2, Shield=3 are verified native surface values.
                armor = float(desired.GetSurfaceDamageTypeModifier(DamageSurfaceType=2, DamageInstigator=controller))
                shield = float(desired.GetSurfaceDamageTypeModifier(DamageSurfaceType=3, DamageInstigator=controller))
                source_armor = float(original.GetSurfaceDamageTypeModifier(DamageSurfaceType=2, DamageInstigator=controller))
                source_shield = float(original.GetSurfaceDamageTypeModifier(DamageSurfaceType=3, DamageInstigator=controller))
                flesh = float(desired.GetSurfaceDamageTypeModifier(DamageSurfaceType=1, DamageInstigator=controller))
                source_flesh = float(original.GetSurfaceDamageTypeModifier(DamageSurfaceType=1, DamageInstigator=controller))
                if abs(armor - 1.0) > 0.00001 or abs(shield - 1.0) > 0.00001:
                    raise RuntimeError(f"Unexpected neutral surface factors: armor={armor:g}, shield={shield:g}")
                if not math.isclose(flesh, source_flesh, rel_tol=0.000001, abs_tol=0.0000001):
                    raise RuntimeError("Raving Retribution changed the native Flesh factor")
                _verified_fixes.add(key)
                unrealsdk.logging.info(
                    f"[KriegRebalance] {key}: armor={armor:g}, shield={shield:g}, "
                    f"source_armor={source_armor:g}, source_shield={source_shield:g}, "
                    f"flesh={flesh:g}, health={float(summary.FinalDamage):g}, "
                    f"shield_damage={float(summary.DamageDealtToShields):g}, source={original._path_name()}"
                )
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _raving_error(exc)  # Diagnostics must never repeat an already executed hit.
    return Block, summary


def _configure_fuel_rampage() -> bool:
    definition = _find("SkillDefinition", FUEL_RAMPAGE_PATH)
    speed = _find("AttributeDefinition", FUEL_SPEED_ATTRIBUTE)
    if definition is None or speed is None:
        return False
    helper = _find("SkillDefinition", FUEL_SPEED_PATH)
    if helper is None:
        helper = unrealsdk.construct_object("SkillDefinition", definition, "KriegRebalance_FuelSpeed")
    effects = list(helper.SkillEffectDefinitions)
    if len(effects) != 1 or not _pain_effect_matches(effects[0], speed, FUEL_SPEED_PER_RANK):
        effect = unrealsdk.make_struct(
            "WillowGame.SkillDefinition:SkillEffectData", AttributeToModify=speed,
            bIncludeDuelingTargets=False, bIncludeSelfAsTarget=False,
            bOnlyEffectTargetsInRange=False, bExcludeNonPlayerCharacters=False,
            EffectTarget=unrealsdk.find_enum("EEffectTarget").TARGET_Self,
            TargetInstanceDataName="None", TargetCriteria=unrealsdk.find_enum("ETargetCriteria").CRITERIA_None,
            ModifierType=unrealsdk.find_enum("EModifierType").MT_Scale,
            GradeToStartApplyingEffect=1, PerGradeUpgradeInterval=1, BonusUpgradeList=[])
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(effect, field))
            value.BaseValueConstant = FUEL_SPEED_PER_RANK
            value.BaseValueAttribute = value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0
            setattr(effect, field, value)
        _set_native_data(helper, "SkillEffectDefinitions", [effect])
    if not _pain_effect_matches(helper.SkillEffectDefinitions[0], speed, FUEL_SPEED_PER_RANK):
        raise RuntimeError("Fuel the Rampage did not retain its native speed effect")
    for obj in (definition, helper):
        _set_property(obj, "SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive)
        _set_property(obj, "BehaviorProviderDefinition", None)
        for field in ("DamageEvents", "SkillEffectPresentations"):
            _set_native_data(obj, field, [])
    _set_native_data(definition, "SkillEffectDefinitions", [])
    _set_property(definition, "SkillDescription", FUEL_DESCRIPTION)
    _set_property(definition, "MaxGrade", 5)
    _set_property(helper, "MaxGrade", EFFECTIVE_SKILL_RANK_LIMIT)
    _set_native_data(helper, "SkillConstraints", [])
    _set_native_data(helper, "TrackedActiveSkills", [])
    _set_property(helper, "TrackedActiveSkill", None)
    _set_property(definition, "TrackedActiveSkill", None)
    _set_property(helper, "DurationType", unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite)
    _set_property(helper, "TrackedSkillType", unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked)
    # A native reference owns the helper; no Python UObject survives map travel.
    _set_native_data(definition, "TrackedActiveSkills", [helper])
    return True


def _fuel_player_context(controller: Any) -> tuple[Any, int, int, float] | None:
    if controller is None or controller.bDeleteMe:
        return None
    get_pawn = getattr(controller, "GetWillowPlayerPawn", None)
    if get_pawn is None or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority):
        return None
    world = controller.WorldInfo
    if world is None or world.bDeleteMe or _world_is_departing(controller, world):
        return None
    pawn = get_pawn()
    if pawn is None or pawn.bDeleteMe or pawn.Controller != controller:
        return None
    now = float(world.TimeSeconds)
    if not math.isfinite(now):
        return None
    return pawn, world._get_address(), pawn._get_address(), now


def _fuel_direct_damage(source: Any, damage_type: Any) -> bool:
    if source is None:
        return False  # Unknown attribution must never grant protection from a DoT.
    if any(str(base.Name) == "WillowDmgSource_StatusEffect" for base in source._superfields()):
        return False  # Includes custom subclasses, not just the vanilla source.
    # Silence the Voices uses a Grenade source with DamageTypeDefinition=None.
    # A missing elemental type is not proof of status damage.
    attribute = getattr(damage_type, "CharacterDamageTypeModifierAttribute", None)
    if attribute is not None and str(attribute._path_name()).endswith("StatusEffectDamageModifier"):
        return False  # Status damage remains excluded even under a custom source.
    return True


def _fuel_error(exc: Exception) -> None:
    key = "Fuel the Rampage"
    if key not in _reported_errors:
        _reported_errors.add(key)
        unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.PRE)
def reduce_fuel_self_damage(pipeline: Any, args: Any, _ret: Any, func: Any) -> tuple[type[Block], Any] | None:
    """A separate input multiplier, not another term in the resistance denominator."""
    try:
        controller = args.InDamageInstigator
        target = args.InDamagedActor
        if controller is None or target is None or getattr(target, "Controller", None) != controller:
            return None
        context = _fuel_player_context(controller)
        if context is None or context[0] != target or target.IsInjuredDead():
            return None
        if not _fuel_direct_damage(args.InDamageSource, pipeline.GetDamageTypeDef()):
            return None
        incoming = float(args.IncomingDamage)
        if not math.isfinite(incoming) or incoming <= 0.0:
            return None
        definition = _find("SkillDefinition", FUEL_RAMPAGE_PATH)
        if definition is None:
            return None
        invested = int(controller.GetSkillGrade(definition))
        rank = _effective_skill_rank(controller, FUEL_RAMPAGE_PATH, invested)
        if rank <= 0:
            return None
        factor = 1.0 - FUEL_REDUCTION_PER_RANK * rank
        owner = controller._get_address()
        scaled_args = copy.copy(args)  # Own the native parameter buffer, not the caller's view.
        scaled_args.IncomingDamage = incoming * factor
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _fuel_error(exc)
        return None  # No native calculation has run yet.
    # Do not redispatch this direct BoundFunction call. Genuine secondary native
    # damage events retain their hooks. Never catch a native error and replay a hit.
    with prevent_hooking_direct_calls():
        summary = func(scaled_args)
    try:
        # The native summary, not raw incoming damage, confirms a damaging hit.
        # Shield-only damage also counts; zero, absorbed and healing hits do not.
        dealt = max(0.0, float(summary.FinalDamage)) + max(0.0, float(summary.DamageDealtToShields))
        if dealt > 0.0:
            if len(_fuel_speed_until) >= 16 and owner not in _fuel_speed_until:
                raise RuntimeError("Fuel the Rampage player-state limit reached")
            _fuel_speed_until[owner] = (context[1], context[2], context[3] + FUEL_SPEED_DURATION)
        key = "Fuel the Rampage independent self-damage multiplier"
        if key not in _verified_fixes:
            _verified_fixes.add(key)
            unrealsdk.logging.info(
                f"[KriegRebalance] {key}: rank={rank}, factor={factor:g}, "
                f"incoming={incoming:g}, scaled={float(scaled_args.IncomingDamage):g}, "
                f"health={float(summary.FinalDamage):g}, shield={float(summary.DamageDealtToShields):g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _fuel_error(exc)  # Reporting/speed errors must never execute this hit again.
    return Block, summary


def _maintain_fuel_rampage(controller: Any) -> None:
    try:
        context = _fuel_player_context(controller)
        if context is None:
            return
        pawn, world, pawn_address, now = context
        owner = controller._get_address()
        if now < _next_fuel_sync.get(owner, 0.0) <= now + 0.1:
            return
        if len(_next_fuel_sync) >= 16 and owner not in _next_fuel_sync:
            _next_fuel_sync.clear()
        _next_fuel_sync[owner] = now + 0.1
        # Retire primitive state from previous maps without touching old actors.
        for stale, state in tuple(_fuel_speed_until.items()):
            if state[0] != world or (stale == owner and state[1] != pawn_address):
                _fuel_speed_until.pop(stale, None)
        definition = _find("SkillDefinition", FUEL_RAMPAGE_PATH)
        helper = _find("SkillDefinition", FUEL_SPEED_PATH)
        if definition is None or helper is None or definition.SkillEffectDefinitions:
            return
        manager = controller.GetSkillManager()
        if manager is None:
            return
        active = [s for s in list(manager.ActiveSkills) if s.SkillInstigator == controller]
        invested = int(controller.GetSkillGrade(definition))
        rank = _effective_skill_rank(controller, FUEL_RAMPAGE_PATH, invested)
        parents = [s for s in active if s.Definition == definition]
        if any(s.SkillEffects for s in parents):
            # Remove this passive's old cooldown/friendly-fire modifiers through
            # the native manager, never by editing shared modifier-stack values.
            manager.DeactivateSkill(controller, definition)
            if rank > 0 and manager.ActivateSkill(controller, definition, None, rank) is False:
                raise RuntimeError("Fuel the Rampage passive migration was rejected")
        state = _fuel_speed_until.get(owner)
        live = (rank > 0 and not pawn.IsInjured() and not pawn.IsInjuredDead()
                and float(pawn.GetHealth()) > 0.0)
        if state is not None and (not live or now >= state[2] or state[2] - now > FUEL_SPEED_DURATION):
            _fuel_speed_until.pop(owner, None)
            state = None
        instances = [s for s in active if s.Definition == helper]
        if state is None:
            if instances:
                manager.DeactivateSkill(controller, helper)
            return
        ready = (len(instances) == 1 and int(instances[0].Grade) == rank
                 and instances[0].SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active)
        if not ready:
            if instances:
                manager.DeactivateSkill(controller, helper)
            if manager.ActivateSkill(controller, helper, None, rank) is False:
                raise RuntimeError("Fuel the Rampage movement bonus was rejected")
            unrealsdk.logging.info(
                f"[KriegRebalance] Fuel the Rampage speed: rank={rank}, "
                f"bonus={rank * FUEL_SPEED_PER_RANK:g}, remaining={max(0.0, state[2] - now):g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _fuel_error(exc)


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_fuel_rampage(_tree: Any, args: Any, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or str(args.SkillDef._path_name()) != FUEL_RAMPAGE_PATH:
        return None
    rank = _skill_footer_rank(args)
    reduction = _format_skill_footer_rank_value(
        args, f"{100 * FUEL_REDUCTION_PER_RANK * rank:g}%", _tree)
    speed = _format_skill_footer_rank_value(
        args, f"+{100 * FUEL_SPEED_PER_RANK * rank:g}%", _tree)
    text = "<br>".join((
        f"Direct Self-Damage Reduction: {reduction}",
        f"Movement Speed: {speed}",
        f"Duration: {FUEL_SPEED_DURATION:g} seconds",
    ))
    return Block, text


def _light_fuse_effect_matches(effect: Any, attribute: Any) -> bool:
    if (effect.AttributeToModify != attribute
            or effect.ModifierType != unrealsdk.find_enum("EModifierType").MT_PostAdd
            or effect.EffectTarget != unrealsdk.find_enum("EEffectTarget").TARGET_Self
            or effect.BonusUpgradeList or effect.GradeToStartApplyingEffect != 1
            or effect.PerGradeUpgradeInterval != 1
            or effect.TargetCriteria != unrealsdk.find_enum("ETargetCriteria").CRITERIA_None
            or str(effect.TargetInstanceDataName) != "None"
            or any((effect.bIncludeDuelingTargets, effect.bIncludeSelfAsTarget,
                    effect.bOnlyEffectTargetsInRange, effect.bExcludeNonPlayerCharacters))):
        return False
    return all(math.isclose(float(value.BaseValueConstant), constant, abs_tol=1e-7)
               and value.BaseValueAttribute is None and value.InitializationDefinition is None
               and float(value.BaseValueScaleConstant) == 1.0
               for value, constant in ((effect.BaseModifierValue, 1.0 / LIGHT_FUSE_GRENADE_INTERVAL),
                                       (effect.PerGradeUpgrade, 0.0)))


def _configure_light_the_fuse() -> bool:
    definition = _find("SkillDefinition", LIGHT_FUSE_PATH)
    attribute = _find("ResourcePoolAttributeDefinition", GRENADE_REGEN_ATTRIBUTE)
    if definition is None or attribute is None:
        return False
    effects = list(definition.SkillEffectDefinitions)
    if len(effects) != 1 or not _light_fuse_effect_matches(effects[0], attribute):
        effect = unrealsdk.make_struct(
            "WillowGame.SkillDefinition:SkillEffectData", AttributeToModify=attribute,
            bIncludeDuelingTargets=False, bIncludeSelfAsTarget=False,
            bOnlyEffectTargetsInRange=False, bExcludeNonPlayerCharacters=False,
            EffectTarget=unrealsdk.find_enum("EEffectTarget").TARGET_Self,
            TargetInstanceDataName="None", TargetCriteria=unrealsdk.find_enum("ETargetCriteria").CRITERIA_None,
            ModifierType=unrealsdk.find_enum("EModifierType").MT_PostAdd,
            GradeToStartApplyingEffect=1, PerGradeUpgradeInterval=1, BonusUpgradeList=[])
        for field, constant in (("BaseModifierValue", 1.0 / LIGHT_FUSE_GRENADE_INTERVAL),
                                ("PerGradeUpgrade", 0.0)):
            value = copy.copy(getattr(effect, field))
            value.BaseValueConstant = constant
            value.BaseValueAttribute = value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0
            setattr(effect, field, value)
        _set_native_data(definition, "SkillEffectDefinitions", [effect])
    if not _light_fuse_effect_matches(definition.SkillEffectDefinitions[0], attribute):
        raise RuntimeError("Light the Fuse did not retain its additive grenade regeneration")
    _set_property(definition, "SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive)
    _set_property(definition, "MaxGrade", 1)
    _set_property(definition, "SkillDescription", LIGHT_FUSE_DESCRIPTION)
    old_speed = _find("SkillDefinition", LIGHT_FUSE_SPEED_PATH)
    for skill in (definition, old_speed):
        if skill is None:
            continue
        _set_property(skill, "BehaviorProviderDefinition", None)
        _set_property(skill, "TrackedActiveSkill", None)
        for field in ("DamageEvents", "KillEvents", "SkillEffectPresentations", "TrackedActiveSkills", "SkillConstraints"):
            _set_native_data(skill, field, [])
    if old_speed is not None:
        _set_native_data(old_speed, "SkillEffectDefinitions", [])
    old_override = _find("Behavior_AttributeEffect", LIGHT_FUSE_OVERRIDE_BEHAVIOR)
    if old_override is not None:
        # A pre-existing provider must not re-enable its dynamite FFYL state.
        _set_native_data(old_override, "AttributeEffects", [])
    return True


def _sync_light_the_fuse(controller: Any) -> None:
    """Native regen owns timing/capacity; migrate only this skill's cached effects."""
    if controller is None or controller.bDeleteMe:
        return
    world = controller.WorldInfo
    if (world is None or world.bDeleteMe or _world_is_departing(controller, world)
            or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
        return
    pawn = controller.GetWillowPlayerPawn()
    if pawn is None or pawn.bDeleteMe or pawn.Controller != controller:
        return
    definition = _find("SkillDefinition", LIGHT_FUSE_PATH)
    attribute = _find("ResourcePoolAttributeDefinition", GRENADE_REGEN_ATTRIBUTE)
    if definition is None or attribute is None or definition.BehaviorProviderDefinition is not None:
        return
    effects = list(definition.SkillEffectDefinitions)
    if len(effects) != 1 or not _light_fuse_effect_matches(effects[0], attribute):
        return
    manager = controller.GetSkillManager()
    if manager is None:
        return
    active = [s for s in list(manager.ActiveSkills) if s.SkillInstigator == controller]
    for skill in active:
        if skill.Definition is not None and str(skill.Definition._path_name()) == LIGHT_FUSE_SPEED_PATH:
            manager.DeactivateSkill(controller, skill.Definition)
    instances = [s for s in active if s.Definition == definition]
    learned = int(controller.GetSkillGrade(definition)) > 0
    # Do not force a state transition while the OLD dynamite FFYL is in progress.
    # The property and exact override path were verified in the native dump/header.
    if (not pawn.IsInjuredDead() and not pawn.IsInjured() and int(pawn.UseInjuredDefinitionOverride) != 0):
        injured = pawn.GetInjuredDefinition()
        if injured is not None and str(injured._path_name()) == LIGHT_FUSE_INJURED_PATH:
            _set_property(pawn, "UseInjuredDefinitionOverride", 0)
    if not learned or pawn.IsInjuredDead():
        if instances:
            manager.DeactivateSkill(controller, definition)
        return
    pool = attribute.ResolveContext(controller)
    if pool is None:
        return  # Wait for inventory binding; do not churn a passive on loading screens.
    ready = (len(instances) == 1 and instances[0].SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active
             and len(instances[0].SkillEffects) == 1
             and _light_fuse_effect_matches(instances[0].SkillEffects[0].EffectData, attribute))
    if not ready:
        if instances:
            manager.DeactivateSkill(controller, definition)
        if manager.ActivateSkill(controller, definition, None, 1) is False:
            raise RuntimeError("Light the Fuse native grenade regeneration was rejected")
    # Readback proves our modifier coexists in the native pool, not just the UI.
    for skill in manager.ActiveSkills:
        if skill.SkillInstigator == controller and skill.Definition == definition:
            for applied in skill.SkillEffects:
                if (applied.Modifier is not None
                        and applied.Modifier in list(pool.ActiveRegenerationRateModifierStack)):
                    if not math.isclose(float(applied.Modifier.Value), 1.0 / LIGHT_FUSE_GRENADE_INTERVAL,
                                        rel_tol=1e-6, abs_tol=1e-7):
                        skill.bForceRefreshModifiersNextTick = True
                        return
                    key = "Light the Fuse additive grenade regeneration"
                    if key not in _verified_fixes:
                        _verified_fixes.add(key)
                        unrealsdk.logging.info(
                            f"[KriegRebalance] {key}: own_rate={float(applied.Modifier.Value):g}, "
                            f"total_rate={float(pool.ActiveRegenerationRate):g}, interval={LIGHT_FUSE_GRENADE_INTERVAL:g}s")
                    return
            skill.bForceRefreshModifiersNextTick = True  # Rebind only our unbound/stale effect.


def _maintain_light_the_fuse(controller: Any) -> None:
    if controller is None:
        return
    try:
        address = controller._get_address()
        now = time.monotonic()
        if now < _next_light_fuse_sync.get(address, 0.0):
            return
        if len(_next_light_fuse_sync) >= 16 and address not in _next_light_fuse_sync:
            _next_light_fuse_sync.clear()
        _next_light_fuse_sync[address] = now + 0.25
        _sync_light_the_fuse(controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Light the Fuse"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_light_the_fuse(_tree: Any, args: Any, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or str(args.SkillDef._path_name()) != LIGHT_FUSE_PATH:
        return None
    number = f"{LIGHT_FUSE_GRENADE_INTERVAL:g}"
    if args.bIncludeHTML and _skill_footer_rank(args) > 0:
        number = f'<font color="#00FF00">{number}</font>'
    return Block, f"Grenade Regeneration: 1 grenade every {number} seconds"


def _configure_strip_the_flesh() -> bool:
    """Raise only the normal explosive bonus; the Fight For Your Life bonus is untouched."""
    definition = _find("SkillDefinition", STRIP_THE_FLESH_PATH)
    if definition is None:
        return False
    explosive = []
    for effect in list(definition.SkillEffectDefinitions):
        if effect.AttributeToModify is None:
            continue
        if str(effect.AttributeToModify._path_name()) != STRIP_THE_FLESH_ATTRIBUTE:
            continue
        explosive.append(effect)
    # Fight For Your Life effects read their value from an attribute.
    # The normal bonus is a plain constant, so its attribute is empty.
    matched = [e for e in explosive if e.BaseModifierValue.BaseValueAttribute is None]
    if not matched:
        details = []
        for effect in explosive:
            source = effect.BaseModifierValue.BaseValueAttribute
            details.append(f"target={int(effect.EffectTarget)} "
                           f"source={source._path_name() if source is not None else None} "
                           f"value={float(effect.BaseModifierValue.BaseValueConstant):g}")
        raise RuntimeError(f"Strip the Flesh found no normal explosive effect among "
                           f"{len(explosive)} explosive effects: " + "; ".join(details))
    changed = False
    for effect in matched:
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            current = getattr(effect, field)
            if abs(float(current.BaseValueConstant) - STRIP_THE_FLESH_BONUS_PER_RANK) > 0.0000001:
                value = copy.copy(current)
                value.BaseValueConstant = STRIP_THE_FLESH_BONUS_PER_RANK
                setattr(effect, field, value)
                changed = True
    if changed:
        definition.SkillEffectDefinitions = list(definition.SkillEffectDefinitions)
    for effect in matched:
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            if abs(float(getattr(effect, field).BaseValueConstant) - STRIP_THE_FLESH_BONUS_PER_RANK) > 0.0000001:
                raise RuntimeError("Strip the Flesh did not retain its explosive bonus")
    return True

def _configure_fuel_the_fire() -> bool:
    """Append a direct incendiary damage bonus; every native Fuel the Fire effect is kept."""
    definition = _find("SkillDefinition", FUEL_THE_FIRE_PATH)
    attribute = _find("AttributeDefinition", FUEL_THE_FIRE_DAMAGE_ATTRIBUTE)
    if definition is None or attribute is None:
        return False
    effects = list(definition.SkillEffectDefinitions)
    # Native effects modify status chances; only our own effect uses this attribute.
    originals = [e for e in effects if e.AttributeToModify != attribute]
    if len(originals) < len(effects) - 1:
        raise RuntimeError("Fuel the Fire has several effects on the incendiary damage attribute")
    effect = unrealsdk.make_struct(
        "WillowGame.SkillDefinition:SkillEffectData", AttributeToModify=attribute,
        bIncludeDuelingTargets=False, bIncludeSelfAsTarget=False,
        bOnlyEffectTargetsInRange=False, bExcludeNonPlayerCharacters=False,
        EffectTarget=unrealsdk.find_enum("EEffectTarget").TARGET_Self,
        TargetInstanceDataName="None", TargetCriteria=unrealsdk.find_enum("ETargetCriteria").CRITERIA_None,
        ModifierType=unrealsdk.find_enum("EModifierType").MT_Scale,
        GradeToStartApplyingEffect=1, PerGradeUpgradeInterval=1, BonusUpgradeList=[])
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(effect, field))
        value.BaseValueConstant = FUEL_THE_FIRE_DAMAGE_PER_RANK
        value.BaseValueAttribute = value.InitializationDefinition = None
        value.BaseValueScaleConstant = 1.0
        setattr(effect, field, value)
    _set_native_data(definition, "SkillEffectDefinitions", originals + [effect])
    matches = [e for e in definition.SkillEffectDefinitions if e.AttributeToModify == attribute]
    if (len(definition.SkillEffectDefinitions) != len(originals) + 1 or len(matches) != 1
            or not all(math.isclose(float(getattr(matches[0], f).BaseValueConstant),
                                    FUEL_THE_FIRE_DAMAGE_PER_RANK, abs_tol=1e-7)
                       for f in ("BaseModifierValue", "PerGradeUpgrade"))):
        raise RuntimeError("Fuel the Fire did not retain its incendiary damage bonus")
    _set_property(definition, "SkillDescription", FUEL_THE_FIRE_DESCRIPTION)
    return True


def _skill_footer_rank(args: Any) -> int:
    """Native Grade already includes COM bonuses and the requested preview point."""
    return min(EFFECTIVE_SKILL_RANK_LIMIT, max(0, int(args.Grade)))


def _skill_footer_can_add_point(args: Any) -> bool:
    grade = max(0, int(args.Grade))
    grade_modifier = max(0, int(args.GradeModifier))
    # args.Grade includes Class-Mod bonus; subtract it to know how many points
    # the player actually invested. Only invested ranks below the native limit
    # may still receive another point. When no more points can be added the
    # maximum-rank numbers turn green; partial-rank numbers use the native tree color.
    invested_grade = grade - grade_modifier
    owner = getattr(args, "PlayerOwner", None)
    return (invested_grade < BASE_SKILL_RANK_LIMIT or not args.bIncludeHTML
            or owner is None
            or int(owner.GetSkillGrade(args.SkillDef)) < BASE_SKILL_RANK_LIMIT)


def _format_skill_footer_rank_value(args: Any, value: str, tree: Any = None) -> str:
    """Style only a rank-dependent numeric token, including its sign and unit."""
    if not args.bIncludeHTML:
        return value
    if not _skill_footer_can_add_point(args):
        return f'<font color="#00FF00">{value}</font>'

    owner = getattr(args, "PlayerOwner", None)
    if int(args.Grade) <= 0 or owner is None or int(owner.GetSkillGrade(args.SkillDef)) <= 0:
        return value
    color = getattr(tree, "SkillIntermediateGradeColor", None)
    style = str(getattr(tree, "SkillLockedModifierTextHTML", ""))
    if color is None or "%c" not in style or "%s" not in style:
        return value
    channels = tuple(int(getattr(color, channel)) for channel in ("R", "G", "B"))
    if any(channel < 0 or channel > 255 for channel in channels):
        return value
    rgb = "".join(f"{channel:02X}" for channel in channels)
    return style.replace("%c", rgb).replace("%s", value)


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_fuel_the_fire(_tree: Any, args: Any, _ret: Any, func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or str(args.SkillDef._path_name()) != FUEL_THE_FIRE_PATH:
        return None
    with prevent_hooking_direct_calls():
        native_text = func(args)
    # Native Grade already includes the equipped COM and the preview increment.
    # GradeModifier is metadata; adding it again pins both blocks at rank 11.
    rank = _skill_footer_rank(args)
    bonus = f"+{FUEL_THE_FIRE_DAMAGE_PER_RANK * rank * 100:g}%"
    bonus = _format_skill_footer_rank_value(args, bonus, _tree)
    separator = "<br>" if args.bIncludeHTML else "\n"
    lines = [line for line in (native_text, f"Direct Incendiary Damage: {bonus}") if line]
    return Block, separator.join(lines)

def _configure_elemental_empathy() -> bool:
    """The native per-grade attribute drives both status-damage healing and its stat."""
    global _hellborn_tuning_revision
    resolver = _find("ConstantAttributeValueResolver", ELEMENTAL_EMPATHY_HEALING_PATH)
    if resolver is None:
        return False
    if abs(float(resolver.ConstantValue) - ELEMENTAL_EMPATHY_HEALING_PER_RANK) > 0.0000001:
        resolver.ConstantValue = ELEMENTAL_EMPATHY_HEALING_PER_RANK
        _hellborn_tuning_revision += 1
    if abs(float(resolver.ConstantValue) - ELEMENTAL_EMPATHY_HEALING_PER_RANK) > 0.0000001:
        raise RuntimeError("Elemental Empathy did not retain its healing coefficient")
    return True


def _configure_numbed_nerves() -> bool:
    """Retain the nine native resistance effects and their reciprocal conversion."""
    global _hellborn_tuning_revision
    definition = _find("SkillDefinition", NUMBED_NERVES_PATH)
    initializer = _find("AttributeInitializationDefinition", NUMBED_INITIALIZER_PATH)
    fire = _find("AttributeExpressionEvaluator", f"{NUMBED_NERVES_PATH}:AttributeExpressionEvaluator_0")
    presentation = _find("AttributePresentationDefinition", f"{NUMBED_NERVES_PATH}:AttributePresentationDefinition_1")
    if definition is None or initializer is None or fire is None or presentation is None:
        return False
    native_rows = list(initializer.ConditionalInitialization.ConditionalExpressionList)
    effects = list(definition.SkillEffectDefinitions)
    resistance = [effect for effect in effects if effect.AttributeToModify is not None
                  and effect.BaseModifierValue.InitializationDefinition == initializer]
    stats = [effect for effect in effects if effect.AttributeToModify is None
             and effect.EffectTarget == unrealsdk.find_enum("EEffectTarget").TARGET_None]
    if not native_rows or not native_rows[0].Expressions or len(resistance) != 9 or len(stats) != 1:
        raise ValueError("Numbed Nerves native rank table or nine resistance effects were not found")
    rows = []
    # Vanilla already caps its rank table at >=5. No native COM boosts this skill;
    # retain that safety boundary rather than inventing >=100% damage reduction.
    for rank in range(1, 6):
        for on_fire in (True, False):
            row = copy.copy(native_rows[0])
            grade = copy.copy(native_rows[0].Expressions[0])
            grade.ComparisonOperator = native_rows[-1 if rank == 5 else 0].Expressions[0].ComparisonOperator
            grade.ConstantOperand2 = float(rank)
            row.Expressions = [grade]
            if on_fire:
                row.Expressions = [grade, copy.copy(fire.Expression)]
            reduction = NUMBED_REDUCTION_PER_RANK * rank * (2 if on_fire else 1)
            value = copy.copy(row.BaseValueIfTrue)
            value.BaseValueConstant = -reduction / (1.0 - reduction)
            value.BaseValueAttribute = value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0
            row.BaseValueIfTrue = value
            rows.append(row)
    conditional = copy.copy(initializer.ConditionalInitialization)
    conditional.bEnabled = True
    conditional.ConditionalExpressionList = rows
    default = copy.copy(conditional.DefaultBaseValue)
    default.BaseValueConstant = 0.0
    default.BaseValueAttribute = default.InitializationDefinition = None
    default.BaseValueScaleConstant = 1.0
    conditional.DefaultBaseValue = default
    formula = copy.copy(initializer.ValueFormula)
    formula.bEnabled = False
    constraints = [entry for entry in definition.SkillConstraints if entry.Evaluator != fire]
    stat = copy.copy(stats[0])
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(stat, field))
        value.BaseValueConstant = NUMBED_REDUCTION_PER_RANK
        value.BaseValueAttribute = value.InitializationDefinition = None
        value.BaseValueScaleConstant = 1.0
        setattr(stat, field, value)
    effects = [stat if entry is stats[0] else entry for entry in effects]
    changed = False
    for obj, field, expected in ((initializer, "ConditionalInitialization", conditional),
                                 (initializer, "ValueFormula", formula),
                                 (definition, "SkillConstraints", constraints),
                                 (definition, "SkillEffectDefinitions", effects)):
        # Always check all four writes; don't short-circuit when one has changed.
        if _set_native_data(obj, field, expected):
            changed = True
    _set_property(definition, "SkillDescription", NUMBED_DESCRIPTION)
    _set_property(presentation, "bDisplayPercentAsFloat", True)  # Preserve 7.5 / 37.5.
    if changed:
        _hellborn_tuning_revision += 1
    return True


def _configure_burn_baby_burn() -> bool:
    """Tune native coefficients used by the effects AND native rank presentations."""
    global _burn_tuning_revision
    base = _find("ConstantAttributeValueResolver", BURN_BABY_BURN_VALUES[0][0])
    on_fire = _find("ConstantAttributeValueResolver", BURN_BABY_BURN_VALUES[1][0])
    if base is None or on_fire is None:
        return False
    changed = False
    for resolver, (_, expected) in zip((base, on_fire), BURN_BABY_BURN_VALUES):
        if abs(float(resolver.ConstantValue) - expected) > 0.0000001:
            resolver.ConstantValue = expected
            changed = True
        if abs(float(resolver.ConstantValue) - expected) > 0.0000001:
            raise RuntimeError("Burn, Baby, Burn did not retain its damage coefficient")
    if changed:
        _burn_tuning_revision += 1
    return True


def _refresh_burn_baby_burn(controller: Any) -> None:
    """Refresh learned caches once per instance/rank/tuning, without reactivation."""
    if controller is None or controller.bDeleteMe:
        return
    world = controller.WorldInfo
    if world is None or world.bDeleteMe:
        return
    manager = controller.GetSkillManager()
    if manager is None:
        return
    active = unrealsdk.find_enum("ESkillState").SKILL_Active
    for skill in list(manager.ActiveSkills):
        if (skill.SkillInstigator != controller or skill.Definition is None
                or str(skill.Definition._path_name()) not in (BURN_BABY_BURN_PATH, BURN_BABY_BURN_CHILD_PATH)
                or int(skill.Grade) <= 0 or skill.SkillState != active):
            continue
        key = (controller._get_address(), skill._get_address(), int(skill.Grade))
        if _burn_refreshed.get(key) == _burn_tuning_revision:
            continue
        if len(_burn_refreshed) >= 64:
            _burn_refreshed.clear()  # Primitive keys only, never keep old skill UObjects.
        skill.bForceRefreshModifiersNextTick = True
        _burn_refreshed[key] = _burn_tuning_revision


def _pull_the_pin_effect_matches(effect: Any, attribute: Any) -> bool:
    if (effect.AttributeToModify != attribute
            or effect.ModifierType != unrealsdk.find_enum("EModifierType").MT_PreAdd
            or effect.EffectTarget != unrealsdk.find_enum("EEffectTarget").TARGET_Self
            or effect.TargetCriteria != unrealsdk.find_enum("ETargetCriteria").CRITERIA_None
            or str(effect.TargetInstanceDataName) != "None"
            or any((effect.bIncludeDuelingTargets, effect.bIncludeSelfAsTarget,
                    effect.bOnlyEffectTargetsInRange, effect.bExcludeNonPlayerCharacters))
            or effect.GradeToStartApplyingEffect != 1 or effect.PerGradeUpgradeInterval != 1
            or effect.BonusUpgradeList):
        return False
    return all(
        float(value.BaseValueConstant) == constant and value.BaseValueAttribute is None
        and value.InitializationDefinition is None and float(value.BaseValueScaleConstant) == 1.0
        for value, constant in ((effect.BaseModifierValue, 1.0), (effect.PerGradeUpgrade, 0.0))
    )


def _pull_the_pin_attribute(definition: Any, *, create: bool = False) -> Any | None:
    # Prefer our existing definition even if Axton's original asset loads later.
    # All three objects are owned/referenced by this skill, not rooted in Python.
    path = f"{PULL_THE_PIN_PATH}:KriegRebalance_FFYL_Grenades"
    attribute = _find("AttributeDefinition", path)
    if attribute is None:
        attribute = _find("AttributeDefinition", FFYL_GRENADE_ATTRIBUTE)
        if attribute is not None or not create:
            return attribute
        attribute = unrealsdk.construct_object("AttributeDefinition", definition, "KriegRebalance_FFYL_Grenades")
    elif not create:
        return attribute
    context = _find("PlayerControllerAttributeContextResolver", f"{path}.ControllerContext")
    if context is None:
        context = unrealsdk.construct_object("PlayerControllerAttributeContextResolver", attribute, "ControllerContext")
    resolver = _find("ObjectPropertyAttributeValueResolver", f"{path}.PermissionValue")
    if resolver is None:
        resolver = unrealsdk.construct_object("ObjectPropertyAttributeValueResolver", attribute, "PermissionValue")
    _set_property(resolver, "PropertyName", "CanThrowGrenadesWhileInDownState")
    _set_property(attribute, "bIsSimpleAttribute", True)
    _set_property(attribute, "AttributeDataType", unrealsdk.find_enum("EAttributeDataType").ADT_Float)
    if list(attribute.ContextResolverChain) != [context]:
        attribute.ContextResolverChain = [context]
    if list(attribute.ValueResolverChain) != [resolver]:
        attribute.ValueResolverChain = [resolver]
    if (list(attribute.ContextResolverChain) != [context]
            or list(attribute.ValueResolverChain) != [resolver]):
        raise RuntimeError("Pull the Pin did not retain its native permission resolvers")
    key = "Pull the Pin private native attribute"
    if key not in _verified_fixes:
        _verified_fixes.add(key)
        unrealsdk.logging.info("[KriegRebalance] Pull the Pin: using private native FFYL grenade attribute")
    return attribute


def _configure_pull_the_pin() -> bool:
    definition = _find("SkillDefinition", PULL_THE_PIN_PATH)
    if definition is None:
        key = "Pull the Pin pending skill asset"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(f"[KriegRebalance] Pull the Pin pending asset: {PULL_THE_PIN_PATH}; will retry")
        return False
    attribute = _pull_the_pin_attribute(definition, create=True)
    effects = list(definition.SkillEffectDefinitions)
    if len(effects) != 1 or not _pull_the_pin_effect_matches(effects[0], attribute):
        # Native SkillEffectData and attribute, not a custom grenade/input pipeline.
        effect = unrealsdk.make_struct(
            "WillowGame.SkillDefinition:SkillEffectData", AttributeToModify=attribute,
            bIncludeDuelingTargets=False, bIncludeSelfAsTarget=False,
            bOnlyEffectTargetsInRange=False, bExcludeNonPlayerCharacters=False,
            EffectTarget=unrealsdk.find_enum("EEffectTarget").TARGET_Self,
            TargetInstanceDataName="None", TargetCriteria=unrealsdk.find_enum("ETargetCriteria").CRITERIA_None,
            ModifierType=unrealsdk.find_enum("EModifierType").MT_PreAdd,
            GradeToStartApplyingEffect=1, PerGradeUpgradeInterval=1, BonusUpgradeList=[],
        )
        for field, constant in (("BaseModifierValue", 1.0), ("PerGradeUpgrade", 0.0)):
            value = copy.copy(getattr(effect, field))
            value.BaseValueConstant = constant
            value.BaseValueAttribute = value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0
            setattr(effect, field, value)
        definition.SkillEffectDefinitions = [effect]
    if (len(definition.SkillEffectDefinitions) != 1
            or not _pull_the_pin_effect_matches(definition.SkillEffectDefinitions[0], attribute)):
        raise RuntimeError("Pull the Pin did not retain its single FFYL grenade permission")
    _set_property(definition, "SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive)
    _set_property(definition, "MaxGrade", 1)
    _set_property(definition, "SkillDescription", PULL_THE_PIN_DESCRIPTION)
    # Replace, rather than stack with, the vanilla death grenade / double XP.
    # These are this skill's own definitions only.
    # The old XP helper is optional: waiting for it used to prevent ALL edits,
    # including the description. The parent no longer starts that helper.
    xp_bonus = _find("SkillDefinition", PULL_THE_PIN_XP_PATH)
    for skill in (definition, xp_bonus):
        if skill is None:
            continue
        _set_property(skill, "BehaviorProviderDefinition", None)
        for field in ("SkillEffectPresentations", "TrackedActiveSkills"):
            if getattr(skill, field):
                setattr(skill, field, [])
            if getattr(skill, field):
                raise RuntimeError(f"Pull the Pin retained obsolete {field}")
    for skill, field in ((definition, "SkillConstraints"), (xp_bonus, "SkillEffectDefinitions")):
        if skill is None:
            continue
        if getattr(skill, field):
            setattr(skill, field, [])
        if getattr(skill, field):
            raise RuntimeError(f"Pull the Pin retained obsolete {field}")
    return True


@hook("WillowGame.PlayerBehavior_SpawnCurrentProjectile:ApplyBehaviorToContext", Type.PRE)
def block_old_pull_the_pin_grenade(behavior: Any, _args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    # Protect late enable too: a native provider instantiated before the static
    # edit may still dispatch its death event. Never block manual grenade throws.
    if str(behavior._path_name()) == PULL_THE_PIN_OLD_SPAWN:
        return Block
    return None


def _sync_pull_the_pin(controller: Any) -> None:
    """Migrate only this passive's live cache; let the engine own/remove its flag."""
    if controller.bDeleteMe:
        return
    world = controller.WorldInfo
    if world is None or world.bDeleteMe or _world_is_departing(controller, world):
        return
    pawn = controller.GetWillowPlayerPawn()
    if pawn is None or pawn.bDeleteMe or pawn.Controller != controller or pawn.IsInjuredDead():
        return
    definition = _find("SkillDefinition", PULL_THE_PIN_PATH)
    if definition is None:
        return
    attribute = _pull_the_pin_attribute(definition)
    if attribute is None:
        return
    effects = list(definition.SkillEffectDefinitions)
    if (definition.BehaviorProviderDefinition is not None or len(effects) != 1
            or not _pull_the_pin_effect_matches(effects[0], attribute)):
        return  # Wait for static tuning; never activate the original behavior.
    manager = controller.GetSkillManager()
    if manager is None:
        return
    active = [skill for skill in manager.ActiveSkills if skill.SkillInstigator == controller]
    # An old XP child can remain registered when enabling mid-session.
    for skill in active:
        if skill.Definition and str(skill.Definition._path_name()) == PULL_THE_PIN_XP_PATH:
            manager.DeactivateSkill(controller, skill.Definition)
    instances = [skill for skill in active if skill.Definition == definition]
    if int(controller.GetSkillGrade(definition)) <= 0:
        if instances:
            manager.DeactivateSkill(controller, definition)
        return
    ready = False
    if len(instances) == 1:
        skill = instances[0]
        applied = list(skill.SkillEffects)
        ready = (skill.SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active
                 and len(applied) == 1 and _pull_the_pin_effect_matches(applied[0].EffectData, attribute)
                 and applied[0].Modifier is not None and float(applied[0].Modifier.Value) == 1.0
                 and applied[0].Modifier in list(controller.CanThrowGrenadesWhileInDownStateModifierStack))
    if not ready:
        # No timers/kill-skill windows belong to this new permanent one-point
        # passive. Native deactivation removes only its own old modifiers.
        manager.DeactivateSkill(controller, definition)
        if manager.ActivateSkill(controller, definition, None, 1) is False:
            raise RuntimeError("Could not refresh Pull the Pin's learned passive")
    key = "Pull the Pin FFYL permission"
    if ready and key not in _verified_fixes:
        _verified_fixes.add(key)
        unrealsdk.logging.info(
            "[KriegRebalance] Pull the Pin live permission verified: "
            f"can_throw_while_downed={float(controller.CanThrowGrenadesWhileInDownState):g}"
        )


def _maintain_pull_the_pin(controller: Any, now: float) -> None:
    if controller is None:
        return
    try:
        address = controller._get_address()
        if now < _next_pull_sync.get(address, 0.0):
            return
        if len(_next_pull_sync) >= 16 and address not in _next_pull_sync:
            _next_pull_sync.clear()
        _next_pull_sync[address] = now + MAINTENANCE_INTERVAL
        _sync_pull_the_pin(controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Pull the Pin live cache"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


def _pain_effect_matches(effect: Any, attribute: Any, coefficient: float) -> bool:
    return (effect.AttributeToModify == attribute
            and effect.ModifierType == unrealsdk.find_enum("EModifierType").MT_Scale
            and effect.EffectTarget == unrealsdk.find_enum("EEffectTarget").TARGET_Self
            and effect.TargetCriteria == unrealsdk.find_enum("ETargetCriteria").CRITERIA_None
            and str(effect.TargetInstanceDataName) == "None"
            and not any((effect.bIncludeDuelingTargets, effect.bIncludeSelfAsTarget,
                         effect.bOnlyEffectTargetsInRange, effect.bExcludeNonPlayerCharacters))
            and effect.GradeToStartApplyingEffect == 1 and effect.PerGradeUpgradeInterval == 1
            and not effect.BonusUpgradeList
            and all(math.isclose(float(value.BaseValueConstant), coefficient, abs_tol=1e-7)
                    and value.BaseValueAttribute is None and value.InitializationDefinition is None
                    and float(value.BaseValueScaleConstant) == 1.0
                    for value in (effect.BaseModifierValue, effect.PerGradeUpgrade)))


def _configure_pain_is_power() -> bool:
    definition = _find("SkillDefinition", PAIN_IS_POWER_PATH)
    if definition is None:
        return False
    paths = (PAIN_CRIT_ATTRIBUTE, PAIN_SPREAD_ATTRIBUTE, PAIN_MELEE_ATTRIBUTE)
    attributes = [_find("AttributeDefinition", path) for path in paths]
    if any(attribute is None for attribute in attributes):
        missing = [path for path, attribute in zip(paths, attributes)
                   if attribute is None]
        key = "Pain is Power pending attributes"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(f"[KriegRebalance] Pain is Power pending attributes: {', '.join(missing)}")
        return False
    helper = _find("SkillDefinition", PAIN_STACK_EFFECT_PATH)
    if helper is None:
        helper = unrealsdk.construct_object("SkillDefinition", definition, "KriegRebalance_PainStacks")
    effects = list(helper.SkillEffectDefinitions)
    coefficients = (PAIN_CRIT_PER_RANK, PAIN_SPREAD_PER_RANK, PAIN_MELEE_PER_RANK)
    if len(effects) != 3 or not all(_pain_effect_matches(e, a, c)
                                   for e, a, c in zip(effects, attributes, coefficients)):
        effects = []
        for attribute, coefficient in zip(attributes, coefficients):
            effect = unrealsdk.make_struct(
                "WillowGame.SkillDefinition:SkillEffectData", AttributeToModify=attribute,
                bIncludeDuelingTargets=False, bIncludeSelfAsTarget=False,
                bOnlyEffectTargetsInRange=False, bExcludeNonPlayerCharacters=False,
                EffectTarget=unrealsdk.find_enum("EEffectTarget").TARGET_Self,
                TargetInstanceDataName="None", TargetCriteria=unrealsdk.find_enum("ETargetCriteria").CRITERIA_None,
                ModifierType=unrealsdk.find_enum("EModifierType").MT_Scale,
                GradeToStartApplyingEffect=1, PerGradeUpgradeInterval=1, BonusUpgradeList=[])
            for field in ("BaseModifierValue", "PerGradeUpgrade"):
                value = copy.copy(getattr(effect, field))
                value.BaseValueConstant = coefficient
                value.BaseValueAttribute = value.InitializationDefinition = None
                value.BaseValueScaleConstant = 1.0
                setattr(effect, field, value)
            effects.append(effect)
        helper.SkillEffectDefinitions = effects
    if len(helper.SkillEffectDefinitions) != 3 or not all(
            _pain_effect_matches(e, a, c) for e, a, c in zip(helper.SkillEffectDefinitions, attributes, coefficients)):
        raise RuntimeError("Pain is Power did not retain its three native stack effects")
    # A private helper has no COM grade bonus of its own. Grade = stacks x native
    # parent grade; native effects own weapon rebinding and modifier cleanup.
    for skill in (definition, helper):
        _set_property(skill, "SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive)
        _set_property(skill, "BehaviorProviderDefinition", None)
        for field in ("SkillConstraints", "TrackedActiveSkills", "SkillEffectPresentations"):
            if getattr(skill, field):
                setattr(skill, field, [])
            if getattr(skill, field):
                raise RuntimeError(f"Pain is Power retained obsolete {field}")
    if definition.SkillEffectDefinitions:
        definition.SkillEffectDefinitions = []
    if definition.SkillEffectDefinitions:
        raise RuntimeError("Pain is Power retained its original bonuses")
    _set_property(definition, "MaxGrade", 5)
    _set_property(definition, "SkillDescription", PAIN_DESCRIPTION)
    _set_property(helper, "MaxGrade", PAIN_STACK_LIMIT * EFFECTIVE_SKILL_RANK_LIMIT)
    return True


def _pain_stack_count(key: tuple[int, int], now: float) -> int:
    count, deadline = _pain_stacks.get(key, (0, now))
    if count and now >= deadline:
        lost = 1 + int((now - deadline) // PAIN_DECAY_INTERVAL)
        count = max(0, count - lost)
        if count:
            _pain_stacks[key] = (count, deadline + lost * PAIN_DECAY_INTERVAL)
        else:
            _pain_stacks.pop(key, None)
    elif count and deadline - now > PAIN_DECAY_DELAY + 0.000001:
        _pain_stacks.pop(key, None)  # Clock rewound: never keep stale buffs indefinitely.
        return 0
    return count


def _pain_player_context(controller: Any) -> tuple[Any, tuple[int, int], float] | None:
    if controller is None or controller.bDeleteMe:
        return None
    world = controller.WorldInfo
    if world is None or world.bDeleteMe or _world_is_departing(controller, world):
        return None
    pawn = controller.GetWillowPlayerPawn()
    if pawn is None or pawn.bDeleteMe or pawn.Controller != controller:
        return None
    now = float(world.TimeSeconds)
    if not math.isfinite(now):
        return None
    key = (world._get_address(), pawn._get_address())
    owner = controller._get_address()
    for stale_owner, stale_key in tuple(_pain_owner_keys.items()):
        if stale_key[0] != key[0]:
            _pain_stacks.pop(stale_key, None)
            _pain_owner_keys.pop(stale_owner, None)
            _next_pain_sync.pop(stale_owner, None)
    previous = _pain_owner_keys.get(owner)
    if previous is not None and previous != key:
        _pain_stacks.pop(previous, None)
    if len(_pain_owner_keys) >= 16 and owner not in _pain_owner_keys:
        # Retire only vanished contexts during normal travel/respawn, never drop
        # another player's active state to make room.
        raise RuntimeError("Pain is Power controller-state limit reached")
    _pain_owner_keys[owner] = key
    return pawn, key, now


def _sync_pain_is_power(controller: Any) -> None:
    context = _pain_player_context(controller)
    if context is None:
        return
    pawn, key, now = context
    definition = _find("SkillDefinition", PAIN_IS_POWER_PATH)
    helper = _find("SkillDefinition", PAIN_STACK_EFFECT_PATH)
    if definition is None or helper is None or definition.SkillEffectDefinitions:
        return  # Static migration has not completed; never duplicate the old bonuses.
    manager = controller.GetSkillManager()
    if manager is None:
        return
    active = [s for s in list(manager.ActiveSkills) if s.SkillInstigator == controller]
    parents = [s for s in active if s.Definition == definition]
    # Neutralize only this parent's stale cached effects, not other skills or
    # attributes shared with them. Do not retarget a modifier still in a stack.
    for skill in parents:
        effects = list(skill.SkillEffects)
        changed = False
        for applied in effects:
            data = applied.EffectData
            if (data.BonusUpgradeList or any(float(v.BaseValueConstant) != 0.0
                    or v.BaseValueAttribute is not None or v.InitializationDefinition is not None
                    for v in (data.BaseModifierValue, data.PerGradeUpgrade))):
                data = copy.copy(data)
                data.BonusUpgradeList = []
                for field in ("BaseModifierValue", "PerGradeUpgrade"):
                    value = copy.copy(getattr(data, field))
                    value.BaseValueConstant = 0.0
                    value.BaseValueAttribute = value.InitializationDefinition = None
                    value.BaseValueScaleConstant = 1.0
                    setattr(data, field, value)
                applied.EffectData = data
                changed = True
        if changed:
            skill.SkillEffects = effects
            skill.bForceRefreshModifiersNextTick = True
    invested = int(controller.GetSkillGrade(definition))
    if invested <= 0 or pawn.IsInjuredDead():
        _pain_stacks.pop(key, None)
    count = _pain_stack_count(key, now)
    rank = max((int(s.Grade) for s in parents), default=0) if invested > 0 else 0
    if invested > 0 and rank <= 0:
        rank = _effective_skill_rank(controller, PAIN_IS_POWER_PATH, invested)
    combined = count * rank
    instances = [s for s in active if s.Definition == helper]
    # Native weapon contexts can be empty while swapping/unarmed. Do not churn
    # a correctly graded passive just because its weapon modifier is not bound yet.
    ready = (len(instances) == 1 and int(instances[0].Grade) == combined
             and instances[0].SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active)
    if ready and len(instances[0].SkillEffects) == 2:
        # Refresh stale spread snapshots even at an unchanged stack count.
        # Empty weapon contexts during swaps remain valid and do not cause churn.
        for applied in instances[0].SkillEffects:
            for expected in helper.SkillEffectDefinitions:
                if (applied.EffectData.AttributeToModify == expected.AttributeToModify
                        and not _pain_effect_matches(applied.EffectData, expected.AttributeToModify,
                                                     float(expected.BaseModifierValue.BaseValueConstant))):
                    ready = False
                    break
    if combined <= 0:
        if instances:
            manager.DeactivateSkill(controller, helper)
            unrealsdk.logging.info("[KriegRebalance] Pain is Power stacks expired or removed")
    elif not ready:
        if instances:
            manager.DeactivateSkill(controller, helper)
        if manager.ActivateSkill(controller, helper, None, combined) is False:
            raise RuntimeError("Could not apply Pain is Power stack effects")
        unrealsdk.logging.info(
            f"[KriegRebalance] Pain is Power: stacks={count}, rank={rank}, "
            f"critical_bonus={combined * PAIN_CRIT_PER_RANK:g}, spread_penalty={combined * PAIN_SPREAD_PER_RANK:g}, "
            f"melee_bonus={combined * PAIN_MELEE_PER_RANK:g}")


@hook("WillowGame.WillowPlayerPawn:TakeDamage", Type.PRE)
def begin_pain_health_damage(pawn: Any, args: Any, _ret: Any, _func: Any) -> None:
    frame = None
    try:
        controller = pawn.Controller
        definition = _find("SkillDefinition", PAIN_IS_POWER_PATH)
        if (controller is not None and definition is not None and float(args.Damage) > 0.0
                and int(controller.GetSkillGrade(definition)) > 0):
            context = _pain_player_context(controller)
            health = float(pawn.GetHealth())
            if (context is not None and context[0] == pawn and math.isfinite(health) and health > 0
                    and not pawn.IsInjured() and not pawn.IsInjuredDead()):
                frame = {"key": context[1], "health": health, "nested_loss": 0.0}
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _pain_error(exc)
    _pain_damage_frames.append(frame)  # Pair even blocked/ineligible native calls.


@hook("WillowGame.WillowPlayerPawn:TakeDamage", Type.POST_UNCONDITIONAL)
def finish_pain_health_damage(pawn: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if not _pain_damage_frames:
        return
    frame = _pain_damage_frames.pop()  # Unwind before applying any native modifiers.
    if frame is None:
        return
    try:
        controller = pawn.Controller
        context = _pain_player_context(controller)
        if context is None or context[0] != pawn or context[1] != frame["key"]:
            return
        health = float(pawn.GetHealth())
        if not math.isfinite(health):
            return
        loss = max(0.0, frame["health"] - max(0.0, health))
        # Nested TakeDamage must not also be counted as health loss of the outer hit.
        for outer in reversed(_pain_damage_frames):
            if outer is not None and outer["key"] == frame["key"]:
                outer["nested_loss"] += loss
                break
        if loss <= frame["nested_loss"] or pawn.IsInjuredDead():
            return
        key, now = context[1:]
        definition = _find("SkillDefinition", PAIN_IS_POWER_PATH)
        if definition is None or int(controller.GetSkillGrade(definition)) <= 0:
            return
        count = _pain_stack_count(key, now)
        if len(_pain_stacks) >= 16 and key not in _pain_stacks:
            raise RuntimeError("Pain is Power player-state limit reached")
        _pain_stacks[key] = (min(PAIN_STACK_LIMIT, count + 1), now + PAIN_DECAY_DELAY)
        if count < PAIN_STACK_LIMIT:
            _sync_pain_is_power(controller)
        # At the cap, only renew the expiry. The existing 0.1s maintenance
        # handles rank/context repairs; repeated hits need no ActiveSkills scan.
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _pain_error(exc)


def _pain_error(exc: Exception) -> None:
    key = "Pain is Power"
    if key not in _reported_errors:
        _reported_errors.add(key)
        unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


def _maintain_pain_is_power(controller: Any, now: float) -> None:
    if controller is None:
        return
    try:
        address = controller._get_address()
        if now < _next_pain_sync.get(address, 0.0):
            return
        if len(_next_pain_sync) >= 16 and address not in _next_pain_sync:
            _next_pain_sync.clear()
        _next_pain_sync[address] = now + 0.1
        _sync_pain_is_power(controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _pain_error(exc)


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_pain_is_power(_tree: Any, args: Any, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or str(args.SkillDef._path_name()) != PAIN_IS_POWER_PATH:
        return None
    rank = _skill_footer_rank(args)
    crit = _format_skill_footer_rank_value(
        args, f"+{100 * PAIN_CRIT_PER_RANK * rank:g}%", _tree)
    melee = _format_skill_footer_rank_value(
        args, f"+{100 * PAIN_MELEE_PER_RANK * rank:g}%", _tree)
    accuracy = f"-{100 * PAIN_SPREAD_PER_RANK * rank:g}%"
    if args.bIncludeHTML:
        accuracy = f'<font color="#FF0000">{accuracy}</font>'
    text = "<br>".join((
        f"Critical Hit Damage per Stack: {crit}",
        f"Melee Damage per Stack: {melee}",
        f"Accuracy per Stack: {accuracy}",
    ))
    return Block, text


def _bloodlust_icon_rgb(transform: Any) -> tuple[float, ...]:
    values = tuple(float(getattr(color, channel)) for color in (transform.Multiply, transform.Add)
                   for channel in ("R", "G", "B"))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Invalid Bloodlust icon color transform")
    return values


def _bloodlust_rgb_matches(left: tuple[float, ...], right: tuple[float, ...]) -> bool:
    # Scaleform may quantize a color transform. Do not rewrite it every HUD tick.
    return len(left) == len(right) and all(math.isclose(a, b, abs_tol=0.01) for a, b in zip(left, right))


def _set_bloodlust_icon_rgb(clip: Any, transform: Any, values: tuple[float, ...]) -> None:
    owned = copy.copy(transform)
    for index, field in enumerate(("Multiply", "Add")):
        color = copy.copy(getattr(transform, field))
        for offset, channel in enumerate(("R", "G", "B")):
            setattr(color, channel, values[index * 3 + offset])
        setattr(owned, field, color)
    clip.SetColorTransform(owned)  # Never modify alpha, display info or clip geometry.


def _restore_bloodlust_icon(movie: Any, slot: int, original: tuple[float, ...]) -> None:
    clip = movie.GetVariableObject(BLOODLUST_IMAGE_PATH.format(slot=slot + 1))
    if clip is None:
        return
    transform = clip.GetColorTransform()
    if _bloodlust_rgb_matches(_bloodlust_icon_rgb(transform), BLOODLUST_RED_RGB):
        _set_bloodlust_icon_rgb(clip, transform, original)


def _maintain_bloodlust_highlight(controller: Any, now: float) -> None:
    """Readiness hint on the native icon only; never a new skill, slot or Canvas draw."""
    try:
        current = get_pc(possibly_loading=True)
        if (controller is None or current != controller or controller.bDeleteMe):
            return
        world = controller.WorldInfo
        if world is None or world.bDeleteMe:
            return
        owner, world_id = controller._get_address(), world._get_address()
        if _pain_hud_departing_context in ((owner, world_id), (owner, 0)):
            return
        if world.Pauser or controller.IsPauseMenuOpen():
            return  # Native HUD visibility/fades are not ours to override.
        if now < _next_bloodlust_tint.get(owner, 0.0):
            return
        if len(_next_bloodlust_tint) >= 16 and owner not in _next_bloodlust_tint:
            _next_bloodlust_tint.clear()
        _next_bloodlust_tint[owner] = now + 0.25
        pawn, tree = controller.GetWillowPlayerPawn(), controller.PlayerSkillTree
        if (pawn is None or pawn.bDeleteMe or pawn.Controller != controller
                or tree is None or not tree.bInitialized):
            return
        movie = controller.GetHUDMovie()
        if movie is None or movie.WPCOwner != controller:
            return
        hud = movie.MyHUDOwner
        if hud is None or hud.bDeleteMe or hud.WorldInfo != world:
            return
        movie_id = movie._get_address()
        for stale_owner, state in tuple(_bloodlust_tint_state.items()):
            if state[0] != world_id or (stale_owner == owner and state[1] != movie_id):
                _bloodlust_tint_state.pop(stale_owner, None)  # No calls into an old movie.
        previous = _bloodlust_tint_state.get(owner)
        definition = _find("SkillDefinition", BLOODLUST_STACKS_PATH)
        overdrive = _find("SkillDefinition", BLOOD_OVERDRIVE_PATH)
        if definition is None or overdrive is None or pawn is None or definition.SkillIcon is None:
            if previous is not None:
                _restore_bloodlust_icon(movie, previous[2], previous[3])
                _bloodlust_tint_state.pop(owner, None)
            return
        ready = int(controller.GetSkillGrade(overdrive)) > 0 and not pawn.IsInjuredDead()
        slot, stacks = -1, 0
        if ready:
            slot = int(movie.GetRemappedSlot(definition))
            attribute = _find("DesignerAttributeDefinition", BLOODLUST_STACK_ATTRIBUTE)
            context = attribute.ResolveContext(controller) if attribute is not None else None
            value = float(context.Value) if context is not None else 0.0
            stacks = int(value) if math.isfinite(value) else 0
        key = "Bloodlust HUD polling"
        if key not in _verified_fixes:
            _verified_fixes.add(key)
            unrealsdk.logging.info(
                f"[KriegRebalance] {key}: stacks={stacks}, native_slot={slot}")
        ready = ready and stacks >= OVERCHARGE_THRESHOLD
        if not ready:
            if previous is not None:
                _restore_bloodlust_icon(movie, previous[2], previous[3])
                _bloodlust_tint_state.pop(owner, None)
            return
        # Resolve the existing loader by its actual loaded SWF URL. A different
        # remap or UI ordering must not accidentally tint another skill's image.
        icon_name = str(definition.SkillIcon.Name).casefold()
        candidates = ([previous[2]] if previous is not None else []) + [slot] + list(range(11))
        seen: set[int] = set()
        clip, display_slot, observed_url = None, -1, ""
        # FindTrackedSkill supplies the live native slot's state and Flash path.
        # Accept it only when BOTH the skill and the known image path match.
        tracked, native_path = None, ""
        if 0 <= slot < 11:
            try:
                state = unrealsdk.make_struct(
                    "WillowGame.WillowPlayerReplicationInfo:TrackedSkillState",
                    SkillDef=None, PackedStackCountAndPercentComplete=0)
                # Out params are mandatory inputs in pyunrealsdk. Its tuple
                # also includes Ellipsis for this function's void return value.
                _void, tracked, native_path, _frame = movie.FindTrackedSkill(
                    definition.TrackedSkillType, slot, state, "", "")
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                # This auxiliary lookup must not prevent the independently
                # verified image-URL fallback from identifying the native icon.
                key = "Bloodlust native HUD lookup"
                if key not in _reported_errors:
                    _reported_errors.add(key)
                    unrealsdk.logging.info(
                        f"[KriegRebalance] {key} unavailable: {exc}; checking loaded image URLs")
        native_path = str(native_path)
        if native_path.startswith("p1."):
            native_path = "_root." + native_path
        if tracked is not None and tracked.SkillDef == definition:
            for candidate in range(11):
                image_path = BLOODLUST_IMAGE_PATH.format(slot=candidate + 1)
                if native_path in (image_path, image_path.removesuffix(".placeholderTexture")):
                    clip = movie.GetVariableObject(image_path)
                    if clip is not None:
                        display_slot = candidate
                    break
        for candidate in candidates:
            if clip is not None:
                break
            if candidate in seen or not 0 <= candidate < 11:
                continue
            seen.add(candidate)
            target = movie.GetVariableObject(BLOODLUST_IMAGE_PATH.format(slot=candidate + 1))
            if target is None:
                continue
            current_url = str(target.GetString("_url"))
            if not observed_url:
                observed_url = current_url
            url = current_url.casefold()
            if url.endswith(icon_name) or icon_name + "." in url:
                clip, display_slot = target, candidate
                break
        if clip is None:
            if previous is not None:
                _restore_bloodlust_icon(movie, previous[2], previous[3])
                _bloodlust_tint_state.pop(owner, None)
            key = "Bloodlust HUD image pending"
            if key not in _reported_errors:
                _reported_errors.add(key)
                unrealsdk.logging.info(
                    f"[KriegRebalance] {key}: expected={definition.SkillIcon.Name}, "
                    f"observed_url={observed_url}, native_path={native_path}")
            return  # Unsupported HUD/loader: leave all icons untouched, do not guess.
        if previous is not None and previous[2] != display_slot:
            _restore_bloodlust_icon(movie, previous[2], previous[3])
            _bloodlust_tint_state.pop(owner, None)
            previous = None
        transform = clip.GetColorTransform()
        current = _bloodlust_icon_rgb(transform)
        if previous is not None and _bloodlust_rgb_matches(current, BLOODLUST_RED_RGB):
            return
        if len(_bloodlust_tint_state) >= 16 and owner not in _bloodlust_tint_state:
            return
        # Capture only numeric RGB values, never retain a GFx/movie/controller object.
        _bloodlust_tint_state[owner] = (world_id, movie_id, display_slot, current)
        _set_bloodlust_icon_rgb(clip, transform, BLOODLUST_RED_RGB)
        key = "Bloodlust red readiness highlight"
        if key not in _verified_fixes:
            _verified_fixes.add(key)
            unrealsdk.logging.info(
                f"[KriegRebalance] {key}: stacks={stacks}, native_slot={slot}, display_slot={display_slot}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Bloodlust HUD highlight"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


def _stack_hud_feedback(
    definition: Any, path: str, object_name: str, label: str, limit: int,
    *, counter: bool = True,
) -> Any | None:
    """A native counter with the menu icon and no gameplay effects or events."""
    if definition.SkillIcon is None:
        return None
    feedback = _find("SkillDefinition", path)
    if feedback is None:
        _prepared_runtime_leaves.discard(path)
        feedback = unrealsdk.construct_object(
            "SkillDefinition", definition, object_name, template_obj=definition)
    _set_property(feedback, "SkillName", f"{label} stacks" if counter else label)
    _set_property(feedback, "SkillIcon", definition.SkillIcon)
    _set_property(feedback, "SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive)
    _set_property(feedback, "bSubjectToGradeRules", False)
    _set_property(feedback, "MaxGrade", limit)
    _set_property(feedback, "TrackedSkillType", unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered)
    _set_property(feedback, "DurationType", unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite)
    _set_property(feedback, "InitialDuration", 0.0)
    _set_property(feedback, "BehaviorProviderDefinition", None)
    _set_property(feedback, "TrackedActiveSkill", None)
    for field in ("SkillEffectDefinitions", "SkillEffectPresentations", "SkillConstraints",
                  "DamageEvents", "KillEvents", "TrackedActiveSkills"):
        if getattr(feedback, field, ()):
            setattr(feedback, field, [])
        if getattr(feedback, field, ()):
            raise RuntimeError(f"{label} HUD retained gameplay data: {field}")
    if not counter:
        _set_property(feedback, "CustomStackCount", None)
        _prepared_runtime_leaves.add(path)
        return feedback
    # The native HUD reads CustomStackCount. Resolve this visual skill's Grade
    # (1..5), never the gameplay helper's stacks*rank or a shared global value.
    count = _find("AttributeDefinition", f"{path}.StackCount")
    if count is None:
        count = unrealsdk.construct_object("AttributeDefinition", feedback, "StackCount")
    context = _find("SkillAttributeContextResolver", f"{path}.StackCount.SkillContext")
    if context is None:
        context = unrealsdk.construct_object("SkillAttributeContextResolver", count, "SkillContext")
    resolver = _find("ObjectPropertyAttributeValueResolver", f"{path}.StackCount.GradeValue")
    if resolver is None:
        resolver = unrealsdk.construct_object("ObjectPropertyAttributeValueResolver", count, "GradeValue")
    _set_property(context, "AssociatedSkill", feedback)
    _set_property(resolver, "PropertyName", "Grade")
    _set_property(count, "bIsSimpleAttribute", True)
    _set_property(count, "AttributeDataType", unrealsdk.find_enum("EAttributeDataType").ADT_Int)
    if list(count.ContextResolverChain) != [context]:
        count.ContextResolverChain = [context]
    if list(count.ValueResolverChain) != [resolver]:
        count.ValueResolverChain = [resolver]
    if list(count.ContextResolverChain) != [context] or list(count.ValueResolverChain) != [resolver]:
        raise RuntimeError(f"{label} HUD did not retain its counter resolvers")
    _set_property(feedback, "CustomStackCount", count)
    _prepared_runtime_leaves.add(path)  # Mark only after all construction/readbacks succeeded.
    # Registration/active instances retain this leaf in the CURRENT native HUD.
    # No Python UObject cache, permanent root flag, or gameplay-child linkage.
    return feedback


def _pain_hud_feedback(definition: Any) -> Any | None:
    return _stack_hud_feedback(
        definition, PAIN_HUD_PATH, "KriegRebalance_PainHUD", "Pain is Power", PAIN_STACK_LIMIT)


def _stack_hud_free_slot(controller: Any, movie: Any, feedback: Any) -> int | None:
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


def _prepare_stack_hud_slot(
    controller: Any, movie: Any, feedback: Any, label: str = "Pain is Power",
) -> bool:
    manager = controller.GetSkillManager()
    active = any(s.Definition == feedback and s.SkillInstigator == controller for s in manager.ActiveSkills)
    slot = _stack_hud_free_slot(controller, movie, feedback)
    if slot is None or (active and (int(feedback.TrackedSkillHUDSlot) != slot
                                   or int(movie.GetRemappedSlot(feedback)) != slot)):
        if active:
            manager.DeactivateSkill(controller, feedback)  # Never the gameplay helper.
            movie.UpdateSkillIcons()
        if slot is None:
            key = f"{label} HUD full"
            if key not in _reported_errors:
                _reported_errors.add(key)
                unrealsdk.logging.info(f"[KriegRebalance] {label} HUD hidden: no free native slot; bonuses unchanged")
            return False
    _set_property(feedback, "TrackedSkillHUDSlot", slot)
    if not any(entry.SkillDef == feedback for entry in movie.AvailableTrackedSkills):
        movie.AddTrackedSkill(feedback)
        # Native registration may remap other entries. Re-evaluate the ACTUAL
        # post-registration state, not a stale list of free slots.
        slot = _stack_hud_free_slot(controller, movie, feedback)
        if slot is None:
            return False
        _set_property(feedback, "TrackedSkillHUDSlot", slot)
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
    _set_property(movie, "NumPurchasedTrigRespSlots", purchased)
    return True


def _sync_pain_hud(controller: Any) -> None:
    global _pain_hud_context, _pain_hud_departing_context
    # Resolve the current local owner every time, never retain a world actor.
    current = get_pc(possibly_loading=True)
    if current is None or current._get_address() != controller._get_address() or controller.bDeleteMe:
        return
    world = controller.WorldInfo
    if world is None or world.bDeleteMe:
        return
    address = (controller._get_address(), world._get_address())
    if (_pain_hud_departing_context is not None
            and (address == _pain_hud_departing_context
                 or _pain_hud_departing_context == (address[0], 0))):
        return  # Residual ticks in a departing world cannot resume HUD work.
    pawn, tree = controller.GetWillowPlayerPawn(), controller.PlayerSkillTree
    if (pawn is None or pawn.bDeleteMe or pawn.Controller != controller or tree is None
            or not tree.bInitialized or world.Pauser or controller.IsPauseMenuOpen()):
        return  # Native HUD owns pause/menu visibility; do not reset gameplay.
    _pain_hud_context = address
    _pain_hud_departing_context = None
    definition = _find("SkillDefinition", PAIN_IS_POWER_PATH)
    if definition is None:
        return
    count = _pain_stacks.get((address[1], pawn._get_address()), (0, 0.0))[0]
    if int(controller.GetSkillGrade(definition)) <= 0 or pawn.IsInjuredDead():
        count = 0
    feedback = _find("SkillDefinition", PAIN_HUD_PATH)
    if count <= 0 and feedback is None:
        return
    movie = controller.GetHUDMovie()
    if movie is None:
        return
    manager = controller.GetSkillManager()
    if manager is None:
        return
    gameplay = _find("SkillDefinition", PAIN_STACK_EFFECT_PATH)
    if count > 0 and not any(s.Definition == gameplay and s.SkillInstigator == controller
                             and int(s.Grade) > 0 for s in manager.ActiveSkills):
        count = 0  # An unapplied gameplay helper is not an active bonus to advertise.
    if count <= 0:
        if any(s.Definition == feedback and s.SkillInstigator == controller for s in manager.ActiveSkills):
            manager.DeactivateSkill(controller, feedback)
            movie.UpdateSkillIcons()
        return
    if feedback is None or PAIN_HUD_PATH not in _prepared_runtime_leaves:
        feedback = _pain_hud_feedback(definition)
    if feedback is None or not _prepare_stack_hud_slot(controller, movie, feedback):
        return
    _show_stack_hud_count(controller, movie, manager, feedback, count, "Pain is Power")


def _show_stack_hud_count(
    controller: Any, movie: Any, manager: Any, feedback: Any, count: int, label: str,
) -> None:
    instances = [s for s in manager.ActiveSkills if s.Definition == feedback and s.SkillInstigator == controller]
    changed = False
    if not instances:
        if manager.ActivateSkill(controller, feedback, None, count) is False:
            raise RuntimeError(f"{label} HUD feedback activation was rejected")
        changed = True
    elif len(instances) != 1:
        raise RuntimeError(f"{label} HUD has duplicate visual instances")
    elif int(instances[0].Grade) != count:
        instances[0].UpdateGrade(count)
        changed = True
    slot = int(movie.GetRemappedSlot(feedback))
    if changed or not (0 <= slot < len(movie.CachedTSkillIcon_TrigResp)
                       and movie.CachedTSkillIcon_TrigResp[slot].Icon == feedback.SkillIcon):
        movie.UpdateSkillIcons()
    key = f"{label} native HUD"
    if key not in _verified_fixes:
        _verified_fixes.add(key)
        unrealsdk.logging.info(f"[KriegRebalance] {label} native HUD registered: slot={slot}, stacks={count}")


def _maintain_pain_hud(controller: Any, now: float) -> None:
    if controller is None:
        return
    try:
        address = controller._get_address()
        if now < _next_pain_hud_sync.get(address, 0.0):
            return
        if len(_next_pain_hud_sync) >= 16 and address not in _next_pain_hud_sync:
            _next_pain_hud_sync.clear()
        _next_pain_hud_sync[address] = now + 0.25
        _sync_pain_hud(controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Pain is Power HUD"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not update {key}: {exc}")
    # Share the existing quarter-second HUD cadence; no additional tick hook.
    try:
        _sync_fuel_rampage_hud(controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Fuel the Rampage HUD"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not update {key}: {exc}")


def _sync_fuel_rampage_hud(controller: Any) -> None:
    global _pain_hud_context, _pain_hud_departing_context
    owner = controller._get_address()
    state = _fuel_speed_until.get(owner)
    if state is None and owner not in _fuel_hud_owners:
        return  # Idle feature: no definition lookup, HUD call or skill scan.
    current = get_pc(possibly_loading=True)
    if current is None or current._get_address() != owner or controller.bDeleteMe:
        return
    world = controller.WorldInfo
    if world is None or world.bDeleteMe:
        return
    address = (owner, world._get_address())
    if _pain_hud_departing_context in (address, (owner, 0)):
        return
    pawn, tree = controller.GetWillowPlayerPawn(), controller.PlayerSkillTree
    if (pawn is None or pawn.bDeleteMe or pawn.Controller != controller or tree is None
            or not tree.bInitialized or world.Pauser or controller.IsPauseMenuOpen()):
        return
    _pain_hud_context = address
    _pain_hud_departing_context = None
    now = float(world.TimeSeconds)
    active = (state is not None and state[:2] == (address[1], pawn._get_address())
              and math.isfinite(now) and 0.0 < state[2] - now <= FUEL_SPEED_DURATION + 0.000001
              and not pawn.IsInjured() and not pawn.IsInjuredDead())
    definition = _find("SkillDefinition", FUEL_RAMPAGE_PATH)
    if definition is None:
        return
    active = active and int(controller.GetSkillGrade(definition)) > 0
    movie = controller.GetHUDMovie()
    if movie is None or movie.WPCOwner != controller:
        return
    hud = movie.MyHUDOwner
    if hud is None or hud.bDeleteMe or hud.WorldInfo != world:
        return
    manager = controller.GetSkillManager()
    if manager is None:
        return
    gameplay = _find("SkillDefinition", FUEL_SPEED_PATH)
    active = active and gameplay is not None and any(
        skill.Definition == gameplay and skill.SkillInstigator == controller
        and int(skill.Grade) > 0
        and skill.SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active
        for skill in manager.ActiveSkills)
    feedback = _find("SkillDefinition", FUEL_HUD_PATH)
    if not active:
        if feedback is not None and any(s.Definition == feedback and s.SkillInstigator == controller
                                        for s in manager.ActiveSkills):
            manager.DeactivateSkill(controller, feedback)
            movie.UpdateSkillIcons()
        _fuel_hud_owners.discard(owner)
        return
    if feedback is None or FUEL_HUD_PATH not in _prepared_runtime_leaves:
        feedback = _stack_hud_feedback(
            definition, FUEL_HUD_PATH, "KriegRebalance_FuelHUD", "Fuel the Rampage", 1,
            counter=False)
    if feedback is None or not _prepare_stack_hud_slot(controller, movie, feedback, "Fuel the Rampage"):
        _fuel_hud_owners.discard(owner)
        return
    _show_stack_hud_count(controller, movie, manager, feedback, 1, "Fuel the Rampage")
    _fuel_hud_owners.add(owner)


def _suspend_pain_hud(controller: Any, *, before_travel: bool = False) -> None:
    global _pain_hud_departing_context
    address = controller._get_address()
    _fuel_hud_owners.discard(address)
    _bloodlust_tint_state.pop(address, None)
    _next_bloodlust_tint.pop(address, None)
    current = get_pc(possibly_loading=True)
    if not ((current is not None and current._get_address() == address)
            or (_pain_hud_context is not None and _pain_hud_context[0] == address)):
        return
    if _pain_hud_departing_context is None or _pain_hud_departing_context[0] != address:
        source = _pain_owner_keys.get(address)
        known = _pain_hud_context if _pain_hud_context is not None and _pain_hud_context[0] == address else None
        _pain_hud_departing_context = known or (address, source[0] if source is not None else 0)
        if before_travel:
            world = controller.WorldInfo  # PRE travel is live; Destroyed never reads world fields.
            _pain_hud_departing_context = (address, world._get_address() if world is not None else 0)
    # No GetHUDMovie/GetSkillManager, deactivation or cleanup on the old owner.


@hook("WillowGame.WillowPlayerController:PreClientTravel", Type.PRE)
def suspend_pain_hud_before_travel(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if _audio_trace and controller._get_address() == _audio_trace["owners"][0]:
        _stop_audio_trace()
    _suspend_pain_hud(controller, before_travel=True)


@hook("WillowGame.WillowPlayerController:Destroyed", Type.PRE)
def suspend_pain_hud_before_destroy(controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if _audio_trace and controller._get_address() == _audio_trace["owners"][0]:
        _stop_audio_trace()
    _suspend_pain_hud(controller)


def _configure_salt_decay() -> bool:
    provider = _find("BehaviorProviderDefinition", SALT_DECAY_PROVIDER_PATH)
    if provider is None:
        return False
    # The native StackDecay sequence subtracts one stack, then schedules itself.
    # Change only that recursive delay, preserving the separate hold/reset timer.
    if len(provider.BehaviorSequences) < 2:
        raise ValueError("Missing Salt the Wound decay sequence")
    sequence = provider.BehaviorSequences[1]
    if str(sequence.BehaviorSequenceName) != "StackDecay":
        raise ValueError("Unexpected Salt the Wound decay sequence")
    if len(sequence.ConsolidatedOutputLinkData) < 3:
        raise ValueError("Missing Salt the Wound decay loop")
    link = sequence.ConsolidatedOutputLinkData[2]
    if int(link.LinkIdAndLinkedBehavior) != -16777216:
        raise ValueError("Unexpected Salt the Wound decay loop")
    _set_property(link, "ActivateDelay", SALT_DECAY_INTERVAL)
    return True


def _configure_stack_hud() -> bool:
    salt = _find("SkillDefinition", SALT_STACKS_PATH)
    elation = _find("SkillDefinition", ELATION_STACKS_PATH)
    if salt is None or elation is None:
        return False
    old_salt = int(salt.TrackedSkillHUDSlot)
    old_elation = int(elation.TrackedSkillHUDSlot)
    if old_salt == SALT_HUD_SLOT and old_elation == ELATION_HUD_SLOT:
        return True
    try:
        _set_property(elation, "TrackedSkillHUDSlot", ELATION_HUD_SLOT)
        _set_property(salt, "TrackedSkillHUDSlot", SALT_HUD_SLOT)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        # Restore both definitions if either native field rejects the layout.
        for definition, previous in ((salt, old_salt), (elation, old_elation)):
            try:
                _set_property(definition, "TrackedSkillHUDSlot", previous)
            except (AttributeError, TypeError, ValueError, RuntimeError):
                pass
        raise
    return True


def _configure_silence_description() -> bool:
    definition = _find("SkillDefinition", SILENCE_PATH)
    if definition is None:
        return False
    description = str(definition.SkillDescription)
    if SILENCE_DESCRIPTION_LINE not in description:
        separator = "<br><br>" if description.strip() else ""
        _set_property(definition, "SkillDescription", description.rstrip() + separator + SILENCE_DESCRIPTION_LINE)
    return True


@hook("WillowGame.Behavior_CauseDamage:ApplyBehaviorToContext", Type.PRE)
def limit_silence_self_damage(behavior: Any, args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    # Block only this skill's native damage event, not melee input/other damage.
    if str(behavior._path_name()) != SILENCE_SELF_DAMAGE_PATH:
        return None
    try:
        context = args.ContextObject
        if context is None:
            return None
        controller = getattr(context, "Controller", None)
        if controller is None:
            controller = context  # Native context may already be the controller.
        if controller.bDeleteMe:
            return None
        pawn = controller.GetWillowPlayerPawn()
        world = controller.WorldInfo
        if (pawn is None or pawn.bDeleteMe or pawn.Controller != controller
                or world is None or world.bDeleteMe):
            return None
        now = float(world.TimeSeconds)  # Gameplay time: paused time does not consume cooldown.
        if not math.isfinite(now):
            return None
        key = (world._get_address(), pawn._get_address())
        previous = _silence_self_damage_at.get(key)
        if previous is not None and 0.0 <= now - previous < SILENCE_SELF_DAMAGE_COOLDOWN:
            message = "Silence the Voices cooldown blocked self-damage"
            if message not in _verified_fixes:
                _verified_fixes.add(message)
                unrealsdk.logging.info(f"[KriegRebalance] {message}")
            return Block
        if len(_silence_self_damage_at) >= 16 and key not in _silence_self_damage_at:
            _silence_self_damage_at.clear()
        _silence_self_damage_at[key] = now
        message = "Silence the Voices self-damage cooldown armed: 3 seconds"
        if message not in _verified_fixes:
            _verified_fixes.add(message)
            unrealsdk.logging.info(f"[KriegRebalance] {message}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key_error = "Silence the Voices self-damage cooldown"
        if key_error not in _reported_errors:
            _reported_errors.add(key_error)
            unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key_error}: {exc}")
    return None  # Unknown contexts fail open; never suppress unrelated damage.


def _configure_silence_visuals() -> bool:
    complete = True
    for path in SILENCE_CAMERA_PATHS:
        behavior = _find("PlayerBehavior_CameraAnim", path)
        if behavior is None:
            complete = False
            continue
        _set_property(behavior, "Anim", None)
    for path in SILENCE_PARTICLE_PATHS:
        behavior = _find("Behavior_ScreenParticle", path)
        if behavior is None:
            complete = False
            continue
        current = behavior.Parameters
        if current.Template is not None or current.TemplateScreenParticleMaterial is not None:
            # Removing both templates suppresses the four screen effects.
            # Keep unrelated struct settings rather than reinitializing all fields.
            parameters = copy.copy(current)
            parameters.Template = None
            parameters.TemplateScreenParticleMaterial = None
            behavior.Parameters = parameters
        actual = behavior.Parameters
        if actual.Template is not None or actual.TemplateScreenParticleMaterial is not None:
            raise RuntimeError("Silence the Voices screen templates were not cleared")
    return complete


def _blood_formula_matches(formula: Any, bonus: Any, grade: Any) -> bool:
    expected = (("Multiplier", 0.0, bonus), ("Level", 0.0, grade),
                ("Power", 1.0, None), ("Offset", 0.0, None))
    if not formula.bEnabled:
        return False
    for name, constant, attribute in expected:
        value = getattr(formula, name)
        if (value.BaseValueConstant != constant or value.BaseValueAttribute != attribute
                or value.InitializationDefinition is not None or value.BaseValueScaleConstant != 1.0):
            return False
    return True


def _configure_blood_overdrive() -> bool:
    initializer = _find("AttributeInitializationDefinition", BLOOD_INITIALIZER_PATH)
    bonus = _find("DesignerAttributeDefinition", BLOOD_BONUS_PATH)
    grade = _find("AttributeDefinition", BLOOD_GRADE_PATH)
    if initializer is None or bonus is None or grade is None:
        return False
    if not _blood_formula_matches(initializer.ValueFormula, bonus, grade):
        formula = copy.copy(initializer.ValueFormula)
        formula.bEnabled = True
        for name, constant, attribute in (("Multiplier", 0.0, bonus), ("Level", 0.0, grade),
                                          ("Power", 1.0, None), ("Offset", 0.0, None)):
            value = copy.copy(getattr(formula, name))
            value.BaseValueConstant = constant
            value.BaseValueAttribute = attribute
            value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0
            setattr(formula, name, value)
        initializer.ValueFormula = formula
    if not _blood_formula_matches(initializer.ValueFormula, bonus, grade):
        raise RuntimeError("Blood Overdrive rank formula did not retain its configured structure")
    return True


def _overcharge_value(template: Any, constant: float = 0.0, attribute: Any = None,
                       initializer: Any = None) -> Any:
    value = copy.copy(template)
    value.BaseValueConstant = constant
    value.BaseValueAttribute = attribute
    value.InitializationDefinition = initializer
    value.BaseValueScaleConstant = 1.0
    return value


def _overcharge_initializer(definition: Any, name: str, template: Any, terms: tuple[Any, ...],
                             *, conditional: bool = False) -> Any:
    """Private initializer; nested source initializers always receive a unit base."""
    initializer = _find("AttributeInitializationDefinition", f"{BLOOD_OVERDRIVE_PATH}:{name}")
    if initializer is None:
        initializer = unrealsdk.construct_object(
            "AttributeInitializationDefinition", definition, name, template_obj=template)
    for field in ("BaseValueMode", "RoundingMode"):
        _set_property(initializer, field, getattr(template, field))
    formula = copy.copy(template.ValueFormula)
    formula.bEnabled = not conditional
    for field, constant, attribute, nested in terms:
        setattr(formula, field, _overcharge_value(getattr(formula, field), constant, attribute, nested))
    _set_native_data(initializer, "ValueFormula", formula)
    for field in (("RandomVariance",) if conditional else ("ConditionalInitialization", "RandomVariance")):
        data = copy.copy(getattr(initializer, field))
        data.bEnabled = False
        _set_native_data(initializer, field, data)
    data = copy.copy(initializer.RangeRestriction)
    data.bEnableMinValueRestriction = data.bEnableMaxValueRestriction = False
    _set_native_data(initializer, "RangeRestriction", data)
    return initializer


def _overcharge_any_kill_events(definition: Any) -> list[Any]:
    """Remove source/type restrictions, preserving the provider's legacy event names."""
    events = []
    for original in definition.KillEvents:
        event = copy.copy(original)
        constraints = []
        for original_constraint in original.EventConstraints:
            constraint = copy.copy(original_constraint)
            constraint.DamageSourceConstraint = None
            constraint.DamageTypeConstraint = None
            constraint.bMustBeCriticalDamage = False
            constraint.bMustBeOneShotKill = False
            constraints.append(constraint)
        event.EventConstraints = constraints
        events.append(event)
    return events


def _restore_overcharge_sources(targets: list[tuple[Any, Any, str]]) -> bool:
    """Unwrap only our former amplification; preserve original skill formulas."""
    changed = False
    for skill, source, name in targets:
        wrapper = _find("AttributeInitializationDefinition", f"{BLOOD_OVERDRIVE_PATH}:KriegRebalance_Overcharge_{name}")
        upgrade = _find("AttributeInitializationDefinition", f"{BLOOD_OVERDRIVE_PATH}:KriegRebalance_Overcharge_{name}_Upgrade")
        effects = []
        restored = False
        for original in skill.SkillEffectDefinitions:
            effect = copy.copy(original)
            if wrapper is not None and effect.BaseModifierValue.InitializationDefinition == wrapper:
                data = copy.copy(effect.BaseModifierValue)
                data.InitializationDefinition = source
                effect.BaseModifierValue = data
                restored = True
            if upgrade is not None and effect.PerGradeUpgrade.InitializationDefinition == upgrade:
                data = copy.copy(effect.PerGradeUpgrade)
                data.InitializationDefinition = upgrade.ValueFormula.Level.InitializationDefinition
                effect.PerGradeUpgrade = data
                restored = True
            effects.append(effect)
        if restored:
            changed |= _set_native_data(skill, "SkillEffectDefinitions", effects)
            _overcharge_restore_paths.add(str(skill._path_name()))
    return changed


def _blood_overdrive_threshold_gate(definition: Any, template: Any, conditions: Any,
                                    grade: Any, stacks: Any, name: str, coefficient: float) -> Any:
    rank = _overcharge_initializer(definition, f"KriegRebalance_Overdrive{name}Rank", template, (
        ("Multiplier", coefficient, None, None), ("Level", 0.0, grade, None),
        ("Power", 1.0, None, None), ("Offset", 0.0, None, None)))
    gate = _overcharge_initializer(definition, f"KriegRebalance_Overdrive{name}Gate", template, (
        ("Multiplier", 0.0, None, None), ("Level", 0.0, None, None),
        ("Power", 1.0, None, None), ("Offset", 0.0, None, None)), conditional=True)
    conditional = copy.copy(conditions.ConditionalInitialization)
    row = copy.copy(conditional.ConditionalExpressionList[-1])
    expression = copy.copy(row.Expressions[0])
    expression.AttributeOperand1, expression.AttributeOperand2 = stacks, None
    expression.ConstantOperand2 = float(OVERCHARGE_THRESHOLD)
    row.Expressions = [expression]
    row.BaseValueIfTrue = _overcharge_value(row.BaseValueIfTrue, 1.0, initializer=rank)
    conditional.bEnabled = True
    conditional.ConditionalExpressionList = [row]
    conditional.DefaultBaseValue = _overcharge_value(conditional.DefaultBaseValue)
    _set_native_data(gate, "ConditionalInitialization", conditional)
    return gate


def _configure_overcharge() -> bool:
    """Native timed child owns the speed/rate buffs; stack gains keep their native graph."""
    global _overcharge_revision, _blood_overdrive_configured, _bloodlust_gain_address
    definition = _find("SkillDefinition", BLOOD_OVERDRIVE_PATH)
    child = _find("SkillDefinition", BLOOD_OVERDRIVE_CHILD_PATH)
    template = _find("AttributeInitializationDefinition", BLOOD_INITIALIZER_PATH)
    grade = _find("AttributeDefinition", BLOOD_GRADE_PATH)
    stacks = _find("DesignerAttributeDefinition", BLOODLUST_STACK_ATTRIBUTE)
    conditions = _find("AttributeInitializationDefinition", NUMBED_INITIALIZER_PATH)
    speed = _find("AttributeDefinition", FUEL_SPEED_ATTRIBUTE)
    fire_rate = _find("AttributeDefinition", "D_Attributes.Weapon.WeaponFireInterval")
    gain = _find("Behavior_SimpleMath", BLOODLUST_GAIN_PATH)
    cap = _find("Behavior_SimpleMath", BLOODLUST_CAP_PATH)
    if (definition is None or child is None or template is None or grade is None
            or stacks is None or conditions is None or speed is None or fire_rate is None
            or gain is None or cap is None):
        return False
    if not definition.KillEvents or not child.KillEvents:
        return False
    rows = list(conditions.ConditionalInitialization.ConditionalExpressionList)
    if not rows or not rows[-1].Expressions:
        return False
    operations = unrealsdk.find_enum("WillowGame.Behavior_SimpleMath.EBinaryMathOperation")
    if gain.Operation != operations.BINARYMATH_Add or cap.Operation != operations.BINARYMATH_Min:
        raise RuntimeError("Bloodlust's native gain/cap operations were changed by another mod")
    targets = []
    for name, source_name in OVERCHARGE_TARGETS:
        skill = _find("SkillDefinition", f"GD_Lilac_Skills_Bloodlust.Skills.{name}")
        source = _find("AttributeInitializationDefinition", f"GD_Lilac_Skills_Bloodlust.Attributes.{source_name}")
        if skill is None or source is None:
            return False
        targets.append((skill, source, source_name))
    # Complete dependency validation precedes removal of any previous effects.
    changed = _restore_overcharge_sources(targets)
    _configure_blood_twitch()  # Its two private formulas no longer reference Overcharge.
    effects = []
    for name, attribute, coefficient in (("Speed", speed, BLOOD_OVERDRIVE_SPEED_PER_RANK),
                                         ("FireRate", fire_rate, -BLOOD_OVERDRIVE_FIRE_RATE_PER_RANK)):
        gate = _blood_overdrive_threshold_gate(definition, template, conditions, grade, stacks, name, coefficient)
        effect = unrealsdk.make_struct(
            "WillowGame.SkillDefinition:SkillEffectData", AttributeToModify=attribute,
            bIncludeDuelingTargets=False, bIncludeSelfAsTarget=False,
            bOnlyEffectTargetsInRange=False, bExcludeNonPlayerCharacters=False,
            EffectTarget=unrealsdk.find_enum("EEffectTarget").TARGET_Self,
            TargetInstanceDataName="None", TargetCriteria=unrealsdk.find_enum("ETargetCriteria").CRITERIA_None,
            ModifierType=unrealsdk.find_enum("EModifierType").MT_Scale,
            GradeToStartApplyingEffect=1, PerGradeUpgradeInterval=1, BonusUpgradeList=[])
        effect.BaseModifierValue = _overcharge_value(effect.BaseModifierValue, 1.0, initializer=gate)
        effect.PerGradeUpgrade = _overcharge_value(effect.PerGradeUpgrade)
        effects.append(effect)
    changed |= _set_native_data(child, "SkillEffectDefinitions", effects)
    changed |= _set_native_data(definition, "SkillEffectDefinitions", [])
    changed |= _set_native_data(definition, "KillEvents", _overcharge_any_kill_events(definition))
    changed |= _set_native_data(child, "KillEvents", _overcharge_any_kill_events(child))
    _set_native_data(definition, "SkillEffectPresentations", [])
    _set_property(definition, "SkillDescription", OVERCHARGE_DESCRIPTION)
    changed |= _set_property_changed(child, "bAutoUpdateContexts", True)
    changed |= _set_property_changed(child, "SkillEffectUpdateIterval", 0.1)
    if changed:
        _overcharge_revision += 1
    _blood_overdrive_configured = True
    _bloodlust_gain_address = gain._get_address()
    return True


def _set_property_changed(obj: Any, field: str, expected: Any) -> bool:
    """Scalar comparison with native float32 tolerance; report only real invalidations."""
    changed = not _native_data_matches(getattr(obj, field), expected)
    if changed:
        setattr(obj, field, expected)
    if not _native_data_matches(getattr(obj, field), expected):
        raise RuntimeError(f"Native field did not retain its value: {field}")
    return changed


def _refresh_overcharge_caches(controller: Any) -> None:
    """One-time live-cache migration after configuration; never restart kill timers."""
    if controller is None or controller.bDeleteMe:
        return
    if _overcharge_revision <= 0:
        return  # Static configuration is still pending, or no migration is needed.
    world = controller.WorldInfo
    if world is None or world.bDeleteMe or world.Pauser:
        return
    manager = controller.GetSkillManager()
    if manager is None:
        return
    paths = {BLOOD_OVERDRIVE_PATH, BLOOD_OVERDRIVE_CHILD_PATH}
    paths.update(_overcharge_restore_paths)
    for skill in list(manager.ActiveSkills):
        if skill.SkillInstigator != controller or skill.Definition is None or str(skill.Definition._path_name()) not in paths:
            continue
        key = (controller._get_address(), world._get_address(), skill._get_address())
        if _overcharge_refreshed.get(key) == _overcharge_revision:
            continue
        expected = list(skill.Definition.SkillEffectDefinitions)
        current = list(skill.SkillEffects)
        unmatched = list(expected)
        paired = []
        rebuild = False
        for applied in current:
            match = next((data for data in unmatched
                          if data.AttributeToModify == applied.EffectData.AttributeToModify), None)
            if match is not None:
                paired.append((applied, match))
                unmatched.remove(match)
            elif applied.EffectData.AttributeToModify is not None:
                rebuild = True
        rebuild |= any(data.AttributeToModify is not None for data in unmatched)
        # Native caches may omit TARGET_None/stat-only rows. Do not detach a
        # magazine modifier just because the dummy rows differ in number/order.
        if rebuild:
            # Both methods and modes are native Skill API (WillowGame headers).
            # Remove only this skill's modifiers before freeing the old array.
            # Build does not dispatch activation events or restart its timer.
            modes = unrealsdk.find_enum("EAdjustModifierMode")
            active = skill.SkillState == unrealsdk.find_enum("ESkillState").SKILL_Active
            if active:
                skill.AdjustModifiers(modes.WILLOW_ADJUST_RemoveModifer, True)
            skill.SkillEffects = []
            skill.BuildSkillEffects()
            if active:
                skill.AdjustModifiers(modes.WILLOW_ADJUST_InitialAddModifer, False)
        else:
            changed = False
            for applied, data in paired:
                if not _native_data_matches(applied.EffectData, data):
                    applied.EffectData = copy.copy(data)
                    changed = True
            if changed:
                skill.SkillEffects = current
        skill.bForceRefreshModifiersNextTick = True
        if len(_overcharge_refreshed) >= 128:
            _overcharge_refreshed.clear()
        _overcharge_refreshed[key] = _overcharge_revision


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_overcharge(_tree: Any, args: Any, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or str(args.SkillDef._path_name()) != BLOOD_OVERDRIVE_PATH:
        return None
    rank = _skill_footer_rank(args)
    values = (("Chance for an extra Bloodlust stack", min(1.0, BLOOD_OVERDRIVE_EXTRA_STACK_CHANCE_PER_RANK * rank), False),
              ("Movement Speed", BLOOD_OVERDRIVE_SPEED_PER_RANK * rank, True),
              ("Fire Rate", BLOOD_OVERDRIVE_FIRE_RATE_PER_RANK * rank, True))
    lines = []
    for label, value, plus in values:
        number = ("+" if plus else "") + f"{100 * value:g}%"
        number = _format_skill_footer_rank_value(args, number, _tree)
        lines.append(f"{label}: {number}")
    return Block, ("<br>" if args.bIncludeHTML else "\n").join(lines)


def _blood_overdrive_gain_rank(args: Any) -> int:
    if not _blood_overdrive_configured:
        return 0
    controller = None
    for name in ("ContextObject", "SelfObject", "MyInstigatorObject"):
        context = getattr(args, name, None)
        if context is None:
            continue
        candidate = getattr(context, "SkillInstigator", None)
        if candidate is None:
            candidate = context if hasattr(context, "GetWillowPlayerPawn") else getattr(context, "Controller", None)
        if candidate is not None and hasattr(candidate, "GetWillowPlayerPawn"):
            controller = candidate
            break
    if (controller is None or controller.bDeleteMe
            or controller.Role != unrealsdk.find_enum("ENetRole").ROLE_Authority):
        return 0
    world = controller.WorldInfo
    if world is None or world.bDeleteMe or world.Pauser:
        return 0
    if _pain_hud_departing_context == (controller._get_address(), world._get_address()):
        return 0
    pawn = controller.GetWillowPlayerPawn()
    if pawn is None or pawn.bDeleteMe or pawn.Controller != controller or pawn.IsInjuredDead():
        return 0
    parent = _find("SkillDefinition", BLOOD_OVERDRIVE_PATH)
    child = _find("SkillDefinition", BLOOD_OVERDRIVE_CHILD_PATH)
    if parent is None or child is None:
        return 0
    invested = int(controller.GetSkillGrade(parent))
    if invested <= 0:
        return 0
    manager = controller.GetSkillManager()
    if manager is None:
        return 0
    skill = manager.GetActiveSkillForInstigatorByDefinition(controller, child)
    if (skill is None or skill.SkillInstigator != controller or skill.Definition != child
            or skill.SkillState != unrealsdk.find_enum("ESkillState").SKILL_Active):
        return 0
    return _effective_skill_rank(controller, BLOOD_OVERDRIVE_PATH, invested)


@hook("WillowGame.Behavior_SimpleMath:ApplyBehaviorToContext", Type.PRE)
def begin_blood_overdrive_gain(behavior: Any, args: Any, _ret: Any, _func: Any) -> None:
    if (not _bloodlust_gain_address or behavior._get_address() != _bloodlust_gain_address
            or str(behavior._path_name()) != BLOODLUST_GAIN_PATH):
        return
    frame: dict[str, Any] = dict(before=None, assigned=None, base=None, behavior=_bloodlust_gain_address)
    _blood_overdrive_gain_scopes.append(frame)
    try:
        current = float(behavior.A)
        if not math.isfinite(current):
            return
        base = current
        if len(_blood_overdrive_gain_scopes) > 1:
            parent = _blood_overdrive_gain_scopes[-2]
            if parent["assigned"] is not None and abs(current - parent["assigned"]) < 0.000001:
                base = parent["base"]
        frame.update(before=current, assigned=base, base=base)
        # A reentrant call from an ineligible player must not inherit +1.
        _set_property(behavior, "A", base)
        operations = unrealsdk.find_enum("WillowGame.Behavior_SimpleMath.EBinaryMathOperation")
        if behavior.Operation != operations.BINARYMATH_Add or base <= 0.0:
            return
        cap = _find("Behavior_SimpleMath", BLOODLUST_CAP_PATH)
        if cap is None or cap.Operation != operations.BINARYMATH_Min:
            return
        stacks, maximum = float(behavior.B), float(cap.B)
        if not (math.isfinite(stacks) and math.isfinite(maximum) and 0.0 <= stacks < maximum):
            return
        rank = _blood_overdrive_gain_rank(args)
        chance = min(1.0, max(0.0, BLOOD_OVERDRIVE_EXTRA_STACK_CHANCE_PER_RANK * rank))
        if chance <= 0.0 or len(_blood_overdrive_gain_scopes) > 16:
            return
        if chance < 1.0 and random.random() >= chance:
            return
        frame["assigned"] = base + 1.0
        _set_property(behavior, "A", frame["assigned"])
        key = "Blood Overdrive extra Bloodlust increment"
        if key not in _verified_fixes:
            _verified_fixes.add(key)
            unrealsdk.logging.info(
                f"[KriegRebalance] {key}: rank={rank}, chance={chance:g}, "
                f"native_increment={base:g}, chosen_increment={frame['assigned']:g}, "
                f"stacks={stacks:g}, native_cap={maximum:g}")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Blood Overdrive extra Bloodlust gain"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


@hook("WillowGame.Behavior_SimpleMath:ApplyBehaviorToContext", Type.POST_UNCONDITIONAL)
def finish_blood_overdrive_gain(behavior: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if (not _blood_overdrive_gain_scopes
            or behavior._get_address() != _blood_overdrive_gain_scopes[-1]["behavior"]):
        return
    frame = _blood_overdrive_gain_scopes.pop()
    if frame["before"] is None or frame["assigned"] is None:
        return
    try:
        # Preserve another mod's intervening change; restore only our exact assignment.
        if abs(float(behavior.A) - frame["assigned"]) < 0.000001:
            _set_property(behavior, "A", frame["before"])
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Blood Overdrive extra Bloodlust cleanup"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not finish {key}: {exc}")


def _configure_blood_bath() -> bool:
    definition = _find("SkillDefinition", BLOOD_BATH_PATH)
    initializer = _find("AttributeInitializationDefinition",
                        "GD_Lilac_Skills_Bloodlust.Attributes.Init_BloodBath_DamageModifier")
    if definition is None or initializer is None:
        return False
    if (len(definition.SkillEffectDefinitions) != 2
            or definition.SkillEffectDefinitions[0].AttributeToModify is not None):
        raise ValueError("Unexpected Blood Bath effect layout")
    # Footer and timed-child damage have separate native coefficient sources.
    # Keep the parent's effective-rank resolver and every activation/loot behavior.
    effects = [copy.copy(effect) for effect in definition.SkillEffectDefinitions]
    for field in ("BaseModifierValue", "PerGradeUpgrade"):
        value = copy.copy(getattr(effects[0], field))
        value.BaseValueConstant = BLOOD_BATH_DAMAGE_PER_RANK_STACK
        value.BaseValueAttribute = None
        value.InitializationDefinition = None
        value.BaseValueScaleConstant = 1.0
        setattr(effects[0], field, value)
    formula = copy.copy(initializer.ValueFormula)
    multiplier = copy.copy(formula.Multiplier)
    multiplier.BaseValueConstant = BLOOD_BATH_DAMAGE_PER_RANK_STACK
    multiplier.BaseValueAttribute = None
    multiplier.InitializationDefinition = None
    multiplier.BaseValueScaleConstant = 1.0
    formula.Multiplier = multiplier
    _set_native_data(initializer, "ValueFormula", formula)
    _set_native_data(definition, "SkillEffectDefinitions", effects)
    return True


def _configure_blood_filled_guns() -> bool:
    global _blood_filled_tuning_revision
    definition = _find("SkillDefinition", BLOOD_FILLED_GUNS_PATH)
    stacks = _find("DesignerAttributeDefinition", BLOODLUST_STACK_ATTRIBUTE)
    damage = _find("AttributeDefinition", "D_Attributes.Weapon.WeaponDamage")
    presentation = _find("AttributePresentationDefinition",
                         f"{BLOOD_FILLED_GUNS_PATH}:AttributePresentationDefinition_1")
    if definition is None or stacks is None or damage is None or presentation is None:
        return False
    originals = definition.SkillEffectDefinitions
    if (len(originals) not in (3, 4) or originals[0].AttributeToModify is not None
            or originals[1].AttributeToModify is None
            or str(originals[1].AttributeToModify._path_name()) != "D_Attributes.Weapon.WeaponClipSize"
            or (len(originals) == 4 and originals[3].AttributeToModify != damage)):
        raise ValueError("Unexpected Blood-Filled Guns effect layout")
    # Own every retained struct before replacing the native array. Effective Grade
    # applies once via base + (Grade - 1) * upgrade; no nested rank initializer.
    effects = [copy.copy(effect) for effect in list(originals)[:3]]
    gun = copy.copy(effects[1])
    gun.AttributeToModify = damage
    for effect, coefficient, attribute in (
            (effects[0], BLOOD_FILLED_MAGAZINE_PER_RANK_STACK, None),
            (effects[1], BLOOD_FILLED_MAGAZINE_PER_RANK_STACK, stacks),
            (gun, BLOOD_FILLED_DAMAGE_PER_RANK_STACK, stacks)):
        effect.GradeToStartApplyingEffect = 1
        effect.PerGradeUpgradeInterval = 1
        effect.BonusUpgradeList = []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(effect, field))
            value.BaseValueConstant = coefficient if attribute is None else 0.0
            value.BaseValueAttribute = attribute
            value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0 if attribute is None else coefficient
            setattr(effect, field, value)
    if _set_native_data(definition, "SkillEffectDefinitions", effects + [gun]):
        _blood_filled_tuning_revision += 1
    _set_property(presentation, "FloatPrecision", 2)
    description = str(definition.SkillDescription)
    explanation = description[description.index("<br><br>"):] if "<br><br>" in description else ""
    _set_property(definition, "SkillDescription",
                  "Increases [skill]Magazine Size[-skill] and [skill]Gun Damage[-skill] "
                  "for each stack of [skill]Bloodlust[-skill]." + explanation)
    return True


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_blood_filled_guns(tree: Any, args: Any, _ret: Any, func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or str(args.SkillDef._path_name()) != BLOOD_FILLED_GUNS_PATH:
        return None
    with prevent_hooking_direct_calls():
        native_text = func(args)
    rank = _skill_footer_rank(args)
    value = _format_skill_footer_rank_value(
        args, f"+{100 * BLOOD_FILLED_DAMAGE_PER_RANK_STACK * rank:g}%", tree)
    separator = "<br>" if args.bIncludeHTML else "\n"
    return Block, separator.join(text for text in (
        native_text, f"Gun Damage per Bloodlust Stack: {value}") if text)


def _configure_blood_twitch() -> bool:
    """Native Bloodlust melee and additive reserve regeneration; preserve swap."""
    global _blood_twitch_tuning_revision
    definition = _find("SkillDefinition", BLOOD_TWITCH_PATH)
    template = _find("AttributeInitializationDefinition", BLOOD_TWITCH_INITIALIZER_PATH)
    stacks = _find("DesignerAttributeDefinition", BLOODLUST_STACK_ATTRIBUTE)
    effect_specs = [("Melee", PAIN_MELEE_ATTRIBUTE, BLOOD_TWITCH_MELEE_PER_RANK_STACK, None)]
    for ammo in BLOOD_TWITCH_AMMO_TYPES:
        prefix = f"D_Attributes.AmmoResource_{ammo}.Ammo_{ammo}_"
        effect_specs.append((f"Reserve_{ammo}", prefix + "RegenerationRate",
                             BLOOD_TWITCH_AMMO_REGEN_PER_RANK_STACK, prefix + "MaxValue"))
    attributes = [_find("ResourcePoolAttributeDefinition" if capacity else "AttributeDefinition", path)
                  for _, path, _, capacity in effect_specs]
    capacities = [_find("ResourcePoolAttributeDefinition", path) if path else None
                  for _, _, _, path in effect_specs]
    if (definition is None or template is None or stacks is None
            or any(a is None for a in attributes) or any(a is None for a in capacities[1:])):
        return False
    initializers = []
    formulas_changed = False
    for (name, _, coefficient, _), capacity in zip(effect_specs, capacities):
        initializer = _find("AttributeInitializationDefinition", f"{BLOOD_TWITCH_PATH}:{name}")
        if initializer is None:
            initializer = unrealsdk.construct_object("AttributeInitializationDefinition", definition, name)
        _set_property(initializer, "BaseValueMode", template.BaseValueMode)
        _set_property(initializer, "RoundingMode", template.RoundingMode)
        formula = copy.copy(template.ValueFormula)
        formula.bEnabled = True
        for field, constant, attribute in (("Multiplier", 0.0 if capacity is not None else coefficient, capacity), ("Level", 1.0, None),
                                           ("Power", 1.0, None), ("Offset", 0.0, None)):
            value = copy.copy(getattr(formula, field))
            value.BaseValueConstant = constant
            value.BaseValueAttribute = attribute
            value.InitializationDefinition = None
            value.BaseValueScaleConstant = coefficient if field == "Multiplier" and capacity is not None else 1.0
            setattr(formula, field, value)
        formulas_changed |= _set_native_data(initializer, "ValueFormula", formula)
        # Private initializers must not inherit a conditional/random/capped route.
        for field in ("ConditionalInitialization", "RandomVariance"):
            data = copy.copy(getattr(initializer, field))
            data.bEnabled = False
            _set_native_data(initializer, field, data)
        data = copy.copy(initializer.RangeRestriction)
        data.bEnableMinValueRestriction = data.bEnableMaxValueRestriction = False
        _set_native_data(initializer, "RangeRestriction", data)
        initializers.append(initializer)
    effects = list(definition.SkillEffectDefinitions)
    # Remove the former recoil effect only when it uses our private initializer.
    legacy_recoil = _find("AttributeInitializationDefinition", f"{BLOOD_TWITCH_PATH}:Recoil")
    owned = initializers + ([legacy_recoil] if legacy_recoil is not None else [])
    originals = [copy.copy(e) for e in effects if e.BaseModifierValue.InitializationDefinition not in owned]
    extras = []
    for attribute, initializer, capacity in zip(attributes, initializers, capacities):
        effect = unrealsdk.make_struct(
            "WillowGame.SkillDefinition:SkillEffectData", AttributeToModify=attribute,
            bIncludeDuelingTargets=False, bIncludeSelfAsTarget=False,
            bOnlyEffectTargetsInRange=False, bExcludeNonPlayerCharacters=False,
            EffectTarget=unrealsdk.find_enum("EEffectTarget").TARGET_Self,
            TargetInstanceDataName="None", TargetCriteria=unrealsdk.find_enum("ETargetCriteria").CRITERIA_None,
            ModifierType=(unrealsdk.find_enum("EModifierType").MT_PostAdd if capacity is not None
                          else unrealsdk.find_enum("EModifierType").MT_Scale),
            GradeToStartApplyingEffect=1, PerGradeUpgradeInterval=1, BonusUpgradeList=[])
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(effect, field))
            value.BaseValueConstant = 0.0
            # Let CalculateModifierValue apply the skill's effective Grade ONCE:
            # base + (Grade - 1) * upgrade, with both terms stacks*coefficient.
            # The initializer itself no longer resolves another skill rank.
            value.BaseValueAttribute = stacks
            value.InitializationDefinition = initializer
            value.BaseValueScaleConstant = 1.0
            setattr(effect, field, value)
        extras.append(effect)
    if _set_native_data(definition, "SkillEffectDefinitions", originals + extras) or formulas_changed:
        _blood_twitch_tuning_revision += 1
    _set_property(definition, "SkillDescription", BLOOD_TWITCH_DESCRIPTION)
    return True


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_blood_twitch(_tree: Any, args: Any, _ret: Any, func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or str(args.SkillDef._path_name()) != BLOOD_TWITCH_PATH:
        return None
    with prevent_hooking_direct_calls():
        native_text = func(args)
    rank = _skill_footer_rank(args)
    melee = _format_skill_footer_rank_value(
        args, f"+{100 * BLOOD_TWITCH_MELEE_PER_RANK_STACK * rank:g}%", _tree)
    ammo = _format_skill_footer_rank_value(
        args, f"+{100 * BLOOD_TWITCH_AMMO_REGEN_PER_RANK_STACK * rank:g}%", _tree)
    separator = "<br>" if args.bIncludeHTML else "\n"
    lines = (
        native_text,
        f"Melee Damage per Bloodlust Stack: {melee}",
        f"Reserve Ammo Regeneration per Bloodlust Stack: {ammo} per second",
    )
    key = "Blood Twitch native COM stat query"
    if int(args.GradeModifier) != 0 and key not in _verified_fixes:
        _verified_fixes.add(key)
        unrealsdk.logging.info(
            f"[KriegRebalance] {key}: grade={int(args.Grade)}, "
            f"grade_modifier={int(args.GradeModifier)}, stats={' | '.join(lines[1:])}")
    text = separator.join(line for line in lines if line)
    return Block, text


def _bloody_constraints_match(constraints: Any, on_foot: Any, health: Any, paused: Any) -> bool:
    if len(constraints) != 2:
        return False
    for constraint, evaluator, definitions in ((constraints[0], None, [on_foot]),
                                                (constraints[1], health, [])):
        if (not constraint.bApplyConstraintOnActivatation or not constraint.bApplyConstraintWhileActive
                or not constraint.bApplyConstraintWhilePaused or constraint.OnFailure != paused
                or constraint.Evaluator != evaluator or list(constraint.EvaluatorDefinitions) != definitions):
            return False
    return True


def _configure_bloody_revival() -> bool:
    definition = _find("SkillDefinition", BLOODY_REVIVAL_PATH)
    health = _find("HealthStateExpressionEvaluator", BLOODY_REVIVAL_HEALTH_PATH)
    on_foot = _find("SkillExpressionEvaluatorDefinition", ON_FOOT_CONSTRAINT_PATH)
    presentation = _find("AttributePresentationDefinition", f"{BLOODY_REVIVAL_PATH}:AttributePresentationDefinition_0")
    weapon_damage = _find("AttributeDefinition", "D_Attributes.Weapon.WeaponDamage")
    if definition is None or health is None or on_foot is None or presentation is None or weapon_damage is None:
        return False
    paused = unrealsdk.find_enum("ESkillState").SKILL_Paused
    if not _bloody_constraints_match(definition.SkillConstraints, on_foot, health, paused):
        if not definition.SkillConstraints:
            raise ValueError("Bloody Revival has no native constraint struct to copy")
        constraints = []
        for evaluator, evaluators in ((None, [on_foot]), (health, [])):
            constraint = copy.copy(definition.SkillConstraints[0])
            constraint.bApplyConstraintOnActivatation = True  # Native spelling.
            constraint.bApplyConstraintWhileActive = True
            constraint.bApplyConstraintWhilePaused = True
            constraint.OnFailure = paused
            constraint.Evaluator = evaluator
            constraint.EvaluatorDefinitions = evaluators
            constraints.append(constraint)
        definition.SkillConstraints = constraints
    if not _bloody_constraints_match(definition.SkillConstraints, on_foot, health, paused):
        raise RuntimeError("Bloody Revival did not retain its two constraints")
    # Tune native gun-damage effects to 10% per rank instead of Bloodlust stacks.
    changed = False
    for effect in list(definition.SkillEffectDefinitions):
        if effect.AttributeToModify is not None and str(effect.AttributeToModify._path_name()) == "D_Attributes.Weapon.WeaponDamage":
            for field in ("BaseModifierValue", "PerGradeUpgrade"):
                value = copy.copy(getattr(effect, field))
                value.BaseValueConstant = BLOODY_REVIVAL_DAMAGE_PER_RANK
                value.BaseValueAttribute = None
                value.InitializationDefinition = None
                value.BaseValueScaleConstant = 1.0
                setattr(effect, field, value)
            effect.AttributeToModify = weapon_damage
            effect.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
            effect.GradeToStartApplyingEffect = 1
            effect.PerGradeUpgradeInterval = 1
            effect.BonusUpgradeList = []
            changed = True
    if changed:
        definition.SkillEffectDefinitions = list(definition.SkillEffectDefinitions)
    _set_property(definition, "SkillDescription", BLOODY_REVIVAL_DESCRIPTION)
    _set_property(presentation, "Description", "Fight For Your Life Gun Damage: +$NUMBER$%")
    return True


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_bloody_revival(_tree: Any, args: Any, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    if args.SkillDef is None or str(args.SkillDef._path_name()) != BLOODY_REVIVAL_PATH:
        return None
    rank = _skill_footer_rank(args)
    ffyl_damage = _format_skill_footer_rank_value(
        args, f"+{100 * BLOODY_REVIVAL_DAMAGE_PER_RANK * rank:g}%", _tree)
    wind_damage = _format_skill_footer_rank_value(
        args, f"+{100 * BLOODY_REVIVAL_DAMAGE_PER_SECOND_WIND * rank:g}%", _tree)
    wind_reduction = _format_skill_footer_rank_value(
        args, f"+{100 * BLOODY_REVIVAL_REDUCTION_PER_SECOND_WIND * rank:g}%", _tree)
    sep = "<br>" if args.bIncludeHTML else "\n"
    text = sep.join((
        f"Fight For Your Life Gun Damage: {ffyl_damage}",
        f"Gun Damage: {wind_damage}",
        f"Damage Reduction: {wind_reduction}",
    ))
    return Block, text


def _sync_bloody_revival_hud(controller: Any) -> None:
    global _pain_hud_context, _pain_hud_departing_context
    current = get_pc(possibly_loading=True)
    if (current is None or current._get_address() != controller._get_address()
            or controller.bDeleteMe):
        return
    world = controller.WorldInfo
    if world is None or world.bDeleteMe:
        return
    owner = controller._get_address()
    address = (owner, world._get_address())
    if _pain_hud_departing_context in (address, (owner, 0)):
        return
    pawn, tree = controller.GetWillowPlayerPawn(), controller.PlayerSkillTree
    if (pawn is None or pawn.bDeleteMe or pawn.Controller != controller or tree is None
            or not tree.bInitialized or world.Pauser or controller.IsPauseMenuOpen()):
        return
    # The existing PRE travel/destroy hooks protect both custom HUD counters.
    _pain_hud_context = address
    _pain_hud_departing_context = None
    definition = _find("SkillDefinition", BLOODY_REVIVAL_PATH)
    if definition is None:
        return
    state = _bloody_revival_state.get(owner)
    count = 0
    if (state is not None and int(controller.GetSkillGrade(definition)) > 0
            and not pawn.IsInjuredDead() and state.get("damage_applied")
            and state.get("reduction_applied")):
        count = max(0, min(BLOODY_REVIVAL_MAX_SECOND_WINDS, int(state["second_winds"])))
    feedback = _find("SkillDefinition", BLOODY_REVIVAL_HUD_PATH)
    if count <= 0 and feedback is None:
        return
    movie = controller.GetHUDMovie()
    if movie is None or movie.WPCOwner != controller:
        return
    hud = movie.MyHUDOwner
    if hud is None or hud.bDeleteMe or hud.WorldInfo != world:
        return
    manager = controller.GetSkillManager()
    if manager is None:
        return
    gameplay = _find("SkillDefinition", BLOODY_REVIVAL_BONUS_PATH)
    if count > 0 and not any(s.Definition == gameplay and s.SkillInstigator == controller
                             and int(s.Grade) > 0 for s in manager.ActiveSkills):
        count = 0  # Never advertise a recorded stack whose native bonus is absent.
    if count <= 0:
        if any(s.Definition == feedback and s.SkillInstigator == controller for s in manager.ActiveSkills):
            manager.DeactivateSkill(controller, feedback)
            movie.UpdateSkillIcons()
        return
    if feedback is None or BLOODY_REVIVAL_HUD_PATH not in _prepared_runtime_leaves:
        feedback = _stack_hud_feedback(
            definition, BLOODY_REVIVAL_HUD_PATH, "KriegRebalance_BloodyRevivalHUD",
            "Bloody Revival", BLOODY_REVIVAL_MAX_SECOND_WINDS)
    if feedback is None or not _prepare_stack_hud_slot(controller, movie, feedback, "Bloody Revival"):
        return
    _show_stack_hud_count(controller, movie, manager, feedback, count, "Bloody Revival")


def _maintain_bloody_revival_hud(controller: Any, now: float) -> None:
    if controller is None:
        return
    try:
        address = controller._get_address()
        if now < _next_bloody_revival_hud_sync.get(address, 0.0):
            return
        if len(_next_bloody_revival_hud_sync) >= 16 and address not in _next_bloody_revival_hud_sync:
            _next_bloody_revival_hud_sync.clear()
        _next_bloody_revival_hud_sync[address] = now + 0.25
        _sync_bloody_revival_hud(controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Bloody Revival HUD"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not update {key}: {exc}")


def _bloody_revival_is_in_ffyl(pawn: Any) -> bool:
    try:
        return bool(pawn.IsInjured()) and not bool(pawn.IsInjuredDead())
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return False


def _bloody_revival_is_dead(pawn: Any) -> bool:
    try:
        return bool(pawn.IsInjuredDead())
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return False


def _bloody_revival_bonus_definition() -> Any | None:
    """Apply the existing coefficients through native skill effects, not a fake pawn API."""
    definition = _find("SkillDefinition", BLOODY_REVIVAL_PATH)
    weapon_damage = _find("AttributeDefinition", "D_Attributes.Weapon.WeaponDamage")
    numbed = _find("SkillDefinition", NUMBED_NERVES_PATH)
    initializer = _find("AttributeInitializationDefinition", NUMBED_INITIALIZER_PATH)
    if definition is None or weapon_damage is None or numbed is None or initializer is None:
        return None
    resistance = [effect for effect in numbed.SkillEffectDefinitions
                  if effect.AttributeToModify is not None
                  and effect.BaseModifierValue.InitializationDefinition == initializer]
    if len(resistance) != 9:
        raise ValueError("Bloody Revival requires the nine native damage-resistance channels")
    helper = _find("SkillDefinition", BLOODY_REVIVAL_BONUS_PATH)
    if helper is None:
        _prepared_runtime_leaves.discard(BLOODY_REVIVAL_BONUS_PATH)
        helper = unrealsdk.construct_object("SkillDefinition", definition, "KriegRebalance_RevivalBonuses")
    pairs = [(weapon_damage, BLOODY_REVIVAL_DAMAGE_PER_SECOND_WIND)] + [
        (effect.AttributeToModify, -BLOODY_REVIVAL_REDUCTION_PER_SECOND_WIND) for effect in resistance]
    effects = list(helper.SkillEffectDefinitions)
    if len(effects) != len(pairs) or not all(_pain_effect_matches(e, attr, coef)
                                            for e, (attr, coef) in zip(effects, pairs)):
        effects = []
        for attribute, coefficient in pairs:
            effect = unrealsdk.make_struct(
                "WillowGame.SkillDefinition:SkillEffectData", AttributeToModify=attribute,
                bIncludeDuelingTargets=False, bIncludeSelfAsTarget=False,
                bOnlyEffectTargetsInRange=False, bExcludeNonPlayerCharacters=False,
                EffectTarget=unrealsdk.find_enum("EEffectTarget").TARGET_Self,
                TargetInstanceDataName="None", TargetCriteria=unrealsdk.find_enum("ETargetCriteria").CRITERIA_None,
                ModifierType=unrealsdk.find_enum("EModifierType").MT_Scale,
                GradeToStartApplyingEffect=1, PerGradeUpgradeInterval=1, BonusUpgradeList=[])
            for field in ("BaseModifierValue", "PerGradeUpgrade"):
                value = copy.copy(getattr(effect, field))
                value.BaseValueConstant = coefficient
                value.BaseValueAttribute = value.InitializationDefinition = None
                value.BaseValueScaleConstant = 1.0
                setattr(effect, field, value)
            effects.append(effect)
        helper.SkillEffectDefinitions = effects
    _set_property(helper, "SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive)
    _set_property(helper, "DurationType", unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite)
    _set_property(helper, "TrackedSkillType", unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked)
    _set_property(helper, "bSubjectToGradeRules", False)
    _set_property(helper, "MaxGrade", BLOODY_REVIVAL_MAX_SECOND_WINDS * EFFECTIVE_SKILL_RANK_LIMIT)
    _set_property(helper, "BehaviorProviderDefinition", None)
    _set_property(helper, "TrackedActiveSkill", None)
    for field in ("SkillEffectPresentations", "SkillConstraints", "DamageEvents", "KillEvents", "TrackedActiveSkills"):
        if getattr(helper, field, ()):
            setattr(helper, field, [])
    effects = list(helper.SkillEffectDefinitions)
    if len(effects) != len(pairs) or not all(_pain_effect_matches(e, attr, coef)
                                            for e, (attr, coef) in zip(effects, pairs)):
        raise RuntimeError("Bloody Revival did not retain its native bonus effects")
    _prepared_runtime_leaves.add(BLOODY_REVIVAL_BONUS_PATH)
    return helper


def _apply_bloody_revival_bonus(controller: Any, rank: int) -> None:
    state = _bloody_revival_state.get(controller._get_address())
    if state is None:
        return
    manager = controller.GetSkillManager()
    if manager is None:
        state["damage_applied"] = state["reduction_applied"] = False
        return
    helper = _find("SkillDefinition", BLOODY_REVIVAL_BONUS_PATH)
    combined = min(BLOODY_REVIVAL_MAX_SECOND_WINDS, max(0, int(state["second_winds"]))) * rank
    instances = [s for s in manager.ActiveSkills if s.Definition == helper and s.SkillInstigator == controller]
    if (BLOODY_REVIVAL_BONUS_PATH in _prepared_runtime_leaves and combined > 0
            and len(instances) == 1 and int(instances[0].Grade) == combined):
        state["damage_applied"] = state["reduction_applied"] = True
        return
    state["damage_applied"] = state["reduction_applied"] = False
    if instances:
        manager.DeactivateSkill(controller, helper)
    if combined <= 0:
        return
    if helper is None or BLOODY_REVIVAL_BONUS_PATH not in _prepared_runtime_leaves:
        helper = _bloody_revival_bonus_definition()
        if helper is None:
            return
    if manager.ActivateSkill(controller, helper, None, combined) is False:
        raise RuntimeError("Bloody Revival Second Wind bonuses were rejected")
    instances = [s for s in manager.ActiveSkills if s.Definition == helper and s.SkillInstigator == controller]
    if len(instances) != 1 or int(instances[0].Grade) != combined:
        raise RuntimeError("Bloody Revival Second Wind bonuses failed native readback")
    state["damage_applied"] = state["reduction_applied"] = True


def _clear_bloody_revival_bonus(controller: Any) -> None:
    helper = _find("SkillDefinition", BLOODY_REVIVAL_BONUS_PATH)
    manager = controller.GetSkillManager()
    if helper is not None and manager is not None and any(
            s.Definition == helper and s.SkillInstigator == controller for s in manager.ActiveSkills):
        manager.DeactivateSkill(controller, helper)
    _bloody_revival_state.pop(controller._get_address(), None)
    _bloody_revival_ffyl_watch.pop(controller._get_address(), None)


def _bloody_revival_recovery_owner(pawn: Any) -> tuple[Any, Any] | None:
    controller = pawn.Controller
    if controller is None or controller.bDeleteMe or get_pc(possibly_loading=True) != controller:
        return None
    world = controller.WorldInfo
    if (world is None or world.bDeleteMe or _world_is_departing(controller, world)
            or controller.GetWillowPlayerPawn() != pawn or pawn.bDeleteMe):
        return None
    return controller, world


@hook("WillowGame.WillowPlayerPawn:SetupPlayerInjuredState", Type.POST)
def observe_bloody_revival_ffyl(pawn: Any, _args: Any, _ret: Any, _func: Any) -> None:
    """Arm a short recovery watch only when the local Krieg enters FFYL."""
    try:
        owner = _bloody_revival_recovery_owner(pawn)
        if owner is None:
            return
        controller, world = owner
        definition = _find("SkillDefinition", BLOODY_REVIVAL_PATH)
        if definition is None or int(controller.GetSkillGrade(definition)) <= 0:
            return
        _bloody_revival_ffyl_watch[controller._get_address()] = {
            "pawn": pawn._get_address(), "world": world._get_address(),
            "reason": int(pawn.SecondWindReason),
        }
        unrealsdk.logging.info("[KriegRebalance] Bloody Revival FFYL entry observed")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _bloody_revival_error(exc)


@hook("WillowGame.WillowPlayerPawn:SetSecondWindReason", Type.PRE)
def observe_bloody_revival_reason(pawn: Any, args: Any, _ret: Any, _func: Any) -> None:
    """Cache the native reason before recovery can clear its transient field."""
    try:
        owner = _bloody_revival_recovery_owner(pawn)
        if owner is None:
            return
        watch = _bloody_revival_ffyl_watch.get(owner[0]._get_address())
        if watch is not None and watch["pawn"] == pawn._get_address():
            watch["reason"] = int(args.Reason)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _bloody_revival_error(exc)


def _award_bloody_revival_second_wind(controller: Any, invested: int) -> None:
    address = controller._get_address()
    state = _bloody_revival_state.setdefault(address, {
        "second_winds": 0, "damage_applied": False, "reduction_applied": False,
        "recovery_pending": False,
    })
    rank = _effective_skill_rank(controller, BLOODY_REVIVAL_PATH, invested)
    state["second_winds"] = min(BLOODY_REVIVAL_MAX_SECOND_WINDS, state["second_winds"] + 1)
    _apply_bloody_revival_bonus(controller, rank)
    unrealsdk.logging.info(
        f"[KriegRebalance] Bloody Revival Second Wind #{state['second_winds']}: "
        f"+{BLOODY_REVIVAL_DAMAGE_PER_SECOND_WIND * rank * state['second_winds']:.0%} gun damage, "
        f"+{BLOODY_REVIVAL_REDUCTION_PER_SECOND_WIND * rank * state['second_winds']:.0%} damage reduction"
    )


def _check_bloody_revival_ffyl_recovery(controller: Any, world: Any) -> None:
    """One cheap transition check per tick while FFYL is armed; no idle polling."""
    address = controller._get_address()
    watch = _bloody_revival_ffyl_watch.get(address)
    if watch is None:
        return
    pawn = controller.GetWillowPlayerPawn()
    if (pawn is None or pawn.bDeleteMe or pawn._get_address() != watch["pawn"]
            or world._get_address() != watch["world"]):
        _bloody_revival_ffyl_watch.pop(address, None)
        return
    if _bloody_revival_is_dead(pawn):
        _bloody_revival_ffyl_watch.pop(address, None)
        _clear_bloody_revival_bonus(controller)
        return
    if _bloody_revival_is_in_ffyl(pawn):
        native_reason = int(pawn.SecondWindReason)
        if native_reason:
            watch["reason"] = native_reason
        return
    _bloody_revival_ffyl_watch.pop(address, None)
    reason = watch["reason"] or int(pawn.SecondWindReason)
    if reason == 3:  # PartnerRevived is not a Second Wind.
        return
    definition = _find("SkillDefinition", BLOODY_REVIVAL_PATH)
    if definition is None:
        return
    invested = int(controller.GetSkillGrade(definition))
    if invested <= 0:
        return
    if reason == 0:
        unrealsdk.logging.info(
            "[KriegRebalance] Bloody Revival FFYL ended with no native reason; "
            "counting the confirmed local recovery"
        )
    _award_bloody_revival_second_wind(controller, invested)


@hook("WillowGame.WillowPlayerPawn:GoFromInjuredToHealthy", Type.PRE)
def begin_bloody_revival_recovery(pawn: Any, _args: Any, _ret: Any, _func: Any) -> None:
    frame = None
    try:
        owner = _bloody_revival_recovery_owner(pawn)
        if owner is not None and _bloody_revival_is_in_ffyl(pawn):
            controller, world = owner
            definition = _find("SkillDefinition", BLOODY_REVIVAL_PATH)
            if definition is not None and int(controller.GetSkillGrade(definition)) > 0:
                # Native ESecondWindReason: kill, level-up, Res, or auto-revive.
                # PartnerRevived and None do not earn a Second Wind stack.
                reason = int(pawn.SecondWindReason)
                if reason == 0 and "Bloody Revival unknown recovery reason" not in _reported_errors:
                    _reported_errors.add("Bloody Revival unknown recovery reason")
                    unrealsdk.logging.info("[KriegRebalance] Bloody Revival recovery had no Second Wind reason; no stack awarded")
                if reason in (1, 2, 4, 5):
                    address = controller._get_address()
                    state = _bloody_revival_state.setdefault(address, {
                        "second_winds": 0, "damage_applied": False, "reduction_applied": False,
                        "recovery_pending": False,
                    })
                    if not state["recovery_pending"]:
                        state["recovery_pending"] = True
                        frame = (pawn._get_address(), address, world._get_address())
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _bloody_revival_error(exc)
    _bloody_revival_recovery_frames.append(frame)  # Pair blocked and nested calls.


@hook("WillowGame.WillowPlayerPawn:GoFromInjuredToHealthy", Type.POST_UNCONDITIONAL)
def finish_bloody_revival_recovery(pawn: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if not _bloody_revival_recovery_frames:
        return
    frame = _bloody_revival_recovery_frames.pop()
    if frame is None:
        return
    pawn_address, address, world_address = frame
    state = _bloody_revival_state.get(address)
    if state is not None:
        state["recovery_pending"] = False
    try:
        owner = _bloody_revival_recovery_owner(pawn)
        if (owner is None or pawn._get_address() != pawn_address
                or owner[0]._get_address() != address or owner[1]._get_address() != world_address
                or pawn.IsInjured() or _bloody_revival_is_dead(pawn)):
            return
        controller = owner[0]
        definition = _find("SkillDefinition", BLOODY_REVIVAL_PATH)
        if definition is None or state is None:
            return
        invested = int(controller.GetSkillGrade(definition))
        if invested <= 0:
            return
        _bloody_revival_ffyl_watch.pop(address, None)
        _award_bloody_revival_second_wind(controller, invested)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _bloody_revival_error(exc)


def _bloody_revival_error(exc: Exception) -> None:
    key = "Bloody Revival Second Wind"
    if key not in _reported_errors:
        _reported_errors.add(key)
        unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


def _sync_bloody_revival_second_wind(controller: Any, now: float) -> None:
    """Maintain native bonuses after COM, death or respec; recovery is event driven."""
    if controller is None or controller.bDeleteMe:
        return
    world = controller.WorldInfo
    if (get_pc(possibly_loading=True) != controller or world is None or world.bDeleteMe
            or _world_is_departing(controller, world) or world.Pauser or controller.IsPauseMenuOpen()):
        return
    address = controller._get_address()
    try:
        _check_bloody_revival_ffyl_recovery(controller, world)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _bloody_revival_error(exc)
    if now < _next_bloody_revival_sync.get(address, 0.0):
        return
    if len(_next_bloody_revival_sync) >= 16 and address not in _next_bloody_revival_sync:
        _next_bloody_revival_sync.clear()
    _next_bloody_revival_sync[address] = now + MAINTENANCE_INTERVAL
    try:
        state = _bloody_revival_state.get(address)
        if state is None:
            return
        pawn = controller.GetWillowPlayerPawn()
        if pawn is None or pawn.bDeleteMe:
            return
        definition = _find("SkillDefinition", BLOODY_REVIVAL_PATH)
        if definition is None:
            return
        invested = int(controller.GetSkillGrade(definition))
        if invested <= 0 or _bloody_revival_is_dead(pawn):
            _clear_bloody_revival_bonus(controller)
            return
        if state["second_winds"] > 0:
            rank = _effective_skill_rank(controller, BLOODY_REVIVAL_PATH, invested)
            _apply_bloody_revival_bonus(controller, rank)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _bloody_revival_error(exc)


def _flame_resistance_matches(effect: Any, attribute: Any, template: Any) -> bool:
    return (
        effect.AttributeToModify == attribute
        and effect.ModifierType == unrealsdk.find_enum("EModifierType").MT_Scale
        and effect.EffectTarget == template.EffectTarget
        and effect.TargetCriteria == template.TargetCriteria
        and effect.TargetInstanceDataName == template.TargetInstanceDataName
        and not any((effect.bIncludeDuelingTargets, effect.bIncludeSelfAsTarget,
                     effect.bOnlyEffectTargetsInRange, effect.bExcludeNonPlayerCharacters))
        and effect.GradeToStartApplyingEffect == 1 and effect.PerGradeUpgradeInterval == 1
        and not effect.BonusUpgradeList
        and all(abs(float(value.BaseValueConstant) - FLAME_RESISTANCE_PER_RANK) <= 0.000001
                and value.BaseValueAttribute is None and value.InitializationDefinition is None
                and abs(float(value.BaseValueScaleConstant) - 1.0) <= 0.000001
                for value in (effect.BaseModifierValue, effect.PerGradeUpgrade))
    )


def _configure_flame_flare() -> bool:
    definition = _find("SkillDefinition", FLAME_FLARE_PATH)
    attribute = _find("AttributeDefinition", FLAME_RESISTANCE_ATTRIBUTE)
    duration_attribute = _find("AttributeDefinition", FLAME_DURATION_ATTRIBUTE)
    presentation = _find("AttributePresentationDefinition", f"{FLAME_FLARE_PATH}:AttributePresentationDefinition_1")
    if definition is None or attribute is None or duration_attribute is None or presentation is None:
        return False
    effects = list(definition.SkillEffectDefinitions)
    template = next((effect for effect in effects if effect.AttributeToModify == duration_attribute), None)
    if template is None:
        raise ValueError("Flame Flare native burn-duration effect was not found")
    resistance = [effect for effect in effects if effect.AttributeToModify == attribute]
    if len(resistance) != 1 or not _flame_resistance_matches(resistance[0], attribute, template):
        # The native duration effect already targets self with CRITERIA_None.
        # Preserve that target and the two original effects; add only resistance.
        effect = copy.copy(template)
        effect.AttributeToModify = attribute
        effect.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
        effect.bIncludeDuelingTargets = effect.bIncludeSelfAsTarget = False
        effect.bOnlyEffectTargetsInRange = effect.bExcludeNonPlayerCharacters = False
        effect.GradeToStartApplyingEffect = effect.PerGradeUpgradeInterval = 1
        effect.BonusUpgradeList = []
        for field in ("BaseModifierValue", "PerGradeUpgrade"):
            value = copy.copy(getattr(effect, field))
            value.BaseValueConstant = FLAME_RESISTANCE_PER_RANK
            value.BaseValueAttribute = value.InitializationDefinition = None
            value.BaseValueScaleConstant = 1.0
            setattr(effect, field, value)
        definition.SkillEffectDefinitions = [entry for entry in effects if entry.AttributeToModify != attribute] + [effect]
    retained = [effect for effect in definition.SkillEffectDefinitions if effect.AttributeToModify == attribute]
    if len(retained) != 1 or not _flame_resistance_matches(retained[0], attribute, template):
        raise RuntimeError("Flame Flare did not retain its single resistance effect")
    _set_property(definition, "SkillDescription", FLAME_FLARE_DESCRIPTION)
    _set_property(presentation, "Description", FLAME_FLARE_STAT)
    return True


def _sync_flame_flare(controller: Any) -> None:
    """Migrate learned passive caches without restarting the skill or its burn timers."""
    definition = _find("SkillDefinition", FLAME_FLARE_PATH)
    attribute = _find("AttributeDefinition", FLAME_RESISTANCE_ATTRIBUTE)
    if definition is None or attribute is None:
        return
    resistance = next((effect for effect in definition.SkillEffectDefinitions
                       if effect.AttributeToModify == attribute), None)
    if resistance is None:
        return  # Static tuning must finish first.
    manager = controller.GetSkillManager()
    if manager is None:
        return
    active = unrealsdk.find_enum("ESkillState").SKILL_Active
    for skill in list(manager.ActiveSkills):
        if (skill.Definition != definition or skill.SkillInstigator != controller
                or int(skill.Grade) <= 0 or skill.SkillState != active):
            continue
        effects = [copy.copy(applied) for applied in skill.SkillEffects]
        matches = [applied for applied in effects if applied.EffectData.AttributeToModify == attribute]
        if len(matches) > 1:
            raise ValueError("Flame Flare has duplicate live resistance modifiers; restart before testing")
        changed = False
        for applied in matches:
            modifier = applied.Modifier
            if (not _flame_resistance_matches(applied.EffectData, attribute, resistance)
                    or modifier is not None and abs(float(modifier.Value)
                                                   - FLAME_RESISTANCE_PER_RANK * int(skill.Grade)) > 0.000001):
                applied.EffectData = copy.copy(resistance)
                changed = True
        if changed:
            skill.SkillEffects = effects  # Keep existing Modifier and Contexts.
        if not matches:
            skill.AddSkillEffect(controller, copy.copy(resistance))
            if not any(applied.EffectData.AttributeToModify == attribute for applied in skill.SkillEffects):
                raise RuntimeError("Flame Flare live cache did not retain the resistance effect")
            changed = True
        if changed:
            skill.bForceRefreshModifiersNextTick = True


def _maintain_live_flame_flare(controller: Any, now: float) -> None:
    if controller is None:
        return
    try:
        address = controller._get_address()
        if now < _next_live_sync.get(address, 0.0):
            return
        if len(_next_live_sync) >= 16 and address not in _next_live_sync:
            _next_live_sync.clear()  # Bound integer keys, never retain old controllers.
        _next_live_sync[address] = now + MAINTENANCE_INTERVAL
        _sync_flame_flare(controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Flame Flare live cache"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


def _configure_overdrive_position() -> bool:
    branch = _find("Object", BLOODLUST_BRANCH_PATH)
    layout = _find("Object", BLOODLUST_LAYOUT_PATH)
    if branch is None or layout is None:
        return False
    if len(branch.Tiers) != 6 or len(layout.Tiers) != 6:
        raise ValueError("Unexpected Bloodlust tree for Blood Overdrive swap")
    rows = [tuple(str(skill._path_name()) for skill in tier.Skills) for tier in branch.Tiers]
    prefix = "GD_Lilac_Skills_Bloodlust.Skills."
    native = ((prefix + "TasteOfBlood", prefix + "BloodyRevival", BLOOD_OVERDRIVE_PATH),
              (NERVOUS_BLOOD_PATH,))
    swapped = ((native[0][0], native[0][1], NERVOUS_BLOOD_PATH), (BLOOD_OVERDRIVE_PATH,))
    if ((rows[1], rows[4]) not in (native, swapped)
            or any(path in row for i, row in enumerate(rows) if i not in (1, 4)
                   for path in (BLOOD_OVERDRIVE_PATH, NERVOUS_BLOOD_PATH))
            or tuple(bool(cell) for cell in layout.Tiers[1].bCellIsOccupied) != (True, True, True)
            or tuple(bool(cell) for cell in layout.Tiers[4].bCellIsOccupied) != (False, True, False)):
        raise ValueError("Unexpected Blood Overdrive / Nervous Blood positions")
    if (rows[1], rows[4]) == swapped:
        return True
    # Own all rows before replacing Tiers: unchanged WrappedStruct views would
    # otherwise reference the array being freed by the native setter.
    tiers = [copy.copy(tier) for tier in branch.Tiers]
    lower, upper = list(tiers[1].Skills), list(tiers[4].Skills)
    lower[2], upper[0] = upper[0], lower[2]
    tiers[1].Skills, tiers[4].Skills = lower, upper
    branch.Tiers = tiers
    actual = (tuple(str(s._path_name()) for s in branch.Tiers[1].Skills),
              tuple(str(s._path_name()) for s in branch.Tiers[4].Skills))
    if actual != swapped:
        raise RuntimeError("Blood Overdrive / Nervous Blood swap did not retain its positions")
    return True


def _configure_blood_euphoria() -> bool:
    definition = _find("SkillDefinition", BLOOD_EUPHORIA_PATH)
    resolver = _find("ConstantAttributeValueResolver", BLOOD_EUPHORIA_RESOLVER_PATH)
    # Object is the common native base class: no guessed layout/branch class names.
    layout = _find("Object", BLOODLUST_LAYOUT_PATH)
    branch = _find("Object", BLOODLUST_BRANCH_PATH)
    if definition is None or resolver is None or layout is None or branch is None:
        return False
    layout_tiers = [copy.copy(tier) for tier in layout.Tiers]
    branch_tiers = [copy.copy(tier) for tier in branch.Tiers]
    if len(layout_tiers) != 6 or len(branch_tiers) != 6:
        raise ValueError("Bloodlust tree differs from the expected six-tier layout")
    rows = [tuple(str(skill._path_name()) for skill in tier.Skills) for tier in branch_tiers]
    original = BLOOD_EUPHORIA_NEIGHBORS
    expected = (original[0], BLOOD_EUPHORIA_PATH, original[1])
    if rows[3] not in (original, expected):
        raise ValueError("Bloodlust tier 4 is occupied by an unexpected skill arrangement")
    if any(BLOOD_EUPHORIA_PATH in row for index, row in enumerate(rows) if index != 3):
        raise ValueError("Blood Euphoria is already placed in another tier")
    cells = tuple(bool(cell) for cell in layout_tiers[3].bCellIsOccupied)
    if cells not in ((True, False, True), (True, True, True)):
        raise ValueError("Bloodlust tier 4 has an unexpected visual layout")
    # Validate the whole destination before writing. Other tiers are never rebuilt.
    _set_property(definition, "MaxGrade", 1)
    # Disconnect the old kill-skill-end graph, and neutralize its heal coefficient
    # as well: an already-instantiated provider may still exist until restart.
    _set_property(resolver, "ConstantValue", 0.0)
    _set_property(definition, "BehaviorProviderDefinition", None)
    _set_property(definition, "SkillDescription", BLOOD_EUPHORIA_DESCRIPTION)
    # Native presentations describe the disabled burst. The lower regeneration
    # stat is rendered by describe_blood_euphoria, independently of that graph.
    if definition.SkillEffectPresentations:
        definition.SkillEffectPresentations = []
    if definition.SkillEffectPresentations:
        raise RuntimeError("Blood Euphoria retained its old burst-heal presentation")
    if rows[3] != expected or branch_tiers[3].PointsToUnlockNextTier != 5:
        tier = copy.copy(branch_tiers[3])
        skills = list(tier.Skills)
        if rows[3] == original:
            skills.insert(1, definition)
        tier.Skills = skills
        tier.PointsToUnlockNextTier = 5
        branch_tiers[3] = tier
        branch.Tiers = branch_tiers
    if cells != (True, True, True):
        tier = copy.copy(layout_tiers[3])
        tier.bCellIsOccupied = [True, True, True]
        layout_tiers[3] = tier
        layout.Tiers = layout_tiers
    if (tuple(str(skill._path_name()) for skill in branch.Tiers[3].Skills) != expected
            or branch.Tiers[3].PointsToUnlockNextTier != 5
            or tuple(bool(cell) for cell in layout.Tiers[3].bCellIsOccupied) != (True, True, True)):
        raise RuntimeError("Blood Euphoria branch/layout did not retain the configured placement")
    # Icon, neighbors, other tiers and all other skills remain untouched.
    return True


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_blood_euphoria(_tree: Any, args: Any, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    """This native query returns LOWER stat text only, not SkillDescription."""
    definition = args.SkillDef
    if definition is None or str(definition._path_name()) != BLOOD_EUPHORIA_PATH:
        return None
    number = f"{BLOOD_EUPHORIA_REGEN_PER_STACK * 100:g}"
    if args.bIncludeHTML and int(args.Grade) > 0:
        number = f'<font color="#00FF00">{number}</font>'
    return Block, f"Health Regeneration per Stack: {number}%"


def _regenerate_blood_euphoria(controller: Any, delta: float) -> None:
    """Current stacks x maximum HP x simulation time; no saved actor/timer state."""
    if controller is None or controller.bDeleteMe:
        return
    world = controller.WorldInfo
    if (world is None or world.bDeleteMe or world.Pauser or _world_is_departing(controller, world)
            or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
        return
    elapsed = float(delta)
    if not math.isfinite(elapsed) or elapsed <= 0.0:
        return
    pawn = controller.GetWillowPlayerPawn()
    if (pawn is None or pawn.bDeleteMe or pawn.Controller != controller
            or pawn.IsInjured() or pawn.IsInjuredDead()):
        return  # Never revive, extend FFYL, or heal a vehicle/another player.
    health, maximum = float(pawn.GetHealth()), float(pawn.GetMaxHealth())
    if not all(math.isfinite(v) for v in (health, maximum)) or not 0.0 < health < maximum:
        return
    definition = _find("SkillDefinition", BLOOD_EUPHORIA_PATH)
    if definition is None or int(controller.GetSkillGrade(definition)) <= 0:
        return
    # Fail closed until the old effect has been disabled (also after streaming).
    resolver = _find("ConstantAttributeValueResolver", BLOOD_EUPHORIA_RESOLVER_PATH)
    if (resolver is None or float(resolver.ConstantValue) != 0.0
            or definition.BehaviorProviderDefinition is not None):
        return
    attribute = _find("DesignerAttributeDefinition", BLOODLUST_STACK_ATTRIBUTE)
    if attribute is None:
        return
    instance = attribute.ResolveContext(controller)
    if instance is None:
        return  # Designer context not instantiated yet; do not create or alter stacks.
    stacks = float(instance.Value)
    if not math.isfinite(stacks) or stacks <= 0.0:
        return
    amount = maximum * BLOOD_EUPHORIA_REGEN_PER_STACK * stacks * elapsed
    pawn.SetHealth(min(maximum, health + amount))
    key = "Blood Euphoria regeneration"
    if key not in _verified_fixes:
        _verified_fixes.add(key)
        unrealsdk.logging.info(
            f"[KriegRebalance] Blood Euphoria regeneration applied: stacks={stacks:g}, "
            f"max_health={maximum:g}, health_per_second={maximum * BLOOD_EUPHORIA_REGEN_PER_STACK * stacks:g}"
        )


@hook("WillowGame.PlayerSkillTree:Initialize", Type.PRE)
def prepare_blood_euphoria_tree(_tree: Any, _args: Any, _ret: Any, _func: Any) -> None:
    """Patch definitions BEFORE native code snapshots its Branches/Tiers/Skills."""
    _reset_static_configuration()
    for key, configure in (("Native stack HUD layout before tree initialization", _configure_stack_hud),
                           ("Blood Overdrive / Nervous Blood positions before tree initialization", _configure_overdrive_position),
                           ("Blood Euphoria before tree initialization", _configure_blood_euphoria),
                           ("Hellfire Halitosis before skill initialization", _configure_hellfire_halitosis)):
        try:
            if configure() and key not in _verified_fixes:
                _verified_fixes.add(key)
                unrealsdk.logging.info(f"[KriegRebalance] {key}")
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            if key not in _reported_errors:
                _reported_errors.add(key)
                unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


def _check_live_blood_euphoria_tree(controller: Any) -> None:
    """Diagnose late enable; never rebuild a learned tree or rewrite save grades."""
    if controller is None or controller.bDeleteMe:
        return
    tree = controller.PlayerSkillTree
    definition = _find("SkillDefinition", BLOOD_EUPHORIA_PATH)
    if tree is None or not tree.bInitialized or definition is None:
        return
    skills = list(tree.Skills)
    # Check this is Bloodlust, not another character whose assets are also loaded.
    if not any(item.Definition and str(item.Definition._path_name()) == BLOOD_EUPHORIA_NEIGHBORS[1]
               for item in skills):
        return
    if any(item.Definition == definition for item in skills):
        key = "Blood Euphoria live tree verified"
        if key not in _verified_fixes:
            _verified_fixes.add(key)
            unrealsdk.logging.info(f"[KriegRebalance] {key}: present=True")
    else:
        key = "Blood Euphoria enabled after tree initialization"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.info(
                f"[KriegRebalance] {key}: definitions updated, but live tree lacks the skill. "
                "Return to the main menu and reload Krieg with this mod already enabled. "
                "No respec is required; existing skill points were not modified."
            )


def _special_melee_formula_matches(formula: Any, game_stage: Any) -> bool:
    if not formula.bEnabled:
        return False
    for name, constant, scale in SPECIAL_MELEE_FORMULA_TERMS:
        value = getattr(formula, name)
        attribute = game_stage if name == "Level" else None
        if (abs(float(value.BaseValueConstant) - constant) > 0.000001
                or value.BaseValueAttribute != attribute or value.InitializationDefinition is not None
                or abs(float(value.BaseValueScaleConstant) - scale) > 0.000001):
            return False
    return True


def _configure_special_melee_scaling() -> bool:
    initializer = _find("AttributeInitializationDefinition", SPECIAL_MELEE_INITIALIZER_PATH)
    game_stage = _find("AttributeDefinition", SPECIAL_MELEE_GAME_STAGE_PATH)
    if initializer is None or game_stage is None:
        return False
    if not _special_melee_formula_matches(initializer.ValueFormula, game_stage):
        formula = copy.copy(initializer.ValueFormula)
        formula.bEnabled = True
        for name, constant, scale in SPECIAL_MELEE_FORMULA_TERMS:
            value = copy.copy(getattr(formula, name))
            value.BaseValueConstant = constant
            value.BaseValueAttribute = game_stage if name == "Level" else None
            value.InitializationDefinition = None
            value.BaseValueScaleConstant = scale
            setattr(formula, name, value)
        initializer.ValueFormula = formula
    if not _special_melee_formula_matches(initializer.ValueFormula, game_stage):
        raise RuntimeError("Krieg special melee did not retain its GameStage formula")
    # Native formula 1 + 0.02 * GameStage: no level-72/OP8 clamp or fixed damage.
    # At level 80 / OP10, expected GameStage 90 gives 2.8 for this factor only.
    return True


def _reset_static_configuration() -> None:
    """Invalidate primitive completion state on load/menu/tree initialization."""
    global _configuration_world
    _configured_skill_steps.clear()
    _configuration_world = None


def _apply_skill_configuration() -> None:
    # No UObject is retained between calls or across map/menu teardown.
    for name, configure in (("Salt the Wound / Elemental Elation separate HUD counters", _configure_stack_hud),
                            ("Salt the Wound decay interval 1.5 seconds per stack", _configure_salt_decay),
                            ("Silence the Voices grenade description", _configure_silence_description),
                            ("Silence the Voices visual clutter", _configure_silence_visuals),
                            ("Blood Overdrive own skill grade", _configure_blood_overdrive),
                            ("Blood Bath gun damage 0.3% per rank per Bloodlust stack", _configure_blood_bath),
                            ("Blood-Filled Guns magazine 0.25% and gun damage 0.4% per rank per stack", _configure_blood_filled_guns),
                            ("Blood Twitch Bloodlust melee 0.15% and reserve ammo regeneration 0.005% per rank", _configure_blood_twitch),
                            ("Blood Overdrive / Nervous Blood positions", _configure_overdrive_position),
                            (f"Blood Overdrive extra Bloodlust stacks; movement 5% and fire rate 4% per rank at {OVERCHARGE_THRESHOLD}+", _configure_overcharge),
                            ("Bloody Revival all gun types in FFYL", _configure_bloody_revival),
                            ("Flame Flare burn resistance 15% per rank", _configure_flame_flare),
                            ("Blood Euphoria tier 4 and regeneration 0.1%/s per stack", _configure_blood_euphoria),
                            ("Krieg special melee native GameStage scaling through OP10", _configure_special_melee_scaling),
                            ("Pull the Pin grenades in FFYL, old death effect removed", _configure_pull_the_pin),
                            ("Pain is Power health-damage stacks", _configure_pain_is_power),
                            ("Strip the Flesh normal explosive bonus 5% per rank", _configure_strip_the_flesh),
                            ("Fuel the Fire direct incendiary damage 4% per rank", _configure_fuel_the_fire),
                            ("Elemental Empathy healing 10% per rank", _configure_elemental_empathy),
                            ("Numbed Nerves reduction 7.5% per rank, doubled while on fire", _configure_numbed_nerves),
                            ("Raving Retribution incendiary efficacy description", _configure_raving_retribution),
                            ("Hellfire Halitosis native self-ignite and on-fire speed 15%", _configure_hellfire_halitosis),
                            ("Fuel the Rampage direct self-damage reduction and timed speed", _configure_fuel_rampage),
                            ("Light the Fuse additive grenade regeneration, old FFYL removed", _configure_light_the_fuse),
                            ("Burn, Baby, Burn 20% Burn Damage per rank, extra 10% while on fire", _configure_burn_baby_burn)):
        if name in _configured_skill_steps:
            continue  # Stable definitions need no copies/lookups every two seconds.
        try:
            if configure():
                _configured_skill_steps.add(name)
                if name not in _verified_fixes:
                    _verified_fixes.add(name)
                    unrealsdk.logging.info(f"[KriegRebalance] Configuration verified: {name}")
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            if name not in _reported_errors:
                _reported_errors.add(name)
                unrealsdk.logging.error(f"[KriegRebalance] Could not apply {name}: {exc}")


def on_enable() -> None:
    global _next_apply_at, _burn_tuning_revision, _hellborn_tuning_revision, _pain_hud_context, _pain_hud_departing_context
    global _blood_twitch_tuning_revision
    global _overcharge_revision, _blood_overdrive_configured, _bloodlust_gain_address
    global _next_bloody_revival_sync
    _next_apply_at = time.monotonic() + MAINTENANCE_INTERVAL
    _reset_static_configuration()
    _verified_fixes.clear()
    _reported_errors.clear()
    _next_live_sync.clear()
    _next_pull_sync.clear()
    _fuel_speed_until.clear()
    _next_fuel_sync.clear()
    _fuel_hud_owners.clear()
    _next_light_fuse_sync.clear()
    _silence_self_damage_at.clear()
    _pain_stacks.clear()
    _pain_damage_frames.clear()
    _next_pain_sync.clear()
    _pain_owner_keys.clear()
    _next_pain_hud_sync.clear()
    _pain_hud_context = _pain_hud_departing_context = None
    _burn_tuning_revision = 0
    _hellborn_tuning_revision = 0
    _blood_twitch_tuning_revision = 0
    _overcharge_revision = 0
    _overcharge_refreshed.clear()
    _overcharge_restore_paths.clear()
    _blood_overdrive_configured = False
    _bloodlust_gain_address = 0
    _blood_overdrive_gain_scopes.clear()
    _bloodlust_tint_state.clear()
    _next_bloodlust_tint.clear()
    _burn_refreshed.clear()
    _class_mod_cache.clear()
    _class_mod_effect_cache.clear()
    _bloody_revival_state.clear()
    _bloody_revival_recovery_frames.clear()
    _bloody_revival_ffyl_watch.clear()
    _prepared_runtime_leaves.clear()
    _next_bloody_revival_sync.clear()
    _next_bloody_revival_hud_sync.clear()
    _apply_skill_configuration()
    unrealsdk.logging.info(
        "[KriegRebalance] Hooks enabled; individual native changes require their verification messages; "
        "unloaded Krieg assets will be retried; "
        "native changes require restart to disable"
    )


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def maintain_krieg_runtime(_controller: Any, _args: Any, _ret: Any, _func: Any) -> None:
    global _next_apply_at, _configuration_world
    if _controller is None or _controller.bDeleteMe:
        return
    world = _controller.WorldInfo
    if world is None or world.bDeleteMe or _world_is_departing(_controller, world):
        return
    now = time.monotonic()
    if now >= _next_apply_at:
        _next_apply_at = now + MAINTENANCE_INTERVAL
        world_address = world._get_address()
        if _configuration_world != world_address:
            _configured_skill_steps.clear()
            _configuration_world = world_address
        _apply_skill_configuration()
        try:
            _check_live_blood_euphoria_tree(_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            key = "Blood Euphoria live tree check"
            if key not in _reported_errors:
                _reported_errors.add(key)
                unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")
        try:
            _refresh_burn_baby_burn(_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            key = "Burn, Baby, Burn live cache"
            if key not in _reported_errors:
                _reported_errors.add(key)
                unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")
        try:
            _refresh_class_mod_skill_caches(_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            key = "Class-mod skill caches"
            if key not in _reported_errors:
                _reported_errors.add(key)
                unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")
        try:
            _refresh_overcharge_caches(_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            key = "Overcharge native cache migration"
            if key not in _reported_errors:
                _reported_errors.add(key)
                unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")
        try:
            _refresh_hellfire_speed_cache(_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            key = "Hellfire Halitosis live speed cache"
            if key not in _reported_errors:
                _reported_errors.add(key)
                unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")
    _maintain_live_flame_flare(_controller, now)
    _maintain_pull_the_pin(_controller, now)
    _maintain_fuel_rampage(_controller)
    _maintain_light_the_fuse(_controller)
    _maintain_pain_is_power(_controller, now)
    _maintain_pain_hud(_controller, now)
    _maintain_bloodlust_highlight(_controller, now)
    try:
        _sync_bloody_revival_second_wind(_controller, now)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Bloody Revival Second Wind"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")
    _maintain_bloody_revival_hud(_controller, now)
    try:
        _regenerate_blood_euphoria(_controller, _args.DeltaTime)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        key = "Blood Euphoria regeneration"
        if key not in _reported_errors:
            _reported_errors.add(key)
            unrealsdk.logging.error(f"[KriegRebalance] Could not apply {key}: {exc}")


@hook("WillowGame.FrontendGFxMovie:Start", Type.POST)
def refresh_frontend_fixes(_movie: Any, _args: Any, _ret: Any, _func: Any) -> None:
    _reset_static_configuration()
    _apply_skill_configuration()


class KriegRebalanceMod(RestartToDisable):
    def load_settings(self) -> None:
        """Default on for new/old installs with no saved state; respect explicit off."""
        super().load_settings()
        if self.is_enabled or not self.auto_enable:
            return
        if self.settings_file is not None:
            try:
                with self.settings_file.open(encoding="utf-8") as stream:
                    if "enabled" in json.load(stream):
                        return
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        self.enable()  # Normal SDK path: enables hooks, calls on_enable and saves state.


# Native edits persist until restart. Explicit saved disabled state is respected.
mod = build_mod(cls=KriegRebalanceMod, auto_enable=True,
                hooks=[prepare_blood_euphoria_tree, describe_blood_euphoria, block_old_pull_the_pin_grenade,
                       limit_silence_self_damage, begin_pain_health_damage, finish_pain_health_damage,
                       describe_pain_is_power, suspend_pain_hud_before_travel, suspend_pain_hud_before_destroy,
                       apply_raving_elemental_efficacy,
                       reduce_fuel_self_damage, describe_fuel_rampage,
                       describe_light_the_fuse, describe_blood_twitch, describe_overcharge, describe_blood_filled_guns,
                       begin_blood_overdrive_gain, finish_blood_overdrive_gain,
                       observe_bloody_revival_ffyl, observe_bloody_revival_reason,
                       begin_bloody_revival_recovery, finish_bloody_revival_recovery,
                       maintain_krieg_runtime, refresh_frontend_fixes, describe_bloody_revival, describe_fuel_the_fire,],
                commands=[toggle_krieg_audio_trace], keybinds=[], options=[])
