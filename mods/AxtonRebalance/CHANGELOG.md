# Changelog

## 1.1 - Forbearance status resistance and area life steal

- Restore Forbearance's native 8% reduction to enemy elemental status duration per effective point. Do not restore its former Maximum Health bonus.
- Replace turret-dependent life steal with 1% Life Steal per point from Axton's own explosive or area damage, without requiring a deployed turret. At 5/5: 40% shorter status duration and 5% Life Steal.
- Allow explosive damage from either of Axton's own Sabre Turrets to heal him at the same rate. Non-explosive turret damage and other players' turrets remain excluded.
- Preserve Health-only recovery, effective class-mod ranks and reentrancy protection. Ally damage, ordinary non-explosive direct hits and non-radial status ticks do not trigger recovery.
- Detect non-explosive area hits through native radius-damage calls, binding the actual damage pipeline and cleaning up after native calls or travel. A hit qualifying as both explosive and area damage heals only once. No new polling timer or per-hit asset/skill searches.
- Update Mod Manager metadata, descriptions and startup diagnostics to 1.1. In-game confirmation of the new damage filter remains pending.

## 1.0 - Initial public release

- Final balance adjustment: increase Nuke's turret weapon damage bonus from 200% to 250%. Preserve the 25% Fire Rate penalty and separate explosion/status damage progression.
- Publish the current Axton skill and Sabre Turret rebalance as version 1.0, including Kill Mastery, class-mod support, native HUD indicators and the latest balance and stability adjustments.
- Align Mod Manager metadata, README and startup diagnostics with the release version. Refresh the menu description for the current Overload, Metal Storm and Pressure effects. No gameplay changes in this release-label update.
- Earlier numbered entries below preserve internal development labels; they are not public releases after 1.0. See README.md for the current balance values and DEVELOPMENT.md for validation details.

## 1.0.7 - Healthy regeneration

- Avoid repeated native object lookups for turret damage and Nuke knockback within the same update pass. Keep late-asset retries and baseline checks between passes.
- Harden Metal Storm's pending-shot cleanup with a weak reference to the original world, preventing writes after a world change or address reuse.
- Increase Laser Sight's Turret Damage from 4% to 6% per point, keeping Turret Fire Rate at 4% per point. Reduce Quick Charge's shield regeneration from 1.5% to 1.2% per second per point; keep Reload Speed at 8% per point.
- Increase Quick Charge's shield regeneration to 1.5% maximum shield per second per effective point. Replace its Damage Resistance with 8% Reload Speed per point while active; retain native kill-skill timing, class-mod ranks and Kill Mastery scaling.
- Pressure now grants its full 7% Damage per effective point whenever shields are above zero. Remove the shield-fullness damage curve; preserve missing-shield recharge-delay scaling and the damage bucket shared with Crisis Management.
- Preparation's native Damage Resistance now scales proportionally with shield fullness, from zero at empty shields to 30% per effective point at full shields. Preserve the fixed 7% Shield Capacity per point. Its native HUD condition now covers any positive shield value.
- Replace Metal Storm's Reload Speed bonus with a 6% chance per effective point not to consume ammunition while the kill skill is active (30% at 5/5). Preserve native Fire Rate, kill activation and duration. Kill Mastery strengthens the chance, capped at 100%.
- Increase Overload's Magazine Size to 10% per point and add native reserve ammunition regeneration at 0.2% of maximum capacity per second per effective point for all six weapon categories. At 5/5: +50% Magazine Size and 1% reserve regeneration per second. Preserve normal shot consumption.
- Increase Nuke's turret weapon damage bonus to 200%, preserving its 25% Fire Rate penalty and separate blast/status scaling.
- Double Up now marks enemies for 25% extra damage for 10 seconds and reduces turret weapon damage by 40%. Cooldown Rate remains +25%.
- Increase Ranger's Amp Damage to 10% per point; Fire Rate remains 5% per point.
- Remove Overload's chance to consume no ammunition and its firing hooks. Retain 8% Magazine Size per point for all weapons.
- Fix Duty Calls accessing Actor-only fields on non-Actor damage causers such as MeleeDefinition. Validate the registered shot source and weak identity first; retain aimed-shot counting and delayed projectile support.
- Reduce Able's regeneration from 0.5% to 0.4% maximum health per second per effective point per stack. Keep five independent 3-second stacks and native trigger timing: 10% per second at 5/5 with five stacks. Version unchanged by request.
- Increase Resourceful's internal incoming-damage cooldown-recovery interval from 0.5 to 1 second. Keep this interval hidden from the skill description; preserve recovery amount and kill-based turret extension. Version unchanged by request.
- Reduce Healthy's passive health regeneration from 0.75% to 0.6% maximum health per second per effective point. Preserve doubling while shields are depleted, Maximum Health and class-mod scaling. At 5/5: 3% per second normally, 6% with depleted shields.

## 1.0.6 - Pressure low-shield damage curve

- Polish Pressure's main description with standard skill highlighting and clearer English, retaining only the existing shield-dependent recharge-delay and damage information.
- Simplify Pressure's main description to the author's supplied wording and remove the word "multiplicative" from Crisis Management's main description. Keep numeric footers and gameplay unchanged.
- Add a damage-curve anchor at 1% shield: +2% damage per effective point (+10% at 5/5). Interpolate from zero at empty shield to this anchor, then to the unchanged +7% per point at 70% shield (+35% at 5/5), capped above that.
- Preserve the 24% per-point maximum recharge-delay coefficient, class-mod scaling and the additive bucket shared with Crisis Management. Update skill wording and documentation; no new hooks, lookups or native writes.
- Twenty-one Pressure tests passed, including partial shields, both anchors, effective ranks, source composition and cleanup. Gameplay confirmation remains pending; no package generated or installed.

## 1.0.5 - Pressure damage and shield curve

- Remove Pressure's movement-speed bonus. Add 7% damage per effective point, scaling linearly from zero at empty shield to maximum at 70% shield; keep the maximum above that threshold. Zero-capacity shields grant no Pressure damage.
- Pressure adds to Crisis Management in a shared damage bucket, which multiplies independently with Last Ditch Effort, Double Up and other damage sources. Reuse the existing damage scope and rank snapshot, without additional periodic hooks or per-hit skill lookups.
- Increase maximum Shield Recharge Delay reduction from 15% to 24% per point. Preserve its native missing-shield curve: maximum effect at empty shield, zero at full shield. Update descriptions, effective-rank previews and menu metadata.
- Fifty-six focused/adjacent checks passed. Gameplay confirmation remains pending after updating and restarting. No SDKMOD generated or installed.

## 1.0.4 - Crisis Management multiplicative damage

- Reduce native damage resistance from 8% to 6% per effective skill point. Replace additive gun damage with a separate 5% damage multiplier per point while shields are depleted (+25% at 5/5).
- Reuse the existing damage scope and shared rank snapshot; preserve class-mod scaling, source ownership, nested-hit cleanup, travel safeguards and native shield conditions. Compose independently with Last Ditch Effort and Double Up. No additional periodic hook or Ambush dependency.
- Update the skill text and menu metadata. Focused configuration and damage-pipeline checks passed; native gameplay confirmation remains pending. No package generated or installed.

## 1.0.3 - Duty Calls stack pacing

- Reduce the stack limit from 40 to 20 and double the bonuses per stack per skill point to 0.5% Critical Hit Damage and 0.4% Reload Speed. Preserve the maximum +50%/+40% at 5/5 and class-mod scaling.
- Increase the initial decay grace period from 1 to 3 seconds without aiming. Continue losing one stack every 0.25 seconds afterward. Update the native HUD count limit, descriptions and menu metadata.
- Twenty-two focused configuration/runtime/HUD checks passed; gameplay confirmation remains pending. No package generated or installed.

## 1.0.2 - Duty Calls aimed-hit stacks

- Replace reload-based stacks with one stack per successful weapon shot while aiming down sights, up to 40. Each stack grants 0.25% Critical Hit Damage and 0.2% Reload Speed per effective skill point (+50%/+40% at 5/5 with 40 stacks).
- After 1 second without aiming, lose one stack every 0.25 seconds. Aiming pauses decay and resets the grace period. Preserve effective class-mod ranks and the separate native HUD counter.
- Deduplicate firing wrappers and associated projectile pellets, ignore non-weapon damage and use existing quarter-second maintenance for effect/HUD updates. Native gameplay validation is pending after restarting.

## 1.0.1 - Resourceful kill extension

- Replace duration extension on damage with 1 second per effective skill point per credited enemy kill (5 seconds at 5/5). Remove the per-deployment extension limit and its lower-description line. Sentry's native duration remains unchanged; Gemini shares one extension per kill.
- Preserve the incoming-damage cooldown reduction and its internal interval. Use the native player-pawn kill event and existing weak action-skill reference/rank cache, removing extension processing from the damage pipeline.
- Fix the initial extension trigger: an in-game capture recorded nine `WillowPlayerPawn:KilledEnemy` calls but no `IncrementPlayerKillStat` calls. Use only the observed player-pawn event, with local pawn ownership checks; no statistics dependency, extra polling or damage-based kill inference.
- Pending Mag-Lock refunds follow actual subsequent extensions rather than assuming a maximum duration budget. Forty-one focused checks passed, including the captured event signature. Confirmation of the correction in gameplay remains pending.

## 1.0.0 - Initial release

