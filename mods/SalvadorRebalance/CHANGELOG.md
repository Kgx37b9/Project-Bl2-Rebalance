# Changelog

## 1.0.1 - Sexual Tyrannosaurus description, 10 November 2026

- Correct the Fire Rate penalty sign: explicitly prefix the displayed number with a minus sign and suppress the native plus sign. Keep native inverse magnitude formatting. At 5/5 the intended line is Fire Rate: -15%.
- Gameplay remains unchanged: both weapon fire-interval modifiers still impose 3% per rank. Six focused checks passed; restart to verify native rendering.

## 1.0.0 - Release preparation, 10 November 2026

- Reduce Fistful of Hurt's owner-only damage vulnerability from 15% to 10%. Preserve its 8-second duration, refresh rules, native punch and self-shock. The lower description uses the gameplay constant.
- Bound stable native HUD allocation to one full scan per second per indicator. Lost icons, changed movies, remaps and conflicting registrations trigger immediate recovery. Preserve independent visual/gameplay helpers and reserve inactive children and their physical remaps.
- Recover native skills/controllers/managers through weak references after callbacks. Discard incoming ActiveSkills views after native rebuilds or stale Rough Rider cleanup; do not continue reading potentially invalid helper instances. Reconciliation resumes from a fresh maintenance pass.
- Preserve the existing one-second skill-maintenance gate, short Asbestos visual retry, conditional writes, both-hand behavior and nonlethal Berzerk cost. No new hooks, global actor searches or gameplay polling loops.
- Prepare release metadata, README and technical notes. Correct the duplicated Get Some entry and the stale Hard to Kill class-mod example (10 effective ranks = 40% maximum health).
- Validation: 150 focused/adjacent offline checks passed; 18 HUD rechecks passed after physical-slot reservation was strengthened. No package was generated or installed. Final fresh-process solo confirmation and co-op remain pending.

## 0.1.41 - Berzerk, Quick Draw and Bus placement, 8 November 2026

- Reduce Berzerk Amp Damage from +100% to +85% on both guns. The footer follows the gameplay constant; health cost, resistance and shield behavior remain unchanged.
- Increase Quick Draw Weapon Swap Speed from 7% to 10% per effective rank, preserving its 4% Critical Hit Damage per rank and native presentations.
- Move Bus That Can't Slow Down from Brawn tier 4, left, into tier 2, center, between Asbestos and I'm the Juggernaut. Leave its former cell empty and preserve Just Got Real's center column, all other skills and unlock costs. No exchange with another skill.
- Prepare placement before native tree initialization, reject conflicting layouts and avoid repeated array writes in stable maintenance. Fully restart after updating. Thirteen targeted/adjacent offline checks passed; native rendering/gameplay and co-op remain unvalidated.

## 0.1.40 - Restore authorized Berzerk bonus, 8 November 2026

- Restore BERZERK_GUN_BONUS to 1.0 (+100% Amp Damage), matching the 0.1.32 balance decision to reduce the previous +125%. The 0.1.39 review incorrectly treated the stale +75% source value as the intended balance.
- Keep the footer derived from the gameplay constant and align README/manager text to +100%. Preserve resistance and the 20% current-health cost.
- The relevant regression run also found the previously documented <=1 HP no-write guard missing. Restore that guard to avoid redundant SetHealth calls at the nonlethal floor, without changing the cost or minimum health.
- All 19 Berzerk checks passed across the focused run and corrected guard rerun. Native gameplay validation remains pending.

## 0.1.39 - Fistful of Hurt self-shock and Berzerk text, 8 November 2026

- Apply native Shock to Salvador on Fistful of Hurt activation, even on a miss. Keep the original punch and existing enemy vulnerability. Use native Shock duration/resistances and minimal base status damage of 1; native immunity can still prevent application. Accepted applications can trigger Asbestos.
- Append one player-targeted native behavior to the activation event, preserving original links and opaque variable payload. No new Python gameplay hook or polling; stable configuration does not grow the graph.
- Derive Berzerk footer values from gameplay constants instead of literals. Current source already uses +75% Amp Damage; correct the outdated +100% README/manager text without changing that gameplay coefficient.
- Twenty-seven relevant/adjacent offline checks passed. Native self-status application, audio lifecycle and Asbestos activation require an in-game test after a full restart; co-op remains unvalidated.

## 0.1.38 - Hard to Kill health and resistance, 8 November 2026

