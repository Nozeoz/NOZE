# 12 — Decisions & Open Questions

> **TL;DR (v0.5):** Part A logs every design decision with its reasoning and the alternatives considered. Part B lists what only **you** can answer. The title is ***Kingsbloom*** (formal clearance pending), the best ideas from your Grok discussion are merged (D-026 to D-032), and building the playable Chapter 1 prototype added D-033 to D-038. **v0.5:** Kingsbloom becomes a **hybrid** with a **Kingdom View** modeled on *Oboro no Ichi*, in a **3D diorama** look (D-039 to D-043). The engine question is open again (Q-14). **D-044:** a Roblox build to test the concept with real players (Q-16).

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
| **D-025** | **Title: *Kingsbloom*** (codename NOZE). The Kingsbloom is also the in-world royal flower that blooms at Kingdom rank | *Crownless* is already used on Steam; *Kingsbloom* passed a quick search and ties title, lore, and logo together | Crownless, Once a Sovereign, Crownroot, Veilwilds, Seedcrown | **Locked** (formal clearance pending) |
| **D-026** | **Kael joins the cast, replacing Durgan**: the reborn (Oathbound) Blacksmith of the Crown, Ch2, runs the Great Forge | From your Grok discussion: a far stronger story link (your past orders, the Sunblade, the Pale Choir's history) for the same system role; the cast stays at 24 | Adding a 25th Sworn (scope), keeping Durgan | **Locked** |
| **D-027** | **Kael's final choice has two answers that both keep him close** | Your feedback: a max-heart ending that pushes a character away feels like a bad ending. Now a rule for every Sworn: *deeper hearts never mean more distance* | The original "apologise → he grows distant" ending | **Locked** |
| **D-028** | **Renames for clarity:** Caelan → **Lucan**, Mari → **Sol**, Kaida → **Akane** | "Kael", "Caelan", and "Kaida" sounded alike; "Mira" and "Mari" too. Players rely on names | Keeping similar names | Default |
| **D-029** | **Faction Standing** (EA): helping one faction can cool its rivals | From the Grok discussion: relationships as politics; fits the sovereign fantasy | No faction layer | Default |
| **D-030** | **Hearts give access** (secret places, rare-material quests, signature items) plus small quests between heart events | From the Grok discussion; makes every heart level worth it | Hearts that only unlock cutscenes | Default |
| **D-031** | **Mira has a hidden agenda** (selling maps to the Dominion); forgive or expel, and she stays a Sworn either way | NPCs with their own agendas make the world feel political, per the Grok discussion | A plain merchant | Default |
| **D-032** | **Guardian Echo**: a weekly re-fight of a defeated Guardian with modifiers | The Grok discussion's weekly boss-rush beat, built from existing content | New weekly bosses (costly) | Default |
| **D-033** | **Ink owns the story flags; the game owns the numbers**, which Ink reads and changes through `EXTERNAL` functions (`item`, `give`, `stat`, `hearts`…) | The same scripts run in the Step 4 prototype and in the real game (Step 11); writers can change scenes without touching game code | Everything in Ink (hard to port); everything in code (writers blocked) | Default |
| **D-034** | **The game decides when a scene plays; the Ink decides what happens** (a trigger table in data) | Quest timing depends on days, buildings and flags, and must be testable; the Ink stays readable | An Ink-driven day loop | Default |
| **D-035** | **The Food Stock starts at the Founding**, and the Longhouse larder holds 20 until the Old Granary is restored | Rook's Trial needs 28 rations, so it pulls you into restoring the Granary (MQ-110): two quests that help each other | Unlimited storage from day 1 | Prototype default; tune in Step 10 |
| **D-036** | **Sunken Cellars Waystones on floors 3, 5, 8 and 10** in the prototype ([03](03_GAMEPLAY_SYSTEMS.md) says every 5 floors) | One dive fills one part of the day; three-floor dives keep the story moving | Every fifth floor | Prototype only; revisit in grey-box 3 (Step 8) |
| **D-037** | **Rook's Trial has a soft deadline**: on time, the gang joins at once and Rook starts a heart higher; late, they stay until you reach 28 | Keeps the pressure without breaking the no-missable-Sworn rule ([14 §1](14_NARRATIVE_AND_PROGRESSION.md#1-narrative-design-principles)) | A hard fail that sends the gang away | Default |
| **D-038** | **Royal Summons from Hamlet rank** (15 Royal Authority brings a settler at the next dawn) | In bot runs the Banish path's slower arrivals stalled Village rank for about 20 days; Summons ([03 §15.1](03_GAMEPLAY_SYSTEMS.md#151-royal-authority-ra)) gives the player an active answer | Waiting; raising the arrival rate | Default |
| **D-039** | **Hybrid structure:** the Sovereign's life-sim stays (walk, farm, dive, fight, befriend), and a **Kingdom View** is added: a free camera over the realm where you build freely and run the **Lantern Market** at night, modeled on *Oboro no Ichi* ([01 §7](01_VISION.md#oboro-no-ichi-cozy-spirit-market-builder-thelaba-early-access-q4-2026)) | Your choice after studying the reference (Sept 2026). Its loop is simple, calm and pretty; Kingsbloom already has what it lacks (story, characters, goals), and light against the Veil gives the market an edge | A full pivot to a god-view builder (smaller scope, loses the personal verbs); borrowing a few features only | **Locked** |
| **D-040** | **3D diorama look** replaces illustrated 2D (D-002): low-poly 3D, warm lantern light against the night Veil, a tilt-shift miniature blur, a free camera in Kingdom View and a close camera when walking. Palette ([08 §6](08_ART_DIRECTION.md#6-palette)), Veil language ([08 §8](08_ART_DIRECTION.md#8-the-veil-visual-language)) and the Royal Storybook UI carry over | Your choice. The reference's charm comes from real 3D lighting, and a building game with a turning camera suits 3D | Keep illustrated 2D (my suggestion at the time: cheaper, more distinct); decide after the prototype | **Locked.** Reopens D-001 and D-003 (see Q-14); docs 08, 10 and 11 get rewritten after the Kingdom View playtest |
| **D-041** | **The Lantern Market loop** (prototype rules): by day you build and the realm produces; at dusk you open the market; visitors walk the Old Road and **turn back on dark stretches**; each stall sells one kind of goods from the shared stores, and upgrades raise price and speed; **Appeal** (decor near paths, variety, light, Sworn stalls) sets how many come; happy visitors tip and **ask to settle if a bed is free**; settlers staff production | Makes every building feed the night: production fills the stores, lights bring people in, decor keeps them, beds keep them for good | Timed business hours with no choice; money as the only reward | Prototype default; tune after your playtest (Q-15) |
| **D-042** | **Lights follow the road, not the realm:** Lantern Posts and String Lights can stand beside any road, even outside the realm; everything else is built inside the Heartflame's reach | Lighting the forest road is the first lesson, and the road runs outside the first realm | Lights only inside the realm (the road could never be lit) | Prototype default |
| **D-043** | **The Sovereign works in the same world as the market:** tend a field (+3, once a day), talk to the Sworn, **serve at a stall** (twice as fast, happier customers), and carry Flicker's light, which keeps nearby visitors brave | The hybrid's link: personal verbs matter inside the management layer, so walking is never wasted time | Walking as a separate mode with no effect on the market | Prototype default |
| **D-044** | **A Roblox build to test the concept with players** ([`roblox/`](../roblox)): *Kingsbloom: Lantern Market*, up to 6 Sovereigns per server with one clearing each. It adds what the three.js prototype lacked: sound, levels and ranks with unlock ceremonies, quests, daily Royal Orders, feats, rising costs and level-based building limits, a fluid Build camera, and real action (jump, the Lantern Staff combo, the Radiant Burst, Gloomlings that snuff lamps) | Your choice after the Kingdom View playtest. Roblox gives instant multiplayer, an audience, free hosting and saves, and a character that can already walk, jump and fight | Keep iterating on the three.js prototype; go straight to Godot | Test build. Findings feed the engine choice (Q-14) and the main game's Kingdom View |

---

## Part B: Open questions for you

### Q-01: Title

**Answered: *Kingsbloom*** (D-025). *Crownless* was already used by several games, including one on Steam ([Crownless](https://store.steampowered.com/app/4484760/Crownless/), [Crownless Abyss](https://store.steampowered.com/app/2440030/Crownless_Abyss/)).

**Clearance checklist** (before the Steam page, Step 17): Indonesia's trademark database (**PDKI**, run by DJKI) · USPTO · EUIPO or WIPO's Global Brand Database · Steam store search · a domain · social handles · consider filing in classes **9** (software) and **41** (entertainment). A trademark consultant or lawyer should do the final clearance.

### Other questions

| ID | Question | Status / default |
|---|---|---|
| **Q-02** | Who makes the art? | **Answered:** you'll hire an artist. **v0.5:** now a 3D artist for the diorama look (D-040). Until then I build placeholders in code ([08 §17](08_ART_DIRECTION.md#17-prototype-placeholder-kit), [`prototypes/kingdom-view`](../prototypes/kingdom-view)) |
| **Q-03** | Platforms? | Default: PC (Steam) first; the web build keeps mobile possible; consoles after 1.0 |
| **Q-04** | Tone? | **Answered:** 70/30 (D-021) |
| **Q-05** | Protagonist: fixed King, or player-chosen King/Queen/Monarch? | Default: player-chosen (wider audience); marketing art can still show a King |
| **Q-06** | Engine? | Answered with my recommendation (D-001), **reopened** by the 3D direction (D-040): see Q-14 |
| **Q-07** | Team & timeline? | **Answered:** just us two for now; finish self-completable prototypes first (D-022) |
| **Q-08** | Scope OK (24 Sworn / 60 creature forms / 6 regions at 1.0)? | Default: keep; the Vertical Slice gate protects us |
| **Q-09** | Combat feel target? | Default: Rune Factory-medium + Perfect Dodge |
| **Q-10** | Your Grok conversation | **Merged** (D-026 to D-032): Kael, the two-answer ending, relationship-as-politics, weekly rhythm, found lore |
| **Q-11** | Step 3 review | Treated as approved ("lanjut next step"); the playable narrative prototype (Step 4) is built from it |
| **Q-12** | Kael as a romance option? | Default: **no** (his arc is about trust and duty, and the romance count stays at 12). Say so if you want him romanceable |
| **Q-13** | Step 4 playtest | **Open:** play Chapter 1 ([`prototypes/narrative-ch1`](../prototypes/narrative-ch1)) and tell me: is each person's purpose clear, is the pace right, does sparing or banishing Rook matter, would you play one more day? |
| **Q-14** | Engine for the 3D direction? | **Open.** Options: **Godot 4** (free and open source, good 3D, exports to web and desktop; my recommendation), **Unity** (the most mature 3D tools; licence terms to watch), **three.js** (what the prototype uses; great in the browser, but we'd build our own editor tools). Default: decide after the Kingdom View playtest |
| **Q-15** | Kingdom View playtest | **Open:** play [`prototypes/kingdom-view`](../prototypes/kingdom-view) and tell me: is build, open the market, watch, improve fun? Does lighting the road feel like a real choice? Does walking as the Sovereign add something? Does the 3D look match what you want? |
| **Q-16** | Roblox playtest | **Open:** open [`roblox/Kingsbloom.rbxlx`](../roblox/Kingsbloom.rbxlx) in Roblox Studio and press Play (and try 2 players with Test → Clients and Servers). Tell me: does progress feel earned now, do the Build camera and menus feel smooth, is the night fight fun or annoying, and send anything that appears in the Output window |
