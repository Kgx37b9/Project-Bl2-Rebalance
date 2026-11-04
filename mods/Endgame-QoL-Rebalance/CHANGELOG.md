# Changelog

## 1.0.9 - 2026-11-03

- Correct the unusually large transferable Voracidous/Chief Ngwatu shield in UVHM at its dedicated native attribute. Calibrate the scale from the measured 11.00 billion shield to about 11.31 million at default settings, 75% of Voracidous' measured 15.08 million HP. Preserve the native transfer and leave other shields unchanged. Fresh-encounter verification is pending.

## 1.0.8 - 2026-11-03

- Fix the slag-audio cleanup gap after death: the native `Died` event records only controller, pawn and world addresses, and confirmed deaths keep a pending cleanup until a different live pawn appears. At that point, check active local slag and post only the exact local slag stop event. Do not touch the dead pawn or play sound during teardown.
- Preserve the respawn marker if an enemy's slag ends during respawn; discard it on world travel. The installed 1.0.7 log showed no cleanup message during the reported death/respawn case. Thirteen focused audio and 51 adjacent UVHM tests pass offline; in-game confirmation remains pending.

## 1.0.7 - 2026-11-03

- Fix a gap in orphan slag-audio cleanup: a slag status ending on an enemy now arms the same local-only cleanup check. The previous hook only armed it when the player was slagged, while the reported loop can follow slag applied to an enemy.
- Preserve active slag on the local player and NPC audio; do not add audio-component scans, per-shot work or a new timer. Ten focused audio and 51 adjacent UVHM tests pass offline. In-game confirmation is pending.

## 1.0.6 - 2026-11-03

- Add a UVHM ammo-pack drop slider under Resources and Storage: 1x-5x, default 2x. At 1x, leave the native drop field untouched. The selected value is frozen until a full restart.
- Raise only Hyperius' own health multiplier from 56 to 98 (+75%) while retaining party-size normalization and leaving shields, other bosses and phases unchanged. The ~13.0M solo HP figure is an estimate from the previously reported ~7.4M observation and awaits in-game confirmation.
- Add focused option and raid-health regression checks.


Version history for EndgameQoLRebalance. Earlier entries retain their historical names and behavior.

## 1.0.5 - 2026-11-01

- Add local slag audio lifecycle cleanup for the confirmed orphan looping sound. Local slag sound/status-end events arm a check in the existing maintenance pass; stop only after native status/type queries report no slag. Clean native per-type audio state and post the exact local-controller stop event confirmed by the author's manual test.
- Preserve active/reapplied and replicated slag, other sound types and NPC audio. Keep no audio objects in Python state, add no global audio-component scan and discard pending work at real travel/destruction.
- Nine new lifecycle tests and 32 adjacent slag/safety/performance tests pass offline. The author confirmed the manual stop removes the swoosh; automatic in-game validation is pending.

## 1.0.4 - 2026-11-01

- Treat frontend/options opening as a temporary pause instead of marking the gameplay world as departing. Resume loot stars and ordinary maintenance after the menu closes in the same map. Preserve departure barriers from actual travel/destruction.
- Skip maintenance while the world is paused or the local pause menu remains open, including the case without a world Pauser. Add repeated-menu integration coverage and lifecycle regressions. Forty-nine focused/adjacent tests pass offline; in-game confirmation is pending.

## 1.0.3 - 2026-11-01

- Correct the slag NPC guard evaluator path to the native nested-subobject form (`Asset:Helper.Guard`). The previous double-colon form caused verification to reject the new evaluator before attaching the constraint.
- Update the offline object fixture to use native subobject naming. Fifteen focused slag/guard tests pass, including constraint reuse, player exclusion and native audio callback preservation. In-game verification remains pending.

## 1.0.2 - 2026-11-01

- Recover gold minimap stars after menus or native HUD timeline changes hide existing clips, reset their opacity/position or clear their drawing. Reconcile only this mod's clips once per second, preserving cached draws between checks and native HUD visibility.
- Add regression coverage for hidden clips, cleared drawings, reset transparency/positions and bounded readback. All 31 loot-star tests and 15 adjacent performance/lifecycle tests pass offline. In-game confirmation remains pending.

## 1.0.1 - 2026-11-01

