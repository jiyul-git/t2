# Layered Avatar System v1

## Goal

Replace fixed, fully-painted portrait identities with one composable avatar model shared by:

- the human player profile
- every bot at the poker table
- future city/country cosmetic packs

Gameplay logic and gameplay RNG do not read avatar state.

## Canonical avatar config

```json
{
  "base": "human",
  "tone": "warm",
  "eyes": "round",
  "hair": "short",
  "hat": "none",
  "beard": "none",
  "outfit": "hanbok_teal",
  "accessory": "none"
}
```

The renderer normalizes unknown/missing values to safe defaults.

## Layers

Render order is fixed:

1. outfit
2. base/head
3. hair
4. eyes
5. mouth
6. beard
7. hat
8. accessory

All parts use the same 240x260 SVG coordinate system. This removes the old atlas crop/eye-center problem.

## User profile

The player config is stored in `t2profile_avatar_v2`.

The old numeric `t2profile_avatar` value is read only as a migration source. It is mapped to a layered preset until the new profile is saved.

The profile flow is:

`Profile -> Character Customization -> Part -> Option`

Each part opens its own selector instead of displaying every option on the main profile sheet.

## Bots

`AvatarSystem.botConfig(pid)` derives a deterministic cosmetic config from pid.

Properties:

- same pid => same appearance after seat moves
- no gameplay RNG consumption
- no production/persona mutation
- 9 initial pids produce 9 distinct configs
- the same renderer is used for user and bots

## Theme expansion

Future packs should extend the catalog instead of creating a second avatar system.

Examples:

- Seoul: hanbok, gat, binyeo, traditional accessories
- Tokyo: kimono/yukata and local accessories
- Las Vegas: suits, neon accessories, sunglasses
- Macau: formal casino styles and gold accents

A later catalog revision can add `pack`, unlock rules, rarity, compatibility constraints, and inventory ownership without changing the serialized avatar contract.

## Files

- `ui/web/avatar_system.js` — catalog, normalization, deterministic bot generation, SVG renderer
- `ui/web/avatar.css` — renderer/editor presentation
- `ui/web/lobby.js` — player avatar editor and migration
- `ui/web/app.js` — hero/bot table rendering

## v1 limitations

The v1 art is vector scaffolding intended to validate the system architecture and UI flow. It is not the final art pack.

Before final art production, freeze:

- common canvas/safe areas
- layer z-order
- hat/hair compatibility policy
- species-specific part rules
- country/city pack ownership and unlock rules
