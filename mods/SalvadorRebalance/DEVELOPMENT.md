# SalvadorRebalance - development

## Sexual Tyrannosaurus sign correction (1.0.1)

The player confirmed that the lower description still displayed a positive Fire Rate bonus. The 1.0.0 audit incorrectly treated the earlier explicit-minus presentation expectation as obsolete; native inverse formatting alone did not guarantee the negative sign in game. Restore SR_FireRate Description = Fire Rate: -$NUMBER$ and bDontDisplayPlusSign = True, retaining bDisplayAsInverse = True for magnitude formatting. Other presentations keep their sign rules. The underlying +0.03 fire-interval coefficient remains unchanged on both weapons: the actual effect is a penalty, not a Fire Rate increase. Six focused checks passed, including repeat-configuration stability. Native rendering of this patch needs confirmation after restart.

## Release audit (1.0.0, 10 November 2026)

Fistful of Hurt uses FIST_HURT_BONUS = 0.10, so its temporary received-damage multiplier is 1.10. Preserve the 8-second owner-only mark, one mark per target, nested-call suspension/restoration, immunity handling and unchanged self-shock. Its percentage footer is constant-derived. Historical 15% entries below describe earlier versions.

Concrete findings and changes:

- Asbestos calls visual maintenance at most every 0.1 second while its window/indicator exists. Its shared allocator previously walked registered skills, purchased skills, tracked children and native icons on every visual pass. Add a primitive-only cache scoped by player/world/movie identity, feedback path and physical slot; reuse it for one second only while icon/remap/registration remain valid. Conflicting remaps, icon loss or a new movie bypass the cache. Clear at tree initialization, enable and teardown. Preserve frequent expiry checks, native timer and immediate status-triggered gameplay activation; only the expensive allocation walk is coalesced.
- Reserve both logical and physical HUD slots when recursively visiting inactive tracked children. A full native HUD hides only feedback, never its gameplay helper.
- Native AdjustModifiers/BuildSkillEffects/ActivateSkill/DeactivateSkill/UpdateGrade can invalidate borrowed ActiveSkills/SkillEffects views. Rebind via WeakPointer, reacquire before restoration, and skip restoration if the object disappeared. After a rebind, record its live rank signature and return instead of traversing the old snapshot. This deliberately processes additional migrations on subsequent maintenance passes. Stable passes do not resubmit unchanged modifiers.
- Rough Rider stale-slot removal also invalidates the caller's snapshot. Piping Hot and visual helpers recover the current controller/manager and verify world/pawn identity after native callbacks. Do not retain actor references in allocation caches. Reconcile weapon bonuses after stack callbacks using a fresh owner.

Reviewed existing bounds and retained intentional work: general skill configuration/effect reconciliation remains gated at one second; short visual maintenance is idle when no Asbestos window or icon exists; weapon inventory recovery is bounded to 40 entries and used only for known outstanding Berzerk weapons; Fistful marks cap at 256 and amplification depth at 16. Damage/fire/status hooks already reject unrelated work early and use paired unconditional cleanup. Modifier construction is reused, and errors/verification messages are emitted once. Berzerk's per-shot underlying-damage check and one health debit per executed shot remain necessary for current bonuses/ammo-free shots and are not removed as redundant.

Validation: 150 selected offline checks passed across release regressions, Fistful, HUD, class-mod/effect refresh, reload, Rough Rider, Asbestos, Berzerk and directly adjacent integrations. Eighteen targeted HUD checks passed again after recursive physical-slot reservation. New regressions simulate skill destruction during modifier removal/build, invalidated later skill views, Rough Rider callbacks and stack callbacks destroying their owner, and verify that repeated Asbestos visual passes skip full allocation scans. Some old test expectations referred to former +100% Berzerk/+15% Fistful or duplicated sign text; align them with current authorized +85%/+10% and native inverse presentation. No other balance values changed.

No native gameplay session or frame-time profile of this build was captured. Offline checks establish structure and guarded behavior under mocks, not measured FPS gains or crash-free gameplay. Before publishing, restart with this build and check both weapons, empty/full reloads, COM/Rough Rider swaps, repeated Gunzerking, simultaneous Piping Hot/Asbestos icons, Fistful hit/miss/expiry and travel/return-to-menu. Co-op remains Unknown. No SDK archive or installed game files were changed. The permission-required personal-use license is unchanged.

## Bus relocation and balance (0.1.41)

Native Branch_Brawn rows 1 and 3 contain (Asbestos, ImTheJuggernaut) and (BusThatCantSlowDown, JustGotReal). Layout_Brawn masks are (true,false,true) and (true,true,false). Move Bus into row 1 center: skills become (Asbestos,Bus,Juggernaut) with all three occupied; row 3 retains only JustGotReal and uses (false,true,false), preserving its center column. Copy every retained tier struct before replacing arrays. Do not rewrite saved skill grades, create a replacement tree or change unlock costs. Validate six tiers, known row arrangements, occupancy masks and absence of Bus in any other row before mutation; tolerate either native/already-moved row and mask states for safe completion.

Placement runs in the existing Initialize PRE/configuration driver. A primitive branch/layout identity signature avoids repeated native tier reads/writes after successful configuration; reset it on enable and before initializing Salvador's tree. Missing assets remain pending. No new hooks or actor caches. Replacing the package requires a full process restart; rendering after an in-session reload is not supported.

Quick Draw now tunes native WeaponSwapTimeMultiplier to -0.10 in both base/per-grade fields, preserving native presentations and the +0.04 critical coefficient. Berzerk constant changes from 1.0 to 0.85, so a base damage of 100/200 becomes 185/370 before other native modifiers. No cost, resistance or shield changes. Thirteen focused/adjacent checks passed: five tree/Quick Draw, six Berzerk damage/footer and two maintenance lifecycle checks. Validate the native menu and skill allocation after restart; offline structures are not native rendering proof.

## Berzerk authorized damage restored (0.1.40)

The author confirmed the earlier +125% to +100% decision, recorded in 0.1.32. BERZERK_GUN_BONUS was still 0.75 in the current source; 0.1.39 mistakenly aligned documents to that stale value. Restore the actual coefficient to 1.0 and README/manager text to +100%, retaining the constant-derived footer. Do not infer intended balance from a source snapshot when explicit author instructions and history disagree. No cause for the earlier source regression is established.

The 19-test Berzerk run passed 18 checks and exposed a pre-existing missing <=1 HP fast return: SetHealth was called redundantly with 0.5 and 1.0. Restore the documented 0.1.30 no-write guard; the affected test then passed. All 19 distinct tests therefore pass, including both-hand damage, stacking/cleanup, failure rollback, text and cost boundaries. Resistance, 20% cost and nonlethal minimum are unchanged. Native confirmation remains pending.

## Fistful of Hurt self-shock and Berzerk description (0.1.39)

The activation event OnMeleeOverrideSkillActivated now also executes a private Behavior_AttemptStatusEffect leaf targeting the same player variable as Behavior_SpecialMove_6. This is independent of PunchedEnemy and therefore works structurally on a missed punch. Context is copied from that native player-context node; TargetContext[0] uses BCONTEXT_UseContextObject and a BVARLINK_Input bound to the same consolidated variable. Shock uses GD_Shock.StatusEffect.Status_Shock, StatusEffectChance 1000, InstigatorChanceModifier 1 and StatusEffectDamage 1. The high chance is an application attempt, not an immunity bypass. Native base duration is 2 seconds before duration resistance, including Asbestos. No scaled punch/self-hit damage is added, and the normal punch damage type stays unchanged.

Only append owned BehaviorData2/variable links/output links and repoint the activation event outputs after publishing those arrays. Never copy or replace the whole sequence or VariableData: opaque native payload must remain intact. Validate the existing activation/context layout and packed-index bounds first; reuse an existing leaf after re-enable. Cache only provider/behavior integer identities to avoid rebuilding arrays on stable one-second maintenance. No UObject context is retained across worlds, no manual audio event is posted, and the native status owns its application/end callbacks. No new Python hook or per-frame work. Shared Shock definitions and existing vulnerability are untouched.

