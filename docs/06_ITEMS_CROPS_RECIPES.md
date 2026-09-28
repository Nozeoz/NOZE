# 06 — Items, Crops & Recipes

> **TL;DR:** Every item category with IDs and milestones: **29 crops + 6 fruit trees + the Tea Bush**, forage by region, ores and gems, processed materials, artisan chains, **26 recipes**, tools, weapons, armour, Pact Sigils, consumables, **20 fish**, and key items. **Prices and times are first-pass placeholders** for the grey-box and will be balanced in playtests.

---

## 1. Item ID conventions

| Prefix | Category | Example |
|---|---|---|
| `seed_` | Seeds & saplings | `seed_turnip`, `sapling_cherry` |
| `crop_` | Harvested crops & fruit | `crop_turnip` |
| `frg_` | Forage | `frg_wild_leek` |
| `min_` | Ores, stone, gems, geodes | `min_copper_ore`, `min_ruby` |
| `mat_` | Materials (raw & processed) | `mat_plank`, `mat_copper_bar` |
| `cmat_` | Creature materials | `cmat_moss_fluff` |
| `art_` | Artisan goods | `art_jam_strawberry` |
| `food_` | Cooked dishes & drinks | `food_vegetable_stew` |
| `tool_` | Tools | `tool_hoe_copper` |
| `wpn_` | Weapons | `wpn_spear_iron` |
| `arm_` / `trk_` | Armour / trinkets | `arm_body_leather`, `trk_moss_ring` |
| `sig_` | Pact Sigils & creature items | `sig_copper`, `sig_treat` |
| `con_` | Consumables | `con_healing_salve` |
| `fish_` | Fish | `fish_sunperch` |
| `key_` | Key & story items | `key_regalia_signet` |
| `fur_` / `dec_` | Furniture / decor | `fur_bed_simple`, `dec_lumen_lamp` |

**Quality tiers** (crops, forage, fish, artisan goods, dishes): Normal · Silver · Gold · **Royal** (sale ×1.0 / ×1.25 / ×1.5 / ×2.0).

---

## 2. Crops

Columns: **Days** to first harvest · **Regrow** (days between harvests, "—" = single harvest) · **Seed** price · **Sell** (Normal quality).

### Spring

| ID | Crop | Days | Regrow | Seed | Sell | Notes | Milestone |
|---|---|---|---|---|---|---|---|
| `crop_turnip` | Turnip | 4 | — | 20 | 36 | Fast starter crop | VS |
| `crop_carrot` | Carrot | 5 | — | 30 | 55 | Mossbun's favourite (Offering) | VS |
| `crop_potato` | Potato | 6 | — | 50 | 85 | 20% chance of an extra potato | VS |
| `crop_cabbage` | Cabbage | 9 | — | 70 | 165 | Stew staple | VS |
| `crop_dawnbell` | **Dawnbell** *(fantasy flower)* | 7 | — | 40 | 90 | Chimes at dawn; attracts Glimmoth; dye | VS |
| `crop_mandrake` | **Mandrake Root** *(fantasy)* | 8 | — | 90 | 180 | 5% chance to be a **Mandragling** | VS |
| `crop_snappea` | Snap Pea | 7 | 3 | 60 | 40 | Trellis (blocks walking) | EA |
| `crop_strawberry` | Strawberry | 8 | 4 | 100 | 60 | Seeds sold only at Blossomfall | EA |

### Summer

| ID | Crop | Days | Regrow | Seed | Sell | Notes | Milestone |
|---|---|---|---|---|---|---|---|
| `crop_tomato` | Tomato | 10 | 4 | 60 | 55 | | EA |
| `crop_corn` | Corn | 14 | 4 | 90 | 50 | Summer **and** Autumn | EA |
| `crop_blueberry` | Blueberry | 13 | 4 | 80 | 45 | 3 berries per harvest | EA |
| `crop_melon` | Melon | 12 | — | 90 | 260 | | EA |
| `crop_chili` | Chili Pepper | 5 | 3 | 40 | 40 | | EA |
| `crop_wheat` | Wheat | 4 | — | 10 | 25 | Summer **and** Autumn → Flour, Ale | EA |
| `crop_sunfruit` | **Sunfruit** *(fantasy)* | 13 | — | 150 | 320 | Glows at night → **Lumen Essence** | EA |
| `crop_emberroot` | **Emberroot** *(fantasy)* | 7 | — | 70 | 140 | Spicy; Warmth dishes; Ignis gear | EA |

