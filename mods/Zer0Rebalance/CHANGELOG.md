# Changelog

## 1.0.7 - Tw0 Fang native firing-state fix

- Reduce Grim Cooldown Rate from 10% to 8% per point; preserve its shield regeneration.

- Capture confirmed that actual extra shots use WeaponFiring.ExtraFireAmmunition, bypassing the base method previously hooked. Apply the free-shot scope to both native entry points.
- Preserve normal-shot cost, proc chance and all existing skill values. Add a dispatch regression covering the observed normal/extra/normal shot sequence and total ammunition.


## Unreleased - Tw0 Fang extra-shot ammunition

- Remove ammunition consumption only from Tw0 Fang's native extra shot. Preserve the initial shot cost, native proc chance and class-mod ranks.
- Restore temporary shot cost on unconditional completion, reset or disable; restrict the effect to the local Zer0 and current weapon/world.


## Unreleased - Unf0reseen, Fearless and Resurgence tuning

- Fearless now requires any positive shield value rather than full shields, granting 5% Fire Rate and 4% Gun Damage per point.
- Show Unf0reseen's 14-meter damage radius in its lower skill description.
- Reduce Resurgence healing to 5% Maximum Health per point on kills; preserve critical-hit shield recovery.
- Replace the level-dependent extra bonus with a fixed 50% at all levels, preserving native level scaling.
- Follow Decepti0n's five native timed damage stacks for up to 200% additional explosion damage. Combined factors range from 1.5x to 4.5x, including status damage.
- Reduce the shared pull/damage radius from 20 to 14 meters; preserve Death Mark and Many Must Fall behavior. No new hooks, timers or per-hit scans.


## 1.0.6 - Combat-path allocation and reflection safeguards

- Prepare all 48 bounded Be Like Water damage modifiers during configuration, removing asset lookups and object creation from nested damage callbacks. Fail safely if a prepared slot is unavailable.
- Reuse static helper definitions for Be Like Water movement and Kill Confirmed stack updates; discard cached references when the session resets.
- Precision skips its nearby-target search for noncritical hits and already-resolved reflections. Explicit modifier rejection now rolls back the attempt without publishing reflection data.
- Preserve all skill values, triggers, timers and HUD behavior. 129 focused and adjacent tests passed; native gameplay and co-op validation remain separate.

## 1.0.5 - Temporary Amp helper ownership

- Resurgence now restores a fixed 6% Maximum Health per point on enemy kills. Correct the native healing coefficient and use Maximum Health in its graph instead of missing health. Update the description and footer; preserve 4% shield recovery on critical hits and the native 0.1-second retrigger interval.

- Replace permanent At One with the Gun modifiers owned by transient weapons with a fixed pool of eight modifiers owned by the static skill definition, isolated by nested firing depth. Preserve damage, charge counting and HUD behavior.
- Eliminate object creation/lookups during empowered shots and fail safely when the nesting limit is exceeded.
- This addresses a concrete lifetime risk found while investigating two native Save & Quit crashes. The dumps do not prove this was their cause; repeated Save & Quit testing remains required. A full game restart is required. Thirty-six focused tests passed.

## 1.0.4 - At One with the Gun HUD

- Increase Fearless Gun Damage to 5% per point; retain 7% Fire Rate and the full-shield requirement. Increase Unf0reseen linear extra damage scaling to +75% at level 1 and +300% at OP10, for both impact and status damage.

- Set Fearless to +7% Fire Rate and +4% Gun Damage per point with full shields. Return Like the Wind damage avoidance to 5% per point.

- Increase Grim shield regeneration from 0.7% to 1.1% Maximum Shield per second per point. Preserve its kill-skill duration and 10% Cooldown Rate per point.

- Increase Resurgence health restoration on kills from 4% to 6% per point, retaining its health-dependent native formula and 4% shield restoration on critical hits. Increase Like the Wind damage avoidance while moving from 5% to 6% per point.