Berzerk source already had BERZERK_GUN_BONUS=0.75, while public docs/metadata still claimed +100%. This pass changes the footer to read that constant and the damage-reduction/cost constants, and aligns README/metadata to +75%; no damage balance change is made. Earlier version descriptions remain historical.

Twenty-seven relevant/adjacent offline checks passed: six graph/configuration, sixteen existing vulnerability, three footer and two maintenance/lifecycle. They establish structure, idempotence, preserved native indices, missing-asset handling and text consistency, not successful native status application. Final in-game test: restart, use Fistful into empty space, verify a brief Shock and Asbestos for 10 seconds when learned; repeat on cooldown completion and on an enemy, checking existing vulnerability. Native immunity may prevent the status. Verify Shock audio ends and no status remains after travel/death. Co-op remains untested.

## Hard to Kill native resistance (0.1.38)

HEALTH_PER_RANK is 0.04. Add nine native damage-type channels (the eight impact/burn/shock/corrosion channels already used by native resistance plus AmpImpactDamageModifier) as TARGET_Self/MT_Scale -0.04 per rank. The author explicitly chose native resistance, not independent damage multiplication. With no other resistance, the nominal 0.20 at rank 5 gives incoming factor 1/1.20, about 16.7% reduction. Other resistance sources follow native combination rules. Preserve original health modifiers/constraints and unrelated effects, remove duplicate named resistance targets, and own every retained struct before replacing native arrays. Resolve all resistance assets before any mutation; missing streamed assets remain pending.

The existing live-effect traversal now includes Hard to Kill in attribute-binding comparison and safely rebuilds native bindings when needed. Grade is never rewritten or combined again with COM metadata. Stable configurations do not rewrite arrays or rebuild modifiers. No new combat hook or polling was added. The existing description hook preserves native health text and appends Damage Resistance with queried effective rank and established current/preview colors. Health regen stays zero; Rough Rider remains PreAdd. Base 1000 and shield 500 with rank 5 now gives 1800 max health, returning to 1200 without the shield.

Thirty-one relevant/adjacent offline checks passed: Hard to Kill 16, Rough Rider 10, resistance 4 and adjacent footer 1. Tests cover missing assets, native channel configuration, idempotence, safe rebind, COM/respec, equipment removal and colors. These are not native damage measurements. Fresh-process gameplay should verify health/equipment changes, resistance and previews with/without a COM; co-op remains untested.

## Fistful of Hurt status feasibility (research only)

Native data exposes OnMeleeOverrideSkillActivated with SkillInstigator and PunchedEnemy with Enemy/SkillInstigator/HitLocation. Its melee definition currently deals normal damage with StatusEffectChance and StatusEffectDamage zero. Separate private Behavior_AttemptStatusEffect behaviors can target the enemy on confirmed contact and Salvador on activation, without converting the punch damage type. Our Hellfire Halitosis implementation already provides a self-status precedent, but this Fistful extension has not been implemented or engine-tested. Self application on activation would occur even on a miss; making it hit-dependent is also possible. Status type, chance, duration and DoT damage still need a design choice. Native immunities/resistance remain relevant. A real self-status can activate Asbestos; preserve status audio/start/end lifecycle and trigger self only once per use.

## Damage balance and Just Got Real thresholds (0.1.37)

Only JUST_GOT_REAL_DAMAGE_PER_RANK (0.10 to 0.12) and PIPING_HOT_PER_RANK (0.001 to 0.0014) change gameplay coefficients. Existing revision/refresh handling updates Just Got Real's native initializer and display coefficient; existing stack helper and footer consume the Piping Hot constant for both hands. No new hooks, timer changes or extra combat queries.

Native dumps confirm JustGotReal has only the shared OnFootOrRidingInBack constraint, with no low-health threshold evaluator. Init_JustGotReal_DamageCalc_P2 computes current health divided by maximum health; P1 uses its negative result with Level/Power 1 to obtain the missing-health fraction. The mod retains that calculation and changes only P1.Multiplier. Intended bonus is `0.12 * effective_rank * (1 - current_health / maximum_health)`: at 5/5, full health gives zero, 75% health gives 15%, 50% gives 30%, and 25% gives 45%. The 60% theoretical maximum is approached near zero health, not granted in full upon crossing 50% or 30%. Shield value is not part of the condition. Native periodic context updates remain unchanged.

Piping Hot still gains one stack per second in Gunzerking, capped at 50, reset on termination; at 5/5 each stack gives +0.7% damage/accuracy and 50 stacks give +35% each. COM ranks are counted once, with current/next fractional stat colors preserved. Seven focused checks passed (Just Got Real 2, off-hand 1, Piping gameplay 2 and footer 2). These confirm offline structure/coefficient consistency, not measured engine damage.

## Asbestos timed Fire Rate (0.1.36)

Accepted-status PRE/POST pairing is retained, including actual reapplication detection, nested frames and rejection of resisted attempts. The primitive local deadline is now always current gameplay time plus 10 seconds, independent of effective rank. The existing native resistance effects are unchanged. A separate private, untracked timed SkillDefinition applies MT_Scale -0.03 per rank to WeaponFireInterval and WeaponFireInterval_Offhand. Grade comes from the accepted active parent or the current active parent on maintenance; never add COM metadata again. Native timed expiry provides removal without relying on the HUD. Reapplications adjust the live helper StartTime using deadline minus Duration instead of deactivating/reapplying modifiers. Only changed grades/deadlines are written.

The former ShotCost/ConsumeAmmo/magazine-refund hooks, firing frames and inventory-chain recovery were removed. The existing active-only 0.1-second HUD cadence also checks bonus expiry/rank; idle returns before native lookups, and no new tick hook was introduced. The helper remains independent of menu icon registration/full slots. The HUD still uses its own effect-free timed leaf and shared allocator. Death, respec and mismatched context remove only the private bonus; teardown guards avoid old actors. The footer preserves native resistance, appends ranked Fire Rate with established colors, and shows a fixed, uncolored 10-second duration.

Divergent Likeness was explicitly excluded by the author before completing this update and retains its prior damage/fire-rate behavior. Focused tests cover accepted/resisted status, refresh, both-hand helper configuration, COM grades, expiration, death/respec/travel, HUD coexistence/full slots, duration/color and absent ammo hooks. Offline tests do not prove native timing or multiplayer replication. Final test after restart: get a status at 1/5 and 5/5 (including a COM), verify the two-gun speed bonus and 10-second icon, reapply near expiration, test respec and ordinary ammo consumption.

## Get Some missing configuration (0.1.35)

The reported stale description exposed absent GET_SOME constants, configuration and maintenance registration in the current runtime; the older regression fixture and development record still specified 0.8 seconds per rank. Native dumps confirm root display-only constant -0.6 and timed GetSome_Active cooldown-rate modifier with grade attribute, scale 0.2 and duration 3 seconds. Restore display -0.8 and active scale 0.8/3, preserving the native grade resolver, duration, graph and presentations (FloatPrecision=1). Resolve and validate both definitions before writes; pending assets retry via existing maintenance. The shared live-effect tuning also repairs the active child scale without resetting its timer or double-counting COM ranks. Stable float32 values do not cause repeated writes. Four focused checks cover display/gameplay agreement through rank 11, native trigger preservation, pending assets, unsupported duration rejection and registration. This is offline evidence, not measured engine cooldown timing.

## Native Rough Rider ordering restored (0.1.34, 8 November 2026)

Remove the live-slot PreAdd-to-PostAdd migration. Hard to Kill retains 6% maximum health per rank; its percentage again includes native Rough Rider flat health. Current formula: `(base + shield health) * (1 + percentage health bonuses)`. With base 1000, shield 500 and Hard to Kill 5/5, maximum health is 1950 while equipped and 1300 after removal. Class-mod ranks scale the percentage once. The 0.1.23 ordering section below is historical and superseded.

