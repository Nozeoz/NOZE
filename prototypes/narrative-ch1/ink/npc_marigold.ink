// Marigold "Goldie" Fenn · Cook & Innkeeper → Kitchen / Tavern (optional Sworn, joins after the VS)
// Story: community is food shared · System: meals, Joy, the arrivals board · Values: Family, Prosperity

=== talk_marigold ===
{
- stat("food") < stat("residents"):
    Sweetheart, the stores are thin. I can stretch a potato a long way, but I can't stretch nothing. #speaker:marigold #mood:worried
    -> DONE
- deed_spared_rook && not react_rook:
    -> react_rook
}
{
- hearts("marigold") >= 2:
    {~Sit. Eat. Then you can go and save the world, sweetheart.|Pip's decided he's your royal food taster. He's tasted everything. Twice.|You work too hard. It's in your shoulders. Have some bread.} #speaker:marigold #mood:smile
- else:
    {~Eat first, talk later.|If you're hungry, the pot's on. If you're not, the pot's still on.|Pip! Hands! Wash them! Both of them!} #speaker:marigold
}
-> DONE
= react_rook
Your crow boy came by the kitchen. Asked for seconds. Then thirds. #speaker:marigold
I like a boy who eats. You can trust a boy who eats. #speaker:marigold #mood:smile
-> DONE

=== help_marigold ===
{~You chop onions for Marigold until your eyes stream. She says that means they're good onions.|You stir the big pot while Marigold tells you exactly what you're doing wrong, lovingly.|Pip teaches you to crack eggs. You are worse at it than Pip.} #scene:The Kitchen #bg:day
~ add_stat("food", 8)
~ add_stat("joy", 2)
Hot food for everyone tonight. That's worth more than gold, sweetheart. #speaker:marigold #mood:smile
~ add_hearts("marigold", 50)
-> DONE

=== gift_marigold(taste) ===
{
- taste == "loved":
    Oh, sweetheart. You remembered. Come here. #speaker:marigold #mood:happy #emote:heart
- taste == "liked":
    Good ingredients! Now we're talking. Now we're cooking. #speaker:marigold #mood:smile
- taste == "disliked":
    Raw ore? In my kitchen? Take it to Tamsin, sweetheart. #speaker:marigold
- else:
    Thank you, love. #speaker:marigold
}
-> DONE

=== heart_marigold_2 ===
Marigold sets four bowls in front of you and folds her arms. #scene:The Kitchen #bg:dusk
New recipes. You're my taster. Be honest. I'll know if you're not. #speaker:marigold
You taste the first. It's wonderful. The second: wonderful. The third is… an experience.
* [Tell the truth about the third.]
    It tastes like a boot that fell in a pond. #speaker:you
    Marigold stares at you. Then she throws her head back and laughs.
    Finally! Someone honest! Pip said it was "interesting". Pip is a coward. #speaker:marigold #mood:happy
* [Say it's lovely.]
    It's… lovely. #speaker:you
    Liar. It's a boot in a pond. But a kind liar. I'll take it. #speaker:marigold #mood:smile
- She pushes the fourth bowl towards you.
My husband's recipe. I've never made it for anyone but Pip. #speaker:marigold
It's the best of the four, by a long way.
~ ev_marigold_2 = true
~ add_hearts("marigold", 40)
-> DONE
