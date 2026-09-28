# 09 — Audio Direction

> **TL;DR:** Warm folk-fantasy with a JRPG melodic heart. The town theme is **adaptive**: it gains instruments as your kingdom grows. The Veil has its own sound (whispers, detuned pads, a tritone motif). No full voice acting; each character gets **voice blips**. **48 music tracks + 11 jingles** at 1.0 (14 in the VS), ~550 SFX, ~30 ambience loops.

---

## 1. Audio pillars

| Pillar | Meaning |
|---|---|
| **Warm & Wistful** | Acoustic, human, a little nostalgic. Every melody should be hummable. |
| **The Kingdom Grows** | Music and ambience audibly get richer as the realm grows (the Suikoden lesson). |
| **The Veil Whispers** | The unknown has a sound: whispers, low drones, detuned textures. You *hear* Exposure rising. |
| **Juicy Feedback** | Every tool, hit, harvest, and pact has a crisp, satisfying sound with variation. |

---

## 2. Musical identity

**Core palette:** acoustic guitar, tin whistle and flute, harp, fiddle, accordion, cello, soft strings, light hand percussion, music box. Brass and choir only at the city/kingdom stage and in epic moments.

| Region | Signature colour |
|---|---|
| Dawnmere Vale | Guitar + whistle, pastoral |
| Whisperwood | Harp, marimba, woodwinds, playful fae rhythms |
| Saltglass Coast | Accordion, concertina, shanty rhythms, steel-string guitar |
| Cinderpeak | Low brass, anvil percussion, dwarven male chorus |
| Frostveil | Glass harmonica, celesta, sparse piano, throat-sung drone |
| The Hollow Crown | Broken court music: detuned harpsichord, reversed strings |

### Leitmotifs

| Motif | Heard in | Character |
|---|---|---|
| **The Sovereign's Theme** | Title, key story beats | Noble, rising, bittersweet |
| **Flicker's Lullaby** | Flicker moments (music box) | The prologue's first sound; finally revealed as your past self's lullaby |
| **The Veil** | Night, dungeons, Hollowed | A descending tritone; detuned, whispering |
| **The Pale Choir** | Nix, Vesper, cultists | Wordless choir, beautiful and wrong |
| **The Halcyon Anthem** | Fragments throughout; **heard in full only in the true ending** | The kingdom's lost national anthem. Seren "rediscovers" it |

---

## 3. Adaptive music

1. **Town theme layering by Kingdom Rank.** One composition, six states. Each rank adds a stem: music box + whistle → + guitar → + fiddle and flute → + strings and percussion → + brass and choir → full orchestra with the Anthem motif.
2. **Day/night variants.** Night versions are sparser, with a music-box layer and more reverb.
3. **Veil proximity.** As Exposure rises, the current music is low-pass filtered and whisper ambience fades in.
4. **Dungeon intensity layer.** The exploration mix adds a percussion/combat stem when enemies engage, then fades back.
5. **Stingers** on key events (Pact success, Rank Up, rare loot) duck the music briefly.

---

## 4. Music track list