- Count a critical weapon shot as two charges total. A later critical pellet upgrades an earlier normal hit from the same shot by one charge; repeated pellets cannot grant more. Preserve the ten-charge cap and next-shot Amp.

- Add a native HUD counter using the original skill icon, showing 1-10 charges. Ten indicates the empowered next shot is ready; consuming the charge removes the icon. No time limit or damage changes.
- Reuse the counted-feedback factory and safe slot allocator from Be Like Water, with independent visual state. Preserve other indicators and gameplay bonuses when HUD space is full.
- Refresh only on changed counts or a bounded one-second recovery check; clear on respec, death, travel or disable. Forty focused and adjacent tests passed; visual validation in game remains pending.

## 1.0.3 - Preserve the native stealth behavior graph

- Fix native array writeback in the Many Must Fall weapon gate. Detach every sequence, event, behavior, output link and variable link before replacing their arrays, preserving native invisibility and termination behaviors.
- A live capture of 1.0.2 showed the original behavior nodes cleared and almost all original output links zeroed after configuration. Add a readback check and regression coverage for borrowed native rows.
- Remove the unsuccessful renewal-context override; preserve the native activation context. Keep the failed-shot delay and original kill-duration graph.
- Sixteen focused and adjacent tests passed. A full game restart is required to recover the original graph; in-game confirmation with this fix remains pending.

## 1.0.2 - Many Must Fall renewal guard and failed-shot exit

- Remove an invalid Actor-only property check on the native Skill UObject, which prevented the previous renewal-context correction from running.
- Route MMF weapon firing directly to the native 0.5-second end delay. Avoid the melee target comparison, since firing does not provide its Enemy output. Preserve the original exit when MMF is not running and the existing kill-renewal graph.
- Migrate the earlier gate without adding duplicate nodes. Record the first successful context normalization for verification.
- Seventeen focused and adjacent tests passed. In-game confirmation of invisibility renewal and failed-shot termination remains pending.

## 1.0.1 - Many Must Fall stealth renewal

- Normalize the native stealth-renewal call to the current character pawn, matching the initial Decepti0n activation. A live trace showed renewal activating Stealth with the controller context while the visual invisibility was missing.
- Preserve native kill processing, bonus duration and reactivation delay. The guard targets only this renewal behavior and adds no periodic queries or skill scans.
- Cover renewal, unrelated activations, travel/reset, invalid contexts and expired actions with focused tests. Visual restoration still requires confirmation after restarting with the updated mod.

## 1.0.0 - Release preparation

- Establish the 1.0 release version and the Mod Manager display name Zer0 Rebalance, preserving the Zer0Rebalance package identifier.
- Consolidate the current skill changes, requirements, installation, compatibility, credits and license references in README.md. Keep technical history and remaining gameplay checks in DEVELOPMENT.md.
- Carry forward the 0.2.4 balance and stability changes without further gameplay changes. Co-op remains unvalidated.

## 0.2.4 - Stability and maintenance review

- Remove the experimental duration skill, tree insertion, icon loading and diagnostics.
- Resolve each distinct skill-definition path once per maintenance snapshot. Cache weapon damage-source ancestry in a bounded, session-reset table.
- Correct At One with the Gun's native enemy filter and remove its dependency on the retired hipfire helper.
- Guard Kill Confirmed against missing controllers and departing worlds; restore nested Unf0reseen formulas in reverse order during cleanup/reset.
- Preserve balance values, including Critical Ascensi0n's 2.5-second decay interval. 104 focused and adjacent tests passed; gameplay and co-op validation remain necessary.

## 0.2.3 - Critical Ascensi0n decay

- Reduce the interval between stack losses from 5 to 2.5 seconds, preserving the native initial delay.

## 0.2.2 - Critical Ascensi0n and numerical tuning

- Critical Ascensi0n: critical hits with all gun types can build stacks. Snipers retain full bonuses; other guns receive half the native Gun Damage and Critical Hit Damage bonuses. Preserve the native initial decay delay, missed-shot behavior and stack limit; change the interval between stack losses from 1 to 5 seconds.
- Grim: Cooldown Rate increased from 8% to 10% per effective rank (50% at 5/5).
- Innervate: Gun Damage increased from 3% to 4% per effective rank (20% at 5/5); health regeneration remains 1.6% per second per rank.
- Eighteen focused tests passed. Conditional weapon bonuses and all-weapon stack generation still require gameplay confirmation.

