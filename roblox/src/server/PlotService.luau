--!strict
-- The six plots: who owns which, their simulations, and everything that makes a simulation visible:
-- building models, paths, the forest, the gate sign, ProximityPrompts, snapshots and effects.
-- Handles every building request from clients.

local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Codec = require(Shared.Codec)
local Config = require(Shared.Config)
local Grid = require(Shared.Grid)
local Layout = require(Shared.Layout)
local Models = require(Shared.Models)
local Net = require(Shared.Net)
local PlotSim = require(Shared.PlotSim)
local Progress = require(Shared.Progress)

local DayNight = require(script.Parent.DayNight)
local ProgressService = require(script.Parent.ProgressService)
local World = require(script.Parent.World)

local PlotService = {}

local B = Catalog.Buildings
local W, H = Grid.W, Grid.H
local TILE = Config.TILE
local ORDER = { 2, 5, 1, 3, 4, 6 }
local NEAR = 330 -- studs from a plot's centre within which you see its visitors

type Plot = {
	index: number,
	cf: CFrame,
	centre: Vector3,
	folder: Folder,
	buildings: Folder,
	pathsF: Folder,
	treesF: Folder,
	owner: Player?,
	userId: number,
	profile: any,
	sim: any,
	models: { [number]: Model },
	sigs: { [number]: string },
	paths: { [number]: BasePart },
	trees: { [number]: Model },
	needsSync: boolean,
	layoutDirty: boolean,
	lastLayout: number,
	lastSummary: string,
	summaryAt: number,
	noBedAt: number,
	viewers: { Player },
}

local plots: { [number]: Plot } = {}
local byPlayer: { [Player]: Plot } = {}
local remotes = Net.get()

local FORWARD = {
	say = true, sale = true, tip = true, tipGone = true, visit = true, leave = true, flee = true, ripe = true, tend = true,
	snuff = true, relight = true, placed = true, removed = true, moved = true, restyled = true, upgraded = true,
	gloomSpawn = true, hit = true, die = true, bolt = true, surge = true, surgeWon = true, settle = true, tier = true,
	produce = true, touch = true, painted = true, gloomFade = true,
}

-- ─── the forest ────────────────────────────────────────────────────────────
local function syncTrees(plot: Plot, terrain: { number })
	for i = 1, W * H do
		local want = Grid.hasTree(terrain, i)
		local m = plot.trees[i]
		if want and not m then
			local x, z = Grid.fromIdx(i)
			local tree = Models.forestTree(x * 31 + z * 17, 0.95 + Grid.hash(x, z, 4) * 0.65)
			local jx = (Grid.hash(x, z, 5) - 0.5) * 2.4
			local jz = (Grid.hash(x, z, 6) - 0.5) * 2.4
			tree:PivotTo(plot.cf * CFrame.new((x + 0.5) * TILE + jx, 0, (z + 0.5) * TILE + jz) * CFrame.Angles(0, Grid.hash(x, z, 7) * 6.28, 0))
			tree.Parent = plot.treesF
			plot.trees[i] = tree
		elseif not want and m then
			m:Destroy()
			plot.trees[i] = nil
		end
	end
end

-- ─── building models ───────────────────────────────────────────────────────
local function sigOf(plot: Plot, o: any): string
	return string.format("%s|%d|%d|%d|%d|%d|%s|%d", o.type, o.x, o.z, o.rot, o.variant or 0, o.level or 0, o.goods or "", o.type == "heartflame" and plot.sim.tier or 0)
end

local function setPrompt(m: Model, name: string, enabled: boolean)
	local hb = m:FindFirstChild("Hitbox")
	local pr = hb and hb:FindFirstChild(name)
	if pr and pr:IsA("ProximityPrompt") then
		pr.Enabled = enabled
	end
end

local function setRipe(m: Model, ripe: boolean)
	local sparkle = m:FindFirstChild("Sparkle")
	local e = sparkle and sparkle:FindFirstChild("Ripe")
	if e and e:IsA("ParticleEmitter") then
		e.Enabled = ripe
	end
	setPrompt(m, "TendPrompt", ripe)
	m:SetAttribute("Ripe", ripe)
end

