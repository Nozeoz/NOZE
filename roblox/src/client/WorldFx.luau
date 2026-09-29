--!strict
-- Turns what happens on a plot into things you can see and hear: tip coins you can grab, sale
-- pops, building puffs, sparkles, Gloomling hits and deaths, tower bolts, bursts, the Heartflame
-- rising. Also lets you click tip coins to collect them.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Config = require(Shared.Config)
local Grid = require(Shared.Grid)
local Layout = require(Shared.Layout)
local Models = require(Shared.Models)
local Palette = require(Shared.Palette)

local State = require(script.Parent.State)
local Audio = require(script.Parent.Audio)
local Entities = require(script.Parent.Entities)
local Actors = require(script.Parent.Actors)
local Shake = require(script.Parent.Shake)

local WorldFx = {}

local TILE = Config.TILE
local fxFolder = Instance.new("Folder")
fxFolder.Name = "KingsbloomFx"
fxFolder.Parent = Workspace
local tipFolder = Instance.new("Folder")
tipFolder.Name = "Tips"
tipFolder.Parent = fxFolder

type Tip = { model: Model, pos: Vector3, t: number }
local tips: { [string]: Tip } = {}
local models: { [number]: { [number]: Model } } = {}
local lastPop: { [string]: number } = {}

local function me(): number
	return State.player.UserId
end

local function myRoot(): BasePart?
	local char = State.player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart")
	if hrp and hrp:IsA("BasePart") then
		return hrp
	end
	return nil
end

local function isMine(plot: number): boolean
	return State.myPlot() == plot
end

local function at(plot: number, x: number, z: number, y: number?): Vector3
	return Layout.toWorld(Layout.plotCFrame(plot), x, z, y or 0)
end

local function throttle(key: string, seconds: number): boolean
	local now = os.clock()
	if now - (lastPop[key] or 0) < seconds then
		return false
	end
	lastPop[key] = now
	return true
end

-- ─── building lookups ──────────────────────────────────────────────────────
local function watchPlot(i: number, buildings: Instance)
	local map: { [number]: Model } = {}
	models[i] = map
	local function add(m: Instance)
		if m:IsA("Model") then
			local id = m:GetAttribute("ObjId")
			if typeof(id) == "number" then
				map[id] = m
			end
		end
	end
	for _, m in buildings:GetChildren() do
		add(m)
	end
	buildings.ChildAdded:Connect(add)
	buildings.ChildRemoved:Connect(function(m)
		local id = m:GetAttribute("ObjId")
		if typeof(id) == "number" and map[id] == m then
			map[id] = nil
		end
	end)
end

function WorldFx.model(plot: number, id: number): Model?
	local map = models[plot]
	return map and map[id]
end

local function modelTop(plot: number, id: number): Vector3?
	local m = WorldFx.model(plot, id)
	if not m then
		return nil
	end
	local cf, size = m:GetBoundingBox()
	return cf.Position + Vector3.new(0, size.Y / 2 + 1, 0)
end

-- ─── little effects ────────────────────────────────────────────────────────
function WorldFx.floatText(pos: Vector3, text: string, color: Color3, size: number?, rise: number?)
	local a = Instance.new("Attachment")
	a.WorldPosition = pos
	a.Parent = Workspace.Terrain
	local g = Instance.new("BillboardGui")
	g.Size = UDim2.fromOffset(200, 48)
	g.AlwaysOnTop = true
	g.LightInfluence = 0
	g.MaxDistance = 160
	g.Adornee = a
	g.Parent = a
	local l = Instance.new("TextLabel")
	l.Size = UDim2.fromScale(1, 1)
	l.BackgroundTransparency = 1
	l.Font = Enum.Font.FredokaOne
	l.TextSize = size or 26
	l.TextColor3 = color
	l.Text = text
	l.Parent = g
	local s = Instance.new("UIStroke")
	s.Color = Color3.fromRGB(40, 24, 16)
	s.Thickness = 2
	s.Parent = l
	local sc = Instance.new("UIScale")
	sc.Scale = 0.4
	sc.Parent = l
	TweenService:Create(sc, TweenInfo.new(0.25, Enum.EasingStyle.Back), { Scale = 1 }):Play()
	TweenService:Create(g, TweenInfo.new(1.1, Enum.EasingStyle.Quad), { StudsOffset = Vector3.new(0, rise or 3.5, 0) }):Play()
	TweenService:Create(l, TweenInfo.new(0.5, Enum.EasingStyle.Quad, Enum.EasingDirection.In, 0, false, 0.6), { TextTransparency = 1 }):Play()
	TweenService:Create(s, TweenInfo.new(0.5, Enum.EasingStyle.Quad, Enum.EasingDirection.In, 0, false, 0.6), { Transparency = 1 }):Play()
	task.delay(1.3, function()
		a:Destroy()
	end)