`_maintain_rough_rider_health` only tracks current local equipment slots and removes a known slot that survives unequipping. Stale definitions are deduplicated before native deactivation; do not inspect the old ActiveSkills snapshot afterward. Stable equipment passes do not rewrite or remove/re-add shield modifiers. No shared definition edits, stored total-health baseline, synthetic healing or new polling. A full restart is required: this is not a migration of a session already modified by an older version.

Twenty-six offline checks passed: ten Rough Rider and sixteen imported adjacent Hard to Kill checks. Repeated equip/removal, ranks 0/1/5/10/11, native modifier preservation, stale cleanup and lifecycle guards are covered. Engine resource-pool/current-health clamping remains unverified. After restarting, compare maximum health with/without Rough Rider repeatedly at 5/5, after a COM swap and after respec. Unequipped maximum must return to its corresponding shield-free value. Co-op remains untested.

## Yippee Ki Yay critical extension (0.1.33)

Native dumps show the kill graph applies an attribute impulse to D_Attributes.Skills.StartTime_DualWield. Its skill-context resolver targets Skill_Gunzerking and its property resolver targets StartTime. The additional critical extension updates that same live property without modifying native kill events, effects or the graph. WillowPlayerStats.IncrementPlayerCriticalHitStat provides an event-based trigger; controller.PlayerStats identifies the local recipient. The hook requires local authority, an unpaused live Salvador context and active Gunzerking/Yippee instances. Effective Skill.Grade supplies COM ranks. Accepted events add 0.3 * rank seconds; pellets and both hands share a gameplay-clock cooldown of 0.5 seconds, checked before reading ActiveSkills. Action callbacks reset the primitive cooldown state; no actor references survive the callback. No new per-frame polling or damage replay is introduced. The description appends a current/next-rank value to the native kill stat and omits the cooldown. Five focused tests plus two adjacent lifecycle tests passed. In-game timing and remote co-op remain unvalidated.

## Hard to Kill (0.1.1)

Native data confirms that Hard to Kill is `GD_Mercenary_Skills.Brawn.Diehard`. Its first effect scales `HealthMaxValue_Player`; the second uses `Init_DieHard_HealthRegenCalc`, and a third null-target effect supports the regeneration stat text.

The maximum-health base and per-grade values are 0.06. Both regeneration-related effects use zero constants with no attribute/initializer. The native regeneration presentation is removed; the maximum-health presentation remains native.

Class-mod points are already included in the active skill Grade and native UI calculations. The mod never adds GradeModifier again or writes saved grades. Existing effect snapshots are migrated with owned struct copies and `bForceRefreshModifiersNextTick`, without restarting skill instances. Stable data is not rewritten; numeric comparisons tolerate float32 round trips.

Local maintenance runs once per second with class, pause, world and teardown guards. No UObject is stored across calls. Tests are focused on this skill; gameplay and co-op require separate engine validation. Record all new technical findings in the [central knowledge guide](../Conhecimento/GUIA_CONHECIMENTO_MODS.md).


## I'm the Juggernaut (0.1.2)

Native skill `GD_Mercenary_Skills.Brawn.ImTheJuggernaut` uses eight impact/status damage modifiers referencing `Att_Juggernaut_DamageReductionPerLvl` (native base -0.04). The skill's own base/per-grade coefficients now use -0.12 directly, avoiding stale designer-attribute instances. Native modifier types, trigger, lifetime and presentation remain intact. Its native damage-reduction calculation is retained; the coefficient is not a promise of a separate final damage multiplier. Both skills share one native ActiveSkills traversal per maintenance pass.


## Just Got Real (0.1.3)

`Init_JustGotReal_DamageCalc_P1` retains its native health-dependent Level/Power/Offset calculation; only Multiplier receives the constant coefficient 0.10. The presentation helper in `JustGotReal.SkillEffectDefinitions` also uses 0.10. The gun-damage effect retains the original initializer and native grade scaling. This bypasses the old designer coefficient without changing health-based behavior or adding repeated combat hooks. A primitive revision refreshes active snapshots only when the initializer actually changes.


## Ain't Got Time to Bleed (0.1.4)

P1 (`Init_AintGotTimeToBleed_RegenFormula_P1`) retains its missing-health P2 in Multiplier. Its Level coefficient is now 0.03, with attribute/initializer cleared; Power and Offset are preserved. The native regeneration effect keeps the P1 reference, while its stat helper uses 0.03. The native ActionAugment behavior continues to control activation. Scoped effect matching prevents Hard to Kill's regeneration removal from touching this skill. Native data lists an older designer coefficient of 0.008; the requested new coefficient is set directly, without multiplying that historical value.


## I'm Ready Already (0.1.5)

`GD_Mercenary_Skills.Rampage.ImReadyAlready` directly scales `D_Attributes.ActiveSkillCooldownResource.ActiveSkillCooldownConsumptionRate`. Both base and per-grade values change from 0.05 to 0.10. Existing shared native snapshot migration handles equipped class-mod ranks. This changes cooldown rate, not a direct percentage subtraction from cooldown duration. No new hook or maintenance loop.


## Divergent Likeness (0.1.6)

The native path is `GD_Mercenary_Skills.Gun_Lust.DivergentLikness` (native spelling). Its AccuracyCalc initializer checks `DualWield_DifferentWeaponType`; its per-rank resolver is 0.06. Two native spread effects now target the main/off-hand WeaponFireInterval attributes, preserving the initializer and negative scale. The two accuracy-minimum effects become zero. Same-type damage and presentation helpers are retained. The stat label becomes Fire Rate.

Changing an attribute requires rebuilding native modifier contexts: remove currently applied modifiers, build effects from the modified definition, and reattach only if the skill was active. No skill activation/timer reset. Owned snapshots are restored if BuildSkillEffects fails. Stable snapshots skip rebuilding. Tests cover both hands, original condition references, paused skills and failed-build recovery; engine validation remains pending.


## All in the Reflexes (0.1.7)

The native skill has two Reload Speed effects (-0.05 base/upgrade) and a melee effect (+0.04). Melee is neutralized and its presentation removed. Base reload effects and their presentation remain native. An extra MT_Scale modifier of -0.05 times the native effective rank is attached only to the reloading weapon's `ReloadTime`, doubling this skill's contribution while preserving other reload bonuses.

`StartReload` reads the current magazine; `TimeWeaponReload` also reads the native `AmmoLeftInClipDuringReload` snapshot. Completion, stopping, aborting, unequipping and inventory removal remove only the dedicated modifier. The existing 1 Hz maintenance checks equipped weapons only while a primitive pending-address set is nonempty, and repairs interrupted reloads or COM/rank changes. It uses `GetReplicatedReloadState` / `EWeaponReloadState.RELOADSTATE_Reloading`; `IsReloading` belongs to WillowPawn, not WillowWeapon.

No actor or modifier is retained globally. A modifier is scoped under its live weapon and referenced by the native modifier stack. Existing native/other-mod entries are preserved. Context and departure checks precede mutation. Main and off-hand weapons receive independent modifiers. In-game timing, reload animation and weapon-specific exceptions remain to be validated in the combined test.


## Sexual Tyrannosaurus (0.1.8)

The learned parent `GD_Mercenary_Skills.Brawn.SexualTyrannosaurus` becomes `SKILL_TYPE_ActionAugment` before native skill-tree initialization. Its damage event, behavior provider and timed-child link are removed. The old `_Active` child's regeneration is zeroed and migrated if already present.

Four native effects replace regeneration: PlayerConvertDamageToHealingPercent (+0.04 per grade, MT_PostAdd), main/off-hand WeaponFireInterval (+0.03 per grade, MT_Scale; positive interval means lower fire rate), and PlayerCriticalHitBonus (-0.05 per grade, MT_Scale). Each targets self. The native damage pipeline owns life-steal healing and composition with other healing sources; no hit-processing hook is added.

