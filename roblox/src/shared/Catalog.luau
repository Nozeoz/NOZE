--!strict
-- Everything that exists in Kingsbloom: Lantern Market: buildings, goods, visitors, levels and ranks,
-- the Heartflame, quests, daily Royal Orders and achievements. Pure data (no Roblox types) plus small helpers.
-- Every number is a placeholder tuned for a fun first hour.

local Catalog = {}

export type Building = {
	id: string,
	name: string,
	cat: string,
	icon: string,
	w: number,
	d: number,
	cost: number,
	lumen: number?,
	level: number,
	desc: string,
	surface: boolean?, -- a path tile painted on the ground
	walkable: boolean?, -- visitors can walk through it (arches, string lights)
	reach: boolean?, -- may stand outside the realm if it's right beside a road
	light: number?, -- light radius in tiles
	lights: { { number } }?, -- several bulbs: { localX, localZ, radius }
	snuffable: boolean?, -- Gloomlings can put it out
	appeal: { number }?, -- { amount, radius }
	rest: boolean?, -- visitors linger beside it
	stall: boolean?,
	produce: { [string]: number }?,
	convert: { input: { [string]: number }, output: { [string]: number } }?,
	seconds: number?, -- production time per batch (without a worker)
	worker: boolean?, -- a settler can work here (twice as fast)
	tendable: boolean?, -- ripens every so often; tend it for a bonus
	needsWater: boolean?,
	beds: number?,
	storage: number?,
	tower: boolean?,
	variants: number?,
	fixed: boolean?,
	growth: number?, -- cost multiplier per building of the same kind you already own
	limit: { number }?, -- { base, per level }: how many you may own
}

Catalog.Categories = {
	{ id = "light", name = "Light & Paths", icon = "🏮" },
	{ id = "market", name = "Market & Farms", icon = "🛒" },
	{ id = "homes", name = "Homes", icon = "🏠" },
	{ id = "decor", name = "Decor", icon = "🌷" },
	{ id = "defense", name = "Defense", icon = "🗼" },
}