end

function WorldFx.puff(pos: Vector3, color: Color3, n: number, size: number?, smoke: boolean?)
	local a = Instance.new("Attachment")
	a.WorldPosition = pos
	a.Parent = Workspace.Terrain
	local e = Models.emitter(a, {
		texture = smoke and "rbxasset://textures/particles/smoke_main.dds" or "rbxasset://textures/particles/sparkles_main.dds",
		rate = 0,
		lifetime = NumberRange.new(0.5, 1.1),
		speed = NumberRange.new(4, 9),
		spread = Vector2.new(180, 180),
		size = Models.seq(size or 1, 0),
		transparency = Models.seq(smoke and 0.3 or 0, 1),
		color = ColorSequence.new(color),
		emission = smoke and 0.2 or 1,
		influence = smoke and 0.6 or 0,
		drag = 4,
		accel = Vector3.new(0, smoke and 3 or -6, 0),
	})
	e:Emit(n)
	task.delay(2.5, function()
		a:Destroy()
	end)
end

local function beam(from: Vector3, to: Vector3, color: Color3, width: number, life: number)
	local a0 = Instance.new("Attachment")
	a0.WorldPosition = from
	a0.Parent = Workspace.Terrain
	local a1 = Instance.new("Attachment")
	a1.WorldPosition = to
	a1.Parent = Workspace.Terrain
	local b = Instance.new("Beam")
	b.Attachment0 = a0
	b.Attachment1 = a1
	b.Width0 = width
	b.Width1 = width * 0.4
	b.Color = ColorSequence.new(color, Color3.new(1, 1, 1))
	b.LightEmission = 1
	b.FaceCamera = true
	b.Transparency = NumberSequence.new(0.1)
	b.Parent = a0
	task.delay(life, function()
		a0:Destroy()
		a1:Destroy()
	end)
end

local function ring(pos: Vector3, radius: number, color: Color3, time: number)
	local p = Models.ball(fxFolder, 1, CFrame.new(pos), color, Enum.Material.Neon, false)
	p.CanQuery = false
	p.CastShadow = false
	p.Transparency = 0.25
	TweenService:Create(p, TweenInfo.new(time, Enum.EasingStyle.Quart), { Size = Vector3.one * radius * 2, Transparency = 1 }):Play()
	local l = Instance.new("PointLight")
	l.Range = radius * 1.5
	l.Brightness = 4
	l.Color = color
	l.Parent = p
	TweenService:Create(l, TweenInfo.new(time), { Brightness = 0 }):Play()
	task.delay(time + 0.05, function()
		p:Destroy()
	end)
end

local function popModel(plot: number, id: number)
	task.delay(0.06, function()
		local m = WorldFx.model(plot, id)
		if not m then
			return
		end
		local v = Instance.new("NumberValue")
		v.Value = 0.55
		local conn = v.Changed:Connect(function(s)
			if m.Parent then
				m:ScaleTo(math.max(0.05, s))
			end
		end)
		local tw = TweenService:Create(v, TweenInfo.new(0.42, Enum.EasingStyle.Back), { Value = 1 })
		tw:Play()
		tw.Completed:Once(function()
			conn:Disconnect()
			if m.Parent then
				m:ScaleTo(1)
			end
			v:Destroy()
		end)
	end)
end

-- ─── tips ──────────────────────────────────────────────────────────────────
local function tipKey(plot: number, id: number): string
	return plot .. ":" .. id
end

local function addTip(plot: number, e: any)
	local key = tipKey(plot, e.id)
	if tips[key] then
		return
	end
	local m = Actors.coin(e.golden == true)
	m:SetAttribute("Plot", plot)
	m:SetAttribute("TipId", e.id)
	local pos = at(plot, e.x, e.z, 0)
	m:PivotTo(CFrame.new(pos + Vector3.new(0, 1.6, 0)))
	m.Parent = tipFolder
	tips[key] = { model = m, pos = pos, t = math.random() * 3 }
	Audio.at("pop", pos, 1.3, 0.5)
	if e.golden then
		WorldFx.puff(pos + Vector3.new(0, 2, 0), Palette.gold, 30, 1.2)
	end
end

