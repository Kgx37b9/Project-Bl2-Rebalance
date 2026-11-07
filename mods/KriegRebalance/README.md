# KriegRebalance 1.0.12

A Borderlands 2 Python SDK mod by **Kgx37b9**, reworking Krieg's Hellborn,
Mania and Bloodlust skills while preserving the game's native skill system.

See [CHANGELOG.md](CHANGELOG.md) for release history and [DEVELOPMENT.md](DEVELOPMENT.md) for technical details and validation limits.

## Main skill changes

Values below refer to 5/5 unless stated otherwise; class-mod ranks scale
supported skills.

| Skill | Current behavior |
| --- | --- |
| Blood Overdrive | Any kill activates/refreshes its native kill-skill duration. During it, each normal Bloodlust gain has a 10% chance per rank for one extra stack (50% at 5/5, 100% at 10/5; capped at 100% chance and one extra stack). At 60+ stacks with the kill skill active: 5% movement speed and 4% fire rate per rank (25%/20% at 5/5). Blood Overdrive is now in tier 5, center; Nervous Blood moves to its former tier 2, right position. |
| Salt the Wound | Loses one stack every 1.5 seconds during decay. Native generation and hold/reset conditions are preserved. |
| Salt the Wound / Elemental Elation | Native logical HUD slots: Bloodlust 1, Elemental Elation 2, Salt the Wound 3. Configure the layout before native tree registration; custom indicators reserve those slots. |
| Silence the Voices | Adds Grenade Damage info to self-attack damage text; removes three camera anims and four screen-particle templates; self-damage limited to one application per 3s. |
| Blood Bath | +0.3% gun damage per rank per Bloodlust stack while active (5/5 at 100 stacks: +150%). Native kill trigger, duration and grenade drops remain unchanged. |
| Blood-Filled Guns | +0.25% magazine size and +0.4% gun damage per effective rank per Bloodlust stack. At 5/5 and 100 stacks: +125% magazine size and +200% gun damage. Class-mod points scale both bonuses. |
| Blood Twitch | Preserves native weapon swap and +0.15% melee damage per rank per Bloodlust stack. Replaces recoil reduction with reserve ammo regeneration: 0.005% of each weapon ammo capacity per second per rank per stack (5/5 at 100 stacks: 2.5%/s). Includes all six weapon ammo types, excludes grenades, and does not regenerate the magazine. Class mods scale both additions. |
| Bloody Revival | Gun damage +10% per rank in FFYL; no assault-rifle requirement. Each Second Wind grants +2% gun damage and +3% damage reduction per rank until death (max 5 stacks). The skill's menu icon shows active Second Wind stacks (1-5) on the native HUD, sharing free space with other skill indicators. Lower stats show FFYL Gun Damage, Gun Damage, and Damage Reduction without redundant Second Wind suffixes. The values use orange until 5/5 direct investment, then green. |
| Flame Flare | Keeps burn duration and reignite chance; adds 15% burn damage resistance per rank. |
| Fuel the Fire | Keeps its native status-effect chance and self-ignite chance; adds 4% direct Incendiary Damage per rank (20% at 5/5), displayed on the skill's lower stat lines. The value is orange until 5/5 directly invested points, then green. This is not Burn/Status Effect Damage. |
| Blood Euphoria | One-point gamechanger at center of Bloodlust tier 4. Regenerates 0.1% of maximum health per second per Bloodlust stack (50 stacks = 5%/s, 100 = 10%/s). |
| Special melee | The special melee damage component tied to Buzz Axe Rampage uses `1 + 0.02 * GameStage`; at expected GameStage 90 (level 80/OP10), this component is x2.8. |
| Pull the Pin | One-point gamechanger allowing grenades in FFYL through the native attribute; normal key, grenade mod and cost. Removes the old death grenade and double XP. |
| Burn, Baby, Burn | +20% Burn Damage per rank, plus another +10% per rank while on fire (rank 5: +100%, or +150% total while on fire). |
| Pain is Power | Up to five stacks from life damage: +2% crit, +2% melee, -2.5% accuracy per stack (rank 5: +10%/+10%/-12.5%). After five seconds without health damage, loses one stack every two seconds. Native HUD icon above XP. Its positive stats are orange until 5/5 directly invested points, then green. |
| Fire Fiend | Original accuracy restored: 10% per point while on fire (50% at rank 5). |
| Hellfire Halitosis | Sets Krieg himself on fire through a native effect; while on fire grants 15% movement speed. |
| Elemental Empathy | Heals 10% per rank of corrosive/incendiary/shock status damage (rank 5: 50%). |
| Numbed Nerves | 7.5% damage reduction per rank, doubled while on fire (rank 5: 37.5%/75%). |
| Raving Retribution | Incendiary damage against enemies uses surface factors of 1 for shield/armor, including burn. |
| Fuel the Rampage | Reduces direct self-damage by 9% per rank (45% at 5/5; 99% at 11/5, without the former 95% cap); grants 10% movement speed per rank for 12 seconds after direct self-damage (+50% at 5/5). Its skill-menu icon appears on the native HUD while the movement bonus is active, using the shared free-slot allocator. |
| Light the Fuse | One grenade every 10s, cumulative with equipment regeneration; old FFYL dynamite removed. |

