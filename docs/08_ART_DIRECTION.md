# 08 — Art Direction

> **TL;DR (v0.2):** **Hand-drawn, illustrated 2D** in a top-down 3/4 view, following the two mood references chosen by the creative lead: clean coloured line art, soft cel shading, a sunny storybook palette, and dense, lived-in props. Characters are chibi-anime and animated with **2D skeletal rigs (Spine)**. Portraits are HD anime illustrations. The visual story is still **light vs. the Veil**: colour and life spread wherever your kingdom's light reaches.
>
> *v0.1 proposed pixel art. v0.2 switches to illustrated 2D per the creative lead's references ([D-002](12_DECISIONS_AND_OPEN_QUESTIONS.md)).*

---

## 1. Visual pillars

| Pillar | Means | Test |
|---|---|---|
| **Storybook Anime Illustration** | Clean coloured lines, soft cel shading, sunny palette, chibi anime characters | Does a screenshot look like a page from an illustrated storybook? |
| **Alive & Lived-in** | Dense natural props, tiny creatures, laundry lines, planters, clutter that tells stories | Can you spot 5 small stories in one screen? |
| **Readable First** | Busy decoration never hides paths, characters, interactables, or danger | Can you read it at phone size in 1 second? |
| **Light vs. Veil** | Colour and saturation live in the light; the Veil desaturates and tints violet-teal | Can you see the Realm's border at night without any UI? |
| **The Kingdom Grows Visibly** | Every rank changes the skyline, props, lights, and crowd density | Would a before/after GIF impress on social media? |

---

## 2. Mood references

### 2.1 The two references from the creative lead (mood only)

| | **Ref A: Forest river** | **Ref B: Village courtyard** |
|---|---|---|
| What it shows | Top-down 3/4 forest with a winding river, a small fishing dock, stepping stones, lily pads with pink lotuses, giant mushrooms, pines and round-canopy trees, ferns, stumps, berry bushes, deer, dragonflies, and many tiny white bunny-like critters | A top-down village courtyard: cream stone houses with terracotta doors and shutters, curved stone garden walls, raised vegetable beds, laundry lines, barrels, clay pots, cobbles and dirt paths in warm afternoon light |
| **We take** | Line and shading style, the sunny yellow-green and teal palette, prop density, organic shapes (river bends, clearings), **ambient life** everywhere | The cream-stone and terracotta village palette, **lived-in clutter**, **raised garden beds** inside the village, warm golden light |
| **We adapt** | Characters must be **larger** than in the image (readability); decoration kept away from walking paths | Ref B draws walls in a **converging "battle-map" perspective**. A scrolling game camera can't use that, so **all buildings use the same 3/4 front-facing projection** |
| Rights | Unknown source | Credited to the artist **Mimosa20** (Patreon) |

> **Rights rule:** references are **mood only**. They are never traced, copied, placed in builds, used in marketing, or committed to this repository. Our artists create original work in this *direction*.

### 2.2 Other touchstones
- **Studio Ghibli backgrounds:** lush nature reclaiming ruins.
- **Don't Starve:** a hand-drawn world built from free-placed props.
- **Cult of the Lamb:** chibi characters with skeletal animation in an HD 2D top-down world.
- **Fields of Mistria, Rune Factory:** anime portraits with strong expressions.
- ***Frieren*** **colour script:** soft pastel skies, melancholy golden hours.

---

## 3. Projection & camera

| Spec | Value |
|---|---|
| Projection | Top-down 3/4 oblique (~60° look-down): tree canopies and roofs from above, fronts of rocks, buildings, and characters visible |
| Consistency rule | **One projection for everything.** No converging perspective, no pure top-down buildings |
| Light | Warm sun from the **top-left**; cast shadows fall to the bottom-right |
| Depth sorting | By the Y of each object's ground pivot |
| Camera | Smooth follow; zoom 1.0 in gameplay, 0.5 in build mode |

---

## 4. Resolution & scale

| Spec | Value |
|---|---|
| Reference display | 1920×1080 (16:9); UI scales for other ratios |
| **Grid unit** | **1 tile = 64 × 64 px at 1080p**, so ~30 × 17 tiles are visible |
| Authoring resolution | **2×** (128 px per tile), so art stays crisp at 1440p and 4K |
| Shipping | 1× textures by default (web and low-memory devices); a 2× high-res pack on desktop |
| Filtering | Smooth (linear) with mipmaps |

**Scale chart (on-screen size at 1080p; author at 2×):**