local function setSnuffed(m: Model, snuffed: boolean)
	Models.setSnuffed(m, snuffed)
	setPrompt(m, "RelightPrompt", snuffed)
end

local processEvents: (Plot) -> ()

local function onPrompt(plot: Plot, id: number, who: Player, action: string)
	local sim = plot.sim
	if not sim then
		return
	end
	if action == "tend" then
		sim:tend(id, who.UserId)
	else
		sim:relight(id, who.UserId)
	end
	processEvents(plot)
end

local function addPrompt(plot: Plot, m: Model, id: number, name: string, action: string, text: string, objectText: string, enabled: boolean)
	local hb = m:FindFirstChild("Hitbox")
	if not hb then
		return
	end
	local pr = Instance.new("ProximityPrompt")
	pr.Name = name
	pr.ActionText = text
	pr.ObjectText = objectText
	pr.HoldDuration = 0.3
	pr.MaxActivationDistance = 16
	pr.RequiresLineOfSight = false
	pr.KeyboardKeyCode = Enum.KeyCode.E
	pr.Enabled = enabled
	pr.Parent = hb
	pr.Triggered:Connect(function(who)
		onPrompt(plot, id, who, action)
	end)
end

local function buildModel(plot: Plot, o: any): Model
	local def = B[o.type]
	local m = Models.build(o.type, o.variant, { level = o.level, goods = o.goods, tier = plot.sim.tier, snuffed = o.snuffed })
	m:PivotTo(Layout.objectCFrame(plot.cf, o.x, o.z, o.w, o.d, o.rot))
	m:SetAttribute("ObjId", o.id)
	m:SetAttribute("Type", o.type)
	m:SetAttribute("Plot", plot.index)
	if def.tendable then
		addPrompt(plot, m, o.id, "TendPrompt", "tend", "Tend", def.name, o.ripe == true)
		setRipe(m, o.ripe == true)
	end
	if def.snuffable then
		addPrompt(plot, m, o.id, "RelightPrompt", "relight", "Relight", def.name, o.snuffed == true)
	end
	m.Parent = plot.buildings
	return m
end

local function syncModels(plot: Plot)
	local sim = plot.sim
	for id, o in sim.objects do
		local sig = sigOf(plot, o)
		local m = plot.models[id]
		if plot.sigs[id] ~= sig or not m then
			if m then
				m:Destroy()
			end
			m = buildModel(plot, o)
			plot.models[id] = m
			plot.sigs[id] = sig
		end
		if m and B[o.type].stall then
			m:SetAttribute("NoPath", sim:serviceTile(o) == nil)
			m:SetAttribute("Level", o.level)
			m:SetAttribute("Goods", o.goods)
		end
		if m and B[o.type].worker then
			m:SetAttribute("Worker", o.worker)
		end
	end
	for id, m in plot.models do
		if not sim.objects[id] then
			m:Destroy()
			plot.models[id] = nil
			plot.sigs[id] = nil
		end
	end
end

local function syncPaths(plot: Plot)
	local surface = plot.sim.surface
	for i = 1, W * H do
		local on = surface[i] == 1
		local p = plot.paths[i]
		if on and not p then
			local x, z = Grid.fromIdx(i)
			local part = Models.pathTile(plot.pathsF, plot.cf * CFrame.new((x + 0.5) * TILE, 0.02, (z + 0.5) * TILE), x * 7 + z * 3)
			part.CastShadow = false
			plot.paths[i] = part
		elseif not on and p then
			p:Destroy()
			plot.paths[i] = nil
		end
	end
end

local function clearVisuals(plot: Plot)
	plot.buildings:ClearAllChildren()
	plot.pathsF:ClearAllChildren()
	plot.models = {}
	plot.sigs = {}
	plot.paths = {}
end

local function setSign(plot: Plot)
	local gate = plot.folder:FindFirstChild("Gate")
	local sign = gate and gate:FindFirstChild("Sign")
	local gui = sign and sign:FindFirstChild("SignGui")
	if not gui then
		return
	end
	local title = gui:FindFirstChild("Title") :: TextLabel?
	local sub = gui:FindFirstChild("Sub") :: TextLabel?
	if plot.owner and plot.profile then
		local rank, _, icon = Catalog.rankFor(plot.profile.level)
		if title then
			title.Text = plot.owner.DisplayName .. "'s Market"
		end
		if sub then
			sub.Text = string.format("%s %s · Lv %d", icon, rank, plot.profile.level)
		end
	else
		if title then
			title.Text = "A Free Clearing"
		end
		if sub then
			sub.Text = "Waiting for a Sovereign"
		end
	end