Three private presentations show Life Steal, Fire Rate and Critical Hit Damage through native grade/preview/color handling. Fire Rate uses inverse presentation for the negative sign. Owned effects and presentation dependencies are prepared before gameplay data is committed. A live one-to-four-effect layout change rebuilds native contexts through the existing helper. This does not reclassify an already-initialized skill tree: restart fully before in-game testing.

Six focused offline tests and 28 adjacent Salvador tests passed. They cover coefficients, both hands, old trigger/child removal, stable UI creation, context rebuilding with unchanged COM grade, pending assets and paused instances. Gunzerking start/end, FFYL, actual healing and co-op still require engine validation.


## Solo feedback and off-hand investigation - 1 November 2026

The user reported the current adjustments working in-game in solo. This is not a measured per-hand comparison or co-op validation.

Native-data review identified the classic off-hand cases: Just Got Real (gun damage), Lay Waste (fire rate), Keep It Piping Hot (gun damage), Incite (reload), 5 Shots or 6 (ammo effect), and I'm Your Huckleberry (pistol bonuses/child activation and grade). The official patch history documents the same six cases: [primary changelog](https://github.com/BLCM/BLCMods/blob/master/Borderlands%202%20mods/Community%20Patch%20Team/Full%20UCP%20Changelog.txt).

The installed `Binaries/01_UCP.txt` and the workspace TXT have their six fixes enabled. File configuration does not prove that a running session executed them. SalvadorRebalance currently preserves an existing off-hand Just Got Real effect but does not create it in an unpatched game. Independent repairs are not implemented in this research step. Existing explicit two-hand changes in Divergent Likeness, Reflexes and Sexual Tyrannosaurus remain intact.

Future repairs should inspect existing paired effects, preserve each skill's native conditions and grade, and avoid duplicating player-wide critical/healing bonuses. Full evidence and a per-hand test plan are in the central knowledge guide. No gameplay code or TXT changed in this review.


## Independent off-hand implementation (0.1.9)

This section supersedes the earlier research-only status. The implementation is based on native skill effects and attribute/context definitions; it does not import an external patch, its command lists or authored helper definitions.

For Just Got Real, Lay Waste, Keep It Piping Hot, Incite_Active and 5Shotsor6, the code checks the learned/active native definition for the intended off-hand target. A valid existing target is preserved. Only when absent is an owned copy of the primary effect created, changing its target attribute to the left-hand counterpart. Its initializer, random resolver, grade, modifier mode and source condition remain live. In 5 Shots or 6, no random result is evaluated or stored by Python. Player-wide critical, melee, grenade and movement effects are not duplicated.

I'm Your Huckleberry uses four private AttributeInitializationDefinitions. Each computes its native per-rank coefficient multiplied by the corresponding Weapon_Is_Pistol or OffhandWeapon_Is_Pistol attribute. The skill's effective grade is applied once by the engine. The whole-skill main-pistol constraint and native child-activation graph are retired; on-foot constraints are preserved and the legacy child's weapon effects are zeroed. Existing external paired effects on the four managed targets are reconciled to this single set of independent conditions. Two TARGET_None helpers keep the native stat preview independent of currently held weapon types.

Both added and replaced layouts are migrated through native BuildSkillEffects with scoped modifier removal/readdition. Active kill-skill duration and native grade are not restarted. Stable definitions do not rewrite arrays; private formulas do not allocate again after creation. The existing 1 Hz pass handles the work without another tick/damage/fire hook.

Offline validation: 10 focused off-hand tests plus 34 adjacent Salvador tests passed. They cover all five mirrored contexts, no duplication with existing pairs, pending assets, native random/conditional reference preservation, current Just Got Real tuning, Huckleberry per-hand inputs, correct native grade, legacy-helper removal, stable state and snapshot rebuilding. Native presentation rendering and actual damage/fire-rate/reload/ammo outcomes require a full-restart in-game comparison, separately with and without other patches. Solo feedback for 0.1.8 is not evidence of these new repairs; co-op remains unvalidated.


## Quick Draw (0.1.10)

The native PlayerCriticalHitBonus effect changes from 0.02 to 0.04 in base and per-grade values. The WeaponSwapTimeMultiplier effect (-0.07 per grade) is preserved. Critical-hit damage uses the player-controller attribute, so no separate off-hand critical effect is added. Native presentation and effective-grade handling remain in use.


## Auto-Loader (0.1.11)

The original one-point passive's behavior provider, KillEvents, swap/Locked & Loaded interaction and flavor-text helper remain intact. Two reload effects use MT_Scale base -0.15, upgrade 0, targeting self through main/off-hand reload attributes. This is a fixed 15% bonus when learned. Existing effects on those targets are reconciled rather than duplicated. A private native stat presentation displays the reload value alongside the original quote. Existing shared snapshot rebuilding handles the new layout. No new reload/fire/damage hook is added.

Three Auto-Loader tests and 22 adjacent shared-helper/Tyrannosaurus tests passed offline. Engine validation of reload speed and the preserved original triggers is pending.


## Keep It Piping Hot (0.1.12)

Native inspection confirmed the old passive is gated by two AttributeExpressionEvaluators: action cooldown current value > 0.1 and cooldown consumption rate > 0. The rework removes only those constraints, retaining on-foot/custom constraints, and changes the parent to an ActionAugment. All former gun/melee/grenade effects are replaced by two TARGET_None display effects; its native effective grade remains owned by the skill tree. It no longer participates in the generic off-hand mirroring pass.

A private, untracked passive (SR_PipingHotStacks) contains four MT_Scale effects: main/off-hand WeaponDamage +0.001 and main/off-hand WeaponSpread -0.001 per combined grade. Combined grade = min(50, floor(gameplay seconds in Gunzerking)) * native parent Grade. Disabling subject-to-grade rules on the helper prevents a second class-mod contribution. UpdateGrade changes the existing helper; stable counts/ranks produce no writes or reactivation. Native contexts follow weapon swaps. The helper reserves no HUD slot.

WillowPlayerController.ActionSkillCallback (ActivatedSkill, bActivated), USkill.ActivatedTime and UpdateGrade were checked against the native SDK headers; the callback anchors the session in WorldInfo.TimeSeconds and deactivates only the private helper at the end. If the manager is updating, removal is deferred to the safe existing maintenance pass. A missed-start recovery uses the active parent's ActivatedTime. Session storage contains only controller/world/pawn identities and a timestamp. Travel/destruction clears it without dereferencing old skill handles; dead/inactive/unlearned parents remove the helper. Timed progression reuses the existing 1 Hz maintenance scan, catches up after delayed ticks and excludes paused gameplay through world time. No per-shot, damage hook or extra HUD machinery was introduced.

Offline evidence: nine focused tests cover native/float32 view stability, removal of legacy bonuses, both hands, per-second progression/cap, class-mod increases/decreases, repeated stable/pause time, immediate end/reset, deferred cleanup during manager updates, shared live migration, travel/character guards, missed-start recovery and death. The 16 shared-maintenance and 10 off-hand tests also passed. These mocks do not prove engine activation, rendering or damage outcomes.

In-game check after a full restart: allocate 5/5, compare both hands at 0/10/50 seconds (+0/+5/+25% each), pause and resume, end/restart Gunzerking, swap to/from a class mod, respec, and confirm no bonus remains during cooldown. Co-op remains unvalidated.


## Keep It Piping Hot footer and HUD (0.1.13)

User observation supersedes the 0.1.12 offline assumption that native floating-percent presentations were sufficient: the engine showed +1%/-1% and did not follow the queried rank correctly. The gameplay coefficients were already +0.001 damage and -0.001 spread per combined grade. This is not evidence that actual outgoing damage had those incorrect displayed values. A scoped GetSkillDescriptionForGrade hook now returns only the two stat lines, deriving both positive percentages from args.Grade once (Grade includes COM; do not add GradeModifier). Current and next queries are formatted independently. GradeModifier is used only to determine invested rank for color selection, with the owner's actual invested rank preventing a 4/5 preview from turning green early. Numeric tokens use SkillIntermediateGradeColor and SkillLockedModifierTextHTML below the cap; only numbers/sign/percent turn green at the purchased cap. Plain-text queries have no markup.

