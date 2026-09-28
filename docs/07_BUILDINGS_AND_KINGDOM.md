# 07 — Buildings & Kingdom

> **TL;DR:** **42 building types** at 1.0 (14 in the Vertical Slice), each with footprint, tiers, unlock condition, function, and staff. Plus crafting stations, **Restoration Projects** (bundle goals), **12 Royal Decrees**, Court Day petition templates, **8 festivals**, and how the town visibly grows at each Kingdom Rank. Costs are placeholders.

---

## 1. Building rules

- **Placement:** prefab buildings on the 16 px tile grid, **inside the Realm** only. Footprints are in tiles (W×H) and include a 1-tile walkable apron at the door.
- **The Throne is fixed** on the hill at the Ashen Throne; every other building can be moved with the Hammer (free, instant).
- **Construction:** materials + gold, then it takes days. The site shows scaffold stages. Builders (Bram, Builder settlers, Crafting familiars) speed it up.
- **Upgrades** happen in place. Some tiers need a specific Sworn; the footprint may grow (the player must leave room).
- **Staffing:** production and service buildings have **worker slots** (settlers or familiars). **Sworn live in quarters inside their own building** (like shopkeepers in classic farming sims), so they need no separate house.
- **Night:** buildings have an emissive "lit windows" layer. Light carves the town out of the Veil.

---

## 2. Kingdom Ranks & what they unlock

| Rank | Title | Requirements | Unlocks |
|---|---|---|---|
| 0 | **Exile's Camp** | Start | Campfire, Heartflame Brazier (Beacon T1), Tent, Workbench, Chest, Cooking Pot |
| 1 | **Hamlet** | 3 residents (2 Sworn), Longhouse, Beacon T1 | **The Founding** (name + banner) · Hut · Storehouse · Granary · Den T1 · Lumber Camp · Cookhouse · Well · Beacon T2 · Sworn buildings for those recruited |
| 2 | **Village** | 12 residents (5 Sworn), the Signet, Beacon T2 | Cottage · Den T2 · Quarry · Mill · Guard Post · Watchtower · Palisade · Waybeacon · **Decree slot 1** · **Court Day** · **Expeditions** · Tithe |
| 3 | **Town** | 25 residents (9 Sworn), Stone Keep, the Scepter | Glasshouse · Den T3 & Sanctuary · stone walls · Beacon T3 (with the Orb) · **Decree slot 2** |
| 4 | **City** | 45 residents (15 Sworn), Castle, the Orb + the Sunblade | Townhouse · Bathhouse · runed walls · Beacon T4 (with the Mantle) · **Decree slot 3** · party of 4 |
| 5 | **Kingdom** | 70 residents (20 Sworn), Palace, the Mantle | Manor · Royal Feast kitchen · Knight statues · **Decree slot 4** · Coronation Festival · Chapter 6 |

A Sworn's building unlocks **when that Sworn joins**, as long as the minimum rank listed in §3 is met.

---

## 3. Building catalogue

### 3.1 Royal & civic

| ID | Building | Footprint | Tiers | Function | Milestone |
|---|---|---|---|---|---|
| `bld_throne` | **The Throne** | 3×3 → 6×5 → 8×7 → 12×10 → 16×12 | T0 Ashen Throne (ruin) → T1 **Longhouse** → T2 **Stone Keep** → T3 **Castle** → T4 **Palace** | Your home (bed, kitchen, storage), Court Day, Decrees, Naming & Knighting ceremonies, **Trade Crate** | VS (T0–T1) · EA (T2) · 1.0 (T3–T4) |
| `bld_beacon` | **Beacon** | 3×3 → 4×4 | T1 Heartflame Brazier → T2 Beacon Tower → T3 Great Beacon → T4 Sunspire | Realm radius 10 / 18 / 28 / 40 | VS (T1–T2) · EA (T3) · 1.0 (T4) |
| `bld_waybeacon` | Waybeacon | 2×2 (in the wild) | — | 6-tile bubble on roads, clears Veil Walls, fast travel | EA |
| `bld_storehouse` | Storehouse | 3×3 → 5×4 | T1–T3 | Shared storage for workers | VS |
| `bld_granary` | **Granary** | 3×3 → 5×5 | T1–T3 (T3 adds a cold cellar) | **Food Stock**, spoilage reduction | VS |

