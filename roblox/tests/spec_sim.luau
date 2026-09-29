-- The plot simulation: map, rules, market, night, Gloomlings, settlers, saves, snapshots.

local T = require("./lib")
local Config = require("./.build/shared/Config")
local Catalog = require("./.build/shared/Catalog")
local Grid = require("./.build/shared/Grid")
local PlotSim = require("./.build/shared/PlotSim")
local DayCycle = require("./.build/shared/DayCycle")
local Codec = require("./.build/shared/Codec")

local test, expect, eq = T.test, T.expect, T.eq

local function newSim(level: number?, gold: number?, seed: number?)
	local profile = { gold = gold or 500, lumen = 100, level = level or 1 }
	local sim = PlotSim.new(profile, seed or 7)
	sim:layStarter()
	return sim, profile
end

local DUSK_T = Config.DAY_LENGTH
local NIGHT_T = Config.DAY_LENGTH + Config.DUSK_LENGTH
local DAWN_T = NIGHT_T + Config.NIGHT_LENGTH

local function run(sim, from: number, seconds: number, players: any?, onEvent: ((any) -> ())?)
	local t = from
	local dt = 0.1
	for _ = 1, math.floor(seconds / dt + 0.5) do
		t += dt
		sim:update(dt, DayCycle.at(t), players)
		for _, e in sim:drain() do
			if onEvent then
				onEvent(e)
			end
		end
	end
	return t
end

local function countEvents(sim, from, seconds, players, kinds)
	local counts = {}
	run(sim, from, seconds, players, function(e)
		if kinds[e.k] then
			counts[e.k] = (counts[e.k] or 0) + 1
		end
	end)
	return counts
end

-- Light the Old Road the way a player would: a lamp beside every dark stretch.
local function lightRoad(sim)
	for z = 16, 29, 3 do
		for _, x in { 13, 16 } do
			if sim:canPlace("lamp", x, z, 0) then
				sim:place("lamp", x, z, 0, 0)
				break
			end
		end
	end
end

T.describe("Grid")

test("the Old Road runs from the entrance to the plaza", function()
	local terrain = Grid.makeTerrain(Catalog.Heartflame[1].radius)
	eq(terrain[Grid.idx(Grid.ENTRANCE.x, Grid.ENTRANCE.z)], Grid.T.ROAD, "entrance")
	eq(terrain[Grid.idx(Grid.PLAZA.x, Grid.PLAZA.z)], Grid.T.ROAD, "plaza")
	eq(terrain[Grid.idx(Grid.HEART_TILE.x, Grid.HEART_TILE.z)], Grid.T.OPEN, "heartflame tile")
	eq(terrain[Grid.idx(9, 7)], Grid.T.WATER, "pond")
end)

test("the forest surrounds the realm but leaves verges beside the road", function()
	local terrain = Grid.makeTerrain(Catalog.Heartflame[1].radius)
	eq(terrain[Grid.idx(2, 2)], Grid.T.FOREST, "far corner")
	eq(terrain[Grid.idx(13, 26)], Grid.T.OPEN, "verge beside the road")
	eq(terrain[Grid.idx(10, 26)], Grid.T.FOREST, "forest away from the road")
	local bigger = Grid.makeTerrain(Catalog.Heartflame[4].radius)
	eq(bigger[Grid.idx(10, 26)], Grid.T.OPEN, "cleared by the Sunspire")
end)

test("hash is deterministic and in [0, 1)", function()
	for x = 0, 40 do
		local h = Grid.hash(x, 3, 1)
		expect(h >= 0 and h < 1, "range")
		eq(h, Grid.hash(x, 3, 1), "deterministic")
	end
end)

T.describe("Starting plot")

