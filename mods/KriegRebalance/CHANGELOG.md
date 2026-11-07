# Changelog

## Release documentation review - 7 November 2026 (1.0.12 unchanged)

- Align the public feature summary with current Bloodlust balance, ammo regeneration, tree placement and the optional EndgameQoLRebalance module.
- Document Pain is Power decay timing and the intermittent HUD absence restored by restart; its original cause remains unconfirmed.
- Separate current release information from historical implementation notes. Preserve license and credits. No gameplay, metadata version or installed package changes.
- Final latest-balance gameplay confirmation and co-op validation remain outstanding; offline checks are not engine proof.

## 1.0.12 - Bloodlust balance, 6 November 2026

- Blood-Filled Guns: double gun damage from 0.2% to 0.4% per rank per Bloodlust stack (5/5, 100 stacks: +200%). Magazine scaling remains 0.25%.
- Blood Bath: reduce gun damage from 0.4% to 0.3% per rank per stack (5/5, 100 stacks: +150%).
- Blood Overdrive: reduce extra-stack chance from 20% to 10% per rank. Chance is 50% at 5/5 and reaches 100% at 10/5; ranks above 10 retain the 100% probability cap and grant at most one extra stack. Preserve movement/fire bonuses, triggers and duration.
- Eleven targeted numerical, class-mod and footer checks passed; native gameplay confirmation pending.

## 1.0.11 - Fuel the Rampage reduction, 6 November 2026

- Set direct self-damage reduction to 9% per effective rank: 45% at 5/5 and 99% at 11/5. Remove the former 95% reduction cap and its description text. Movement speed, 12-second duration, HUD and status-damage exclusions are unchanged.

## 1.0.10 - Fuel the Rampage movement and HUD, 6 November 2026

- Increase movement speed from 7% to 10% per effective rank (5/5: +50%). Preserve the 12-second renewal window and existing direct self-damage reduction.
- Show the skill-menu icon while the movement effect is confirmed active. Use a separate effect-free native visual and the shared allocator, reserving other skills' logical/remapped slots, learned children and cached icons. A full HUD hides only this visual; the movement bonus remains active.
- Share the existing quarter-second HUD driver; no new tick hook. Skip idle work and avoid resending unchanged icons. Forty-seven relevant offline checks passed; native rendering still requires an in-game test.

## 1.0.9 - Blood Twitch ammo balance, 6 November 2026

- Reduce reserve ammo regeneration from 0.02% to 0.005% of capacity per second per rank per Bloodlust stack. At 5/5 and 100 stacks: 2.5%/s, previously 10%/s. Preserve all other effects and the reserve-only implementation.

## 1.0.8 - Repeated-work reduction, 6 November 2026

- Cache successful static configuration steps using primitive completion keys. The existing two-second pass retries only pending/failed steps; loading another world, initializing the skill tree, opening the frontend or enabling the mod invalidates completion state.
- At five Pain is Power stacks, incoming health damage renews expiration without an immediate full skill/effect scan. Existing 0.1-second maintenance retains rank/context repairs; stack changes still synchronize immediately.
- Allow a tiny floating-point tolerance in the clock-rewind check to prevent valid stacks from being removed by subtraction roundoff. No balance values or native Blood Twitch regeneration changes.
- Forty focused/adjacent offline checks passed. A controlled warm-cache check avoided all 25 configuration calls over 30 further maintenance passes. These counts are not an in-game FPS measurement.

## 1.0.7 - Blood Twitch reserve ammo regeneration, 6 November 2026

- Replace the added recoil reduction with 0.02% of maximum weapon ammo capacity regenerated per second, per effective rank and Bloodlust stack. At 5/5 with 100 stacks this is 10%/s; class mods continue scaling it.
- Regenerate reserves for assault rifles, shotguns, SMGs, pistols, launchers and sniper rifles; exclude grenades and leave the magazine unchanged. Preserve native swap speed, melee damage, triggers and HUD.
- Use additive native resource-pool modifiers with no new combat polling. Remove only the former private recoil effect, preserving unrelated modifiers. Nineteen relevant offline checks passed; reserve-only behavior and rates need gameplay confirmation.

