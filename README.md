# MayaRebalance 1.0

A Borderlands 2 Python SDK mod by **Kgx37b9**, reworking Maya's survivability,
control and elemental synergies while preserving the game's native skill system.

See [CHANGELOG.md](CHANGELOG.md) for balance history and
[DEVELOPMENT.md](DEVELOPMENT.md) for technical evidence and validation limits.

## Main skill changes

Values below refer to 5/5 unless stated otherwise; class-mod ranks scale supported skills.

| Skill | Current behavior |
| --- | --- |
| Accelerate | +20% gun damage and +25% projectile speed. |
| Flicker | +50% status-effect chance and +30% elemental damage. |
| Suspension | +3.5 seconds of Phaselock duration. |
| Wreck | Passive +25% fire rate/+15% gun damage, doubled during Phaselock. |
| Quicken | +50% cooldown rate, including Scorn. Scorn's base cooldown is 12 seconds. |
| Kinetic Reflection | During its kill skill, 25% general damage reduction and 50% total bullet reduction; the reductions do not add together. |
| Sustenance | Applying an elemental status heals 15% maximum health, with a shared 0.5-second cooldown; reapplications can trigger it. |
| Elated | Passive 5% maximum-health regeneration per second, doubled during Phaselock. |
| Recompense | 25% chance to avoid damage, with a 3-second cooldown; replaces retaliation. |
| Res | Retains ally revival and adds an automatic Second Wind with a 120-second cooldown, reset on full character death. |
| Immolate | During a 12-second Phaselock window, qualifying gun hits add incendiary damage equal to 25% of their final health-plus-shield damage. |
| Blight Phoenix | Native kill-skill trigger/duration; +25% movement speed and 40% chance not to consume elemental gun ammo. Pure explosive/non-elemental weapons are excluded; the old aura is removed. |
| Scorn | Passive +50% elemental status duration, plus retuned beam damage. |
| Backdraft | +35% Skill Damage, additional fire damage on Scorn beams, and a shield-break nova with a 920-unit radius. The former melee fire effect is removed. |
| Elemental Mastery | One-point Cataclysm skill: +7.5% damage received from Maya per distinct fire, shock, corrosive or slag status, up to +30%. |
| Psychic Shriek | Replaces Thoughtlock: normal Phaselock, +2 seconds duration; the main target takes +15% damage and nearby enemies deal 20% less damage for 8 seconds. Includes immune targets and allied damage against the main target. |

Ruin, Scorn and Helios use linear extra-damage progression between stage 1 and
stage 90 (level 80 + OP10). Baseline damage follows the live global game scaler;
these percentages stay the same when that scaler changes.

| Skill | Stage 1 bonus | Stage 90 bonus |
| --- | --- | --- |
| Ruin | +15% | +190% |
| Scorn | +25% | +235% |
| Helios | +15% | +125% |

Immolate uses an independent post-hit dispatcher. Initial solo logs confirm its
fire delivery and expected final damage in sampled health hits; shields and
co-op still need broader validation. Restart completely after replacing it.

Scorn's curve affects its beams/damage area, not its separate native impact
explosions. Backdraft's separate fire damage retains native level/rank scaling
and receives an additional factor of `1 + 0.18 * effective rank`; no former
0.85 multiplier remains. Ruin retains its native elemental delivery sequence.

## Requirements

- Borderlands 2 and the modern Willow2 Python SDK/Mod Manager.
- A compatible `mods_base` runtime; local development used mods_base 1.12 and
  the embedded Python 3.14 SDK interface.
- Maya as the playable character for this mod's skill changes.

UCP, Skill Scaling Patch and VaultHunterSupport are not required installations.

## Installation

1. Close Borderlands 2 completely.
2. Remove older MayaRebalance copies and the former `VHRebalanceMod` package/folder.
3. Copy `MayaRebalance.sdkmod` into the game's `sdk_mods` directory. Alternatively,
   extract it so `sdk_mods/MayaRebalance/__init__.py` exists. Use one installation.