local B: { [string]: Building } = {
	path = { id = "path", name = "Stone Path", cat = "light", icon = "🪨", w = 1, d = 1, cost = 2, level = 1, surface = true, growth = 1, desc = "Visitors only walk on roads and paths. Hold and drag to paint." },
	lamp = { id = "lamp", name = "Lantern Post", cat = "light", icon = "🏮", w = 1, d = 1, cost = 15, level = 1, light = 3.6, snuffable = true, appeal = { 1, 2 }, reach = true, growth = 1.03, desc = "Travelers won't walk in the dark. Lamps may stand beside the road, even outside your realm." },
	string = { id = "string", name = "String Lights", cat = "light", icon = "✨", w = 1, d = 3, cost = 35, level = 3, walkable = true, reach = true, snuffable = true, lights = { { 0, 0, 2.6 }, { 0, 1, 2.6 }, { 0, 2, 2.6 } }, appeal = { 3, 2.2 }, growth = 1.05, desc = "Little lanterns strung over a path. People walk underneath." },
	arch = { id = "arch", name = "Lantern Arch", cat = "light", icon = "⛩️", w = 1, d = 3, cost = 110, level = 7, walkable = true, reach = true, snuffable = true, lights = { { 0, 0, 3.4 }, { 0, 2, 3.4 } }, appeal = { 6, 3.2 }, growth = 1.08, desc = "A grand arch over a path. Bright and beloved." },
	stall = { id = "stall", name = "Market Stall", cat = "market", icon = "🛒", w = 2, d = 1, cost = 40, level = 1, stall = true, light = 1.6, variants = 4, limit = { 2, 0.5 }, desc = "Sells one kind of goods. Its counter must face a path." },
	field_turnip = { id = "field_turnip", name = "Turnip Field", cat = "market", icon = "🥬", w = 3, d = 3, cost = 30, level = 1, produce = { harvest = 1 }, seconds = 14, worker = true, tendable = true, limit = { 2, 0.45 }, desc = "Grows turnips. When it sparkles, walk up and tend it." },
	fishery = { id = "fishery", name = "Fishing Hut", cat = "market", icon = "🎣", w = 2, d = 2, cost = 60, level = 2, produce = { catch = 1 }, seconds = 16, worker = true, needsWater = true, light = 1.4, limit = { 1, 0.2 }, desc = "Catches fish. It has to touch the pond." },
	field_wheat = { id = "field_wheat", name = "Wheat Field", cat = "market", icon = "🌾", w = 3, d = 3, cost = 45, level = 3, produce = { grain = 1 }, seconds = 15, worker = true, tendable = true, limit = { 1, 0.35 }, desc = "Grows wheat for bread. Tend it when it sparkles." },
	granary = { id = "granary", name = "Granary", cat = "market", icon = "🏛️", w = 2, d = 2, cost = 150, level = 4, storage = 60, light = 1.2, limit = { 1, 0.15 }, desc = "Stores 60 more of every good." },
	cookhouse = { id = "cookhouse", name = "Cookhouse", cat = "market", icon = "🍲", w = 3, d = 2, cost = 140, level = 5, convert = { input = { harvest = 1, catch = 1 }, output = { stew = 1 } }, seconds = 12, worker = true, light = 2, limit = { 1, 0.15 }, desc = "Turns turnips and fish into Stew, the best seller." },
	tent = { id = "tent", name = "Tent", cat = "homes", icon = "⛺", w = 2, d = 2, cost = 25, level = 1, beds = 1, light = 1.1, desc = "A bed for one settler." },
	hut = { id = "hut", name = "Hut", cat = "homes", icon = "🛖", w = 2, d = 2, cost = 80, level = 2, beds = 2, light = 1.5, variants = 3, desc = "Beds for two settlers." },
	cottage = { id = "cottage", name = "Cottage", cat = "homes", icon = "🏡", w = 3, d = 3, cost = 240, level = 7, beds = 4, light = 2, variants = 3, desc = "Beds for four settlers." },
	flowers = { id = "flowers", name = "Flower Bed", cat = "decor", icon = "🌷", w = 1, d = 1, cost = 6, level = 1, appeal = { 2, 2.5 }, variants = 4, growth = 1.02, desc = "Appeal +2 nearby." },
	hedge = { id = "hedge", name = "Hedge", cat = "decor", icon = "🌿", w = 1, d = 1, cost = 5, level = 1, appeal = { 1, 1.5 }, growth = 1.02, desc = "Appeal +1. Good for edges." },
	tree = { id = "tree", name = "Tree", cat = "decor", icon = "🌳", w = 1, d = 1, cost = 12, level = 1, appeal = { 2, 3 }, variants = 3, growth = 1.03, desc = "Appeal +2 nearby." },
	bench = { id = "bench", name = "Bench", cat = "decor", icon = "🪑", w = 1, d = 1, cost = 16, level = 2, appeal = { 2, 2.5 }, rest = true, growth = 1.05, desc = "Visitors rest here after shopping." },
	crates = { id = "crates", name = "Crates", cat = "decor", icon = "📦", w = 1, d = 1, cost = 6, level = 2, appeal = { 1, 1.5 }, growth = 1.03, desc = "Appeal +1. Looks busy." },
	banner = { id = "banner", name = "Royal Banner", cat = "decor", icon = "🚩", w = 1, d = 1, cost = 20, level = 3, appeal = { 3, 3 }, variants = 4, growth = 1.05, desc = "Your colours. Appeal +3." },
	well = { id = "well", name = "Well", cat = "decor", icon = "🪣", w = 1, d = 1, cost = 45, level = 4, appeal = { 3, 2.5 }, rest = true, desc = "Appeal +3. Visitors stop for a drink." },
	fountain = { id = "fountain", name = "Fountain", cat = "decor", icon = "⛲", w = 2, d = 2, cost = 180, level = 8, appeal = { 8, 4.5 }, rest = true, desc = "Appeal +8. Visitors love to linger." },
	statue = { id = "statue", name = "Sovereign Statue", cat = "decor", icon = "🗽", w = 2, d = 2, cost = 450, level = 12, appeal = { 12, 5 }, desc = "You, in stone. Appeal +12." },
	tower = { id = "tower", name = "Lumen Tower", cat = "defense", icon = "🗼", w = 1, d = 1, cost = 200, lumen = 15, level = 6, light = 4.5, tower = true, reach = true, limit = { 1, 0.25 }, desc = "Shoots light at Gloomlings nearby. The Veil can't snuff it." },
	heartflame = { id = "heartflame", name = "Heartflame", cat = "fixed", icon = "🔥", w = 2, d = 2, cost = 0, level = 1, fixed = true, light = 5.5, desc = "The heart of your realm." },
}
Catalog.Buildings = B
Catalog.BuildOrder = {
	"path", "lamp", "string", "arch",
	"stall", "field_turnip", "fishery", "field_wheat", "granary", "cookhouse",
	"tent", "hut", "cottage",
	"flowers", "hedge", "tree", "bench", "crates", "banner", "well", "fountain", "statue",
	"tower",
}