## 1.0.6 - Blood Overdrive balance and placement, 6 November 2026

- Increase movement speed from 4% to 5% and fire rate from 3% to 4% per effective rank (5/5: +25%/+20%). Preserve the current 60-stack threshold, kill-skill duration and extra Bloodlust gain.
- Swap Blood Overdrive (tier 2, right) with Nervous Blood (tier 5, center), preserving the other cells and tier unlock costs. Prepare the swap before native tree initialization; Blood Euphoria retains its position. Restart after updating; no live save-grade rewriting.
- Eight focused and adjacent offline checks passed; native rendering and gameplay remain to be confirmed.

## 1.0.5 - Blood Bath, 6 November 2026

- Reduce gun damage per rank per Bloodlust stack from 0.5% to 0.4% (20% reduction). At 5/5 with 100 stacks, the bonus is +200% instead of +250%. Preserve the kill trigger, duration and grenade drops.
- Update both native footer and damage coefficient; preserve native effective-rank scaling. Three focused offline checks passed; gameplay confirmation remains pending.

## 1.0.4 - Blood-Filled Guns, 6 November 2026

- Halve magazine size scaling from 0.5% to 0.25% per rank per Bloodlust stack. Add 0.2% gun damage per rank per stack: 5/5 at 100 stacks gives +125% magazine size and +100% gun damage.
- Preserve native Bloodlust conditions, stack cap and HUD. Both bonuses scale with effective class-mod ranks, counted once. Update the description and existing COM effect-cache refresh; no new combat polling.
- Eight relevant offline checks passed. Native gameplay confirmation remains pending.

## 1.0.3 - Salt the Wound decay, 6 November 2026

- Set the interval between individual stack losses to 1.5 seconds using the native decay loop. Preserve native gain/reset conditions, bonuses and HUD.
- Three focused offline configuration checks passed; in-game timing remains to be verified.

## 1.0.2 - Salt the Wound HUD collision, 5 November 2026

- Fix the previous counter layout putting Salt the Wound in Bloodlust's logical slot 1. Keep Bloodlust unchanged in 1, restore Salt the Wound to its native 3, and retain Elemental Elation in 2.
- Prepare this layout before native skill-tree initialization registers its counters; keep the existing idempotent maintenance fallback. Custom Pain is Power and Bloody Revival indicators continue reserving native slots through the shared allocator.
- Preserve native stack generation, limits, bonuses and conditions. Five focused layout checks and 47 adjacent custom HUD checks passed. Fresh-process registration and rendering still need in-game confirmation.

## 1.0.1 - Class-mod description ranks, 5 November 2026

- Fix Blood Overdrive counting class-mod points twice in the skill footer: 5 invested plus 5 from equipment now displays rank 10 instead of clamping to 11.
- Apply the same correction to Pain is Power, Fuel the Rampage and Bloody Revival; centralize the effective description rank used by custom footers, including the already-correct Fuel the Fire and Blood Twitch.
- Preserve current/next-rank coloring, skill coefficients and gameplay. Light the Fuse's fixed-value color eligibility also uses the query grade alone.
- Nineteen relevant offline description tests passed, including current/next points, COM swaps and ranks through 11. Visual confirmation in-game remains pending.

## 1.0 - Temporary audio investigation, 1 November 2026

- Add the optional `krieg_audio_trace` console command for a bounded 90-second local audio/status observation. Diagnostic hooks stay disabled during normal gameplay. The reported movement/fire sound still requires reproduction; this is not an audio fix.

## 1.0 - Fuel the Fire class-mod description fix, 1 November 2026

- Direct Incendiary Damage now uses the native effective grade exactly once for both current and next-point text. Class-mod bonuses no longer make the description clamp prematurely at rank 11. Gameplay coefficients and numeric coloring are unchanged.
- Eleven focused offline tests pass; visual confirmation in-game remains pending.



## 1.0 - Release balance pass, 1 November 2026

- License clarification: personal gameplay use is permitted; prior written permission is required to reuse original project code or material. Third-party rights remain separate. No gameplay behavior changed.

