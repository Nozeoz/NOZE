// Mira Caravel, "The Veilrunner" · travelling merchant (visits Tue/Fri in Chapter 1; joins in Chapter 2)
// Story: freedom vs. belonging; a spy who will choose a home · System: shop, selling · Values: Prosperity, Freedom
// Secret S11 (docs/14 §7): she sells maps of your realm to the Dominion. Chapter 1 only hints at it.

=== talk_mira ===
{
- kingdom_rank >= 2 && not react_village:
    -> react_village
- ch1_founded && not react_founded:
    -> react_founded
- deed_banished_rook && not react_banished:
    -> react_banished
}
{
- hearts("mira") >= 3:
    {~For you? Special price. It's the regular price, but I say it warmly.|Humphrey's put on weight. It's your turnips. I'm billing you.|You know what I like about you? You pay. Nobody in the Veil pays.} #speaker:mira #mood:wink
- else:
    {~Darling! Buying, selling, or just admiring?|Everything's for sale, darling. Except Humphrey. Humphrey's priceless. Also nobody will take him.|Fresh from the Outer Realms! Well. Fresh-ish.} #speaker:mira #mood:happy
}
-> DONE
= react_founded
{var_kingdom_name}! You named it! I'll put it on my maps. #speaker:mira #mood:happy
She writes something in a small leather book and snaps it shut a little too quickly.
-> DONE
= react_banished
Word travels, darling. The Crowfeather boys are telling every campfire you've got a sharp crown. #speaker:mira
Good for business, actually. Nobody robs a caravan that stops at a sharp crown. #speaker:mira #mood:wink
-> DONE
= react_village
A Village! With a Court! Darling, I could sell you a market stall. I could sell you a whole market. #speaker:mira #mood:happy
Build me a Market plot one day and I might stop travelling. Might. #speaker:mira
-> DONE

=== gift_mira(taste) ===
{
- taste == "loved":
    Oh, you shouldn't have. You absolutely should have. I'll never sell it. Probably. #speaker:mira #mood:happy #emote:heart
- taste == "liked":
    Now this has resale value. And sentimental value. Mostly resale. Thank you, darling. #speaker:mira #mood:wink
- taste == "disliked":
    Darling. I can't sell this. I can't even give this away. #speaker:mira
- else:
    A gift! For the merchant! How unusual. How lovely. #speaker:mira
}
-> DONE

=== heart_mira_2 ===
Mira waves you round the back of her cart, where Humphrey is asleep in a heap, and opens a ledger bound in faded red leather. #scene:The Caravan #bg:day
Want to see my most important book? It's my list of debts the Veil owes me. #speaker:mira
Every page is a list of losses: a cart wheel, three lanterns, a whole shipment of silk, and, underlined twice, "Papa's compass".
The Veil takes and takes. I keep count so one day I can send it the bill. #speaker:mira #mood:smile
* [Ask about the compass.]
    Mira's smile slips, just for a second.
    Some debts aren't the Veil's fault, darling. Some are people's. #speaker:mira
    She closes the ledger.
* [Ask what's on the last page.]
    Mira flips to the back. The last page is blank except for one word: {var_kingdom_name}.
    Oh, that's not a debt. That's an investment. #speaker:mira #mood:wink
- She tucks the ledger away, somewhere deep inside her coat, and is bright and loud again.
Now! Are you buying or not? #speaker:mira #mood:happy
~ ev_mira_2 = true
~ add_hearts("mira", 40)
-> DONE