- License clarification: personal gameplay use is permitted; prior written permission is required to reuse original project code or material. Third-party rights remain separate. No gameplay behavior changed.

- Reduce stable raid-health audit allocations: native rows and playthrough records are copied only when a balance value actually needs repair. Keep the same two-second audit and native readback after writes.
- Gold minimap stars retain only numeric render positions and a visibility flag. Unchanged icons no longer receive repeat GFx position, child visibility, overlay visibility or count writes at the 20 Hz draw cadence. Changes in player position, map orientation, item positions and item removal still update the overlay.
- Resolve the local player once per storage-capacity context and update the test fixture to load the current source folder.
- Correct the README source-install path. No skill, balance value, setting default or gameplay trigger changed. Co-op and in-game FPS impact remain unverified.

## 1.0 - 2026-10-30

- Use EndgameQoLRebalance as the SDK project and display name.
- Split Level Difference Corrections into independent higher-level enemy resistance, enemy damage and elemental status chance switches. Existing combined settings migrate to all three switches.
- Group backpack, personal bank and ammo switches under Resources and Storage. Add an optional 1000-Eridium carrying cap on verified Windows BL2 executables through a memory-only adjustment; unsupported builds keep their native limit.
- Remove the temporary raid-health observation hooks and related log spam; the raid-health balance rules remain.
- Refresh publication text and package metadata. New options and the Eridium cap require in-game validation after a full restart.

## 0.6.26 - 2026-10-30

- Update raid-health documentation with the current solo observations: Pyro Pete and Voracidous log values, the user-reported Hyperius value, and clearly marked approximate +75% references for other bosses. No raid-health gameplay tuning changed.

