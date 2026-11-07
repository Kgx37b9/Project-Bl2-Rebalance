# Development notes - KriegRebalance 1.0.12

## Release documentation review - 7 November 2026

Version remains 1.0.12: this pass changes documentation only, not runtime behavior. README is the current feature summary; older version sections below preserve the implementation history and their original coefficients/test status. Later version notes supersede earlier values. No new gameplay test or co-op validation was performed for this documentation pass.

### Intermittent Pain is Power indicator

On 6 November the author reported an absent indicator, then confirmed it returned after restarting. The new session logged native HUD registration in slot 3 at 17:12:30 local time, with stacks present and no Krieg error observed. No snapshot of the failing state was obtained. Registration and the author's rendering confirmation establish recovery in that session, not a root-cause fix. The read-only HUD probe now records primitive Pain/Fuel state, gameplay helpers and native slots. Capture a recurrence before restarting; no speculative HUD rewrite was made.

### Release contents

Publish __init__.py, pyproject.toml, README.md, CHANGELOG.md, DEVELOPMENT.md and LICENSE.md together. Keep probes, offline fixtures, SDK logs and the workspace knowledge guide outside the distributable package. No archive was generated or installed by this review. The existing personal-use/permission-required license is unchanged.

## Bloodlust balance (1.0.12)

Only coefficients/log labels changed: Blood-Filled Guns damage0.004; Blood Bath0.003; Overdrive extra-stack chance0.10 per effective rank with existing min(1,chance). Display paths derive from these coefficients. Preserve clip0.0025, native rank formulas, movement/fire threshold, timers, HUD and runtime optimization. Eleven focused checks passed, covering damage/footer rank agreement and exact random boundaries through rank9, guaranteed rank10/11, and50% rank5. No new hooks or polling.

## Fuel the Rampage reduction (1.0.11)

Remove FUEL_REDUCTION_LIMIT. Both damage and footer now use0.09*effective rank directly; native input multiplier is1-0.09*rank. The existing shared effective-rank limit remains11, so the maximum supported rank gives0.01 incoming self-damage without an extra resistance cap. Preserve independent damage multiplication, status exclusion, movement/HUD and event timing. Seven focused numerical/description checks passed; native gameplay confirmation remains pending.

## Fuel the Rampage HUD (1.0.10)

FUEL_SPEED_PER_RANK is now0.10. A separate private FUEL_HUD_PATH leaf uses the parent menu icon, Grade1 and infinite visual duration; it has no effects, constraints, damage/kill events, children or CustomStackCount. Extend the shared feedback builder with counter=False to avoid allocating unused stack-counter resolvers; existing counters keep their default behavior.

_sync_fuel_rampage_hud runs from the existing0.25s Pain HUD cadence and rejects an idle feature before native lookups. Only show it for the current local owner/world/pawn, a positive learned rank, an unexpired primitive fuel deadline and an active positive-grade native movement helper. Use existing pause, departure, movie-owner and world guards. The shared allocator can deactivate or move only the visual when slots collide; never give it the gameplay helper. _fuel_hud_owners stores integer owners only, permits cleanup after deadline removal, and resets on travel/destroy/enable. The native helper owns gameplay timing; the icon disappears on the next HUD update after expiry. No new tick hooks or canvas drawing.

Forty-seven focused/adjacent offline checks passed:9 new HUD tests,31 Fuel gameplay/description tests,3 COM footer tests and4 shared visual/slot checks. Legacy Fuel tests still expected19% self-damage reduction from an earlier revision; their expected values were aligned with the existing9.5% coefficient, without changing that gameplay coefficient. Validate after restarting: direct self-hit, +50% speed at5/5, icon for12 seconds and renewal, expiration/FFYL, occupied native slots, menus and travel; co-op remains unvalidated.

## Performance audit (1.0.8)

The installed 1.0.7 SDK log for 6 November shows no Krieg errors, successful configuration of the recent changes, and normal event-driven Pain stack messages. BSABT reports None.ExitPoints at save_spawn_station (13:32:23 local); this belongs to another mod and does not establish the cause of combat stutter. No native frame-time trace was available, so neither a DLC-specific cause nor measured FPS improvement is claimed.

The main PlayerTick previously executed all25 static configure functions every2 seconds, including owned struct/formula creation and recursive comparison for six new Blood Twitch reserve initializers. Completed steps are now remembered by string names; unresolved/failed steps keep retrying at the original cadence. Completion state is invalidated on enable, Initialize PRE, frontend start and detection of a different current world in the maintenance pass. No UObject or actor is stored in this cache; the world identity is only an integer. Runtime COM refresh, native regen effects, HUD collision allocation and gameplay repair routines continue normally. External mid-world rewrites of already-verified static definitions are no longer continuously overwritten; the documented lifecycle invalidation revalidates them.