local function removeTip(plot: number, e: any)
	local key = tipKey(plot, e.id)
	local tip = tips[key]
	if not tip then
		return
	end
	tips[key] = nil
	local m = tip.model
	if e.by == me() then
		local root = myRoot()
		Audio.play("coin", 1 + math.random() * 0.2)
		if root then
			local start = m:GetPivot()
			local v = Instance.new("NumberValue")
			v.Value = 0
			v.Changed:Connect(function(a)
				if m.Parent and root.Parent then
					local target = root.Position + Vector3.new(0, 1.5, 0)
					m:PivotTo(CFrame.new(start.Position:Lerp(target, a) + Vector3.new(0, math.sin(a * math.pi) * 3, 0)))
				end
			end)
			local tw = TweenService:Create(v, TweenInfo.new(0.35, Enum.EasingStyle.Quad, Enum.EasingDirection.In), { Value = 1 })
			tw:Play()
			tw.Completed:Once(function()
				m:Destroy()
				v:Destroy()
			end)
			WorldFx.floatText(root.Position + Vector3.new(0, 3, 0), "+" .. tostring(e.value) .. " 🪙", Palette.ui.gold, 28)
			return
		end
	elseif e.by == 0 and isMine(plot) and (e.value or 0) > 0 then
		WorldFx.floatText(tip.pos + Vector3.new(0, 2, 0), "+" .. tostring(e.value) .. " 🪙", Palette.ui.gold, 20)
	end
	for _, p in m:GetDescendants() do
		if p:IsA("BasePart") then
			TweenService:Create(p, TweenInfo.new(0.3), { Transparency = 1 }):Play()
		end
	end
	task.delay(0.35, function()
		m:Destroy()
	end)
end

-- ─── the event handlers ────────────────────────────────────────────────────
local handlers: { [string]: (number, any) -> () } = {}

handlers.say = function(plot, e)
	Entities.say(plot, e.id, e.text)
end

handlers.leave = function(plot, e)
	if e.mood == 1 then
		Entities.emote(plot, e.id, e.kind == "goldbun" and "🌟" or "💛")
	elseif e.mood == -1 and math.random() < 0.5 then
		Entities.emote(plot, e.id, "😞")
	end
end

handlers.tip = addTip
handlers.tipGone = removeTip

handlers.sale = function(plot, e)
	local pos = modelTop(plot, e.obj)
	if pos then
		WorldFx.floatText(pos, "+" .. e.price .. " 🪙", Palette.ui.gold, e.helper == me() and 30 or 24)
		if isMine(plot) and throttle("sale", 0.25) then
			Audio.at("coin", pos, 1.1, 0.8)
		end
		if e.helper == me() then
			WorldFx.puff(pos, Palette.gold, 8, 0.6)
		end
	end
end

handlers.produce = function(plot, e)
	if not isMine(plot) or not throttle("prod" .. e.obj, 6) then
		return
	end
	local pos = modelTop(plot, e.obj)
	local g = Catalog.Goods[e.goods]
	if pos and g then
		WorldFx.floatText(pos, "+" .. e.n .. " " .. g.icon, Color3.fromRGB(g.color[1], g.color[2], g.color[3]), 20, 2.5)
	end
end

handlers.placed = function(plot, e)
	popModel(plot, e.obj)
	task.delay(0.08, function()
		local m = WorldFx.model(plot, e.obj)
		if m then
			local pos = m:GetPivot().Position
			WorldFx.puff(pos + Vector3.new(0, 1, 0), Palette.stone, 14, 1.6, true)
			Audio.at("hammer", pos, 1, 0.8)
		end
	end)
end

handlers.moved = function(plot, e)
	popModel(plot, e.obj)
end

handlers.restyled = function(plot, e)
	popModel(plot, e.obj)
end

handlers.upgraded = function(plot, e)
	popModel(plot, e.obj)
	task.delay(0.08, function()
		local pos = modelTop(plot, e.obj)
		if pos then
			WorldFx.puff(pos, Palette.gold, 30, 1)
			Audio.at("achievement", pos)
		end
	end)
end

handlers.removed = function(plot, e)
	local _ = e
	if isMine(plot) then
		Audio.play("remove")
	end
end

handlers.painted = function(plot, e)
	if throttle("paint", 0.08) then
		local pos = at(plot, e.x + 0.5, e.z + 0.5, 0.5)
		WorldFx.puff(pos, Palette.path[1], 5, 0.8, true)
		Audio.at("place", pos, 1.4, 0.4)
	end
end

handlers.snuff = function(plot, e)
	local pos = modelTop(plot, e.obj)
	if pos then
		WorldFx.puff(pos, Palette.veilDeep, 22, 2.2, true)
		Audio.at("gloom", pos, 0.7)
	end
