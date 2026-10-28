from __future__ import annotations

import copy
import random
import re
import time
from typing import TYPE_CHECKING, Any

import unrealsdk  # pyright: ignore[reportMissingModuleSource]
from mods_base import ObjectFlags, RestartToDisable, build_mod, get_pc, hook
from unrealsdk.hooks import Block, Type  # pyright: ignore[reportMissingModuleSource]
from unrealsdk.unreal import WeakPointer  # pyright: ignore[reportMissingModuleSource]

if TYPE_CHECKING:
    from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # pyright: ignore[reportMissingModuleSource]


class _RestartSafeMod(RestartToDisable):
    """Persist disable requests, keeping native mutations AND their guards together."""

    def disable(self, dont_update_setting: bool = False) -> None:
        if self.enabling_locked or not self.is_enabled:
            return
        # Unlike the base class, do NOT remove hooks from a still-patched engine.
        # Native definitions are restored only by a fresh game process.
        self.is_enabled = False
        if self.auto_enable and not dont_update_setting:
            self.save_settings()
        unrealsdk.logging.info(
            "[MayaRebalance] Disable scheduled for restart; runtime guards remain active until exit"
        )

    def enable(self) -> None:
        if self.enabling_locked or self.is_enabled:
            return
        if self._ever_enabled:
            # Cancel a pending restart-disable without registering the hooks twice.
            self.is_enabled = True
            if self.auto_enable:
                self.save_settings()
            return
        super().enable()


SUSTENANCE_PATH = "GD_Siren_Skills.Harmony.Sustenance"
RECOMPENSE_PATH = "GD_Siren_Skills.Harmony.Recompense"
SLAGGER_TEMPLATE_PATH = "GD_Siren_Skills.Harmony.Skill_Sphere"
SLAGGER_PATH = "GD_Siren_Skills.Cataclysm.MR_Slagger"
SLAGGER_TREE_PATH = "GD_Siren_Streaming.SkillTree.SkillTree_Siren"
SLAGGER_BRANCH_PATH = "GD_Siren_Skills.SkillTree.Branch_Cataclysm"
SLAGGER_LAYOUT_PATH = "GD_Siren_Skills.SkillTree.Layout_Cataclysm"
SLAGGER_BONUS = 0.075  # Per distinct elemental status, not per allocated point.
SLAGGER_RECEIVED_FIELDS = (
    "ReceivedBulletDamageModifier", "ReceivedGrenadeDamageModifier",
    "ReceivedMeleeDamageModifier", "ReceivedRocketDamageModifier",
    "ReceivedStatusEffectDamageModifier", "ReceivedSkillDamageModifier",
)
# Only known native source classes use the narrow path. Unknown/custom classes
# retain all six fields rather than guessing how their damage is classified.
SLAGGER_SOURCE_FIELDS = {
    f"WillowGame.WillowDmgSource_{name}": f"Received{kind}DamageModifier"
    for kind, names in (
        ("Bullet", ("Bullet", "Pistol", "Shotgun", "MachineGun", "SubMachineGun", "Sniper")),
        ("Grenade", ("Grenade",)), ("Melee", ("Melee",)), ("Rocket", ("Rocket",)),
        ("StatusEffect", ("StatusEffect",)), ("Skill", ("Skill", "Skill_IgnoreIOs")),
    )
    for name in names
}
SLAGGER_DESCRIPTION = (
    "Enemies take [skill]increased damage[-skill] from you for each different "
    "[skill]elemental status effect[-skill] affecting them. "
    "[skill]Ignite, Shock, Corrosion and Slag[-skill] each count once, up to [skill]4 stacks[-skill]."
)
_slagger_definition: Any | None = None
_slagger_modifier_pool: dict[int, tuple[tuple[str, Any, Any], ...]] = {}
_slagger_received_attributes: dict[str, Any] = {}
_slagger_status_type_bits: dict[int, int] = {}
_slagger_damage_scopes: list[dict[str, Any]] = []
_slagger_live_tree_context: tuple[int, int] | None = None
_slagger_logged_amplification: set[int] = set()
RES_PATH = "GD_Siren_Skills.Harmony.Res"
RES_PLAYER_CLASS_PATH = "GD_Siren.Character.CharClass_Siren"
RES_COOLDOWN_SECONDS = 120.0
RES_DESCRIPTION = (
    "You can [skill]instantly revive[-skill] a friend in [skill]Fight For Your Life[-skill] "
    "by using [skill]Phaselock[-skill] on him/her. "
    "Additionally, entering [skill]Fight For Your Life[-skill] automatically grants you "
    "a [skill]Second Wind[-skill] when available. Cooldown: 120 seconds. "
    "The cooldown resets on death."
)
_res_player_states: dict[tuple[Any, ...], dict[str, Any]] = {}
_res_death_contexts: list[dict[str, Any] | None] = []
_res_hud_feedback: Any | None = None
_recompense_cooldown_hud_feedback: Any | None = None
_cooldown_hud_suspended = False
_cooldown_hud_context: tuple[int, int] | None = None
_cooldown_hud_departing_context: tuple[int, int] | None = None
FLICKER_PATH = "GD_Siren_Skills.Cataclysm.Flicker"
BLIGHT_PHOENIX_PATH = "GD_Siren_Skills.Cataclysm.BlightPhoenix"
BLIGHT_PHOENIX_SPEED_ATTRIBUTE_PATH = "D_Attributes.GameplayAttributes.FootSpeed"
BLIGHT_PHOENIX_AURA_ATTRIBUTE_PATH = "GD_Siren_Skills.Misc.Att_BlightPhoenix_IsActive"
BLIGHT_PHOENIX_AURA_DAMAGE_PATHS = (
    f"{BLIGHT_PHOENIX_PATH}:BehaviorProviderDefinition_2.Behavior_CauseDamage_6",
    f"{BLIGHT_PHOENIX_PATH}:BehaviorProviderDefinition_2.Behavior_CauseDamage_7",
)
BLIGHT_PHOENIX_AMMO_CHANCE_PER_RANK = 0.08
BLIGHT_PHOENIX_SPEED_PER_RANK = 0.05
_blight_phoenix_last_ammo_log: tuple[int, int, int] | None = None
_blight_phoenix_last_speed_log: tuple[int, int, float | None] | None = None
_blight_phoenix_shot_contexts: list[dict[str, Any]] = []
_blight_phoenix_fire_calls: list[dict[str, Any] | None] = []
ACCELERATE_PATH = "GD_Siren_Skills.Motion.Accelerate"
SUSPENSION_PATH = "GD_Siren_Skills.Motion.Suspension"
QUICKEN_PATH = "GD_Siren_Skills.Motion.Quicken"
KINETIC_REFLECTION_PATH = "GD_Siren_Skills.Motion.KineticReflection"
KINETIC_REFLECTION_ATTRIBUTE_PATH = "D_Attributes.BulletReflection.BulletReflectedOffSelfDamageTakenScale"
KINETIC_REFLECTION_BULLET_REDUCTION_PER_RANK = 0.10
KINETIC_REFLECTION_GENERAL_REDUCTION_PER_RANK = 0.05
KINETIC_REFLECTION_DESCRIPTION = (
    "[skill]Kill Skill[-skill]. After killing an enemy, you [skill]deflect enemy bullets[-skill] "
    "toward nearby enemies and gain [skill]damage reduction[-skill] for a short time. "
    "The [skill]stronger reduction against bullets[-skill] replaces the general reduction."
)
_kinetic_reflection_logged_ranks: set[int] = set()
MINDS_EYE_PATH = "GD_Siren_Skills.Harmony.MindsEye"
THOUGHTLOCK_PATH = "GD_Siren_Skills.Motion.ThoughtLock"
THOUGHTLOCK_DAMAGE_REDUCTION = 0.20
THOUGHTLOCK_DAMAGE_TAKEN = 0.15
THOUGHTLOCK_DEBUFF_SECONDS = 8.0
THOUGHTLOCK_DURATION_BONUS_SECONDS = 2.0
THOUGHTLOCK_FEEDBACK_PATH = "GD_Siren_Skills.Motion.ThoughtLock_Feedback"
THOUGHTLOCK_HUD_SLOT = 7
_thoughtlock_hud_feedback: Any | None = None
THOUGHTLOCK_CONVERGE_PATH = "GD_Siren_Skills.Melee.Converge_MeleeDefinition"
_thoughtlock_marks: dict[tuple[int, int], dict[str, Any]] = {}
_thoughtlock_marks_world: int | None = None
_thoughtlock_marks_expiry = 0.0
_thoughtlock_marks_clock = 0.0
_thoughtlock_damage_logged: set[float] = set()
MINDS_EYE_ACCURACY_ATTRIBUTE_PATH = "D_Attributes.Weapon.WeaponSpread"
MINDS_EYE_MELEE_ATTRIBUTE_PATH = "D_Attributes.DamageSourceModifiers.InstigatedMeleeDamageModifier"
RESTORATION_PATH = "GD_Siren_Skills.Harmony.Restoration"
SCORN_PATH = "GD_Siren_Skills.Harmony.Scorn"
SCORN_STATUS_DURATION_BONUS = 0.50
SCORN_STATUS_DESCRIPTION_SUFFIX = (
    "<br>Passively increases your [skill]elemental status effect duration[-skill]."
)
RUIN_PATH = "GD_Siren_Skills.Cataclysm.Ruin"
SCORN_DAMAGE_SPAWN_PATH = f"{SCORN_PATH}:BehaviorProviderDefinition_15.Behavior_SpawnProjectile_2"
SCORN_DAMAGE_AREA_PATH = "GD_Siren_Skills.Projectiles.Projectile_Scorn:WillowDamageArea_27"
PROJECTILE_DAMAGE_ATTRIBUTE_PATH = "D_Attributes.Projectile.ProjectileDamage"
PLAYER_MELEE_BASE_INITIALIZER_PATH = "GD_Balance_HealthAndDamage.HealthAndDamage.Init_PlayerMeleeDamageBase"
SKILL_LEVEL_SCALER_PATH = "GD_Balance_HealthAndDamage.HealthAndDamage.Att_UniversalBalanceScaler"
SKILL_GAME_STAGE_PATH = "GD_Lobelia_GameStages.Attributes.GameStageViaGetGameStage"
# Author-defined bonuses over level-only damage. Stage90 = level80/OP10.
SKILL_DAMAGE_BONUS_ANCHORS = {
    "Ruin": ((1, .15), (90, 1.90)),
    "Scorn": ((1, .25), (90, 2.35)),
    "Helios": ((1, .15), (90, 1.25)),
}
SKILL_LEVEL_DAMAGE_BASES = {"Ruin": 1.0, "Scorn": 8.0}
RUIN_DAMAGE_PROVIDER_PATH = "GD_Siren_Skills.Phaselock.ActionSkill_Phaselock:BehaviorProviderDefinition_0"
# Native Ruin slag/corrosive/shock behaviors, NOT Phaselock's direct damage (_11).
RUIN_DAMAGE_BEHAVIOR_PATHS = tuple(
    f"{RUIN_DAMAGE_PROVIDER_PATH}.Behavior_CauseDamage_{index}" for index in (10, 14, 15)
)
PHASELOCK_DIRECT_DAMAGE_PATHS = tuple(
    f"{RUIN_DAMAGE_PROVIDER_PATH}.Behavior_CauseDamage_{index}" for index in (11, 16)
)
PHASELOCK_DIRECT_DAMAGE_MULTIPLIER = 1.75
_level_damage_initializers: dict[str, Any] = {}  # Static definitions only.
_logged_level_damage_runtime: set[tuple[str, int]] = set()
_ruin_level_readiness: tuple[int, int, int] | None = None
_ruin_native_damage_stack: list[dict[str, Any]] = []
_ruin_native_damage_log_at: dict[str, float] = {}
_logged_ruin_runtime_repairs: set[str] = set()
ELATED_PATH = "GD_Siren_Skills.Harmony.Elated"
WRECK_PATH = "GD_Siren_Skills.Harmony.Wreck"
WRECK_FIRE_INTERVAL_PER_RANK = -0.05
WRECK_WEAPON_DAMAGE_PER_RANK = 0.03
_wreck_passive_definition: Any | None = None
_wreck_passive_request: tuple[int, int, int, int] | None = None
WRECK_DESCRIPTION = (
    "Increases your [skill]Fire Rate[-skill] and [skill]Gun Damage[-skill]. "
    "These bonuses [skill]double[-skill] while you have an enemy [skill]Phaselocked[-skill]."
)
IMMOLATE_PATH = "GD_Siren_Skills.Cataclysm.Immolate"
PHASELOCK_PATH = "GD_Siren_Skills.Phaselock.Skill_Phaselock"
PHASELOCK_DURATION_ATTRIBUTE_PATH = "GD_Siren_Skills.Misc.Att_Phaselock_Duration"
PHASELOCK_HEALTH_EVALUATOR_PATH = (
    f"{PHASELOCK_PATH}:HealthStateExpressionEvaluator_0"
)
PHASELOCK_COOLDOWN_MANAGER_PATH = f"{PHASELOCK_PATH}_CooldownManager"
PHASELOCK_BASE_DELAY_PATH = (
    "GD_Siren_Skills.Phaselock.ActionSkill_Phaselock:"
    "BehaviorProviderDefinition_0.Behavior_Delay_10"
)
SCORN_COOLDOWN_ATTRIBUTE_PATH = "GD_Siren_Skills.Misc.Cooldown_Scorn"
SWEET_RELEASE_PROJECTILE_PATH = "GD_Siren_Skills.Projectiles.SweetRelease_Projectile"
HELIOS_DAMAGE_BEHAVIOR_PATH = (
    "GD_Siren_Skills.Phaselock.ActionSkill_Phaselock:"
    "BehaviorProviderDefinition_0.Behavior_CauseDamage_17"
)
HELIOS_DAMAGE_INITIALIZER_PATH = "GD_Siren_Skills.Misc.Init_Ablaze_DamageCalc"
BACKDRAFT_PATH = "GD_Siren_Skills.Cataclysm.Backdraft"
BACKDRAFT_SKILL_DAMAGE_PER_RANK = 0.07
BACKDRAFT_SKILL_DAMAGE_FIELD = "InstigatedSkillDamageModifier"
BACKDRAFT_SKILL_DESCRIPTION_SUFFIX = "<br>Increases your [skill]Skill Damage[-skill]."
_backdraft_skill_damage_attribute: Any | None = None
# Legacy BPD event label retained for the explicit Scorn bridge only.
BACKDRAFT_MELEE_EVENT_NAME = "Damaged Enemy with Melee"
BACKDRAFT_FINAL_DAMAGE_PER_RANK = 0.18
BACKDRAFT_NOVA_RADIUS = 800.0 * 1.15
BACKDRAFT_SCORN_SLAG_TEMPLATE_PATH = "GD_Amp.DamageType.DmgType_Amp_Impact"
BACKDRAFT_SCORN_DESCRIPTION_SUFFIX = (
    "The beams from [skill]Scorn[-skill] deal additional [skill]fire damage[-skill]."
)
BACKDRAFT_DESCRIPTION = (
    BACKDRAFT_SCORN_DESCRIPTION_SUFFIX + BACKDRAFT_SKILL_DESCRIPTION_SUFFIX
    + "<br>When your shields are depleted, you create a [skill]fiery explosion[-skill], "
    "damaging nearby enemies. Your shields must fully recharge between explosions."
)
_backdraft_scorn_damage_type: Any | None = None
_backdraft_fire_trace_stack: list[bool] = []
_backdraft_scorn_next_damage_logs: dict[str, float] = {}
_backdraft_scorn_hit_contexts: list[dict[str, Any] | None] = []
BACKDRAFT_NOVA_BEHAVIOR_PATH = (
    "GD_Siren_Skills.Cataclysm.Backdraft:BehaviorProviderDefinition_0.Behavior_Explode_0"
)
BACKDRAFT_MELEE_BEHAVIOR_PATH = (
    "GD_Siren_Skills.Cataclysm.Backdraft:BehaviorProviderDefinition_0.Behavior_CauseDamage_22"
)
ACTION_SKILL_COOLDOWN_RATE_ATTRIBUTE_PATH = (
    "D_Attributes.ActiveSkillCooldownResource.ActiveSkillCooldownConsumptionRate"
)
MELEE_SKILL_COOLDOWN_RATE_ATTRIBUTE_PATH = (
    "D_Attributes.MeleeSkillCooldownResource.MeleeSkillCooldownConsumptionRate"
)
IMMOLATE_FIRE_DAMAGE_ATTRIBUTE_PATH = (
    "D_Attributes.Weapon.WeaponPerShotAccuracyImpulse"
)
IMMOLATE_REVIVE_TIME_ATTRIBUTE_PATH = "D_Attributes.injured.TimeToBeRevivedMultiplier"
IMMOLATE_CAUSE_DAMAGE_BEHAVIOR_PATH = (
    f"{IMMOLATE_PATH}:BehaviorProviderDefinition_9.Behavior_CauseDamage_113"
)
IMMOLATE_IMPACT_DAMAGE_TYPE_PATH = "GD_Incendiary.DamageType.DmgType_Incendiary_Impact"
RECOMPENSE_FEEDBACK_PATH = "GD_Siren_Skills.Harmony.Recompense_Feedback"
RECOMPENSE_NATIVE_DAMAGE_PATH = f"{RECOMPENSE_PATH}:BehaviorProviderDefinition_0.Behavior_CauseDamage_0"
RECOMPENSE_NATIVE_FEEDBACK_TRIGGER_PATH = f"{RECOMPENSE_PATH}:BehaviorProviderDefinition_0.Behavior_ActivateSkill_0"
_recompense_blocked_legacy_behaviors: set[str] = set()
IMMOLATE_HUD_SLOT = 0
RECOMPENSE_HUD_SLOT = 4

RECOMPENSE_COOLDOWN_SECONDS = 3.0
RECOMPENSE_AVOID_CHANCE_PER_RANK = 0.05
SUSTENANCE_COOLDOWN_SECONDS = 0.5
SUSTENANCE_HEAL_PER_RANK = 0.03
SWEET_RELEASE_PROJECTILE_SPEED = 1200.0
MINDS_EYE_SPREAD_PER_RANK = -0.05
PHASELOCK_BASE_DURATION_SECONDS = 7.0
SUSPENSION_DURATION_PER_RANK = 0.7
SCORN_BASE_COOLDOWN_SECONDS = 12.0
QUICKEN_COOLDOWN_RATE_PER_RANK = 0.10
ELATED_REGEN_PER_RANK = 0.01
IMMOLATE_DAMAGE_PER_RANK = 0.05
FLICKER_STATUS_CHANCE_PER_RANK = 0.10
FLICKER_DIRECT_DAMAGE_PER_RANK = 0.06
ACCELERATE_WEAPON_DAMAGE_PER_RANK = 0.04
ACCELERATE_PROJECTILE_SPEED_PER_RANK = 0.05
IMMOLATE_DURATION_SECONDS = 12.0
BASE_SKILL_RANK_LIMIT = 5
CLASS_MODDED_SKILL_RANK_LIMIT = 11
CLASS_MOD_SKILL_RANK_LIMIT = 6
SKILL_UI_VALIDATION_INTERVAL_SECONDS = 1.0
CLASS_MOD_RANK_REFRESH_INTERVAL_SECONDS = 1.0
SKILL_STAT_LINES_REFRESH_INTERVAL_SECONDS = 0.25
PHASELOCK_VALIDATION_INTERVAL_SECONDS = 1.0

SKILL_PRESENTATION_PATHS = {
    SUSTENANCE_PATH: f"{SUSTENANCE_PATH}:AttributePresentationDefinition_77",
    RECOMPENSE_PATH: f"{RECOMPENSE_PATH}:AttributePresentationDefinition_1",
    FLICKER_PATH: f"{FLICKER_PATH}:AttributePresentationDefinition_0",
    ACCELERATE_PATH: f"{ACCELERATE_PATH}:AttributePresentationDefinition_0",
    SUSPENSION_PATH: f"{SUSPENSION_PATH}:AttributePresentationDefinition_0",
    QUICKEN_PATH: f"{QUICKEN_PATH}:AttributePresentationDefinition_0",
    RESTORATION_PATH: f"{RESTORATION_PATH}:AttributePresentationDefinition_0",
    ELATED_PATH: f"{ELATED_PATH}:AttributePresentationDefinition_0",
    IMMOLATE_PATH: f"{IMMOLATE_PATH}:AttributePresentationDefinition_0",
    BLIGHT_PHOENIX_PATH: f"{BLIGHT_PHOENIX_PATH}:AttributePresentationDefinition_0",
}

_recompense_player_states: dict[tuple[Any, ...], dict[str, Any]] = {}
_sustenance_ready_at: dict[int, float] = {}
_sustenance_status_contexts: list[dict[str, Any]] = []
_sustenance_logged_status_types: set[tuple[int, int, bool]] = set()
_sustenance_allowed_types: set[int] = set()
_sustenance_next_heal_log_at: dict[int, float] = {}
_immolate_buff_expires_at = 0.0
_immolate_final_damage_logged = False
_immolate_damage_contexts: list[dict[str, Any]] = []
_immolate_hit_contexts: list[dict[str, Any] | None] = []
_immolate_fire_type: Any | None = None
_immolate_gun_sources: tuple[Any, ...] = ()
_immolate_skill_source: Any | None = None
_immolate_hud_feedback: Any | None = None
_immolate_hud_native_active = False
_immolate_buff_controller_address: int | None = None
_pending_scorn_cooldown = True
_pending_sweet_release_speed = True
_pending_damage_tuning: set[str] = {"Helios", "Backdraft", "Scorn", "Ruin", "Phaselock", "BackdraftScorn"}
_pending_phaselock_tuning = True
_next_phaselock_validation_at = 0.0
_last_logged_errors: set[str] = set()
_logged_skill_presentation_overrides: set[str] = set()
_logged_skill_presentation_resolutions: set[str] = set()
_last_skill_ui_ranks: dict[str, tuple[int, bool]] = {}
_logged_ranked_skill_descriptions: set[tuple[str, int, int, bool]] = set()
_ranked_skill_description_depth = 0
_next_skill_ui_validation_at = 0.0
_next_skill_stat_lines_refresh_at = 0.0
_last_skill_runtime_context: tuple[int, int, int] | None = None
_next_cooldown_hud_sync_at = 0.0
_cached_class_mod_ranks: dict[str, int] = {}
_cached_class_mod_controller_address: int | None = None
_cached_class_mod_equipment_identity: tuple[int, int] | None = None
_next_class_mod_rank_refresh_at = 0.0
_last_applied_skill_ranks: dict[str, int] = {}
_last_applied_skill_controller_address: int | None = None
_skill_package_loaded = False
_flicker_modifier_controller_address: int | None = None
_flicker_runtime_modifiers: dict[str, Any] = {}
_flicker_runtime_modifier_generation = 0
_flicker_runtime_rank: int | None = None
_quicken_melee_modifier_controller_address: int | None = None
_quicken_melee_runtime_modifier: Any | None = None
_quicken_melee_modifier_generation = 0
_quicken_melee_runtime_rank: int | None = None
_quicken_melee_runtime_pool: Any | None = None
_minds_eye_diagnostic_states: dict[int, Any] = {}
_pending_skill_effects: set[tuple[str, str]] = {
    (FLICKER_PATH, "D_Attributes.Weapon.WeaponStatusEffectChanceModifier"),
    (ACCELERATE_PATH, "D_Attributes.Weapon.WeaponDamage"),
    (ACCELERATE_PATH, "D_Attributes.Weapon.WeaponProjectileSpeedMultiplier"),
    (SUSPENSION_PATH, "GD_Siren_Skills.Misc.Att_Phaselock_Duration"),
    (QUICKEN_PATH, ACTION_SKILL_COOLDOWN_RATE_ATTRIBUTE_PATH),
    (RESTORATION_PATH, "D_Attributes.HealthResourcePool.HealthMaxValue"),
    (IMMOLATE_PATH, IMMOLATE_FIRE_DAMAGE_ATTRIBUTE_PATH),
}
_next_skill_tuning_retry_at = 0.0

FLICKER_DIRECT_DAMAGE_ATTRIBUTES = (
    (
        "D_Attributes.DamageTypeModifers.InstigatedIncindiaryDamageModifier",
        "InstigatedIncindiaryDamageModifier",
        FLICKER_DIRECT_DAMAGE_PER_RANK,
        "Incendiary",
    ),
    (
        "D_Attributes.DamageTypeModifers.InstigatedShockDamageModifier",
        "InstigatedShockDamageModifier",
        FLICKER_DIRECT_DAMAGE_PER_RANK,
        "Shock",
    ),
    (
        "D_Attributes.DamageTypeModifers.InstigatedCorrosiveDamageModifier",
        "InstigatedCorrosiveDamageModifier",
        FLICKER_DIRECT_DAMAGE_PER_RANK,
        "Corrosive",
    ),
)

SKILL_UI = {
    SUSTENANCE_PATH: (
        "Applying [skill]Ignite[-skill], [skill]Shock[-skill], [skill]Corrosion[-skill] "
        "or [skill]Slag[-skill] to an enemy from any source "
        "[skill]restores a percentage of your maximum health[-skill]. "
        "Damage-over-time ticks do not trigger this effect. Healing cooldown: 0.5 seconds."
    ),
    RECOMPENSE_PATH: (
        "You have a chance to [skill]completely ignore incoming damage[-skill]. "
        "Cooldown: 3 seconds."
    ),
    FLICKER_PATH: (
        "Increases your [skill]chance to inflict status effects[-skill] "
        "and your [skill]elemental damage[-skill]."
    ),
    ACCELERATE_PATH: (
        "Increases [skill]weapon damage[-skill] and also increases [skill]bullet speed[-skill]."
    ),
    SUSPENSION_PATH: "Increases [skill]Phaselock duration[-skill].",
    QUICKEN_PATH: "Increases the [skill]cooldown rate[-skill] of [skill]Phaselock[-skill] and [skill]Scorn[-skill].",
    RESTORATION_PATH: (
        "Shooting other players [skill]heals[-skill] them.  "
        "Also increases your [skill]Maximum Health[-skill]."
    ),
    ELATED_PATH: (
        "[skill]Regenerates health[-skill] each second. [skill]Regeneration doubles[-skill] "
        "while [skill]Phaselock[-skill] is active."
    ),
    IMMOLATE_PATH: (
        "Activating [skill]Phaselock[-skill] adds [skill]incendiary damage[-skill] "
        "to your shots for 12 seconds."
    ),
    BLIGHT_PHOENIX_PATH: (
        "[skill]Kill Skill[-skill]. Killing an enemy increases your "
        "[skill]movement speed[-skill] and gives your [skill]Incendiary[-skill], "
        "[skill]Shock[-skill], [skill]Corrosive[-skill] and [skill]Slag[-skill] weapons "
        "a chance to [skill]not consume ammunition[-skill] for a short time."
    ),
}
SKILL_PATHS_BY_NAME = {
    skill_path.rsplit(".", 1)[-1].casefold(): skill_path
    for skill_path in SKILL_UI
}
SKILL_PATHS_BY_NAME["backdraft"] = BACKDRAFT_PATH


def _log_error_once(message: str) -> None:
    if message not in _last_logged_errors:
        if len(_last_logged_errors) >= 256:
            # Retain a bounded deduplication window, not every dynamic actor path
            # ever seen during a long session. Errors are still reported.
            _last_logged_errors.clear()
        unrealsdk.logging.error(f"[MayaRebalance] {message}")
        _last_logged_errors.add(message)


def _skill_rank(player_controller: Any, skill_path: str) -> int:
    invested_rank = _invested_skill_rank(player_controller, skill_path)
    return _effective_skill_rank(player_controller, skill_path, invested_rank)


def _invested_skill_rank(player_controller: Any, skill_path: str) -> int:
    skill_definition = unrealsdk.find_object("SkillDefinition", skill_path)
    return max(0, int(player_controller.GetSkillGrade(skill_definition)))


def _effective_skill_rank(
    player_controller: Any,
    skill_path: str,
    invested_rank: int,
) -> int:
    if invested_rank == 0:
        return 0

    class_mod_rank = _class_mod_skill_rank(player_controller, skill_path)
    return min(
        CLASS_MODDED_SKILL_RANK_LIMIT,
        invested_rank + class_mod_rank,
    )


def _skill_ui_rank(
    player_controller: Any,
    skill_path: str,
    invested_rank: int,
    effective_rank: int,
) -> int:
    """Return the exact effective rank whose values the skill UI must preview."""

    if skill_path in {SUSTENANCE_PATH, ELATED_PATH}:
        # Keep the shared fallback at the current value. The tree's two outer
        # queries format their own Grade/GradeModifier, never this cached preview.
        return effective_rank

    if invested_rank < BASE_SKILL_RANK_LIMIT:
        return _effective_skill_rank(
            player_controller,
            skill_path,
            invested_rank + 1,
        )
    return effective_rank


def _class_mod_skill_rank(player_controller: Any, skill_path: str) -> int:
    global _cached_class_mod_controller_address
    global _cached_class_mod_equipment_identity
    global _cached_class_mod_ranks
    global _next_class_mod_rank_refresh_at

    now = time.monotonic()
    controller_address = player_controller._get_address()
    pawn = player_controller.Pawn
    inventory_manager = pawn.InvManager if pawn else None
    equipped = inventory_manager.GetCurrentClassMod() if inventory_manager else None
    equipment_identity = (pawn._get_address() if pawn else 0,
                          equipped._get_address() if equipped else 0)
    if (
        controller_address == _cached_class_mod_controller_address
        and equipment_identity == _cached_class_mod_equipment_identity
        and now < _next_class_mod_rank_refresh_at
    ):
        return min(
            CLASS_MOD_SKILL_RANK_LIMIT,
            _cached_class_mod_ranks.get(skill_path, 0),
        )

    class_mod_ranks: dict[str, int] = {}
    # ItemChain includes unequipped COMs. Only the equipped item grants ranks.
    if equipped:
        stats = equipped.ItemCardModifierStats
        if len(stats) > 64:
            raise ValueError("Equipped class mod has more than 64 item-card stats")
        for stat in stats:
            presentation = stat.AttributePresentation
            if not presentation:
                continue

            presentation_path = str(presentation._path_name())
            presentation_name = str(presentation.Name)
            rank_bonus = float(stat.ModifierValue)
            if (
                ".Skills_" not in presentation_path
                or not presentation_name.startswith("AttrPresent_")
            ):
                continue

            boosted_skill_name = presentation_name.removeprefix(
                "AttrPresent_"
            ).casefold()
            boosted_skill_path = SKILL_PATHS_BY_NAME.get(boosted_skill_name)
            if boosted_skill_path is None:
                continue

            if rank_bonus > 0 and rank_bonus.is_integer():
                class_mod_ranks[boosted_skill_path] = min(
                    CLASS_MOD_SKILL_RANK_LIMIT,
                    class_mod_ranks.get(boosted_skill_path, 0) + int(rank_bonus),
                )

    if (
        controller_address != _cached_class_mod_controller_address
        or class_mod_ranks != _cached_class_mod_ranks
    ):
        rank_summary = ", ".join(
            f"{path.rsplit('.', 1)[-1]}={rank}"
            for path, rank in sorted(class_mod_ranks.items())
        ) or "none"
        unrealsdk.logging.info(
            f"[MayaRebalance] Detected class-mod skill ranks: "
            f"{rank_summary}"
        )

    _cached_class_mod_controller_address = controller_address
    _cached_class_mod_equipment_identity = equipment_identity
    _cached_class_mod_ranks = class_mod_ranks
    _next_class_mod_rank_refresh_at = (
        now + CLASS_MOD_RANK_REFRESH_INTERVAL_SECONDS
    )
    return min(
        CLASS_MOD_SKILL_RANK_LIMIT,
        class_mod_ranks.get(skill_path, 0),
    )


def _rank_limit(rank: int) -> int:
    if rank > BASE_SKILL_RANK_LIMIT:
        return CLASS_MODDED_SKILL_RANK_LIMIT
    return BASE_SKILL_RANK_LIMIT


def _format_percentage_progression(
    label: str,
    per_rank: float,
    rank: int,
    can_add_point: bool,
    suffix: str = "",
    show_plus: bool = False,
) -> str:
    value = per_rank * rank
    formatted_value = _format_number(value)
    if show_plus:
        formatted_value = f"+{formatted_value}"
    formatted_value += "%"
    if not can_add_point:
        formatted_value = f'<font color="#00FF00">{formatted_value}</font>'
    return f"{label}: {formatted_value}{suffix}"


def _color_stat_percentages(text: str) -> str:
    """Include the unit in native colored footer numbers too; leave plain text alone."""
    return re.sub(r"(<font\b[^>]*>[^<>]*)(</font>)(%)", r"\1\3\2", text, flags=re.IGNORECASE)


def _format_number(value: float) -> str:
    return f"{value:g}"


def _format_rank_progression(
    label: str,
    per_rank: float,
    rank: int,
    can_add_point: bool,
    unit: str,
    show_plus: bool = False,
) -> str:
    value = per_rank * rank
    formatted_value = _format_number(value)
    if show_plus:
        formatted_value = f"+{formatted_value}"
    if not can_add_point:
        formatted_value = f'<font color="#00FF00">{formatted_value}</font>'
    return f"{label}: {formatted_value} {unit}"