- Reduce maximum health from 6% to 4% per effective rank and add 4% native Damage Resistance per rank. Preserve Rough Rider health ordering, class-mod scaling and removal of health regeneration.
- Use nine native impact/status damage-modifier channels; no per-hit hook. Native resistance has diminishing returns: the nominal 20% at 5/5 means about 16.7% damage reduction by itself.
- Preserve the native health stat and add a ranked resistance line using existing current/preview colors. Rebuild live effect bindings once when the added attributes are missing, without changing the skill rank or timer; stable passes do not resend unchanged modifiers.
- Thirty-one relevant/adjacent offline checks passed. In-game confirmation and co-op validation remain pending. Fistful of Hurt status application was researched only and is unchanged.

## 0.1.37 - Just Got Real and Keep It Piping Hot, 8 November 2026

- Just Got Real: increase the gun-damage coefficient from 10% to 12% per effective rank. Preserve the native continuous missing-health calculation and both-hand support; no new health threshold.
- Keep It Piping Hot: increase Gun Damage and Accuracy per stack from 0.1% to 0.14% per effective rank. At 5/5: +0.7% each per stack, up to +35% each at 50 stacks. Preserve generation, cap, duration, HUD, class-mod ranks and reset conditions.
- Seven focused numerical, live-refresh, off-hand and footer/color checks passed. No new hooks or polling; final native gameplay confirmation remains pending.

## 0.1.36 - Asbestos fire-rate rework, 8 November 2026

- Replace ammo-free gunfire with +3% Fire Rate per effective rank for a fixed 10 seconds after an accepted elemental status application. Reapplications renew the window; bonuses do not stack. Preserve the original elemental duration resistance.
- Apply native timed fire-interval modifiers to both guns, independently of the existing HUD visual. Preserve free-slot allocation. Remove the former Asbestos firing/ammo-consumption hooks and refunds.
- Class-mod points scale Fire Rate once; duration remains 10 seconds at every rank. Divergent Likeness is unchanged. Engine confirmation requires a fresh-process gameplay test; co-op remains unvalidated.

## 0.1.35 - Get Some configuration restored, 8 November 2026

- Restore missing Get Some configuration and register it with existing maintenance. The skill footer and active cooldown effect again use 0.8 seconds per effective rank (4 seconds at 5/5), as intended in 0.1.32. Preserve the native shot trigger and 3-second window.
- Keep native presentation, rank/COM handling and live effect refresh; add no hooks or polling. Four focused offline checks passed; native timing still requires gameplay confirmation after restart.

## 0.1.34 - Hard to Kill / Rough Rider, 8 November 2026

- Restore native Rough Rider health ordering: Hard to Kill's 6% maximum health per rank also scales the shield's flat health contribution. Remove the live PreAdd-to-PostAdd migration introduced in 0.1.23.
- Preserve local equipment-slot tracking and cleanup of known shield-slot effects left active after unequipping. No shared shield definition or total-health baseline changes.
- Twenty-six relevant/adjacent offline checks passed, including repeated equip/removal, class-mod rank changes, native unequip and lifecycle guards. Engine confirmation requires a full restart; co-op remains unvalidated.

## 0.1.33 - Yippee Ki Yay critical hits

- Preserve the kill extension; critical hits add 0.3 seconds of Gunzerking per effective rank, including class-mod points.
- Both hands and pellets share a 0.5-second internal cooldown, reset on action lifecycle changes. The cooldown is omitted from the in-game description.
- Add a critical-extension footer while retaining the original kill stat.
- Five focused tests and two adjacent lifecycle tests passed; gameplay confirmation remains pending.

## 0.1.32 - Get Some and Berzerk balance

- Adjusted Get Some from 0.9 to 0.8 seconds of Gunzerking cooldown reduction per effective rank, about 33% above its original 0.6 seconds. Its native hit trigger and active duration are unchanged.
- Reduced Berzerk's fixed Amp Damage on both guns from +125% to +100%. Health cost, damage resistance and shield behavior are unchanged.
- The two focused Get Some tests and 18 focused Berzerk tests pass offline; the new values still need in-game confirmation.

## 0.1.31 - Get Some cooldown

- Increased Get Some's cooldown reduction by 50%, from 0.6 to 0.9 seconds per effective rank. Both the native timed cooldown effect and its skill-tree value are updated. The hit trigger and active duration remain unchanged.
- Focused offline tests cover the effective-rank attribute, display value, idempotent configuration and streamed-asset retry. In-game timing remains to be checked.

## 0.1.30 - Berzerk nonlethal floor