A separate SR_PipingHotHUD native SkillDefinition clones the menu icon, then removes every gameplay effect, event, constraint and child link. Passive/Infinite/Triggered, MaxGrade50, bSubjectToGradeRules=False. Its CustomStackCount resolves this visual skill's Grade via a private SkillAttributeContextResolver and ObjectPropertyAttributeValueResolver; it never resolves the gameplay helper's combined grade or tree rank. The gameplay helper remains untracked. Registration retains the visual leaf in the current HUD; Python keeps no movie/actor references between passes.

The allocator follows the established Krieg counter pattern: reserve native row types2/3/5/6 from all registered entries (even inactive), both logical and remapped slots, purchased definitions and children, active definitions and occupied cached icons. Protect graph traversal with a visited set and512-node limit. Recheck after AddTrackedSkill; edit only this visual's RemappedSlot and only increase NumPurchasedTrigRespSlots within the native cache capacity. A future collision moves/deactivates only the visual. If no slot is free, hide the counter while retaining gameplay. UpdateSkillIcons runs on counter changes or missing cached art, not on every stable pass. Counter errors are isolated and cannot interrupt the gameplay update or end cleanup.

Gameplay readback now verifies exactly one helper with the requested Grade. Milestone logs report the accepted grade and nominal damage/spread coefficients at1/10/25/50 stacks once per effective rank per enable; they do not measure target damage. This allows the next game test to distinguish a missing activation from a presentation defect. The reviewed current unrealsdk.log recorded Salvador's configuration at21:24:05 local time on2026-11-01 and teardown at21:30:43, with no Salvador exception. Installed0.1.12 source matched the workspace when inspected. There were no stack measurements, so the log cannot confirm the previous runtime bonuses.

Validation:9 UI/HUD regressions,9 stack/gameplay regressions and16 adjacent shared-maintenance tests passed offline. Coverage includes fractional ranks1..5, COM current/next queries without double addition, green-preview prevention, actual menu icon, visual count versus combined grade, inactive/remapped/child/cached reservations, purchased-slot range, collision/full-HUD behavior, stable/no-redundant refresh, re-registration after HUD reset, end/restart cleanup and rendering failure isolation. No other character suite was run. In-game check: restart, compare footer ranks1..5 and a COM swap; observe the counter growing during Gunzerking, disappearing at its end and returning from1 next time; activate other HUD skills and open/close menus; inspect applied/HUD log lines. Actual engine rendering/gameplay and co-op remain pending.


## Keep It Piping Hot game evidence and Asbestos (0.1.14)

The user confirmed the0.1.13 footer and stack HUD render correctly. Current SDK log,2026-11-01 local21:46:09/21:46:18, shows rank5 with stacks1/10, accepted combined grades5/50, gun_damage0.005/0.05 and spread_modifier-0.005/-0.05; the visual registered slot7. No Salvador error was recorded. This verifies the requested helper grades/coefficients were accepted and complements the observed HUD, but does not directly measure enemy health loss.

Native Asbestos data: GD_Mercenary_Skills.Brawn.Asbestos is a passive with five resistance effects (Amp, Corrosive, Ignite, Shock, Slow duration resistance), native coefficient attribute and on-foot constraint. The implementation changes only upper prose and appends a rank-specific Ammo-Free Duration footer to the original result via GetSkillDescriptionForGrade. Effects, initializers, event/constraint data, skill classification and original presentation objects are not replaced. Queried Grade already includes COM and is not combined again with GradeModifier.

StatusEffectsComponent.ApplyStatusEffect has no return value, so a POST alone does not prove acceptance. PRE/POST_UNCONDITIONAL pair all invocations, including ignored/blocked/nested calls. Only the current local Salvador's OwnerTarget is eligible. Accept status types Ignite/Corrosive/Shock/Amp/Slow; exclude Healing/Unknown. Snapshot matching ActiveStatusEffects into primitive signatures (definition, duration, elapsed time, author, region) and counts before/after. A new instance or refreshed elapsed time confirms application; unchanged/resisted attempts grant nothing. Consume nested observations in enclosing snapshots to avoid attributing the same application twice. Read the native active Asbestos grade only on eligible application, with invested points required. No per-frame status polling or damage tick hook.

A primitive tuple(controller,world,pawn,deadline) stores the window; deadline=WorldInfo.TimeSeconds+0.3*effective rank. A new application refreshes it without adding durations. Travel/destruction/enable clear the window; new contexts are rejected. Expired firing clears it so later shots return through a primitive fast path. World time preserves remaining duration across pause. The player can trigger it outside Gunzerking; it affects guns in both hands and not grenades.

Ammo saving follows the project's proven paired firing strategy: FireAmmunition/SharedFireAmmunition PRE scopes zero ShotCost only for an eligible equipped gun, ConsumeAmmo PRE blocks resource consumption within that shot, conditional POST marks native execution and POST_UNCONDITIONAL restores cost. SharedFire nested in Fire uses the outer scope, including deadline crossing. Only the observed magazine loss of an executed shot is corrected; never refill an empty clip, touch the reserve, undo independent gains or supply free reloads. Resolve the weapon anew in the current hands or bounded inventory chain; never retain weapon wrappers between callbacks. Cleanup can resolve a dead-but-valid current pawn to restore ShotCost if death occurred synchronously inside fire, while fresh eligibility still excludes death. A first-window/first-shot log is bounded rather than emitted every tick/shot. Cooperation with third-party ammo/fire overrides and co-op still need live testing.

Offline evidence:11 focused tests cover native-data preservation/idempotence, accepted/resisted/unknown/healing/foreign/unlearned applications, elapsed-time reapplication, effective COM ranks, refreshing deadline, exact expiry and fast-path clearing, both hands, nested native fire, recomputed cost, blocked fire, empty magazines, independent gains, death cleanup, travel and native-footer preservation. Sixteen adjacent shared tests also passed. Native headers confirmed ApplyStatusEffect/ActiveStatusEffect fields; no unrelated character tests were run.

In-game check after restart: allocate1/5 and5/5, confirm old resistance line plus0.3/1.5-second duration; fire both guns after a fresh elemental affliction and verify clip/reserve remain unchanged only inside the window. Reapply a status to refresh, continue firing beyond expiry, test a COM and inspect Asbestos window/shot logs. Actual engine validation of the new feature remains pending.


## Double Your Fun (0.1.15)

Native inspection: GD_Mercenary_Skills.Rampage.DoubleYourFun is already an ActionAugment, MaxGrade1, on-foot constrained. Its original TARGET_None critical-hit dummy presents the double-grenade value; the real IsSkillListeningForThrowGrenadeOverrideEvent effect enables an OnThrowGrenadeOverrideSkillActivated behavior that dispatches a special move. Both effects and the behavior provider are removed, along with obsolete presentation/child/event links. The parent classification, rank cap and on-foot constraint stay intact.

A single native ResourcePoolAttributeDefinition effect targets D_Attributes.Ammo_Grenade_Protean.Ammo_Grenade_ProteanActiveRegenerationRate, MT_PostAdd, TARGET_Self, base0.1, per-grade upgrade0. No class-mod multiplication of the fixed interval. This follows the project's native grenade-regeneration pattern: the resource pool handles timing, capacity and fractional progress; equipment contributions remain additive. Native Gunzerking activation/removal gates the effect instead of a new Python timer. No additional firing, grenade-spawn or tick hook is introduced. The existing shared native-effect rebuild removes a pre-existing listener snapshot without restarting the skill; a full process restart is still required to retire old graph registrations safely.