test("the starter layout works: a stall on the road, a route in, some appeal", function()
	local sim = newSim()
	local stall = sim:stalls()[1]
	expect(stall, "a stall")
	expect(sim:serviceTile(stall), "the stall faces the road")
	expect(#sim:route() > 10, "a route from the entrance to the plaza")
	local lit = sim:roadLit()
	expect(lit > 10 and lit < 85, "the road starts partly dark (" .. lit .. "%)")
	expect(sim:appeal().total > 0, "some appeal")
	eq(sim.stock.harvest, Config.START_STOCK.harvest, "starting turnips")
end)

T.describe("Building rules")

test("lights may stand beside the road outside the realm; farms may not", function()
	local sim = newSim(3)
	expect(sim:canPlace("lamp", 13, 25, 0), "lamp on the verge")
	local ok, reason = sim:canPlace("field_turnip", 18, 24, 0)
	expect(not ok and reason, "field in the forest fails")
	ok = sim:canPlace("flowers", 14, 20, 0)
	expect(not ok, "nothing solid on the road")
	expect(sim:canPlace("string", 14, 18, 0), "string lights over the road")
end)

test("levels gate buildings and goods", function()
	local sim = newSim(1)
	local ok, reason = sim:canPlace("string", 14, 18, 0)
	expect(not ok and string.find(reason, "level 3"), "string lights at level 3")
	local stall = sim:stalls()[1]
	ok = sim:setGoods(stall.id, "catch")
	expect(not ok, "fish unlock at level 2")
	sim.profile.level = 2
	expect(sim:setGoods(stall.id, "catch"), "fish at level 2")
end)

test("build limits and rising costs", function()
	local sim = newSim(1, 5000)
	local limit = Catalog.limitFor("stall", 1)
	eq(limit, 2, "two stalls at level 1")
	local o = sim:place("stall", 13, 18, 1, 0)
	expect(o, "second stall")
	local ok, reason = sim:canPlace("stall", 18, 12, 1)
	expect(not ok and string.find(reason, "Limit"), "third stall refused: " .. tostring(reason))
	local c1 = sim:costOf("lamp")
	sim:place("lamp", 13, 26, 0, 0)
	local c2 = sim:costOf("lamp")
	expect(c2 >= c1, "costs never fall")
	local f1 = sim:costOf("flowers")
	for z = 11, 14 do
		expect(sim:place("flowers", 18, z, 0, 0), "flowers")
	end
	expect(sim:costOf("flowers") >= f1, "decor cost creeps up")
end)

test("the Fishing Hut must touch the pond", function()
	local sim = newSim(2)
	expect(sim:canPlace("fishery", 12, 7, 0), "beside the pond")
	expect(not sim:canPlace("fishery", 19, 11, 0), "away from the pond")
end)

test("paths: inside the realm, or joined to a path outside it", function()
	local sim = newSim()
	expect(not sim:canPaint(13, 12), "the plaza is already paved")
	expect(sim:canPaint(11, 15), "inside the realm")
	expect(sim:canPaint(13, 25), "on the verge, joined to the road")
	expect(not sim:canPaint(12, 25), "in the forest")
	local gold = sim.profile.gold
	expect(sim:paint(11, 15), "paint")
	eq(sim.profile.gold, gold - 2, "paid 2 gold")
	expect(sim:erase(11, 15), "erase")
end)

test("remove refunds half, move keeps the building", function()
	local sim, profile = newSim(1, 100)
	local o = sim:place("flowers", 18, 18, 0, 0)
	local gold = profile.gold
	local ok = sim:remove(o.id)
	expect(ok, "removed")
	eq(profile.gold, gold + math.floor(o.paid * Config.REFUND), "half back")
	local t = sim:place("tree", 18, 18, 0, 0)
	expect(sim:move(t.id, 17, 19, 0), "moved")
	eq(sim:objectAt(17, 19).id, t.id, "occupies the new tile")
	eq(sim:objectAt(18, 18), nil, "left the old tile")
end)

test("you can't remove the last bed of a settler", function()
	local sim = newSim()
	sim:addSettler("Wren", "traveler", true)
	local tent = sim:list(function(o)
		return o.type == "tent"
	end)[1]
	local ok, reason = sim:remove(tent.id)
	expect(not ok and string.find(reason, "sleeps"), "refused")
end)

test("the Heartflame needs level, gold and Lumen, and clears the forest", function()
	local sim, profile = newSim(3, 1000)
	profile.lumen = 100
	expect(not sim:canRaiseHeart(), "level 4 needed")
	profile.level = 4
	expect(sim:raiseHeart(), "raised")
	eq(sim.tier, 2, "tier 2")
	eq(sim.terrain[Grid.idx(6, 13)], Grid.T.OPEN, "forest cleared")
end)

T.describe("The market by day")

test("visitors come, buy, and pay", function()
	local sim, profile = newSim(1, 0, 3)
	local counts = countEvents(sim, 0, 200, {}, { visit = true, sale = true, tip = true, happy = true })
	expect((counts.visit or 0) >= 8, "visitors came: " .. tostring(counts.visit))
	expect((counts.sale or 0) >= 6, "sales: " .. tostring(counts.sale))
	expect(profile.gold > 0, "earned gold: " .. profile.gold)
end)

test("the Sovereign serving doubles the speed and delights customers", function()
	local sim = newSim(1, 0, 11)
	local stall = sim:stalls()[1]
	local tile = sim:serviceTile(stall)
	local served = 0
	run(sim, 0, 150, { { id = 1, x = tile[1] + 0.5, z = tile[2] + 0.5, owner = true } }, function(e)
		if e.k == "sale" and e.helper == 1 then
			served += 1
		end
	end)
	expect(served >= 3, "served " .. served)
end)

test("fields ripen and can be tended once", function()
	local sim = newSim()
	local field = sim:list(function(o)
		return o.type == "field_turnip"
	end)[1]
	field.ripeTimer = Config.TEND_INTERVAL - 0.05
	run(sim, 0, 0.2, {})
	expect(field.ripe, "ripe")
	local before = sim.stock.harvest
	expect(sim:tend(field.id, 1), "tended")
	eq(sim.stock.harvest, before + 3, "+3 turnips")
	expect(not sim:tend(field.id, 1), "only once")
end)

test("tips land near happy visitors and a player can pick them up", function()
	local sim, profile = newSim()
	sim:spawnTip(15.5, 20.5, 6)
	local gold = profile.gold
	run(sim, 0, 0.2, { { id = 1, x = 15.5, z = 20.8, owner = true } })
	eq(#sim.tips, 0, "picked up")
	eq(profile.gold, gold + 6, "gold")
end)

T.describe("The night and the Veil")

test("a dark road turns travelers back; a lit one keeps them", function()
	local function fled(lit: boolean)
		local total, visits = 0, 0
		for seed = 1, 4 do
			local sim = newSim(1, 1000, seed)
			if lit then
				lightRoad(sim)
			end
			sim.gloomTimer = 1e9 -- no Gloomlings: light alone
			sim.surge = { alive = 0, total = 0, won = true }
			local c = countEvents(sim, NIGHT_T, 120, {}, { flee = true, visit = true })
			total += c.flee or 0
			visits += c.visit or 0
		end
		return total, visits
	end
	local dark, dv = fled(false)
	local bright, bv = fled(true)
	expect(dark > 0, "some turn back on a dark road (" .. dark .. "/" .. dv .. ")")
	expect(bright < dark, "fewer turn back on a lit road (" .. bright .. "/" .. bv .. ")")
end)

test("Gloomlings come at night, snuff lamps, and fade at dawn", function()
	local sim = newSim(1, 1000, 5)
	lightRoad(sim)
	local counts = countEvents(sim, NIGHT_T, Config.NIGHT_LENGTH - 1, {}, { gloomSpawn = true, snuff = true, surge = true })
	expect((counts.gloomSpawn or 0) >= 4, "spawned " .. tostring(counts.gloomSpawn))
	expect((counts.snuff or 0) >= 1, "snuffed " .. tostring(counts.snuff))
	eq(counts.surge, 1, "one Veil Surge")
	run(sim, DAWN_T, 2, {})
	eq(#sim.gloom, 0, "gone at dawn")
end)

test("the staff kills Gloomlings for Lumen; they bite players who stand close", function()
	local sim = newSim(1, 1000, 9)
	run(sim, NIGHT_T, 20, {})
	local g = sim.gloom[1] or sim:spawnGloom(false)
	expect(g, "a Gloomling")
	local bites = 0
	run(sim, NIGHT_T + 20, 2, { { id = 1, x = g.x + 0.3, z = g.z, owner = true } }, function(e)
		if e.k == "touch" then
			bites += 1
		end
	end)
	expect(bites >= 1, "bit the player")
	local died = nil
	for _ = 1, 10 do
		if sim:damageGloom(g.id, 14, 1, g.x - 1, g.z, false) then
			break
		end
	end
	for _, e in sim:drain() do
		if e.k == "die" then
			died = e
		end
	end
	expect(died and died.lumen >= 1, "died and dropped Lumen")
end)

test("Gloomlings can't enter the Heartflame's glow", function()
	local sim = newSim(1, 1000, 2)
	expect(sim:sanctuary(Grid.HEART_X, Grid.HEART_Z + 1), "plaza is safe")
	local g = sim:spawnGloom(false)
	g.x, g.z = Grid.HEART_X, Grid.HEART_Z + 6
	g.target = { kind = "plaza" }
	g.retarget = 100
	run(sim, NIGHT_T, 20, {})
	expect(not sim:sanctuary(g.x, g.z), "stopped at the edge")
end)

T.describe("Settlers")

test("a happy visitor with a free bed moves in and gets a job", function()
	local sim = newSim(1, 1000, 4)
	local v = sim:spawnVisitor("traveler")
	run(sim, 0, 6, {})
	v.sat = 100
	v.fear = 0
	v.state = "linger"
	local settled = false
	for _ = 1, 40 do
		v.state = "linger"
		v.sat = 100
		sim.rng = PlotSim.makeRng(_ * 13)
		sim:finishVisit(v)
		if v.state == "home" then
			break
		end
	end
	eq(v.state, "home", "heading home")
	run(sim, 0, 30, {}, function(e)
		if e.k == "settle" then
			settled = true
		end
	end)
	expect(settled, "settled")
	eq(#sim.settlers, 1, "one settler")
	expect(sim.settlers[1].job, "working the field")
end)

T.describe("Saving")

test("serialize and load round-trip", function()
	local sim = newSim(4, 3000, 8)
	sim:place("lamp", 13, 26, 0, 0)
	sim:place("fishery", 12, 7, 0, 0)
	sim:paint(11, 15)
	sim:upgradeStall(sim:stalls()[1].id)
	sim:addSettler("Maeve", "merchant", true)
	local data = sim:serialize()
	local copy = PlotSim.new({ gold = 0, lumen = 0, level = 4 }, 1)
	copy:load(data)
	local n1, n2 = 0, 0
	for _ in sim.objects do
		n1 += 1
	end
	for _ in copy.objects do
		n2 += 1
	end
	eq(n2, n1, "objects")
	eq(copy.surface[Grid.idx(11, 15)], 1, "path")
	eq(copy:stalls()[1].level, 2, "stall level")
	eq(copy.stock.harvest, sim.stock.harvest, "stock")
	eq(#copy.settlers, 1, "settler")
end)

test("a damaged save falls back to the starter plot", function()
	local sim = PlotSim.new({ gold = 0, lumen = 0, level = 1 }, 1)
	sim:load("garbage")
	expect(#sim:stalls() == 1, "starter")
	local sim2 = PlotSim.new({ gold = 0, lumen = 0, level = 1 }, 1)
	sim2:load({ tier = 99, objs = { { "nope", 1, 1 }, { "lamp", -5, 3 }, "x" }, paths = { -1, 5000, "a" } })
	eq(sim2.tier, #Catalog.Heartflame, "tier clamped")
end)

T.describe("Snapshots")

test("encode/decode keeps ids, kinds and positions", function()
	local sim = newSim(1, 0, 3)
	run(sim, 0, 60, {})
	sim:spawnGloom(false)
	local b = Codec.encode(4, sim)
	local plot, list = Codec.decode(b)
	eq(plot, 4, "plot")
	expect(#list >= 1, "entities")
	expect(buffer.len(b) <= 900, "under the unreliable payload limit")
	local byId = {}
	for _, e in list do
		byId[e.id] = e
	end
	for _, v in sim.visitors do
		local e = byId[v.id]
		expect(e and math.abs(e.x - v.x) < 0.01 and math.abs(e.z - v.z) < 0.01, "visitor position")
	end
end)
