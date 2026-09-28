// Flicker: tutorial voice, hint system, and the quest log.

// The quest log the game shows in its side panel. One objective per line: ID¦Title¦Objective.
=== function quest_log() ===
{ch1_woke && not ch1_campfire:
    MQ-101¦Waking at the Ashen Throne¦Gather 10 wood ({item("mat_wood")}/10) and 5 stone ({item("min_stone")}/5), then light a campfire.
}
{ch1_woke && not ch1_survived_night1:
    MQ-102¦The First Night¦When night falls, keep the fire alive until dawn.
}
{ch1_first_crops && not ch1_smoke_seen:
    MQ-103¦Old Royal Fields¦Water your turnips every day, forage, and sell to Mira (Tuesdays and Fridays).
}
{ch1_smoke_seen && not npc_bram_found:
    MQ-104¦The Old Oak¦Follow the smoke to the Windmill Ruin.
}
{npc_bram_found && not npc_bram_recruited:
    MQ-104¦The Old Oak¦Bring Bram 3 Healing Herbs ({item("frg_healing_herb")}/3) and a cooked meal ({item("food_any")}/1).
}
{ch1_meadow_shown && not ch1_first_pact:
    MQ-105¦Pacts of the Vale¦Offer a carrot to a Mossbun in Mossbun Meadow (carrots: {item("crop_carrot")}).
}
{ch1_first_pact && not ch1_emberkit_pact:
    MQ-105¦Pacts of the Vale¦Optional: subdue the Emberkit with a Twine Sigil (craft one from 3 fiber).
}
{npc_bram_recruited && not npc_linnea_recruited:
    MQ-106¦The Lost Healer¦Listen for the chapel bell at dusk, from Spring 5.
}
{ch1_longhouse_planned && not built("longhouse"):
    MQ-107¦A Roof and a Name¦{stat("construction") > 0: Bram is raising the Longhouse. {stat("construction")} day(s) to go.|Bring 80 wood, 50 stone and 150 gold, then order the Longhouse in Build.}
}
{built("longhouse") && not ch1_founded:
    MQ-107¦A Roof and a Name¦{npc_hob_arrived: Hold the Founding in the Longhouse.|Wait for someone to find your light.}
}
{npc_rook_trial == "active" || npc_rook_trial == "late":
    MQ-109¦Rook's Trial¦Stock 28 rations ({stat("food")}/28; your stores hold {stat("food_cap")}). {npc_rook_trial == "active": {stat("trial_days")} day(s) left.|The week is up, but the gang is waiting.}
}
{ch1_granary_shown && not ch1_granary_restored:
    MQ-110¦Below the Granary¦Deliver the three bundles for the Old Granary (Projects).
}
{world_cellars_open && not npc_tamsin_found:
    MQ-111¦Sparks in the Dark¦Explore the Sunken Cellars (deepest floor: {stat("floor")}).
}
{npc_tamsin_found && not npc_tamsin_recruited:
    MQ-111¦Sparks in the Dark¦Bring Tamsin 10 copper ore ({item("min_copper_ore")}/10).
}
{world_cellars_open && not ch1_signet:
    MQ-112¦The Shell That Holds a Tower¦Reach floor 10 ({stat("floor")}/10). Ruinback needs power 3 (yours: {stat("power")}).
}
{ch1_signet && not ch1_vs_complete:
    MQ-113¦The Founding Feast¦{npc_rook_recruited || deed_banished_rook: The feast is tonight.|Finish Rook's Trial first.}
}
{ch1_vs_complete && not npc_marigold_met:
    SQ-114¦Hearth and Home¦Keep an eye on the south road at dusk.
}
{npc_marigold_met && not npc_marigold_recruited:
    SQ-114¦Hearth and Home¦Build Marigold a Kitchen.
}
{ch1_vs_complete && not npc_juniper_recruited:
    SQ-115¦The Scattered Herd¦{npc_juniper_met: Round up Juniper's Mossbuns in Mossbun Meadow ({herd_found}/8).|Someone is shouting in Mossbun Meadow.}
}
{ch1_vs_complete && not court_held:
    MQ-116¦The Crown's Word¦Reach Village: 12 residents ({stat("residents")}/12), 5 Sworn ({stat("sworn")}/5), the Signet, Beacon Tower (tier {stat("beacon")}/2). Court meets on Sundays.
}
{court_held && not ch1_bridge_restored:
    MQ-117¦The Old Bridge¦{ch1_bridge_shown: Restore the Old Bridge (Projects).|Bram wants a word.}
}
{ch1_bridge_restored && not ch1_complete:
    MQ-117¦The Old Bridge¦Build a Waybeacon at the Veil Wall.
}
{ask_bram == "open":
    Ask¦Bram's request¦Bring Bram 20 wood ({item("mat_wood")}/20).
}
{ask_linnea == "open":
    Ask¦Linnea's request¦Bring Linnea 5 Healing Herbs ({item("frg_healing_herb")}/5).
}
{ask_rook == "open":
    Ask¦Rook's request¦Find Magpie's slingshot somewhere in the Sunken Cellars.
}
{ask_tamsin == "open":
    Ask¦Tamsin's request¦Bring Tamsin 10 copper ore to practise on ({item("min_copper_ore")}/10).
}

// "Ask Flicker": the single most useful next step, in Flicker's voice.
=== talk_flicker ===
{
- not ch1_campfire:
    Wood and stone, Majesty. Ten and five. Then fire! Fire is my whole personality. #speaker:flicker
- not ch1_survived_night1:
    Just get through tonight. Stay by the fire. I'll do the rest. Mostly. #speaker:flicker #mood:worried
- npc_bram_found && not npc_bram_recruited:
    {
    - item("frg_healing_herb") < 3:
        Bram needs Healing Herbs. They grow wild: go foraging in the Vale. #speaker:flicker
    - item("food_any") < 1:
        Cook something at the fire. A roasted turnip counts. Roasted, not raw. We're not animals. #speaker:flicker
    - else:
        Herbs, hot food… Bram's waiting at the windmill. Go! #speaker:flicker #mood:happy
    }
- ch1_smoke_seen && not npc_bram_found:
    The smoke by the windmill! Someone's there. Go and see. #speaker:flicker
- ch1_meadow_shown && not ch1_first_pact && item("crop_carrot") > 0:
    You've got a carrot. The Mossbuns are waiting. I can feel them wanting that carrot from here. #speaker:flicker
- ch1_meadow_shown && not ch1_first_pact:
    Mossbuns want carrots. Mira sells them on Tuesdays and Fridays. Or grow your own, if you're patient. You're not, but still. #speaker:flicker
- npc_bram_recruited && not npc_linnea_recruited:
    Keep busy. Farm, forage, cook. And when it gets dark, listen. Bells carry a long way at dusk. #speaker:flicker #mood:squint
- ch1_longhouse_planned && not built("longhouse") && stat("construction") == 0:
    The Longhouse, Majesty! Eighty wood, fifty stone, a hundred and fifty gold. Gather, sell to Mira, then tell Bram in Build. #speaker:flicker
- built("longhouse") && not ch1_founded && not npc_hob_arrived:
    A roof! Now we just need someone to find us. Keep the light burning. They'll come. #speaker:flicker
- npc_rook_trial == "active" || npc_rook_trial == "late":
    {
    - not ch1_granary_restored && stat("food_cap") < 28:
        Our larder only holds {stat("food_cap")}. Fix the Old Granary so we can store twenty-eight. The bundles are under Projects. #speaker:flicker
    - else:
        Food, food, food. Harvest, forage, set settlers on a Commons Field, buy from Mira. Rook's counting every sack. #speaker:flicker
    }
- ch1_granary_shown && not ch1_granary_restored:
    The Old Granary needs three bundles. Crops, timber and stone, and a forager's basket. Check Projects. #speaker:flicker
- npc_tamsin_found && not npc_tamsin_recruited:
    Tamsin needs ten copper ore. The Cellars are full of it. Dig, Majesty, dig! #speaker:flicker
- world_cellars_open && not ch1_signet && stat("floor") >= 9 && stat("power") < 3:
    Ruinback's shell is harder than Bram's opinions. We need power three: Tamsin's sword, the Emberkit, Linnea at your side… stack them! #speaker:flicker #mood:worried
- world_cellars_open && not ch1_signet:
    The Cellars go down ten floors. Something gold is waiting at the bottom. I can feel it humming. #speaker:flicker
- ch1_signet && not ch1_vs_complete:
    {npc_rook_recruited || deed_banished_rook: We should celebrate. Properly. Tonight!|Rook's Trial isn't done yet. Food first, feast after.} #speaker:flicker
- ch1_vs_complete && not court_held:
    {
    - stat("sworn") < 5:
        We need five Sworn for a Village. There's someone shouting in Mossbun Meadow, and Hob swears he's seen lights on the south road at dusk. #speaker:flicker
    - stat("beacon") < 2:
        A Village needs a Beacon Tower. That's stone, wood, copper, and Veilglass from the deep Cellars. Bram and Tamsin can build it. #speaker:flicker
    - stat("residents") < 12:
        More people! Settlers come when there's a free bed, enough food, and a happy realm. Build Huts, keep the Granary full. #speaker:flicker
    - else:
        Everything's ready. Court meets on Sunday. Wear something clean. You don't own anything clean, but try. #speaker:flicker
    }
- court_held && not ch1_complete:
    The Old Bridge, then a Waybeacon at the Veil Wall. Then the road north. I'm not scared. You're scared. #speaker:flicker
- ch1_complete:
    Chapter one: done. Whisperwood's waiting. So is whoever's singing. #speaker:flicker #mood:serious
- else:
    {~Farm a little, forage a little, talk to people. Kingdoms are mostly talking to people.|Have you eaten? Eat something. Then rule something.|If you ever run out of ideas, check the quest log. It's like me, but quieter.} #speaker:flicker
}
-> DONE
