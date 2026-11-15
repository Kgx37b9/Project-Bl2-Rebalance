# AxtonRebalance 1.1

A Borderlands 2 PythonSDK mod by **Kgx37b9** that rebalances Axton's skills and Sabre Turret, adds **Kill Mastery**, and provides native HUD indicators for custom buffs. Skill ranks follow class-mod bonuses without adding equipment points twice.

## Sabre Turret

- **Base cooldown:** 30 seconds.
- **Base health:** increased by 40%. Longbow grants another 50%, for a combined 2.10x native base health.
- **Damage progression:** an additional linear bonus from +30% at GameStage 1 to +275% at level 80 OP10 (GameStage 90). The underlying damage continues to follow the game's global level-scaling rate.
- **Tree positions:** Resourceful takes Crisis Management's original slot; Last Ditch Effort takes Resourceful's original slot; Crisis Management takes Last Ditch Effort's original slot. Nuke becomes the Guerrilla capstone and Double Up the Gunpowder capstone.

## Turret upgrades

| Skill | Changes |
| --- | --- |
| Laser Sight | Retains turret accuracy; adds 6% Turret Damage and 4% Turret Fire Rate per point. |
| Scorched Earth | Retains rocket pods, removes the hidden 15% turret bullet damage penalty, and grants passive 10% Explosive Damage to Axton. |
| Phalanx Shield | Increases barrier capacity by 70% and grants Axton passive 20% Shield Capacity. |
| Longbow | Retains long-distance deployment and grants 50% Turret Health. Faster throwing belongs to Mag-Lock. |
| Mag-Lock | Retains wall/ceiling attachment, increases enemy attention and makes throwing 75% faster. A turret destroyed by damage refunds 35% of the total cooldown once per deployment cycle; expiry and recall do not qualify. Scripted enemy targeting can override threat priority. |
| Double Up | Retains the second gun and slag rounds, with a 40% turret weapon damage penalty. Grants passive 25% Cooldown Rate. Direct turret hits make enemies take 25% more damage from Axton and allies for 10 seconds; further hits refresh without stacking. The multiplier is independent of slag. |
| Nuke | Grants 250% turret weapon damage with a 25% Fire Rate penalty. Its blast and elemental status damage use a separate linear bonus from +30% at level 1 to +250% at level 80 OP10. Knockback is removed. |
| Gemini | Retains two turrets and adds 20% Turret Fire Rate. Each active turret projects a **20-meter defensive aura** with 50% native Damage Resistance for Axton and allies. Overlapping auras do not stack. A native HUD icon indicates protection. |

## Player skills

Unless a skill is a single-point upgrade, values below are **per skill point**. Effective class-mod ranks are supported. Native damage-resistance and shield-delay percentages are engine coefficients; their effective reductions follow the game's formulas and other modifiers.

