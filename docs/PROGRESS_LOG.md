# Progress Log

> **TL;DR:** The Design Bible is at v0.5 (a hybrid life-sim plus Kingdom View, in a 3D diorama look). Three playable prototypes exist: Chapter 1 in Ink, the Kingdom View in three.js, and now **Kingsbloom: Lantern Market for Roblox**. The Roblox build is complete and tested under a stand-in engine; it's waiting for your playtest in Roblox Studio (Q-16). Newest session first.

---

## Session 4 (2026-09-29): the Roblox build

### What you asked

After playing the three.js Kingdom View you listed what was missing:

1. No sound effects.
2. No sense of achievement when progressing. You could spam building, and nothing felt earned.
3. The menus felt clunky.
4. The camera was stiff: it only turned and zoomed, with no fluid drag.
5. Too few actions: you couldn't jump or hit anything.

You asked for a **Roblox version first, to test the concept**, built "properly playable, pro quality, worth playing for many people". You also asked for this note so you can continue in Claude Code.

### What I built

A complete Rojo project in [`roblox/`](../roblox): about 15,000 lines of Luau, including the tests. [`roblox/README.md`](../roblox/README.md) explains how to open, play and publish it. [`roblox/Kingsbloom.rbxlx`](../roblox/Kingsbloom.rbxlx) is the ready-to-open place file.

| Your point | What the Roblox build does |
|---|---|
| Sound | 28 effects, music playlists for day, night and the Surge that crossfade by time of day, and ambience (birds, wind, night, a crowd that grows with visitors). All are public Roblox, APM and ProSoundEffects uploads found through the Creator Store API |
| Achievement | **XP and 30 levels** with ranks: Exile's Camp → Hamlet (Lv 3) → Village (6) → Town (10) → City (15) → Kingdom (20). A **level-up ceremony** shows rays, confetti and cards for each unlock. **Building limits grow with level**, and **costs rise ×1.12** for each extra building of a kind, so spamming stops paying. There's a **20-step quest chain** with a guide arrow, **3 Royal Orders** every dawn (a Royal Seal for all three), **14 feats** in bronze, silver and gold, a **visitor Codex** with rare and legendary visitors announced to the server, the **Heartflame's 4 tiers** (each pushes the forest back), and the **Night Ledger** every dawn |
| Menus | The "Royal Storybook" UI kit: parchment panels, chunky press-down buttons, counters that count up, toasts, banners. Build mode has a category drawer with cards (cost, lock, "2/3" limit), a tool strip, and a live ghost that turns green, yellow or red and says *why* ("Keep the paths clear", "Needs a path in front") |
| Camera | Build mode's Kingdom View camera: grab-and-drag panning with inertia, right-drag (or two fingers) to turn and tilt, zoom toward the cursor (scroll or pinch), WASD, Q/E, and tilt-shift depth of field. Play mode uses Roblox's own camera |
| Actions | A normal Roblox character: jump, **double jump**, Shift to run. The **Lantern Staff** has a 3-hit combo whose third hit is a lunging finisher, with aim assist. The **Radiant Burst** (Q) clears Gloomlings and relights lamps. You **tend** ripe fields (E), **serve** at a stall (twice as fast, happier customers), and grab tip coins |

**How it plays:**
- Up to 6 players per server, and each gets a clearing along the Royal Avenue.
- By day, visitors trickle in, fields grow and stalls sell.
- At dusk the **Lantern Market** opens: prices rise 25%, visitors come more often, and rarer visitors appear.
- At night the Veil sends **Gloomlings** to snuff lamps and scare visitors. Travelers turn back on dark road. At midnight a **Veil Surge** sends a wave.
- Happy visitors tip and move in when a bed is free. Settlers work fields, the fishery and the Cookhouse at double speed.
- Everything saves to DataStores.

**Architecture:**
- The server is authoritative.
- A pure-Luau plot simulation (`PlotSim`) is shared by the server, the client (for instant placement previews) and the tests.
- 8-byte entity snapshots go out 10 times a second over an UnreliableRemoteEvent.
- Clients draw visitors and Gloomlings from these snapshots, with interpolation and walk cycles.
- Details are in [`CLAUDE.md`](../CLAUDE.md).

### How it was checked (without Roblox Studio)

I can't run Roblox Studio here, so I checked the build four ways:

1. **Unit and pacing tests** (Lune, 34 passing): building rules, the market by day and night, Gloomlings, settlers, saves, snapshots and progression. A **bot** plays 8 in-game days on 3 seeds. It reaches Hamlet on day 1 and Village on days 3.4–3.8, about 25 minutes for a bot that plays well.
2. **Strict type-checking** of every script against the Roblox API (luau-lsp with the Roblox definitions): clean.
3. **A stand-in Roblox engine** ([`roblox/tests/engine`](../roblox/tests/engine)). It runs the real server and client scripts together under Lune, with a simulated clock, signals, remotes, DataStores, tweens and terrain. A scripted player plays two full days: builds, paints paths, claims quests, serves, tends, fights, opens every panel, leaves, and comes back. **36 of 36 checks pass**, with no script errors, no invalid network payloads or saves, and a largest snapshot of 82 bytes.
4. **Visual preview.** Every part of a grown plot and a showcase of all models was dumped and rendered with three.js, then checked by eye.
5. **UI preview.** The client ran at a desktop size (1366×768) and a phone size (844×390, touch), and every screen was dumped and laid out by a small Roblox layout engine in the browser, with Roblox's own top bar, chat, thumbstick and jump button drawn in. 14 screens on each size were checked by eye, and the tool flags any text that overflows its box.

