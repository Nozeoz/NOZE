# 08 — Art Direction

> **TL;DR:** **Warm, anime-inspired pixel art** in a top-down 3/4 view. 16 px tiles, small expressive sprites, and large detailed **pixel portraits** that carry the anime emotion (the classic farming-sim formula). The visual story of the game is **light vs. the Veil**: colour, warmth, and life spread wherever your kingdom's light reaches.

---

## 1. Visual pillars

| Pillar | Means | Test |
|---|---|---|
| **Warm Anime Pixel** | Soft saturated palettes, expressive faces, gentle shading, cozy lighting | Does a screenshot feel like a frame from a slice-of-life anime? |
| **Readable First** | Clear silhouettes, walkable vs. blocked contrast, telegraphs that pop | Can you read it at phone size in 1 second? |
| **Light vs. Veil** | Colour and saturation live in the light; the Veil desaturates and tints violet-teal | Can you see the Realm's border at night without a UI overlay? |
| **The Kingdom Grows Visibly** | Every rank changes the skyline, props, lights, and crowd density | Would a before/after GIF of the town impress on social media? |

---

## 2. Mood references (for feel only, never to copy)

- **Fields of Mistria, Stardew Valley:** cozy pixel farming, portrait-driven emotion.
- **Eastward, Sea of Stars, CrossCode:** high-craft pixel environments, lighting, animation.
- **Studio Ghibli backgrounds** (*Nausicaä*, *Howl's Moving Castle*): lush nature overtaking ruins.
- ***Frieren*** **colour script:** soft pastel skies, melancholy golden hours.
- ***Tensura*** **/ monster-nation anime:** cute creatures becoming a nation.
- **Rune Factory portraits:** clean anime faces with strong expressions.

---

## 3. Camera, perspective & grid

| Spec | Value |
|---|---|
| Perspective | Top-down 3/4 ("JRPG oblique"): fronts of objects visible, tops foreshortened |
| Tile size | **16 × 16 px** |
| Reference view | **480 × 270** game pixels shown at **×4 = 1920×1080** |
| Scaling | Integer scaling only (×2 / ×3 / ×4 / ×6 / ×8), nearest-neighbour, no sub-pixel jitter |
| Gameplay view | ~30 × 17 tiles |
| Build mode | Zooms out to ×2 (~60 × 34 tiles) |
| Light direction | Sun from the **top-left**; cast shadows fall bottom-right at a fixed angle |
| Depth sorting | By the Y of each sprite's "feet" pivot |

---

## 4. Scale chart

| Thing | Size (px) | Notes |
|---|---|---|
| Tile | 16 × 16 | |
| Humanoid body | ~16 × 32 visible | Drawn in a **32 × 48 frame** (headroom for hair, hats, ears, weapon arcs). Pivot: bottom-centre |
| Halfling / gnome | ~14 × 24 | Same frame |
| Dwarf | ~18 × 28 | Same frame |
| Creature S | 32 × 32 frame | Most creatures |
| Creature M | 48 × 48 frame | Wolves, sheep, deer |
| Creature L | 64 × 64 frame | Mammoss, mounts |
| Bosses | 96–192 frame | Guardians |
| Door | 16–32 wide × 32 tall | Characters are ~2 tiles tall |
| Tent / Hut / Cottage | 2×2 / 3×3 / 4×4 tiles | Plus height (roofs overlap tiles above) |
| Castle / Palace | 12×10 / 16×12 tiles | |
| Item icon | **16 × 16** | 1 px dark outline for inventory readability |
| Portrait | **128 × 128** bust-up | Shown at ×3 (384 px at 1080p) |
| Flicker | 16 × 16 | Floats ~10 px above the ground |

---

## 5. Characters

- **Proportions:** chibi-leaning, ~2.5 heads tall on the sprite; big head, readable hair shapes.
- **Faces at sprite size:** eyes 1×2 px with a highlight pixel; emotion is carried by pose + emote bubbles. Full emotion lives in **portraits**.
- **Hair = silhouette.** Hair and headgear are the main identifiers at sprite size (see the cast rules in [04 §9](04_CHARACTERS.md#9-character-design-rules)).
- **Outlines:** characters and creatures use a **1 px coloured (darker-hue) outline**, never pure black, with selective lightening on lit edges. Tiles have **no outlines**.
- **Paper-doll system (player and settlers):**
  - Body, legs, and arms animate **per frame**.
  - Head-attached layers (**hair, eyes, hats, accessories**) are drawn **once per direction** and positioned by a **per-frame head-offset table**.
  - Tops are drawn per direction (neutral + action pose), bottoms per frame (limited set).
  - Colours come from **palette ramps** (skin, hair, cloth) swapped by shader.
  - This keeps each new hairstyle to ~6 drawings instead of ~300. It's the key cost-saver for customization.

### Portraits
- Bust-up, **128 × 128**, anime style: large eyes with 2 highlights, 2–3 tone cel shading, coloured line art.
- **Built in layers:** base head + eyes / brows / mouth / blush swaps, so 8 expressions cost far less than 8 full drawings.
- Optional (EA): 2-frame **blink** + 2-frame **mouth flap** while talking, for a visual-novel feel.
- Transparent background; a subtle rim light in the character's signature colour.

---

## 6. Palette

- **One master palette** of ~64 colours, organised in **hue-shifted ramps** (shadows shift toward blue/violet, highlights toward yellow/warm).
- **Starting point:** a well-known open pixel palette (e.g. *Resurrect 64* on Lospec), then customised into a project palette ("NOZE-64") during the Art Style Test.
- **Reserved colours** (never used for anything else):
  - **Veil:** violet `#6B4FD8` → teal `#3FD6C6` gradient
  - **Heartflame / Lumen:** gold `#FFC94A` → cream `#FFF3C4`
  - **Enemy telegraph:** warning red-orange `#FF5A3C`
- **Region colour keys:**

| Region | Key colours |
|---|---|
| Dawnmere Vale | Fresh greens, warm golds, sky blue, dawn pink |
| Whisperwood | Deep teal-greens, mushroom magenta, firefly yellow |
| Saltglass Coast | Turquoise, sand cream, glass-sparkle white, coral |
| Cinderpeak | Charcoal, ember orange, obsidian purple-black, hot-spring aqua |
| Frostveil | Ice blue, white, aurora green-violet, night navy |
| The Hollow Crown | Desaturated gold, ash grey, Veil violet-teal |

(Hex values above are placeholders until the Art Style Test locks the palette.)

---

## 7. Lighting & time of day

- **Colour grading per phase** (LUT or tint + saturation): Dawn (pink-gold) → Day (neutral) → Dusk (orange-violet) → Night (deep blue, low saturation).
- **Point lights:** campfires, lamps, windows, Flicker, glowing creatures (additive light sprites with soft pixel falloff).
- **Shadows:** a blob shadow under characters and creatures; hand-drawn cast shadows for buildings and trees at the fixed sun angle.
- **Weather overlays:** rain streaks + splashes, snowfall, fog layers, storm flashes; seasonal particles (petals, leaves, fireflies).

---

## 8. The Veil: visual language

| Element | Spec |
|---|---|
| Veil fog | 3 parallax layers of scrolling noise, violet-teal, alpha-dithered edges (no smooth gradients) |
| Light border | A **dithered transition band** where light meets the Veil |
| Outside the light | −40% saturation, violet tint, floating motes |
| Veil Wall | Dense animated fog curtain with tendrils; impassable |
| Veil-choked land | Purple-grey soil tiles, Veil Bramble, crystal nodes |
| **Hollowed shader** | Desaturate 60% → violet-teal rim light → eyes replaced with glowing white → trailing mist particles |
| Purification | Golden burst + a **colour-restore wave** (saturation returns from the centre outward) |
| Exposure feedback | Screen-edge vignette in Veil colours; at 70+, subtle wobble distortion (off with reduced motion) |

---

## 9. Seasons

- Separate **seasonal variants** of ground, foliage, and trees for the overworld (Spring, Summer, Autumn, Winter).
- Winter uses **snow-cap overlays** on roofs, trees, and fences instead of redrawing everything.
- Cherry trees get a **blossom** state (Spring) that drops petal particles.

---

## 10. Environment rules

1. **Clusters, not noise:** textures use pixel clusters; never single-pixel dithering noise on large areas.
2. **Walkable is quieter than blocked:** ground tiles are low-contrast; obstacles have stronger values and shadows.
3. **Interactables get a highlight:** forage, ore, and harvestable crops have a 1-pixel light edge or a subtle shimmer.
4. **Ruins everywhere:** broken Halcyon architecture (sun sigils, white stone, gold trim) appears in every region, a visual breadcrumb for the mystery.
5. **Terrain transitions:** Tiled corner-based Wang sets (16 tiles per terrain pair) plus 2–4 variants of each full tile.

---

## 11. UI art direction: "Royal Storybook"

- **Materials:** parchment cards, deep navy panels, gold filigree trim, wax-seal accents for royal actions (Decrees, Court Day).
- **Components:** 9-slice panels, clear button states (normal / hover / pressed / disabled / focused), large touch-friendly targets.
- **Icons:** 16 × 16, 1 px dark outline, consistent top-left lighting.
- **Colour-blind safety:** elements, quality, and statuses always pair colour with a **shape**.
- **Motion:** quick, soft tweens (120–200 ms); a small bounce on success; nothing blocks input for more than 300 ms.
- **Fonts:** a readable pixel body font (with Latin Extended, for future localisation), a royal pixel-serif for headings, bold numerals for damage and gold.

---

## 12. Animation standards

**Directions:** D (down), U (up), S (side, mirrored for left/right) = 3 drawn directions.

### Player

| Animation | Frames | Directions | FPS |
|---|---|---|---|
| Idle | 4 | D/U/S | 6 |
| Walk | 6 | D/U/S | 10 |
| Run | 6 | D/U/S | 12 |
| Tool swing (hoe, axe, pickaxe share the body motion) | 5 | D/U/S | 12 |
| Watering | 4 | D/U/S | 8 |
| Sickle sweep | 4 | D/U/S | 12 |
| Attack combo ×3 (per weapon family) | 4 each | D/U/S | 14 |
| Charge hold + release | 3 + 4 | D/U/S | 12 |
| Dodge roll | 5 | D/U/S | 16 |
| Hurt | 2 | D/U/S | 10 |
| Knockout | 5 | D | 8 |
| Cast (Royal Art) | 5 | D/U/S | 12 |
| Pact throw | 4 | D/U/S | 12 |
| Carry (idle / walk) | 4 / 6 | D/U/S | 6 / 10 |
| Fishing (cast / wait / reel / catch) | 4 / 2 / 4 / 5 | D/S | 10 |
| Eat / drink | 4 | D | 8 |
| Sit · sleep | 1 · 2 | D/U/S · D | — |
| Pet a familiar | 4 | D/U/S | 8 |
| Emotes (joy, surprise, sad, think) | 4 each | D | 8 |
| Ride mount (1.0) | 4 | D/U/S | 10 |

### Others

| Rig | Set |
|---|---|
| **Sworn** | Idle 4, walk 6 (D/U/S) · signature work loop 6 · sit · talk gesture 4 · emote 4. **Companion Sworn** add: attack 2×4, skill 5, hurt 2, KO 4 |
| **Settlers** | Idle, walk, carry, work-farm, work-chop, work-hammer, work-generic, sit, sleep (D/U/S), all on shared skeletons |
| **Creature S** | Idle 4 (side + front) · move 6 (side) · attack 5 · hurt 2 · faint 4 · work 4 · sleep 2 · happy 4 |
| **Creature M / L** | As S, but idle and move in D/U/S |
| **Boss** | Custom per fight (~80–150 frames) |

**Principles:** anticipation → action → recovery on every attack; 2–4 frames of **hitstop** on impact; squash & stretch on creatures; secondary motion on hair, capes, tails; landing dust.

---

## 13. VFX style

- Pixel particles with 2–4 colours each; additive blending for magic only.
- **Colour language:** gold = the player and Lumen · red-orange = enemy danger · violet-teal = the Veil · element colours for element effects.
- Anime-style **emote bubbles** (! ? ♥ … 💢 💧 ♪ zzz) above heads.
- Defeated creatures **dissolve into mist** (a generic effect tinted per element).

---

## 14. Logo & key art concept

- **Logo motif:** a **broken crown with a green sprout growing through the crack**. The fallen monarch and the farm in one symbol.
- **Key art:** at dawn, the Sovereign sits on the moss-covered Ashen Throne with Flicker glowing on their shoulder; below, the Veil rolls through the valley; silhouettes of familiars and future companions wait in the mist; the first light of the Beacon cuts a golden path.

---

## 15. Do's & Don'ts

| ✅ Do | ❌ Don't |
|---|---|
| Hue-shift shadows and highlights | Darken with plain black or grey |
| Keep silhouettes distinct | Give two characters the same hair shape and colour |
| Use pixel clusters | Use noisy dithering on large areas |
| Keep lighting from the top-left | Mix light directions in one scene |
| Let portraits carry the emotion | Cram facial detail into 16 px sprites |
| Show the Veil with colour, tint, and motion | Use gore or horror imagery |
| Use integer scaling | Rotate or scale pixel art at odd angles |

---

## 16. Art Style Test (Step 11) deliverables & review checklist

**Deliverables:** locked palette · Dawnmere tile sample (Spring) · Veil border sample (night) · Sovereign idle/walk (3 directions) · Flicker · Mossbun and Emberkit (idle, move, attack) · Linnea portrait (3 expressions) · UI kit sample (panel, button, hotbar, dialogue box) → combined into one **Target Frame** (a real in-engine screenshot).

**Review checklist:**
- [ ] Reads at phone size and at 4K
- [ ] The Realm/Veil border is obvious at night
- [ ] Characters pop from backgrounds
- [ ] Interactables are distinguishable from decoration
- [ ] Colour-blind simulation passes (deuteranopia, protanopia, tritanopia)
- [ ] Feels "warm anime" in a blind poll of 5 people