- Prepare release metadata and Mod Manager description for AxtonRebalance 1.0 by Kgx37b9.
- Overload retains 8% Magazine Size per point and adds 4% chance per point to consume no ammo per shot (20% at rank 5), for all weapons. Effective class-mod ranks apply, capped at 100%. One roll covers nested firing calls and extra pellets, including failed rolls. Temporary zero cost and paired cleanup preserve the magazine without reserve manipulation or passive generation.
- Add current/next-rank chance to Overload's lower description, retaining native Magazine Size text and number colors. Reuse shared rank maintenance; no new polling or per-shot skill scans. Preserve Ranger's last-round and reload behavior.
- Increase Gemini's defensive aura radius from 12 to 20 meters; preserve strength, team targeting, non-stacking behavior and HUD indication. Derive its displayed radius and startup summary from the gameplay constant.
- Remove the lower-description line "Enemy Attention: Increased" from Mag-Lock. Preserve aggro, native attachment, faster throwing, destruction refund and the main description.
- Consolidate the README into current skill changes, requirements, installation, compatibility, credits and license. Retain development history and validation details in CHANGELOG.md and DEVELOPMENT.md.
- Preserve the runtime optimizations and balance from 0.3.3. Co-op and final in-game checks remain outstanding; no package generated or installed in this preparation step.

## 0.3.3 - Runtime audit and redundant-call reduction

- Ranger reuses a weak reference to its private Amp modifier for the current empowered magazine. Avoid repeated object/enum lookups per shot, while preserving current-damage calculation, nested-shot guards and immediate modifier removal.
- Forbearance rejects zero/invalid final damage before player/resource queries. At full Health, skip turret, target-opinion and damage-type checks; preserve every eligible healing event without a new cooldown.
- Resourceful rejects zero/invalid incoming damage before player queries while keeping paired damage frames balanced. No shield timer or native attack behavior changes.
- Deduplicate runtime errors by operation and exception type, retaining the first full error detail without growing a per-actor message cache. Correct Double Up's diagnostic factor to reflect its actual current value.
- Ninety-nine distinct focused/adjacent checks passed, including travel, HUD allocation, modifier cleanup, nested damage and class-mod-grade behavior in the affected features. Updated an outdated Double Up/Last Ditch test expectation to match the existing 8%-per-rank balance.
- No new polling, balance changes or package generated/installed. In-game performance measurement and co-op validation remain pending.

## 0.3.2 - Pressure and Forbearance tuning

- Increase Pressure's maximum Shield Recharge Delay reduction coefficient from 12% to 15% per rank (75% at rank 5). Preserve native delay calculation, missing-shield scaling and Movement Speed.
- Reduce Forbearance Life Steal from 0.5% to 0.4% per rank (2% at rank 5). Keep own-damage-only healing while a living turret is active, without an internal cooldown or Shield recovery.
- Update descriptions, startup summaries and metadata. Focused tests passed; in-game confirmation is pending. No package generated or installed.

## 0.3.1 - Ranger partial-reload cleanup

- Observe native BeginReload in addition to StartReload when ending an empowered magazine.
- A successful partial reload explicitly retires any remaining Ranger bonus and HUD before processing Ready and Duty Calls. It cannot preserve or reactivate the previous empowered magazine if the start notification was missed.
- Preserve empty-reload activation, duplicate-event protection, class-mod ranks and all damage values. Busy skill managers defer native helper cleanup to existing maintenance while the Amp state is cleared immediately.
- Seventy focused and adjacent checks passed. Confirm the partial-reload fix in game after restarting; no package generated or installed.

## 0.3.0 - Damage tuning and Forbearance life steal

- Ranger: increase Amp Damage from 7% to 8% per rank (+40% at rank 5); retain Fire Rate and empowered-magazine behavior.
- Last Ditch Effort: increase multiplicative damage from 6% to 8% per rank (+40% at rank 5), preserving the below-50%-health condition and eligible damage sources.
- Laser Sight: add 4% turret weapon damage per rank and reduce turret Fire Rate from 5% to 4% per rank (+20% each at rank 5), preserving native accuracy and turret targeting. Repair existing fire-rate effects during migration rather than adding duplicates.
- Replace Forbearance turret life/shield steal with 0.5% Life Steal per rank from Axton's own enemy damage while a living Sabre Turret is deployed (2.5% at rank 5). Exclude turret damage, remove the recovery cooldown, and restore only Health. Either Gemini turret qualifies without stacking the effect.
- Preserve the shared final-damage callback and cached effective grade; no new periodic hooks or global actor searches. Guard reentrant healing and reject stale contexts, travel, invalid damage and FFYL.
- Focused and adjacent tests passed; in-game confirmation remains pending. No package generated or installed.

## 0.2.59 - Preparation and Pressure tuning

- Increase Preparation Shield Capacity from 5% to 7% per rank (+35% at rank 5), preserving its full-shield resistance.
- Reduce Pressure's maximum Movement Speed from 12% to 10% per rank (+50% at rank 5). Missing-shield scaling and maximum Shield Recharge Delay reduction of 12% per rank remain unchanged.
- Focused Preparation and Pressure checks passed; in-game confirmation is pending. No package generated or installed.

## 0.2.58 - Pressure missing-shield bonuses and Phalanx Shield

- Replace Pressure's shield-capacity/health tradeoff with Movement Speed and Shield Recharge Delay reduction, both scaling with missing shields up to 12% per rank (+60% movement / -60% delay at rank 5). Full shields grant zero; depleted shields grant maximum strength. Replace weapon Reload Speed with Movement Speed.
- Use private native initializers with bounded fractions and a safe denominator for zero-capacity shields. No additional Python polling; class-mod grades apply once. Keep current/next-rank tooltip colors and show maximum values.
- Increase Phalanx Shield's passive player Shield Capacity from 10% to 20%; preserve the 70% turret barrier capacity increase.
- Thirty-three focused and adjacent tests passed. In-game confirmation is pending; no package generated or installed.

## 0.2.57 - Ready fire rate and Ranger tuning

- Ready: replace the post-reload movement bonus with5% Fire Rate per effective rank for6 seconds (+25% at5/5). Preserve the passive8% Reload Speed per rank, refreshing/no-stacking behavior and active HUD icon. Migrate the old movement effect/presentation through the stable helper path.
- Ranger: increase magazine Amp Damage from6% to7% and Fire Rate from4% to5% per rank (+35%/+25% at5/5). Preserve the empty-reload trigger, magazine lifetime, normal HUD and all cleanup rules.
- Update current descriptions, metadata and expected modifier values. Targeted tests passed; native gameplay confirmation pending.

## 0.2.56 - Duty Calls reload stacks and Ready

- Duty Calls now gains one stack per completed reload, up to five. Each stack grants 2% Critical Hit Damage and 2% Reload Speed per effective rank (+10%/+10% per stack at5/5; +50%/+50% with five stacks).
- Successful empty and partial reloads refresh a shared15-second duration, including at the cap. All stacks expire together; damage/critical generation and gradual decay are removed. Keep the native HUD stack counter and slot allocation.
- Reuse the existing validated ReloadDone event and shared maintenance. Recheck allocation/context after Ready callbacks, reject same-frame duplicate completion, and remove the old per-damage consumer.
- Ready: increase movement from5% to6% per rank (+30% at5/5), retaining the five-second refreshing duration and passive reload bonus.
- Current descriptions, metadata and manual Duty Calls probe updated.117 distinct targeted/adjacent cases passed across the affected runs; native gameplay confirmation pending.

## 0.2.55 - Ranger magazine rework and Overload

- Ranger: completing a reload from an empty magazine empowers that magazine with 6% Amp Damage and 4% Fire Rate per effective rank (+30%/+20% at5/5). No time limit; the bonus ends on depletion, a new reload or weapon switch.
- Remove Ranger hit stacks, per-target shot tracking, projectile/firing-group caches, kill extensions, recovery delay and icon color transforms. Keep the normal menu icon in a non-overlapping native HUD slot only while the empowered magazine is active, with no counter.
- Preserve scoped Post-Add Gun Damage, including the final round, paired firing callbacks and class-mod grades. Capture empty-reload eligibility before native ReloadDone resets its fields; failed/partial reloads do not activate Ranger.
- Overload: increase all-weapon Magazine Size from5% to8% per rank (+40% at5/5), remove passive magazine regeneration and its footer, and delete ammo-generation/repair routines and fractional state. Existing shared combat maintenance remains for the other skills and performs no ammo polling or writes.
- Update descriptions, metadata, regression checks and the manual Ranger probe. Restart after updating; native gameplay confirmation pending.

## 0.2.54 - Balance pass

- Ranger: Amp Damage increased from 7% to 10% per rank (+50% at 5/5).
- Last Ditch Effort: multiplicative damage increased from 5% to 6% per rank (+30% at 5/5), retaining the below-50%-health condition.
- Duty Calls: each stack now grants 0.4% Critical Hit Damage and 0.5% Reload Speed per rank (+40%/+50% at 5/5 with20 stacks).
- Healthy: Maximum Health increased to 5% per rank and passive regeneration to 0.75% maximum health/s per rank; regeneration still doubles with depleted shields. At5/5: +25% Maximum Health,3.75%/s regeneration or7.5%/s depleted. Footer precision supports0.75% without rounding it to0.8%.
- Forbearance: turret life/shield steal increased to1% per rank (5% at5/5); health-first recovery and the shared interval remain unchanged.
- Battlefront: Critical Hit Damage increased from4% to5% per rank (+25% at5/5); other effects remain unchanged.
- Preserve all triggers, duration limits, HUD behavior and effective class-mod scaling. Update current README/menu descriptions and startup logs; correct Ranger's diagnostic duration to use its existing constant.

## 0.2.53 - Kill Mastery

- Rename Boost to Kill Mastery, preserving its tree position, icon and saved definition path.
- Reduce Kill Skill Duration from 20% to 10% per point (+50% at 5/5).
- Add 5% relative Kill Skill Bonus Strength per point (+25% at 5/5) to Onslaught, Metal Storm and Quick Charge, including the current Quick Charge regeneration/resistance effects. Preserve native formulas, trigger conditions and effective class-mod ranks.
- Native source-state constraints gate private passive helpers; no duplicate kill-skill icons, fake kills or new periodic hooks. Fifty-nine targeted/adjacent tests passed; gameplay confirmation pending.