Pain health-damage POST still updates the expiry for every confirmed hit. It skips immediate helper sync only when the computed count is already at the cap. The existing0.1s repair pass handles class-mod/context changes; new or regained stacks still sync immediately. A regression at TimeSeconds15.1 exposed deadline20.1-now15.1 rounding above5.0; the rewind comparison now allows1e-6 tolerance without changing intended decay.

Forty relevant checks passed:8 new cache/per-hit checks,22 Pain gameplay-model checks,8 prior runtime-audit checks and2 maintenance/streaming integration checks. A controlled fixture observed25 first-pass config calls and0 more across30 warm passes. This is work-count evidence only. Next native check: restart on1.0.8, repeat the Tina DLC combat with the same weapon/skills, include5-stack incoming damage, then travel and verify unchanged regen/HUD/COM behavior. Do not hot-reload while actors are active.

## Blood Twitch native reserve regeneration (1.0.7)

ResourcePoolAttributeDefinition paths D_Attributes.AmmoResource_{type}.Ammo_{type}_RegenerationRate resolve ActiveRegenerationRate (absolute units/s). Corresponding MaxValue attributes provide each ammo capacity. Verified six types in local native dumps: Combat_Rifle, Combat_Shotgun, Patrol_SMG, Repeater_Pistol, Rocket_Launcher, Sniper_Rifle. Native ammo pools start with zero regeneration, so MT_PostAdd adds independently to existing regeneration rather than scaling zero.

For each type the private initializer uses Multiplier=MaxValue*0.0002, Level=1, Power=1, Offset=0 with the original BASEVALUE_InitializationDefScalesBaseValue mode. Effect input is Bloodlust stacks and both base and upgrade match: rate=MaxValue*0.0002*stacks*effective Grade. No nested rank resolver, clip counter write, AddRegeneratedAmmo call or new tick. Preserve melee initializer and native swap effects; remove only effects referencing our former Recoil initializer. Own retained effect structs before replacing the native array. Existing COM tuning revision invalidates caches once.

Nineteen focused/adjacent offline checks passed, including all six capacities, ranks0..11, native float views/idempotence, selective recoil migration, pending assets, COM/footer colors, and absence of Overdrive amplification. Native full-pool clamping, true reserve-only gameplay and co-op need confirmation after restart.

## Blood Overdrive / Nervous Blood swap (1.0.6)

Native Branch_Bloodlust has BloodOverdrive at Tiers[1].Skills[2] and NervousBlood at Tiers[4].Skills[0]. Validate both native or already-swapped rows and occupied-cell masks before writing. Exchange skill references using owned copies of every retained tier; the layout masks and PointsToUnlockNextTier stay unchanged. Run via existing Initialize PRE and configuration maintenance. Blood Euphoria also copies all retained tier structs before replacing its shared arrays, avoiding borrowed views invalidated by native setters. No live learned-tree rebuild or save-grade changes. Movement/fire coefficients now0.05/0.04; native fire interval uses negative sign as before. Eight focused checks covered placement, both configuration orders, initialization, missing/unexpected layouts, native bonus math and footer colors/ranks. Fresh-process in-game validation pending.

## Blood Bath coefficient (1.0.5)

The root skill effect0 displays a constant per-rank coefficient, while BloodBathChild uses stacks with Init_BloodBath_DamageModifier. Configure the root base/upgrade at0.004 and the initializer multiplier as constant0.004, preserving its native parent-grade Level, Power and Offset. This avoids stale designer-attribute coefficients without replacing the kill graph or changing grenade drops. Retained effect structs are owned copies. Existing configuration maintenance remains idempotent; no new hooks or polling. Three focused checks passed; engine validation pending.

## Blood-Filled Guns (1.0.4)

Native magazine coefficient is 0.005 per rank per stack. Configure the display-only effect at 0.0025 and replace the nested rank initializer on the real clip effect with stacks * 0.0025 in both base and per-grade terms. Add a native MT_Scale WeaponDamage effect using stacks * 0.002 in both terms. Native Grade applies the effective rank exactly once. Keep constraints, Bloodlust cap and tracked counter. Copy retained structs before replacing the native array; configure idempotently through existing maintenance. Add the skill to existing COM cache refresh with a tuning revision. Native magazine footer uses two decimals; a menu-only hook appends gun damage with the shared current/next-rank formatting helper. No new combat tick or per-hit hook. Eight relevant offline checks passed; actual gameplay and COM swaps need confirmation.

## Salt the Wound decay interval (1.0.3)

