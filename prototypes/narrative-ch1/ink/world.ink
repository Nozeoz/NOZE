// World events: settler arrivals, thefts, knockouts, the Blossomfall festival.

// A settler applies at dawn. The game fills in arrival_name, arrival_background and arrival_trait first.
=== arrival ===
~ arrival_accepted = false
A traveller is waiting by the Heartflame at dawn, holding a small bundle. #scene:{var_kingdom_name} #bg:dawn
I'm {arrival_name}. I was a {arrival_background} before the mist took my village. #speaker:{arrival_name}
{kingdom_reputation == "merciful": They say the {var_title} here spares people. Even thieves. I thought… maybe there's room for me.|They say there's a light out here, and a {var_title} who feeds people.} #speaker:{arrival_name}
People call me {arrival_trait}. I'll work hard, if you'll have me. #speaker:{arrival_name}
+ [Welcome them to {var_kingdom_name}.]
    ~ arrival_accepted = true
    Welcome to {var_kingdom_name}. #speaker:you
    {arrival_name} lets out a breath they've clearly been holding for days.
+ [Turn them away for now.]
    We can't take anyone else yet. I'm sorry. #speaker:you
    {arrival_name} nods, shoulders the bundle, and walks back into the mist.
-
-> DONE

// Banished path only: the Crowfeather Gang still raids now and then until Chapter 2.
=== theft_report ===
Hob meets you at the Longhouse door, grim-faced. #scene:The Longhouse #bg:dawn
Someone got into the stores last night. {theft_loss} Crow feathers by the fence. #speaker:hob #mood:worried
{~Bram mutters something about fences. Nobody feels very safe.|Linnea says nothing, but she looks towards the Veil for a long time.|Flicker glares at the treeline hard enough to singe it.}
-> DONE

// Knocked out in the Sunken Cellars.
=== knockout_wake ===
{npc_linnea_recruited:
    You wake in the Herbalist Hut with a cool cloth on your forehead and Linnea's fingers on your pulse. #scene:Herbalist Hut #bg:day
    Your familiars dragged you home. You lost what you were carrying, but not yourself. That's the part I care about. #speaker:linnea #mood:worried
- else:
    You wake by the Heartflame, soaked, with no memory of the climb back up. #scene:The Ashen Throne #bg:day
    Your familiars dragged you home. Or I did. Emotionally. #speaker:flicker #mood:worried
}
-> DONE

// Blossomfall, Spring 13 (docs/07 §8). The whole day is the festival.
=== fest_blossomfall ===
Blossomfall. Overnight the old cherry trees by the river have burst into pink, and petals fall like slow snow. #scene:Blossomfall · Spring 13 #bg:festival
Nobody plans a festival. It just happens. Hob spreads a blanket under the trees. {npc_linnea_recruited: Linnea brings a pot of tea.} Bram brings a table, because of course he does.
Blossomfall! People used to dance under these trees. I think. My memory has holes in it, but the dancing part feels right. #speaker:flicker #mood:happy
Someone has found a fiddle. {npc_rook_recruited: It's Jackdaw, and he is shockingly good.|It's Hob, and he is enthusiastic.}
The Blossom Dance is starting. Who will you ask?
* {npc_linnea_recruited} [Ask Linnea.]
    ~ blossom_partner = "linnea"
    I don't really know how. …Alright. If you lead. #speaker:linnea #mood:shy
    She's lighter on her feet than she thinks.
    ~ add_hearts("linnea", 120)
* {npc_rook_recruited} [Ask Rook.]
    ~ blossom_partner = "rook"
    Dance? Me? #speaker:rook #mood:surprised
    He drops out of the tree and bows, extravagantly.
    Try to keep up, Majesty. #speaker:rook #mood:smug
    ~ add_hearts("rook", 120)
* {npc_tamsin_recruited} [Ask Tamsin.]
    ~ blossom_partner = "tamsin"
    Tamsin opens her mouth, closes it, and nods very fast. She steps on your feet six times and apologises seven.
    That was the best dance I've ever been bad at. #speaker:tamsin #mood:happy
    ~ add_hearts("tamsin", 120)
* {npc_bram_recruited} [Ask Bram.]
    ~ blossom_partner = "bram"
    My knees filed a complaint before you were born. …One song. #speaker:bram #mood:smile
    ~ add_hearts("bram", 120)
* [Ask Hob.]
    ~ blossom_partner = "hob"
    Hob dances like a man who used to be very good at it, and mostly still is.
    ~ add_hearts("hob", 120)
* [Dance with Flicker.]
    ~ blossom_partner = "flicker"
    You dance alone under the petals with a small flame spinning round your head. Everyone agrees it's the best dance of the day. Flicker agrees loudest.
- The music runs on into the evening. Petals in your hair, in your pockets, in the stew.
~ add_stat("joy", 10)
{npc_bram_recruited && blossom_partner != "bram":
    ~ add_hearts("bram", 30)
}
{npc_linnea_recruited && blossom_partner != "linnea":
    ~ add_hearts("linnea", 30)
}
{npc_rook_recruited && blossom_partner != "rook":
    ~ add_hearts("rook", 30)
}
{npc_tamsin_recruited && blossom_partner != "tamsin":
    ~ add_hearts("tamsin", 30)
}
-> DONE