### Autumn

| ID | Crop | Days | Regrow | Seed | Sell | Notes | Milestone |
|---|---|---|---|---|---|---|---|
| `crop_pumpkin` | Pumpkin | 13 | — | 100 | 320 | | EA |
| `crop_eggplant` | Eggplant | 5 | 5 | 30 | 60 | | EA |
| `crop_grape` | Grapes | 10 | 3 | 60 | 80 | Trellis → Wine | EA |
| `crop_yam` | Yam | 10 | — | 60 | 160 | | EA |
| `crop_cranberry` | Cranberry | 7 | 5 | 240 | 75 | 2 per harvest | EA |
| `crop_lanterngourd` | **Lanterngourd** *(fantasy)* | 12 | — | 120 | 240 | Carve → Lumen Lamp | EA |
| `crop_rice` | Rice | 8 | — | 40 | 60 | Needs a flooded **paddy** tile | 1.0 |
| `crop_nightcorn` | **Nightcorn** *(fantasy)* | 10 | — | 110 | 220 | Grows only on **unlit** tiles | 1.0 |

### Winter

| ID | Crop | Days | Regrow | Seed | Sell | Notes | Milestone |
|---|---|---|---|---|---|---|---|
| `crop_frostkale` | Frostkale | 6 | — | 50 | 110 | | EA |
| `crop_winterradish` | Winter Radish | 5 | — | 40 | 90 | | EA |
| `crop_snowberry` | Snowberry *(bush)* | 10 | 5 | 150 | 70 | | EA |
| `crop_icebloom` | **Icebloom** *(fantasy flower)* | 9 | — | 120 | 230 | → **Chilling Essence** | 1.0 |
| `crop_frostcap` | Frostcap Mushroom | 7 | — | 60 | 130 | Grows only in shade (next to buildings) | 1.0 |

### Veil Seeds (rare dungeon loot, any season)

| ID | Crop | Days | Sell | Rule | Milestone |
|---|---|---|---|---|---|
| `crop_veilblossom` | Veilblossom | 10 | 600 | Must be within 2 tiles of a Lumen source or it becomes a Hollow Sprout | EA |
| `crop_crystalwheat` | Crystal Wheat | 8 | 420 | Same rule; → Veilglass Flour (enchanting) | 1.0 |
| `crop_starmelon` | Starmelon | 14 | 1,200 | Same rule; loved by many | 1.0 |

**Crop counts:** VS **6** · EA **25** · 1.0 **29** (plus 3 Veil Seed crops).

---

## 3. Trees & perennials

| ID | Tree | Fruit season | Sapling | Sell (fruit) | Notes | Milestone |
|---|---|---|---|---|---|---|
| `tree_cherry` | Cherry (blossom) | Spring | 600 | 80 | Blossoms during Blossomfall | EA |
| `tree_peach` | Peach | Summer | 800 | 140 | | EA |
| `tree_orange` | Orange | Summer | 800 | 100 | | EA |
| `tree_apple` | Apple | Autumn | 700 | 100 | | EA |
| `tree_pomegranate` | Pomegranate | Autumn | 900 | 140 | | 1.0 |
| `tree_silverpear` | **Silverpear** *(fantasy)* | Winter | 1,500 | 260 | Fruit shimmers in snow | 1.0 |
| `bush_tea` | Tea Bush | Spring–Autumn | 1,000 | Leaves 50 | Leaves every 3 days → Black Tea | EA |
| `bush_halcyon_rose` | **Halcyon Rose** *(story)* | Any | Story | — | An "extinct" flower re-grown from a seed found in Ch5; Caelan's loved gift | 1.0 |

Wild (non-fruit) trees: Oak, Pine, Maple, Birch, Palm (coast), Giant Mushroom (Whisperwood), Charred Pine (Cinderpeak), Frost Fir (Frostveil), **Veil Tree** (outside the Realm; gives Hardwood and Veil Sap).

---

## 4. Forage (by region)

| Region | Spring | Summer | Autumn | Winter | Any / special |
|---|---|---|---|---|---|
| **Dawnmere Vale** | Wild Leek, Dandelion, Clover | Sunberry, Clover | Blackberry, Hazelnut | Snowdrop, Winter Root | Healing Herb (not winter), Wild Mint (Sp–Au), Fiber (weeds) |
| **Whisperwood** | Morel | Fiddlehead Fern, Wild Honey | Chanterelle, **Golden Acorn** (rare) | Frost Moss | **Glowcap** (night), **Shadow Plum** (night, rare), **Moonpetal** (full moon, rare) |
| **Saltglass Coast** | Clam, Seaweed | Coral, Sea Urchin | Cockle | — | Saltglass Shard, **Pearl** (rare), **Rainbow Shell** (rare) |
| **Cinderpeak** | — | Firecap | **Emberbean**, **Golden Hops** | — | Cinder Moss, Obsidian Shard |
| **Frostveil** | — | Snowbloom | — | Ice Lichen | **Stardust** (Starfall Crater, night) |