def _skill_stat_line(
    skill_path: str,
    rank: int,
    can_add_point: bool,
) -> str:
    if skill_path == SUSTENANCE_PATH:
        return _format_percentage_progression(
            "Healing per application", SUSTENANCE_HEAL_PER_RANK * 100,
            rank, can_add_point, " max health"
        )

    if skill_path == RECOMPENSE_PATH:
        return _format_percentage_progression(
            "Chance to ignore damage", RECOMPENSE_AVOID_CHANCE_PER_RANK * 100, rank, can_add_point
        )

    if skill_path == FLICKER_PATH:
        return "<br>".join(
            (
                _format_percentage_progression(
                    "Status effect chance", FLICKER_STATUS_CHANCE_PER_RANK * 100, rank, can_add_point,
                    show_plus=True,
                ),
                _format_percentage_progression(
                    "Elemental damage", FLICKER_DIRECT_DAMAGE_PER_RANK * 100, rank, can_add_point,
                    show_plus=True,
                ),
            )
        )

    if skill_path == ACCELERATE_PATH:
        return _format_percentage_progression(
            "Weapon damage", ACCELERATE_WEAPON_DAMAGE_PER_RANK * 100, rank, can_add_point, show_plus=True
        )

    if skill_path == SUSPENSION_PATH:
        return _format_rank_progression(
            "Phaselock duration", SUSPENSION_DURATION_PER_RANK,
            rank, can_add_point, "seconds", show_plus=True,
        )

    if skill_path == QUICKEN_PATH:
        return _format_percentage_progression(
            "Cooldown rate",
            QUICKEN_COOLDOWN_RATE_PER_RANK * 100,
            rank,
            can_add_point,
            show_plus=True,
        )

    if skill_path == RESTORATION_PATH:
        return _format_percentage_progression(
            "Maximum health", 4, rank, can_add_point, show_plus=True
        )

    if skill_path == ELATED_PATH:
        return _format_percentage_progression(
            "Health regeneration",
            ELATED_REGEN_PER_RANK * 100,
            rank,
            can_add_point,
            " max health",
        )

    if skill_path == IMMOLATE_PATH:
        return _format_percentage_progression(
            "Incendiary damage",
            IMMOLATE_DAMAGE_PER_RANK * 100,
            rank,
            can_add_point,
            show_plus=True,
        )

    if skill_path == BLIGHT_PHOENIX_PATH:
        return "<br>".join((
            _format_percentage_progression(
                "Chance to not consume ammo", 100 * min(1.0, BLIGHT_PHOENIX_AMMO_CHANCE_PER_RANK * rank),
                1, can_add_point,
            ),
            _format_percentage_progression(
                "Movement speed", BLIGHT_PHOENIX_SPEED_PER_RANK * 100,
                rank, can_add_point, show_plus=True,
            ),
        ))

    raise ValueError(f"No skill stat-line formatter for {skill_path}")


def _attribute_path(effect: Any) -> str:
    attribute = effect.AttributeToModify
    if not attribute:
        return ""
    return str(effect.AttributeToModify._path_name())


def _presentation_attribute_path(presentation: Any) -> str | None:
    attribute = presentation.Attribute
    return None if not attribute else str(attribute._path_name())


def _find_skill_presentation(skill_path: str, skill_definition: Any) -> Any:
    presentation_path = SKILL_PRESENTATION_PATHS[skill_path]
    attribute_path = {
        ACCELERATE_PATH: "D_Attributes.Weapon.WeaponDamage",
        RESTORATION_PATH: "D_Attributes.HealthResourcePool.HealthMaxValue",
        IMMOLATE_PATH: IMMOLATE_FIRE_DAMAGE_ATTRIBUTE_PATH,
    }.get(skill_path)
    presentations = list(skill_definition.SkillEffectPresentations)

    if attribute_path is not None:
        for presentation in presentations:
            if _presentation_attribute_path(presentation) == attribute_path:
                if skill_path not in _logged_skill_presentation_resolutions:
                    unrealsdk.logging.info(
                        f"[MayaRebalance] Resolved {skill_path} UI "
                        f"presentation by {attribute_path}"
                    )
                    _logged_skill_presentation_resolutions.add(skill_path)
                return presentation

    try:
        return unrealsdk.find_object(
            "AttributePresentationDefinition",
            presentation_path,
        )
    except ValueError as direct_lookup_error:
        if skill_path in {ELATED_PATH, IMMOLATE_PATH} and len(
            presentations
        ) == 1:
            if skill_path not in _logged_skill_presentation_resolutions:
                unrealsdk.logging.info(
                    f"[MayaRebalance] Resolved {skill_path} UI "
                    "presentation as its only effect presentation"
                )
                _logged_skill_presentation_resolutions.add(skill_path)
            return presentations[0]

        raise ValueError(
            f"Could not find UI presentation {presentation_path}"
            + (
                f" or a presentation for {attribute_path}"
                if attribute_path is not None
                else ""
            )
            + f": {direct_lookup_error}"
        ) from direct_lookup_error


def _set_effect_value(effect: Any, value: float) -> None:
    for field_name in ("BaseModifierValue", "PerGradeUpgrade"):
        modifier_value = copy.copy(getattr(effect, field_name))
        modifier_value.BaseValueConstant = value
        modifier_value.BaseValueAttribute = None
        modifier_value.InitializationDefinition = None
        modifier_value.BaseValueScaleConstant = 1.0
        setattr(effect, field_name, modifier_value)