## 0.2.1 - Resurgence and Many Must Fall triggers

- Resurgence now restores shields from confirmed critical damage in the native damage pipeline. Remove its dependency on the critical-hit statistics callback, which did not fire during the captured hits. Preserve the 4% per-rank amount and effective class-mod ranks.
- Many Must Fall now routes weapon firing through the native melee-resolution grace path while the native MMF-running condition is true. Preserve the original weapon exit when MMF is not active, along with native kill handling, duration and decoy behavior.
- Sixty-two focused and adjacent tests passed; in-game shield restoration and firearm-kill renewal still need confirmation after updating.

## 0.2.0 - Numerical balance adjustments

- Grim: Cooldown Rate reduced from 12% to 8% per effective rank (40% at 5/5).
- Rename Optics to Pin point; Accuracy increased from 10% to 20% per effective rank (100% displayed at 5/5). Recoil Reduction and Aim Speed remain unchanged.
- Innervate: Maximum Health regeneration increased from 1% to 1.6% per second per effective rank (8% at 5/5). Other effects and class-mod rank support are retained.

## 0.1.28 - Precision native reflection result

- Live capture confirmed that critical hits activated the reflection attributes, but the pipeline still returned no reflection. Precision now publishes the native instigator ReflectionData result during the confirmed critical event instead of relying on attributes to recalculate an already-finished damage pass.
- Preserve original hit damage, existing reflection decisions, 30-meter search radius and rank-based reflected damage. Leave native projectile reflection flags unchanged.
- Add a once-per-session diagnostic for publication of the reflection result. Forty focused tests passed; actual secondary hits and native projectile handling still require in-game validation.

## 0.1.27 - Precision critical-event guard and pulse lifetime

- Remove the transient pipeline bCanReflect check that rejected confirmed critical bullet events in live captures, including ordinary sniper hits with nearby enemies. Native projectile reflection flags remain unchanged.
- Keep each critical's reflection attributes and 30-meter radius through the return from TakeDamage. Clear them before the next impact or local player tick, and during travel/disable. Nested damage cannot arm another pulse.
- Preserve damage and effective class-mod scaling. Thirty-six focused Precision tests and thirty-seven adjacent movement/HUD/damage tests passed; native ricochet behavior after updating still needs gameplay confirmation.

## 0.1.26 - Unf0reseen matching damage and pull areas

- Expand Unf0reseen's explosion damage radius to match its 2,000-unit (20-meter) pull radius. Preserve damage scaling, falloff, Shock effects and Death Mark behavior.

## 0.1.25 - Precision native radius type

- Fix the float-to-int conversion error when temporarily setting Precision's 30-meter ricochet radius. Both activation and restoration now write integer values, matching the native field.
- Test five consecutive critical-hit pulses and recovery after a failed pulse, with a mock that rejects floating-point writes like the engine.
- Preserve ricochet damage, class-mod scaling, target selection and recursion safeguards. Thirty-two focused tests passed; repeated ricochets still need confirmation in game.

## 0.1.24 - Be Like Water runtime availability

- Remove the requirement for the retired melee/ranged active skills to remain loaded. These definitions are only optional cleanup/icon sources; their absence no longer prevents movement stacks and HUD counters from initializing after a world refresh.
- Fix the stationary Damage bonus to target native Enemy allegiance rather than Friendly allegiance.
- Preserve stack values, timing, transitions, effective class-mod ranks and separate HUD slots. Thirty-seven focused tests passed; updated in-game movement and HUD behavior still require confirmation.

## 0.1.23 - Unf0reseen native parameter binding