## 0.2.52 - Repeated Bee recharge audio

- Prevent duplicate The Bee full-shield recharge cues for the local Axton while the shield remains full. Keep the first notification and rearm after shield damage or an observed real deficit.
- Preserve shield/Amp gameplay and other sounds. Scope the filter to the exact native recharge sound behavior and equipped-owner context; reset on travel and player/world changes.
- Reuse existing damage and quarter-second maintenance hooks. No recurring audio scan or additional tick hook. Fifty-two focused/adjacent checks passed; in-game confirmation pending.

## 0.2.51 - Double Up balance

- Increase the marked enemy's damage taken bonus from 15% to 20%, and the turret weapon damage penalty from 25% to 35%. Preserve the 8-second refreshing team debuff and passive 25% Cooldown Rate.

## 0.2.50 - Ranger duration

- Increase Ranger's reload bonus duration from 6 to 8 seconds. Each kill still adds 2 seconds, now up to 16 seconds total per activation (four extensions). Preserve damage, fire rate, HUD and stack rules.

## 0.2.49 - Healthy passive regeneration

- Healthy now passively regenerates 0.6% Maximum Health per second per effective rank, doubled with depleted shields. Preserve 4% Maximum Health per rank and class-mod support; remove the turret-deployment requirement.
- Native shield-state evaluation replaces the deployment condition, without a new polling or healing timer. Show fractional regeneration values in the footer.

## 0.2.48 - Recent-feature stability and repeated-check audit

- Fix Mag-Lock initialization when the game's native threat attribute is unavailable: create a private Pawn-context attribute for the same verified TargetPriority property. Reuse it on subsequent initialization; no AI package loading or polling is required. Turret attention remains +3.
- Deduplicate successful turret-health verification across the two existing deployment events for the same player/world within 0.25 seconds. Missing assets retry immediately, and initialization/new worlds still validate afresh.
- Roll back our turret/Longbow health changes if the second native write is rejected or fails after changing its value. Preserve unrelated starting values changed in the meantime.
- Guard Boost configuration against native reentry and reread/revalidate the branch/layout after loading icon assets, before writing any skill cell.
- Seventy-one focused/adjacent checks passed. The live log confirms Boost's inclusion in the tree; Mag-Lock's new fallback and the new safeguards remain to be confirmed in native gameplay. No balance changes or new per-frame hooks.

## 0.2.47 - Resourceful extension budget per rank

- Resourceful's maximum additional turret duration now scales by 4 seconds per effective rank: 4 seconds at 1/5, 20 at 5/5 and 40 at 10/5. Preserve 0.1 seconds per hit per rank, incoming-damage cooldown reduction, native triggers and Sentry's separate duration.
- Display Maximum Extra Duration as a rank-scaled lower stat, including previews and class-mod ranks. Both Gemini turrets still share one deployment budget.
- Equipment changes preserve already spent/granted duration. A lower rank blocks further extension if the budget is already exceeded; a higher rank unlocks only the remaining budget.
- Adjust Mag-Lock's deferred-refund expiry for the rank-scaled budget and accept valid Resourceful-shifted start times beyond the current timestamp. Expired/dead action skills remain excluded.
- Fifty-six focused/adjacent checks passed, including dynamic rank limits, equipment changes, timing precision, refunds and the shared damage POST. Native gameplay confirmation remains pending.

## 0.2.46 - Redistribute Longbow turret health into base health

- Increase Sabre Turret's native class health multiplier by 40% (3.0 to 4.2), while reducing Longbow's own Turret Health bonus from +110% to +50%.
- Preserve the combined health total with Longbow: 1.40 x 1.50 = 2.10, matching the previous 1.00 x 2.10. Turrets without Longbow gain the base increase; native level scaling and deployment range are unchanged.
- Apply detached class starting values and the native Longbow constant together after validation. Retry late assets only through existing deployment events; no new per-frame queries or writes to live turret health. The native lower description reads the updated 50% constant.
- Nine focused/adjacent checks passed, including idempotence, combined-health equivalence, invalid/missing data, rejected base writes, late assets and unchanged deployment descriptions. Native confirmation with newly deployed turrets remains pending.

## 0.2.45 - Restore Pressure capacity and health values

- Restore Pressure to +15% Shield Capacity and -7% Maximum Health per rank (+75%/-35% at 5/5). Preserve depleted-shield recharge delay and other skill behavior. Update current descriptions and metadata; three focused rank/preview checks passed.

## 0.2.44 - Boost passive skill

- Add Boost (provisional name) in Guerrilla tier 4, to the right of Grenadier, with five ranks and +20% Kill Skill Duration per rank (+100% at 5/5).
- Use a private controller attribute targeting the native KillSkillDurationMultiplier property with additive modifiers, following the engine mechanism used by Krieg's duration class mods. Preserve native elimination triggers and other duration bonuses; custom non-kill timers remain unchanged.
- Reuse Gaige's Unstoppable Force menu icon. Load its compatibility asset only during tree construction if needed; do not edit the source skill or require a separate character mod.
- Use a stable private skill path, preserve neighbors/unlock costs and validate the free right-hand cell. Prepare before native skill-tree initialization and verify the live tree afterward. No combat hooks, new HUD slot or periodic updater added.
- Thirteen focused/adjacent checks passed, covering rank scaling, controller resolver, icon loading/failure, idempotence, conflicts and existing tree rotations. Native confirmation remains pending; no package generated or installed.

## 0.2.43 - Skill balance pass

- Gemini: increase aura radius from 8 to 12 meters and Damage Reduction from 25% to 50%; overlapping auras still do not stack.
- Pressure: reduce Shield Capacity to 12% per rank and Maximum Health penalty to 6% per rank (+60%/-30% at 5/5). Depleted-shield recharge delay remains unchanged.
- Forbearance: increase turret life/shield steal to 0.6% per rank (3% at 5/5), keeping health priority and its shared interval.
- Healthy: reduce Maximum Health to 4% per rank (+20% at 5/5); turret-dependent regeneration remains unchanged.
- Nuke: reduce turret weapon damage bonus to +100% and Fire Rate penalty to -25%. Nuclear blast/status progression remains unchanged.
- Last Ditch Effort: apply its existing damage bonus below 50% enemy health instead of below 30%. Exactly 50% does not qualify.
- Update current descriptions, logs and manager metadata. Twelve focused checks passed; new values still need native gameplay confirmation.

## 0.2.42 - Healthy maximum health adjustment

- Reduce Healthy's Maximum Health bonus from 6% to 5% per effective rank (+25% at 5/5). Preserve turret-dependent health regeneration and native class-mod scaling. Update current descriptions and metadata; two focused configuration checks passed.

## 0.2.41 - Explicit fast-travel buff reset

- End owned temporary Ready, Ranger, Duty Calls, Able and turret-dependent helper effects before fast travel, in addition to clearing their Python state. Clear pending stacks, duration-extension/refund state, partial magazine-regeneration progress and temporary HUD feedback.
- Reset the native kill-skill timer and call WillowPlayerController.ForceKillSkillsOff without removing allocated skills or passive bonuses.
- Mark departure before callbacks can reactivate gameplay. Reacquire the live player/manager after every native cleanup call; never inspect a retained ActiveSkills snapshot. Busy/refused cleanup retries through the existing maintenance pass using only the current context. Destroyed does not inspect old buff instances.
- Thirteen focused/adjacent cleanup checks passed. No new per-frame hook or polling loop. Native confirmation after fast travel remains pending; no package generated or installed.

## 0.2.40 - Stability and repeated-query audit

- Check existing tick intervals before resolving the local player in turret damage maintenance, Gemini and shared combat passives. Foreign controller ticks still cannot consume local timers.
- Reject unrelated damage before player queries in the shared damage POST; Forbearance also rejects impacts inside its shared interval before querying player resources.
- Revalidate weapon, pool, owner, pawn and world after native ammo-pool updates. Overload no longer credits an old magazine if a callback changes the weapon or gameplay context.
- Allow Mag-Lock's damage-death refund when the native skill's optional CachedActionSkill reference is empty, while retaining verified pawn-action/turret ownership and rejecting conflicting references.
- Ninety-two targeted/adjacent checks passed offline. No balance, HUD position or new polling changes; gameplay performance and co-op still require native validation.

## 0.2.39 - Ranger red highlight and recovery interval

- Replace the active Ranger HUD tint with the red transform used by Bloodlust in KriegRebalance. Preserve alpha, original icon, slot ownership, fades and counter behavior.
- Block new stacks for 0.5 seconds after the reload bonus ends, including kill-extended activations. Natural expiry uses the actual deadline rather than restarting the interval on each maintenance pass. Rejected shot groups cannot count later through extra pellets.
- No new hooks, timers or per-hit skill scans. Update current documentation; native confirmation of the new tint and interval remains pending.

## 0.2.38 - Ready, Ranger and Forbearance balance

- Ready's movement bonus now lasts 5 seconds after reloading, up from 3; further reloads still refresh without stacking.
- Ranger now grants 5% Fire Rate per effective rank (+25% at 5/5). Remove Required Hits from the lower description; keep the ten-hit requirement in the main description and gameplay.
- Forbearance now steals 0.5% of turret damage per effective rank (2.5% at 5/5), preserving health-first recovery and the shared 0.25-second interval.
- Update current descriptions and manager metadata. Native gameplay confirmation of these values remains pending.

## 0.2.37 - Forbearance turret life and shield steal

