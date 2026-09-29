--!strict
-- Builds the world once at startup: terrain, the Royal Avenue and its plaza, the forest around
-- everything, each plot's Old Road and plaza, lighting and post-processing, and the Veil mist.

local Lighting = game:GetService("Lighting")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local Grid = require(Shared.Grid)
local Layout = require(Shared.Layout)
local Models = require(Shared.Models)
local Palette = require(Shared.Palette)

local World = {}

local TILE = Config.TILE
local M = Enum.Material
local terrain = Workspace.Terrain

local root: Folder
local plotsFolder: Folder

local function folder(name: string, parent: Instance): Folder
	local f = parent:FindFirstChild(name)
	if f and f:IsA("Folder") then
		return f
	end
	local nf = Instance.new("Folder")
	nf.Name = name
	nf.Parent = parent
	return nf
end

local function slab(parent: Instance, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material): Part
	local p = Models.box(parent, size, cf, color, material)
	p.CastShadow = false
	return p
end

-- ─── lighting ──────────────────────────────────────────────────────────────
local function setupLighting()
	Lighting.Brightness = 2.4
	Lighting.EnvironmentDiffuseScale = 1
	Lighting.EnvironmentSpecularScale = 0.6
	Lighting.GlobalShadows = true
	Lighting.ShadowSoftness = 0.25
	Lighting.GeographicLatitude = 30
	Lighting.Ambient = Color3.fromRGB(70, 64, 80)
	Lighting.OutdoorAmbient = Color3.fromRGB(150, 140, 150)
	Lighting.ClockTime = 9

	for _, c in Lighting:GetChildren() do
		if c:IsA("PostEffect") or c:IsA("Atmosphere") or c:IsA("Sky") then
			c:Destroy()
		end
	end
	local atmosphere = Instance.new("Atmosphere")
	atmosphere.Density = 0.3
	atmosphere.Offset = 0.2
	atmosphere.Color = Color3.fromRGB(214, 206, 196)
	atmosphere.Decay = Color3.fromRGB(120, 110, 140)
	atmosphere.Glare = 0.2
	atmosphere.Haze = 1.4
	atmosphere.Parent = Lighting

	local sky = Instance.new("Sky")
	sky.SunAngularSize = 14
	sky.MoonAngularSize = 9
	sky.StarCount = 3000
	sky.CelestialBodiesShown = true
	sky.Parent = Lighting

	local bloom = Instance.new("BloomEffect")
	bloom.Intensity = 0.7
	bloom.Size = 28
	bloom.Threshold = 1.4
	bloom.Parent = Lighting

	local cc = Instance.new("ColorCorrectionEffect")
	cc.Name = "Grade"
	cc.Brightness = 0.02
	cc.Contrast = 0.08
	cc.Saturation = 0.14
	cc.TintColor = Color3.fromRGB(255, 248, 236)
	cc.Parent = Lighting

	local rays = Instance.new("SunRaysEffect")
	rays.Intensity = 0.04
	rays.Spread = 0.6
	rays.Parent = Lighting

	local clouds = terrain:FindFirstChildOfClass("Clouds") or Instance.new("Clouds")
	clouds.Cover = 0.45
	clouds.Density = 0.5
	clouds.Color = Color3.fromRGB(255, 250, 244)
	clouds.Parent = terrain
end

-- ─── terrain ───────────────────────────────────────────────────────────────
local function fill(cx: number, cz: number, sx: number, sz: number, material: Enum.Material, top: number?, depth: number?)
	local t = top or 0
	local d = depth or 12
	terrain:FillBlock(CFrame.new(cx, t - d / 2, cz), Vector3.new(sx, d, sz), material)
end

local function carvePond(i: number)
	local cf = Layout.plotCFrame(i)
	local p = Grid.POND
	local cx = (p.x0 + p.x1 + 1) / 2 * TILE
	local cz = (p.z0 + p.z1 + 1) / 2 * TILE
	local size = Vector3.new((p.x1 - p.x0 + 1) * TILE, 8, (p.z1 - p.z0 + 1) * TILE)
	local centre = cf * CFrame.new(cx, -4, cz)
	terrain:FillBlock(centre, size, M.Air)
	terrain:FillBlock(centre * CFrame.new(0, -0.5, 0), size - Vector3.new(0, 1, 0), M.Water)
	terrain:FillBlock(centre * CFrame.new(0, -7, 0), Vector3.new(size.X + 8, 2, size.Z + 8), M.Mud)
