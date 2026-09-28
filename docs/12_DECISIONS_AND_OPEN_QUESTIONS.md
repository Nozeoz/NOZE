# 12 — Decisions & Open Questions

> **TL;DR (v0.2):** Part A logs every design decision with its reasoning and the alternatives considered. Part B lists what only **you** can answer. After Step 2: tone, team, art direction, and engine are **Locked**; the title is **open again** because *Crownless* is already used on Steam.

**Status:** **Locked** = you approved it · **Default** = my call as lead designer; it stands unless you object · **Revisit** = re-check after a playtest or gate.

---

## Part A: Decision log

| ID | Decision | Why | Alternatives considered | Status |
|---|---|---|---|---|
| **D-001** | **Engine: Phaser 4 + TypeScript, web-first; Spine for character animation; Electron for Steam** | You review by playing browser links, nothing to install; official Spine runtime for Phaser 4 supports the HD art; Tiled gives a visual map editor. Full comparison in [11 §1](11_TECHNICAL_DESIGN.md#1-engine-decision) | Godot 4 (second choice: great free editor, heavier to share builds from our workflow), Unity, GameMaker | **Locked** (re-check at the VS gate, Step 16) |
| **D-002** | **Hand-drawn illustrated 2D** (coloured line art, soft cel shading, sunny storybook palette, dense lived-in props), chibi-anime characters, HD layered portraits; authored at 2×, 64 px grid at 1080p | Your two mood references. Replaces v0.1's pixel-art proposal | Pixel art (v0.1 proposal), 3D | **Locked** |
| **D-003** | **One top-down 3/4 projection for everything** | Matches Ref A; Ref B's converging "battle-map" walls can't work with a scrolling camera, so we keep its palette and clutter but not its projection | True top-down, isometric | **Locked** |
| **D-004** | **Prefab buildings with upgrades**, not free-form wall-by-wall rooms | Reads far better in a 3/4 illustrated view; far less pathfinding and roof complexity; cozy players prefer it | Dungeon Settlers-style free room design (kept as a possible post-1.0 "castle interior" mode) | Default |
| **D-005** | **Real-time action combat + Command Mode** (slow-time orders) | Farming-sim players expect direct control; Command Mode keeps Dungeon Settlers' tactical party idea | Full real-time-with-pause party combat | Default |
| **D-006** | **Survival = positive-food Satiety + Exposure (light vs. Veil)**, following the Frontier Principle | Tension without chores; survival lives at the frontier, home becomes safe | Classic hunger/thirst/temperature meters | Default |
| **D-007** | **No multiplayer for 1.0** | Multiplayer multiplies the cost of every system | Co-op at launch | Default |
| **D-008** | **Defeated creatures dissolve into mist**; no meat from creatures | Keeps familiars emotionally consistent; cozy-safe; E10+/T rating | Palworld-style harvesting | Default |
| **D-009** | **12 romance options, available whatever the player's gender** | Genre expectation; widest audience | Gender-locked romance | Default |
| **D-010** | **English at launch; every string key-based** | Your request; localisation later (e.g. Bahasa Indonesia) costs little | — | **Locked** |
| **D-011** | **Premium, one-time price; no microtransactions** | Genre norm; trust with cozy players | Free-to-play | Default |
| **D-012** | **Two-tier people: 24 hand-made Sworn + generated Settlers** | Suikoden-style heroes plus colony-sim scale without 90 bespoke portraits | All hand-made, all generated | Default |
| **D-013** | **28-day seasons, day 06:00–02:00, ~14 real minutes per day** | Proven pacing | Shorter seasons | Default |
| **D-014** | **Naming → Ascension for every familiar; True Ascension (new art) for 17 species** | The Tensura hook without doubling the creature art budget | Full evolutions for every species | Default |
| **D-015** | **No deaths in normal play**: knockouts, injuries, settlers leaving instead | Cozy promise; the endings carry the stakes | Permadeath | Default |
| **D-016** | **Save on sleep + one suspend save** | The day is the unit of play | Save anywhere | Default |
| **D-017** | **Ink for dialogue** | Industry-proven narrative scripting; writer-friendly; the Step 4 prototype scripts carry straight into the game | Custom JSON dialogue | Default |
| **D-018** | **Tiled for maps and dungeon room chunks** (props placed freely on object layers) | Industry standard; lets the artist and you dress maps by hand | LDtk | Default |
| **D-019** | **Open daily life inside chapters gated by Regalia + Waybeacons** | Life-sim freedom with story pacing | Linear story, or no gates | Default |
| **D-020** | **The 12 romanceable Sworn are also the companion-capable party members** | One combat animation set serves both romance and dungeon party | All 24 Sworn as companions | Default |
| **D-021** | **Tone: ~70% cozy / 30% dark mystery** | Your answer in Step 2 | Cozier (Mistria) or darker (Dungeon Settlers) | **Locked** |
| **D-022** | **Narrative-first pre-production**: lore, NPC purposes, progression, and a playable Ink prototype before the tech foundation | Your direction: finish everything the two of us can complete before hiring | Tech first | **Locked** |
| **D-023** | **Wisplings**: ambient white spirit critters whose numbers mirror kingdom happiness | Brings the life of Ref A into a system; a glanceable health bar for the realm | Pure decoration | Default |
| **D-024** | **References are mood-only**: never traced, shipped, or committed to the repo | Copyright; Ref B is credited to the artist Mimosa20 | — | **Locked** |

---

## Part B: Open questions for you

### Q-01: Title (open again)

**Finding:** *Crownless* is **already in use**, so I recommend not using it:
- a game called **[Crownless on Steam](https://store.steampowered.com/app/4484760/Crownless/)**,
- **[Crownless Abyss](https://store.steampowered.com/app/2440030/Crownless_Abyss/)** (also on Steam),
- a mobile game **[Crownless by Tealmobile Games](https://tealmobile.com/crownless)**,
- **[Songs of Silence – Crownless King Expansion](https://store.steampowered.com/app/4561030/Songs_of_Silence__Crownless_King_Expansion/)**,
- a tabletop RPG, **[THE CROWNLESS](https://marrensmusings.itch.io/the-crownless)**.

Launching with the same name on the same store means buried search results, player confusion, and a real risk of a trademark dispute.

**Shortlist** (quick web search only, not a legal clearance):

| Title | Meaning | Quick search result | My take |
|---|---|---|---|
| **Kingsbloom** | "The king's flower blooms again": royalty + farming + regrowth | No game, app, or brand found | ⭐ **Recommended.** It can also be the in-world name of the extinct royal flower you re-grow (today's "Halcyon Rose"): *"the Kingsbloom only flowers under a true sovereign."* Fits the broken-crown-with-a-sprout logo |
| **Once a Sovereign** | The premise in three words | No exact match; "The Sovereign" and "The Last Sovereign" exist | Good, but reads more like a tagline |
| **Crownroot** | Crown + root (in botany, a plant's crown is where root meets stem) | No game found; similar trademarks "CROWN ROOTS" / "CRWN ROOTZ" exist | Nice meaning; some confusion risk |
| **Veilwilds** | Our world's name | No exact match; "VeilWood" and "VEIL" exist | Moody, but "Veil" is crowded |
| **Seedcrown** | Seed + crown | "Seed Crown®" is a registered gardening product | Clashes in search |

**Next step once you pick:** check Indonesia's official trademark database (**PDKI**, run by DJKI), plus USPTO, EUIPO or WIPO's Global Brand Database, the Steam store, a domain, and social handles. Consider filing a trademark in classes **9** (software) and **41** (entertainment) before the Steam page goes live. For certainty, a trademark consultant or lawyer should do the final clearance.

### Other questions

| ID | Question | Status / default |
|---|---|---|
| **Q-02** | Who makes the art? | **Answered:** you'll hire an artist, illustrated style per your references. Until then I build an in-house placeholder kit ([08 §17](08_ART_DIRECTION.md#17-prototype-placeholder-kit)) |
| **Q-03** | Platforms? | Default: PC (Steam) first; the web build keeps mobile possible; consoles after 1.0 |
| **Q-04** | Tone? | **Answered:** 70/30 (D-021) |
| **Q-05** | Protagonist: fixed King, or player-chosen King/Queen/Monarch? | Default: player-chosen (wider audience); marketing art can still show a King |
| **Q-06** | Engine? | **Answered** with my recommendation (D-001). Say so if you'd rather edit visually in Godot yourself |
| **Q-07** | Team & timeline? | **Answered:** just us two for now; finish self-completable prototypes first (D-022) |
| **Q-08** | Scope OK (24 Sworn / 60 creature forms / 6 regions at 1.0)? | Default: keep; the Vertical Slice gate protects us |
| **Q-09** | Combat feel target? | Default: Rune Factory-medium + Perfect Dodge |
| **Q-10** | Your Grok conversation | The share link can't be opened from our environment. Please **paste the text** into the chat and I'll merge the good ideas into the Design Bible |
| **Q-11** | Step 3 review | Read [`14_NARRATIVE_AND_PROGRESSION.md`](14_NARRATIVE_AND_PROGRESSION.md) and tell me what to change before I build the playable narrative prototype (Step 4) |