- Bind GetBehaviorContext and the pull behavior's ApplyBehaviorToContext parameters by name. This addresses the UObject-to-WrappedStruct conversion error recorded while preparing the decoy explosion.
- Fix Unf0reseen's Death Mark target filter to resolve the native Enemy enum instead of requiring Friendly opinion 2.
- Preserve the existing damage/status scaling, pull radius and momentum, native Death Mark duration, class-mod ranks, formula restoration and travel/cancellation safeguards. Precision and other skills are unchanged.
- Replace permissive call mocks with keyword-only native-call contracts. Eighteen focused Unf0reseen tests passed; in-game confirmation after updating remains pending.

## 0.1.22 - Precision pawn reflection modifiers

- Set Precision's ricochet search radius to 30 meters from the struck enemy. Use the same radius for native reflection during the critical impact, then restore the previous native value. Preserve damage and all other skill effects.
- Remove the temporary skill activation dependency from Precision's critical-hit pulse. The 0.1.21 live log reported rejected activation; a follow-up snapshot showed valid helper class and constraints.
- Apply scoped native AttributeModifiers directly to the pawn's enemy-reflection chance and reflected-damage scale. Keep the same effective-rank progression and remove only these owned modifiers at impact cleanup.
- Preserve other reflection bonuses, native target selection, recursion limits and weak pawn/world validation. Clean up partial additions on failure. No skill-manager activation or asset lookup is performed per critical hit.
- Twenty-eight focused tests passed. These are simulated checks; reflected hits with this version still require in-game confirmation. No package generated or installed.

## 0.1.21 - Precision explicit pulse activation

- Replace Precision's graph ActivateSkill invocation with an explicit native Skill Manager activation at grade 1 after all critical-hit, owner and target guards pass. The live capture showed the graph call completing without creating an active or paused helper instance, leaving reflection chance at zero.
- Block the original graph activation to prevent duplicate execution. Keep the pulse scoped to the current impact and clean it up once after superclass/nested callbacks complete.
- Cache only the rooted helper definition; do not retain a live skill instance or look up assets on each critical hit. Skip activation while the manager is updating skills.
- Preserve damage progression, class-mod ranks, target radius and recursion guards. Twenty-six focused tests passed, including explicit activation, refusal cleanup, pulse lifetime and no per-hit asset lookup. In-game confirmation remains pending.

## 0.1.20 - Precision destination precheck

- Remove Precision's additional Python FastTrace veto. A live capture on 0.1.19 showed valid hostile pawns at approximately 603 and 779 units inside the native 1800-unit radius, but every extra trace returned false and prevented activation.
- Keep the bounded nearby-enemy check, native enemy allegiance, living-target/world/range checks, native reflection eligibility and recursion/cleanup safeguards. The game's reflection mechanism selects the actual destination.
- Preserve critical-hit requirements and all damage coefficients. No target-list scan on PlayerTick or new timer added; the extra trace calls are removed from the activation path.
- Twenty-two focused tests passed, including a regression where the extra trace returns false. Actual reflected hits after updating still require in-game confirmation.

## 0.1.19 - Precision enemy allegiance

- Fix Precision rejecting hostile ricochet targets: the old check used opinion 2, which is Friendly. Resolve the native Enemy enum during configuration instead of hardcoding a value.
- Preserve critical-bullet activation, damage progression, class-mod ranks, native reflection radius, visibility checks and recursion/cleanup safeguards.
- Correct the allegiance values in the focused tests and temporary diagnostic. Add regressions for Enemy 0, Neutral 1 and Friendly 2, including an allied pawn appearing before a valid enemy in the pawn list.
- Twenty-one focused tests passed. The live capture established the target-filter failure; ricochets after this fix still require confirmation in game. No package generated or installed.

## 0.1.18 - Precision impact timing