GetSkillDescriptionForGrade returns the new fixed regeneration-interval footer instead of the original double-grenade dummy text. Source and descriptions are versioned0.1.15. Validation:4 focused tests cover listener/graph removal, fixed additive coefficients, native action scope/cap/constraints, no repeated writes, missing-resource retry, cached-effect migration without rank/timer restart and the new footer.16 shared-maintenance,6 Tyrannosaurus and3 Auto-Loader tests cover the directly affected shared coefficient/type/target handling; all29 pass offline. No other character suite was run.

Engine check after restart: spend grenades, enter Gunzerking and observe approximately one recovered grenade per10 seconds, confirm regeneration stops at Gunzerking's end, confirm only one grenade is thrown per input, and compare with a grenade-regenerating item equipped. Native capacity/fractional pool behavior and co-op need game validation; offline tests do not prove these outcomes.


## Asbestos HUD and rank colors (0.1.16)

User feedback confirms Asbestos and Double Your Fun gameplay from0.1.15. This change adds only Asbestos visualization and its duration-number formatting. A shared rank-value formatter preserves Piping Hot output while giving Asbestos the same native intermediate numeric style and green invested-cap treatment. Grade already includes COM; GradeModifier is used only to infer invested points, and the owner's current invested rank prevents the rank5 preview from turning green when still4/5. Original Asbestos resistance footer text remains supplied by the native function. Only the duration number is colored; the label and seconds unit remain normal.

SR_AsbestosHUD clones the Asbestos menu icon and is a private Passive/Timed/Triggered visual, MaxGrade1, no CustomStackCount, no grade rules and no effects/presentations/constraints/events/behavior/child links. It is never linked as a gameplay child. Native InitialDuration is set to the exact remaining WorldInfo.TimeSeconds deadline when the visual starts. A confirmed reapplication restarts only this visual's native timer; the unchanged gameplay deadline remains the sole source of truth. Stable passes neither reactivate nor restart the timer. The native timed skill removes the icon at expiry even without firing. The project's existing allocator reserves registered/logical/remapped/child/active/cached slots, rechecks after native registration and repairs the purchased prefix; a full HUD affects visualization only.

Display starts immediately after confirmation. A lightweight0.1-second retry/cleanup call precedes the existing1-second skill-maintenance gate to support0.3-second rank1 windows and retry unavailable movies/manager updates. With no window or pending visual, it returns before native queries. Only primitive identities/deadline are retained between passes. Remote controller ticks cannot consume the local retry deadline. Pause defers HUD work without changing the gameplay deadline. Death/expiry clear pending state and remove the visual when safe; travel/destruction clears primitive state without touching departing movie handles. Missing cached art or a rebuilt registration is repaired in the current movie. Visual exceptions remain isolated from ammo gameplay.

Validation:8 focused tests cover timed icon/menu art, exact remaining duration, no copied resistance/gameplay effects, coexistence with Piping Hot, fixed/non-repeated activation, renewal, expiry without firing, idle fast path, inactive/full-slot reservations, pause/cache repair, death/travel guards, green/current/next/COM/plain-text output and processing before the1Hz gate.11 Asbestos gameplay tests and9 Piping Hot UI tests also pass (28 total). No other character or unrelated suite was run. In-game check after restart: observe the icon for0.3/1.5seconds at1/5 and5/5, refresh it with another status, let it expire without firing, pause/resume, and confirm simultaneous Piping Hot remains in its own slot. Check green duration at5/5 and non-green preview at4/5. Native rendering of this new visual remains pending.


## No Kill Like Overkill (0.1.17)

Native data confirms the parent owns the kill graph and tracks NoKillLikeOverkill_Active. The child has separate MT_PostAdd main/off-hand WeaponDamage effects, each referencing its own Init_NoKillLikeOverkill_DamageCalc initializer. Each initializer divides LastKillExcessDamageDealt by the corresponding projectile count and caps the result through its native Part2 initializer. Reducing only the excess-damage multiplier would not halve capped outcomes.

The change sets BaseValueScaleConstant=0.5 in both BaseModifierValue and PerGradeUpgrade of the two active damage effects, outside their unchanged initializers. Expected relation is new bonus=0.5*completed native bonus, including its cap. No kill attribution, projectile divisor, graph, rank, timer or HUD data is replaced. The parent description specifies50% excess damage; the original flavor footer remains. Shared effect maintenance migrates active snapshots without reactivation or a new damage hook. Reconfiguration assigns0.5 rather than multiplying repeatedly.

Four focused tests plus16 adjacent shared tests passed: owned float32 views/idempotence, both initializer references and unrelated native data preserved, half outputs below/at the native cap, cached active migration without changing duration/grade, and deferred streamed-child loading. Engine damage comparison remains pending after restart; tests validate configuration and migration, not actual target damage.


## Money Shot (0.1.18)

Native dump explains the displayed-versus-effective discrepancy: Init_MoneyShot_DamageCalc multiplies Att_MoneyShot_DamagePerLevel (0.8) by SmallClipGovernor_P1, which is min(WeaponClipSize,12)/Att_MoneyShot_MinClipSizeForFullBonus (10). Thus the actual native maximum is0.8*12/10=0.96 per rank, despite the stock coefficient line showing0.8 and threshold line showing10. Setting the coefficient to0.72 would produce0.864 at the cap, missing the requested target.

The change retains the entire initializer/governor graph and sets the real LastShotInClipBonusModifier effect's outer BaseValueScaleConstant to0.75 in both base/per-grade formulas. Therefore native0.96*0.75=0.72 per effective rank; small magazines are reduced proportionally while their native trigger/condition remains. The modifier is the player-wide damage-enhancement attribute, not a weapon-specific context requiring an added off-hand effect. The shared native skill grade applies once, including COM points. No initializer, designer coefficient, graph or per-shot handler is replaced.

Two display-only helpers are reconciled: null-attribute damage base/upgrade0.72 and TARGET_None WeaponPerShotAccuracyImpulse helper base12/upgrade0. This changes only the stated maximum/threshold, not real accuracy or magazine size. Existing native presentations, grade colors and current/next queries remain engine-owned. An existing externally corrected0.96/12 display layout is normalized without duplication or compound scaling. Mods that separately change the native magazine governor require a compatibility check.

Offline validation:5 focused tests cover initializer/native graph preservation, real maximum calculation versus the incorrect0.864 alternative, short/full magazines, effective ranks1/5/11, idempotence/float32 views, pre-corrected display layouts, cached skill migration without grade changes and pending assets. Four adjacent Overkill tests cover the shared completed-initializer scaling branch and16 shared-maintenance tests also passed (25 total). In-game restart and last-round comparison with/without a COM, short/full magazines and both hands remain pending. Tests prove data/migration, not measured engine damage.


## Fistful of Hurt received-damage vulnerability (0.1.19)

The skill and special-move graph remain native. Data inspection identifies GD_Mercenary_Skills.Misc.MeleeDefinition_FistfulOfHurt as the exact IIDamageCauser for the special punch. Checking only the FistfulOfHurt_Active helper would be unsafe: its4-second melee listener could also observe an ordinary punch during cooldown. WillowAIPawn.TakeDamage POST exposes DamageCauser, InstigatedBy and Pipeline; the mark is granted only for the dedicated causer, the local authoritative Salvador with the point allocated, a hostile surviving current-world pawn and a positive native damage summary (health or shields). Misses, blocked/resisted zero-damage attempts, other players and normal melee do not mark. A first-confirmation log records attribution. Engine attribution still needs a real game test.

Marks last8 gameplay seconds and refresh without stacking. Their keys/values contain only world/address, target CreationTime/path, controller address and deadline; capacity256 with expired/world cleanup prevents unbounded growth and stale actor reuse. A current-world maintenance pass prunes history, without scanning pawn lists. The debuff benefits Salvador and friendly allies by default; hostile attackers do not inherit it. Solo/host authority is required; co-op support remains unvalidated.