end

-- An unclaimed plot: forest, the Old Road, and a cold brazier.
local function shell(plot: Plot)
	clearVisuals(plot)
	World.paintRealm(plot.index, Catalog.Heartflame[1].radius)
	syncTrees(plot, Grid.makeTerrain(Catalog.Heartflame[1].radius))
	local m = Models.build("heartflame", 0, { tier = 1 })
	for _, d in m:GetDescendants() do
		if d:IsA("Fire") then
			d.Enabled = false
		elseif d:IsA("ParticleEmitter") then
			d.Enabled = false
		end
	end
	Models.setSnuffed(m, true)
	m:PivotTo(Layout.objectCFrame(plot.cf, Grid.HEART_TILE.x, Grid.HEART_TILE.z, 2, 2, 0))
	m.Parent = plot.buildings
	setSign(plot)
end

-- ─── what the owner's client needs ─────────────────────────────────────────
local function sendLayout(plot: Plot)
	local owner = plot.owner
	if not owner or not plot.sim then
		return
	end
	local sim = plot.sim
	local objs = {}
	for _, o in sim.objects do
		table.insert(objs, { o.id, o.type, o.x, o.z, o.rot, o.variant or 0, o.level or 0, o.goods or "", o.snuffed == true, o.ripe == true, o.worker or "" })
	end
	local paths = {}
	for i = 1, W * H do
		if sim.surface[i] == 1 then
			table.insert(paths, i)
		end
	end
	local settlers = {}
	for _, s in sim.settlers do
		table.insert(settlers, { s.id, s.name, s.kind })
	end
	plot.layoutDirty = false
	plot.lastLayout = os.clock()
	ProgressService.send(owner, "layout", { index = plot.index, tier = sim.tier, objs = objs, paths = paths, settlers = settlers, nextId = sim.nextId })
end