| Thing | Size |
|---|---|
| Tile | 64 × 64 |
| Adult character | ~64 wide × ~128 tall (2 tiles tall; chibi 2.5–3 heads) |
| Halfling / gnome · dwarf · Tor (wolfkin) | ~96 · ~110 · ~150 tall |
| Flicker | ~32 px, floating |
| Creature S / M / L | ~48–80 / ~96–128 / ~160–200 px |
| Guardians | 300–700 px |
| Trees · rocks | 128–320 · 32–128 px tall |
| Buildings | Footprint × 64 px, plus roof height |
| Item icon | 64 × 64 (authored 128) |
| Portrait | Bust-up shown at ~512 × 512 (authored 1024 × 1024) |

---

## 5. Line art & shading

1. **Line colour:** a darker, slightly desaturated hue of the fill it surrounds. **Never pure black.**
2. **Line weight hierarchy (at 1080p):** outer silhouette ~3 px, inner detail ~1.5 px. Characters get the thickest silhouette line in the scene so they pop.
3. **Cel shading:** base + 1 shadow tone + 1 small highlight. Shadow shapes follow the top-left light.
4. **Contact shadows:** every object gets a soft multiply shadow (30–40% opacity) where it touches the ground.
5. **Gradients** only for water, sky, light, and magic.
6. **Texture:** small hand-drawn marks (clover scribbles, grass tufts, stone cracks), as in Ref A. No photo textures.

---

## 6. Palette

Swatches sampled from the references (approximations; locked during the Art Style Test).

| Group | Swatches |
|---|---|
| Meadow grass | light `#D1D987` · mid `#B6CE6F` · muted `#98A067` · shade `#698D66` |
| Foliage & pines | light `#729F8B` · dark `#3C6D62` · deepest `#345F50` |
| Water | main `#95C6C6` · light `#B8DAD9` · foam `#D9EAE7` · deep (banks) `#3C6D62` |
| Wood & bark | `#8E6D56` · dark `#4B372B` |
| Village stone & paths | cream `#F9EAC5` · warm cream `#F6E5B9` · sand path `#E2CB9D` · stone shade `#B8A689` |
| Village greens (warmer) | `#B7B864` · `#A5AA58` · dark `#5F552F` |
| Terracotta (doors, shutters, roofs) | lit ~`#B85A40` · shade `#8C5039` · dark `#5E3827` |
| Accents | mushroom gold `#D7B068` · lotus pink ~`#F0A7B4` · berry red ~`#C9483E` · lavender ~`#9E8AC8` |
| Line darks | forest `#2E3327` · village `#554B2F` |
| **Reserved** (never used for anything else) | **Veil** violet `#6B4FD8` → teal `#3FD6C6` · **Heartflame/Lumen** gold `#FFC94A` → cream `#FFF3C4` · **enemy telegraph** `#FF5A3C` |

**Region colour keys:**

| Region | Key colours |
|---|---|
| Dawnmere Vale | Ref A meadow greens + Ref B cream stone and terracotta village |
| Whisperwood | Deeper teal-greens, mushroom gold and magenta, firefly yellow |
| Saltglass Coast | Turquoise, sand cream, glass-sparkle white, coral |
| Cinderpeak | Charcoal, ember orange, obsidian purple-black, hot-spring aqua |
| Frostveil | Ice blue, white, aurora green-violet, night navy |
| The Hollow Crown | Faded gold, ash grey, Veil violet-teal |

---

## 7. Lighting & time of day

- **Colour grading per phase:** Dawn (pink-gold) → Day (neutral, warm) → Dusk (orange-violet) → Night (deep blue, low saturation).
- **Light sprites:** campfires, lamps, windows, Flicker, glowing creatures (soft additive glows).
- **Night:** windows get a warm emissive layer; lantern light pools on the ground.
- **Weather overlays:** rain with splashes, snow, fog banks, storm flashes; seasonal particles (petals, leaves, fireflies).

---

## 8. The Veil: visual language

| Element | Spec |
|---|---|
| Veil fog | 2–3 layers of soft scrolling noise, violet-teal, drifting slowly |
| Light border | A soft glowing edge where light meets the Veil, with drifting motes |
| Outside the light | −40% saturation, violet tint |
| Veil Wall | A dense animated fog curtain with tendrils; impassable |
| Veil-choked land | Grey-violet soil, Veil Bramble, glowing crystal nodes |
| **Hollowed shader** | Desaturate 60% → violet-teal rim light → eyes replaced with glowing white → trailing mist particles |
| Purification | Golden burst + a **colour-restore wave** spreading outward |
| Exposure feedback | A Veil-coloured screen-edge vignette; at 70+, a gentle wobble (off with reduced motion) |

