# Changelog

## 1.0 - Immolate follow-up review, 28 October 2026

- User solo tests and three sampled SDK summaries confirm independent fire
  delivery with final damage matching the expected values; no SDK errors were
  found in the reviewed session. Shield overflow and co-op remain unverified.
- Hardened post-native correction failures against replaying the calculation;
  guarded logging and teardown paths. Balance, duration and HUD are unchanged.
- Updated startup diagnostic, knowledge guide and validation evidence; 53
  targeted offline tests passed. Follow-up guards await in-game exercise.

## 1.0 - independent Immolate delivery, 28 October 2026

- Replaced the former native-graph bypass with a post-hit dispatcher using the
  game's pooled damage pipeline. No output links or SimpleMath bindings are
  edited; legacy native delivery is suppressed to prevent duplicate damage.
- Retains 5% final source damage per rank, the 12-second Phaselock window and
  existing native HUD. Dedicated scope guards prevent recursion, duplicate
  damage modifiers and stale-world access. In-game validation pending.
- A verified pre-change backup is retained in the development workspace.

## 1.0 - release preparation, 28 October 2026

This is the current version label, not a claim that publication or co-op testing
has been completed. The README is the current balance summary. Older entries
below document development snapshots and may contain superseded values.

- Ruin: linear extra damage +15% to +190% from stage 1 to stage 90.
- Scorn: +25% to +235% across the same stages; beam/area scope retained.
- Helios: +15% to +125%; replaces the earlier flat increase while preserving
  its native rank-sensitive calculation and global level scaling.
- Phaselock: direct-damage scale configured to 1.75 with native linked inputs
  preserved. The exact increase against other mod configurations is not verified.
- Backdraft: removes melee fire; retains shield-break nova and Scorn fire,
  +7% Skill Damage per rank and radius 920. Both fire paths use native baseline
  damage with an additional factor `1 + 0.18 * effective rank`. Removed 0.85.
- Renamed the pending damage group to `_pending_damage_tuning`.
- Documentation split into README, CHANGELOG, DEVELOPMENT and LICENSE; retained
  Immolate graph adaptation explicitly identified. Own contributions reserved.

## 1.0 - preceding balance and maintenance notes

The following snapshot was recorded before this documentation split. Later
entries above and the current README take precedence.



Scorn/HUD correction (23 October 2026): the menu's lower Scorn line explicitly
shows its **12 s base**, preserving the original upper description. Quicken
still adds 10% cooldown rate per rank: expected recharge is 8 s at rank 5
without other modifiers, not a 50% linear reduction. Maintenance now updates
the live designer attribute and recalculates a stale resource-pool base, rather
than only editing the definition. Cooldown progress is retained during repair.

