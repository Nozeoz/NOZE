# Continue on your own computer

How to move the Roblox build from the cloud session to your own computer, play it in Roblox Studio, and keep working on it with Claude Code there. On your computer, Claude Code can work with Studio directly: it can start a playtest, read the Output window, take screenshots, and fix what it finds.

## 1. Get the project

Everything is on the branch **`claude/inspiring-bardeen-cxmi0l`**. The repository's `main` branch still holds only the first README, so the GitHub front page looks empty. Pick one way:

- **With git:**

  ```bash
  git clone -b claude/inspiring-bardeen-cxmi0l https://github.com/Nozeoz/NOZE.git Kingsbloom
  ```

- **Without git:** on [github.com/Nozeoz/NOZE](https://github.com/Nozeoz/NOZE), click the branch menu (it says `main`), choose `claude/inspiring-bardeen-cxmi0l`, then **Code → Download ZIP**, and unzip it.

## 2. Play it in Roblox Studio

1. Open Roblox Studio and sign in.
2. **File → Open from File…**, then choose `roblox/Kingsbloom.rbxlx` in the project folder.
3. Press **Play** (F5). For several players, use **Test → Clients and Servers**.

To see the phone layout, turn on the device emulator (the **Device** button on the **Test** tab) and pick a phone.

Saving progress needs a published place with **Game Settings → Security → Enable Studio Access to API Services** turned on. Without it the game still runs and says saving is off.

## 3. Connect Studio to Claude Code

Roblox Studio has an MCP server built in. It lets Claude Code work with the place you have open ([Roblox's guide](https://create.roblox.com/docs/studio/mcp)).

1. In Studio, open **Assistant**, click **… → Manage MCP Servers**, and turn on **Enable Studio as MCP server**.
2. Open **Quick connect** and turn on **Claude Code**.
3. If Claude Code was already running, restart it.

## 4. Start Claude Code

Open a terminal in the project folder and run `claude`, or open the folder from the Claude desktop app. Claude Code reads [`CLAUDE.md`](../CLAUDE.md) first, so it knows the project. Then paste this:

> Read CLAUDE.md and docs/PROGRESS_LOG.md. Set up this project on my computer: install the tools from rokit.toml with Rokit, install the Rojo plugin for Studio, and start `rojo serve` in `roblox/`. After I click Connect in the Rojo plugin, playtest Kingsbloom through the Roblox Studio MCP: start Play, read the Output, take screenshots, and fix every error you find in `roblox/src`.

Claude Code installs the tools itself. If you'd rather do it by hand:

| | Command |
|---|---|
| Install Rokit on Windows (PowerShell) | `Invoke-RestMethod https://raw.githubusercontent.com/rojo-rbx/rokit/main/scripts/install.ps1 \| Invoke-Expression` |
| Install Rokit on macOS | `curl -sSf https://raw.githubusercontent.com/rojo-rbx/rokit/main/scripts/install.sh \| bash` |
| Install Rojo, Lune and luau-lsp (in the project folder) | `rokit install` |
| Add the Rojo plugin to Studio (then restart Studio) | `rojo plugin install` |
| Start live sync (in `roblox/`) | `rojo serve` |

## 5. Working together

- Keep `rojo serve` running in `roblox/`. In Studio, open the **Plugins** tab → **Rojo** → **Connect**. If Rojo asks to accept its changes, accept them.
- Claude Code changes the files in `roblox/src`, and Rojo copies each change into Studio within a second.
- Claude Code starts and stops playtests, reads the Output and takes screenshots through the Studio MCP.
- Don't edit the synced scripts inside Studio: Rojo overwrites them. Ask Claude Code to change the files instead.
- The files in `roblox/src` are the real source. Save the place in Studio (Ctrl+S) only if you want a `.rbxlx` snapshot.
- Claude Code commits and pushes to the branch as before.
