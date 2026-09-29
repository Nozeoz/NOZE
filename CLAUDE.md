# CLAUDE.md

Working notes for Claude Code sessions on **Kingsbloom** (codename NOZE). Read this first, then [`docs/PROGRESS_LOG.md`](docs/PROGRESS_LOG.md) for the full history.

## The project in one paragraph

Kingsbloom is a cozy game about a fallen Sovereign rebuilding a kingdom: a farming life-sim, dungeon crawler and kingdom builder with creature pacts. It also has a **Kingdom View**, where you build freely and run a lantern-lit night market in a warm 3D diorama look, modeled on *Oboro no Ichi*. This repo holds the Design Bible (`docs/`), three playable prototypes, and a placeholder art kit. The current focus is the **Roblox test build** in [`roblox/`](roblox), which the owner will playtest in Roblox Studio.

## How to work with the owner

- They write casual Indonesian ("gw/lu"). **Reply in casual Indonesian.** All game text, code comments and docs are in **English**.
- They like to see real, finished, playable things. Verify before claiming ("udah dites" means tested). Say plainly what couldn't be checked.
- Reference images and videos are **mood only**: never trace them, ship them or commit them (D-024).
- **Ask before spending their AI credits** (image or video generation connectors).
- Never ask for account passwords. A Roblox Open Cloud API key is a secret: use one only if they create it and choose to share it.
- No pull requests unless they ask. Commit and push to the branch the session names.

## Repository map

| Path | What | State |
|---|---|---|
| `docs/00–14` | The Design Bible, v0.5 (hybrid direction, 3D diorama look) | Living docs; decisions in `docs/12` (D-001…D-044), open questions Q-01…Q-16 |
| `docs/PROGRESS_LOG.md` | What happened in every session, and why | Keep it updated at the end of each session |
| `prototypes/narrative-ch1` | Chapter 1 in Ink, playable in a browser | Waiting for the owner's playtest (Q-13) |
| `prototypes/kingdom-view` | The 3D Kingdom View and Lantern Market in three.js | Waiting for the owner's playtest (Q-15). Their feedback led to the Roblox build |
| `art/placeholder` | Code-made placeholder art kit and the Asset Atlas | Never ships |
| `roblox/` | **Kingsbloom: Lantern Market** for Roblox (Rojo project) | Complete test build; waiting for the owner's Studio playtest (Q-16) |

## The Roblox build (`roblox/`)

Read [`roblox/README.md`](roblox/README.md) for how to play, publish and the controls.

**Layout:**
- `src/shared`: pure logic plus shared helpers. `PlotSim.luau` is the whole plot simulation. `Progress.luau` holds XP, quests, orders and feats. `Catalog.luau` and `Config.luau` hold content and numbers. `Models.luau` builds everything from Parts. `Codec.luau` packs the snapshots.
- `src/server`: `init.server.luau` boots `World`, `DayNight`, `DataService`, `ProgressService`, `PlotService` and `CombatService`.
- `src/client`: `init.client.luau` starts `Sky`, `Entities`, `WorldFx`, `Build` with `BuildCamera`, `Combat`, `Guide`, `Audio`, and `UI/` (`Theme`, `HUD`, `BuildBar`, `Panels`, `Ceremony`).

**Rules of the code:**
- The server is authoritative. Clients send requests through `Remotes.Request` (a RemoteFunction) and `Swing`/`Burst`, and get back `Me` (their own state), `Fx` (batched plot events), `Snap` (8-byte entity snapshots over an UnreliableRemoteEvent; keep them under 900 bytes) and `Notice`.
- Keep `PlotSim`, `Grid`, `Catalog`, `Progress` and `DayCycle` free of Roblox types, so Lune can test them. Shared modules require siblings with `require(script.Parent.X)`; the test runner rewrites these.
- Everything is `--!strict` except `PlotSim.luau` (`--!nonstrict`). Keep `luau-lsp analyze` clean.
- Remote payloads and saves must be valid Roblox data: no mixed tables, no sparse arrays, no NaN or infinity. The mock engine checks this.
- Models are built around the footprint centre on the ground, with the front facing +Z. Light sources are Neon parts named `Glow` with a PointLight named `Light`. **A WedgePart is full height at its +Z end and slopes down to −Z.**
- Don't set Ref properties (`Adornee`, `PrimaryPart`…) to `nil`. Toggle `Enabled` instead: it works in Roblox, and Lune can't clear Refs.
- Tune the game in `Config.luau` and `Catalog.luau`, then check pacing with `lune run tests/report.luau 8 1`.

**Before you push Roblox changes (all must pass):**

```bash
cd roblox
lune run tests/run.luau                                                # 34 unit and pacing tests
rojo build default.project.json -o tests/engine/Kingsbloom.rbxlx && lune run tests/engine/play.luau   # 36 checks
rojo sourcemap default.project.json -o sourcemap.json && luau-lsp analyze --platform=roblox \
  --sourcemap=sourcemap.json --definitions=@roblox=<luau-lsp>/scripts/globalTypes.None.d.luau \
  --base-luaurc=.luaurc src                                            # no output means clean
rojo build default.project.json -o Kingsbloom.rbxlx                    # refresh the committed place file
```

To look at models without Studio, use `tests/engine/dump.luau` with `tools/preview` (see the README). The mock engine is `tests/engine/Engine.luau`: it runs the real scripts under Lune with a simulated clock. If a script uses a Roblox API the mock doesn't have yet, add it there.

**Installing the tools in a cloud container:** GitHub release downloads were blocked (403), but crates.io and `git clone` work.
- `cargo install rojo --version 7.7.0 --locked` and `cargo install lune --locked` (selene installs too, but `selene generate-roblox-std` needs network access that was blocked; luau-lsp's lints cover the gap).
- Build luau-lsp from `git clone --recursive https://github.com/JohnnyMorganz/luau-lsp` with CMake. Remove `-Werror` from its `CMakeLists.txt` for GCC 13, then `make Luau.LanguageServer.CLI`. The Roblox definitions are in its `scripts/globalTypes.None.d.luau`.
- The Roblox API dump is in `git clone https://github.com/MaximumADHD/Roblox-Client-Tracker` (`API-Dump.json`). Use it to check a property or enum before using it.
- The Creator Store search API (`apis.roblox.com/toolbox-service/v2/assets:search`) works without login and is how the sound IDs were found. Asset downloads need a login, so all models are made from Parts.

## The web prototypes

- `prototypes/kingdom-view`: `npm install`, `npm test` (15 tests), `npm run build` (writes `dist/index.html`, self-contained). Published as an Artifact: https://claude.ai/artifact/GTpRXVxxp4YN4zBnkQYWfc
- `prototypes/narrative-ch1`: Ink story plus a small engine; see its README.

## Writing docs

Plain, direct English with short sentences. Keep a table's columns consistent. Put the reasoning behind each decision in `docs/12` (the decision log). Update `docs/PROGRESS_LOG.md` and the README's Status table when something ships.