end

-- Grass inside the realm, forest floor outside it.
function World.paintRealm(i: number, radiusTiles: number)
	local cf = Layout.plotCFrame(i)
	local centre = cf * CFrame.new(Layout.PLOT_SIZE / 2, -2, Layout.PLOT_SIZE / 2)
	terrain:FillBlock(centre, Vector3.new(Layout.PLOT_SIZE, 4, Layout.PLOT_SIZE), M.LeafyGrass)
	local heart = cf * CFrame.new(Grid.HEART_X * TILE, -2, Grid.HEART_Z * TILE)
	terrain:FillCylinder(heart, 4, radiusTiles * TILE + 2, M.Grass)
	carvePond(i)
end

local function setupTerrain()
	terrain:SetMaterialColor(M.Grass, Palette.grass)
	terrain:SetMaterialColor(M.LeafyGrass, Palette.forestFloor)
	terrain:SetMaterialColor(M.Cobblestone, Palette.cobble)
	terrain:SetMaterialColor(M.Ground, Palette.road)
	terrain:SetMaterialColor(M.Mud, Palette.soilWet)
	terrain.WaterColor = Palette.water
	terrain.WaterTransparency = 0.35
	terrain.WaterReflectance = 0.6
	terrain.WaterWaveSize = 0.06
	terrain.WaterWaveSpeed = 6
	terrain:Clear()
	local x0, x1 = Layout.WORLD_X[1] - Layout.MARGIN, Layout.WORLD_X[2] + Layout.MARGIN
	local z0, z1 = Layout.WORLD_Z[1] - Layout.MARGIN, Layout.WORLD_Z[2] + Layout.MARGIN
	fill((x0 + x1) / 2, (z0 + z1) / 2, x1 - x0, z1 - z0, M.LeafyGrass, 0, 16)
	-- the Royal Avenue: grass verges and a cobbled road
	fill(2, 0, Layout.WORLD_X[2] - Layout.WORLD_X[1] + 24, Layout.AVENUE_HALF * 2, M.Grass, 0, 4)
	fill(2, 0, Layout.WORLD_X[2] - Layout.WORLD_X[1] + 24, 48, M.Cobblestone, 0, 4)
	terrain:FillCylinder(CFrame.new(Layout.HUB.X, -2, Layout.HUB.Z), 4, 44, M.Cobblestone)
	for i = 1, Config.PLOT_COUNT do
		World.paintRealm(i, 7.5)
	end
end

