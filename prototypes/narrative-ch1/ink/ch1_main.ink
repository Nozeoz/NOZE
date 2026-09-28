// Chapter 1 main path: MQ-101 → MQ-117, following docs/14 §9.
// Each knot is one scene. The game decides WHEN a scene plays (see src/content.js, SCENES);
// the scene decides WHAT happens and sets the flags.

// ─────────────────────────────────────────────── MQ-101 Waking at the Ashen Throne
=== mq101_waking ===
Wet grass. Cold stone at your back. Somewhere, water drips. #scene:The Ashen Throne #bg:dawn
You open your eyes. A tiny flame wearing a tiny golden crown hovers an inch from your nose.
Oh good, you're not dead. Again. #speaker:flicker #mood:smug
* [Who are you?]
    Who… are you? #speaker:you
    Rude. I'm Flicker. Last spark of the Heartflame. Your guide, your conscience, your very small light in the dark. #speaker:flicker
* [Where am I?]
    Where am I? #speaker:you
    Excellent question. Terrible answer: I'm not entirely sure. I'm Flicker, though, and I'm here too, so that's something. #speaker:flicker
* [Is that a crown?]
    Is that… a crown? #speaker:you
    It's a very small crown for a very important flame. I'm Flicker. Keep up. #speaker:flicker #mood:smug
- You look different. Younger. Muddier. Do you remember your name? #speaker:flicker #mood:squint
Type your name. #input:var_player_name
{var_player_name}. Yes. That sounds right. It tastes right, too. Like toast. #speaker:flicker #mood:happy
And when people bowed to you, what did they call you? #speaker:flicker
* [King]
    ~ var_title = "King"
* [Queen]
    ~ var_title = "Queen"
* [Monarch]
    ~ var_title = "Monarch"
- {var_title} {var_player_name}. It suits you. Well. It suited you. We'll get there. #speaker:flicker
Behind you stands a stone throne, split down the middle and furred with moss. Ash sits in every crack.
That's the Ashen Throne. Yours, I think. You were sitting on it for… a while. #speaker:flicker
* Then I have a kingdom to find. #speaker:you #tone:regal
    ~ tone("regal")
    Ooh. Chin up and everything. I missed that. #speaker:flicker #mood:happy
* At least I woke up to a friendly face. #speaker:you #tone:warm
    ~ tone("warm")
    I'm a face! You think I'm a face! #speaker:flicker #mood:happy #emote:heart
* Comfortable. Five stars. Would wake up in the mud again. #speaker:you #tone:wry
    ~ tone("wry")
    Ha! The mud's free, at least. Everything else costs. #speaker:flicker
- Down the slope, a still pond catches the grey sky. In it, a stranger looks back at you: about twenty, tired eyes, a coat that used to be royal.
Past the pond, the world disappears into a violet mist that glitters teal at the edges.
See that? That's the Veil. Pretty by day. At night it gets… bitey. #speaker:flicker #mood:worried
We need a fire before dark. Ten wood and five stone. You remember sticks? Pointy, woody, very popular. #speaker:flicker
~ ch1_woke = true
~ unlock("activity:gather")
~ unlock("recipe:sig_twine")
-> DONE

=== mq101_campfire ===
You ring the stones at the foot of the throne and stack the sticks inside. #scene:The Ashen Throne #bg:day
Allow me. #speaker:flicker #mood:smug
Flicker dives in. For a moment nothing happens. Then the sticks catch with a soft whump, and warmth hits your face.
Ahhh. That's the stuff. I haven't been properly warm in… a long time. #speaker:flicker #mood:happy
~ give("mat_wood", -10)
~ give("min_stone", -5)
~ ch1_campfire = true
~ unlock("activity:cook")
Now we can cook, too. Cooking is free. Eating is free. I love free. #speaker:flicker
-> DONE

// ─────────────────────────────────────────────── MQ-102 The First Night
=== mq102_first_night ===
{
- not ch1_campfire:
    The light is going. You scrape together every stick in reach, and Flicker lights them with a squeak of panic. #scene:The Ashen Throne #bg:night
    ~ ch1_campfire = true
    ~ unlock("activity:cook")
- else:
    The sun drops behind the hills, and the Veil comes down the valley like a slow violet tide. #scene:The Ashen Throne #bg:night
}
Beyond the firelight, the mist glitters teal. Something moves in it. Several somethings.
Duskwolves. They don't like light. Stay in the light. That's the whole plan. #speaker:flicker #mood:worried
~ temp fed = 0
- (watch)
{
- fed == 0: The fire is already burning low.
- fed == 1: The wolves circle closer. Two pairs of eyes. Then five.
- else: Hours pass. The wolves are patient.
}
+ {item("mat_wood") > 0} [Feed the fire with a stick.]
    ~ give("mat_wood", -1)
    The flames jump. The eyes in the mist blink and back away.
+ [Break a branch off the dead tree beside the throne.]
    The branch cracks like a whip. The wolves flinch. So does Flicker.
* [Step into the dark for more sticks.]
    ~ add_stat("exposure", 25)
    Three steps past the light, the cold gets inside your coat. Whispers brush your ears in no language you know. You grab an armful of sticks and run back.
    What did I say? What did I literally just say? #speaker:flicker #mood:angry
    That cold is Exposure. Out in the Veil it builds up in you. Light and fire burn it off. #speaker:flicker
-
~ fed++
{fed < 3: -> watch}
Near dawn, one wolf loses patience and lunges. You swing a burning branch. It connects, and the wolf comes apart into mist, like breath on a cold morning.
They don't die. They just… go back into the Veil. #speaker:flicker
Grey light. Birdsong. The Veil pulls back up the valley. #bg:dawn
We did it! Night one! I'm so proud of us. Mostly me. #speaker:flicker #mood:happy
Flicker sinks into the embers. The whole fire turns gold and rises into a steady, living flame.
This is the Heartflame. Well, a piece of it. Everything its light touches is safe. That's your Realm, Majesty. Small. Cute. A starter kingdom. #speaker:flicker #mood:proud
~ add_stat("exposure", -100)
~ add_stat("beacon", 1)
~ ch1_survived_night1 = true
~ unlock("beacon:1")
-> DONE

