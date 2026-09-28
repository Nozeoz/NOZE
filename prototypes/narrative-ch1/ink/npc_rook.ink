// Rook, "The Crowfeather" · Scout, ex-bandit → Scout's Post
// Story: the spared enemy who becomes family · System: maps, bounties, later Expeditions · Values: Freedom, Family

=== talk_rook ===
{
- not npc_rook_recruited:
    -> trial_talk
- ask_rook == "open" && item("key_magpie_slingshot") > 0:
    -> ask_done
- ask_rook == "none" && hearts("rook") >= 3:
    -> ask_offer
- season() == "Summer" && stat("season_day") == 3:
    Who told you it's my birthday? …It was Finch. It's always Finch. #speaker:rook #mood:embarrassed
    -> DONE
- ch1_signet && not react_signet:
    -> react_signet
- npc_rook_trial == "done" && not react_joined:
    -> react_joined
}
{
- hearts("rook") >= 5:
    {~Don't tell the others, but this is the first place I've slept through a whole night since I was twelve.|You know what the worst thing about you is? I can't find the angle. Everyone's got an angle. You just… feed people.|Magpie says I've gone soft. Magpie also cried at the feast, so.} #speaker:rook
- hearts("rook") >= 2:
    {~Relax, Your Royal Muddiness. If I wanted your stuff, you'd already be missing it.|Saw a Duskwolf pack east of the river. Don't go that way after dark. Or do. I'm not your mum.|Finch has adopted your pot. There's no getting it back. I've tried.|From the roof you can see the whole Vale. It's smaller than it feels. Most kingdoms are.} #speaker:rook #mood:smug
- else:
    {~Majesty.|What. I'm working. This is what working looks like when you're good at it.|Don't give me that look. I'm on the roof because the roof's the best place to be.} #speaker:rook
}
-> DONE
= trial_talk
{npc_rook_trial == "active": {stat("food")} rations, {stat("trial_days")} day(s). Tick tock, Majesty.|Still short. We're not going anywhere. Don't read into that.} #speaker:rook #mood:smug
{~Jackdaw's been helping Hob in the fields. Don't tell anyone. He has a reputation.|Magpie wants to know if your Mossbun is edible. I said no. She says "hypothetically".|You know you're mad, right? Feeding the people who robbed you. Just checking you know.} #speaker:rook
-> DONE
= react_signet
A gold ring off a giant tortoise. Heard all about it. Finch wants to know if there are more tortoises. #speaker:rook
There aren't more tortoises, are there? #speaker:rook #mood:worried
-> DONE
= react_joined
So. This is what it's like on the other side of the pantry door. #speaker:rook
It's warm. I hate it. Don't tell anyone I hate it. #speaker:rook #mood:embarrassed
-> DONE
= ask_offer
Majesty. Small thing. Magpie lost her slingshot the night we, uh, visited your stores. Down some hole by the Granary, she thinks. #speaker:rook
If you're ever in the Cellars and see a slingshot with a crow carved on it… she'd never say it, but she'd cry. #speaker:rook
~ ask_rook = "open"
~ unlock("ask:rook")
-> DONE
= ask_done
You hand Rook a small slingshot with a crow carved into the grip. He turns it over twice without a word.
Magpie! Get over here! #speaker:rook
Magpie snatches it, stares at you, and walks off very fast so nobody sees her face.
Thanks, Majesty. That's… yeah. Thanks. #speaker:rook
~ give("key_magpie_slingshot", -1)
~ ask_rook = "done"
~ add_hearts("rook", 60)
Here. Gang's old stash. We were saving it for a rainy day. Every day's rainy in the Veil, so. #speaker:rook
~ add_stat("gold", 80)
-> DONE

=== help_rook ===
{~Rook takes you up to his lookout on the Longhouse roof and teaches you to read the Veil: thick means Hollowed, thin means wind, sparkly means trouble.|You spend a few hours with Rook tracking a Duskwolf pack along the river. He moves like a shadow. You move like a person carrying a very loud sword.|Rook shows you the gang's old hiding places. Most of them are now full of your turnips.} #scene:Scout's Post #bg:day
~ add_stat("gold", 40)
{~Bounty on a Gnawrat nest by the mill. Easy coin, Majesty.|Found a stash some traveller hid and forgot. Finders, keepers, kings.|See? Scouting pays. Mostly in coins, sometimes in not dying.} #speaker:rook #mood:smug
~ add_hearts("rook", 50)
-> DONE

=== gift_rook(taste) ===
{
- taste == "loved":
    Is that… a crow-feather charm? Where did you… Never mind. I'm keeping it. Forever. Don't make it weird. #speaker:rook #mood:embarrassed #emote:heart
- taste == "liked":
    Oh, food. You know the way to a thief's heart. It's through his stomach. It's always through his stomach. #speaker:rook #mood:smile
- taste == "disliked":
    Cabbage. Majesty. What did I ever do to you? Don't answer that. #speaker:rook #mood:grumpy
- else:
    For me? Huh. Thanks. #speaker:rook
}
-> DONE

=== heart_rook_2 ===
Rook drops out of a tree beside you as you walk home at dusk. You barely flinch now. #scene:The Old Oak #bg:dusk
Come on. Want to show you something. #speaker:rook
He climbs the biggest oak at the edge of the Vale, and after a lot of swearing, so do you. At the top there's a platform of boards, a blanket, and a view over the whole valley.
This is where we used to watch the stars. Before. Me, Magpie, Jackdaw, Finch. On the nights we didn't eat, we'd count stars instead. #speaker:rook
Above the Veil, the sky is enormous and clear.
* That one's mine. The bright one. #speaker:you #tone:regal
    ~ tone("regal")
    Course it is. Crowns always pick the brightest. That's Jackdaw's star, actually. He'll fight you. #speaker:rook #mood:smug
* Thank you for showing me this. #speaker:you #tone:warm
    ~ tone("warm")
    Don't get sentimental. …It's alright. I wanted to. #speaker:rook
* How many did you count, on the bad nights? #speaker:you #tone:wry
    ~ tone("wry")
    Four hundred and twelve. Once. Finch got to four hundred and thirteen and wouldn't stop going on about it. #speaker:rook #mood:smile
- You stay until the fire in the Longhouse window is the brightest star below you.
~ ev_rook_2 = true
~ add_hearts("rook", 40)
-> DONE

=== heart_rook_4 ===
Linnea finds you at dusk, furious in her quiet way. Her medicine chest has been opened. A whole vial of fever tonic is gone. #scene:Herbalist Hut #bg:dusk
You find Rook in the gang's tent, holding the tonic to Magpie's lips. She's shivering, flushed with fever.
He looks up and doesn't bother to hide the vial.
She was burning up. Linnea was asleep. I didn't think. I just took it. Old habits. #speaker:rook
So. Judge me, Majesty. That's the deal, isn't it? #speaker:rook #mood:defiant
* [Forgive him.]
    You took it for family. I'd have done the same. Next time, wake Linnea. #speaker:you
    ~ deed_judged_rook_medicine = "forgave"
    Rook stares at you. Then at the tonic. Then he nods, once.
    Next time I'll wake her. #speaker:rook
* [Dock his share of the stores for a week.]
    You'll repay Linnea from your share of the stores. Rules are the same for everyone. #speaker:you
    ~ deed_judged_rook_medicine = "docked"
    Rook laughs, short and surprised.
    Fair. Actually fair. Nobody's ever been fair with me before. It's worse than shouting. #speaker:rook
- Later, Linnea takes Magpie's temperature and says she'll live, and Rook goes outside and sits by the fire for a long time.
~ ev_rook_4 = true
~ add_hearts("rook", 60)
-> DONE
