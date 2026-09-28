# Chapter 1 narrative prototype (Step 4)

A playable, text-first prototype of **Chapter 1: Ashes and Embers**. You live the chapter day by day, meet the people who become your realm, make the big choices, and watch flags, hearts, the Food Stock, Kingdom Rank, and unlocks change as you go.

**Play it:** open [`dist/index.html`](dist/index.html) in any browser (it works offline), or use the published link from the review message. Progress saves in your browser.

---

## What's in it

| | |
|---|---|
| **Story** | MQ-101 to MQ-117 plus SQ-114 and SQ-115 from [docs/14 §9](../../docs/14_NARRATIVE_AND_PROGRESSION.md#9-chapter-1-quest-by-quest-prototype-ready): waking at the Ashen Throne, the first night, Bram, the first Pacts, Linnea on her birthday, the Founding, Rook's raid (**Spare or Banish**), the Old Granary, the Sunken Cellars, Tamsin, Ruinback and the Signet, the Founding Feast (end of the Vertical Slice), Marigold and Pip, Juniper's herd, the first Court Day and Decree, the Old Bridge, and the road to Chapter 2 |
| **People** | Daily talk lines by heart tier, reactions to your deeds, gifts (two a week, birthdays ×5), a request at 3♥, and heart events at 2♥ and 4♥ for Bram, Linnea, Rook and Tamsin (2♥ for Juniper, Marigold and Mira) |
| **Days** | Morning, afternoon and evening: one action each (gather, forage, fields, a location, the caravan, a dive, time with someone, rest). Night comes on its own |
| **Free actions** | Talking, gifts, cooking and crafting, building, restoration bundles, stocking the stores, work orders, and Royal Summons use no time |
| **The realm** | Food Stock, Joy, Safety, Royal Authority, beds, settlers who arrive at dawn (accept or turn away), thefts on the Banish path, Blossomfall on Spring 13 |
| **Side panel** | Quests (written in Ink), Realm, People (hearts and each person's purpose), Bag, Log, and **Flags**: every story variable, with the last changes highlighted |
| **Skip ahead** | The Founding · Rook's night · the Founding Feast · Court Day. A bot plays the days before, as "Aria" |

## What we're testing ([docs/14 §10](../../docs/14_NARRATIVE_AND_PROGRESSION.md#10-plan-for-step-4-the-playable-narrative-prototype))

1. Does each person's purpose in the kingdom feel clear?
2. Is the pace of Chapter 1 right?
3. Does sparing (or banishing) Rook feel like it matters?
4. Would you play one more day?

**Success check:** after playing, you can say in your own words why each of the four Vertical Slice Sworn (Bram, Linnea, Rook, Tamsin) matters to the kingdom.

---

## How it's built

| Part | Files | Job |
|---|---|---|
| Story | [`ink/`](ink) (14 files, about 2,000 lines) | Scenes, dialogue, choices, and the story flags. Written in [Ink](https://www.inklestudios.com/ink/) |
| Game | [`src/sim.js`](src/sim.js) | Time, items, fields, buildings, the Food Stock, settlers, dives, hearts, saves |
| Data | [`src/content.js`](src/content.js) | Items, crops, buildings, projects, the shop, people and their gifts, and **when each scene plays** |
| Page | [`src/ui.js`](src/ui.js), [`src/style.css`](src/style.css), [`src/main.js`](src/main.js) | The "Royal Storybook" interface ([docs/08 §12](../../docs/08_ART_DIRECTION.md#12-ui-royal-storybook)), with portraits from the [placeholder kit](../../art/placeholder) |
| Bot | [`src/autoplay.js`](src/autoplay.js) | A goal-driven player used by the tests and by "Skip ahead" |
| Tests | [`test/playthrough.test.mjs`](test/playthrough.test.mjs) | Nine checks, including six full playthroughs |

### The contract between the game and the Ink

- **Ink owns the story flags.** Names follow [docs/14 §9.4](../../docs/14_NARRATIVE_AND_PROGRESSION.md#94-state-the-prototype-must-track) with the dots written as underscores (`npc.bram.recruited` → `npc_bram_recruited`). They're declared in [`ink/globals.ink`](ink/globals.ink).
- **The game owns the numbers** (items, gold, food, hearts, time, buildings). Ink reads and changes them through `EXTERNAL` functions: `item`, `give`, `stat`, `add_stat`, `hearts`, `add_hearts`, `weekday`, `season`, `built`, `unlock`, `plant`, `add_settler`. In Step 11 the Phaser game binds the same functions, so these scripts move into the real game unchanged.
- **The game decides when, the Ink decides what.** `SCENES` and `HEART_EVENTS` in `content.js` say when a knot plays; the knot says what happens and sets the flags.
- **Tags drive presentation:** `#speaker:<id>` `#mood:<expression>` `#emote:heart` `#scene:<place>` `#bg:<dawn|day|dusk|night|cellar|feast|festival>` `#style:<note|memory|hymn>` `#input:<variable>` `#banner` `#tone:<regal|warm|wry>` (on spoken choices) `#vs_end` `#chapter_end`.
- Scenes that can play more than once (arrivals, weekly Court) use sticky `+` choices.

## Build and test

```bash
cd prototypes/narrative-ch1
npm install
npm test          # compiles the Ink, then plays Chapter 1 on both paths with three seeds
npm run build     # writes dist/index.html (self-contained)
```

## Pacing baseline from the bot

| Path | Founding | Founding Feast (end of the VS) | Village | Chapter 1 complete |
|---|---|---|---|---|
| Spare | day 10 | day 17–18 | day 28 | day 30 (Summer 2) |
| Banish | day 10 | day 17 | day 28–29 | day 30–31 |

Targets in [docs/14 §3.3](../../docs/14_NARRATIVE_AND_PROGRESSION.md#33-pacing-targets): the VS by Spring 14 and Chapter 1 by Summer 14 (day 42). The bot plays efficiently and skips most conversations, so a person playing for the story will be slower. Your playtest gives us the real number.

## Simplified on purpose

- **Satiety isn't tracked**, and Exposure appears only in night scenes. Survival gets its own grey-box (Step 7).
- **Combat is choices plus a power check.** Ruinback needs power 3: your base, plus any two of Linnea, Tamsin's sword, and the Emberkit.
- **Numbers are placeholders**, scaled down from [docs/07 §3.7](../../docs/07_BUILDINGS_AND_KINGDOM.md#37-example-costs-vs-placeholders) so a text prototype moves at a readable pace.
- Prototype-only rules, logged as decisions **D-033 to D-038** in [docs/12](../../docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#part-a-decision-log): Waystones on floors 3, 5, 8 and 10; the Food Stock starts at the Founding, and the Longhouse larder holds 20 until the Old Granary is restored; a soft deadline for Rook's Trial; Royal Summons from Hamlet rank.

## What comes next

Your playtest notes → one tuning pass → **Step 5: Tech Foundation**. These Ink scripts run inside the real game in **Step 11**.