---

## 5. Minerals, ores & gems

| ID | Item | Where | Pickaxe needed | Milestone |
|---|---|---|---|---|
| `min_stone` | Stone | Everywhere | Crude | VS |
| `min_coal` | Coal | Dungeons | Crude | VS |
| `min_clay` | Clay | Riverbanks, digging | Hoe | VS |
| `min_copper_ore` | Copper Ore | Sunken Cellars | Crude | VS |
| `min_iron_ore` | Iron Ore | Rootdeep Labyrinth | Copper | EA |
| `min_silver_ore` | Silver Ore | Drowned Bells | Iron | EA |
| `min_emberite_ore` | Emberite Ore | The Forgeheart | Silver | 1.0 |
| `min_starmetal_ore` | Starmetal Ore | Starfall Spire | Silver | 1.0 |
| `min_veilglass` | **Veilglass** | All dungeons + crystal nodes **outside the Realm at night** | Copper | VS |
| `min_heartstone` | Heartstone Shard | Halcyon Below | Starmetal | 1.0 |
| `min_sand` / `min_saltglass` | Sand / Saltglass | Coast | Hoe | EA |

**Gems:**

| Gem | Element | Where | Milestone |
|---|---|---|---|
| Quartz | — | Common | VS |
| Emerald | Terra | Cellars, Rootdeep | VS |
| Amber | — | Rootdeep | EA |
| Aquamarine | Aqua | Drowned Bells | EA |
| Jade | Zephyr | Rootdeep, Starfall | EA |
| Pearl | — | Coast | EA |
| Sunstone | Lumen | Drowned Bells, Starfall | EA |
| Onyx | Umbra | Rootdeep, Halcyon Below | EA |
| Ruby | Ignis | Forgeheart | 1.0 |
| Moonstone | — | Starfall | 1.0 |
| Star Diamond | — | Halcyon Below (very rare) | 1.0 |

**Geodes:** Veil Geode (VS) · Magma Geode (1.0) · Frost Geode (1.0), cracked at the Smithy.

---

## 6. Materials & processing

| Material | Made from | Station | Milestone |
|---|---|---|---|
| Wood / Hardwood / Sap / Fiber | Trees, stumps, weeds | — | VS |
| Plank | 2 Wood | Workbench (1 at a time) / Sawmill (bulk) | VS |
| Copper / Iron / Silver / Emberite / Starmetal Bar | 5 Ore + 1 Coal | **Smelter** | VS → 1.0 |
| **Sunsteel Bar** | Starmetal Bar + Heartflame Ember | Great Forge | 1.0 |
| Charcoal | 5 Wood | Kiln | EA |
| Brick | 2 Clay | Kiln | EA |
| Glass | Sand | Kiln | EA |
| Rope | 3 Fiber | Pocket | VS |
| Cloth / Silk Cloth / Thick Cloth | Cloud Wool / Silk / Mammoth Wool | Loom | EA / EA / 1.0 |
| **Glow Oil** | Glimmer Dust + Sap | Workbench | VS |
| **Lumen Essence** | Sunfruit | Preserves Jar | EA |
| **Chilling Essence** | Icebloom | Preserves Jar | 1.0 |
| **Veil Essence** | 3 Veilglass | Enchanting Table | EA |
| Dye (by colour) | Flowers | Dye Pot | EA |
| Brass Gear | Copper Bar + Quartz | Workshop | EA |
| Whetstone | Stone + Quartz | Workbench | EA |

### Creature materials (VS list)

| Species | Common drop | Rare drop |
|---|---|---|
| Mossbun | Moss Fluff | Verdant Heart (catalyst) |
| Puddlepup | Clear Droplet | Tide Pearl |
| Emberkit | Ember Fur | Ember Heart (catalyst) |
| Cloudfleece | Cloud Wool | Nimbus Tuft |
| Cluckatrice | Egg | Stone Egg (geode-like) |
| Glimmoth | Glimmer Dust | Aurora Silk |
| Mandragling | Mandrake Leaf | Screaming Root |
| Duskwolf | Dusk Fang | Moonless Fang |
| Jellop | Gel | Royal Jelly |
| Pebblet | Pebble Core | Granite Heart |
| Wickling | Wax Drop | Eternal Wick |
| Gnawrat | Old Coin | Rat Crown |

