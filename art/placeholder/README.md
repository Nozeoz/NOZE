# Placeholder art kit

In-house vector placeholders in the illustrated direction of [docs/08](../../docs/08_ART_DIRECTION.md): coloured line art (never pure black), two-tone cel shading, light from the top left, soft contact shadows. They let the prototypes look like Kingsbloom before we hire an artist ([docs/08 §17](../../docs/08_ART_DIRECTION.md#17-prototype-placeholder-kit)).

**This art never ships.** The hired artist replaces every asset, starting with the Art Style Test (Step 13). The two mood references guided the feel only; nothing was traced or copied from them.

**See it:** open [`gallery.html`](gallery.html), the Asset Atlas: a camp scene at in-game scale, the palette, every asset by category, a UI mock-up, and a live Veil and Beacon demo.

## Contents

| Category | Assets | IDs (from [docs/10](../../docs/10_ASSET_LIST.md)) |
|---|---|---|
| Brand | 1 | `logo_kingsbloom` |
| Characters | 6 | `chr_sovereign`, `chr_flicker`, `chr_bram`, `chr_linnea`, `chr_rook`, `chr_tamsin` |
| Creatures | 6 | `cre_mossbun`, `cre_puddlepup`, `cre_emberkit`, `cre_glimmoth`, `cre_jellop`, `amb_wispling` |
| Terrain | 6 | `tile_grass`, `tile_path`, `tile_tilled`, `tile_watered`, `tile_water`, `tile_veil` |
| Props | 13 | trees (sapling, young, mature, pine), giant mushrooms, rock, stump, fern, berry bush, lily and lotus, Veilglass node, Heartflame Brazier, Lumen Lamp |
| Crops | 7 | turnip stages 1–5, Dawnbell, Mandrake Root |
| Buildings | 5 | `bld_throne_t0`, `bld_tent`, `bld_hut`, `bld_longhouse`, `bld_beacon_t2` |
| Item icons | 10 | turnip, copper ore, Veilglass, Twine Sigil, Healing Herb, Vegetable Stew, hoe, gold, the Signet, Kingsbloom |
| Element icons | 7 | Terra, Aqua, Ignis, Zephyr, Lumen, Umbra, Veil (each a colour and a shape) |
| **Total** | **61** | |

## Files

| File | What it is |
|---|---|
| [`kit.mjs`](kit.mjs) | The art itself: every asset drawn as SVG in code, plus the registry (ID, label, category, milestone, note) |
| [`build.mjs`](build.mjs) | Writes `svg/<id>.svg` for each asset and the `gallery.html` page |
| [`gallery.css`](gallery.css), [`gallery-client.js`](gallery-client.js) | The Asset Atlas page's styles, and its Veil fog and Beacon demo |
| [`svg/`](svg) | One SVG per asset; the [narrative prototype](../../prototypes/narrative-ch1) uses the portraits and the logo |

Rebuild after editing `kit.mjs`:

```bash
node art/placeholder/build.mjs
```