export type Goods = { name: string, icon: string, price: number, level: number, color: { number } }
Catalog.Goods = {
	harvest = { name = "Turnips", icon = "🥬", price = 4, level = 1, color = { 157, 187, 90 } },
	catch = { name = "Fish", icon = "🐟", price = 7, level = 2, color = { 127, 178, 196 } },
	grain = { name = "Bread", icon = "🍞", price = 6, level = 3, color = { 215, 176, 104 } },
	stew = { name = "Stew", icon = "🍲", price = 15, level = 5, color = { 201, 112, 62 } },
} :: { [string]: Goods }
Catalog.GoodsOrder = { "harvest", "catch", "grain", "stew" }

-- Stall upgrades: price multiplier, seconds per customer, gold to reach this level.
Catalog.StallLevels = {
	{ mult = 1.0, service = 2.6, cost = 0 },
	{ mult = 1.3, service = 2.0, cost = 90 },
	{ mult = 1.6, service = 1.5, cost = 280 },
	{ mult = 2.0, service = 1.1, cost = 750 },
}

export type VisitorKind = {
	name: string,
	icon: string,
	weight: number,
	rarity: string,
	minLevel: number,
	wants: { [string]: number },
	desc: string,
	settles: boolean?,
	creature: boolean?,
	pay: number?,
	lantern: number?,
	fearless: boolean?,
	nightOnly: boolean?,
	nightWeight: number?,
}
Catalog.Visitors = {
	traveler = { name = "Traveler", icon = "🧳", weight = 30, rarity = "Common", minLevel = 1, settles = true, wants = { harvest = 3, catch = 2, grain = 2, stew = 2 }, desc = "Folk on the long road between towns. Happy to stay if there's a bed." },
	merchant = { name = "Merchant", icon = "💼", weight = 16, rarity = "Common", minLevel = 1, settles = true, pay = 1.2, wants = { harvest = 1, catch = 3, grain = 2, stew = 3 }, desc = "Pays a little extra. Loves fish and stew." },
	farmhand = { name = "Farmhand", icon = "🧑‍🌾", weight = 16, rarity = "Common", minLevel = 1, settles = true, wants = { harvest = 2, catch = 1, grain = 3, stew = 3 }, desc = "Hungry after a day in the fields." },
	mossbun = { name = "Mossbun", icon = "🐰", weight = 9, rarity = "Uncommon", minLevel = 1, creature = true, wants = { harvest = 5, grain = 1 }, desc = "A little Veilkin made of moss. Mad about turnips." },
	puddlepup = { name = "Puddlepup", icon = "🐶", weight = 7, rarity = "Uncommon", minLevel = 2, creature = true, wants = { catch = 5, harvest = 1 }, desc = "Splashes in every puddle on the way in." },
	monk = { name = "Lantern Monk", icon = "🏮", weight = 8, rarity = "Uncommon", minLevel = 3, settles = true, lantern = 1.8, nightOnly = true, wants = { grain = 3, harvest = 2, stew = 2 }, desc = "Walks the night roads with a lantern. Never afraid of the dark." },
	emberkit = { name = "Emberkit", icon = "🐱", weight = 6, rarity = "Rare", minLevel = 4, creature = true, lantern = 1.4, nightOnly = true, wants = { stew = 3, catch = 2 }, desc = "A warm little cat of living coals. Only comes out at night." },
	knight = { name = "Wandering Knight", icon = "🛡️", weight = 2.5, rarity = "Rare", minLevel = 6, settles = true, pay = 2, fearless = true, nightWeight = 1.5, wants = { stew = 3, grain = 2, catch = 2 }, desc = "Fearless and generous. Tips like royalty." },
	goldbun = { name = "Golden Mossbun", icon = "✨", weight = 0.7, rarity = "Legendary", minLevel = 3, creature = true, pay = 3, wants = { harvest = 4, grain = 2 }, desc = "A legend of the old roads. Brings luck and a shower of gold." },
} :: { [string]: VisitorKind }
Catalog.VisitorOrder = { "traveler", "merchant", "farmhand", "mossbun", "puddlepup", "monk", "emberkit", "knight", "goldbun" }
Catalog.RarityColor = {
	Common = { 214, 204, 180 },
	Uncommon = { 125, 200, 110 },
	Rare = { 110, 170, 255 },
	Legendary = { 255, 196, 60 },
}