Every species has 1 common + 1 rare material: **76 creature materials at 1.0**.

---

## 7. Artisan goods (processing chains, ≤3 steps)

| Station | Input → Output | Milestone |
|---|---|---|
| **Mill** | Wheat → Flour · Corn → Cornmeal | EA |
| **Oven** (Tavern / Kitchen) | Flour → Bread | EA |
| **Preserves Jar** | Fruit → Jam · Vegetable → Pickles · Sunfruit → Lumen Essence | EA |
| **Keg** | Fruit → Wine · Wheat → Ale · Honey → Mead · Vegetable → Juice · Tea Leaves → Black Tea · Emberbean → Coffee | EA |
| **Churn / Cheese Press** | Milk → Butter / Cheese | EA |
| **Loom** | Wool / Silk → Cloth / Silk Cloth | EA |
| **Beehive** | → Honey (flavoured by nearby flowers: *Blossom*, *Wildflower*) | EA |
| **Smoker** | Fish + Charcoal → Smoked Fish | EA |
| **Brewery** (Hilde) | Golden Hops + Wheat → **Stonebrew Ale** (premium) | 1.0 |

---

## 8. Cooking recipes (26)

| # | Dish | Ingredients | Satiety | Buff | Source | Milestone |
|---|---|---|---|---|---|---|
| 1 | Roasted Turnip | Turnip | 20 | Energy +15 | Start | VS |
| 2 | Forager's Skewer | Any 2 forage | 25 | Energy +20 | Start | VS |
| 3 | Baked Potato | Potato | 30 | Energy +25 | Bram (recruit) | VS |
| 4 | **Vegetable Stew** | Carrot + Potato + Cabbage | 60 | **Warmth** 3h | Windmill Ruin scroll | VS |
| 5 | Herb Tea *(drink)* | Healing Herb + Wild Mint | — | HP +30, Exposure gain −20% 2h | Linnea | VS |
| 6 | Fried Egg | Egg | 25 | Energy +30 | Start | VS |
| 7 | Farmer's Omelette | Egg + Cabbage + Wild Leek | 45 | Green Thumb 3h | Mira | VS |
| 8 | Dawnbell Tea *(drink)* | Dawnbell | — | Swift 2h | Flicker | VS |
| 9 | Mushroom Soup | Morel or Chanterelle + Wild Leek | 45 | Miner's Grit 3h | Fen | EA |
| 10 | Pancakes | Flour + Egg + Milk | 50 | Lucky 4h | Tavern | EA |
| 11 | Fish Stew | Any fish + Potato + Carrot | 65 | Guard 4h | Orin | EA |
| 12 | Grilled Fish | Any fish | 35 | Might 2h | Fishing 2 | EA |
| 13 | Smoked Fish | Smoker product | 40 | Well-Fed | Smoker | EA |
| 14 | Strawberry Shortcake | Strawberry + Flour + Egg + Milk | 55 | Kindred 4h | Tamsin 4♥ | EA |
| 15 | Carrot Cake | Carrot + Flour + Egg | 50 | Kindred 3h | Juniper | EA |
| 16 | Blueberry Muffin | Blueberry + Flour + Butter | 45 | Lucky 3h | Tavern | EA |
| 17 | Tomato Soup | 2 Tomato + Butter | 50 | Well-Fed | Tavern | EA |
| 18 | Pumpkin Pie | Pumpkin + Flour + Egg + Milk | 70 | Lucky 6h | Harvest Court | EA |
| 19 | Apple Pie | Apple + Flour + Butter | 60 | Lucky 4h | Rook 6♥ | EA |
| 20 | Honey Tea *(drink)* | Honey + Tea Leaves | — | Energy regen 3h | Linnea 4♥ | EA |
| 21 | Seaweed Tea *(drink)* | Seaweed + Tea Leaves | — | Guard 2h | Orin | EA |
| 22 | Sunfruit Sorbet | Sunfruit + Milk + Honey | 40 | HP +80, Veil-rot immunity 2h | Nix | EA |
| 23 | **Spicy Curry** | Emberroot + Rice + Carrot | 70 | **Warmth 6h** + Might | Kaida | 1.0 |
| 24 | Mushroom Pie | Mushroom + Flour + Butter | 65 | Miner's Grit 6h | Durgan | 1.0 |
| 25 | Frostkale Hotpot | Frostkale + Winter Radish + any fish | 70 | Warmth 6h | Saga | 1.0 |
| 26 | **Royal Feast** | 6 dishes | 100 | Party-wide: all buffs 6h | Palace kitchen | 1.0 |

