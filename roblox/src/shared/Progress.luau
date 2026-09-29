--!strict
-- Player progression as pure data rules: the saved profile, XP and levels, the quest chain,
-- daily Royal Orders, achievements, the visitor Codex, and what each level unlocks.
-- The server's ProgressService wraps this with remotes and effects; the Lune tests use it directly.

local Catalog = require(script.Parent.Catalog)

local Progress = {}

export type Live = { tier: number, appeal: number, roadLit: number, counts: { [string]: number } }

export type OrderState = { id: string, stat: string, target: number, base: number, claimed: boolean }

export type Profile = {
	v: number,
	gold: number,
	lumen: number,
	level: number,
	xp: number,
	stats: { [string]: number },
	quest: { i: number, base: number },
	orders: { day: number, list: { OrderState }, sealed: boolean },
	ach: { [string]: number },
	codex: { [string]: number },
	built: { [string]: boolean },
	day: number,
	plot: any,
	settings: { music: number, sfx: number, amb: number },
	welcomed: boolean,
	best: { [string]: number },
}

local STATS = {
	"sales", "sold_harvest", "sold_catch", "sold_grain", "sold_stew", "happy", "tips", "tipGold", "kills", "tends",
	"lights", "settlers", "served", "placed", "visitors", "earned", "nights", "surges", "relights", "fled",
}

function Progress.newProfile(): Profile
	local stats = {}
	for _, s in STATS do
		stats[s] = 0
	end
	return {
		v = 1,
		gold = 120,
		lumen = 0,
		level = 1,
		xp = 0,
		stats = stats,
		quest = { i = 1, base = 0 },
		orders = { day = -1, list = {}, sealed = false },
		ach = {},
		codex = {},
		built = {},
		day = 1,
		plot = nil,
		settings = { music = 0.5, sfx = 0.8, amb = 0.6 },
		welcomed = false,
		best = { nightGold = 0, nightHappy = 0 },
	}
end

local function num(v: any, default: number): number
	return type(v) == "number" and v == v and v or default
end

-- Fill in anything missing from an older or damaged save.
function Progress.sanitize(raw: any): Profile
	local p = Progress.newProfile()
	if type(raw) ~= "table" then
		return p
	end
	p.gold = math.max(0, math.floor(num(raw.gold, p.gold)))
	p.lumen = math.max(0, math.floor(num(raw.lumen, 0)))
	p.level = math.clamp(math.floor(num(raw.level, 1)), 1, Catalog.MAX_LEVEL)
	p.xp = math.max(0, math.floor(num(raw.xp, 0)))
	if type(raw.stats) == "table" then
		for k, v in raw.stats do
			if type(k) == "string" then
				p.stats[k] = num(v, 0)
			end
		end
	end
	if type(raw.quest) == "table" then
		p.quest.i = math.max(1, math.floor(num(raw.quest.i, 1)))
		p.quest.base = num(raw.quest.base, 0)
	end
	if type(raw.orders) == "table" and type(raw.orders.list) == "table" then
		p.orders.day = num(raw.orders.day, -1)
		p.orders.sealed = raw.orders.sealed == true
		for _, o in raw.orders.list do
			if type(o) == "table" and type(o.id) == "string" and type(o.stat) == "string" then
				table.insert(p.orders.list, { id = o.id, stat = o.stat, target = num(o.target, 1), base = num(o.base, 0), claimed = o.claimed == true })
			end
		end
	end
	for _, key in { "ach", "codex" } do
		local src = raw[key]
		if type(src) == "table" then
			for k, v in src do
				if type(k) == "string" then
					(p :: any)[key][k] = num(v, 0)
				end
			end
		end
	end
	if type(raw.built) == "table" then
		for k, v in raw.built do
			if type(k) == "string" and v then
				p.built[k] = true
			end
		end
	end
	p.day = math.max(1, math.floor(num(raw.day, 1)))
	p.plot = raw.plot
	if type(raw.settings) == "table" then
		p.settings.music = math.clamp(num(raw.settings.music, 0.5), 0, 1)
		p.settings.sfx = math.clamp(num(raw.settings.sfx, 0.8), 0, 1)
		p.settings.amb = math.clamp(num(raw.settings.amb, 0.6), 0, 1)
	end
	p.welcomed = raw.welcomed == true
	if type(raw.best) == "table" then
		for k, v in raw.best do
			if type(k) == "string" then
				p.best[k] = num(v, 0)
			end
		end
	end
	return p
end

function Progress.bump(p: Profile, stat: string, n: number?)
	p.stats[stat] = (p.stats[stat] or 0) + (n or 1)
end

function Progress.discovered(p: Profile): number
	local n = 0
	for _ in p.codex do
		n += 1
	end
	return n
end

-- A stat's current value. Live values (level, tier, appeal, how many you own) come from the plot.
function Progress.value(p: Profile, stat: string, live: Live?): number
	if stat == "level" then
		return p.level
	elseif stat == "discovered" then
		return Progress.discovered(p)
	end
	if live then
		if stat == "tier" then
			return live.tier
		elseif stat == "appeal" then
			return live.appeal
		elseif stat == "roadLit" then
			return live.roadLit
		elseif string.sub(stat, 1, 6) == "count_" then
			return live.counts[string.sub(stat, 7)] or 0
		end
	end
	return p.stats[stat] or 0