- Fix the Ricochet Damage footer inheriting the old accuracy presentation's forced-positive sign. Show the actual sign: negative below rank 5, zero at rank 5, positive above rank 5. Preserve damage coefficients.
- Fix Precision's reflection scope lifetime. A live capture recorded the critical activation behavior after AdjustDamage returned, when its former scope had already closed and the guard blocked every activation.
- Scope the complete pawn TakeDamage call and bind the actual pipeline during AdjustDamage. Check native reflection eligibility at the critical event, after pipeline initialization. Share one pulse across AIPawn/superclass calls and clean up once when the outer impact ends.
- Preserve rank/damage progression, critical-bullet filtering, native reflection policy, nearby-target safeguards and recursion limits. No per-frame actor scan or delayed cleanup timer added. Correct the enabled-version log.
- Eighteen focused Precision checks passed. Native ricochet confirmation after updating and restarting remains pending; no package generated or installed.

## 0.1.17 - Precision configuration and description

- Fix Precision's graph construction to use native BehaviorVariableLinkData2 for consolidated variable links. The legacy type expects an integer array instead of SubarrayData and caused the live configuration error before the ricochet description was applied.
- Restore the intended critical-bullet ricochet main description and Ricochet Damage footer. Preserve damage progression, class-mod ranks, critical checks and target/cleanup safeguards.
- Thirteen Precision checks passed, including native link-schema regression and restoration of overwritten descriptions. Native confirmation after updating and restarting remains pending. No package generated or installed.

## 0.1.16 - Skill configuration and Be Like Water HUD

- Fix Iron Hand's negative lower-description sign using native positive sign style. Preserve resistance coefficients, Maximum Health and class-mod scaling.
- Fix the missing-asset configuration blocker for Optics and Precision: create private attributes for verified native aim-time and bullet-reflection properties when the optional native attribute objects are unavailable. Be Like Water has equivalent fallbacks for movement and its damage display/source templates. Loading the shared attribute package alone did not resolve the live failure.
- Add two visual-only native Be Like Water counters, one for Movement and one for Damage, each showing 1-5 stacks independently of effective skill rank. Use native icons and reserve physical/remapped slots plus inactive tracked children. Hide feedback safely if all slots are occupied.
- Reuse existing maintenance for count changes/recovery, throttle failed activation and return after native callbacks. Preserve damage, movement, transitions and decay. Fifty-three focused/adjacent checks passed; native gameplay confirmation remains pending. No package generated or installed.

## 0.1.15 - Unf0reseen scaling and utility

- Add a linear bonus from +25% damage at effective level 1 to +175% at OP10 (stage 90), clamped at the endpoints. Scale the native direct-damage and Shock-status inputs without replacing global scaling or adding class-mod ranks twice.
- Initiate a zero-damage native pull before the decoy's damage call, using the original Converge radius and negative-momentum values. Preserve the decoy graph, original damage radius and Shock explosion.
- Record actual positive explosion hits and request the original Death Mark on surviving enemies if the skill remains learned. Refresh the native mark without stacking copies; preserve native duration and debuff effects.
- Reuse the shared skill cache, use bounded weak target records and restore temporary formulas/context on completion, cancellation, error, disable and travel. No periodic actor scans or added gameplay timer. Eighteen focused/adjacent checks passed; native gameplay and co-op remain unvalidated.


## 0.1.14 - Be Like Water generic damage

- Replace stationary Amp Damage with generic Damage affecting weapons, melee, grenades, status effects and owned skill-damage events attributed to Zer0.
- Preserve 2% per effective point per stack, five-stack limits, movement bonuses, transition timing and decay. Ambush's behind/unaware-target conditions are not added.
- Remove Be Like Water's temporary weapon-Amp firing hooks. Apply and clean a source-aware damage multiplier inside each native damage calculation, reusing cached definitions/modifiers and isolating nested foreign hits. Keep At One with the Gun Amp unchanged.


## 0.1.13 - At One with the Gun

- Preserve native Sniper Reload Speed and Magazine Size; remove Hip-Shot Accuracy and its old behavior graph/helper effects.
- Add a ten-hit charge using separate weapon shots. The next shot gains 20% Amp Damage per effective skill point, with any weapon. No stack timer; reset on travel, menu return or respec.
- Group nested firing wrappers and registered physical projectiles by shot. Do not count extra pellets, repeated registered-projectile impacts, the empowered shot, status ticks, grenades or melee. Limit weak-reference registries and skip unrecognized sources.
- Apply Amp in a temporary firing scope, clean it on cancellation/error/travel, and add it alongside Be Like Water Amp without multiplying the two bonuses. Actual native firing/projectile paths still require gameplay validation.


