# Kingdom View prototype (Step 4b)

A playable 3D prototype of Kingsbloom's **Kingdom View**, the management layer the hybrid direction adds ([D-039](../../docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#part-a-decision-log)), in the new 3D diorama look ([D-040](../../docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#part-a-decision-log)). You build the hamlet freely, light the Old Road, open the **Lantern Market** at dusk, and watch travelers shop, linger, tip, and sometimes ask to stay. Switch to **Walk** at any time to play as the Sovereign in the same world.

**Play it:** open [`dist/index.html`](dist/index.html) in a browser with WebGL 2 (it works offline), or use the published link. Progress saves in your browser.

---

## What's in it

| | |
|---|---|
| **Kingdom View** | Free building on the tile grid: stone paths (drag to paint), Lantern Posts, String Lights, Market Stalls, Turnip and Wheat Fields, a Fishing Hut, a Cookhouse, Tents, Huts and eight kinds of decor. Rotate, change style, move, and remove for half the cost. Build inside the Heartflame's reach; lights can also stand beside any road |
| **The Lantern Market** | Open it at dusk. Travelers, merchants, farmhands, Lantern Monks and Veilkin (Mossbun, Puddlepup, Emberkit) walk up the Old Road, queue at the stalls, buy from the kingdom stores, linger by benches and flowers, and leave tips you can click. Close it yourself or let it close at 03:00, then read the **Night Ledger**: sales, how people felt, what they asked for, and who is moving in |
| **Light and the Veil** | At night the Veil fills every unlit place. A traveler who walks too far in the dark turns back. Lamps are decor and protection at once |
| **Stalls** | Each sells one kind of goods (Harvest, Grain, Catch, Stew), and Linnea sells her Tonics. Upgrades raise the price (×1.3, then ×1.6) and serve faster (3.0 s, 2.4 s, 1.8 s) |
| **Appeal** | Decor near the paths, variety, how much of the way in is lit, and Linnea's stall. More appeal brings more visitors |
| **People** | Happy visitors ask to settle when there is a free bed. Settlers work the fields, the Fishing Hut and the Cookhouse. Twelve residents and a raised Heartflame make the Hamlet a **Village** |
| **Walk** | Play as the Sovereign with Flicker: tend a field (+3, once a day), talk to Bram, Linnea and Hob, serve at a stall (twice as fast, and customers love it), and carry light down a dark road |
| **Story** | Ten tasks from Bram, Linnea, Hob and Flicker, and seven pages of the **Royal Chronicle** |
| **Comfort** | Pause, 1×, 2× and fast; skip to dusk; photo mode; music and sound generated in the browser; three graphics levels; **Skip ahead** in Settings (Bram plays a few days for you) |

## What we're testing

1. Is the loop fun: build, open the market, watch, improve?
2. Does lighting the road feel like a real choice, beauty and protection at once?
3. Does walking as the Sovereign in the same world add something to the market?
4. Does the 3D diorama look match what you want for Kingsbloom?

## How it's built

| Part | Files | Job |
|---|---|---|
| Simulation | [`src/sim/`](src/sim) | The map, building rules, time, production, the market, visitors, light and the Veil, appeal, residents, tasks and saves. No rendering, so it runs in Node for the tests |
| Content | [`src/sim/catalog.js`](src/sim/catalog.js) | Goods, buildings, visitor kinds, lines, tasks and Chronicle pages. Every number is a placeholder |
| 3D view | [`src/render/`](src/render) | [three.js](https://threejs.org): terrain and the forest ring, low-poly models built from primitives in code, instanced drawing, lantern light pools, the Veil (a light texture that tints every material, plus drifting mist), bloom and a tilt-shift miniature blur |
| HUD | [`src/ui/`](src/ui) | The "Royal Storybook" HUD ([docs/08 §12](../../docs/08_ART_DIRECTION.md#12-ui-royal-storybook)), tools, the build catalogue, building details, walking, speech bubbles, the Night Ledger, the Chronicle, settings, and generated audio |
| Bot | [`src/sim/bot.js`](src/sim/bot.js) | A simple player used by the tests and by Skip ahead |
| Tests | [`test/sim.test.mjs`](test/sim.test.mjs) | 15 checks, including full runs to Village rank on four seeds |

## Build and test

```bash
cd prototypes/kingdom-view
npm install
npm test          # the simulation, building rules, a dark and a lit night, walking, saves, four runs to Village
npm run build     # writes dist/index.html (self-contained, three.js bundled in)
```

## Pacing baseline from the bot

The bot lights the road on day 1 and reaches **Village on day 6 or 7** (seeds 1, 7, 42, 99 and 123). A day lasts about 3½ minutes at normal speed, so a person who stops to build and look around should reach Village in roughly 30 to 45 minutes. Your playtest gives us the real number.

## Simplified on purpose

- One map (the Dawnmere clearing), one season, no weather.
- Buildings cost gold only; materials come later.
- Stalls need no staff, and settlers are given jobs automatically.
- The pond and the forest are fixed; you can't clear trees.
- No combat, dungeons or hoeing by hand here. Those stay in the life-sim layer ([docs/03](../../docs/03_GAMEPLAY_SYSTEMS.md)) and get their own grey-boxes.
- Placeholder art: every model is built from primitives in code. Nothing here ships.

## Reference

The loop is modeled on [*Oboro no Ichi*](https://store.steampowered.com/app/4559930/Oboro_no_Ichi/) (TheLaba), a cozy spirit-market builder: build freely, open the market, watch visitors shop, collect tips, grow appeal. We took the mechanics only. Its theme, UI, names and art are not used; the setting stays Kingsbloom's kingdom, the Veil and the Sworn. See [docs/01 §7](../../docs/01_VISION.md#7-reference-breakdown-what-we-take-and-what-we-leave).

## What comes next

Your playtest ([Q-15](../../docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#other-questions)) → choose the engine for the 3D direction ([Q-14](../../docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#other-questions)) → re-plan Steps 5 to 12 around the hybrid.