Blood Euphoria is the only added tree entry; Blood Overdrive and Nervous Blood exchange positions. Changes are limited to the skills listed above and their supporting effects. Class-mod equipment definitions and global game scaling are not rewritten. Restart completely after replacing the package.

## Requirements

- Borderlands 2 and the modern Willow2 Python SDK/Mod Manager.
- A compatible `mods_base` runtime; local development used mods_base 1.12 and
  the embedded Python 3.14 SDK interface.
- Krieg as the playable character for this mod's skill changes.

No other rebalance mod is required.

## Installation

1. Close Borderlands 2 completely.
2. Remove older KriegRebalance copies.
3. Copy `KriegRebalance.sdkmod` into the game's `sdk_mods` directory.
   Alternatively, extract it so `sdk_mods/KriegRebalance/__init__.py` exists.
   Use one installation only.
4. Start the game and enable KriegRebalance in the Mod Manager.

Restart after replacing the package. Fully disabling native changes also
requires restarting; do not replace or hot-reload the mod during gameplay.

## Known compatibility

- Other mods editing the same Krieg skills, native behavior graphs or damage
  initializers can conflict.
- The optional EndgameQoLRebalance changes global rules independently;
  Krieg's level-scaled damage follows the active global scaler.
- Co-op is **unvalidated** (`Unknown`); solo observations do not establish
  co-op support.

## Validation and known issues

- Targeted offline checks cover current coefficients, class-mod ranks, native configuration and HUD allocation; they do not replace engine testing.
- Solo gameplay has confirmed working skill effects and HUD indicators during development. The latest balance values still need final release-session confirmation.
- Pain is Power's indicator was absent once and returned after a full restart. The failure state was not captured, so its cause remains unresolved. Gameplay stacks and HUD rendering must be distinguished when reporting a recurrence.
- Co-op remains untested. No measured frame-time benchmark or guarantee of compatibility with other skill mods is claimed.

## Credits

- **Kgx37b9**: author of KriegRebalance and its balance design.
- **Mike**: visual-effects credit for Silence the Voices reduction category.
- **bl-sdk contributors**: [unrealsdk](https://github.com/bl-sdk/unrealsdk),
  [pyunrealsdk](https://github.com/bl-sdk/pyunrealsdk) and mods_base, the
  SDK/runtime.
- **BLCM/OpenBLCMM community**: [OpenBLCMM-Data](https://github.com/BLCM/OpenBLCMM-Data)
  and [BPD classroom](https://github.com/BLCM/BLCMods/wiki/BPD-classroom),
  native data and behavior-graph documentation used during development.

References consulted for selected Silence the Voices, Bloody Revival,
Flame Flare and special melee adjustments are documented in
CHANGELOG.md and DEVELOPMENT.md. No complete reference mod is bundled.

## License

You may download and use the official, unmodified release for your own gameplay. Prior written permission from Kgx37b9 is required before reusing any part of the project's original code or other original material. Redistribution and modified releases are not permitted. Third-party material remains subject to its own terms; see [LICENSE.md](LICENSE.md).