- Burn, Baby, Burn: +20% Burn Damage per rank and an additional +10% per rank while Krieg is on fire (5/5: +100% base, +150% total while on fire).
- Fuel the Rampage: direct self-damage reduction is 9.5% per effective rank (47.5% at 5/5); the existing 95% cap remains for additional class-mod ranks. Movement speed and duration are unchanged.
- Bloody Revival FFYL recovery watcher and HUD counter follow-up included from 0.1.48; the author confirmed the icon returned after a successful solo Second Wind. Co-op remains unvalidated.
- Special melee initializer review: only `Init_RampageBonusDamagePerLevel.ValueFormula` is configured by this mod, using `1 + 0.02 * GameStage`; this is a factor for the initializer's special melee damage component, not a general melee bonus.
- Updated the Mod Manager description and release documentation. Co-op remains unvalidated.


## 0.1.48 - Bloody Revival FFYL recovery fallback, 1 November 2026

- Arm a recovery watch on the native FFYL entry event. If the injured-to-healthy callback is skipped, the existing player tick confirms that the local pawn recovered and grants the stack and HUD counter immediately.
- Cache the native Second Wind reason to exclude partner revives; death and world changes discard the watch. The extra state check runs only while FFYL is armed.
- This change addresses the missing HUD icon reported after a successful Second Wind. In-game confirmation remains pending.

## 0.1.47 - Second Wind event and internal naming, 1 November 2026

- Renamed the runtime configuration/maintenance functions to describe their Krieg role.
- Bloody Revival now records a qualifying Second Wind from the native injured-to-healthy transition, even when FFYL lasts less than two seconds. Partner revives and failed recoveries do not grant stacks. The existing periodic maintenance only refreshes native bonuses after class-mod changes and clears them after death or respec.
- The HUD and bonus coefficients are unchanged. In-game confirmation of the recovery event is pending; co-op is not validated.

## 0.1.46 - Runtime audit and reduced redundant work, 1 November 2026

- Read an unchanged native property once instead of twice; preserve readback
  validation after actual writes.
- Configure private Pain is Power and Bloody Revival HUD definitions once after
  successful preparation. Counter updates and slot collision checks stay live.
  Partial construction failures remain retryable; readiness stores paths only.
- Reuse Bloody Revival's prepared native bonus definition while its applied
  grade is unchanged, retaining stack/class-mod updates and death/respec cleanup.
- Avoid copying already neutral armor/shield formula structs on every Raving
  Retribution fire impact or burn tick. Live flesh changes still synchronize.
- Stop tick maintenance, passive migration and regeneration in departing worlds
  before resolving old pawns or managers. No teardown cleanup calls are added.
- Correct Blood Overdrive's configuration log to use its actual 60-stack limit.

## 0.1.45 - Bloody Revival HUD counter, 1 November 2026

- Show the skill's existing menu icon on the native combat HUD while its Second
  Wind bonuses are active, with a counter of 1-5. The visual reads the existing
  stack state and has no gameplay effects of its own.
- Share the counter builder and slot reservation with Pain is Power. Registered
  indicators, learned skill children and occupied HUD positions are reserved;
  later conflicts relocate only the custom visual. A full row hides the custom
  counter without replacing another skill's indicator.
- Repair the underlying Second Wind bonus application, which referenced a
  nonexistent native modifier structure, pawn method and damage-reduction
  attribute. A private native passive now applies the existing per-rank,
  per-stack coefficients, refreshes with stack/COM changes and is removed on
  death or respec. The HUD requires this bonus to be active before showing it.
- Keep the native purchased-slot range large enough to render the new counter.
  Pause, travel and controller destruction use the existing lifecycle guards.

## 0.1.44 - Native colors on rank-dependent numbers, 1 November 2026

- Apply the native intermediate-rank style only to variable numerical values,
  including their sign and percent symbol. Labels and fixed duration keep
  their normal style; next-rank text retains the game's outer formatting.
- Blood Overdrive now follows the same rank-color rule as the five corrected
  tooltips, instead of showing green values from rank 1.
- Directly allocated maximum rank remains green with class-mod points too.

## 0.1.43 - Native partial-rank footer styling, 1 November 2026