**Crafted gift and creature items:** Creature Treat (Carrot + Clover), Bond Snack (Honey + Moss Fluff), Plush Mossbun (Moss Fluff + Cloth), Wooden Figurine (Hardwood), Handmade Scarf (Cloth + Dye), Crow-Feather Charm (found in the Cellars / sold by Mira).

---

## 9. Tools

| Tool | Crude | Copper | Iron | Silver | Starmetal | Notes |
|---|---|---|---|---|---|---|
| **Hoe** | 1 tile | 1×3 | 1×5 | 3×3 | 5×5 | Charge for area |
| **Watering Can** (capacity) | 30 | 50 | 70 | 90 | 120 | Same charge areas as the hoe |
| **Axe** (power) | 1 | 2 | 3 (Hardwood) | 4 (Veil Trees) | 5 | |
| **Pickaxe** (power) | 1 | 2 | 3 | 4 | 5 | Each dungeon's ore needs the previous tier |
| **Sickle** | 1 tile | 3 tiles | 3 tiles + quality | 5 tiles | 5 tiles + quality | |
| **Lantern** | Tin Lantern | Brass | Silver | — | **Heartflame Lantern** (no fuel) | Fuel: Glow Oil |
| **Fishing Rod** (EA) | Bamboo | Copper | — | Silver | Starmetal | |
| **Hammer** | — | — | — | — | — | Build mode; no tiers |

**Upgrade cost (Smithy):** Copper 5 bars + 500g (1 day) · Iron 5 bars + 2,000g (1 day) · Silver 5 bars + 5,000g (1 day) · Starmetal 5 bars + 15,000g (2 days, **Great Forge** only).

---

## 10. Weapons

| Type | T0 Crude | T1 Copper | T2 Iron | T3 Silver | T4 Emberite | T5 Starmetal | Milestone |
|---|---|---|---|---|---|---|---|
| Sword & Buckler | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | VS (T0–T1) |
| Spear | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | VS (T0–T1) |
| Greatsword | — | ✔ | ✔ | ✔ | ✔ | ✔ | EA |
| Twin Daggers | — | ✔ | ✔ | ✔ | ✔ | ✔ | EA |
| Bow | — | ✔ | ✔ | ✔ | ✔ | ✔ | EA |
| Catalyst | — | ✔ | ✔ | ✔ | ✔ | ✔ | EA |

- Tiers 0–3 are forged at the **Smithy** (Tamsin); tiers 4–5 at the **Great Forge** (Durgan).
- **Legendary line:** Sunblade (Ch4) → Sunblade, Awakened → **Sunblade of Halcyon** (Ch6).
- Weapons can be **enchanted** with one element at the Enchanter's Spire (Nix).
- **Count:** 32 standard weapons + 3 Sunblade stages = **35** at 1.0.

---

## 11. Armour & trinkets

- **Slots:** Body armour · Boots · 2 Trinkets. Clothing is cosmetic (Wardrobe).
- **Body armour:** light and heavy lines × 6 tiers = 12. **Boots:** 6 tiers. **Special sets:** 6 (e.g. the Crowfeather set, the Rose Plate set).
- **Trinkets (30 at 1.0; 6 in VS):** e.g. *Moss Ring* (HP regen), *Crow-Feather Charm* (+crit), *Ember Charm* (Burn on hit), *Lantern Pin* (Exposure −15%), *Beastcaller Bell* (+familiar ATK), *Miner's Band* (+ore).

---

## 12. Pact Sigils & creature items

