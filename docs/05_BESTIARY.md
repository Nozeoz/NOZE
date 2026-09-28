# 05 — Bestiary (Veilkin, Guardians & Enemies)

> **TL;DR:** **38 Veilkin species** (12 in the Vertical Slice), **5 Guardians** (dungeon bosses, pactable post-game), and **17 True Ascension** forms: **60 creature forms** at 1.0. Every species has an element, a Pact method, work skills, a combat role, and a clear silhouette. The Hollowed are corrupted variants made with a shader and VFX, not new sprites.

---

## 1. Creature design rules

| Element | Shape language | Palette | Icon shape (colour-blind safe) |
|---|---|---|---|
| **Terra** | Round, blocky, mossy, heavy | Greens, browns, stone grey | ■ square |
| **Aqua** | Droplets, curves, bubbles, fins | Blues, teals, foam white | ● circle |
| **Ignis** | Sharp flame tips, embers, spikes | Reds, oranges, ember yellow | ▲ triangle |
| **Zephyr** | Feathers, swirls, floaty, light | White, mint, sky | ◆ diamond |
| **Lumen** | Stars, halos, glow, symmetry | Gold, cream, soft white | ★ star |
| **Umbra** | Crescents, points, big eyes, wispy | Indigo, violet, black | ☾ crescent |
| *Veil (Hollowed)* | Cracks, hollow white eyes, trailing mist | Desaturated + violet-teal glow | ✖ cracked circle |