end

-- ─── XP and levels ─────────────────────────────────────────────────────────
function Progress.xpNeeded(p: Profile): number
	return Catalog.xpForLevel(p.level)
end

-- Adds XP; returns the levels reached (possibly several).
function Progress.addXP(p: Profile, n: number): { number }
	local gained = {}
	if p.level >= Catalog.MAX_LEVEL then
		return gained
	end
	p.xp += math.max(0, math.floor(n))
	while p.level < Catalog.MAX_LEVEL and p.xp >= Catalog.xpForLevel(p.level) do
		p.xp -= Catalog.xpForLevel(p.level)
		p.level += 1
		table.insert(gained, p.level)
	end
	if p.level >= Catalog.MAX_LEVEL then
		p.xp = 0
	end
	return gained
end

export type Card = { icon: string, title: string, text: string, kind: string }

-- What reaching `level` unlocks, as cards for the level-up ceremony.
function Progress.unlocksAt(level: number): { Card }
	local cards: { Card } = {}
	for _, r in Catalog.Ranks do
		if r.level == level and level > 1 then
			table.insert(cards, { icon = r.icon, title = r.name, text = "Your realm is now a " .. r.name .. "!", kind = "rank" })
		end
	end
	for _, id in Catalog.BuildOrder do
		local def = Catalog.Buildings[id]
		if def.level == level and level > 1 then
			table.insert(cards, { icon = def.icon, title = def.name, text = "New building", kind = "building" })
		end
	end
	for _, g in Catalog.GoodsOrder do
		local def = Catalog.Goods[g]
		if def.level == level and level > 1 then
			table.insert(cards, { icon = def.icon, title = def.name, text = "New goods visitors will ask for", kind = "goods" })
		end
	end
	for i, t in Catalog.Heartflame do
		if i > 1 and t.level == level then
			table.insert(cards, { icon = "🔥", title = t.name, text = "The Heartflame can be raised", kind = "heart" })
		end
	end
	for _, id in Catalog.BuildOrder do
		local def = Catalog.Buildings[id]
		if def.limit and level > 1 and def.level < level then
			local now, before = Catalog.limitFor(id, level), Catalog.limitFor(id, level - 1)
			if now and before and now > before then
				table.insert(cards, { icon = def.icon, title = "+1 " .. def.name, text = `You can own {now}`, kind = "limit" })
			end
		end
	end
	for _, k in Catalog.VisitorOrder do
		local def = Catalog.Visitors[k]
		if def.minLevel == level and level > 1 then
			table.insert(cards, { icon = def.icon, title = def.name, text = "May visit your market now", kind = "visitor" })
		end
	end
	return cards
end

-- ─── quests ────────────────────────────────────────────────────────────────
export type QuestView = { def: Catalog.Quest, index: number, progress: number, target: number, ready: boolean }

function Progress.quest(p: Profile, live: Live?): QuestView?
	local def = Catalog.Quests[p.quest.i]
	if not def then
		return nil
	end
	local v = Progress.value(p, def.stat, live)
	local progress = def.abs and v or (v - p.quest.base)
	progress = math.clamp(progress, 0, def.target)
	return { def = def, index = p.quest.i, progress = progress, target = def.target, ready = progress >= def.target }
end

-- Moves to the next quest and records where its count starts.
function Progress.startQuest(p: Profile, index: number, live: Live?)
	p.quest.i = index
	local def = Catalog.Quests[index]
	p.quest.base = def and Progress.value(p, def.stat, live) or 0
end

export type Reward = { gold: number, lumen: number, xp: number }

function Progress.claimQuest(p: Profile, live: Live?): (Catalog.Quest?, Reward?)
	local q = Progress.quest(p, live)
	if not q or not q.ready then
		return nil, nil
	end
	local r = { gold = q.def.gold or 0, lumen = q.def.lumen or 0, xp = q.def.xp or 0 }
	p.gold += r.gold
	p.lumen += r.lumen
	Progress.startQuest(p, p.quest.i + 1, live)
	return q.def, r
end

