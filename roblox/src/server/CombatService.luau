--!strict
-- The Lantern Staff and the Radiant Burst. The staff is a Tool (so the default Animate script plays
-- its slash) whose lantern also lights the dark around you. Hits are decided here, on the server,
-- against the Gloomlings of the plot you're standing on.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local StarterPack = game:GetService("StarterPack")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local Layout = require(Shared.Layout)
local Net = require(Shared.Net)
local Palette = require(Shared.Palette)

local PlotService = require(script.Parent.PlotService)
local ProgressService = require(script.Parent.ProgressService)

local CombatService = {}

local TILE = Config.TILE
local remotes = Net.get()
local lastSwing: { [Player]: number } = {}
local combo: { [Player]: number } = {}
local lastBurst: { [Player]: number } = {}

local function weld(a: BasePart, b: BasePart)
	local w = Instance.new("WeldConstraint")
	w.Part0 = a
	w.Part1 = b
	w.Parent = a
end

local function toolPart(tool: Tool, handle: BasePart, size: Vector3, offset: CFrame, color: Color3, material: Enum.Material, shape: Enum.PartType?): Part
	local p = Instance.new("Part")
	if shape then
		p.Shape = shape
	end
	p.Size = size
	p.CFrame = handle.CFrame * offset
	p.Color = color
	p.Material = material
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Massless = true
	p.Anchored = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = tool
	weld(handle, p)
	return p
end

local function makeStaff(): Tool
	local tool = Instance.new("Tool")
	tool.Name = "LanternStaff"
	tool.ToolTip = "Lantern Staff"
	tool.CanBeDropped = false
	tool.RequiresHandle = true
	-- Held like a sword: the lantern end (+z of the handle) points up out of the fist.
	tool.Grip = CFrame.fromMatrix(Vector3.new(0, 0, -1.5), Vector3.new(0, 1, 0), Vector3.new(0, 0, 1), Vector3.new(1, 0, 0))

	local handle = Instance.new("Part")
	handle.Name = "Handle"
	handle.Size = Vector3.new(0.4, 0.4, 6)
	handle.CFrame = CFrame.new()
	handle.Color = Palette.woodDark
	handle.Material = Enum.Material.Wood
	handle.CanCollide = false
	handle.CanQuery = false
	handle.Massless = true
	handle.TopSurface = Enum.SurfaceType.Smooth
	handle.BottomSurface = Enum.SurfaceType.Smooth
	handle.Parent = tool

	toolPart(tool, handle, Vector3.new(0.6, 0.6, 0.5), CFrame.new(0, 0, 2.7), Palette.gold, Enum.Material.Metal)
	toolPart(tool, handle, Vector3.new(0.18, 1.6, 0.18), CFrame.new(0, 0, 3.6) * CFrame.Angles(math.pi / 2, 0, 0), Palette.gold, Enum.Material.Metal)
	local lantern = toolPart(tool, handle, Vector3.new(1.1, 1.1, 1.1), CFrame.new(0, 0, 3.6), Palette.lantern, Enum.Material.Neon, Enum.PartType.Ball)
	lantern.Name = "Lantern"
	toolPart(tool, handle, Vector3.new(0.35, 0.35, 0.35), CFrame.new(0, 0, -3.05), Palette.gold, Enum.Material.Metal, Enum.PartType.Ball)

	local light = Instance.new("PointLight")
	light.Range = 16
	light.Brightness = 1.4
	light.Color = Palette.lantern
	light.Parent = lantern

	local a0 = Instance.new("Attachment")
	a0.Name = "TrailA"
	a0.Position = Vector3.new(0, 0, 1)
	a0.Parent = handle
	local a1 = Instance.new("Attachment")
	a1.Name = "TrailB"
	a1.Position = Vector3.new(0, 0, 4.2)
	a1.Parent = handle
	local trail = Instance.new("Trail")
	trail.Name = "SwingTrail"
	trail.Attachment0 = a0
	trail.Attachment1 = a1
	trail.Lifetime = 0.2
	trail.Color = ColorSequence.new(Palette.gold, Palette.white)
	trail.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.1), NumberSequenceKeypoint.new(1, 1) })
	trail.LightEmission = 1
	trail.FaceCamera = true
	trail.Enabled = false
	trail.Parent = handle

	local sparks = Instance.new("ParticleEmitter")
	sparks.Texture = "rbxasset://textures/particles/sparkles_main.dds"
	sparks.Rate = 3
	sparks.Lifetime = NumberRange.new(0.6, 1.2)
	sparks.Speed = NumberRange.new(0.5, 1.5)
	sparks.SpreadAngle = Vector2.new(180, 180)
	sparks.Size = NumberSequence.new(0.3, 0)
	sparks.Color = ColorSequence.new(Palette.lantern)
	sparks.LightEmission = 1
	sparks.Parent = lantern
	return tool
end

local function flashTrail(char: Model)
	local tool = char:FindFirstChild("LanternStaff")
	local handle = tool and tool:FindFirstChild("Handle")
	local trail = handle and handle:FindFirstChild("SwingTrail")
	if trail and trail:IsA("Trail") then
		trail.Enabled = true
		task.delay(0.28, function()
			if trail.Parent then
				trail.Enabled = false
			end
		end)
	end
