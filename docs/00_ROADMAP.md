# 00 — Production Roadmap

> **Project NOZE** · working title **_Crownless_** · Design Bible v0.1
> **We are here → Step 1 (Design Bible v0.1) ✅ — waiting for your review (Step 2).**

---

## TL;DR

We build the game in **small, reviewable steps**. Each step ends with something you can read, play, or look at, and nothing moves forward until you approve it. Nothing basic gets skipped: design → tech foundation → grey-box prototypes (one system at a time) → fun check → art and audio style tests → vertical slice → early access → 1.0.

The rule behind every step: **prove it's fun in grey boxes before paying for pretty pixels.**

---

## How each step works

```
 ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────┐
 │ I build  │ →  │ You review   │ →  │ We adjust &  │ →  │ Next    │
 │ the step │    │ (read/play)  │    │ lock it      │    │ step    │
 └──────────┘    └──────────────┘    └──────────────┘    └─────────┘
```

- **Docs** live in `/docs` (this folder). Every doc has a TL;DR at the top.
- **Playable builds** (from Step 3 onward) run in a web browser, so you can test them on PC or phone without installing anything.
- **Decisions** get logged in [`12_DECISIONS_AND_OPEN_QUESTIONS.md`](12_DECISIONS_AND_OPEN_QUESTIONS.md), so we never re-argue a settled question by accident.

Status legend: ✅ done · 🔄 in progress · ⏳ next · ⬜ not started

---

## Phase 0: Pre-production

| # | Step | What you get | Definition of done | Status |
|---|------|--------------|--------------------|--------|
| 1 | **Design Bible v0.1** | Vision, story/world, systems, characters, bestiary, items, buildings, art and audio direction, **master asset list**, tech plan, decisions | All docs written and cross-consistent; open questions listed | ✅ |
| 2 | **Review & Lock** | Your feedback applied → Design Bible v0.2 | Title, tone, art scale, platform, scope, and "who makes the art" are decided | ⏳ |
| 3 | **Tech Foundation** | Project scaffold (TypeScript + Phaser + Vite), folder structure, lint/test/CI, boot → title screen, input layer, debug overlay, save/load skeleton, content registry | Blank game runs in the browser; CI green; playable link shared | ⬜ |
| 4 | **Grey-box 1: "First Day"** | Movement, camera, collision, Tiled map, hotbar, hoe/watering can/seeds, crop growth, clock, energy, sleep = save | You can farm turnips across 3 in-game days | ⬜ |
| 5 | **Grey-box 2: "Survive the Night"** | Foraging, satiety, campfire crafting, the Veil at night, Exposure, Beacon radius, first enemy (Duskwolf), basic combat | Surviving night 1 feels tense but fair | ⬜ |
| 6 | **Grey-box 3: "Into the Depths"** | Dungeon floor generator (room chunks), mining, loot, Waystones, pass-out rules, boss prototype | 10 floors plus a boss are playable | ⬜ |
| 7 | **Grey-box 4: "The First Pact"** | Pact flow (Subdue/Offering), familiar follow and assist, familiar work assignments on the farm | A pacted Puddlepup waters your field for you | ⬜ |
| 8 | **Grey-box 5: "A Hamlet Rises"** | Build mode, buildings, settler arrival, jobs, Food Stock, housing, Kingdom Rank 0 → 1 | You found a Hamlet and settlers work on their own | ⬜ |
| 9 | **Grey-box 6: "People of the Realm"** | Dialogue (Ink), hearts and gifts, recruit quest (Rook: defeat → spare → trial), Court Day prototype | You recruit a former enemy | ⬜ |
| 10 | **Fun Check** | Internal playtest of the full grey-box loop, plus a pillars review | "One more day" feeling confirmed, or we pivot. **Go/No-Go gate** | ⬜ |
| 11 | **Art Style Test** | Final palette, tileset sample, Sovereign sprite, 2 creatures, 1 portrait, UI kit sample, combined into a **Target Frame** | One screenshot that looks like the real game | ⬜ |
| 12 | **Audio Style Test** | Main theme sketch, Veil-night ambience, 20 core SFX | Theme and SFX approved | ⬜ |

## Phase 1: Vertical Slice (VS)