| Skill | Changes |
| --- | --- |
| Ready | Retains passive 8% Reload Speed. Completing a reload grants 5% Fire Rate for 6 seconds, refreshing without stacking. A native icon indicates the buff. |
| Expertise | Retains original bonuses and adds passive 15% Recoil Reduction, including native Hyperion handling. |
| Able | Damage grants independent 3-second stacks, up to five, each regenerating 0.4% maximum health per second per point. The native 0.5-second trigger interval remains. Five stacks at 5/5 regenerate 10% maximum health per second. |
| Grenadier | Retains grenade capacity and adds 4% Explosive Damage. |
| Crisis Management | While shields are depleted, gain 5% multiplicative damage and 6% native Damage Resistance per effective skill point. The damage multiplier covers Axton-attributed damage, including owned turret hits, and multiplies separately with Last Ditch Effort and Double Up. |
| Impact | Retains gun damage and replaces melee damage with 5% Accuracy. |
| Overload | Grants 10% Magazine Size and regenerates 0.2% of maximum reserve ammunition per second per effective point for all six weapon categories. At 5/5: +50% Magazine Size and 1% reserve ammunition per second. Does not regenerate the magazine or grant a chance to consume no ammunition. |
| Metal Storm | Retains its native Fire Rate bonus and kill trigger. While active, each shot has a 6% chance per effective point to consume no ammunition (30% at 5/5). Replaces the former Reload Speed bonus. Kill Mastery also strengthens this chance; the final chance is capped at 100%. |
| Steady | Grants passive 5% Grenade Damage. While holding a rocket launcher, also grants 6% Rocket Launcher Damage and 8% Reload Speed. |
| Battlefront | Retains gun/grenade damage and its turret-deployed condition; replaces melee damage with 5% Critical Hit Damage. |
| Duty Calls | Hitting an enemy with a weapon shot while aiming down sights grants one stack per shot, up to 20. Each stack grants 0.5% Critical Hit Damage and 0.4% Reload Speed per skill point: +50% critical damage and +40% reload speed at 5/5 with 20 stacks. After 3 seconds without aiming, lose one stack every 0.25 seconds. Aiming pauses decay and resets the grace period. A native HUD icon shows the count. |
| Ranger | Completing an empty-magazine reload empowers that magazine with 10% Amp Damage and 5% Fire Rate per point. The bonus ends when the magazine empties, another reload starts/completes, or the weapon is switched. A partial reload cannot preserve it. A normal HUD icon indicates the buff, without a counter or special color. |
| Healthy | Grants 5% Maximum Health and passive regeneration of 0.6% maximum health per second per point, doubled while shields are depleted. |
| Preparation | Grants a fixed 7% Shield Capacity per point. Native Damage Resistance scales proportionally with current shield fullness, reaching 30% per effective point at full shields and zero at empty shields. Replaces health regeneration. |
| Pressure | Grants the full 7% Damage per effective point whenever shields are above zero (+35% at 5/5); the damage bonus ends at empty shields. This bonus adds only to Crisis Management before multiplying other damage sources. Shield Recharge Delay reduction still scales with missing shields, up to 24% per point at empty shield. Zero-capacity shields grant maximum delay reduction and no Pressure damage. |
| Forbearance | Reduces enemy elemental status duration by 8% per effective point. Your own explosive or area damage and your Sabre Turret's explosive damage steal 1% Health per point for Axton. At 5/5: 40% shorter status duration and 5% Life Steal. Axton's own damage does not require a deployed turret; non-explosive turret damage does not trigger Life Steal. |
| Quick Charge | Regenerates 1.2% maximum shield per second per effective point and grants 8% Reload Speed per point while the kill skill is active. At 5/5: 6% shield regeneration per second and +40% Reload Speed. No longer grants Damage Resistance. |
| Resourceful | Taking health/shield damage reduces remaining turret cooldown by 0.3 seconds per point. Each credited enemy kill extends the active Sabre Turret deployment by 1 second per point (5 seconds at 5/5), with no accumulated extension limit. Sentry remains independent; Gemini receives one extension per kill for the shared deployment. |
| Last Ditch Effort | Grants 8% multiplicative damage against enemies below 50% health, affecting Axton's weapons, melee, grenades, status damage and owned turrets. Replaces the old Fight For Your Life effects. |

### Kill Mastery

A new five-point Guerrilla passive in tier 4, **right of Grenadier**, using the game's **Unstoppable Force icon**. Grants **10% Kill Skill Duration** and **5% Kill Skill Bonus Strength** per point (+50% duration/+25% strength at 5/5).

It strengthens **Onslaught, Metal Storm and Quick Charge**, including Quick Charge's shield regeneration and Reload Speed. This is a relative increase: a 30% skill bonus becomes 37.5% with Kill Mastery 5/5. Ranger and other custom timed buffs are not native kill skills and are unaffected. Native kill triggers, original Gaige skills and Krieg class mods are not changed.

## Requirements

- Borderlands 2 on PC.
- The modern Willow2 PythonSDK and Mod Manager.
- The game's Mechromancer compatibility assets for Kill Mastery's menu icon.

No other character rebalance mod is required.

## Installation

1. Place the published `.sdkmod` in the game's `sdk_mods` directory, or place the extracted `AxtonRebalance` source folder there. Do not install both formats simultaneously.
2. Enable **AxtonRebalance** in the Mod Manager.
3. Restart the game after installing or replacing files so native skill definitions and the tree are rebuilt.

## Compatibility and known limitations

- Disable other mods' **Axton skill changes and skill-position changes**, including those options in UCP. Other mods that rewrite the same definitions or damage inputs may conflict.
- Global level-scaling changes continue to affect underlying turret damage; this mod adds its own level bonuses on top.
- **Co-op has not been validated.** Some custom damage/cooldown features handle only the local authority player; independent remote-player behavior is not guaranteed.
- Fast travel clears temporary custom buffs/stacks and resets the native kill-skill timer. Passive bonuses and allocated points remain.
- The Bee's duplicate full-recharge sound is suppressed without changing shield stats or Amp Damage. Native zero-damage impacts can still restart recharge delay, as observed against Terramorphous; this mod does not suppress those attacks.
- Latest adjustments still require final in-game confirmation. Focused test results, investigations and validation limits are recorded in [DEVELOPMENT.md](DEVELOPMENT.md); version history is in [CHANGELOG.md](CHANGELOG.md).

## Credits

- **Kgx37b9**: project author.
- **Borderlands PythonSDK / bl-sdk contributors**: SDK and mod infrastructure.
- **UCP and 55tumbl's Skill Scaling Patch**: research references used to identify native turret damage inputs. The bonus curve and Python implementation here were developed for this mod.
- **Gearbox Software / Borderlands 2**: game assets, native skill behavior and icons.

## License

You may download and use the official, unmodified release for your own gameplay. Prior written permission from **Kgx37b9** is required to reuse original code or other original material. Redistribution and modified releases are not permitted. Third-party material remains subject to its own terms. See [LICENSE.md](LICENSE.md).