end

local function rootOf(player: Player): (BasePart?, Model?)
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	local hrp = char and char:FindFirstChild("HumanoidRootPart")
	if not char or not hum or hum.Health <= 0 or not hrp or not hrp:IsA("BasePart") then
		return nil, nil
	end
	return hrp, char
end

local function levelMult(player: Player): number
	local p = ProgressService.profile(player)
	return 1 + ((p and p.level or 1) - 1) * 0.03
end

local function broadcast(plot: any, fx: { any }, except: Player?)
	for _, p in plot.viewers do
		if p ~= except and p.Parent then
			remotes.Fx:FireClient(p, plot.index, fx)
		end
	end
end

local function onSwing(player: Player, targetId: any)
	local hrp, char = rootOf(player)
	if not hrp or not char or not char:FindFirstChild("LanternStaff") then
		return
	end
	local now = os.clock()
	if now - (lastSwing[player] or 0) < Config.STAFF_COOLDOWN - 0.1 then
		return
	end
	local gap = now - (lastSwing[player] or 0)
	lastSwing[player] = now
	local c = (gap < 0.95 and (combo[player] or 0) % 3 or 0) + 1
	combo[player] = c
	flashTrail(char)
	local plot, px, pz = PlotService.plotAt(hrp.Position)
	if not plot or not plot.sim then
		return
	end
	local sim = plot.sim
	local finisher = c == 3
	local look = hrp.CFrame.LookVector
	local aim = Vector3.new(look.X, 0, look.Z).Unit
	-- Aim at the Gloomling the client picked, if it's really in reach.
	if typeof(targetId) == "number" then
		local g = sim:gloomById(targetId)
		if g then
			local gp = Layout.toWorld(plot.cf, g.x, g.z, hrp.Position.Y)
			local d = gp - hrp.Position
			if d.Magnitude <= Config.STAFF_RANGE + 3 and d.Magnitude > 0.1 then
				aim = Vector3.new(d.X, 0, d.Z).Unit
			end
		end
	end
	local dmg = Config.STAFF_DAMAGE * levelMult(player) * (finisher and Config.COMBO_FINISHER_MULT or 1)
	local range = Config.STAFF_RANGE + (finisher and 3 or 0)
	local hits = 0
	local list: { any } = table.clone(sim.gloom)
	for _, g in list do
		local gp = Layout.toWorld(plot.cf, g.x, g.z, hrp.Position.Y)
		local d = gp - hrp.Position
		local flat = Vector3.new(d.X, 0, d.Z)
		local dist = flat.Magnitude
		if dist <= range and (dist < 3 or flat.Unit:Dot(aim) >= Config.STAFF_ARC) then
			hits += 1
			sim:damageGloom(g.id, math.floor(dmg + 0.5), player.UserId, px, pz, finisher)
		end
	end
	broadcast(plot, { { k = "swing", by = player.UserId, combo = c, hits = hits } }, player)
	PlotService.processEvents(plot)
end

local function onBurst(player: Player)
	local hrp = rootOf(player)
	if not hrp then
		return
	end
	local now = os.clock()
	if now - (lastBurst[player] or -100) < Config.BURST_COOLDOWN - 0.3 then
		return
	end
	lastBurst[player] = now
	local plot, px, pz = PlotService.plotAt(hrp.Position)
	local fx = { { k = "burst", by = player.UserId, x = px, z = pz } }
	if plot and plot.sim then
		local sim = plot.sim
		local r = Config.BURST_RADIUS / TILE
		local dmg = math.floor(Config.BURST_DAMAGE * levelMult(player) + 0.5)
		local list: { any } = table.clone(sim.gloom)
		for _, g in list do
			local dx, dz = g.x - px, g.z - pz
			if dx * dx + dz * dz <= r * r then
				sim:damageGloom(g.id, dmg, player.UserId, px, pz, true)
			end
		end
		-- The burst also rekindles snuffed lamps close by.
		for _, o in sim:snuffables() do
			if o.snuffed then
				local cx, cz = sim:objCentre(o)
				if (cx - px) ^ 2 + (cz - pz) ^ 2 <= r * r then
					sim:relight(o.id, player.UserId)
				end
			end
		end
		broadcast(plot, fx, nil)
		PlotService.processEvents(plot)
	else
		remotes.Fx:FireClient(player, 0, fx)
	end
end

function CombatService.start()
	local staff = makeStaff()
	staff.Parent = StarterPack
	-- Anyone already here gets one too.
	for _, p in Players:GetPlayers() do
		local bp = p:FindFirstChildOfClass("Backpack")
		if bp and not bp:FindFirstChild("LanternStaff") then
			staff:Clone().Parent = bp
		end
	end
	remotes.Swing.OnServerEvent:Connect(onSwing)
	remotes.Burst.OnServerEvent:Connect(onBurst)
	Players.PlayerRemoving:Connect(function(p)
		lastSwing[p] = nil
		combo[p] = nil
		lastBurst[p] = nil
	end)
end

return CombatService