Catalog.Names = {
	"Wren", "Tobin", "Maeve", "Corin", "Ilse", "Pell", "Rosalind", "Bastian", "Nell", "Oswin", "Edda", "Finch", "Hollis",
	"Mabry", "Orla", "Percival", "Quill", "Rue", "Sabine", "Teodor", "Una", "Vesper", "Willa", "Brannoc", "Cress", "Dunstan",
	"Elowen", "Fenwick", "Greer", "Hesper", "Isolde", "Jory", "Lark", "Merrin", "Nessa", "Odo", "Posy", "Sorrel", "Tansy", "Wynn",
	"Alder", "Briar", "Clove", "Dell", "Emrys", "Fable", "Gilly", "Heath", "Ivo", "Juniper", "Kestrel", "Linden", "Moss", "Nettle",
}

Catalog.Lines = {
	arrive = { "Lanterns all the way up. Someone cares!", "Warm lights ahead!", "A market! At this hour?", "What a welcome!" },
	dark = { "So dark... is this the way?", "I can barely see the road.", "The mist is thick tonight." },
	flee = { "Too dark! I'm going back!", "Something's in the mist!", "Not tonight. No lights." },
	scared = { "What was that?!", "Eek! A Gloomling!", "Stay back!" },
	buy = {
		harvest = { "Fresh turnips!", "Crunchy and sweet." },
		grain = { "Still-warm bread!", "Smells like home." },
		catch = { "Fish from your own pond?", "Grilled trout, please!" },
		stew = { "Hot stew on a misty night...", "Seconds, please!" },
	},
	served = { "The Sovereign served me!", "Royal service!", "I'll tell everyone!", "Thank you, Your Majesty!" },
	none = { harvest = "No turnips?", grain = "No bread anywhere?", catch = "No fish today?", stew = "I hoped for something warm..." },
	soldOut = { "Sold out already?", "Empty crates...", "Nothing left?" },
	strollHigh = { "What a lovely market!", "The flowers smell wonderful.", "I could stay here forever." },
	strollMid = { "Nice and cozy.", "Pleasant spot." },
	strollLow = { "A bit bare, isn't it?", "Could use some flowers." },
	settle = { "Is there room for one more?", "I'd like to stay!", "This feels like home." },
	creature = {
		mossbun = { "Mip!", "*happy thump*" },
		puddlepup = { "Arf!", "*splash*" },
		emberkit = { "Mrrp.", "*warm purr*" },
		goldbun = { "*golden sparkle*", "Mip mip!" },
	},
}