1. **Cute-to-cool ratio:** base forms are ~70% cute and 30% cool. True Ascension forms flip to ~40/60.
2. **One read at thumbnail size:** each species has one dominant feature (Mossbun's moss ears, Emberkit's ember tail).
3. **No real-animal copies:** always add a fantasy twist (element, material, behaviour).
4. **Size classes** (on-screen at 1080p): **S** ~48–80 px · **M** ~96–128 px · **L** ~160–200 px · **Boss** 300–700 px (see [08 §4](08_ART_DIRECTION.md#4-resolution--scale)).
5. **Defeated creatures dissolve into mist** and drop *materials* (fluff, gel, shells, essence), never meat or corpses.

---

## 2. Veilkin species

Columns: **Pact** = Subdue / Offering (favourite item) / Challenge / Hatch · **Work** = work skills with level (1–3) · **TA** = True Ascension form.

### 2.1 Dawnmere Vale (overworld)

| ID | Name | Element | Size | Rarity | Pact | Work | Yield / drops | Combat role | TA form | Milestone |
|---|---|---|---|---|---|---|---|---|---|---|
| `cre_mossbun` | **Mossbun**, a rabbit with moss for ears | Terra | S | Common | Offering (Carrot) | Tending 1, Foraging 1 | Moss Fluff (weekly) | Support (Moss Mend heal-over-time) | **Grovehare** | VS |
| `cre_puddlepup` | **Puddlepup**, a round water puppy with a bubble tail | Aqua | S | Common | Subdue | Watering 2 | Clear Droplet | Ranged (water spit) | **Tidehound** | VS |
| `cre_emberkit` | **Emberkit**, a fox kit with a smouldering tail | Ignis | S | Common | Subdue | Kindling 2, Guarding 1 | Ember Fur | Striker | **Blazetail** | VS |
| `cre_cloudfleece` | **Cloudfleece**, a sheep that floats a few inches off the ground | Zephyr | M | Common | Offering (Clover) | Hauling 1 | **Cloud Wool** (every 3 days) | Support (wind shield) | Nimbusram *(post-1.0)* | VS |
| `cre_cluckatrice` | **Cluckatrice**, a baby cockatrice hen | Terra | S | Common | Offering (Grain) | Foraging 1 | **Eggs** (daily) | Control (petrifying glare = stun) | — | VS |
| `cre_glimmoth` | **Glimmoth**, a glowing moth drawn to lights at night | Lumen | S | Uncommon | Offering (Nectar), night only | Lighting 2 | Glimmer Dust (→ Glow Oil) | Support (dazzle) | **Aurormoth** | VS |
| `cre_mandragling` | **Mandragling**, a mandrake that screams when startled | Terra | S | Uncommon | **Hatch**: 5% of Mandrake Root harvests | Tending 2 | Mandrake Leaf | Control (scream stun) | Mandragora *(post-1.0)* | VS |
| `cre_duskwolf` | **Duskwolf**, a shadow-furred pack wolf that hunts at night | Umbra | M | Common (night) | Subdue | Guarding 2 | Dusk Fang | Striker (pack tactics) | **Nightfang** | VS |
| `cre_creamhorn` | **Creamhorn**, a gentle bison-cow with a bell | Terra | M | Common | Offering (Hay) | Hauling 2 | **Milk** (daily) | Tank | — | EA |

### 2.2 Sunken Cellars (dungeon 1)

| ID | Name | Element | Size | Rarity | Pact | Work | Yield / drops | Combat role | TA form | Milestone |
|---|---|---|---|---|---|---|---|---|---|---|
| `cre_jellop` | **Jellop**, a wobbly slime | Aqua | S | Common | Subdue | Hauling 1, Watering 1 | Gel | Tank | — | VS |
| `cre_pebblet` | **Pebblet**, a pebble golem child | Terra | S | Common | Subdue | Mining 2, Hauling 1 | Pebble Core | Tank | **Cragguard** | VS |
| `cre_wickling` | **Wickling**, a living candle-wisp | Ignis | S | Uncommon | Subdue | Kindling 1, Lighting 1 | Wax Drop | Caster (fire bolts) | Lanternwraith *(post-1.0)* | VS |
| `cre_gnawrat` | **Gnawrat**, a sneaky rat hugging a stolen coin | Umbra | S | Common | Offering (Cheese) | Hauling 2, Foraging 1 | Old Coin | Rogue (steals items!) | — | VS |
| `cre_chompkin` | **Chompkin**, a mimic treasure chest | Terra | M | Rare | **Challenge** (Mimic Guess) | Hauling 3, Guarding 1 | Mimic Tongue | Tank | **Vaultmaw** | EA |

### 2.3 Whisperwood & Rootdeep Labyrinth

| ID | Name | Element | Size | Rarity | Pact | Work | Yield / drops | Combat role | TA form | Milestone |
|---|---|---|---|---|---|---|---|---|---|---|
| `cre_capling` | **Capling**, a mushroom sprite | Terra | S | Common | Offering (Compost) | Tending 1, Healing 1 | Spore Cap | Support (healing spores) | Myconid Sage *(post-1.0)* | EA |
| `cre_bramblehog` | **Bramblehog**, a thorn-backed boar | Terra | M | Common | Subdue | Logging 2 | Thorn Bristle | Charger | **Thornbeast** (mount at 1.0) | EA |
| `cre_breezling` | **Breezling**, a mischievous sylph | Zephyr | S | Uncommon | **Challenge** (race) | Hauling 2, Foraging 2 | Sylph Feather | Evasive striker | Galesylph *(post-1.0)* | EA |
| `cre_hootsage` | **Hootsage**, a spectacled scholar owl | Zephyr | S | Uncommon | Offering (Ancient Page) | Crafting 1 | Wise Feather | Caster (wind blades) | **Archowl** | EA |
| `cre_silkspinner` | **Silkspinner**, a fluffy (cute!) spider | Umbra | S | Uncommon | Subdue | Crafting 2 | **Silk** (every 2 days) | Control (webs) | Weaver Queen *(post-1.0)* | EA |
| `cre_moondeer` | **Moondeer**, a glowing deer seen on full moons | Lumen | M | Rare | **Challenge** (stealth approach) | Lighting 1, Healing 2 | Moonlit Antler | Healer | **Stellar Stag** | EA |
| `cre_timberbeetle` | **Timberbeetle**, a huge-horned beetle | Terra | M | Uncommon | Subdue | Logging 3, Hauling 1 | Beetle Shell | Tank / charger | — | EA |

### 2.4 Saltglass Coast & Drowned Bells

| ID | Name | Element | Size | Rarity | Pact | Work | Yield / drops | Combat role | TA form | Milestone |
|---|---|---|---|---|---|---|---|---|---|---|
| `cre_shellsnip` | **Shellsnip**, a glass-shelled crab | Aqua | S | Common | Subdue | Mining 1, Guarding 1 | Saltglass Shell | Tank | **Tidefortress** | EA |
| `cre_driftotter` | **Driftotter**, a playful otter | Aqua | S | Common | Offering (Clam) | Watering 2, Foraging 1 | Otter Whisker | Striker | — | EA |
| `cre_squallgull` | **Squallgull**, a storm seagull that delivers mail | Zephyr | S | Common | Subdue | Hauling 2 | Storm Feather | Ranged (dive) | Stormalbatross *(post-1.0)* | EA |
| `cre_lumenjelly` | **Lumenjelly**, a floating glowing jellyfish | Lumen | S | Uncommon | Offering (Plankton) | Lighting 2 | Glow Jelly | Support (dazzle pulse) | — | EA |
| `cre_bubbleseal` | **Bubbleseal**, a seal pup that blows cold bubbles | Aqua | M | Uncommon | Offering (Fish) | Chilling 2 | Frost Bubble | Control (slow) | — | EA |
| `cre_tollhermit` | **Tollhermit**, a hermit crab living in a small bell | Terra | S | Uncommon | Subdue | Guarding 2 (alarm!) | Bell Fragment | Tank (bell stun) | — | EA |

### 2.5 Cinderpeak Highlands & the Forgeheart

| ID | Name | Element | Size | Rarity | Pact | Work | Yield / drops | Combat role | TA form | Milestone |
|---|---|---|---|---|---|---|---|---|---|---|
| `cre_cinderling` | **Cinderling**, a magma salamander | Ignis | S | Common | Subdue | Kindling 3 | Cinder Scale | Striker (burn) | **Magmalisk** | 1.0 |
| `cre_emberhorn` | **Emberhorn**, a goat with glowing horns | Ignis | M | Common | Subdue | Mining 2 | Warm Milk | Charger | **Volcanic Ram** (mount) | 1.0 |
| `cre_forgeling` | **Forgeling**, an anvil-bodied golem child | Terra | M | Uncommon | **Challenge** (crafting test) | Crafting 3, Mining 1 | Iron Heart | Tank | Anvil Colossus *(post-1.0)* | 1.0 |
| `cre_ashbat` | **Ashbat**, a sooty cave bat | Umbra | S | Common | Subdue | Hauling 1 | Soot Wing | Swarm | — | 1.0 |
| `cre_cindercheep` | **Cindercheep**, a phoenix chick | Ignis | S | Rare | **Hatch** (lava-nest egg) | Kindling 2, Healing 1 | Phoenix Down | Support (revive once) | **Phoenix** | 1.0 |

### 2.6 Frostveil Reaches & Starfall Spire

| ID | Name | Element | Size | Rarity | Pact | Work | Yield / drops | Combat role | TA form | Milestone |
|---|---|---|---|---|---|---|---|---|---|---|
| `cre_glacimew` | **Glacimew**, an ice-furred cat | Aqua | S | Common | Offering (Fish) | Chilling 2 | Frost Whisker | Striker | **Auroralynx** | 1.0 |
| `cre_mammoss` | **Mammoss**, a moss-covered mammoth calf | Terra | L | Uncommon | Offering (Hay) | Hauling 3, Logging 1 | Mammoth Wool | Tank | **Glacier Titan** (mount) | 1.0 |
| `cre_chillpip` | **Chillpip**, a penguin chick | Aqua | S | Common | Subdue | Chilling 1, Watering 1 | Snow Feather | Ranged (ice pebbles) | — | 1.0 |
| `cre_starlit` | **Starlit**, a star-shaped sky spirit | Lumen | S | Rare | **Challenge** (trace a constellation) | Lighting 3 | Stardust | Caster (star bolts) | **Constella** | 1.0 |
| `cre_nyxcat` | **Nyxcat**, a shadow cat that follows you home at night | Umbra | S | Uncommon | Offering (Fish), night only | Guarding 2 (night bonus) | Shadow Tuft | Rogue | — | 1.0 |

### 2.7 Halcyon Below

| ID | Name | Element | Size | Rarity | Pact | Work | Yield / drops | Combat role | TA form | Milestone |
|---|---|---|---|---|---|---|---|---|---|---|
| `cre_knightling` | **Knightling**, a tiny suit of Halcyon armour animated by old loyalty | Lumen | S | Rare | **Challenge** (duel of honour) | Guarding 3 | Royal Rivet | Tank (taunt) | — | 1.0 |

### 2.8 Counts

| Milestone | Species (cumulative) | Notes |
|---|---|---|
| **VS** | **12** | Mossbun, Puddlepup, Emberkit, Cloudfleece, Cluckatrice, Glimmoth, Mandragling, Duskwolf, Jellop, Pebblet, Wickling, Gnawrat |
| **EA** | **27** | + Creamhorn, Chompkin, 7 Whisperwood/Rootdeep, 6 Saltglass/Drowned Bells |
| **1.0** | **38** | + 5 Cinderpeak, 5 Frostveil, 1 Halcyon Below |

### 2.9 Ambient life: Wisplings

Inspired by the tiny white critters in the creative lead's forest reference (our own design, not a copy).

| | |
|---|---|
| What | **Wisplings**: palm-sized white spirit-bunnies with a faint glow. Harmless, curious, a little shy |
| Pactable? | **No.** Ambient life, not a familiar |
| Behaviour | Gather where the Realm is peaceful; follow Flicker around; hide in grass when you run; scatter when the Hollowed appear |
| **System link** | Their **number in town mirrors average happiness**: a living, glanceable health bar for the kingdom. At high Prosperity they sometimes leave a small gift (forage, a flower) at your door in the morning |
| Asset | One small frame-by-frame set (idle, hop, hide, sleep, carry-gift) with 3 variants |
| Milestone | VS |

Other ambient life (no gameplay role): dragonflies, butterflies, fish shadows, songbirds, deer herds.

---

## 3. True Ascension forms (17)

A **Named** familiar plus a regional **catalyst** evolves into its True Ascension form (new sprite, new skill, higher work level).

| # | Base → True Ascension | Catalyst | Milestone |
|---|---|---|---|
| 1 | Mossbun → **Grovehare** (antlered, flower-crowned hare) | Verdant Heart (Sunken Cellars) | VS |
| 2 | Emberkit → **Blazetail** (three-tailed fire fox) | Ember Heart (Sunken Cellars) | VS |
| 3 | Puddlepup → **Tidehound** | Tide Pearl | EA |
| 4 | Pebblet → **Cragguard** | Granite Heart | EA |
| 5 | Glimmoth → **Aurormoth** | Aurora Silk | EA |
| 6 | Duskwolf → **Nightfang** | Moonless Fang | EA |
| 7 | Chompkin → **Vaultmaw** | Royal Lockpick | EA |
| 8 | Bramblehog → **Thornbeast** (rideable once the Hunter's Lodge exists, 1.0) | Elder Thorn | EA |
| 9 | Hootsage → **Archowl** | Lost Codex | 1.0 |
| 10 | Moondeer → **Stellar Stag** | Moonstone | 1.0 |
| 11 | Shellsnip → **Tidefortress** | Bell Bronze | 1.0 |
| 12 | Cinderling → **Magmalisk** | Magma Core | 1.0 |
| 13 | Emberhorn → **Volcanic Ram** (rideable) | Obsidian Horn | 1.0 |
| 14 | Cindercheep → **Phoenix** | Heartflame Ember | 1.0 |
| 15 | Glacimew → **Auroralynx** | Aurora Shard | 1.0 |
| 16 | Mammoss → **Glacier Titan** (rideable) | Glacier Heart | 1.0 |
| 17 | Starlit → **Constella** | Fallen Star | 1.0 |

Cumulative: **VS 2 · EA 8 · 1.0 17**. Forms marked *(post-1.0)* in §2 (Nimbusram, Mandragora, Lanternwraith, Myconid Sage, Galesylph, Weaver Queen, Stormalbatross, Anvil Colossus) are **reserved for post-1.0 updates**.

---

## 4. Guardians (dungeon bosses)

Great Veilkin bound to guard the Regalia, corrupted by the Hunger. Defeat → purify → the Regalia is recovered. Post-game, each can be pacted through a **Legend Trial**.

| ID | Guardian | Element | Dungeon | Fight concept | Phases | Regalia | Milestone |
|---|---|---|---|---|---|---|---|
| `boss_ruinback` | **Ruinback**, a colossal turtle carrying a ruined watchtower on its shell | Terra | Sunken Cellars | Arena of pillars. Shell slams send shockwaves; Hollowed spawn from the tower. Break 3 Veil crystals on the shell to expose its Veil Core. Teaches reading telegraphs and Purify. | 2 | Signet | VS |
| `boss_mycel` | **Mother Mycel**, a fungal matriarch rooted in the library | Umbra | Rootdeep Labyrinth | Spore clouds (Fear), root cages, clones in darkness. Use light sources to reveal the real one. | 3 | Scepter | EA |
| `boss_tidetoll` | **Tidetoll**, a bell-leviathan whale | Aqua | Drowned Bells | The arena floods and drains; bell tolls stun. Ring the cathedral bells in counter-rhythm to break its song. | 3 | Orb | EA |
| `boss_vulkarn` | **Vulkarn**, the Forge Wyrm | Ignis | The Forgeheart | Lava rises; hide behind forged shields; quench its armour with Aqua attacks. | 3 | Sunblade | 1.0 |
| `boss_astraea` | **Astraea**, the Star-Eyed, a celestial owl-sphinx | Zephyr | Starfall Spire | Gravity flips (the tower is upside down); starfall zones; wind currents. | 3 | Mantle | 1.0 |

**Story bosses (humans & finale):**

| ID | Boss | Chapter | Concept | Outcome |
|---|---|---|---|---|
| `boss_rook` | Rook, Crowfeather duel | 1 | 1v1 dagger duel; teaches parry and dodge | Spare → recruit |
| `boss_nix` | Nix, the Unsung | 2 | Shadow teleports, sigil traps | Spare → recruit |
| `boss_ingrid` | Commander Ingrid Valk | 4 | Shield wall, lance charges, commands soldiers | Spare → recruit |
| `boss_vesper` | Choirmaster Vesper | 5 | Hymn-based bullet patterns, Hollowed choir | Spare → redemption |
| `boss_warden` | The Ashen Warden (Lucan) | 6 | Mirror of the prologue: uses your old Royal Arts | Purify → recruit |
| `boss_maw` | The Maw Below | 6 | Multi-stage finale; in Ending B your whole realm joins the fight | Ending |

---

## 5. The Hollowed (corrupted variants)

- **Any species can appear Hollowed.** No new sprite: a **Veil shader** (desaturate + violet-teal rim light + white hollow eyes) plus a trailing-mist **VFX**.
- Stats: +50% HP, +20% ATK, more aggressive. Attacks inflict **Veil-rot**.
- At ≤25% HP a cracked **Veil Core** appears. Purify it → it becomes a normal Veilkin with Pact chance +50%.
- **Hollowed Alphas** (bounties, Tor): a bigger scale (×1.5), one unique attack, rare drops.

---

## 6. Human enemies

| Faction | Enemy | Archetype | Milestone |
|---|---|---|---|
| Crowfeather Gang | Cutpurse | Fast melee, steals gold | VS |
| | Brute | Tank, club slam | VS |
| | Slinger | Ranged | VS |
| Pale Choir | Acolyte | Caster (Umbra bolts) | EA |
| | Chanter | Support: buffs the Hollowed with hymns | EA |
| | Silent Blade | Ambusher (invisible until close) | EA |
| Aldmark Dominion | Soldier | Sword & shield | EA |
| | Crossbowman | Ranged, volley | EA |
| | Warden Engine | Veilglass-powered construct, tank | 1.0 |

Spared human enemies can become **settlers** (see [03 §13.5](03_GAMEPLAY_SYSTEMS.md#135-mercy)).

---

## 7. Totals (sprite sets to produce)

| | VS | EA | 1.0 |
|---|---|---|---|
| Veilkin species | 12 | 27 | 38 |
| True Ascension forms | 2 | 8 | 17 |
| Guardians | 1 | 3 | 5 |
| **Creature forms total** | **15** | **38** | **60** |
| Story bosses (humans, finale) | 1 | 2 | 6 |
| Human enemy types | 3 | 8 | 9 |
