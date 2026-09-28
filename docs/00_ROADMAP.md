# 00 — Production Roadmap

> **Project NOZE** · title **TBD** (see [Q-01](12_DECISIONS_AND_OPEN_QUESTIONS.md#part-b-open-questions-for-you)) · Design Bible **v0.2**
> **We are here → Step 3 (Narrative & Progression Design) 🔄 — first draft ready for your review.**

---

## TL;DR

We build the game in **small, reviewable steps**. Each step ends with something you can read, play, or look at, and nothing moves forward until you approve it.

**v0.2 change:** for now it's just the two of us, so we first finish **everything that doesn't need a hired artist**: the story, lore, NPC purposes, progression, a playable narrative prototype, then the grey-box game prototypes with in-house placeholder art. The artist joins at the **Art Style Test (Step 13)**.

The rule behind every step: **prove it's fun with placeholder art before paying for final art.**

---

## How each step works

```
 ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────┐
 │ I build  │ →  │ You review   │ →  │ We adjust &  │ →  │ Next    │
 │ the step │    │ (read/play)  │    │ lock it      │    │ step    │
 └──────────┘    └──────────────┘    └──────────────┘    └─────────┘
```

- **Docs** live in `/docs`. Every doc has a TL;DR at the top.
- **Playable builds** (from Step 4 onward) run in a web browser, so you can test them on PC or phone without installing anything.
- **Decisions** are logged in [`12_DECISIONS_AND_OPEN_QUESTIONS.md`](12_DECISIONS_AND_OPEN_QUESTIONS.md).

Legend: ✅ done · 🔄 in progress · ⏳ next · ⬜ not started · 🎨 needs the hired artist

---

## Phase 0: Pre-production

### Track A: what we two can finish ourselves

| # | Step | What you get | Definition of done | Status |
|---|---|---|---|---|
| 1 | **Design Bible v0.1** | Vision, story, systems, cast, bestiary, items, buildings, art & audio direction, asset list, tech plan | All docs written and cross-consistent | ✅ |
| 2 | **Review & Lock → v0.2** | Your answers applied: tone, team, art direction (illustrated 2D), engine, title search | Decisions logged; open items listed | ✅ |
| 3 | **Narrative & Progression Design** | Lore texts, **NPC purpose matrix** (story ↔ systems ↔ progression), interaction design, heart-event arcs for all 24 Sworn, knowledge & secrets matrix, **Chapter 1 quest breakdown with flags** ([`14_NARRATIVE_AND_PROGRESSION.md`](14_NARRATIVE_AND_PROGRESSION.md)) | You approve how every NPC connects to story and progress | 🔄 |
| 4 | **Narrative Prototype (playable)** | A browser-playable, text-first prototype of Chapter 1: days pass, you talk to NPCs, make choices (spare Rook or not), and watch flags, hearts, Kingdom Rank, and unlocks change. Written in **Ink**, so the scripts carry into the real game | You can play Chapter 1's story flow start to finish | ⏳ |
| 5 | **Tech Foundation + Placeholder Kit** | Project scaffold (TypeScript + Phaser 4 + Vite + Spine runtime), lint/test/CI, boot → title screen, input layer, debug overlay, save/load skeleton, content registry, **placeholder art kit** in the reference style | Blank game runs in the browser; CI green; playable link shared | ⬜ |
| 6 | **Grey-box 1: "First Day"** | Movement, camera, collision, Tiled map, hotbar, hoe/watering can/seeds, crop growth, clock, energy, sleep = save | You can farm turnips across 3 in-game days | ⬜ |
| 7 | **Grey-box 2: "Survive the Night"** | Foraging, satiety, campfire crafting, the Veil at night, Exposure, Beacon radius, first enemy (Duskwolf), basic combat | Surviving night 1 feels tense but fair | ⬜ |
| 8 | **Grey-box 3: "Into the Depths"** | Dungeon floor generator (room chunks), mining, loot, Waystones, knockout rules, boss prototype | 10 floors plus a boss are playable | ⬜ |
| 9 | **Grey-box 4: "The First Pact"** | Pact flow (Subdue/Offering), familiar follow and assist, familiar work on the farm | A pacted Puddlepup waters your field | ⬜ |
| 10 | **Grey-box 5: "A Hamlet Rises"** | Build mode, buildings, settler arrival, jobs, Food Stock, housing, Kingdom Rank 0 → 1 | You found a Hamlet and settlers work on their own | ⬜ |
| 11 | **Grey-box 6: "People of the Realm"** | The Step 4 Ink scripts running in-engine: dialogue, hearts and gifts, Rook's recruit arc, Court Day prototype | You recruit a former enemy in-game | ⬜ |
| 12 | **Fun Check** | Internal playtest of the whole grey-box loop, plus a pillars review | "One more day" feeling confirmed, or we pivot. **Go/No-Go gate** | ⬜ |

### Track B: with the hired artist and composer

| # | Step | What you get | Status |
|---|---|---|---|
| 13 | **Art Style Test** 🎨 | Paid test → hire → locked palette, terrain and prop sample, Sovereign rig, 2 creatures, 1 portrait, UI kit sample, combined into a **Target Frame** | ⬜ |
| 14 | **Audio Style Test** | Main theme sketch, Veil-night ambience, 20 core SFX | ⬜ |

## Phase 1: Vertical Slice (VS)

| # | Step | Scope | Status |
|---|---|---|---|
| 15 | **VS Content Production** 🎨 | Prologue + Chapter 1 part 1: Dawnmere Vale, Sunken Cellars F1–10 + Ruinback, Spring, 4 Sworn, 12 creatures, ~14 structures | ⬜ |
| 16 | **VS Polish & External Playtest** | Juice (hitstop, screen shake, particles), onboarding, metrics, surveys. **VS gate** (+ engine re-check) | ⬜ |
| 17 | **Public Presence** | Steam page, capsule art, first trailer, devlog cadence on X / Instagram / TikTok | ⬜ |

## Phase 2: Production → Early Access (EA)

| # | Step | Scope | Status |
|---|---|---|---|
| 18 | **Chapter 1 complete** | All seasons' systems, Village rank, Juniper and Marigold, Court Day, Decrees v1 | ⬜ |
| 19 | **Chapter 2: Whisperwood** | Region, Rootdeep Labyrinth, 5 Sworn, Pale Choir arc, Expeditions | ⬜ |
| 20 | **Chapter 3: Saltglass Coast** | Region, Drowned Bells, 4 Sworn, fishing, trade, Veil Surges | ⬜ |
| 21 | **EA Hardening** | Settings, accessibility, save migration, performance, bug bash, Steam demo (Next Fest) | ⬜ |
| 22 | **🚀 Early Access Launch** | Chapters 1–3 | ⬜ |

## Phase 3: Early Access → 1.0

| # | Step | Scope | Status |
|---|---|---|---|
| 23 | **Chapter 4: Cinderpeak** | Forgeheart, Dominion war arc, 5 Sworn, mounts, bathhouse | ⬜ |
| 24 | **Chapter 5: Frostveil** | Starfall Spire, the Long Winter event, 3 Sworn | ⬜ |
| 25 | **Chapter 6: The Hollow Crown** | Halcyon Below, Ashen Warden, the Maw, 3 endings, post-game Veil Rifts | ⬜ |
| 26 | **🏁 1.0 Launch** | Full game; evaluate console ports, localisation, and mod support | ⬜ |

---

## Parallel tracks (things to start early)

| Track | When | What |
|---|---|---|
| **Title clearance** | Now → before Step 17 | Pick the title → check Indonesia's trademark database (PDKI, DJKI), USPTO, EUIPO/WIPO, Steam, domain, social handles → consider filing a trademark (classes 9 and 41) before the Steam page goes live |
| **Artist search** | From Step 10 | Shortlist portfolios that match [08 §18](08_ART_DIRECTION.md#18-hiring-an-artist-brief--paid-test); run the paid test so the Art Style Test can start right after the Fun Check |
| **Build in public** | From Step 6 | Weekly GIF or short clip (grey-boxes can be charming); later art reveals; wishlist call-to-action from Step 17 |

---

## Milestone content targets

| Content | Vertical Slice | Early Access | 1.0 |
|---|---|---|---|
| Story chapters | Prologue + Ch1 (part) | Prologue + Ch1–3 | Prologue + Ch1–6 + 3 endings |
| Overworld regions | 1 (Dawnmere Vale) | 3 | 6 |
| Dungeons (floors) | 1 (10 + boss) | 3 (10 / 15 / 15 + bosses) | 6 (+ endless Veil Rifts) |
| Seasons | Spring | All 4 | All 4 |
| Sworn (named recruits) | 4 | 15 | 24 |
| Romanceable | 3 | 7 | 12 |
| Creature species (+ Guardians) | 12 (+1) | 27 (+3) | 38 (+5) |
| True Ascension forms | 2 | 8 | 17 |
| Crops (+ trees & perennials) | 6 | 25 (+5) | 29 (+8) |
| Buildings (types) | 14 | 31 | 42 |
| Kingdom Rank reached | 1 (Hamlet) | 3 (Town) | 5 (Kingdom) |
| Festivals | 1 | 8 | 8 |
| Music tracks (+ jingles) | 14 (+10) | 35 (+11) | 48 (+11) |

Full per-asset breakdown: [`10_ASSET_LIST.md`](10_ASSET_LIST.md).

---

## Gates (go / no-go)

1. **Fun Gate (Step 12).** If the grey-box loop isn't fun with placeholder art, final art won't save it. We fix or cut systems here, while it's cheap.
2. **Style Gate (Step 13).** The Target Frame must read clearly at phone size and on a 4K monitor before we produce assets at scale.
3. **VS Gate (Step 16).** At least 70% of external playtesters want to keep playing after 60 minutes. The Steam page goes live only after this. We also re-confirm the engine here.
4. **EA Gate (Step 21).** Crash-free rate at least 99.5% in testing; 15+ hours of content; save compatibility guaranteed from EA onward.

---

## Top risks and mitigations

| Risk | Why it's real | Mitigation |
|---|---|---|
| **Scope explosion** (5 genres in one) | Every genre is a full game on its own | One unifying loop ("everything feeds the Kingdom"), a hard VS scope, and a MoSCoW feature list ([`03_GAMEPLAY_SYSTEMS.md` §22](03_GAMEPLAY_SYSTEMS.md#22-feature-priority-moscow)) |
| **Content cost** (24 named characters, portraits, dialogue) | Portraits and writing are the most expensive assets per character | Two-tier people: 24 hand-made **Sworn** plus generated **Settlers** built from modular parts |
| **Survival feels like chores** | Hunger meters annoy cozy players | "Survival lives at the frontier": harsh in the wilds, comfortable at home; Cozy difficulty mode |
| **System interplay bugs** | Farming × AI × economy × time interact constantly | Simulation separated from rendering, deterministic ticks, unit tests on systems |
| **HD art throughput** | Illustrated art and animation cost more per asset than pixel art | Spine rigs and skins, layered portraits, a reusable prop kit, shaders for variants ([`10_ASSET_LIST.md` §16](10_ASSET_LIST.md#16-production-notes)) |
| **Too similar to existing games** | Rune Factory, Palworld, and Stardew all loom large | Our differentiators: the fallen-monarch fantasy, enemy recruitment, Court Day and Decrees, the Veil/Beacon territory loop |
| **Title conflict** | *Crownless* is already taken on Steam | Title clearance track above |

For scale: Stardew Valley took its solo creator roughly four and a half years. Gating on a vertical slice is how we keep this project finishable.