The multiplier uses the same six Controller Received*DamageModifier fields as Elemental Mastery: bullet, grenade, melee, rocket, status and skill. A temporary MT_PostAdd modifier has Value=current received factor*0.15, yielding current*1.15 before native damage proceeds. This composes multiplicatively with an existing received multiplier and keeps ordinary gun/critical/elemental calculations native. Zero/immunity factors and healing are preserved. Known damage sources touch only the required field; unknown sources prepare all six. Private property-resolver attributes and per-depth modifiers are rooted non-world assets reused within a16-depth bound; no target/controller/movie object is stored in the pool.

Paired AdjustDamage PRE/POST_UNCONDITIONAL frames always remove only this feature's modifiers. Nested damage on the same recipient temporarily suspends the enclosing Fistful modifier, computes its own eligibility and restores the parent afterward, avoiding double amplification or leakage to hostile attackers. Partial installation errors roll back and still owe POST cleanup. No manual recursive AdjustDamage call or extra hit is generated. Travel PRE removes in-flight modifiers while actors are still current; controller destruction only invalidates synchronous references, avoiding probes of an already departing actor. Marks are cleared on travel/destruction/enable. Without marks or an enclosing active scope, PRE returns before damage actor/attribute lookup.

Fourteen focused tests plus16 shared-maintenance tests passed: exact causer, confirmed shield/health hits, unlearned/friendly/foreign/resisted cases, duration refresh, multiplicative composition, cap/identity expiry, nested same/hostile attacks, team/owner-only policies, healing/immunity, source-specific/unknown categories and pool reuse, partial failure, unconditional cleanup, travel and no-mark fast path. Original skill data/idempotent prose also pass. Mocks do not prove native attribution or actual damage; after restart, compare identical hits before/after the special punch, verify +15% for8 seconds, test normal melee on cooldown and a missed swing, then inspect the two Fistful logs. Co-op and interactions with mods that generate already-scaled secondary damage require live testing.


## Fistful of Hurt owner-only clarification (0.1.20)

The author explicitly chose only the Salvador who landed the punch. This supersedes0.1.19's temporary team default: FIST_HURT_TEAM=False rejects any other damage-instigating controller, including friendly allies. The existing nested-scope suspension still prevents another attacker from inheriting an enclosing owner's factor. Upper prose now says increased damage from you and replaces the previous suffix rather than appending a duplicate. The15% factor,8-second deadline, refresh rule and native punch remain unchanged. Fourteen focused tests pass with an asserted owner-only default; no unrelated suite was rerun.


### Fistful world/type guard follow-up (0.1.20)

Pylance reported optional-member access on world.bDeleteMe/TimeSeconds and an optional key passed to dict.pop. The earlier conditional lookup made mark non-None at runtime, but that did not narrow the correlated world/key variables for the type checker. Validate world is not None and not bDeleteMe explicitly, then create key: tuple[int,int] without a None branch. This also exits safely during target-world teardown. Fifteen focused tests and AST parsing pass, including a new missing/departing-world regression. Pyright is not installed in the current environment, so the editor diagnostics were addressed structurally rather than claiming a full static-check run. No gameplay constants or unrelated skill changed.


## Berzerk replaces Come At Me, Bro (0.1.21)

Author confirmed two choices: the75% Post-Add bonus is fixed and unrelated to health spent; the50% reduction uses native resistance rather than an independent incoming-damage multiplier. The internal native path stays GD_Mercenary_Skills.Brawn.ComeAtMeBro; SkillName is Berzerk. Both parent/legacy child behavior providers and old child links/events/effects are retired, removing taunt/full heal/old threat/DR activation. A full process restart is required to discard pre-existing graph registrations. Parent remains a native one-point ActionAugment with on-foot constraints; the native Gunzerking lifetime gates its static effects.

Shield regeneration is blocked through D_Attributes.ShieldResourcePool.ShieldRegenerationDisabled, MT_PostAdd base1/upgrade0, using its verified RegenerationDisabled pool counter. Do not overwrite rates, drain the shield or reset shared pool flags. Native skill modifier removal restores the previous counter contribution. Direct shield-restoration effects are distinct from passive/active/idle regeneration and are not rewritten.

Nine DamageTypeModifers channels match the native general-resistance pattern, including AmpImpactDamageModifier. Each MT_Scale coefficient is -R/(1-R)=-1 for R=0.5, upgrade0. This gives50% reduction alone using the reciprocal native conversion; additional resistance combines under the normal native formula, e.g.1/(1+1+0.6), not0.5 times another reduction. No damage-pipeline hook was added for defense.

The WeaponDamage attribute's actual native property resolver points to InstantHitDamage. Berzerk attaches a uniquely named weapon-local AttributeModifier of type MT_PostAdd with Value=0.75*underlying InstantHitDamage on each equipped gun. Underlying=current InstantHitDamage minus our existing post-add amount. Repeated sync therefore does not compound the bonus, and other native scale/post-add sources remain intact. If underlying damage changes, remove only our modifier, reread the native recalculation and reattach the updated amount. Verify the resulting field equals1.75*underlying; a partial/rejected application is tracked and rolled back. This avoids a self-referencing initializer that could continuously amplify its own result. Weapon modifiers remain attached throughout Gunzerking, including between shots, so projectile damage queried after launch still sees the active bonus. Engine behavior of delayed projectile/weapon swaps needs testing.

Native ActionSkillCallback start/end tracks only primitive owner/world/pawn identities. The existing shared1Hz skill traversal also recovers the active parent, refreshes equipped guns and removes stale/legacy snapshots. Fire PRE refreshes only the current gun's amount and records eligibility; nested SharedFire for the same gun owns no extra scope. Conditional POST confirms native execution; POST_UNCONDITIONAL consumes15% of then-current health via SetHealth once for an executed shot. Different guns each pay sequentially. Ammo-saving/zero ShotCost never bypasses the health cost, but empty clips and PRE-blocked calls pay nothing. Using current health at completion preserves native healing during fire rather than restoring an old health snapshot. Resource consumption bypasses native shields/resistance and does not dispatch a synthetic damaging hit. Cost has a1-health floor and does not raise a value already below1; dead/invalid/new-world pawns are never charged.

OnUnequip/ItemRemoved hooks remove only the tagged modifier. A bounded inventory lookup handles a missed unequip event without retaining weapon objects. Gunzerking end and travel PRE clean current owned guns; Destroyed clears primitive tracking without touching old pawn/world/weapon handles. Stable guns do not repeatedly remove/readd modifiers. No per-shot skill-manager scan, projectile scan or reserve-ammo manipulation is introduced. Bounded logs report the first verified native PostAdd field and the first confirmed health cost.

Validation:18 focused tests cover complete legacy replacement, native shield/resistance data and reciprocal math, fixed/no-grade scaling, missing-asset retry, both hands, no compounding, changing native gun damage, confirmed and nested same/different-gun shots, blocked/empty/unallocated fire, free-ammo/Asbestos interaction, healing/nonlethal health handling, unequip/swap/inventory fallback, partial Add failure rollback, foreign-modifier preservation, travel/delayed POST guards, cached effect migration and one-point footer colors. Eleven Asbestos and16 shared-maintenance tests also passed (45 total). No Maya/Krieg/global suite was run.

In-game test after a full restart: allocate Berzerk, compare each gun's damage inside/outside Gunzerking, spend shield and confirm recharge stops only during Gunzerking, compare incoming damage alone and with another resistance, fire each gun and verify current health changes by15% per executed shot (not per pellet), test Asbestos, canceled/empty fire, reload/swap and repeated Gunzerking activations. Confirm pressing the old taunt input no longer restores health. Watch the Berzerk PostAdd/health-cost logs and confirm damage modifiers are gone after Gunzerking ends. Actual engine behavior and co-op remain pending.


## Berzerk wording (0.1.22)