-- ─── levels and Kingdom Rank ───────────────────────────────────────────────
Catalog.MAX_LEVEL = 30
-- XP needed to go from `level` to `level + 1`.
function Catalog.xpForLevel(level: number): number
	return math.floor(110 * level ^ 1.6)
end

Catalog.Ranks = {
	{ level = 1, name = "Exile's Camp", icon = "⛺" },
	{ level = 3, name = "Hamlet", icon = "🏘️" },
	{ level = 6, name = "Village", icon = "🏡" },
	{ level = 10, name = "Town", icon = "🏰" },
	{ level = 15, name = "City", icon = "🌆" },
	{ level = 20, name = "Kingdom", icon = "👑" },
}
function Catalog.rankFor(level: number): (string, number, string)
	local r = Catalog.Ranks[1]
	local index = 1
	for i, rank in Catalog.Ranks do
		if level >= rank.level then
			r, index = rank, i
		end
	end
	return r.name, index, r.icon
end

Catalog.Heartflame = {
	{ name = "Heartflame Brazier", radius = 7.5, light = 5.5, level = 1, gold = 0, lumen = 0 },
	{ name = "Heartflame Beacon", radius = 10, light = 7, level = 4, gold = 300, lumen = 20 },
	{ name = "Great Beacon", radius = 12.5, light = 8.5, level = 9, gold = 1200, lumen = 80 },
	{ name = "Sunspire", radius = 15.5, light = 10, level = 14, gold = 4000, lumen = 240 },
}

function Catalog.limitFor(id: string, level: number): number?
	local def = B[id]
	if not def or not def.limit then
		return nil
	end
	return math.floor(def.limit[1] + def.limit[2] * (level - 1))
end

-- XP for the things you do.
Catalog.XP = { happy = 3, tip = 1, kill = 5, place = 2, firstOfKind = 10, tend = 4, settle = 15, served = 2, discovery = 15, surge = 40, relight = 2 }
function Catalog.saleXP(price: number): number
	return 1 + price // 5
end

Catalog.Npcs = {
	Flicker = { icon = "🔥", title = "Heartflame Sprite" },
	Bram = { icon = "🧔", title = "Royal Steward" },
	Hob = { icon = "👨‍🌾", title = "Farmer" },
	Linnea = { icon = "🌿", title = "Herbalist" },
}

