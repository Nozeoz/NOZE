-- Progression rules: profiles, XP, quests, orders, achievements, unlock cards, event routing.

local T = require("./lib")
local Catalog = require("./.build/shared/Catalog")
local Progress = require("./.build/shared/Progress")
local PlotSim = require("./.build/shared/PlotSim")

local test, expect, eq = T.test, T.expect, T.eq

local live = { tier = 1, appeal = 20, roadLit = 30, counts = {} }

T.describe("Progression")

test("sanitize survives garbage and keeps good values", function()
	local p = Progress.sanitize({ gold = "lots", level = 999, stats = { sales = 5, [3] = 1 }, codex = { mossbun = 2 } })
	eq(p.gold, 120, "default gold")
	eq(p.level, Catalog.MAX_LEVEL, "level clamped")
	eq(p.stats.sales, 5, "stat kept")
	eq(p.codex.mossbun, 2, "codex kept")
	eq(Progress.sanitize(nil).level, 1, "nil save")
end)

test("XP carries over several levels", function()
	local p = Progress.newProfile()
	local total = Catalog.xpForLevel(1) + Catalog.xpForLevel(2) + 5
	local gained = Progress.addXP(p, total)
	eq(#gained, 2, "two levels")
	eq(p.level, 3, "level 3")
	eq(p.xp, 5, "leftover XP")
end)

test("the quest chain counts from when each quest starts", function()
	local p = Progress.newProfile()
	Progress.startQuest(p, 1, live)
	local q = Progress.quest(p, live)
	eq(q.def.id, "build", "first quest")
	expect(not q.ready, "not ready")
	Progress.bump(p, "placed")
	expect(Progress.quest(p, live).ready, "ready")
	local def, r = Progress.claimQuest(p, live)
	eq(def.id, "build", "claimed")
	eq(r.gold, 30, "reward")
	Progress.bump(p, "sales", 3)
	eq(Progress.quest(p, live).progress, 3, "second quest counts from its start")
end)

test("absolute quests read live values", function()
	local p = Progress.newProfile()
	Progress.startQuest(p, 4, live)
	eq(Progress.quest(p, live).def.id, "field", "More Turnips")
	expect(Progress.quest(p, { tier = 1, appeal = 0, roadLit = 0, counts = { field_turnip = 2 } }).ready, "two fields")
end)

test("Royal Orders: three a day, a seal for all three", function()
	local p = Progress.newProfile()
	p.level = 6
	Progress.rollOrders(p, PlotSim.makeRng(4))
	eq(#p.orders.list, 3, "three orders")
	local ids = {}
	for _, o in p.orders.list do
		expect(not ids[o.id], "distinct")
		ids[o.id] = true
		Progress.bump(p, o.stat, o.target)
	end
	local gold = p.gold
	local _, sealed1 = Progress.claimOrder(p, 1)
	Progress.claimOrder(p, 2)
	local r3, sealed3 = Progress.claimOrder(p, 3)
	expect(not sealed1 and sealed3, "sealed on the third")
	eq(r3.lumen, 5, "seal Lumen")
	expect(p.gold > gold, "gold")
	expect(not Progress.claimOrder(p, 1), "no double claim")
end)

test("achievements unlock tiers and pay Lumen", function()
	local p = Progress.newProfile()
	p.stats.sales = 300
	local list = Progress.checkAchievements(p, live)
	local merchant = 0
	for _, a in list do
		if a.def.id == "merchant" then
			merchant += 1
		end
	end
	eq(merchant, 2, "bronze and silver")
	eq(p.ach.merchant, 2, "tier saved")
	expect(p.lumen >= 20, "lumen")
	eq(#Progress.checkAchievements(p, live), 0, "nothing twice")
end)

test("level-up cards announce what's new", function()
	local function titles(level)
		local out = {}
		for _, c in Progress.unlocksAt(level) do
			out[c.title] = true
		end
		return out
	end
	local six = titles(6)
	expect(six["Village"], "Village rank at 6")
	expect(six["Lumen Tower"], "tower at 6")
	local two = titles(2)
	expect(two["Fishing Hut"] and two["Fish"] and two["Puddlepup"], "level 2 unlocks")
	local four = titles(4)
	expect(four["Heartflame Beacon"], "Heartflame at 4")
end)

test("event routing: sales, serving, helpers, discoveries", function()
	local p = Progress.newProfile()
	local g = Progress.onEvent(p, { k = "sale", goods = "harvest", price = 5, helper = 1 }, 1)
	eq(p.stats.served, 1, "served by the owner")
	expect(g.xp >= 3, "sale XP")
	g = Progress.onEvent(p, { k = "sale", goods = "harvest", price = 5, helper = 42 }, 1)
	eq(g.helper, 42, "a friend helped")
	g = Progress.onEvent(p, { k = "visit", kind = "mossbun" }, 1)
	eq(g.discovered, "mossbun", "new kind")
	g = Progress.onEvent(p, { k = "visit", kind = "mossbun" }, 1)
	eq(g.discovered, nil, "only once")
	g = Progress.onEvent(p, { k = "placed", type = "lamp" }, 1)
	eq(g.first, "lamp", "first lamp")
	eq(p.stats.lights, 1, "lights counted")
end)
