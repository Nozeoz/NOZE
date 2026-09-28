# 10 — Master Asset List

> **TL;DR:** Every art, audio, and UI asset the game needs, mapped by **ID**, **spec**, and **milestone** (VS / EA / 1.0), with production **templates** so each asset type is made the same way. Totals per milestone are in [§15](#15-totals-by-milestone). This file is the source of truth; when art production starts (Step 11), it gets exported to a tracker spreadsheet (owner, due date, review status).

**Status legend:** ☐ to do · ◐ in progress · ☑ done · ✖ cut. Every asset below starts at ☐.

---

## 1. How to read this list

- **IDs** follow the prefixes in §2.1; the file name is the ID plus its extension.
- **Milestone** = the first build that needs the asset. Later milestones only add to it.
- **Templates** (§2.4) define frame size and animation set. Instead of repeating "idle 4 frames, walk 6 frames…" for 60 creatures, each row names its template.
- Content definitions (who, what, why) live in the design docs; this list only covers **what must be produced**.

---

## 2. Conventions

### 2.1 Asset ID prefixes

| Prefix | Type | Example |
|---|---|---|
| `spr_` | Animated sprite sheet | `spr_npc_bram` |
| `por_` | Portrait sheet | `por_linnea` |
| `ico_` | Icon (atlas frame) | `ico_crop_turnip` |
| `tls_` | Tileset | `tls_dawnmere_ground_spring` |
| `map_` / `chk_` | Tiled map / dungeon room chunk | `map_dawnmere_vale`, `chk_cellars_combat_03` |
| `bld_` | Building sprite | `bld_smithy_t1` |
| `prp_` | Prop / nature object | `prp_tree_oak_mature_spring` |
| `fur_` / `dec_` | Furniture / decor | `fur_bed_simple`, `dec_banner` |
| `ui_` | UI element or screen | `ui_panel_parchment` |
| `vfx_` | Visual effect | `vfx_hit_spark_stone` |
| `mus_` `jgl_` `amb_` `sfx_` `vox_` | Music, jingle, ambience, SFX, voice blips | `sfx_tool_hoe_01` |
| `fnt_` | Font | `fnt_body` |
| `mkt_` | Marketing | `mkt_key_art_wide` |

### 2.2 Folder structure

```
art_src/                  source files (.aseprite, .psd, .kra), stored with Git LFS
  characters/ portraits/ creatures/ tiles/ buildings/ props/ items/ ui/ vfx/ marketing/
audio_src/                DAW projects and stems (Git LFS)
game/public/assets/       exported runtime files
  atlases/                packed PNG + JSON
  tilesets/  maps/  portraits/  fonts/
  audio/music/  audio/sfx/  audio/amb/  audio/vox/
```

### 2.3 File formats

| Type | Source | Runtime |
|---|---|---|
| Sprites & icons | Aseprite with tagged animations (`idle_d`, `walk_s`, …) | PNG atlas + JSON |
| Tilesets | Aseprite | PNG + Tiled `.tsj` |
| Maps & room chunks | Tiled `.tmx` | Tiled `.tmj` (JSON) |
| Portraits | Aseprite, layered (base / eyes / brows / mouth / blush) | PNG sheet |
| Music | DAW project + stems | `.ogg` + `.m4a` |
| SFX | WAV 48 kHz / 24-bit | `.ogg` + `.m4a` audio sprites |
| Fonts | `.ttf` / `.otf` or bitmap | Bitmap font (`.png` + `.fnt`) |

### 2.4 Production templates

Directions: **D/U/S** = down, up, side (mirrored for left/right). Full animation tables are in [`08_ART_DIRECTION.md` §12](08_ART_DIRECTION.md#12-animation-standards).

| Template | Frame | Contents | ≈ Frames |
|---|---|---|---|
| **T-PLAYER** | 32×48 | Full player set (move, tools, 6 weapon families, dodge, cast, pact, carry, fishing, emotes, ride) | VS ~300 · EA ~475 · 1.0 ~490 (per body frame) |
| **T-SWORN** | 32×48 | Idle 4, walk 6 (D/U/S), signature loop 6, sit 3, talk 4, emote 4 | ~47 |
| **T-SWORN-COMP** | 32×48 (+64×64 FX) | T-SWORN + attack 2×4, skill 5, hurt 2, KO 4 (D/U/S) | ~96 |
| **T-SETTLER** | 32×48 | Idle, walk, carry, work-farm, work-chop, work-hammer, work-generic, sit, sleep, on shared skeletons | ~120 per skeleton |
| **T-ENEMY** | 32×48 | Idle, move, attack ×2, hurt, KO (D/U/S) | ~60 |
| **T-CRE-S** | 32×32 | Idle (side + front), move (side), attack, hurt, faint, work, sleep, happy | ~35 |
| **T-CRE-M** | 48×48 | As S, idle and move in D/U/S | ~61 |
| **T-CRE-L** | 64×64 | As M | ~61 |
| **T-MOUNT** | 64×64 | Adds mounted idle/walk/run (D/U/S) + rider anchor points | +~40 |
| **T-BOSS** | 96–192 | Custom per fight | 80–150 |
| **T-PORTRAIT** | 128×128 | 8 layered expressions: Neutral, Happy, Laugh, Sad, Angry, Surprised, Blush, Signature | 8 |
| **T-ICON** | 16×16 | 1 px dark outline, top-left light | 1 |
| **T-CROP** | 16×16 or 16×32 | 4–6 growth stages + harvestable + regrow | ~6 |
| **T-TREE** | 32×48 to 48×64 | Sapling, young, mature, stump, fall (4), shake (2), per season | ~12 per season |

---

## 3. Characters

### 3.1 Player: the Sovereign (paper-doll)

| Layer | Method | VS | EA | 1.0 |
|---|---|---|---|---|
| Body frame A (skin via palette ramp) | Per frame (T-PLAYER) | 1 | 1 | 1 |
| Body frame B | Edit pass over A (~30% of A's cost) | 1 | 1 | 1 |
| Eyes (4 shapes, colour via ramp) | Per direction + head-offset table | 4 | 4 | 4 |
| Hair styles (front + back) | Per direction + offsets | 6 | 12 | 16 |
| Tops | Per direction × 2 poses + offsets | 3 | 10 | 24 |
| Bottom shapes (trousers, shorts, skirt, robe) | Per frame, colour via ramp | 2 | 4 | 4 |
| Hats | Per direction + offsets | — | 6 | 12 |
| Accessories | Per direction + offsets | — | 4 | 12 |
| Tool layers (hoe, can, axe, pickaxe, sickle; tiers via palette) | Per frame of tool animations | 5 | 5 | 5 |
| Weapon layers (tiers via palette; unique shapes at T4–T5) | Per frame of attack animations | 2 families | 6 families | 6 + T4/T5 shapes |
| Held items (lantern, fishing rod, sigil) | Per frame | 2 | 3 | 3 |
| **Prologue Sovereign** (full regalia, combat subset) `spr_sovereign_prologue` | T-PLAYER combat subset | 1 | — | — |

### 3.2 Flicker

| ID | Contents | Milestone |
|---|---|---|
| `spr_flicker` | Idle bob 6 · fly 4 · talk 4 · eat 6 · 6 emotes × 4 | VS |
| `spr_flicker_growth` | One added flame/crown layer per Regalia (6 stages) | VS (stage 1) → 1.0 |
| `spr_flicker_true` | True form (Ch6) | 1.0 |

### 3.3 Sworn sprites

| ID | Sworn | Template | Signature loop | Milestone |
|---|---|---|---|---|
| `spr_npc_bram` | Bram | T-SWORN | Sawing / hammering | VS |
| `spr_npc_linnea` | Linnea | T-SWORN-COMP | Grinding herbs | VS |
| `spr_npc_rook` | Rook | T-SWORN-COMP | Coin flip | VS |
| `spr_npc_tamsin` | Tamsin | T-SWORN-COMP | Anvil strike | VS |
| `spr_npc_mira` | Mira (+ caravan cart) | T-SWORN | Counting coins | VS |
| `spr_npc_juniper` | Juniper | T-SWORN | Feeding creatures | EA |
| `spr_npc_marigold` | Marigold | T-SWORN | Stirring a pot | EA |
| `spr_npc_elowen` | Elowen | T-SWORN-COMP | Reading a floating book | EA |
| `spr_npc_fen` | Fen | T-SWORN | Playing the flute | EA |
| `spr_npc_aldous` | Aldous | T-SWORN | Lighting a lantern | EA |
| `spr_npc_nix` | Nix | T-SWORN-COMP | Tracing sigils | EA |
| `spr_npc_mari` | Mari | T-SWORN-COMP | Spyglass | EA |
| `spr_npc_orin` | Orin | T-SWORN | Fishing | EA |
| `spr_npc_seren` | Seren | T-SWORN-COMP | Lute strum | EA |
| `spr_npc_pim`, `spr_npc_pom` | Pim & Pom | T-SWORN (small body) ×2 | Wrenching; small explosion | EA |
| `spr_npc_durgan` | Durgan | T-SWORN | Heavy hammer | 1.0 |
| `spr_npc_kaida` | Kaida | T-SWORN-COMP | Shadowboxing | 1.0 |
| `spr_npc_hollis` | Hollis | T-SWORN-COMP | Pouring flasks | 1.0 |
| `spr_npc_hilde` | Hilde | T-SWORN | Rolling a barrel | 1.0 |
| `spr_npc_ingrid` | Ingrid | T-SWORN-COMP | Sword drill | 1.0 |
| `spr_npc_saga` | Saga | T-SWORN | Stargazing | 1.0 |
| `spr_npc_tor` | Tor | T-SWORN-COMP | Whittling | 1.0 |
| `spr_npc_isolde` | Isolde | T-SWORN | Sewing | 1.0 |
| `spr_npc_caelan` | Caelan | T-SWORN-COMP | Kneeling vigil | 1.0 |

Companion-capable (T-SWORN-COMP) = the 12 romance options: **VS 3 · EA 7 · 1.0 12**.

### 3.4 Settlers (modular)

**Sprite kit (T-SETTLER):**

| Part | VS | EA | 1.0 |
|---|---|---|---|
| Skeletons × body frames A/B | Medium A/B | + Small A/B | + Stout A/B |
| Race overlays (elf ears, beast ears + tails ×3, dragon horns ×2 + tail, fins) | — | 6 | 9 |
| Hair styles | 6 | 10 | 12 |
| Job outfits (tops; bottoms reuse the player's shapes) | 6 (farmer, forager, woodcutter, hauler, builder, cook) | 12 | 16 |
| Accessories (hats, bandanas, glasses) | 3 | 6 | 10 |
| Colour ramps (skin 8, hair 12, cloth 16) | ✔ | ✔ | ✔ |

**Portrait kit (128×128, composited at runtime):**

| Part | VS | EA | 1.0 |
|---|---|---|---|
| Face shapes | 4 | 6 | 6 |
| Eyes (3 moods each) | 6 | 10 | 10 |
| Brows | 4 | 6 | 6 |
| Mouths (3 moods each) | 6 | 8 | 8 |
| Noses | 3 | 4 | 4 |
| Hair (front + back) | 6 | 10 | 12 |
| Ears (race) | 1 | 5 | 8 |
| Collars (per job) | 6 | 12 | 16 |
| Accessories | 3 | 6 | 10 |
| **Total parts** | **39** | **67** | **80** |

The same portrait kit can later give the **player** a dialogue portrait (optional, EA).

### 3.5 Story NPCs & human enemies

| ID | Character | Template | Milestone |
|---|---|---|---|
| `spr_npc_caelan_prologue` | Caelan in prologue armour | T-SWORN-COMP | VS |
| `spr_npc_vesper` | Vesper (prologue, then Choirmaster) + boss attacks | T-SWORN + boss set | VS (prologue) / EA |
| `spr_npc_hob` | Hob Furrow | Settler kit + unique hair | VS |
| `spr_npc_magpie`, `_jackdaw`, `_finch` | Crowfeather trio | Settler kit + T-ENEMY | VS |
| `spr_cre_humphrey` | Mira's pack-beast | T-CRE-M | VS |
| `spr_npc_pip` | Pip (child, 32×32 frame) | T-SWORN (child) | EA |
| `spr_npc_thane` | Lord-Marshal Thane | T-SWORN | EA |
| `spr_enm_cutpurse` / `_brute` / `_slinger` | Crowfeather Gang | T-ENEMY | VS |
| `spr_enm_acolyte` / `_chanter` / `_silentblade` | Pale Choir | T-ENEMY | EA |
| `spr_enm_soldier` / `_crossbow` | Dominion | T-ENEMY | EA |
| `spr_enm_warden_engine` | Dominion construct | T-CRE-L | 1.0 |
| `spr_enm_hollow_sprout` | A Veil Seed gone wrong | T-CRE-S | EA |

### 3.6 Portraits

| ID | Character | Expressions | Extras | Milestone |
|---|---|---|---|---|
| `por_bram` `por_linnea` `por_rook` `por_tamsin` `por_mira` | VS Sworn + Mira | 8 each | — | VS |
| `por_flicker` | Flicker | 10 (8 + Hungry + Sheepish) | True Form (+1) at 1.0 | VS |
| `por_caelan_prologue`, `por_vesper_prologue` | Prologue | 3 each | — | VS |
| `por_hob`, `por_magpie`, `por_jackdaw`, `por_finch`, `por_humphrey` | Minor | 3 / 2 / 2 / 2 / 2 | — | VS |
| `por_juniper` `por_marigold` `por_elowen` `por_fen` `por_aldous` `por_nix` `por_mari` `por_orin` `por_seren` | EA Sworn | 8 each | — | EA |
| `por_pim`, `por_pom` | Tinker twins | 8 each | — | EA |
| `por_vesper` | Choirmaster (masked + unmasked) | 6 | — | EA |
| `por_thane`, `por_pip` | Story NPCs | 4 each | — | EA |
| `por_durgan` `por_kaida` `por_hollis` `por_hilde` `por_ingrid` `por_saga` `por_tor` `por_isolde` `por_caelan` | 1.0 Sworn | 8 each | — | 1.0 |
| `por_*_wedding` | 12 romance options | 3 each | Wedding outfits | 1.0 |

**Portrait counts:** VS **67** · EA **169** · 1.0 **278** expressions.

---

## 4. Creatures

Species details: [`05_BESTIARY.md`](05_BESTIARY.md). Each form needs: **sprite sheet** + **compendium icon** (32×32; the unknown silhouette is generated) + 3 SFX (audio list). **The Hollowed** are a shader (0 new frames). The **Named crown mark** is one shared overlay placed via per-species anchor points.

| Group | IDs (`spr_cre_*`) | Template | Milestone |
|---|---|---|---|
| VS species, S (10) | mossbun, puddlepup, emberkit, cluckatrice, glimmoth, mandragling, jellop, pebblet, wickling, gnawrat | T-CRE-S | VS |
| VS species, M (2) | cloudfleece, duskwolf | T-CRE-M | VS |
| VS True Ascension (2) | grovehare, blazetail | T-CRE-M | VS |
| EA species, S (9) | capling, breezling, hootsage, silkspinner, shellsnip, driftotter, squallgull, lumenjelly, tollhermit | T-CRE-S | EA |
| EA species, M (6) | creamhorn, chompkin, bramblehog, moondeer, timberbeetle, bubbleseal | T-CRE-M | EA |
| EA True Ascension (6) | tidehound, cragguard, aurormoth (M) · nightfang, vaultmaw (L) · thornbeast (L, T-MOUNT added at 1.0) | T-CRE-M / T-CRE-L | EA |
| 1.0 species, S (8) | cinderling, ashbat, cindercheep, glacimew, chillpip, starlit, nyxcat, knightling | T-CRE-S | 1.0 |
| 1.0 species, M (2) | emberhorn, forgeling | T-CRE-M | 1.0 |
| 1.0 species, L (1) | mammoss | T-CRE-L | 1.0 |
| 1.0 True Ascension (9) | archowl, tidefortress, magmalisk, auroralynx, constella (M) · stellar_stag, phoenix (L) · volcanic_ram, glacier_titan (L + T-MOUNT) | T-CRE-M / T-CRE-L | 1.0 |

**Creature forms:** VS **15** (incl. Ruinback) · EA **38** · 1.0 **60** (see §5 for Guardians).

---

## 5. Bosses

| ID | Boss | Frame | ≈ Frames | Extra parts | Milestone |
|---|---|---|---|---|---|
| `spr_boss_ruinback` | Ruinback | 192×128 | 100 | Breakable shell crystals, tower debris | VS |
| `spr_boss_rook` | Rook duel | Rook's sheet | +30 | Smoke-bomb FX | VS |
| `spr_boss_mycel` | Mother Mycel | 128×128 | 120 | Clones, root cages | EA |
| `spr_boss_tidetoll` | Tidetoll | 192×160 | 120 | Bells, water-level states | EA |
| `spr_boss_nix` | Nix duel | Nix's sheet | +30 | Sigil traps | EA |
| `spr_boss_vulkarn` | Vulkarn | 192×192 | 150 | Lava rise, armour plates | 1.0 |
| `spr_boss_astraea` | Astraea | 160×160 | 140 | Starfall zones | 1.0 |
| `spr_boss_ingrid` | Ingrid | Ingrid's sheet | +30 | Lance charge | 1.0 |
| `spr_boss_vesper` | Vesper | Vesper's sheet | +40 | Hymn bullet patterns | 1.0 |
| `spr_boss_warden` | The Ashen Warden | 48×64 | 90 | Echoes of the prologue Royal Arts | 1.0 |
| `spr_boss_maw` | The Maw Below | Multi-part, screen-sized | 300+ | Tendrils, core, phases | 1.0 |

---

## 6. Environments

### 6.1 Overworld tilesets

| ID | Contents | ≈ Tiles | Seasons | Milestone |
|---|---|---|---|---|
| `tls_farm` | Tilled and watered soil, paddy (1.0), trellis bases | 60 | — | VS |
| `tls_dawnmere_ground` | Grass, dirt, flowers, cliffs, transitions | 180 | Spring (VS) → ×4 (EA) | VS |
| `tls_dawnmere_water` | River, pond, shoreline, waterfall (4-frame animation) | 90 | ×4 (EA) | VS |
| `tls_ruins_halcyon` | Halcyon ruin set pieces used in every region | 120 | Snow overlay (EA) | VS |
| `tls_veil` | Veil-choked soil, bramble, Veil Wall, crystal nodes, light-border dither | 70 | — | VS |
| `tls_town` | Paths (dirt → stone → brick), plazas, wall materials | 150 | Snow overlay | VS (dirt) → 1.0 |
| `tls_prologue` | Burning Halcyon capital | 120 | — | VS |
| `tls_whisperwood_*` | Forest floor, giant roots, mushroom rings | 200 | ×4 | EA |
| `tls_saltglass_*` | Sand, glass sand, cliffs, tide pools, docks | 200 | ×4 | EA |
| `tls_cinderpeak_*` | Rock, lava (animated), obsidian, hot springs | 200 | Snow on peaks | 1.0 |
| `tls_frostveil_*` | Snow, ice, frozen lake, aurora sky | 180 | — | 1.0 |
| `tls_hollowcrown_*` | Ruined capital in the deep Veil | 200 | — | 1.0 |

### 6.2 Dungeon tilesets & room chunks

| ID | Dungeon | ≈ Tiles | Room chunks | Milestone |
|---|---|---|---|---|
| `tls_dgn_cellars` | Sunken Cellars | 150 | 40 | VS |
| `tls_dgn_rootdeep` | Rootdeep Labyrinth | 170 | 45 | EA |
| `tls_dgn_bells` | Drowned Bells | 170 | 45 | EA |
| `tls_dgn_forgeheart` | The Forgeheart | 180 | 50 | 1.0 |
| `tls_dgn_starfall` | Starfall Spire | 180 | 50 | 1.0 |
| `tls_dgn_halcyon` | Halcyon Below | 200 | 60 | 1.0 |
| — | Veil Rifts (remix all chunk sets + `tls_veil`) | — | — | 1.0 |

**Chunk types per dungeon:** entrance, standard combat (majority), mining, treasure vault, spring, captive, nest, memory shrine, Veil rift, merchant, Waystone, Descent, Guardian arena.
**Room chunks:** VS **40** · EA **130** · 1.0 **290**.

### 6.3 Interiors

| ID | Used for | Milestone |
|---|---|---|
| `tls_int_wood` | Longhouse, huts, Lodge, Cookhouse, Den, Scout's Post, Windmill Ruin | VS |
| `tls_int_stone` | Keep, Chapel, Archive, Clinic | EA |
| `tls_int_shop` | Market, Tavern, Workshop, Harbor office | EA |
| `tls_int_castle` | Castle, Palace, Hall of Knights | 1.0 |

**Interior maps:** VS **8** · EA **20** · 1.0 **30**.

### 6.4 Maps

| ID | Map | Milestone |
|---|---|---|
| `map_prologue_halcyon` | Prologue: burning capital | VS |
| `map_dawnmere_vale` | Home region (192×144 tiles) | VS |
| `map_whisperwood` · `map_saltglass_coast` | Regions 2–3 | EA |
| `map_cinderpeak` · `map_frostveil` · `map_hollow_crown` | Regions 4–6 | 1.0 |
| `map_thorn_court` · `map_brinemouth` · `map_emberhold` · `map_rimewatch` · `map_frozen_manor` · `map_starfall_crater` | Special locations | EA / 1.0 |
| Festival decoration layers for the town map | Per festival | VS (1) → EA (8) |

### 6.5 Props & nature

| Group | Contents | Milestone |
|---|---|---|
| Wild trees (T-TREE) | Oak, Pine, Maple (VS, Spring) → + Birch, Palm, Giant Mushroom (EA, ×4 seasons) → + Charred Pine, Frost Fir, Veil Tree (1.0) | VS → 1.0 |
| Fruit trees & perennials | 6 fruit trees + Tea Bush (3 stages × 4 seasons + fruit overlay) + Halcyon Rose bush | EA / 1.0 |
| Bushes | Berry and decorative bushes (8), seasonal | VS (2) → 1.0 |
| Rocks | Small, large, boulder × region variants + break animation | VS → 1.0 |
| Ore nodes | Copper, Veilglass crystal, gem, geode (VS) → Iron, Silver (EA) → Emberite, Starmetal, Heartstone (1.0); 2 sizes + break animation | VS → 1.0 |
| Forage on the ground | One sprite per forage item (~35) | VS (8) → 1.0 |
| Weeds & cuttable grass | 4 types × seasons | VS |
| Veil features | Bramble, crystal node, Veil Wall segment, tendrils | VS |
| Ruins set pieces | Pillars, broken walls, sun-sigil tiles, gates, the **headless Sovereign statue** (a story hint) | VS (20) → 1.0 (60) |
| Light props | Campfire, brazier, torch, Lumen Lamp, lantern post, light-shrine (all animated) | VS |
| **Story landmarks** (ruined + restored states) | Ashen Throne (dormant, kindled), Windmill Ruin, Old Bridge, Ruined Chapel, Old Granary, Reflection Pond | VS |
| Misc | Signposts, crates, barrels, carts (Mira's caravan), fences (wood, stone), field gates | VS |

### 6.6 Crops (T-CROP)

- Per crop: 4–6 growth stages, harvestable stage, regrow stage if any; one shared **withered** sprite; trellis crops use 16×32.
- Seed packets: one shared packet template + per-crop art (counted as icons in §8).
- **Crop sprites:** VS ~36 · EA ~160 · 1.0 ~190.

---

## 7. Buildings

Each exterior needs: the tier sprite + a **night emissive layer** (lit windows) + a **winter snow overlay** (EA). Surge damage uses a **shared damage-decal set**, not new sprites.

| ID pattern | Building | Tiers to draw | Milestone |
|---|---|---|---|
| `bld_throne_t0…t4` | The Throne | 5 | VS (t0–t1) · EA (t2) · 1.0 (t3–t4) |
| `bld_beacon_t1…t4` | Beacon | 4 | VS (t1–t2) · EA (t3) · 1.0 (t4) |
| `bld_storehouse_t1…t3` · `bld_granary_t1…t3` | Storage | 3 + 3 | VS (t1) · EA (t2–t3) |
| `bld_tent` · `bld_hut` · `bld_well` | Early basics | 1 each | VS |
| `bld_lumber_camp_t1…t2` · `bld_den_t1…t4` | Production | 2 + 4 | VS (t1) · EA (rest) |
| `bld_lodge` · `bld_clinic_t1` · `bld_scout_post_t1` · `bld_smithy_t1` · `bld_tavern_t1` | VS Sworn / service | 1 each | VS |
| `bld_clinic_t2` · `bld_scout_post_t2` · `bld_tavern_t2` | Upgrades | 1 each | EA |
| `bld_waybeacon` · `bld_cottage` · `bld_quarry` · `bld_mill` · `bld_glasshouse` · `bld_guard_post` · `bld_watchtower` | EA general | 1 each | EA |
| `bld_market` · `bld_archive` · `bld_nursery` · `bld_chapel` · `bld_spire` · `bld_harbor` · `bld_bandstand` · `bld_workshop` | EA Sworn | 1 each | EA |
| `bld_wall_*` · `bld_gate_*` | Palisade (EA) → Stone → Runed (1.0) | Wang set + gate per material | EA / 1.0 |
| `bld_smithy_t2` · `bld_townhouse` · `bld_manor` · `bld_bathhouse` | 1.0 general | 1 each | 1.0 |
| `bld_arena` · `bld_lab` · `bld_brewery` · `bld_barracks` · `bld_observatory` · `bld_hunters_lodge` · `bld_tailor` · `bld_hall_of_knights` | 1.0 Sworn | 1 each | 1.0 |
| `bld_scaffold_{s,m,l,xl}_{1..3}` | Construction stages by footprint class | 3 per class | VS (s, m) → EA (l, xl) |
| `vfx_bld_damage_*` · `bld_snow_*` | Shared damage decals · snow caps | Sets | EA |

**Exterior sprites:** VS **16** · EA **~46** · 1.0 **65**.

---

## 8. Items & icons (T-ICON, 16×16)

| Category | Technique | VS | EA | 1.0 |
|---|---|---|---|---|
| Seeds & saplings | Shared packet template + crop art | 6 | 31 | 39 |
| Crops, fruit, tea leaves | Unique | 6 | 31 | 39 |
| Forage | Unique | 6 | 25 | 35 |
| Ores, stone, gems, geodes | Unique | 8 | 18 | 27 |
| Materials (raw & processed) | Bars share a template, tinted | 8 | 18 | 25 |
| Creature materials | Unique | 24 | 54 | 76 |
| Artisan goods | **Tinted templates** (jam, wine, juice, pickles, dye) | — | 22 | 30 |
| Dishes & drinks | Unique | 8 | 22 | 26 |
| Tools (all tiers) | Tier palettes | 12 | 27 | 34 |
| Weapons | Tier palettes; unique T4/T5 shapes | 4 | 20 | 35 |
| Armour & trinkets | Unique | 9 | 30 | 54 |
| Sigils, creature items, catalysts | Unique | 5 | 15 | 24 |
| Consumables | Unique | 5 | 10 | 10 |
| Fish (+ trash) | Unique | — | 16 | 23 |
| Key items (Regalia, fragments, embers, charter, rings, keys…) | Unique | 5 | 16 | 26 |
| Clothing (cosmetic) | From paper-doll parts | 3 | 20 | 60 |
| **Total icons** | | **~110** | **~375** | **~560** |

Furniture and decor icons are counted in §9.

---

## 9. Furniture & decor

| Group | Examples | VS | EA | 1.0 |
|---|---|---|---|---|
| Beds, tables, chairs, storage | Simple → royal styles | 8 | 22 | 30 |
| Lighting | Candles, lanterns, Lumen Lamps, chandeliers | 3 | 8 | 12 |
| Rugs & wall decor | Tapestries, paintings, trophies, mounted Regalia replicas | 2 | 12 | 23 |
| Plants & kitchen | Potted plants, stoves, shelves | 2 | 8 | 15 |
| Outdoor decor | Benches, flower beds, fountains, hedges, clocktower | 3 | 10 | 16 |
| Festival decor | Lanterns, banners, stalls, pumpkins, snow sculptures | 1 | 8 | 16 |
| **Banners (heraldry)** | Composited at runtime from field shapes (6), patterns (12), emblems (30), colours | ✔ | ✔ | ✔ |
| **Knight statues** | Generated: a Sworn's idle-down frame remapped to a stone ramp + pedestal | — | — | up to 24 |
| **Total objects** | | **~20** | **~70** | **~120** |

---

## 10. UI

### 10.1 Component kit

| ID | Component | Milestone |
|---|---|---|
| `ui_panel_parchment` / `_navy` / `_card` / `_tooltip` / `_dialogue` | 9-slice panels | VS |
| `ui_button_{s,m,l}` | Normal, hover, pressed, disabled, focused | VS |
| `ui_tab`, `ui_scrollbar`, `ui_slider`, `ui_toggle`, `ui_checkbox`, `ui_dropdown`, `ui_textfield` | Controls | VS |
| `ui_slot`, `ui_slot_selected`, `ui_hotbar` | Inventory slots | VS |
| `ui_bar_hp` / `_energy` / `_exposure` / `ui_satiety_bowl` | HUD meters | VS |
| `ui_clock`, `ui_calendar`, `ui_gold` | HUD info | VS |
| `ui_cursor_*` | Default, interact, attack, build, talk, invalid | VS |
| `ui_focus_frame` | Gamepad focus highlight | VS |
| `ui_toast`, `ui_speech_bubble`, `ui_quest_marker` | Feedback | VS |
| `ui_wax_seal`, `ui_filigree_*` | Royal accents (Decrees, Court) | EA |

### 10.2 UI icon sets

| Set | Count | Milestone |
|---|---|---|
| Elements (with shapes) | 7 | VS |
| Buffs, statuses, survival states | 22 | VS (12) → EA |
| Work skills | 12 | VS (6) → EA |
| Settler traits | 30 | VS (12) → 1.0 |
| Attributes | 6 | VS |
| Moods (settler 5, familiar 3) | 8 | VS |
| Quality stars | 4 | VS |
| Hearts (full, half, empty, broken, locked) + Bond | 6 | VS |
| Weather 6 · seasons 4 · moon phases 4 | 14 | VS |
| Map icons | 30 | VS (15) → 1.0 |
| Royal Arts | 8 | VS (2) → 1.0 |
| Input glyphs (keyboard/mouse, Xbox, PlayStation) | ~90 | VS (KB/M + Xbox) → EA |
| Emote bubbles (! ? ♥ … 💢 💧 ♪ zzz) | 8 | VS |
| Heraldry parts (fields, patterns, emblems) | 48 | VS (basic 20) → 1.0 |

### 10.3 Screens

| # | Screen | Milestone |
|---|---|---|
| 1 | Title | VS |
| 2 | Save slots | VS |
| 3 | New game (difficulty) | VS |
| 4 | Settings (basic → full accessibility) | VS → EA |
| 5 | Pause | VS |
| 6 | Character creator (the pond) | VS |
| 7 | HUD | VS |
| 8 | Inventory | VS |
| 9 | Crafting | VS |
| 10 | Cooking | VS |
| 11 | Shop | VS |
| 12 | Dialogue | VS |
| 13 | Build mode | VS |
| 14 | Kingdom overview | VS |
| 15 | Residents | VS |
| 16 | Familiars (+ work assignment) | VS |
| 17 | Relationships | VS |
| 18 | Compendium | VS |
| 19 | Journal | VS |
| 20 | World map | VS |
| 21 | **The Founding**: kingdom name + banner editor | VS |
| 22 | Naming / Ascension ceremony | VS |
| 23 | Day summary (sleep report: sales, settlers, Food Stock) | VS |
| 24 | Loading screens (art + tips) | VS |
| 25 | Court Day | EA |
| 26 | Decrees | EA |
| 27 | Expeditions | EA |
| 28 | Fishing minigame | EA |
| 29 | Full heraldry editor (Tailor) | 1.0 |
| 30 | Credits | 1.0 |

**Screens:** VS **24** · EA **28** · 1.0 **30**.

---

## 11. VFX

| Group | Effects | VS | EA | 1.0 |
|---|---|---|---|---|
| Combat | Slash arcs per weapon family (×3 combo), thrust, heavy impact ring, hit sparks by material (4), crit flash, parry flash, Perfect-Dodge afterimage + time-slow tint, enemy telegraphs (circle, line, cone), dissolve-into-mist, loot pop | 18 | 30 | 36 |
| Projectiles | Arrow, water spit, fire bolt, wind blade, star bolt, shadow orb, ice pebble + impacts | 3 | 10 | 14 |
| Element statuses | Burn, Soak, Root, Stagger, Dazzle, Fear (shiver lines), Veil-rot | 7 | 7 | 7 |
| Royal Arts | One signature effect each | 2 | 5 | 8 |
| Pact & familiars | Sigil throw arc, seal circle, struggle, success burst, fail shatter, Naming (crown glyph), Ascension (light cocoon → reveal), purification (golden burst + colour-restore wave), Named crown mark | 9 | 9 | 9 |
| Farming & tools | Dirt clods, water splash, wood chips, stone chips, ore sparkle, harvest pop, morning growth sparkle, Dew Totem spray | 6 | 8 | 8 |
| World | Footstep dust / splash / snow, chimney smoke, fire (campfire, brazier, forge), Beacon pulse + radius ring, lantern glow, fireflies, petals, leaves, rain + splash, snow, fog layers, **Veil fog layers**, Veil Wall, tendrils, crystal shimmer, Hollowed mist trail, water shimmer, waterfall foam | 16 | 26 | 32 |
| Special | Lava bubbles, aurora, meteor shower, fireworks, river lanterns, confetti (rank up), construction dust, completion sparkle | 3 | 8 | 12 |
| UI | Heart pop, coin burst, item-get glow, rank-up banner, quest-complete stamp | 5 | 5 | 5 |
| Emote bubbles | ! ? ♥ … 💢 💧 ♪ zzz (animated) | 8 | 8 | 8 |
| **Total** | | **~77** | **~116** | **~139** |

---

## 12. Audio

Full lists in [`09_AUDIO_DIRECTION.md`](09_AUDIO_DIRECTION.md).

| Type | VS | EA | 1.0 |
|---|---|---|---|
| Music tracks | 14 | 35 | 48 |
| Jingles | 10 | 11 | 11 |
| SFX | ~150 | ~380 | ~550 |
| Ambience loops | 6 | 18 | 30 |
| Voice-blip sets | ~10 | ~22 | 32 |

---

## 13. Fonts

| ID | Use | Requirement |
|---|---|---|
| `fnt_body` | Dialogue, menus | Readable pixel font; Latin Extended (for future localisation); commercial-use licence (e.g. SIL OFL) |
| `fnt_heading` | Titles, names | Royal pixel-serif |
| `fnt_numbers` | Damage, gold, clock | Bold, monospaced digits |
| `fnt_dyslexic` | Accessibility option | Dyslexia-friendly font with an open licence |

Every font's licence gets verified and recorded in `CREDITS.md` before shipping.

---

## 14. Marketing & store

| ID | Asset | Milestone |
|---|---|---|
| `mkt_logo` | Logo (vector + pixel versions): the broken crown with a sprout | Step 15 |
| `mkt_key_art_wide` / `_tall` | Illustrated key art (see [08 §14](08_ART_DIRECTION.md#14-logo--key-art-concept)) | Step 15 |
| `mkt_capsule_*` | All Steam capsule and library sizes (per the current Steamworks spec) | Step 15 |
| `mkt_screenshots` | 10 curated in-engine screenshots | Step 15 |
| `mkt_trailer_announce` | 60–90 s announce trailer | Step 15 |
| `mkt_gifs_weekly` | Build-in-public GIFs and clips (from Step 4 onward) | Ongoing |
| `mkt_social_*` | Avatars and banners for X, Instagram, TikTok, YouTube | Step 15 |
| `mkt_devlog_template` | Devlog header template | Step 15 |
| `mkt_presskit` | Fact sheet, logos, screenshots, key art | Step 19 |
| `mkt_trailer_ea` | Early Access launch trailer | Step 20 |

---

## 15. Totals by milestone

| Category | Unit | VS | EA | 1.0 |
|---|---|---|---|---|
| Player body animation | Frames per body frame | ~300 | ~475 | ~490 |
| Player customization | Hair / tops / hats / accessories | 6 / 3 / 0 / 0 | 12 / 10 / 6 / 4 | 16 / 24 / 12 / 12 |
| Sworn sprite sheets | Sheets | 5 | 15 | 24 |
| Companion combat sets | Sets | 3 | 7 | 12 |
| Story NPC & enemy sheets | Sheets | 10 | 18 | 19 |
| Settler portrait kit | Parts | 39 | 67 | 80 |
| Portraits | Expressions | 67 | 169 | 278 |
| Creature forms (incl. Guardians) | Sprite sets | 15 | 38 | 60 |
| Bosses (all) | Sheets | 2 | 5 | 11 |
| Overworld tilesets | Sets | 7 | 9 (+ seasons) | 12 |
| Dungeon tilesets / room chunks | Sets / chunks | 1 / 40 | 3 / 130 | 6 / 290 |
| Interior tilesets / maps | Sets / maps | 1 / 8 | 3 / 20 | 4 / 30 |
| Building exteriors | Sprites | 16 | ~46 | 65 |
| Item icons | Icons | ~110 | ~375 | ~560 |
| Furniture & decor | Objects | ~20 | ~70 | ~120 |
| UI screens | Screens | 24 | 28 | 30 |
| VFX | Effects | ~77 | ~116 | ~139 |
| Music (+ jingles) | Tracks | 14 (+10) | 35 (+11) | 48 (+11) |
| SFX / ambience | Sounds / loops | ~150 / 6 | ~380 / 18 | ~550 / 30 |

---

## 16. Production notes

### 16.1 Cost savers (built into the specs above)
1. **Paper-doll with head-offset tables** for the player and settlers: a new hairstyle is ~6 drawings, not ~300.
2. **Palette ramps** for skin, hair, cloth, tool and weapon tiers, and seasonal tints.
3. **The Hollowed are a shader**: 38 corrupted variants for zero new frames.
4. **Layered portraits**: expressions swap eyes, brows, and mouth.
5. **Tinted icon templates** for artisan goods (jam, wine, juice, pickles, dye).
6. **Shared scaffolds, snow overlays, and damage decals** for all buildings.
7. **Generated Knight statues** from Sworn sprites.
8. **Mirrored side animations** (left = flipped right).
9. **Room chunks** reused across floors; Veil Rifts remix all existing chunks.
10. **The Named crown mark** is one overlay with per-species anchor points.

### 16.2 Outsourcing packages (if hiring artists)
| Package | Contents | Must include |
|---|---|---|
| A: Tiles & props | One region at a time | Aseprite template with the palette and grid, Tiled test map, reference board |
| B: Character sprites | Sworn sheets | T-SWORN / T-SWORN-COMP template file, cast bible excerpt |
| C: Portraits | Sworn portraits | T-PORTRAIT layered template, expression guide |
| D: Creatures | By size class | T-CRE templates, bestiary excerpt, shape-language table |
| E: UI & icons | Kit + icon sets | 9-slice guides, icon grid, colour-blind rules |
| F: VFX | By group | Colour language, frame budgets |

### 16.3 Per-asset review checklist
- [ ] Uses only the master palette
- [ ] Correct frame size and pivot (bottom-centre for characters)
- [ ] Aseprite tags follow the naming convention (`idle_d`, `walk_s`, `attack1_u`, …)
- [ ] Reads clearly at ×1 zoom
- [ ] No stray pixels or anti-aliasing against transparency
- [ ] Timing matches the animation spec
- [ ] Exported with the project export script (never by hand)
- [ ] Status updated in the tracker