- The per-shot health cost stops at 1 HP and skips SetHealth completely when health is already 1 HP or lower. This avoids a redundant native health write at the floor. Damage, resistance, shield behavior and cost rate are unchanged.
- All 18 focused Berzerk tests passed, including low-health shots; gameplay confirmation remains pending.


## 0.1.29 - Sexual Tyrannosaurus footer

- Corrects the native Fire Rate footer to show a negative percentage for its Gunzerking penalty. The effect values and all gameplay behavior are unchanged.

## 0.1.28 - Berzerk damage

- Increases Berzerk's fixed Amp Damage bonus on both guns from +75% to +125%. Health cost, native resistance, shield regeneration block and all other effects remain unchanged.

## 0.1.27 - Stability and repeated-work audit

- Asbestos rejects enemy/world status applications before local-player and skill-manager lookups. Bursts still refresh the gameplay deadline immediately, while visual updates share the existing100ms HUD retry interval.
- Fistful of Hurt skips unmarked targets before controller lookups and scope allocation, preserving temporary-modifier cleanup for nested damage.
- All in the Reflexes skips reload-end/unequip cleanup when no owned reload modifier is tracked.
- Rough Rider orphan cleanup deactivates each definition only once per pass. Its snapshot inspection now runs before Piping Hot can deactivate helpers contained in that snapshot.
- Clears pending reload identities on enable. No skill values, durations or damage formulas changed.
- Validation:81 targeted/adjacent tests passed; current SDK log contained no SalvadorRebalance error lines. No FPS gain or co-op result is asserted without gameplay testing.

## 0.1.26 - Restore native Double Your Fun

- Removes the entire Double Your Fun rework: grenade-regeneration effect, configuration, cached-effect migration branches and custom footer hook. The mod no longer loads or writes this skill.
- After a full game restart, the original skill description, double-grenade behavior and native graph remain intact. Updating in a running game cannot restore definitions already changed by an older version.
- Current README and Mod Manager summary no longer advertise grenade regeneration. Historical entries below describe older versions only.

## 0.1.25 - No Kill Like Overkill description

- Clarifies the skill description and current public summaries: maximum bonus is +200%, reduced from the native +400% cap. Removes the confusing50% wording.
- Text-only correction; the existing0.5 final-bonus scaling, timing and both-hand behavior remain unchanged.

## 0.1.24 - Description cleanup and Berzerk cost

- Auto-Loader upper prose no longer repeats its percentage. The footer now displays Reload Speed: +15%, without exposing the negative native reload-time coefficient; gameplay remains unchanged.
- Fistful of Hurt upper prose no longer contains the15% vulnerability amount. Adds Damage Taken from You: +15% to the lower stat block, preserving native punch stats and the eight-second duration.
- Fixed one-point footer bonuses turn green only when learned; previews remain uncolored.
- Berzerk now costs20% of current health per executed gun shot instead of15%. Its upper prose remains non-numerical; the footer follows the cost constant. Damage, resistance and the nonlethal floor remain unchanged.
- Validation:37 focused tests passed (Auto-Loader3, fixed footers1, Berzerk18, Fistful of Hurt15). Native UI rendering still requires gameplay confirmation.

## 0.1.23 - Rough Rider health ordering

- On the local Salvador, moves the live Rough Rider flat-health modifier from PreAdd to PostAdd. Percentage health bonuses apply to the character base, then the shield health is added. Keeps the native shield formula, item grade and resistance effects.
- Updates cached effect data and its native modifier together, with rollback on migration failure. Does not write shared shield definitions or saved item data.
- Uses equipment-change callbacks and the existing one-second skill maintenance; stable passes do not remove/add modifiers again. Removes a previously tracked local shield slot if it survives unequip.
- Targeted tests cover Hard to Kill, class-mod rank changes, shield removal, local-player isolation, idempotency and rollback. In-game equip/unequip validation remains required.

## 0.1.22 - Berzerk wording

- Changes the displayed Post-Add Gun Damage label to Amp Damage in the skill, Mod Manager summary and current README. Runtime messages use the same label; the underlying MT_PostAdd implementation is unchanged.
- Upper skill prose now says each shot costs some Health, without a percentage. The lower stat block retains the15% Current Health Cost per Shot.
- Wording-only update: numerical values, timing, formulas and hooks are unchanged. User reported Berzerk working in initial gameplay.

## 0.1.21 - Berzerk