| # | ID | Title | Use | Milestone |
|---|---|---|---|---|
| 1 | `mus_title` | **Once a Sovereign** (Main Theme) | Title screen | VS |
| 2 | `mus_prologue` | The Last Decree | Prologue battle | VS |
| 3 | `mus_flicker` | Flicker's Lullaby | Flicker moments | VS |
| 4 | `mus_memory` | Memories of Halcyon | Memory Fragments | VS |
| 5 | `mus_founding` | The Founding | Naming the kingdom | VS |
| 6 | `mus_town` | **Hearth of the Realm** (adaptive, 6 states) | Town by day | VS (states 0–1) · EA (2–3) · 1.0 (4–5) |
| 7 | `mus_spring` | First Bloom | Overworld, Spring | VS |
| 8 | `mus_gloaming` | The Gloaming | Night outside the light | VS |
| 9 | `mus_dgn_cellars` | Sunken Cellars | Dungeon 1 | VS |
| 10 | `mus_battle` | Steel in the Mist | Overworld combat | VS |
| 11 | `mus_guardian` | Guardian of the Anchor | Guardian fights | VS |
| 12 | `mus_duel` | Rival's Challenge | Rook / Kaida / Ingrid duels; Sun Tourney | VS |
| 13 | `mus_shop` | Coin & Caravan | Mira, the Market | VS |
| 14 | `mus_fest_blossom` | Blossomfall | Festival | VS |
| 15 | `mus_town_night` | Lamplight | Town at night | EA |
| 16 | `mus_summer` | Sunlit Rows | Overworld, Summer | EA |
| 17 | `mus_autumn` | Amber Harvest | Overworld, Autumn | EA |
| 18 | `mus_winter` | Quiet Snow | Overworld, Winter | EA |
| 19 | `mus_whisperwood` | Whisperwood | Region 2 | EA |
| 20 | `mus_saltglass` | Saltglass Coast | Region 3 | EA |
| 21 | `mus_dgn_rootdeep` | Rootdeep Labyrinth | Dungeon 2 | EA |
| 22 | `mus_dgn_bells` | The Drowned Bells | Dungeon 3 | EA |
| 23 | `mus_choir` | Hymn of the Pale Choir | Nix and Vesper encounters | EA |
| 24 | `mus_tavern` | Last Call at the Tavern | Tavern | EA |
| 25 | `mus_court` | Audience at the Throne | Court Day | EA |
| 26 | `mus_heart` | Heartstrings | Romance heart events | EA |
| 27 | `mus_sad` | Embers of Memory | Emotional scenes | EA |
| 28 | `mus_comedy` | Flicker's Mischief | Comedy scenes; Beast Fair | EA |
| 29 | `mus_mystery` | Whispers | Mystery and investigation | EA |
| 30 | `mus_wedding` | Royal Wedding | Wedding | EA |
| 31 | `mus_fest_lantern` | Lantern Tide | Festival | EA |
| 32 | `mus_fest_harvest` | Harvest Court | Festival | EA |
| 33 | `mus_fest_hollow` | Hollow's Eve | Festival | EA |
| 34 | `mus_fest_hearth` | Hearthfire Night | Festival | EA |
| 35 | `mus_fest_starfall` | Starfall Vigil | Festival | EA |
| 36 | `mus_cinderpeak` | Cinderpeak Highlands | Region 4 | 1.0 |
| 37 | `mus_frostveil` | Frostveil Reaches | Region 5 | 1.0 |
| 38 | `mus_hollowcrown` | The Hollow Crown | Region 6 | 1.0 |
| 39 | `mus_dgn_forgeheart` | The Forgeheart | Dungeon 4 | 1.0 |
| 40 | `mus_dgn_starfall` | Starfall Spire | Dungeon 5 | 1.0 |
| 41 | `mus_dgn_halcyon` | Halcyon Below | Dungeon 6 | 1.0 |
| 42 | `mus_dgn_rift` | Veil Rift | Post-game | 1.0 |
| 43 | `mus_warden` | The Ashen Warden | Caelan boss (reprises the prologue) | 1.0 |
| 44 | `mus_truth` | What I Decreed | The Chapter 5 reveal | 1.0 |
| 45 | `mus_final` | The Maw Below | Finale (multi-phase) | 1.0 |
| 46 | `mus_end_dawn` | Halcyon Dawn | Ending B | 1.0 |
| 47 | `mus_end_flame` | The Eternal Flame | Ending A | 1.0 |
| 48 | `mus_end_hearth` | The Hearth Commonwealth | Ending C | 1.0 |

**Counts:** VS **14** · EA **35** · 1.0 **48**.

### Jingles (short stingers)
`jgl_pact_success` · `jgl_ascension` · `jgl_rank_up` · `jgl_level_up` · `jgl_quest_complete` · `jgl_day_start` · `jgl_pass_out` · `jgl_rare_item` · `jgl_victory` · `jgl_defeat` · `jgl_surge_warning` (EA). **VS 10 · EA/1.0 11.**

---

## 5. Sound effects