// ─────────────────────────────────────────────── MQ-103 Old Royal Fields
=== mq103_old_fields ===
Morning. Flicker bobs ahead of you down the hill, towards a patchwork of overgrown fields. #scene:Old Royal Fields #bg:day
Old stone markers stand at the corners, each carved with a sun. Moss has eaten half of them.
Somebody grew food here for a lot of people, once. #speaker:flicker
* [Look closer at the sun carvings.]
    The sun has a face, a crown, and twelve rays. You feel sure you've seen it before. You can't think where.
    ~ lore_sun_sigil = true
* [Get to work.]
- You lash a flat stone to a stick for a hoe and clear six patches of earth.
In the roots of an old hedge you find a clay jar of wild turnip seeds, still good.
~ plant("crop_turnip", 6)
Turnips! Four days of sun and water, and then… turnips. #speaker:flicker #mood:happy
Water them every day. Or find a friend who likes watering. Just a thought. #speaker:flicker
~ unlock("activity:fields")
A bell jingles on the old road. A huge shaggy creature plods out of the mist, hung with pots and lanterns, pulling a painted cart.
Darling! A customer! In the Veil! Do you know how rare you are? #speaker:mira #mood:happy
I'm Mira. Mira Caravel. This is Humphrey. Don't feed him your fingers. #speaker:mira
Humphrey sneezes. Several lanterns rattle.
* Welcome to my kingdom. Such as it is. #speaker:you #tone:regal
    ~ tone("regal")
    Your kingdom! Oh, I love a big dream. Big dreams buy things. #speaker:mira #mood:happy
* Nice to meet you, Mira. And Humphrey. #speaker:you #tone:warm
    ~ tone("warm")
    Manners! Out here! Humphrey, remember this face. #speaker:mira #mood:happy
* Are you lost, or is this a very bad road? #speaker:you #tone:wry
    ~ tone("wry")
    Both, darling. Always both. That's where the customers are. #speaker:mira
- She looks at your coat, then at your field, then at your coat again.
Tell you what. I'll buy whatever you grow or forage, any day I'm passing. And here's a free sample. #speaker:mira
~ add_stat("gold", 50)
~ give("seed_carrot", 4)
~ give("crop_carrot", 1)
Fifty coins for your first sale, four carrot seeds, and one carrot. Mossbuns go silly for carrots. Call it an investment in a very muddy future. #speaker:mira #mood:wink
I come through on Tuesdays and Fridays. Bring coin, or bring gossip. #speaker:mira
~ npc_mira_met = true
~ unlock("activity:caravan")
~ ch1_first_crops = true
She's lovely. She's also going to take all our money. Both things can be true. #speaker:flicker
-> DONE

// ─────────────────────────────────────────────── MQ-105 Pacts of the Vale (intro)
=== mq105_intro ===
By the fire, Flicker is unusually quiet. Then: #scene:The Ashen Throne #bg:dusk
Did you see them by the river? Little round rabbits with moss on their ears? #speaker:flicker
Those are Mossbuns. Veilkin: creatures born where the Veil mixed with the wild. They're not evil. The Veil is just home, for them. #speaker:flicker
And you can make Pacts with them. Because you're special. Don't ask me how I know that. I don't know how I know that. #speaker:flicker #mood:squint
Offer a Mossbun a carrot and it might stay. Some creatures want a gift. Some want to be beaten fair and square first. #speaker:flicker
~ ch1_meadow_shown = true
~ unlock("location:meadow")
-> DONE

=== loc_meadow ===
{
- not ch1_first_pact:
    -> first_pacts
- not ch1_emberkit_pact && item("sig_twine") > 0:
    Mossbun Meadow. The Emberkit is back, sunning itself on a rock with its tail curled round it like a scarf. #scene:Mossbun Meadow #bg:day
    -> emberkit
- ch1_vs_complete && not npc_juniper_recruited:
    -> sq115_herd
- else:
    -> idle
}
= first_pacts
Mossbun Meadow is all clover and soft hills. Round shapes with mossy ears freeze as you arrive. #scene:Mossbun Meadow #bg:day
{item("crop_carrot") < 1:
    The Mossbuns sniff the air, find nothing interesting about you, and hop away.
    You came to a negotiation empty-handed? Carrots, Majesty. Mira sells them. Or grow some. #speaker:flicker
    -> DONE
}
* [Kneel and hold out the carrot.]
- One Mossbun, braver than the rest, hops over. It sniffs the carrot. It sniffs you. Something hums in your chest, low and warm.
~ give("crop_carrot", -1)
It takes the carrot and leans its whole weight against your knee.
That's a Pact! An Offering Pact! Look at it, it's already bossing you around. #speaker:flicker #mood:happy #emote:heart
~ add_stat("familiars", 1)
Back at the fields you set up a little Field Post by the turnips. The Mossbun claims it at once and starts nudging the soil with its nose.
Mossbuns love tending crops. Now your field gets watered even on days you're busy being a {var_title}. #speaker:flicker
~ ch1_first_pact = true
~ unlock("familiar:tending")
The meadow rustles. A small orange fox with an ember for a tail darts out of the clover, steals the carrot top, and sits there chewing it at you.
An Emberkit! Those don't take gifts. They take you seriously, or not at all. #speaker:flicker
{item("sig_twine") < 1 && item("mat_fiber") >= 3:
    Twist some fiber into a Twine Sigil. Quick! I'll hold your… nothing. I'll watch. #speaker:flicker
    ~ give("mat_fiber", -3)
    ~ give("sig_twine", 1)
}
{item("sig_twine") < 1:
    The Emberkit yips once and vanishes into the grass.
    We'll need a Twine Sigil for that one. Three fiber, twisted with purpose. Come back when you have it. #speaker:flicker
    -> DONE
}
-> emberkit
= emberkit
The Emberkit circles you, tail blazing.
* [Dodge its first pounce.]
    You roll aside. It skids past, surprised and pleased.
* [Stand your ground.]
    It singes your sleeve and bounces off, delighted.
