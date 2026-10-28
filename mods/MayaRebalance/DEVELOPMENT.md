# Development notes

Documentation review: 28 October 2026. This file separates implementation
observations, historical investigations and outstanding engine validation.
The current balance summary is in README.md; version history is in CHANGELOG.md.

## Follow-up review and solo evidence - 28 October 2026

The user reported successful solo testing. The SDK log for 13:13-13:17
America/Sao_Paulo (16:13-16:17 UTC) contains 318 lines, no ERROR/WARNING,
tracebacks or missing-delivery diagnostics. Installed gameplay source matches
the tested workspace exactly (SHA256
`fa7507a18676166ceade8cee5059a9945644f57a837f8ea1d3e77981e48ac5f8`).
The installed archive has different ZIP metadata/a directory entry; its Python
contents are identical, so archive size alone is not a version mismatch.

Four Immolate windows were logged. Three sampled completed hits match their
expected final fire damage: 339.201, 339.201 and 124.694. FinalShield is zero in
all three samples. This confirms dispatch and normalization in those solo
health-damage cases; it does not prove every source fraction, shield overflow,
co-op or frame-time behavior. Res also logged a confirmed automatic Second
Wind with a 120-second cooldown. Menu suspension/resumption was observed.
Support-module INFO entries about unloaded assets are deferred work, not errors.

The follow-up hardening changes only Immolate's exceptional paths: after the
native calculation completes, correction failure returns Block plus the native
summary rather than allowing a fallthrough that could recalculate the hit.
A partially adjusted shield is rolled back where possible; rollback failure is
reported. Logging failure preserves the corrected result. Teardown after the
native call avoids further target reads. Balance and HUD behavior are unchanged.
The stale startup phrase about live graph validation was replaced as well.

53 targeted offline tests passed, including native-summary fallback, diagnostic
failure and teardown during native calculation. The hardening itself has not
been tested in the engine yet. Expanded shield/proc-kill/COM/high-projectile
cases remain acceptance checks, and co-op remains Unknown. This is a scoped
review of the new damage dispatcher and adjacent rank/lifecycle/debuff/HUD
paths, not a claim that the entire mod is free of vulnerabilities.

## Independent Immolate delivery - 28 October 2026

This update supersedes the graph-based implementation described in the earlier
review and investigation below. The backup is stored outside the installable
package as `../Suporte/MayaRebalance_pre_immolate_independente_20261028.zip`.

- The native skill's damage events and behavior-provider reference are detached.
  No Immolate output/variable link or SimpleMath coefficient is modified. A
  narrowly scoped blocker suppresses legacy CauseDamage_113 calls retained by
  old instances or another mod; it never redirects their graph.
- A paired AI TakeDamage scope captures scalar final health/shield damage from
  bullet/rocket pipelines. The proc is emitted only after the source call ends,
  if the target is alive, the owner/world are still valid and the window remains
  active. No next-frame actor queues or manual ShotEnemy notifications are used.
- The player pawn borrows an engine pipeline with the native incendiary damage
  definition, emits one Skill-source TakeDamage event and releases the pipeline
  in finally. Native parameters were checked against McSimp's Engine and
  WillowGame reflected parameter headers. No private damage UObject is allocated
  per projectile. There is no copied behavior graph in this dispatcher.
- Normalization is restricted to the exact pipeline/target/owner identity of
  that emitted event. The native adjustment is executed once with direct-call
  hook suppression; health/shield are corrected to 5% per effective rank of
  the original final damage. Existing Elemental Mastery/Psychic Shriek bonuses
  are inherited from the source once, rather than applied twice.
- A synchronous guard excludes recursive procs. Every source scope is paired
  with POST_UNCONDITIONAL, including blocked/nested calls. DoT, grenades, melee,
  other skill hits, healing, zero/nonfinite damage, remote clients and teardown
  are excluded. Source hits that already kill the target emit no corpse hit.
- Window duration remains 12 seconds. The existing native visual-only HUD,
  dynamic slot allocation and pause/menu behavior are unchanged.

### Validation of this replacement