## 0.1.12 - Innervate

- Increase Gun Damage from 2% to 3% per skill point and Maximum Health regeneration from 0.8% to 1% per second per point during Decepti0n.
- Preserve native Movement Speed, constraints, HUD and class-mod scaling. Update both native healing gameplay and its lower-description coefficient; reuse the shared effect-cache refresh without adding polling hooks.


## 0.1.11 - Precision rework

- Replace Accuracy with critical bullet ricochets using native reflection. Damage progresses from 60% at rank 1 to 100% at rank 5, then gains 10 percentage points per effective rank above 5.
- Require another valid nearby enemy within the native reflection radius; skip missing, dead, friendly, obstructed or invalid targets. Bound target searches and cache their results briefly.
- Scope the reflection helper to one damage calculation, reject nested activations and clear pending state on travel or disable. Native event ordering and actual ricochets still require in-game validation after restarting.


## 0.1.10 - Be Like Water rework

- Replace the original shooting/melee bonuses with Movement Speed stacks while moving and Amp Damage stacks while stationary. Each stack grants 2% per effective skill point; each mode has a five-stack limit and gains a stack every 0.5 seconds.
- On a state change, immediately remove one previous-state stack. Then remove another every 0.5 seconds as the new bonus builds. Both bonuses remain effective for their remaining stacks during transitions; reversing state preserves remaining stacks.
- Use an untracked native movement helper and paired firing scopes for temporary Post-Add Gun Damage. Preserve class-mod scaling, prevent duplicate Amp through nested firing wrappers, and remove temporary modifiers on completion, failure, travel and disable.
- Remove the old damage events, graph and gameplay helper effects. Reuse shared skill snapshots; stable stacks do not rewrite movement modifiers and firing does not scan skills.
- Nineteen focused checks passed, including adjacent Kill Confirmed/Like the Wind cache behavior. Gameplay and co-op validation remain pending; no package generated or installed.

## 0.1.9 - Like the Wind damage avoidance

- Replace the original Gun/Melee Damage bonuses with 5% chance per effective rank to ignore incoming damage while moving (25% at 5/5), without an internal cooldown. Disable the legacy melee helper and graph.
- Retain native movement/on-foot constraints, menu icon and reserved HUD slot 5. Add a native rank-aware chance description; no Canvas icon, additional HUD slot or HUD polling.
- Use one incoming-damage roll with a weak skill reference from the shared cache. Reject stationary, invalid, stale, paused and non-authoritative contexts without scanning skills per hit.
- Eleven focused checks passed. Gameplay, HUD appearance and co-op still require in-game confirmation.

## 0.1.8 - Optics rework

- Replace original Zoom and aim-disruption effects with 10% Accuracy, 12% Recoil Reduction and 10% Aim Speed per effective skill point. Aim Speed uses the native attribute also used by Expertise; no Axton module dependency is added.
- Add three native rank-aware description lines and update the main description. Reuse the shared live-effect cache to remove obsolete modifiers, with no additional polling or combat hooks.
- Five focused checks passed; in-game confirmation remains pending.

## 0.1.7 - Resurgence healing on all kills

- Remove the melee requirement from Resurgence's native healing trigger. Any enemy kill now qualifies, preserving the original health restoration formula and native graph.
- Keep critical-hit shield recovery unchanged at 4% Maximum Shield per effective rank. Update the main description and Mod Manager summary; no new polling or kill hooks.
- Fourteen focused checks passed, including unchanged shield recovery and adjacent cache stability. In-game confirmation remains pending.

## 0.1.6 - Many Must Fall kill trigger

