--!strict
-- Tunables for Kingsbloom: Lantern Market (Roblox).
-- Every number here is a placeholder tuned for a fun first hour; change freely.

local Config = {}

-- World
Config.TILE = 6 -- studs per grid tile
Config.PLOT_W = 30
Config.PLOT_H = 30
Config.PLOT_COUNT = 6
Config.HEARTFLAME = { x = 15, z = 13 } -- tile-corner coordinates of the Heartflame's centre
Config.ENTRANCE = { x = 15, z = 29 } -- visitors walk in here (the plot's outer edge)

-- Day and night (seconds). Day market all day; the Lantern Market (bonus) and the Veil at night.
Config.DAY_LENGTH = 210
Config.DUSK_LENGTH = 20
Config.NIGHT_LENGTH = 170
Config.DAWN_LENGTH = 20

-- Economy
Config.START_GOLD = 120
Config.START_STOCK = { harvest = 12, grain = 0, catch = 0, stew = 0 }
Config.STORE_CAP_BASE = 60 -- per good; Granaries add more
Config.NIGHT_PRICE_MULT = 1.25
Config.COST_GROWTH = 1.12 -- each extra building of the same kind costs 12% more
Config.REFUND = 0.5

-- Visitors
Config.VISITOR_SPEED = 1.7 -- tiles per second
Config.MAX_VISITORS = 16
Config.FEAR_DARK_STEP = 6
Config.FEAR_TURN_BACK = 45
Config.LIT = 0.18

-- The Veil
Config.GLOOM_MAX = 5 -- at once, before the midnight surge; +1 every 5 levels
Config.GLOOM_HP = 36
Config.GLOOM_SPEED = 1.15
Config.GLOOM_TOUCH_DAMAGE = 9
Config.LAMP_SNUFF_TIME = 14 -- seconds a Gloomling needs beside a lamp to snuff it

-- Combat (the Lantern Staff)
Config.STAFF_DAMAGE = 14
Config.STAFF_RANGE = 11 -- studs
Config.STAFF_ARC = 0.25 -- dot product threshold (wide arc)
Config.STAFF_COOLDOWN = 0.32
Config.COMBO_FINISHER_MULT = 1.8
Config.BURST_DAMAGE = 30
Config.BURST_RADIUS = 20
Config.BURST_COOLDOWN = 9

-- Collecting and serving
Config.TIP_PICKUP_RADIUS = 7
Config.SERVE_RADIUS = 8
Config.TEND_INTERVAL = 55 -- a field ripens this often (seconds of daylight)

-- Saving
Config.DATASTORE = "KingsbloomLanternMarket_v1"
Config.AUTOSAVE = 90

-- Sounds: official Roblox, APM and ProSoundEffects uploads from the Creator Store (public, free).
-- Swap any id for one you like; an empty string mutes that sound.
Config.SOUNDS = {
	click = "rbxassetid://15675059323", -- Roblox_UI_Bright_Click
	pop = "rbxassetid://15675055424", -- Roblox_UI_Cute_Pop
	whoosh = "rbxassetid://15674975792", -- Roblox_UI_Whoosh_03
	notify = "rbxassetid://17208361335", -- Roblox GUI - Notification High
	pickup = "rbxassetid://17208319162", -- Roblox GUI - Pickup
	coin = "rbxassetid://127645268874265", -- CoinTransfer_01 (Roblox)
	coins = "rbxassetid://9113849492", -- Coins Or Keys Jingle 6
	place = "rbxassetid://9120888980", -- Wood Hits Board Impacts On Fence Post 7
	hammer = "rbxassetid://9114756916", -- Hammer Nail Into Wood 25
	remove = "rbxassetid://9113225986", -- Axe Impact Giant Thuddy Hits On Wood Floor 5
	error = "rbxassetid://12221967", -- button.wav (Roblox), played low
	levelup = "rbxassetid://1845411858", -- Top Prize (APM)
	rankup = "rbxassetid://1836473422", -- Victory Fanfare Sting (APM)
	quest = "rbxassetid://125706237686412", -- Glistening Harp - Sting (APM)
	achievement = "rbxassetid://9126073001", -- Synth Sparkle Tone High Pitch Bell Tone Ding
	sparkle = "rbxassetid://9116395089", -- Magic Glows Soft Clusters Of Chiming Hits 4
	swing = "rbxassetid://9120972321", -- Wood Whoosh Slicing Air Quick Swings 4
	hit = "rbxassetid://9116394545", -- Magic Glows Soft Clusters Of Chiming Hits 1
	burst = "rbxassetid://9116384485", -- Magic Burst 1
	poof = "rbxassetid://9125640290", -- Magic Poofs Short Breathy Bursts
	gloom = "rbxassetid://9113970398", -- Creature Blip 8
	hurt = "rbxassetid://9113991080", -- Creature Vocal Spider Hiss Squawk 1
	bell = "rbxassetid://9125440445", -- Church Bell Single Successive Hits
	tend = "rbxassetid://9116394876", -- Magic Glows Soft Clusters Of Chiming Hits 2
	-- ambience loops
	ambDay = "rbxassetid://9113444532", -- Birds Peaceful 2
	ambNight = "rbxassetid://9112835862", -- Night Ambience 1
	ambWind = "rbxassetid://9116258071", -- Leaves Rustle Wind Blowing Through Trees 1
	ambCrowd = "rbxassetid://9112841064", -- Outdoor Walla 2
}

-- Music playlists (APM, public). Crossfaded by time of day.
Config.MUSIC_DAY = {
	"rbxassetid://131370222076689", -- Market Place
	"rbxassetid://9038197447", -- Peaceful Meadow
	"rbxassetid://1847223700", -- Prelude For 2 Lutes
	"rbxassetid://9046391468", -- Peaceful Wilderness
}
Config.MUSIC_NIGHT = {
	"rbxassetid://1837211641", -- The Enchanted Forest
	"rbxassetid://1839883317", -- Mystical Nature
	"rbxassetid://9042496567", -- Celtic Dreamworld A
	"rbxassetid://1848354536", -- Relaxed Scene
}
Config.MUSIC_SURGE = "rbxassetid://1845205138" -- Forest Chase

-- Optional: badge ids from your Creator Hub (leave 0 to skip).
Config.BADGES = {
	firstSale = 0,
	village = 0,
	kingdom = 0,
	nightWarden = 0,
}

return Config