end

handlers.relight = function(plot, e)
	local pos = modelTop(plot, e.obj)
	if pos then
		WorldFx.puff(pos, Palette.lantern, 24, 0.8)
		Audio.at("sparkle", pos)
	end
end

handlers.ripe = function(plot, e)
	if isMine(plot) and throttle("ripe", 3) then
		local pos = modelTop(plot, e.obj)
		if pos then
			Audio.at("sparkle", pos, 1.2, 0.6)
		end
	end
end

handlers.tend = function(plot, e)
	local pos = modelTop(plot, e.obj)
	if pos then
		WorldFx.puff(pos, Color3.fromRGB(255, 236, 140), 26, 1)
		Audio.at("tend", pos)
		if (e.n or 0) > 0 then
			WorldFx.floatText(pos, "+" .. e.n .. " 🧺", Color3.fromRGB(180, 230, 120), 26)
		end
	end
end

handlers.gloomSpawn = function(plot, e)
	local pos = at(plot, e.x, e.z, 2)
	WorldFx.puff(pos, Palette.veil, 18, 3, true)
	if throttle("gspawn", 1.5) then
		Audio.at("gloom", pos, 0.8, 0.8)
	end
end

handlers.hit = function(plot, e)
	Entities.flash(plot, e.id)
	local pos = at(plot, e.x, e.z, 4)
	local mine = e.by == me()
	WorldFx.floatText(pos, tostring(e.dmg), e.crit and Palette.ui.gold or Color3.new(1, 1, 1), e.crit and 34 or 24, 3)
	WorldFx.puff(pos, e.crit and Palette.gold or Palette.lantern, e.crit and 18 or 8, 0.7)
	Audio.at("hit", pos, e.crit and 0.8 or 1.1)
	if mine then
		Shake.add(e.crit and 0.45 or 0.18)
	end
end

handlers.die = function(plot, e)
	local pos = Entities.kill(plot, e.id) or at(plot, e.x, e.z, 2)
	WorldFx.puff(pos + Vector3.new(0, 2, 0), Palette.veil, 26, 2.6, true)
	WorldFx.puff(pos + Vector3.new(0, 2, 0), Palette.lumen, 20, 0.9)
	Audio.at("poof", pos)
	if e.by == me() and (e.lumen or 0) > 0 then
		local root = myRoot()
		if root then
			beam(pos + Vector3.new(0, 2, 0), root.Position + Vector3.new(0, 1, 0), Palette.lumen, 0.5, 0.25)
			WorldFx.floatText(root.Position + Vector3.new(0, 3.5, 0), "+" .. e.lumen .. " 💠", Palette.ui.lumen, 28)
			Audio.play("pickup", 1.2)
		end
	end
end

handlers.gloomFade = function(plot, e)
	local pos = Entities.kill(plot, e.id)
	if pos then
		WorldFx.puff(pos + Vector3.new(0, 2, 0), Palette.veil, 12, 2, true)
	end
end

handlers.bolt = function(plot, e)
	local m = WorldFx.model(plot, e.obj)
	local from = m and m:GetPivot().Position + Vector3.new(0, 15.6, 0)
	if from then
		local to = at(plot, e.x, e.z, 2.2)
		beam(from, to, Palette.lumen, 0.8, 0.18)
		WorldFx.puff(to, Palette.lumen, 10, 0.8)
		Audio.at("hit", to, 1.5, 0.6)
	end
end

handlers.swing = function(_plot, e)
	local p = game:GetService("Players"):GetPlayerByUserId(e.by)
	local char = p and p.Character
	local root = char and char:FindFirstChild("HumanoidRootPart")
	if root and root:IsA("BasePart") then
		Audio.at("swing", root.Position, e.combo == 3 and 0.8 or 1)
	end
end

handlers.burst = function(plot, e)
	local pos: Vector3
	if plot == 0 then
		local root = myRoot()
		if not root then
			return
		end
		pos = root.Position
	else
		pos = at(plot, e.x, e.z, 2)
	end
	ring(pos, Config.BURST_RADIUS, Palette.lantern, 0.55)
	WorldFx.puff(pos, Palette.gold, 40, 1.4)
	Audio.at("burst", pos)
	local root = myRoot()
	if root and (root.Position - pos).Magnitude < 70 then
		Shake.add(0.7)
	end
end