- Remove the melee damage-source requirement from Decepti0n's native Many Must Fall kill event. Any enemy kill during active Decepti0n can trigger the original decoy, re-stealth and duration behavior.
- Update skill and feedback descriptions. Preserve the native allocation/active-skill checks, event dispatch, damage events and graph; no extra kill hooks or polling.
- Six focused checks passed. In-game confirmation remains pending.

## 0.1.5 - Velocity

- Remove Velocity Critical Hit Damage and its description line. Increase Gun Damage from 2% to 5% per effective rank, preserving Bullet Speed and native class-mod scaling.
- Reuse the existing live-effect cache to remove obsolete critical modifiers on refresh; no new periodic checks or combat hooks. Five focused checks passed; in-game validation pending.

## 0.1.4 - Kill Confirmed stack timing

- Gain one stack every 0.25 seconds while aiming. After unzooming, lose one stack every 2 seconds instead of clearing all stacks immediately. Returning to aiming cancels pending decay.
- Preserve native Critical Hit Damage, five-stack maximum, class-mod scaling and stack HUD. Reuse the shared rank snapshot; apply native stack changes only when the count changes.
- Eleven focused checks passed, including timing, re-aiming, travel, callback invalidation and adjacent cache behavior. In-game confirmation remains pending.

## 0.1.3 - Resurgence critical-hit shield recovery

- Preserve original melee-kill healing. Critical hits also restore 4% Maximum Shield per effective skill point (20% at 5/5), including class-mod points, without an internal cooldown.
- Add native current/next-rank shield-recovery text without changing shield capacity. Use the native critical-hit event and the existing shared rank cache; avoid per-hit skill scans and redundant shield writes.
- Twelve focused offline checks passed. In-game validation remains pending.

## 0.1.2 - Fearless full-shield condition

- Change Fearless from depleted shields to full shields, preserving Gun Damage, Fire Rate, native class-mod ranks, HUD and remaining constraints.
- Use a native current-versus-maximum shield comparison with minimal float tolerance; no new gameplay polling or modifier rebuilds. Update the main description.

## 0.1.1 - Grim cooldown rate

- Increase Grim Cooldown Rate from 1.5% to 12% per effective rank (60% at rank 5). Preserve both shield-regeneration rows, native kill trigger, duration, constraints and native presentations.
- Reuse shared equipment/rank cache refresh for both changed skills. Ignore presentation-only rows when reconciling live gameplay effects, preserve optional metadata rows and keep native kill-skill state unchanged.
- Retry configuration independently per skill so a streamed/missing Grim asset does not block Iron Hand or cause repeated configuration of completed skills.
- Twenty-four exclusive Zer0 tests passed, plus syntax and metadata checks. In-game/co-op validation remains pending; no archive generated or installed.

## 0.1.0 - Iron Hand initial implementation

- Add the Python entry point and modern SDK Mod Manager metadata for Zer0Rebalance, an independent module by Kgx37b9.
- Replace Iron Hand Melee Damage with 5% native Damage Resistance per effective skill point. Preserve the original Maximum Health bonus, constraints, icon and tree position.
- Replace the lower-description Melee Damage line with Damage Reduction using the native rank, percentage and color handling.
- Support native class-mod ranks and refresh live effect caches on equipment/rank/context changes. Avoid repeated modifier writes when the state is stable; no combat or per-frame actor scans.
- Retry streamed assets on Zer0, configure before native skill-tree initialization, and clear primitive cache identities on travel, disable and context changes. Native definition changes require restart to remove.
- Sixteen Zer0-only tests passed, with syntax and metadata checks. Gameplay/co-op validation remains pending. No package generated or installed.

## Unreleased — Project documentation

### 2026-11-12

- Create the initial Zer0 Rebalance documentation: README, changelog, development notes and license.
- Identify Kgx37b9 as the author and apply the workspace's personal-use, permission-required licensing policy.
- Establish the module as an independent character project with no implemented skill changes, Python entry point or installable package yet.
- Record the project in the workspace index and central knowledge guide.

No gameplay, balance or compatibility changes are included in this documentation stage. A release version will be assigned when the first playable implementation is prepared.