The initial replacement passed 50 targeted tests; the follow-up above passed 53.
They cover fractions at ranks 1/5/11, subclasses/rockets,
shield overflow with and without immediate shield consumption, exact scope,
multiple pellets/ricochets, nested events, blocked sources, failed dispatch,
respec/expiry/teardown and integration with the two damage debuffs. Native HUD
regressions are retained. These mocks do not establish actual game delivery or
co-op support; co-op remains Unknown.

After fully restarting, allocate Immolate 5/5 and compare a non-elemental,
single-pellet body hit outside/during/after Phaselock. During the 12-second
window the fire hit should equal 25% of the source's final damage. Check shields,
critical hits, proc kills, ranks/class-mod swaps, Sand Hawk/Chain Reaction fights
and repeated menu re-entry. Look for `Immolate independent window` followed by
`Immolate final damage` with final health + shield equal to Expected. Any
`did not reach its dedicated damage pipeline` message means delivery failed;
activation/HUD alone is not acceptance. Do not restore the graph bypass as a
silent fallback. The package must not be hot-reloaded into an older session.

Primary native API references:
[Engine parameter headers](https://github.com/McSimp/Borderlands2SDK/blob/master/src/GameSDK/Engine_f_structs.h),
[WillowGame parameter headers](https://github.com/McSimp/Borderlands2SDK/blob/master/src/GameSDK/WillowGame_f_structs.h).

## Earlier provenance review: Immolate (before the replacement below)

At the documentation-review snapshot, `_configure_immolate_native_trigger` still set
`ConsolidatedOutputLinkData[4].LinkIdAndLinkedBehavior = 1`.
This is the native graph bypass documented by 55tumbl in
[Elemental Banshee Maya](https://github.com/BLCM/BLCMods/blob/master/Borderlands%202%20mods/55tumbl/Elemental%20Banshee%20Maya/ElementalBansheeMaya.blcm#L310-L318).
At that snapshot it was a **retained technical adaptation**, not merely a historical inspiration.
Subsequent changes do not establish that this graph modification was replaced.

| Component | Current attribution/status |
| --- | --- |
| Immolate output-link 4 bypass to destination 1 | Retained adaptation of the documented Elemental Banshee Maya edit. |
| Native game behaviors, fields and art | Borderlands 2 data, accessed through the SDK; not authored by this project. |
| Phaselock activation window, guarded final-damage normalization and cleanup | Project-specific follow-on implementation; does not erase the retained graph adaptation. |
| Ruin/Scorn/Helios bonus curves | Current project-defined linear percentages; Skill Scaling Patch remains an earlier research reference. |
| UCP adjustments | Balance reference and earlier adapted implementations; no blanket claim that every adapted field has been replaced. |

### Reference conditions and evidence

55tumbl's [Elemental Banshee Maya README](https://github.com/BLCM/BLCMods/blob/master/Borderlands%202%20mods/55tumbl/Elemental%20Banshee%20Maya/README.md)
asks users of small reused pieces to credit and notify the author; broader reuse
requires permission first. It also restricts reuploading the original files.
No author notification or permission confirmation was supplied in this workspace.
This review did not contact authors. Attribution records provenance; it does not
establish fulfillment of those conditions. LICENSE.md covers only the original
contributions owned by Kgx37b9 and cannot relicense this adaptation.

The internal derivation audit is retained at
`../Suporte/MAYA_AUDITORIA_DERIVACOES.md`; it records earlier findings rather than
serving as evidence of permission. Original reference packages are not bundled.

## Earlier documentation-review validation and remaining limits

- The documentation split changes no gameplay Python. Validation for this task
  covers links, TOML, package contents and unchanged gameplay source hash only.
- Earlier offline tests exercise mocked native interfaces. They do not run the
  engine, prove final damage values or certify co-op.
- Solo user reports confirm many earlier behaviors; the newest numerical and
  Backdraft changes still require targeted in-game comparisons after restart.
- Phaselock's configured 1.75 scale is not proof of +75% versus every setup:
  the earlier UCP configuration uses a different scale (25) on a relevant direct
  damage behavior. Verify native baseline, linked inputs and load order before
  asserting a measured increase. No gameplay change was made during this review.
- Clean logs are not frame-time measurements. Test repeated menu/re-entry,
  class-mod swaps, respecs and high-projectile/status fights separately.
- Co-op remains Unknown; do not infer network authority or replication coverage
  from local tests. Retained lifecycle guards are required during teardown.

## Current Immolate acceptance check

After a complete restart, use a single-pellet non-elemental gun, no class mod,
amp shield or other on-hit effects. Compare body hits before Phaselock, during
its 12-second window and afterward. At rank 5, the separate final fire hit should
be 25% of the original final health-plus-shield damage; at rank 1, 5%; at rank 0,
none. Check shields, critical hits and overflow separately. Melee, grenade and
DoT sources should not trigger it. Retest FFYL without an active window.

## Damage tuning and native-flow research

The following dated engineering notes were moved from the former README.
They preserve investigation history; later values in README/CHANGELOG supersede
intermediate values and pending statements. Damage-base diagnostics are not
interchangeable with final incoming/health/shield measurements.

Current damage progression (28 October 2026):

| Level / stage | Ruin extra damage | Scorn extra damage | Helios extra damage |
| --- | --- | --- | --- |
| 1 | 15% | 25% | 15% |
| 80 + OP10 (stage 90) | 190% | 235% | 125% |

Extra damage progresses linearly on every stage from 1 to 90 and holds its
percentage above stage 90. Percentages are bonuses, not final multipliers: +190%
means 2.90 times the baseline. Ruin and Scorn keep their private level-only
definitions (nominal bases 1/8); Helios keeps its native rank-sensitive initializer
and replaces the previous flat UCP increase. Both its initial hit and native burn
damage receive the new Helios percentage. Its native rank and level calculations
remain live. No global scaler is hardcoded: the default reference is 1.05, and
changing the game scaler changes baseline damage without changing these percentages.

Phaselock's native direct damage is increased by 75% at every level. Its original
linked inputs remain intact and the fixed 1.75 factor does not compound between
casts. Ruin's native-flow/timing fixes, status chance, Scorn's status-duration
bonus and Backdraft beam interaction are preserved. No hooks were added.
In-game validation of these new values is pending; credits below retain the
history of earlier implementations.

Ruin native-flow correction (28 October 2026): keep all five original native
input bindings and restore older detached groups only when necessary. With
Ruin trained, Phaselock entry also repairs a missing RuinSkill definition
reference on the current action. The own damage curve is still applied in the
existing pre-behavior callback. No manual status application or extra damage
event is introduced. In-game confirmation remains pending.

Ruin activation timing follow-up: the definition reference is now prepared on
Phaselock's archetype and in the existing PRE start event, before native action
initialization. The former POST repair happened too late to guarantee the
initialization saw it. The latest balance update separately increases native
direct Phaselock damage by 75%, preserving that initialization fix.
Sampled Ruin logs now distinguish prepared damage from native incoming/health/
shield damage summaries. This timing fix still requires an in-game check.

Scorn scope: the author-defined extra damage scales the orb's slag beams through
ProjectileDamage and its damage area. Native impact explosions have separate
formulas and were not retuned by this curve; Backdraft's additional fire proc
is also separate. The beam-base diagnostic is not a per-hit damage measurement.

Native delivery correction (28 October 2026): caster-specific damage is evaluated
once per behavior use and passed as a positive resolved constant. Ruin is also
prepared at Phaselock entry, before its native event chain, and retains its
original status chance and effect types. Ruin/Scorn initializer seeds stay nonzero
before a caster is available. Historical logs from the previous curve measured
Scorn projectile base 1698.56 and beam incoming 339.712 at stage 90/scaler1.05;
these are different measurements and are not the values of the latest curve.

Class-mod correction (27 October 2026): only the equipped class mod grants
bonus ranks; carried items no longer contribute. Swapping or removing it
invalidates the rank cache immediately. Native description queries already
contain the class-mod bonus in Grade, so it is no longer added a second time.
This fixes Flicker/Accelerate getting stuck at 11/5 and covers the other custom
rank footers, including Backdraft. Balance values are unchanged.

Release maintenance (27 October 2026): native rank refresh only touches the
requesting player's skill instances and defers while the skill manager updates.
Recent logs contain no SDK errors or warnings; the final guards still require
a short allocation/class-mod/respec and menu/re-entry check. Co-op remains
unvalidated, and clean logs are not a frame-time benchmark.

Backdraft update (28 October 2026): melee attacks no longer trigger bonus fire
damage. Scorn's beams keep their completed-hit fire bridge, using normal
Backdraft fire damage with native level/rank/class-mod scaling. The former0.85
fire adjustment has been removed. Scorn's own damage curve does not determine
this separate fire proc's base.

Backdraft's nova and Scorn fire also gain a final damage factor of
`1 + 0.18 * effective rank`, over their native level/grade damage. This replaces
the former1.30 nova increase. At5/5 both effects use the same factor 1.90 over
their respective native damage at that rank; no separate0.85 factor remains.
Class-mod ranks participate once. Inputs are prepared at native behavior entry,
so repeated casts and different casters cannot compound a previous factor.
This hidden scaling adjustment is not added to the in-game description.
Pending configuration for all affected skills is tracked by `_pending_damage_tuning`.

The passive +7% Skill Damage per rank remains (+35% at 5/5), affecting Ruin,
Scorn, Helios and Cloud Kill. The shield-depletion nova keeps its recharge
requirement; its radius is920 game units (native800 plus15%).
It uses skill damage, with no added roid-damage scaling. The original
Backdraft Damage rank footer remains, alongside the Skill Damage percentage.
One scoped nova-entry hook was added; no new HUD icon or damage-pipeline hook.
Restart the game after replacing the package;
melee removal, Scorn fire and the shield nova still need in-game confirmation.

Immolate balance update: its additional hit deals 5% of the final source-hit
damage per effective rank (25% at 5/5). Its trigger and duration are unchanged.

Description maintenance (27 October 2026): custom maximum-rank percentage
highlights include the percent sign. Current/next-rank footers use each query's
rank and class-mod bonus, including Flicker. Native extra stat rows are preserved;
balance values and gameplay effects are unchanged.

Scorn update (27 October 2026): allocating its point passively increases the
duration of your Ignite, Shock, Corrosion and Slag effects on enemies by 50%,
independent of the orb's cooldown. Native applications use a temporary duration
formula scale, restored afterwards; other players and nested calls remain isolated.
Reapplication renews the duration without compounding the bonus. Sustenance still
heals on confirmed applications/refreshes with its shared 0.5-second cooldown.
Its snapshots now filter irrelevant statuses and its heal diagnostics are sampled
every 2 seconds; actual healing is not throttled further. In-game validation is
still required.

Ricochet-path maintenance (27 October 2026): known native bullet hits skip
Scorn-only capture/diagnostic work while preserving the paired hooks. Empty
modifier stacks avoid unnecessary address queries. Stable skill tuning and
Mind's Eye maintenance avoid reflected copies; actual repairs retain owned
structures and native recalculation. Chain Reaction's chance and damage are
unchanged. Offline checks passed; in-game frame-time gains remain unmeasured.

Cloud Kill/status performance maintenance (27 October 2026): received-damage
bonuses now modify only the matching field for known native damage sources.
Unknown/custom sources retain the complete fallback. Cross-source orphan cleanup,
nested damage, status expiry and damage values are preserved. Duplicate elemental
statuses avoid repeated duration checks, and Sustenance snapshots avoid duplicate
property reads. Offline operation counts improved; frame-time gains still need
in-game measurement.

Description maintenance (27 October 2026): Kinetic Reflection removes duplicate
footer rows, Accelerate colors its complete percentage at maximum rank, and
Recompense's next-point preview stays uncolored until the fifth point is allocated.
These changes only affect text formatting.

Kinetic Reflection update (27 October 2026): while its native kill-skill window
is active, it also reduces non-bullet damage by 5% per rank. Its native reduction
against deflected bullets is 10% per rank: at 5/5, 25% general protection and
50% bullet protection. Bullet hits do not receive both factors. Deflection,
reflected damage, kill trigger, duration and HUD behavior remain native. Class
mod ranks are taken from the active skill once; the next-rank description uses
the rank requested by the skill tree. In-game validation is still required.

Performance maintenance (27 October 2026): Immolate checks its current native
graph before copying reflected structures. An already-correct graph avoids
those copies; changed fields still follow the full repair path. This reduces
repeated setup work on Phaselock without changing its damage or timing.
In-game frame-time improvement has not yet been measured.

Psychic Shriek update (27 October 2026): its target takes 15% more damage and
nearby enemies still deal 20% less damage, for 8 gameplay seconds. Its Phaselock
duration bonus is now 2 seconds. The duration change updates existing native
effect snapshots without reactivating the gameplay skill.

A native HUD indicator uses Psychic Shriek's skill-tree icon during its debuff
window. It shares the dynamic logical/physical slot allocator with Immolate,
Res and Recompense, replacing the obsolete charm feedback. It follows gameplay
time and normal HUD visibility, without drawing on the pause menu. A full row
leaves other indicators intact and retries when space is available; the native
11-slot capacity is preserved. No canvas fallback or fixed screen position.

Crash fix (27 October 2026): Psychic Shriek resolves its current native skill
definition for each rank query instead of retaining an unrooted UObject across
menu/map garbage collection. Both the charm decision and active-debuff validation
use the fresh lookup. The Converge radius asset is also resolved for each pulse,
so it cannot retain the same kind of expired reference after a menu reload.
Unloaded rank definitions skip the effect until available; a missing area asset
still leaves the primary-target debuff intact and reports the missing area.
This fixes the stale-reference path identified in the 08:06 crash dump; a new
menu/reload/cast test in game is still required. No balance values changed.

Maintenance (27 October 2026): Scorn explicitly validates its resolved designer
attribute before use. Psychic Shriek's primary debuff survives unavailable area
assets or individual neighbor failures; expired mark history is retired even on
unrelated hits. Area-only records cannot evict active primary vulnerabilities.
Received-damage scopes reject non-finite native readbacks and skip deleted targets
before resolving their controllers. Balance values are unchanged. Co-op remains
unvalidated, including mark ownership when two Mayas target the same enemy.

Tooltip update: Thoughtlock is displayed as **Psychic Shriek**, retaining its
internal identity. The opening "Action Skill Alteration" label was removed.
Enemy damage dealt (-20%) and damage taken by the target (+15%) appear in
the lower stat block, alongside the native duration line, now +2 seconds.

Runtime fixes: an unloaded received-damage attribute now uses a cached private
property resolver without changing the shared bullet attribute. The area trace
now passes a zero vector extent and a separate boolean using the native API's
four-argument signature. These fixes address the two errors in the latest log;
verify nearby debuffs and actual damage in game after updating with BL2 closed.

Elemental Mastery (26 October 2026) replaces Slagger in the same one-point
Cataclysm slot and keeps its private skill identity for saved allocations. Each
distinct active Ignite, Shock, Corrosion or Slag on the target grants 7.5% more
damage from Maya, up to 30% with all four. Repeated effects of the same type
count once; class mods do not increase the bonus. Native slag multipliers remain
unchanged. These changes pass focused offline checks; verify them in game after
installing with BL2 closed.

Healing tooltip fix (26 October 2026): Elated and Sustenance format the current
rank and next-point preview independently using the menu query's grade and class
mod bonus. Shared presentation refreshes no longer replace the current value
with the next rank. Healing amounts and gameplay behavior are unchanged.

Balance update (26 October 2026): Accelerate grants +4% gun damage per rank
(+20% at rank 5), retaining +5% bullet speed per rank. Recompense grants 5%
avoidance per effective rank (+25% at rank 5), with a 3-second cooldown. Res
recharges in 120 gameplay seconds and resets on full character death. Entering
FFYL, an ordinary Second Wind, a respec or a map/pawn change alone does not reset
it. Descriptions and rank previews reflect these values; in-game testing remains
necessary after replacing the package with BL2 closed.

Thoughtlock rework (updated 27 October 2026): Phaselock lifts ordinary targets instead
of charming them. Its primary target takes 15% more damage from Maya and her
allies, including when the target is immune to lifting. Nearby enemies deal 20%
less damage. Both debuffs last 8 gameplay seconds and use Converge's native
radius (normally 2,000 game units), with line-of-sight checks for nearby enemies.
Converge does not need an invested point. Reapplying refreshes the duration
without stacking; an area-only refresh does not extend an older primary-target
vulnerability. Its own Phaselock duration bonus is +2 seconds. The old enemy damage,
aggro and critical-damage effects are removed. Vulnerability multiplies with
Elemental Mastery through one temporary received-damage scope, and Immolate
inherits the combined bonus once. Verify lifting, immune targets, damage and
expiration in game after replacing the package with BL2 closed.

Release audit (26 October 2026): Backdraft's Scorn bridge requires a valid
invested rank before reporting a missing damage context or forwarding fire
damage. Removing its point during a respec also rejects stale active instances.
Quicken maintenance compares cached formula inputs, leaving the engine's
transient modifier output alone, and defers while the skill manager is updating.
Balance values are unchanged. The startup log identifies this maintenance build
with `allocation guards; Quicken input-only maintenance; release audit 2026-10-26`.
Offline regressions pass; this updated build still needs an in-game retest.

Rebalances Maya's Borderlands 2 skills with new synergies, healing/damage/cooldown
adjustments and native HUD indicators. Version 1.0 is prepared for final testing;
the version number does not certify multiplayer or every integration scenario.

Maintenance fix: ammo eligibility, Sustenance status observation and the combat
HUD check the player's class before looking up Maya skills. Other characters
keep their normal behavior without missing-Siren-asset warnings. The startup log
identifies this build with `character-scoped ammo/status/HUD hooks`. Balance values
and the version number remain unchanged; in-game confirmation is still required.

HUD maintenance: Res, Recompense and Immolate allocate logical skill slots and
physical icon positions separately. Their icons fill available positions without
moving other skills or restarting gameplay timers. The startup log includes
`separate logical/physical HUD slots`. Verify all three indicators together with
the other purchased skills after upgrading and after a respec.


## Lifecycle and timing research



- **Disabling takes effect after restarting the game process.** The menu shows
  `Disabling on Restart`. The current session keeps both native edits and their
  runtime hooks active, so disabling cannot leave half-patched skills behind.
- Re-enabling before exit cancels the request without registering duplicate
  hooks. Do not hot-reload, deregister or replace this mod during gameplay.
- Skill effects/stat text are synchronized at most every 0.25 s, with immediate
  invalidation for a new controller/pawn/world. Native HUD polling uses the same
  interval. This is not a measured FPS claim.
- Immolate, Res and Recompense use native HUD feedback only; no fixed-position
  canvas fallback. Each visual clones its loaded parent skill with gameplay
  fields cleared, without requiring the optional vanilla Recompense_Feedback.
- Native HUD polling is skipped while the pause menu is
  open or the world is paused. This does not reset timers or deactivate buffs;
  missing Immolate registration is retried using only the remaining buff time.
- Phaselock's cached duration uses GetWillowPlayerPawn, not the vehicle Pawn
  while driving. Missing/deleting character pawns are skipped until ready.
- Elated uses gameplay DeltaTime and pauses with the world. Res retains its
  gameplay cooldown. Immolate, Recompense and Sustenance retain their previous
  real-time windows/deadlines; pausing does not extend those timers.
- Recompense has independent player/save cooldowns, not one shared deadline.
- Blight Phoenix prepares ShotCost in PRE, confirms native execution in POST
  and cleans up in POST_UNCONDITIONAL, including when another mod cancels fire.
  It does not execute a shot early inside PRE. Other firing mods still need
  integration testing; universal compatibility is not claimed.


## Immolate investigation and native graph references

The investigation below retains the reasoning and failed approaches. Its
acceptance percentages have been updated to the current 5% per-rank rule.
Do not restore obsolete manual event bridges from this history.



The last bridge revision prepared the provider but still did not deliver a
`ShotEnemy` event. Earlier revisions had emptied `DamageEvents`, which disabled
the original engine route, and manually deactivated/recreated the passive for
each window. Both changes have now been removed. The game handles source
constraints, original health/shield damage, grade calculations, and the extra
incendiary hit; Python controls the sequence's activation state and normalizes
the extra hit's final damage as described below.

The previous `native_active=True` log proved only activation. The later
`NotifySkillDamagedEvent` log proved only that the Python bridge called that
notification method. It did not prove that the `ShotEnemy` behavior event ran.
The claim that a runtime passive was missing from an internal damage-consumer
list was a hypothesis, not a demonstrated engine limitation. Event type 25 is
`SEVT_DamagedUnawareEnemy`; type 4 is the normal `SEVT_DamagedEnemy` notification.

The original passive receives `ShotEnemy` from the game. Its FFYL comparison is
bypassed using the same output-link change as
[Elemental Banshee Maya](https://github.com/BLCM/BLCMods/blob/master/Borderlands%202%20mods/55tumbl/Elemental%20Banshee%20Maya/ElementalBansheeMaya.blcm#L310-L318).
The native event structures and method signatures were checked against
[McSimp's SDK headers](https://github.com/McSimp/Borderlands2SDK/tree/master/src/GameSDK).
Sequence enable/disable states (1/2) were cross-checked against the real
[Loot Randomizer implementation](https://github.com/mopioid/Borderlands-Loot-Randomizer/blob/master/LootRandomizer/Mod/bl2/locations.py).
Kernel calls use named arguments because the reflected signatures differ from
the generated C++ wrapper order. Native calls with out/ref parameters return
tuples in the modern SDK; the gate checks the actual boolean at index zero,
not the truthiness of the whole tuple.

After native activation started working, the extra hit was still reduced by
another damage-pipeline pass. The
[Skill Scaling Patch](https://github.com/BLCM/BLCMods/blob/master/Borderlands%202%20mods/55tumbl/Skill%20Scaling%20Patch/SkillScalingPatch.blcm#L97-L106)
documents Immolate's duplicate OP-level penalty. This mod's requested rule is
stricter: at rank 5, a final 1,000-damage gun hit must add exactly 250 damage,
including on shields, regardless of a second elemental/level multiplier.
The resolved constant from the native Immolate graph supplies this amount.
While that specific `Behavior_CauseDamage_113` executes, a guarded pre-hook wraps
its first local-player incendiary `WillowDamagePipeline.AdjustDamage` call,
executes the native body once, and returns a corrected damage summary. Shield
damage is allocated before health; a pool already consumed by the calculation
is reconciled, otherwise the normal handler applies the summary. An
unconditional post-hook clears the scope, including blocked calls. Nested procs,
other skills, ordinary incendiary shots, and status-effect pipelines are excluded.
Using a pre-hook matters: modern PythonSDK discards post-hook return overrides.

The additional coefficient fix follows the documented
[BPD input-variable behavior](https://github.com/BLCM/BLCMods/wiki/BPD-classroom#unlinking-variables):
a linked input can overwrite a field every time a behavior runs.

Offline checks (the relevant Immolate tests under `../Suporte/`, selected for the change being tested) exercise the native
graph's original packed links with the edited coefficient, effective ranks 1/5/11,
the restored native constraints, sequence activation/expiry without deactivating
the passive, zero rank/damage, SDK out-parameter returns, final fractions after
reductions/boosts, shield overflow, and nested-scope cleanup. They do not run the
game engine or prove in-game damage delivery.

Restart the game completely. Test in solo play with a non-elemental, single-pellet
weapon, no class mod, no amp shield, and no other on-hit skills. Shoot the same
kind of living enemy in the body before Phaselock, during the window, and after
12 seconds. At rank 5, the final extra incendiary hit should equal 25% of the
original final health plus shield damage. Its own elemental resistance,
vulnerability, and level multipliers must not reduce or amplify that fraction.
Repeat at rank 1 (5%) and rank 0 (no extra hit); melee and DoT ticks should not
trigger Immolate. Test FFYL without a Phaselock window to check that its old
trigger is gone.

Expected diagnostics are `Restored native Immolate Bullet/Rocket DamageEvents`,
`Immolate native damage gate: enabled=True` on Phaselock and `enabled=False` on
expiry, and `Behavior_CauseDamage_113` with the runtime damage constant/scale and
incendiary damage type on the first qualifying hit. The former bridge's
`Immolate emitted ShotEnemy` diagnostic no longer exists. The in-game damage
numbers remain the acceptance criterion.
The additional `Immolate final damage` line reports `Expected`,
`NativeBeforeCorrection`, `FinalHealth`, and `FinalShield` once per window.
`FinalHealth + FinalShield` should equal `Expected`, including for critical hits.

