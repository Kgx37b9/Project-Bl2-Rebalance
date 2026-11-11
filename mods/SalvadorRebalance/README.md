# SalvadorRebalance 1.0.1

A Borderlands 2 Python SDK mod by **Kgx37b9**, rebalancing Salvador's survivability, weapon bonuses and Gunzerking skills, with native class-mod scaling and off-hand fixes.

## Equipment interaction

Hard to Kill also scales the Rough Rider health contribution using the native order: (base health + shield health) multiplied by percentage health bonuses. Unequipping removes the shield contribution; a local cleanup handles known shield-slot effects left behind after removal. Other shield effects and other characters are unchanged. Fully restart the game after updating; do not hot-reload this change.

## Skill changes

- **Bus That Can't Slow Down:** moved to Brawn tier 2, center, between Asbestos and I'm the Juggernaut. Its former tier-4 left cell is empty; Just Got Real stays in the center. No skill is exchanged or removed. Restart completely after updating.

- **Get Some:** shooting an enemy reduces Gunzerking cooldown by **0.8 seconds per effective rank** (4 seconds at 5/5), retaining the native once-every-3-seconds trigger.

- **Yippee Ki Yay:** retains the original Gunzerking extension on kills and adds **0.3 seconds per effective rank on critical hits** while Gunzerking (**1.5 seconds at 5/5**), including class-mod points.

- **Berzerk (formerly Come At Me, Bro):** while Gunzerking, blocks shield regeneration, grants native damage resistance equivalent to 50% reduction on its own, and grants both guns a fixed +85% Amp Damage bonus. Every executed gun shot costs 20% of current health, including ammo-free shots. Other resistance sources use the native stacking formula. The old taunt/full-heal effects are removed. The health cost is nonlethal and does not count as a normal incoming-damage event.

- **Fistful of Hurt:** using the skill applies Shock to Salvador even when the punch misses. Native Shock lasts 2 seconds before duration resistance and uses minimal base status damage of 1; accepted applications can activate Asbestos. The special punch also makes surviving enemies hit take +10% damage only from the Salvador who landed it for 8 seconds. This is a separate received-damage multiplier. Repeated hits refresh the vulnerability without stacking. Original punch damage, knockback and cooldown remain intact.

- **Money Shot:** maximum last-round bonus decreases from the actual native +96% to +72% per effective rank (+360% at 5/5). Smaller magazines retain their reduced bonus. The footer shows the corrected maximum and the actual native 12-round magazine threshold; class-mod points remain native.

- **No Kill Like Overkill:** grants up to +200% Bonus Damage to both weapons, reduced from the original +400% maximum. The kill trigger, duration and projectile-count calculation remain unchanged.

- **Double Your Fun:** unchanged; retains its original extra-grenade behavior while Gunzerking.

- **Asbestos:** retains elemental status-duration resistance. Receiving an elemental status effect grants **3% Fire Rate per effective rank for 10 seconds** (+15% at 5/5); reapplications refresh the duration without stacking. Applies to both guns. The timed native HUD icon remains separate from the gameplay effect and uses free space; the former ammo-free effect is removed.

- **Keep It Piping Hot:** replaces its cooldown-only bonuses with one stack per second spent Gunzerking, up to 50 stacks. Each stack grants +0.14% Gun Damage and Accuracy per effective rank (+0.7% per stack at 5/5, up to +35% each). Both weapons benefit. A native HUD counter uses the skill icon and displays the real stack count, reserving a free slot without replacing another skill. The footer shows +0.14% through +0.7% per stack at ranks 1 through 5, with native-style current/next-rank colors and class-mod support. All stacks reset when Gunzerking ends; pauses do not advance the timer.

- **Auto-Loader:** passively grants +15% Reload Speed to both hands, in addition to its native reload-on-kill and Locked & Loaded interaction.

- **Quick Draw:** +10% Weapon Swap Speed per effective rank (+50% at 5/5), and +4% Critical Hit Damage per rank (+20% at 5/5).

- **Off-hand fixes:** Just Got Real, Lay Waste, Incite, 5 Shots or 6 and I'm Your Huckleberry now have independent native-context repairs. Existing paired effects are preserved to avoid duplication. Huckleberry checks each weapon's pistol type separately and uses the native effective rank.

- **Sexual Tyrannosaurus:** while Gunzerking, grants 4% Life Steal per effective rank, with -3% Fire Rate and -5% Critical Hit Damage per rank. At 5/5: 20% Life Steal, -15% Fire Rate and -25% Critical Hit Damage. Replaces the old damage-triggered regeneration.

- **All in the Reflexes:** removes melee damage; retains 5% Reload Speed per rank, doubled when starting a reload with an empty magazine (25% normally / 50% empty at 5/5). Each hand is handled independently.

- **Divergent Likeness:** different gun types grant Fire Rate instead of Accuracy (native 6% per rank, 30% at 5/5) while Gunzerking. The same-type gun-damage bonus is preserved.

- **I'm Ready Already:** +10% Gunzerking Cooldown Rate per effective rank (+50% at 5/5).

- **Ain't Got Time to Bleed:** regenerates 3% of missing health per second per effective rank while Gunzerking (15% at 5/5).

- **Just Got Real:** gun-damage coefficient increases to 12% per rank, retaining its continuous missing-health dependence: no fixed health threshold; at 5/5, 50% health gives +30% gun damage and 25% health gives +45%.

- **I'm the Juggernaut:** damage-reduction coefficient increases from 4% to 12% per rank. Native kill-skill trigger, duration and damage-reduction rules are retained.

- **Hard to Kill:** +4% maximum health and +4% native Damage Resistance per effective rank (+20% each in the stat block at 5/5). Resistance follows the native formula: the nominal 20% yields about 16.7% less incoming damage in isolation. Health regeneration remains removed. Class-mod points scale both bonuses; Rough Rider health still participates in the native health calculation.
- Equipped class-mod points use the native skill grade: 5 invested points plus 5 bonus points grant +40% maximum health. No invested points or item bonuses are rewritten.
- Native maximum-health stat text, current/next-rank previews and progression colors are retained.

## Requirements and installation

Requires Borderlands 2 and the modern Willow2 Python SDK/Mod Manager. For local testing, place this package in `sdk_mods/SalvadorRebalance/` and enable it in the Mod Manager. Close the game before replacing files. Restart to fully disable native changes. Co-op has not been validated.

## Known compatibility

Designed for Borderlands 2 with the modern Willow2 SDK. The off-hand repairs work without another patch and detect existing paired effects to avoid duplication. Other mods changing the same skills, skill-tree cells or weapon modifiers require compatibility testing.

Solo gameplay confirmations during development include the Piping Hot HUD/description and initial Berzerk behavior. Final release preparation passed 150 focused offline checks of the affected damage, HUD, class-mod, reload, equipment and lifecycle integrations, plus targeted HUD rechecks. Offline checks do not validate engine rendering or measure frame times. Confirm the final build in a fresh solo session before publication; co-op remains unvalidated.


## Documentation

[CHANGELOG](CHANGELOG.md) | [Development](DEVELOPMENT.md) | [License](LICENSE.md)

## Credits and license

Author: **Kgx37b9**. SDK infrastructure: **bl-sdk contributors**.
Personal gameplay use of the official unmodified release is permitted. Reusing original code or material requires prior written permission; see [LICENSE.md](LICENSE.md).
