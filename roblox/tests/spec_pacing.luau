-- Pacing: a bot plays whole days and we record when it reaches each level.
-- This is a baseline for tuning, not a promise about real players.

local T = require("./lib")
local Config = require("./.build/shared/Config")
local Catalog = require("./.build/shared/Catalog")
local PlotSim = require("./.build/shared/PlotSim")
local Progress = require("./.build/shared/Progress")
local DayCycle = require("./.build/shared/DayCycle")
local Bot = require("./bot")

local test, expect = T.test, T.expect

local function play(seed: number, days: number)
	math.randomseed(seed)
	local p = Progress.newProfile()
	local sim = PlotSim.new(p, seed)
	sim:layStarter()
	Progress.startQuest(p, 1, nil)
	Progress.rollOrders(p, PlotSim.makeRng(seed))
	local pos = { id = 1, x = 15.5, z = 18.5, owner = true }
	local reached = {}
	local t, dt = 0, 0.1
	local lastPhase = "day"
	local swing, think = 0, 0
	local stats = { visitors = 0, happy = 0, fled = 0, kills = 0, sales = 0, snuffed = 0 }
	local steps = math.floor(days * DayCycle.LENGTH / dt)
	for _ = 1, steps do
		t += dt
		local clock = DayCycle.at(t)
		if clock.phase ~= lastPhase then
			if clock.phase == "day" then
				p.day += 1
				Progress.rollOrders(p, PlotSim.makeRng(seed + p.day))
			end
			lastPhase = clock.phase
		end
		Bot.move(sim, pos, dt)
		sim:update(dt, clock, { pos })
		swing -= dt
		if swing <= 0 then
			swing = Config.STAFF_COOLDOWN + 0.05
			Bot.swing(sim, pos)
		end
		for _, tip in sim.tips do
			if tip.age > 3 then
				sim:collectTip(tip.id, 1)
				break
			end
		end
		for _, e in sim:drain() do
			local g = Progress.onEvent(p, e, 1)
			p.lumen += g.lumen
			for _, lv in Progress.addXP(p, g.xp) do
				reached[lv] = t / DayCycle.LENGTH
			end
			if e.k == "visit" then
				stats.visitors += 1
			elseif e.k == "happy" then
				stats.happy += 1
			elseif e.k == "flee" then
				stats.fled += 1
			elseif e.k == "die" then
				stats.kills += 1
			elseif e.k == "sale" then
				stats.sales += 1
			elseif e.k == "snuff" then
				stats.snuffed += 1
			end
		end
		think -= dt
		if think <= 0 then
			think = 3
			Bot.act(sim, p)
			for _, lv in Progress.addXP(p, Bot.claim(sim, p)) do
				reached[lv] = t / DayCycle.LENGTH
			end
		end
	end
	return p, sim, reached, stats
end

T.describe("Pacing (bot)")

test("a steady player reaches Hamlet on day 1-2 and Village within 8 days", function()
	local rows = {}
	local villages = {}
	for _, seed in { 1, 7, 42 } do
		local p, sim, reached, st = play(seed, 8)
		table.insert(villages, reached[6] or 99)
		table.insert(
			rows,
			string.format(
				"      seed %-3d  L3 day %.1f  L6 day %s  final L%d  gold %d  lumen %d  appeal %d  tier %d  settlers %d  visitors %d  happy %d%%  fled %d  kills %d  snuffed %d  quest %d",
				seed,
				reached[3] or 99,
				reached[6] and string.format("%.1f", reached[6]) or "-",
				p.level,
				p.gold,
				p.lumen,
				sim:appeal().total,
				sim.tier,
				#sim.settlers,
				st.visitors,
				st.visitors > 0 and math.floor(st.happy / st.visitors * 100) or 0,
				st.fled,
				st.kills,
				st.snuffed,
				p.quest.i
			)
		)
		expect((reached[3] or 99) <= 2, "Hamlet by day 2 (seed " .. seed .. ")")
	end
	for _, r in rows do
		print(r)
	end
	for _, d in villages do
		expect(d <= 8, "Village within 8 days")
	end
end)

test("XP curve: early levels come fast, Kingdom is a long goal", function()
	local sum = 0
	for l = 1, 19 do
		sum += Catalog.xpForLevel(l)
	end
	expect(Catalog.xpForLevel(1) <= 120, "level 2 is quick")
	expect(sum > 30000, "Kingdom takes real play (" .. sum .. " XP)")
end)