- Use the active skill tree's intermediate-rank color and text template for
  the custom footer block. Labels, values, units and duration now share the
  native style, replacing the fixed orange applied only to individual numbers.
- Applied to Pain is Power, Fuel the Fire, Fuel the Rampage, Blood Twitch and
  Bloody Revival. Maximum-rank numbers keep the same green treatment as Maya.

## 0.1.42 - Restore explicit partial-rank colors, 1 November 2026

- Restore explicit orange markup for the custom rank values of Pain is Power,
  Fuel the Fire, Fuel the Rampage, Blood Twitch and Bloody Revival. Returning
  uncolored text rendered their current rank values white in the game.
- Keep maximum-rank green and Pain is Power's red accuracy penalty.

## 0.1.41 - Correct partial-rank tooltip color, 31 October 2026

- Replaced the `[skill]` markup on custom rank values with explicit orange
  (`#FF9900`). The game's skill markup resolves to `#FFDEAD`, which rendered
  yellow and did not match the orange lower-rank values.
- Applied the same partial-rank color to Fuel the Fire, Blood Twitch, Bloody
  Revival, Pain is Power and Fuel the Rampage. Green remains exclusive to
  directly invested rank 5/5.

## 0.1.40 - Skill rank-progress coloring, 31 October 2026

- Corrected skill-stat rank detection: custom values turn green only when
  `Grade` and directly allocated points both confirm rank 5/5. The initial
  partial-rank color used `[skill]` markup and was yellow; 0.1.41 replaces it
  with explicit orange.
- Blood Twitch's two custom per-stack stats are formatted from the native
  effective `Grade` instead of querying unallocated temporary skill definitions,
  which prevented the rank-5 green state from being detected.
- Bloody Revival keeps its FFYL, Gun Damage and Damage Reduction stat lines;
  only the redundant “per Second Wind” suffixes are omitted.

## 0.1.39 - Skill footer color and stat labels, 31 October 2026

- The attempted custom HTML color wrappers were unreliable and are superseded
  by the rank detection in 0.1.40 and the explicit orange partial-rank color
  in 0.1.41.

## 0.1.38 - Skill description polish, 31 October 2026

- Blood Twitch no longer grants Movement Speed; its native weapon swap,
  Bloodlust-scaled Melee Damage and Recoil Reduction remain.
- Previous footer-color and Bloody Revival line-removal behavior was corrected
  in 0.1.39; see the entry above.

## 0.1.37 - Fuel the Fire tooltip and Bloodlust skill tuning, 31 October 2026

- Fuel the Fire now appends a rank-aware `Direct Incendiary Damage` line to its
  lower skill description while preserving the native status-effect stat lines.
  The value is 4% per rank and is distinct from Burn/Status Effect Damage.
- Blood Overdrive's active movement/fire-rate threshold is 60 Bloodlust stacks.
  Its native HUD readiness highlight uses the same threshold.
- Blood Twitch preserves its native weapon swap and adds 0.05% Movement Speed,
  0.15% Melee Damage and 0.12% Recoil Reduction per skill rank per Bloodlust
  stack. The recoil effect uses the native weapon accuracy impulse modifier.
- Melee attack-speed scaling is not included: no supported native attribute
  for it has been verified, and changing weapon fire rate would affect guns.

## 0.1.36 - Bloody Revival damage reduction buff and tooltip formatting, 30 October 2026

- Bloody Revival Second Wind bonus: damage reduction increased from 2% to 3%
  per rank per Second Wind. Gun damage per Second Wind remains 2% per rank.
  At 5/5 with 5 stacks: +10% gun damage, +15% damage reduction (was +10%/+10%).
  The FFYL gun damage bonus remains 10% per rank. Constants now use separate
  `BLOODY_REVIVAL_DAMAGE_PER_SECOND_WIND` and `BLOODY_REVIVAL_REDUCTION_PER_SECOND_WIND`.