### 3.2 Housing

| ID | Building | Footprint | Beds | Comfort | Milestone |
|---|---|---|---|---|---|
| `bld_tent` | Tent | 2×2 | 1 | ★ | VS |
| `bld_hut` | Hut | 3×3 | 2 | ★★ | VS |
| `bld_cottage` | Cottage | 4×4 | 4 | ★★★ | EA |
| `bld_townhouse` | Townhouse | 4×5 | 6 | ★★★★ | 1.0 |
| `bld_manor` | Knights' Manor | 6×5 | Up to 4 Knights (optional move-in) | ★★★★★, +Loyalty | 1.0 |

### 3.3 Production

| ID | Building | Footprint | Staff | Function | Milestone |
|---|---|---|---|---|---|
| `bld_well` | Well | 2×2 | — | Refill the watering can; +fire safety | VS |
| `bld_lumber_camp` | Lumber Camp | 4×3 → 5×4 | 2 → 4 | Logging jobs, tree replanting; T2 adds a **sawmill** (bulk planks) | VS |
| `bld_den` | **Creature Den** | 4×3 → 5×4 → 6×5 → **Sanctuary** 8×6 | Familiar beds 4 / 8 / 16 / 30 | Familiar rest, feeding, Bond; produce collection; Sanctuary adds a pasture, egg incubator, hatching (Juniper) | VS (T1) · EA (T2–Sanctuary) |
| `bld_quarry` | Quarry | 4×4 (on rocky terrain) | 3 | Stone, clay, occasional ore | EA |
| `bld_mill` | Mill | 3×4 | 1 | Flour, cornmeal | EA |
| `bld_glasshouse` | Glasshouse | 7×6 | 2 | Any-season crops (120 tiles) | EA |

### 3.4 Sworn buildings (services)

| ID | Building | Sworn | Min rank | Footprint | Function | Milestone |
|---|---|---|---|---|---|---|
| `bld_lodge` | **Carpenter's Lodge** | Bram | 0 | 5×4 | Enables construction and upgrades; builder jobs | VS |
| `bld_clinic` | Herbalist Hut → **Clinic** | Linnea | 0 | 3×3 → 5×4 | Knockout recovery, injuries, early potions, Veil-rot cleansing | VS (T1) · EA (T2) |
| `bld_scout_post` | **Scout's Post** → Expedition Hall | Rook | 1 | 3×3 → 4×4 | Map, bounties; **Expeditions** at T2 | VS (T1) · EA (T2) |
| `bld_smithy` | **Smithy** → Great Forge | Tamsin → Durgan | 1 | 5×4 → 7×5 | Tool and weapon upgrades, smelting, geodes; Great Forge: tiers 4–5 and the Sunblade | VS (T1) · 1.0 (T2) |
| `bld_tavern` | Cookhouse → **Tavern** | (settler cook) → Marigold | 1 | 4×3 → 6×5 | Communal meals (Food Stock → dishes), recipes, arrivals notice board, rumours | VS (T1) · EA (T2) |
| `bld_market` | **Market** | Mira | 2 | 7×5 | Daily shop, settler stalls, trade | EA |
| `bld_archive` | **Royal Archive** | Elowen | 2 | 6×5 | Donations, collections, Memory Fragments, **research** | EA |
| `bld_nursery` | **Grove Nursery** | Fen | 2 | 5×5 | Saplings, rare seeds, Veil Seed germination | EA |
| `bld_chapel` | **Chapel of Dawn** | Aldous | 2 | 5×6 | Weekly blessings, Veil-rot cleansing, festivals, **weddings** | EA |
| `bld_spire` | **Enchanter's Spire** | Nix | 2 | 3×3 (tall) | Sigil upgrades, enchanting, Veil Essence | EA |
| `bld_harbor` | **River Harbor** (+ Fishery wing) | Mari (+ Orin) | 3 | 8×5 (on the river) | Trade routes, sea expeditions, fishing upgrades, Tide Traps | EA |
| `bld_bandstand` | **Bandstand** | Seren | 3 | 4×4 | Morale, festival bonuses, the kingdom anthem | EA |
| `bld_workshop` | **Workshop** | Pim & Pom | 3 | 5×4 | Dew Totems, Hauler Posts, auto-feeders, Clocktower | EA |
| `bld_arena` | **Arena** | Kaida | 4 | 8×8 | Sparring, challenges, familiar duels, Sun Tourney venue | 1.0 |
| `bld_lab` | **Alchemist Lab** | Hollis | 4 | 4×4 | Potions, fertilizers, Veil tonics | 1.0 |
| `bld_brewery` | **Brewery** | Hilde | 4 | 5×4 | Premium ales and wines, festival drinks | 1.0 |
| `bld_barracks` | **Barracks** | Ingrid | 4 | 6×5 | Guards, training, Surge defense | 1.0 |
| `bld_observatory` | **Observatory** | Saga | 4 | 5×5 (tower) | Forecasts, luck, star events | 1.0 |
| `bld_hunters_lodge` | **Hunter's Lodge** | Tor | 4 | 5×4 | Bounties, tracking, **mounts** | 1.0 |
| `bld_tailor` | **Tailor's House** | Isolde | 4 | 4×4 | Clothing, dyes, **heraldry editor** | 1.0 |
| `bld_hall_of_knights` | **Hall of Knights** | Caelan | 5 | 8×6 | Knight Order upgrades; final defense | 1.0 |
| `bld_bathhouse` | **Bathhouse** | (settlers) | 4 | 6×5 | Joy, Energy restore; heated by Kindling familiars | 1.0 |

