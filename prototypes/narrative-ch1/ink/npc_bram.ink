// Bram Holloway, "The Old Oak" · Carpenter → Carpenter's Lodge
// Story: the past that gave up waiting · System: construction · Values: Family, Tradition

=== talk_bram ===
{
- ask_bram == "open" && item("mat_wood") >= 20:
    -> ask_done
- ask_bram == "none" && hearts("bram") >= 3:
    -> ask_offer
- deed_spared_rook && not react_spared:
    -> react_spared
- deed_banished_rook && not react_banished:
    -> react_banished
- ch1_signet && not react_signet:
    -> react_signet
- kingdom_rank >= 1 && not react_hamlet:
    -> react_hamlet
- stat("construction") > 0:
    {~Can't talk long. Walls don't raise themselves. Well, they would if you paid them.|Another day on this one, give or take. Mostly take.|If you want it faster, grab the other end of this beam.} #speaker:bram
    -> DONE
}
{
- hearts("bram") >= 5:
    {~I used to think I'd die waiting at that windmill. Now I haven't got time to die. Too many roofs.|You're getting better at this, kid. Ruling, I mean. Still rubbish with a hammer.|If my crew could see this place… Harlow would've laughed. Then he'd have picked up a saw.} #speaker:bram
- hearts("bram") >= 2:
    {~Measure twice, cut once, complain forever. That's carpentry, kid.|Oak for beams, pine for walls, birch for nothing. Birch is a liar.|Linnea keeps putting flowers on my workbench. Waste of good soil. …Don't tell her I said that.|That Longhouse roof would hold up the sky. I checked.} #speaker:bram
- else:
    {~Kid.|Busy. But not too busy. What?|Wood's wet. Everything's wet. It's the Veil. Gets a man damp all the way to his soul.|You want something built, bring wood and stone. You want conversation, bring tea.} #speaker:bram
}
-> DONE
= react_spared
Letting a thief into the pantry. Bold. Stupid, maybe. Bold. #speaker:bram
…That big one, Jackdaw. Lifts a beam on his own. I'll give him that. #speaker:bram
-> DONE
= react_banished
You sent that crow boy packing. Good. Probably good. #speaker:bram
Still. I was a stranger here once. Somebody brought me herbs instead of a boot. #speaker:bram #mood:thoughtful
-> DONE
= react_signet
Heard you came back up with a gold ring and a tortoise story. #speaker:bram
Suits you. Don't let it go to your head. The ring, I mean. The tortoise can go wherever it likes. #speaker:bram #mood:smile
-> DONE
= react_hamlet
A Hamlet. Huh. I've lived in worse. I've lived in a windmill. #speaker:bram #mood:smile
-> DONE
= ask_offer
Kid. Got a favour to ask, and I don't like asking. #speaker:bram
I'm making something. Don't ask what. I need twenty wood. Good straight lengths. #speaker:bram
~ ask_bram = "open"
~ unlock("ask:bram")
-> DONE
= ask_done
Twenty lengths. Straight as a sermon. Thank you. #speaker:bram #mood:smile
~ give("mat_wood", -20)
~ ask_bram = "done"
~ add_hearts("bram", 60)
He hands you a page torn from an old notebook, covered in cramped handwriting and one grease stain.
My ma's stew. Carrot, potato, whatever's green. Warms you right through, even out in the Veil. #speaker:bram
~ unlock("recipe:food_vegetable_stew")
-> DONE

=== help_bram ===
{~You spend hours hauling timber while Bram measures, grumbles, and measures again.|Bram teaches you to plane a board. You do it wrong. He does it again, slower, without a word.|You hold the other end of a beam while Bram talks about ship's knots. There are a lot of ship's knots.} #scene:Carpenter's Lodge #bg:day
{
- stat("construction") > 0:
    ~ add_stat("construction", -1)
    With two pairs of hands, the work goes a full day faster.
- else:
    Nothing's being built today, so Bram has you split and stack the offcuts. You keep a good armful.
    ~ give("mat_wood", 8)
}
Not bad, kid. Not good. But not bad. #speaker:bram
~ add_hearts("bram", 50)
-> DONE

=== gift_bram(taste) ===
{
- taste == "loved":
    Now that's a gift. You didn't have to. …I'm glad you did. #speaker:bram #mood:smile #emote:heart
- taste == "liked":
    Good wood. Well, good something. Thanks, kid. #speaker:bram #mood:smile
- taste == "disliked":
    Flowers. For me. Waste of good soil, kid. #speaker:bram #mood:grumpy
- else:
    Huh. Thanks. I'll find a use for it. #speaker:bram
}
-> DONE

// ─────────────── Heart events (docs/14 §6)
=== heart_bram_2 ===
Bram waves you into the Lodge after supper. On his workbench sits a ship: a model as long as your arm, perfect down to the ropes. #scene:Carpenter's Lodge #bg:dusk
The Wren. Expedition ship. Carried us in, twelve years back. Meant to come back for us in a month. #speaker:bram
He turns one of the tiny sails with a thick finger.
I built this the first winter. Every rope. So I'd remember what she looked like when she came back. #speaker:bram
* Twelve years is a long watch. You can stand down now. #speaker:you #tone:regal
    ~ tone("regal")
    …Stand down. You keep saying it like you've said it to soldiers. #speaker:bram #mood:thoughtful
* She might still come. #speaker:you #tone:warm
    ~ tone("warm")
    Twelve years, kid. I stopped watching the river a long time ago. #speaker:bram
* It's a beautiful ship. Can it carry turnips? #speaker:you #tone:wry
    ~ tone("wry")
    Bram snorts, and it turns into a real laugh.
    Forty tons of turnips. She was a good ship. #speaker:bram
- He sets the model on the highest shelf in the Lodge, where the Heartflame's light reaches it.
There. Now she's home, at least. #speaker:bram #mood:smile
~ ev_bram_2 = true
~ add_hearts("bram", 40)
-> DONE

=== heart_bram_4 ===
A storm comes out of nowhere after dark. You wake to a crack like a falling tree: half the Lodge roof has peeled back like a page. #scene:Carpenter's Lodge #bg:night
Bram is already up the ladder in the rain, swearing at the wind.
Don't just stand there! Hold this! #speaker:bram
* [Climb up and hold the beam.]
- For an hour you hold beams while he nails them, rain running down your collar. Somewhere in the second hour, he starts talking.
Harlow was our cartographer. Drew maps on everything. Tablecloths. My arm, once. #speaker:bram
The Keane brothers couldn't cook to save their lives. So I did. That's how I learned. #speaker:bram
Seven of us walked into the Veil. I'm the one who walked out. Never knew why me. #speaker:bram #mood:sad
* Maybe so someone would remember them. #speaker:you #tone:warm
    ~ tone("warm")
* Maybe so you could build this. #speaker:you #tone:regal
    ~ tone("regal")
* Maybe because you're too stubborn to be eaten. #speaker:you #tone:wry
    ~ tone("wry")
- The last nail goes in. The rain drums on a roof that holds. Bram sits on the ridge beam, soaked, and looks out at the Veil for a long time.
Harlow would've liked you. He liked anyone who stayed up a ladder in a storm. #speaker:bram #mood:smile
~ ev_bram_4 = true
~ add_hearts("bram", 60)
-> DONE
