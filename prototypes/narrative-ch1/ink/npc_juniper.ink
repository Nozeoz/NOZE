// Juniper "June" Thistle · Beast Warden → Den / Sanctuary (optional Sworn, joins after the VS)
// Story: loving again after loss · System: familiar care, Bond · Values: Nature, Freedom

=== talk_juniper ===
{
- season() == "Spring" && stat("season_day") == 10:
    It's my birthday! The Mossbuns made me a cake. It's grass. It's a pile of grass. I love it. #speaker:juniper #mood:happy
    -> DONE
- deed_spared_rook && not react_rook:
    -> react_rook
}
{
- hearts("juniper") >= 2:
    {~Ooh! Your Emberkit's tail is extra sparky today. That means it's happy. Or hungry. Or plotting.|Every creature here has a friend. That's me. And you. Mostly me.|The pig's name is Sir Reginald. He chose it. Don't ask how.} #speaker:juniper #mood:happy
- else:
    {~Hi! Hello! Have you met Button? Button, say hi. …Okay, Button's shy. Mostly the ones with teeth.|The Den needs more straw. Always more straw. Straw is love.|Everyone, this is the {var_title}! Say hi! Nobody say anything rude.} #speaker:juniper #mood:happy
}
-> DONE
= react_rook
That Magpie girl asked if Mossbuns are edible. I said NO. She said "hypothetically". I'm watching her. #speaker:juniper #mood:angry
-> DONE

=== help_juniper ===
{~You muck out the Den with Juniper. She names every Mossbun as she brushes it. There are a lot of Mossbuns.|Juniper shows you how to read a familiar's ears: forward is curious, back is scared, one each way is "I have seen a butterfly".|You spend a while lying in the clover while Mossbuns climb on you. Juniper calls it "bonding". It is mostly being sat on.} #scene:The Den #bg:day
~ give("frg_forage", 3)
~ add_stat("food", 2)
The Mossbuns found wild greens while you worked. Clever buns! #speaker:juniper #mood:happy
~ add_hearts("juniper", 50)
-> DONE

=== gift_juniper(taste) ===
{
- taste == "loved":
    A Creature Treat! For the buns? For me? For the buns. Oh, this is the best day. #speaker:juniper #mood:happy #emote:heart
- taste == "liked":
    Ooh! Snacks! Button, look! Button, no! #speaker:juniper #mood:happy
- else:
    Thank you! I'll put it in the Den. Everything ends up in the Den eventually. #speaker:juniper
}
-> DONE

=== heart_juniper_2 ===
Juniper drags you into the Den, where fourteen Mossbuns sit in a wobbly row, and one embarrassed pig. #scene:The Den #bg:day
Right! Introductions! This is Button, Clover, Dumpling, Sir Fluffington, Moss, Other Moss, Pebble, Wobble, Biscuit, Nib, Toast, Bun Bun, Admiral, and Kevin. #speaker:juniper #mood:happy
And Sir Reginald. #speaker:juniper
* Which one is Kevin? #speaker:you #tone:wry
    ~ tone("wry")
    Juniper points at a Mossbun identical to all the others. "Obviously."
* It's an honour to meet you all. #speaker:you #tone:regal
    ~ tone("regal")
    The row of Mossbuns bows. Or falls over. It's hard to tell.
* They're all so lovely, June. #speaker:you #tone:warm
    ~ tone("warm")
    Juniper beams. Several Mossbuns climb into your lap.
- When I was small, I had a herd. The Hollowing took all of them in one night. #speaker:juniper
I swore I'd never have that many again. And then I had fourteen. Funny how that happens. #speaker:juniper #mood:smile
~ ev_juniper_2 = true
~ add_hearts("juniper", 40)
-> DONE