- Replace critical-hit shield restoration with 0.4% of owned Sabre Turret damage recovered per effective rank (2% at 5/5). Restore Health first; overflow restores Shield only once Health is full, capped at capacity.
- Share a hidden 0.25-second interval between both recovery pools and Gemini turrets. Full resources do not consume the interval. Killing hits remain eligible; other players' turrets, friendly targets, healing and zero-damage events are excluded.
- Reuse the existing damage POST and quarter-second rank snapshot; no additional hook, actor scan or per-hit skill lookup. Reserve the interval before native writes and re-resolve the player after health callbacks.
- Update the skill description and manager metadata. Offline validation passed; native gameplay and co-op confirmation remain pending. Restart after replacing the mod. No package generated or installed.

## 0.2.36 - Duty Calls critical damage and reload speed

- Replace the stacking Fire Rate bonus with Reload Speed and increase Critical Hit Damage. Each stack now grants 0.25% Critical Hit Damage and 0.35% Reload Speed per effective rank: +25%/+35% at rank 5 with 20 stacks.
- Update parent presentation effects and the actual gameplay helper, including a positive Reload Speed display using the native inverse presentation. Preserve fractional precision, the existing HUD, trigger ownership, two stacks on critical hits, 20-stack limit and decay timing.
- Accept the original and previous critical/fire-rate layouts for migration; repeated configuration does not duplicate or compound effects. Class-mod ranks remain applied once.
- Twenty-three focused/adjacent checks passed. Restart after replacing the mod to retire the previous active helper. Native confirmation of the new bonuses remains pending. No package generated/installed.

## 0.2.35 - Softer Ranger highlight

- Lighten Ranger's active-bonus base color from #43517D to #7898BE, retaining the corrected byte-unit offsets and 0.20 RGB multiplication for contrast.
- Preserve alpha, native fades, HUD allocation, counters and gameplay. Three targeted color/alpha/stable-write checks passed. Native confirmation of the softer shade remains pending; no package generated/installed.

## 0.2.34 - Ranger color-transform units and Gunpowder-blue reference

- Fix additive RGB offsets being calculated as normalized 0-1 values. Scaleform additive offsets use byte-channel units (0-255); the old small offsets barely compensated the 0.20 multipliers and darkened the icon.
- Use a representative blue sampled from the Gunpowder background gradient, #43517D, as an additive RGB floor (67,81,125). Retain 0.20 multiplication for icon contrast and preserve alpha, fades, placement and ownership checks. The reference is representative rather than an exact flat native color: the background is baked artwork with a gradient.
- Verify the applied transform by reading it back and log the actual RGB once. A visual failure remains isolated from gameplay.
- Twenty-four focused HUD checks passed, including byte-unit rendering math, a visible blue floor for dark pixels, preserved contrast and rejected-transform reporting. Native visual confirmation is pending. No gameplay values, package installation or other character modules changed.

## 0.2.33 - Ranger exact highlight color and kill extensions

- Set Ranger's highlight to #A7D8F0. Derive the RGB transform from this single hex value while retaining contrast and alpha.
- Each credited kill while the reload bonus is active adds 2 seconds, up to 12 seconds total from the original activation: 6 -> 8 -> 10 -> 12. At most three distinct victims extend each activation; extra kills do not refresh it and expired bonuses cannot be revived.
- Extend only the live private proc's StartTime, preserving native duration, ranks and modifiers. Damage, Fire Rate, hidden counter and tint follow the same extended deadline. Reset the extension budget on the next prepared reload; no periodic kill scan.
- Update the main description and lower duration lines. Seventy-one focused Ranger gameplay/HUD/kill-extension checks passed. Native confirmation of kill extension remains pending. No package generated/installed.

## 0.2.32 - Ranger lighter highlight, hidden active counter and proc interval

- Change the active-bonus tint from dark blue to baby blue while preserving alpha, icon contrast and native slot allocation.
- Increase the hidden minimum interval between gained preparation stacks from 0.1 to 0.15 seconds.
- Hide the preparation number after the prepared reload: disable the visual helper's CustomStackCount and use visual Grade 1 during the bonus. Keep the same icon active and colored; restore the grade counter for the next preparation cycle. Gameplay rank, damage, cadence and six-second duration are unchanged.
- Fifty-eight focused Ranger/gameplay-HUD tests passed. The previous blue highlight was confirmed by the user; the new tone/counter presentation still needs an in-game check. No package generated/installed.

## 0.2.31 - Pressure rank description repair

- Restore all three lower-description values: Shield Capacity +15%, Maximum Health -7%, and Shield Recharge Delay while Depleted -7% per effective rank. At 5/5: +75%, -35%, -35%.
- Render the requested native tooltip grade directly, preserving class-mod/current/next-rank values and coloring only numeric values. Rank-5 previews from rank 4 remain non-green.
- Detect overwritten Pressure effects/presentation arrays when its tooltip is requested; restore the intended configuration only when needed and invalidate native modifier caches if gameplay definitions changed. No new combat polling or balance changes.
- Twenty-six focused/adjacent tests passed (Pressure and class-mod refresh). Native description confirmation is pending. No package generated/installed.

## 0.2.30 - Ranger blue HUD image lookup

- Resolve Ranger's visible Flash image through FindTrackedSkill with all required output arguments. Native remapped/cache indices can differ from the actual rushN image path. Fall back to a bounded search of the loaded Ranger texture when the native path is unavailable.
- Verify native feedback ownership or the loaded image identity before tinting/restoring; preserve alpha, icon position, allocation and all gameplay values. Restore the original color through the verified visible image before hiding, including generic loader URLs confirmed by native state.
- Add a one-time applied-highlight log for the next native check. Twenty-one focused HUD tests passed. The user and session log confirmed the damage/cadence bonus; post-fix color confirmation remains pending. No package generated/installed.

## 0.2.29 - Ranger deferred weapon impacts

- Fix Ranger remaining at zero progress for native bullets whose damage arrives after FireAmmunition/SharedFireAmmunition return and identifies the weapon as damage causer. Zero progress had also prevented its HUD and prepared reload bonus from activating.
- Retain one weak, consumable firing-group record per weapon on the ordinary POST callback; nested firing wrappers reuse the same record. Preserve projectile-specific records, rank/owner/source/damage checks, the hidden interval and existing buff behavior.
- Bound retained weapon groups to 16 with a 30-second expiry; prune through existing maintenance and invalidate on reload activation, lifecycle changes and respec. Add one-time retention and accepted-hit diagnostics. No global actor scans.
- Two read-only native captures confirmed the callback ordering and live Ranger rank 5. Seventy-eight focused/adjacent offline checks passed, including a replay of the captured delayed-SMG sequence through reload and Amp Damage. Post-fix native verification remains pending. No package generated/installed.

## 0.2.28 - Ranger HUD progress and blue active bonus

- Add a visual-only native Ranger icon showing 1-10 preparation stacks. A prepared reload keeps the icon at 10 and colors it blue for the six-second gameplay bonus; expiry or reset hides it appropriately.
- Reuse the shared free-slot allocator, including inactive reserved skills and physical remaps. Keep RGB tinting limited to the verified Ranger texture; preserve alpha, native fades, position and other skill icons. Restore the original RGB before hiding, and forget old movie identities during teardown.
- Use existing quarter-second maintenance after combat processing, with fresh player/manager references. Counter refresh callbacks cannot suppress the combat caches for other skills. Stable tint does not generate repeated color writes; visual failures leave gameplay intact.
- Seventy focused/adjacent offline checks passed across Ranger HUD/gameplay, Ready HUD allocation and Duty Calls stacks. Native confirmation remains pending. No package generated or installed.

## 0.2.27 - Ranger prepared reload rework

- Remove all seven previous passive Ranger bonuses. Ten distinct gunshots hitting the same enemy prepare a reload bonus: +7% Amp Damage and +4% Fire Rate per effective rank for 6 seconds (+35%/+20% at 5/5).
- Extra pellets share their firing event, including mapped delayed projectiles. A hidden 0.1-second interval limits gained stacks. Hitting another enemy resets progress/prepared state, but preserves an already active bonus; no progress accrues during the bonus. Misses and unprepared reloads preserve progress.
- Use scoped MT_PostAdd weapon damage and native timed cadence; preserve other modifiers. Reuse completed-ammo-transfer reload detection, independently of Ready allocation. Reconcile class-mod grades without adding equipment points twice; clear progress at death, travel, skill-tree initialization, respec and disable.
- Fifty-one focused/adjacent offline checks passed (Ranger, Ready and native-grade support). Native gameplay/co-op remain unverified. No package generated or installed.

## 0.2.26 - Resourceful extension cap

- Increase the per-deployment Resourceful duration-extension cap from 15 to 20 seconds, including the shared Gemini budget. Preserve 0.1 seconds per effective rank per qualifying hit and Sentry/native duration.
- Derive the lower-description cap and setup log from the same runtime constant. Eighteen focused/adjacent offline checks passed; native gameplay confirmation remains pending. No package generated/installed.

## 0.2.25 - Resourceful live action lookup

- Fix active turret-duration extension being rejected when the native Scorpio skill has an empty CachedActionSkill. Resolve the current action actor through Pawn.MyActionSkill, then retain existing owner/world/ending/living-turret checks. Never use a stale cached actor as fallback.
- Preserve +0.1 seconds per effective rank per qualifying Axton damage event, the separate 15-second cycle cap, Sentry/native duration and incoming-damage cooldown reduction. No extra actor scan, hook or timer.
- Two read-only live captures confirmed the empty cache and valid pawn-owned Scorpio action; fifty-nine focused/adjacent offline checks passed after the fix. Post-fix lifetime confirmation still requires installing/restarting. No package generated/installed.

## 0.2.24 - Nuke blast/status progression

- Increase the independent Nuke blast and elemental status damage curve to +30% at level 1 and +250% at level 80 OP10 (GameStage 90), interpolating linearly. This corresponds to factors 1.30 to 3.50 above the native level/global-scaled base.
- Preserve +200% turret weapon damage, the -40% Fire Rate penalty and removed knockback. Align the README Fire Rate penalty with the already configured -40%.
- Seven focused/adjacent Nuke checks passed; engine verification remains pending. No package generated/installed.