Native dump: SaltTheWound:BehaviorProviderDefinition_14, BehaviorSequences[1] StackDecay. Its subtraction/clamp feeds output link 2, which schedules remote StackDecay again (packed link -16777216). Configure only ActivateDelay=1.5 in place, validating the sequence and link first. Leave the Default sequence metronome, StackHoldTime reset, stack bonuses and HUD untouched. No new hooks or polling; use existing configuration retries. Three focused offline checks passed; actual timing requires a fresh-process gameplay test.

## Salt the Wound counter collision (1.0.2)

The read-only live HUD snapshot at 22:15:37 local time on 2026-11-05 shows SaltTheWound_Stacks and Bloodlust_Stacks both as tracked type 3, logical slot 1, registered RemappedSlot 1 and actual remap 1. The displayed icon in that slot is Bloodlust's Psycho37. The root Salt the Wound skill has grade 5; its stack leaf was paused (state 2) at snapshot time, so this sample alone does not demonstrate nonzero Salt stacks. The duplicate registration nevertheless proves the layout conflict. Pain's indicator was in slot 5 and was not the occupant hiding Salt.

The previous alternate layout used Salt=1 and Elation=2, overlooking Bloodlust's native slot 1. Native SkillDefinition dumps confirm Bloodlust=1, Salt=3, Elation=3, Hellfire=4, Bloody Revival=5 and Numbed Nerves=6. Restore Salt=3 and keep Elation=2, separating the three native counters without moving Bloodlust or touching their effects. Apply the definition layout in the existing Initialize PRE hook before native registration, not only in the later two-second maintenance pass. The custom visual allocator already reserves learned native children and registered/remapped entries; leave it intact. No new HUD polling, skill activation/deactivation, forced stack values or edits to active native arrays are needed for this fix. A full restart is required to rebuild registrations from the corrected definitions.

Five focused layout checks passed, including preserving Bloodlust, preparing the layout before registration and avoiding repeated writes. All 23 Pain HUD and 24 Bloody Revival HUD checks also passed. Syntax/metadata validated. Next engine test: fresh process, allocate the relevant skills, take enemy damage to health to generate Salt stacks, and verify its icon together with Bloodlust, Elemental Elation and custom indicators; repeat after travel. The read-only probe can verify distinct native registrations. Installed files were not changed by tools.

## Class-mod description ranks (1.0.1)

The custom Blood Overdrive footer added GradeModifier to Grade even though native GetSkillDescriptionForGrade already supplies the effective rank, including the preview increment. Thus a rank-10 query with COM +5 was computed as 15 and capped at 11. Pain is Power, Fuel the Rampage and Bloody Revival had the same mistake. All six custom ranked footers now use a shared query-rank helper; Fuel the Fire and Blood Twitch retain their already-correct results. GradeModifier remains only for invested-rank color eligibility and diagnostic metadata. Light the Fuse's fixed-value color condition also no longer adds COM metadata. Runtime COM caches and gameplay coefficients were not changed.

Regression coverage includes 5+5=10, allocated ranks 0..5 with COM +0/+2/+5/+6, separate current/next queries, equipment swaps and green versus intermediate preview colors. Nineteen relevant offline tests passed; visual confirmation remains pending. Three older tests incorrectly modeled Grade as invested-only; corrected their inputs to native effective grades. Also corrected a stale Fuel the Rampage color-test expectation left at 19% despite the existing 9.5% gameplay coefficient.

This document records implementation scope, measured facts and remaining engine-validation limits. The public feature summary is in README.md; release changes are in CHANGELOG.md.

## Historical 1.0 balance pass (superseded by 1.0.10-1.0.12)

### Burn, Baby, Burn

The mod writes two existing `ConstantAttributeValueResolver.ConstantValue` values used by the skill and its on-fire child:

- `Att_BurnBabyBurn_BurnModifierBonus`: 0.20 per effective rank.
- `Att_BurnBabyBurn_BurnModifierBonusWhileOnFire`: 0.10 additional per effective rank.

At 5/5 the ordinary bonus is +100% Burn Damage. While on fire, the additional term brings the total to +150%. The implementation revises native resolver values and marks active parent/child skill instances for a one-time modifier refresh when the tuning revision changes. It does not add a per-hit hook.

### Fuel the Rampage

Direct self-damage reduction uses a separate damage multiplier, `1 - min(0.95, 0.095 * effective_rank)`. At five effective ranks this is 47.5% reduction. The cap remains for ranks added by class mods. The already existing speed effect stays at 7% per effective rank for 12 seconds after qualifying direct self-damage; status damage is excluded. Neither duration nor speed changed in 1.0.

## Krieg special melee: what the code changes

The runtime configuration changes only this native initializer:

`GD_Lilac_SkillsBase.ActionSkill.Init_RampageBonusDamagePerLevel.ValueFormula`