- Bloody Revival tooltip standardized with game conventions: upper text only
  describes mechanics ("Gun Damage during Fight For Your Life is increased. Each
  time you get a Second Wind gain Gun Damage and Damage Reduction up to 5 stacks
  until you die."), while rank-based values are displayed on lower stat lines
  via `SkillTreeGFxObject:GetSkillDescriptionForGrade`.

## 0.1.35 - Separate stack counters, 30 October 2026

- Salt the Wound retains its native HUD slot 1; Elemental Elation uses slot 2.
  Both native stack counts and gameplay effects are preserved. The two skill
  definitions must be loaded before the layout is changed.

## 0.1.34 - Blood Overdrive rework, 30 October 2026

- Replaced other-talent amplification with a new Blood Overdrive: any kill
  activates/refreshes its native duration; during the kill skill, each normal
  Bloodlust gain has a 20% chance per rank to gain one extra stack, capped at
  100% chance and one additional stack. Works below 80 stacks too.
- At 80 or more stacks with the kill skill active, gain 4% movement speed and
  3% fire rate per rank: 20%/15% at 5/5. Class mods increase the bonuses but
  not the chance beyond 100%. No ammo regeneration, no other-talent
  amplification, no return of the old melee/fuse bonuses. Blood Twitch keeps
  its swap/movement/melee behavior.
- Salt the Wound: native HUD slot 2 counter. Elemental Elation keeps its
  native position; no new icons created.
- Silence the Voices: adds Grenade Damage info to self-attack damage text,
  keeping the existing upper text and its highlight. Removes three camera
  anims and four screen-particle templates from self-attacks. Self-damage
  limited to one application per 3s of gameplay; no change to hit chance,
  damage value or skill description.
- Blood Overdrive: formula uses SkillGrade_BloodOverdrive instead of Taste of
  Blood rank. Keeps the native per-stack bonus attribute and the effective
  rank calculated by the game, including class-mod rank.
- Blood Twitch: preserves native weapon-swap behavior and adds 0.05% movement
  speed and 0.15% melee damage per rank per Bloodlust stack. Lower line shows
  per-stack values; other mods' effects on the same skill are not removed.
- Bloody Revival: removes the assault-rifle requirement; the native weapon
  damage bonus applies to any weapon type in FFYL and is now 10% per invested
  rank (instead of Bloodlust stacks). Keeps FFYL and on-foot/in vehicle-back
  checks. Each time Krieg enters FFYL and Second Winds (stands up without
  dying), he gains a permanent +2% gun damage and +2% damage reduction bonus
  per invested rank until he dies. Maximum 5 Second Wind bonuses stack for up
  to +10% damage and +10% damage reduction. Description and lower line match.
- Flame Flare: keeps burn duration and reignite chance, adding 15% burn
  damage resistance per rank. Uses the same native MT_Scale effect with a
  -0.15 coefficient, including effective class-mod rank. Lower line shows
  Reignite Chance and Burn Damage Resistance.
- Blood Euphoria: native one-point gamechanger at the center of Bloodlust
  tier 4, between Blood Trance and Boiling Blood. Regenerates 0.1% of maximum
  health per second per current Bloodlust stack: 50 stacks = 5%/s, 100 stacks
  = 10%/s. No active kill skill required. The old end-of-kill-skill heal is
  removed. Qualitative upper description with highlights, no 100-stack
  example; lower line: "Health Regeneration per Stack: 0.1%". All in-game and
  SDK menu texts are in English, including credits and warnings.
- Special melee: uses the initializer `Init_RampageBonusDamagePerLevel`
  with the formula `1 + 0.02 × GameStage`. Uses the native GameStage
  attribute, not experience level, with no OP8 cap. At level 80/OP10,
  expected GameStage 90 gives factor 2.8 vs 2.6 at level 80/OP0. These are
  factors of this component only, not final hit damage nor a universal
  6.6% bonus.
- Pull the Pin: one-point gamechanger allowing grenades in FFYL through the
  native attribute used for that permission. Uses the normal key, equipped
  grenade mod and normal cost; no free grenades, extra damage or refund.
  Removes the automatic death grenade, double XP and the damage bonus that an
  equivalent item may have added. Light the Fuse has a separate rework
  described below.
- Burn, Baby, Burn: 10% burn damage per point, plus 20% per point while on
  fire. Rank 5: +50% normally and +100% additional while on fire
  (+150% skill contribution in that state). Keeps the native trigger,
  effective rank with class mods, and original English descriptions.
- Pain is Power: replaces all old effects with up to five stacks, one per
  life-damage event. Each point gives +2% Critical Hit Damage, +2% Melee
  Damage and -2.5% Accuracy per stack; rank 5: +10% critical, +10% melee and
  -12.5% accuracy per stack, up to +50%/+50%/-62.5%. Self-damage and DoTs
  count when they remove HP; shield, healing and blocked hits do not. After
  5s without life damage loses a stack; then loses one every 2s. New HP loss
  renews the wait, even at the limit. Death/respawn, map and respec clear it.
  English menu; negative penalty in text, positive spread in engine.
  Native icon/counter in the bar above XP, using the skill menu image.
  Dynamic reservation without displacing other indicators; if no space, hides
  only this icon, not the bonuses. No Canvas drawing or second stack timer.
- Fire Fiend: original accuracy restored, 10% per point while on fire (50%
  at rank 5). Preserves melee ignite chance, reload, on-fire condition,
  Hyperion behavior and native min/max accuracy ratios.
- Hellfire Halitosis: the breath now sets Krieg himself on fire through a
  native effect, without self-hit or weapon-scaled self-damage. While on fire
  from any source, grants 15% movement speed. English description.
- Elemental Empathy: heals 10% per rank of corrosive, incendiary and shock
  status damage, vs 5% native; rank 5: 50%, following effective class-mod
  rank. Keeps damage events, life condition and native presentation.
- Numbed Nerves: 7.5% damage reduction per point even when not on fire;
  doubles while on fire. Rank 5: 37.5% normally, 75% while on fire. Keeps
  the nine native resistance channels and reciprocal conversion; does not
  simulate resistance by healing HP nor interfere with Pain is Power hooks.
  Preserves the native rank-5-limited table; no native COM boosts this skill.
- Raving Retribution: keeps fireballs and their trigger/cooldown. On learning
  the skill, all Krieg incendiary damage against enemies uses surface
  elemental factors equal to 1 for shield/armor, including burn. Flesh bonus
  and specific resistances/immunities remain native. This addition is
  passive, requires neither being on fire nor an active fireball. Does not
  change ally damage, other classes without the skill, or self damage.
  Uses a private damage-type variant only during that hit's native
  calculation, with try/finally reference restoration; no global table
  changed.
- Fuel the Rampage: rank 5 reduces 95% of direct self damage caused by Krieg,
  without reducing fire/shock/corrosive/slag status or other-author damage.
  Its 0.05 factor is independent of Numbed Nerves/armor; not added to the
  resistance denominator. Movement bonus is 35% at rank 5 for 12s; new direct
  self damage renews, does not stack. Shield can also activate. Absorbed/zero
  damage does not trigger. Movement removed in FFYL, death, respec or
  pawn/map swap. Time uses gameplay and does not expire during real pause.
  COMs use the existing cache; movement follows swap without extending the
  timer; reduction stays limited to 95%. Coop still needs separate testing.
- Light the Fuse: one-point passive; one grenade every 10s, cumulative with
  equipment regeneration. A private MT_PostAdd modifier adds 0.1 to the
  native rate, without replacing other modifiers or writing the stock.
  Removing the skill removes only that bonus. Does not increase capacity or
  rate by class mod. The old FFYL dynamite function and its movement bonus
  were removed. Pull the Pin still allows throwing normal grenades in FFYL.

Only the listed adjustments were implemented. The only tree addition is
Blood Euphoria. Does not change other skills, global scaling, COMs, ammo or
native kill-skill triggers. If another mod occupies that place, it diagnoses
the conflict instead of overwriting that mod's skill. Blood Euphoria
regeneration uses simulation time; the new Pull the Pin uses the native
grenade permission.

## Earlier versions (0.1.20 – 0.1.33)

Historical entries for versions 0.1.20 through 0.1.33 were removed from this
package at 0.1.34 because the full record is kept in TESTES.md (entries
0.1.1 – 0.1.34) and Suporte/KRIEG_KNOWLEDGE.md. They are not part of the
current installation and must not be restored into the code.