## 0.2.23 - Nuke turret bonuses

- Increase Nuke turret gun damage from +150% to +200% and change the Fire Rate penalty from -30% to -40%. Update the native effect coefficients, lower description and setup log together.
- Preserve the separate nuclear blast/status progression: linear +15% at level 1 through +155% at GameStage 90 (level 80 OP10). The turret weapon bonus does not modify those separate inputs. Knockback remains removed.
- Six focused Nuke checks passed; native gameplay verification remains pending. No package generated/installed.

## 0.2.22 - Pressure depleted-shield delay

- Replace Pressure health-dependent Shield Recharge Delay scaling with the full 7% reduction per effective rank only while shields are depleted (35% at 5/5). Remove the delay bonus when shields regain charge.
- Preserve +15% Shield Capacity and -7% Maximum Health per rank. Update the lower-description coefficient and condition. Use a private native initializer; leave shared native health-based formulas untouched. No new hooks, helpers or polling.
- Twenty-six focused/adjacent offline checks passed. Native gameplay confirmation remains pending; no package generated/installed.

## 0.2.21 - Ready HUD indicator

- Show Ready's original skill icon while its three-second reload movement bonus is active. Use separate visual-only native feedback and the shared free-slot allocator; preserve reserved native slots and cached physical mappings.
- Follow actual timed-helper state and expiry; hide on expiry, paused gameplay effect, respec, incapacitation, travel and disable. Keep movement/expiry independent of HUD availability or relocation.
- Reuse existing quarter-second maintenance and one-second stable-slot checks; no new tick/render hook or Canvas drawing. Sixty-four focused/adjacent offline checks passed. Native HUD/gameplay confirmation remains pending; no package generated/installed.

## 0.2.20 - Pressure shield/health tradeoff

- Replace Pressure weapon Reload Speed with +15% Shield Capacity and -7% Maximum Health per effective rank (+75%/-35% at 5/5).
- Preserve the original health-dependent Shield Recharge Delay effect, its initializer chain, coefficient and native presentation without rewriting them. Add separate shield-capacity and signed maximum-health lower-description rows. Include Pressure in existing class-mod reconciliation.
- Twenty-four focused/adjacent offline checks passed; engine verification remains pending. No extra hooks, timers or manual resource writes; no package generated/installed.

## 0.2.19 - Able regeneration

- Increase Able from 0.4% to 0.5% maximum health regeneration per second per effective rank per stack. At 5/5 and five stacks: 12.5% maximum health per second. Preserve five independent three-second stacks, native trigger interval and class-mod scaling.
- Four focused Able checks passed. No new hooks or polling; native confirmation of the new coefficient remains pending.

## Verification - 2026-11-11: Able

- Read-only live capture confirmed five simultaneous independent Able stacks at rank 5, each regenerating 2% of maximum health per second; combined regeneration reached the expected 10%/second. Health gain matched the combined modifiers.
- No gameplay correction or balance change was needed. Document independent three-second expiry and retain the existing implementation. Add a short read-only probe for future diagnosis; co-op and other effective ranks still need engine validation.

## 0.2.18 - Ready reload movement

- Increase Ready movement speed after reloading from 4% to 5% per effective rank (25% at 5/5). Preserve native 8% Reload Speed per rank, three-second duration, refresh without stacking and class-mod support.
- Replace dependence on SkillDefinition.OnWeaponReloaded dispatch with paired weapon ReloadDone hooks. Require a completed ammo transfer; early cancellation and empty-reserve attempts do not trigger the buff. Invalidate pending primitive frames across initialization/travel/disable, and reacquire the owner/manager after native deactivation when refreshing.
- Add one first-activation log containing effective rank, movement bonus and duration. Forty-three focused/adjacent offline checks passed. Native activation coverage and actual movement still require gameplay confirmation; no package generated or installed.

## 0.2.17 - Sabre Turret base cooldown

- Reduce native Sabre Turret base cooldown from 42 to 30 seconds. Preserve cooldown-rate bonuses, resource-pool consumption, Resourceful reductions and Mag-Lock percentage refunds.
- Twenty-seven focused/adjacent offline checks passed; native gameplay confirmation remains pending. No package generated or installed.

## 0.2.16 - Quick Charge damage resistance

- Replace the 8% Cooldown Rate per rank bonus with 5% native Damage Reduction per effective rank during the kill skill (25% at 5/5). Preserve native shield regeneration, kill trigger, duration and class-mod grade rules.
- Add native self-target resistance effects across the existing nine normal/elemental impact/status channels, remove obsolete cooldown/ammo rows, and show a single positive Damage Reduction line. No extra helper, hook, timer or per-hit checks.
- Eighteen focused/adjacent offline checks passed. Native gameplay/co-op verification remains pending; no package generated or installed.

## 0.2.15 - Forbearance critical shield restoration

- Replace all prior Forbearance effects with 2.5% Maximum Shield restored per effective rank on a critical hit (12.5% at 5/5), capped at shield capacity. Keep a hidden shared 0.5-second interval.
- Remove status-application observers, temporary fire-rate/movement buff and slow-immunity interception. Use the native player critical-hit event and reserve the interval before restoring shields. Support class-mod ranks once; display fractional percentages with one decimal place.
- Sixty-four focused/adjacent offline checks passed; native gameplay/co-op testing remains pending. No package generated or installed.

## 0.2.14 - Mag-Lock destruction refund

- Add a 35% total action-skill cooldown refund when an owned Sabre Turret dies from damage while Mag-Lock is learned. Apply when the native cooldown starts, once per deployment cycle; Gemini does not double the refund. Expiry, recall and scripted cleanup are excluded.
- Preserve attachment, throw speed and attention effects. Add a separate lower-description refund line. Reuse the existing quarter-second driver only while a refund is pending; no new timer or per-hit hook.
- Clear pending state on new deployment, travel, initialization, owner incapacitation/identity change and disable. Gameplay/co-op confirmation remains pending.

## 0.2.13 - Gemini and Healthy

- Increase Gemini defensive aura from 15% to 25%; preserve its native resistance formula, radius, allies, non-stacking behavior and HUD.
- Healthy grants 6% Maximum Health per effective rank and regenerates 1% Maximum Health per second per rank while the turret is deployed, replacing its conditional resistance. Two turrets do not duplicate healing.
- Eighty focused/adjacent offline checks passed. Native gameplay/co-op verification remains pending; no package generated or installed.

## 0.2.12 - Able regeneration

- Restore Able to 0.4% maximum health regeneration per second per effective rank per stack. Keep five independent stacks, their native three-second duration, trigger interval and class-mod scaling. At 5/5 with five stacks: 10% maximum health per second.
- Four focused Able checks passed; no other gameplay changes.

## 0.2.11 - Resourceful damage-driven turret extension

- Add 0.1 seconds of active Sabre Turret duration per effective Resourceful rank when Axton deals positive enemy damage (0.5 seconds at 5/5). Only Axton's own weapons/grenades/melee/status damage qualify; turret and ally damage are excluded.
- Cap this effect at 15 extra seconds per native action-skill activation. Sentry's native duration is neither replaced nor charged against the cap. Gemini shares the same action-skill cycle; throwing its second turret does not reset or double the budget.
- Change only the live action skill's StartTime; leave Duration, its base value, Sentry's initializer/modifier stack and definitions untouched. Do not revive expired/ending cycles or operate without a living owned turret.
- Preserve the existing incoming-damage cooldown reduction and its hidden interval. Add separate lower-description duration/cap lines with native rank formatting.
- Reuse the existing damage-summary hook and quarter-second skill snapshot. No extra hooks, timers, actor scans or skill-manager lookup per hit. Stop extension work after the cap, and round timestamps conservatively to float32. Clear state/weak references on lifecycle boundaries.
- Sixty-seven distinct focused/adjacent offline checks passed across Resourceful, Duty Calls, Double Up, configuration and class-mod integration. Native gameplay and co-op verification remain pending; no package generated/installed.

## 0.2.10 - Preparation resistance / Duty Calls footer

- Replace Preparation's full-shield health regeneration with 30% native Damage Resistance per effective rank. Preserve 5% Shield Capacity per rank, the precision-safe full-shield condition and native icon. At 5/5, the native +150% resistance coefficient reduces damage by 60% in isolation; it is not a flat 150% reduction.
- Use a private native initializer that reads Preparation's effective parent grade once, including class-mod points. Cover normal, explosive, corrosive, incendiary, shock and amp damage channels. Remove regeneration from the parent display and active effect. No extra hook, timer or rank polling.
- Remove Decay Delay and Stack Decay Interval from Duty Calls' lower description. Stack gain, cap, decay timing and HUD are unchanged.
- Seventeen focused/adjacent checks passed, with two repeat-configuration checks rerun after native-array comparison hardening. Restart after updating; native gameplay and co-op confirmation remain pending.

## 0.2.9 - Preparation native full-shield condition

- Replace the unsuccessful Python Evaluate-hook workaround with a native constraint expression: current shield >= maximum shield * 0.999999. This retains only a 0.0001% rounding tolerance, preserving the shield-capacity/on-foot guards, healing coefficient, class-mod ranks and native HUD behavior.
- Remove the global evaluator hook and its address cache. No new polling, custom HUD skill or native attribute is required.
- The player confirmed blinking with the previous fix installed (0.2.8). Sixteen focused checks passed, including float32 comparisons and idempotent configuration. Restart and confirm Preparation + Phalanx stability, damage interruption and recharge recovery in game.

## 0.2.8 - Mag-Lock description

