// Tamsin Hale, "Sparks" · Blacksmith → Smithy
// Story: finding your own voice · System: tool and weapon upgrades, metal for buildings · Values: Progress, Honor

=== talk_tamsin ===
{
- not npc_tamsin_recruited && item("min_copper_ore") >= 10:
    -> tamsin_forge
- not npc_tamsin_recruited:
    U-um. Ten copper ore. For the forge. It's shiny and orange and it's in the walls down there. Sorry. You know what copper is. #speaker:tamsin #mood:shy
    You've got {item("min_copper_ore")}. #speaker:tamsin
    -> DONE
- ask_tamsin == "open" && item("min_copper_ore") >= 10:
    -> ask_done
- ask_tamsin == "none" && hearts("tamsin") >= 3:
    -> ask_offer
- deed_spared_rook && not react_rook:
    -> react_rook
}
{
- hearts("tamsin") >= 5:
    {~When I'm at the forge I'm not scared of anything. Then I put the hammer down and I'm scared of everything again. Except you. You're fine.|My old master said I'd never make a blade worth the ore. I made you one. It's worth the ore.|I've been thinking about Veilglass. You can't forge it. Everyone says. But everyone said I couldn't talk to people, and look.} #speaker:tamsin #mood:happy
- hearts("tamsin") >= 2:
    {~I-it's not a sword yet. It's a promise of a sword.|Copper's soft but honest. Iron's hard but it lies about cracks. I like copper.|Bram says my forge is too loud. I say his hammering is too quiet. We're friends now.|Is your blade holding up? Can I see it? Can I hold it? Can I— sorry. Just. Can I see it.} #speaker:tamsin
- else:
    {~Oh! Hi. Um. Hello. Hi.|S-sorry, I'm covered in soot. I'm always covered in soot.|The forge is good. Thank you. For the forge. And the… everything.} #speaker:tamsin #mood:shy
}
-> DONE
= react_rook
That Rook boy asked me to sharpen his knives. I did. Then he asked me not to tell you. #speaker:tamsin
I'm telling you. I'm bad at secrets. Except one. Never mind. #speaker:tamsin #mood:shy
-> DONE
= ask_offer
C-could I ask for something? I want to practise. Properly. Ten more copper ore. #speaker:tamsin
If I get it right, I can make you better tools. Hoes that don't bend. That sort of thing. #speaker:tamsin
~ ask_tamsin = "open"
~ unlock("ask:tamsin")
-> DONE
= ask_done
Ten! Oh, you're the best. Stand back. Further than that. #speaker:tamsin #mood:happy
~ give("min_copper_ore", -10)
~ ask_tamsin = "done"
~ add_hearts("tamsin", 60)
An hour later she hands you a copper hoe with an edge so fine it sings when you tap it.
Field work will be easier with this. Less digging, more… growing. Sorry, that sounded better in my head. #speaker:tamsin #mood:shy
~ unlock("tool:hoe_copper")
-> DONE

=== help_tamsin ===
{~You pump the bellows for Tamsin while she hammers out nails, rivets, hinges. She hums the whole time and doesn't notice.|Tamsin teaches you to quench a blade. You hiss louder than the steel does.|You sort scrap metal into piles while Tamsin explains the difference between them with enormous enthusiasm.} #scene:The Smithy #bg:day
~ add_stat("gold", 35)
Mira buys my nails by the bag. That's your share. No, take it. I insist. I insist quietly. #speaker:tamsin #mood:shy
~ add_hearts("tamsin", 50)
-> DONE

=== gift_tamsin(taste) ===
{
- taste == "loved":
    Oh. Oh! For me? Nobody's ever… thank you. I'll keep it on the anvil. No, that's a terrible place. I'll keep it safe. #speaker:tamsin #mood:happy #emote:heart
- taste == "liked":
    Ore! Look at the colour! You know me so well. Sorry. That's a weird thing to say. It's true, though. #speaker:tamsin #mood:happy
- taste == "disliked":
    Oh. Um. Fish. Thank you. I'll… Linnea likes fish. Maybe. #speaker:tamsin #mood:shy
- else:
    Th-thank you! #speaker:tamsin #mood:shy
}
-> DONE

=== heart_tamsin_2 ===
Tamsin is waiting outside the Smithy at dusk, holding something wrapped in a cloth, and has clearly been rehearsing. #scene:The Smithy #bg:dusk
I, um. I made. It's a. I. #speaker:tamsin #mood:shy
She gives up and unwraps it. A sword. A real one, the steel folded and bright, the grip wrapped in blue leather.
It's my first real sword. Not a promise. A real one. My master never let me finish one. I wanted you to see it first. #speaker:tamsin
* It's magnificent, Tamsin. A royal armoury would be proud of it. #speaker:you #tone:regal
    ~ tone("regal")
* You should be really proud. I'm proud of you. #speaker:you #tone:warm
    ~ tone("warm")
* Can I hold it? I promise not to hit myself. #speaker:you #tone:wry
    ~ tone("wry")
- Tamsin goes pink to the tips of her ears and doesn't stammer at all when she answers.
Next one's for you. Better than this. I know how to do it now. #speaker:tamsin #mood:determined
~ ev_tamsin_2 = true
~ add_hearts("tamsin", 40)
-> DONE

=== heart_tamsin_4 ===
You knock on the Smithy door at night to borrow a lantern and walk in on Tamsin sitting by the dying forge, sewing. #scene:The Smithy #bg:night
In her enormous soot-black hands is a very small, very round, very lovingly stitched plush Mossbun.
She freezes. You freeze. The plush Mossbun stares at both of you with its button eyes.
…This isn't what it looks like. #speaker:tamsin #mood:panicked
It's exactly what it looks like. #speaker:tamsin #mood:shy
* [Swear on the Signet you'll never tell a soul.]
    Tamsin laughs, a big surprised honk of a laugh, and shows you the others: a Glimmoth, an Emberkit with a felt flame, and a lopsided Flicker.
* [Ask if you can have one.]
    Tamsin stares at you. Then she digs in her apron and hands you a lopsided plush Flicker with a yellow felt crown.
    I was saving it for someone who wouldn't laugh. #speaker:tamsin #mood:shy
- Don't tell Rook. He'd never let me live it down. #speaker:tamsin
He might want one, though. #speaker:tamsin #mood:thoughtful
~ ev_tamsin_4 = true
~ add_hearts("tamsin", 60)
-> DONE
