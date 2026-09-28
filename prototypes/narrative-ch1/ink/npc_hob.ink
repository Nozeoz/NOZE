// Hob Furrow · the first settler (not a Sworn)
// Story: proof that ordinary people will follow you · System: completes the Hamlet; farms the Commons

=== talk_hob ===
{
- stat("food") < stat("residents"):
    Stores are getting thin, {var_title}. Nobody's starving, but nobody's singing either. #speaker:hob #mood:worried
    -> DONE
- deed_banished_rook && not react_banished:
    -> react_banished
- deed_spared_rook && not react_spared:
    -> react_spared
}
{~Turnips are coming up lovely. Your Mossbun thinks it's in charge. I let it think so.|My wife used to say a field is a promise you make to winter.|Back's bad today. Hands are good. Hands are always good.|Grew up hearing stories about the Drowned Kingdom. Never thought I'd farm its fields.|That Flicker ate my lunch. Didn't even ask. Just… ate it. With fire.} #speaker:hob #mood:smile
-> DONE
= react_banished
Good riddance to them thieves, I say. Though… that little one had a nasty cough. #speaker:hob #mood:worried
-> DONE
= react_spared
Jackdaw's been helping me haul water. Big lad. Gentle, too, when nobody's looking. #speaker:hob #mood:smile
-> DONE

=== help_hob ===
{~You work the Commons with Hob, hoeing rows until the sun is high.|Hob teaches you to tell a ripe turnip by the colour of its shoulders.|You and Hob mend the fence the Gnawrats chewed. He tells you the names of every one of his old cows.} #scene:The Commons #bg:day
~ add_stat("food", 4)
That's four more rations in the stores. Good day's work, {var_title}. #speaker:hob #mood:smile
~ add_hearts("hob", 50)
-> DONE

=== gift_hob(taste) ===
{
- taste == "loved" || taste == "liked":
    For me? Well, now. Thank you kindly. #speaker:hob #mood:smile
- else:
    That's thoughtful, that is. #speaker:hob
}
-> DONE