handlers.touch = function(plot, e)
	if e.player == me() then
		Audio.play("hurt")
		Shake.add(0.35)
		State.toast.fire("", nil, "hurt")
		local root = myRoot()
		local from = Entities.worldPos(plot, e.id)
		if root and from then
			local away = Vector3.new(root.Position.X - from.X, 0, root.Position.Z - from.Z)
			if away.Magnitude > 0.1 then
				root.AssemblyLinearVelocity += away.Unit * 28 + Vector3.new(0, 18, 0)
			end
		end
	end
end

handlers.flee = function(plot, e)
	local _ = plot
	local _2 = e
end

handlers.settle = function(plot, e)
	local pos = at(plot, Grid.HEART_X, Grid.HEART_Z + 2, 3)
	WorldFx.puff(pos, Palette.flowers[1], 30, 1)
	if isMine(plot) then
		Audio.play("notify")
	end
	local _ = e
end

handlers.surge = function(plot, _e)
	local pos = at(plot, Grid.HEART_X, Grid.HEART_Z, 6)
	ring(pos, 120, Palette.veil, 1.6)
	Audio.play("gloom", 0.5, 1.5)
	Shake.add(0.5)
end

handlers.surgeWon = function(plot, _e)
	if isMine(plot) then
		Audio.play("achievement")
	end
end

handlers.tier = function(plot, e)
	local tier = e.tier
	local before = Grid.makeTerrain(Catalog.Heartflame[math.max(1, tier - 1)].radius)
	local after = Grid.makeTerrain(Catalog.Heartflame[tier].radius)
	local n = 0
	for i = 1, Grid.W * Grid.H do
		if Grid.hasTree(before, i) and not Grid.hasTree(after, i) then
			n += 1
			if n <= 90 then
				local x, z = Grid.fromIdx(i)
				local delay = Grid.distToHeart(x, z) * 0.06
				task.delay(delay, function()
					WorldFx.puff(at(plot, x + 0.5, z + 0.5, 4), Palette.leaf[1], 10, 2.2, true)
				end)
			end
		end
	end
	local pos = at(plot, Grid.HEART_X, Grid.HEART_Z, 5)
	ring(pos, Catalog.Heartflame[tier].radius * TILE, Palette.flame, 1.4)
	WorldFx.puff(pos + Vector3.new(0, 4, 0), Palette.flame, 60, 1.6)
	Audio.play("rankup")
	Shake.add(1)
end

function WorldFx.handle(plot: number, events: { any })
	for _, e in events do
		local h = if typeof(e) == "table" then handlers[e.k] else nil
		if h then
			local handler = h :: (number, any) -> ()
			local ok, err = pcall(function()
				handler(plot, e)
			end)
			if not ok then
				warn("[Kingsbloom] fx " .. tostring(e.k) .. ": " .. tostring(err))
			end
		end
	end
end

-- ─── clicking coins ────────────────────────────────────────────────────────
local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Include
params.FilterDescendantsInstances = { tipFolder }

local function tryCollect(screen: Vector2, isMouse: boolean)
	local cam = Workspace.CurrentCamera
	local ray = isMouse and cam:ViewportPointToRay(screen.X, screen.Y) or cam:ScreenPointToRay(screen.X, screen.Y)
	local hit = Workspace:Raycast(ray.Origin, ray.Direction * 600, params)
	if not hit then
		return
	end
	local m = hit.Instance:FindFirstAncestorOfClass("Model")
	local plot = m and m:GetAttribute("Plot")
	local id = m and m:GetAttribute("TipId")
	if typeof(plot) == "number" and typeof(id) == "number" then
		task.spawn(State.request, "collect", { p = plot, id = id })
	end
end

function WorldFx.start()
	local root = Workspace:WaitForChild("Kingsbloom")
	local plots = root:WaitForChild("Plots")
	for i = 1, Config.PLOT_COUNT do
		local f = plots:WaitForChild("Plot" .. i)
		watchPlot(i, f:WaitForChild("Buildings"))
	end
	RunService.RenderStepped:Connect(function(dt)
		for _, tip in tips do
			tip.t += dt
			local m = tip.model
			m:PivotTo(CFrame.new(tip.pos + Vector3.new(0, 1.7 + math.sin(tip.t * 3) * 0.3, 0)) * CFrame.Angles(0, tip.t * 2.6, 0) * CFrame.Angles(math.pi / 2, 0, 0))
		end
	end)
	UserInputService.InputBegan:Connect(function(input, processed)
		if processed then
			return
		end
		if input.UserInputType == Enum.UserInputType.MouseButton1 then
			tryCollect(UserInputService:GetMouseLocation(), true)
		elseif input.UserInputType == Enum.UserInputType.Touch then
			tryCollect(Vector2.new(input.Position.X, input.Position.Y), false)
		end
	end)
end

return WorldFx