-- ─── quests: one chain, one at a time ──────────────────────────────────────
-- `abs` quests read a live value (level, appeal, how many you own); the rest count from when the quest starts.
export type Quest = { id: string, giver: string, title: string, text: string, stat: string, target: number, abs: boolean?, gold: number?, lumen: number?, xp: number? }
Catalog.Quests = {
	{ id = "build", giver = "Flicker", title = "Your Realm Awaits", text = "Press 🔨 Build (or B) and place anything: a Flower Bed is a fine start.", stat = "placed", target = 1, gold = 30, xp = 40 },
	{ id = "sell", giver = "Flicker", title = "First Customers", text = "Travelers are coming up the road. Sell 8 goods at your stall.", stat = "sales", target = 8, gold = 40, xp = 50 },
	{ id = "tend", giver = "Hob", title = "Royal Hands", text = "When a field sparkles ✨, walk up to it and press E to tend it.", stat = "tends", target = 2, gold = 40, xp = 50 },
	{ id = "field", giver = "Hob", title = "More Turnips", text = "Visitors are hungry. Own 2 Turnip Fields.", stat = "count_field_turnip", target = 2, abs = true, gold = 40, xp = 60 },
	{ id = "lamps", giver = "Bram", title = "Light the Old Road", text = "At night travelers turn back in the dark. Place Lantern Posts beside the Old Road until 85% of the way in is lit.", stat = "roadLit", target = 85, abs = true, gold = 60, xp = 80 },
	{ id = "night", giver = "Flicker", title = "Night Watch", text = "At night the Veil sends Gloomlings to snuff your lamps. Defeat 5 with your Lantern Staff (click).", stat = "kills", target = 5, lumen = 10, xp = 100 },
	{ id = "fish", giver = "Hob", title = "Fish from the Pond", text = "Build a Fishing Hut touching the pond, set a stall to Fish, and sell 3 fish.", stat = "sold_catch", target = 3, gold = 80, xp = 90 },
	{ id = "hut", giver = "Bram", title = "A Roof for Newcomers", text = "Happy visitors only stay if there's a free bed. Build a Hut.", stat = "count_hut", target = 1, abs = true, gold = 50, xp = 80 },
	{ id = "settler", giver = "Flicker", title = "Someone Stays", text = "Make a visitor happy enough to settle in your realm.", stat = "settlers", target = 1, gold = 100, xp = 120 },
	{ id = "appeal", giver = "Linnea", title = "Make it Lovely", text = "Raise your market's Appeal to 40 with flowers, benches and banners beside the paths.", stat = "appeal", target = 40, abs = true, gold = 120, xp = 150 },
	{ id = "heart2", giver = "Bram", title = "Raise the Heartflame", text = "Click the Heartflame in Build mode and raise it. More light, more land.", stat = "tier", target = 2, abs = true, lumen = 10, xp = 250 },
	{ id = "village", giver = "Linnea", title = "A Village at Last", text = "Reach level 6 and earn the rank of Village.", stat = "level", target = 6, abs = true, gold = 300, xp = 0 },
	{ id = "stew", giver = "Hob", title = "Stew for Cold Nights", text = "Build a Cookhouse and sell 10 Stew.", stat = "sold_stew", target = 10, gold = 250, xp = 300 },
	{ id = "tower", giver = "Bram", title = "Towers of Light", text = "Build a Lumen Tower to guard the road.", stat = "count_tower", target = 1, abs = true, lumen = 25, xp = 300 },
	{ id = "surge", giver = "Flicker", title = "Hold the Line", text = "Repel 2 Veil Surges (defeat every Gloomling of the midnight wave).", stat = "surges", target = 2, lumen = 40, xp = 400 },
	{ id = "heart3", giver = "Bram", title = "The Great Beacon", text = "Raise the Heartflame to its third tier.", stat = "tier", target = 3, abs = true, lumen = 50, xp = 600 },
	{ id = "town", giver = "Linnea", title = "Onward to Town", text = "Reach level 10 and earn the rank of Town.", stat = "level", target = 10, abs = true, gold = 1500, xp = 0 },
	{ id = "appeal2", giver = "Linnea", title = "The Talk of the Realm", text = "Raise your Appeal to 70.", stat = "appeal", target = 70, abs = true, gold = 800, xp = 800 },
	{ id = "heart4", giver = "Bram", title = "The Sunspire", text = "Raise the Heartflame to its final tier.", stat = "tier", target = 4, abs = true, lumen = 100, xp = 1500 },
	{ id = "kingdom", giver = "Linnea", title = "Long Live the Sovereign", text = "Reach level 20: a true Kingdom.", stat = "level", target = 20, abs = true, gold = 5000, xp = 0 },
} :: { Quest }