Player-facing changes for VaultHunterSupport. Older entries describe the behavior of their respective versions, not the current defaults. Project credits are consolidated in [README.md](README.md#credits-and-references).

## 0.6.25 - 2026-10-30

- Supplement temporary raid-health observations with a bounded local pawn-list traversal: at most 256 pawns every four seconds, cycle protection, no retained actors and deferred health-pool validation. Add a known-balance fallback for supported raid identities.
- Report discovery separately from actual HP. Raid multipliers are unchanged; new diagnostic coverage needs in-game confirmation after restart.
- Record author confirmation that solo bank and backpack capacities work correctly; their values are unchanged.

## 0.6.24 - 2026-10-30

- Set Master Gee's UVHM own health multiplier from 3,500 to 1,000, before the existing player-count normalization. Keep its native class base outside UVHM unchanged.
- Set Dexiduous' class-base health multiplier from 100,000 to 2,500. Preserve its native party scaling and unrelated attributes. Both fixed-base policies are controlled by Raid Boss Health and require a complete restart/fresh encounter.
- Update the README projection table: in the documented solo UVHM 5% profile, Master Gee level 92 is approximately 38.30M HP and Dexiduous level 93 is approximately 87.74M. Keep the temporary real-health logger for runtime confirmation.

## 0.6.23 - 2026-10-30

- Add temporary, read-only raid-health observations after natural spawn, customization or level-change events. Log native maximum/current health, level, party counts and network mode once per observed state; distinguish the raid version of Son of Crawmerax from its story encounter.
- Use the existing two-second maintenance budget, bounded path-only queues and travel/menu cleanup. Do not spawn test actors, change health, scan all enemies or print startup health estimates. Capture in the game remains unverified.

## 0.6.22 - 2026-10-30

- Add an enabled-by-default Raid Boss Health toggle. Normalize Hyperius, Master Gee, Voracidous and Pyro Pete health against actual party size when effective player count is inflated. No fixed unconditional solo nerf; equal counts give a neutral factor, and four players retain their native weight.
- Preserve native health-pool identities and wrap only health-multiplier entries across class, playthrough and map definitions. Retain original coefficients/initializers and compatible native health-weight changes; avoid compounded maintenance edits and global player-count changes. Shields, damage, loot and scripted healing/phases are not rebalanced.
- Add the health equation, assumptions, level-1/OP10 projection table and remaining uncertainties to [README.md](README.md#raid-boss-health). This is a planning table; runtime health and co-op validation remain pending.

## 0.6.21 - 2026-10-29

- Isolate NPC-only slag movement/fire-rate penalties in a rooted internal skill with no audiovisual graph. Preserve the native slag skill's visual/audio activation and deactivation; a rejected player penalty no longer uses the native dissolve-effect graph.
- Restore native slag status processing and native activation bookkeeping. Keep the existing application/end callbacks, and append one paired activation/cleanup for the silent NPC debuff without duplicating callbacks during maintenance.
- Keep the seven-second base duration, neutral damage, NPC penalties and player protection. No new per-hit/tick audio hooks, global sound muting or player modifier removal. The reported sound loop requires in-game confirmation after a full restart.

## 0.6.20 - 2026-10-29

- Set shotgun starting reserve capacity to 140. Keep +30 per purchased SDU; with nine SDUs, capacity is 410.

## 0.6.19 - 2026-10-29

- Allow personal-bank/backpack capacity policies for a local listen-server host with exactly one native player, in addition to standalone mode. Keep clients, dedicated servers and active co-op excluded.
- Resolve unavailable storage SDU indices through the loaded globals' actual BlackMarketUpgrades references and order, without fixed save-array indices. Reject ambiguous matches and retry pending assets.
- Add deduplicated storage readiness/SDU diagnostics so session or asset gates no longer fail silently. Preserve storage curves, item contents, larger capacities, setter reentrancy guards and maintenance intervals.

## 0.6.18 - 2026-10-29

- Increase backpack starting capacity from 12 to 22. Preserve intermediate SDU gains; the ninth/final native SDU grants 15 instead of 5 slots, reaching 70 with all nine upgrades. Continue preserving larger capacity and occupied inventory.

## 0.6.17 - 2026-10-29

- Consolidate all support runtime code into `__init__.py`, including enemy, loot, mission and vendor level policies.
- Keep level-policy state/helpers separately named to avoid collisions with balance maintenance. Preserve saved option keys, defaults, hooks, replay guards and the 0.6.16 optimizations.
- Simplify installation to four files: `__init__.py`, `pyproject.toml`, `README.md` and `CHANGELOG.md`.

## 0.6.16 - 2026-10-29

- Avoid schema/reflection lookups for unchanged numeric, boolean and nested-struct values. Native writes still resolve schemas, prepare references before committing and verify readback; enum, array and FName comparisons retain their metadata rules.
- Skip the second global/UVHM level-table scan when the first complete inspection finds no edits. Reuse the current UVHM signature when no write occurred; retain complete post-write verification and rotating audits.
- Skip idle PlayerTick context validation when neither maintenance nor loot-star drawing is due. Keep loading/departure guards, forced startup checks and the existing maintenance/marker intervals.
- In offline fixtures, repeated stable-state checks avoid unnecessary metadata queries. Across simulated frames, context checks are reduced while marker draw deadlines remain serviced. These are request counts, not in-game frame-time measurements.

## 0.6.15 - 2026-10-29

- Add Backpack Capacity, enabled by default for solo play: retain 12 initial slots; SDUs add +3, +3, +4, +4, +4, then +5 for every later upgrade. Previously purchased SDUs count toward the same curve.
- Preserve larger existing capacity, occupied inventory, equipment and SDU purchase records. Guard native capacity setters against reduction and repeated execution after exceptions; retain native setter flags.
- Share ownership/loading validation between the personal-bank and backpack policies. Continue using the existing two-second maintenance budget; do not add item scans or per-shot work. Multiplayer remains excluded from both storage policies.

## 0.6.14 - 2026-10-29

- Add Personal Bank Capacity, enabled by default for solo play: 25 initial slots, then +5, +5, +10, +15 and +20 for each further bank SDU. Existing purchased SDUs contribute to the same progression.
- Expand only the owning character's personal-bank capacity ceiling and slot count. Preserve larger existing capacity and occupied slots, including unloadable equipment. Keep shared stash, global storage defaults, SDU counts/prices and bank contents unchanged.
- Protect native SDU slot updates from reducing an expanded bank. Use the existing two-second maintenance budget and prepare capacity when opening the personal bank; loading/departure, foreign ownership and network sessions are excluded.
- The removed inventory-to-bank transfer, inventory input hook and keybind remain absent. In-game save/load and UI behavior require a focused retest.

## 0.6.13 - 2026-10-29

- Add Ammo Capacity, enabled by default and applicable in all playthroughs: sniper base reserve increases from 48 to 72, with 24 additional rounds per SDU instead of 12; shotgun base reserve increases from 80 to 104, with 30 additional shells per SDU instead of 20.
- Preserve purchased upgrade counts, native upgrade formulas, magazine sizes, SDU prices and other ammunition types. Use absolute targets with the existing maintenance budget, without firing hooks or repeated multiplication of edited values.

## 0.6.12 - 2026-10-29

- Remove Send to Personal Bank entirely at the author's request: no Inventory Management category, bank-transfer keybind, inventory-input hook, transfer state, native bank calls or menu-save requests remain.
- Old saved bank options and keybind entries are ignored; they cannot reactivate the removed feature. A full restart is required after replacing an older build.
- Preserve the bounded equipment validator used by loot minimap stars. Update the current README and mod-manager description to match the reduced feature set.

## 0.6.11 - 2026-10-29

- Remove only the UVHM passive health-regeneration effect. Preserve unrelated native/other-mod enemy attribute effects, their formulas and ordering, including newly inserted balance tiers and later repairs.
- Block the original native call after any ordinary Python exception during a level-policy replay. This includes `IndexError`, which previously could allow a partially executed call to run again.
- Guard each level-policy callback for its full lifetime, including vendor stock updates. A nested replay cannot release its outer callback's guard; reentrant stock queries do not initialize the same item twice.
- Bound the shared equipment-class validation used by bank transfers and loot stars, preventing malformed class hierarchies from causing an unbounded loop.

## 0.6.10 - 2026-10-29

- Remove the 0.6.9 background stack watchdog and its testing option entirely. The new crash dump identifies an access violation in that diagnostic thread while inspecting another thread's Python frames. Saved `freeze_diagnostics` entries no longer enable anything. A full restart is required.
- Fix loot-star displacement while walking: use the native minimap world-radius-to-icon scale rather than the map texture's units-per-pixel value. The world-space outer radius is not treated as a UI radius.
- In rotating-map mode, use cached player yaw instead of adding it to the fixed map offset. Use the native rectangular icon area for edge clipping; preserve the custom star shape, rarity filters, pooling and scan/draw budgets.
- Preserve the 0.6.9 slag-guard and registered departure-hook fixes. The earlier 15:30 AppHang still has no conclusive captured cause; do not conflate it with the newly identified diagnostic crash.

## 0.6.9 - 2026-10-29

- Prevent duplicate slag guards when an equivalent native constraint array is reallocated. Attach once per rooted definition/evaluator, with recovery for an empty array, without following old evaluator pointers.
- Register the travel/controller-destruction callback in the explicit SDK hook list. The callback existed in 0.6.8 but was omitted from that list.
- Add Freeze Diagnostics (Testing), enabled by default: one Python watchdog writes stack snapshots every 30 seconds to `VaultHunterSupport.hang.log` beside the mod settings. Disable this testing option after the investigation; replacing the build/settings requires a full restart.
- Windows confirmed an AppHang around 15:30 with 0.6.8. No hang dump/stack was retained, so these fixes address reproduced code defects without claiming a proven cause or confirmed runtime resolution of that incident.

## 0.6.8 - 2026-10-29

- Fix the maintenance path implicated by both 0.6.6 crash dumps: stop inspecting old native constraint `Evaluator` pointers and their object paths. Reuse a rooted guard, with primitive array/owner identity to avoid repeated attachment.
- Suspend periodic maintenance before travel/controller destruction and menu entry. Resume only for the current initialized player in a new gameplay context; keep definition preparation in the explicit initialization hooks.
- Prevent stacking of the native slag skill. The movement diagnostic captured two copies of the slow modifier in the affected session.
- Preserve the rooted-evaluator fix from 0.6.7. Both reported crashes used the still-installed 0.6.6 package; offline tests do not establish runtime stability of this build.

## 0.6.7 - 2026-10-29

- Preserve the dynamically created slag evaluator across garbage collection with the SDK lifetime flag. Use its fully qualified native class and validate compatibility with the destination constraint property before applying debuffs.
- Address the new 0.6.6 log error `Object is not instance of ExpressionEvaluator` observed after an initial successful validation and a loading transition. Runtime retesting remains required.
- Clarified the original slowdown report: changing maps did not clear it; reloading the character from the main menu did. This does not by itself prove slag was the cause.

## 0.6.6 - 2026-10-29

- Restrict the new slag movement/fire-rate penalties to non-player recipients using a native activation/active-state constraint. Preserve native status expiry and other skills' movement modifiers.
- Add rate-limited movement diagnostics to the existing two-second maintenance pass. This observes low speed and its modifier sources without resetting speed or removing effects.
- The reported persistent slowdown had no matching exception or movement snapshot in the previous log; the slag scope defect is fixed, while confirmation of that particular episode's cause requires an in-game retest.

## 0.6.5 - 2026-10-29

- Preserved loot minimap stars, bank transfer and all balance/level options.

## 0.6.4 - 2026-10-29

- Drive loot stars from the already observed local PlayerTick through GetHUDMovie. Removed viewport-visibility/open-movie prerequisites that could silently prevent minimap discovery.
- Added an owned-widget lookup fallback with a cached path, retaining no UI objects between callbacks.
- Accept eligible equipment attached to a surface and query its native rarity when the pickup's replicated rarity is not yet available.
- Offline regressions passed. In-game transfer/loading behavior, star drawing and positioning still require confirmation.

## 0.6.3 - 2026-10-29

- Moved gold loot star updates to the viewport render event, avoiding reliance on hooks for the native C++ minimap update path.
- Added a native-radius scale fallback and concise diagnostics for render entry, minimap initialization and eligible loot detection.
- Preserve loading readiness, holding/release timers, destination placement and world/station particle effects.
- Offline regressions passed; in-game star drawing and alignment require confirmation with this build.

## 0.6.2 - 2026-10-29

- Added Inventory Management / Send to Personal Bank, enabled by default.
- Added a configurable Send Selected Item to Bank key, default B, available while selecting unequipped backpack equipment in the inventory. Initial support is solo-only.
- Respect native bank capacity, including unloadable items; reject equipped/restricted items and inventory transitions. Preserve the shared stash and existing equipment levels/parts.
- Use a single native deposit with postcondition checks, input debouncing, native menu save-on-close and a stop on unverified partial results. No extra tick/damage hooks or external storage files.
- In-game transfer behavior and persistence still require confirmation with an expendable item.

## 0.6.1 - 2026-10-28

- Added the Rare Loot Minimap Stars toggle, enabled by default and applied after restart.
- Added a custom five-point gold vector star for Legendary, Pearlescent, Seraph and Effervescent ground equipment, excluding E-tech and mission tokens.
- Render inside the minimap without replacing native icons or occupying skill/radar slots. Reuse clips and reconcile the native pickup list at most four times per second, without shot/damage hooks.
- Added world/HUD cleanup, out-of-range hiding and error backoff. Minimap drawing, projection and co-op require in-game confirmation.

## 0.6.0 - 2026-10-28

- Added the event-driven level policies and Level Scaling category.
- Five selectors control enemy minimum/maximum, loot minimum/maximum and mission minimum. Each offers Vanilla, effective player level, and player +1 through +10.
- Defaults: enemy minimum at player level and maximum Vanilla; loot minimum at player level and maximum Vanilla; mission minimum at player level.
- Added toggles for on-level vendors and a level-80 cap on newly generated equipment, both enabled by default.
- Relative levels include active OP scaling. Only the item cap imposes an 80 ceiling; it takes priority over loot/vendor settings.
- Use native generation, inventory and mission-level entry points without adding a tick or damage hook. Preserve loaded player equipment and locked missions.
- Fourteen focused offline tests passed. Gameplay coverage and co-op remain pending.

## 0.5.14 - 2026-10-28

- Brought weapon depth closer by category: assault rifles 3; launchers 5 (Bandit 7); pistols 10 or 12 according to their native depth group; SMGs 0; shotguns and snipers 3.
- Calculate depth from fixed category targets, avoiding accumulated offsets. Unrecognized categories or depth groups retain native X.
- Five relevant offline tests passed; final appearance, aiming and clipping need in-game confirmation.

## Documentation update - 2026-10-28

- Reorganized the README around current features, options, installation and compatibility.
- Separated version history into this file; technical investigations remain in the workspace's development records.
- Consolidated project credits in the README and simplified menu/log wording.
- No balance or gameplay logic changes. Package version remains 0.5.13.

## 0.5.13 - 2026-10-28

- Apply the presentation setting to controller defaults and valid local controllers, preserving loading readiness and holding-release controls.
- Retired the final TXT importer.

## 0.5.12 - 2026-10-28

- Set the horizontal target to Y = 0 for assault rifles, launchers, pistols, SMGs, shotguns and snipers.
- Kept targets separate by category for later visual calibration.

## 0.5.11 - 2026-10-28

- Replaced the previous fixed family presets. At this version, offsets remained fully native; horizontal placement changed in 0.5.12.

## 0.5.10 - 2026-10-28

- Separated game and money growth into native-resolver policies driven by independent sliders.
- Preserved existing saved choices, the 1-20% range and 5% defaults.
- Apply absolute factors without compounding previous edits.

## 0.5.9 - 2026-10-28

- Rebuilt the mission-reward feature as an additive operation.
- Add the reward once while preserving loaded XP, money, other items and item pools.
- Retry unavailable DLC assets before committing a reward edit.

## 0.5.8 - 2026-10-28

- Removed duplicate special-currency pickup and one-purchase ammo-refill rules, their menu categories and shop hooks.
- Ignore obsolete option keys without changing other saved preferences.
- Kept the separate UVHM ammo-drop multiplier.

## 0.5.7 - 2026-10-28

- Replaced the remaining fixed uncommon-chest-weight curve with level boundaries: 0.15 through level 60, 0.0625 at 61-70, and 0.025 from 71 onward.
- Preserve native/custom thresholds and keep common-item weights independent.

## 0.5.6 - 2026-10-28

- Common-item weight: 0.10 at levels 50-60 and 0.02 from level 61 onward, UVHM only.
- Preserve the native common-item field below level 50.

## 0.5.5 - 2026-10-28

- Unified three level-difference corrections under one switch.
- Neutralize higher-level enemy damage resistance, higher-level enemy extra damage, and elemental status chance modifiers in global tables and UVHM/OP overrides.
- Preserve unrelated fields, native thresholds and experience rules.

## 0.5.4 - 2026-10-28

- Reworked slag: 7-second base duration, 30% less movement speed and 25% less weapon fire rate.
- Removed damage amplification and made slag damage neutral against all health surfaces.
- Removed character-specific companion and action-skill edits.

## 0.5.3 - 2026-10-28

- Added separate UVHM status-damage tuning inputs for burning, shock and corrosion, initially neutral at 1x.
- Removed additional rank-gain and weapon-swap edits.

## 0.5.2 - 2026-10-28

- Extended the UVHM durability slider to enemy shields, retaining the native badass proportion.
- Set UVHM player vehicle weapon damage to 3x and ammo drops to 2x.
- Stopped setting the UVHM enemy-damage multipliers.

## 0.5.1 - 2026-10-28

- Removed passive regeneration granted to enemies by UVHM balance effects.
- Preserved scripted healing, boss phases and unrelated effects.

## 0.5.0 - 2026-10-28

- Introduced the UVHM health slider: 1-4x, step 0.25x, default 2x.
- Preserved the native badass health proportion instead of using a fixed durability curve.

## 0.4.1

- Simplified the options menu and removed separate restart notices.
- Made the travel presentation adjustment always active; obsolete toggle keys no longer control it.

## 0.4.0 - 2026-10-26

- Added category switches and independent game/money growth sliders.
- Freeze choices for the running process and require a full restart to apply changes.
- Preserve saved options and show when a restart is required.

## 0.3.0 - 2026-10-26

- Added the selected quality-of-life profile covering growth, pickup, shops and mission rewards.
- Later versions removed or replaced these earlier fixed settings individually.

## 0.2.1 - 2026-10-26

- Strengthened bounded runtime auditing and recovery after balance data changes.
- Prepare field values and references before native writes and verify the resulting data.

## 0.2.0 - 2026-10-26

- Expanded the initial global corrections with UVHM durability, regeneration, loot and elemental balance settings.
- Subsequent 0.5.x releases revised the implementation and feature set.

## 0.1.0 - 2026-10-26

- Initial shared support module with level-difference damage and status-chance corrections.
- Kept the support module independent of character skill modules.