def _refresh_skill_effect_rank(
    player_controller: Any,
    skill_path: str,
    rank: int,
) -> None:
    global _immolate_buff_expires_at
    global _last_applied_skill_controller_address

    controller_address = player_controller._get_address()
    if controller_address != _last_applied_skill_controller_address:
        _last_applied_skill_ranks.clear()
        _last_applied_skill_controller_address = controller_address

    previous_rank = _last_applied_skill_ranks.get(skill_path, 0)
    if skill_path == SUSPENSION_PATH:
        _sync_suspension_effects(player_controller)
        _last_applied_skill_ranks[skill_path] = rank
        return
    if skill_path == SUSTENANCE_PATH:
        try:
            _sync_sustenance_regeneration(player_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not suppress live Sustenance regeneration: {exc}")
        _last_applied_skill_ranks[skill_path] = rank
        return
    if skill_path == QUICKEN_PATH:
        try:
            _sync_quicken_effects(player_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not preserve Quicken's native effect: {exc}")
        try:
            _sync_quicken_melee_cooldown_modifier(player_controller, rank)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not apply Quicken to Scorn: {exc}")
        _last_applied_skill_ranks[skill_path] = rank
        return
    if skill_path == IMMOLATE_PATH:
        _sync_immolate_native_gate(player_controller, rank)
        _last_applied_skill_ranks[skill_path] = rank
        return

    skill_manager = player_controller.GetSkillManager()
    if skill_manager.bUpdatingSkills:
        return  # Retry later; do not mark a deferred rank as already applied.
    if _last_applied_skill_ranks.get(skill_path) == rank:
        return

    if rank == 0 and previous_rank == 0:
        _last_applied_skill_ranks[skill_path] = rank
        return

    skill_definition = unrealsdk.find_object("SkillDefinition", skill_path)
    active_definitions = [
        active_skill.Definition
        for active_skill in skill_manager.ActiveSkills
        if active_skill.Definition and active_skill.SkillInstigator == player_controller
        and str(active_skill.Definition._path_name()) == skill_path
    ]
    for active_definition in active_definitions:
        skill_manager.DeactivateSkill(player_controller, active_definition)

    if rank > 0:
        skill_manager.ActivateSkill(
            player_controller,
            skill_definition,
            None,
            rank,
        )
    active_after = [
        active_skill
        for active_skill in skill_manager.ActiveSkills
        if active_skill.Definition and active_skill.SkillInstigator == player_controller
        and str(active_skill.Definition._path_name()) == skill_path
    ]
    unrealsdk.logging.info(
        f"[MayaRebalance] DEBUG active: {skill_path}, "
        f"rank={rank}, active_instances={len(active_after)}"
    )
    _last_applied_skill_ranks[skill_path] = rank
    unrealsdk.logging.info(
        f"[MayaRebalance] Reapplied {skill_path} "
        f"at effective rank {rank}"
    )


def _set_skill_effect(
    skill_path: str,
    attribute_path: str,
    value: float,
    attribute_class: str = "AttributeDefinition",
    add_if_missing: bool = False,
) -> None:
    skill_definition = unrealsdk.find_object("SkillDefinition", skill_path)
    effects = list(skill_definition.SkillEffectDefinitions)
    matching_index = next(
        (
            index
            for index, effect in enumerate(effects)
            if _attribute_path(effect) == attribute_path
        ),
        None,
    )

    if matching_index is None:
        if not add_if_missing:
            raise ValueError(
                f"No skill effect for {attribute_path} was found in {skill_path}"
            )
        if not effects:
            raise ValueError(f"No existing skill effect can be copied for {skill_path}")

        matching_effect = copy.copy(effects[0])
        matching_effect.AttributeToModify = unrealsdk.find_object(
            attribute_class,
            attribute_path,
        )
        effects.append(matching_effect)
    else:
        matching_effect = effects[matching_index]

    if matching_index is not None and all(
        abs(
            float(getattr(matching_effect, field_name).BaseValueConstant) - value
        )
        <= 0.000001
        and not getattr(matching_effect, field_name).BaseValueAttribute
        and not getattr(matching_effect, field_name).InitializationDefinition
        and abs(
            float(getattr(matching_effect, field_name).BaseValueScaleConstant) - 1.0
        )
        <= 0.000001
        for field_name in ("BaseModifierValue", "PerGradeUpgrade")
    ):
        return

    # Stable validation needs no reflected copies. If writing, still own EVERY
    # row before replacing the native array; do not retain views into its buffer.
    effects = [copy.copy(effect) for effect in effects]
    matching_effect = effects[matching_index if matching_index is not None else -1]
    _set_effect_value(matching_effect, value)
    skill_definition.SkillEffectDefinitions = effects

    updated_effect = next(
        (
            effect
            for effect in skill_definition.SkillEffectDefinitions
            if _attribute_path(effect) == attribute_path
        ),
        None,
    )
    if updated_effect is None:
        raise ValueError(
            f"{skill_path} did not retain the effect for {attribute_path}"
        )
    for field_name in ("BaseModifierValue", "PerGradeUpgrade"):
        formula = getattr(updated_effect, field_name)
        if not (
            abs(float(formula.BaseValueConstant) - value) <= 0.000001
            and not formula.BaseValueAttribute
            and not formula.InitializationDefinition
            and abs(float(formula.BaseValueScaleConstant) - 1.0) <= 0.000001
        ):
            raise ValueError(
                f"{skill_path} {attribute_path} {field_name} "
                f"did not retain the constant formula {value:g}"
            )
    unrealsdk.logging.info(
        f"[MayaRebalance] DEBUG effect: {skill_path} "
        f"{attribute_path}, ModifierType={updated_effect.ModifierType}, "
        f"EffectTarget={updated_effect.EffectTarget}, "
        f"Base={float(updated_effect.BaseModifierValue.BaseValueConstant):g}, "
        f"PerGrade={float(updated_effect.PerGradeUpgrade.BaseValueConstant):g}"
    )
    unrealsdk.logging.info(
        f"[MayaRebalance] Set {skill_path} {attribute_path} "
        f"to {value:g} per rank"
    )


def _remove_skill_effect(skill_path: str, attribute_path: str) -> None:
    """Remove an effect added by an earlier development version of this mod."""

    skill_definition = unrealsdk.find_object("SkillDefinition", skill_path)
    effects = [
        copy.copy(effect)
        for effect in skill_definition.SkillEffectDefinitions
        if _attribute_path(effect) != attribute_path
    ]
    if len(effects) == len(skill_definition.SkillEffectDefinitions):
        return

    skill_definition.SkillEffectDefinitions = effects
    if any(
        _attribute_path(effect) == attribute_path
        for effect in skill_definition.SkillEffectDefinitions
    ):
        raise ValueError(
            f"{skill_path} retained the obsolete effect for {attribute_path}"
        )
    unrealsdk.logging.info(
        f"[MayaRebalance] Removed obsolete {attribute_path} effect from {skill_path}"
    )


def _modifier_is_in_stack(modifier: Any, modifier_stack: Any) -> bool:
    if not modifier_stack:
        return False  # The usual orphan sweep can inspect six empty native stacks.
    modifier_address = modifier._get_address()
    return any(
        current_modifier
        and current_modifier._get_address() == modifier_address
        for current_modifier in modifier_stack
    )


def _is_vault_hunters_flicker_modifier(modifier: Any) -> bool:
    return bool(
        modifier
        and modifier._path_name().rsplit(".", 1)[-1].startswith("VH_Flicker_")
    )


def _remove_stale_flicker_modifiers(player_controller: Any) -> None:
    """Remove modifiers left behind by a development hot reload."""

    for attribute_path, field_name, _per_rank, _label in (
        FLICKER_DIRECT_DAMAGE_ATTRIBUTES
    ):
        attribute = unrealsdk.find_object("AttributeDefinition", attribute_path)
        modifier_stack = list(
            getattr(player_controller, f"{field_name}ModifierStack")
        )
        for modifier in modifier_stack:
            if _is_vault_hunters_flicker_modifier(modifier):
                attribute.RemoveAttributeModifier(
                    player_controller,
                    modifier,
                    False,
                )


def _sync_flicker_runtime_modifiers(
    player_controller: Any,
    rank: int,
) -> None:
    """Apply Flicker's direct damage through the native attribute API."""

    global _flicker_modifier_controller_address
    global _flicker_runtime_modifier_generation
    global _flicker_runtime_rank

    controller_address = player_controller._get_address()
    if controller_address != _flicker_modifier_controller_address:
        _flicker_runtime_modifiers.clear()
        _flicker_runtime_rank = None
        _remove_stale_flicker_modifiers(player_controller)
        _flicker_modifier_controller_address = controller_address

    rank = max(0, rank)
    needs_refresh = rank != _flicker_runtime_rank
    if not needs_refresh and rank > 0:
        for _attribute_path, field_name, _per_rank, _label in (
            FLICKER_DIRECT_DAMAGE_ATTRIBUTES
        ):
            modifier = _flicker_runtime_modifiers.get(field_name)
            if modifier is None or not _modifier_is_in_stack(
                modifier,
                getattr(player_controller, f"{field_name}ModifierStack"),
            ):
                needs_refresh = True
                break

    if not needs_refresh:
        return

    for attribute_path, field_name, _per_rank, _label in (
        FLICKER_DIRECT_DAMAGE_ATTRIBUTES
    ):
        modifier = _flicker_runtime_modifiers.get(field_name)
        if modifier is None:
            continue

        attribute = unrealsdk.find_object("AttributeDefinition", attribute_path)
        modifier_stack = getattr(
            player_controller,
            f"{field_name}ModifierStack",
        )
        if _modifier_is_in_stack(modifier, modifier_stack):
            attribute.RemoveAttributeModifier(
                player_controller,
                modifier,
                False,
            )
    _flicker_runtime_modifiers.clear()

    applied_values = []
    if rank > 0:
        modifier_type = unrealsdk.find_enum("EModifierType").MT_Scale
        for attribute_path, field_name, per_rank, label in (
            FLICKER_DIRECT_DAMAGE_ATTRIBUTES
        ):
            attribute = unrealsdk.find_object("AttributeDefinition", attribute_path)
            _flicker_runtime_modifier_generation += 1
            modifier = unrealsdk.construct_object(
                "AttributeModifier",
                player_controller,
                (
                    f"VH_Flicker_{label}_{time.monotonic_ns()}_"
                    f"{_flicker_runtime_modifier_generation}"
                ),
            )
            modifier.Type = modifier_type
            modifier.Value = per_rank * rank
            if not attribute.AddAttributeModifier(
                player_controller,
                modifier,
                False,
            ):
                raise ValueError(
                    f"Could not add Flicker modifier for {attribute_path}"
                )

            modifier_stack = getattr(
                player_controller,
                f"{field_name}ModifierStack",
            )
            if not _modifier_is_in_stack(modifier, modifier_stack):
                raise ValueError(
                    f"Flicker modifier was not retained for {attribute_path}"
                )

            _flicker_runtime_modifiers[field_name] = modifier
            applied_values.append(f"{label}={modifier.Value:g}")

    _flicker_runtime_rank = rank
    unrealsdk.logging.info(
        "[MayaRebalance] Synced native Flicker modifiers: "
        f"rank={rank}"
        + (f", {', '.join(applied_values)}" if applied_values else "")
    )


def _log_flicker_runtime_attributes(player_controller: Any, rank: int) -> None:
    attribute_names = (
        "InstigatedIncindiaryDamageModifier",
        "InstigatedShockDamageModifier",
        "InstigatedCorrosiveDamageModifier",
    )
    owners = (
        ("controller", player_controller),
        ("pawn", player_controller.Pawn),
    )

    for owner_name, owner in owners:
        if not owner:
            continue

        values = []
        for attribute_name in attribute_names:
            try:
                value = float(getattr(owner, attribute_name))
                modifier_stack = getattr(owner, f"{attribute_name}ModifierStack")
                values.append(
                    f"{attribute_name}={value:g},stack={len(modifier_stack)}"
                )
            except (AttributeError, TypeError, ValueError):
                continue

        if values:
            unrealsdk.logging.info(
                f"[MayaRebalance] DEBUG Flicker runtime: "
                f"rank={rank}, owner={owner_name}, {', '.join(values)}"
            )


def _zero_skill_effects(
    skill_path: str,
    health_regeneration_only: bool = False,
) -> None:
    skill_definition = unrealsdk.find_object("SkillDefinition", skill_path)
    effects = [
        copy.copy(effect)
        for effect in skill_definition.SkillEffectDefinitions
    ]
    matching_effects = [
        effect
        for effect in effects
        if not health_regeneration_only
        or (
            "health" in _attribute_path(effect).casefold()
            and "regen" in _attribute_path(effect).casefold()
        )
    ]
    if not matching_effects:
        purpose = "health regeneration" if health_regeneration_only else "effects"
        raise ValueError(f"No native {purpose} found in {skill_path}")

    changed_paths = []
    for effect in matching_effects:
        attribute_path = _attribute_path(effect)
        if any(
            abs(float(getattr(effect, field_name).BaseValueConstant)) > 0.000001
            or getattr(effect, field_name).BaseValueAttribute
            or getattr(effect, field_name).InitializationDefinition
            or abs(
                float(getattr(effect, field_name).BaseValueScaleConstant) - 1.0
            )
            > 0.000001
            for field_name in ("BaseModifierValue", "PerGradeUpgrade")
        ):
            _set_effect_value(effect, 0.0)
            changed_paths.append(attribute_path)

    if changed_paths:
        skill_definition.SkillEffectDefinitions = effects
        unrealsdk.logging.info(
            f"[MayaRebalance] Disabled native {skill_path} effect(s): "
            f"{', '.join(changed_paths)}"
        )


def _sync_sustenance_regeneration(player_controller: Any) -> None:
    """Zero only Sustenance's native regen, including already applied snapshots."""
    _zero_skill_effects(SUSTENANCE_PATH, health_regeneration_only=True)
    for skill in player_controller.GetSkillManager().ActiveSkills:
        if str(skill.Definition._path_name()) != SUSTENANCE_PATH:
            continue
        if skill.SkillInstigator != player_controller:
            continue
        effects = [copy.copy(effect) for effect in skill.SkillEffects]
        changed = False
        for applied_effect in effects:
            effect_data = copy.copy(applied_effect.EffectData)
            if _attribute_path(effect_data) != (
                "D_Attributes.HealthResourcePool.HealthPassiveRegenerationRate"
            ):
                continue
            data_matches = all(
                abs(float(value.BaseValueConstant)) <= 0.000001
                and not value.BaseValueAttribute
                and not value.InitializationDefinition
                and abs(float(value.BaseValueScaleConstant) - 1.0) <= 0.000001
                for value in (effect_data.BaseModifierValue, effect_data.PerGradeUpgrade)
            )
            modifier = applied_effect.Modifier
            if data_matches and (not modifier or abs(float(modifier.Value)) <= 0.000001):
                continue
            _set_effect_value(effect_data, 0.0)
            applied_effect.EffectData = effect_data
            changed = True
        if changed:
            # Keep the native Modifier and Contexts; the skill manager updates
            # its own attribute stack on the next tick, as for Suspension.
            skill.SkillEffects = effects
            skill.bForceRefreshModifiersNextTick = True
            unrealsdk.logging.info(
                "[MayaRebalance] Suppressed live Sustenance passive regeneration: "
                f"grade={int(skill.Grade)}, expected_regen=0"
            )


def _set_designer_attribute_value(attribute_path: str, value: float) -> None:
    attribute = unrealsdk.find_object(
        "DesignerAttributeDefinition",
        attribute_path,
    )
    base_value = copy.copy(attribute.BaseValue)
    base_value.BaseValueConstant = value
    base_value.BaseValueAttribute = None
    base_value.InitializationDefinition = None
    base_value.BaseValueScaleConstant = 1.0
    attribute.BaseValue = base_value

    actual_value = float(attribute.BaseValue.BaseValueConstant)
    if abs(actual_value - value) > 0.000001:
        raise ValueError(
            f"{attribute_path} remained {actual_value:g} instead of {value:g}"
        )
    unrealsdk.logging.info(
        f"[MayaRebalance] Set {attribute_path} to "
        f"{actual_value:g} seconds"
    )


def _set_scorn_cooldown() -> None:
    attribute = unrealsdk.find_object(
        "DesignerAttributeDefinition",
        SCORN_COOLDOWN_ATTRIBUTE_PATH,
    )
    if (
        abs(
            float(attribute.BaseValue.BaseValueConstant)
            - SCORN_BASE_COOLDOWN_SECONDS
        )
        <= 0.000001
    ):
        return
    _set_designer_attribute_value(
        SCORN_COOLDOWN_ATTRIBUTE_PATH,
        SCORN_BASE_COOLDOWN_SECONDS,
    )


def _configure_scorn_description() -> None:
    definition = unrealsdk.find_object("SkillDefinition", SCORN_PATH)
    if definition is None:
        raise ValueError("Scorn definition is unavailable")
    description = str(definition.SkillDescription).replace(SCORN_STATUS_DESCRIPTION_SUFFIX, "")
    expected = description + SCORN_STATUS_DESCRIPTION_SUFFIX
    if definition.SkillDescription != expected:
        definition.SkillDescription = expected
    if definition.SkillDescription != expected:
        raise ValueError("Scorn did not retain its passive-duration description")


def _sync_scorn_cooldown(player_controller: Any, pool: Any) -> None:
    """Repair the instantiated designer attribute AND the already-created pool."""
    _set_scorn_cooldown()
    attribute = unrealsdk.find_object("DesignerAttributeDefinition", SCORN_COOLDOWN_ATTRIBUTE_PATH)
    previous_max, remaining = float(pool.MaxValue), float(pool.CurrentValue)
    changed = False
    # A pool may resolve its designer attributes through its associated provider.
    # Never retain either actor/context across world transitions.
    sources = [player_controller]
    if pool.AssociatedProvider and pool.AssociatedProvider != player_controller:
        sources.append(pool.AssociatedProvider)
    instance: Any = None
    for source in sources:
        instance = attribute.ResolveContext(source)
        if not instance:
            return  # Still streaming; retry on the next maintenance pass.
        if abs(float(instance.ValueBaseValue) - SCORN_BASE_COOLDOWN_SECONDS) > 0.000001:
            if not attribute.SetAttributeBaseValue(source, SCORN_BASE_COOLDOWN_SECONDS, False):
                raise ValueError("Scorn's live designer attribute rejected its 12-second base")
            if abs(float(instance.ValueBaseValue) - SCORN_BASE_COOLDOWN_SECONDS) > 0.000001:
                raise ValueError("Scorn's live designer attribute retained its previous base")
            changed = True
    if instance is None:
        return
    expected_max_base = float(instance.Value)
    # Recalculate without calling Reinitialize/ClearAttributeModifierStacks.
    if abs(float(pool.MaxValueBaseValue) - expected_max_base) > 0.000001:
        pool.CalculateBaseValues(False)
        changed = True
    if abs(float(pool.MaxValueBaseValue) - expected_max_base) > 0.000001:
        raise ValueError("Scorn's resource pool retained its cached cooldown base")
    if not changed:
        return
    # Preserve cooldown progress instead of refilling it on a respec/repair.
    progress = remaining / previous_max if previous_max > 0.0 else 0.0
    pool.SetCurrentValue(max(0.0, min(1.0, progress)) * float(pool.MaxValue))
    unrealsdk.logging.info(
        "[MayaRebalance] Repaired live Scorn cooldown base: "
        f"pool_max={previous_max:g}->{float(pool.MaxValue):g}, "
        f"remaining={remaining:g}->{float(pool.CurrentValue):g}"
    )


def _phaselock_health_constraint(constraints: Any) -> Any | None:
    for constraint in constraints:
        evaluator = constraint.Evaluator
        if evaluator and str(evaluator._path_name()) == PHASELOCK_HEALTH_EVALUATOR_PATH:
            return constraint
    return None


def _phaselock_tuning_matches() -> bool:
    duration_attribute = unrealsdk.find_object(
        "DesignerAttributeDefinition",
        PHASELOCK_DURATION_ATTRIBUTE_PATH,
    )
    if abs(
        float(duration_attribute.BaseValue.BaseValueConstant)
        - PHASELOCK_BASE_DURATION_SECONDS
    ) > 0.000001:
        return False

    base_delay = unrealsdk.find_object("Behavior_Delay", PHASELOCK_BASE_DELAY_PATH)
    if abs(float(base_delay.Delay) - PHASELOCK_BASE_DURATION_SECONDS) > 0.000001:
        return False

    skill_definition = unrealsdk.find_object("SkillDefinition", PHASELOCK_PATH)
    health_constraint = _phaselock_health_constraint(
        skill_definition.SkillConstraints
    )
    return bool(
        health_constraint
        and not health_constraint.bApplyConstraintWhileActive
        and health_constraint.bApplyConstraintOnActivatation
    )


def _configure_phaselock_base() -> None:
    """Configure static Phaselock data and preserve it through FFYL."""

    # The vanilla dump gives this attribute BaseValueConstant=5. The
    # LiftActionSkill.LockDurationFormula reads it directly. Existing pawns
    # cache a separate InstancedDesignerAttribute: update those below too.
    _set_designer_attribute_value(
        PHASELOCK_DURATION_ATTRIBUTE_PATH,
        PHASELOCK_BASE_DURATION_SECONDS,
    )

    base_delay = unrealsdk.find_object("Behavior_Delay", PHASELOCK_BASE_DELAY_PATH)
    base_delay.Delay = PHASELOCK_BASE_DURATION_SECONDS
    if abs(float(base_delay.Delay) - PHASELOCK_BASE_DURATION_SECONDS) > 0.000001:
        raise ValueError("Phaselock behavior delay did not retain 7 seconds")

    configured_definitions = []
    for skill_path, constraint_required in (
        (PHASELOCK_PATH, True),
        (PHASELOCK_COOLDOWN_MANAGER_PATH, False),
    ):
        skill_definition = unrealsdk.find_object("SkillDefinition", skill_path)
        constraints = [
            copy.copy(constraint)
            for constraint in skill_definition.SkillConstraints
        ]
        health_constraint = _phaselock_health_constraint(constraints)
        if health_constraint is None:
            if constraint_required:
                raise ValueError("Phaselock health-state constraint was not found")
            continue

        # Keep the vanilla activation check, but do not deactivate an already
        # running Phaselock when Maya enters Fight For Your Life.
        health_constraint.bApplyConstraintWhileActive = False
        skill_definition.SkillConstraints = constraints

        retained_constraint = _phaselock_health_constraint(
            skill_definition.SkillConstraints
        )
        if retained_constraint is None or bool(
            retained_constraint.bApplyConstraintWhileActive
        ):
            raise ValueError(
                f"{skill_path} retained its active FFYL constraint"
            )
        configured_definitions.append(skill_path.rsplit(".", 1)[-1])

    unrealsdk.logging.info(
        "[MayaRebalance] Configured Phaselock: "
        f"base duration={PHASELOCK_BASE_DURATION_SECONDS:g}, "
        f"base delay={float(base_delay.Delay):g}, "
        "active FFYL constraint disabled on "
        + ", ".join(configured_definitions)
    )


def _sync_phaselock_duration(player_controller: Any) -> None:
    """Refresh the pawn's cached base without replacing skill modifiers."""
    # Pawn is the vehicle while driving; only the character has this attribute.
    pawn = player_controller.GetWillowPlayerPawn()
    if not pawn or pawn.bDeleteMe:
        return
    duration_attribute = unrealsdk.find_object(
        "DesignerAttributeDefinition",
        PHASELOCK_DURATION_ATTRIBUTE_PATH,
    )
    instance = pawn.GetInstancedDesignerAttribute(
        duration_attribute,
        duration_attribute.ValueName,
        duration_attribute.AttributeDataType,
    )
    if not instance:
        raise ValueError("Phaselock duration has no pawn attribute instance")
    # Remove only the superseded development modifier, if it ever existed.
    for modifier in list(instance.ValueModifierStack):
        if modifier and str(modifier.Name) == "VH_Phaselock_BaseDuration":
            duration_attribute.RemoveAttributeModifier(pawn, modifier, False)
    if abs(float(instance.ValueBaseValue) - PHASELOCK_BASE_DURATION_SECONDS) > 0.000001:
        previous_base = float(instance.ValueBaseValue)
        instance.SetBaseValue(copy.copy(duration_attribute.BaseValue), pawn)
        if abs(float(instance.ValueBaseValue) - PHASELOCK_BASE_DURATION_SECONDS) > 0.000001:
            raise ValueError("Phaselock pawn base duration did not retain 7 seconds")
        unrealsdk.logging.info(
            "[MayaRebalance] Updated live Phaselock duration: "
            f"base={previous_base:g}->{float(instance.ValueBaseValue):g}, "
            f"total={float(instance.Value):g} seconds"
        )


def _configure_slagger() -> None:
    """Create a stable-path definition using Sphere's icon; leave the prototype/input intact."""
    global _slagger_definition
    template = unrealsdk.find_object("SkillDefinition", SLAGGER_TEMPLATE_PATH)
    branch = unrealsdk.find_object("Object", SLAGGER_BRANCH_PATH)
    layout = unrealsdk.find_object("Object", SLAGGER_LAYOUT_PATH)
    icon = unrealsdk.find_object("SwfMovie", "SharedSkillIcons_Siren.SkillIcon-Sphere")
    tiers, cells = list(branch.Tiers), list(layout.Tiers)
    if len(tiers) != 6 or len(cells) != 6:
        raise ValueError("Elemental Mastery requires Cataclysm's six-tier layout")
    original = ("GD_Siren_Skills.Cataclysm.Reaper",)
    expected = original + (SLAGGER_PATH,)
    rows = [tuple(str(skill._path_name()) for skill in tier.Skills) for tier in tiers]
    occupied = tuple(bool(value) for value in cells[3].bCellIsOccupied)
    if rows[3] not in (original, expected) or occupied not in ((False, True, False), (False, True, True)):
        raise ValueError("Cataclysm tier 4 is occupied by an incompatible mod layout")
    if any(SLAGGER_PATH in row for index, row in enumerate(rows) if index != 3):
        raise ValueError("Elemental Mastery/Sphere is already assigned to another tier")
    definition = _slagger_definition
    if definition is None:
        try:
            definition = unrealsdk.find_object("SkillDefinition", SLAGGER_PATH)
        except ValueError:
            definition = unrealsdk.construct_object(
                "SkillDefinition", tiers[3].Skills[0].Outer, "MR_Slagger",
                template_obj=template, flags=ObjectFlags.KEEP_ALIVE,
            )
        if str(definition._path_name()) != SLAGGER_PATH:
            raise ValueError("Elemental Mastery's private definition has an unexpected object path")
        _slagger_definition = definition
    for name, value in (
        ("SkillName", "Elemental Mastery"), ("SkillDescription", SLAGGER_DESCRIPTION),
        ("MaxGrade", 1), ("bSubjectToGradeRules", True),
        ("SkillIcon", icon), ("SkillType", unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive),
        ("DurationType", unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite),
        ("InitialDuration", 0.0),
        ("TrackedSkillType", unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked),
        ("BehaviorProviderDefinition", None), ("TrackedActiveSkill", None),
    ):
        if getattr(definition, name) != value:
            setattr(definition, name, value)
    for name in ("SkillConstraints", "SkillEffectDefinitions", "SkillEffectPresentations",
                 "DamageEvents", "KillEvents", "TrackedActiveSkills"):
        if getattr(definition, name):
            setattr(definition, name, [])
    if rows[3] != expected:
        tier = copy.copy(tiers[3])
        tier.Skills = list(tier.Skills) + [definition]
        tiers[3] = tier
        branch.Tiers = tiers
    if occupied != (False, True, True):
        tier = copy.copy(cells[3])
        tier.bCellIsOccupied = [False, True, True]
        cells[3] = tier
        layout.Tiers = cells
    if (tuple(str(skill._path_name()) for skill in branch.Tiers[3].Skills) != expected
            or tuple(bool(value) for value in layout.Tiers[3].bCellIsOccupied) != (False, True, True)):
        raise ValueError("Elemental Mastery's Cataclysm insertion did not retain its values")
    _slagger_definition = definition


@hook("WillowGame.PlayerSkillTree:Initialize", Type.PRE)
def prepare_slagger_tree(_tree: UObject, args: WrappedStruct, _ret: Any, _func: Any) -> None:
    global _slagger_live_tree_context
    if not args.SkillTreeDef or str(args.SkillTreeDef._path_name()).casefold() != SLAGGER_TREE_PATH.casefold():
        return
    _slagger_live_tree_context = None
    try:
        _configure_slagger()
        unrealsdk.logging.info("[MayaRebalance] Elemental Mastery prepared before Maya skill-tree initialization")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not prepare Elemental Mastery before skill-tree initialization: {exc}")


def _check_slagger_live_tree(controller: Any) -> None:
    global _slagger_live_tree_context
    if _slagger_definition is None:
        return
    tree = controller.PlayerSkillTree
    context = (controller._get_address(), tree._get_address())
    if context == _slagger_live_tree_context:
        return
    present = any(item.Definition == _slagger_definition for item in tree.Skills)
    _slagger_live_tree_context = context
    if present:
        unrealsdk.logging.info("[MayaRebalance] Elemental Mastery live Cataclysm tree verified: present=True")
    else:
        unrealsdk.logging.info(
            "[MayaRebalance] Elemental Mastery is missing from the current live tree. "
            "Return to the main menu and reload Maya with this mod enabled; no respec is required."
        )


def _kinetic_reflection_footer(native_text: str, general_text: str, include_html: bool) -> str:
    """Deduplicate native rows and replace any general row from an inner query."""
    rows, seen = [], set()
    for row in re.split(r"<br\s*/?>|\r?\n", native_text, flags=re.IGNORECASE):
        plain = re.sub(r"<[^>]*>", "", row).strip()
        key = " ".join(plain.casefold().split())
        if not key or key.startswith("general damage reduction:") or key in seen:
            continue
        seen.add(key)
        rows.append(row.strip() if include_html else plain)
    rows.append(general_text)
    result = ("<br>" if include_html else "\n").join(rows)
    return _color_stat_percentages(result) if include_html else result


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_slagger(_tree: UObject, args: WrappedStruct, _ret: Any, _func: Any) -> tuple[type[Block], str] | None:
    if not args.SkillDef or str(args.SkillDef._path_name()) != SLAGGER_PATH:
        return None
    # Ignore GradeModifier: this is a one-point gamechanger, never a COM-scaled bonus.
    learned = int(args.Grade) > 0
    return Block, _format_percentage_progression(
        "Damage per elemental status", SLAGGER_BONUS * 100, int(learned),
        not learned or not args.bIncludeHTML, show_plus=True,
    )


def _elemental_mastery_status_count(component: Any) -> int:
    if component is None:
        return 0
    if not _slagger_status_type_bits:
        types = unrealsdk.find_enum("EStatusEffectType")
        _slagger_status_type_bits.update({value: 1 << index for index, value in enumerate((
            int(types.STATUS_EFFECT_Ignite), int(types.STATUS_EFFECT_Shock),
            int(types.STATUS_EFFECT_Corrosive), int(types.STATUS_EFFECT_Amp),
        ))})  # Enum integers only; never cache actors, status arrays or their counts.
    active = 0
    for effect in component.ActiveStatusEffects:
        definition = effect.StatusEffectDefinition
        if not definition:
            continue
        bit = _slagger_status_type_bits.get(int(definition.StatusEffectType), 0)
        if (bit and not active & bit and (definition.bIsInfiniteDuration
                or float(effect.TotalElapsedTime) < float(effect.Duration))):
            active |= bit
            if active.bit_count() == 4:
                break
    return active.bit_count()


def _received_damage_attribute(field: str, outer: Any) -> Any:
    """Reuse loaded leaves; an unloaded leaf gets its own private property resolver."""
    attribute = _slagger_received_attributes.get(field)
    if attribute is not None:
        return attribute
    if field not in SLAGGER_RECEIVED_FIELDS:
        raise ValueError(f"Unsupported received-damage field: {field}")
    try:
        attribute = unrealsdk.find_object("AttributeDefinition", f"D_Attributes.DamageSourceModifiers.{field}")
    except ValueError:
        # These six Controller float fields are verified in the native dump.
        # Their data-package definitions are not necessarily loaded together.
        template = unrealsdk.find_object(
            "AttributeDefinition", "D_Attributes.DamageSourceModifiers.ReceivedBulletDamageModifier",
        )
        attribute = unrealsdk.construct_object(
            "AttributeDefinition", outer, f"MR_Received_{field}",
            template_obj=template, flags=ObjectFlags.KEEP_ALIVE,
        )
        resolver = unrealsdk.construct_object(
            "ObjectPropertyAttributeValueResolver", attribute, "ReceivedDamageValue",
            template_obj=template.ValueResolverChain[0], flags=ObjectFlags.KEEP_ALIVE,
        )
        resolver.PropertyName = field
        resolver.CachedProperty = None
        attribute.ValueResolverChain = [resolver]
        if (len(attribute.ValueResolverChain) != 1
                or str(attribute.ValueResolverChain[0].PropertyName) != field):
            raise ValueError(f"Private received-damage resolver was not retained: {field}")
        unrealsdk.logging.info(f"[MayaRebalance] Private received-damage attribute prepared: field={field}")
    _slagger_received_attributes[field] = attribute
    return attribute


def _elemental_mastery_modifiers(depth: int, source: Any = None) -> tuple[tuple[str, Any, Any], ...]:
    rows = _slagger_modifier_pool.get(depth)
    if rows is None:
        # Prepare every leaf before constructing modifiers, including unloaded ones.
        outer = _slagger_definition
        if outer is None:
            outer = unrealsdk.find_object("SkillDefinition", THOUGHTLOCK_PATH)
        attributes = [(field, _received_damage_attribute(field, outer)) for field in SLAGGER_RECEIVED_FIELDS]
        rows = tuple((field, attribute, unrealsdk.construct_object(
            "AttributeModifier", outer, f"MR_ElementalMastery_{depth}_{field}",
            flags=ObjectFlags.KEEP_ALIVE)) for field, attribute in attributes)
        for _, _, modifier in rows:
            modifier.Type = unrealsdk.find_enum("EModifierType").MT_PostAdd
        _slagger_modifier_pool[depth] = rows
    if source is not None:
        field = SLAGGER_SOURCE_FIELDS.get(str(source._path_name()))
        if field is not None:
            selected = tuple(row for row in rows if row[0] == field)
            if len(selected) == 1:
                return selected
    return rows


def _set_slagger_scope_active(scope: dict[str, Any], active: bool) -> None:
    """Temporary source multipliers work without requiring the native slag flag."""
    recipient = scope["recipient"]
    scope["added"] = False
    if not recipient or recipient.bDeleteMe:
        return
    errors = []
    for field, attribute, modifier in scope["modifiers"]:
        try:
            stack_name = field + "ModifierStack"
            present = _modifier_is_in_stack(modifier, getattr(recipient, stack_name))
            if active and not present:
                before = float(getattr(recipient, field))
                if not 0.0 < before < float("inf"):
                    continue  # Preserve zero/invalid native damage factors.
                if attribute.ResolveContext(recipient) != recipient:
                    raise ValueError(f"Elemental Mastery context mismatch for {field}")
                modifier.Value = before * scope["bonus"]
                added = attribute.AddAttributeModifier(recipient, modifier, False)
                present = _modifier_is_in_stack(modifier, getattr(recipient, stack_name))
                scope["added"] |= present
                if not added or not present:
                    raise ValueError(f"Elemental Mastery modifier rejected for {field}")
                actual = float(getattr(recipient, field))
                if (not 0.0 <= actual < float("inf")
                        or abs(actual - before * (1.0 + scope["bonus"])) > max(.00001, abs(before) * .00001)):
                    raise ValueError(f"Elemental Mastery native multiplier mismatch for {field}")
            elif not active and present:
                attribute.RemoveAttributeModifier(recipient, modifier, False)
                if _modifier_is_in_stack(modifier, getattr(recipient, stack_name)):
                    raise ValueError(f"Elemental Mastery modifier was not removed for {field}")
            elif active:
                scope["added"] = True
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            errors.append(str(exc))
    if errors:
        scope["added"] = True  # A partial preparation still owes cleanup.
        raise ValueError("; ".join(errors))


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.PRE)
def begin_slagger_damage(pipeline: UObject, args: WrappedStruct, _ret: Any, _func: Any) -> None:
    """Compose Elemental Mastery/Thoughtlock once per native damage source."""
    scope: dict[str, Any] = {"pipeline": pipeline._get_address(), "recipient": None,
                             "added": False, "parent": None, "modifiers": (), "bonus": 0.0}
    _slagger_damage_scopes.append(scope)
    if _cooldown_hud_suspended:
        return  # Do not inspect actors while the old controller/world is being destroyed.
    try:
        target = args.InDamagedActor
        if not target or target.bDeleteMe:
            return  # Do not resolve a controller through a departing/deleted target.
        recipient = getattr(target, "Controller", None) if target else None
        if recipient is None:
            return
        scope["recipient"] = recipient
        # A nested hit from another attacker must not inherit the outer hit's buff.
        for parent in reversed(_slagger_damage_scopes[:-1]):
            if parent["added"] and parent["recipient"] == recipient:
                scope["parent"] = parent
                _set_slagger_scope_active(parent, False)
                break
        depth = len(_slagger_damage_scopes) - 1
        scope["modifiers"] = _slagger_modifier_pool.get(depth, ())
        if scope["modifiers"]:
            _set_slagger_scope_active(scope, False)  # Repair interrupted callbacks at this depth.
        controller = args.InDamageInstigator
        if (_cooldown_hud_suspended or not controller or controller.bDeleteMe
                or target.bDeleteMe or recipient.bDeleteMe
                or int(getattr(controller, "Role", 0)) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
            return
        damage = float(args.IncomingDamage)
        if not 0.0 < damage < float("inf"):
            return
        damage_type = pipeline.GetDamageTypeDef()
        if (damage_type is None or damage_type.IsHealingDamageType()
                or _is_immolate_extra_hit(pipeline, args)):
            return  # Immolate already inherits the boosted source hit's final damage.
        thoughtlock_factor, count = _thoughtlock_hit_factor(target, controller), 0
        factor = thoughtlock_factor
        pawn = controller.Pawn
        if (_slagger_definition is not None and getattr(controller, "PlayerClass", None)
                and _is_maya_controller(controller) and pawn and not pawn.bDeleteMe and target != pawn
                and int(controller.GetSkillGrade(_slagger_definition)) > 0
                and hasattr(target, "GetOpinion")
                and int(target.GetOpinion(pawn)) == int(unrealsdk.find_enum("EOpinion").OPINION_Enemy)):
            count = _elemental_mastery_status_count(target.GetStatusEffectsComponent())
            factor *= 1.0 + SLAGGER_BONUS * count
        if factor == 1.0 or depth >= 16:
            return
        scope["bonus"] = factor - 1.0
        scope["modifiers"] = _elemental_mastery_modifiers(depth, getattr(args, "InDamageSource", None))
        _set_slagger_scope_active(scope, True)
        if scope["added"] and thoughtlock_factor != 1.0 and thoughtlock_factor not in _thoughtlock_damage_logged:
            _thoughtlock_damage_logged.add(thoughtlock_factor)
            unrealsdk.logging.info(
                f"[MayaRebalance] Thoughtlock native damage factor: factor={thoughtlock_factor:g}, "
                f"combined_factor={factor:g}, elemental_statuses={count}"
            )
        if scope["added"] and count and count not in _slagger_logged_amplification:
            _slagger_logged_amplification.add(count)
            unrealsdk.logging.info(
                f"[MayaRebalance] Elemental Mastery native vulnerability: statuses={count}, "
                f"damage_bonus={SLAGGER_BONUS * count:g}, includes_slag=True"
            )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        # If preparation only partially succeeded, remove our contribution now.
        try:
            if scope["added"]:
                _set_slagger_scope_active(scope, False)
        except (AttributeError, TypeError, ValueError, RuntimeError) as cleanup_exc:
            _log_error_once(f"Could not roll back received-damage modifiers: {cleanup_exc}")
        finally:
            _log_error_once(f"Could not prepare received-damage modifiers: {exc}")


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.POST_UNCONDITIONAL)
def finish_slagger_damage(pipeline: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    if not _slagger_damage_scopes:
        return
    scope = _slagger_damage_scopes.pop()
    if _cooldown_hud_suspended:
        # PRE travel/destroy has already suspended gameplay. Never dereference
        # an actor retained by the unfinished hit after its world was torn down.
        scope["added"] = False
        return
    try:
        if scope["added"]:
            _set_slagger_scope_active(scope, False)
        if scope["pipeline"] != pipeline._get_address():
            _log_error_once("Received-damage modifier hooks were not paired")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not clean up received-damage modifiers: {exc}")
    finally:
        if scope["parent"] is not None:
            try:
                _set_slagger_scope_active(scope["parent"], True)
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _log_error_once(f"Could not restore enclosing received-damage modifiers: {exc}")


def _get_wreck_passive_definition(definition: Any) -> Any:
    """Reuse native weapon contexts without inheriting Wreck's Phaselock gate or HUD icon."""
    global _wreck_passive_definition
    if _wreck_passive_definition is None:
        passive = unrealsdk.construct_object(
            "SkillDefinition", definition, "MR_Wreck_Passive",
            flags=ObjectFlags.KEEP_ALIVE, template_obj=definition,
        )
        effects = []
        for path, value in (
            ("D_Attributes.Weapon.WeaponFireInterval", WRECK_FIRE_INTERVAL_PER_RANK),
            ("D_Attributes.Weapon.WeaponDamage", WRECK_WEAPON_DAMAGE_PER_RANK),
        ):
            effect = next((copy.copy(effect) for effect in definition.SkillEffectDefinitions
                           if _attribute_path(effect) == path), None)
            if effect is None:
                raise ValueError(f"Wreck is missing its native effect for {path}")
            _set_effect_value(effect, value)
            effects.append(effect)
        passive.SkillEffectDefinitions = effects
        passive.SkillConstraints = [
            copy.copy(constraint) for constraint in definition.SkillConstraints
            if not (constraint.Evaluator and str(constraint.Evaluator._path_name())
                    == f"{WRECK_PATH}:AttributeExpressionEvaluator_20")
        ]
        passive.SkillName = "Wreck - passive bonus"
        passive.SkillDescription = ""
        passive.SkillEffectPresentations = []
        passive.DamageEvents = []
        passive.BehaviorProviderDefinition = None
        passive.TrackedActiveSkill = None
        passive.TrackedActiveSkills = []
        passive.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked
        passive.bSubjectToGradeRules = False
        _wreck_passive_definition = passive
    return _wreck_passive_definition


def _sync_wreck_effects(controller: Any) -> None:
    """Leave vanilla Wreck's lifetime to the tree; manage only our passive companion."""
    global _wreck_passive_request
    manager = controller.GetSkillManager()
    if manager.bUpdatingSkills:
        return  # Never mutate the manager's lists during its native update loop.
    definition = unrealsdk.find_object("SkillDefinition", WRECK_PATH)
    _set_skill_effect(WRECK_PATH, "D_Attributes.Weapon.WeaponFireInterval", WRECK_FIRE_INTERVAL_PER_RANK)
    _set_skill_effect(WRECK_PATH, "D_Attributes.Weapon.WeaponDamage", WRECK_WEAPON_DAMAGE_PER_RANK)
    if definition.SkillDescription != WRECK_DESCRIPTION:
        definition.SkillDescription = WRECK_DESCRIPTION
    rank = _skill_rank(controller, WRECK_PATH)
    definitions = [definition]
    if rank > 0 or _wreck_passive_definition is not None:
        definitions.append(_get_wreck_passive_definition(definition))
    for current in definitions:
        instances = [skill for skill in manager.ActiveSkills
                     if skill.Definition == current and skill.SkillInstigator == controller]
        conditional = current == definition
        request = None
        if not conditional:
            pawn = controller.Pawn
            request = (controller._get_address(), manager._get_address(),
                       pawn._get_address() if pawn else 0, rank)
        # Multiple native entries are not a request to destroy/rebuild the skill.
        # Paused/deferred conditional Wreck may also be absent from ActiveSkills.
        for skill in (instances if rank > 0 else ()):
            if not conditional and int(skill.Grade) != rank:
                skill.UpdateGrade(rank)
            effects = [copy.copy(effect) for effect in skill.SkillEffects]
            changed = False
            for applied in effects:
                path = _attribute_path(applied.EffectData)
                value = {
                    "D_Attributes.Weapon.WeaponFireInterval": WRECK_FIRE_INTERVAL_PER_RANK,
                    "D_Attributes.Weapon.WeaponDamage": WRECK_WEAPON_DAMAGE_PER_RANK,
                }.get(path)
                if value is None:
                    continue
                if all(
                    abs(float(getattr(applied.EffectData, field).BaseValueConstant) - value) <= 0.000001
                    and not getattr(applied.EffectData, field).BaseValueAttribute
                    and not getattr(applied.EffectData, field).InitializationDefinition
                    and abs(float(getattr(applied.EffectData, field).BaseValueScaleConstant) - 1.0) <= 0.000001
                    for field in ("BaseModifierValue", "PerGradeUpgrade")
                ):
                    continue
                data = copy.copy(applied.EffectData)
                _set_effect_value(data, value)
                applied.EffectData = data
                changed = True
            if changed:
                skill.SkillEffects = effects
                skill.bForceRefreshModifiersNextTick = True
                unrealsdk.logging.info(
                    f"[MayaRebalance] Refreshed Wreck native half: skill={current.SkillName}, rank={rank}"
                )
        if conditional:
            continue  # No ActivateSkill/DeactivateSkill/UpdateGrade for vanilla Wreck.
        if rank <= 0:
            _wreck_passive_request = None
            if instances or manager.IsSkillActive(controller, current) or manager.IsSkillPaused(controller, current):
                manager.DeactivateSkill(controller, current)  # Our helper only, once per respec.
            continue
        if instances or manager.IsSkillActive(controller, current) or manager.IsSkillPaused(controller, current):
            _wreck_passive_request = request
            continue
        if _wreck_passive_request == request:
            continue  # An activation already requested/deferred in this world must not be duplicated.
        _wreck_passive_request = request
        if manager.ActivateSkill(controller, current, None, rank) is False:
            _wreck_passive_request = None
            raise ValueError(f"Wreck native bonus was rejected: {current.SkillName}")
        unrealsdk.logging.info(
            f"[MayaRebalance] Wreck native half registered: skill={current.SkillName}, "
            f"rank={rank}, conditional=False"
        )


def _sync_suspension_effects(player_controller: Any) -> None:
    """Update the native skill's cached effect data, retaining its contexts."""
    for skill in player_controller.GetSkillManager().ActiveSkills:
        if str(skill.Definition._path_name()) != SUSPENSION_PATH:
            continue
        if skill.SkillInstigator != player_controller:
            continue
        effects = [copy.copy(effect) for effect in skill.SkillEffects]
        changed = False
        for applied_effect in effects:
            effect_data = copy.copy(applied_effect.EffectData)
            if _attribute_path(effect_data) != PHASELOCK_DURATION_ATTRIBUTE_PATH:
                continue
            data_matches = all(
                abs(float(getattr(effect_data, field).BaseValueConstant)
                    - SUSPENSION_DURATION_PER_RANK) <= 0.000001
                for field in ("BaseModifierValue", "PerGradeUpgrade")
            )
            # Modifier.Value is managed by the native tick/context. Do not
            # repeatedly rewrite correct input data while awaiting its output.
            if data_matches:
                continue
            _set_effect_value(effect_data, SUSPENSION_DURATION_PER_RANK)
            applied_effect.EffectData = effect_data
            changed = True
        if changed:
            # SkillEffects contains a snapshot made by BuildSkillEffects.
            # Editing SkillDefinition alone leaves the old 0.5-second values
            # here. Retain the native Modifier and Contexts, then let the skill
            # manager recalculate using the current Grade on its next tick.
            skill.SkillEffects = effects
            skill.bForceRefreshModifiersNextTick = True
            unrealsdk.logging.info(
                "[MayaRebalance] Refreshed cached Suspension effects: "
                f"grade={int(skill.Grade)}, "
                f"expected_bonus={SUSPENSION_DURATION_PER_RANK * int(skill.Grade):g} seconds"
            )


def _sync_quicken_effects(player_controller: Any) -> None:
    """Preserve Quicken at 10% per rank without rebuilding the live skill."""

    manager = player_controller.GetSkillManager()
    if manager is None or getattr(manager, "bUpdatingSkills", False):
        return  # Do not replace snapshots while the native manager is iterating.
    _remove_skill_effect(QUICKEN_PATH, MELEE_SKILL_COOLDOWN_RATE_ATTRIBUTE_PATH)
    _set_skill_effect(
        QUICKEN_PATH,
        ACTION_SKILL_COOLDOWN_RATE_ATTRIBUTE_PATH,
        QUICKEN_COOLDOWN_RATE_PER_RANK,
    )

    for skill in list(manager.ActiveSkills):
        if skill is None or skill.SkillInstigator != player_controller or skill.Definition is None:
            continue
        if str(skill.Definition._path_name()) != QUICKEN_PATH:
            continue

        effects = [copy.copy(effect) for effect in skill.SkillEffects]
        changed = False
        cleaned_legacy_melee_effect = False
        for applied_effect in effects:
            effect_data = copy.copy(applied_effect.EffectData)
            attribute_path = _attribute_path(effect_data)
            if attribute_path == ACTION_SKILL_COOLDOWN_RATE_ATTRIBUTE_PATH:
                expected_value = QUICKEN_COOLDOWN_RATE_PER_RANK
            elif attribute_path == MELEE_SKILL_COOLDOWN_RATE_ATTRIBUTE_PATH:
                # Older development builds injected this effect directly into
                # Quicken. Neutralize its live snapshot to prevent double-counting
                # with the dedicated runtime modifier below.
                expected_value = 0.0
                cleaned_legacy_melee_effect = True
            else:
                continue
            data_matches = all(
                abs(float(getattr(effect_data, field).BaseValueConstant)
                    - expected_value) <= 0.000001
                and getattr(effect_data, field).BaseValueAttribute is None
                and getattr(effect_data, field).InitializationDefinition is None
                and abs(float(getattr(effect_data, field).BaseValueScaleConstant) - 1.0) <= 0.000001
                for field in ("BaseModifierValue", "PerGradeUpgrade")
            )
            # Modifier.Value is an output owned by the native context/tick.
            # Correct inputs must not be rewritten while that output settles.
            if data_matches:
                continue
            _set_effect_value(effect_data, expected_value)
            applied_effect.EffectData = effect_data
            changed = True
        if changed:
            skill.SkillEffects = effects
            skill.bForceRefreshModifiersNextTick = True
            unrealsdk.logging.info(
                "[MayaRebalance] Refreshed cached Quicken action-skill effect: "
                f"grade={int(skill.Grade)}, "
                f"expected_rate={QUICKEN_COOLDOWN_RATE_PER_RANK * int(skill.Grade):g}, "
                f"cleaned_legacy_melee_effect={cleaned_legacy_melee_effect}"
            )


def _sync_quicken_melee_cooldown_modifier(
    player_controller: Any,
    rank: int,
) -> None:
    """Apply Quicken to the native melee-override cooldown used by Scorn."""

    global _quicken_melee_modifier_controller_address
    global _quicken_melee_modifier_generation
    global _quicken_melee_runtime_modifier
    global _quicken_melee_runtime_rank
    global _quicken_melee_runtime_pool

    cooldown_attribute = unrealsdk.find_object(
        "AttributeDefinition",
        MELEE_SKILL_COOLDOWN_RATE_ATTRIBUTE_PATH,
    )
    # AddAttributeModifier takes an already resolved Context, unlike GetValue
    # and SetAttributeBaseValue, which take a ContextSource. The native resolver
    # maps the controller to ResourcePool.ConsumptionRate.
    pool = cooldown_attribute.ResolveContext(player_controller)
    if not pool:
        return  # Resource pools may not exist yet while loading a character.
    expected_pool = player_controller.MeleeSkillCooldownPool.Data
    if not expected_pool or pool._get_address() != expected_pool._get_address():
        raise ValueError("Quicken resolved a different pool from MeleeSkillCooldownPool.Data")

    # Definition tuning alone left this live resource at 18 in the user's log.
    # Do this before the unchanged-rank fast path, including Quicken rank zero.
    _sync_scorn_cooldown(player_controller, pool)

    controller_address = player_controller._get_address()
    pool_changed = (
        _quicken_melee_runtime_pool is None
        or pool._get_address() != _quicken_melee_runtime_pool._get_address()
    )
    if controller_address != _quicken_melee_modifier_controller_address or pool_changed:
        _quicken_melee_runtime_modifier = None
        _quicken_melee_runtime_rank = None
        _quicken_melee_modifier_controller_address = controller_address
        _quicken_melee_runtime_pool = pool
        # Remove only our own modifiers after a development hot reload.
        for stale_modifier in list(pool.ConsumptionRateModifierStack):
            if stale_modifier and stale_modifier._path_name().rsplit(".", 1)[-1].startswith(
                "VH_Quicken_ScornCooldown_"
            ):
                if not cooldown_attribute.RemoveAttributeModifier(pool, stale_modifier, False):
                    raise ValueError("Could not remove stale Quicken Scorn cooldown modifier")

    rank = max(0, rank)
    if rank == _quicken_melee_runtime_rank and (
        rank == 0 or (
            _quicken_melee_runtime_modifier is not None
            and _modifier_is_in_stack(
                _quicken_melee_runtime_modifier, pool.ConsumptionRateModifierStack
            )
        )
    ):
        return

    if _quicken_melee_runtime_modifier is not None and _modifier_is_in_stack(
        _quicken_melee_runtime_modifier, pool.ConsumptionRateModifierStack
    ):
        if not cooldown_attribute.RemoveAttributeModifier(
            pool,
            _quicken_melee_runtime_modifier,
            False,
        ):
            raise ValueError("Could not remove Quicken's Scorn cooldown modifier")
    _quicken_melee_runtime_modifier = None

    applied_value = 0.0
    if rank > 0:
        _quicken_melee_modifier_generation += 1
        modifier = unrealsdk.construct_object(
            "AttributeModifier",
            pool,
            (
                f"VH_Quicken_ScornCooldown_{time.monotonic_ns()}_"
                f"{_quicken_melee_modifier_generation}"
            ),
        )
        modifier.Type = unrealsdk.find_enum("EModifierType").MT_Scale
        modifier.Value = QUICKEN_COOLDOWN_RATE_PER_RANK * rank
        if not cooldown_attribute.AddAttributeModifier(
            pool,
            modifier,
            False,
        ):
            raise ValueError("Could not add Quicken's Scorn cooldown modifier")
        _quicken_melee_runtime_modifier = modifier
        if not _modifier_is_in_stack(modifier, pool.ConsumptionRateModifierStack):
            raise ValueError("Quicken Scorn modifier was not retained in the resource pool")
        applied_value = modifier.Value

    _quicken_melee_runtime_rank = rank
    unrealsdk.logging.info(
        "[MayaRebalance] Synced native Quicken Scorn cooldown modifier: "
        f"rank={rank}, value={applied_value:g}, pool={pool._path_name()}, "
        f"consumption_rate={float(pool.ConsumptionRate):g}, "
        f"pool_max={float(pool.MaxValue):g}"
    )


@hook("WillowGame.WillowPlayerController:StartMeleeSkillCooldown", Type.POST)
def log_scorn_cooldown_started(
    controller: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    if _cooldown_hud_suspended or controller != get_pc():
        return
    try:
        if _skill_rank(controller, SCORN_PATH) <= 0:
            return
        _sync_quicken_melee_cooldown_modifier(controller, _skill_rank(controller, QUICKEN_PATH))
        pool = controller.MeleeSkillCooldownPool.Data
        if not pool:
            return
        rate = float(pool.ConsumptionRate)
        remaining = float(pool.CurrentValue)
        unrealsdk.logging.info(
            "[MayaRebalance] Scorn cooldown started: "
            f"current={remaining:g}, consumption_rate={rate:g}, "
            f"estimated_seconds={remaining / rate if rate > 0 else -1:g}"
        )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not inspect Scorn cooldown resource: {exc}")


@hook("WillowGame.LiftActionSkill:OnActionSkillStarted", Type.PRE)
def prepare_phaselock_duration(
    _action_skill: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    controller = get_pc()
    if not controller or not args.TheController:
        return
    if controller._get_address() != args.TheController._get_address():
        return
    try:
        # Must precede native OnActionSkillStarted: the action initializes its
        # Ruin state from this definition, not from a later POST repair.
        _prepare_ruin_level_damage(controller, _action_skill)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not prepare Ruin before native Phaselock initialization: {exc}")
    try:
        if not _phaselock_tuning_matches():
            _configure_phaselock_base()
        _sync_phaselock_duration(controller)
        _sync_suspension_effects(controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not prepare live Phaselock duration: {exc}")


def _configure_immolate_native_trigger() -> None:
    """Detach native damage delivery; never rewrite the original behavior graph."""
    global _immolate_fire_type, _immolate_gun_sources, _immolate_skill_source
    definition = unrealsdk.find_object("SkillDefinition", IMMOLATE_PATH)
    definition.SkillType = unrealsdk.find_enum("ESkillType").SKILL_TYPE_Passive
    definition.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Untracked
    definition.TrackedSkillHUDSlot = 0
    if definition.DamageEvents:
        definition.DamageEvents = []
    if definition.BehaviorProviderDefinition is not None:
        definition.BehaviorProviderDefinition = None
    if definition.DamageEvents or definition.BehaviorProviderDefinition is not None:
        raise ValueError("Immolate native damage delivery was not detached")
    if _immolate_fire_type is None:
        _immolate_fire_type = unrealsdk.find_object("WillowDamageTypeDefinition", IMMOLATE_IMPACT_DAMAGE_TYPE_PATH)
    if not _immolate_gun_sources:
        _immolate_gun_sources = tuple(unrealsdk.find_class(name) for name in (
            "WillowDmgSource_Bullet", "WillowDmgSource_Rocket",
        ))
    if _immolate_skill_source is None:
        _immolate_skill_source = unrealsdk.find_class("WillowDmgSource_Skill")


def _sync_immolate_native_gate(player_controller: Any, rank: int) -> None:
    """Maintain the window/HUD only; no native damage sequence is enabled."""
    global _immolate_buff_expires_at
    if (rank <= 0 or player_controller._get_address() != _immolate_buff_controller_address
            or time.monotonic() >= _immolate_buff_expires_at):
        _immolate_buff_expires_at = 0.0
        if _immolate_hud_native_active:
            _stop_immolate_hud_indicator(player_controller)


def _get_immolate_hud_feedback() -> Any:
    """Make a visual-only leaf from the loaded skill, not an optional asset."""

    global _immolate_hud_feedback

    if _immolate_hud_feedback is not None:
        return _immolate_hud_feedback

    immolate = unrealsdk.find_object("SkillDefinition", IMMOLATE_PATH)
    feedback = unrealsdk.construct_object(
        "SkillDefinition",
        immolate,
        "VH_Immolate_HUD_Feedback",
        flags=int(ObjectFlags.KEEP_ALIVE),
        template_obj=immolate,
    )
    feedback.SkillName = "Immolate buff"
    feedback.SkillIcon = immolate.SkillIcon
    feedback.bSubjectToGradeRules = False
    feedback.TrackedSkillType = (
        unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered
    )
    feedback.TrackedSkillHUDSlot = IMMOLATE_HUD_SLOT
    feedback.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Timed
    feedback.InitialDuration = IMMOLATE_DURATION_SECONDS
    feedback.SkillEffectDefinitions = []
    feedback.SkillEffectPresentations = []
    feedback.SkillConstraints = []
    feedback.BehaviorProviderDefinition = None
    feedback.DamageEvents = []
    feedback.TrackedActiveSkill = None
    feedback.TrackedActiveSkills = []
    immolate.TrackedActiveSkills = list(immolate.TrackedActiveSkills) + [feedback]
    _immolate_hud_feedback = feedback
    unrealsdk.logging.info(
        "[MayaRebalance] Created native Immolate HUD feedback "
        f"with {feedback.SkillIcon._path_name()} in slot {IMMOLATE_HUD_SLOT}"
    )
    return feedback


def _start_immolate_hud_indicator(
    player_controller: Any, rank: int, *, restart: bool = True,
) -> None:
    """Register/retry the native icon without extending the real buff window."""

    global _immolate_hud_native_active
    try:
        remaining = _immolate_buff_expires_at - time.monotonic()
        if rank <= 0 or remaining <= 0.0:
            return
        feedback = _get_immolate_hud_feedback()
        movie = player_controller.GetHUDMovie()
        if not movie or not _prepare_combat_hud_feedback(player_controller, movie, feedback):
            _immolate_hud_native_active = False
            return

        manager = player_controller.GetSkillManager()
        active = bool(manager.IsSkillActive(player_controller, feedback))
        if active and restart:
            manager.DeactivateSkill(player_controller, feedback)
            active = False
        if not active:
            feedback.InitialDuration = remaining
            activated = manager.ActivateSkill(player_controller, feedback, None, rank)
            if activated is False:
                raise ValueError("the native HUD feedback skill was rejected")
        _immolate_hud_native_active = bool(
            manager.IsSkillActive(player_controller, feedback)
        )
        if not _immolate_hud_native_active:
            raise ValueError("the native HUD feedback skill is not active")
        if movie and (not active or not _immolate_hud_icon_is_displayed()):
            movie.UpdateSkillIcons()
        if not active:
            unrealsdk.logging.info(
                "[MayaRebalance] Activated native Immolate HUD icon "
                f"for {remaining:g} seconds in slot {int(feedback.TrackedSkillHUDSlot)}"
            )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _immolate_hud_native_active = False
        _log_error_once(f"Could not activate native Immolate HUD icon: {exc}")


def _stop_immolate_hud_indicator(player_controller: Any) -> None:
    global _immolate_hud_native_active

    try:
        if _immolate_hud_feedback is not None:
            manager = player_controller.GetSkillManager()
            if manager.IsSkillActive(player_controller, _immolate_hud_feedback):
                manager.DeactivateSkill(player_controller, _immolate_hud_feedback)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not stop native Immolate HUD icon: {exc}")
    finally:
        _immolate_hud_native_active = False


def _immolate_hud_icon_is_displayed() -> bool:
    """An active feedback skill is not proof that the HUD drew its icon."""

    if not _immolate_hud_native_active or _immolate_hud_feedback is None:
        return False
    try:
        player_controller = get_pc()
        if not player_controller:
            return False
        movie = player_controller.GetHUDMovie()
        if not movie:
            return False
        icon_path = str(_immolate_hud_feedback.SkillIcon._path_name())
        return any(
            state.Icon and str(state.Icon._path_name()) == icon_path
            for state in movie.CachedTSkillIcon_TrigResp
        )
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return False


def _configure_thoughtlock_duration(definition: Any, controller: Any | None = None) -> None:
    """Change only the duration input, including live snapshots; never restart gameplay."""
    manager = controller.GetSkillManager() if controller is not None else None
    if controller is not None and (manager is None or getattr(manager, "bUpdatingSkills", False)):
        return  # Defer definition arrays as well as snapshots during a native update.

    def adjusted(original: Any) -> tuple[Any, bool]:
        if _attribute_path(original) != PHASELOCK_DURATION_ATTRIBUTE_PATH:
            return original, False
        matches = all(
            abs(float(getattr(original, field).BaseValueConstant) - value) <= .000001
            and getattr(original, field).BaseValueAttribute is None
            and getattr(original, field).InitializationDefinition is None
            and abs(float(getattr(original, field).BaseValueScaleConstant) - 1.0) <= .000001
            for field, value in (("BaseModifierValue", THOUGHTLOCK_DURATION_BONUS_SECONDS),
                                 ("PerGradeUpgrade", 0.0))
        )
        if matches:
            return original, False
        effect = copy.copy(original)
        for field, value in (("BaseModifierValue", THOUGHTLOCK_DURATION_BONUS_SECONDS),
                             ("PerGradeUpgrade", 0.0)):
            data = copy.copy(getattr(original, field))
            data.BaseValueConstant, data.BaseValueScaleConstant = value, 1.0
            data.BaseValueAttribute, data.InitializationDefinition = None, None
            setattr(effect, field, data)
        return effect, True

    if not any(_attribute_path(effect) == PHASELOCK_DURATION_ATTRIBUTE_PATH
               for effect in definition.SkillEffectDefinitions):
        raise ValueError("Psychic Shriek has no native Phaselock duration effect")
    changed = False
    effects = []
    for original in definition.SkillEffectDefinitions:
        effect, updated = adjusted(original)
        effects.append(effect)
        changed |= updated
    if changed:
        definition.SkillEffectDefinitions = effects
    if manager is None:
        return
    for skill in manager.ActiveSkills:
        if skill.Definition != definition or skill.SkillInstigator != controller:
            continue
        changed, effects = False, []
        for original in skill.SkillEffects:
            data, updated = adjusted(original.EffectData)
            applied = copy.copy(original) if updated else original
            if updated:
                applied.EffectData = data
            effects.append(applied)
            changed |= updated
        if changed:
            skill.SkillEffects = effects
            skill.bForceRefreshModifiersNextTick = True


def _link_thoughtlock_hud_feedback(definition: Any) -> None:
    """Replace only the obsolete charm indicator; preserve other mods' children."""
    if (definition.TrackedActiveSkill is not None
            and str(definition.TrackedActiveSkill._path_name()) == THOUGHTLOCK_FEEDBACK_PATH):
        definition.TrackedActiveSkill = None
    children = list(definition.TrackedActiveSkills)
    kept = [child for child in children
            if child is None or str(child._path_name()) != THOUGHTLOCK_FEEDBACK_PATH]
    if _thoughtlock_hud_feedback is not None and _thoughtlock_hud_feedback not in kept:
        kept.append(_thoughtlock_hud_feedback)
    if len(kept) != len(children) or any(a != b for a, b in zip(kept, children)):
        definition.TrackedActiveSkills = kept


def _get_thoughtlock_hud_feedback() -> Any:
    global _thoughtlock_hud_feedback
    definition = unrealsdk.find_object("SkillDefinition", THOUGHTLOCK_PATH)
    if _thoughtlock_hud_feedback is None:
        feedback = unrealsdk.construct_object(
            "SkillDefinition", definition, "MR_PsychicShriek_HUD_Feedback",
            flags=int(ObjectFlags.KEEP_ALIVE), template_obj=definition,
        )
        feedback.SkillName, feedback.SkillIcon = "Psychic Shriek debuff", definition.SkillIcon
        feedback.bSubjectToGradeRules = False
        feedback.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered
        feedback.TrackedSkillHUDSlot = THOUGHTLOCK_HUD_SLOT
        # The debuff uses gameplay time. Native infinite feedback follows that
        # window instead of expiring on a separate, possibly unpaused timer.
        feedback.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite
        feedback.InitialDuration = 0.0
        feedback.SkillEffectDefinitions, feedback.SkillEffectPresentations = [], []
        feedback.SkillConstraints, feedback.DamageEvents, feedback.KillEvents = [], [], []
        feedback.BehaviorProviderDefinition, feedback.TrackedActiveSkill = None, None
        feedback.TrackedActiveSkills = []
        _thoughtlock_hud_feedback = feedback
    _link_thoughtlock_hud_feedback(definition)
    return _thoughtlock_hud_feedback


def _sync_thoughtlock_hud_indicator() -> None:
    try:
        controller = _cooldown_hud_controller()
        if controller is None or not _is_maya_controller(controller):
            return
        world = controller.WorldInfo
        if world.Pauser or controller.IsPauseMenuOpen():
            return
        now, world_id = float(world.TimeSeconds), world._get_address()
        owner_id = _thoughtlock_actor_identity(controller)
        # Inspect primitive records only, not a new per-frame scan of enemies.
        wanted = any(key[0] == world_id and mark["owner_id"] == owner_id
                     and mark["started"] <= now < mark["until"]
                     for key, mark in _thoughtlock_marks.items())
        wanted = wanted and _thoughtlock_rank(controller) > 0
        manager = controller.GetSkillManager()
        if manager is None or getattr(manager, "bUpdatingSkills", False):
            return
        if not wanted:
            if _thoughtlock_hud_feedback is not None and manager.IsSkillActive(controller, _thoughtlock_hud_feedback):
                manager.DeactivateSkill(controller, _thoughtlock_hud_feedback)
            return
        movie = controller.GetHUDMovie()
        if movie is None:
            return
        feedback = _get_thoughtlock_hud_feedback()
        # A previously registered charm child must not reserve a ghost slot.
        for skill in list(manager.ActiveSkills):
            if (skill.SkillInstigator == controller and skill.Definition is not None
                    and str(skill.Definition._path_name()) == THOUGHTLOCK_FEEDBACK_PATH):
                manager.DeactivateSkill(controller, skill.Definition)
        entries = list(movie.AvailableTrackedSkills)
        kept = [entry for entry in entries if entry.SkillDef is None
                or str(entry.SkillDef._path_name()) != THOUGHTLOCK_FEEDBACK_PATH]
        if len(kept) != len(entries):
            movie.AvailableTrackedSkills = [copy.copy(entry) for entry in kept]
        if not _prepare_combat_hud_feedback(controller, movie, feedback):
            return  # Full HUD: preserve every existing skill and retry later.
        if not manager.IsSkillActive(controller, feedback):
            if manager.ActivateSkill(controller, feedback, None, 1) is False:
                raise ValueError("Psychic Shriek visual feedback was rejected")
            movie.UpdateSkillIcons()
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not update Psychic Shriek HUD indicator: {exc}")


def _configure_thoughtlock_description(controller: Any | None = None) -> None:
    definition = unrealsdk.find_object("SkillDefinition", THOUGHTLOCK_PATH)
    _configure_thoughtlock_duration(definition, controller)
    _link_thoughtlock_hud_feedback(definition)
    definition.SkillName = "Psychic Shriek"
    definition.SkillDescription = (
        "[skill]Phaselock[-skill] reduces the [skill]damage dealt[-skill] by nearby enemies "
        f"for [skill]{THOUGHTLOCK_DEBUFF_SECONDS:g} seconds[-skill]. "
        "Its target also takes [skill]increased damage[-skill] from you and your allies, "
        "even if it cannot be [skill]Phaselocked[-skill]. "
        "Additionally, [skill]Phaselock's Duration[-skill] is increased."
    )
    # Discard obsolete charm/cooldown text; retain the tuned native duration line.
    obsolete = {f"{THOUGHTLOCK_PATH}:AttributePresentationDefinition_{i}" for i in (0, 2)}
    presentations = list(definition.SkillEffectPresentations)
    filtered = [p for p in presentations if p and str(p._path_name()) not in obsolete]
    if len(filtered) != len(presentations):
        definition.SkillEffectPresentations = filtered


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def describe_thoughtlock_stats(_tree: UObject, args: WrappedStruct, _ret: Any, func: Any) -> tuple[type[Block], str] | None:
    if not args.SkillDef or str(args.SkillDef._path_name()) != THOUGHTLOCK_PATH:
        return None
    try:
        # One-point skill: ignore COM modifiers and preserve the native duration footer.
        learned = int(args.Grade) > 0
        plain = not learned or not args.bIncludeHTML
        separator = "<br>" if args.bIncludeHTML else "\n"
        dealt = _format_percentage_progression(
            "Enemy damage dealt", -100 * THOUGHTLOCK_DAMAGE_REDUCTION if learned else 0,
            int(learned), plain,
        )
        taken = _format_percentage_progression(
            "Damage taken by target", 100 * THOUGHTLOCK_DAMAGE_TAKEN,
            int(learned), plain, show_plus=True,
        )
        with unrealsdk.hooks.prevent_hooking_direct_calls():
            native = func(args)
        return Block, separator.join(part for part in (native, dealt, taken) if part)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not format Psychic Shriek description: {exc}")
        return None


def _thoughtlock_actor_identity(actor: Any) -> tuple[int, float, str]:
    return (actor._get_address(), float(actor.CreationTime), str(actor._path_name()))


def _thoughtlock_rank(controller: Any) -> int:
    # A Python UObject reference does not keep this native asset alive across
    # menu/map GC. Resolve it at the point of use; never probe the old wrapper.
    try:
        definition = unrealsdk.find_object("SkillDefinition", THOUGHTLOCK_PATH)
    except ValueError:
        return 0  # The current world's class assets may not be loaded yet.
    return max(0, int(controller.GetSkillGrade(definition))) if definition is not None else 0


def _thoughtlock_owner(action: Any) -> Any:
    if _cooldown_hud_suspended:
        return None
    controller = action.MyController
    if (not controller or controller.bDeleteMe or not getattr(controller, "PlayerClass", None)
            or not _is_maya_controller(controller)
            or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
        return None
    pawn, world = controller.Pawn, controller.WorldInfo
    if (not pawn or pawn.bDeleteMe or not world or world.bDeleteMe or world.Pauser
            or pawn.WorldInfo != world):
        return None
    return controller if _thoughtlock_rank(controller) > 0 else None


@hook("WillowGame.LiftActionSkill:CanCharmTarget", Type.PRE)
def suppress_thoughtlock_charm(action: UObject, _args: Any, _ret: Any, _func: Any) -> tuple[type[Block], bool] | None:
    try:
        if _thoughtlock_owner(action) is not None:
            # The native false branch performs ordinary lifting and still respects
            # CanLiftTargetIf. Do not modify boss immunity, the BPD or skill grade.
            return Block, False
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not suppress Thoughtlock charm: {exc}")
    return None


def _thoughtlock_enemy(target: Any, controller: Any, world: Any) -> bool:
    return bool(target and not target.bDeleteMe and not target.bPendingDelete
                and target.WorldInfo == world
                and target.Class._inherits(unrealsdk.find_class("WillowAIPawn"))
                and float(target.GetHealth()) > 0.0
                and int(target.GetOpinion(controller.Pawn)) == int(unrealsdk.find_enum("EOpinion").OPINION_Enemy))


def _store_thoughtlock_mark(target: Any, controller: Any, world: Any, now: float, primary: bool) -> bool:
    global _thoughtlock_marks_world, _thoughtlock_marks_expiry, _thoughtlock_marks_clock
    world_id = world._get_address()
    if _thoughtlock_marks_world != world_id or now < _thoughtlock_marks_clock:
        _thoughtlock_marks.clear()
    if not _thoughtlock_marks:
        _thoughtlock_marks_world, _thoughtlock_marks_expiry = world_id, 0.0
    _thoughtlock_marks_clock = now
    key = world_id, target._get_address()
    identity, owner_id = _thoughtlock_actor_identity(target), _thoughtlock_actor_identity(controller)
    previous = _thoughtlock_marks.get(key)
    # Area refreshes renew suppression, but must not extend an earlier primary
    # target's vulnerability. Multiple casts never stack these fixed percentages.
    incoming_until = 0.0
    if (previous and previous["target"] == identity and previous["owner_id"] == owner_id
            and previous["started"] <= now < previous["until"]):
        incoming_until = previous["incoming_until"]
    if primary:
        incoming_until = now + THOUGHTLOCK_DEBUFF_SECONDS
    if len(_thoughtlock_marks) >= 256 and key not in _thoughtlock_marks:
        # Area-only marks may not evict an active primary-target vulnerability.
        evict = next((old_key for old_key, mark in _thoughtlock_marks.items()
                      if mark["incoming_until"] <= now), None)
        if evict is None:
            if not primary:
                return False
            evict = next(iter(_thoughtlock_marks))
        _thoughtlock_marks.pop(evict)
    _thoughtlock_marks[key] = dict(
        target=identity, owner=WeakPointer(controller), owner_id=owner_id,
        started=now, until=now + THOUGHTLOCK_DEBUFF_SECONDS, incoming_until=incoming_until,
    )
    _thoughtlock_marks_expiry = max(_thoughtlock_marks_expiry, now + THOUGHTLOCK_DEBUFF_SECONDS)
    return True


@hook("WillowGame.LiftActionSkill:OnBeginLiftingTarget", Type.PRE)
@hook("WillowGame.LiftActionSkill:OnTargetBlocked", Type.PRE)
def mark_thoughtlock_targets(action: UObject, args: WrappedStruct, _ret: Any, _func: Any) -> None:
    try:
        controller = _thoughtlock_owner(action)
        if controller is None or args.SkillInstigator != controller.Pawn:
            return
        target, world = args.SkillTarget, controller.WorldInfo
        if not _thoughtlock_enemy(target, controller, world):
            return  # No marks for Res, allies, dead targets, missed or failed casts.
        now = float(world.TimeSeconds)
        if not 0.0 <= now < float("inf"):
            return
        for key, mark in tuple(_thoughtlock_marks.items()):
            if key[0] != world._get_address() or not mark["started"] <= now < mark["until"]:
                _thoughtlock_marks.pop(key, None)
        # The primary debuff must not depend on a nearby actor or the area asset.
        _store_thoughtlock_mark(target, controller, world, now, True)
        # Like the rank definition, this native asset may be unloaded at a menu.
        # Only retain it for this synchronous pulse, never across world changes.
        converge = unrealsdk.find_object("MeleeDefinition", THOUGHTLOCK_CONVERGE_PATH)
        radius = float(converge.DamageRadius)
        if not 0.0 < radius < float("inf"):
            raise ValueError("Thoughtlock requires a positive finite Converge radius")
        # Walk the current world's native pawn list only on a confirmed target.
        # No global object scan, per-frame area scan or strong actor cache.
        center, candidate, seen, count = target.Location, world.PawnList, set(), 0
        extent = copy.copy(center)
        extent.X, extent.Y, extent.Z = 0.0, 0.0, 0.0
        while candidate is not None:
            address = candidate._get_address()
            if address in seen or len(seen) >= 4096:
                _log_error_once("Thoughtlock area pawn list was cyclic or exceeded its safety bound")
                break
            seen.add(address)
            next_pawn = candidate.NextPawn
            try:
                if candidate != target and _thoughtlock_enemy(candidate, controller, world):
                    point = candidate.Location
                    distance_sq = sum((float(getattr(point, axis)) - float(getattr(center, axis))) ** 2
                                      for axis in ("X", "Y", "Z"))
                    if distance_sq <= radius * radius and target.FastTrace(point, center, extent, False):
                        count += int(_store_thoughtlock_mark(candidate, controller, world, now, False))
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _log_error_once(f"Could not inspect a Psychic Shriek area target: {exc}")
            candidate = next_pawn
        unrealsdk.logging.info(
            f"[MayaRebalance] Thoughtlock debuffs: suppression={THOUGHTLOCK_DAMAGE_REDUCTION:g}, "
            f"vulnerability={THOUGHTLOCK_DAMAGE_TAKEN:g}, "
            f"duration={THOUGHTLOCK_DEBUFF_SECONDS:g}, radius={radius:g}, nearby={count}, "
            f"target={target._path_name()}"
        )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not finish Psychic Shriek debuff pulse: {exc}")


def _active_thoughtlock_mark(target: Any) -> dict[str, Any] | None:
    if not target or target.bDeleteMe or target.bPendingDelete:
        return None
    world = target.WorldInfo
    if not world or world.bDeleteMe or world.Pauser:
        return None
    key = world._get_address(), target._get_address()
    mark = _thoughtlock_marks.get(key)
    if mark is None:
        return None
    now, owner = float(world.TimeSeconds), mark["owner"]()
    if (not mark["started"] <= now < mark["until"]
            or _thoughtlock_actor_identity(target) != mark["target"]
            or not owner or owner.bDeleteMe or owner.WorldInfo != world
            or _thoughtlock_actor_identity(owner) != mark["owner_id"]
            or not _is_maya_controller(owner)
            or _thoughtlock_rank(owner) <= 0
            or not owner.Pawn or owner.Pawn.bDeleteMe
            or not _thoughtlock_enemy(target, owner, world)):
        _thoughtlock_marks.pop(key, None)
        return None
    return mark


def _thoughtlock_hit_factor(target: Any, controller: Any) -> float:
    global _thoughtlock_marks_clock
    if not _thoughtlock_marks:
        return 1.0
    world = target.WorldInfo
    if not world or world.bDeleteMe or world.Pauser:
        return 1.0
    now = float(world.TimeSeconds)
    if (_thoughtlock_marks_world != world._get_address()
            or not _thoughtlock_marks_clock <= now < _thoughtlock_marks_expiry):
        # Drop expired/unrelated-world history on ANY damage, not only a hit on
        # the marked enemy (which may already have died and left the pawn list).
        _thoughtlock_marks.clear()
        return 1.0
    _thoughtlock_marks_clock = now
    source = getattr(controller, "Pawn", None)
    factor = 1.0 - THOUGHTLOCK_DAMAGE_REDUCTION if _active_thoughtlock_mark(source) else 1.0
    mark = _active_thoughtlock_mark(target)
    if (mark is not None and float(target.WorldInfo.TimeSeconds) < mark["incoming_until"]
            and source and not source.bDeleteMe and source.WorldInfo == target.WorldInfo):
        owner = mark["owner"]()
        opinions = unrealsdk.find_enum("EOpinion")
        if (owner and (controller == owner or int(owner.Pawn.GetOpinion(source)) == int(opinions.OPINION_Friendly))
                and int(target.GetOpinion(source)) == int(opinions.OPINION_Enemy)):
            factor *= 1.0 + THOUGHTLOCK_DAMAGE_TAKEN
    return factor


@hook("WillowGame.WillowPlayerController:PreClientTravel", Type.PRE)
@hook("WillowGame.WillowPlayerController:Destroyed", Type.PRE)
def clear_thoughtlock_marks(controller: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    if controller == get_pc():
        _thoughtlock_marks.clear()
    else:
        owner_id = controller._get_address()
        for key, mark in tuple(_thoughtlock_marks.items()):
            if mark["owner_id"][0] == owner_id:
                _thoughtlock_marks.pop(key, None)


def _configure_minds_eye() -> Any:
    definition = unrealsdk.find_object("SkillDefinition", MINDS_EYE_PATH)
    effects = list(definition.SkillEffectDefinitions)
    if any(_attribute_path(effect) == MINDS_EYE_MELEE_ATTRIBUTE_PATH for effect in effects):
        effects = [copy.copy(effect) for effect in effects]
        for effect in effects:
            if _attribute_path(effect) == MINDS_EYE_MELEE_ATTRIBUTE_PATH:
                effect.AttributeToModify = unrealsdk.find_object(
                    "AttributeDefinition", MINDS_EYE_ACCURACY_ATTRIBUTE_PATH
                )
                _set_effect_value(effect, MINDS_EYE_SPREAD_PER_RANK)
        definition.SkillEffectDefinitions = effects
    _set_skill_effect(MINDS_EYE_PATH, MINDS_EYE_ACCURACY_ATTRIBUTE_PATH, MINDS_EYE_SPREAD_PER_RANK)
    description = "Increases [skill]Critical Hit Damage[-skill] and [skill]Accuracy[-skill]."
    if definition.SkillDescription != description:
        definition.SkillDescription = description
    presentation = unrealsdk.find_object(
        "AttributePresentationDefinition", f"{MINDS_EYE_PATH}:AttributePresentationDefinition_1"
    )
    attribute = presentation.Attribute
    if attribute is None or str(attribute._path_name()) != MINDS_EYE_ACCURACY_ATTRIBUTE_PATH:
        presentation.Attribute = unrealsdk.find_object("AttributeDefinition", MINDS_EYE_ACCURACY_ATTRIBUTE_PATH)
    if presentation.Description != "Accuracy: $NUMBER$":
        presentation.Description = "Accuracy: $NUMBER$"
    return definition


def _log_minds_eye_runtime(player_controller: Any, skill: Any) -> None:
    """Log actual values/contexts once per state, not once per render."""
    attribute = unrealsdk.find_object("AttributeDefinition", MINDS_EYE_ACCURACY_ATTRIBUTE_PATH)
    weapon = attribute.ResolveContext(player_controller)
    rows = []
    for applied in skill.SkillEffects:
        data = applied.EffectData
        path = _attribute_path(data)
        if path not in {MINDS_EYE_MELEE_ATTRIBUTE_PATH, MINDS_EYE_ACCURACY_ATTRIBUTE_PATH}:
            continue
        rows.append((
            path,
            float(data.BaseModifierValue.BaseValueConstant),
            float(data.PerGradeUpgrade.BaseValueConstant),
            float(applied.Modifier.Value) if applied.Modifier else None,
            tuple(str(context._path_name()) for context in applied.Contexts if context),
            bool(weapon and applied.Modifier and _modifier_is_in_stack(
                applied.Modifier, weapon.SpreadModifierStack
            )) if path == MINDS_EYE_ACCURACY_ATTRIBUTE_PATH else None,
        ))
    state = (int(skill.Grade), int(skill.SkillState),
             weapon._get_address() if weapon else None, tuple(rows))
    address = skill._get_address()
    if _minds_eye_diagnostic_states.get(address) == state:
        return
    # Bound diagnostics across respawns/map loads without keeping UObject refs.
    if len(_minds_eye_diagnostic_states) >= 64:
        _minds_eye_diagnostic_states.clear()
    _minds_eye_diagnostic_states[address] = state
    unrealsdk.logging.info(
        "[MayaRebalance] DEBUG Mind's Eye runtime: "
        f"grade={int(skill.Grade)}, skill_state={int(skill.SkillState)}, "
        f"weapon={weapon._path_name() if weapon else 'None'}, "
        f"spread={float(weapon.Spread) if weapon else 'None'}, "
        f"spread_base={float(weapon.SpreadBaseValue) if weapon else 'None'}, effects={rows}"
    )


def _sync_minds_eye_effects(player_controller: Any) -> None:
    definition = _configure_minds_eye()
    accuracy_definition = next(
        effect for effect in definition.SkillEffectDefinitions
        if _attribute_path(effect) == MINDS_EYE_ACCURACY_ATTRIBUTE_PATH
    )
    for skill in list(player_controller.GetSkillManager().ActiveSkills):
        if str(skill.Definition._path_name()) != MINDS_EYE_PATH or skill.SkillInstigator != player_controller:
            continue
        effects = list(skill.SkillEffects)
        found_accuracy = False
        changed = False
        for index, applied in enumerate(effects):
            data = applied.EffectData
            path = _attribute_path(data)
            if path == MINDS_EYE_ACCURACY_ATTRIBUTE_PATH:
                found_accuracy = True
                expected = MINDS_EYE_SPREAD_PER_RANK
            elif path == MINDS_EYE_MELEE_ATTRIBUTE_PATH:
                # Do not retarget a Modifier still attached to the melee stack.
                expected = 0.0
            else:
                continue  # In particular, preserve the critical-hit bonus.
            data_matches = all(
                abs(float(value.BaseValueConstant) - expected) <= 0.000001
                and not value.BaseValueAttribute and not value.InitializationDefinition
                and abs(float(value.BaseValueScaleConstant) - 1.0) <= 0.000001
                for value in (data.BaseModifierValue, data.PerGradeUpgrade)
            )
            modifier = applied.Modifier
            if data_matches and (not modifier or abs(float(modifier.Value) - expected * int(skill.Grade)) <= 0.000001):
                continue
            if not changed:
                effects = [copy.copy(effect) for effect in effects]
            data = copy.copy(data)
            _set_effect_value(data, expected)
            effects[index].EffectData = data
            changed = True
        if changed:
            skill.SkillEffects = effects
            skill.bForceRefreshModifiersNextTick = True
        if not found_accuracy:
            # Let the native skill build the new Modifier and resolve weapon
            # contexts. Never deactivate/reactivate or rebuild the whole skill.
            skill.AddSkillEffect(player_controller, copy.copy(accuracy_definition))
            if not any(_attribute_path(e.EffectData) == MINDS_EYE_ACCURACY_ATTRIBUTE_PATH for e in skill.SkillEffects):
                raise ValueError("Mind's Eye did not retain its native accuracy effect")
            changed = True
        if changed:
            skill.bForceRefreshModifiersNextTick = True
        _log_minds_eye_runtime(player_controller, skill)


def _blight_phoenix_speed_effect_matches(effect: Any) -> bool:
    return (
        effect.ModifierType == unrealsdk.find_enum("EModifierType").MT_Scale
        and effect.GradeToStartApplyingEffect == 1
        and effect.PerGradeUpgradeInterval == 1
        and not effect.BonusUpgradeList
        and all(
            abs(float(value.BaseValueConstant) - BLIGHT_PHOENIX_SPEED_PER_RANK) <= 0.000001
            and value.BaseValueAttribute is None and value.InitializationDefinition is None
            and abs(float(value.BaseValueScaleConstant) - 1.0) <= 0.000001
            for value in (effect.BaseModifierValue, effect.PerGradeUpgrade)
        )
    )


def _blight_phoenix_aura_effect_is_disabled(effect: Any) -> bool:
    return not effect.BonusUpgradeList and all(
        abs(float(value.BaseValueConstant)) <= 0.000001
        and value.BaseValueAttribute is None and value.InitializationDefinition is None
        and abs(float(value.BaseValueScaleConstant) - 1.0) <= 0.000001
        for value in (effect.BaseModifierValue, effect.PerGradeUpgrade)
    )


def _disable_blight_phoenix_aura(definition: Any) -> None:
    """Disable only this skill's original aura graph and designer-attribute effect."""
    changed = definition.BehaviorProviderDefinition is not None
    definition.BehaviorProviderDefinition = None
    effects = list(definition.SkillEffectDefinitions)
    for index, effect in enumerate(effects):
        if (_attribute_path(effect) != BLIGHT_PHOENIX_AURA_ATTRIBUTE_PATH
                or _blight_phoenix_aura_effect_is_disabled(effect)):
            continue
        disabled = copy.copy(effect)
        _set_effect_value(disabled, 0.0)
        disabled.BonusUpgradeList = []
        effects[index] = disabled
        changed = True
    if changed:
        definition.SkillEffectDefinitions = effects
    if (definition.BehaviorProviderDefinition is not None or any(
        _attribute_path(effect) == BLIGHT_PHOENIX_AURA_ATTRIBUTE_PATH
        and not _blight_phoenix_aura_effect_is_disabled(effect)
        for effect in definition.SkillEffectDefinitions
    )):
        raise ValueError("Blight Phoenix retained its original aura")
    if changed:
        unrealsdk.logging.info("[MayaRebalance] Disabled original Blight Phoenix aura; native kill trigger/duration preserved")


@hook("WillowGame.Behavior_CauseDamage:ApplyBehaviorToContext", Type.PRE)
def prevent_original_blight_phoenix_aura(behavior: UObject, _args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    # Old active instances may still have queued behaviors from their original graph.
    if str(behavior._path_name()) in BLIGHT_PHOENIX_AURA_DAMAGE_PATHS:
        return Block
    return None


def _configure_blight_phoenix() -> Any:
    """Keep the native kill trigger/timer, disable the aura and add movement."""
    definition = unrealsdk.find_object("SkillDefinition", BLIGHT_PHOENIX_PATH)
    _disable_blight_phoenix_aura(definition)
    effects = list(definition.SkillEffectDefinitions)
    index = next((i for i, effect in enumerate(effects)
                  if _attribute_path(effect) == BLIGHT_PHOENIX_SPEED_ATTRIBUTE_PATH), None)
    if index is not None and _blight_phoenix_speed_effect_matches(effects[index]):
        return definition
    if not effects:
        raise ValueError("Blight Phoenix has no native self-effect template")
    speed = copy.copy(effects[index] if index is not None else effects[0])
    speed.AttributeToModify = unrealsdk.find_object("AttributeDefinition", BLIGHT_PHOENIX_SPEED_ATTRIBUTE_PATH)
    speed.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
    _set_effect_value(speed, BLIGHT_PHOENIX_SPEED_PER_RANK)
    speed.GradeToStartApplyingEffect = 1
    speed.PerGradeUpgradeInterval = 1
    speed.BonusUpgradeList = []
    if index is None:
        effects.append(speed)
    else:
        effects[index] = speed
    definition.SkillEffectDefinitions = effects
    retained = next(effect for effect in definition.SkillEffectDefinitions
                    if _attribute_path(effect) == BLIGHT_PHOENIX_SPEED_ATTRIBUTE_PATH)
    if not _blight_phoenix_speed_effect_matches(retained):
        raise ValueError("Blight Phoenix did not retain its movement effect")
    unrealsdk.logging.info("[MayaRebalance] Configured Blight Phoenix: native kill trigger/duration preserved; original aura disabled; speed=0.05 per rank")
    return definition


def _kinetic_reflection_effect_matches(effect: Any) -> bool:
    return (
        int(effect.ModifierType) == int(unrealsdk.find_enum("EModifierType").MT_PostAdd)
        and int(effect.EffectTarget) == 1  # TARGET_Self
        and int(effect.GradeToStartApplyingEffect) == 1
        and int(effect.PerGradeUpgradeInterval) == 1
        and not effect.BonusUpgradeList
        and all(
            abs(float(getattr(effect, field).BaseValueConstant)
                + KINETIC_REFLECTION_BULLET_REDUCTION_PER_RANK) <= 0.000001
            and getattr(effect, field).BaseValueAttribute is None
            and getattr(effect, field).InitializationDefinition is None
            and abs(float(getattr(effect, field).BaseValueScaleConstant) - 1.0) <= 0.000001
            for field in ("BaseModifierValue", "PerGradeUpgrade")
        )
    )


def _configure_kinetic_reflection(controller: Any = None) -> None:
    """Keep the native bullet route and kill window; never activate the skill here."""
    manager = controller.GetSkillManager() if controller is not None else None
    if manager is not None and getattr(manager, "bUpdatingSkills", False):
        return
    definition = unrealsdk.find_object("SkillDefinition", KINETIC_REFLECTION_PATH)
    if definition is None:
        raise ValueError("Kinetic Reflection definition is unavailable")
    matches = [i for i, effect in enumerate(definition.SkillEffectDefinitions)
               if _attribute_path(effect) == KINETIC_REFLECTION_ATTRIBUTE_PATH]
    if len(matches) != 1:
        raise ValueError("Kinetic Reflection must have exactly one native bullet reduction effect")
    index = matches[0]
    desired = definition.SkillEffectDefinitions[index]
    if not _kinetic_reflection_effect_matches(desired):
        desired = copy.copy(desired)
        _set_effect_value(desired, -KINETIC_REFLECTION_BULLET_REDUCTION_PER_RANK)
        desired.ModifierType = unrealsdk.find_enum("EModifierType").MT_PostAdd
        desired.EffectTarget = 1
        desired.GradeToStartApplyingEffect = desired.PerGradeUpgradeInterval = 1
        desired.BonusUpgradeList = []
        effects = list(definition.SkillEffectDefinitions)
        effects[index] = desired
        definition.SkillEffectDefinitions = effects
        desired = definition.SkillEffectDefinitions[index]
        if not _kinetic_reflection_effect_matches(desired):
            raise ValueError("Kinetic Reflection did not retain its bullet reduction formula")
    if definition.SkillDescription != KINETIC_REFLECTION_DESCRIPTION:
        definition.SkillDescription = KINETIC_REFLECTION_DESCRIPTION
    # Preserve the other native presentations (deflection chance and damage).
    presentation = unrealsdk.find_object(
        "AttributePresentationDefinition", f"{KINETIC_REFLECTION_PATH}:AttributePresentationDefinition_0",
    )
    if presentation is None:
        raise ValueError("Kinetic Reflection bullet presentation is unavailable")
    if presentation.Description != "Bullet Damage Reduction: $NUMBER$":
        presentation.Description = "Bullet Damage Reduction: $NUMBER$"
    if (definition.SkillDescription != KINETIC_REFLECTION_DESCRIPTION
            or presentation.Description != "Bullet Damage Reduction: $NUMBER$"):
        raise ValueError("Kinetic Reflection did not retain its description")
    if manager is None:
        return
    skill = manager.GetActiveSkillForInstigatorByDefinition(controller, definition)
    if skill is None or skill.SkillInstigator != controller:
        return
    # Repair a stale effect snapshot without refreshing the kill-skill duration.
    changes = []
    for i, applied in enumerate(skill.SkillEffects):
        if (_attribute_path(applied.EffectData) == KINETIC_REFLECTION_ATTRIBUTE_PATH
                and not _kinetic_reflection_effect_matches(applied.EffectData)):
            migrated = copy.copy(applied)
            migrated.EffectData = copy.copy(desired)
            changes.append((i, migrated))
    if changes:
        effects = list(skill.SkillEffects)
        for i, migrated in changes:
            effects[i] = migrated
        skill.SkillEffects = effects
        skill.bForceRefreshModifiersNextTick = True


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.PRE)
def kinetic_reflection_reduce_general_damage(
    pipeline: UObject, args: WrappedStruct, _ret: Any, func: BoundFunction,
) -> tuple[type[Block], Any] | None:
    """Non-bullet hits get half the native bullet protection, never both factors."""
    if _cooldown_hud_suspended:
        return None
    # A prior return override may already have executed this hit. Do not replay it.
    if _ret is not unrealsdk.hooks.Unset and not isinstance(_ret, unrealsdk.hooks.Unset):
        return None
    try:
        controller = get_pc()
        target = args.InDamagedActor
        if (controller is None or target is None or controller.Pawn != target
                or controller.bDeleteMe or target.bDeleteMe or not _is_maya_controller(controller)
                or int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
            return None
        incoming = float(args.IncomingDamage)
        if not 0.0 < incoming < float("inf"):
            return None
        source = args.InDamageSource
        if source is not None and (str(source.Name) == "WillowDmgSource_Bullet"
                                   or any(str(base.Name) == "WillowDmgSource_Bullet"
                                          for base in source._superfields())):
            return None  # Bullet protection is already applied by native reflection.
        definition = unrealsdk.find_object("SkillDefinition", KINETIC_REFLECTION_PATH)
        if definition is None or int(controller.GetSkillGrade(definition)) <= 0:
            return None
        skill = controller.GetSkillManager().GetActiveSkillForInstigatorByDefinition(controller, definition)
        if (skill is None or skill.SkillInstigator != controller or int(skill.Grade) <= 0
                or int(skill.SkillState) != int(unrealsdk.find_enum("ESkillState").SKILL_Active)):
            return None
        damage_type = pipeline.GetDamageTypeDef()
        if damage_type is not None and damage_type.IsHealingDamageType():
            return None
        rank = min(CLASS_MODDED_SKILL_RANK_LIMIT, int(skill.Grade))  # Native Grade already includes COMs.
        factor = max(0.0, 1.0 - KINETIC_REFLECTION_GENERAL_REDUCTION_PER_RANK * rank)
        scaled_args = copy.copy(args)
        scaled_args.IncomingDamage = incoming * factor
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not prepare Kinetic Reflection general reduction: {exc}")
        return None
    # Hook args are copies in this SDK. Call the native calculation once with
    # owned parameters; bypass only this direct call, retaining secondary procs.
    with unrealsdk.hooks.prevent_hooking_direct_calls():
        summary = func(scaled_args)
    try:
        if rank not in _kinetic_reflection_logged_ranks:
            _kinetic_reflection_logged_ranks.add(rank)
            unrealsdk.logging.info(
                f"[MayaRebalance] Kinetic Reflection general reduction: rank={rank}, "
                f"factor={factor:g}, incoming={incoming:g}, scaled={incoming * factor:g}; bullets use native reflection"
            )
    except Exception:
        pass  # A reporting failure after native damage must never replay the hit.
    return Block, summary


def _blight_phoenix_active_skill(controller: Any, definition: Any) -> Any | None:
    skill = controller.GetSkillManager().GetActiveSkillForInstigatorByDefinition(controller, definition)
    if (skill is None or skill.SkillInstigator != controller or int(skill.Grade) <= 0
            or int(skill.SkillState) != int(unrealsdk.find_enum("ESkillState").SKILL_Active)):
        return None
    return skill


def _sync_blight_phoenix_effects(controller: Any) -> None:
    """Migrate only the speed cache of an already-active native kill skill."""
    global _blight_phoenix_last_speed_log
    definition = _configure_blight_phoenix()
    skill = _blight_phoenix_active_skill(controller, definition)
    if skill is None:
        _blight_phoenix_last_speed_log = None
        return  # Never activate a kill skill merely because points were invested.
    speed_definition = next(effect for effect in definition.SkillEffectDefinitions
                            if _attribute_path(effect) == BLIGHT_PHOENIX_SPEED_ATTRIBUTE_PATH)
    effects = [copy.copy(applied) for applied in skill.SkillEffects]
    changed, found = False, False
    for applied in effects:
        if _attribute_path(applied.EffectData) == BLIGHT_PHOENIX_AURA_ATTRIBUTE_PATH:
            modifier = applied.Modifier
            if (not _blight_phoenix_aura_effect_is_disabled(applied.EffectData)
                    or (modifier is not None and abs(float(modifier.Value)) > 0.000001)):
                disabled = copy.copy(applied.EffectData)
                _set_effect_value(disabled, 0.0)
                disabled.BonusUpgradeList = []
                applied.EffectData = disabled
                changed = True
            continue
        if _attribute_path(applied.EffectData) != BLIGHT_PHOENIX_SPEED_ATTRIBUTE_PATH:
            continue
        found = True
        if not _blight_phoenix_speed_effect_matches(applied.EffectData):
            applied.EffectData = copy.copy(speed_definition)
            changed = True
    if changed:
        skill.SkillEffects = effects
        skill.bForceRefreshModifiersNextTick = True
    if not found:
        skill.AddSkillEffect(controller, copy.copy(speed_definition))
        skill.bForceRefreshModifiersNextTick = True
    applied_speed = next((applied for applied in skill.SkillEffects
                          if _attribute_path(applied.EffectData) == BLIGHT_PHOENIX_SPEED_ATTRIBUTE_PATH), None)
    if applied_speed is None:
        raise ValueError("Active Blight Phoenix did not retain its movement effect")
    modifier = applied_speed.Modifier
    actual = float(modifier.Value) if modifier is not None else None
    if actual is not None and abs(actual - BLIGHT_PHOENIX_SPEED_PER_RANK * int(skill.Grade)) > 0.000001:
        skill.bForceRefreshModifiersNextTick = True  # Refresh a cached old grade, never restart the kill skill.
    state = (skill._get_address(), int(skill.Grade), actual)
    if state != _blight_phoenix_last_speed_log:
        _blight_phoenix_last_speed_log = state  # Only primitive values survive travel.
        unrealsdk.logging.info(
            f"[MayaRebalance] Blight Phoenix native speed: grade={int(skill.Grade)}, "
            f"expected_bonus={BLIGHT_PHOENIX_SPEED_PER_RANK * int(skill.Grade):g}, modifier={actual}"
        )


def _blight_phoenix_ammo_rank(weapon: Any) -> int:
    """Read eligibility only; no random roll and no writes to weapon resources."""
    if _cooldown_hud_suspended:
        return 0
    try:
        controller = get_pc()
        if controller is None or controller.bDeleteMe or not _is_maya_controller(controller):
            return 0
        pawn = controller.Pawn
        if pawn is None or pawn.bDeleteMe or pawn.Weapon != weapon or weapon.Instigator != pawn:
            return 0
        definition = unrealsdk.find_object("SkillDefinition", BLIGHT_PHOENIX_PATH)
        skill = _blight_phoenix_active_skill(controller, definition)
        if skill is None:
            return 0
        damage_types = unrealsdk.find_enum("EDamageType")
        if not any(weapon.DoesDamageType(element) for element in (
            damage_types.DAMAGE_TYPE_Incindiary, damage_types.DAMAGE_TYPE_Shock,
            damage_types.DAMAGE_TYPE_Corrosive, damage_types.DAMAGE_TYPE_Amp,
        )):
            return 0  # Explosive-only and non-elemental guns retain normal cost.
        return int(skill.Grade)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not read Blight Phoenix ammo eligibility: {exc}")
        return 0


def _blight_phoenix_current_shot_weapon(address: int) -> Any | None:
    """Re-resolve a locally owned gun; never dereference a retained actor after travel."""
    if _cooldown_hud_suspended:
        return None
    controller = get_pc()
    if controller is None or controller.bDeleteMe:
        return None
    pawn = controller.Pawn
    if pawn is None or pawn.bDeleteMe:
        return None
    current = pawn.Weapon
    if current is not None and current._get_address() == address:
        return None if current.bDeleteMe else current
    # A custom firing behavior may switch guns synchronously. Restore the old
    # gun only if found anew in the CURRENT inventory, not through a saved actor.
    inventory = pawn.InvManager
    item = inventory.ItemChain if inventory is not None else None
    for _ in range(40):
        if item is None:
            break
        if item._get_address() == address:
            return None if item.bDeleteMe else item
        item = item.Inventory
    return None


@hook("WillowGame.WillowWeapon:ConsumeAmmo", Type.PRE)
def preserve_blight_phoenix_shot_resources(
    weapon: UObject, _args: Any, _ret: Any, _func: Any,
) -> type[Block] | None:
    # ConsumeAmmo blocking alone supplies free reloads, NOT an unchanged magazine
    # (see Apple's Borderlands Cheats). The paired firing hooks handle the clip.
    if not _blight_phoenix_shot_contexts or _cooldown_hud_suspended:
        return None
    context = _blight_phoenix_shot_contexts[-1]
    if not context["saved"] or context["weapon"] != weapon._get_address():
        return None
    cost = int(weapon.ShotCost)
    if cost != 0:
        context["restore_cost"] = cost  # Preserve a native recomputation during fire.
        weapon.ShotCost = 0
    return Block


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.PRE)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.PRE)
def blight_phoenix_save_elemental_ammo(
    weapon: UObject, _args: Any, _ret: Any, _func: Any,
) -> None:
    """Prepare cost without executing native fire ahead of other PRE hooks."""
    _blight_phoenix_fire_calls.append(None)  # Pair ignored and nested calls too.
    try:
        rank = _blight_phoenix_ammo_rank(weapon)
        if rank <= 0:
            return
        address = weapon._get_address()
        if any(context["weapon"] == address for context in _blight_phoenix_shot_contexts):
            return  # SharedFire inside Fire is the SAME shot, including failed rolls.
        cost, before = int(weapon.ShotCost), int(weapon.ReloadCnt)
        if cost <= 0 or before <= 0:
            return  # Preserve already-free weapons and empty-magazine restrictions.
        chance = min(1.0, BLIGHT_PHOENIX_AMMO_CHANCE_PER_RANK * rank)
        context = dict(weapon=address, restore_cost=cost, before=before, rank=rank,
                       chance=chance, executed=False,
                       saved=chance >= 1.0 or random.random() < chance)
        _blight_phoenix_shot_contexts.append(context)
        _blight_phoenix_fire_calls[-1] = context
        if context["saved"]:
            weapon.ShotCost = 0
        if context["saved"] and int(weapon.ShotCost) != 0:
            raise ValueError("Blight Phoenix zero shot cost was not retained")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not prepare Blight Phoenix ammo saving: {exc}")


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST)
def mark_blight_phoenix_native_shot(_weapon: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    # BL2's SDK dispatches conditional POST before POST_UNCONDITIONAL cleanup.
    if _blight_phoenix_fire_calls and _blight_phoenix_fire_calls[-1] is not None:
        _blight_phoenix_fire_calls[-1]["executed"] = True


@hook("WillowGame.WillowWeapon:FireAmmunition", Type.POST_UNCONDITIONAL)
@hook("WillowGame.WillowWeapon:SharedFireAmmunition", Type.POST_UNCONDITIONAL)
def finish_blight_phoenix_shot(_weapon: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    """Verify real fire and restore cost even when another PRE cancelled it."""
    global _blight_phoenix_last_ammo_log
    if not _blight_phoenix_fire_calls:
        return
    context = _blight_phoenix_fire_calls.pop()
    if context is None:
        return
    if not _blight_phoenix_shot_contexts or _blight_phoenix_shot_contexts[-1] is not context:
        _log_error_once("Blight Phoenix fire hooks were not paired")
        return
    _blight_phoenix_shot_contexts.pop()
    address = context["weapon"]
    try:
        if not context["executed"] or not context["saved"]:
            return
        current = _blight_phoenix_current_shot_weapon(address)
        if current is None:
            return
        before = context["before"]
        after_native = int(current.ReloadCnt)
        if 0 <= after_native < before:
            # Correct only THIS shot's observed loss. Never refill the entire clip
            # or touch the reserve, and preserve any independent ammo gains.
            current.ReloadCnt = before
        after = int(current.ReloadCnt)
        if after < before:
            raise ValueError(f"Blight Phoenix magazine still decreased: {before}->{after}")
        state = (get_pc()._get_address(), address, context["rank"])
        if state != _blight_phoenix_last_ammo_log:
            _blight_phoenix_last_ammo_log = state
            unrealsdk.logging.info(
                f"[MayaRebalance] Blight Phoenix zero-cost shot verified: rank={context['rank']}, "
                f"chance={context['chance']:g}, clip_before={before}, clip_after_native={after_native}, "
                f"clip_final={after}, normal_cost={context['restore_cost']}, weapon={current._path_name()}"
            )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not apply Blight Phoenix ammo saving: {exc}")
    finally:
        try:
            current = _blight_phoenix_current_shot_weapon(address)
            if context["saved"] and current is not None and int(current.ShotCost) == 0:
                current.ShotCost = context["restore_cost"]
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not restore Blight Phoenix shot cost: {exc}")


def _set_sweet_release_projectile_speed() -> None:
    """Set the configured healing-orb speed, preserving other projectile inputs."""
    projectile = unrealsdk.find_object("ProjectileDefinition", SWEET_RELEASE_PROJECTILE_PATH)
    if abs(float(projectile.SpeedFormula.BaseValueConstant) - SWEET_RELEASE_PROJECTILE_SPEED) <= 0.000001:
        return
    speed_formula = copy.copy(projectile.SpeedFormula)
    speed_formula.BaseValueConstant = SWEET_RELEASE_PROJECTILE_SPEED
    projectile.SpeedFormula = speed_formula
    if abs(float(projectile.SpeedFormula.BaseValueConstant) - SWEET_RELEASE_PROJECTILE_SPEED) > 0.000001:
        raise ValueError("Sweet Release projectile did not retain its speed override")
    unrealsdk.logging.info(
        "[MayaRebalance] Set Sweet Release projectile speed "
        f"to {SWEET_RELEASE_PROJECTILE_SPEED:g}"
    )


def _set_behavior_damage_scale(behavior: Any, field: str, scale: float) -> None:
    """Set an absolute scale, preserving the engine's linked damage inputs."""
    original = getattr(behavior, field)
    if abs(float(original.BaseValueScaleConstant) - scale) <= 0.000001:
        return
    value = copy.copy(original)
    value.BaseValueScaleConstant = scale
    setattr(behavior, field, value)
    if not _scaling_formula_matches(getattr(behavior, field), value):
        raise ValueError(f"Native damage scale was not retained: {behavior._path_name()} {field}")


def _prepare_helios_level_damage(behavior: Any, multiplier: float) -> None:
    # Native Helios includes its actual skill grade (including class mods).
    # Apply the linear bonus through the native rank-sensitive initializer.
    initializer = unrealsdk.find_object("AttributeInitializationDefinition", HELIOS_DAMAGE_INITIALIZER_PATH)
    damage = _native_damage_input(behavior.DamageFormula, 0.0, .2 * multiplier, initializer=initializer)
    if not _scaling_formula_matches(behavior.DamageFormula, damage):
        behavior.DamageFormula = damage
    if not _scaling_formula_matches(behavior.DamageFormula, damage):
        raise ValueError("Helios did not retain its native rank-based damage input")
    # The graph supplies this value. Preserve its base/initializer after binding.
    _set_behavior_damage_scale(behavior, "StatusEffectDamage", multiplier)


def _configure_helios_level_damage() -> None:
    behavior = unrealsdk.find_object("Behavior_CauseDamage", HELIOS_DAMAGE_BEHAVIOR_PATH)
    _prepare_helios_level_damage(behavior, 1.0)
    unrealsdk.logging.info("[MayaRebalance] Helios native rank/level damage configured; linear bonus stages1..90")


def _configure_phaselock_direct_damage() -> None:
    for path in PHASELOCK_DIRECT_DAMAGE_PATHS:
        behavior = unrealsdk.find_object("Behavior_CauseDamage", path)
        _set_behavior_damage_scale(behavior, "DamageFormula", PHASELOCK_DIRECT_DAMAGE_MULTIPLIER)
    unrealsdk.logging.info("[MayaRebalance] Phaselock native direct damage configured: multiplier=1.75")


def _configure_backdraft_damage() -> None:
    nova = unrealsdk.find_object("Behavior_Explode", BACKDRAFT_NOVA_BEHAVIOR_PATH)
    # Prepare native baseline before a caster exists; PRE applies the live rank.
    _prepare_backdraft_damage(nova)
    radius = _native_damage_input(nova.DamageRadiusFormula, BACKDRAFT_NOVA_RADIUS)
    if not _scaling_formula_matches(nova.DamageRadiusFormula, radius):
        nova.DamageRadiusFormula = radius
    if not _scaling_formula_matches(nova.DamageRadiusFormula, radius):
        raise ValueError("Backdraft did not retain its native radius plus15%")
    fire = unrealsdk.find_object("Behavior_CauseDamage", BACKDRAFT_MELEE_BEHAVIOR_PATH)
    _prepare_backdraft_damage(fire)
    unrealsdk.logging.info(
        f"[MayaRebalance] Backdraft damage configured: nova_radius={BACKDRAFT_NOVA_RADIUS:g}, "
        f"final_damage_per_rank={BACKDRAFT_FINAL_DAMAGE_PER_RANK:g}"
    )


def _backdraft_damage_rank(context: Any) -> int:
    """Resolve the actual caster, never a local-player fallback or cached actor."""
    if context is None or getattr(context, "bDeleteMe", False):
        return 0
    controller = context if str(context.Class.Name) == "WillowPlayerController" else None
    if controller is None:
        # Known native contexts: player pawn, skill instance, action skill.
        controller = (getattr(context, "Controller", None) or getattr(context, "SkillInstigator", None)
                      or getattr(context, "MyController", None))
    if (controller is None or getattr(controller, "bDeleteMe", False)
            or str(controller.Class.Name) != "WillowPlayerController"):
        return 0
    return max(0, int(_skill_rank(controller, BACKDRAFT_PATH)))


def _prepare_backdraft_damage(behavior: Any, context: Any = None) -> tuple[int, float]:
    """Apply one absolute author factor over native level/grade damage."""
    path = str(behavior._path_name())
    if path not in (BACKDRAFT_NOVA_BEHAVIOR_PATH, BACKDRAFT_MELEE_BEHAVIOR_PATH):
        raise ValueError("Unexpected Backdraft damage behavior")
    rank = _backdraft_damage_rank(context)
    scale = 1.0 + BACKDRAFT_FINAL_DAMAGE_PER_RANK * rank
    # Native BPD math already supplies level and grade. Never multiply its last
    # cast's result or derive the fire base from the completed Scorn beam hit.
    for field in ("DamageFormula", "StatusEffectDamage"):
        _set_behavior_damage_scale(behavior, field, scale)
    return rank, scale


def _native_damage_input(
    original: Any, base: float, scale: float = 1.0, *, initializer: Any = None, attribute: Any = None,
) -> Any:
    formula = copy.copy(original)
    formula.BaseValueConstant = base
    formula.BaseValueAttribute = attribute
    formula.InitializationDefinition = initializer
    formula.BaseValueScaleConstant = scale
    return formula


def _scaling_formula_matches(actual: Any, expected: Any) -> bool:
    return all(getattr(actual, field) == getattr(expected, field) for field in (
        "BaseValueConstant", "BaseValueAttribute", "InitializationDefinition", "BaseValueScaleConstant",
    ))


def _configure_backdraft_scorn() -> None:
    """Keep the working Scorn-only bridge; remove automatic melee dispatch.

    A private copy of the *same slag* definition identifies only these beams.
    The legacy BPD event label remains an explicit entry point, not a listener.
    Preserve the original rank/level math and shield-depletion nova chain.
    """
    global _backdraft_scorn_damage_type
    definition = unrealsdk.find_object("SkillDefinition", BACKDRAFT_PATH)
    area = unrealsdk.find_object("WillowDamageArea", SCORN_DAMAGE_AREA_PATH)
    template = unrealsdk.find_object("WillowDamageTypeDefinition", BACKDRAFT_SCORN_SLAG_TEMPLATE_PATH)
    skill_source = unrealsdk.find_class("WillowDmgSource_Skill")
    if area.DamageSource != skill_source:
        raise ValueError("Scorn beams must retain their Skill damage source")
    if (area.DamageTypeDefinition != template
            and (_backdraft_scorn_damage_type is None or area.DamageTypeDefinition != _backdraft_scorn_damage_type)):
        raise ValueError("Scorn beams have an unexpected damage type; refusing to overwrite it")

    events = list(definition.DamageEvents)
    # Removing the row is essential: an empty constraint array could mean an
    # unrestricted listener and recurse on Backdraft's own fire damage.
    remaining = [event for event in events if str(event.EventName) != BACKDRAFT_MELEE_EVENT_NAME]

    if _backdraft_scorn_damage_type is None:
        owner = unrealsdk.find_object("SkillDefinition", SCORN_PATH)
        damage_type = unrealsdk.construct_object(
            "WillowDamageTypeDefinition", owner, "VH_Scorn_Backdraft_Slag",
            flags=int(ObjectFlags.KEEP_ALIVE), template_obj=template,
        )
        if damage_type == template:
            raise ValueError("Scorn needs a private slag definition, not the shared original")
        # Cloning changes identity ONLY, not element, status or resistance rules.
        for field in ("DamageType", "StatusEffect", "CharacterDamageTypeModifierAttribute"):
            if getattr(damage_type, field) != getattr(template, field):
                raise ValueError(f"Scorn private slag did not preserve {field}")
        for field in ("FleshDamageModifier", "ArmorDamageModifier", "ShieldDamageModifier"):
            if not _scaling_formula_matches(getattr(damage_type, field), getattr(template, field)):
                raise ValueError(f"Scorn private slag did not preserve {field}")
        _backdraft_scorn_damage_type = damage_type  # Static definition; never a live actor.
    damage_type = _backdraft_scorn_damage_type

    # Also migrate older private/generic Scorn constraints by removing their
    # entire legacy row. Do not modify unrelated damage events or the BPD.
    def signature(event: Any) -> tuple:
        return (str(event.EventName), int(event.EventType), tuple(
            (c.DamageSourceConstraint, c.DamageTypeConstraint,
             bool(c.bMustBeCriticalDamage), bool(c.bMustBeOneShotKill))
            for c in event.EventConstraints
        ))

    expected_events = tuple(signature(event) for event in remaining)
    if len(remaining) != len(events):
        definition.DamageEvents = [copy.copy(event) for event in remaining]
    actual = list(definition.DamageEvents)
    if (tuple(signature(event) for event in actual) != expected_events
            or any(str(event.EventName) == BACKDRAFT_MELEE_EVENT_NAME for event in actual)):
        raise ValueError("Backdraft did not retain removal of its melee listener")
    if area.DamageTypeDefinition != damage_type:
        area.DamageTypeDefinition = damage_type
    if area.DamageTypeDefinition != damage_type or area.DamageSource != skill_source:
        raise ValueError("Scorn did not retain its private slag marker and Skill source")
    _configure_backdraft_description(definition)
    unrealsdk.logging.info(
        "[MayaRebalance] Backdraft/Scorn completed-hit bridge configured: beams only, private slag; "
        "melee listener removed; shield nova preserved"
    )


def _backdraft_damage_effect_matches(effect: Any, attribute: Any) -> bool:
    return (
        effect.AttributeToModify == attribute
        and int(effect.ModifierType) == int(unrealsdk.find_enum("EModifierType").MT_Scale)
        and int(effect.EffectTarget) == 1  # TARGET_Self: the skill's instigator.
        and int(effect.GradeToStartApplyingEffect) == 1
        and int(effect.PerGradeUpgradeInterval) == 1 and not effect.BonusUpgradeList
        and all(
            abs(float(value.BaseValueConstant) - BACKDRAFT_SKILL_DAMAGE_PER_RANK) <= .000001
            and value.BaseValueAttribute is None and value.InitializationDefinition is None
            and abs(float(value.BaseValueScaleConstant) - 1.0) <= .000001
            for value in (effect.BaseModifierValue, effect.PerGradeUpgrade)
        )
    )


def _configure_backdraft_skill_damage(controller: Any = None) -> None:
    """One native passive effect; no damage hooks, global formulas or actor caches."""
    global _backdraft_skill_damage_attribute
    manager = controller.GetSkillManager() if controller is not None else None
    if manager is not None and manager.bUpdatingSkills:
        return
    definition = unrealsdk.find_object("SkillDefinition", BACKDRAFT_PATH)
    attribute = _backdraft_skill_damage_attribute
    if attribute is None:
        # The Controller property exists, but BL2 has no packaged Skill leaf.
        # Clone a controller-context attribute and ONLY its value resolver.
        template = unrealsdk.find_object(
            "AttributeDefinition", "D_Attributes.DamageSourceModifiers.InstigatedBulletDamageModifier",
        )
        attribute = unrealsdk.construct_object(
            "AttributeDefinition", definition, "MR_Backdraft_SkillDamage",
            template_obj=template, flags=ObjectFlags.KEEP_ALIVE,
        )
        resolver = unrealsdk.construct_object(
            "ObjectPropertyAttributeValueResolver", attribute, "SkillDamageValue",
            template_obj=template.ValueResolverChain[0], flags=ObjectFlags.KEEP_ALIVE,
        )
        resolver.PropertyName = BACKDRAFT_SKILL_DAMAGE_FIELD
        resolver.CachedProperty = None
        attribute.ValueResolverChain = [resolver]
        if (len(attribute.ValueResolverChain) != 1
                or str(attribute.ValueResolverChain[0].PropertyName) != BACKDRAFT_SKILL_DAMAGE_FIELD):
            raise ValueError("Backdraft did not retain its private skill-damage resolver")
        _backdraft_skill_damage_attribute = attribute
    effects = list(definition.SkillEffectDefinitions)
    matches = [i for i, effect in enumerate(effects) if effect.AttributeToModify == attribute]
    if len(matches) > 1:
        raise ValueError("Backdraft has duplicate skill-damage effects")
    index = matches[0] if matches else None
    desired = effects[index] if index is not None else None
    if desired is None or not _backdraft_damage_effect_matches(desired, attribute):
        # Own all rows before replacing the reflected array. The original
        # TARGET_None row carries rank for the nova/fire graph; it is not a
        # passive melee buff and must remain even after retiring melee events.
        effects = [copy.copy(effect) for effect in effects]
        desired = copy.copy(effects[index] if index is not None else effects[0])
        desired.AttributeToModify = attribute
        desired.EffectTarget = 1
        desired.ModifierType = unrealsdk.find_enum("EModifierType").MT_Scale
        desired.GradeToStartApplyingEffect = desired.PerGradeUpgradeInterval = 1
        desired.BonusUpgradeList = []
        _set_effect_value(desired, BACKDRAFT_SKILL_DAMAGE_PER_RANK)
        if index is None:
            effects.append(desired)
        else:
            effects[index] = desired
        definition.SkillEffectDefinitions = effects
        desired = next(effect for effect in definition.SkillEffectDefinitions
                       if effect.AttributeToModify == attribute)
        if not _backdraft_damage_effect_matches(desired, attribute):
            raise ValueError("Backdraft did not retain its skill-damage effect")
        unrealsdk.logging.info(
            f"[MayaRebalance] Backdraft passive Skill Damage configured: +{BACKDRAFT_SKILL_DAMAGE_PER_RANK * 100:g}% per rank"
        )
    if manager is None:
        return
    rank = _skill_rank(controller, BACKDRAFT_PATH)
    for skill in manager.ActiveSkills:
        if skill.Definition != definition or skill.SkillInstigator != controller:
            continue
        if int(skill.Grade) != rank:
            skill.UpdateGrade(rank)  # Existing rank/COM logic, no activation or graph restart.
        if rank <= 0:
            continue
        applied = [effect for effect in skill.SkillEffects
                   if effect.EffectData.AttributeToModify == attribute]
        if len(applied) > 1:
            raise ValueError("Backdraft has duplicate active skill-damage effects")
        if not applied:
            skill.AddSkillEffect(controller, copy.copy(desired))
            if sum(effect.EffectData.AttributeToModify == attribute for effect in skill.SkillEffects) != 1:
                raise ValueError("Backdraft did not retain its active skill-damage effect")
        elif not _backdraft_damage_effect_matches(applied[0].EffectData, attribute):
            migrated = [copy.copy(effect) for effect in skill.SkillEffects]
            for effect in migrated:
                if effect.EffectData.AttributeToModify == attribute:
                    effect.EffectData = copy.copy(desired)
            skill.SkillEffects = migrated
            skill.bForceRefreshModifiersNextTick = True


def _configure_backdraft_description(definition: Any = None) -> None:
    """Replace retired melee wording, keeping the native Backdraft damage rank."""
    if definition is None:
        definition = unrealsdk.find_object("SkillDefinition", BACKDRAFT_PATH)
    expected = BACKDRAFT_DESCRIPTION
    if str(definition.SkillDescription) != expected:
        definition.SkillDescription = expected
    if str(definition.SkillDescription) != expected:
        raise ValueError("Backdraft did not retain its Scorn description sentence")


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def preserve_backdraft_description(
    _tree: UObject, args: WrappedStruct, _ret: Any, func: Any,
) -> tuple[type[Block], str] | None:
    if _cooldown_hud_suspended:
        return
    definition = args.SkillDef
    if definition and str(definition._path_name()) == BACKDRAFT_PATH:
        try:
            _configure_backdraft_description(definition)
            grade = max(0, int(args.Grade))
            # Native Grade already includes the COM bonus; GradeModifier is metadata.
            rank = min(CLASS_MODDED_SKILL_RANK_LIMIT, grade)
            owner = args.PlayerOwner
            can_add = (grade < BASE_SKILL_RANK_LIMIT or not args.bIncludeHTML or owner is None
                       or int(owner.GetSkillGrade(definition)) < BASE_SKILL_RANK_LIMIT)
            native = _native_ranked_skill_text(func, args)
            line = _format_percentage_progression(
                "Skill Damage", BACKDRAFT_SKILL_DAMAGE_PER_RANK * 100, rank, can_add, show_plus=True,
            )
            return Block, native + ("<br>" if args.bIncludeHTML else "\n") + line
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not update Backdraft description: {exc}")


@hook("WillowGame.WillowAIPawn:TakeDamage", Type.PRE)
def begin_backdraft_scorn_hit(pawn: UObject, args: WrappedStruct, _ret: Any, _func: Any) -> None:
    """Pair every invocation, including blocked calls; store NO live objects."""
    context = None
    try:
        if not _cooldown_hud_suspended and _backdraft_scorn_damage_type is not None and args.InstigatedBy:
            source = getattr(args, "DamageType", None)  # TakeDamage's native UClass source, not its elemental definition.
            field = SLAGGER_SOURCE_FIELDS.get(str(source._path_name())) if source is not None else None
            if field is None or field == "ReceivedSkillDamageModifier":
                context = {
                    "target_address": pawn._get_address(),
                    "instigator_address": args.InstigatedBy._get_address(),
                    "summary": None,
                }
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not begin Backdraft/Scorn hit: {exc}")
    _backdraft_scorn_hit_contexts.append(context)


def _capture_backdraft_scorn_hit(pipeline: Any, args: Any, summary: Any) -> None:
    """Copy only scalars before native code can reuse/reset its pipeline."""
    controller = args.InDamageInstigator
    if (not args.InDamagedActor or controller is None or getattr(controller, "bDeleteMe", False)
            or args.InDamageSource != unrealsdk.find_class("WillowDmgSource_Skill")):
        return
    context = _backdraft_scorn_hit_contexts[-1] if _backdraft_scorn_hit_contexts else None
    if context is not None and (
            args.InDamagedActor._get_address() != context["target_address"]
            or controller._get_address() != context["instigator_address"]):
        return
    if _skill_rank(controller, BACKDRAFT_PATH) <= 0:
        return  # No valid allocation: no fire bridge and no missing-context error.
    if context is None:
        _log_error_once("Backdraft/Scorn beam has no AI TakeDamage context")
        return
    health, shield = max(0.0, float(summary.FinalDamage)), max(0.0, float(summary.DamageDealtToShields))
    if health + shield <= 0.0 or context["summary"] is not None:
        return
    context["summary"] = {
        "HealthDamageDone": health, "ShieldDamageDone": shield,
        "bWasCrit": bool(summary.bWasCrit), "bWasInjured": bool(summary.bWasInjured),
        "ExcessDamageDone": max(0.0, health - float(summary.PreviousHealth)),
        "PenetrationCount": int(pipeline.PenetrationCount),
    }


@hook("WillowGame.WillowAIPawn:TakeDamage", Type.POST_UNCONDITIONAL)
def finish_backdraft_scorn_hit(pawn: UObject, args: WrappedStruct, _ret: Any, _func: Any) -> None:
    """Run only after the original hit, bypassing native source-event filters.

    The old manager hook was not observed delivering these hits. TakeDamage is
    a script event; AdjustDamage already demonstrably reaches our pipeline hook.
    OnDamagedEnemy explicitly supplies the native graph with its own consumer,
    instigator, target and completed damage. No shared source/type is rewritten.
    """
    if not _backdraft_scorn_hit_contexts:
        return
    context = _backdraft_scorn_hit_contexts.pop()
    if context is None or _cooldown_hud_suspended or context["summary"] is None:
        return
    try:
        controller = args.InstigatedBy
        if (pawn.bDeleteMe or not controller or getattr(controller, "bDeleteMe", False)
                or pawn._get_address() != context["target_address"]
                or controller._get_address() != context["instigator_address"]
                or _skill_rank(controller, BACKDRAFT_PATH) <= 0
                or not pawn.Controller or float(pawn.GetHealth()) <= 0.0):
            return
        for skill in controller.GetSkillManager().ActiveSkills:
            if (skill.Definition and str(skill.Definition._path_name()) == BACKDRAFT_PATH
                    and skill.SkillInstigator == controller and int(skill.Grade) > 0 and int(skill.SkillState) == 1):
                handle = skill.GetBehaviorConsumerHandle()
                if int(handle.PID) == 0:
                    raise ValueError("Backdraft has no valid native behavior consumer")
                now = time.monotonic()
                if now >= _backdraft_scorn_next_damage_logs.get("dispatch", 0.0):
                    unrealsdk.logging.info(
                        f"[MayaRebalance] Backdraft/Scorn completed beam -> native fire event: "
                        f"rank={int(skill.Grade)}, PID={int(handle.PID)}, target={pawn._path_name()}"
                    )
                    _backdraft_scorn_next_damage_logs["dispatch"] = now + 2.0
                # Call the actual BPD event, not Skill.NotifySkillDamagedEvent.
                # Keyword order is checked against the reflected SDK signature.
                skill.Definition.OnDamagedEnemy(
                    ConsumerHandle=handle, SpecializedEventName=BACKDRAFT_MELEE_EVENT_NAME,
                    SkillInstigator=controller, Enemy=pawn.Controller,
                    HitLocation=args.HitLocation, **context["summary"],
                )
                return  # Never trigger twice for duplicate passive instances.
        if _skill_rank(controller, BACKDRAFT_PATH) > 0:
            _log_error_once("Backdraft/Scorn completed beam found no active native Backdraft instance")
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not dispatch completed Scorn hit to Backdraft: {exc}")


@hook("WillowGame.Behavior_CauseDamage:ApplyBehaviorToContext", Type.PRE)
@hook("WillowGame.Behavior_Explode:ApplyBehaviorToContext", Type.PRE)
def begin_backdraft_fire_trace(behavior: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    path = str(behavior._path_name())
    if path == BACKDRAFT_NOVA_BEHAVIOR_PATH:
        if _cooldown_hud_suspended:
            return
        try:
            rank, scale = _prepare_backdraft_damage(behavior, getattr(_args, "ContextObject", None))
            now = time.monotonic()
            if now >= _backdraft_scorn_next_damage_logs.get("nova", 0.0):
                unrealsdk.logging.info(
                    f"[MayaRebalance] Backdraft nova damage prepared: rank={rank}, final_scale={scale:g}"
                )
                _backdraft_scorn_next_damage_logs["nova"] = now + 2.0
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not prepare Backdraft nova damage: {exc}")
        return
    if path in RUIN_DAMAGE_BEHAVIOR_PATHS:
        record = {"path": path, "damage_type": None, "hits": 0}
        _ruin_native_damage_stack.append(record)
        if not _cooldown_hud_suspended:
            try:
                record["damage_type"] = str(behavior.DamageTypeDefinition._path_name())
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _log_error_once(f"Could not prepare Ruin native damage trace: {exc}")
    if path == BACKDRAFT_MELEE_BEHAVIOR_PATH:
        # Prepare this input and trace it; no extra damage calls or cached actors.
        _backdraft_fire_trace_stack.append(not _cooldown_hud_suspended)
        if not _cooldown_hud_suspended:
            try:
                rank, scale = _prepare_backdraft_damage(behavior, getattr(_args, "ContextObject", None))
                now = time.monotonic()
                if now >= _backdraft_scorn_next_damage_logs.get("behavior", 0.0):
                    formula = behavior.DamageFormula
                    unrealsdk.logging.info(
                        f"[MayaRebalance] Backdraft native fire behavior reached: "
                        f"base={float(formula.BaseValueConstant):g}, scale={scale:g}, rank={rank}"
                    )
                    _backdraft_scorn_next_damage_logs["behavior"] = now + 2.0
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _log_error_once(f"Could not trace Backdraft fire behavior: {exc}")


@hook("WillowGame.Behavior_CauseDamage:ApplyBehaviorToContext", Type.POST_UNCONDITIONAL)
def end_backdraft_fire_trace(behavior: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    path = str(behavior._path_name())
    if path in RUIN_DAMAGE_BEHAVIOR_PATHS and _ruin_native_damage_stack:
        record = _ruin_native_damage_stack.pop()
        if not _cooldown_hud_suspended and record["hits"] == 0:
            now = time.monotonic()
            if now >= _ruin_native_damage_log_at.get(path, 0.0):
                unrealsdk.logging.info(
                    f"[MayaRebalance] Ruin native damage trace: behavior={path}, pipeline_hits=0"
                )
                _ruin_native_damage_log_at[path] = now + 2.0
    if path == BACKDRAFT_MELEE_BEHAVIOR_PATH and _backdraft_fire_trace_stack:
        _backdraft_fire_trace_stack.pop()


def _trace_ruin_native_damage(pipeline: Any, args: Any, summary: Any) -> None:
    """Observe actual damage, not the prepared formula; never modify the summary."""
    if _cooldown_hud_suspended or not _ruin_native_damage_stack:
        return
    try:
        record = _ruin_native_damage_stack[-1]
        source = args.InDamageSource
        if source is None or SLAGGER_SOURCE_FIELDS.get(str(source._path_name())) != "ReceivedSkillDamageModifier":
            return
        damage_type = pipeline.GetDamageTypeDef()
        if damage_type is None or str(damage_type._path_name()) != record["damage_type"]:
            return
        record["hits"] += 1
        now = time.monotonic()
        path = record["path"]
        if now < _ruin_native_damage_log_at.get(path, 0.0):
            return
        unrealsdk.logging.info(
            f"[MayaRebalance] Ruin native direct hit: behavior={path}, "
            f"incoming={float(args.IncomingDamage):g}, health={float(summary.FinalDamage):g}, "
            f"shield={float(summary.DamageDealtToShields):g}"
        )
        _ruin_native_damage_log_at[path] = now + 2.0
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not inspect Ruin native direct damage: {exc}")


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.POST)
def log_backdraft_scorn_damage(pipeline: UObject, args: WrappedStruct, ret: Any, _func: Any) -> None:
    """Sample actual native summaries; fire samples can also be normal melee."""
    if _immolate_hit_contexts:
        _capture_immolate_source_hit(pipeline, args, ret)
    if _ruin_native_damage_stack:
        _trace_ruin_native_damage(pipeline, args, ret)
    if _cooldown_hud_suspended or _backdraft_scorn_damage_type is None:
        return
    try:
        source = args.InDamageSource
        field = SLAGGER_SOURCE_FIELDS.get(str(source._path_name())) if source is not None else None
        if (field is not None and field != "ReceivedSkillDamageModifier"
                and not (_backdraft_fire_trace_stack and _backdraft_fire_trace_stack[-1])):
            return  # Ricochet/ordinary bullet hits cannot be Scorn's private Skill beam.
        damage_type = pipeline.GetDamageTypeDef()
        if damage_type == _backdraft_scorn_damage_type:
            kind = "beam"
            # Capture EVERY hit before applying the diagnostics' log throttle.
            _capture_backdraft_scorn_hit(pipeline, args, ret)
        elif (_backdraft_fire_trace_stack and _backdraft_fire_trace_stack[-1] and damage_type
              and str(damage_type._path_name()) == IMMOLATE_IMPACT_DAMAGE_TYPE_PATH):
            kind = "fire"
        else:
            return
        now = time.monotonic()
        if now < _backdraft_scorn_next_damage_logs.get(kind, 0.0):
            return
        controller = args.InDamageInstigator
        rank = _skill_rank(controller, BACKDRAFT_PATH) if controller else 0
        target = args.InDamagedActor
        unrealsdk.logging.info(
            f"[MayaRebalance] Backdraft/Scorn native {kind} hit: rank={rank}, "
            f"incoming={float(args.IncomingDamage):g}, health={float(ret.FinalDamage):g}, "
            f"shield={float(ret.DamageDealtToShields):g}, target={target._path_name() if target else 'None'}"
        )
        _backdraft_scorn_next_damage_logs[kind] = now + 2.0
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not trace Backdraft/Scorn native damage: {exc}")


def _skill_damage_bonus(skill: str, stage: int) -> float:
    """Linear bonus at stages1..90; hold the tail, stage0 means no caster."""
    points = SKILL_DAMAGE_BONUS_ANCHORS[skill]
    if stage < points[0][0]:
        return 0.0
    for (left, low), (right, high) in zip(points, points[1:]):
        if stage <= right:
            return low + (high - low) * (stage - left) / (right - left)
    return points[-1][1]


def _get_level_damage_initializer(skill: str) -> Any:
    """Own native level-only exponent, independent of the shared skill/status curves."""
    cached = _level_damage_initializers.get(skill)
    if cached is not None:
        return cached
    base = SKILL_LEVEL_DAMAGE_BASES[skill]
    template = unrealsdk.find_object("AttributeInitializationDefinition", PLAYER_MELEE_BASE_INITIALIZER_PATH)
    owner = unrealsdk.find_object("SkillDefinition", RUIN_PATH if skill == "Ruin" else SCORN_PATH)
    scaler = unrealsdk.find_object("AttributeDefinition", SKILL_LEVEL_SCALER_PATH)
    stage = unrealsdk.find_object("AttributeDefinition", SKILL_GAME_STAGE_PATH)
    initializer = unrealsdk.construct_object(
        "AttributeInitializationDefinition", owner, f"MR_{skill}_LevelOnly",
        flags=int(ObjectFlags.KEEP_ALIVE), template_obj=template,
    )
    # The template supplies native mode/rounding/schema; configure the curve below.
    formula = copy.copy(template.ValueFormula)
    formula.bEnabled = True
    formula.Multiplier = _native_damage_input(formula.Multiplier, base)
    formula.Level = _native_damage_input(formula.Level, 0.0, attribute=scaler)
    formula.Power = _native_damage_input(formula.Power, 0.0, attribute=stage)
    formula.Offset = _native_damage_input(formula.Offset, 0.0)
    initializer.ValueFormula = formula
    for field in ("ConditionalInitialization", "RandomVariance"):
        value = copy.copy(getattr(initializer, field))
        value.bEnabled = False
        setattr(initializer, field, value)
    limits = copy.copy(initializer.RangeRestriction)
    limits.bEnableMinValueRestriction = limits.bEnableMaxValueRestriction = False
    initializer.RangeRestriction = limits
    actual = initializer.ValueFormula
    if (not actual.bEnabled or any(
            not _scaling_formula_matches(getattr(actual, field), getattr(formula, field))
            for field in ("Multiplier", "Level", "Power", "Offset"))
            or initializer.ConditionalInitialization.bEnabled or initializer.RandomVariance.bEnabled
            or initializer.RangeRestriction.bEnableMinValueRestriction
            or initializer.RangeRestriction.bEnableMaxValueRestriction):
        raise ValueError(f"{skill} did not retain its private level-only damage definition")
    _level_damage_initializers[skill] = initializer
    return initializer


def _resolved_level_damage_input(original: Any, skill: str, multiplier: float, context: Any = None) -> Any:
    """Resolve once per cast, handing native behaviors a positive scalar value.

    Keep a nonzero seed even before a caster exists. Ruin's original native
    inputs use1; zero seeds were introduced by the level-curve reconstruction.
    """
    initializer = _get_level_damage_initializer(skill)
    data = _native_damage_input(original, 1.0, multiplier, initializer=initializer)
    if context is None:
        return data
    damage = float(initializer.EvaluateInitializationData(data, context, None))
    if not 0.0 < damage < float("inf"):
        raise ValueError(f"{skill} level damage did not evaluate to a positive finite value: {damage}")
    return _native_damage_input(original, damage)


def _set_scorn_level_input(spawn: Any, multiplier: float, context: Any = None) -> None:
    attribute = unrealsdk.find_object("AttributeDefinition", PROJECTILE_DAMAGE_ATTRIBUTE_PATH)
    values = spawn.ChildProjectileBaseValues
    if not values or values[0].Attribute != attribute:
        raise ValueError("Scorn has an unexpected projectile damage binding")
    damage = _resolved_level_damage_input(values[0].BaseValue, "Scorn", multiplier, context)
    if _scaling_formula_matches(values[0].BaseValue, damage):
        return
    # Own every row before replacing the reflected array, preserving other inputs.
    replacement = [copy.copy(row) for row in values]
    replacement[0].BaseValue = damage
    spawn.ChildProjectileBaseValues = replacement
    if not _scaling_formula_matches(spawn.ChildProjectileBaseValues[0].BaseValue, damage):
        raise ValueError("Scorn did not retain its level-damage input")


def _configure_scorn_level_damage() -> None:
    spawn = unrealsdk.find_object("Behavior_SpawnProjectile", SCORN_DAMAGE_SPAWN_PATH)
    area = unrealsdk.find_object("WillowDamageArea", SCORN_DAMAGE_AREA_PATH)
    _set_scorn_level_input(spawn, 1.0)
    attribute = unrealsdk.find_object("AttributeDefinition", PROJECTILE_DAMAGE_ATTRIBUTE_PATH)
    beam = _native_damage_input(area.DamagePerSecond, 0.0, attribute=attribute)
    if not _scaling_formula_matches(area.DamagePerSecond, beam):
        area.DamagePerSecond = beam
    if not _scaling_formula_matches(area.DamagePerSecond, beam):
        raise ValueError("Scorn beams did not retain the projectile's damage")
    unrealsdk.logging.info("[MayaRebalance] Scorn independent level scaling configured; linear bonus stages1..90")


def _restore_ruin_native_bindings(provider: Any) -> None:
    """Keep the original five inputs; undo only our older detached binding groups.

    The native kernel owns the action's execution flow. Preserve its original
    binding metadata and override values only at the existing behavior PRE.
    """
    expected = ["Context", "TargetContext", "StatusEffectDamage", "RadiusFormula", "DamageFormula"]
    retained = ["Context", "TargetContext", "RadiusFormula"]
    found = set()
    sequences = [copy.copy(seq) for seq in provider.BehaviorSequences]
    changed = False
    for seq in sequences:
        links = seq.ConsolidatedVariableLinkData
        behaviors = [copy.copy(row) for row in seq.BehaviorData2]
        sequence_changed = False
        for row in behaviors:
            if row.Behavior is None:
                continue
            path = str(row.Behavior._path_name())
            if path not in RUIN_DAMAGE_BEHAVIOR_PATHS:
                continue
            if path in found:
                raise ValueError(f"Duplicate Ruin behavior: {path}")
            found.add(path)
            packed = int(row.LinkedVariables.ArrayIndexAndLength)
            start, count = packed >> 16, packed & 0xFFFF
            if start < 0 or start + count > len(links):
                raise ValueError(f"Invalid Ruin native bindings: {path}")
            current = links[start:start + count]
            names = [str(link.PropertyName) for link in current]
            if names == expected:
                continue
            if names != retained:
                raise ValueError(f"Unexpected Ruin native binding schema: {path}: {names}")
            # Older versions appended groups instead of deleting originals.
            # Match the original group by its unique context/target/radius links.
            candidates = []
            for i in range(len(links) - 4):
                group = links[i:i + 5]
                if [str(link.PropertyName) for link in group] != expected:
                    continue
                if all(int(group[j].LinkedVariables.ArrayIndexAndLength)
                       == int(current[k].LinkedVariables.ArrayIndexAndLength)
                       for k, j in enumerate((0, 1, 3))):
                    candidates.append(i)
            if len(candidates) != 1:
                raise ValueError(f"Could not identify original Ruin bindings: {path}")
            pointer = copy.copy(row.LinkedVariables)
            pointer.ArrayIndexAndLength = (candidates[0] << 16) | 5
            row.LinkedVariables = pointer
            sequence_changed = True
        if sequence_changed:
            seq.BehaviorData2 = behaviors
            changed = True
    if found != set(RUIN_DAMAGE_BEHAVIOR_PATHS):
        raise ValueError("Native Phaselock graph is missing Ruin behaviors")
    if changed:
        provider.BehaviorSequences = sequences
        unrealsdk.logging.info("[MayaRebalance] Restored original Ruin native input bindings")


def _configure_ruin_level_damage() -> None:
    _get_level_damage_initializer("Ruin")
    # Future action instances must inherit the definition before Initialize/Start.
    # Like native HeliosSkill/CharmSkill references, this grants no skill points.
    action = unrealsdk.find_object("LiftActionSkill", RUIN_DAMAGE_PROVIDER_PATH.split(":", 1)[0])
    if action.RuinSkill is None:
        definition = unrealsdk.find_object("SkillDefinition", RUIN_PATH)
        action.RuinSkill = definition
        if action.RuinSkill != definition:
            raise ValueError("Phaselock archetype did not retain its Ruin definition")
    provider = unrealsdk.find_object("BehaviorProviderDefinition", RUIN_DAMAGE_PROVIDER_PATH)
    _restore_ruin_native_bindings(provider)
    for path in RUIN_DAMAGE_BEHAVIOR_PATHS:
        _preserve_ruin_runtime_scaling(unrealsdk.find_object("Behavior_CauseDamage", path))
    unrealsdk.logging.info("[MayaRebalance] Ruin independent level scaling configured; linear bonus stages1..90")


def _preserve_ruin_runtime_scaling(behavior: Any, multiplier: float = 1.0, context: Any = None) -> None:
    """After native binding, restore both Ruin inputs without replaying damage."""
    if _cooldown_hud_suspended:
        return
    path = str(behavior._path_name())
    if path not in RUIN_DAMAGE_BEHAVIOR_PATHS:
        return
    expected = _resolved_level_damage_input(behavior.DamageFormula, "Ruin", multiplier, context)
    changed = []
    for field in ("DamageFormula", "StatusEffectDamage"):
        current = getattr(behavior, field)
        if not _scaling_formula_matches(current, expected):
            setattr(behavior, field, expected)
            if not _scaling_formula_matches(getattr(behavior, field), expected):
                raise ValueError(f"Ruin runtime formula was not retained: {path} {field}")
            changed.append(field)
    if changed and path not in _logged_ruin_runtime_repairs:
        unrealsdk.logging.info(
            f"[MayaRebalance] Restored Ruin level scaling before damage: behavior={path}, fields={','.join(changed)}"
        )
        _logged_ruin_runtime_repairs.add(path)


def _prepare_ruin_level_damage(controller: Any, action: Any = None) -> None:
    """Prepare trained Ruin before its native event chain, without activating it."""
    global _ruin_level_readiness
    if _cooldown_hud_suspended:
        return
    rank = _invested_skill_rank(controller, RUIN_PATH)
    pawn = controller.Pawn
    if pawn is None or pawn.bDeleteMe:
        return
    stage = max(0, int(pawn.GetGameStage()))
    damage = 0.0
    repaired_definition = False
    if rank > 0:
        # ALiftActionSkill.RuinSkill is a USkillDefinition*, not a live USkill.
        # Restore a missing native definition reference only for trained Ruin.
        if action is not None and action.RuinSkill is None:
            definition = unrealsdk.find_object("SkillDefinition", RUIN_PATH)
            action.RuinSkill = definition
            if action.RuinSkill != definition:
                raise ValueError("Native action did not retain its Ruin definition")
            repaired_definition = True
        multiplier = 1.0 + _skill_damage_bonus("Ruin", stage)
        for path in RUIN_DAMAGE_BEHAVIOR_PATHS:
            behavior = unrealsdk.find_object("Behavior_CauseDamage", path)
            _preserve_ruin_runtime_scaling(behavior, multiplier, pawn)
            damage = float(behavior.DamageFormula.BaseValueConstant)
    state = (controller._get_address(), rank, stage)
    if state != _ruin_level_readiness or repaired_definition:
        _ruin_level_readiness = state
        unrealsdk.logging.info(
            f"[MayaRebalance] Ruin ready for native Phaselock: invested_rank={rank}, "
            f"game_stage={stage}, resolved_damage={damage:g}, native_definition_repaired={repaired_definition}"
        )


@hook("WillowGame.Behavior_CauseDamage:ApplyBehaviorToContext", Type.PRE)
@hook("WillowGame.Behavior_SpawnProjectile:ApplyBehaviorToContext", Type.PRE)
def prepare_skill_level_damage(behavior: UObject, args: WrappedStruct, _ret: Any, _func: BoundFunction) -> None:
    """Set author bonus once per behavior execution, never once per beam hit."""
    path = str(behavior._path_name())
    if _cooldown_hud_suspended or path not in (
        *RUIN_DAMAGE_BEHAVIOR_PATHS, SCORN_DAMAGE_SPAWN_PATH,
        HELIOS_DAMAGE_BEHAVIOR_PATH, *PHASELOCK_DIRECT_DAMAGE_PATHS,
    ):
        return
    try:
        if path in PHASELOCK_DIRECT_DAMAGE_PATHS:
            # Native BPD bindings set the base before PRE. Never multiply the
            # previous cast's value, detach bindings, or touch Ruin/Res damage.
            _set_behavior_damage_scale(behavior, "DamageFormula", PHASELOCK_DIRECT_DAMAGE_MULTIPLIER)
            return
        context = args.ContextObject
        if hasattr(context, "MyWillowPawn"):
            context = context.MyWillowPawn
        # Missing context must not leak the previous caster's bonus. Repair to
        # level-only damage; the engine still resolves its own base context.
        stage = max(0, int(context.GetGameStage())) if context is not None else 0
        skill = ("Scorn" if path == SCORN_DAMAGE_SPAWN_PATH else
                 "Helios" if path == HELIOS_DAMAGE_BEHAVIOR_PATH else "Ruin")
        bonus = _skill_damage_bonus(skill, stage)
        multiplier = 1.0 + bonus
        if skill == "Scorn":
            _set_scorn_level_input(behavior, multiplier, context)
            formula = behavior.ChildProjectileBaseValues[0].BaseValue
        elif skill == "Ruin":
            _preserve_ruin_runtime_scaling(behavior, multiplier, context)
            formula = behavior.DamageFormula
        else:
            _prepare_helios_level_damage(behavior, multiplier)
            formula = behavior.DamageFormula
        if context is None:
            _log_error_once(f"{skill} level-damage context is unavailable; used zero additional bonus")
            return
        key = (path, stage)
        if key in _logged_level_damage_runtime:
            return
        damage_details = (
            f"formula_scale={float(formula.BaseValueScaleConstant):g}, resolved_constant=False"
            if skill == "Helios" else
            f"base_damage={float(formula.BaseValueConstant):g}, resolved_constant=True"
        )
        unrealsdk.logging.info(
            f"[MayaRebalance] {skill} independent scaling runtime: game_stage={stage}, "
            f"additional_bonus={bonus:g}, {damage_details}"
        )
        _logged_level_damage_runtime.add(key)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not prepare skill level damage: {exc}")


def _apply_skill_tuning() -> None:
    global _pending_scorn_cooldown
    global _pending_sweet_release_speed
    global _pending_phaselock_tuning
    global _skill_package_loaded

    if not _skill_package_loaded:
        try:
            unrealsdk.load_package("GD_Siren_Skills")
            unrealsdk.load_package("GD_Siren_Streaming")
            _skill_package_loaded = True
            unrealsdk.logging.info(
                "[MayaRebalance] Loaded GD_Siren_Streaming for skill tuning"
            )
        except (AttributeError, TypeError, ValueError) as exc:
            _log_error_once(f"Could not load Maya skill assets: {exc}")
            return

    try:
        _configure_slagger()
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not configure Elemental Mastery: {exc}")

    try:
        _configure_res_description()
    except (AttributeError, TypeError, ValueError) as exc:
        _log_error_once(f"Could not update Res description: {exc}")

    try:
        _configure_blight_phoenix()
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not configure Blight Phoenix: {exc}")

    try:
        _configure_kinetic_reflection()
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not configure Kinetic Reflection: {exc}")
    try:
        _configure_scorn_description()
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not configure Scorn description: {exc}")

    try:
        _configure_backdraft_skill_damage()
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not configure Backdraft Skill Damage: {exc}")

    try:
        _disable_recompense_native()
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not disable original Recompense: {exc}")

    if _pending_sweet_release_speed:
        try:
            _set_sweet_release_projectile_speed()
            _pending_sweet_release_speed = False
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not tune Sweet Release projectile speed: {exc}")

    for name, apply_tuning in (
        ("Helios", _configure_helios_level_damage),
        ("Backdraft", _configure_backdraft_damage),
        ("Scorn", _configure_scorn_level_damage),
        ("Ruin", _configure_ruin_level_damage),
        ("Phaselock", _configure_phaselock_direct_damage),
        ("BackdraftScorn", _configure_backdraft_scorn),
    ):
        if name not in _pending_damage_tuning:
            continue
        try:
            apply_tuning()
            _pending_damage_tuning.discard(name)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not apply {name} damage tuning: {exc}")

    tuning_operations = {
        FLICKER_PATH: (
            ("D_Attributes.Weapon.WeaponStatusEffectChanceModifier", FLICKER_STATUS_CHANCE_PER_RANK,
             "AttributeDefinition", False),
        ),
        ACCELERATE_PATH: (
            ("D_Attributes.Weapon.WeaponDamage", ACCELERATE_WEAPON_DAMAGE_PER_RANK, "AttributeDefinition", False),
            ("D_Attributes.Weapon.WeaponProjectileSpeedMultiplier", ACCELERATE_PROJECTILE_SPEED_PER_RANK,
             "AttributeDefinition", False),
        ),
        SUSPENSION_PATH: (
            (
                PHASELOCK_DURATION_ATTRIBUTE_PATH,
                SUSPENSION_DURATION_PER_RANK,
                "DesignerAttributeDefinition",
                False,
            ),
        ),
        QUICKEN_PATH: (
            (
                ACTION_SKILL_COOLDOWN_RATE_ATTRIBUTE_PATH,
                QUICKEN_COOLDOWN_RATE_PER_RANK,
                "AttributeDefinition",
                False,
            ),
        ),
        RESTORATION_PATH: (
            (
                "D_Attributes.HealthResourcePool.HealthMaxValue",
                0.04,
                "AttributeDefinition",
                False,
            ),
        ),
        IMMOLATE_PATH: (
            (
                IMMOLATE_FIRE_DAMAGE_ATTRIBUTE_PATH,
                IMMOLATE_DAMAGE_PER_RANK,
                "AttributeDefinition",
                False,
            ),
        ),
    }

    for skill_path, operations in tuning_operations.items():
        for attribute_path, value, attribute_class, add_if_missing in operations:
            try:
                _set_skill_effect(
                    skill_path,
                    attribute_path,
                    value,
                    attribute_class,
                    add_if_missing,
                )
                _pending_skill_effects.discard((skill_path, attribute_path))
            except (AttributeError, TypeError, ValueError) as exc:
                _log_error_once(
                    f"Could not tune {skill_path} {attribute_path}: {exc}"
                )

    try:
        _remove_skill_effect(QUICKEN_PATH, MELEE_SKILL_COOLDOWN_RATE_ATTRIBUTE_PATH)
    except (AttributeError, TypeError, ValueError) as exc:
        _log_error_once(f"Could not remove Quicken's obsolete Scorn effect: {exc}")

    if _pending_phaselock_tuning:
        try:
            _configure_phaselock_base()
            _pending_phaselock_tuning = False
        except (AttributeError, TypeError, ValueError) as exc:
            _log_error_once(f"Could not configure Phaselock base behavior: {exc}")

    try:
        _configure_immolate_native_trigger()
    except (AttributeError, TypeError, ValueError) as exc:
        _log_error_once(f"Could not configure independent Immolate delivery: {exc}")

    if _pending_scorn_cooldown:
        try:
            _set_scorn_cooldown()
            _pending_scorn_cooldown = False
        except (AttributeError, TypeError, ValueError) as exc:
            _log_error_once(f"Could not tune {SCORN_PATH} cooldown: {exc}")

    try:
        _zero_skill_effects(ELATED_PATH, health_regeneration_only=True)
    except (AttributeError, TypeError, ValueError) as exc:
        _log_error_once(
            f"Could not disable native Elated regeneration: {exc}"
        )

    try:
        _zero_skill_effects(SUSTENANCE_PATH, health_regeneration_only=True)
    except (AttributeError, TypeError, ValueError) as exc:
        _log_error_once(
            f"Could not disable native Sustenance regeneration: {exc}"
        )


def _update_skill_ui_text(
    skill_path: str,
    rank: int,
    can_add_point: bool,
) -> None:
    skill_definition = unrealsdk.find_object("SkillDefinition", skill_path)
    description = _skill_description_text(skill_path)
    skill_definition.SkillDescription = description

    presentation = _find_skill_presentation(skill_path, skill_definition)
    stat_line = _skill_stat_line(skill_path, rank, can_add_point)
    presentation.Description = stat_line

    presentations = list(skill_definition.SkillEffectPresentations)
    if skill_path == IMMOLATE_PATH:
        presentations = [
            current
            for current in presentations
            if _presentation_attribute_path(current)
            != IMMOLATE_REVIVE_TIME_ATTRIBUTE_PATH
        ]
    presentation_path_name = presentation._path_name()
    for index, current in enumerate(presentations):
        if current._path_name() == presentation_path_name:
            presentations[index] = presentation
            break
    else:
        presentations.append(presentation)
    skill_definition.SkillEffectPresentations = presentations

    if (
        skill_definition.SkillDescription != description
        or presentation.Description != stat_line
        or not any(
            current._path_name() == presentation_path_name
            for current in skill_definition.SkillEffectPresentations
        )
    ):
        raise ValueError(f"The game did not retain the UI text for {skill_path}")


def _skill_ui_text_matches(
    skill_path: str,
    rank: int,
    can_add_point: bool,
) -> bool:
    skill_definition = unrealsdk.find_object("SkillDefinition", skill_path)
    if skill_definition.SkillDescription != _skill_description_text(skill_path):
        return False

    presentation = _find_skill_presentation(skill_path, skill_definition)
    return presentation.Description == _skill_stat_line(
        skill_path, rank, can_add_point
    )


def _skill_description_text(skill_path: str) -> str:
    return SKILL_UI[skill_path]


@hook("WillowGame.FrontendGFxMovie:Start", Type.POST)
def set_implemented_skill_descriptions(*_: Any) -> None:
    global _next_skill_tuning_retry_at

    if _cooldown_hud_suspended:
        return
    player_controller = _cooldown_hud_controller()
    if player_controller is None or not _is_maya_controller(player_controller):
        return

    _apply_skill_tuning()
    _next_skill_tuning_retry_at = time.monotonic() + 1.0
    for skill_path in SKILL_UI:
        try:
            invested_rank = _invested_skill_rank(player_controller, skill_path)
            rank = min(
                CLASS_MODDED_SKILL_RANK_LIMIT,
                _effective_skill_rank(
                    player_controller, skill_path, invested_rank
                ),
            )
            can_add_point = invested_rank < BASE_SKILL_RANK_LIMIT
            ui_rank = _skill_ui_rank(
                player_controller,
                skill_path,
                invested_rank,
                rank,
            )
            _update_skill_ui_text(skill_path, ui_rank, can_add_point)
            _last_skill_ui_ranks[skill_path] = (ui_rank, can_add_point)
            unrealsdk.logging.info(
                f"[MayaRebalance] Updated UI text for {skill_path} "
                f"at effective rank {rank}/{_rank_limit(rank)}, "
                f"invested rank {invested_rank}/{BASE_SKILL_RANK_LIMIT}"
            )
        except (AttributeError, TypeError, ValueError) as exc:
            _log_error_once(f"Could not update the skill UI for {skill_path}: {exc}")


def refresh_skill_stat_lines(player_controller: Any) -> None:
    global _next_skill_ui_validation_at

    if player_controller.GetSkillManager().bUpdatingSkills:
        return  # Some helpers edit native effect snapshots; defer the whole pass.
    now = time.monotonic()
    validate_text = now >= _next_skill_ui_validation_at
    # These two skills retain their native multi-line presentations/rank logic.
    # Keep them out of SKILL_UI, whose formatter replaces those presentations.
    if validate_text:
        try:
            _configure_slagger()
            _check_slagger_live_tree(player_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not verify Elemental Mastery's skill tree: {exc}")
        try:
            _configure_backdraft_description()
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not update Backdraft description: {exc}")
        try:
            _disable_recompense_native(player_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not clean original Recompense: {exc}")
        try:
            _configure_res_description()
        except (AttributeError, TypeError, ValueError) as exc:
            _log_error_once(f"Could not update Res description: {exc}")
        try:
            _configure_thoughtlock_description(player_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not update Thoughtlock description: {exc}")
        try:
            _configure_kinetic_reflection(player_controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not maintain Kinetic Reflection: {exc}")
        try:
            _configure_scorn_description()
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not maintain Scorn description: {exc}")
    try:
        _sync_minds_eye_effects(player_controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not synchronize Mind's Eye accuracy: {exc}")
    try:
        _sync_blight_phoenix_effects(player_controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not apply Blight Phoenix movement speed: {exc}")
    try:
        _sync_wreck_effects(player_controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not apply Wreck passive/Phaselock bonuses: {exc}")
    try:
        _configure_backdraft_skill_damage(player_controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not maintain Backdraft Skill Damage: {exc}")
    for skill_path in SKILL_UI:
        try:
            invested_rank = _invested_skill_rank(player_controller, skill_path)
            rank = min(
                CLASS_MODDED_SKILL_RANK_LIMIT,
                _effective_skill_rank(
                    player_controller, skill_path, invested_rank
                ),
            )
            if skill_path in {
                SUSTENANCE_PATH,
                FLICKER_PATH,
                ACCELERATE_PATH,
                SUSPENSION_PATH,
                QUICKEN_PATH,
                RESTORATION_PATH,
                ELATED_PATH,
                IMMOLATE_PATH,
            }:
                _refresh_skill_effect_rank(
                    player_controller,
                    skill_path,
                    rank,
                )
            can_add_point = invested_rank < BASE_SKILL_RANK_LIMIT
            ui_rank = _skill_ui_rank(
                player_controller,
                skill_path,
                invested_rank,
                rank,
            )
            ui_rank_state = (ui_rank, can_add_point)
            rank_changed = _last_skill_ui_ranks.get(skill_path) != ui_rank_state
            if skill_path == FLICKER_PATH:
                _sync_flicker_runtime_modifiers(player_controller, rank)
                if rank_changed:
                    _log_flicker_runtime_attributes(player_controller, rank)
            if not rank_changed and (
                not validate_text
                or _skill_ui_text_matches(skill_path, ui_rank, can_add_point)
            ):
                continue

            _update_skill_ui_text(skill_path, ui_rank, can_add_point)
            _last_skill_ui_ranks[skill_path] = ui_rank_state
            unrealsdk.logging.info(
                f"[MayaRebalance] Refreshed stat line for {skill_path} "
                f"at effective rank {rank}/{_rank_limit(rank)}, "
                f"invested rank {invested_rank}/{BASE_SKILL_RANK_LIMIT}"
            )
        except (AttributeError, TypeError, ValueError) as exc:
            _log_error_once(f"Could not refresh the skill UI for {skill_path}: {exc}")
    if validate_text:
        _next_skill_ui_validation_at = now + SKILL_UI_VALIDATION_INTERVAL_SECONDS


def _start_immolate_buff(player_controller: Any) -> None:
    global _immolate_buff_expires_at
    global _immolate_buff_controller_address
    global _immolate_final_damage_logged

    immolate_rank = _skill_rank(player_controller, IMMOLATE_PATH)
    if immolate_rank <= 0:
        return

    _configure_immolate_native_trigger()
    _immolate_final_damage_logged = False
    _immolate_buff_controller_address = player_controller._get_address()
    _immolate_buff_expires_at = time.monotonic() + IMMOLATE_DURATION_SECONDS
    _refresh_skill_effect_rank(
        player_controller,
        IMMOLATE_PATH,
        immolate_rank,
    )

    _start_immolate_hud_indicator(player_controller, immolate_rank)
    unrealsdk.logging.info(
        f"[MayaRebalance] Immolate independent window: rank={immolate_rank}, "
        f"duration={IMMOLATE_DURATION_SECONDS:g} seconds"
    )


@hook("WillowGame.LiftActionSkill:OnActionSkillStarted", Type.POST)
def activate_immolate_when_phaselock_starts(
    _action_skill: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    player_controller = get_pc()
    action_skill_controller = args.TheController
    if (
        not player_controller
        or not action_skill_controller
        or player_controller._get_address()
        != action_skill_controller._get_address()
    ):
        return

    try:
        duration_attribute = unrealsdk.find_object(
            "DesignerAttributeDefinition",
            PHASELOCK_DURATION_ATTRIBUTE_PATH,
        )
        base_delay = unrealsdk.find_object(
            "Behavior_Delay",
            PHASELOCK_BASE_DELAY_PATH,
        )
        phaselock_definition = unrealsdk.find_object(
            "SkillDefinition",
            PHASELOCK_PATH,
        )
        health_constraint = _phaselock_health_constraint(
            phaselock_definition.SkillConstraints
        )
        instance = player_controller.Pawn.GetInstancedDesignerAttribute(
            duration_attribute,
            duration_attribute.ValueName,
            duration_attribute.AttributeDataType,
        )
        unrealsdk.logging.info(
            "[MayaRebalance] DEBUG Phaselock runtime: "
            f"duration_definition="
            f"{float(duration_attribute.BaseValue.BaseValueConstant):g}, "
            f"pawn_base={float(instance.ValueBaseValue):g}, "
            f"pawn_total={float(instance.Value):g}, "
            f"skill_duration={float(_action_skill.SkillDuration):g}, "
            f"base_delay={float(base_delay.Delay):g}, "
            f"health_constraint_active="
            f"{bool(health_constraint and health_constraint.bApplyConstraintWhileActive)}, "
            f"ruin_definition_present={bool(_action_skill.RuinSkill)}, "
            f"ruin_native_scalar={float(_action_skill.RuinDamageScalar):g}"
        )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not inspect Phaselock runtime tuning: {exc}")

    try:
        _start_immolate_buff(player_controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not start Immolate from Phaselock: {exc}")


@hook("WillowGame.LiftActionSkill:LockTarget", Type.POST)
def log_phaselock_target_duration(
    action_skill: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    controller = get_pc()
    if not controller or action_skill.MyController != controller:
        return
    unrealsdk.logging.info(
        "[MayaRebalance] Phaselock target locked: "
        f"skill_duration={float(action_skill.SkillDuration):g}, "
        f"state_duration={float(action_skill.StateDuration):g} seconds"
    )


@hook("WillowGame.Behavior_CauseDamage:ApplyBehaviorToContext", Type.PRE)
def block_legacy_immolate_damage(behavior: UObject, _args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    # Stale native instances may retain their provider; suppress only its hit.
    if str(behavior._path_name()) == IMMOLATE_CAUSE_DAMAGE_BEHAVIOR_PATH:
        return Block
    return None


def _is_immolate_extra_hit(pipeline: Any, args: Any) -> bool:
    if not _immolate_damage_contexts:
        return False
    context = _immolate_damage_contexts[-1]
    return (context["pipeline"] == pipeline._get_address()
            and args.InDamagedActor is not None and args.InDamageInstigator is not None
            and context["target"] == args.InDamagedActor._get_address()
            and context["owner"] == args.InDamageInstigator._get_address())


@hook("WillowGame.WillowAIPawn:TakeDamage", Type.PRE)
def begin_immolate_source_hit(pawn: UObject, args: Any, _ret: Any, _func: Any) -> None:
    """Pair all calls, including blocked/nested hits; retain scalars only."""
    context = None
    try:
        if (not _cooldown_hud_suspended and not _immolate_damage_contexts
                and time.monotonic() < _immolate_buff_expires_at and len(_immolate_hit_contexts) < 32
                and args.DamageType is not None
                and any(args.DamageType._inherits(base) for base in _immolate_gun_sources)):
            controller, current = args.InstigatedBy, get_pc()
            if (controller is not None and current is not None
                    and not controller.bDeleteMe and not pawn.bDeleteMe
                    and controller._get_address() == current._get_address()
                    and controller._get_address() == _immolate_buff_controller_address
                    and int(controller.Role) == int(unrealsdk.find_enum("ENetRole").ROLE_Authority)
                    and _is_maya_controller(controller)):
                rank = _skill_rank(controller, IMMOLATE_PATH)
                if rank > 0:
                    context = {"target": pawn._get_address(), "owner": controller._get_address(),
                               "world": controller.WorldInfo._get_address(), "rank": rank, "damage": None}
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not prepare Immolate source hit: {exc}")
    _immolate_hit_contexts.append(context)


def _capture_immolate_source_hit(pipeline: Any, args: Any, summary: Any) -> None:
    if (not _immolate_hit_contexts or _immolate_damage_contexts
            or _cooldown_hud_suspended or summary is None):
        return
    context = _immolate_hit_contexts[-1]
    if context is None or context["damage"] is not None:
        return
    try:
        source = args.InDamageSource
        if source is None or not any(source._inherits(base) for base in _immolate_gun_sources):
            return  # Skills, status ticks, grenades and melee never qualify.
        if (args.InDamagedActor is None or args.InDamageInstigator is None
                or args.InDamagedActor._get_address() != context["target"]
                or args.InDamageInstigator._get_address() != context["owner"]):
            return
        damage_type = pipeline.GetDamageTypeDef()
        if damage_type is not None and damage_type.IsHealingDamageType():
            return
        health, shield = float(summary.FinalDamage), float(summary.DamageDealtToShields)
        if not (0.0 <= health < float("inf") and 0.0 <= shield < float("inf")):
            return
        total = health + shield
        if 0.0 < total < float("inf"):
            context["damage"] = total  # Copy before native code reuses its summary.
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not capture Immolate source damage: {exc}")


@hook("WillowGame.WillowAIPawn:TakeDamage", Type.POST_UNCONDITIONAL)
def finish_immolate_source_hit(pawn: UObject, args: Any, _ret: Any, _func: Any) -> None:
    if not _immolate_hit_contexts:
        return
    context = _immolate_hit_contexts.pop()
    if (context is None or context["damage"] is None or _cooldown_hud_suspended
            or _immolate_damage_contexts or time.monotonic() >= _immolate_buff_expires_at):
        return
    try:
        controller = args.InstigatedBy
        if (controller is None or controller.bDeleteMe or pawn.bDeleteMe
                or pawn._get_address() != context["target"]
                or controller._get_address() != context["owner"]
                or controller._get_address() != _immolate_buff_controller_address
                or controller.WorldInfo._get_address() != context["world"]
                or float(pawn.GetHealth()) <= 0.0):
            return  # Never emit after a source hit that already killed the target.
        emitter = controller.Pawn
        if emitter is None or emitter.bDeleteMe or _skill_rank(controller, IMMOLATE_PATH) <= 0:
            return
        expected = context["damage"] * context["rank"] * IMMOLATE_DAMAGE_PER_RANK
        if not 0.0 < expected < float("inf"):
            return
        _emit_immolate_fire_hit(emitter, pawn, controller, args.HitLocation, expected)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not emit Immolate fire damage: {exc}")  # Never replay the shot.


def _emit_immolate_fire_hit(emitter: Any, target: Any, controller: Any, location: Any, expected: float) -> None:
    """Borrow/release an engine pipeline instead of creating a UObject per hit."""
    pipeline = emitter.GetDamagePipeline(
        InDamageTypeDef=_immolate_fire_type, InImpactDef=None,
        inCanHitFriendly=False, InHitObject=target,
    )
    if pipeline is None:
        raise ValueError("Immolate could not acquire an engine damage pipeline")
    context = None
    try:
        context = {"pipeline": pipeline._get_address(), "target": target._get_address(),
                   "owner": controller._get_address(), "expected_damage": expected, "claimed": False}
        _immolate_damage_contexts.append(context)
        target.TakeDamage(
            Damage=expected, InstigatedBy=controller, HitLocation=location,
            Momentum=unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=0.0),
            DamageType=_immolate_skill_source,
            HitInfo=unrealsdk.make_struct("TraceHitInfo"), DamageCauser=None, Pipeline=pipeline,
        )
        if not context["claimed"]:
            _log_error_once("Immolate fire event did not reach its dedicated damage pipeline")
    finally:
        if context is not None:
            _immolate_damage_contexts.pop()
        if not _cooldown_hud_suspended and not emitter.bDeleteMe:
            emitter.ReleaseDamagePipeline(Pipeline=pipeline)


@hook("WillowGame.WillowDamagePipeline:AdjustDamage", Type.PRE)
def apply_immolate_final_damage_fraction(
    pipeline: UObject,
    args: WrappedStruct,
    _ret: Any,
    func: BoundFunction,
) -> tuple[type[Block], Any] | None:
    """Normalize only our borrowed pipeline to the source hit's final fraction."""

    global _immolate_final_damage_logged

    if _cooldown_hud_suspended or not _is_immolate_extra_hit(pipeline, args):
        return None
    context = _immolate_damage_contexts[-1]
    expected_damage = context["expected_damage"]
    if expected_damage is None or context["claimed"]:
        return None
    controller = get_pc()
    instigator = args.InDamageInstigator
    if (
        not controller or not instigator
        or controller._get_address() != instigator._get_address()
    ):
        return None
    damage_type = pipeline.GetDamageTypeDef()
    if not damage_type or str(damage_type._path_name()) != IMMOLATE_IMPACT_DAMAGE_TYPE_PATH:
        return None

    target = args.InDamagedActor
    if not target:
        return None
    shield_before = max(0.0, float(target.GetShieldStrength()))
    # Claim before calling the native function: reentry and secondary procs
    # must not be normalized as another Immolate hit.
    context["claimed"] = True
    with unrealsdk.hooks.prevent_hooking_direct_calls():
        native_summary = func(args)
    # Once the native body has run, every path must Block further execution.
    # A reflected-field or diagnostic failure must never fall through and let
    # the SDK execute that same damage calculation a second time.
    shield_after = None
    shield_change_attempted = False
    try:
        if _cooldown_hud_suspended or target.bDeleteMe:
            return Block, native_summary
        summary = copy.copy(native_summary)
        native_health = float(summary.FinalDamage)
        native_shield = float(summary.DamageDealtToShields)
        shield_damage = min(expected_damage, shield_before)
        health_damage = expected_damage - shield_damage
        summary.DamageDealtToShields = shield_damage
        summary.FinalDamage = health_damage
        summary.bWasCrit = False
        summary.bWasOneShotKill = (
            float(summary.PreviousHealth) > 0.0
            and health_damage >= float(summary.PreviousHealth)
        )
        shield_after = max(0.0, float(target.GetShieldStrength()))
        pipeline.DamageSummary = summary
        if shield_after < shield_before - 0.0001:
            shield_change_attempted = True
            target.SetShieldStrength(shield_before - shield_damage)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        # Preserve the result already calculated by the engine if correction
        # fails. Restore a consumed pool before returning the native summary.
        if not _cooldown_hud_suspended:
            try:
                if shield_change_attempted and shield_after is not None and not target.bDeleteMe:
                    target.SetShieldStrength(shield_after)
                pipeline.DamageSummary = native_summary
            except (AttributeError, TypeError, ValueError, RuntimeError) as cleanup_exc:
                _log_error_once(f"Could not restore Immolate native damage result: {cleanup_exc}")
        _log_error_once(f"Could not normalize Immolate fire damage; native result retained: {exc}")
        return Block, native_summary

    if not _immolate_final_damage_logged:
        _immolate_final_damage_logged = True
        try:
            unrealsdk.logging.info(
                "[MayaRebalance] Immolate final damage: "
                f"Expected={expected_damage:g}, "
                f"NativeBeforeCorrection={native_health + native_shield:g}, "
                f"FinalHealth={health_damage:g}, FinalShield={shield_damage:g}"
            )
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not log completed Immolate damage: {exc}")
    return Block, summary


def refresh_combat_skill_effects(player_controller: Any, delta: float) -> None:
    """Elated uses simulation time, never render frequency or time spent paused."""
    if (player_controller.WorldInfo.Pauser
            or int(player_controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority)):
        return
    pawn = player_controller.Pawn
    if not pawn or pawn.bDeleteMe:
        return
    elapsed = max(0.0, float(delta))
    if elapsed <= 0.0:
        return
    elated_rank = _skill_rank(player_controller, ELATED_PATH)
    if elated_rank <= 0:
        return
    health = float(pawn.GetHealth())
    max_health = float(pawn.GetMaxHealth())
    if health <= 0.0 or max_health <= 0.0 or health >= max_health:
        return
    phaselock_definition = unrealsdk.find_object("SkillDefinition", PHASELOCK_PATH)
    phaselock_active = player_controller.GetSkillManager().IsSkillActive(
        player_controller, phaselock_definition,
    )
    regeneration_multiplier = 2.0 if phaselock_active else 1.0
    regenerated_health = (
        max_health
        * ELATED_REGEN_PER_RANK
        * elated_rank
        * regeneration_multiplier
        * elapsed
    )
    pawn.SetHealth(min(max_health, health + regenerated_health))


def _native_ranked_skill_text(func: Any, args: Any) -> str:
    """Inner presentation hooks must not replace this query's rank with cached preview text."""
    global _ranked_skill_description_depth
    _ranked_skill_description_depth += 1
    try:
        with unrealsdk.hooks.prevent_hooking_direct_calls():
            return func(args)
    finally:
        _ranked_skill_description_depth -= 1


@hook("WillowGame.SkillTreeGFxObject:GetSkillDescriptionForGrade", Type.PRE)
def correct_ranked_skill_description(
    _tree: UObject,
    args: WrappedStruct,
    _ret: Any,
    func: BoundFunction,
) -> tuple[type[Block], Any] | None:
    """Format each tree query with its own rank, including the next-point query."""
    definition = args.SkillDef
    if not definition:
        return None
    skill_path = str(definition._path_name())
    if skill_path not in {SUSPENSION_PATH, RECOMPENSE_PATH, BLIGHT_PHOENIX_PATH, SCORN_PATH,
                         SUSTENANCE_PATH, ELATED_PATH, KINETIC_REFLECTION_PATH,
                         FLICKER_PATH, ACCELERATE_PATH, QUICKEN_PATH, RESTORATION_PATH, IMMOLATE_PATH}:
        return None
    try:
        if skill_path == SCORN_PATH:
            # This is the base cooldown, not the current grade times 12, nor a
            # stale cached designer value. Preserve Scorn's native upper prose.
            stat_line = _format_rank_progression(
                "Scorn Cooldown", SCORN_BASE_COOLDOWN_SECONDS, 1,
                int(args.Grade) < 1 or not args.bIncludeHTML, "seconds",
            )
            duration_line = _format_percentage_progression(
                "Elemental status effect duration", SCORN_STATUS_DURATION_BONUS * 100,
                int(int(args.Grade) > 0), int(args.Grade) < 1 or not args.bIncludeHTML
                or args.PlayerOwner is None or int(args.PlayerOwner.GetSkillGrade(definition)) <= 0,
                show_plus=True,
            )
            return Block, ("<br>" if args.bIncludeHTML else "\n").join((stat_line, duration_line))
        grade = max(0, int(args.Grade))
        grade_modifier = int(args.GradeModifier)
        # Runtime trace: allocated1, COM+5 -> Grade6, GradeModifier5. Adding
        # GradeModifier again wrongly turns current6 and preview7 into11/11.
        rank = min(CLASS_MODDED_SKILL_RANK_LIMIT, grade)
        owner = getattr(args, "PlayerOwner", None)
        can_add_point = (grade < BASE_SKILL_RANK_LIMIT or not args.bIncludeHTML
                         or owner is None or int(owner.GetSkillGrade(definition)) < BASE_SKILL_RANK_LIMIT)
        if skill_path == KINETIC_REFLECTION_PATH:
            native_text = _native_ranked_skill_text(func, args)
            general_text = _format_percentage_progression(
                "General damage reduction", KINETIC_REFLECTION_GENERAL_REDUCTION_PER_RANK * 100,
                rank, can_add_point,
            )
            return Block, _kinetic_reflection_footer(native_text, general_text, bool(args.bIncludeHTML))
        stat_line = _skill_stat_line(skill_path, rank, can_add_point)
        if skill_path in {BLIGHT_PHOENIX_PATH, SUSTENANCE_PATH, ELATED_PATH,
                          FLICKER_PATH, QUICKEN_PATH, IMMOLATE_PATH}:
            # Their original native effects are deliberately disabled/replaced;
            # format the queried rank directly, without native aggregation/cache.
            # This function returns lower stat text only, not the upper prose.
            description = stat_line if args.bIncludeHTML else _skill_stat_line(
                skill_path, rank, True,
            ).replace("<br>", "\n")
        else:
            presentation = _find_skill_presentation(skill_path, definition)
            previous_description = presentation.Description
            # GetSkillEffectPresentations/TranslateStatData are called internally by
            # native code and did not fire their hooks in the observed session.
            # Modify the actual UObject only for this outer UI query, then restore.
            try:
                presentation.Description = stat_line
                description = _native_ranked_skill_text(func, args)
            finally:
                presentation.Description = previous_description
        if args.bIncludeHTML:
            description = _color_stat_percentages(description)
        key = (skill_path, grade, grade_modifier, bool(args.bIncludeHTML))
        if key not in _logged_ranked_skill_descriptions:
            _logged_ranked_skill_descriptions.add(key)
            unrealsdk.logging.info(
                f"[MayaRebalance] Skill tree description {skill_path}: "
                f"grade={grade}, grade_modifier={grade_modifier}, effective_rank={rank}, "
                f"stat={stat_line}, result={description}"
            )
        return Block, description
    except (AttributeError, TypeError, ValueError) as exc:
        _log_error_once(f"Could not correct skill tree description for {skill_path}: {exc}")
        return None


@hook("WillowGame.SkillDefinition:GetSkillEffectPresentations", Type.POST)
def update_computed_skill_presentations(
    skill_definition: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    if _ranked_skill_description_depth:
        return  # The outer query already supplies its exact current/next + COM rank.
    skill_path = str(skill_definition._path_name())
    if skill_path not in SKILL_UI:
        return

    if skill_path in {SUSPENSION_PATH, RECOMPENSE_PATH, BLIGHT_PHOENIX_PATH,
                      SUSTENANCE_PATH, ELATED_PATH}:
        # These queries are handled at the outer SkillTreeGFxObject boundary.
        return

    player_controller = get_pc()
    if not player_controller:
        return

    try:
        invested_rank = _invested_skill_rank(player_controller, skill_path)
        effective_rank = min(
            CLASS_MODDED_SKILL_RANK_LIMIT,
            _effective_skill_rank(
                player_controller,
                skill_path,
                invested_rank,
            ),
        )
        can_add_point = invested_rank < BASE_SKILL_RANK_LIMIT
        ui_rank = _skill_ui_rank(
            player_controller,
            skill_path,
            invested_rank,
            effective_rank,
        )
        stat_line = _skill_stat_line(skill_path, ui_rank, can_add_point)
        skill_definition.SkillDescription = _skill_description_text(skill_path)
        target_presentation_path = str(
            _find_skill_presentation(skill_path, skill_definition)._path_name()
        )
        updated = False
        for effect_presentation in args.EffectPresentations:
            presentation = effect_presentation.AttributePresentation
            if not presentation:
                continue
            pres_path = str(presentation._path_name())
            if (
                skill_path == IMMOLATE_PATH
                and _presentation_attribute_path(presentation)
                == IMMOLATE_REVIVE_TIME_ATTRIBUTE_PATH
            ):
                presentation.Description = ""
                continue
            if pres_path == target_presentation_path:
                presentation.Description = stat_line
                updated = True

        if not updated:
            raise ValueError(
                f"GetSkillEffectPresentations returned no presentation for "
                f"{target_presentation_path}"
            )

        if skill_path not in _logged_skill_presentation_overrides:
            unrealsdk.logging.info(
                f"[MayaRebalance] Updated computed UI presentation "
                f"for {skill_path} at effective rank "
                f"{effective_rank}/{_rank_limit(effective_rank)}"
            )
            _logged_skill_presentation_overrides.add(skill_path)
    except (AttributeError, TypeError, ValueError) as exc:
        _log_error_once(
            f"Could not update the computed UI presentation for "
            f"{skill_path}: {exc}"
        )


def _cooldown_hud_controller(*, allow_resume: bool = False) -> Any | None:
    """Resolve only the CURRENT live controller; never retain actors across travel."""
    global _cooldown_hud_context, _cooldown_hud_suspended
    if _cooldown_hud_suspended and not allow_resume:
        return None
    controller = get_pc()
    if controller is None or controller.bDeleteMe:
        return None
    pawn = controller.Pawn
    tree = controller.PlayerSkillTree
    world = controller.WorldInfo
    if (pawn is None or pawn.bDeleteMe or tree is None or not tree.bInitialized
            or world is None or world.bDeleteMe):
        return None
    context = (controller._get_address(), world._get_address())
    if _cooldown_hud_suspended:
        if context == _cooldown_hud_departing_context:
            return None  # The old world may still tick after PreClientTravel.
        _cooldown_hud_suspended = False
        unrealsdk.logging.info("[MayaRebalance] Cooldown HUD resumed in current gameplay world")
    _cooldown_hud_context = context  # Primitive addresses only, not actor references.
    return controller


def _is_maya_controller(controller: Any) -> bool:
    player_class = controller.PlayerClass
    return bool(player_class and str(player_class._path_name()) == RES_PLAYER_CLASS_PATH)


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def tick_maya_combat_effects(controller: UObject, args: Any, _ret: Any, _func: Any) -> None:
    """Gameplay work is independent of rendering; resolve only the current world."""
    global _immolate_buff_expires_at
    if _cooldown_hud_suspended:
        return
    try:
        current = _cooldown_hud_controller()
        if current is None or current != controller or not _is_maya_controller(current):
            return
        refresh_combat_skill_effects(current, float(args.DeltaTime))
        # Immolate/Recompense keep their existing real-time deadlines. Expiry
        # must not wait for the throttled stat/UI synchronization.
        if _immolate_buff_expires_at > 0.0:
            changed_owner = current._get_address() != _immolate_buff_controller_address
            if changed_owner or time.monotonic() >= _immolate_buff_expires_at:
                if changed_owner:
                    _immolate_buff_expires_at = 0.0
                _sync_immolate_native_gate(current, _skill_rank(current, IMMOLATE_PATH))
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not update Maya gameplay tick: {exc}")


def _suspend_cooldown_hud(controller: Any, *, before_travel: bool = False) -> None:
    global _cooldown_hud_suspended, _cooldown_hud_departing_context
    address = controller._get_address()
    current = get_pc()
    is_current = current is not None and current._get_address() == address
    if not (is_current
            or (_cooldown_hud_context is not None and _cooldown_hud_context[0] == address)):
        return  # Destroying a remote player must not suspend the local HUD.
    if not _cooldown_hud_suspended:
        _cooldown_hud_departing_context = _cooldown_hud_context or (address, 0)
        if before_travel and is_current:
            # PRE travel is still live; capture even if no HUD sync/pawn existed.
            # Destroyed does not inspect world fields of the departing actor.
            world = controller.WorldInfo
            _cooldown_hud_departing_context = (address, world._get_address() if world is not None else 0)
        _cooldown_hud_suspended = True
        unrealsdk.logging.info("[MayaRebalance] Cooldown HUD suspended before controller/world teardown")
    # No GetSkillManager/GetHUDMovie call, cleanup, or dereference of an old owner.


@hook("WillowGame.WillowPlayerController:PreClientTravel", Type.PRE)
def suspend_cooldown_hud_before_travel(controller: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    _suspend_cooldown_hud(controller, before_travel=True)


@hook("WillowGame.WillowPlayerController:Destroyed", Type.PRE)
def suspend_cooldown_hud_before_destroy(controller: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    _suspend_cooldown_hud(controller)


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def resume_cooldown_hud_in_gameplay(controller: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    if not _cooldown_hud_suspended:
        return
    current = get_pc()
    if current is not None and current._get_address() == controller._get_address():
        _cooldown_hud_controller(allow_resume=True)


def _res_hud_cooldown_active() -> bool:
    """Read the local player's gameplay cooldown; never run another HUD timer."""
    try:
        controller = get_pc()
        if not controller or not _is_maya_controller(controller) or not controller.Pawn:
            return False
        if _invested_skill_rank(controller, RES_PATH) <= 0:
            return False
        state = _res_state(controller)
        return state is not None and float(state["remaining"]) > 0.0
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not read Res HUD cooldown: {exc}")
        return False


def _get_res_hud_feedback() -> Any:
    global _res_hud_feedback
    if _res_hud_feedback is None:
        definition = unrealsdk.find_object("SkillDefinition", RES_PATH)
        feedback = unrealsdk.construct_object(
            "SkillDefinition", definition, "VH_Res_Cooldown_HUD_Feedback",
            flags=int(ObjectFlags.KEEP_ALIVE), template_obj=definition,
        )
        feedback.SkillName = "Res cooldown"
        feedback.SkillIcon = definition.SkillIcon
        feedback.bSubjectToGradeRules = False
        feedback.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered
        # The gameplay timer, not a second timed skill, determines visibility.
        feedback.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite
        feedback.SkillEffectDefinitions = []
        feedback.SkillEffectPresentations = []
        feedback.SkillConstraints = []
        feedback.DamageEvents = []
        feedback.BehaviorProviderDefinition = None
        feedback.TrackedActiveSkill = None
        feedback.TrackedActiveSkills = []
        definition.TrackedActiveSkills = list(definition.TrackedActiveSkills) + [feedback]
        _res_hud_feedback = feedback
    return _res_hud_feedback


def _combat_free_hud_slot(controller: Any, movie: Any, feedback: Any) -> int | None:
    """Allocate a logical skill slot; remapped screen positions are a separate namespace."""
    occupied: set[int] = set()
    visited: set[str] = set()
    def reserve(definition: Any) -> None:
        if not definition or definition == feedback:
            return
        path = str(definition._path_name())
        if path in visited:
            return
        visited.add(path)
        if int(definition.TrackedSkillType) in {2, 3, 5}:  # Triggered, Respond, MeleeOverride.
            occupied.add(int(definition.TrackedSkillHUDSlot))
        reserve(definition.TrackedActiveSkill)
        for child in definition.TrackedActiveSkills:
            reserve(child)
    for entry in movie.AvailableTrackedSkills:
        definition = entry.SkillDef
        # Feedback children often have GetSkillGrade()==0 even when their parent
        # is purchased. Their registered slots are NOT free between activations.
        if definition and definition != feedback:
            reserve(definition)
    tree = controller.PlayerSkillTree
    if tree:
        for item in tree.Skills:
            if int(item.Grade) > 0:
                reserve(item.Definition)
    for skill in controller.GetSkillManager().ActiveSkills:
        reserve(skill.Definition)
    # Native cache is a fixed array of 11 slots. Do not invent a twelfth slot.
    preferred = int(feedback.TrackedSkillHUDSlot)
    if 0 <= preferred < len(movie.CachedTSkillIcon_TrigResp) and preferred not in occupied:
        return preferred
    return next((slot for slot in range(len(movie.CachedTSkillIcon_TrigResp))
                 if slot not in occupied), None)


def _ensure_combat_hud_mapping(movie: Any, feedback: Any, slot: int) -> int:
    """Fill a physical HUD hole, independently of the definition's logical slot."""
    occupied: set[int] = set()
    registered_icons = []
    for entry in movie.AvailableTrackedSkills:
        definition = entry.SkillDef
        if not definition or int(definition.TrackedSkillType) not in {2, 3, 5}:
            continue
        registered_icons.append(definition.SkillIcon)
        if definition != feedback and int(entry.RemappedSlot) >= 0:
            occupied.add(int(entry.RemappedSlot))
    for index, state in enumerate(movie.CachedTSkillIcon_TrigResp):
        # Cache images survive inactive states and native remapping. A registered
        # skill's CURRENT mapping, not its previous image, owns the position.
        if (state.Icon and int(state.Type) in {2, 3, 5}
                and state.Icon not in registered_icons):
            occupied.add(index)
    physical = next((index for index in range(len(movie.CachedTSkillIcon_TrigResp))
                     if index not in occupied), None)
    if physical is None:
        raise ValueError(f"Combat HUD has no free physical slot for logical slot {slot}; other icons preserved")
    # Native UpdateSkillIcons only treats this prefix as purchased. A manual
    # remap outside it can be active in SkillManager yet never appear on screen.
    purchased = max(int(movie.NumPurchasedTrigRespSlots), physical + 1)
    if purchased > len(movie.CachedTSkillIcon_TrigResp):
        raise ValueError("Combat HUD purchased slot count exceeds its native capacity")
    movie.NumPurchasedTrigRespSlots = purchased
    if int(movie.GetRemappedSlot(feedback)) == physical:
        return physical
    entries = [copy.copy(entry) for entry in movie.AvailableTrackedSkills]
    for entry in entries:
        if entry.SkillDef == feedback:
            entry.RemappedSlot = physical
            movie.AvailableTrackedSkills = entries
            if int(movie.GetRemappedSlot(feedback)) != physical:
                raise ValueError("Combat HUD did not retain its non-overlapping remapped slot")
            return physical
    raise ValueError("Combat HUD feedback has no native registration")


def _prepare_combat_hud_feedback(controller: Any, movie: Any, feedback: Any) -> bool:
    """Share one allocator/mapping policy across all custom combat indicators."""
    manager = controller.GetSkillManager()
    slot = _combat_free_hud_slot(controller, movie, feedback)
    active = manager.IsSkillActive(controller, feedback)
    old_mapping = int(movie.GetRemappedSlot(feedback))
    if slot is None or (active and int(feedback.TrackedSkillHUDSlot) != slot):
        if active:
            manager.DeactivateSkill(controller, feedback)  # Visual feedback only.
            active = False
        if slot is None:
            _log_error_once(f"Combat HUD has no free native slot for {feedback.SkillName}; other icons preserved")
            return False
    feedback.TrackedSkillHUDSlot = slot
    if not any(entry.SkillDef == feedback for entry in movie.AvailableTrackedSkills):
        movie.AddTrackedSkill(feedback)
        # Registration may remap existing native entries. Re-read the movie,
        # rather than forcing the slot that was free before AddTrackedSkill.
        slot = _combat_free_hud_slot(controller, movie, feedback)
        if slot is None:
            if manager.IsSkillActive(controller, feedback):
                manager.DeactivateSkill(controller, feedback)
            _log_error_once(f"Combat HUD has no free native slot after registering {feedback.SkillName}")
            return False
        feedback.TrackedSkillHUDSlot = slot
    try:
        physical = _ensure_combat_hud_mapping(movie, feedback, slot)
    except ValueError:
        if manager.IsSkillActive(controller, feedback):
            manager.DeactivateSkill(controller, feedback)
        raise
    if active and old_mapping != physical:
        manager.DeactivateSkill(controller, feedback)  # Retry the visual, not the gameplay skill.
    if old_mapping != physical:
        unrealsdk.logging.info(
            f"[MayaRebalance] Combat HUD mapping repaired: {feedback.SkillName}; "
            f"logical_slot={slot}, remapped_slot={physical}, "
            f"purchased_slots={int(movie.NumPurchasedTrigRespSlots)}"
        )
    return True


def _sync_res_hud_indicator() -> None:
    try:
        controller = _cooldown_hud_controller()
        if controller is None:
            return
        wanted = _res_hud_cooldown_active()
        manager = controller.GetSkillManager()
        if not wanted:
            if _res_hud_feedback is not None and manager.IsSkillActive(controller, _res_hud_feedback):
                manager.DeactivateSkill(controller, _res_hud_feedback)
            return
        movie = controller.GetHUDMovie()
        if not movie:
            return
        feedback = _get_res_hud_feedback()
        if not _prepare_combat_hud_feedback(controller, movie, feedback):
            return
        if not manager.IsSkillActive(controller, feedback):
            if manager.ActivateSkill(controller, feedback, None, 1) is False:
                raise ValueError("Res visual feedback was rejected")
            movie.UpdateSkillIcons()
            unrealsdk.logging.info(
                f"[MayaRebalance] Res cooldown native HUD indicator: slot={int(feedback.TrackedSkillHUDSlot)}, "
                f"remapped_slot={int(movie.GetRemappedSlot(feedback))}"
            )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not update native Res HUD indicator: {exc}")


def _disable_recompense_native(controller: Any | None = None) -> None:
    """Remove only vanilla retaliation/feedback, never mutate its shared template."""
    definition = unrealsdk.find_object("SkillDefinition", RECOMPENSE_PATH)
    changed = bool(definition.DamageEvents) or definition.BehaviorProviderDefinition is not None
    definition.DamageEvents = []
    definition.BehaviorProviderDefinition = None
    single = definition.TrackedActiveSkill
    if single and str(single._path_name()) == RECOMPENSE_FEEDBACK_PATH:
        definition.TrackedActiveSkill = None
        changed = True
    children = list(definition.TrackedActiveSkills)
    kept = [child for child in children
            if not child or str(child._path_name()) != RECOMPENSE_FEEDBACK_PATH]
    if len(kept) != len(children):
        definition.TrackedActiveSkills = kept
        changed = True
    if definition.DamageEvents or definition.BehaviorProviderDefinition is not None:
        raise ValueError("original Recompense damage event/provider was not removed")
    if changed:
        unrealsdk.logging.info("[MayaRebalance] Disabled original Recompense retaliation and feedback links")
    if controller is None:
        return
    manager = controller.GetSkillManager()
    for skill in list(manager.ActiveSkills):
        if (str(skill.Definition._path_name()) == RECOMPENSE_FEEDBACK_PATH
                and skill.SkillInstigator == controller):
            manager.DeactivateSkill(controller, skill.Definition)
            changed = True
    movie = controller.GetHUDMovie()
    if movie:
        entries = list(movie.AvailableTrackedSkills)
        kept_entries = [copy.copy(entry) for entry in entries
                        if not entry.SkillDef
                        or str(entry.SkillDef._path_name()) != RECOMPENSE_FEEDBACK_PATH]
        if len(kept_entries) != len(entries):
            # Do not sort/remap other skills, including Res's verified slot.
            movie.AvailableTrackedSkills = kept_entries
            changed = True
        if changed:
            movie.UpdateSkillIcons()


def _block_recompense_legacy_behavior(behavior: Any, expected_path: str) -> type[Block] | None:
    if str(behavior._path_name()) != expected_path:
        return None
    if expected_path not in _recompense_blocked_legacy_behaviors:
        _recompense_blocked_legacy_behaviors.add(expected_path)
        unrealsdk.logging.info(f"[MayaRebalance] Blocked cached original Recompense behavior: {expected_path}")
    return Block


@hook("WillowGame.Behavior_CauseDamage:ApplyBehaviorToContext", Type.PRE)
def prevent_original_recompense_damage(behavior: UObject, _args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    return _block_recompense_legacy_behavior(behavior, RECOMPENSE_NATIVE_DAMAGE_PATH)


@hook("WillowGame.Behavior_ActivateSkill:ApplyBehaviorToContext", Type.PRE)
def prevent_original_recompense_feedback(behavior: UObject, _args: Any, _ret: Any, _func: Any) -> type[Block] | None:
    return _block_recompense_legacy_behavior(behavior, RECOMPENSE_NATIVE_FEEDBACK_TRIGGER_PATH)


def _sync_recompense_cooldown_hud_indicator() -> None:
    """Render Recompense beside Res in the native row, not over it on canvas."""
    global _recompense_cooldown_hud_feedback
    try:
        controller = _cooldown_hud_controller()
        if controller is None:
            return
        state = _recompense_state(controller)
        wanted = state is not None and time.monotonic() < state["ready_at"]
        feedback = _recompense_cooldown_hud_feedback
        manager = controller.GetSkillManager()
        if not wanted:
            if feedback is not None and manager.IsSkillActive(controller, feedback):
                manager.DeactivateSkill(controller, feedback)
            return
        movie = controller.GetHUDMovie()
        if not movie:
            return
        if feedback is None:
            definition = unrealsdk.find_object("SkillDefinition", RECOMPENSE_PATH)
            feedback = unrealsdk.construct_object(
                "SkillDefinition", definition, "VH_Recompense_Cooldown_HUD_Feedback",
                flags=int(ObjectFlags.KEEP_ALIVE), template_obj=definition,
            )
            feedback.SkillName = "Recompense cooldown"
            feedback.SkillIcon = definition.SkillIcon
            feedback.bSubjectToGradeRules = False
            feedback.TrackedSkillType = unrealsdk.find_enum("ETrackedSkillType").TRACKEDSKILL_Triggered
            feedback.TrackedSkillHUDSlot = RECOMPENSE_HUD_SLOT
            feedback.DurationType = unrealsdk.find_enum("EEffectDurationType").DURATION_Infinite
            feedback.SkillEffectDefinitions = []
            feedback.SkillEffectPresentations = []
            feedback.SkillConstraints = []
            feedback.DamageEvents = []
            feedback.BehaviorProviderDefinition = None
            feedback.TrackedActiveSkill = None
            feedback.TrackedActiveSkills = []
            definition.TrackedActiveSkills = list(definition.TrackedActiveSkills) + [feedback]
            _recompense_cooldown_hud_feedback = feedback
        if not _prepare_combat_hud_feedback(controller, movie, feedback):
            return
        if not manager.IsSkillActive(controller, feedback):
            if manager.ActivateSkill(controller, feedback, None, 1) is False:
                raise ValueError("Recompense visual feedback was rejected")
            movie.UpdateSkillIcons()
            unrealsdk.logging.info(
                f"[MayaRebalance] Recompense cooldown native HUD indicator: slot={int(feedback.TrackedSkillHUDSlot)}, "
                f"remapped_slot={int(movie.GetRemappedSlot(feedback))}"
            )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not update native Recompense cooldown HUD indicator: {exc}")


def _draw_combat_skill_indicators(canvas: Any) -> None:
    """Maintain the native skill row only; never draw fixed-position fallbacks."""
    global _next_cooldown_hud_sync_at

    if _cooldown_hud_suspended:
        return
    try:
        controller = _cooldown_hud_controller()
        if (controller is None or not _is_maya_controller(controller) or controller.WorldInfo.Pauser
                or controller.IsPauseMenuOpen()):
            return  # Visual-only suppression; never reset buffs or cooldowns.
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not check combat HUD pause visibility: {exc}")
        return
    now = time.monotonic()
    if now >= _next_cooldown_hud_sync_at:
        _next_cooldown_hud_sync_at = now + SKILL_STAT_LINES_REFRESH_INTERVAL_SECONDS
        _sync_recompense_cooldown_hud_indicator()
        _sync_res_hud_indicator()
        if now < _immolate_buff_expires_at:
            _start_immolate_hud_indicator(
                controller, _skill_rank(controller, IMMOLATE_PATH), restart=False,
            )
        _sync_thoughtlock_hud_indicator()


@hook("WillowGame.WillowGameViewportClient:PostRender", Type.PRE)
def refresh_skill_ui_before_render(
    _viewport: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    global _next_skill_tuning_retry_at
    global _next_phaselock_validation_at
    global _next_skill_stat_lines_refresh_at, _next_cooldown_hud_sync_at
    global _next_skill_ui_validation_at, _next_class_mod_rank_refresh_at
    global _last_skill_runtime_context

    if _cooldown_hud_suspended:
        return
    try:
        player_controller = _cooldown_hud_controller()
        if player_controller is None or not _is_maya_controller(player_controller):
            return
        context = (player_controller._get_address(), player_controller.Pawn._get_address(),
                   player_controller.WorldInfo._get_address())
        if context != _last_skill_runtime_context:
            _last_skill_runtime_context = context
            _next_skill_stat_lines_refresh_at = 0.0
            _next_skill_ui_validation_at = 0.0
            _next_class_mod_rank_refresh_at = 0.0
            _next_phaselock_validation_at = 0.0
            _next_cooldown_hud_sync_at = 0.0
        now = time.monotonic()
        if now < _next_skill_stat_lines_refresh_at:
            return
        _next_skill_stat_lines_refresh_at = now + SKILL_STAT_LINES_REFRESH_INTERVAL_SECONDS
        if (
            (_pending_skill_effects or _pending_sweet_release_speed
             or _pending_damage_tuning or _pending_scorn_cooldown
             or _pending_phaselock_tuning)
            and now >= _next_skill_tuning_retry_at
        ):
            _apply_skill_tuning()
            _next_skill_tuning_retry_at = now + 1.0
        if now >= _next_phaselock_validation_at:
            _next_phaselock_validation_at = now + PHASELOCK_VALIDATION_INTERVAL_SECONDS
            try:
                if not _phaselock_tuning_matches():
                    _configure_phaselock_base()
                _sync_phaselock_duration(player_controller)
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _log_error_once(f"Could not validate Phaselock base behavior: {exc}")
        refresh_skill_stat_lines(player_controller)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not update Maya combat skill effects: {exc}")


@hook("WillowGame.WillowGameViewportClient:PostRender", Type.POST)
def draw_combat_skill_indicators(
    _viewport: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    canvas = args.Canvas
    if canvas:
        _draw_combat_skill_indicators(canvas)


def _sustenance_controller(instigator: Any) -> Any | None:
    if not instigator:
        return None
    if str(instigator.Class.Name) == "WillowPlayerController":
        return instigator
    controller = getattr(instigator, "Controller", None)
    if controller and str(controller.Class.Name) == "WillowPlayerController":
        return controller
    return None


def _sustenance_status_snapshot(
    component: Any, filters: dict[int, set[int]] | None = None,
) -> dict[tuple[Any, ...], int]:
    """Copy primitive values: WrappedStruct references can change during Apply."""
    snapshot: dict[tuple[Any, ...], int] = {}
    for effect in component.ActiveStatusEffects:
        definition_address = effect.StatusEffectDefinition._get_address()
        if filters is not None and definition_address not in filters:
            continue
        instigator = effect.EventInstigator
        author_address = instigator._get_address() if instigator else 0
        if filters is not None and author_address not in filters[definition_address]:
            continue
        hit_region = effect.HitRegion
        signature = (
            definition_address, author_address,
            hit_region._get_address() if hit_region else 0,
            float(effect.Duration),
            float(effect.TotalElapsedTime),
        )
        snapshot[signature] = snapshot.get(signature, 0) + 1
    return snapshot


def _set_scorn_duration_scope(scope: dict[str, Any], active: bool) -> None:
    """Temporarily scale the existing native formula, without cloning the status."""
    definition = scope["definition"]()  # Weak reference; never probe an expired wrapper.
    if definition is None or scope["active"] == active:
        return
    expected = scope["base"] if active else scope["scaled"]
    if not _scaling_formula_matches(definition.BaseDuration, expected):
        scope["active"] = False
        return  # Preserve an external change made inside the native application.
    desired = scope["scaled"] if active else scope["base"]
    scope["active"] = active
    try:
        definition.BaseDuration = copy.copy(desired)
        if not _scaling_formula_matches(definition.BaseDuration, desired):
            raise ValueError("Scorn status duration formula did not persist")
    except (AttributeError, TypeError, ValueError, RuntimeError):
        # This write failed synchronously; restore the original before native Apply.
        definition.BaseDuration = copy.copy(scope["base"])
        scope["active"] = False
        raise


def _finish_scorn_duration(context: dict[str, Any], *, resume_parent: bool = True) -> None:
    try:
        if context.get("duration_scope") is not None:
            _set_scorn_duration_scope(context["duration_scope"], False)
    finally:
        if resume_parent and context.get("duration_parent") is not None:
            _set_scorn_duration_scope(context["duration_parent"], True)


@hook("WillowGame.StatusEffectsComponent:ApplyStatusEffect", Type.PRE)
def prepare_sustenance_status_application(
    component: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    # Pair every invocation, including ignored/blocked calls, so spreading and
    # nested ApplyStatusEffect calls cannot borrow another application's state.
    context: dict[str, Any] = {"component": component._get_address(), "before": None}
    _sustenance_status_contexts.append(context)
    try:
        definition = args.StatusEffectDefinition
        if not definition:
            return
        definition_address = definition._get_address()
        # Nested calls by another player must not inherit the outer Maya's scale.
        for parent in reversed(_sustenance_status_contexts[:-1]):
            duration_scope = parent.get("duration_scope")
            if (duration_scope is not None and duration_scope["active"]
                    and duration_scope["address"] == definition_address):
                context["duration_parent"] = duration_scope
                _set_scorn_duration_scope(duration_scope, False)
                break
        if _cooldown_hud_suspended:
            return
        if not _sustenance_allowed_types:
            status_types = unrealsdk.find_enum("EStatusEffectType")
            _sustenance_allowed_types.update((
                int(status_types.STATUS_EFFECT_Ignite), int(status_types.STATUS_EFFECT_Shock),
                int(status_types.STATUS_EFFECT_Corrosive), int(status_types.STATUS_EFFECT_Amp),
            ))
        status_type = int(definition.StatusEffectType)
        if status_type not in _sustenance_allowed_types:
            return
        controller = _sustenance_controller(args.InstigatedBy)
        if controller is None and args.bIsFromSpreading:
            controller = _sustenance_controller(args.SpreadSource.EventInstigator)
        if controller is None and args.DamageCauser:
            resolve_controller = getattr(args.DamageCauser, "GetControllerResponsibleForDamage", None)
            if resolve_controller is not None:
                controller = _sustenance_controller(resolve_controller())
        if controller is None or not _is_maya_controller(controller):
            return
        pawn = controller.Pawn
        target = component.OwnerTarget
        if not pawn or not target or target == pawn:
            return
        # GetOpinion is exposed by WillowPawn; ignore scenery/non-pawn targets.
        if not hasattr(target, "GetOpinion") or int(target.GetOpinion(pawn)) != int(
            unrealsdk.find_enum("EOpinion").OPINION_Enemy
        ):
            return
        if int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority):
            return
        try:
            scorn = unrealsdk.find_object("SkillDefinition", SCORN_PATH)
            if (scorn is not None and int(controller.GetSkillGrade(scorn)) > 0
                    and not definition.bIsInfiniteDuration):
                base = copy.copy(definition.BaseDuration)
                scale = float(base.BaseValueScaleConstant)
                if not -float("inf") < scale < float("inf"):
                    raise ValueError("Scorn status duration has a non-finite scale")
                scaled = copy.copy(base)
                scaled.BaseValueScaleConstant = scale * (1.0 + SCORN_STATUS_DURATION_BONUS)
                scope = dict(definition=WeakPointer(definition), address=definition_address,
                             base=base, scaled=scaled, active=False)
                context["duration_scope"] = scope
                _set_scorn_duration_scope(scope, True)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not apply Scorn status duration: {exc}")
        rank = _skill_rank(controller, SUSTENANCE_PATH)
        if rank <= 0:
            return
        context.update(
            controller=controller,
            target=target,
            definition=definition_address,
            author_addresses={
                controller._get_address(), pawn._get_address(),
                args.InstigatedBy._get_address() if args.InstigatedBy else 0,
            } - {0},
            status_type=status_type,
            rank=rank,
            spreading=bool(args.bIsFromSpreading),
        )
        filters: dict[int, set[int]] = {}
        for parent in _sustenance_status_contexts[:-1]:
            if parent["component"] == context["component"] and parent["before"] is not None:
                for watched, authors in parent["filters"].items():
                    filters.setdefault(watched, set()).update(authors)
        filters.setdefault(definition_address, set()).update(context["author_addresses"])
        context["filters"] = filters
        context["before"] = _sustenance_status_snapshot(component, filters)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        context["before"] = None
        _log_error_once(f"Could not observe Sustenance status application: {exc}")


def _try_sustenance_status_heal(controller: Any, rank: int, status_type: int) -> None:
    pawn = controller.Pawn
    if not pawn or rank <= 0:
        return
    now = time.monotonic()
    controller_address = controller._get_address()
    if now < _sustenance_ready_at.get(controller_address, 0.0):
        return
    current_health = float(pawn.GetHealth())
    max_health = float(pawn.GetMaxHealth())
    if current_health <= 0 or current_health >= max_health:
        return
    new_health = min(max_health, current_health + max_health * SUSTENANCE_HEAL_PER_RANK * rank)
    # Reserve before SetHealth so a nested callback cannot proc a second heal.
    _sustenance_ready_at[controller_address] = now + SUSTENANCE_COOLDOWN_SECONDS
    if len(_sustenance_ready_at) >= 64:
        for old_address, deadline in list(_sustenance_ready_at.items()):
            if deadline <= now:
                del _sustenance_ready_at[old_address]
    pawn.SetHealth(new_health)
    if now >= _sustenance_next_heal_log_at.get(controller_address, 0.0):
        _sustenance_next_heal_log_at[controller_address] = now + 2.0
        if len(_sustenance_next_heal_log_at) >= 64:
            for old_address, deadline in list(_sustenance_next_heal_log_at.items()):
                if deadline <= now:
                    del _sustenance_next_heal_log_at[old_address]
        unrealsdk.logging.info(
            "[MayaRebalance] Sustenance status heal: "
            f"rank={rank}, status_type={status_type}, healed={new_health - current_health:g}, "
            f"cooldown={SUSTENANCE_COOLDOWN_SECONDS:g}"
        )


@hook("WillowGame.StatusEffectsComponent:ApplyStatusEffect", Type.POST_UNCONDITIONAL)
def finish_sustenance_status_application(
    component: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> None:
    if not _sustenance_status_contexts:
        return
    context = _sustenance_status_contexts.pop()
    try:
        _finish_scorn_duration(context)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not restore Scorn status duration: {exc}")
    if _cooldown_hud_suspended:
        return  # Formula restoration is asset-only; do not touch old actors.
    if context["component"] != component._get_address():
        for parent in reversed(_sustenance_status_contexts):
            try:
                _finish_scorn_duration(parent, resume_parent=False)
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _log_error_once(f"Could not unwind Scorn status duration: {exc}")
        _sustenance_status_contexts.clear()
        _log_error_once("Sustenance status hooks were not paired; ignored application")
        return
    before = context["before"]
    if before is None:
        return
    try:
        controller = context["controller"]
        pawn = controller.Pawn
        if not pawn:
            return
        author_addresses = context["author_addresses"]
        after = _sustenance_status_snapshot(component, context["filters"])
        confirmed = any(
            signature[0] == context["definition"]
            and signature[1] in author_addresses
            and count > before.get(signature, 0)
            for signature, count in after.items()
        )
        log_key = (controller._get_address(), context["status_type"], confirmed)
        if log_key not in _sustenance_logged_status_types:
            if len(_sustenance_logged_status_types) >= 256:
                _sustenance_logged_status_types.clear()
            _sustenance_logged_status_types.add(log_key)
            unrealsdk.logging.info(
                "[MayaRebalance] Sustenance status application: "
                f"confirmed={confirmed}, target={context['target']._path_name()}, "
                f"status_type={context['status_type']}, spreading={context['spreading']}"
            )
        if not confirmed:
            return
        # Consume observed changes in enclosing calls on this component. Native
        # callbacks can recursively apply the same effect before the outer POST.
        for parent in _sustenance_status_contexts:
            if parent["component"] == context["component"] and parent["before"] is not None:
                parent["before"].update(after)
        _try_sustenance_status_heal(controller, context["rank"], context["status_type"])
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not process Sustenance status application: {exc}")


def _configure_res_description() -> None:
    # Keep the native skill, effects and Phaselock ally-revive logic intact.
    definition = unrealsdk.find_object("SkillDefinition", RES_PATH)
    if definition.SkillDescription != RES_DESCRIPTION:
        definition.SkillDescription = RES_DESCRIPTION


def _player_skill_state(
    controller: Any,
    states: dict[tuple[Any, ...], dict[str, Any]],
    timer_field: str,
    defaults: dict[str, Any],
) -> dict[str, Any] | None:
    """Stable player/save identity; store primitives, never a previous controller."""
    if int(controller.Role) != int(unrealsdk.find_enum("ENetRole").ROLE_Authority):
        return None
    player_class = controller.PlayerClass
    if not player_class or str(player_class._path_name()) != RES_PLAYER_CLASS_PATH:
        return None
    pri = controller.PlayerReplicationInfo
    if not pri:
        return None
    uid = pri.UniqueId.Uid
    network_id = int(uid) if isinstance(uid, int) else (int(uid.A), int(uid.B))
    identity = network_id if network_id not in (0, (0, 0)) else ("offline", int(pri.PlayerID))
    save = controller.GetCachedSaveGame()
    # Remote cached saves may be unavailable. Sharing that player's cooldown
    # conservatively is safer than granting another charge on pawn replacement.
    save_id = int(save.SaveGameId) if save else "uncached"
    key = (identity, save_id)
    unknown_key = (identity, "uncached")
    if save and key not in states and unknown_key in states:
        states[key] = states.pop(unknown_key)
    if not save:
        known = [value for (owner, _save), value in states.items() if owner == identity]
        if known:
            return max(known, key=lambda value: value[timer_field])
    if key not in states:
        # Bound idle history without evicting a cooldown or pending FFYL recovery.
        if len(states) >= 64:
            expired = time.monotonic() if timer_field == "ready_at" else 0.0
            for old_key, state in list(states.items()):
                if (state[timer_field] <= expired and not state.get("down")
                        and not state.get("pending") and not state.get("awaiting")):
                    del states[old_key]
        states[key] = dict(defaults)
    return states[key]


def _res_state(controller: Any) -> dict[str, Any] | None:
    return _player_skill_state(
        controller, _res_player_states, "remaining",
        dict(remaining=0.0, down=None, pending=None, awaiting=None, wait=0.0),
    )


def _recompense_state(controller: Any) -> dict[str, Any] | None:
    return _player_skill_state(
        controller, _recompense_player_states, "ready_at", dict(ready_at=0.0),
    )


def _res_confirm_recovery(pawn: Any, state: dict[str, Any]) -> bool:
    if pawn.IsInjured() or pawn.IsInjuredDead() or float(pawn.GetHealth()) <= 0:
        return False
    state.update(remaining=RES_COOLDOWN_SECONDS, awaiting=None, down=None, pending=None)
    unrealsdk.logging.info(
        f"[MayaRebalance] Res Second Wind confirmed: cooldown={RES_COOLDOWN_SECONDS:g}, "
        f"health={float(pawn.GetHealth()):g}, shield={float(pawn.GetShieldStrength()):g}"
    )
    return True


def _reset_res_after_death(state: dict[str, Any]) -> None:
    had_cooldown = state["remaining"] > 0.0
    state.update(remaining=0.0, down=None, pending=None, awaiting=None, wait=0.0)
    if had_cooldown:
        unrealsdk.logging.info("[MayaRebalance] Res cooldown reset after death")


@hook("WillowGame.WillowPlayerPawn:Died", Type.PRE)
def prepare_res_death_reset(pawn: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    state = None
    if not _cooldown_hud_suspended:
        try:
            controller = pawn.Controller
            if controller and controller.Pawn == pawn:
                state = _res_state(controller)
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            _log_error_once(f"Could not prepare Res death reset: {exc}")
    # Keep only primitive state. Died may detach/destroy the pawn/controller
    # before returning, so POST must not resolve either actor or the HUD again.
    _res_death_contexts.append(state)


@hook("WillowGame.WillowPlayerPawn:Died", Type.POST_UNCONDITIONAL)
def reset_res_cooldown_after_death(_pawn: UObject, _args: Any, ret: Any, _func: Any) -> None:
    if not _res_death_contexts:
        return
    state = _res_death_contexts.pop()
    if state is not None and ret is True:
        _reset_res_after_death(state)  # False/blocked death and FFYL never reset it.


def _res_observe_entry(controller: Any, pawn: Any, state: dict[str, Any]) -> None:
    address = pawn._get_address()
    if state["down"] == address:
        return
    state["down"] = address
    state["pending"] = None
    if pawn.IsInjuredDead() or _invested_skill_rank(controller, RES_PATH) <= 0:
        return
    if state["remaining"] > 0.0:
        unrealsdk.logging.info(
            f"[MayaRebalance] Res unavailable: cooldown={state['remaining']:.2f} seconds"
        )
        return
    state["pending"] = address
    unrealsdk.logging.info("[MayaRebalance] Res FFYL entry: auto Second Wind queued")


@hook("WillowGame.WillowPlayerPawn:SetupPlayerInjuredState", Type.POST)
def queue_res_auto_second_wind(pawn: UObject, _args: Any, _ret: Any, _func: Any) -> None:
    try:
        controller = pawn.Controller
        if not controller or controller.Pawn != pawn:
            return
        state = _res_state(controller)
        if state is not None and pawn.IsInjured():
            _res_observe_entry(controller, pawn, state)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not queue Res Second Wind: {exc}")


def _tick_res_second_wind(controller: Any, delta: float) -> None:
    state = _res_state(controller)
    if state is None or controller.WorldInfo.Pauser:
        return
    delta = max(0.0, float(delta))
    state["remaining"] = max(0.0, state["remaining"] - delta)
    pawn = controller.Pawn
    if not pawn:
        state.update(down=None, pending=None, awaiting=None)
        return
    address = pawn._get_address()
    injured = bool(pawn.IsInjured())
    dead = bool(pawn.IsInjuredDead())
    if dead:
        _reset_res_after_death(state)  # Fallback if native Died was not observed.
        return
    if state["awaiting"] is not None:
        if state["awaiting"] != address or dead:
            state["awaiting"] = None
            _log_error_once("Res Second Wind failed: pawn changed or died; charge not consumed")
        elif _res_confirm_recovery(pawn, state):
            pass
        else:
            state["wait"] += delta
            if state["wait"] >= 1.0:
                state["awaiting"] = None
                _log_error_once("Res Second Wind did not leave FFYL; charge not consumed")
    if not injured or dead:
        state.update(down=None, pending=None)
        return
    # Tick fallback detects entry even if the setup callback was not dispatched.
    if state["down"] != address:
        _res_observe_entry(controller, pawn, state)
        return  # Wait another gameplay tick before attempting the transition.
    if state["pending"] != address:
        return
    state["pending"] = None  # Never retry every frame in the same FFYL.
    if state["remaining"] > 0 or _invested_skill_rank(controller, RES_PATH) <= 0:
        return
    state.update(awaiting=address, wait=0.0)
    try:
        # Native recovery, not a fabricated kill, damage block, or manual heal.
        pawn.SetSecondWindReason(unrealsdk.find_enum("ESecondWindReason").ESECONDWIND_AutoRevive)
        pawn.RejuvenateFromInjured()
        _res_confirm_recovery(pawn, state)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        state["awaiting"] = None
        raise


@hook("WillowGame.WillowPlayerController:PlayerTick", Type.POST)
def tick_res_auto_second_wind(controller: UObject, args: Any, _ret: Any, _func: Any) -> None:
    try:
        _tick_res_second_wind(controller, float(args.DeltaTime))
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not update Res Second Wind: {exc}")


@hook("WillowGame.WillowPlayerPawn:TakeDamage", Type.PRE)
def recompense_avoid_damage(
    pawn: UObject,
    args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> type[Block] | None:
    controller = pawn.Controller
    if not controller:
        return None

    try:
        # A zero-damage notification is not an eligible hit for avoidance.
        if float(args.Damage) <= 0.0:
            return None
        state = _recompense_state(controller)
        if state is None:
            return None
        rank = _skill_rank(controller, RECOMPENSE_PATH)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log_error_once(f"Could not process Recompense incoming damage: {exc}")
        return None

    now = time.monotonic()
    if rank <= 0 or now < state["ready_at"]:
        return None

    if random.random() < min(1.0, RECOMPENSE_AVOID_CHANCE_PER_RANK * rank):
        state["ready_at"] = now + RECOMPENSE_COOLDOWN_SECONDS
        return Block

    return None


build_mod(cls=_RestartSafeMod)
unrealsdk.logging.info(
    "[MayaRebalance] Loaded 1.0; restart-safe lifecycle; isolated Recompense cooldowns; "
    "quarter-second stat sync; Elated gameplay tick; paired native firing hooks; "
    "Wreck passive/Phaselock split, native lifecycle guard; "
    "Elemental Mastery (7.5% per unique elemental status, max 4); "
    "pause-aware combat HUD; "
    "character-scoped ammo/status/HUD hooks; "
    "separate logical/physical HUD slots; "
    "native-only HUD feedback; character-pawn Phaselock validation; "
    "ranked UI via GetSkillDescriptionForGrade; Res auto Second Wind (120s, reset on death); "
    "Res/Recompense HUD lifecycle guard enabled; Blight Phoenix elemental ammo/speed enabled; "
    "Blight Phoenix zero-cost firing guard enabled; "
    "Scorn/Ruin author-defined level curves through OP10; "
    "Backdraft/Scorn completed-hit native event bridge enabled; allocation guards; "
    "Quicken input-only maintenance; release audit 2026-10-26; "
    "Psychic Shriek: enemy damage -20%, target damage taken +15%, 8s, team; Phaselock duration +2s; "
    "Psychic Shriek native HUD feedback with shared non-overlapping slot allocation; "
    "fresh Psychic Shriek rank/radius lookup across menu/asset reload; "
    "Immolate independent post-hit fire dispatcher with exact pipeline scope; "
    "source-scoped received-damage modifiers and duplicate-status scan reduction; "
    "ricochet-path filter, empty-stack shortcut and stable-effect copy avoidance; "
    "Scorn passive elemental duration +50%; filtered Sustenance snapshots and sampled heal logs; "
    "Kinetic Reflection: half-strength general protection, non-stacking native bullet reduction; "
    "cached received-damage attribute fallback; four-argument area trace; "
    f"source={__file__}"
)