- Replaces Come At Me, Bro completely with Berzerk. Removes the taunt, full heal, legacy active child effects/graphs and old stat text; retains the native one-point Gunzerking action-augment lifecycle.
- During Gunzerking, disables shield regeneration using the native resource-pool counter and grants50% damage reduction in isolation through the nine native resistance channels. Other resistance stacks normally; no separate damage-input multiplier is used.
- Both guns receive a fixed+75% MT_PostAdd Gun Damage bonus. Tagged weapon modifiers exclude their own previous value when recalculated, preventing feedback growth. They follow native gun damage changes, remain available for delayed projectile calculations during Gunzerking and are removed on unequip/end/travel.
- Each executed shot consumes15% of then-current health, once per shot rather than once per pellet or nested Fire/SharedFire call. Ammo-free shots still pay; blocked/empty-magazine attempts do not. Direct nonlethal health consumption bypasses shields/resistance without creating self-damage events.
- Adds the fixed-value footer, native one-point green numeric values and bounded first-damage/health-cost diagnostics.
- Eighteen focused Berzerk tests plus27 directly adjacent Asbestos/shared tests passed offline. A full restart is required; actual weapon damage, shield/resistance behavior and co-op remain unvalidated.

## 0.1.20 - Fistful of Hurt owner-only clarification

- Fixes four related Pylance diagnostics by explicitly rejecting a missing/departing target world before creating the non-optional mark key. Fifteen focused Fistful tests pass; valid-world gameplay is unchanged.

- Per the author's clarification, only damage from the Salvador who applied the debuff receives the15% multiplier; allies are excluded. Duration, refresh behavior and all original punch effects are unchanged.
- Updates the current description and documents the superseding policy. The14 focused Fistful tests pass, including the owner-only default and nested hostile/ally isolation. Engine validation remains pending.

## 0.1.19 - Fistful of Hurt vulnerability

- Adds a multiplicative +15% received-damage debuff for8 seconds after the native special punch damages a surviving enemy. Applies to Salvador and friendly allies; repeated hits refresh rather than stack the bonus.
- Identifies the exact MeleeDefinition damage causer, avoiding normal melee attacks during cooldown, missed swings and skill activation alone. Preserves native punch damage, knockback, cooldown and graphs; appends the new effect to the description.
- Uses the same received-damage stage as Elemental Mastery, multiplying the existing native factor by1.15 inside each affected damage calculation and removing only its own modifier afterward. Supports all six verified damage-source categories, bounded/reused modifier assets and primitive target records.
- Handles nested hits, healing/immunity, exact expiry, actor identity reuse and travel/destruction cleanup. No enemy scans or actor handles retained between hits; unmarked combat takes a fast path.
- Fourteen focused tests and16 adjacent shared-maintenance tests passed offline. In-game hit attribution/damage comparison and co-op remain unvalidated.

## 0.1.18 - Money Shot

- Reduces the completed Money Shot bonus by25%, taking its native maximum from96% to72% per effective rank (480% to360% at5/5).
- Preserves the native last-round initializer, small-magazine governor, firing events, presentation objects, class-mod grades and visual graph. Updates the display-only helpers to72% per rank and the actual12-round native maximum-bonus threshold.
- Reuses existing effect maintenance without additional firing/damage hooks. Five focused Money Shot tests, four adjacent Overkill tests and16 shared tests passed offline; actual last-round damage comparison remains pending.

## 0.1.17 - No Kill Like Overkill

- Halves the completed native bonus in both hands by setting the active effects' outer formula scales to0.5. This reduces both below-cap and capped outcomes rather than only the excess-damage input.
- Preserves original initializers, per-hand projectile division, kill graphs, timer, HUD and skill rank. Updates the description to50% of excess damage.
- Uses existing effect maintenance; no additional hooks. Four focused tests and16 adjacent shared-maintenance tests passed offline. In-game damage comparison remains pending.

## 0.1.16 - Asbestos HUD and duration color

- Adds a native timed Asbestos indicator using the menu icon, visible for the remaining ammo-free window. Confirmed reapplications renew only the visual timer; gameplay duration and ammo behavior are unchanged.
- Reuses the non-overlapping HUD allocator with inactive/remapped/child/cache reservations and purchased-slot repair. A full HUD hides only the new indicator, preserving the bonus and other icons.
- Uses immediate application-driven display plus a 0.1-second retry/cleanup pass only while the window/visual is pending. Native timing handles expiry; stable indicators are not repeatedly restarted.
- Formats the duration number in native intermediate-rank colors and green at the invested cap. Prevents early green in the next-rank preview and preserves class-mod/query-grade handling and original resistance text.
- User confirmed Asbestos and Double Your Fun gameplay. Eight focused HUD/color tests plus20 adjacent Asbestos/Piping Hot UI tests passed offline; in-game validation of the new indicator remains pending.

