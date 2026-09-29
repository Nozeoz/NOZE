--!nonstrict
-- The simulation of one plot: the tile map, building rules, light and the Veil, appeal, production,
-- the market (visitors, stalls, tips), settlers and Gloomlings.
-- Pure Luau: no Roblox types or services, so the same file runs on the server, on the client
-- (placement previews) and in the Lune tests. It never grants XP; it records what happened in
-- `events` for the server to route. Positions are in tile units; tile (x, z) has its centre at (x+0.5, z+0.5).

local Config = require(script.Parent.Config)
local Catalog = require(script.Parent.Catalog)
local Grid = require(script.Parent.Grid)

local W, H = Grid.W, Grid.H
local T = Grid.T
local idx = Grid.idx
local inBounds = Grid.inBounds
local B = Catalog.Buildings
local KINDS = Catalog.Visitors
local LINES = Catalog.Lines

local LIT = Config.LIT
local QUEUE_GAP = 0.42
local PLAYER_LIGHT = 2.6 -- the Sovereign's lantern staff lights this far (tiles)
local SERVE_TILES = Config.SERVE_RADIUS / Config.TILE
local TIP_TILES = Config.TIP_PICKUP_RADIUS / Config.TILE
local TIP_LIFE = 60
local ROT_CS = { [0] = { 1, 0 }, [1] = { 0, 1 }, [2] = { -1, 0 }, [3] = { 0, -1 } }

local function clamp(v: number, a: number, b: number): number
	return math.max(a, math.min(b, v))
end

