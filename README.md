# Project NOZE (title TBD)

> ***Once a sovereign. Now an exile. Rebuild the kingdom you lost.***

A farming life-sim × dungeon crawler × kingdom builder with mystical creature pacts, anime heart, and survival at the frontier, in a hand-drawn illustrated storybook style.

You were the legendary Last Sovereign of Halcyon. A thousand years after your death you wake in the **Veilwilds**, a mist-drowned land you don't recognise, with only **Flicker**, a talking ember with a tiny crown, for company. You survive the first nights, farm to feed yourself and then your people, dive into shifting dungeons, form **Pacts** with mystical creatures that work and fight beside you, **spare and recruit your enemies**, and rebuild a kingdom from a single campfire.

*Stardew Valley meets Suikoden, with pact-bound creatures and a fallen monarch's second chance.*

---

## Status

| | |
|---|---|
| **Phase** | Pre-production, Design Bible **v0.2** |
| **Done** | ✅ Step 1: Design Bible v0.1 · ✅ Step 2: Review & Lock |
| **Now** | 🔄 Step 3: Narrative & Progression Design ([doc 14](docs/14_NARRATIVE_AND_PROGRESSION.md), awaiting your review) |
| **Next** | ⏳ Step 4: a playable narrative prototype of Chapter 1 (in the browser) |
| **Title** | Open: *Crownless* is already used on Steam; shortlist in [Q-01](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#q-01-title-open-again) |

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
| 05 | [Bestiary](docs/05_BESTIARY.md) | **38 creature species**, 17 True Ascensions, 5 Guardians, Wisplings, enemies |
| 06 | [Items, Crops & Recipes](docs/06_ITEMS_CROPS_RECIPES.md) | Crops, trees, forage, ores, artisan goods, 26 recipes, tools, weapons, fish |
| 07 | [Buildings & Kingdom](docs/07_BUILDINGS_AND_KINGDOM.md) | 42 buildings, Kingdom Ranks, Restoration Projects, 12 Decrees, Court Day, festivals |
| 08 | [Art Direction](docs/08_ART_DIRECTION.md) | **Illustrated 2D** style from your references, palette, scale, the Veil look, UI, animation, artist hiring brief |
| 09 | [Audio Direction](docs/09_AUDIO_DIRECTION.md) | Adaptive music, 48-track list, SFX, ambience, voice |
| 10 | [Master Asset List](docs/10_ASSET_LIST.md) | **Every asset mapped** by ID, template, and milestone, with totals |
| 11 | [Technical Design](docs/11_TECHNICAL_DESIGN.md) | Engine comparison in plain language, architecture, data, saves, testing, CI |
| 12 | [Decisions & Open Questions](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md) | Why each call was made, and what you still need to decide |
| 13 | [Glossary](docs/13_GLOSSARY.md) | One word, one meaning |
| 14 | [Narrative & Progression](docs/14_NARRATIVE_AND_PROGRESSION.md) | **NPC purpose → story → progression**, quest chain, heart events, secrets matrix, lore texts, Chapter 1 flags |

**Short on time?** Read this README → [Narrative & Progression](docs/14_NARRATIVE_AND_PROGRESSION.md) → [Open Questions](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#part-b-open-questions-for-you).

---

## Quick facts

| | |
|---|---|
| Genre | Farming life-sim · dungeon crawler · kingdom builder · creature pacts · frontier survival |
| Look | Top-down 3/4, hand-drawn illustrated 2D, chibi-anime characters, HD portraits |
| Platform | PC (Steam) first; every development build is playable in a web browser |
| Language | English (localisation-ready) |
| Tech | TypeScript · Phaser 4 · Spine · Vite · Tiled · Ink |
| Business model | Premium, no microtransactions |

## Repository layout

```
docs/          The Design Bible (you are here)
game/          (Step 5) the game project
art_src/       (Step 13) layered source art and Spine projects
audio_src/     (Step 14) source audio
tools/         (Step 5) pipeline scripts
```
