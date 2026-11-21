# Zer0 Rebalance 1.0.7

A standalone Borderlands 2 PythonSDK rebalance by **Kgx37b9**, expanding Zer0's weapon choices, survivability and skill interactions. Includes reworked movement bonuses, critical-hit effects, decoy damage and stack mechanics, with effective class-mod ranks and HUD counters where applicable.

## Skill changes

Values below are per effective skill point unless stated otherwise.

| Skill | Changes |
| --- | --- |
| Iron Hand | Retains 3% Maximum Health and replaces Melee Damage with 5% native Damage Resistance. |
| Grim | Grants 8% Cooldown Rate and regenerates 1.1% Maximum Shield per second per point while the kill skill is active. |
| Tw0 Fang | Retains its native extra-shot chance and effective class-mod ranks. The extra shot does not consume ammunition; the initial shot retains its normal cost. |
| Fearless | Grants 5% Fire Rate and 4% Gun Damage per point while any shield remains. |
| Resurgence | Restores 5% Maximum Health per point on any enemy kill, regardless of missing health. Critical hits additionally restore 4% Maximum Shield. |
| Kill Confirmed | Gains one stack every 0.25 seconds while aiming; loses one every 2 seconds after unzooming. Retains the five-stack cap. |
| Velocity | Grants 5% Gun Damage and retains Bullet Speed; removes Critical Hit Damage. |
| Many Must Fall | Enemy kills during Decepti0n can renew it regardless of damage source. Weapon firing uses the native resolution grace when the talent is active; an already-ended action skill is not reactivated. |
| Pin point (formerly Optics) | Grants 20% Accuracy, 12% Recoil Reduction and 10% Aim Speed. |
| Like the Wind | Grants a 5% chance per point to ignore incoming damage while moving, capped at 100%, with a HUD indicator. |
| Be Like Water | Moving builds Movement Speed; standing still builds generic Damage. Each stack grants 2% per point, up to five stacks of each. Stacks build every 0.5 seconds; switching state immediately loses one old-state stack, then continues its decay while the new stacks build. Separate HUD counters show both bonuses. |
| Precision | Critical bullets can ricochet toward another enemy within 30 meters. Reflected damage is 60% at rank 1 and 100% at rank 5, gaining 10 percentage points per additional rank. No valid target means no ricochet. |
| Innervate | During Decepti0n, grants 4% Gun Damage and regenerates 1.6% Maximum Health per second. Retains its original Movement Speed bonus. |
| At One with the Gun | Retains passive Sniper Reload Speed and Magazine Size, removing Hip-Shot Accuracy. Ten charges empower the next shot with 20% Amp Damage per point. Any gun can build and use the bonus. A normal shot grants one charge; a shot with at least one critical hit grants two total, even when a normal pellet hits first. Extra pellets cannot exceed this per-shot limit. Preparation has no time limit and resets on travel or returning to the menu. Its original icon shows 1-10 charges in the HUD; 10 means the next shot is empowered, and consuming the charge hides it. |
| Unf0reseen | Adds a fixed 50% damage bonus at every level, on top of game-level scaling. Decepti0n's native timed damage stacks additionally increase explosion damage by up to 200% (1.5x initially, up to 4.5x at full charge). The decoy pulls enemies inward and deals Shock damage within a 14-meter radius. Damaged enemies receive native Death Mark if learned. |
| Critical Ascensi0n | Critical hits with all gun types build stacks. Snipers retain full native bonuses; other guns receive half. Retains the 999-stack cap and initial decay delay; subsequent stack losses occur every 2.5 seconds. |

Damage Resistance follows the game's native diminishing-return formula. Be Like Water's Damage bonus affects weapons, melee, grenades and status effects; At One with the Gun uses a separate Amp bonus. Native class-mod grades are used without adding equipment points twice.

## Requirements

- Borderlands 2 on PC.
- The modern Willow2 PythonSDK and Mod Manager.

Other character rebalances and Endgame and QoL Rebalance are optional, independent modules.

## Installation

1. Place the official `Zer0Rebalance.sdkmod` file in the game's `sdk_mods` directory, or place the official source folder there as `sdk_mods/Zer0Rebalance`.
2. Enable **Zer0 Rebalance** in the Mod Manager.
3. Restart the game after installing, updating or disabling the mod. Loaded native skill definitions are not fully reverted by disabling hooks during a session.

Use one installation format at a time to avoid loading duplicate copies.

## Compatibility and validation

- Disable overlapping Zer0 skill changes in UCP or other mods.
- Other character rebalances do not need to be disabled; this module does not import or modify them.
- Co-op has not been validated.
- Focused offline checks cover the changed code. Recent trigger, ricochet, delayed-projectile and weapon-switch interactions still need in-game confirmation; remaining checks are documented in [DEVELOPMENT.md](DEVELOPMENT.md).

See [CHANGELOG.md](CHANGELOG.md) for release and balance history.

## Credits

- **Kgx37b9** - project author.
- **Borderlands PythonSDK / bl-sdk contributors** - SDK and mod infrastructure.
- **Gearbox Software / Borderlands 2** - native assets and skill system.

## License

Personal gameplay use of official, unmodified releases is permitted. Prior written permission from **Kgx37b9** is required to reuse original code or other original material. Redistribution, modpacks and modified releases require permission. Third-party material retains its own terms. See [LICENSE.md](LICENSE.md).