- Now! The sigil! #speaker:flicker
* [Wrap the Twine Sigil round your hand and reach for it.]
- The sigil flares. For a moment you see a thread of light between you and the little fox. It stops. It sits. It sneezes a spark.
~ give("sig_twine", -1)
~ add_stat("familiars", 1)
~ add_stat("power", 1)
~ ch1_emberkit_pact = true
A Subdue Pact. It respects you now. That's the most an Emberkit respects anyone. It'll fight at your side, too. #speaker:flicker #mood:proud
-> DONE
= idle
Mossbun Meadow hums with bees. {~A Mossbun is asleep on its back in the clover.|Two Mossbuns are having a slow, serious argument about a dandelion.|Your Mossbun's cousins watch you from a respectful distance.} #scene:Mossbun Meadow #bg:day
You gather what the meadow offers.
~ give("frg_forage", 3)
~ give("mat_fiber", 2)
~ give("frg_healing_herb", 1)
-> DONE

// ─────────────────────────────────────────────── MQ-104 The Old Oak
=== mq104_smoke ===
A thin line of smoke rises in the north-west, where an old windmill leans against the sky. #scene:Dawnmere Vale #bg:day
Smoke means fire. Fire means people. People means… actually, a lot of things. Let's go and look. Carefully. #speaker:flicker
~ ch1_smoke_seen = true
~ unlock("location:windmill")
-> DONE

=== loc_windmill ===
{
- npc_bram_recruited:
    -> after
- npc_bram_found:
    The windmill creaks. Bram looks up from his fire. #scene:Windmill Ruin #bg:day
    Back again. Did you bring it? #speaker:bram
    -> check_items
}
The Windmill Ruin creaks in the wind. Its sails hang in ribbons. Someone has patched the door with planks from a boat. #scene:Windmill Ruin #bg:day
Inside, by a smoky fire, a big grey-bearded man sits with a bloody bandage round one leg and a hammer in his fist.
Don't just stand there gawping, kid. Either help or finish robbing me. #speaker:bram #mood:grumpy
~ npc_bram_found = true
* Stand down. I mean you no harm. #speaker:you #tone:regal
    ~ tone("regal")
    Stand down. Ha. Haven't heard that in twelve years. #speaker:bram
* I'm not here to rob you. I saw your smoke. #speaker:you #tone:warm
    ~ tone("warm")
    Then you're the first thing in this valley that isn't. #speaker:bram
* Rob you of what? The ambience? #speaker:you #tone:wry
    ~ tone("wry")
    Cheeky. Good. Cheeky means you're not a ghost. #speaker:bram
- Bram. Bram Holloway. A Duskwolf got my leg two nights back. Fever's coming, I can feel it. #speaker:bram
A torn coat hangs on a nail. On the shoulder is a faded badge: a compass crossed with a sword.
Aldmark Dominion. Expedition Corps. I came into this mist with a whole survey team, twelve years ago. I'm what's left. #speaker:bram
I need Healing Herbs. Green, little white flowers. Three. And food. Real food, cooked. Can you manage that? #speaker:bram
He's proud. He won't ask twice. #speaker:flicker
~ unlock("quest:bram_herbs")
-> check_items
= check_items
{
- item("frg_healing_herb") >= 3 && item("food_any") >= 1:
    -> recruit
- item("frg_healing_herb") >= 3:
    Herbs, good. Now something hot. Cook it at your fire. Anything but mud. #speaker:bram
- item("food_any") >= 1:
    Smells good. But this leg needs herbs first. Three. White flowers. #speaker:bram
- else:
    Three Healing Herbs and one cooked meal. I'll be here. Not like I can go anywhere. #speaker:bram
}
-> DONE
= recruit
You hand over the herbs and the food. Bram chews the herbs into a paste, packs his wound, and eats like a man who has lived on pride for a week.
~ give("frg_healing_herb", -3)
~ give("food_any", -1)
That's… that's better. Thank you, kid. #speaker:bram
He stares into the fire for a while.
Twelve years I waited for a ship that wasn't coming. You get good at waiting. You forget how to do anything else. #speaker:bram
* I have a throne, a fire, and a field of turnips. I need a carpenter. #speaker:you #tone:regal
    ~ tone("regal")
* Then stop waiting. Come and build something with me. #speaker:you #tone:warm
    ~ tone("warm")
* I can't pay you. But the view is great, and the flame talks. #speaker:you #tone:wry
    ~ tone("wry")
    I heard that. #speaker:flicker
- Bram looks at you for a long moment. Then at Flicker. Then at his hammer.
Measure twice, cut once, complain forever. That's carpentry, kid. #speaker:bram
…Might as well build something that stays put. #speaker:bram #mood:smile
~ npc_bram_recruited = true
He pulls a waterlogged notebook from inside his coat.
Here. My survey report. Read it if you want to know what this mist does to people. #speaker:bram
Dominion Expedition Corps, Survey 7. Day 19. Compass useless. Veilglass readings off every scale. We've lost Harlow and the Keane brothers. The mist sings at night. If anyone reads this: we did not go mad. It really does sing. #style:note
~ give("key_expedition_report", 1)
~ unlock("building:lodge")
~ unlock("recipe:food_baked_potato")
A carpenter! Bram can build anything, Majesty. Homes, workshops, and I'm hoping a little shelf for me. #speaker:flicker #mood:happy
-> DONE
= after
The windmill is quiet. Bram's tools have moved to his Lodge by your fire, but his old camp still smells of pipe smoke. #scene:Windmill Ruin #bg:day
{~On the wall, someone has carved a tally of days. It stops somewhere past four thousand.|A ship's lantern hangs from a nail. It has been polished, recently and often.|Under a loose board you find a little carved wooden bird. You put it back.}
You pick up a few useful things on the way home.
~ give("mat_wood", 6)
~ give("frg_healing_herb", 1)
-> DONE

// ─────────────────────────────────────────────── MQ-106 The Lost Healer
=== mq106_lost_healer ===
Dusk. A bell rings, thin and far away, from the east. Once. Twice. Then too many times, too fast. #scene:The Ashen Throne #bg:dusk
That's the old chapel bell. Someone's out there at dusk. Idiot. Or brave. Usually both. #speaker:bram
Majesty, a person is ringing that. A scared one. #speaker:flicker #mood:worried
* [Run for the chapel.]
- You cross the river on stepping stones as the Veil slides down the valley. #scene:The Ruined Chapel #bg:night
The Ruined Chapel has no roof, only arches and ivy. Inside, a young woman with an ash-blonde braid is feeding a tiny fire with pages torn from a hymnbook.
Pale shapes circle the chapel in the mist. A deer. A fox. A boar. Their eyes are white and empty.
Hollowed. Creatures the Hunger got into. Don't let them touch you. #speaker:flicker #mood:worried
Stay back! They're drawn to— oh. You're not one of them. #speaker:linnea #mood:scared
I'm Linnea. I've kept this fire alive since noon. I'm running out of hymns. #speaker:linnea
~ temp watch = 0
- (defend)
~ watch++
{
- watch == 1: The first Hollowed deer steps into the doorway. The fire hisses.
- watch == 2: Midnight. A boar batters at the broken wall. Linnea's hands are shaking. Her voice isn't.
- else: The darkest hour. The mist presses in so thick you can hear it whisper.
}
+ [Feed the fire with broken pews.]
    You throw on the last splinters of a pew. The light swells and the Hollowed flinch back.
+ [Guard the doorway.]
    You plant yourself in the arch, stick up. Something white-eyed snaps at you and retreats, hissing mist.
    ~ add_stat("exposure", 10)
    Hold still. Yarrow. It stings, sorry. #speaker:linnea
    She presses a green poultice to your arm, and the cold drains out of it.
+ [Help Linnea keep the hurt Mossbun warm.]
    A Mossbun with a torn ear is tucked in her shawl. You hold it close to the fire until it stops shaking.
    ~ add_hearts("linnea", 30)
- {watch < 3: -> defend}
Dawn comes all at once, the way it does after a long night. The Veil pulls back, and the Hollowed go with it. #bg:dawn
Linnea sits down on the chapel step as if her strings have been cut.
My village was called Marsh End. The Hollowing came through it in one night. I'm a healer. I couldn't heal any of it. #speaker:linnea #mood:sad
I've been walking ever since. #speaker:linnea
{season() == "Spring" && stat("season_day") == 5:
    It's my birthday, actually. Today. I didn't think I'd see it. #speaker:linnea #mood:smile
    ~ deed_saved_linnea_on_birthday = true
    ~ add_hearts("linnea", 100)
}
* My realm needs a healer. I'd be honoured if it were you. #speaker:you #tone:regal
    ~ tone("regal")
* Come home with me. We have a fire that doesn't go out. #speaker:you #tone:warm
    ~ tone("warm")
* You were out here alone with a boar problem and a hymnbook. Come on. #speaker:you #tone:wry
    ~ tone("wry")
- Linnea laughs, surprised at herself.
If you have a fire, you have people who get hurt near it. You'll need someone to mend them… if that's alright. #speaker:linnea
~ npc_linnea_recruited = true
~ add_stat("exposure", -100)
~ unlock("building:clinic")
~ unlock("recipe:food_herb_tea")
From now on, if something knocks you flat, you wake up in Linnea's care instead of a ditch. Upgrade! #speaker:flicker #mood:happy
-> DONE

// ─────────────────────────────────────────────── MQ-107 A Roof and a Name
=== mq107_plans ===
Bram is drawing in the dirt with a stick when you wake. #scene:The Ashen Throne #bg:day
Three people and a flame can't sleep under a broken chair forever. We need a roof. A proper one. #speaker:bram
A Longhouse. Long hall, big hearth, room for a table. Somewhere to stand when you want to sound important. #speaker:bram
It'll cost us. Eighty wood, fifty stone, and a hundred and fifty coins for nails and rope. Bring it and I'll have her up in two days. #speaker:bram
~ ch1_longhouse_planned = true
~ unlock("building:longhouse")
A Longhouse! That's the Throne's next tier, Majesty. From ruin to… slightly bigger ruin, with a roof! #speaker:flicker #mood:happy
-> DONE

=== mq107_hob ===
An old man in a straw hat is standing at the edge of your turnip field, leaning on a hoe, crying a little. #scene:Old Royal Fields #bg:day
Sorry. Sorry. I followed a light through the mist. Didn't think anyone lived out here any more. #speaker:hob
Hob Furrow. I farm. Farmed. My farm's somewhere back there, under all that. #speaker:hob
* This realm could use a farmer. Stay. #speaker:you #tone:regal
    ~ tone("regal")
* Then farm here. You're welcome to stay. #speaker:you #tone:warm
    ~ tone("warm")
* Our turnips could use supervision. Stay. #speaker:you #tone:wry
    ~ tone("wry")
- Stay? Just like that? #speaker:hob #mood:surprised
Well. My back's bad, but my hands are good. I'll earn my bread. #speaker:hob #mood:smile
~ npc_hob_arrived = true
~ add_settler("Hob Furrow", "Farmer")
Our first settler! Ordinary people choosing to follow you. That's how kingdoms start, Majesty. #speaker:flicker #mood:proud
-> DONE

=== mq107_founding ===
The Longhouse stands at the foot of the Ashen Throne, its raw timber still smelling of sap. Bram slaps the doorframe like the flank of a horse. #scene:The Longhouse #bg:day
Solid. She'll outlast me. That's the idea. #speaker:bram
Linnea has hung bundles of drying herbs from the rafters. Hob has put a jar of wildflowers on the new table. Nobody asked him to.
Every kingdom needs a name. Preferably not "Mudhold". #speaker:flicker
Name your kingdom. #input:var_kingdom_name
{var_kingdom_name}. {var_kingdom_name}! Oh, say it again. #speaker:flicker #mood:happy
And a banner. Something people see from far away and think: home. #speaker:flicker
Design your banner. #banner
Everyone is looking at you, waiting for you to say something.
* We're not much yet. But every great kingdom began with a roof, a fire, and people who stayed. #speaker:you #tone:regal
    ~ tone("regal")
    Bram grunts approval. Hob wipes his eyes on his hat.
* Thank you. All of you. I couldn't have done any of this alone. #speaker:you #tone:warm
    ~ tone("warm")
    Linnea smiles into her sleeve. Bram pretends to have something in his eye.
* Welcome to {var_kingdom_name}. Population: four, and a very small fire. #speaker:you #tone:wry
    ~ tone("wry")
    I heard that! #speaker:flicker #mood:angry
    Hob laughs so hard he has to sit down.
- To {var_kingdom_name}. #speaker:bram
To {var_kingdom_name}. #speaker:linnea
To the {var_title}! #speaker:hob
The Heartflame flares on its brazier. For a moment the Veil at the edge of the valley draws back, just a little, as if something has been decided.
~ kingdom_rank = 1
~ ch1_founded = true
~ ch1_founded_day = stat("day")
~ deed_rank_up = true
~ add_stat("ra", 5)
~ unlock("rank:1")
{var_kingdom_name} is a Hamlet! New blueprints: Hut, Tent, Commons Field, Beacon Tower. And now settlers can find us. #speaker:flicker #mood:proud
-> DONE

// ─────────────────────────────────────────────── MQ-110 Below the Granary
=== mq110_granary ===
Hob walks you to a round stone building half-sunk in brambles at the edge of the Old Royal Fields. #scene:The Old Granary #bg:day
Royal granary, they say. Fed a whole town through winter, once. Walls are sound. Roof's gone. Floor's… odd. #speaker:hob
Fix it and we'd have somewhere to keep real food. The Longhouse larder only holds twenty rations. #speaker:hob
A Restoration Project! Bring the three bundles and the kingdom restores the rest. It's like shopping, but you pay in turnips. #speaker:flicker
~ ch1_granary_shown = true
~ unlock("project:granary")
-> DONE

=== mq110_stairs ===
The last beam goes up. The Granary has a roof again, and Hob has already started arguing with a Mossbun about where the turnips go. #scene:The Old Granary #bg:day
Then Bram lifts a rotten floorboard and goes very still.
Kid. Come and look at this. #speaker:bram
Stone stairs spiral down into the dark. Cold air breathes up out of them, and with it a faint violet glow.
The Sunken Cellars. The old city had a whole world underneath it. Storerooms, tunnels, vaults. #speaker:flicker
Something down there is humming. Like a song stuck in a wall. #speaker:flicker #mood:worried
~ ch1_granary_restored = true
~ world_cellars_open = true
~ unlock("activity:dive")
The deeper you go, the harder it gets. Every few floors there's a Waystone, so you won't have to start from the top. #speaker:flicker
-> DONE

// ─────────────────────────────────────────────── MQ-108 Crowfeather
=== mq108_crowfeather ===
A crash from the storeroom. Then Hob's voice, high and furious: "Thieves!" #scene:The Longhouse #bg:night
Three hooded shapes are running for the trees with sacks on their shoulders: a skinny one with a sling, a huge one carrying two sacks, and a small one carrying your only good pot.
~ add_stat("food", -6)
* [Give chase.]
- You catch them at the edge of the light. The three stop and turn, but they aren't looking at you. They're looking past you. #scene:The Edge of the Light
A young man drops out of an oak and lands between you and them. Black hair with one white streak. A cloak of crow feathers. Two knives.
Evening, Your Royal Muddiness. #speaker:rook #mood:smug
You're Rook. Everyone in the Vale knows you're Rook. #speaker:flicker #mood:angry
Magpie, Jackdaw, Finch: go. I'll dance with the {var_title}. #speaker:rook
~ npc_rook_met = true
He comes at you fast and low.
* [Parry.]
    Knife meets stick. The stick loses a chip. You don't.
* [Sidestep.]
    He cuts the air where you were, and grins like that was a compliment.
- He feints left. Twice. The third time he means it.
* [Read the feint and catch his wrist.]
    You catch his wrist on the downswing. One knife spins away into the grass.
* {ch1_emberkit_pact} [Whistle for the Emberkit.]
    A streak of orange fire hits Rook's ankle. He yelps and hops, and you sweep his feet out from under him.
- Rook lands flat on his back in the wet grass, winded, with your stick at his throat.
At the treeline, the gang has stopped running. The big one, Jackdaw, has put the sacks down.
Go on, then. Crowns always finish it. #speaker:rook #mood:defiant
{npc_linnea_recruited:
    They're hungry. Look at them. Mostly they're just hungry. #speaker:linnea
}
{npc_bram_recruited:
    A thief steals twice, kid. Your call. It's always your call now. #speaker:bram
}
Flicker hovers close, and for once says nothing at all.
* [Spare him.]
    -> spare
* [Banish him.]
    -> banish
= spare
~ deed_spared_rook = true
~ kingdom_reputation = "merciful"
You lower the stick.
* Get up. Nobody in {var_kingdom_name} gets finished. Not even thieves. #speaker:you #tone:regal
    ~ tone("regal")
* Get up. You're hungry, aren't you? All of you. #speaker:you #tone:warm
    ~ tone("warm")
* Get up. You're getting mud on my nice grass. #speaker:you #tone:wry
    ~ tone("wry")
- Rook doesn't move. He stares at you as if you've started speaking another language.
…Why? #speaker:rook
* A kingdom with room only for good people is going to be very empty. #speaker:you
* Because you stole food, not gold. #speaker:you
- He gets up slowly. Behind him the gang has crept closer: Magpie with her sling, Jackdaw with his sacks, little Finch with the pot.
You're mad. Fine. Mad I can work with. #speaker:rook
Here's the deal, Majesty. My lot eat. Four mouths, seven days. Get twenty-eight rations into your granary inside a week, and we're yours. #speaker:rook
Miss it and we walk. No hard feelings. Some hard feelings. #speaker:rook #mood:smug
~ npc_rook_trial = "active"
~ add_stat("food", 6)
~ unlock("quest:rooks_trial")
Twenty-eight rations, and our own people eat one each a day. We'll need fields, forage, and a proper granary. And fewer thieves. Oh, wait. #speaker:flicker
-> DONE
= banish
~ deed_banished_rook = true
~ kingdom_reputation = "stern"
* Take your gang and go. Come near my people again and I won't be this polite. #speaker:you #tone:regal
    ~ tone("regal")
* Go. Please. Find somewhere that can feed you, because we can't. #speaker:you #tone:warm
    ~ tone("warm")
* Leave the sacks. Take your knives. Don't come back. #speaker:you #tone:wry
    ~ tone("wry")
- Rook gets up, collects his knife from the grass, and bows. It's almost not mocking.
Noted, Majesty. Sharp crown you've got. #speaker:rook
The Crowfeather Gang melts into the Veil. Jackdaw leaves the sacks behind. Finch does not leave the pot.
~ add_stat("food", 4)
He'll be back. His kind always comes back. Hopefully with better manners. #speaker:flicker
~ unlock("quest:banished")
-> DONE

// ─────────────────────────────────────────────── MQ-109 Rook's Trial
=== mq109_trial_start ===
Rook is sitting on the Longhouse roof when you come out in the morning, eating one of your turnips. #scene:The Longhouse #bg:dawn
Clock's ticking, Majesty. Seven days. #speaker:rook
Everyone here eats one ration a day from the stores, so every mouth counts twice. #speaker:hob
And the Longhouse larder only holds twenty. For twenty-eight, you'll want the Old Granary fixed. #speaker:hob
Fields, foraging, Mira's caravan, and a Commons Field for settlers to work. Food Stock, Majesty. It's the heartbeat of a kingdom. A very hungry heartbeat. #speaker:flicker
~ unlock("building:commons")
-> DONE

=== mq109_join ===
Rook is waiting outside the Granary at dawn, counting sacks, lips moving. #scene:The Granary #bg:dawn
{npc_rook_trial == "active":
    Twenty-eight. Twenty-nine. Huh. You actually did it. Inside the week. #speaker:rook #mood:surprised
    ~ add_hearts("rook", 100)
- else:
    Twenty-eight. Took you long enough. #speaker:rook
    He doesn't sound annoyed. He sounds like someone who expected to be let down, and wasn't. Quite.
}
Magpie, Jackdaw and Finch stand behind him with everything they own in three small bundles. Finch still has your pot.
Alright. We're yours. Or… we're here. Let's say here. I don't kneel. #speaker:rook
* Welcome to {var_kingdom_name}, Rook. #speaker:you #tone:regal
    ~ tone("regal")
    Don't make it sound official. …It's a bit official. Fine. #speaker:rook
* Nobody's asking you to kneel. #speaker:you #tone:warm
    ~ tone("warm")
    Good. My knees are for running. #speaker:rook
* Finch can keep the pot. #speaker:you #tone:wry
    ~ tone("wry")
    Finch hugs the pot. Rook very nearly smiles.
- They pitch three patched tents by the treeline without being asked. Rook climbs back onto the Longhouse roof and stays there, watching the Veil.
~ npc_rook_recruited = true
~ npc_rook_trial = "done"
~ add_settler("Magpie", "Slinger")
~ add_settler("Jackdaw", "Brute")
~ add_settler("Finch", "Cutpurse")
~ unlock("building:scout_post")
A scout! The Scout's Post means maps, bounties, and one day expeditions. And a very annoying lookout. #speaker:flicker #mood:happy
-> DONE

=== mq109_deadline ===
Rook finds you at breakfast. #scene:The Longhouse #bg:dawn
Week's up, Majesty. {stat("food")} rations. Needed twenty-eight. #speaker:rook
He shrugs, and doesn't leave.
Thing is, you fed us every day anyway. Nobody does that. We'll stick around till you get there. Don't make it weird. #speaker:rook
~ npc_rook_trial = "late"
-> DONE

// ─────────────────────────────────────────────── MQ-111 Sparks in the Dark
=== mq111_captive ===
Floor three is quieter than the others. Too quiet. At the end of a flooded corridor, something has built a cage out of old iron and roots. #scene:Sunken Cellars · Floor 3 #bg:cellar
Inside, a tall young woman in a scorched leather apron is trying to pick the lock with a hairpin.
Oh! U-um. Hi. Are you… real? Sorry. That's a weird question. #speaker:tamsin #mood:shy
I'm Tamsin. I was a smith's apprentice. With the Dominion. They left in a hurry and I… wasn't in the hurry. #speaker:tamsin
~ npc_tamsin_found = true
* [Smash the lock.]
    You hit the lock. Your stick breaks. The lock does not.
    Th-the hinge pin. It's copper. Soft. Hit it there, not— yes! There! #speaker:tamsin
* [Ask her how to open it.]
    How do I get you out? #speaker:you
    The hinge pin's copper. Soft. One good hit, right at the top. #speaker:tamsin
- You hit the hinge. The door swings open.
Tamsin climbs out, unfolds to her full height, and looks down at your stick-sword with deep professional pain.
Is that… your weapon? #speaker:tamsin
If you bring me ten copper ore, I can build a forge. And make you a real sword. Not… that. #speaker:tamsin #mood:determined
You lead her up through the tunnels and back into the light.
~ unlock("quest:tamsin_ore")
-> DONE

=== tamsin_forge ===
You pile ten chunks of copper ore at Tamsin's feet. She stares at them. #scene:The Longhouse #bg:day
Oh. Oh, these are good. Look at the grain on this one— #speaker:tamsin #mood:happy
She builds a forge out of river stones and Bram's spare bricks in a single afternoon, talking the whole time, not stammering once.
Bellows! Flux! Heat! Okay. Stand back. Further. Further than that. #speaker:tamsin
The copper glows. The hammer rings. By evening she presses a short, bright sword into your hands, still warm.
~ give("min_copper_ore", -10)
~ add_stat("power", 1)
It's not a sword yet. It's… it's a promise of a sword. But it'll cut Hollowed. #speaker:tamsin #mood:shy
* A fine blade. The realm is in your debt. #speaker:you #tone:regal
    ~ tone("regal")
* It's beautiful, Tamsin. Thank you. #speaker:you #tone:warm
    ~ tone("warm")
* It's so much pointier than my stick. #speaker:you #tone:wry
    ~ tone("wry")
- Tamsin goes red to the ears and hides behind the anvil.
C-can I stay? I'd need a smithy. And coal. And… people who don't leave in a hurry. #speaker:tamsin
~ npc_tamsin_recruited = true
~ unlock("building:smithy")
A blacksmith! Better tools, better weapons, and metal fittings for bigger buildings. Tamsin matters, Majesty. #speaker:flicker #mood:happy
-> DONE

// ─────────────────────────────────────────────── MQ-112 The Shell That Holds a Tower
=== mq112_ruinback ===
~ ruinback_tries++
The tenth floor opens into a vast drowned hall. In the middle of the black water sits a hill. #scene:Sunken Cellars · Floor 10 #bg:cellar
Then the hill opens one eye.{ruinback_tries > 1: It remembers you.}
A tortoise the size of a house rises out of the water. On its shell stands a ruined stone tower, and at the top of the tower, something glints gold.
Ruinback. A Guardian. The Veil's got into it: see the mist in its eyes? #speaker:flicker #mood:worried
And up there… Majesty. That's a piece of the Regalia. I can feel it from here. #speaker:flicker
Ruinback's head sweeps across the hall like a battering ram.
* [Duck and strike at its foreleg.]
* [Run up its tail onto the shell.]
- {stat("power") >= 3: -> win}
Your blows skitter off stone-hard scales. Ruinback shrugs, and the wave off its shoulders throws you across the hall.
{npc_linnea_recruited: You come to beside the Waystone with one of Linnea's poultices on your forehead and Flicker shouting at you.|You come to beside the Waystone, soaked, with Flicker shouting at you.}
We need a better blade, or more friends with teeth! Tamsin's forge, an Emberkit, anything! #speaker:flicker #mood:angry
~ add_stat("energy", -100)
-> DONE
= win
Your {npc_tamsin_recruited:copper blade|blade} bites deep. Ruinback roars, and the Veil pours out of the wound like smoke.
{ch1_emberkit_pact: Your Emberkit darts in and sets the mist alight. For a moment the whole hall glows.}
{npc_linnea_recruited: Linnea's yarrow keeps the cold out of your bones just long enough.}
Ruinback sinks to the floor of the hall, still breathing, eyes clouded violet.
Now, Majesty! Hold out your hand. Trust me! #speaker:flicker
You hold out your hand. Flicker lands in your palm, and light pours out of you both: gold, warm, and very old.
The violet drains from Ruinback's eyes. What's left is an old, tired, enormous tortoise, blinking at you.
Purified. It's just… itself again. #speaker:flicker #mood:amazed
You climb the tower on its shell. At the top, in a nest of moss, lies a heavy gold ring with a sun on its face.
The Signet. #speaker:flicker #mood:serious
When you touch it, the world goes white.
A golden city at dawn. Towers and banners over a sea of people. A crown lowered onto your head. A voice, maybe yours: "For the Halcyon Days." #style:memory
Then it's gone, and you're standing on a tortoise in the dark, holding a ring.
~ give("key_regalia_signet", 1)
~ ch1_signet = true
~ world_regalia_signet = true
~ world_surges_active = true
~ add_stat("ra", 10)
~ unlock("regalia:signet")
I can Purify! I learned a thing! And I feel… taller. Emotionally. #speaker:flicker #mood:happy
Far above you, the mist shivers once. Nobody else seems to notice.
-> DONE

// ─────────────────────────────────────────────── MQ-113 The Founding Feast (VS end)
=== mq113_feast ===
{var_kingdom_name} holds its first feast in the Longhouse. Every lantern you own is lit. #scene:The Founding Feast #bg:feast
Hob roasts turnips six different ways. Bram has carved a new bench for the head of the table and is pretending he hasn't.
{npc_rook_recruited: Rook sits on the rafters instead of the bench. Magpie is trying to teach Finch to juggle the good plates.}
{npc_tamsin_recruited: Tamsin has made everyone copper cups. Hers is the only one that doesn't leak.}
Linnea has woven flowers along the whole length of the table.
- (table)
* [Sit with Bram.]
    Bram raps the new bench with his knuckles.
    Carved it for the kid who's going to be a {var_title}. Sit. It's not for looking at. #speaker:bram #mood:smile
    ~ add_hearts("bram", 50)
    -> table
* {npc_linnea_recruited} [Sit with Linnea.]
    {deed_saved_linnea_on_birthday: A week ago I was burning hymnbooks for warmth, on my birthday. Now look.|Not long ago I was sleeping in ruins. Now look.} #speaker:linnea
    Thank you. For the fire. For all of it. #speaker:linnea #mood:smile
    ~ add_hearts("linnea", 50)
    -> table
* {npc_rook_recruited} [Climb up to Rook on the rafters.]
    Best seat in the house. You can see who's stealing the bread. #speaker:rook #mood:smug
    It's Finch. It's always Finch. …Thanks for this, Majesty. Don't tell anyone I said it. #speaker:rook
    ~ add_hearts("rook", 50)
    -> table
* {npc_tamsin_recruited} [Sit with Tamsin.]
    Th-this cup leaks. I'm so sorry. I'll make you a better one. I'll make you ten. #speaker:tamsin #mood:shy
    ~ add_hearts("tamsin", 50)
    -> table
* [Sit with Hob.]
    My wife would've liked you. She liked anyone who fed people. #speaker:hob #mood:smile
    -> table
* [Share a turnip with Flicker.]
    Flicker eats the whole turnip, somehow, and burps a small blue flame.
    Worth it. #speaker:flicker #mood:happy
    -> table
* [Stand and raise your cup.]
    -> toast
= toast
Everyone goes quiet.
* To the people who stayed. Every crown is held up by many hands. #speaker:you #tone:regal
    ~ tone("regal")
* To all of you. You're the kingdom. I'm just the one with the hat. #speaker:you #tone:warm
    ~ tone("warm")
* To turnips! Our finest subjects! #speaker:you #tone:wry
    ~ tone("wry")
- The cups clatter together. And in the quiet after the cheer, everyone hears it.
From the forest far to the north, voices are singing. Many voices, all on one note.
All that clings is torn. All that is held will bleed. #style:hymn
Let go the hand, the name, the crown, the seed. #style:hymn
Nobody moves. {npc_linnea_recruited: Linnea's hand has found Bram's sleeve.}
That's not a song. That's a warning. #speaker:linnea #mood:scared
I know that tune. I don't know how I know it. #speaker:flicker #mood:serious
The singing stops. Every lantern in the Longhouse flickers at once, then steadies.
~ ch1_vs_complete = true
~ ch1_vs_day = stat("day")
To be continued… #vs_end
-> DONE

// ─────────────────────────────────────────────── SQ-114 Hearth and Home (Marigold)
=== sq114_cart ===
At dusk a small figure comes running up the south road out of the mist, straight for your light: a boy of about eight, with a wooden spoon in his fist. #scene:The South Road #bg:dusk
Help! Mum's cart is stuck and the fog's doing the whispering thing! #speaker:pip
Pip Fenn, you get back here this instant! #speaker:marigold
* [Follow Pip into the Veil.]
- Twenty steps into the mist, you find a cart sunk to its axles, and a woman with a marigold pinned in her hair pushing it with her whole body.
You're the one with the light? Good. Sweetheart, grab that wheel. Pip, lantern high. Higher. #speaker:marigold
~ temp pushes = 0
- (push)
~ pushes++
+ [Put your shoulder to the wheel.]
    The cart lurches forward an inch.
+ [Hold the lantern higher so the whispers back off.]
    The mist hisses away from the light. Pip grins up at you.
- {pushes < 2: -> push}
With a sucking pop, the wheel comes free. You walk the cart home to {var_kingdom_name} with Pip chattering the whole way.
Marigold Fenn. Goldie, if you like me. That's Pip. He likes you already, which is annoying, because now I have to like you too. #speaker:marigold #mood:smile
She looks at your Longhouse, your fire, and your people eating cold turnips.
Oh, sweethearts. No. Build me a kitchen and nobody here eats cold turnip again. #speaker:marigold
~ npc_marigold_met = true
~ unlock("building:kitchen")
-> DONE

=== sq114_kitchen ===
The kitchen's first fire is barely lit before Marigold has three pots going and Pip has been sent for water twice. #scene:The Kitchen #bg:day
Sit. Eat. Then you can go and save the world, sweetheart. #speaker:marigold #mood:smile
It is the best thing you have eaten in a thousand years. Possibly literally.
~ npc_marigold_recruited = true
~ add_settler("Pip", "Child")
~ add_stat("food", 10)
~ unlock("building:tavern")
A cook! Hot meals make happier people, and happier people bring more people. It's a very tasty kind of politics. #speaker:flicker #mood:happy
-> DONE

// ─────────────────────────────────────────────── SQ-115 The Scattered Herd (Juniper)
=== sq115_herd ===
{not npc_juniper_met: -> meet}
{herd_found >= 8: -> boar}
Juniper waves both arms at you from across the meadow. #scene:Mossbun Meadow #bg:day
-> herd
= meet
A tiny woman with teal hair in two puffs is standing on a rock in the middle of the meadow, shouting. #scene:Mossbun Meadow #bg:day
Has anyone seen fourteen Mossbuns?! No, six! Eight? Eight missing! Oh no. Oh no no no. #speaker:juniper #mood:scared
She sees you, jumps off the rock, and grabs both your hands.
You're the one with the light! And a Mossbun! Hi, Mossbun! I'm Juniper. June. A boar came out of the mist, a Hollowed one, and my herd scattered everywhere. #speaker:juniper
Help me round them up? Mossbuns trust people who smell of carrots. You smell a bit like carrots. #speaker:juniper
~ npc_juniper_met = true
~ unlock("quest:herd")
-> herd
= herd
~ temp found = 0
{herd_found > 0: {herd_found} of 8 found. Juniper is keeping count on her fingers, loudly.}
+ [Crouch low and wait for them to come to you.]
    ~ found = 2
    Two Mossbuns creep out of the clover and sit on your boots.
+ {item("sig_treat") > 0} [Rattle a Creature Treat.]
    ~ give("sig_treat", -1)
    ~ found = 4
    Four Mossbuns appear from nowhere and form an orderly queue.
+ [Chase them.]
    ~ found = 1
    You chase one Mossbun in a wide circle. It lets you catch it, out of pity.
-
~ herd_found = herd_found + found
{herd_found >= 8: -> boar}
That's {herd_found}! The rest are hiding deeper in. Come back tomorrow? They're shy in the afternoons. And the mornings. #speaker:juniper
-> DONE
= boar
All eight. All fourteen! Oh, you beautiful fluffy idiots. #speaker:juniper #mood:happy
A grunt from the treeline. The Hollowed boar steps out, white-eyed, trailing mist.
Flicker, now! #speaker:you
Flicker lands in your palm. Gold light pours out. The boar staggers, sneezes, and turns out to be an ordinary, embarrassed pig.
~ add_stat("ra", 3)
Juniper stares at the pig. Then at you.
You didn't hurt him. You fixed him. #speaker:juniper #mood:surprised
That's it. I'm coming with you. All of us are. Fourteen Mossbuns and one pig. You'll need a Den. A big one. #speaker:juniper #mood:happy
~ npc_juniper_recruited = true
~ add_stat("familiars", 2)
~ unlock("building:den")
A beast warden! Juniper will look after every familiar we ever meet. Including the pig, apparently. #speaker:flicker
-> DONE

// ─────────────────────────────────────────────── MQ-116 The Crown's Word
=== mq116_court ===
Word has gone round. On Sunday morning your people come to the Longhouse, all of them, and stand in a nervous line. #scene:Court Day · The Longhouse #bg:day
They want you to rule, Majesty. Properly. Court Day: they bring you their troubles, and you decide. #speaker:flicker #mood:serious
Bram has put the carved bench at the head of the room. It is very nearly a throne.
-> court_petitions ->
-> court_decree ->
The last petitioner bows and goes. The Longhouse doors stand open, and the whole valley seems brighter.
~ kingdom_rank = 2
~ court_held = true
~ deed_rank_up = true
~ add_stat("ra", 10)
~ unlock("rank:2")
{var_kingdom_name} is a Village! Court every Sunday, Decrees, and one day, expeditions. You're really doing it, Majesty. #speaker:flicker #mood:proud
-> DONE

// ─────────────────────────────────────────────── MQ-117 The Old Bridge
=== mq117_bridge ===
Bram unrolls a map on the Longhouse table, weighs the corners down with Tamsin's cups, and taps the northern edge. #scene:The Longhouse #bg:day
The old bridge. Stone arches over the river, and the north road past it. Beyond that, the Veil Wall. #speaker:bram
Fix the bridge, set a Waybeacon at the Wall, and the road opens. Whatever's singing out there, we'll at least see it coming. #speaker:bram
~ ch1_bridge_shown = true
~ unlock("project:bridge")
-> DONE

=== mq117_bridge_done ===
The last stone slides into place. The Old Bridge stands again, three grey arches over the river. #scene:The Old Bridge #bg:day
Tamsin runs her hand along the new iron clamps. Bram stamps on the keystone, twice, and nods.
One more thing. The Wall. #speaker:bram
~ ch1_bridge_restored = true
~ unlock("building:waybeacon")
-> DONE

=== mq117_waybeacon ===
At the far end of the bridge the Veil stands like a wall: a curtain of violet mist taller than the trees, whispering. #scene:The Veil Wall #bg:dusk
Your people set the Waybeacon's last stone. Flicker hovers over it, suddenly shy.
Here goes. #speaker:flicker
The Waybeacon catches. A pillar of gold light rises, and the Veil Wall draws back from it like a curtain on a stage.
Beyond it: a forest of enormous trees and even bigger mushrooms, all softly glowing, and fireflies in their thousands.
Whisperwood. #speaker:flicker #mood:amazed
And very faintly, from somewhere deep inside it, many voices singing on one note.
{npc_rook_recruited:
    Well. That's not creepy at all. #speaker:rook
}
{deed_banished_rook: Somewhere in the trees, a crow calls. Flicker glances at you and says nothing.}
The road north is open, Majesty. Chapter two, here we come. #speaker:flicker #mood:determined
~ ch1_complete = true
~ unlock("chapter:2")
End of Chapter 1. #chapter_end
-> DONE