-- ─── the plots' fixed ground: the Old Road, the plaza, the gate ────────────
local function buildPlotGround(i: number)
	local cf = Layout.plotCFrame(i)
	local f = folder("Plot" .. i, plotsFolder)
	f:SetAttribute("Index", i)
	local ground = folder("Ground", f)
	ground:ClearAllChildren()
	local hx, hz = Grid.HEART_TILE.x, Grid.HEART_TILE.z
	local ex = Grid.ENTRANCE.x
	-- the Old Road, running out onto the avenue
	local roadZ0, roadZ1 = hz + 4, Config.PLOT_H + 2
	local road = slab(ground, Vector3.new(2 * TILE, 0.4, (roadZ1 - roadZ0) * TILE), cf * CFrame.new(ex * TILE, 0.02, (roadZ0 + roadZ1) / 2 * TILE), Palette.road, M.Ground)
	road.Name = "OldRoad"
	-- the plaza ring around the Heartflame
	local function plaza(x0: number, z0: number, x1: number, z1: number)
		local p = slab(ground, Vector3.new((x1 - x0) * TILE, 0.44, (z1 - z0) * TILE), cf * CFrame.new((x0 + x1) / 2 * TILE, 0.04, (z0 + z1) / 2 * TILE), Palette.stone, M.Cobblestone)
		p.Name = "Plaza"
	end
	plaza(hx - 2, hz - 2, hx + 4, hz)
	plaza(hx - 2, hz + 2, hx + 4, hz + 4)
	plaza(hx - 2, hz, hx, hz + 2)
	plaza(hx + 2, hz, hx + 4, hz + 2)
	-- the gate: two posts and a sign over the road
	local gate = folder("Gate", f)
	gate:ClearAllChildren()
	local gz = Config.PLOT_H * TILE - 1
	for _, gx in { (ex - 1.35) * TILE, (ex + 1.35) * TILE } do
		Models.box(gate, Vector3.new(1.4, 13, 1.4), cf * CFrame.new(gx, 6.5, gz), Palette.woodDark, M.Wood)
		Models.ball(gate, 1.6, cf * CFrame.new(gx, 13.6, gz), Palette.gold, M.Metal)
	end
	local beam = Models.box(gate, Vector3.new(19, 1.2, 1), cf * CFrame.new(ex * TILE, 12, gz), Palette.woodDark, M.Wood)
	beam.Name = "Beam"
	local board = Models.box(gate, Vector3.new(14, 3.6, 0.5), cf * CFrame.new(ex * TILE, 9.6, gz), Palette.woodLight, M.WoodPlanks)
	board.Name = "Sign"
	local gui = Instance.new("SurfaceGui")
	gui.Name = "SignGui"
	gui.Face = Enum.NormalId.Back -- faces the avenue (+z local)
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 36
	gui.LightInfluence = 0.2
	gui.Parent = board
	local label = Instance.new("TextLabel")
	label.Name = "Title"
	label.BackgroundTransparency = 1
	label.Size = UDim2.fromScale(1, 0.62)
	label.Font = Enum.Font.FredokaOne
	label.TextScaled = true
	label.TextColor3 = Palette.ui.ink
	label.Text = "A Free Clearing"
	label.Parent = gui
	local sub = Instance.new("TextLabel")
	sub.Name = "Sub"
	sub.BackgroundTransparency = 1
	sub.Position = UDim2.fromScale(0, 0.6)
	sub.Size = UDim2.fromScale(1, 0.36)
	sub.Font = Enum.Font.FredokaOne
	sub.TextScaled = true
	sub.TextColor3 = Palette.ui.inkSoft
	sub.Text = "Waiting for a Sovereign"
	sub.Parent = gui
	local lantern = Models.box(gate, Vector3.new(1, 1.3, 1), cf * CFrame.new(ex * TILE, 10.6, gz + 1.2), Palette.lantern, M.Neon)
	lantern.CanCollide = false
	local l = Instance.new("PointLight")
	l.Range = 18
	l.Brightness = 1.4
	l.Color = Palette.lantern
	l.Parent = lantern
	folder("Buildings", f)
	folder("Paths", f)
	folder("Trees", f)
end

-- ─── the hub ───────────────────────────────────────────────────────────────
local function sign(parent: Instance, cf: CFrame, size: Vector3, title: string, body: string): Part
	for _, x in { -size.X / 2 + 0.6, size.X / 2 - 0.6 } do
		Models.box(parent, Vector3.new(0.9, size.Y + 4, 0.9), cf * CFrame.new(x, (size.Y + 4) / 2, 0), Palette.woodDark, M.Wood)
	end
	local board = Models.box(parent, size, cf * CFrame.new(0, 4 + size.Y / 2, 0), Palette.woodLight, M.WoodPlanks)
	Models.box(parent, Vector3.new(size.X + 1, 0.6, size.Z + 0.6), cf * CFrame.new(0, 4.3 + size.Y, 0), Palette.roof[1], M.RoofShingles)
	local gui = Instance.new("SurfaceGui")
	gui.Name = "Board"
	gui.Face = Enum.NormalId.Front
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 30
	gui.LightInfluence = 0.2
	gui.Parent = board
	local head = Instance.new("TextLabel")
	head.Name = "Title"
	head.BackgroundTransparency = 1
	head.Size = UDim2.new(1, 0, 0.2, 0)
	head.Font = Enum.Font.GrenzeGotisch
	head.TextScaled = true
	head.TextColor3 = Palette.ui.royalDeep
	head.Text = title
	head.Parent = gui
	local text = Instance.new("TextLabel")
	text.Name = "Body"
	text.BackgroundTransparency = 1
	text.Position = UDim2.new(0.05, 0, 0.22, 0)
	text.Size = UDim2.new(0.9, 0, 0.74, 0)
	text.Font = Enum.Font.FredokaOne
	text.TextScaled = true
	text.TextWrapped = true
	text.TextXAlignment = Enum.TextXAlignment.Left
	text.TextYAlignment = Enum.TextYAlignment.Top
	text.TextColor3 = Palette.ui.ink
	text.RichText = true
	text.Text = body
	text.Parent = gui
	return board