Author requested Amp Damage as the user-facing name for Berzerk's existing75% Post-Add Gun Damage. All source display/runtime strings and current README/manager wording use Amp Damage; the native enum, tagged modifier, formula and numeric values are unchanged. Upper skill prose says Each shot costs some Health; the footer still explicitly shows15% Current Health Cost per Shot. Historical technical sections retain MT_PostAdd terminology to explain the implementation. AST comparison with all string literals normalized confirms no executable non-text change. Only the two affected footer tests and syntax/metadata checks are relevant; no gameplay suite is rerun. User reported the rework working in initial gameplay.


## Rough Rider health ordering (0.1.23)

Native ShieldDefinition GD_Sage_Shields.A_Item_Custom.Shield_Buckler uses a Special02 health slot with MT_PreAdd, Init_HealthBonusFromShields_Formula and the native item-grade progression. Hard to Kill uses MT_Scale. Their original order is (base + shield health) * (1 + percentage bonuses). The new local applied-slot order is base * (1 + percentage bonuses) + shield health: base 1000, Hard to Kill 30%, shield 500 gives 1800 instead of 1950. The shared shield definition and health initializer are never edited.

EquippedItems and RuntimeAttributeSlotSkill identify the current local Salvador's shield slot. Only its applied health effects and matching AttributeModifier.Type change to MT_PostAdd. Native AdjustModifiers removes the old registration before migration and adds it again after; owned SkillEffects copies preserve other fields. Failure restores the previous layout/type. The native value and rank formulas are retained; no displayed total health is captured as a new base, and no health modifier stack is cleared.

A primitive path/owner/world/pawn registry identifies previously equipped slots. If one remains in ActiveSkills after unequip, only that local slot definition is deactivated, after traversal. Equipment RPC callbacks also work while the inventory is open; the existing one-second maintenance is a fallback. Travel/destruction/enable discard identities without retaining actors. Stable passes do not write/rebind or log repeatedly. Other characters are excluded by the caller.

The inspected game log contained no detailed Rough Rider health/modifier records, so the exact original source of the reported lingering health was not established. The ordering defect is supported by native data; orphan cleanup is defensive. 24 targeted tests (16 existing Hard to Kill and 8 new slot tests) pass in simulation. This does not prove Unreal resource-pool behavior. Required live test: full restart, record maximum health without shield; equip and remove Rough Rider repeatedly at 5/5; unequipped maximum must return to baseline; swap a class mod and repeat. Check logs for migration/cleanup failures. Co-op remains untested.


## Fixed footer presentation and Berzerk cost (0.1.24)

Auto-Loader retains the native -0.15 reload-time effects in both hands. Its custom attribute presentation exposed a negative number despite the inverse flag; the presentation is now excluded and a scoped GetSkillDescriptionForGrade hook appends the positive +15% Reload Speed label. The same hook appends Fistful of Hurt's +15% vulnerability below native punch stats. Calls to the native formatter use prevent_hooking_direct_calls; unrelated skills are ignored. Learned one-point values turn green, while unlearned previews remain plain. The upper prose omits these percentages. No combat formula changed for either skill.

Berzerk health cost is0.20 instead of0.15. Its fixed footer derives the percentage from BERZERK_HEALTH_COST, preventing UI drift. Sequential shots from1000 health now leave800 then640 before other healing. Existing blocked-shot, nested firing, both-hand, free-ammo and nonlethal-floor tests remain relevant.37 affected tests passed; no unrelated module suites were run.


## Native Double Your Fun restored (0.1.26)

The earlier Double Your Fun rework documented above is retired. Its constants, grenade-regeneration tuning branch, configure routine, footer hook and live-layout migration registration are removed. No replacement graph or native definition snapshot is written. A fresh game process loads the original assets and this mod leaves them untouched. Fully close and restart the game after updating; simply disabling/re-enabling or replacing the file in a running process cannot undo already-mutated definitions. Two focused regression tests verify no configuration lookup/write of the native skill and no grenade-regeneration tuning for it.


## Auditoria de estabilidade e repeticoes (0.1.27, 2026-11-03)

Asbestos: o hook global de status consultava o jogador local antes de descartar aplicacoes em inimigos. Agora verifica primeiro o Controller/PlayerClass do alvo; personagens remotos ainda passam pela validacao completa de propriedade. A renovacao confirmada da janela continua imediata, incluindo reaplicacoes, mas o indicador usa o mesmo limite de100ms da manutencao visual. Um teste com20 aplicacoes em sequencia confirma20 atualizacoes do prazo de gameplay e apenas uma sincronizacao visual nesse intervalo. A proxima sincronizacao usa o prazo mais recente. A taxa maxima visual foi limitada; isso nao comprova ganho de FPS no jogo.

Fistful of Hurt: enquanto existia qualquer marca, danos contra outros atores tambem alocavam um escopo e liam o AIController. Agora mundo/identidade da vitima descartam alvos sem marca antes dessas operacoes, exceto quando existe um modificador temporario pai que precisa ser suspenso/restaurado. Foram preservados os testes de dano aninhado, rollback e viagem. Os modificadores temporarios ainda precisam ser adicionados/removidos em cada dano pertinente, pois mante-los entre hits afetaria atacantes nao autorizados.

All in the Reflexes: eventos de termino de recarga e unequip de armas sem identificador em _reflexes_pending retornam antes de consultar jogador, skill manager ou pilha de modificadores. A limpeza de uma arma realmente rastreada continua nativa. O estado primitivo e zerado no enable; nao se elimina o acompanhamento em viagem sem antes resolver a limpeza nativa.

Rough Rider: listas ActiveSkills copiadas nao devem ser usadas depois de helpers serem desativados. A analise do escudo foi movida para antes da sincronizacao de Piping Hot, apos a travessia principal. Um teste faz o acesso ao helper removido falhar explicitamente, impedindo regressao da ordem. Definicoes orfas repetidas sao deduplicadas antes de DeactivateSkill. O tipo de modificador, valor e comportamento de vida nao foram rebalanceados nesta etapa.

Validacao:81 testes unicos relevantes/adjacentes passaram (Asbestos13, HUD8, Fistful16, Reflexes9, Rough Rider10, Hard to Kill16, Piping UI9). Sintaxe e metadados verificados. A leitura do unrealsdk.log atual nao encontrou linhas de erro do SalvadorRebalance, mas corresponde a versao instalada antes desta auditoria e nao prova o comportamento da nova versao. Ainda exigem teste real: reaplicacoes de status durante tiros com ambas as armas; recargas vazias/canceladas e troca de COM; termino de Gunzerking; troca de escudo; retorno ao menu e reentrada. Co-op continua sem validacao.

## Berzerk 0.1.28 (2026-11-03)

The fixed weapon-local MT_PostAdd Amp Damage factor is now 1.25 of underlying InstantHitDamage, producing 2.25x underlying damage while active. The in-game footer derives its +125% label from BERZERK_GUN_BONUS. The existing health cost, native resistance, shield regeneration block and lifecycle are unchanged. All 18 focused Berzerk tests pass; gameplay confirmation is still pending. Earlier 0.1.21-0.1.24 sections document historical values.

## Sexual Tyrannosaurus footer sign (0.1.29)

The native main/off-hand WeaponFireInterval effect stays +0.03 per rank and therefore slows firing. In-game feedback showed its inverse presentation rendering a positive Fire Rate number. The presentation now uses a literal minus before $NUMBER$ and suppresses the generated plus sign; Life Steal and Critical Hit Damage presentations retain their earlier flags. The six focused tests passed; verify the rendered current and next-rank footer in game.

## Berzerk nonlethal health-cost guard (0.1.30)

The original charge already used a 1 HP floor but still called SetHealth when current health was at or below it. The POST_UNCONDITIONAL cost now returns before the native write at <=1 HP and clamps a paid shot to at least 1 HP. The guard only concerns Berzerk cost; incoming enemy or status damage remains governed by the game. Focused validation: 18 Berzerk tests pass, including 0.5, 1.0 and 1.1 HP cases.