| # | Step | Scope | Status |
|---|------|-------|--------|
| 13 | **VS Content Production** | Prologue + Chapter 1 part 1: Dawnmere Vale, Sunken Cellars F1–10 + Ruinback, Spring, 4 Sworn, 12 creatures, ~14 structures | ⬜ |
| 14 | **VS Polish & External Playtest** | Juice (hitstop, screenshake, particles), onboarding, metrics, surveys | ⬜ |
| 15 | **Public Presence** | Steam page, capsule art, first trailer, devlog cadence on X / Instagram / TikTok | ⬜ |

## Phase 2: Production → Early Access (EA)

| # | Step | Scope | Status |
|---|------|-------|--------|
| 16 | **Chapter 1 complete** | All of Spring through Winter systems, Village rank, Juniper and Marigold, Court Day, Decrees v1 | ⬜ |
| 17 | **Chapter 2: Whisperwood** | Region, Rootdeep Labyrinth, 5 Sworn, Pale Choir arc, Expeditions | ⬜ |
| 18 | **Chapter 3: Saltglass Coast** | Region, Drowned Bells, 4 Sworn, fishing, trade, Veil Surges | ⬜ |
| 19 | **EA Hardening** | Settings, accessibility, save migration, performance, bug bash, Steam demo (Next Fest) | ⬜ |
| 20 | **🚀 Early Access Launch** | Chapters 1–3 | ⬜ |

## Phase 3: Early Access → 1.0

| # | Step | Scope | Status |
|---|------|-------|--------|
| 21 | **Chapter 4: Cinderpeak** | Forgeheart, Dominion war arc, 5 Sworn, mounts, bathhouse | ⬜ |
| 22 | **Chapter 5: Frostveil** | Starfall Spire, the Long Winter event, 3 Sworn | ⬜ |
| 23 | **Chapter 6: The Hollow Crown** | Halcyon Below, Ashen Warden, the Maw, 3 endings, post-game Veil Rifts | ⬜ |
| 24 | **🏁 1.0 Launch** | Full game; evaluate console ports, localization, and mod support | ⬜ |

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

1. **Fun Gate (Step 10).** If the grey-box loop isn't fun with boxes and circles, art won't save it. We fix or cut systems here, while it's cheap.
2. **Style Gate (Step 11).** The Target Frame must read clearly at 1× phone size and 4× monitor size before we produce assets at scale.
3. **VS Gate (Step 14).** At least 70% of external playtesters want to keep playing after 60 minutes. The Steam page goes live only after this.
4. **EA Gate (Step 19).** Crash-free rate at least 99.5% in testing; 15+ hours of content; save compatibility guaranteed from EA onward.

---

## Parallel track: build in public

The indie devs you see posting progress on X, IG, Pinterest, and in Steam communities are doing this for a reason: **wishlists come from months of visible progress.**

| When | What |
|---|---|
| From Step 4 | Weekly GIF or short clip (a grey-box can be charming: "turnip grows, Puddlepup waters it") |
| From Step 11 | Art reveals: character sheets, creature designs, "before/after" of the Veil |
| From Step 15 | Steam page, wishlist call-to-action in every post, monthly devlog |
| From Step 19 | Demo, Next Fest, streamer/press outreach |

---

## Top risks and mitigations

| Risk | Why it's real | Mitigation |
|---|---|---|
| **Scope explosion** (5 genres in one) | Every genre is a full game on its own | One unifying loop ("everything feeds the Kingdom"), a hard VS scope, and a MoSCoW feature list ([`03_GAMEPLAY_SYSTEMS.md` §22](03_GAMEPLAY_SYSTEMS.md#22-feature-priority-moscow)) |
| **Content cost** (24 named characters, portraits, dialogue) | Portraits and writing are the most expensive assets per character | Two-tier people: 24 hand-made **Sworn** plus procedurally generated **Settlers** built from modular parts |
| **Survival feels like chores** | Hunger meters annoy cozy players | "Survival lives at the frontier": harsh in the wilds, comfortable at home; Cozy difficulty mode |
| **System interplay bugs** | Farming × AI × economy × time interact constantly | Simulation separated from rendering, deterministic ticks, unit tests on systems |
| **Art throughput** | Pixel animation is slow | Templates, palette swaps, modular layers, and reuse rules ([`08_ART_DIRECTION.md`](08_ART_DIRECTION.md)) |
| **Too similar to existing games** | Rune Factory, Palworld, and Stardew all loom large | Our differentiators: the fallen-king fantasy, enemy recruitment, Court Day and Decrees, the Veil/Beacon territory loop |

For scale: Stardew Valley took its solo creator roughly four and a half years. Gating on a vertical slice is how we keep this project finishable.