4. Start the game and enable MayaRebalance in the Mod Manager.

Restart after replacing the package. Fully disabling native changes also requires
restarting; do not replace or hot-reload the mod during gameplay.

## Known compatibility

- Other mods editing the same Maya skills, native behavior graphs or damage
  initializers can conflict. UCP's overlapping Maya options require integration testing.
- The optional VaultHunterSupport changes global rules independently; Maya's
  level-scaled damage follows the active global scaler.
- Co-op is **unvalidated** (`Unknown`), especially authority-sensitive healing,
  revival and damage effects. Solo observations do not establish co-op support.
- Current validation limits, including native Phaselock damage comparisons and
  the latest numerical changes, are recorded in DEVELOPMENT.md.

## Credits


- **Kgx37b9**: author of MayaRebalance and its balance design.
- **Shadowevil and the Community Patch Team**:
  [Unofficial Community Patch (UCP)](https://github.com/BLCM/BLCMods/tree/master/Borderlands%202%20mods/Community%20Patch%20Team),
  Reference for balance decisions and historical implementations explored during development. Earlier adaptations have been revised or replaced as documented in [DEVELOPMENT.md](DEVELOPMENT.md).
- **55tumbl**:
  [Skill Scaling Patch](https://github.com/BLCM/BLCMods/tree/master/Borderlands%202%20mods/55tumbl/Skill%20Scaling%20Patch),
  historical reference for earlier Scorn/Ruin damage-scaling corrections; and
  [Elemental Banshee Maya](https://github.com/BLCM/BLCMods/tree/master/Borderlands%202%20mods/55tumbl/Elemental%20Banshee%20Maya),
  historical native-behavior research and the former Immolate graph adaptation. The current independent dispatcher replaces that graph-based route; see DEVELOPMENT.md. Neither complete mod is bundled.
- **bl-sdk contributors**: [unrealsdk](https://github.com/bl-sdk/unrealsdk),
  [pyunrealsdk](https://github.com/bl-sdk/pyunrealsdk) and mods_base, the SDK/runtime.
- **BLCM/OpenBLCMM community**:
  [OpenBLCMM-Data](https://github.com/BLCM/OpenBLCMM-Data) and
  [BPD classroom](https://github.com/BLCM/BLCMods/wiki/BPD-classroom), native data
  and behavior-graph documentation used during development.
- **osetor74**: [Oselands](https://github.com/BLCM/BLCMods/blob/master/Borderlands%202%20mods/osetor74/Oselands/Oselands.blcm),
  reference for the earlier Thoughtlock investigation. The current rework uses
  normal Phaselock events and temporary received-damage modifiers.

Additional technical references consulted, not bundled dependencies:
[SecondWindStuff (Hydrattler)](https://github.com/BLCM/BLCMods/tree/master/Borderlands%202%20mods/Hydrattler/SecondWindStuff),
[Scaling Adjuster and ammo examples (apple1417)](https://github.com/apple1417/willow2-sdk-mods),
[Oselands (osetor74)](https://github.com/BLCM/BLCMods/tree/master/Borderlands%202%20mods/osetor74/Oselands),
[Loot Randomizer (mopioid)](https://github.com/mopioid/Borderlands-Loot-Randomizer),
and [Borderlands2SDK headers (McSimp and contributors)](https://github.com/McSimp/Borderlands2SDK).
Detailed investigation history and attribution are documented in
[CHANGELOG.md](CHANGELOG.md) and [DEVELOPMENT.md](DEVELOPMENT.md).

## License

**All rights reserved** for Kgx37b9's original contributions for now; see
[LICENSE.md](LICENSE.md). This is not a blanket license for third-party work.
Third-party conditions remain applicable where third-party material is used.
The recorded provenance and replacement history are described in DEVELOPMENT.md.
