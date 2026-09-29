# Kingsbloom: Lantern Market (Roblox test build)

A Roblox version of the Kingdom View, built to test the concept with real players ([D-044](../docs/12_DECISIONS_AND_OPEN_QUESTIONS.md#part-a-decision-log)). Up to six Sovereigns share a server, and each claims a clearing in the forest. You build a market on the Old Road and light it against the Veil. By day travelers trickle in. At dusk the **Lantern Market** opens with better prices and more visitors, and the Veil sends **Gloomlings** to snuff your lamps. You fight them with the **Lantern Staff**. Dawn brings the **Night Ledger**, fresh **Royal Orders**, and usually a level-up.

Everything is built from ordinary Parts in code, so nothing has to be uploaded first. The sounds and music are public Roblox, APM and ProSoundEffects uploads.

---

## Play it in Roblox Studio (5 minutes)

1. Download [`Kingsbloom.rbxlx`](Kingsbloom.rbxlx) from this folder.
2. Open **Roblox Studio** → **File → Open from File…** → pick `Kingsbloom.rbxlx`.
3. Press **Play** (F5). To try it with friends, use **Test → Clients and Servers** with 2 or 3 players.
4. Saving only works once the place is published and **Game Settings → Security → Enable Studio Access to API Services** is on. Until then the game still runs, and a notice says saving is off.

## Publish it so other people can play

1. **File → Publish to Roblox** (as a new experience).
2. **Game Settings → Places → Max Players: 6** (one clearing each).
3. **Game Settings → Security → Enable Studio Access to API Services** (for DataStores).
4. **Game Settings → Basic Info**: name, description, genre *Town and City* or *Adventure*. **Permissions → Public** when you're ready.
5. Optional badges: create them in the Creator Hub and put their IDs in [`Config.BADGES`](src/shared/Config.luau).
6. If a sound doesn't play for you, swap its ID in [`Config.SOUNDS`](src/shared/Config.luau). An empty string mutes it.

## Controls

| | Keyboard and mouse | Touch |
|---|---|---|
| Move, jump, run | WASD · Space (press twice to double-jump) · hold Shift | Thumbstick · jump button |
| Swing the Lantern Staff (3-hit combo) | Click | ⚔️ |
| Radiant Burst (clears Gloomlings, relights lamps nearby) | Q | ✨ |
| Tend a ripe field, relight a lamp | E (walk up to it) | Tap the prompt |
| Collect a tip | Walk over it or click it | Walk over it or tap it |
| Build mode | B (or 🔨) | 🔨 |
| In Build: look around | Drag · right-drag to turn and tilt · scroll to zoom · WASD · Q/E | One finger drags · two fingers pinch and turn |
| In Build: place, rotate, remove, cancel | Click · R · X · Esc | Tap a spot, then ✔ Build here (or tap it again) · ↻ · 🧹 · ✖ |
| Journal (quests, Royal Orders, feats, Codex) | J (or 📖, or click the quest card) | 📖 or the quest card |
| Close a menu | Esc, ✖, or click outside it | ✖ or tap outside it |

## How it plays

| | |
|---|---|
| **Your clearing** | A 30×30-tile plot (6 studs a tile) with a Heartflame, a plaza, the Old Road down to the Royal Avenue, and a pond. You start with a stall, a turnip field, a tent, a lamp and 120 gold |
| **Visitors** | Travelers, merchants, farmhands, Lantern Monks, a Wandering Knight, and Veilkin (Mossbun, Puddlepup, Emberkit, the legendary Golden Mossbun). They only walk on the road and on paths. They buy what they want from your stalls, linger near decor and benches, tip when they're happy, and move in when a bed is free |
| **Light and the Veil** | At night, travelers who walk too far in the dark turn back. Lamps (and String Lights and Arches) keep the road lit. Gloomlings come out of the forest to snuff them. The Heartflame's inner glow keeps them away and heals you, and Lumen Towers shoot them |
| **Progress** | XP from everything you do; levels 1–30; ranks Exile's Camp → Hamlet → Village → Town → City → Kingdom. Each level-up shows what it unlocked. Costs rise as you build more of one kind, and some buildings have limits that grow with your level, so every level matters |
| **Goals** | A 20-step quest chain (with a guide arrow), 3 Royal Orders every dawn (finish all 3 for a Royal Seal), 14 feats with bronze, silver and gold tiers, a visitor Codex, and the Heartflame's four tiers, each of which pushes the forest back |
| **Nights** | The midnight **Veil Surge** sends a wave. Defeat it for Lumen. The Night Ledger at dawn sums up the night: visitors, moods, sales, gold, Gloomlings, lamps snuffed, travelers who turned back, who moved in, and what people asked for that you don't sell yet |

The numbers live in [`Config.luau`](src/shared/Config.luau) and [`Catalog.luau`](src/shared/Catalog.luau). They are placeholders tuned with a bot. A bot that plays well reaches **Village (level 6) in about 25 minutes**, so real players should take somewhere between 30 and 50.

## The code

| Folder | In the place | What's there |
|---|---|---|
| [`src/shared`](src/shared) | `ReplicatedStorage.Shared` | **PlotSim** (the whole plot simulation in pure Luau: rules, light, appeal, visitors, stalls, settlers, Gloomlings, saves), **Progress** (XP, quests, orders, feats), **Catalog** and **Config** (content and numbers), **Models** (every building made from Parts), **Grid**, **Layout**, **DayCycle**, **Codec** (8-byte entity snapshots), **Net**, **Palette** |
| [`src/server`](src/server) | `ServerScriptService.Server` | **World** (terrain, avenue, hub, forest, lighting), **PlotService** (claims, simulations at 10 Hz, models, prompts, snapshots, effects, every build request with validation and rate limits), **ProgressService**, **CombatService** (the staff and the burst, hits decided on the server), **DayNight**, **DataService** |
| [`src/client`](src/client) | `StarterPlayerScripts.Client` | **BuildCamera** and **Build** (the Kingdom View), **Entities** and **Actors** (visitors and Gloomlings drawn from snapshots), **WorldFx**, **Combat**, **Guide**, **Sky** (the day and the Veil night), **Audio**, and **UI/** (Theme, HUD, BuildBar, Panels, Ceremony) |
| [`tests`](tests) | — | Lune tests for the simulation and progression, a pacing bot, and [`tests/engine`](tests/engine): a stand-in Roblox engine that runs the real server and client together |

The server owns all the rules: clients only ask. The client keeps a mirror of your plot so the Build ghost can turn green or red at once, and the server checks every request again.

### Tools

[Rojo](https://rojo.space) 7.7, [Lune](https://lune-org.github.io/docs) 0.10, [luau-lsp](https://github.com/JohnnyMorganz/luau-lsp) (for type-checking), and optionally Node for the model preview.

```bash
cd roblox
rojo build default.project.json -o Kingsbloom.rbxlx     # the place file
rojo serve                                               # live-sync into Studio with the Rojo plugin
lune run tests/run.luau                                  # 34 unit and pacing tests
rojo build default.project.json -o tests/engine/Kingsbloom.rbxlx && lune run tests/engine/play.luau
                                                         # plays two days of the real game under the mock engine
lune run tests/report.luau 8 1                           # pacing report: XP by source, moods, sales, per day
rojo sourcemap default.project.json -o sourcemap.json && \
  luau-lsp analyze --platform=roblox --sourcemap=sourcemap.json \
  --definitions=@roblox=<path>/globalTypes.None.d.luau --base-luaurc=.luaurc src
                                                         # strict type-check against the Roblox API
```

**Seeing the models without Studio:** `lune run tests/engine/dump.luau tests/engine/Kingsbloom.rbxlx out.json` writes every part of a grown plot plus a showcase row of all buildings and characters. [`tools/preview`](tools/preview) renders it with three.js (`npm install`, `npm run bundle`, `node build_html.mjs out.json out.html`, `node shot.mjs $PWD/out.html shot.png "view=close"`).

**Seeing the UI without Studio:** `ui_dump.luau` runs the client at a given window size, opens every screen (welcome, HUD, a busy moment with a banner and notifications, Build, Inspect, the Journal tabs, Settings, a level-up, the Night Ledger) and writes the GUI trees. `ui.mjs` lays them out with a small Roblox layout engine (`ui_layout.js`) and `ui_shot.mjs` screenshots them and lists any text that overflows its box. Roblox's own top bar, chat, player list, thumbstick and jump button are drawn as grey shapes, so overlaps show.

```bash
lune run tests/engine/ui_dump.luau tests/engine/Kingsbloom.rbxlx desk.json 1366 768
lune run tests/engine/ui_dump.luau tests/engine/Kingsbloom.rbxlx phone.json 844 390 touch
cd tools/preview
FONTS=<dir with the @fontsource woff2 files> node ui.mjs ../../desk.json out d 1366 768
node ui_shot.mjs out 1366 768                  # writes out/d_*.png
```

### Swapping in real art

Put a Model named after a building's id (for example `lamp`, `stall` or `cottage`) in **ReplicatedStorage → Assets**. It replaces the procedural model. Its pivot must sit at the footprint's centre on the ground, with the front facing +Z. Toolbox models work too, as long as they're anchored.

## What the mock engine caught

These bugs showed up before any Studio run:

- Gable roofs were upside down. A WedgePart is full height at its +Z end.
- The Heartflame's crown rendered as a solid disc.
- Speech bubbles tried to animate after their visitor had left.
- Gloomlings hit too hard for a cozy game. They now deal 6 damage every 1.6 s, and the Heartflame's glow heals you.

The UI preview caught these:

- On a phone the quest card sat under the menu buttons, the market strip sat on the thumbstick, and the combat buttons overlapped the jump button. Phones now get their own layout.
- In Build mode the tool strip covered the Done button and the chat window.
- The Night Ledger's rows ran under its closing line once a night had ten or more of them.
- Notification cards slid in over the quest card, and banners landed on top of toasts. They now share one stack under the clock.
- The Build button's caption was cut off at the bottom of the screen.

What it can't check: real rendering, physics, touch input and the feel of it all. Please report anything from Studio's **Output** window.

## Known limits

- Up to 6 players per server, one plot each. A seventh player can walk around but can't build.
- No session locking on saves yet. Don't play the same account in two servers at once.
- Visitors come in only through the plot's own gate. Settlers idle near their work and go home at night.
- Placeholder art and sounds; nothing is final.
