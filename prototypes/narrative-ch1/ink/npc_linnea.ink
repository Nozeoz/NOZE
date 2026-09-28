// Linnea Marsh, "The Quiet Remedy" · Herbalist & Healer → Herbalist Hut / Clinic
// Story: mercy and healing; guilt turned into care · System: knockout recovery, herbs · Values: Mercy, Nature

=== talk_linnea ===
{
- ask_linnea == "open" && item("frg_healing_herb") >= 5:
    -> ask_done
- ask_linnea == "none" && hearts("linnea") >= 3:
    -> ask_offer
- deed_spared_rook && not react_spared:
    -> react_spared
- deed_banished_rook && not react_banished:
    -> react_banished
- stat("exposure") > 0:
    You're cold. I can see it in your fingers. Sit by the fire, and no arguing. #speaker:linnea #mood:worried
    -> DONE
}
{
- hearts("linnea") >= 5:
    {~Chamomile for sleep, yarrow for cuts… and for kings who don't rest, a stern talking-to.|I haven't dreamed about Marsh End in a week. I think that's your fault. Thank you.|Some days I think I'm only good at patching people up after it's too late. Then someone like Hob laughs at supper, and I remember that's not true.} #speaker:linnea
- hearts("linnea") >= 2:
    {~The Mossbun with the torn ear follows me everywhere now. I've named her Stitch. Is that silly?|Mint by the river, sorrel in the shade. The Vale's like a pharmacy nobody's minding.|You've got mud on your face. No, the other side. …You've got mud on both sides.|Bram pretends my flowers annoy him. He moved one into the light yesterday.} #speaker:linnea #mood:smile
- else:
    {~Oh! Hello. Sorry, I was counting leaves.|If you're hurt, tell me. Don't be brave about it. Brave is how people get infected.|Thank you again. For the chapel. I haven't said that enough.} #speaker:linnea
}
-> DONE
= react_spared
You let them stay. Rook and his… family. #speaker:linnea
The small one, Finch, has a cough. I'll see to it. I'm glad you chose this, if that's alright to say. #speaker:linnea #mood:smile
-> DONE
= react_banished
They'll be cold out there tonight. #speaker:linnea #mood:sad
I know why you did it. I just… I hope they find a fire somewhere. #speaker:linnea
-> DONE
= ask_offer
Could I ask you something? It's small. #speaker:linnea
I want to make salves for when you go down into the Cellars. I need five Healing Herbs. Only if you pass any, if that's alright. #speaker:linnea
~ ask_linnea = "open"
~ unlock("ask:linnea")
-> DONE
= ask_done
Five! You found five. You didn't have to. Thank you. #speaker:linnea #mood:happy
~ give("frg_healing_herb", -5)
~ ask_linnea = "done"
~ add_hearts("linnea", 60)
~ give("con_healing_salve", 3)
Three salves. If something down there knocks you flat, one of these gets you back up before you lose anything. Promise me you'll carry them. #speaker:linnea
-> DONE

=== help_linnea ===
{~You spend a few hours by the river with Linnea, filling her satchel with mint and yarrow.|You grind herbs in her mortar until your arms ache. She says you have "a good steady pestle", and means it.|Linnea shows you how to bind a sprained wrist, using yours.} #scene:Herbalist Hut #bg:day
~ give("frg_healing_herb", 3)
{~Yarrow's leaves look like feathers. Hemlock's don't. Remember that one, please.|Chamomile for sleep. Willow bark for aches. And for kings who skip meals, soup.|There. You're better at this than you think.} #speaker:linnea #mood:smile
~ add_hearts("linnea", 50)
-> DONE

=== gift_linnea(taste) ===
{
- taste == "loved":
    Dawnbells! They ring at sunrise, did you know? Tiny bells. I'll keep them by the window. #speaker:linnea #mood:happy #emote:heart
- taste == "liked":
    Oh, these are lovely. I can use every bit of them. Thank you. #speaker:linnea #mood:smile
- taste == "disliked":
    Oh. That's… thank you. I'll find somewhere for it. Somewhere far away. #speaker:linnea
- else:
    For me? That's kind. Thank you. #speaker:linnea
}
-> DONE

=== heart_linnea_2 ===
Linnea catches your sleeve by the river and crouches beside two plants that look exactly alike. #scene:Riverbank #bg:dusk
This one's yarrow. It closes wounds. This one's hemlock. It closes everything. #speaker:linnea
She shows you: the feathered leaf, the spotted stem, the smell when you crush it.
Healers learn the poison first. Otherwise you can't be trusted with the cure. #speaker:linnea
* Is that how you learned? #speaker:you #tone:warm
    ~ tone("warm")
    My mother made me eat a leaf of each. Well, lick. I was very, very sick. I have never forgotten. #speaker:linnea #mood:smile
* A good rule for rulers, too. #speaker:you #tone:regal
    ~ tone("regal")
    Linnea tilts her head. "Know the harm before you hand out the help." Yes. I suppose it is. #speaker:linnea
* So if I annoy you, I should watch my soup. #speaker:you #tone:wry
    ~ tone("wry")
    Linnea laughs out loud, then covers her mouth, scandalised at herself.
- She tucks a sprig of yarrow into your buttonhole.
For the next time you do something brave and stupid. #speaker:linnea #mood:smile
~ ev_linnea_2 = true
~ add_hearts("linnea", 40)
-> DONE

=== heart_linnea_4 ===
At dusk you find Linnea alone at the Ruined Chapel, kneeling where the altar used to be, lighting small candles in a row. #scene:The Ruined Chapel #bg:dusk
There are a lot of candles.
One for each house in Marsh End. I don't know if anyone's listening. I do it anyway. #speaker:linnea #mood:sad
* [Kneel beside her and light one.]
    You light a candle and set it at the end of the row. She watches you do it and doesn't say anything for a long time.
* [Stand at the door and keep watch.]
    You stand in the arch with your back to her, facing the Veil, until the last candle is lit.
- I keep thinking I should have been faster. Smarter. Stronger. #speaker:linnea
* You were there. You stayed. That counts. #speaker:you #tone:warm
    ~ tone("warm")
* You carried them out of the dark in your memory. Now you carry our people too. #speaker:you #tone:regal
    ~ tone("regal")
* You're the most stubborn healer alive. That had to come from somewhere. #speaker:you #tone:wry
    ~ tone("wry")
- Linnea wipes her eyes on her shawl and stands.
Let's go home. I'd like to go home now. #speaker:linnea #mood:smile
It's the first time she's called it that.
~ ev_linnea_4 = true
~ add_hearts("linnea", 60)
-> DONE