end

local function buildHub()
	local hub = folder("Hub", root)
	hub:ClearAllChildren()
	local centre = Layout.HUB
	local fountain = Models.build("fountain", 0, nil)
	local hit = fountain:FindFirstChild("Hitbox")
	if hit then
		hit:Destroy()
	end
	fountain:ScaleTo(1.9)
	fountain:PivotTo(CFrame.new(centre))
	fountain.Parent = hub
	-- the Royal Ledger (top Sovereigns in this kingdom) and the welcome board
	local ledger = sign(hub, CFrame.new(centre + Vector3.new(34, 0, 0)) * CFrame.Angles(0, math.pi / 2, 0), Vector3.new(16, 10, 0.6), "Royal Ledger", "")
	ledger.Name = "LedgerBoard"
	sign(
		hub,
		CFrame.new(centre + Vector3.new(-30, 0, 0)) * CFrame.Angles(0, -math.pi / 2, 0),
		Vector3.new(16, 10, 0.6),
		"Kingsbloom",
		"<b>Build</b> your market, <b>light</b> the road.\nBy night the <b>Veil</b> sends Gloomlings: swing your <b>Lantern Staff</b>!\n🔨 B  Build   ⚔️ Click  Swing   ✨ Q  Burst"
	)
	-- lamps and greenery along the avenue, leaving the gates clear
	local gates = {}
	for i = 1, 3 do
		table.insert(gates, Layout.plotCFrame(i).Position.X + Grid.ENTRANCE.x * TILE)
	end
	local function nearGate(x: number): boolean
		for _, gx in gates do
			if math.abs(x - gx) < 16 then
				return true
			end
		end
		return false
	end
	local n = 0
	for x = Layout.WORLD_X[1] + 6, Layout.WORLD_X[2] - 6, 26 do
		if not nearGate(x) and math.abs(x - centre.X) > 46 then
			for _, z in { -27, 27 } do
				n += 1
				local lamp = Models.build("lamp", 0, nil)
				local hb = lamp:FindFirstChild("Hitbox")
				if hb then
					hb:Destroy()
				end
				lamp:ScaleTo(1.25)
				lamp:PivotTo(CFrame.new(x, 0, z) * CFrame.Angles(0, z > 0 and math.pi or 0, 0))
				lamp.Parent = hub
				local deco = Models.build(n % 3 == 0 and "tree" or "flowers", n, nil)
				local hb2 = deco:FindFirstChild("Hitbox")
				if hb2 then
					hb2:Destroy()
				end
				deco:PivotTo(CFrame.new(x + 12, 0, z + (z > 0 and 3 or -3)))
				deco.Parent = hub
			end
		end
	end
	for k = 0, 5 do
		local a = k * math.pi / 3 + math.pi / 6
		local bench = Models.build("bench", 0, nil)
		local hb = bench:FindFirstChild("Hitbox")
		if hb then
			hb:Destroy()
		end
		local p = centre + Vector3.new(math.cos(a) * 22, 0, math.sin(a) * 22)
		bench:PivotTo(CFrame.lookAt(p, centre) * CFrame.Angles(0, math.pi, 0))
		bench.Parent = hub
	end
	local spawn = Instance.new("SpawnLocation")
	spawn.Name = "HubSpawn"
	spawn.Anchored = true
	spawn.Size = Vector3.new(8, 1, 8)
	spawn.CFrame = CFrame.new(Layout.SPAWN - Vector3.new(0, 3.4, 0))
	spawn.Transparency = 1
	spawn.CanCollide = false
	spawn.Neutral = true
	spawn.Duration = 0
	spawn.Parent = hub
end

