-- Pacing report for tuning:   cd roblox && lune run tests/run.luau && lune run tests/report.luau [days] [seed]
-- Plays the bot and prints, per day: level, XP by source, gold, visitors and how they felt.

local process = require("@lune/process")
local Config = require("./.build/shared/Config")
local PlotSim = require("./.build/shared/PlotSim")
local Progress = require("./.build/shared/Progress")
local DayCycle = require("./.build/shared/DayCycle")
local Bot = require("./bot")

local days = tonumber(process.args[1]) or 8
local seed = tonumber(process.args[2]) or 1
math.randomseed(seed)

local p = Progress.newProfile()
local sim = PlotSim.new(p, seed)
sim:layStarter()
Progress.startQuest(p, 1, nil)
Progress.rollOrders(p, PlotSim.makeRng(seed))
local pos = { id = 1, x = 15.5, z = 18.5, owner = true }
local t, dt = 0, 0.1
local lastPhase = "day"
local swing, think = 0, 0
local day = nil
local function newDay()
	return { xp = {}, visitors = 0, leave = 0, happy = 0, content = 0, unhappy = 0, fled = 0, satSum = 0, bought = 0, missing = {}, soldOut = 0, sales = 0, kills = 0, lumen = 0, goldStart = p.gold, spent = 0 }
end
day = newDay()
local function addXP(src, n)
	if n and n > 0 then
		day.xp[src] = (day.xp[src] or 0) + n
		Progress.addXP(p, n)
	end
end
local function report(d)
	local parts = {}
	local total = 0
	for k, v in day.xp do
		table.insert(parts, k .. " " .. v)
		total += v
	end
	table.sort(parts)
	local miss = {}
	for g, n in day.missing do
		table.insert(miss, g .. " " .. n)
	end
	print(string.format("day %d  L%d (%d/%d xp)  +%d xp  gold %d  lumen %d  appeal %d  roadLit %d  tier %d  settlers %d/%d beds",
		d, p.level, p.xp, Progress.xpNeeded(p), total, p.gold, p.lumen, sim:appeal().total, sim:roadLit(), sim.tier, #sim.settlers, sim:beds()))
	print("   xp: " .. table.concat(parts, ", "))
	local left = math.max(1, day.leave)
	print(string.format("   visitors %d  left %d  happy %d%%  content %d%%  unhappy %d%%  fled %d  avg sat %.0f  bought/visitor %.2f  sales %d  soldOut %d  missing {%s}  kills %d  lumen +%d",
		day.visitors, day.leave, day.happy * 100 // left, day.content * 100 // left, day.unhappy * 100 // left, day.fled, day.satSum / left, day.bought / left, day.sales, day.soldOut, table.concat(miss, ", "), day.kills, day.lumen))
	local stock = {}
	for g, n in sim.stock do
		table.insert(stock, g .. " " .. n)
	end
	local counts = {}
	for _, o in sim.objects do
		counts[o.type] = (counts[o.type] or 0) + 1
	end
	local cs = {}
	for k, n in counts do
		table.insert(cs, k .. " " .. n)
	end
	table.sort(cs)
	print("   stock {" .. table.concat(stock, ", ") .. "}  quest " .. p.quest.i)
	print("   built: " .. table.concat(cs, ", "))
end

local d = 1
for _ = 1, math.floor(days * DayCycle.LENGTH / dt) do
	t += dt
	local clock = DayCycle.at(t)
	if clock.phase ~= lastPhase then
		if clock.phase == "day" then
			report(d)
			d += 1
			day = newDay()
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
		day.lumen += g.lumen
		addXP(e.k, g.xp)
		if e.k == "visit" then
			day.visitors += 1
		elseif e.k == "leave" then
			day.leave += 1
			day.satSum += e.sat
			day.bought += e.bought
			if e.mood == 1 then
				day.happy += 1
			elseif e.mood == 0 then
				day.content += 1
			else
				day.unhappy += 1
			end
		elseif e.k == "flee" then
			day.fled += 1
		elseif e.k == "want" then
			day.missing[e.goods] = (day.missing[e.goods] or 0) + 1
		elseif e.k == "sale" then
			day.sales += 1
		elseif e.k == "die" then
			day.kills += 1
		end
	end
	think -= dt
	if think <= 0 then
		think = 3
		Bot.act(sim, p)
		addXP("claims", Bot.claim(sim, p))
	end
end