| ID | Item | Pact multiplier | Recipe | Milestone |
|---|---|---|---|---|
| `sig_twine` | Twine Sigil | ×1.0 | 3 Fiber + 1 Veilglass | VS |
| `sig_copper` | Copper Sigil | ×1.3 | Copper Bar + 1 Veilglass | VS |
| `sig_silver` | Silver Sigil | ×1.6 | Silver Bar + 2 Veilglass | EA |
| `sig_starmetal` | Starmetal Sigil | ×2.0 | Starmetal Bar + 3 Veil Essence | 1.0 |
| `sig_crown` | **Crown Sigil** | Guaranteed (not Guardians) | Rare reward only | EA |
| `sig_treat` | Creature Treat | Offering +25% | Carrot + Clover | VS |
| `sig_bond_snack` | Bond Snack | +Bond | Honey + Moss Fluff | EA |
| `sig_catalysts` | True Ascension catalysts (17) | — | See [05 §3](05_BESTIARY.md#3-true-ascension-forms-17) | VS → 1.0 |

---

## 13. Consumables

| Item | Effect | Milestone |
|---|---|---|
| Healing Salve | HP +40 | VS |
| Energy Tonic | Energy +40 | VS |
| Torch | Light for 2 in-game hours (small radius) | VS |
| Campfire Kit | Place a one-night safe bubble (radius 4) | VS |
| **Waystone Charm** | Warp from a dungeon to its entrance | VS |
| Beacon Charm | Warp home to the Throne | EA |
| Warm Brew | Warmth 4h | EA |
| Cleansing Draught | Cures Veil-rot | EA |
| Smoke Bomb | Escape combat (not bosses) | EA |
| Potions (Hollis) | Advanced buffs (+50% with his Knight perk) | 1.0 |

---

## 14. Fish (20)

| Location | Fish | Legendary | Milestone |
|---|---|---|---|
| Dawnmere river & pond | Sunperch, River Carp, Mossback Trout, Moonminnow (night) | **Glassback Carp** (Orin's quest) | EA |
| Whisperwood streams | Fernfin, Shadow Loach (night) | — | EA |
| Saltglass Coast | Saltglass Snapper, Bell Eel, Tidefin Tuna, Reef Grouper | **Stormscale Marlin** | EA |
| Sunken Cellars pools | Cave Blindfish | — | EA |
| Cinderpeak hot springs | Ember Koi, Obsidian Catfish | **Ember Emperor** | 1.0 |
| Frostveil lakes | Ice Pike, Frostfin Char | **Aurora Salmon** | 1.0 |
| Halcyon Below | — | **Veil Angler** | 1.0 |

Counts: EA **13** · 1.0 **20** (5 legendary). Trash catches: Soggy Boot, Driftwood, Broken Sigil.

---

## 15. Key items & collectibles

| Item | Purpose | Count |
|---|---|---|
| **Regalia**: Signet, Scepter, Orb, Sunblade, Mantle, Crown | Story powers (see [02 §7](02_STORY_AND_WORLD.md#7-the-regalia)) | 6 |
| **Memory Fragments** | Lore; Archive donations → Lore | 30 |
| **Crown Embers** | +10 max Energy or HP each | 10 |
| Kingdom Charter | Received at the Founding | 1 |
| Blossom Brooch | Start dating (8♥) | Craftable |
| Consort's Ring | Proposal (10♥): Silver Bar + Pearl + Heartflame Ember | Craftable |
| Heartflame Ember | Rare catalyst (TA Phoenix, Sunsteel, Consort's Ring) | Rare |
| Royal Seal | The Ch3 reveal | 1 |
| Old Letters | Caelan's backstory | 6 |
| Dungeon Keys | Vault floors | Per dungeon |
| Ancient Tome, Poetry Book, Golden Lute String, Exotic Spice, Bittersweet Chocolate, Spiced Rum | Gifts (Market, trade routes, dungeons) | — |

---

## 16. Universal gift tastes

| Taste | Items |
|---|---|
| **Universal loves** | Royal Feast, Star Diamond, Starmelon |
| **Universal likes** | Most cooked dishes, gems, flowers, honey |
| **Neutral** | Most raw crops, eggs, milk |
| **Dislikes** | Raw ore, stone, fiber, clay |
| **Hates** | Gel, Soggy Boot, Driftwood |

Individual tastes are in the cast bible ([`04_CHARACTERS.md`](04_CHARACTERS.md)).

---

## 17. Totals

| Category | VS | EA | 1.0 |
|---|---|---|---|
| Crops (+ Veil Seeds) | 6 | 25 (+1) | 29 (+3) |
| Fruit trees + perennials | 0 | 5 | 8 |
| Recipes | 8 | 22 | 26 |
| Fish | 0 | 13 | 20 |
| Standard weapons (+ Sunblade stages) | 4 | 20 | 32 (+3) |
| Tools (all tiers) | 12 | 27 | 34 |
| Trinkets | 6 | 18 | 30 |
| Creature materials | 24 | 54 | 76 |