- Explicitly describe increased turret enemy attention and faster turret throwing while retaining wall/ceiling attachment. The lower block lists +75% Turret Throw Speed and increased Enemy Attention.
- Update presentation before gameplay-attribute configuration, so a missing threat attribute no longer leaves the native description unchanged. Gameplay values are unchanged; this does not resolve the separately logged threat-attribute lookup error. Seven focused description checks passed.

## 0.2.7 - Duty Calls stack feedback

- Add a separate, visual-only Duty Calls HUD skill using its menu icon and a native stack counter (1-20). Reserve both logical and physical slots of other skills, including inactive tracked children and Gemini. A full HUD hides feedback without removing gameplay bonuses.
- Reuse the existing quarter-second maintenance. Update visual grades only when stacks change; avoid repeated allocation scans within one second and skip HUD lookups while idle. Clear feedback on zero stacks, respec, incapacitation and travel.
- Runtime diagnosis found the damage trigger and gameplay modifiers working at rank 5 / 20 stacks: critical modifier +0.20 on the controller, fire-interval modifier -0.25 on the equipped weapon. Preserve those coefficients.
- Forty-seven focused/adjacent offline checks passed, plus targeted rechecks after strengthening physical-slot reservation. New HUD confirmation in game remains pending.

## 0.2.6 - Preparation full-shield stability

- Prevent Preparation healing/HUD flicker caused by tiny shield-capacity rounding differences when combined with Phalanx Shield. The existing full-shield condition accepts only a relative float tolerance of 0.0001%; other native constraints remain unchanged.
- Preserve health regeneration, shield bonuses, class-mod ranks and native HUD slots. No new polling loop. Sixteen focused offline checks passed; in-game confirmation remains pending.

## 0.2.5 - Double Up and Gemini

- Restore Double Up's native turret-weapon damage penalty at a fixed 25%. Keep its second gun, slag rounds, cooldown rate and enemy debuff. Scorched Earth alone remains in the penalty-removal routine.
- Reduce Gemini aura Damage Reduction to 15%; preserve 20% Turret Fire Rate, 8-meter radius, non-stacking protection and HUD behavior.
- Update lower/upper descriptions. Forty focused offline checks passed; restart and validate turret damage and aura protection in game.

## 0.2.4 - Resourceful incoming-damage trigger

- Change Resourceful from critical hits to taking actual health or shield damage. Reduce remaining Sabre Turret cooldown by 0.3 seconds per effective rank (1.5 seconds at 5/5).
- Add a hidden 0.5-second internal interval shared by all qualifying damage. Blocked/no-loss hits do not consume the interval.
- Preserve current cooldown-rate modifiers and clamp at zero. Remove the critical-stat hook; use paired incoming-damage callbacks with lifecycle and nested-call guards.
- Update descriptions and keep the internal interval out of skill text. Focused/adjacent offline checks passed; restart and validate in game.

## 0.2.3 - Duty Calls damage stacks

- Replace Duty Calls completely: dealing damage to an enemy grants one stack; critical hits grant two, up to 20 stacks.
- Each stack grants 0.25% Fire Rate and 0.2% Critical Hit Damage per effective rank. At 5/5 and 20 stacks: +25% Fire Rate and +20% Critical Hit Damage.
- After 2 seconds without dealing damage, lose one stack every 0.5 seconds. Further damage refreshes the delay. Remove the non-elemental weapon restriction; owned turret damage and damage-over-time events can contribute.
- Reuse the existing damage callback and combat-maintenance pass. Coalesce native effect changes, preserve class-mod scaling, and clear stacks on incapacitation/travel/respec.
- Update descriptions; fixed limits/times are not rank-colored. Offline checks passed. Restart after updating; native gameplay and co-op validation remain pending.

## 0.2.2 - Resourceful critical-hit cooldown reduction

- Replace Resourceful's passive cooldown-rate and multiplicative turret-damage bonuses with 0.2 seconds of remaining Sabre Turret cooldown reduction per rank for each critical hit (1 second at 5/5).
- Account for current cooldown consumption rate, clamp at zero, and apply only while cooling down. No internal proc interval is added. Effective class-mod ranks are preserved.
- Remove Resourceful from the turret damage multiplier and its recurring rank lookup. Use the existing cached combat pass for the critical-event rank.
- Preserve Double Up's independent cooldown bonus and Nuke/turret scaling. Update descriptions; restart after updating. Offline checks passed, while native/co-op validation remains pending.

## 0.2.1 - Quick Charge cooldown rate

- Replace Quick Charge's magazine regeneration with 8% Action Skill Cooldown Rate per rank, active only during the kill skill (+40% at 5/5).
- Preserve shield regeneration at 1% maximum shield per second per rank, the native kill trigger/duration and class-mod ranks.
- Remove Quick Charge's rank contribution from the magazine generator. Overload remains unchanged. Migrate the old ammo effect/footer to the new cooldown effect/footer.
- Focused offline checks passed. Restart after updating; actual cooldown gain/expiry still needs gameplay verification.

## 0.2.0 - Ready movement after reloading

- Update the project and Mod Manager version to 0.2.0.
- Keep Ready's passive 8% Reload Speed per rank. Its 4% Movement Speed per rank now lasts 3 seconds after completing a reload instead of being passive.
- Further reloads refresh the duration without stacking. Use the native reload event and a single native timed helper; the previous incoming-damage cooldown effect remains removed.
- Support effective class-mod ranks and respec cleanup. Update descriptions and keep the fixed duration outside rank coloring. Restart after updating; native gameplay/co-op verification is pending.

## 0.1.47 - Steady passive grenade damage

- Remove Steady's Movement Speed bonus and restore its original passive 5% Grenade Damage per rank.
- Keep 6% Rocket Launcher Damage and 8% Reload Speed per rank while holding a rocket launcher. These conditional bonuses use an untracked native helper; no additional HUD icon or per-hit callback is added.
- Preserve effective class-mod ranks. Update upper/lower descriptions; restart after updating. Offline checks passed; gameplay validation remains pending.

## 0.1.46 - Ready and Mag-Lock

- Ready grants its original 8% Reload Speed per rank alongside 4% Movement Speed per rank. Both bonuses are passive; remove its incoming-damage cooldown effect and callbacks.
- Move the 75% faster turret throw from Longbow to Mag-Lock. Restore native wall/ceiling attachment and keep increased enemy attention. Remove Mag-Lock's previous weapon-range and detection-radius bonuses.
- Keep Longbow's native deployment/health bonuses. Update upper and lower descriptions without adding skill-HUD slots.
- Focused offline checks passed. Restart and verify allocation, class mods, throw speed and attachment in game.

## 0.1.45 - Preparation, Quick Charge and Healthy balance

- Restore Preparation's original secondary effect: regenerate 0.4% maximum health per second per rank while shields are full. Retain the increased 5% Shield Capacity per rank.
- Restore Quick Charge's shield regeneration to 1% maximum shield per second per rank. Keep its 1% magazine regeneration per second per rank and native kill-skill behavior.
- Increase Healthy's turret-deployed Damage Reduction from 4% to 5% per rank, retaining 4% Maximum Health per rank and effective class-mod ranks.
- Restart the game after replacing the mod. Offline checks passed; new engine validation is pending.

## 0.1.44 - Ready: movement and cooldown on damage

- Replace Ready's Reload Speed with 4% Movement Speed per rank. Taking actual health or shield damage reduces the remaining turret cooldown by 0.3 seconds per rank, with a hidden 0.5-second internal interval. At 5/5: +20% movement and 1.5 seconds per activation.
- Use effective native ranks, including class mods. Native lower descriptions show Movement Speed and fractional cooldown seconds; the internal interval is not displayed.
- Confirm damage with paired player TakeDamage hooks. Ignore blocked/no-loss calls and full/deployed cooldown states; use the current pool consumption rate to convert seconds into pool units, clamp at zero and claim the interval before native callbacks. Preserve other cooldown-rate bonuses.
- Reuse the existing combat snapshot, with no new tick or per-hit skill-list scan. Clear pending context on tree initialization/travel; preserve nested callback pairing. Local authority implementation; remote co-op remains unvalidated.
- Fourteen focused Ready tests plus nine adjacent ammo/cache checks passed. Native values, trigger timing and rendering need verification after a full restart.

## 0.1.43 - Mag-Lock: attention and range

- Replace remote recall with increased turret threat priority and +50% weapon range. Increase turret sight radius by the same 50% to support detection at greater distances. Keep wall/ceiling attachment disabled.
- Apply native Scorpio-sourced effects: WeaponRange +0.50 scale, SightRadius +0.50 scale and TargetPriority +3 post-add. Use private property resolvers for range/sight; shared native attribute resolvers and global AI/weapon definitions remain unchanged.
- Remove recall input interception, held-key polling, custom cooldown refund state and its activation/cooldown hooks. Native nearby pickup and Gemini button behavior are restored. Longbow's +75% throw-speed bonus remains intact.
- Put the +50% range value in the lower description block, with no obsolete attachment/refund stats. Twenty focused and adjacent checks passed; actual targeting/range and co-op behavior still need game verification after a full restart.

## 0.1.42 - Native array ownership during skill initialization

- The native fault capture identifies `_configure_steady`, assigning `SkillConstraints` (installed 0.1.41, line 2171). Copy retained constraint structs into Python-owned storage before replacing their original native array. Preserve the on-foot condition and the private launcher condition.
- Apply the same ownership fix to retained effect structs in Expertise, Double Up, Scorched Earth and Quick Charge. No skill values, conditions or formulas changed.
- Remove the temporary per-stage startup messages; keep native-fault capture for the next validation. The missing SDK messages did not mean initialization had not started: the Python crash stack confirms it had reached Steady.
- A reallocation regression fails before the fix and passes afterward. Thirty-four focused/adjacent checks passed; native character loading still needs confirmation.

## 0.1.41 - Native-fault traceback capture