-- ─── daily Royal Orders ────────────────────────────────────────────────────
function Progress.rollOrders(p: Profile, rng: { next: () -> number })
	local pool = {}
	for _, o in Catalog.Orders do
		if (o.level or 1) <= p.level then
			table.insert(pool, o)
		end
	end
	local list = {}
	for _ = 1, 3 do
		if #pool == 0 then
			break
		end
		local i = math.min(#pool, 1 + math.floor(rng.next() * #pool))
		local o = table.remove(pool, i) :: Catalog.Order
		table.insert(list, { id = o.id, stat = o.stat, target = Catalog.orderTarget(o, p.level), base = p.stats[o.stat] or 0, claimed = false })
	end
	p.orders = { day = p.day, list = list, sealed = false }
end

function Progress.orderProgress(p: Profile, o: OrderState): number
	return math.clamp((p.stats[o.stat] or 0) - o.base, 0, o.target)
end

function Progress.claimOrder(p: Profile, i: number): (Reward?, boolean)
	local o = p.orders.list[i]
	if not o or o.claimed or Progress.orderProgress(p, o) < o.target then
		return nil, false
	end
	o.claimed = true
	local gold, xp = Catalog.orderReward(p.level)
	local r = { gold = gold, lumen = 0, xp = xp }
	local all = true
	for _, other in p.orders.list do
		if not other.claimed then
			all = false
		end
	end
	local sealed = false
	if all and not p.orders.sealed then
		p.orders.sealed = true
		sealed = true
		r.lumen += 5
	end
	p.gold += r.gold
	p.lumen += r.lumen
	return r, sealed
end

-- ─── achievements ──────────────────────────────────────────────────────────
export type AchievementUnlock = { def: Catalog.Achievement, tier: number, lumen: number }

function Progress.checkAchievements(p: Profile, live: Live?): { AchievementUnlock }
	local out = {}
	for _, a in Catalog.Achievements do
		local have = p.ach[a.id] or 0
		local v = Progress.value(p, a.stat, live)
		while have < #a.tiers and v >= a.tiers[have + 1] do
			have += 1
			local lumen = Catalog.AchievementLumen[have]
			p.lumen += lumen
			table.insert(out, { def = a, tier = have, lumen = lumen })
		end
		p.ach[a.id] = have
	end
	return out
end

-- ─── the visitor Codex ─────────────────────────────────────────────────────
-- Returns true the first time a kind is seen.
function Progress.meet(p: Profile, kind: string): boolean
	local seen = p.codex[kind]
	p.codex[kind] = (seen or 0) + 1
	return seen == nil
end

-- ─── plot events → stats and XP ────────────────────────────────────────────
-- What one plot event is worth. `owner` is the plot owner's UserId; `by`/`helper` fields name whoever
-- did the deed, who may be a visiting friend. The server applies `helperXp`/`helperLumen` to that player.
export type Gain = { xp: number, lumen: number, helper: number?, helperXp: number, helperLumen: number, discovered: string?, first: string? }

local LIGHTS = { lamp = true, string = true, arch = true, tower = true }

function Progress.onEvent(p: Profile, e: any, owner: number): Gain
	local g: Gain = { xp = 0, lumen = 0, helper = nil, helperXp = 0, helperLumen = 0, discovered = nil, first = nil }
	local k = e.k
	local XP = Catalog.XP
	if k == "sale" then
		Progress.bump(p, "sales")
		Progress.bump(p, "sold_" .. e.goods)
		Progress.bump(p, "earned", e.price)
		local xp = Catalog.saleXP(e.price)
		if e.helper == owner then
			Progress.bump(p, "served")
			xp += XP.served
		elseif e.helper then
			g.helper, g.helperXp = e.helper, XP.served + 1
		end
		g.xp += xp
	elseif k == "happy" then
		Progress.bump(p, "happy")
		g.xp += XP.happy
	elseif k == "tipGone" then
		if e.by and e.by ~= 0 then
			Progress.bump(p, "tips")
			Progress.bump(p, "tipGold", e.value)
			if e.by == owner then
				g.xp += XP.tip
			else
				g.helper, g.helperXp = e.by, XP.tip
			end
		end
		Progress.bump(p, "earned", e.value)
	elseif k == "die" then
		Progress.bump(p, "kills")
		if e.by == nil or e.by == owner then
			g.xp += e.by and XP.kill or XP.kill // 2
			g.lumen += e.lumen
		else
			g.helper, g.helperXp, g.helperLumen = e.by, XP.kill, e.lumen
			g.lumen += 1
		end
	elseif k == "tend" then
		if e.by == owner or e.by == nil then
			Progress.bump(p, "tends")
			g.xp += XP.tend
		else
			g.helper, g.helperXp = e.by, XP.tend
		end
	elseif k == "relight" then
		Progress.bump(p, "relights")
		if e.by == owner or e.by == nil then
			g.xp += XP.relight
		else
			g.helper, g.helperXp = e.by, XP.relight
		end
	elseif k == "settle" then
		Progress.bump(p, "settlers")
		g.xp += XP.settle
	elseif k == "placed" then
		Progress.bump(p, "placed")
		if LIGHTS[e.type] then
			Progress.bump(p, "lights")
		end
		g.xp += XP.place
		if not p.built[e.type] then
			p.built[e.type] = true
			g.xp += XP.firstOfKind
			g.first = e.type
		end
	elseif k == "visit" then
		Progress.bump(p, "visitors")
		if Progress.meet(p, e.kind) then
			g.xp += XP.discovery
			g.discovered = e.kind
		end
	elseif k == "surgeWon" then
		Progress.bump(p, "surges")
		g.xp += XP.surge
		g.lumen += 5
	elseif k == "night" then
		Progress.bump(p, "nights")
	elseif k == "flee" then
		Progress.bump(p, "fled")
	end
	return g
end

return Progress