Its `Level` input references `GD_Lobelia_GameStages.Attributes.GameStageViaGetGameStage` at scale 0.02. `Multiplier`, `Power` and `Offset` are set to 1, yielding the formula `1 + 0.02 * GameStage`. The component evaluates to 2.6 at GameStage 80 and 2.8 at GameStage 90, the expected stage for level 80/OP10.

This is not a general melee-damage modifier and the code does not hook weapon damage, ordinary melee events, axe throws or damage processing. The initializer is attached to Krieg's special melee/action-skill data; the Python implementation does not enumerate every native graph that consumes it. Therefore the precise set of attack animations that read this initializer remains unverified without inspecting the native consumer graphs or comparing damage by attack type in-game. The formula directly reads GameStage and does not read a global damage-scaling setting; final hits may still be affected by other game and mod multipliers.

## Bloody Revival recovery and HUD

Version 0.1.48 added an FFYL-entry watch and caches the native Second Wind reason. The existing player tick checks for recovery only while this watch is armed; it does not add an idle per-frame query. The native injured-to-healthy callback remains the immediate path, and both paths share stack state to prevent duplicates. Partner-revive reason 3 and death are excluded. If a confirmed local recovery has no reason value, the fallback counts it and emits a diagnostic. The reported in-game regression prompted this addition because the earlier game log contained no stack-award event.

Offline focused mocks cover native callback and fallback paths, duplicate suppression, partner revive, death and HUD state. They cannot prove the game dispatches each native event identically in all modes. The author confirmed the icon returned after a successful solo Second Wind on 0.1.48; this code path is unchanged in 1.0. Co-op remains unvalidated. The two new balance values still need in-game confirmation.

## Compatibility and release

- Requires Borderlands 2 and the modern Willow2 Python SDK/Mod Manager.
- Mods that edit the same Krieg skills, initializers or damage pipeline can conflict.
- The optional EndgameQoLRebalance module changes global balance separately.
- Fully restart the game after replacing or disabling this package. Do not hot-reload during a gameplay session.
- No `.sdkmod` is included in a public source repository unless packaged separately by the release maintainer.

## Fuel the Fire class-mod description fix

`GetSkillDescriptionForGrade.Grade` already contains the class-mod contribution and the preview increment. `describe_fuel_the_fire` had added `GradeModifier` again, causing both description blocks to clamp at effective rank 11. It now uses only the native `Grade`, as Blood Twitch does. No cached rank or new runtime query is introduced. With a +6 COM, the first-point preview is rank 7 (+28%), followed by current rank 7 / preview rank 8 (+28% / +32%); rank 11 (+44%) is reached only at 5 invested points. Eleven focused offline tests cover current/preview ranks, COM changes, colors and native effects. Python syntax is valid; in-game confirmation is pending.

## Temporary audio investigation

The author reports a sound apparently beginning while on fire, continuing during movement and stopping while stationary. The reviewed SDK session contains no audio exception or event trace; the actual sound and cause remain unidentified. Do not equate this report with the earlier slag constraint problem: the support module already keeps its NPC debuff graph silent and preserves the native slag callbacks. Hellfire's ignition uses the native incendiary status, whose original application/end callbacks post separate Play/Stop events. Its normal refresh path does not reactivate that status.

A temporary opt-in console command, `krieg_audio_trace`, enables observation for 90 seconds; invoking it again stops it. Before reproducing the problem, enable the command, walk, stop and wait until the fire ends. The command logs calls to verified Actor/PlayerController audio entry points only for the local pawn/controller, plus half-second samples of movement/status transitions. It never blocks audio or writes status definitions. Counts describe observed entry calls, not unique playback instances: an event can traverse several entry points. Native Wwise events posted outside those interfaces may remain invisible. Start capture before the suspected trigger.

Diagnostic hooks are absent from normal gameplay registration and enabled only by the command. They stop on timeout, pawn replacement or departure, cap unique event keys at 64, log repeated calls only at counts 1/2/8/32, and keep no UObject references. Six focused diagnostic tests, one registration test and eleven adjacent Fuel the Fire tests pass; syntax is valid. No audio root-cause fix is claimed pending reproduction. Native interface evidence: local Borderlands2SDK Engine_classes.h; original fire callback evidence: local OpenBLCMM BL2 2023-04-20 data dump.

### Follow-up: Hellfire Halitosis trigger confirmed by the author

The author confirms using Hellfire Halitosis before the noise and hearing it after the visible flames end. The original graph posts `Ake_Lilac_PL_Psycho.Ak_Play_FX_Player_Psycho_Flame_Breath`; native self-burn posts the distinct `Ake_FX_Global.Ak_Play_FX_Elemental_Incendiary_StatusEffect_lp` / Stop counterpart. Both are candidates, not identified causes. The current SDK log still has no Audio trace entries. Capture should begin before breathing fire, followed by moving/stopping both during and after ignition. No additional gameplay/audio change follows solely from this correlation.