- The loading crash recurred with the installed 0.1.40 at the same native SDK offset. The previous guards did not resolve it; its exact source remains unconfirmed.
- Temporarily enable Python's native fault handler while the mod is enabled, writing Python tracebacks directly to `%TEMP%/AxtonRebalance-native-crash.log`. Keep the descriptor open, preserve any pre-existing handler, and unregister the owned handler before closing its file on disable. No polling or intentional crash generation.
- Five focused diagnostic lifecycle tests passed; gameplay values remain unchanged. This version collects evidence and is not a confirmed fix.

## 0.1.40 - Loading guards for turret runtime hooks

- Keep turret damage synchronization and weapon-definition inspection dormant until the native Axton skill-tree initialization returns. Longbow animation inspection follows the same guard. Do not read loading-time weapon buffers or query skill ranks from these paths prematurely.
- Preserve existing damage values, Resourceful updates before deployment, turret-only weapon refresh and Longbow throw speed after initialization.
- The third crash used the installed 0.1.39 and again reached SDK offset `0xB7BF2`, without a recorded skill-tree entry checkpoint. This guard addresses unsafe early access; a successful in-game load is still required to confirm crash resolution.
- Five focused loading-guard tests and nine adjacent turret/Longbow checks passed offline.

## 0.1.39 - Temporary startup diagnostics

- Add startup-only checkpoints before each skill configuration and inside Gemini helper creation, effect assignment and presentation setup. No per-frame diagnostics or gameplay changes.
- Two character-loading crashes reached the same native SDK offset (`0xB7BF2`); loading with AxtonRebalance disabled succeeded. The exact failing operation remains unconfirmed. The next run's last checkpoint will help isolate it.
- Sixteen existing Gemini checks passed offline; Python syntax and metadata validated. This diagnostic version is not a confirmed crash fix.

## 0.1.38 - Double Up and Longbow description layout

- Move Double Up's 15% marked-enemy vulnerability and 8-second duration from the main description into the lower stats block. Retain native gun/slag/cooldown lines.
- Move Longbow's 75% throw-speed value into the lower stats block, retaining its native range/health lines.
- Color learned single-point bonus percentages green; unlearned next-point previews inherit the UI color, and fixed duration stays outside the percentage color span.
- Presentation only: no gameplay values or triggers changed. Five focused footer tests and two adjacent configuration checks passed.

## 0.1.37 - Mag-Lock remote recall

- Replace wall/ceiling attachment with hold-to-recall. Hold the currently bound Action Skill button for 0.6 seconds while a turret exists; short presses preserve Gemini second deployment, and initial deployment stays immediate.
- Use native action-skill deactivation to clean up the turrets and start cooldown. Do not manually destroy turret actors or create another turret copy.
- Refund `0.60 * min(remaining_duration_fraction / 0.90, 1)` of the cooldown pool's maximum, once per action cycle. Replace the original nearby-pickup refund for learned Mag-Lock rather than stacking both. Preserve other cooldown reductions and native consumption-rate bonuses.
- Track only primitive action/context identities and clear requests on invalid contexts or travel. Input checks run only while a hold/refund is pending. The four original attachment-evaluator branches are disabled for this rework; Longbow's throw-speed bonus stays intact.
- Fifteen focused and eleven adjacent offline tests passed. This is a solo/host trial; real input bindings, teardown/refund timing, attachment removal and client co-op require gameplay verification.

## 0.1.36 - Steady rework

- Remove Steady's recoil reduction and grenade-damage bonus.
- Grant 6% Rocket Launcher Damage, 8% Reload Speed and 5% Movement Speed per effective rank, all while holding a rocket launcher.
- Preserve the native on-foot constraint and append a private equipped-launcher evaluator. No shared weapon-type evaluator is modified and no weapon polling hook is added.
- Replace the description and rank stats; include Steady in live class-mod cache refresh. Six focused and ten adjacent tests passed offline. Verify weapon switching and actual effects after restarting.

## 0.1.35 - Quick Charge magazine regeneration

- Keep Quick Charge's shield regeneration, kill trigger and duration; add magazine regeneration at 1% of current capacity per second per effective rank while active.
- Add its rate to Overload in the existing shared pass. Use one timer/fractional balance and the same pool-backed clip generation, without spending reserve ammunition or introducing negative counters.
- Add the magazine-regeneration description/stat. Native class-mod grades are used once; inactive kill-skill instances contribute nothing.
- Seven focused and 14 adjacent offline checks passed. Test gameplay after restarting, including both skills together and expiry.

## 0.1.34 - Forbearance initialization fix

- Fix Forbearance failing to update its description and effects when an enemy-package attribute was unavailable. Configuration no longer looks up or loads GD_SkagShared.
- Protect local Axton from recognized negative-movement status skills at SkillEffectManager.ActivateSkill. Preserve gear penalties, other players, elemental status damage and application callbacks. Existing matching slows still use normal deactivation cleanup.
- Migrate the previous passive-guard layout to two display-only effects; no balance changes to the 7%/6%-per-rank bonuses or 10-second duration.
- Fifteen focused and 20 adjacent tests passed offline. Restart with the updated package and confirm the successful Forbearance configuration log; native gameplay remains pending.

## 0.1.33 - Gemini defensive aura

- Preserve two turrets and add fixed 20% Turret Fire Rate. The earlier proposed burst-count increase is superseded and was not implemented.
- Grant Axton and allied players native 20% Damage Reduction within an active turret's 8-meter radius, without stacking across overlapping turrets or Gemini owners.
- Add a separate, empty HUD feedback skill using Gemini's original icon. Reserve tracked children, remapped entries and cached icons; expand the purchased prefix as needed. A full HUD hides feedback without affecting protection.
- Maintain gameplay at quarter-second intervals using weak turret references and one bounded bootstrap walk per relevant world. Throttle idle maintenance and steady HUD allocation scans to once per second. Change native skills only when membership changes, and clean helpers before travel.
- Fifteen focused and 22 adjacent offline tests passed. Native gameplay, distance calibration and co-op remain pending.

## 0.1.32 - Forbearance rework

- Remove the original maximum-health and status-duration resistance effects and their feedback behavior.
- Confirmed Ignite, Corrosive, Shock, Slag or Slow applications grant 7% Fire Rate and 6% Movement Speed per effective rank for a fixed 10 seconds. Reapplications refresh without stacking; resisted attempts and ordinary DoT ticks do not trigger it.
- The first point enables the native player-slow guard. Previously applied native slows using the same guard are removed through their normal deactivation, preserving damage, other statuses and equipment penalties.
- Reuse the existing combat snapshot for helper activation, grade changes, expiry and respec cleanup. Clear pending windows on travel; no new per-frame status polling or HUD slot.
- Twelve new and 29 adjacent offline tests passed. Native gameplay/co-op validation remains pending.

## 0.1.31 - Longbow throw speed

- Move the 75% turret throw animation speed bonus from Mag-Lock to Longbow Turret. Keep the original effects of both skills unchanged.
- Update skill descriptions and the allocation check; Mag-Lock alone no longer grants the speed bonus, and learning both does not double it.
- Seven focused checks passed offline. Gameplay confirmation remains pending after restarting.

## 0.1.30 - Healthy

- Reduce Healthy's Maximum Health bonus from 6% to 4% per rank.
- Add native Damage Reduction at 4% per rank while the Sabre Turret is deployed, using an independent helper with the native Battlefront deployment constraints. Battlefront allocation is not required.
- Include class-mod rank changes, removal after respec, and a separate description stat. No additional HUD slot or per-frame turret scan is used.
- Seven new tests and 24 adjacent checks passed offline. Gameplay confirmation is pending.

## 0.1.29 - Class-mod effect refresh

- Preserve native effective ranks and descriptions without adding equipment points twice or overwriting invested points.
- Refresh cached effects after equipment/rank changes, including Able and Preparation auxiliary effects.
- Share the existing skill snapshot, check equipment at most once per second, and stop traversal after native rebuilding. Clear caches on travel/tree initialization.
- Ten focused tests and 23 adjacent checks passed offline. In-game verification remains pending.

## 0.1.28 - Quick Charge and Laser Sight stat display

- Enable decimal percentage display for Quick Charge: 1.5%, 3%, 4.5%, 6% and 7.5% at ranks 1 through 5.
- Give Laser Sight Fire Rate its own attribute presentation, reading the actual 5%-per-rank fire-rate effect instead of repeating accuracy's 50% value at 5/5.
- Repair the legacy combined presentation even when the fire effect is already installed. Gameplay coefficients, native grades and original accuracy remain unchanged.
- Six focused tests and syntax validation passed. Visual confirmation remains pending.

## 0.1.27 - Double Up initialization fix

- Fix the native class used to find the cooldown-rate attribute: it is an AttributeDefinition, not a ResourcePoolAttributeDefinition.
- The failed lookup prevented the entire Double Up update, including its new description, cooldown effect and debuff setup. Skill values are unchanged.
- Make the focused configuration test enforce the native class instead of accepting any object with the matching path. The test and syntax validation passed; confirmation after restarting with the updated package remains pending.

## 0.1.26 - Nuke

- Retain the deployment blast; add turret-only +150% Weapon Damage and a native Fire Rate penalty displayed as −30%, preserving the Scorpio instance-data targeting.
- Separate Nuke's blast/status progression from the general turret gun curve: +15% at GameStage 1 through +155% at GameStage 90, linearly, keeping native global/level initializers.
- Include the separate Nuke melee-definition status input and incendiary impact formula. Cache baselines per asset AND field and apply the new factor once through the outer scale.
- Remove the attack's Knockback and the explosion/radius-damage MomentumFormula without changing radius, damage types or particle effects.
- Update the main description and bonus footer. Six new Nuke tests plus nine adjacent damage/Resourceful tests passed; engine behavior, cadence and observed damage remain pending validation.