**Bugs this caught before you ever opened Studio:**
- Every gable roof was upside down (a WedgePart is tall at +Z).
- The Heartflame's crown rendered as a solid disc.
- Speech bubbles animated after their visitor had left.
- Gloomlings were deadly for a cozy game. They now deal 6 damage every 1.6 s, and the Heartflame's glow heals you.
- A tuning pass cut day-one XP from 1,700 to about 1,200, cut Gloomlings from about 32 to about 20 a night, fixed settlers never moving in, and made the Cookhouse leave some fish for the stalls.

### The menu and HUD pass

The UI preview showed the menus worked on a desktop but broke on a phone, where most Roblox players are. Fixes:

- **Phone layout.** On a phone the HUD moves to the top edge and the right-hand column, away from the thumbstick. The ⚔️ and ✨ buttons sit just left of Roblox's jump button. Text is a little larger than a plain fit to the screen.
- **Build mode.** The tools stand in a column left of the drawer and one big ✔ Done sits right of it, so nothing covers the chat or the clock. The drawer slides away while you inspect a building. On a phone you **tap a spot to move the ghost, then press ✔ Build here**, so a stray tap never builds by accident.
- **Notifications.** Toasts and cards (quest done, feats, new visitors) share one stack under the clock. A banner takes the top slot and pushes the stack down, so they never overlap.
- **Menus.** Clicking outside a menu closes it. The quest card opens the Journal. Menus never grow taller than the screen; long lists scroll. The level-up screen is one centred column that fits a phone.
- **Bugs found:** the Night Ledger's rows ran under its closing line once a night had ten or more of them; the Build button's caption was cut off; clicks between the Build drawer's cards could build behind it.
- **The mock engine** lost the handlers of buttons whose Lua reference had been dropped (Lune gave a fresh userdata after garbage collection). Signals are now kept for the life of the run.

**Not checked:** real rendering in Roblox, physics, touch input, network latency, and how it *feels*. That's your playtest.

### Decisions

- **D-044:** Roblox build for testing (see [`12`](12_DECISIONS_AND_OPEN_QUESTIONS.md#part-a-decision-log)).
- **Q-16:** the Roblox playtest.

### Next steps

1. **You:** open `roblox/Kingsbloom.rbxlx` in Roblox Studio and press Play, then try Test → Clients and Servers with 2 players. Send me anything from the **Output** window, plus what felt good and what felt off (Q-16).
2. Then: tune numbers from your notes, publish (steps in the README), and invite testers.
3. Ideas that aren't built yet:
   - a "visit a friend's market" list;
   - session locking for saves;
   - more visitor behaviours;
   - trading between players;
   - seasonal events;
   - real art through `ReplicatedStorage.Assets`.

---

## Session 3 (2026-09-29): Oboro no Ichi, and the Kingdom View prototype

- You shared *Oboro no Ichi* (TheLaba) from Threads and asked me to study how it plays. I wrote a breakdown in Indonesian and asked three questions.
- Your answers: a **Hybrid** structure, a **3D diorama** look like Oboro, and a playable prototype first.
- Design Bible **v0.5**: **D-039** (hybrid), **D-040** (3D diorama), **D-041** (the Lantern Market loop), **D-042** (lights follow the road), **D-043** (the Sovereign works in the market). Open questions **Q-14** (engine for 3D; Godot 4 recommended) and **Q-15** (Kingdom View playtest). Docs 01, 03, 07, 08, 10, 11 and 13 were updated.
- **Step 4b:** [`prototypes/kingdom-view`](../prototypes/kingdom-view).
  - Built with three.js as a single self-contained page. The simulation has 15 tests.
  - You build, light the Old Road, run the Lantern Market at night and walk as the Sovereign.
  - The look comes from a Veil tint, bloom and a tilt-shift blur. Sound is generated in the browser.
  - Published at https://claude.ai/artifact/GTpRXVxxp4YN4zBnkQYWfc
- Commit `4d33a39`.

## Session 2 (2026-09-28): the narrative prototype and the art kit

- **Step 4:** [`prototypes/narrative-ch1`](../prototypes/narrative-ch1), a playable Chapter 1 in Ink with a small web engine. Decisions **D-033…D-038** (Ink owns story flags, the game owns numbers; the scene trigger table; Food Stock; Waystones; Rook's Trial; Royal Summons).
- [`art/placeholder`](../art/placeholder): a code-made placeholder art kit and the Asset Atlas.
- Commit `ac05079`.

## Session 1 (2026-09-28): the Design Bible

- **v0.1** (working title *Crownless*): docs 00–13 cover the roadmap, vision, story and world, systems, characters, bestiary, items, buildings, art, audio, asset list, tech, decisions and glossary.
- **v0.2:** illustrated 2D art, Phaser 4 + TypeScript as the engine, a narrative-first roadmap (D-022), and doc 14 (Narrative & Progression).
- **v0.3:** the title is ***Kingsbloom*** (D-025). Ideas from your Grok conversation were merged (**D-026…D-032**): Kael, the two-answer ending, faction standing, hearts giving access, Mira's secret, and the Guardian Echo.
- Commits `89ef96f`, `3533e7e`, `971076e`.

## Still open

| | |
|---|---|
| **Q-13** | Play Chapter 1 (the narrative prototype) |
| **Q-14** | Engine for the 3D direction (Godot 4 recommended) |
| **Q-15** | Play the three.js Kingdom View |
| **Q-16** | Play the Roblox build |
