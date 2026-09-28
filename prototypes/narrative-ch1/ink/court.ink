// Court Day petitions (templates from docs/07 §7) and the first Royal Decree (docs/07 §6).
// court_name is filled in by the game with one of your settlers before Court opens.
VAR court_name = "Ada"

=== court_petitions ===
// ── Field Dispute
The first petitioners are Hob and {court_name}, both talking at once, both pointing east. #scene:Court Day · The Longhouse #bg:day
Hob and {court_name} both claim the east field. #style:note
It was my wife's idea to plant there, {var_title}. Before. #speaker:hob
With respect, it's gone wild for years. I cleared it. #speaker:{court_name}
* [Give it to Hob.]
    ~ add_hearts("hob", 50)
    ~ add_stat("joy", -2)
    Hob bows so low his hat falls off. {court_name} goes home unhappy, but calm.
* [Split it between them.]
    ~ add_stat("joy", 3)
    They grumble at the same moment, then laugh at the same moment. You get the feeling they'll be friends by harvest.
* [Make it a royal field that feeds everyone.]
    ~ add_stat("ra", 3)
    ~ add_stat("food", 5)
    Neither of them loves it. Both of them eat from it by Tuesday.
-
~ add_stat("ra", 1)
// ── Repair Request
Next comes a young mother with a baby on her hip and rain still in her hair.
The Hut roof leaks. Can the crown spare twenty Wood? #style:note
* {item("mat_wood") >= 20} [Grant it. (−20 Wood, +Joy)]
    ~ give("mat_wood", -20)
    ~ add_stat("joy", 4)
    Bram is on the roof before she's finished thanking you.
* [Delay it. (−Joy)]
    ~ add_stat("joy", -3)
    She nods. She's heard "later" before. You can tell.
-
~ add_stat("ra", 1)
// ── Omen
The last petitioner is {court_name} again, whispering this time.
Strange lights over the northern wood last night… #style:note
Blue ones. Green ones. And singing, sort of. Everyone says I dreamed it. #speaker:{court_name}
* [Order it investigated.]
    ~ omen_investigated = true
    North. The hymn at the feast came from the north, too. I don't like this, Majesty. #speaker:flicker #mood:worried
* [Tell them to stay inside the light.]
    Stay close to the fires. Whatever's out there, the Beacon keeps it out. #speaker:you
-
~ add_stat("ra", 1)
->->

=== court_decree ===
Flicker hovers at your shoulder.
One more thing, Majesty. A Village gets a Decree: one law, yours, that shapes how {var_kingdom_name} lives. You can change it later, but it costs Royal Authority. #speaker:flicker #mood:serious
* [Harvest Tithe: a tenth of every harvest goes straight to the Granary. Crop sales earn 5% less.]
    ~ kingdom_first_decree = "harvest_tithe"
    Good. Families eat first. That's how it should be. #speaker:bram
    {npc_marigold_recruited:
        Good for the pot, bad for the purse. I'll allow it. #speaker:marigold
    }
* [Open Gates: twice as many settlers arrive. Safety drops a little.]
    ~ kingdom_first_decree = "open_gates"
    {npc_rook_recruited:
        Open gates. For people like us. Huh. #speaker:rook #mood:surprised
    }
    {npc_juniper_recruited:
        More people means more friends for the buns! #speaker:juniper #mood:happy
    }
    More people means more beds, kid. I'll get the saw. #speaker:bram
* [Night Curfew: half as many night incidents. Joy drops a little.]
    ~ kingdom_first_decree = "night_curfew"
    {npc_rook_recruited:
        A curfew. In a kingdom run by someone who wanders the Veil at midnight. Sure. #speaker:rook #mood:grumpy
    }
    Safer nights. My old crew would've liked a curfew. #speaker:bram
* [Rationing: a quarter less food eaten each day. Joy drops.]
    ~ kingdom_first_decree = "rationing"
    Smaller portions for growing people? I don't like it, {var_title}. #speaker:hob #mood:worried
    {npc_marigold_recruited:
        Rationing. In my kitchen. I'll make it taste like more, sweetheart, but I won't pretend I'm happy. #speaker:marigold
    }
* [Festival Year: festivals bring twice the Joy. Work slows in festival weeks.]
    ~ kingdom_first_decree = "festival_year"
    Old ways. Good ways. My ma never missed a feast day. #speaker:bram #mood:smile
* [Mercy Edict: people you spare join faster. Safety drops slightly.]
    ~ kingdom_first_decree = "mercy_edict"
    Mercy, written into law. I… I didn't think I'd live to see that. #speaker:linnea #mood:smile
    {npc_rook_recruited:
        Can't argue with that one. Wouldn't be here without it. #speaker:rook
    }
- The Decree is read aloud from the Longhouse steps. {var_kingdom_name} has its first law.
~ unlock("decree")
->->

// Every Sunday once you're a Village: a short Court with one petition.
=== court_weekly ===
Sunday. Court. A short line of petitioners waits at the Longhouse. #scene:Court Day · The Longhouse #bg:day
{~-> festival_request|-> new_arrival|-> fence}
= festival_request
{court_name} would like a small feast for the first ripe strawberries. #style:note
+ [Fund it. (−40 gold, +Joy)]
    ~ add_stat("gold", -40)
    ~ add_stat("joy", 5)
    There are not many strawberries. Everyone agrees it was the best feast ever.
+ [Not this week.]
    Fair enough, {var_title}. #speaker:{court_name}
-
~ add_stat("ra", 2)
-> DONE
= new_arrival
A traveller is waiting at the gate. A former soldier from the Outer Realms, says {court_name}. Asks to join. #style:note
+ [Let them in.]
    ~ add_settler("Corwin Ashe", "Soldier")
    He salutes, badly. Rook watches him from the roof all day.
+ [Ask for proof they mean well.]
    He comes back the next day with a basket of mushrooms and a very sincere face. You let him in.
    ~ add_settler("Corwin Ashe", "Soldier")
-
~ add_stat("ra", 2)
-> DONE
= fence
Gnawrats are getting into the Commons. {court_name} wants a proper fence. #style:note
+ {item("mat_wood") >= 15} [Grant it. (−15 Wood)]
    ~ give("mat_wood", -15)
    ~ add_stat("food", 4)
    The fence goes up. The Gnawrats file a complaint, somewhere, with someone.
+ [Set the Emberkit on guard duty.]
    The Emberkit takes the job very seriously. Nothing gets past it. Several things get singed.
-
~ add_stat("ra", 2)
-> DONE
