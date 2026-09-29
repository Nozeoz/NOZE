# Kingsbloom

*Project codename: NOZE*

> ***Once a sovereign. Now an exile. Rebuild the kingdom you lost.***

A farming life-sim × dungeon crawler × kingdom builder with mystical creature pacts, anime heart, and survival at the frontier, plus a **Kingdom View** where you build freely and run a lantern-lit night market, in a warm **3D diorama** look.

You were the legendary Last Sovereign of Halcyon. A thousand years after your death you wake in the **Veilwilds**, a mist-drowned land you don't recognise, with only **Flicker**, a talking ember with a tiny crown, for company. You survive the first nights, farm to feed yourself and then your people, dive into shifting dungeons, form **Pacts** with mystical creatures that work and fight beside you, **spare and recruit your enemies**, and rebuild a kingdom from a single campfire.

*Stardew Valley meets Suikoden, with pact-bound creatures and a fallen monarch's second chance.*

---

## Status

| | |
|---|---|
| **Phase** | Pre-production, Design Bible **v0.5** |
| **Done** | ✅ Step 1: Design Bible · ✅ Step 2: Review & Lock · ✅ Step 3: Narrative & Progression Design |
| **Now** | 🔄 **Step 4c: the Roblox test build**, *Kingsbloom: Lantern Market* for up to 6 players ([`roblox/`](roblox), open [`roblox/Kingsbloom.rbxlx`](roblox/Kingsbloom.rbxlx) in Roblox Studio) · 🔄 Step 4b: the Kingdom View prototype in three.js ([`prototypes/kingdom-view`](prototypes/kingdom-view)) · 🔄 Step 4: the Chapter 1 narrative prototype ([`prototypes/narrative-ch1`](prototypes/narrative-ch1)) · all three wait for your playtest |
| **Direction (v0.5)** | **Hybrid** life-sim + Kingdom View, modeled on *Oboro no Ichi* ([D-039](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#part-a-decision-log)); **3D diorama** look ([D-040](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#part-a-decision-log)); engine to be re-chosen ([Q-14](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#other-questions)) |
| **Next** | ⏳ Your playtests (the Roblox build first, [Q-16](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#other-questions)) → choose the engine → re-plan Steps 5 to 12 |
| **Title** | ***Kingsbloom*** (formal trademark clearance pending, see [Q-01](docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#q-01-title)) |

Full plan: [`docs/00_ROADMAP.md`](docs/00_ROADMAP.md) · What happened so far: [`docs/PROGRESS_LOG.md`](docs/PROGRESS_LOG.md) · Notes for Claude Code: [`CLAUDE.md`](CLAUDE.md)

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
| 08 | [Art Direction](docs/08_ART_DIRECTION.md) | Palette, the Veil look, UI, animation, artist hiring brief (being rewritten for the **3D diorama** look, D-040) |
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
| Genre | Farming life-sim · dungeon crawler · kingdom builder · creature pacts · frontier survival · cozy market builder (Kingdom View) |
| Look | 3D diorama: low-poly, lantern-lit, tilt-shift miniature feel, chibi characters (v0.5; was illustrated 2D) |
| Platform | PC (Steam) first; every development build is playable in a web browser |
| Language | English (localisation-ready) |
| Tech | Ink for story; the Kingdom View prototype runs on three.js; the Roblox test build is Luau with Rojo; the game engine is being re-chosen for 3D (Godot 4, Unity or three.js) |
| Business model | Premium, no microtransactions |

## Repository layout

```
docs/          The Design Bible (you are here)
prototypes/    (Step 4) playable prototypes: narrative-ch1 is Chapter 1 in Ink; kingdom-view is the 3D Kingdom View and Lantern Market
roblox/        (Step 4c) Kingsbloom: Lantern Market, the Roblox test build (Rojo project, tests, ready-to-open place file)
art/           (Step 4) in-house placeholder art kit and the Asset Atlas (never ships)
game/          (Step 5) the game project
art_src/       (Step 13) layered source art and Spine projects
audio_src/     (Step 14) source audio
tools/         (Step 5) pipeline scripts
```