## 0.1.15 - Double Your Fun grenade regeneration

- Replaces the extra grenade throw with +0.1 grenade per second (one per10 seconds) while Gunzerking. The fixed rate is additive with equipment regeneration and respects native resource capacity.
- Removes the grenade-override listener, old display effect and special-move behavior provider. Retains ActionAugment classification, native one-point cap and on-foot constraint, allowing Gunzerking to own activation/removal.
- Replaces the old footer with the regeneration interval. Reuses existing scoped native-effect migration and maintenance; no grenade-spawn, firing or timer hooks are added for this skill.
- Four focused tests plus25 adjacent shared/native-effect tests passed offline. Full restart and in-game checks of regeneration, equipment interaction and single-grenade throwing remain required; co-op remains unvalidated.

## 0.1.14 - Asbestos ammo-free window

- Keeps every native Asbestos resistance, constraint and stat presentation. Adds 0.3 seconds of ammo-free gunfire per effective rank after a confirmed elemental affliction (1.5 seconds at 5/5); new applications refresh rather than extend the duration additively.
- Includes burn, corrosion, shock, slag and slow. Ignores resisted attempts, healing/unknown statuses and DoT ticks. Uses native effective class-mod grades and gameplay time.
- Covers both hands through scoped firing/consumption hooks. Preserves empty-magazine restrictions, reloads, reserve transfers and independent ammo gains. Restores shot cost even for blocked shots; no persistent weapon-property edits or status polling.
- Preserves the original native footer and adds the query-specific ammo-free duration. New diagnostics record the first confirmed window and verified free shot.
- Keep It Piping Hot: user confirmed footer/HUD working; the latest log records rank5, stacks1/10, accepted combined grades5/50 and nominal damage/spread bonuses0.005/0.05, without a skill error. This verifies helper application, not a separate measurement of damage dealt to a target.
- Eleven Asbestos tests and16 adjacent shared-maintenance tests passed offline. In-game Asbestos validation and co-op remain pending.

## 0.1.13 - Keep It Piping Hot footer and HUD

- Replaces the incorrect native fractional footer output with a query-specific formatter: both Gun Damage and Accuracy display +0.1% per effective rank per stack, reaching +0.5% at 5/5. Uses the queried grade once, including class-mod points; current/next-rank values and numeric colors follow the skill tree.
- Adds a native, visual-only stack counter using the menu icon. The displayed count is 1..50, independent of the gameplay helper's stacks-times-rank grade. The counter disappears when Gunzerking ends and returns for the next activation.
- Reserves logical, remapped, child and cached-icon slots before allocation; rechecks after native registration, repairs the purchased-slot prefix and moves only the new visual on collision. A full HUD leaves gameplay active without replacing another skill.
- Adds bounded diagnostic milestones (1/10/25/50 stacks per effective rank), checks the gameplay helper's actual grade after application and isolates visual errors from bonuses/cleanup. Reuses existing 1 Hz maintenance; stable counter values do not trigger redundant refreshes.
- Reviewed the current SDK log: no Salvador exception was recorded, but prior logs lacked stack diagnostics and cannot prove the previous bonus applied. 34 focused and adjacent offline tests pass; engine validation after a full restart remains required.

## 0.1.12 - Keep It Piping Hot

- Replaces the former cooldown gun/melee/grenade bonuses with Gunzerking stacks: one per gameplay second, maximum 50, lost when Gunzerking ends.
- Each stack grants +0.1% Gun Damage and Accuracy per effective rank. At 5/5: +0.5% each per stack, maximum +25% each. Supports class-mod ranks and both weapons.
- Adds native per-stack stat presentations and removes obsolete cooldown constraints. Uses native action callbacks and the existing throttled maintenance; no damage/fire hooks or additional HUD slot.
- Nine focused tests plus 26 adjacent shared/off-hand tests passed offline. Requires a full restart; in-game and co-op validation remain pending.

## 0.1.11 - Auto-Loader

- Adds a fixed passive 15% Reload Speed bonus for both hands.
- Preserves original reload-on-kill behavior, weapon-swap trigger and one-point maximum.
- Adds a native Reload Speed stat line and keeps the original flavor text.
- Reconciles existing reload effects to avoid stacking; no new hook or maintenance loop.
- In-game validation pending.