### 3.5 Defense

| ID | Building | Footprint | Function | Milestone |
|---|---|---|---|---|
| `bld_guard_post` | Guard Post | 2×2 | 1 guard slot; stops pests; Surge defense | EA |
| `bld_watchtower` | Watchtower | 2×2 | +8-tile Realm bubble; archer slot | EA |
| `bld_wall` | Walls | 1×1 segments | Palisade (EA) → Stone (Town) → Runed (City, 1.0) | EA |
| `bld_gate` | Gate | 3×1 | Opens for residents, closes on Surge nights | EA |

### 3.6 Decor (no staff; adds Comfort, Joy, Prosperity)
Paths (dirt, stone, brick) · fences · **Lumen Lamps** · flower beds · benches · fountains · **banners** (your heraldry) · **Knight statues** (one per Knight; 1.0) · Clocktower · hedges · festival decorations.

**Building type counts:** VS **14** · EA **31** · 1.0 **42**.

### 3.7 Example costs (VS placeholders)

| Building | Cost | Build time |
|---|---|---|
| Tent | 10 Wood, 5 Fiber | Instant |
| Hut | 40 Wood, 20 Stone, 5 Rope | 1 day |
| **Longhouse** (Throne T1) | 150 Wood, 80 Stone, 20 Planks, 500g | 3 days |
| Storehouse | 60 Planks, 30 Stone | 1 day |
| Granary | Free via Restoration Project, or 80 Planks, 50 Stone, 300g | 1 day |
| Carpenter's Lodge | 50 Wood, 30 Stone | 1 day |
| Herbalist Hut | 40 Wood, 20 Fiber, 10 Healing Herb | 1 day |
| Smithy | 60 Stone, 40 Wood, 10 Copper Ore | 2 days |
| Scout's Post | 40 Wood, 20 Planks | 1 day |
| Den T1 | 50 Wood, 30 Fiber, 10 Clover | 1 day |
| Lumber Camp | 60 Wood, 20 Stone | 1 day |
| Cookhouse | 40 Wood, 40 Stone, 5 Copper Bars | 1 day |
| Well | 30 Stone, 10 Wood | Instant |
| **Beacon Tower** (T2) | 80 Stone, 40 Planks, 10 Copper Bars, 5 Veilglass | 2 days |

---

## 4. Crafting stations (placeable objects)