local function sendSummary(plot: Plot, force: boolean?)
	local owner = plot.owner
	if not owner or not plot.sim then
		return
	end
	local sim = plot.sim
	local s = sim:summary()
	local stalls = {}
	for _, st in sim:stalls() do
		table.insert(stalls, { st.id, st.goods, st.level, #st.queue, st.sold, sim:serviceTile(st) == nil })
	end
	local data = {
		appeal = s.appeal,
		decor = s.appealParts.decor,
		variety = s.appealParts.variety,
		light = s.appealParts.light,
		roadLit = s.roadLit,
		stock = s.stock,
		cap = s.cap,
		settlers = s.settlers,
		beds = s.beds,
		tier = s.tier,
		visitors = s.visitors,
		gloom = s.gloom,
		stalls = stalls,
	}
	local json = HttpService:JSONEncode(data)
	if force or json ~= plot.lastSummary then
		plot.lastSummary = json
		ProgressService.send(owner, "plot", data)
	end
end

-- ─── events from the simulation ────────────────────────────────────────────
local function playerById(id: number?): Player?
	if not id or id == 0 then
		return nil
	end
	return Players:GetPlayerByUserId(id)
end

processEvents = function(plot: Plot)
	local sim = plot.sim
	if not sim then
		return
	end
	local events = sim:drain()
	if #events == 0 and not plot.needsSync then
		return
	end
	local owner = plot.owner
	local fx = {}
	for _, e in events do
		local k = e.k
		if owner and plot.profile then
			local gain = Progress.onEvent(plot.profile, e, plot.userId)
			if gain.xp > 0 or gain.lumen ~= 0 then
				ProgressService.grant(owner, gain.xp, gain.lumen)
			else
				ProgressService.markDirty(owner)
			end
			if gain.helper then
				local hp = playerById(gain.helper)
				if hp then
					ProgressService.grant(hp, gain.helperXp, gain.helperLumen)
				end
			end
			if gain.discovered then
				ProgressService.discovered(owner, gain.discovered)
			end
			if gain.first then
				local def = B[gain.first]
				if def then
					ProgressService.toast(owner, "Your first " .. def.name .. "!", def.icon, "good")
				end
			end
		end
		local m = e.obj and plot.models[e.obj]
		if k == "snuff" then
			if m then
				setSnuffed(m, true)
			end
			plot.layoutDirty = true
		elseif k == "relight" then
			if m then
				setSnuffed(m, false)
			end
			plot.layoutDirty = true
		elseif k == "ripe" then
			if m then
				setRipe(m, true)
			end
		elseif k == "tend" then
			if m then
				setRipe(m, false)
			end
		elseif k == "tier" then
			World.paintRealm(plot.index, sim:radius())
			syncTrees(plot, sim.terrain)
			plot.needsSync = true
			if owner then
				ProgressService.send(owner, "tier", { tier = sim.tier, name = Catalog.Heartflame[sim.tier].name })
			end
		elseif k == "placed" or k == "removed" or k == "moved" or k == "restyled" or k == "upgraded" or k == "painted" then
			plot.needsSync = true
		elseif k == "touch" then
			local victim = playerById(e.player)
			local char = victim and victim.Character
			local hum = char and char:FindFirstChildOfClass("Humanoid")
			if hum and hum.Health > 0 then
				hum:TakeDamage(e.dmg)
			end
		elseif k == "settle" then
			plot.layoutDirty = true
			if owner then
				ProgressService.toast(owner, e.name .. " moved into your realm!", "🏠", "good")
			end
		elseif k == "noBed" then
			if owner and os.clock() - plot.noBedAt > 40 then
				plot.noBedAt = os.clock()
				ProgressService.toast(owner, e.name .. " wanted to stay, but there's no free bed.", "🛏️", "warn")
			end
		elseif k == "dusk" then
			if owner then
				ProgressService.nightStart(owner)
			end
		elseif k == "surge" then
			if owner then
				ProgressService.send(owner, "surge", { n = e.n })
			end
		elseif k == "surgeWon" then
			if owner then
				ProgressService.send(owner, "surgeWon", {})
			end
		elseif k == "dawn" then
			local ledger = e.ledger
			if ledger and owner then
				local xp, lumen = ProgressService.nightTotals(owner)
				ledger.xp = xp
				ledger.lumen = lumen
				ledger.gold = ledger.revenue + ledger.tips
				ProgressService.send(owner, "ledger", ledger)
			end
		end
		if FORWARD[k] then
			local copy = table.clone(e)
			copy.ledger = nil
			table.insert(fx, copy)
		end
	end
	if plot.needsSync then
		plot.needsSync = false
		syncPaths(plot)
		syncModels(plot)
		plot.layoutDirty = true
		setSign(plot)
	end
	if #fx > 0 then
		for _, p in plot.viewers do
			if p.Parent then
				remotes.Fx:FireClient(p, plot.index, fx)
			end
		end
	end
end

-- ─── claiming and releasing ────────────────────────────────────────────────
local function roadCFrame(plot: Plot): CFrame
	local pos = Layout.toWorld(plot.cf, Grid.ENTRANCE.x, Grid.ENTRANCE.z - 3, 4)
	local look = Layout.toWorld(plot.cf, Grid.HEART_X, Grid.HEART_Z, 4)
	return CFrame.lookAt(pos, look)
end

function PlotService.sendHome(player: Player, index: number?)
	local plot = index and plots[index] or byPlayer[player]
	local char = player.Character
	if plot and char then
		char:PivotTo(roadCFrame(plot))
	end
end

function PlotService.claim(player: Player, profile: any): number?
	for _, i in ORDER do
		local plot = plots[i]
		if not plot.owner then
			plot.owner = player
			plot.userId = player.UserId
			plot.profile = profile
			local sim = PlotSim.new(profile, (player.UserId % 100000) + math.floor(os.clock() * 1000) % 997)
			if profile.plot then
				sim:load(profile.plot)
			else
				sim:layStarter()
			end
			sim:drain()
			plot.sim = sim
			clearVisuals(plot)
			World.paintRealm(i, sim:radius())
			syncTrees(plot, sim.terrain)
			syncPaths(plot)
			syncModels(plot)
			setSign(plot)
			byPlayer[player] = plot
			plot.folder:SetAttribute("Owner", player.UserId)
			player:SetAttribute("Plot", i)
			sendLayout(plot)
			sendSummary(plot, true)
			return i
		end
	end
	return nil
end

-- Writes the plot into the profile (for saving).
function PlotService.store(player: Player)
	local plot = byPlayer[player]
	if plot and plot.sim and plot.profile then
		plot.profile.plot = plot.sim:serialize()
	end
end

function PlotService.release(player: Player)
	local plot = byPlayer[player]
	if not plot then
		return
	end
	PlotService.store(player)
	byPlayer[player] = nil
	plot.owner = nil
	plot.userId = 0
	plot.profile = nil
	plot.sim = nil
	plot.folder:SetAttribute("Owner", nil)
	shell(plot)
end

function PlotService.live(player: Player): Progress.Live?
	local plot = byPlayer[player]
	if not plot or not plot.sim then
		return nil
	end
	local sim = plot.sim
	local counts = {}
	for _, o in sim.objects do
		counts[o.type] = (counts[o.type] or 0) + 1
	end
	return { tier = sim.tier, appeal = sim:appeal().total, roadLit = sim:roadLit(), counts = counts }
end

function PlotService.plotAt(pos: Vector3): (any, number, number)
	local i, x, z = Layout.plotAt(pos)
	if not i then
		return nil, 0, 0
	end
	return plots[i], x, z
end

function PlotService.get(index: number): any
	return plots[index]
end

function PlotService.processEvents(plot: any)
	processEvents(plot)
end

-- ─── the tick ──────────────────────────────────────────────────────────────
local function tick(dt: number)
	local c = DayNight.now()
	local clock = { phase = c.phase, night = c.night, progress = c.progress }
	local positions: { [number]: { any } } = {}
	local roots: { [Player]: Vector3 } = {}
	for _, p in Players:GetPlayers() do
		local char = p.Character
		local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
		local hum = char and char:FindFirstChildOfClass("Humanoid")
		if hrp and hum and hum.Health > 0 then
			roots[p] = hrp.Position
			local i, x, z = Layout.plotAt(hrp.Position)
			if i and not p:GetAttribute("Building") then
				positions[i] = positions[i] or {}
				table.insert(positions[i], { id = p.UserId, x = x, z = z, owner = plots[i].owner == p })
			end
			-- the Heartflame's glow mends you
			local sim = i and plots[i].sim
			if sim and hum.Health < hum.MaxHealth and sim:sanctuary(x, z) then
				hum.Health = math.min(hum.MaxHealth, hum.Health + Config.HEARTH_HEAL * dt)
			end
		end
	end
	local now = os.clock()
	for i, plot in plots do
		local viewers = {}
		for p, pos in roots do
			if p == plot.owner or (pos - plot.centre).Magnitude < NEAR then
				table.insert(viewers, p)
			end
		end
		if plot.owner and not roots[plot.owner] then
			table.insert(viewers, plot.owner)
		end
		plot.viewers = viewers
		local sim = plot.sim
		if sim then
			local ok, err = pcall(function()
				sim:update(dt, clock, positions[i] or {})
			end)
			if not ok then
				warn("[Kingsbloom] plot " .. i .. " update failed: " .. tostring(err))
			end
			processEvents(plot)
			if #viewers > 0 then
				local buf = Codec.encode(i, sim)
				for _, p in viewers do
					remotes.Snap:FireClient(p, buf)
				end
			end
			if plot.layoutDirty and now - plot.lastLayout > 0.25 then
				sendLayout(plot)
			end
			if now - plot.summaryAt > 0.5 then
				plot.summaryAt = now
				sendSummary(plot)
			end
		end
	end
end

-- ─── requests from clients ─────────────────────────────────────────────────
local function int(v: any, lo: number, hi: number): number?
	if typeof(v) ~= "number" or v ~= v then
		return nil
	end
	local n = math.floor(v)
	if n < lo or n > hi then
		return nil
	end
	return n
end

local buckets: { [Player]: { tokens: number, at: number } } = {}
local function allow(player: Player): boolean
	local b = buckets[player]
	local now = os.clock()
	if not b then
		b = { tokens = 40, at = now }
		buckets[player] = b
	end
	b.tokens = math.min(40, b.tokens + (now - b.at) * 20)
	b.at = now
	if b.tokens < 1 then
		return false
	end
	b.tokens -= 1
	return true
end

type Result = { ok: boolean, reason: string?, n: number? }
local handlers: { [string]: (Player, any, any) -> Result } = {}

local function result(ok: boolean, reason: string?): Result
	return { ok = ok, reason = reason }
end

handlers.place = function(player, plot, a)
	local t = typeof(a.t) == "string" and a.t or ""
	local x, z = int(a.x, 0, W - 1), int(a.z, 0, H - 1)
	local r, v = int(a.r, 0, 3) or 0, int(a.v, 0, 9) or 0
	if not B[t] or not x or not z then
		return result(false, "That doesn't fit.")
	end
	local o, reason = plot.sim:place(t, x, z, r, v)
	return result(o ~= nil, reason)
end

local function tilesArg(a: any): { { number } }
	local out = {}
	if typeof(a.tiles) ~= "table" then
		return out
	end
	for i, t in a.tiles do
		if i > 80 then
			break
		end
		if typeof(t) == "table" then
			local x, z = int(t[1], 0, W - 1), int(t[2], 0, H - 1)
			if x and z then
				table.insert(out, { x, z })
			end
		end
	end
	return out
end

handlers.paint = function(player, plot, a)
	local n, reason = 0, nil
	for _, t in tilesArg(a) do
		local ok, why = plot.sim:paint(t[1], t[2])
		if ok then
			n += 1
		else
			reason = why
		end
	end
	return { ok = n > 0, reason = n == 0 and reason or nil, n = n }
end

handlers.erase = function(player, plot, a)
	local n = 0
	for _, t in tilesArg(a) do
		if plot.sim:erase(t[1], t[2]) then
			n += 1
		end
	end
	if n > 0 then
		plot.needsSync = true
	end
	return { ok = n > 0, n = n }
end

handlers.remove = function(player, plot, a)
	local id = int(a.id, 1, 1e7)
	if not id then
		return result(false, "Nothing there.")
	end
	local ok, reason = plot.sim:remove(id)
	return result(ok, reason)
end

handlers.move = function(player, plot, a)
	local id = int(a.id, 1, 1e7)
	local x, z, r = int(a.x, 0, W - 1), int(a.z, 0, H - 1), int(a.r, 0, 3)
	if not id or not x or not z or not r then
		return result(false, "That doesn't fit.")
	end
	local ok, reason = plot.sim:move(id, x, z, r)
	return result(ok, reason)
end

handlers.variant = function(player, plot, a)
	local id, v = int(a.id, 1, 1e7), int(a.v, 0, 9)
	if not id or not v then
		return result(false)
	end
	return result(plot.sim:setVariant(id, v))
end

handlers.goods = function(player, plot, a)
	local id = int(a.id, 1, 1e7)
	local g = typeof(a.g) == "string" and a.g or ""
	if not id then
		return result(false)
	end
	local ok, reason = plot.sim:setGoods(id, g)
	return result(ok, reason)
end

handlers.upgrade = function(player, plot, a)
	local id = int(a.id, 1, 1e7)
	if not id then
		return result(false)
	end
	local ok, reason = plot.sim:upgradeStall(id)
	return result(ok, reason)
end

handlers.heart = function(player, plot, _a)
	local ok, reason = plot.sim:raiseHeart()
	return result(ok, reason)
end

handlers.relight = function(player, plot, a)
	local id = int(a.id, 1, 1e7)
	local o = id and plot.sim.objects[id]
	if not o or not o.snuffed then
		return result(false, "It's already lit.")
	end
	-- From afar (Build mode) Flicker relights it for a few coins.
	local char = player.Character
	local m = plot.models[id]
	local near = char and m and (char:GetPivot().Position - m:GetPivot().Position).Magnitude < 20
	if not near then
		if plot.profile.gold < 5 then
			return result(false, "Relighting from afar costs 5 gold.")
		end
		plot.profile.gold -= 5
	end
	return result(plot.sim:relight(id, player.UserId))
end

local open: { [string]: (Player, Plot?, any) -> Result } = {}

open.collect = function(player, _plot, a)
	local index = int(a.p, 1, Config.PLOT_COUNT)
	local id = int(a.id, 1, 70000)
	local target = index and plots[index]
	if not target or not target.sim or not id then
		return result(false)
	end
	if target.owner ~= player then
		local char = player.Character
		if not char or (char:GetPivot().Position - target.centre).Magnitude > 200 then
			return result(false)
		end
	end
	local v = target.sim:collectTip(id, player.UserId)
	processEvents(target)
	return result(v > 0)
end

open.claimQuest = function(player, _plot, _a)
	local ok, reason = ProgressService.claimQuest(player)
	return result(ok, reason)
end

open.claimOrder = function(player, _plot, a)
	local i = int(a.i, 1, 3)
	if not i then
		return result(false)
	end
	local ok, reason = ProgressService.claimOrder(player, i)
	return result(ok, reason)
end

open.settings = function(player, _plot, a)
	ProgressService.settings(player, a)
	return result(true)
end

open.mode = function(player, _plot, a)
	player:SetAttribute("Building", a.build == true)
	return result(true)
end

open.home = function(player, _plot, _a)
	PlotService.sendHome(player)
	return result(true)
end

open.visit = function(player, _plot, a)
	local i = int(a.i, 1, Config.PLOT_COUNT)
	if not i then
		return result(false)
	end
	PlotService.sendHome(player, i)
	return result(true)
end

open.sync = function(player, plot, _a)
	if plot then
		sendLayout(plot)
		sendSummary(plot, true)
	end
	ProgressService.push(player)
	return result(true)
end

local function onRequest(player: Player, action: any, args: any): Result
	if typeof(action) ~= "string" then
		return result(false)
	end
	if not allow(player) then
		return result(false, "Slow down a little.")
	end
	local a = typeof(args) == "table" and args or {}
	local plot = byPlayer[player]
	local h = handlers[action]
	local o = open[action]
	if not h and not o then
		return result(false, "Unknown action.")
	end
	if h and (not plot or not plot.sim) then
		return result(false, "You don't have a plot.")
	end
	local ok, res = pcall(function(): Result
		if h then
			return h(player, plot, a)
		end
		return (o :: any)(player, plot, a)
	end)
	if not ok then
		warn("[Kingsbloom] request " .. action .. " failed: " .. tostring(res))
		return result(false, "Something went wrong.")
	end
	if h and plot then
		processEvents(plot)
		ProgressService.markDirty(player)
	end
	return res
end

function PlotService.start()
	for i = 1, Config.PLOT_COUNT do
		local cf = Layout.plotCFrame(i)
		local f = World.plotFolder(i)
		local plot: Plot = {
			index = i,
			cf = cf,
			centre = Layout.toWorld(cf, W / 2, H / 2, 0),
			folder = f,
			buildings = f:WaitForChild("Buildings") :: Folder,
			pathsF = f:WaitForChild("Paths") :: Folder,
			treesF = f:WaitForChild("Trees") :: Folder,
			owner = nil,
			userId = 0,
			profile = nil,
			sim = nil,
			models = {},
			sigs = {},
			paths = {},
			trees = {},
			needsSync = false,
			layoutDirty = false,
			lastLayout = 0,
			lastSummary = "",
			summaryAt = 0,
			noBedAt = 0,
			viewers = {},
		}
		plots[i] = plot
		shell(plot)
	end
	ProgressService.setLive(PlotService.live)
	ProgressService.onLevel(function(player, _level)
		local plot = byPlayer[player]
		if plot then
			setSign(plot)
			plot.layoutDirty = true
		end
	end)
	remotes.Request.OnServerInvoke = onRequest
	local acc = 0
	RunService.Heartbeat:Connect(function(dt)
		acc += dt
		if acc >= 0.1 then
			local step = math.min(acc, 0.3)
			acc = 0
			tick(step)
		end
	end)
	Players.PlayerRemoving:Connect(function(p)
		buckets[p] = nil
	end)
end

return PlotService
