-- A simple player used to measure pacing: it lights the road, builds stalls and farms, decorates,
-- keeps beds free, serves at the busiest stall by day, and hunts Gloomlings at night.

local Catalog = require("./.build/shared/Catalog")
local Grid = require("./.build/shared/Grid")
local Progress = require("./.build/shared/Progress")

local B = Catalog.Buildings
local Bot = {}

local function tryAll(sim, type_, score)
	local best, bestS = nil, -math.huge
	for z = 0, Grid.H - 1 do
		for x = 0, Grid.W - 1 do
			for rot = 0, (B[type_].w ~= B[type_].d) and 3 or 0 do
				if sim:canPlace(type_, x, z, rot) then
					local s = score(x, z, rot)
					if s and s > bestS then
						best, bestS = { x, z, rot }, s
					end
				end
			end
		end
	end
	if best then
		return sim:place(type_, best[1], best[2], best[3], math.random(0, 3))
	end
	return nil
end

local function distPlaza(x, z)
	return math.abs(x + 0.5 - Grid.PLAZA.x) + math.abs(z + 0.5 - Grid.PLAZA.z)
end

function Bot.lamp(sim)
	local before = sim:roadLit()
	local best, bestGain = nil, 0
	for z = 0, Grid.H - 1 do
		for x = 0, Grid.W - 1 do
			if sim:canPlace("lamp", x, z, 0) then
				local o = sim:place("lamp", x, z, 0, 0, { fixed = true })
				local gain = sim:roadLit() - before
				sim:stamp(o, 0)
				sim.objects[o.id] = nil
				sim:changed()
				if gain > bestGain then
					best, bestGain = { x, z }, gain
				end
			end
		end
	end
	if best then
		return sim:place("lamp", best[1], best[2], 0, 0)
	end
	return nil
end

function Bot.stall(sim, goods)
	local o = tryAll(sim, "stall", function(x, z, rot)
		local probe = { id = -1, type = "stall", x = x, z = z, rot = rot }
		probe.w, probe.d = sim:size("stall", rot)
		for _, t in sim:frontTiles(probe) do
			if sim:visitorWalkable(t[1], t[2]) and sim:reachable(t[1], t[2]) then
				return -distPlaza(x, z)
			end
		end
		return nil
	end)
	if o then
		sim:setGoods(o.id, goods)
	end
	return o
end

function Bot.near(sim, type_)
	return tryAll(sim, type_, function(x, z)
		return -distPlaza(x, z) + math.random() * 2
	end)
end

function Bot.decor(sim, type_)
	return tryAll(sim, type_, function(x, z)
		if not sim:besidePath(x, z) then
			return nil
		end
		return -distPlaza(x, z) * 0.5 + math.random() * 3
	end)
end

local function sellers(sim, goods)
	local n = 0
	for _, s in sim:stalls() do
		if s.goods == goods then
			n += 1
		end
	end
	return n
end