Immolate no longer forces slot 0 (Elated's native position). Immolate, Res and
Recompense share a free-slot allocator that checks learned native skills,
their feedback children, registered/remapped slots and occupied icon caches.
Only custom feedback entries move; no Canvas fallback or changes to native
skill positions. An exhausted native cache suppresses our visual with a
diagnostic instead of overwriting another icon; it does not stop the buff.
These corrections pass offline regression tests; in-game validation is pending.

- Sustenance: every confirmed enemy status application heals 3% max health per
  effective rank, with a 0.5 s ICD. All four statuses, including slag; no DoT-tick
  trigger, chance roll or native passive regeneration.
- Recompense: 5% avoidance per effective rank, 3 s cooldown; non-positive input
  damage does not roll or consume it. Original retaliation/feedback disabled.
- Quicken: +10% cooldown rate per rank. Scorn base is 12 s, or 8 s at Quicken 5
  with no other cooldown modifiers. Phaselock base remains 7 s.
- Blight Phoenix: native kill-skill trigger/duration, 8% ammo-saving chance and
  +5% movement speed per rank. Fire/shock/corrosive/slag guns only, no pure
  explosive. Original aura disabled. Lower label: `Chance to not consume ammo`.
- Life Tap is unchanged by the current mod. Flicker adds direct elemental damage,
  not the old status-damage implementation described in historical notes.

The workspace knowledge guide and TESTES.md contain the full current skill map,
evidence and exact acceptance tests. Changes in this workspace do not update an
installed .sdkmod automatically. Close the game before replacing the package.

Offline checks: run only the relevant tests in `Suporte` and adjacent integration
checks for the changed code, plus syntax and Python 3.14 grammar validation.
Mocks do not certify native HUD, crashes, remote clients or every weapon.


## Historical development snapshots

These are preserved development records, not current installation instructions
or a promise that every listed experiment remains in the code. In particular,
old Immolate 4%/20% values, Canvas HUD attempts, former Sweet Release critical
healing and Life Tap duration experiments do not describe the current release.


The material below is retained as history. Its superseded values, Life Tap,
critical-hit healing and activation strategies must not be restored by copying
these notes into the current implementation.

### Version 0.3.9

Implemented:

- Sweet Release: after a critical hit, rolls a 3% chance per invested rank and heals 4% of maximum health per rank.
- Recompense: rolls a 3% chance per invested rank to block incoming damage, with a 2.5-second cooldown after a successful proc.
- Immolate uses a 12-second native tracked-skill HUD indicator with the same icon as its skill-tree entry. Recompense keeps its cooldown indicator; the former canvas icon for Immolate remains as a fallback until the native HUD actually caches the icon.
- Skill stat lines show the next-rank value only while the player can manually invest another point (up to 5/5); at 5/5 they show the current effective value, including class-mod ranks.
- For an uninvested skill, the next-rank preview includes eligible class-mod ranks that will activate when its first point is invested.
- Numeric stat values use the game's default orange color until the skill reaches
  5/5 base ranks, then turn green.
- Skill stat lines refresh when the front-end movie starts and when a skill's effective rank changes. They account for up to 6 ranks from equipped class mods, for a maximum effective rank of 11, and only count class-mod ranks when at least one point is invested in the skill.
- Mod-managed skill behavior and stat-line calculations use the effective rank, including eligible class-mod bonuses.
- Changes to class-mod ranks trigger reactivation of the modified skill effect at the new effective rank.
- Class-mod rank scanning collects bonuses for every Maya skill in one inventory pass.
- Numeric skill tuning is checked repeatedly and reapplied if the game resets a skill definition after a respec or asset reload.
- Skill text is also updated on the computed `GetSkillEffectPresentations` result used by the game UI.
- Skill descriptions and stat lines are checked once per second and restored if the game overwrites them, without rewriting text that is already correct.
- Flicker grants +10% status-effect chance and +6% direct elemental damage per rank.
- Elemental Mastery is a one-point skill on Cataclysm's fourth tier, to the right
  of Reaper. It uses the existing Sphere icon and grants 7.5% more damage from
  Maya for each distinct active Ignite, Shock, Corrosion or Slag on the target
  (maximum 30%). Class mods do not increase this bonus. Native slag behavior and
  other players' damage are preserved. The private skill definition, internally
  named MR_Slagger for compatibility,
  is recreated before skill-tree initialization; the original Sphere prototype
  and its input action are unchanged. Test saving/reloading the invested point
  after installing this update. No additional combat HUD slot is allocated.
  The latest maintenance fix removes an invalid SkillDefinition field and
  prepares the skill using Maya's actual streamed tree path. It also fixes the
  same invalid field in Wreck's passive half. Restart the game completely when
  replacing the package; the startup log identifies `native tree/schema fix`.
- Accelerate grants +5% weapon damage and +5% bullet speed per rank.
- Wreck grants +5% fire rate and +3% gun damage per rank at all times. These
  bonuses double while an enemy is Phaselocked: +25%/+15% at rank 5 normally,
  +50%/+30% during Phaselock. The passive half has no additional HUD icon; the
  original conditional half keeps its native icon, weapon contexts and constraints.
  Its native activation/deactivation is owned by the game. Maintenance patches
  cached inputs without recreating Wreck, including when its instance is paused
  or absent from the active list. Companion grade changes update in place, and
  deferred companion activation is requested only once per player/pawn/manager/rank.
- Suspension increases Phaselock duration by 0.7 seconds per rank.
  Version 0.3.11 also updates `Skill.SkillEffects[].EffectData`, the native
  snapshot used by skills already learned when tuning runs. It requests
  `bForceRefreshModifiersNextTick` so the engine recalculates the existing
  modifiers and contexts at the current grade, without manually reactivating
  Suspension. This preserves class-mod rank handling and avoids leaving the
  cached vanilla 0.5-second effect active after editing the definition.
- Phaselock's base duration is 7 seconds. Entering Fight For Your Life no
  longer ends a Phaselock that is already active; its normal duration keeps
  running, while activation from FFYL remains unavailable. The mod validates
  duration definition and calls `SetBaseValue` on the pawn's cached
  `InstancedDesignerAttribute` before Phaselock starts and after streaming.
  Suspension remains a separate 0.7-second bonus per effective rank. The
  immune-target delay and active health constraint are also validated.

  Confirmed against the BL2 datapack distributed by
  [OpenBLCMM-Data](https://github.com/BLCM/OpenBLCMM-Data):
  `DesignerAttributeDefinition.dump.1` gives `Att_Phaselock_Duration` a vanilla
  base of **5**, not zero. `LiftActionSkill.dump.1` shows that
  `ActionSkill_Phaselock.LockDurationFormula.BaseValueAttribute` references
  this definition. Changing only the definition does not refresh existing
  pawn instances. The previous zero-base/+2-modifier implementation was based
  on an incorrect interpretation and has been removed. Runtime diagnostics
  now report `pawn_base`, `pawn_total`, `SkillDuration`, and `StateDuration`.
  Test on a fresh normal enemy without shooting: expect 7 seconds with no
  Suspension, or 10.5 seconds with Suspension 5/5 and no class mod/Thoughtlock.
  Repeated locks on the same enemy can still receive vanilla diminishing returns.
- Restoration increases maximum health by 4% per rank.
- Life Tap's active effect is extended to 12 seconds when its active-skill instance exposes a duration property. Its damage-to-health conversion rate is shown in the skill UI from the skill's live effect values.
- Skill asset loading is retried so tuning can be applied when the Maya skill data becomes available.
- Life Tap's skill description includes its 12-second duration.
- Scorn's cooldown is set to 8 seconds through its `Cooldown_Scorn` designer attribute.
- Elated regenerates 1% of maximum health per effective rank per second, doubled while Phaselock is active.
- Immolate's implementation uses its native separate incendiary-hit graph at
  4% of final gun-hit damage per effective rank during the 12-second Phaselock
  window. Its final health plus shield damage is normalized after the extra
  hit's native calculation, so level, slag, critical, and elemental modifiers
  are not applied a second time. Its incendiary impact type is retained;
  ordinary gun hits and DoT calculations are untouched. The original
  `DamageEvents` entry (`SDE_DamagedEnemy`, Bullet/Rocket, `ShotEnemy`) is restored.
  The passive stays naturally active through the skill tree; Phaselock enables
  only its damage sequence for 12 seconds, then disables that sequence. There is
  no manual damage-event forwarding or per-window skill activation/deactivation.
  The sequence starts disabled and the original FFYL comparison is bypassed.
  Its edited provider is initialized on the native active skill consumer.
  The coefficient's old BPD input is disconnected while the
  native Grade input and Result output are retained, so the kernel cannot
  overwrite 4% with its embedded 10% value. This revision needs in-game validation.
- Immolate's visual-only feedback skill follows the game's Recompense feedback pattern: it is tracked as a triggered skill, uses Immolate's own `SkillIcon`, and ends with the 12-second Phaselock window. It has no damage effects or behavior graph. Recompense's existing 2.5-second cooldown icon is unchanged.
- For the HUD test, invest at least one point in Immolate and activate Phaselock. The native Immolate icon should appear with the game's other tracked-skill icons for 12 seconds, then disappear; repeated Phaselocks should restart its timer. Check for `Activated native Immolate HUD icon` in the log. If the native HUD does not cache the icon, the previous canvas icon remains visible during the buff.
- Immolate's rank-scaled incendiary damage and duration are included in its description and lower skill stat presentation.
- Scorn, Elated, and Immolate have updated skill descriptions and rank-aware stat lines, including class-mod ranks up to 11.

Version 0.3.2 fixes Scorn's cooldown by tuning the actual designer attribute, replaces Immolate's damage multiplier with an additional hit during the Phaselock window, and monitors Life Tap's active-skill instance to apply its requested duration. Version 0.3.3 makes Immolate's extra hit explicitly Incendiary and fixes HUD icon lookup. Version 0.3.4 corrects the TakeDamage field used for the Incendiary type and preserves Immolate's native rank effect definition while keeping the native skill inactive. Version 0.3.5 included a custom HUD renderer and damage-hook diagnostics. Version 0.3.6 removes the broken HUD renderer, resolves the player controller from the instigating pawn, ignores zero-damage events, and creates the separate incendiary hit with the game's `Behavior_CauseRadiusDamage` call. Version 0.3.7 removes the nonexistent class lookup and duplicated description values. Version 0.3.8 removes the broken manual damage hook and ports the native behavior-link setup. Earlier Immolate revisions manually activated its passive during the 12-second Phaselock window. The current revision instead keeps the original passive registered and changes only the native sequence activation state. Version 0.3.9 adds gray skill-icon indicators for Immolate's 12-second effect and Recompense's cooldown, arranged side-by-side when both are active. Restart the game before testing the HUD or Immolate. Life Tap duration depends on the runtime active-skill instance exposing a supported duration field; if the log reports that it does not, the native duration remains unchanged.

Other requested skill reworks remain deferred.


## Earlier 0.2.9-0.3.8 chronology

The 0.2.9 log confirmed that the game kept rebuilding skill presentation text, and code inspection found that class-mod scanning cached only the first skill queried. Version 0.2.10 updates the computed presentation result and collects class-mod bonuses for all listed skills. Version 0.2.11 fixes the periodic validation condition so descriptions overwritten by the game are restored instead of being skipped. Version 0.3.0 added the Scorn, Elated, and Immolate reworks; version 0.3.1 adjusted Elated and attempted to manage Immolate's activation. Version 0.3.2 replaces Immolate's damage multiplier with an additional hit and applies Scorn's cooldown to the actual designer attribute. Version 0.3.3 makes Immolate's extra hit specifically incendiary and fixes the HUD icon path lookup. Version 0.3.4 fixes the damage-type field and keeps Immolate's UI effect definition while preventing the native skill effect from applying slag damage. Version 0.3.5 added the custom HUD renderer and damage-hook diagnostics; version 0.3.6 removes the broken overlay and fixes the damage-event path and incendiary type arguments; version 0.3.7 removes the nonexistent class lookup and duplicated description values; version 0.3.8 uses the native Immolate skill effect in a timed Phaselock window rather than injecting an extra TakeDamage call. Verify in game after restarting.