-- ─── the forest around everything ──────────────────────────────────────────
local function insidePlot(x: number, z: number, pad: number): boolean
	for i = 1, Config.PLOT_COUNT do
		local tx, tz = Layout.toTile(Layout.plotCFrame(i), Vector3.new(x, 0, z))
		local p = pad / TILE
		if tx > -p and tz > -p and tx < Config.PLOT_W + p and tz < Config.PLOT_H + p then
			return true
		end
	end
	return false
end

local function buildForest()
	local forest = folder("Forest", root)
	forest:ClearAllChildren()
	local x0, x1 = Layout.WORLD_X[1] - Layout.MARGIN + 8, Layout.WORLD_X[2] + Layout.MARGIN - 8
	local z0, z1 = Layout.WORLD_Z[1] - Layout.MARGIN + 8, Layout.WORLD_Z[2] + Layout.MARGIN - 8
	local step = 17
	local gx = 0
	for x = x0, x1, step do
		gx += 1
		local gz = 0
		for z = z0, z1, step do
			gz += 1
			local h = Grid.hash(gx, gz, 11)
			local px = x + (Grid.hash(gx, gz, 12) - 0.5) * step * 0.8
			local pz = z + (Grid.hash(gx, gz, 13) - 0.5) * step * 0.8
			if h < 0.72 and math.abs(pz) > Layout.AVENUE_HALF + 4 and not insidePlot(px, pz, 3) then
				local tree = Models.forestTree(gx * 31 + gz, 1.3 + Grid.hash(gx, gz, 14) * 0.9)
				tree:PivotTo(CFrame.new(px, 0, pz) * CFrame.Angles(0, h * 20, 0))
				tree.Parent = forest
			end
		end
	end
	-- walls at the edge of the world
	local walls = folder("Walls", root)
	walls:ClearAllChildren()
	local wx0, wx1 = Layout.WORLD_X[1] - 40, Layout.WORLD_X[2] + 40
	local wz0, wz1 = Layout.WORLD_Z[1] - 40, Layout.WORLD_Z[2] + 40
	for _, w in {
		{ Vector3.new(4, 200, wz1 - wz0), Vector3.new(wx0, 100, 0) },
		{ Vector3.new(4, 200, wz1 - wz0), Vector3.new(wx1, 100, 0) },
		{ Vector3.new(wx1 - wx0, 200, 4), Vector3.new((wx0 + wx1) / 2, 100, wz0) },
		{ Vector3.new(wx1 - wx0, 200, 4), Vector3.new((wx0 + wx1) / 2, 100, wz1) },
	} do
		local p = Models.box(walls, w[1], CFrame.new(w[2]), Palette.white, M.SmoothPlastic)
		p.Transparency = 1
		p.CastShadow = false
	end
	-- the Veil's mist, woken at night by DayNight
	local mist = folder("VeilMist", root)
	mist:ClearAllChildren()
	for k = 0, 15 do
		local a = k / 16 * math.pi * 2
		local pos = Vector3.new(math.cos(a) * 360 + 2, 2, math.sin(a) * 250)
		local anchor = Models.box(mist, Vector3.new(60, 1, 60), CFrame.new(pos), Palette.veil, M.SmoothPlastic, false)
		anchor.Transparency = 1
		anchor.CanQuery = false
		anchor.CastShadow = false
		local e = Models.emitter(anchor, {
			texture = "rbxasset://textures/particles/smoke_main.dds",
			rate = 4,
			lifetime = NumberRange.new(8, 12),
			speed = NumberRange.new(0.5, 1.5),
			spread = Vector2.new(180, 10),
			size = Models.seq(14, 24),
			transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.3, 0.8), NumberSequenceKeypoint.new(1, 1) }),
			color = ColorSequence.new(Palette.veil),
			emission = 0.2,
			influence = 0.4,
			enabled = false,
		})
		e.Shape = Enum.ParticleEmitterShape.Box
		e.Name = "Mist"
	end
end

function World.plotFolder(i: number): Folder
	return folder("Plot" .. i, plotsFolder)
end

function World.root(): Folder
	return root
end

function World.build()
	root = folder("Kingsbloom", Workspace)
	plotsFolder = folder("Plots", root)
	setupLighting()
	setupTerrain()
	for i = 1, Config.PLOT_COUNT do
		buildPlotGround(i)
	end
	buildHub()
	buildForest()
end

return World