---

## 9. Building environments that look like the references

1. **Ground:** painted terrain tiles (64 px) with **soft, organic transition edges** (Tiled terrain sets), 3–4 variants per terrain, plus free-placed ground **decals** (clover patches, flowers, dirt specks).
2. **Props are placed freely**, not grid-locked: trees, rocks, mushrooms, ferns, stumps, logs, lily pads go on Tiled **object layers**, each with a collision shape and a sort pivot. This is how the organic density of Ref A is achieved.
3. **Water:** painted banks + an animated water shader (flow highlights, shimmer) + props (lily pads, lotuses, stepping stones, docks).
4. **Density rule:** dense decoration **frames** open, calm clearings. Paths and farm areas stay clear.
5. **Farm:** tilled and watered soil overlays with painted edges; **raised garden beds** (Ref B) as a buildable object for settler homes and village gardens.
6. **Village (Dawnmere):** cream stone, terracotta shutters, curved stone garden walls (Ref B). **Lived-in clutter sets** (laundry lines, barrels, pots, stools, planters) are attached to homes and **appear as a household's happiness grows**, so the kingdom visibly gets cozier.
7. **Ambient life:** **Wisplings** (our own tiny white spirit critters; see the [Bestiary](05_BESTIARY.md#29-ambient-life-wisplings)), dragonflies, butterflies, fish shadows, deer. Wisplings gather where the realm is happy and scatter from the Hollowed.

---

## 10. Characters

- **Proportions:** chibi anime, 2.5–3 heads tall; big expressive eyes; simple, clean shapes; job-readable outfits.
- **Views:** front (down), back (up), side (mirrored for left/right).
- **Animation:** **2D skeletal rigs in Spine** (one rig per view). Hair, capes, and tails use physics constraints for secondary motion.
- **Customization via Spine skins:** hair, outfits, hats, and accessories are attachments swapped per slot; colours come from tint or gradient-map shaders.
- **Pop from busy backgrounds:** a thicker silhouette line + a subtle rim light in the character's signature colour.
- **Silhouette & signature colours:** see the cast rules in [04 §9](04_CHARACTERS.md#9-character-design-rules).

### Portraits
- HD anime bust-ups in the same line and shading language, with slightly more detail.
- **Layered** (base + eyes / brows / mouth / blush / sweat / tears) so 8 expressions cost far less than 8 paintings.
- Optional (EA): blink and mouth-flap layers while talking. Optional (1.0 stretch): Live2D-style subtle motion.

---

## 11. Creatures

- Same line and shading language as the world; element shape language from the [Bestiary §1](05_BESTIARY.md#1-creature-design-rules).
- **S-size** creatures may be frame-by-frame (few frames, very expressive); **M, L, and bosses** use Spine rigs.
- The Hollowed are a **shader**, never new art.

---

## 12. UI: "Royal Storybook"

- **Materials:** parchment cards, deep navy panels, gold filigree trim, wax-seal accents for royal actions (Decrees, Court Day).
- **Icons:** 64 × 64, same coloured line art, consistent top-left light.
- **Fonts** (open licences, verified before shipping): a royal serif for headings (e.g. *Cinzel*), a rounded, friendly sans for body text (e.g. *Nunito*), plus a dyslexia-friendly option.
- **Colour-blind safety:** elements, quality, and statuses always pair colour with a **shape**.
- **Motion:** soft tweens of 120–200 ms; nothing blocks input for more than 300 ms.

---

## 13. Animation standards

**Directions:** D (down), U (up), S (side, mirrored). Rig animations play at 30 fps. Durations are targets.

### Player

| Animation | Directions | Target duration |
|---|---|---|
| Idle (breathing loop) | D/U/S | 1.2 s loop |
| Walk / run | D/U/S | 0.6 s / 0.45 s loop |
| Tool swing (hoe, axe, pickaxe share the body motion) | D/U/S | 0.4 s |
| Watering · sickle sweep | D/U/S | 0.5 s · 0.3 s |
| Attack combo ×3 (per weapon family) | D/U/S | 0.25–0.35 s each |
| Charge hold + release | D/U/S | loop + 0.3 s |
| Dodge roll | D/U/S | 0.35 s |
| Hurt · knockout | D/U/S · D | 0.2 s · 0.8 s |
| Cast (Royal Art) · Pact throw | D/U/S | 0.5 s · 0.4 s |
| Carry (idle / walk) | D/U/S | loops |
| Fishing (cast / wait / reel / catch) | D/S | per phase |
| Eat / drink · sit · sleep · pet a familiar | varies | — |
| Emotes (joy, surprise, sad, think) | D | 0.8 s |
| Ride mount (1.0) | D/U/S | loop |

### Others

| Rig | Animation set |
|---|---|
| **Sworn** | Idle, walk (D/U/S) · signature work loop · sit · talk gesture · emote. **Companion Sworn** add attack ×2, skill, hurt, KO |
| **Settlers** | Idle, walk, carry, work-farm, work-chop, work-hammer, work-generic, sit, sleep, on shared rigs with skins |
| **Creatures** | Idle, move, attack, hurt, faint, work, sleep, happy |
| **Bosses** | Custom per fight |

**Principles:** anticipation → action → recovery on every attack; 2–4 frames of **hitstop** on impact; squash & stretch on creatures; secondary motion on hair, capes, and tails.

---

## 14. VFX

- Hand-drawn effect sprites plus particles in the same line language; additive glow only for magic.
- **Colour language:** gold = the player and Lumen · red-orange = enemy danger · violet-teal = the Veil · element colours for element effects.
- Anime-style **emote bubbles** (! ? ♥ … 💢 💧 ♪ zzz).
- Defeated creatures **dissolve into mist**.

---

## 15. Logo & key art concept

- **Logo motif:** a **broken crown with a sprout growing through the crack, topped by a Kingsbloom bud**. The fallen monarch, the farm, and the title in one symbol.
- **Key art:** at dawn, the Sovereign sits on the moss-covered Ashen Throne with Flicker on their shoulder; below, the Veil rolls through the valley; silhouettes of familiars and future companions wait in the mist; the first light of the Beacon cuts a golden path, and a single Kingsbloom bud waits beside the throne.

---

## 16. Do's & Don'ts

| ✅ Do | ❌ Don't |
|---|---|
| Use coloured line art with a weight hierarchy | Outline with pure black |
| Keep one 3/4 projection everywhere | Mix in converging "battle-map" walls |
| Frame calm clearings with dense props | Scatter props over paths and farm areas |
| Give characters the strongest silhouette in the scene | Let characters blend into busy foliage |
| Show the Veil with colour, tint, and motion | Use gore or horror imagery |
| Keep lighting from the top-left | Mix light directions in one scene |
| Treat references as mood | Trace, copy, or ship reference images |

---

## 17. Prototype placeholder kit

Until the hired artist delivers, prototypes use a **placeholder kit** built in-house as simple vector art in this same language (coloured outlines, flat cel shading, the palette above): terrain tiles, trees, rocks, mushrooms, water edges, soil states, the Sovereign, Flicker, a Mossbun, and a few buildings. It's legally clean, makes grey-boxes feel close to the target, and **never ships**.

**Built (Step 4):** 61 assets in [`art/placeholder`](../art/placeholder), with the Asset Atlas page (`gallery.html`) showing them in a camp scene, by category, in a UI mock-up, and in a live Veil and Beacon demo.

---

## 18. Hiring an artist: brief & paid test

**Look for:** clean coloured line art and cel shading · top-down environment props · chibi character design · Spine rigging and animation (can be a separate animator) · consistency across many assets.

**Paid test task (small, identical for every candidate):** one round-canopy tree, one rock, one giant mushroom, one 3×3-tile patch of grass-to-dirt transition, and the Sovereign as a front/back/side turnaround, delivered at 2× in layered files.

**What we give the artist:** this document, the palette swatches, the scale chart, the naming conventions from [`10_ASSET_LIST.md`](10_ASSET_LIST.md), and a reference board (links only).

---

## 19. Art Style Test deliverables & review checklist

**Deliverables:** locked palette · Dawnmere terrain and prop sample (Spring) · Veil border at night · the Sovereign rig (idle and walk, 3 views) · Flicker · Mossbun and Emberkit · Linnea portrait (3 expressions) · UI kit sample (panel, button, hotbar, dialogue box) → combined into one **Target Frame** (a real in-engine screenshot).

**Review checklist:**
- [ ] Reads at phone size and at 4K
- [ ] Characters and interactables pop from busy backgrounds
- [ ] The Realm/Veil border is obvious at night
- [ ] One consistent projection and light direction
- [ ] Colour-blind simulation passes (deuteranopia, protanopia, tritanopia)
- [ ] Feels like "storybook anime" in a blind poll of 5 people
