# NOZE: *Crownless* (working title)

> ***Once a sovereign. Now an exile. Rebuild the kingdom you lost.***

A farming life-sim × dungeon crawler × kingdom builder with mystical creature pacts, anime heart, and survival at the frontier.

You were the legendary Last Sovereign of Halcyon. A thousand years after your death you wake in the **Veilwilds**, a mist-drowned land you don't recognise, with only **Flicker**, a talking ember with a tiny crown, for company. You survive the first nights, farm to feed yourself and then your people, dive into shifting dungeons, form **Pacts** with mystical creatures that work and fight beside you, **spare and recruit your enemies**, and rebuild a kingdom from a single campfire.

*Stardew Valley meets Suikoden, with pact-bound creatures and a fallen monarch's second chance.*

---

## Status

| | |
|---|---|
| **Phase** | Pre-production |
| **Current step** | ✅ Step 1: Design Bible v0.1 |
| **Next step** | ⏳ Step 2: Review & Lock (answer the [open questions](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#part-b-open-questions-for-you)) |
| **Then** | Step 3: Tech Foundation (first playable browser build) |

Full plan: [`docs/00_ROADMAP.md`](docs/00_ROADMAP.md)

---

## The Design Bible

| # | Document | What's inside |
|---|---|---|
| 00 | [Roadmap](docs/00_ROADMAP.md) | Step-by-step production plan, milestone targets, gates, risks |
| 01 | [Vision](docs/01_VISION.md) | Pitch, core fantasy, design pillars, what we take from each reference game, audience |
| 02 | [Story & World](docs/02_STORY_AND_WORLD.md) | Lore, the four-layer mystery, regions, factions, chapters, endings *(spoilers)* |
| 03 | [Gameplay Systems](docs/03_GAMEPLAY_SYSTEMS.md) | Loops, time, survival, the Veil, farming, combat, dungeons, pacts, kingdom, decrees, romance, economy, controls |
| 04 | [Characters](docs/04_CHARACTERS.md) | The Sovereign, Flicker, **24 Sworn**, antagonists, settler generation, relationship map |
| 05 | [Bestiary](docs/05_BESTIARY.md) | **38 creature species**, 17 True Ascensions, 5 Guardians, enemies |
| 06 | [Items, Crops & Recipes](docs/06_ITEMS_CROPS_RECIPES.md) | Crops, trees, forage, ores, artisan goods, 26 recipes, tools, weapons, fish |
| 07 | [Buildings & Kingdom](docs/07_BUILDINGS_AND_KINGDOM.md) | 42 buildings, Kingdom Ranks, Restoration Projects, 12 Decrees, Court Day, festivals |
| 08 | [Art Direction](docs/08_ART_DIRECTION.md) | Style, scale, palette, lighting, the Veil look, UI, animation standards |
| 09 | [Audio Direction](docs/09_AUDIO_DIRECTION.md) | Adaptive music, 48-track list, SFX, ambience, voice |
| 10 | [Master Asset List](docs/10_ASSET_LIST.md) | **Every asset mapped** by ID, template, and milestone, with totals |
| 11 | [Technical Design](docs/11_TECHNICAL_DESIGN.md) | Engine choice, architecture, data, saves, testing, CI |
| 12 | [Decisions & Open Questions](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md) | Why each call was made, and what you need to decide |
| 13 | [Glossary](docs/13_GLOSSARY.md) | One word, one meaning |

**Short on time?** Read this README → [Vision](docs/01_VISION.md) → [Roadmap](docs/00_ROADMAP.md) → [Open Questions](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md) (about 15 minutes).

---

## Quick facts

| | |
|---|---|
| Genre | Farming life-sim · dungeon crawler · kingdom builder · creature pacts · frontier survival |
| View | Top-down 3/4, anime-inspired pixel art (16 px tiles) |
| Platform | PC (Steam) first; every development build is playable in a web browser |
| Language | English (localisation-ready) |
| Tech (proposed) | TypeScript · Phaser 4 · Vite · Tiled · Ink |
| Business model | Premium, no microtransactions |

## Repository layout

```
docs/          The Design Bible (you are here)
game/          (Step 3) the game project
art_src/       (Step 11) source art
audio_src/     (Step 12) source audio
tools/         (Step 3) pipeline scripts
```
