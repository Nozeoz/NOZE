// Kingsbloom · Chapter 1 narrative prototype · shared state
// Flag names follow docs/14 §9.4 with the dots written as underscores (ch1.woke → ch1_woke).
// Ink owns the story flags below. Numbers the game owns (gold, items, hearts, food, time)
// are read and changed through these EXTERNAL functions, so the same scripts can move into
// the real game (Step 11) with the engine answering them instead of the prototype.

EXTERNAL item(id)                 // how many of an item the Sovereign carries; "food_any" = any cooked dish
EXTERNAL give(id, n)              // add items (a negative n removes them)
EXTERNAL stat(key)                // gold, food, food_cap, energy, exposure, joy, safety, ra, beacon, floor, power, familiars, residents, sworn, settlers, beds_free, day, season_day, trial_days, construction
EXTERNAL add_stat(key, n)
EXTERNAL hearts(npc)              // whole hearts, 0–10
EXTERNAL add_hearts(npc, points)  // 100 points = 1 heart
EXTERNAL weekday()                // "Mon" … "Sun"
EXTERNAL season()                 // "Spring" or "Summer"
EXTERNAL built(id)                // true once that building stands
EXTERNAL unlock(what)             // tells the game (and the player) that something new is available
EXTERNAL plant(crop, n)           // sows n field plots
EXTERNAL add_settler(name, role)  // a named settler moves in

// ---- The Sovereign (var.*) ----
VAR var_player_name = "Sovereign"
VAR var_title = "Monarch"          // King / Queen / Monarch
VAR var_tone = "warm"              // regal / warm / wry: whichever you pick most
VAR tone_regal = 0
VAR tone_warm = 0
VAR tone_wry = 0
VAR var_kingdom_name = "the realm"
VAR var_banner = ""

// ---- Chapter 1 progress (ch1.*) ----
VAR ch1_woke = false
VAR ch1_campfire = false
VAR ch1_survived_night1 = false
VAR ch1_first_crops = false
VAR ch1_smoke_seen = false
VAR ch1_meadow_shown = false
VAR ch1_first_pact = false
VAR ch1_emberkit_pact = false
VAR ch1_longhouse_planned = false
VAR ch1_founded = false
VAR ch1_founded_day = 0
VAR ch1_granary_shown = false
VAR ch1_granary_restored = false
VAR ch1_signet = false
VAR ch1_vs_complete = false
VAR ch1_vs_day = 0
VAR ch1_bridge_shown = false
VAR ch1_bridge_restored = false
VAR ch1_complete = false

// ---- World (world.*) and kingdom (kingdom.*) ----
VAR world_cellars_open = false
VAR world_regalia_signet = false
VAR world_surges_active = false
VAR kingdom_rank = 0               // 0 Exile's Camp · 1 Hamlet · 2 Village
VAR kingdom_reputation = "none"    // merciful (spared Rook) · stern (banished him)
VAR kingdom_first_decree = ""
VAR court_held = false
VAR lore_sun_sigil = false
VAR omen_investigated = false

// ---- People (npc.*) ----
VAR npc_mira_met = false
VAR npc_bram_found = false
VAR npc_bram_recruited = false
VAR npc_linnea_recruited = false
VAR npc_hob_arrived = false
VAR npc_rook_met = false
VAR npc_rook_trial = "none"        // none · active · late · done
VAR npc_rook_recruited = false
VAR npc_tamsin_found = false
VAR npc_tamsin_recruited = false
VAR npc_marigold_met = false
VAR npc_marigold_recruited = false
VAR npc_juniper_met = false
VAR npc_juniper_recruited = false
VAR herd_found = 0
VAR ruinback_tries = 0

// ---- Remembered deeds (deed.*) ----
VAR deed_saved_linnea_on_birthday = false
VAR deed_spared_rook = false
VAR deed_banished_rook = false
VAR deed_judged_rook_medicine = ""  // forgave · docked (Rook 4♥)
VAR deed_rank_up = false

// ---- Heart events (played once each) ----
VAR ev_bram_2 = false
VAR ev_bram_4 = false
VAR ev_linnea_2 = false
VAR ev_linnea_4 = false
VAR ev_rook_2 = false
VAR ev_rook_4 = false
VAR ev_tamsin_2 = false
VAR ev_tamsin_4 = false
VAR ev_juniper_2 = false
VAR ev_marigold_2 = false
VAR ev_mira_2 = false
VAR blossom_partner = ""

// ---- Personal requests at 3♥ (docs/14 §5.8): none · open · done ----
VAR ask_bram = "none"
VAR ask_linnea = "none"
VAR ask_rook = "none"
VAR ask_tamsin = "none"

// ---- Filled in by the game before an arrival scene ----
VAR arrival_name = ""
VAR arrival_background = ""
VAR arrival_trait = ""
VAR arrival_accepted = false
VAR theft_loss = ""

// Records the tone of a spoken choice and keeps var_tone on the most-used one.
=== function tone(t) ===
{
- t == "regal":
    ~ tone_regal++
- t == "warm":
    ~ tone_warm++
- t == "wry":
    ~ tone_wry++
}
{
- tone_regal > tone_warm && tone_regal > tone_wry:
    ~ var_tone = "regal"
- tone_wry > tone_warm && tone_wry > tone_regal:
    ~ var_tone = "wry"
- else:
    ~ var_tone = "warm"
}