| Category | Contents | VS | 1.0 |
|---|---|---|---|
| Footsteps | 8 surfaces (grass, dirt, stone, wood, sand, snow, shallow water, tilled soil) × 4 variants | 20 | 32 |
| Tools | Till, pour, chop, tree fall, pick hit, rock/ore break, sickle, harvest pop, plant, hammer, lantern | 25 | 40 |
| Fishing | Cast, bite, reel loop, catch, line snap | — | 6 |
| Combat | Swings per weapon family, hits by material, parry, perfect-dodge time-slow, crit, block, charge, hurt, KO, arrows, catalyst bolts per element | 30 | 75 |
| Royal Arts | One signature sound each | 4 | 12 |
| Elements & statuses | Apply + tick for Burn, Soak, Root, Stagger, Dazzle, Fear, Veil-rot | 8 | 14 |
| Creatures | 3 vocalisations per species (idle/happy, attack, hurt/faint) + 8 per Guardian | 44 | 154 |
| Pact & Bond | Sigil throw, struggle, success, fail, Naming, Ascension, pet, feed | 8 | 10 |
| UI | Click, hover, open/close, tab, confirm, cancel, error, coin, item pickup (3 rarities), craft, quest, toast, level up, heart gain | 20 | 30 |
| Voice blips | Per character (pitch + timbre), see §7 | 10 sets | 32 sets |
| World one-shots | Doors, chests, gates, chapel bell, Beacon hum, construction done, rank-up bells, thunder, Veil whispers (6 variants) | 15 | 45 |
| Kingdom | Build place / cancel / demolish, construction loop, forge anvils, mill, market crowd | 6 | 20 |
| **Total (approx.)** | | **~150** | **~550** |

**Variation rules:** common sounds get 3–4 variants plus random pitch (±5%) and volume (±2 dB). No identical sound plays twice in a row.

---

## 6. Ambience loops

| Group | Loops | Milestone |
|---|---|---|
| Dawnmere Vale | Day (birds, river, breeze) · Night (crickets, Veil drone) | VS |
| Dungeons | One bed per dungeon (drips, echoes, embers, bells…) | VS → 1.0 |
| Interiors | Home, tavern, forge, chapel, archive | VS (home) → EA |
| Weather | Rain, storm, snow wind, fog | VS (rain) → EA |
| Town walla | 3 densities (hamlet / town / city) | VS (hamlet) → 1.0 |
| Other regions | Day + night for each | EA / 1.0 |

**Counts:** VS **6** · EA **18** · 1.0 **30**.

---

## 7. Voice

- **No full voice acting** (cost, localisation, and scope). Dialogue uses **voice blips**: short synthesized or recorded syllables, pitched and timbred per character (like animal-crossing-style speech, but softer).
- **Optional at 1.0:** 6–8 short vocal **barks** per Sworn ("Hmph!", "Ha!", "Ooh!") for anime flavour in combat and emotes, recorded by voice actors or cut.
- **Voice blip sets:** 24 Sworn + Flicker + 4 generic settler voices + 3 antagonists = **32 at 1.0** (VS: ~10).

---

## 8. Technical specs

| Spec | Value |
|---|---|
| Formats | Ogg Vorbis (primary) + AAC `.m4a` fallback; the loader picks what the browser supports |
| Sample rate | 44.1 kHz; music stereo, most SFX mono |
| Loudness | Music around −16 LUFS integrated; SFX peaks ≤ −1 dBTP; UI sounds quieter than gameplay sounds |
| Buses | Master → Music · Ambience · SFX · UI · Voice (each has its own volume slider) |
| Ducking | Dialogue ducks music −4 dB; stingers duck music −6 dB for their duration |
| Spatial | Stereo pan by screen position + distance attenuation for world sounds |
| Looping | Seamless loop points marked in file metadata; town-theme stems are sample-aligned |
| Web note | Audio unlocks on the first user input (browser autoplay policy) |
| Memory | Music streamed; SFX preloaded per scene in audio sprites |

---

## 9. Audio Style Test (Step 14) deliverables
- A 60–90 s sketch of **Once a Sovereign** (main theme), plus a music-box version (Flicker's Lullaby).
- Town theme states 0 and 1, to prove the layering concept.
- The Gloaming (Veil night) ambience + whisper layer.
- 20 core SFX: footsteps (grass, dirt), hoe, watering, harvest pop, axe, pickaxe, sword swing, hit, dodge, Pact success, UI click/confirm/cancel, coin, item pickup, level up, Flicker chirp.