local function makeRng(seed: number)
	local s = math.floor(seed) % 2147483647
	if s <= 0 then
		s += 2147483646
	end
	local r = {}
	function r.next(): number
		s = (s * 48271) % 2147483647
		return s / 2147483647
	end
	function r.range(a: number, b: number): number
		return a + (b - a) * r.next()
	end
	function r.int(a: number, b: number): number
		return math.min(b, a + math.floor(r.next() * (b - a + 1)))
	end
	function r.chance(p: number): boolean
		return r.next() < p
	end
	function r.pick(list)
		return list[r.int(1, #list)]
	end
	function r.weighted(items)
		local total = 0
		for _, it in items do
			total += it[2]
		end
		if total <= 0 then
			return items[1] and items[1][1]
		end
		local roll = r.next() * total
		for _, it in items do
			roll -= it[2]
			if roll <= 0 then
				return it[1]
			end
		end
		return items[#items][1]
	end
	return r
end

local PlotSim = {}
PlotSim.__index = PlotSim
PlotSim.makeRng = makeRng

export type Profile = { gold: number, lumen: number, level: number }
export type PlayerPos = { id: number, x: number, z: number, owner: boolean }
export type Clock = { phase: string, night: number, progress: number }

function PlotSim.new(profile: Profile, seed: number?)
	local self = setmetatable({}, PlotSim)
	self.profile = profile
	self.rng = makeRng(seed or 1)
	self.tier = 1
	self.terrain = Grid.makeTerrain(Catalog.Heartflame[1].radius)
	self.surface = table.create(W * H, 0)
	self.occ = table.create(W * H, 0)
	self.objects = {}
	self.nextId = 1
	self.version = 0
	self.stock = { harvest = 0, catch = 0, grain = 0, stew = 0 }
	self.visitors = {}
	self.gloom = {}
	self.tips = {}
	self.settlers = {}
	self.players = {}
	self.events = {}
	self.cache = {}
	self.eid = 0
	self.time = 0
	self.spawnTimer = 4
	self.gloomTimer = 5
	self.surge = nil
	self.night = nil
	self.clock = { phase = "day", night = 0, progress = 0 }
	self.usedNames = {}
	return self
end

-- ─── events ────────────────────────────────────────────────────────────────
function PlotSim:emit(e)
	table.insert(self.events, e)
end

function PlotSim:drain()
	local out = self.events
	self.events = {}
	return out
end

function PlotSim:newId(): number
	self.eid = self.eid % 65000 + 1
	return self.eid
end

-- ─── map helpers ───────────────────────────────────────────────────────────
function PlotSim:size(type_: string, rot: number): (number, number)
	local def = B[type_]
	if rot % 2 == 1 then
		return def.d, def.w
	end
	return def.w, def.d
end

function PlotSim:objectAt(x: number, z: number)
	if not inBounds(x, z) then
		return nil
	end
	local id = self.occ[idx(x, z)]
	if id == 0 then
		return nil
	end
	return self.objects[id]
end

function PlotSim:isPath(x: number, z: number): boolean
	if not inBounds(x, z) then
		return false
	end
	local i = idx(x, z)
	return self.surface[i] == 1 or self.terrain[i] == T.ROAD
end

function PlotSim:besidePath(x: number, z: number): boolean
	for _, n in Grid.N8 do
		if self:isPath(x + n[1], z + n[2]) then
			return true
		end
	end
	return false
end

function PlotSim:visitorWalkable(x: number, z: number): boolean
	if not self:isPath(x, z) then
		return false
	end
	local o = self:objectAt(x, z)
	return o == nil or B[o.type].walkable == true
end

function PlotSim:groundWalkable(x: number, z: number): boolean
	if not inBounds(x, z) then
		return false
	end
	local t = self.terrain[idx(x, z)]
	if t == T.FOREST or t == T.WATER then
		return false
	end
	local o = self:objectAt(x, z)
	if o == nil then
		return true
	end
	local def = B[o.type]
	return def.walkable == true or (def.cat == "decor" and def.w == 1 and def.d == 1 and not def.rest)
end

function PlotSim:radius(): number
	return Catalog.Heartflame[self.tier].radius
end

function PlotSim:inRealm(x: number, z: number): boolean
	return Grid.distToHeart(x, z) <= self:radius()
end

function PlotSim:objCentre(o): (number, number)
	return o.x + o.w / 2, o.z + o.d / 2
end

function PlotSim:frontTiles(o)
	local f = Grid.FRONT[o.rot]
	local out = {}
	if f[2] == 1 then
		for i = 0, o.w - 1 do
			table.insert(out, { o.x + i, o.z + o.d })
		end
	elseif f[2] == -1 then
		for i = 0, o.w - 1 do
			table.insert(out, { o.x + i, o.z - 1 })
		end
	elseif f[1] == 1 then
		for j = 0, o.d - 1 do
			table.insert(out, { o.x + o.w, o.z + j })
		end
	else
		for j = 0, o.d - 1 do
			table.insert(out, { o.x - 1, o.z + j })
		end
	end
	return out
end

function PlotSim:neighbourTiles(o)
	local out = {}
	for x = o.x - 1, o.x + o.w do
		for z = o.z - 1, o.z + o.d do
			local inside = x >= o.x and x < o.x + o.w and z >= o.z and z < o.z + o.d
			local corner = (x == o.x - 1 or x == o.x + o.w) and (z == o.z - 1 or z == o.z + o.d)
			if not inside and not corner then
				table.insert(out, { x, z })
			end
		end
	end
	return out
end

-- Centre of local tile (lx, lz) of an object's unrotated footprint, in plot tile units.
function PlotSim:rotLocal(o, lx: number, lz: number): (number, number)
	local def = B[o.type]
	local cx = lx + 0.5 - def.w / 2
	local cz = lz + 0.5 - def.d / 2
	local cs = ROT_CS[o.rot]
	local rx = cx * cs[1] + cz * cs[2]
	local rz = -cx * cs[2] + cz * cs[1]
	local ox, oz = self:objCentre(o)
	return ox + rx, oz + rz
end

function PlotSim:stamp(o, value: number)
	for dz = 0, o.d - 1 do
		for dx = 0, o.w - 1 do
			self.occ[idx(o.x + dx, o.z + dz)] = value
		end
	end
end

function PlotSim:count(type_: string): number
	local n = 0
	for _, o in self.objects do
		if o.type == type_ then
			n += 1
		end
	end
	return n
end

function PlotSim:list(pred)
	local out = {}
	for _, o in self.objects do
		if pred(o) then
			table.insert(out, o)
		end
	end
	table.sort(out, function(a, b)
		return a.id < b.id
	end)
	return out
end

function PlotSim:changed(mapChanged: boolean?)
	if mapChanged ~= false then
		self.version += 1
	end
	self.cache = {}
	self:assignJobs()
end

-- ─── building rules ────────────────────────────────────────────────────────
function PlotSim:costOf(type_: string): (number, number)
	local def = B[type_]
	local growth = def.growth or Config.COST_GROWTH
	return math.floor(def.cost * growth ^ self:count(type_) + 0.5), def.lumen or 0
end

function PlotSim:limitOf(type_: string): number?
	return Catalog.limitFor(type_, self.profile.level)
end

-- Geometry only: the footprint, terrain, other buildings, the realm and the pond.
function PlotSim:fits(type_: string, x: number, z: number, rot: number, ignoreId: number?): (boolean, string?)
	local def = B[type_]
	if not def then
		return false, "Unknown building."
	end
	local w, d = self:size(type_, rot)
	local allRealm, allReach, wet = true, true, false
	for dz = 0, d - 1 do
		for dx = 0, w - 1 do
			local tx, tz = x + dx, z + dz
			if not inBounds(tx, tz) then
				return false, "That runs off the edge of your land."
			end
			local i = idx(tx, tz)
			local t = self.terrain[i]
			if t == T.FOREST then
				return false, "The forest is too thick. Raise the Heartflame to clear it."
			end
			if t == T.WATER then
				return false, "That's the pond."
			end
			local occ = self.occ[i]
			if occ ~= 0 and occ ~= ignoreId then
				return false, "Something is already here."
			end
			if not def.walkable and self:isPath(tx, tz) then
				return false, "Keep the paths clear."
			end
			if not self:inRealm(tx, tz) then
				allRealm = false
				if not self:besidePath(tx, tz) then
					allReach = false
				end
			end
			if def.needsWater and not wet then
				for _, n in Grid.N4 do
					local nx, nz = tx + n[1], tz + n[2]
					if inBounds(nx, nz) and self.terrain[idx(nx, nz)] == T.WATER then
						wet = true
						break
					end
				end
			end
		end
	end
	if def.reach then
		if not allReach then
			return false, "Lights go inside your realm or right beside a road."
		end
	elseif not allRealm then
		return false, "Outside your realm. Raise the Heartflame to build farther out."
	end
	if def.needsWater and not wet then
		return false, "A Fishing Hut has to touch the pond."
	end
	return true, nil
end

function PlotSim:canPlace(type_: string, x: number, z: number, rot: number): (boolean, string?)
	local def = B[type_]
	if not def or def.fixed then
		return false, "You can't build that."
	end
	if self.profile.level < def.level then
		return false, `Unlocks at level {def.level}.`
	end
	if def.surface then
		return self:canPaint(x, z)
	end
	local limit = self:limitOf(type_)
	if limit and self:count(type_) >= limit then
		return false, `Limit reached ({limit}). Level up to build more.`
	end
	local ok, reason = self:fits(type_, x, z, rot, 0)
	if not ok then
		return false, reason
	end
	local gold, lumen = self:costOf(type_)
	if self.profile.gold < gold then
		return false, `You need {gold} gold.`
	end
	if lumen > 0 and self.profile.lumen < lumen then
		return false, `You need {lumen} Lumen.`
	end
	return true, nil
end

function PlotSim:canPaint(x: number, z: number): (boolean, string?)
	if not inBounds(x, z) then
		return false, "Off your land."
	end
	local i = idx(x, z)
	local t = self.terrain[i]
	if t == T.ROAD then
		return false, "The road is already here."
	end
	if t ~= T.OPEN then
		return false, "You can't pave that."
	end
	if self.surface[i] == 1 then
		return false, "Already a path."
	end
	local o = self:objectAt(x, z)
	if o and not B[o.type].walkable then
		return false, "Something is in the way."
	end
	if not self:inRealm(x, z) then
		local joined = false
		for _, n in Grid.N4 do
			if self:isPath(x + n[1], z + n[2]) then
				joined = true
				break
			end
		end
		if not joined then
			return false, "Outside the realm, a path must join another path."
		end
	end
	if self.profile.gold < B.path.cost then
		return false, "You need 2 gold."
	end
	return true, nil
end

local function clampVariant(def, variant: number?): number
	local n = def.variants or 1
	return math.floor(variant or 0) % n
end

function PlotSim:initObj(o)
	local def = B[o.type]
	if def.stall then
		o.level = o.level or 1
		o.goods = o.goods or "harvest"
		o.queue = {}
		o.progress = 0
		o.sold = 0
	end
	if def.produce or def.convert then
		o.timer = self.rng.range(0, 4)
	end
	if def.tendable then
		o.ripe = false
		o.ripeTimer = self.rng.range(0, Config.TEND_INTERVAL * 0.6)
	end
	if def.snuffable then
		o.snuffed = false
	end
	if def.tower then
		o.cooldown = 0
	end
end

-- Places a building. opts.free skips the cost; opts.fixed skips every rule (starting layout, loading).
function PlotSim:place(type_: string, x: number, z: number, rot: number?, variant: number?, opts)
	opts = opts or {}
	local def = B[type_]
	if not def then
		return nil, "Unknown building."
	end
	local r = math.floor(rot or 0) % 4
	if def.surface then
		local ok, reason = self:paint(x, z, opts.free)
		if ok then
			return { type = "path", x = x, z = z }, nil
		end
		return nil, reason
	end
	if not opts.fixed then
		local ok, reason = self:canPlace(type_, x, z, r)
		if not ok then
			return nil, reason
		end
	end
	local gold, lumen = self:costOf(type_)
	if opts.free or opts.fixed then
		gold, lumen = 0, 0
	end
	self.profile.gold -= gold
	self.profile.lumen -= lumen
	local w, d = self:size(type_, r)
	local o = { id = self.nextId, type = type_, x = x, z = z, rot = r, w = w, d = d, variant = clampVariant(def, variant), paid = gold, paidLumen = lumen }
	self.nextId += 1
	self:initObj(o)
	self:stamp(o, o.id)
	self.objects[o.id] = o
	self:changed()
	if not opts.fixed then
		self:emit({ k = "placed", obj = o.id, type = type_, gold = gold })
	end
	return o, nil
end

function PlotSim:paint(x: number, z: number, free: boolean?): (boolean, string?)
	local ok, reason = self:canPaint(x, z)
	if not ok and not (free and reason == "You need 2 gold.") then
		return false, reason
	end
	if not free then
		self.profile.gold -= B.path.cost
	end
	self.surface[idx(x, z)] = 1
	self:changed()
	if not free then
		self:emit({ k = "painted", x = x, z = z })
	end
	return true, nil
end

function PlotSim:erase(x: number, z: number): (boolean, string?)
	if not inBounds(x, z) or self.surface[idx(x, z)] ~= 1 then
		return false, "No path there."
	end
	self.surface[idx(x, z)] = 0
	self.profile.gold += 1
	self:changed()
	return true, nil
end

function PlotSim:beds(): number
	local n = 0
	for _, o in self.objects do
		n += B[o.type].beds or 0
	end
	return n
end

function PlotSim:freeBeds(): number
	return math.max(0, self:beds() - #self.settlers)
end

function PlotSim:storeCap(): number
	local cap = Config.STORE_CAP_BASE
	for _, o in self.objects do
		cap += B[o.type].storage or 0
	end
	return cap
end

function PlotSim:remove(id: number): (boolean, string?, number?)
	local o = self.objects[id]
	if not o then
		return false, "Nothing there.", nil
	end
	local def = B[o.type]
	if def.fixed then
		return false, "The Heartflame stays.", nil
	end
	if def.beds and self:beds() - def.beds < #self.settlers then
		return false, "Someone sleeps here. Build another home first.", nil
	end
	self:stamp(o, 0)
	self.objects[id] = nil
	local refund = math.floor((o.paid or 0) * Config.REFUND)
	if o.level and o.level > 1 then
		for l = 2, o.level do
			refund += math.floor(Catalog.StallLevels[l].cost * Config.REFUND)
		end
	end
	local lumenBack = math.floor((o.paidLumen or 0) * Config.REFUND)
	self.profile.gold += refund
	self.profile.lumen += lumenBack
	self:changed()
	self:emit({ k = "removed", obj = id, type = o.type, refund = refund })
	return true, nil, refund
end

function PlotSim:move(id: number, x: number, z: number, rot: number): (boolean, string?)
	local o = self.objects[id]
	if not o or B[o.type].fixed then
		return false, "That can't be moved."
	end
	local r = math.floor(rot) % 4
	local ok, reason = self:fits(o.type, x, z, r, id)
	if not ok then
		return false, reason
	end
	self:stamp(o, 0)
	o.x, o.z, o.rot = x, z, r
	o.w, o.d = self:size(o.type, r)
	self:stamp(o, id)
	if o.queue then
		o.queue = {}
	end
	self:changed()
	self:emit({ k = "moved", obj = id })
	return true, nil
end

function PlotSim:setVariant(id: number, variant: number): boolean
	local o = self.objects[id]
	if not o then
		return false
	end
	o.variant = clampVariant(B[o.type], variant)
	self:changed(false)
	self:emit({ k = "restyled", obj = id })
	return true
end

function PlotSim:setGoods(id: number, goods: string): (boolean, string?)
	local o = self.objects[id]
	local g = Catalog.Goods[goods]
	if not o or not B[o.type].stall or not g then
		return false, "Not a stall."
	end
	if self.profile.level < g.level then
		return false, `{g.name} unlocks at level {g.level}.`
	end
	o.goods = goods
	o.queue = {}
	o.progress = 0
	self:changed(false)
	self:emit({ k = "restyled", obj = id })
	return true, nil
end

function PlotSim:upgradeStall(id: number): (boolean, string?)
	local o = self.objects[id]
	if not o or not B[o.type].stall then
		return false, "Not a stall."
	end
	local nxt = Catalog.StallLevels[o.level + 1]
	if not nxt then
		return false, "This stall is at its best."
	end
	if self.profile.gold < nxt.cost then
		return false, `You need {nxt.cost} gold.`
	end
	self.profile.gold -= nxt.cost
	o.level += 1
	self:changed(false)
	self:emit({ k = "upgraded", obj = id, level = o.level })
	return true, nil
end

function PlotSim:canRaiseHeart(): (boolean, string?)
	local nxt = Catalog.Heartflame[self.tier + 1]
	if not nxt then
		return false, "The Heartflame burns at its greatest."
	end
	if self.profile.level < nxt.level then
		return false, `Reach level {nxt.level} first.`
	end
	if self.profile.gold < nxt.gold then
		return false, `You need {nxt.gold} gold.`
	end
	if self.profile.lumen < nxt.lumen then
		return false, `You need {nxt.lumen} Lumen.`
	end
	return true, nil
end

function PlotSim:raiseHeart(): (boolean, string?)
	local ok, reason = self:canRaiseHeart()
	if not ok then
		return false, reason
	end
	local nxt = Catalog.Heartflame[self.tier + 1]
	self.profile.gold -= nxt.gold
	self.profile.lumen -= nxt.lumen
	self.tier += 1
	self.terrain = Grid.makeTerrain(nxt.radius)
	self:changed()
	self:emit({ k = "tier", tier = self.tier })
	return true, nil
end

-- ─── residents and work ────────────────────────────────────────────────────
function PlotSim:assignJobs()
	local jobs = self:list(function(o)
		return B[o.type].worker == true
	end)
	local homes = self:list(function(o)
		return (B[o.type].beds or 0) > 0
	end)
	for _, o in jobs do
		o.worker = nil
	end
	local h, used = 1, 0
	for i, s in self.settlers do
		local job = jobs[i]
		s.job = job and job.id or nil
		if job then
			job.worker = s.name
		end
		while homes[h] and used >= (B[homes[h].type].beds or 0) do
			h += 1
			used = 0
		end
		s.home = homes[h] and homes[h].id or nil
		used += 1
	end
end

-- ─── light and the Veil ────────────────────────────────────────────────────
function PlotSim:lightSources()
	local out = {}
	for _, o in self.objects do
		local def = B[o.type]
		if o.snuffed then
			continue
		end
		if o.type == "heartflame" then
			table.insert(out, { o.x + 1, o.z + 1, Catalog.Heartflame[self.tier].light })
		elseif def.lights then
			for _, b in def.lights do
				local lx, lz = self:rotLocal(o, b[1], b[2])
				table.insert(out, { lx, lz, b[3] })
			end
		elseif def.light then
			local cx, cz = self:objCentre(o)
			table.insert(out, { cx, cz, def.light })
		end
	end
	return out
end

function PlotSim:staticLight()
	local L = self.cache.light
	if L then
		return L
	end
	L = table.create(W * H, 0)
	for _, s in self:lightSources() do
		local sx, sz, r = s[1], s[2], s[3]
		for z = math.max(0, math.floor(sz - r)), math.min(H - 1, math.floor(sz + r)) do
			for x = math.max(0, math.floor(sx - r)), math.min(W - 1, math.floor(sx + r)) do
				local dx, dz = x + 0.5 - sx, z + 0.5 - sz
				local v = 1 - math.sqrt(dx * dx + dz * dz) / r
				local i = idx(x, z)
				if v > L[i] then
					L[i] = v
				end
			end
		end
	end
	self.cache.light = L
	return L
end

-- Light at a tile right now, including the Sovereign's staff and lantern-carrying visitors.
function PlotSim:lightAt(x: number, z: number): number
	if not inBounds(x, z) then
		return 1 -- the Royal Avenue is always lit
	end
	local l = self:staticLight()[idx(x, z)]
	local cx, cz = x + 0.5, z + 0.5
	for _, p in self.players do
		local dx, dz = cx - p.x, cz - p.z
		local v = 1 - math.sqrt(dx * dx + dz * dz) / PLAYER_LIGHT
		if v > l then
			l = v
		end
	end
	for _, v in self.visitors do
		local lantern = KINDS[v.kind].lantern
		if lantern then
			local dx, dz = cx - v.x, cz - v.z
			local f = 1 - math.sqrt(dx * dx + dz * dz) / lantern
			if f > l then
				l = f
			end
		end
	end
	return l
end

function PlotSim:towers()
	local t = self.cache.towers
	if not t then
		t = self:list(function(o)
			return B[o.type].tower == true
		end)
		self.cache.towers = t
	end
	return t
end

-- Gloomlings can't enter the Heartflame's inner glow or a Lumen Tower's.
function PlotSim:sanctuary(px: number, pz: number): boolean
	local r = Catalog.Heartflame[self.tier].light * 0.62
	local dx, dz = px - Grid.HEART_X, pz - Grid.HEART_Z
	if dx * dx + dz * dz < r * r then
		return true
	end
	for _, o in self:towers() do
		local cx, cz = self:objCentre(o)
		local ex, ez = px - cx, pz - cz
		if ex * ex + ez * ez < 2.2 * 2.2 then
			return true
		end
	end
	return false
end

function PlotSim:snuffables()
	local s = self.cache.snuffables
	if not s then
		s = self:list(function(o)
			return B[o.type].snuffable == true
		end)
		self.cache.snuffables = s
	end
	return s
end

-- ─── paths ─────────────────────────────────────────────────────────────────
function PlotSim:findPath(sx: number, sz: number, gx: number, gz: number, walkable)
	if not inBounds(sx, sz) or not inBounds(gx, gz) then
		return nil
	end
	local start, goal = idx(sx, sz), idx(gx, gz)
	local prev = table.create(W * H, -1)
	prev[start] = start
	local queue = { start }
	local head = 1
	while head <= #queue do
		local cur = queue[head]
		head += 1
		if cur == goal then
			break
		end
		local cx, cz = Grid.fromIdx(cur)
		for _, n in Grid.N4 do
			local nx, nz = cx + n[1], cz + n[2]
			if inBounds(nx, nz) then
				local ni = idx(nx, nz)
				if prev[ni] == -1 and (ni == goal or walkable(nx, nz)) then
					prev[ni] = cur
					table.insert(queue, ni)
				end
			end
		end
	end
	if prev[goal] == -1 then
		return nil
	end
	local rev = {}
	local cur = goal
	while cur ~= start do
		local x, z = Grid.fromIdx(cur)
		table.insert(rev, { x, z })
		cur = prev[cur]
	end
	table.insert(rev, { sx, sz })
	local path = {}
	for i = #rev, 1, -1 do
		table.insert(path, rev[i])
	end
	return path
end

function PlotSim:walkV()
	local f = self.cache.walkV
	if not f then
		f = function(x, z)
			return self:visitorWalkable(x, z)
		end
		self.cache.walkV = f
	end
	return f
end

function PlotSim:walkG()
	local f = self.cache.walkG
	if not f then
		f = function(x, z)
			return self:groundWalkable(x, z)
		end
		self.cache.walkG = f
	end
	return f
end

function PlotSim:entranceDist()
	local dist = self.cache.entrance
	if dist then
		return dist
	end
	dist = table.create(W * H, -1)
	local e = Grid.ENTRANCE
	local start = idx(e.x, e.z)
	dist[start] = 0
	local queue = { start }
	local head = 1
	while head <= #queue do
		local cur = queue[head]
		head += 1
		local cx, cz = Grid.fromIdx(cur)
		for _, n in Grid.N4 do
			local nx, nz = cx + n[1], cz + n[2]
			if inBounds(nx, nz) and self:visitorWalkable(nx, nz) then
				local ni = idx(nx, nz)
				if dist[ni] == -1 then
					dist[ni] = dist[cur] + 1
					table.insert(queue, ni)
				end
			end
		end
	end
	self.cache.entrance = dist
	return dist
end

function PlotSim:reachable(x: number, z: number): boolean
	return inBounds(x, z) and self:entranceDist()[idx(x, z)] >= 0
end

-- Where customers stand to buy from a stall, or nil if no reachable path runs past its counter.
function PlotSim:serviceTile(o)
	self.cache.service = self.cache.service or {}
	local c = self.cache.service[o.id]
	if c ~= nil then
		return c or nil
	end
	local found = false
	for _, t in self:frontTiles(o) do
		if self:visitorWalkable(t[1], t[2]) and self:reachable(t[1], t[2]) then
			found = t
			break
		end
	end
	self.cache.service[o.id] = found
	return found or nil
end

function PlotSim:restTile(o)
	self.cache.rest = self.cache.rest or {}
	local c = self.cache.rest[o.id]
	if c ~= nil then
		return c or nil
	end
	local found = false
	for _, t in self:neighbourTiles(o) do
		if self:visitorWalkable(t[1], t[2]) and self:reachable(t[1], t[2]) then
			found = t
			break
		end
	end
	self.cache.rest[o.id] = found
	return found or nil
end

-- The walk in from the entrance to the plaza, and how much of it is lit at night (0..100).
function PlotSim:route()
	local r = self.cache.route
	if r then
		return r
	end
	r = self:findPath(Grid.ENTRANCE.x, Grid.ENTRANCE.z, Grid.PLAZA.x, Grid.PLAZA.z, self:walkV()) or {}
	self.cache.route = r
	return r
end

function PlotSim:roadLit(): number
	local route = self:route()
	if #route == 0 then
		return 0
	end
	local L = self:staticLight()
	local lit = 0
	for _, t in route do
		if L[idx(t[1], t[2])] >= LIT then
			lit += 1
		end
	end
	return math.floor(lit / #route * 100 + 0.5)
end

-- ─── appeal ────────────────────────────────────────────────────────────────
function PlotSim:decorMap()
	local D = self.cache.decor
	if D then
		return D
	end
	D = table.create(W * H, 0)
	for _, o in self.objects do
		local ap = B[o.type].appeal
		if ap then
			local a, r = ap[1], ap[2]
			local cx, cz = self:objCentre(o)
			for z = math.max(0, math.floor(cz - r - 1)), math.min(H - 1, math.floor(cz + r + 1)) do
				for x = math.max(0, math.floor(cx - r - 1)), math.min(W - 1, math.floor(cx + r + 1)) do
					local dx, dz = x + 0.5 - cx, z + 0.5 - cz
					local f = 1 - math.sqrt(dx * dx + dz * dz) / r
					if f > 0 then
						local i = idx(x, z)
						D[i] = math.min(10, D[i] + a * f)
					end
				end
			end
		end
	end
	self.cache.decor = D
	return D
end

function PlotSim:appeal()
	local c = self.cache.appeal
	if c then
		return c
	end
	local D = self:decorMap()
	local L = self:staticLight()
	local decorSum, decorN, lit, walk = 0, 0, 0, 0
	for z = 0, H - 1 do
		for x = 0, W - 1 do
			if self:visitorWalkable(x, z) and self:reachable(x, z) then
				walk += 1
				local i = idx(x, z)
				if L[i] >= LIT then
					lit += 1
				end
				if self:inRealm(x, z) then
					decorSum += D[i]
					decorN += 1
				end
			end
		end
	end
	local kinds = {}
	local nKinds = 0
	for _, o in self.objects do
		local def = B[o.type]
		if def.appeal and not kinds[o.type] then
			kinds[o.type] = true
			nKinds += 1
		end
	end
	local decor = decorN > 0 and (decorSum / decorN) * 9 or 0
	local variety = math.min(8, nKinds) * 2.5
	local light = walk > 0 and (lit / walk) * 25 or 0
	local total = math.floor(clamp(decor + variety + light, 0, 100) + 0.5)
	c = { total = total, decor = math.floor(decor + 0.5), variety = math.floor(variety + 0.5), light = math.floor(light + 0.5) }
	self.cache.appeal = c
	return c
end

-- ─── the starting layout (a gift from Bram) ─────────────────────────────────
function PlotSim:placeHeart()
	local h = Grid.HEART_TILE
	if not self:objectAt(h.x, h.z) then
		self:place("heartflame", h.x, h.z, 0, 0, { fixed = true })
	end
end

function PlotSim:layStarter()
	self:placeHeart()
	local put = function(type_, x, z, rot, variant)
		local o = self:place(type_, x, z, rot, variant, { fixed = true })
		if o then
			o.paid = math.floor(B[type_].cost * 0.5)
		end
		return o
	end
	put("stall", 16, 17, 3, 0)
	put("field_turnip", 9, 12, 0, 0)
	put("tent", 18, 16, 0, 0)
	put("lamp", 13, 17, 0, 0)
	put("bench", 16, 15 + 1, 0, 0)
	put("flowers", 12, 16, 0, 1)
	self.stock.harvest = Config.START_STOCK.harvest
	self:changed()
end

-- ─── saving ────────────────────────────────────────────────────────────────
function PlotSim:serialize()
	local objs = {}
	for _, o in self:list(function(o)
		return o.type ~= "heartflame"
	end) do
		table.insert(objs, { o.type, o.x, o.z, o.rot, o.variant, o.paid or 0, o.level or 0, o.goods or "", o.paidLumen or 0 })
	end
	local paths = {}
	for i = 1, W * H do
		if self.surface[i] == 1 then
			table.insert(paths, i)
		end
	end
	local settlers = {}
	for _, s in self.settlers do
		table.insert(settlers, { s.name, s.kind })
	end
	return {
		v = 1,
		tier = self.tier,
		objs = objs,
		paths = paths,
		stock = { harvest = self.stock.harvest, catch = self.stock.catch, grain = self.stock.grain, stew = self.stock.stew },
		settlers = settlers,
	}
end

function PlotSim:load(data)
	if type(data) ~= "table" or type(data.objs) ~= "table" then
		self:layStarter()
		return
	end
	self.tier = clamp(math.floor(tonumber(data.tier) or 1), 1, #Catalog.Heartflame)
	self.terrain = Grid.makeTerrain(self:radius())
	self:placeHeart()
	if type(data.paths) == "table" then
		for _, i in data.paths do
			if type(i) == "number" and i >= 1 and i <= W * H and self.terrain[i] == T.OPEN then
				self.surface[i] = 1
			end
		end
	end
	for _, rec in data.objs do
		if type(rec) ~= "table" then
			continue
		end
		local type_, x, z, rot, variant = rec[1], tonumber(rec[2]), tonumber(rec[3]), tonumber(rec[4]) or 0, tonumber(rec[5]) or 0
		local def = type(type_) == "string" and B[type_]
		if not def or def.fixed or def.surface or not x or not z then
			continue
		end
		if not self:fits(type_, x, z, rot % 4, 0) then
			continue
		end
		local o = self:place(type_, x, z, rot, variant, { fixed = true })
		if o then
			o.paid = tonumber(rec[6]) or 0
			o.paidLumen = tonumber(rec[9]) or 0
			if def.stall then
				o.level = clamp(math.floor(tonumber(rec[7]) or 1), 1, #Catalog.StallLevels)
				local g = rec[8]
				o.goods = (type(g) == "string" and Catalog.Goods[g]) and g or "harvest"
			end
		end
	end
	local cap = self:storeCap()
	for g in Catalog.Goods do
		local n = type(data.stock) == "table" and tonumber(data.stock[g]) or 0
		self.stock[g] = clamp(math.floor(n or 0), 0, cap)
	end
	if type(data.settlers) == "table" then
		for _, s in data.settlers do
			if type(s) == "table" and type(s[1]) == "string" and #self.settlers < self:beds() then
				self:addSettler(s[1], KINDS[s[2]] and s[2] or "traveler", true)
			end
		end
	end
	self:changed()
end

-- ─── production ────────────────────────────────────────────────────────────
function PlotSim:addStock(goods: string, n: number, o): number
	local cap = self:storeCap()
	local before = self.stock[goods] or 0
	local after = math.min(cap, before + n)
	self.stock[goods] = after
	if o and after > before then
		self:emit({ k = "produce", obj = o.id, goods = goods, n = after - before })
	end
	return after - before
end

function PlotSim:produceTick(dt: number)
	if self.clock.phase == "night" then
		return -- fields sleep at night; sell what you stored by day
	end
	for _, o in self.objects do
		local def = B[o.type]
		if def.produce or def.convert then
			o.timer = (o.timer or 0) + dt * (o.worker and 2 or 1)
			local secs = def.seconds or 14
			if o.timer >= secs then
				o.timer -= secs
				if def.produce then
					for g, n in def.produce do
						self:addStock(g, n, o)
					end
				elseif def.convert then
					-- The cook leaves a few of each input for the stalls.
					local ok = true
					for g, n in def.convert.input do
						if (self.stock[g] or 0) < n + 6 then
							ok = false
						end
					end
					if ok then
						for g, n in def.convert.input do
							self.stock[g] -= n
						end
						for g, n in def.convert.output do
							self:addStock(g, n, o)
						end
					end
				end
			end
		end
		if def.tendable and not o.ripe then
			o.ripeTimer = (o.ripeTimer or 0) + dt
			if o.ripeTimer >= Config.TEND_INTERVAL then
				o.ripe = true
				o.ripeTimer = 0
				self:emit({ k = "ripe", obj = o.id })
			end
		end
	end
end

function PlotSim:tend(id: number, by: number?): (boolean, string?)
	local o = self.objects[id]
	if not o or not B[o.type].tendable then
		return false, "Nothing to tend."
	end
	if not o.ripe then
		return false, "Not ripe yet."
	end
	o.ripe = false
	o.ripeTimer = 0
	local got = 0
	for g, _ in B[o.type].produce do
		got += self:addStock(g, 3, nil)
	end
	self:emit({ k = "tend", obj = id, by = by, n = got })
	return true, nil
end

function PlotSim:relight(id: number, by: number?): (boolean, string?)
	local o = self.objects[id]
	if not o or not o.snuffed then
		return false, "It's already lit."
	end
	o.snuffed = false
	self:changed(false)
	self:emit({ k = "relight", obj = id, by = by })
	return true, nil
end

-- ─── stalls ────────────────────────────────────────────────────────────────
function PlotSim:stalls()
	local s = self.cache.stalls
	if not s then
		s = self:list(function(o)
			return B[o.type].stall == true
		end)
		self.cache.stalls = s
	end
	return s
end

function PlotSim:sellers(goods: string)
	local out = {}
	for _, s in self:stalls() do
		if s.goods == goods and self:serviceTile(s) then
			table.insert(out, s)
		end
	end
	return out
end

-- The player standing closest to a stall's counter, if anyone is close enough to serve.
function PlotSim:helperAt(s): number?
	local tile = self:serviceTile(s)
	if not tile then
		return nil
	end
	local best, bestD = nil, SERVE_TILES
	for _, p in self.players do
		local dx, dz = p.x - (tile[1] + 0.5), p.z - (tile[2] + 0.5)
		local d = math.sqrt(dx * dx + dz * dz)
		if d <= bestD then
			best, bestD = p.id, d
		end
	end
	return best
end

function PlotSim:stallTick(dt: number)
	for _, s in self:stalls() do
		if #s.queue == 0 then
			s.progress = 0
			s.helper = nil
			continue
		end
		local helper = self:helperAt(s)
		s.helper = helper
		s.progress += dt * (helper and 2 or 1)
		if s.progress >= Catalog.StallLevels[s.level].service then
			s.progress = 0
			local vid = table.remove(s.queue, 1)
			local v = self:visitorById(vid)
			if v then
				self:sell(s, v, helper)
			end
		end
	end
end

function PlotSim:visitorById(id: number)
	for _, v in self.visitors do
		if v.id == id then
			return v
		end
	end
	return nil
end

function PlotSim:priceOf(s, v): number
	local g = Catalog.Goods[s.goods]
	local mult = Catalog.StallLevels[s.level].mult
	local night = self.clock.phase == "night" and Config.NIGHT_PRICE_MULT or 1
	local pay = KINDS[v.kind].pay or 1
	return math.max(1, math.floor(g.price * mult * night * math.min(pay, 1.5) + 0.5))
end

function PlotSim:sell(s, v, helper: number?)
	local g = s.goods
	v.stallId = 0
	v.state = "buy"
	for i, w in v.wants do
		if w == g then
			table.remove(v.wants, i)
			break
		end
	end
	if (self.stock[g] or 0) <= 0 then
		v.sat -= 8
		if self.night then
			self.night.soldOut += 1
		end
		self:sayPick(v, LINES.soldOut, 0.8)
		return self:planNext(v)
	end
	self.stock[g] -= 1
	local price = self:priceOf(s, v)
	self.profile.gold += price
	s.sold += 1
	v.bought += 1
	v.sat += helper and 18 or 13
	if self.night then
		self.night.sold[g] = (self.night.sold[g] or 0) + 1
		self.night.revenue += price
	end
	local def = KINDS[v.kind]
	if helper then
		v.served += 1
		self:sayPick(v, LINES.served, 0.8)
	elseif def.creature then
		self:sayPick(v, LINES.creature[v.kind] or LINES.strollMid, 0.4)
	else
		self:sayPick(v, LINES.buy[g], 0.4)
	end
	self:emit({ k = "sale", obj = s.id, goods = g, price = price, helper = helper })
	return self:planNext(v)
end

-- ─── visitors ──────────────────────────────────────────────────────────────
function PlotSim:maxVisitors(): number
	return Config.MAX_VISITORS + math.floor(self.profile.level / 2)
end

function PlotSim:spawnInterval(): number
	local ap = self:appeal().total
	local base = clamp(15 - ap * 0.1 - (self.profile.level - 1) * 0.25, 4, 15)
	local phase = self.clock.phase
	if phase == "night" then
		return base * 0.6
	elseif phase == "dusk" then
		return base * 0.8
	end
	return base
end

function PlotSim:pickKind(): string
	local night = self.clock.phase == "night"
	local items = {}
	for _, k in Catalog.VisitorOrder do
		local def = KINDS[k]
		if def.minLevel <= self.profile.level and (night or not def.nightOnly) then
			local w = def.weight
			if night and def.nightWeight then
				w *= def.nightWeight
			end
			table.insert(items, { k, w })
		end
	end
	return self.rng.weighted(items)
end

function PlotSim:spawnTick(dt: number)
	self.spawnTimer -= dt
	if self.spawnTimer > 0 then
		return
	end
	self.spawnTimer = self:spawnInterval() * self.rng.range(0.7, 1.3)
	if #self.visitors >= self:maxVisitors() or #self:route() == 0 then
		return
	end
	self:spawnVisitor()
end

function PlotSim:spawnVisitor(kind: string?)
	local rng = self.rng
	local k = kind or self:pickKind()
	local def = KINDS[k]
	local pool = {}
	for g, w in def.wants do
		if Catalog.Goods[g].level <= self.profile.level then
			table.insert(pool, { g, w })
		end
	end
	if #pool == 0 then
		table.insert(pool, { "harvest", 1 })
	end
	local nWants = rng.weighted({ { 1, 3 }, { 2, 4 }, { 3, 2 } })
	local wants = {}
	for _ = 1, nWants do
		local options = {}
		for _, it in pool do
			if not table.find(wants, it[1]) then
				table.insert(options, it)
			end
		end
		if #options == 0 then
			break
		end
		table.insert(wants, rng.weighted(options))
	end
	local name = def.name
	if not def.creature then
		local free = {}
		for _, n in Catalog.Names do
			if not self.usedNames[n] then
				table.insert(free, n)
			end
		end
		name = #free > 0 and rng.pick(free) or rng.pick(Catalog.Names)
	end
	local a = Grid.APPROACH
	local path = {}
	for _, t in a do
		table.insert(path, { t[1], t[2] })
	end
	table.insert(path, { Grid.ENTRANCE.x, Grid.ENTRANCE.z })
	local v = {
		id = self:newId(),
		kind = k,
		name = name,
		x = a[1][1] + 0.5,
		z = a[1][2] + 0.5,
		tx = a[1][1],
		tz = a[1][2],
		path = path,
		pi = 2,
		state = "enter",
		wants = wants,
		complained = {},
		sat = 55,
		fear = 0,
		speed = rng.range(1.45, 1.8),
		timer = 0,
		stallId = 0,
		warned = false,
		greeted = false,
		served = 0,
		bought = 0,
		seed = rng.int(0, 255),
		sayAt = -10,
		mood = 0,
	}
	table.insert(self.visitors, v)
	if self.night then
		self.night.visitors += 1
	end
	self:emit({ k = "visit", id = v.id, kind = k, name = name })
	return v
end

function PlotSim:say(v, text: string?)
	if not text or self.time - v.sayAt < 2.2 then
		return
	end
	v.sayAt = self.time
	self:emit({ k = "say", id = v.id, text = text })
end

function PlotSim:sayPick(v, list, p: number?)
	if list and #list > 0 and self.rng.chance(p or 1) then
		self:say(v, self.rng.pick(list))
	end
end

function PlotSim:creatureLines(v)
	return LINES.creature[v.kind] or { "..." }
end

-- Decide where to go next: a stall, a place to linger, or home.
function PlotSim:planNext(v)
	local creature = KINDS[v.kind].creature
	local best, bestD, bestG = nil, math.huge, nil
	for _, g in v.wants do
		if (self.stock[g] or 0) <= 0 then
			continue
		end
		for _, s in self:sellers(g) do
			local tile = self:serviceTile(s)
			local d = math.abs(tile[1] - v.tx) + math.abs(tile[2] - v.tz) + #s.queue * 3
			if d < bestD then
				best, bestD, bestG = s, d, g
			end
		end
	end
	if best then
		v.stallId = best.id
		v.goal = bestG
		return self:walkTo(v, self:serviceTile(best), "toStall")
	end
	-- Nothing to buy from here: walk up to the market first, then grumble about what's missing.
	if (v.state == "enter" or v.state == "arrive") and not self:inRealm(v.tx, v.tz) then
		return self:walkTo(v, { Grid.PLAZA.x, Grid.PLAZA.z }, "arrive")
	end
	for _, g in v.wants do
		if table.find(v.complained, g) then
			continue
		end
		table.insert(v.complained, g)
		if #self:sellers(g) == 0 then
			v.sat -= 4
			if self.night then
				self.night.missing[g] = (self.night.missing[g] or 0) + 1
			end
			if creature then
				self:sayPick(v, self:creatureLines(v), 0.5)
			else
				self:say(v, LINES.none[g])
			end
		else
			v.sat -= 6
			if self.night then
				self.night.soldOut += 1
			end
			self:sayPick(v, creature and self:creatureLines(v) or LINES.soldOut, 0.7)
		end
		self:emit({ k = "want", goods = g })
	end
	v.wants = {}
	if v.state == "enter" or v.state == "arrive" or v.state == "toStall" or v.state == "buy" then
		return self:planStroll(v)
	end
	return self:finishVisit(v)
end

function PlotSim:planStroll(v)
	local rng = self.rng
	local spots = {}
	for _, o in self.objects do
		if B[o.type].rest then
			local t = self:restTile(o)
			if t then
				table.insert(spots, t)
			end
		end
	end
	local tile = nil
	if #spots > 0 and rng.chance(0.7) then
		tile = rng.pick(spots)
	end
	if not tile then
		local D = self:decorMap()
		local options = {}
		for z = 0, H - 1 do
			for x = 0, W - 1 do
				if self:inRealm(x, z) and self:visitorWalkable(x, z) and self:reachable(x, z) then
					table.insert(options, { { x, z }, 1 + D[idx(x, z)] })
				end
			end
		end
		if #options > 0 then
			tile = rng.weighted(options)
		end
	end
	if not tile then
		return self:finishVisit(v)
	end
	return self:walkTo(v, tile, "stroll")
end

function PlotSim:walkTo(v, tile, state: string)
	if not inBounds(v.tx, v.tz) then
		return self:finishVisit(v)
	end
	local path = self:findPath(v.tx, v.tz, tile[1], tile[2], self:walkV())
	if not path then
		return self:finishVisit(v)
	end
	v.path = path
	v.pi = 2
	v.state = state
	if #path <= 1 then
		self:arrive(v)
	end
	return true
end

-- A path from where the visitor stands back out to the avenue.
function PlotSim:exitPath(v)
	local path
	if inBounds(v.tx, v.tz) then
		path = self:findPath(v.tx, v.tz, Grid.ENTRANCE.x, Grid.ENTRANCE.z, self:walkV())
	end
	path = path or { { v.tx, v.tz } }
	local a = Grid.APPROACH
	for i = #a, 1, -1 do
		if a[i][2] > path[#path][2] then
			table.insert(path, { a[i][1], a[i][2] })
		end
	end
	return path
end

function PlotSim:leaveQueue(v)
	local s = self.objects[v.stallId]
	if s and s.queue then
		local i = table.find(s.queue, v.id)
		if i then
			table.remove(s.queue, i)
			if i == 1 then
				s.progress = 0
			end
		end
	end
	v.stallId = 0
end

function PlotSim:freeHome()
	local homes = self:list(function(o)
		return (B[o.type].beds or 0) > 0
	end)
	local used = {}
	for _, s in self.settlers do
		if s.home then
			used[s.home] = (used[s.home] or 0) + 1
		end
	end
	for _, v in self.visitors do
		if v.state == "home" and v.homeId then
			used[v.homeId] = (used[v.homeId] or 0) + 1
		end
	end
	for _, o in homes do
		if (used[o.id] or 0) < B[o.type].beds then
			return o
		end
	end
	return nil
end

-- Leave for home. Happiness is settled here: tips, moving in, and the night's tally.
function PlotSim:finishVisit(v)
	local st = v.state
	if st == "leave" or st == "flee" or st == "gone" or st == "home" then
		return
	end
	if v.stallId ~= 0 then
		self:leaveQueue(v)
	end
	v.sat = clamp(v.sat - v.fear / 4, 0, 100)
	local n = self.night
	local def = KINDS[v.kind]
	if v.sat >= 70 then
		v.mood = 1
		if n then
			n.happy += 1
		end
		self:emit({ k = "happy", id = v.id, kind = v.kind })
		local night = self.clock.phase == "night" and 1.5 or 1
		local value = math.floor(self.rng.range(2, 5) * (1 + self:appeal().total / 100) * (def.pay or 1) * night + 0.5)
		self:spawnTip(v.x + self.rng.range(-0.3, 0.3), v.z + self.rng.range(-0.3, 0.3), value, v.kind == "goldbun")
		if def.settles and self.rng.chance(0.25) then
			local home = self:freeHome()
			if home then
				local t = self:restTile(home) or self:nearestGround(home)
				if t then
					self:sayPick(v, LINES.settle, 1)
					self.usedNames[v.name] = true
					v.homeId = home.id
					local path = self:findPath(v.tx, v.tz, t[1], t[2], self:walkG())
					if path then
						v.state = "home"
						v.path = path
						v.pi = 2
						return
					end
				end
				-- No way to walk there: they move in anyway and fade away toward their new home.
				self:addSettler(v.name, v.kind, false)
				v.state = "gone"
				return
			else
				self:emit({ k = "noBed", name = v.name })
				if n then
					n.noBed += 1
				end
			end
		end
	elseif v.sat >= 40 then
		v.mood = 0
		if n then
			n.content += 1
		end
	else
		v.mood = -1
		if n then
			n.unhappy += 1
		end
		self:emit({ k = "unhappy", id = v.id })
	end
	v.state = "leave"
	v.speed = math.max(v.speed, 1.7)
	v.path = self:exitPath(v)
	v.pi = 2
	self:emit({ k = "leave", id = v.id, sat = v.sat, mood = v.mood, bought = v.bought, kind = v.kind })
end

function PlotSim:nearestGround(o)
	for _, t in self:neighbourTiles(o) do
		if self:groundWalkable(t[1], t[2]) then
			return t
		end
	end
	return nil
end

function PlotSim:turnBack(v)
	if v.stallId ~= 0 then
		self:leaveQueue(v)
	end
	v.state = "flee"
	v.mood = -1
	v.speed = 2.6
	if self.night then
		self.night.fled += 1
	end
	self:emit({ k = "flee", id = v.id })
	self:sayPick(v, KINDS[v.kind].creature and self:creatureLines(v) or LINES.flee, 0.9)
	v.path = self:exitPath(v)
	v.pi = 2
end

function PlotSim:enterTile(v, x: number, z: number)
	v.tx, v.tz = x, z
	local def = KINDS[v.kind]
	local st = v.state
	if self.clock.night >= 0.5 and not def.lantern and not def.fearless and inBounds(x, z) and (st == "enter" or st == "arrive" or st == "toStall" or st == "leave") then
		if self:lightAt(x, z) >= LIT then
			v.fear = math.max(0, v.fear - 3)
		else
			v.fear += Config.FEAR_DARK_STEP
			if not v.warned and v.fear >= 18 then
				v.warned = true
				self:sayPick(v, def.creature and self:creatureLines(v) or LINES.dark, 0.7)
			end
			if v.fear >= Config.FEAR_TURN_BACK and st ~= "leave" then
				self:turnBack(v)
				return
			end
		end
	end
	if not v.greeted and inBounds(x, z) and self:inRealm(x, z) and st ~= "leave" and st ~= "flee" then
		v.greeted = true
		if v.fear == 0 and not def.creature and self.clock.night >= 0.5 then
			self:sayPick(v, LINES.arrive, 0.35)
		end
	end
end

function PlotSim:arrive(v)
	local st = v.state
	if st == "enter" then
		self:planNext(v)
	elseif st == "toStall" then
		local s = self.objects[v.stallId]
		if not s or not s.queue or not self:serviceTile(s) then
			v.stallId = 0
			self:planNext(v)
			return
		end
		table.insert(s.queue, v.id)
		v.state = "queue"
	elseif st == "stroll" then
		v.state = "linger"
		v.timer = self.rng.range(3.5, 7)
		local score = self:decorMap()[idx(v.tx, v.tz)] or 0
		v.sat += clamp((score - 1.5) * 3.5, -6, 14)
		if KINDS[v.kind].creature then
			self:sayPick(v, self:creatureLines(v), 0.6)
		elseif score >= 4 then
			self:sayPick(v, LINES.strollHigh, 0.7)
		elseif score >= 1.5 then
			self:sayPick(v, LINES.strollMid, 0.5)
		else
			self:sayPick(v, LINES.strollLow, 0.7)
		end
	elseif st == "arrive" then
		self:planNext(v)
	elseif st == "home" then
		self:addSettler(v.name, v.kind, false)
		v.state = "gone"
	elseif st == "leave" or st == "flee" then
		v.state = "gone"
	end
end

function PlotSim:updateQueued(v, dt: number)
	local s = self.objects[v.stallId]
	if not s or not s.queue then
		v.stallId = 0
		self:planNext(v)
		return
	end
	local pos = table.find(s.queue, v.id)
	local tile = self:serviceTile(s)
	if not pos or not tile then
		v.stallId = 0
		self:planNext(v)
		return
	end
	-- Stand in line, stretching back along the path away from the counter.
	local f = Grid.FRONT[s.rot]
	local tx = tile[1] + 0.5 + f[1] * QUEUE_GAP * (pos - 1)
	local tz = tile[2] + 0.5 + f[2] * QUEUE_GAP * (pos - 1)
	local k = math.min(1, dt * 5)
	v.x += (tx - v.x) * k
	v.z += (tz - v.z) * k
end

function PlotSim:updateVisitor(v, dt: number)
	local st = v.state
	if st == "queue" then
		self:updateQueued(v, dt)
		return
	elseif st == "linger" then
		v.timer -= dt
		if v.timer <= 0 then
			self:finishVisit(v)
		end
		return
	elseif st == "gone" then
		return
	end
	local step = v.speed * dt
	while step > 0 and v.pi <= #v.path do
		local t = v.path[v.pi]
		local dx, dz = t[1] + 0.5 - v.x, t[2] + 0.5 - v.z
		local d = math.sqrt(dx * dx + dz * dz)
		if d <= step then
			v.x, v.z = t[1] + 0.5, t[2] + 0.5
			step -= d
			v.pi += 1
			local before = v.state
			self:enterTile(v, t[1], t[2])
			if v.state ~= before then
				break -- turned back: the path was replaced
			end
		else
			v.x += dx / d * step
			v.z += dz / d * step
			step = 0
		end
	end
	if v.pi > #v.path and v.state ~= "queue" and v.state ~= "linger" and v.state ~= "gone" then
		self:arrive(v)
	end
end

-- ─── tips ──────────────────────────────────────────────────────────────────
function PlotSim:spawnTip(x: number, z: number, value: number, golden: boolean?)
	local tip = { id = self:newId(), x = x, z = z, value = value, age = 0, golden = golden == true }
	table.insert(self.tips, tip)
	self:emit({ k = "tip", id = tip.id, x = x, z = z, value = value, golden = tip.golden })
	return tip
end

function PlotSim:collectTip(id: number, by: number?): number
	for i, tip in self.tips do
		if tip.id == id then
			table.remove(self.tips, i)
			self.profile.gold += tip.value
			if self.night then
				self.night.tips += tip.value
			end
			self:emit({ k = "tipGone", id = id, by = by, value = tip.value, x = tip.x, z = tip.z })
			return tip.value
		end
	end
	return 0
end

function PlotSim:tipTick(dt: number)
	for i = #self.tips, 1, -1 do
		local tip = self.tips[i]
		tip.age += dt
		if tip.age >= TIP_LIFE then
			-- Flicker gathers what you missed, but only half of it.
			table.remove(self.tips, i)
			local half = math.floor(tip.value / 2)
			self.profile.gold += half
			self:emit({ k = "tipGone", id = tip.id, by = 0, value = half, x = tip.x, z = tip.z })
		end
	end
	for _, p in self.players do
		for i = #self.tips, 1, -1 do
			local tip = self.tips[i]
			local dx, dz = tip.x - p.x, tip.z - p.z
			if dx * dx + dz * dz <= TIP_TILES * TIP_TILES then
				self:collectTip(tip.id, p.id)
			end
		end
	end
end

-- ─── settlers ──────────────────────────────────────────────────────────────
function PlotSim:addSettler(name: string, kind: string, quiet: boolean)
	self.usedNames[name] = true
	local s: any = { id = self:newId(), name = name, kind = kind, x = 0, z = 0, tx = 0, tz = 0, path = {}, pi = 1, timer = 0, inside = true, seed = #self.settlers, home = nil, job = nil }
	table.insert(self.settlers, s)
	self:assignJobs()
	local home = s.home and self.objects[s.home]
	if home then
		local t = self:nearestGround(home)
		if t then
			s.x, s.z, s.tx, s.tz = t[1] + 0.5, t[2] + 0.5, t[1], t[2]
		end
	end
	if not quiet then
		if self.night then
			table.insert(self.night.settled, name)
		end
		self:emit({ k = "settle", name = name, kind = kind })
	end
	return s
end

function PlotSim:settlerTick(dt: number)
	local night = self.clock.phase == "night"
	for _, s in self.settlers do
		local anchor = (not night and s.job and self.objects[s.job]) or (s.home and self.objects[s.home])
		if not anchor then
			s.inside = true
			continue
		end
		if s.pi <= #s.path then
			local step = 1.2 * dt
			while step > 0 and s.pi <= #s.path do
				local t = s.path[s.pi]
				local dx, dz = t[1] + 0.5 - s.x, t[2] + 0.5 - s.z
				local d = math.sqrt(dx * dx + dz * dz)
				if d <= step then
					s.x, s.z, s.tx, s.tz = t[1] + 0.5, t[2] + 0.5, t[1], t[2]
					step -= d
					s.pi += 1
				else
					s.x += dx / d * step
					s.z += dz / d * step
					step = 0
				end
			end
			continue
		end
		s.timer -= dt
		if s.timer > 0 then
			continue
		end
		s.timer = self.rng.range(3, 8)
		local atHome = night and s.home and anchor.id == s.home
		local options = self:neighbourTiles(anchor)
		local goal = self.rng.pick(options)
		if atHome then
			local t = self:nearestGround(anchor)
			goal = t or goal
		end
		if goal and self:groundWalkable(goal[1], goal[2]) and inBounds(s.tx, s.tz) then
			local path = self:findPath(s.tx, s.tz, goal[1], goal[2], self:walkG())
			if path and #path > 1 then
				s.path = path
				s.pi = 2
				s.inside = false
			elseif atHome then
				s.inside = true
			end
		end
		if not night then
			s.inside = false
		end
	end
end

-- ─── Gloomlings ────────────────────────────────────────────────────────────
function PlotSim:gloomMax(): number
	return math.min(Config.GLOOM_MAX + self.profile.level // 5, 9)
end

function PlotSim:spawnGloom(surge: boolean?)
	local rng = self.rng
	local best, bestScore = nil, -math.huge
	local L = self:staticLight()
	for _ = 1, 40 do
		local x, z = rng.int(0, W - 1), rng.int(0, H - 1)
		local px, pz = x + 0.5, z + 0.5
		if L[idx(x, z)] >= LIT or self:sanctuary(px, pz) then
			continue
		end
		local near = math.huge
		for _, p in self.players do
			near = math.min(near, math.sqrt((p.x - px) ^ 2 + (p.z - pz) ^ 2))
		end
		if near < 5 then
			continue
		end
		local toLight = 30
		for _, o in self:snuffables() do
			if not o.snuffed then
				local cx, cz = self:objCentre(o)
				toLight = math.min(toLight, math.sqrt((cx - px) ^ 2 + (cz - pz) ^ 2))
			end
		end
		local score = -toLight + rng.range(0, 8)
		if score > bestScore then
			best, bestScore = { px, pz }, score
		end
	end
	if not best then
		return nil
	end
	local hp = Config.GLOOM_HP + (self.profile.level - 1) * 2 + (surge and 12 or 0)
	local g = {
		id = self:newId(),
		x = best[1],
		z = best[2],
		hp = hp,
		maxHp = hp,
		speed = Config.GLOOM_SPEED * rng.range(0.85, 1.15),
		target = nil,
		snuff = 0,
		touchCd = 0,
		retarget = 0,
		surge = surge == true,
		chasing = false,
		seed = rng.int(0, 255),
	}
	table.insert(self.gloom, g)
	self:emit({ k = "gloomSpawn", id = g.id, x = g.x, z = g.z, surge = g.surge })
	return g
end

function PlotSim:pickGloomTarget(g)
	local best, bestD = nil, math.huge
	for _, o in self:snuffables() do
		if not o.snuffed then
			local cx, cz = self:objCentre(o)
			if not self:sanctuary(cx, cz) then
				local d = math.sqrt((cx - g.x) ^ 2 + (cz - g.z) ^ 2)
				if d < bestD then
					best, bestD = { kind = "light", id = o.id }, d
				end
			end
		end
	end
	if best and bestD < 14 then
		return best
	end
	local vb, vd = nil, 12
	for _, v in self.visitors do
		if v.state ~= "gone" and v.state ~= "flee" then
			local d = math.sqrt((v.x - g.x) ^ 2 + (v.z - g.z) ^ 2)
			if d < vd then
				vb, vd = { kind = "visitor", id = v.id }, d
			end
		end
	end
	return vb or best or { kind = "plaza" }
end

function PlotSim:gloomTick(dt: number)
	local phase = self.clock.phase
	if phase ~= "night" then
		if #self.gloom > 0 then
			for _, g in self.gloom do
				self:emit({ k = "gloomFade", id = g.id })
			end
			self.gloom = {}
		end
		return
	end
	-- the midnight Veil Surge
	if not self.surge and self.clock.progress >= 0.45 then
		local n = 3 + self.profile.level // 3
		self.surge = { alive = 0, total = 0, won = false }
		for _ = 1, n do
			if self:spawnGloom(true) then
				self.surge.alive += 1
				self.surge.total += 1
			end
		end
		self:emit({ k = "surge", n = self.surge.total })
	end
	self.gloomTimer -= dt
	if self.gloomTimer <= 0 then
		self.gloomTimer = self.rng.range(8, 13)
		local normal = 0
		for _, g in self.gloom do
			if not g.surge then
				normal += 1
			end
		end
		if normal < self:gloomMax() then
			self:spawnGloom(false)
		end
	end
	for _, g in self.gloom do
		self:updateGloom(g, dt)
	end
end

function PlotSim:updateGloom(g, dt: number)
	g.touchCd -= dt
	g.retarget -= dt
	-- A player nearby draws it in.
	local prey, preyD = nil, 4
	for _, p in self.players do
		local d = math.sqrt((p.x - g.x) ^ 2 + (p.z - g.z) ^ 2)
		if d < preyD then
			prey, preyD = p, d
		end
	end
	local tx, tz
	g.chasing = prey ~= nil
	if prey then
		tx, tz = prey.x, prey.z
		if preyD < 1.05 and g.touchCd <= 0 then
			g.touchCd = Config.GLOOM_TOUCH_COOLDOWN
			self:emit({ k = "touch", player = prey.id, dmg = Config.GLOOM_TOUCH_DAMAGE, id = g.id })
		end
	else
		if not g.target or g.retarget <= 0 then
			g.target = self:pickGloomTarget(g)
			g.retarget = 1.5
		end
		local t = g.target
		if t.kind == "light" then
			local o = self.objects[t.id]
			if not o or o.snuffed then
				g.target = nil
				g.snuff = 0
			else
				tx, tz = self:objCentre(o)
				local d = math.sqrt((tx - g.x) ^ 2 + (tz - g.z) ^ 2)
				if d < 1.25 then
					g.snuff += dt
					tx, tz = nil, nil
					if g.snuff >= Config.LAMP_SNUFF_TIME then
						g.snuff = 0
						o.snuffed = true
						g.target = nil
						self:changed(false)
						if self.night then
							self.night.snuffed += 1
						end
						self:emit({ k = "snuff", obj = o.id })
					end
				else
					g.snuff = 0
				end
			end
		elseif t.kind == "visitor" then
			local v = self:visitorById(t.id)
			if not v or v.state == "gone" or v.state == "flee" then
				g.target = nil
			else
				tx, tz = v.x, v.z
			end
		else
			tx, tz = Grid.HEART_X, Grid.HEART_Z
		end
	end
	if tx then
		local dx, dz = tx - g.x, tz - g.z
		local d = math.sqrt(dx * dx + dz * dz)
		if d > 0.3 then
			local step = g.speed * (prey and 1.3 or 1) * dt
			local nx, nz = g.x + dx / d * math.min(step, d), g.z + dz / d * math.min(step, d)
			if not self:sanctuary(nx, nz) then
				g.x = clamp(nx, 0.3, W - 0.3)
				g.z = clamp(nz, 0.3, H + 2.7)
			end
		end
	end
	-- Visitors close by panic.
	for _, v in self.visitors do
		local st = v.state
		if st ~= "gone" and st ~= "flee" and st ~= "leave" and st ~= "home" and not KINDS[v.kind].fearless then
			local d = math.sqrt((v.x - g.x) ^ 2 + (v.z - g.z) ^ 2)
			if d < 1.6 then
				v.fear += 30 * dt
				if not v.scared then
					v.scared = true
					self:sayPick(v, KINDS[v.kind].creature and self:creatureLines(v) or LINES.scared, 0.9)
				end
				if v.fear >= Config.FEAR_TURN_BACK then
					self:turnBack(v)
				end
			end
		end
	end
end

function PlotSim:gloomById(id: number)
	for _, g in self.gloom do
		if g.id == id then
			return g
		end
	end
	return nil
end

-- Damage a Gloomling. (fx, fz) is where the blow came from, for knockback. Returns true if it died.
function PlotSim:damageGloom(id: number, dmg: number, by: number?, fx: number?, fz: number?, finisher: boolean?): boolean
	local g = self:gloomById(id)
	if not g then
		return false
	end
	g.hp -= dmg
	if fx and fz then
		local dx, dz = g.x - fx, g.z - fz
		local d = math.sqrt(dx * dx + dz * dz)
		if d > 0.01 then
			local push = finisher and 1.4 or 0.6
			local nx, nz = g.x + dx / d * push, g.z + dz / d * push
			if not self:sanctuary(nx, nz) then
				g.x, g.z = clamp(nx, 0.3, W - 0.3), clamp(nz, 0.3, H + 2.7)
			end
		end
	end
	g.snuff = 0
	self:emit({ k = "hit", id = id, dmg = dmg, by = by, crit = finisher == true, x = g.x, z = g.z })
	if g.hp > 0 then
		return false
	end
	for i, other in self.gloom do
		if other == g then
			table.remove(self.gloom, i)
			break
		end
	end
	local lumen = (self.rng.chance(0.6) and 1 or 0) + (g.surge and 1 or 0) + (self.rng.chance(0.1) and 1 or 0)
	if self.night then
		self.night.kills += 1
	end
	self:emit({ k = "die", id = id, by = by, x = g.x, z = g.z, lumen = lumen, surge = g.surge })
	if g.surge and self.surge and not self.surge.won then
		self.surge.alive -= 1
		if self.surge.alive <= 0 then
			self.surge.won = true
			if self.night then
				self.night.surge = true
			end
			self:emit({ k = "surgeWon" })
		end
	end
	return true
end

function PlotSim:towerTick(dt: number)
	if #self.gloom == 0 then
		return
	end
	for _, o in self:towers() do
		o.cooldown = (o.cooldown or 0) - dt
		if o.cooldown > 0 then
			continue
		end
		local cx, cz = self:objCentre(o)
		local best, bestD = nil, 5.2
		for _, g in self.gloom do
			local d = math.sqrt((g.x - cx) ^ 2 + (g.z - cz) ^ 2)
			if d < bestD then
				best, bestD = g, d
			end
		end
		if best then
			o.cooldown = 1.5
			self:emit({ k = "bolt", obj = o.id, id = best.id, x = best.x, z = best.z })
			self:damageGloom(best.id, 12, nil, cx, cz, false)
		end
	end
end

-- ─── time ──────────────────────────────────────────────────────────────────
function PlotSim:startNight()
	self.night = {
		visitors = 0,
		happy = 0,
		content = 0,
		unhappy = 0,
		fled = 0,
		sold = {},
		revenue = 0,
		tips = 0,
		kills = 0,
		snuffed = 0,
		soldOut = 0,
		noBed = 0,
		missing = {},
		settled = {},
		surge = false,
	}
	self.surge = nil
end

function PlotSim:onPhase(from: string, to: string)
	if to == "dusk" then
		self:startNight()
		self:emit({ k = "dusk" })
	elseif to == "night" then
		if not self.night then
			self:startNight()
		end
		self:emit({ k = "night" })
	elseif to == "dawn" then
		local ledger = self.night
		if ledger then
			ledger.appeal = self:appeal().total
			ledger.roadLit = self:roadLit()
		end
		self:emit({ k = "dawn", ledger = ledger })
		self.night = nil
		self.surge = nil
	elseif to == "day" then
		self:emit({ k = "day" })
	end
end

function PlotSim:update(dt: number, clock: Clock, players: { PlayerPos }?)
	self.time += dt
	local prev = self.clock.phase
	self.clock = clock
	self.players = players or {}
	if clock.phase ~= prev then
		self:onPhase(prev, clock.phase)
	end
	self:produceTick(dt)
	self:stallTick(dt)
	self:spawnTick(dt)
	for _, v in self.visitors do
		self:updateVisitor(v, dt)
	end
	for i = #self.visitors, 1, -1 do
		if self.visitors[i].state == "gone" then
			local v = table.remove(self.visitors, i)
			if v.stallId ~= 0 then
				self:leaveQueue(v)
			end
		end
	end
	self:gloomTick(dt)
	self:towerTick(dt)
	self:settlerTick(dt)
	self:tipTick(dt)
end

-- What the owner's HUD shows about the plot.
function PlotSim:summary()
	local ap = self:appeal()
	return {
		appeal = ap.total,
		appealParts = ap,
		roadLit = self:roadLit(),
		stock = self.stock,
		cap = self:storeCap(),
		settlers = #self.settlers,
		beds = self:beds(),
		tier = self.tier,
		visitors = #self.visitors,
		gloom = #self.gloom,
	}
end

return PlotSim