-- One round of decisions. Keeps a little gold back for lamps.
function Bot.act(sim, p)
	for _, o in sim.objects do
		if o.snuffed then
			sim:relight(o.id, 1)
		end
		if o.ripe then
			sim:tend(o.id, 1)
		end
	end
	if sim:canRaiseHeart() then
		sim:raiseHeart()
	end
	if sim:roadLit() < 90 and p.gold >= sim:costOf("lamp") then
		if Bot.lamp(sim) then
			return
		end
	end
	local L = p.level
	local q = Catalog.Quests[p.quest.i]
	local questType = q and string.match(q.stat, "^count_(.+)$")
	local wants = {
		{ questType or "", questType ~= nil and sim:count(questType) < q.target },
		{ "field_turnip", L >= 1 and sim:count("field_turnip") < 2 },
		{ "stall:catch", L >= 2 and sellers(sim, "catch") == 0 and sim:count("fishery") > 0 },
		{ "fishery", L >= 2 and sim:count("fishery") == 0 },
		{ "tent", sim:freeBeds() == 0 and L < 3 and #sim.settlers < 8 },
		{ "hut", sim:freeBeds() == 0 and L >= 3 and #sim.settlers < 8 },
		{ "field_wheat", L >= 3 and sim:count("field_wheat") == 0 },
		{ "stall:grain", L >= 3 and sellers(sim, "grain") == 0 and sim:count("field_wheat") > 0 },
		{ "cookhouse", L >= 5 and sim:count("cookhouse") == 0 },
		{ "stall:stew", L >= 5 and sellers(sim, "stew") == 0 and sim:count("cookhouse") > 0 },
		{ "field_turnip", sim:count("field_turnip") < (Catalog.limitFor("field_turnip", L) or 0) },
		{ "tower", L >= 6 and sim:count("tower") == 0 },
		{ "bench", L >= 2 and sim:count("bench") < 3 },
		{ "flowers", sim:appeal().total < 70 },
		{ "banner", L >= 3 and sim:appeal().total < 70 },
		{ "tree", sim:appeal().total < 70 },
		{ "stall:harvest", sellers(sim, "harvest") < 2 and sim:count("stall") < (Catalog.limitFor("stall", L) or 0) - (L >= 2 and 1 or 0) - (L >= 3 and 1 or 0) - (L >= 5 and 1 or 0) },
	}
	for _, w in wants do
		if w[2] and w[1] ~= "" then
			local id = w[1]
			local goods = string.match(id, "^stall:(%a+)$")
			local type_ = goods and "stall" or id
			local cost = sim:costOf(type_)
			if p.gold >= cost + 10 then
				local placed
				if goods then
					placed = Bot.stall(sim, goods)
				elseif B[type_].cat == "decor" then
					placed = Bot.decor(sim, type_)
				else
					placed = Bot.near(sim, type_)
				end
				if placed then
					return
				end
			end
		end
	end
	for _, s in sim:stalls() do
		local nxt = Catalog.StallLevels[s.level + 1]
		if nxt and p.gold > nxt.cost * 2 then
			sim:upgradeStall(s.id)
			return
		end
	end
end

-- Where the Sovereign stands: at the busiest stall by day, chasing Gloomlings at night.
function Bot.move(sim, pos, dt)
	local tx, tz
	local g = sim.gloom[1]
	if g then
		local best = math.huge
		for _, other in sim.gloom do
			local d = (other.x - pos.x) ^ 2 + (other.z - pos.z) ^ 2
			if d < best then
				best, g = d, other
			end
		end
		tx, tz = g.x, g.z
	else
		local busiest, n = nil, -1
		for _, s in sim:stalls() do
			if #s.queue > n and sim:serviceTile(s) then
				busiest, n = s, #s.queue
			end
		end
		if busiest then
			local t = sim:serviceTile(busiest)
			tx, tz = t[1] + 0.5, t[2] + 0.5
		end
	end
	if tx then
		local dx, dz = tx - pos.x, tz - pos.z
		local d = math.sqrt(dx * dx + dz * dz)
		local step = 3.3 * dt
		if d > 0.05 then
			pos.x += dx / d * math.min(step, d)
			pos.z += dz / d * math.min(step, d)
		end
	end
end

function Bot.swing(sim, pos)
	for _, g in sim.gloom do
		local d = math.sqrt((g.x - pos.x) ^ 2 + (g.z - pos.z) ^ 2)
		if d < 1.8 then
			sim:damageGloom(g.id, 14, 1, pos.x, pos.z, false)
			return
		end
	end
end

function Bot.claim(sim, p)
	local live = { tier = sim.tier, appeal = sim:appeal().total, roadLit = sim:roadLit(), counts = {} }
	for _, o in sim.objects do
		live.counts[o.type] = (live.counts[o.type] or 0) + 1
	end
	local _, r = Progress.claimQuest(p, live)
	local xp = r and r.xp or 0
	for i = 1, #p.orders.list do
		local rr = Progress.claimOrder(p, i)
		if rr then
			xp += rr.xp
		end
	end
	Progress.checkAchievements(p, live)
	return xp
end

return Bot
