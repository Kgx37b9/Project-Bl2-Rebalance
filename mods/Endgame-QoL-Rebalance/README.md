# EndgameQoLRebalance 1.0.5

Configurable endgame balance and quality-of-life settings for **Borderlands 2**. Version **1.0.5** by **Kgx37b9**.

The mod offers level rules for enemies, loot, missions and vendors; growth sliders; UVHM and raid-boss balance; a Grog Nozzle quest reward; gold minimap stars for rare loot; and resource-capacity adjustments. Settings take effect after a full game restart. The installable runtime uses one Python file.

## Features and options

| Menu category | Controls | Default |
| --- | --- | --- |
| Level Scaling | Enemy/loot minimum and maximum, mission minimum, on-level vendors, new-item level-80 cap | See [Level Scaling](#level-scaling) |
| Resources and Storage | Independent backpack, personal bank, sniper/shotgun ammo and 1000-Eridium-cap switches | All on |
| Rare Loot Minimap Stars | Gold markers for Legendary, Pearlescent, Seraph and Effervescent drops | On |
| Game Scaling | Global health/damage growth: 1%-20% per level | 5% |
| Money Scaling | Money/price growth: 1%-20% per level | 5% |
| UVHM Balance | Enemy health and shields, passive regeneration, loot, vehicle damage, ammo drops and slag | On; health/shields 2x |
| Raid Boss Health | Party-size health adjustment and Master Gee/Dexiduous multipliers | On |
| Grog Nozzle Mission Reward | Add the Grog Nozzle to the existing quest rewards | On |
| Level Difference Corrections | Separate switches for higher-level enemy resistance, higher-level enemy damage and elemental status chance | All on |

The three level-difference switches affect only penalties caused by level difference. They do not remove intrinsic immunities or elemental resistances. The Resources and Storage switches are independent of UVHM Balance. The Eridium switch changes the limit to 1000 in memory on compatible Windows BL2 builds; it does not modify the executable file. If the build cannot be verified, the native limit remains in place and the mod logs a warning. This new switch needs in-game validation.

The backpack begins at **22 slots** and its purchased SDUs add **3, 3, 4, 4, 4, 5, 5, 5 and 15**. The personal bank begins at **25 slots** and its SDUs add **5, 5, 10, 15 and 20 for each further upgrade**. Sniper ammo capacity is **72 + 24 per SDU**; shotgun capacity is **140 + 30 per SDU**. Backpack and bank changes preserve existing upgrades and apply to supported local solo sessions. Ammo capacity applies in every playthrough. The four-slot shared stash is unchanged.

The UVHM health and shield slider ranges from **1x to 4x** in steps of **0.25x**. Badass enemies retain the native health proportion: regular enemies at 2x correspond to badass enemies at 1.3x. Boss phases and scripted healing remain. Player vehicle weapon damage is 3x, ammo drops are 2x, and passive enemy UVHM regeneration is removed. Slag lasts seven seconds, slows NPC movement by 30% and weapon fire rate by 25%, and does not amplify damage. The slag slow does not affect players. Melee and special-attack speed are unchanged.

The Grog Nozzle is added to *The Beard Makes The Man* rewards without removing XP, money or other rewards. Completed quests do not receive a retroactive item.

**Restart the game completely after changing options.** Changing maps or disabling and re-enabling the mod does not apply a new selection in the same process.

### UVHM loot weights

The values below are relative weights, not direct drop percentages.

| Effective level | Common-item weight | Uncommon chest-item weight |
| --- | --- | --- |
| Below 50 | Unchanged | 0.15 |
| 50-60 | 0.10 | 0.15 |
| 61-70 | 0.02 | 0.0625 |
| 71 and above, including OP levels | 0.02 | 0.025 |

## Raid Boss Health

The toggle normalizes **Hyperius, Master Gee, Voracidous and Pyro Pete** in all playthroughs, independently of UVHM Balance. It also sets **Master Gee's UVHM own health multiplier to 1,000** (previously 3,500) and **Dexiduous' class-base multiplier to 2,500** (previously 100,000). Master Gee's native class coefficient outside UVHM is unchanged; Dexiduous keeps its existing player-count scaling. Original health-pool definitions, scripted phases/heals, shields, damage, experience and loot are preserved. This does not rewrite the current HP of an already spawned boss.

The native player-count attribute reads `GameInfo.EffectiveNumPlayers`. This policy adds a private attribute reading `GameInfo.NumPlayers` and evaluates the native health-weight table against both. It never changes either global counter or the original weight table:

```text
R = clamp(F(actual players, champion, playthrough)
          / max(0.000001, F(effective players, champion, playthrough)), 0, 1)

New boss health multiplier = selected boss health multiplier * R
```

`F` is the native player/champion/playthrough health weight, including any compatible changes to that table. If actual and effective counts already match, **R = 1**. Four players still receive their four-player health weight. The upper bound prevents an accidental health increase if the effective counter lags behind the real party. Inclusion in this policy does not prove that a boss forces four players in every version or configuration; Pyro Pete's earlier four-player estimate was provisional.

For the current **5% growth** projection:

```text
B(level) = 50.5 * (1 + 0.02 * level) * 1.05^level
HP(level) = B(level) * K
K = own boss multiplier * UVHM health factor * player health weight
```

`K` is the effective multiplier; it already includes the boss's own multiplier. Do not multiply by both again. Example, Hyperius in the adopted UVHM profile: `56 * 1.3 * 8 = 582.4` before normalization; with one real player, `R = 2 / 8 = 0.25`, so `K = 145.6`. At level 92 this former estimate is `12,765.129723 * 145.6 = approximately 1,858,603 HP`; the current user-reported solo observation is about 7.4M.

For another growth setting, replace `1.05` with `1 + growth_percent / 100`. During initial map setup, a transient zero real-player count uses the solo weight.

The following retains the former solo planning projection for comparison. It uses growth 1.05 and UVHM health slider 2.00 (badass 1.30). Level 1 is hypothetical, not a legal spawn level. Runtime testing found that most raid bosses have about 75% more health than this target. The updated reference column applies that approximate correction; only Pyro Pete and Voracidous have exact SDK-log readings recorded below. Hyperius is listed separately at the user-reported solo value of about 7.4M. Other corrected figures are estimates, not per-boss measurements.

| Raid boss | Own multiplier | Effective K, solo | Hypothetical level-1 HP | OP10 level | Former projection | Updated observed/reference HP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Terramorphous | 1,000 | 3,000 | 162,257 | 92 | 38,295,389 | ~67,016,931* |
| Vermivorous | 200 | 520 | 28,124 | 93 | 7,018,844 | ~12,282,977* |
| Hyperius | 56 | 145.6 | 7,875 | 92 | 1,858,603 | ~7,434,412 (user-reported solo value) |
| Master Gee | 1,000 | 3,000 | 162,257 | 92 | 38,295,389 | ~67,016,931* |
| Pyro Pete | 338 | 1,014 | 54,843 | 92 | 12,943,842 | 22,781,064 (measured) |
| Voracidous | 225 | 675 | 36,508 | 92 | 8,616,463 | 15,078,746 (measured) |
| Dexiduous | 2,500 | 6,500 | 351,556 | 93 | 87,735,546 | ~153,537,206* |
| Healianth | 300 | 900 | 48,677 | 93 -> 113* | 12,147,999 -> 36,740,265* | ~21,258,998 -> 64,295,464* |
| Brood | 150 | 450 | 24,338 | 93 -> 113* | 6,073,999 -> 18,370,132* | ~10,629,498 -> 32,147,731* |
| Boost | 100 | 300 | 16,226 | 93 | 4,049,333 | ~7,086,333* |
| Incinerator | 200 | 600 | 32,451 | 93 -> 113* | 8,098,666 -> 24,493,510* | ~14,172,666 -> 42,863,643* |
| Invincible Son of Crawmerax (raid) | 180 | 468 | 25,312 | 93 | 6,316,959 | ~11,054,678* |
| Haderax | 1,200 | 3,600 | 194,708 | 92 | 45,954,467 | ~80,420,317* |

*Non-Hyperius corrected figures are approximate +75% references based on the observed trend, not direct HP captures for each boss. Pyro Pete and Voracidous are exact log readings from level 92 solo encounters. Hyperius at about 7.4M is the user-reported solo value. The three dragons affected by Boost have a theoretical 20-level increase in the native level-up behavior; level 113 remains a projection of 93 + 20.*

The recorded solo log values for Pyro Pete and Voracidous are about 76% and 75% above the former projections. This points to a systematic mismatch in the estimate; the table marks the other +75% values as approximations until individually measured. Hyperius is treated separately because its roughly 7.4M solo health is reported as expected for one player. These observations do not by themselves identify which runtime multiplier causes the difference.

Health mechanics to account for before further balance changes: Hyperius has protection/enrage phases; Gee relies on acid and a separate shield; Pete has shield/helmet phases; Voracidous receives Ngwatu's shield and has an enrage transition. Healianth heals other dragons, Boost raises their levels, and Incinerator has protected/reflecting phases. Son of Crawmerax has scripted healing transitions, Haderax can recover large amounts of health, and Dexiduous relies on vulnerable hit regions. Passive UVHM regeneration removal does not remove these scripted mechanics.

Confirm in a fresh encounter after a complete restart: solo HP versus the same boss/level with the toggle off, then actual party-size scaling. Do not use a boss damaged before installation as a reference. The implementation has offline tests; it has not yet been validated against raid HP in the engine.

## Backpack Capacity

The backpack starts with **22 slots**. Purchased backpack SDUs add **3, 3, 4, 4 and 4 slots** for the first five upgrades. The sixth through eighth SDUs add **5 slots each**; the ninth/final native SDU adds **15 slots**, reaching **70 slots**.

| Purchased backpack SDUs | Capacity |
| --- | --- |
| 0 | 22 |
| 1 | 25 |
| 2 | 28 |
| 3 | 32 |
| 4 | 36 |
| 5 | 40 |
| 6 | 45 |
| 7 | 50 |
| 8 | 55 |
| 9 | 70 |

Existing purchased SDUs contribute automatically. Prices and the number of purchasable SDUs remain native. Larger existing capacity and occupied inventory are preserved. This option applies to the owning local character in solo play, independently of Personal Bank Capacity, and requires a full restart after changing its setting. It changes capacity limits only; equipment and SDU purchase records are not rebuilt. Solo capacity behavior was confirmed by the author; co-op remains untested.

Solo bank and backpack behavior was confirmed in game by the author on 2026-10-30.

## Personal Bank Capacity

In solo play, the personal bank starts at **25 slots**. The first four purchased bank SDUs add **5, 5, 10 and 15 slots** respectively. The fifth and every later bank SDU add **20 slots each**.

| Purchased bank SDUs | Capacity |
| --- | --- |
| 0 | 25 |
| 1 | 30 |
| 2 | 35 |
| 3 | 45 |
| 4 | 60 |
| 5 | 80 |
| 6 | 100 |
| 7 | 120 |

Previously purchased bank SDUs count automatically. The number of purchasable upgrades and their prices remain native. The adjustment only increases the current personal bank's slot limits; a larger existing bank or occupied capacity is preserved. The four-slot shared stash and global storage-class defaults are unchanged.

This is a capacity adjustment for the physical bank. It does not restore the removed inventory-to-bank action, move items, add keybinds, clone equipment or rewrite save files. The option is enabled by default and applies after a full restart. Multiplayer is currently excluded. Solo capacity behavior was confirmed by the author; co-op remains untested.

## Ammo Capacity

This option applies in every playthrough, independently of UVHM Balance.

| Ammo type | Native base | New base | Native gain per SDU | New gain per SDU |
| --- | --- | --- | --- | --- |
| Sniper | 48 | 72 (+50%) | 12 | 24 (+100%) |
| Shotgun | 80 | 140 (+75%) | 20 | 30 (+50%) |

Reserve capacity is the base plus the number of purchased upgrades multiplied by the gain per SDU. The two increases are independent; they do not multiply the previous upgrade's total. Existing upgrades contribute through the game's own upgrade-count attribute. This option does not change magazine sizes, upgrade counts, SDU prices or other ammunition types. Restart after changing the toggle or installing the build. Check the reserve capacity after loading the character; buying a new SDU is not required to benefit from previously purchased upgrades.

## Level Scaling

This category controls levels, separately from the percentage growth sliders:

| Option | Default |
| --- | --- |
| Minimum Enemy Level | Player Level |
| Maximum Enemy Level | Vanilla |
| Minimum Loot Level | Player Level |
| Maximum Loot Level | Vanilla |
| Minimum Mission Level | Player Level |
| On-Level Vendors | On |
| Cap New Items at Level 80 | On |

Each of the five selectors supports **Vanilla**, **Player Level**, or **Player +1** through **Player +10**. Vanilla leaves that bound unchanged by this module. If the selected minimum exceeds the selected maximum, the maximum takes priority.

Player Level means the effective level, including the active OP modifier: level 80 at OP10 uses 90. Enemy and mission policies do not impose a level-80 ceiling. The item cap is applied last and can override loot bounds or on-level vendors: with the cap enabled, new equipment cannot exceed 80, including OP equipment. Disable the cap to allow higher item levels.

On-Level Vendors requests equipment at effective player level, still subject to the cap. With this toggle off, ordinary loot policies can still affect newly generated shop equipment. Ammo/health stock without equipment definition data is not rebuilt.

The module handles newly generated hostile AI, equipment pools, mission item rewards and vendor stock. It does not periodically rescale living enemies, rewrite already loaded player equipment or deliberately relevel already locked missions. Mission-level changes use native level setters; reward contents and experience/currency formulas are preserved. Equipment parts are preserved when shop stock is reinitialized.

**Disable Enemy Item Scaling, or another mod controlling the same levels, before testing this category.** Do not stack competing level policies. Host-side behavior is implemented; co-op and special/scripted generation paths still require in-game validation. Client-side level changes are skipped. Custom generation paths that bypass the native hooks may need additional support.

Restart after changing choices, then spawn new enemies/items, open a vendor and accept an unlocked mission to test. Existing equipment and accepted mission levels are not a reliable test of the new-generation policy.

Slag audio follows the local status lifecycle. If slag ends, the UVHM feature ensures its local looping sound is stopped without changing other audio or muting an active slag effect. This cleanup is armed by local slag events and uses the existing maintenance budget; it does not scan audio components during gameplay. Co-op remains unvalidated.

## Rare Loot Minimap Stars

This switch adds a small, five-point gold vector star with a dark outline to the native minimap. It does not replace mission/enemy markers, use skill HUD slots or consume dynamic radar slots. It does not add a marker to the full-screen map.

Eligible ground equipment uses the native BL2 rarity identifiers for Legendary, Pearlescent, Seraph and Effervescent. E-tech, ordinary mission tokens, currency and unknown high rarity numbers are excluded. Attached pickup physics do not disqualify equipment; if the pickup rarity has not arrived yet, the equipment supplies its rarity. Custom rarity systems may require explicit support.

The implementation reconciles the game's pickup list at most four times per second, including moved or replicated drops. Position updates are limited to twenty per second and reuse existing star clips. Once per second, the renderer checks its own clips for visibility, transparency, position and missing vector drawings, recovering them after menu/HUD changes without forcing the native minimap or other icons to be visible. Unchanged clips receive no repeat writes. No shot or damage hooks are involved. Stars are hidden outside the minimap radius and disappear after collection/destruction is reflected in the pickup list. The drawing is a child of the native minimap. The existing local PlayerTick drives it through the controller's native GetHUDMovie function. A delayed minimap binding has a bounded lookup fallback, followed by cached-path lookup; UI objects are not retained in Python state. Cleanup follows the HUD/world lifecycle. Opening the mods/options interface pauses maintenance temporarily; closing it resumes markers in the same map. Actual travel/destruction keeps the old-world safety barrier. If the cached units-per-pixel field is zero, initialized native world/pixel radii supply the scale.

**Disable LootMarker or another loot-marker renderer when using this option to avoid duplicate markers.** This mod does not change other mods' settings. Co-op and custom rarity systems still need in-game validation.

## Requirements

- Borderlands 2 on PC. The Eridium limit adjustment currently supports only verified 32-bit Windows BL2 executables.
- The Willow2 PythonSDK with `mods_base`, its mod menu, and support for `.sdkmod` packages.
- The relevant DLC installed and available for DLC-specific features.

The character rebalance mods are optional. This mod does not require a separate TXT balance preset.

## Installation

1. Close Borderlands 2 completely.
2. Remove any older `EndgameQoLRebalance.sdkmod` installation. Copy `EndgameQoLRebalance.sdkmod` into the game's `sdk_mods` folder. Alternatively, install the source `EndgameQoLRebalance` folder containing `__init__.py`, `pyproject.toml`, `README.md` and `CHANGELOG.md`.
3. Use either the package or the source folder, never both. The source folder and mod menu use the same EndgameQoLRebalance name.
4. Launch the game and configure the mod menu. New installations enable the mod by default; an explicitly saved disabled state is respected.

Disable the mod and restart the game to stop applying its changes. Existing characters, enemies, rewards and cached effects are not rebuilt to simulate live rollback.

## Compatibility and testing

- Co-op has not been validated. Enemy/loot generation and host/client ownership still require multiplayer testing.
- Other mods that write the same scaling tables, slag definitions or mission rewards may conflict. This mod does not change their settings or loading order automatically.
- Do not load an older combined TXT profile alongside these features; it can overwrite the same data.
- Automatic special-currency pickup and one-purchase ammo refills are not provided by this mod. They may be supplied by other enabled mods.
- Enemy-level selection, experience growth and global health/damage growth are separate systems. The Eridium cap uses a verified memory-only adjustment; unsupported executables keep the native limit.

## Credits and references

**Author and maintainer:** Kgx37b9.

These projects and authors informed feature ideas, balance decisions and technical research. Earlier approaches were revised or replaced during development; this section preserves those references. Tools and SDK dependencies are listed separately from design inspiration.

| Reference | Author(s) | Contribution to the project's development |
| --- | --- | --- |
| [UVHM Rebalance](https://github.com/BLCM/BLCMods/tree/master/Borderlands%202%20mods/Nifsara/UVHM%20Rebalance) | Nifsara | Inspiration and historical research for UVHM balance features. |
| [Higher Level Scaling Remover](https://github.com/BLCM/BLCMods/blob/master/Borderlands%202%20mods/apple1417/HigherLevelScalingRemover.blcm) | apple1417 | Reference for level-difference modifiers. |
| Mods compilation | Filipe Ramos | Historical references for growth and quality-of-life feature design. |
| Money-scaling reference | Checometer | Historical reference for money-growth settings. |
| Grog Nozzle Mission Reward | Jim Raven | Inspiration and historical reference for the mission-reward feature. |
| [LootMarker](https://bl-sdk.github.io/willow2-mod-db/mods/lootmarker/) | juso | Feature precedent for loot markers. The custom star renderer was written for this project using native SDK/GFx interfaces. |
| Community Patch | shadowevil, LightChaosman and contributors | Community balance and quality-of-life references. |
| [Elemental Banshee Maya](https://github.com/BLCM/BLCMods/blob/master/Borderlands%202%20mods/55tumbl/Elemental%20Banshee%20Maya/ElementalBansheeMaya.blcm) | 55tumbl | Additional technical research. |

Tools and technical foundations:

- [Borderlands PythonSDK / bl-sdk](https://github.com/bl-sdk): SDK, native-object access and mod infrastructure.
- [BLCM / OpenBLCMM-Data](https://github.com/BLCM/OpenBLCMM-Data): tools and reference dumps of native game data.
- Borderlands 2 and its native game data: Gearbox Software / 2K.

See [CHANGELOG.md](CHANGELOG.md) for version history and balance changes. Detailed investigations and internal test records are maintained separately from this player-facing guide.


## License

You may download and use the official, unmodified release for your own gameplay. Prior written permission from Kgx37b9 is required before reusing any part of the project's original code or other original material. Redistribution and modified releases are not permitted. Third-party material remains subject to its own terms; see [LICENSE.md](LICENSE.md).