## 0.1.25 - Double Up cooldown and team vulnerability

- Retain the second gun and slag bullets; add a fixed passive 25% Cooldown Rate bonus and its stat line.
- Successful direct hits from the local Axton's Sabre Turret mark surviving enemies for 8 seconds. Marked targets take 15% more damage from Axton and allies; new hits refresh, rather than stack, the effect. Status ticks do not refresh it.
- Combine vulnerability multiplicatively with Last Ditch Effort in the same received-damage scope. All six native damage categories are supported, without replaying damage.
- Update the main description to explain the new debuff and remove the claim that slag itself increases damage.
- Share the existing four-per-second skill-cache pass, bound mark storage and clear marks on travel/respec. Preserve the new cooldown effect during augment-penalty cleanup.
- 35 focused/adjacent tests passed, including destruction after the local-controller lookup disappears. In-game turret attribution, observed damage, remote co-op and replication still require validation.

## 0.1.24 - Nuke and Double Up positions

- Swap Nuke and Double Up: Nuke becomes Guerrilla's capstone, Double Up becomes Gunpowder's capstone.
- Preserve skill definitions/effects, capstone tier requirements and the existing Crisis Management/Resourceful/Last Ditch Effort rotation.
- Validate both original and already-swapped layouts before writing; repeated initialization does not swap them back.
- Six focused tree-position tests passed. In-game tree confirmation remains pending after restart.

## 0.1.23 - Mag-Lock throw speed

- Add a 1.75x player throw-animation speed multiplier while Mag-Lock is learned, retaining wall/ceiling attachment.
- Apply the multiplier only to the local Sabre Turret master special-move invocation; preserve shared animation definitions, launch notifies, projectile travel and turret unfolding.
- Update the skill description. Six focused tests passed; actual first/third-person timing, release synchronization, Longbow and Gemini require gameplay validation.

## 0.1.22 - Scorched Earth explosive damage

- Add a fixed passive 10% Explosive Damage bonus while Scorched Earth is learned, retaining its rocket pods and native count stat.
- Add an explosive-damage stat and update the main description.
- Keep the added effect through turret-penalty cleanup. Recognize the real native TARGET_None reload-attribute marker used by both augments, in addition to null-attribute layouts.
- Four feature/integration tests and two adjacent penalty-cleanup tests passed. Gameplay verification remains pending.

## 0.1.21 - Phalanx Shield

- Increase the projected barrier's capacity by 70%, retaining native level and global scaling.
- Add a fixed passive 10% player Shield Capacity bonus while the skill is learned, plus its stat line.
- Preserve the original barrier behavior and turret-shield count stat.
- Three focused tests passed for formula inputs, player effect, repeated setup and unexpected-data rejection. Gameplay verification remains pending.

## 0.1.20 - Quick Charge

- Increase shield regeneration by 50%, from 1% to 1.5% of maximum shield per second per rank (7.5% per second at 5/5).
- Update the native coefficient shared by gameplay and the rank stat; retain activation, duration, constraints and class-mod grades.
- Two focused coefficient/idempotence tests passed. Gameplay confirmation remains pending.

## 0.1.19 - Metal Storm reload speed

- Replace Metal Storm's recoil reduction with 10% Reload Speed per rank, preserving native Fire Rate, kill activation and duration.
- Remove both the recoil gameplay row and its old display row; update the main description and stat line.
- Keep Expertise's passive recoil independent of Metal Storm's current effect array and presentation, including Hyperion behavior.
- Five focused Metal Storm/Expertise tests passed, including effective ranks through 11, initialization in either order and repeated configuration. Gameplay verification remains pending.

## 0.1.18 - Expertise recoil

- Add Metal Storm's native recoil reduction to Expertise as a passive effect: 15% per rank, with native Hyperion handling and class-mod grades.
- Preserve Expertise's swap, aim and aiming-movement bonuses, and leave Metal Storm unchanged.
- Add a recoil stat line and update the description. Two focused tests passed; gameplay verification remains pending.

## 0.1.17 - Duty Calls

- Replace gun damage with 4% Critical Hit Damage per rank and increase Fire Rate to 5% per rank.
- Preserve native non-elemental weapon constraints, class-mod grade rules and Fire Rate presentation; update the damage stat and main description.
- Two focused tests passed, covering effective ranks through 11, repeated configuration and unexpected native data. Gameplay verification remains pending.

## 0.1.16 - Overload ammo balance

- Back regenerated magazine rounds with an equal increase in real total ammo, preserving reserves and the existing regeneration rate.
- Reconcile legacy negative reserves, respect total ammo capacity and avoid overwriting native reloads during pool updates.
- Avoid AddRegeneratedAmmo, which initiated a reload in the live probe.
- Fix travel cleanup accessing BoundFunction.func.Name.
- Ten focused Overload tests and two adjacent travel/shared-cache tests passed. Gameplay validation remains pending.

## 0.1.15 - Last Ditch Effort

- Corrected the Block import to unrealsdk.hooks and explicitly typed the temporary damage scope dictionary, fixing the three reported editor diagnostics.

- Replaced the old FFYL gun damage and movement effects with 5% multiplicative damage per rank against enemies below 30% health.
- Included all native damage source categories and AI damage attributed to the local Axton through PlayerMaster, including owned turrets.
- Updated the description/stat line and removed the obsolete FFYL HUD tracking.
- Added pooled temporary native damage modifiers with nested-hit isolation and travel cleanup. Effective grade caching shares Overload's existing four checks per second.
- Ten focused Last Ditch Effort tests and four adjacent Overload tests passed. Gameplay and remote co-op support remain unverified.

## 0.1.14 - Preparation

- Increased shield capacity from 3% to 5% per rank.
- Replaced health regeneration at full shields with shield regeneration at full health.
- Preserved the native regeneration percentage of 0.4% per rank per second, now based on maximum shield, and updated the description/stat line.

## 0.1.13 - Resourceful

- Increased native cooldown rate from 5% to 8% per rank.
- Added a separate turret damage factor of `1 + 0.04 * effective rank`, reaching 1.20x at 5/5.
- Added a native turret damage stat line; it does not grant player gun damage.
- Refresh the damage sources before deployment, before the turret weapon initializes, and on the existing one-second maintenance pass. Scorched Earth rockets inherit the weapon multiplier once.
- Gameplay verification remains pending; shared source tuning does not independently handle different co-op player ranks.

## 0.1.12 - Ranger

- Doubled all seven original bonuses from 1% to 2% per rank, preserving native presentations and class mod grade rules.

## 0.1.11 - Battlefront

- Replaced melee damage with 4% critical hit damage per rank.
- Preserved gun damage, grenade damage and the native turret-deployed condition; updated the description and rank stat line.

## 0.1.10 - Overload

- Changed magazine capacity to +5% per rank and extended it to all weapon categories.
- Added regeneration of 1% of the equipped weapon's magazine capacity per second per rank. Reserve ammo is unchanged.
- Added fractional accumulation and resets for reloads, weapon/rank/capacity changes, full magazines, pauses and invalid contexts. Regeneration runs for the local authority player, at four checks per second.
- Added a native rank stat line and updated the skill description. Gameplay and co-op validation are pending.

## 0.1.9 - Impact

- Replaced the melee damage bonus with 5% accuracy per rank; retained the original gun damage.
- Updated the description and native stat presentation to display accuracy as a positive bonus.

## 0.1.8 - Grenadier

- Added 4% explosive damage per rank while preserving the original grenade capacity bonus.
- Added a native percentage stat line and updated the description. Class mod grades and next-rank values resolve through the existing skill system.

## 0.1.7 - Able

- Reduced health regeneration to 0.3% maximum health per second per rank per stack.
- Allowed up to five independent stacks using the existing damage trigger, its 0.5-second debounce and the native three-second duration.
- Updated the description, per-stack duration and maximum stack count. Gameplay verification is pending.

## 0.1.6 - Crisis Management

- Replaced its conditional melee bonus with 8% damage reduction per rank while shields are depleted.
- Preserved its gun damage and shield condition; updated its description and rank stat line.

## 0.1.5 - Laser Sight

- Added 5% Sabre Turret fire rate per Laser Sight rank while retaining its native accuracy bonus.
- Updated the skill description and rank text; unexpected native layouts are reported without replacing the skill effects.

## 0.1.4 - Turret augment penalties

- Removed the hidden turret bullet damage penalties from Scorched Earth and Double Up while keeping the native rocket, extra-gun and slag effects.
- Added a strict original-effect check: unexpected definitions are left unchanged and reported in the log. Gameplay verification remains pending.

## 0.1.3 - Original Axton layout only

- Require the original Axton skill positions before the three-way rotation. An already-swapped layout is reported and left unchanged.
- Updated the installation note to disable other Axton skill-position changes before starting the game.

## 0.1.2 - Skill tree rotation

- Moved Resourceful into Crisis Management's original Guerrilla cell, Last Ditch Effort into Resourceful's original Survival cell, and Crisis Management into Last Ditch Effort's original Survival cell.
- Kept each skill definition and its effects intact. Version 0.1.3 narrows the accepted starting layout to the original tree.
- Added pre-initialization tree validation and focused tests. In-game verification remains pending.

## 0.1.1 - Sabre Turret damage progression

- Added a linear damage bonus for the Sabre Turret, from +30% at GameStage 1 to +275% at GameStage 90 (level 80 OP10), applied over the existing level-scaled base.
- Covered turret bullets and identified Nuke explosion/status inputs. Kept turret health, shield, fire rate, cooldown and skill descriptions unchanged.
- Added a one-second stage check with idempotent asset updates and a log that reports how many inputs are available. Offline tests pass; gameplay, Scorched Earth rockets and co-op remain unverified.

## 0.1.0 - Initial project scaffold

- Create the AxtonRebalance Python SDK project structure.
- No gameplay changes are included.