## 0.1.10 - Quick Draw

- Critical Hit Damage increases from 2% to 4% per effective rank (+20% at 5/5).
- Native Weapon Swap Speed, class-mod grades and stat presentations are preserved.
- Uses existing throttled native effect maintenance; in-game validation pending.

## 0.1.9 - Independent off-hand skill fixes

- Fixes a static type-inference error in Huckleberry effect specifications; gameplay is unchanged.

- Adds only missing native left-hand contexts for Just Got Real gun damage, Lay Waste fire rate, Keep It Piping Hot gun damage, Incite reload speed and 5 Shots or 6 ammo effects.
- Preserves formulas, live random resolvers, effective ranks, kill triggers and existing valid paired effects. Just Got Real's current 10% coefficient reaches both hands through the same health-dependent initializer.
- Replaces I'm Your Huckleberry's parent-gated helper with independent native pistol checks for each hand. Uses the learned skill's grade for both hands; retires and neutralizes the old off-hand helper to prevent stacking.
- Preserves pistol stat previews using two display-only helpers and native coefficient attributes; no new HUD slot.
- Migrates added effect contexts through the existing native rebuild helper without restarting timers. Reuses existing throttled maintenance; no per-shot hook or external patch import.
- Ten focused off-hand tests and 34 adjacent Salvador tests passed offline. Full restart and in-game left/right comparisons remain required.

## 0.1.8 - Sexual Tyrannosaurus

- Replaces damage-triggered regeneration with a native Gunzerking action augment.
- Per effective rank: +4% Life Steal, -3% Fire Rate to both weapons and -5% Critical Hit Damage.
- Removes the old incoming-damage event, behavior provider and timed-regeneration child link; neutralizes the legacy child's healing.
- Adds native rank-aware stat presentations, preserving class-mod grades.
- Uses native damage-to-healing conversion without Python damage hooks.
- Full restart required for the new skill classification. The user subsequently reported current changes working in solo; dedicated off-hand comparisons and co-op remain untested.

## 0.1.7 - All in the Reflexes

- Removes the melee-damage bonus and its stat line.
- Retains 5% Reload Speed per rank and adds another 5% per rank for empty-magazine reloads.
- Uses per-weapon reload events and the native ammo-at-reload-start snapshot; handles main/off-hand separately.
- Cleans up after completion, interruption and unequip; existing throttled maintenance repairs missed endings and class-mod changes.
- Updates the main description; native base reload stat and class-mod scaling are retained. In-game validation pending.

## 0.1.6 - Divergent Likeness

- Replaces different-type Accuracy with Fire Rate for both weapons while Gunzerking, retaining 6% per rank.
- Preserves same-type gun damage, native type checks and class-mod scaling.
- Updates skill text and stat label. Migrates existing modifier contexts without restarting the skill.
- In-game validation pending the combined test.

## 0.1.5 - I'm Ready Already

- Gunzerking cooldown rate increases from 5% to 10% per effective rank (+50% at 5/5).
- Keeps native class-mod ranks, stat presentation and cooldown calculation.
- In-game validation pending the combined test.

## 0.1.4 - Ain't Got Time to Bleed

- Regeneration uses 3% of missing health per second per effective rank during Gunzerking.
- Retains the native missing-health formula and action-skill condition.
- Native stat text now identifies missing health.
- Shares existing maintenance and native class-mod scaling. In-game validation pending.

## 0.1.3 - Just Got Real

- Increases the native gun-damage coefficient from 8% to 10% per effective rank.
- Keeps the health-dependent formula, native UI and class-mod scaling.
- In-game validation remains pending the combined test.

## 0.1.2 - I'm the Juggernaut

- Damage-reduction coefficient increases from 4% to 12% per effective rank.
- Preserves native kill-skill activation, duration, UI, class-mod ranks and damage-reduction calculation.
- Shares the existing throttled maintenance pass; no additional combat hook.
- In-game validation pending the combined balance test.

## 0.1.1 - Hard to Kill

- Maximum health increases from 4% to 6% per effective rank.
- Removed the native regeneration effect and its stat text.
- Retains native class-mod grades, current/next-rank previews and colors.
- Repairs existing effect snapshots without reactivating skills; maintenance is throttled to once per second.
- In-game confirmation is pending.

## 0.1.0 ? project scaffold

- Created a loadable SalvadorRebalance package with empty hooks, commands, keybinds and options.
- No gameplay changes are included.
- Added project documentation and a research/validation outline.