-- ─── daily Royal Orders: three new ones every dawn ─────────────────────────
export type Order = { id: string, text: string, stat: string, base: number, level: number? }
Catalog.Orders = {
	{ id = "sell_harvest", text = "Sell %d turnips", stat = "sold_harvest", base = 10 },
	{ id = "sell_catch", text = "Sell %d fish", stat = "sold_catch", base = 6, level = 2 },
	{ id = "sell_grain", text = "Sell %d bread", stat = "sold_grain", base = 6, level = 3 },
	{ id = "sell_stew", text = "Sell %d stew", stat = "sold_stew", base = 4, level = 5 },
	{ id = "kills", text = "Defeat %d Gloomlings", stat = "kills", base = 6 },
	{ id = "tips", text = "Collect %d tips", stat = "tips", base = 8 },
	{ id = "served", text = "Serve %d customers yourself", stat = "served", base = 5 },
	{ id = "happy", text = "Make %d visitors happy", stat = "happy", base = 6 },
	{ id = "tends", text = "Tend %d ripe fields", stat = "tends", base = 3 },
	{ id = "relights", text = "Relight %d snuffed lamps", stat = "relights", base = 2, level = 2 },
} :: { Order }
function Catalog.orderTarget(order: Order, level: number): number
	return math.floor(order.base * (1 + (level - 1) * 0.12) + 0.5)
end
function Catalog.orderReward(level: number): (number, number)
	return 25 + level * 10, 20 + level * 6 -- gold, xp
end

-- ─── achievements: three tiers of one stat each ────────────────────────────
export type Achievement = { id: string, name: string, icon: string, stat: string, tiers: { number }, desc: string }
Catalog.Achievements = {
	{ id = "merchant", name = "Merchant", icon = "🪙", stat = "sales", tiers = { 25, 250, 2500 }, desc = "Sell goods" },
	{ id = "warden", name = "Night Warden", icon = "⚔️", stat = "kills", tiers = { 10, 100, 500 }, desc = "Defeat Gloomlings" },
	{ id = "beloved", name = "Beloved", icon = "💛", stat = "happy", tiers = { 20, 200, 1000 }, desc = "Make visitors happy" },
	{ id = "tender", name = "Green Thumb", icon = "🌱", stat = "tends", tiers = { 10, 50, 200 }, desc = "Tend ripe fields" },
	{ id = "lamplighter", name = "Lamplighter", icon = "🏮", stat = "lights", tiers = { 5, 20, 50 }, desc = "Place lights" },
	{ id = "homemaker", name = "Homemaker", icon = "🏠", stat = "settlers", tiers = { 3, 8, 16 }, desc = "Welcome settlers" },
	{ id = "service", name = "Royal Service", icon = "🤝", stat = "served", tiers = { 10, 100, 500 }, desc = "Serve customers yourself" },
	{ id = "tipjar", name = "Tip Jar", icon = "💰", stat = "tips", tiers = { 25, 250, 1500 }, desc = "Collect tips" },
	{ id = "builder", name = "Master Builder", icon = "🔨", stat = "placed", tiers = { 20, 100, 300 }, desc = "Place buildings" },
	{ id = "flame", name = "Keeper of the Flame", icon = "🔥", stat = "tier", tiers = { 2, 3, 4 }, desc = "Raise the Heartflame" },
	{ id = "codex", name = "Collector", icon = "📖", stat = "discovered", tiers = { 4, 7, 9 }, desc = "Discover visitor kinds" },
	{ id = "nights", name = "Lantern Keeper", icon = "🌙", stat = "nights", tiers = { 3, 15, 50 }, desc = "Run Lantern Markets" },
	{ id = "surges", name = "Veilbreaker", icon = "🌀", stat = "surges", tiers = { 1, 10, 40 }, desc = "Repel Veil Surges" },
	{ id = "sovereign", name = "Sovereign", icon = "👑", stat = "level", tiers = { 6, 10, 20 }, desc = "Reach Village, Town, Kingdom" },
} :: { Achievement }
Catalog.AchievementLumen = { 5, 15, 40 }
Catalog.TierNames = { "Bronze", "Silver", "Gold" }

return Catalog
