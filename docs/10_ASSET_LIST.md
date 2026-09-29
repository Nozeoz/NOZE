# 10 — Master Asset List

> **TL;DR (v0.2):** Every art, audio, and UI asset the game needs, mapped by **ID**, **spec**, and **milestone** (VS / EA / 1.0), with production **templates** so each asset type is made the same way. v0.2 specs follow the **illustrated 2D** direction ([`08_ART_DIRECTION.md`](08_ART_DIRECTION.md)): art authored at **2×**, characters and larger creatures as **Spine rigs**, a **64 px** tile grid at 1080p. Totals per milestone are in [§15](#15-totals-by-milestone). When art production starts (Step 13, the Art Style Test), this list is exported to a tracker spreadsheet (owner, due date, review status).

> ⚠️ **v0.5:** the art direction is now a 3D diorama ([D-040](12_DECISIONS_AND_OPEN_QUESTIONS.md#part-a-decision-log)). The IDs and milestones below still hold; the specs (2× sprites, Spine rigs, 64 px tiles) will be redone for 3D models after the Kingdom View playtest.

**Status legend:** ☐ to do · ◐ in progress · ☑ done · ✖ cut. Every asset below starts at ☐.

---

## 1. How to read this list

- **IDs** follow the prefixes in §2.1; the file name is the ID plus its extension.
- **Milestone** = the first build that needs the asset. Later milestones only add to it.
- **Templates** (§2.4) define method, size, and animation set, so each row just names its template.
- **Sizes** are on-screen at 1080p. **Author everything at 2×** (e.g. a 64 px icon is painted at 128 px).
- Content definitions (who, what, why) live in the design docs; this list only covers **what must be produced**.

---

## 2. Conventions

### 2.1 Asset ID prefixes

| Prefix | Type | Example |
|---|---|---|
| `rig_` | Spine skeleton (character, creature, boss) | `rig_npc_bram` |
| `spr_` | Frame-by-frame sprite sheet | `spr_cre_mossbun` |
| `por_` | Portrait (layered) | `por_linnea` |
| `ico_` | Icon (atlas frame) | `ico_crop_turnip` |
| `tls_` | Terrain tileset | `tls_dawnmere_ground_spring` |
| `map_` / `chk_` | Tiled map / dungeon room chunk | `map_dawnmere_vale`, `chk_cellars_combat_03` |
| `bld_` | Building | `bld_smithy_t1` |
| `prp_` | Prop / nature object | `prp_tree_oak_mature_spring` |
| `dcl_` | Ground decal | `dcl_clover_patch_02` |
| `fur_` / `dec_` | Furniture / decor | `fur_bed_simple`, `dec_banner` |
| `ui_` | UI element or screen | `ui_panel_parchment` |
| `vfx_` | Visual effect | `vfx_hit_spark_stone` |
| `mus_` `jgl_` `amb_` `sfx_` `vox_` | Music, jingle, ambience, SFX, voice blips | `sfx_tool_hoe_01` |
| `fnt_` | Font | `fnt_body` |
| `mkt_` | Marketing | `mkt_key_art_wide` |

### 2.2 Folder structure

```
art_src/                  layered source files (.psd / .kra / .clip) and Spine projects (.spine), Git LFS
  characters/ portraits/ creatures/ terrain/ props/ buildings/ items/ ui/ vfx/ marketing/
audio_src/                DAW projects and stems (Git LFS)
game/public/assets/       exported runtime files
  rigs/                   Spine .skel/.json + atlas
  atlases/                packed PNG + JSON (props, icons, UI, VFX)
  terrain/  maps/  portraits/  fonts/
  audio/music/  audio/sfx/  audio/amb/  audio/vox/
```

### 2.3 File formats

| Type | Source | Runtime |
|---|---|---|
| Characters, creatures, bosses | Layered parts (PSD/Krita) → **Spine** project | Spine `.skel` (binary) + atlas |
| Small creatures, FX | Layered file with frame folders | PNG sheet + JSON |
| Props, decals, icons, UI | Layered PSD/Krita at 2× | Packed PNG atlases + JSON (1× default, 2× high-res pack) |
| Terrain | Painted tiles at 2× | PNG + Tiled `.tsj` |
| Maps & room chunks | Tiled `.tmx` | Tiled `.tmj` (JSON) |
| Portraits | Layered PSD (base / eyes / brows / mouth / blush / sweat / tears) | PNG layers composited at runtime |
| Music | DAW project + stems | `.ogg` + `.m4a` |
| SFX | WAV 48 kHz / 24-bit | `.ogg` + `.m4a` audio sprites |
| Fonts | `.ttf` / `.otf` | Web font or bitmap-font export |

**Layer naming for Spine parts** (so any animator can rig any character): `head`, `hair_front`, `hair_back`, `eye_l`, `eye_r`, `mouth`, `torso`, `arm_l_upper`, `arm_l_lower`, `hand_l`, `leg_l_upper`, `leg_l_lower`, `foot_l` (and `_r`), `cape`, `tail`, `weapon`, `tool`.

### 2.4 Production templates

Views: **D/U/S** = down (front), up (back), side (mirrored for left/right). Animation lists and target durations: [`08_ART_DIRECTION.md` §13](08_ART_DIRECTION.md#13-animation-standards).

| Template | Method | Size at 1080p | Contents |
|---|---|---|---|
| **T-PLAYER** | Spine rig ×3 views + **skins** | ~64 × 128 | Full player set: move, tools, 6 weapon families, dodge, cast, pact, carry, fishing, emotes, ride (VS ~30 · EA ~46 · 1.0 ~47 animations) |
| **T-SWORN** | Spine rig ×3 views | ~64 × 128 | Idle, walk, signature loop, sit, talk gesture, emote |
| **T-SWORN-COMP** | T-SWORN + combat set | ~64 × 128 | + attack ×2, skill, hurt, KO |
| **T-SETTLER** | Shared rigs (Medium / Small / Stout) + skins | ~64 × 96–128 | Idle, walk, carry, work-farm, work-chop, work-hammer, work-generic, sit, sleep |
| **T-ENEMY** | Spine rig ×3 views | ~64 × 128 | Idle, move, attack ×2, hurt, KO |
| **T-CRE-S** | Frame-by-frame (or small rig) | ~48–80 | Idle (side + front), move, attack, hurt, faint, work, sleep, happy |
| **T-CRE-M** | Spine rig ×3 views | ~96–128 | As S, with idle and move in D/U/S |
| **T-CRE-L** | Spine rig ×3 views | ~160–200 | As M |
| **T-MOUNT** | T-CRE-L + mounted set | ~160–200 | Mounted idle/walk/run + rider attachment bone |
| **T-BOSS** | Custom Spine rig | 300–700 | Custom per fight, multi-part |
| **T-PORTRAIT** | Layered illustration | Shown ~512², authored 1024² | 8 expressions: Neutral, Happy, Laugh, Sad, Angry, Surprised, Blush, Signature |
| **T-ICON** | Illustration | 64², authored 128² | Coloured line art, top-left light |
| **T-CROP** | Illustration | 64 × 64 or 64 × 128 | 4–6 growth stages + harvestable + regrow |
| **T-TREE** | Illustration (+ optional sway bones) | 128–320 tall | Sapling, young, mature, stump, fall, shake, per season |
| **T-PROP** | Illustration | Varies | + collision shape + sort pivot (placed as a Tiled object) |
| **T-TERRAIN** | Painted tiles | 64² | Full tile ×3–4 variants + soft-edge transition set per terrain pair |

---

## 3. Characters

### 3.1 Player: the Sovereign (Spine skins)

| Part | Method | VS | EA | 1.0 |
|---|---|---|---|---|
| Body rig (3 views), skin tone via tint | T-PLAYER | 1 | 1 | 1 |
| Body shape B | Alternate torso/hip attachments on the same rig | 1 | 1 | 1 |
| Eye shapes (colour via tint) | Attachments | 4 | 4 | 4 |
| Hair styles (front + back) | Skins | 6 | 12 | 16 |
| Outfits (top + bottom) | Skins | 3 | 10 | 24 |
| Hats | Skins | — | 6 | 12 |
| Accessories | Skins | — | 4 | 12 |
| Tools (hoe, can, axe, pickaxe, sickle; tiers via tint + small shape changes) | Attachments on `tool` slot | 5 | 5 | 5 |
| Weapons (unique shapes at T4–T5) | Attachments on `weapon` slot | 2 families | 6 families | 6 + T4/T5 shapes |
| Held items (lantern, fishing rod, sigil) | Attachments | 2 | 3 | 3 |
| **Prologue Sovereign** (full regalia, combat subset) `rig_sovereign_prologue` | T-PLAYER skin + combat subset | 1 | — | — |

### 3.2 Flicker

| ID | Contents | Milestone |
|---|---|---|
| `spr_flicker` | Idle bob · fly · talk · eat · 6 emotes (frame-by-frame, ~32 px) | VS |
| `spr_flicker_growth` | One added flame/crown layer per Regalia (6 stages) | VS (stage 1) → 1.0 |
| `spr_flicker_true` | True form (Ch6) | 1.0 |

### 3.3 Sworn rigs

| ID | Sworn | Template | Signature loop | Milestone |
|---|---|---|---|---|
| `rig_npc_bram` | Bram | T-SWORN | Sawing / hammering | VS |
| `rig_npc_linnea` | Linnea | T-SWORN-COMP | Grinding herbs | VS |
| `rig_npc_rook` | Rook | T-SWORN-COMP | Coin flip | VS |
| `rig_npc_tamsin` | Tamsin | T-SWORN-COMP | Anvil strike | VS |
| `rig_npc_mira` | Mira (+ caravan cart prop) | T-SWORN | Counting coins | VS |
| `rig_npc_juniper` | Juniper | T-SWORN | Feeding creatures | EA |
| `rig_npc_marigold` | Marigold | T-SWORN | Stirring a pot | EA |
| `rig_npc_elowen` | Elowen | T-SWORN-COMP | Reading a floating book | EA |
| `rig_npc_fen` | Fen | T-SWORN | Playing the flute | EA |
| `rig_npc_aldous` | Aldous | T-SWORN | Lighting a lantern | EA |
| `rig_npc_nix` | Nix | T-SWORN-COMP | Tracing sigils | EA |
| `rig_npc_kael` | Kael | T-SWORN | Tempering a blade | EA |
| `rig_npc_sol` | Sol | T-SWORN-COMP | Spyglass | EA |
| `rig_npc_orin` | Orin | T-SWORN | Fishing | EA |
| `rig_npc_seren` | Seren | T-SWORN-COMP | Lute strum | EA |
| `rig_npc_pim`, `rig_npc_pom` | Pim & Pom | T-SWORN (Small rig) ×2 | Wrenching; small explosion | EA |
| `rig_npc_akane` | Akane | T-SWORN-COMP | Shadowboxing | 1.0 |
| `rig_npc_hollis` | Hollis | T-SWORN-COMP | Pouring flasks | 1.0 |
| `rig_npc_hilde` | Hilde | T-SWORN | Rolling a barrel | 1.0 |
| `rig_npc_ingrid` | Ingrid | T-SWORN-COMP | Sword drill | 1.0 |
| `rig_npc_saga` | Saga | T-SWORN | Stargazing | 1.0 |
| `rig_npc_tor` | Tor | T-SWORN-COMP | Whittling | 1.0 |
| `rig_npc_isolde` | Isolde | T-SWORN | Sewing | 1.0 |
| `rig_npc_lucan` | Lucan | T-SWORN-COMP | Kneeling vigil | 1.0 |

Companion-capable (T-SWORN-COMP) = the 12 romance options: **VS 3 · EA 7 · 1.0 12**.

### 3.4 Settlers (modular)

**Rig kit (T-SETTLER):**

| Part | VS | EA | 1.0 |
|---|---|---|---|
| Rigs × body shapes A/B | Medium A/B | + Small A/B | + Stout A/B |
| Race attachments (elf ears, beast ears + tails ×3, dragon horns ×2 + tail, fins) | — | 6 | 9 |
| Hair styles | 6 | 10 | 12 |
| Job outfits | 6 (farmer, forager, woodcutter, hauler, builder, cook) | 12 | 16 |
| Accessories (hats, bandanas, glasses) | 3 | 6 | 10 |
| Colour sets via tint/gradient map (skin 8, hair 12, cloth 16) | ✔ | ✔ | ✔ |

**Portrait kit (layered, composited at runtime):**

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
| `rig_npc_lucan_prologue` | Lucan in prologue armour (skin on Lucan's rig) | T-SWORN-COMP | VS |
| `rig_npc_vesper` | Vesper (prologue, then Choirmaster) + boss attacks | T-SWORN + boss set | VS (prologue) / EA |
| `rig_npc_hob` | Hob Furrow | Settler kit + unique hair | VS |
| `rig_npc_magpie`, `_jackdaw`, `_finch` | Crowfeather trio | Settler kit + T-ENEMY set | VS |
| `rig_cre_humphrey` | Mira's pack-beast | T-CRE-M | VS |
| `rig_npc_pip` | Pip (child) | T-SWORN (Small rig) | EA |
| `rig_npc_thane` | Lord-Marshal Thane | T-SWORN | EA |
| `rig_enm_cutpurse` / `_brute` / `_slinger` | Crowfeather Gang | T-ENEMY | VS |
| `rig_enm_acolyte` / `_chanter` / `_silentblade` | Pale Choir | T-ENEMY | EA |
| `rig_enm_soldier` / `_crossbow` | Dominion | T-ENEMY | EA |
| `rig_enm_warden_engine` | Dominion construct | T-CRE-L | 1.0 |
| `spr_enm_hollow_sprout` | A Veil Seed gone wrong | T-CRE-S | EA |

### 3.6 Portraits

| ID | Character | Expressions | Extras | Milestone |
|---|---|---|---|---|
| `por_bram` `por_linnea` `por_rook` `por_tamsin` `por_mira` | VS Sworn + Mira | 8 each | — | VS |
| `por_flicker` | Flicker | 10 (8 + Hungry + Sheepish) | True Form (+1) at 1.0 | VS |
| `por_lucan_prologue`, `por_vesper_prologue` | Prologue | 3 each | — | VS |
| `por_hob`, `por_magpie`, `por_jackdaw`, `por_finch`, `por_humphrey` | Minor | 3 / 2 / 2 / 2 / 2 | — | VS |
| `por_juniper` `por_marigold` `por_elowen` `por_fen` `por_aldous` `por_nix` `por_kael` `por_sol` `por_orin` `por_seren` | EA Sworn | 8 each | — | EA |
| `por_pim`, `por_pom` | Tinker twins | 8 each | — | EA |
| `por_vesper` | Choirmaster (masked + unmasked) | 6 | — | EA |
| `por_thane`, `por_pip` | Story NPCs | 4 each | — | EA |
| `por_akane` `por_hollis` `por_hilde` `por_ingrid` `por_saga` `por_tor` `por_isolde` `por_lucan` | 1.0 Sworn | 8 each | — | 1.0 |
| `por_*_wedding` | 12 romance options | 3 each | Wedding outfits | 1.0 |

**Portrait counts:** VS **67** · EA **177** · 1.0 **278** expressions (layered, so most expressions are face-layer swaps, not new paintings).

---

## 4. Creatures

Species details: [`05_BESTIARY.md`](05_BESTIARY.md). Each form needs: **rig or sprite sheet** + **compendium icon** (T-ICON; the unknown silhouette is generated) + 3 SFX. **The Hollowed** are a shader (no new art). The **Named crown mark** is one shared overlay placed via a per-species anchor bone or point.

| Group | IDs (`rig_cre_*` / `spr_cre_*`) | Template | Milestone |
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

### 4.1 Ambient life

| ID | Asset | Method | Milestone |
|---|---|---|---|
| `spr_amb_wispling` | **Wisplings** (idle, hop, hide, sleep, carry-gift; 3 variants) | Frame-by-frame | VS |
| `spr_amb_dragonfly`, `spr_amb_butterfly`, `spr_amb_fish_shadow` | Ambient critters | Frame-by-frame | VS |
| `spr_amb_songbird`, `rig_amb_deer` | Ambient critters | Frame-by-frame / rig | EA |

---

## 5. Bosses

| ID | Boss | Size at 1080p | Extra parts | Milestone |
|---|---|---|---|---|
| `rig_boss_ruinback` | Ruinback | ~640 × 420 | Breakable shell crystals, tower debris | VS |
| `rig_boss_rook` | Rook duel | Rook's rig | + smoke-bomb FX, duel animations | VS |
| `rig_boss_mycel` | Mother Mycel | ~420 × 420 | Clones, root cages | EA |
| `rig_boss_tidetoll` | Tidetoll | ~640 × 520 | Bells, water-level states | EA |
| `rig_boss_nix` | Nix duel | Nix's rig | + sigil traps | EA |
| `rig_boss_vulkarn` | Vulkarn | ~640 × 640 | Lava rise, armour plates | 1.0 |
| `rig_boss_astraea` | Astraea | ~520 × 520 | Starfall zones | 1.0 |
| `rig_boss_ingrid` | Ingrid | Ingrid's rig | + lance charge | 1.0 |
| `rig_boss_vesper` | Vesper | Vesper's rig | + hymn bullet patterns | 1.0 |
| `rig_boss_warden` | The Ashen Warden | ~160 × 210 | Echoes of the prologue Royal Arts | 1.0 |
| `rig_boss_maw` | The Maw Below | Multi-part, screen-sized | Tendrils, core, phases | 1.0 |

---

## 6. Environments

### 6.1 Terrain tilesets (T-TERRAIN, 64 px)

| ID | Contents | ≈ Tiles | Seasons | Milestone |
|---|---|---|---|---|
| `tls_farm` | Tilled and watered soil (soft edges), paddy (1.0) | 40 | — | VS |
| `tls_dawnmere_ground` | Meadow grass, dirt, path, cliff faces, transitions | 90 | Spring (VS) → ×4 (EA) | VS |
| `tls_dawnmere_water` | River and pond banks + animated water shader | 40 | ×4 (EA) | VS |
| `tls_veil` | Veil-choked soil, Veil Wall, light-border glow | 30 | — | VS |
| `tls_town` | Paths (dirt → cobble → brick), plazas | 60 | Snow overlay | VS (dirt) → 1.0 |
| `tls_prologue` | Burning Halcyon capital | 60 | — | VS |
| `tls_whisperwood_*` | Forest floor, root-covered ground | 90 | ×4 | EA |
| `tls_saltglass_*` | Sand, glass sand, rock shelves, tide pools | 90 | ×4 | EA |
| `tls_cinderpeak_*` | Rock, lava (shader), obsidian, hot springs | 90 | Snow on peaks | 1.0 |
| `tls_frostveil_*` | Snow, ice, frozen lake | 80 | — | 1.0 |
| `tls_hollowcrown_*` | Ruined capital ground in the deep Veil | 90 | — | 1.0 |

Most of the "reference look" comes from **props and decals placed on top** (§6.5), not from terrain tiles.

### 6.2 Dungeon tilesets & room chunks

| ID | Dungeon | ≈ Tiles | Room chunks | Milestone |
|---|---|---|---|---|
| `tls_dgn_cellars` | Sunken Cellars | 80 | 40 | VS |
| `tls_dgn_rootdeep` | Rootdeep Labyrinth | 90 | 45 | EA |
| `tls_dgn_bells` | Drowned Bells | 90 | 45 | EA |
| `tls_dgn_forgeheart` | The Forgeheart | 90 | 50 | 1.0 |
| `tls_dgn_starfall` | Starfall Spire | 90 | 50 | 1.0 |
| `tls_dgn_halcyon` | Halcyon Below | 100 | 60 | 1.0 |
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
| `map_dawnmere_vale` | Home region (192 × 144 tiles) | VS |
| `map_whisperwood` · `map_saltglass_coast` | Regions 2–3 | EA |
| `map_cinderpeak` · `map_frostveil` · `map_hollow_crown` | Regions 4–6 | 1.0 |
| `map_thorn_court` · `map_brinemouth` · `map_emberhold` · `map_rimewatch` · `map_frozen_manor` · `map_starfall_crater` | Special locations | EA / 1.0 |
| Festival decoration layers for the town map | Per festival | VS (1) → EA (8) |

### 6.5 Props, decals & nature (T-PROP, placed freely)

| Group | Contents | Milestone |
|---|---|---|
| Wild trees (T-TREE) | Round-canopy oak, pine, maple (VS, Spring) → + birch, palm, giant mushroom tree (EA, ×4 seasons) → + charred pine, frost fir, Veil Tree (1.0) | VS → 1.0 |
| Fruit trees & perennials | 6 fruit trees + Tea Bush (3 stages × 4 seasons + fruit overlay) + the **Kingsbloom** (bud and full-bloom states) | EA / 1.0 |
| Forest-floor set | Giant mushrooms (3 sizes), ferns, stumps, fallen logs, roots, berry bushes, flower clumps | VS (20 pieces) → 1.0 (50) |
| Water set | Lily pads, lotuses, reeds, stepping stones, driftwood, small dock, floating log | VS (12) → EA (20) |
| Rocks | Small, large, boulder × region variants + break animation | VS → 1.0 |
| Ore nodes | Copper, Veilglass crystal, gem, geode (VS) → Iron, Silver (EA) → Emberite, Starmetal, Heartstone (1.0); 2 sizes + break animation | VS → 1.0 |
| Forage on the ground | One prop per forage item (~35) | VS (6) → 1.0 |
| **Ground decals** (`dcl_`) | Clover patches, grass tufts, flower scatters, dirt specks, leaves, pebbles | VS (30) → 1.0 (80) |
| Veil features | Bramble, crystal node, Veil Wall segment, tendrils | VS |
| Ruins set pieces | Pillars, broken walls, sun-sigil floor stones, gates, the **headless Sovereign statue** (a story hint) | VS (20) → 1.0 (60) |
| Light props | Campfire, brazier, torch, Lumen Lamp, lantern post, light-shrine (animated flames or glow) | VS |
| **Lived-in clutter sets** | Laundry lines, barrels, clay pots, stools, crates, planters, **raised garden beds**, watering cans | VS (10) → EA (25) → 1.0 (40) |
| **Story landmarks** (ruined + restored states) | Ashen Throne (dormant, kindled), Windmill Ruin, Old Bridge, Ruined Chapel, Old Granary, Reflection Pond | VS |
| Misc | Signposts, carts (Mira's caravan), fences (wood, stone), field gates | VS |

### 6.6 Crops (T-CROP)

- Per crop: 4–6 growth stages, harvestable stage, regrow stage if any; one shared **withered** state; trellis crops are 64 × 128.
- Seed packets: one shared packet template + per-crop art (counted as icons in §8).
- **Crop images:** VS ~36 · EA ~160 · 1.0 ~190.

---

## 7. Buildings

Each exterior needs: the tier illustration + a **night emissive layer** (lit windows) + a **winter snow overlay** (EA). Surge damage uses a **shared damage-decal set**. All buildings use the same 3/4 front-facing projection ([08 §3](08_ART_DIRECTION.md#3-projection--camera)); Dawnmere buildings use the cream-stone and terracotta palette.

| ID pattern | Building | Tiers to draw | Milestone |
|---|---|---|---|
| `bld_throne_t0…t4` | The Throne | 5 | VS (t0–t1) · EA (t2) · 1.0 (t3–t4) |
| `bld_beacon_t1…t4` | Beacon | 4 | VS (t1–t2) · EA (t3) · 1.0 (t4) |
| `bld_storehouse_t1…t3` · `bld_granary_t1…t3` | Storage | 3 + 3 | VS (t1) · EA (t2–t3) |
| `bld_tent` · `bld_hut` · `bld_well` | Early basics | 1 each | VS |
| `bld_lumber_camp_t1…t2` · `bld_den_t1…t4` | Production | 2 + 4 | VS (t1) · EA (rest) |
| `bld_lodge` · `bld_clinic_t1` · `bld_scout_post_t1` · `bld_smithy_t1` · `bld_tavern_t1` | VS Sworn / service | 1 each | VS |
| `bld_clinic_t2` · `bld_scout_post_t2` · `bld_tavern_t2` · `bld_smithy_t2` (Great Forge) | Upgrades | 1 each | EA |
| `bld_waybeacon` · `bld_cottage` · `bld_quarry` · `bld_mill` · `bld_glasshouse` · `bld_guard_post` · `bld_watchtower` | EA general | 1 each | EA |
| `bld_market` · `bld_archive` · `bld_nursery` · `bld_chapel` · `bld_spire` · `bld_harbor` · `bld_bandstand` · `bld_workshop` | EA Sworn | 1 each | EA |
| `bld_wall_*` · `bld_gate_*` | Palisade (EA) → Stone → Runed (1.0) | Wall-piece set + gate per material | EA / 1.0 |
| `bld_townhouse` · `bld_manor` · `bld_bathhouse` | 1.0 general | 1 each | 1.0 |
| `bld_arena` · `bld_lab` · `bld_brewery` · `bld_barracks` · `bld_observatory` · `bld_hunters_lodge` · `bld_tailor` · `bld_hall_of_knights` | 1.0 Sworn | 1 each | 1.0 |
| `bld_scaffold_{s,m,l,xl}_{1..3}` | Construction stages by footprint class | 3 per class | VS (s, m) → EA (l, xl) |
| `vfx_bld_damage_*` · `bld_snow_*` | Shared damage decals · snow caps | Sets | EA |

**Exterior illustrations:** VS **16** · EA **~47** · 1.0 **65**.

---

## 8. Items & icons (T-ICON, 64 px)

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
| Tools (all tiers) | Tier tints + small shape changes | 12 | 27 | 34 |
| Weapons | Tier tints; unique T4/T5 shapes | 4 | 20 | 35 |
| Armour & trinkets | Unique | 9 | 30 | 54 |
| Sigils, creature items, catalysts | Unique | 5 | 15 | 24 |
| Consumables | Unique | 5 | 10 | 10 |
| Fish (+ trash) | Unique | — | 16 | 23 |
| Key items (Regalia, fragments, embers, charter, rings, keys…) | Unique | 5 | 16 | 26 |
| Clothing (cosmetic) | Rendered from the Spine skins | 3 | 20 | 60 |
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
| **Knight statues** | Generated: a Sworn's idle pose rendered through a stone shader + pedestal | — | — | up to 24 |
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
| `fnt_body` | Dialogue, menus | Rounded, friendly, highly readable sans (e.g. *Nunito*); Latin Extended for future localisation; open licence (e.g. SIL OFL) |
| `fnt_heading` | Titles, names | Royal serif capitals (e.g. *Cinzel*) |
| `fnt_numbers` | Damage, gold, clock | Bold weight of the body font, tabular digits |
| `fnt_dyslexic` | Accessibility option | Dyslexia-friendly font with an open licence |

Every font's licence gets verified and recorded in `CREDITS.md` before shipping.

---

## 14. Marketing & store

| ID | Asset | Milestone |
|---|---|---|
| `mkt_logo` | Logo: the broken crown with a sprout (vector) | Step 17 |
| `mkt_key_art_wide` / `_tall` | Illustrated key art (see [08 §15](08_ART_DIRECTION.md#15-logo--key-art-concept)) | Step 17 |
| `mkt_capsule_*` | All Steam capsule and library sizes (per the current Steamworks spec) | Step 17 |
| `mkt_screenshots` | 10 curated in-engine screenshots | Step 17 |
| `mkt_trailer_announce` | 60–90 s announce trailer | Step 17 |
| `mkt_gifs_weekly` | Build-in-public GIFs and clips (from Step 6 onward) | Ongoing |
| `mkt_social_*` | Avatars and banners for X, Instagram, TikTok, YouTube | Step 17 |
| `mkt_devlog_template` | Devlog header template | Step 17 |
| `mkt_presskit` | Fact sheet, logos, screenshots, key art | Step 21 |
| `mkt_trailer_ea` | Early Access launch trailer | Step 22 |

---

## 15. Totals by milestone

| Category | Unit | VS | EA | 1.0 |
|---|---|---|---|---|
| Player rig animations | Animations (most in 3 views) | ~30 | ~46 | ~47 |
| Player customization skins | Hair / outfits / hats / accessories | 6 / 3 / 0 / 0 | 12 / 10 / 6 / 4 | 16 / 24 / 12 / 12 |
| Sworn rigs | Rigs | 5 | 16 | 24 |
| Companion combat sets | Sets | 3 | 7 | 12 |
| Story NPC & enemy rigs | Rigs / sheets | 10 | 18 | 19 |
| Settler portrait kit | Parts | 39 | 67 | 80 |
| Portraits | Expressions | 67 | 177 | 278 |
| Creature forms (incl. Guardians) | Rigs / sheets | 15 | 38 | 60 |
| Ambient life | Sets | 4 | 6 | 6 |
| Bosses (all) | Rigs | 2 | 5 | 11 |
| Terrain tilesets | Sets | 6 | 8 (+ seasons) | 11 |
| Dungeon tilesets / room chunks | Sets / chunks | 1 / 40 | 3 / 130 | 6 / 290 |
| Interior tilesets / maps | Sets / maps | 1 / 8 | 3 / 20 | 4 / 30 |
| Ground decals | Decals | 30 | 55 | 80 |
| Lived-in clutter pieces | Props | 10 | 25 | 40 |
| Building exteriors | Illustrations | 16 | ~47 | 65 |
| Item icons | Icons | ~110 | ~375 | ~560 |
| Furniture & decor | Objects | ~20 | ~70 | ~120 |
| UI screens | Screens | 24 | 28 | 30 |
| VFX | Effects | ~77 | ~116 | ~139 |
| Music (+ jingles) | Tracks | 14 (+10) | 35 (+11) | 48 (+11) |
| SFX / ambience | Sounds / loops | ~150 / 6 | ~380 / 18 | ~550 / 30 |

---

## 16. Production notes

### 16.1 Cost savers (built into the specs above)
1. **Spine skins** for the player, settlers, and outfits: a new hairstyle is one set of attachments, not a redrawn animation.
2. **Tint and gradient-map shaders** for skin, hair, cloth, tool and weapon tiers, and seasonal colour shifts.
3. **The Hollowed are a shader**: 38 corrupted variants with zero new art.
4. **Layered portraits**: expressions swap eyes, brows, and mouth.
5. **A small prop kit dresses big maps**: the reference look comes from **density and placement**, so trees, mushrooms, rocks, decals, and clutter are reused everywhere.
6. **Tinted icon templates** for artisan goods (jam, wine, juice, pickles, dye).
7. **Shared scaffolds, snow overlays, and damage decals** for all buildings.
8. **Generated Knight statues** from Sworn rigs.
9. **Mirrored side views** (left = flipped right).
10. **Room chunks** reused across floors; Veil Rifts remix all existing chunks.
11. **The Named crown mark** is one overlay with per-species anchor points.

### 16.2 Outsourcing packages (for hired artists)
| Package | Contents | Must include |
|---|---|---|
| A: Terrain & props | One region at a time | Palette swatches, scale chart, a Tiled test map, reference board (links) |
| B: Character parts + rigs | Sworn, player, settlers | Layer naming (§2.3), turnaround sheets, cast bible excerpt; rigging can be a separate Spine animator |
| C: Portraits | Sworn portraits | Layered template, expression guide |
| D: Creatures | By size class | T-CRE templates, bestiary excerpt, shape-language table |
| E: UI & icons | Kit + icon sets | 9-slice guides, icon grid, colour-blind rules |
| F: VFX | By group | Colour language, timing targets |

### 16.3 Per-asset review checklist
- [ ] Palette, line weight, and shading steps match [08 §5–6](08_ART_DIRECTION.md#5-line-art--shading)
- [ ] Authored at 2×; correct pivot (ground contact point) and sort point
- [ ] Layers and Spine slots follow the naming convention
- [ ] Reads clearly at 1080p **and** at phone size
- [ ] Same 3/4 projection and top-left light as everything else
- [ ] Original work (no tracing or copying of references)
- [ ] Exported with the project export script (never by hand)
- [ ] Status updated in the tracker