| Station | Function | Milestone |
|---|---|---|
| Campfire | Light, basic cooking, one-night safe bubble in the wild | VS |
| Workbench | Crafting | VS |
| Cooking Pot → Kitchen | Cooking (Kitchen is inside the Longhouse or better) | VS → EA |
| **Smelter** | Ore → bars (fuel or a **Kindling** familiar) | VS |
| Chest / Seed Chest / Harvest Chest | Storage; familiar farm-work supply | VS |
| **Field Post** | Marks a familiar work zone (radius 6) | VS |
| Straw Sentinel | Keeps crop-stealing Gnawrats away | VS |
| Compost Bin | Compost fertilizer | VS |
| Lumen Lamp | Light, Exposure reduction (radius 3) | VS |
| Preserves Jar · Keg · Churn · Cheese Press · Loom · Beehive · Kiln · Smoker · Dye Pot | Artisan goods ([06 §7](06_ITEMS_CROPS_RECIPES.md#7-artisan-goods-processing-chains-3-steps)) | EA |
| Dew Totem T1–T3 · Hauler Post · Incubator · Tide Trap | Automation & familiars | EA |
| Enchanting Table · Alchemy Set · Auto-Feeder | Advanced | EA / 1.0 |

---

## 5. Restoration Projects (bundle goals)

Landmarks restored by delivering **bundles** of items. Inspired by community-restoration goals in classic farming sims, but here you're **restoring your own kingdom's ruins**.

| Project | Bundles (examples) | Reward | Milestone |
|---|---|---|---|
| **The Old Granary** (Dawnmere) | Spring Harvest · Timber & Stone · Forager's Basket | Granary T1 built free; Food Stock system explained | VS |
| **The Old Bridge** (Dawnmere) | 50 Planks, 40 Stone, 5 Copper Bars | Road north (with a Waybeacon → Chapter 2) | EA |
| **The Windmill** (Dawnmere) | Wood, Cloth, Wheat | Free Mill; wheat yield +10% | EA |
| **The Ruined Chapel** (Dawnmere) | Stone, Glass, Dawnbells | Chapel site for Aldous | EA |
| **The Royal Aqueduct** (Dawnmere) | Bricks, Copper, Aquamarine | Commons fields watered automatically | EA |
| **The Great Library** (Whisperwood) | Ancient Pages, Amber, Glowcaps | Archive research tree | EA |
| **The Lighthouse** (Saltglass) | Glass, Silver Bars, Glow Oil | Safer trade routes; night fishing bonus | EA |
| **Emberhold Gate** (Cinderpeak) | Emberite, Obsidian, Stonebrew Ale | Dwarven trade; Durgan's trust | 1.0 |
| **Rimewatch Beacon** (Frostveil) | Thick Cloth, Warm Brews, Sunstone | Support during the Long Winter | 1.0 |

---

## 6. Royal Decrees

Slots: Village 1 · Town 2 · City 3 · Kingdom 4. Changing a decree costs **10 RA**; each must stay active **at least 7 days**. **Values** show whose Loyalty goes up (+) or down (−) (see [04](04_CHARACTERS.md)).

| # | Decree | Upside | Downside | Values + / − | Milestone |
|---|---|---|---|---|---|
| 1 | **Harvest Tithe** | 10% of all harvests go straight to the Granary | Crop sale income −5% | + Family · − Prosperity | EA |
| 2 | **Open Gates** | Settler arrivals ×2 | Safety −10 | + Freedom, Mercy · − Order | EA |
| 3 | **Night Curfew** | Night incidents −50%; Surges −1 wave | Joy −5 (Night Owls −15) | + Order · − Freedom | EA |
| 4 | **Festival Year** | Festival Joy ×2 | Production −10% in festival weeks | + Tradition, Family · − Prosperity | EA |
| 5 | **Rationing** | Food consumption −25% | Joy −10 | + Order · − Family | EA |
| 6 | **Mercy Edict** | Spared enemies join faster; more arrivals from spared factions | Safety −5 | + Mercy, Faith · − Order | EA |
| 7 | **Forge Mandate** | Smithing and crafting speed +25% | Joy −5 (noise) | + Progress · − Nature | 1.0 |
| 8 | **Sanctuary Act** | Familiar Bond gain +25% | Familiar work speed −10% | + Nature · − Prosperity | 1.0 |
| 9 | **Iron Law** | Guards +20%; pests and theft stopped | Joy −10 | + Order, Honor · − Freedom, Mercy | 1.0 |
| 10 | **Free Market** | Sell prices +10% | Buy prices +10% | + Prosperity, Freedom · − Tradition | 1.0 |
| 11 | **Scholars' Charter** | Research cost −25% | Production −5% | + Progress · − Tradition | 1.0 |
| 12 | **Knights' Oath** | Knight perks +50% | RA gain −1/day | + Honor · − Freedom | 1.0 |

Ending C (*The Hearth Commonwealth*) requires having enacted **Mercy Edict** and **Scholars' Charter** at least once.

---

## 7. Court Day petition templates

Petitions are **data-driven cards**: a template plus variables (names, items, amounts). Target: 60+ at 1.0 (15 in EA's first chapter).

| Template | Example text | Options (effects) |
|---|---|---|
| **Field Dispute** | "{A} and {B} both claim the east field." | Give it to A (+A, −B) · Split it (−10% yield, +both) · Royal field (+RA, −both) |
| **Repair Request** | "The {building} roof leaks. Can the crown spare {n} {item}?" | Grant (−items, +Joy) · Delay (−Joy) |
| **New Arrival** | "A {background} from {place} asks to join." | Accept (+1 settler) · Decline · Ask for proof (quest) |
| **Decree Proposal** | "{A} suggests we enact {decree}." | Enact now (costs RA) · Consider later · Refuse (−A Standing) |
| **Omen** | "Strange lights over the {region} last night…" | Investigate (unlocks an event) · Ignore |
| **Theft** | "Someone's been taking from the Granary." | Investigate (Gnawrat mini-hunt) · Post a guard · Forgive |
| **Festival Request** | "Could we hold a small feast for {occasion}?" | Fund it (−gold, +Joy) · Decline |
| **Personal** | "{Sworn} asks to speak with you privately." | Opens a **heart event** |

---

## 8. Festivals

| Date | Festival | Activities | Milestone |
|---|---|---|---|
| Spring 13 | **Blossomfall** | Cherry-blossom picnic, the Blossom Dance (romance), strawberry seeds on sale | VS |
| Spring 24 | **Beast Fair** | Familiar show (judged by Bond, Named, Ascended), creature races | EA |
| Summer 11 | **Sun Tourney** | Sparring brackets with Sworn; the Arena hosts it from 1.0 | EA |
| Summer 26 | **Lantern Tide** | Floating lanterns on the river, fireworks, festival outfits, night market | EA |
| Autumn 16 | **Harvest Court** | Crop judging at the Throne, the Tithe Feast, a royal speech | EA |
| Autumn 27 | **Hollow's Eve** | Costumes, ghost stories, a safe "haunted" Veil maze | EA |
| Winter 8 | **Hearthfire Night** | Communal bonfire, storytelling, secret gift exchange | EA |
| Winter 25 | **Starfall Vigil** | Meteor shower on the hill, wishes, confessions | EA |

**Story festivals:** the Founding Feast (VS, story-triggered) · Royal Wedding (EA) · Coronation (Kingdom rank, 1.0).
No festival falls on a Sunday (Court Day) or a New Moon (Surge night).

---

## 9. How the kingdom visibly grows

| Rank | Skyline | Night view | Town music layer |
|---|---|---|---|
| 0 Exile's Camp | Ruined throne, tent, campfire; heavy Veil at the edges | One small circle of light | Music box + whistle |
| 1 Hamlet | Longhouse, huts, first fields, one banner | A warm glowing cluster | + acoustic guitar |
| 2 Village | Cottages, tavern chimney smoke, market stalls, chapel bell | Lamps along paths | + fiddle & flute |
| 3 Town | Stone Keep, stone walls, river harbor, glasshouse | The walls ringed in light | + strings & light percussion |
| 4 City | Castle, Great Forge smoke, arena, towers | Bright districts, a Sunspire glow | + brass & choir |
| 5 Kingdom | Palace, gardens, Knight statues, the Sunspire | The Veil pushed back to the horizon | Full orchestra + the **Halcyon Anthem** motif |

This is the Suikoden lesson: **the player should feel the kingdom grow just by walking through it and listening.**
