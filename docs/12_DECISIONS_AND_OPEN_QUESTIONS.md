# 12 — Decisions & Open Questions

> **TL;DR:** Part A lists the design decisions I made as your lead designer, each with its reasoning and the alternatives considered. They're **Proposed** until you approve them in Step 2 (Review & Lock). Part B lists the questions only **you** can answer, the ones that change the plan.

Status: **Proposed** (awaiting your review) · **Locked** (approved) · **Revisit** (to re-check after a playtest).

---

## Part A: Decision log

| ID | Decision | Why | Alternatives considered | Status |
|---|---|---|---|---|
| **D-001** | **Engine: Phaser 4 + TypeScript, web-first**; Electron for Steam | You can play every step from a browser link (PC or phone); code-first workflow suits our collaboration; proven web-to-Steam path | Godot 4 (great editor, harder to share builds here), Unity (heavy), GameMaker (proprietary) | Proposed |
| **D-002** | **Anime-inspired pixel art**, 16 px tiles, 480×270 reference at ×4 | The genre's proven look (farming sims); cheaper to animate than HD; portraits carry the anime feel | HD hand-drawn 2D (much higher cost per animation), 3D chibi (a different skill set) | Proposed |
| **D-003** | **Top-down 3/4 perspective** | Genre standard; readable for farming grids and building placement | Isometric (costly art, harder grid readability) | Proposed |
| **D-004** | **Prefab buildings with upgrades**, not free-form wall-by-wall rooms | Reads far better in 3/4 pixel art; much less pathfinding and roof complexity; cozy players prefer it | Dungeon Settlers-style free room design (kept for a possible post-1.0 "castle interior" mode) | Proposed |
| **D-005** | **Real-time action combat + Command Mode** (slow-time orders) | Farming-sim players expect direct control; Command Mode keeps the tactical party idea of Dungeon Settlers | Full real-time-with-pause party combat | Proposed |
| **D-006** | **Survival = positive-food Satiety + Exposure (light vs. Veil)**, following the Frontier Principle | Keeps tension without chores; survival lives at the frontier, home becomes safe | Classic hunger/thirst/temperature meters (tested poorly with cozy audiences) | Proposed |
| **D-007** | **No multiplayer for 1.0** | Multiplayer multiplies the cost of every system; the state model stays host-friendly for possible later co-op | Co-op at launch | Proposed |
| **D-008** | **Defeated creatures dissolve into mist**; no meat from creatures | Keeps pacts and familiars emotionally consistent; cozy-safe; E10+/T rating | Palworld-style harvesting (tonal clash) | Proposed |
| **D-009** | **12 romance options, available whatever the player's gender** | Genre expectation; widest audience | Gender-locked romance | Proposed |
| **D-010** | **English at launch; every string key-based** | Your request; localisation later (e.g. Bahasa Indonesia) costs little | — | Proposed |
| **D-011** | **Premium, one-time price; no microtransactions** | Genre norm; trust with cozy players | Free-to-play (wrong genre fit) | Proposed |
| **D-012** | **Two-tier people: 24 hand-made Sworn + generated Settlers** | Suikoden-style heroes plus colony-sim scale without 90 bespoke portraits | All-handmade (unaffordable), all-generated (soulless) | Proposed |
| **D-013** | **28-day seasons, day 06:00–02:00, ~14 real minutes per day** | Proven pacing; players already know it | Shorter seasons (less room for planning) | Proposed |
| **D-014** | **Naming → Ascension for every familiar; True Ascension (new sprite) for 17 species** | The Tensura hook without doubling the creature art budget | Full evolutions for all species | Proposed |
| **D-015** | **No deaths in normal play**: knockouts, injuries, and settlers leaving instead | Cozy promise; the endings carry the stakes | Permadeath (Exile mode only has harsher losses, not deaths) | Proposed |
| **D-016** | **Save on sleep + one suspend save** | The day is the unit of play; prevents save-scumming while respecting real life | Save anywhere | Proposed |
| **D-017** | **Ink for dialogue** | Industry-proven narrative scripting; writer-friendly; variables bind to game state | Custom JSON dialogue (painful at scale) | Proposed |
| **D-018** | **Tiled for maps and dungeon room chunks** | Industry standard; native Phaser support | LDtk (excellent, less direct Phaser support) | Proposed |
| **D-019** | **Open daily life inside chapters gated by Regalia + Waybeacons** | Freedom of a life-sim with story pacing; the gates tie exploration to building | Linear story, or no story gates | Proposed |
| **D-020** | **Twelve romanceable Sworn are also the companion-capable party members** | One set of combat animations serves both romance and dungeon party | All 24 Sworn as companions (combat art for everyone) | Proposed |

---

## Part B: Open questions for you

Answer in any order, even with short replies like "Q-01: Crownless OK".

| ID | Question | Options | My recommendation |
|---|---|---|---|
| **Q-01** | **Game title?** | *Crownless* · *Once & Future Sovereign* · *Heartflame Kingdom* · *Veilborn Realm* · or **NOZE** as the real title | *Crownless* (short, memorable, says the premise). Needs a trademark and Steam name search before we commit |
| **Q-02** | **Who makes the art?** This changes budget and timeline the most. | (a) You draw · (b) hire pixel artists (portfolios on X, ArtStation, Fiverr) · (c) licensed asset packs for the prototype, commission later · (d) AI-assisted concepts only | (c) now, then (b) from the Art Style Test. Note: Steam requires disclosing AI-generated content, and cozy and pixel-art communities often react badly to AI-made final art |
| **Q-03** | **Platforms?** | PC (Steam) · + mobile · + consoles | PC first; the web build keeps mobile possible; consoles after 1.0 |
| **Q-04** | **Tone?** | Cozier (Mistria) ↔ darker (Dungeon Settlers) | Current mix: 70% cozy / 30% dark mystery |
| **Q-05** | **Protagonist?** | Fixed male King · player-chosen King/Queen/Monarch | Player-chosen (wider audience); marketing art can still show a King |
| **Q-06** | **Engine OK?** | Web-first Phaser · Godot (if you want to edit scenes visually yourself) | Phaser, unless you want hands-on editor work |
| **Q-07** | **Team & timeline?** | Just you and me · a small team · any deadline (e.g. a Steam Next Fest)? | Tell me and I'll size the milestones to it |
| **Q-08** | **Scope OK?** | 24 Sworn / 60 creature forms / 6 regions at 1.0, or smaller | Keep it, since the Vertical Slice gate protects us |
| **Q-09** | **Combat feel target?** | Stardew-light · Rune Factory-medium · Hades-like | Rune Factory-medium plus the Perfect Dodge for skill expression |
| **Q-10** | **Any must-have ideas I missed?** | Mounts earlier? Children? Pets? Co-op? A specific anime reference? | — |

Once these are answered, I'll update the Design Bible to **v0.2**, mark the decisions **Locked**, and start **Step 3: Tech Foundation**.
