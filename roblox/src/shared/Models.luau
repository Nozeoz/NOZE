--!strict
-- Procedural models for every building, built from ordinary Parts so the game needs no uploaded assets.
-- Each model is built around its footprint centre on the ground (y = 0), front facing +z, then pivoted
-- into place. Light sources are Neon parts named "Glow" holding a PointLight named "Light".
-- To use your own art instead, put a Model with the building's id in ReplicatedStorage.Assets;
-- it's cloned in place of the procedural one (same pivot rules).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Catalog = require(script.Parent.Catalog)
local Palette = require(script.Parent.Palette)
local Config = require(script.Parent.Config)

local Models = {}

local TILE = Config.TILE
local M = Enum.Material
local rgb = Color3.fromRGB
local PI = math.pi

export type Extra = { level: number?, goods: string?, tier: number?, snuffed: boolean? }

-- ─── helpers ───────────────────────────────────────────────────────────────
local function finish(p: BasePart, parent: Instance, color: Color3, material: Enum.Material?, collide: boolean?)
	p.Anchored = true
	p.Color = color
	p.Material = material or M.SmoothPlastic
	p.CanCollide = collide ~= false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = parent
end

local function box(parent: Instance, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material?, collide: boolean?): Part
	local p = Instance.new("Part")
	p.Size = size
	p.CFrame = cf
	finish(p, parent, color, material, collide)
	return p
end
Models.box = box

local function ball(parent: Instance, d: number, cf: CFrame, color: Color3, material: Enum.Material?, collide: boolean?): Part
	local p = Instance.new("Part")
	p.Shape = Enum.PartType.Ball
	p.Size = Vector3.new(d, d, d)
	p.CFrame = cf
	finish(p, parent, color, material, collide)
	return p
end
Models.ball = ball

-- A squashed or stretched sphere (a sphere mesh on a block keeps the collision box simple).
local function blob(parent: Instance, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material?, collide: boolean?): Part
	local p = box(parent, size, cf, color, material, collide)
	local mesh = Instance.new("SpecialMesh")
	mesh.MeshType = Enum.MeshType.Sphere
	mesh.Parent = p
	return p
end
Models.blob = blob

-- An upright cylinder: height along y.
local function cyl(parent: Instance, height: number, d: number, cf: CFrame, color: Color3, material: Enum.Material?, collide: boolean?): Part
	local p = Instance.new("Part")
	p.Shape = Enum.PartType.Cylinder
	p.Size = Vector3.new(height, d, d)
	p.CFrame = cf * CFrame.Angles(0, 0, PI / 2)
	finish(p, parent, color, material, collide)
	return p
end
Models.cyl = cyl

-- A horizontal cylinder along x.
local function rod(parent: Instance, length: number, d: number, cf: CFrame, color: Color3, material: Enum.Material?, collide: boolean?): Part
	local p = Instance.new("Part")
	p.Shape = Enum.PartType.Cylinder
	p.Size = Vector3.new(length, d, d)
	p.CFrame = cf
	finish(p, parent, color, material, collide)
	return p
end

local function wedge(parent: Instance, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material?, collide: boolean?): WedgePart
	local p = Instance.new("WedgePart")
	p.Size = size
	p.CFrame = cf
	finish(p, parent, color, material, collide)
	return p
end

-- A gable roof whose ridge runs along local z: two wedges meeting at x = 0.
-- `cf` is the centre of the roof's base.
local function gable(parent: Instance, length: number, width: number, height: number, cf: CFrame, color: Color3, material: Enum.Material?)
	wedge(parent, Vector3.new(length, height, width / 2), cf * CFrame.new(-width / 4, height / 2, 0) * CFrame.Angles(0, -PI / 2, 0), color, material)
	wedge(parent, Vector3.new(length, height, width / 2), cf * CFrame.new(width / 4, height / 2, 0) * CFrame.Angles(0, PI / 2, 0), color, material)
end
Models.gable = gable

local function light(part: BasePart, range: number, brightness: number, color: Color3, shadows: boolean?): PointLight
	local l = Instance.new("PointLight")
	l.Name = "Light"
	l.Range = range
	l.Brightness = brightness
	l.Color = color
	l.Shadows = shadows == true
	l.Parent = part
	return l
end

-- A Neon light source that Gloomlings can snuff.
local function glow(parent: Instance, part: BasePart, radiusTiles: number, color: Color3?, brightness: number?)
	part.Name = "Glow"
	part.Material = M.Neon
	part.CanCollide = false
	light(part, radiusTiles * TILE, brightness or 1.6, color or Palette.lantern, false)
end

local function seq(a: number, b: number): NumberSequence
	return NumberSequence.new({ NumberSequenceKeypoint.new(0, a), NumberSequenceKeypoint.new(1, b) })
end
Models.seq = seq

local function emitter(parent: Instance, props: { [string]: any }): ParticleEmitter
	local e = Instance.new("ParticleEmitter")
	e.Texture = props.texture or "rbxasset://textures/particles/sparkles_main.dds"
	e.Rate = props.rate or 5
	e.Lifetime = props.lifetime or NumberRange.new(1, 2)
	e.Speed = props.speed or NumberRange.new(1, 2)
	e.SpreadAngle = props.spread or Vector2.new(30, 30)
	e.Size = props.size or seq(0.4, 0)
	e.Transparency = props.transparency or seq(0, 1)
	e.Color = props.color or ColorSequence.new(Palette.lantern)
	e.LightEmission = props.emission or 1
	e.LightInfluence = props.influence or 0
	e.Acceleration = props.accel or Vector3.zero
	e.Drag = props.drag or 0
	e.Rotation = props.rotation or NumberRange.new(0, 360)
	e.RotSpeed = props.rotSpeed or NumberRange.new(-30, 30)
	e.ZOffset = props.zOffset or 0
	e.Enabled = props.enabled ~= false
	e.LockedToPart = props.locked == true
	e.Parent = parent
	return e
end
Models.emitter = emitter

-- An invisible part the size of the footprint: the click target in Build mode.
local function hitbox(model: Model, w: number, d: number, h: number): Part
	local p = box(model, Vector3.new(w * TILE - 0.2, h, d * TILE - 0.2), CFrame.new(0, h / 2, 0), Palette.white, M.SmoothPlastic, false)
	p.Name = "Hitbox"
	p.Transparency = 1
	p.CastShadow = false
	return p
end

local function pick<T>(list: { T }, i: number): T
	return list[(i % #list) + 1]
end

-- ─── goods on display ──────────────────────────────────────────────────────
local function goodsProp(parent: Instance, goods: string, cf: CFrame)
	if goods == "harvest" then
		ball(parent, 1.1, cf * CFrame.new(0, 0.5, 0), rgb(236, 226, 240), M.SmoothPlastic, false)
		box(parent, Vector3.new(0.25, 0.9, 0.5), cf * CFrame.new(0, 1.3, 0) * CFrame.Angles(0, 0, 0.3), rgb(96, 160, 70), M.SmoothPlastic, false)
	elseif goods == "catch" then
		blob(parent, Vector3.new(1.6, 0.5, 0.7), cf * CFrame.new(0, 0.3, 0), rgb(140, 176, 196), M.SmoothPlastic, false)
		wedge(parent, Vector3.new(0.2, 0.6, 0.5), cf * CFrame.new(0.95, 0.3, 0) * CFrame.Angles(0, PI / 2, 0), rgb(120, 156, 176), M.SmoothPlastic, false)
	elseif goods == "grain" then
		blob(parent, Vector3.new(1.5, 0.8, 0.9), cf * CFrame.new(0, 0.4, 0), rgb(206, 150, 84), M.SmoothPlastic, false)
	else
		cyl(parent, 0.8, 1.3, cf * CFrame.new(0, 0.4, 0), rgb(90, 74, 66), M.Metal, false)
		cyl(parent, 0.1, 1.1, cf * CFrame.new(0, 0.82, 0), rgb(186, 104, 60), M.SmoothPlastic, false)
	end
end

-- ─── the buildings ─────────────────────────────────────────────────────────
local builders: { [string]: (Model, number, Extra) -> () } = {}

builders.heartflame = function(m, _v, extra)
	local tier = extra.tier or 1
	local stone, dark = Palette.stone, Palette.stoneDark
	cyl(m, 1.2, 11.4, CFrame.new(0, 0.6, 0), dark, M.Slate)
	cyl(m, 1, 9, CFrame.new(0, 1.7, 0), stone, M.Slate)
	local bowlY = 2.2
	if tier >= 2 then
		cyl(m, 4.2, 3, CFrame.new(0, 4.3, 0), stone, M.Slate)
		bowlY = 6.4
		for i = 0, 3 do
			local a = i * PI / 2 + PI / 4
			local p = CFrame.new(math.cos(a) * 4.4, 0, math.sin(a) * 4.4)
			cyl(m, 3, 0.9, p * CFrame.new(0, 3.7, 0), dark, M.Slate)
			local g = ball(m, 0.9, p * CFrame.new(0, 5.6, 0), Palette.lantern)
			glow(m, g, 1.2, Palette.lantern, 0.8)
		end
	end
	if tier >= 3 then
		for i = 0, 3 do
			local a = i * PI / 2
			local p = CFrame.new(math.cos(a) * 5, 0, math.sin(a) * 5)
			box(m, Vector3.new(1.2, 10, 1.2), p * CFrame.new(0, 5, 0), stone, M.Slate)
			box(m, Vector3.new(1.6, 0.6, 1.6), p * CFrame.new(0, 10.3, 0), Palette.gold, M.Metal)
		end
		cyl(m, 0.5, 12, CFrame.new(0, 10.4, 0), Palette.goldDeep, M.Metal, false).Transparency = 0.3
		bowlY = 7.2
	end
	if tier >= 4 then
		cyl(m, 6, 2.2, CFrame.new(0, 12, 0), Palette.plaster, M.Marble)
		cyl(m, 4, 1.4, CFrame.new(0, 17, 0), Palette.plaster, M.Marble)
		local sun = ball(m, 4.2, CFrame.new(0, 21.5, 0), Palette.gold)
		glow(m, sun, 3, Palette.gold, 2)
		emitter(sun, { rate = 12, lifetime = NumberRange.new(1.5, 2.5), speed = NumberRange.new(2, 4), spread = Vector2.new(180, 180), size = seq(0.6, 0), color = ColorSequence.new(Palette.gold) })
		for i = 0, 7 do
			local a = i * PI / 4
			local s = ball(m, 0.8, CFrame.new(math.cos(a) * 4.2, 21.5, math.sin(a) * 4.2), Palette.gold, M.Neon, false)
			s.Name = "Orbit"
		end
	end
	cyl(m, 1.8, 5.4, CFrame.new(0, bowlY + 0.9, 0), rgb(70, 60, 58), M.Metal)
	cyl(m, 0.4, 6, CFrame.new(0, bowlY + 1.8, 0), Palette.gold, M.Metal)
	local core = ball(m, 2.6, CFrame.new(0, bowlY + 2.6, 0), Palette.flame)
	core.Name = "Glow"
	core.Material = M.Neon
	core.CanCollide = false
	local def = Catalog.Heartflame[math.clamp(tier, 1, #Catalog.Heartflame)]
	light(core, def.light * TILE, 3, Palette.flame, true)
	local fire = Instance.new("Fire")
	fire.Size = 5 + tier
	fire.Heat = 9
	fire.Color = Palette.flame
	fire.SecondaryColor = rgb(255, 220, 120)
	fire.Parent = core
	emitter(core, {
		rate = 10,
		lifetime = NumberRange.new(1.2, 2.4),
		speed = NumberRange.new(3, 6),
		spread = Vector2.new(20, 20),
		size = seq(0.35, 0),
		color = ColorSequence.new(rgb(255, 200, 90), rgb(255, 120, 40)),
		accel = Vector3.new(0, 2, 0),
	})
end

builders.lamp = function(m, _v, _extra)
	box(m, Vector3.new(1.6, 0.6, 1.6), CFrame.new(0, 0.3, 0), Palette.stoneDark, M.Slate)
	box(m, Vector3.new(0.7, 9, 0.7), CFrame.new(0, 4.6, 0), Palette.woodDark, M.Wood)
	box(m, Vector3.new(2.4, 0.4, 0.4), CFrame.new(0.9, 8.7, 0), Palette.woodDark, M.Wood)
	box(m, Vector3.new(1.5, 0.35, 1.5), CFrame.new(1.8, 8.3, 0), rgb(60, 50, 46), M.Metal, false)
	local g = box(m, Vector3.new(1, 1.3, 1), CFrame.new(1.8, 7.45, 0), Palette.lantern, M.Neon, false)
	glow(m, g, (Catalog.Buildings.lamp.light :: number), Palette.lantern, 1.8)
	box(m, Vector3.new(1.2, 0.2, 1.2), CFrame.new(1.8, 6.75, 0), rgb(60, 50, 46), M.Metal, false)
end

builders.string = function(m, _v, _extra)
	local h = 9
	local a = Vector3.new(-2.6, h, -8.4)
	local b = Vector3.new(2.6, h, 8.4)
	box(m, Vector3.new(0.5, h, 0.5), CFrame.new(a.X, h / 2, a.Z), Palette.woodDark, M.Wood)
	box(m, Vector3.new(0.5, h, 0.5), CFrame.new(b.X, h / 2, b.Z), Palette.woodDark, M.Wood)
	local bulbs = 9
	local prev = a
	local colors = { Palette.lantern, rgb(255, 150, 120), rgb(255, 226, 140) }
	for i = 1, bulbs do
		local t = i / (bulbs + 1)
		local p = a:Lerp(b, t) - Vector3.new(0, math.sin(t * PI) * 1.6, 0)
		local seg = p - prev
		box(m, Vector3.new(0.08, 0.08, seg.Magnitude), CFrame.lookAt(prev + seg / 2, p), rgb(40, 34, 30), M.SmoothPlastic, false)
		prev = p
		local bulb = ball(m, 0.55, CFrame.new(p - Vector3.new(0, 0.35, 0)), pick(colors, i), M.Neon, false)
		if i == 2 or i == 5 or i == 8 then
			glow(m, bulb, 2.6, Palette.lantern, 1.2)
		end
	end
	local seg = b - prev
	box(m, Vector3.new(0.08, 0.08, seg.Magnitude), CFrame.lookAt(prev + seg / 2, b), rgb(40, 34, 30), M.SmoothPlastic, false)
end

builders.arch = function(m, _v, _extra)
	for _, z in { -6, 6 } do
		box(m, Vector3.new(2.2, 1, 2.2), CFrame.new(0, 0.5, z), Palette.stoneDark, M.Slate)
		box(m, Vector3.new(1.6, 11, 1.6), CFrame.new(0, 6, z), Palette.stone, M.Slate)
		box(m, Vector3.new(0.4, 0.4, 1.6), CFrame.new(1.1, 9.4, z), Palette.woodDark, M.Wood, false)
		local g = box(m, Vector3.new(0.9, 1.2, 0.9), CFrame.new(1.4, 8.4, z), Palette.lantern, M.Neon, false)
		glow(m, g, 3.4, Palette.lantern, 1.6)
		local g2 = box(m, Vector3.new(0.9, 1.2, 0.9), CFrame.new(-1.4, 8.4, z), Palette.lantern, M.Neon, false)
		g2.CanCollide = false
	end
	box(m, Vector3.new(2.4, 1.2, 16), CFrame.new(0, 12, 0), Palette.stone, M.Slate)
	box(m, Vector3.new(2.8, 0.5, 16.8), CFrame.new(0, 12.8, 0), Palette.roof[1], M.ClayRoofTiles)
	box(m, Vector3.new(0.3, 1.6, 5), CFrame.new(1.25, 12, 0), Palette.gold, M.Metal, false)
end

builders.stall = function(m, v, extra)
	local cloth = pick(Palette.cloth, v)
	local level = extra.level or 1
	local goods = extra.goods or "harvest"
	-- counter at the front (+z), shelf at the back
	box(m, Vector3.new(11, 3, 1.6), CFrame.new(0, 1.5, 2), Palette.woodLight, M.WoodPlanks)
	box(m, Vector3.new(11.6, 0.35, 2.2), CFrame.new(0, 3.15, 2), level >= 3 and Palette.gold or Palette.woodDark, level >= 3 and M.Metal or M.Wood)
	box(m, Vector3.new(11, 4.2, 1), CFrame.new(0, 2.1, -2.4), Palette.wood, M.WoodPlanks)
	for _, x in { -5.4, 5.4 } do
		for _, z in { -2.6, 2.6 } do
			box(m, Vector3.new(0.5, 7.6, 0.5), CFrame.new(x, 3.8, z), Palette.woodDark, M.Wood)
		end
	end
	-- a striped awning
	local tilt = CFrame.new(0, 8, 0.3) * CFrame.Angles(math.rad(14), 0, 0)
	box(m, Vector3.new(12.6, 0.3, 7.4), tilt, cloth, M.Fabric)
	for i = -2, 2, 2 do
		box(m, Vector3.new(1.6, 0.32, 7.42), tilt * CFrame.new(i * 2.4, 0.02, 0), Palette.plaster, M.Fabric, false)
	end
	if level >= 2 then
		for i = 0, 5 do
			local x = -5.5 + i * 2.2
			wedge(m, Vector3.new(0.1, 0.9, 0.9), CFrame.new(x, 6.9, 4.1) * CFrame.Angles(PI, PI / 2, 0), pick(Palette.cloth, i + v + 1), M.Fabric, false)
		end
	end
	-- goods on the counter
	for i = 0, 3 do
		goodsProp(m, goods, CFrame.new(-3.9 + i * 2.6, 3.3, 2))
	end
	-- the sign
	local sign = box(m, Vector3.new(3.4, 1.8, 0.3), CFrame.new(0, 10.1, 3.5), Palette.woodDark, M.Wood, false)
	local gui = Instance.new("SurfaceGui")
	gui.Face = Enum.NormalId.Front
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 40
	gui.LightInfluence = 0.3
	gui.Parent = sign
	local label = Instance.new("TextLabel")
	label.BackgroundTransparency = 1
	label.Size = UDim2.fromScale(1, 1)
	label.Text = (level >= 4 and "👑" or "") .. Catalog.Goods[goods].icon
	label.TextScaled = true
	label.Font = Enum.Font.FredokaOne
	label.TextColor3 = Palette.white
	label.Parent = gui
	box(m, Vector3.new(0.2, 1.2, 0.2), CFrame.new(-1.2, 9.2, 3.5), Palette.woodDark, M.Wood, false)
	box(m, Vector3.new(0.2, 1.2, 0.2), CFrame.new(1.2, 9.2, 3.5), Palette.woodDark, M.Wood, false)
	local g = box(m, Vector3.new(0.7, 0.9, 0.7), CFrame.new(5.4, 6.4, 3.1), Palette.lantern, M.Neon, false)
	glow(m, g, (Catalog.Buildings.stall.light :: number), Palette.lantern, 1.2)
end

local function field(m: Model, crop: string)
	box(m, Vector3.new(17.4, 0.6, 17.4), CFrame.new(0, 0.3, 0), Palette.soil, M.Ground)
	for r = 0, 3 do
		local z = -6.3 + r * 4.2
		box(m, Vector3.new(15.6, 0.5, 2.2), CFrame.new(0, 0.8, z), Palette.soilWet, M.Ground, false)
		for c = 0, 3 do
			local x = -5.7 + c * 3.8
			local cf = CFrame.new(x, 1.05, z)
			if crop == "wheat" then
				box(m, Vector3.new(0.35, 2.6, 0.35), cf * CFrame.new(0, 1.3, 0) * CFrame.Angles(0, 0, 0.08), rgb(196, 170, 90), M.SmoothPlastic, false).Name = "Crop"
				blob(m, Vector3.new(0.7, 1.4, 0.7), cf * CFrame.new(0.1, 2.9, 0), rgb(232, 196, 96), M.SmoothPlastic, false).Name = "Crop"
			else
				ball(m, 1.3, cf * CFrame.new(0, 0.35, 0), rgb(230, 214, 236), M.SmoothPlastic, false).Name = "Crop"
				blob(m, Vector3.new(1.6, 1.3, 0.5), cf * CFrame.new(0, 1.35, 0), rgb(96, 164, 72), M.SmoothPlastic, false).Name = "Crop"
			end
		end
	end
	for _, s in { -1, 1 } do
		box(m, Vector3.new(18, 0.35, 0.35), CFrame.new(0, 1.3, s * 8.8), Palette.wood, M.Wood, false)
		box(m, Vector3.new(0.35, 0.35, 18), CFrame.new(s * 8.8, 1.3, 0), Palette.wood, M.Wood, false)
		for _, t in { -1, 1 } do
			box(m, Vector3.new(0.6, 1.8, 0.6), CFrame.new(s * 8.8, 0.9, t * 8.8), Palette.woodDark, M.Wood)
		end
	end
	local sparkle = box(m, Vector3.new(16, 1, 16), CFrame.new(0, 2, 0), Palette.gold, M.SmoothPlastic, false)
	sparkle.Name = "Sparkle"
	sparkle.Transparency = 1
	sparkle.CanQuery = false
	sparkle.CastShadow = false
	local e = emitter(sparkle, {
		rate = 14,
		lifetime = NumberRange.new(0.8, 1.6),
		speed = NumberRange.new(0.5, 2),
		spread = Vector2.new(60, 60),
		size = seq(0.8, 0),
		color = ColorSequence.new(rgb(255, 236, 140)),
		accel = Vector3.new(0, 2, 0),
		enabled = false,
	})
	e.Name = "Ripe"
	e.Shape = Enum.ParticleEmitterShape.Box
end

builders.field_turnip = function(m, _v, _extra)
	field(m, "turnip")
end

builders.field_wheat = function(m, _v, _extra)
	field(m, "wheat")
end

builders.fishery = function(m, _v, _extra)
	for _, x in { -4.6, 4.6 } do
		for _, z in { -4.6, 4.6 } do
			box(m, Vector3.new(0.7, 2, 0.7), CFrame.new(x, 1, z), Palette.woodDark, M.Wood)
		end
	end
	box(m, Vector3.new(11, 0.5, 11), CFrame.new(0, 2.2, 0), Palette.woodLight, M.WoodPlanks)
	box(m, Vector3.new(7, 5, 6.5), CFrame.new(-1, 4.9, -1.5), Palette.wood, M.WoodPlanks)
	gable(m, 7.6, 8, 3, CFrame.new(-1, 7.4, -1.5) * CFrame.Angles(0, PI / 2, 0), Palette.roof[2], M.RoofShingles)
	box(m, Vector3.new(1.8, 3, 0.3), CFrame.new(-1, 3.9, 1.8), Palette.woodDark, M.Wood)
	box(m, Vector3.new(1, 1.4, 1), CFrame.new(3.6, 3.2, 3.2), rgb(120, 90, 60), M.Wood)
	rod(m, 7, 0.18, CFrame.new(4.2, 5.4, 1) * CFrame.Angles(0, PI / 4, math.rad(28)), Palette.woodDark, M.Wood, false)
	box(m, Vector3.new(3.6, 0.2, 0.2), CFrame.new(-3.4, 6.2, 2.8), Palette.woodDark, M.Wood, false)
	for i = 0, 1 do
		blob(m, Vector3.new(0.5, 1.4, 0.3), CFrame.new(-4.2 + i * 1.4, 5.3, 2.8), rgb(140, 176, 196), M.SmoothPlastic, false)
	end
	local g = box(m, Vector3.new(0.7, 0.9, 0.7), CFrame.new(1, 6, 1.9), Palette.lantern, M.Neon, false)
	glow(m, g, (Catalog.Buildings.fishery.light :: number), Palette.lantern, 1.2)
end

builders.granary = function(m, _v, _extra)
	box(m, Vector3.new(10.5, 1, 10.5), CFrame.new(0, 0.5, 0), Palette.stoneDark, M.Cobblestone)
	box(m, Vector3.new(9, 7, 9), CFrame.new(0, 4.5, 0), Palette.roof[1], M.WoodPlanks)
	for _, x in { -4.55, 4.55 } do
		box(m, Vector3.new(0.4, 7, 0.4), CFrame.new(x, 4.5, 4.55), Palette.plaster, M.Wood, false)
	end
	box(m, Vector3.new(9.2, 0.4, 0.4), CFrame.new(0, 4.8, 4.6), Palette.plaster, M.Wood, false)
	gable(m, 10, 10.4, 4, CFrame.new(0, 8, 0), Palette.woodDark, M.RoofShingles)
	box(m, Vector3.new(3.6, 4.6, 0.3), CFrame.new(0, 3.3, 4.6), Palette.woodDark, M.Wood)
	box(m, Vector3.new(2.4, 1.8, 1.8), CFrame.new(3.6, 0.9, 6), Palette.thatch, M.Fabric)
	box(m, Vector3.new(1.8, 1.8, 2.4), CFrame.new(-3.6, 0.9, 6), Palette.thatch, M.Fabric)
	local g = box(m, Vector3.new(0.6, 0.8, 0.6), CFrame.new(2.4, 6.4, 4.9), Palette.lantern, M.Neon, false)
	glow(m, g, (Catalog.Buildings.granary.light :: number), Palette.lantern, 1)
end

builders.cookhouse = function(m, _v, _extra)
	box(m, Vector3.new(15, 7, 7), CFrame.new(-1, 3.5, -2), Palette.stone, M.Cobblestone)
	gable(m, 16, 8, 3.6, CFrame.new(-1, 7, -2) * CFrame.Angles(0, PI / 2, 0), Palette.roof[1], M.ClayRoofTiles)
	local chimney = box(m, Vector3.new(1.8, 5, 1.8), CFrame.new(4.4, 9, -3.4), Palette.stoneDark, M.Brick)
	local smoke = Instance.new("Attachment")
	smoke.Position = Vector3.new(0, 2.6, 0)
	smoke.Parent = chimney
	emitter(smoke, {
		texture = "rbxasset://textures/particles/smoke_main.dds",
		rate = 3,
		lifetime = NumberRange.new(3, 5),
		speed = NumberRange.new(2, 3),
		spread = Vector2.new(10, 10),
		size = seq(1.4, 4),
		transparency = seq(0.5, 1),
		color = ColorSequence.new(rgb(200, 196, 190)),
		emission = 0,
		influence = 1,
		accel = Vector3.new(1, 0.5, 0),
	})
	box(m, Vector3.new(2.4, 4, 0.3), CFrame.new(-4, 2.4, 1.6), Palette.woodDark, M.Wood)
	box(m, Vector3.new(2, 1.8, 0.3), CFrame.new(1, 4, 1.6), rgb(255, 214, 140), M.Glass, false)
	-- the cauldron outside
	cyl(m, 2, 3, CFrame.new(4.8, 1.6, 3.2), rgb(62, 56, 54), M.Metal)
	cyl(m, 0.1, 2.6, CFrame.new(4.8, 2.62, 3.2), rgb(186, 104, 60), M.SmoothPlastic, false)
	local g = box(m, Vector3.new(1.6, 0.4, 1.6), CFrame.new(4.8, 0.3, 3.2), Palette.flame, M.Neon, false)
	glow(m, g, (Catalog.Buildings.cookhouse.light :: number), Palette.flame, 1.4)
	box(m, Vector3.new(5, 0.4, 2), CFrame.new(-2.6, 2.4, 3.6), Palette.woodLight, M.WoodPlanks)
	box(m, Vector3.new(0.4, 2.2, 1.8), CFrame.new(-4.8, 1.1, 3.6), Palette.woodDark, M.Wood)
	box(m, Vector3.new(0.4, 2.2, 1.8), CFrame.new(-0.4, 1.1, 3.6), Palette.woodDark, M.Wood)
end

builders.tent = function(m, v, _extra)
	local cloth = pick({ rgb(232, 220, 196), rgb(200, 170, 130), rgb(190, 90, 80) }, v)
	gable(m, 9, 9.6, 6, CFrame.new(0, 0, 0), cloth, M.Fabric)
	box(m, Vector3.new(2.2, 3.6, 0.2), CFrame.new(0, 1.8, 4.55), rgb(80, 60, 44), M.Fabric, false)
	rod(m, 10, 0.3, CFrame.new(0, 6.1, 0) * CFrame.Angles(0, PI / 2, 0), Palette.woodDark, M.Wood, false)
	local g = box(m, Vector3.new(0.5, 0.6, 0.5), CFrame.new(1.8, 1.6, 5.2), Palette.lantern, M.Neon, false)
	glow(m, g, (Catalog.Buildings.tent.light :: number), Palette.lantern, 1)
end

local function house(m: Model, v: number, w: number, d: number, wallH: number, roofH: number)
	local walls = pick({ Palette.plaster, Palette.woodLight, rgb(214, 200, 176) }, v)
	local roof = pick(Palette.roof, v)
	box(m, Vector3.new(w + 0.6, 0.8, d + 0.6), CFrame.new(0, 0.4, 0), Palette.stoneDark, M.Cobblestone)
	box(m, Vector3.new(w, wallH, d), CFrame.new(0, 0.8 + wallH / 2, 0), walls, v % 3 == 1 and M.WoodPlanks or M.Plaster)
	for _, x in { -w / 2, w / 2 } do
		for _, z in { -d / 2, d / 2 } do
			box(m, Vector3.new(0.5, wallH, 0.5), CFrame.new(x, 0.8 + wallH / 2, z), Palette.woodDark, M.Wood, false)
		end
	end
	gable(m, w + 1.2, d + 1.4, roofH, CFrame.new(0, 0.8 + wallH, 0) * CFrame.Angles(0, PI / 2, 0), roof, M.RoofShingles)
	box(m, Vector3.new(2, 3.6, 0.3), CFrame.new(0, 2.6, d / 2 + 0.1), Palette.woodDark, M.Wood)
	local win = box(m, Vector3.new(1.6, 1.4, 0.3), CFrame.new(w / 2 - 1.8, 0.8 + wallH * 0.62, d / 2 + 0.1), rgb(255, 214, 140), M.Glass, false)
	light(win, 9, 0.8, Palette.lantern, false)
	return walls
end

builders.hut = function(m, v, _extra)
	house(m, v, 8.4, 8.4, 5, 3.6)
end

builders.cottage = function(m, v, _extra)
	house(m, v, 13.4, 12.4, 7, 5)
	box(m, Vector3.new(1.8, 5, 1.8), CFrame.new(-4, 12.2, -2), Palette.stoneDark, M.Brick)
	box(m, Vector3.new(1.6, 1.4, 0.3), CFrame.new(-4, 5.2, 6.3), rgb(255, 214, 140), M.Glass, false)
	box(m, Vector3.new(3, 0.5, 1.6), CFrame.new(0, 0.25, 7.4), Palette.stone, M.Slate)
	for i = 0, 2 do
		ball(m, 0.8, CFrame.new(3 + i * 1.1, 1.2, 6.8), pick(Palette.flowers, i + v), M.SmoothPlastic, false)
	end
end

builders.flowers = function(m, v, _extra)
	box(m, Vector3.new(5.2, 0.6, 5.2), CFrame.new(0, 0.3, 0), Palette.woodDark, M.Wood)
	box(m, Vector3.new(4.6, 0.7, 4.6), CFrame.new(0, 0.4, 0), Palette.soil, M.Ground, false)
	blob(m, Vector3.new(4.2, 1.4, 4.2), CFrame.new(0, 1, 0), rgb(92, 150, 74), M.Grass, false)
	local color = pick(Palette.flowers, v)
	local spots = { { -1.4, -1.2 }, { 1.2, -1.4 }, { 0, 0 }, { -1.2, 1.3 }, { 1.4, 1.1 }, { 0.2, -0.2 } }
	for i, s in spots do
		local c = i % 3 == 0 and pick(Palette.flowers, v + 1) or color
		ball(m, 0.95, CFrame.new(s[1], 1.75 + (i % 2) * 0.25, s[2]), c, M.SmoothPlastic, false)
	end
end

builders.hedge = function(m, _v, _extra)
	box(m, Vector3.new(5.6, 3, 5.6), CFrame.new(0, 1.5, 0), rgb(84, 140, 70), M.Grass)
	blob(m, Vector3.new(5.2, 1.4, 5.2), CFrame.new(0, 3, 0), rgb(96, 154, 76), M.Grass, false)
end

local function roundTree(m: Model, scale: number, color: Color3, seed: number)
	cyl(m, 5 * scale, 1.1 * scale, CFrame.new(0, 2.5 * scale, 0), Palette.trunk, M.Wood)
	ball(m, 6.2 * scale, CFrame.new(0, 6.6 * scale, 0), color, M.Grass, false)
	local a = seed * 2.1
	ball(m, 4 * scale, CFrame.new(math.cos(a) * 2 * scale, 5.4 * scale, math.sin(a) * 2 * scale), color:Lerp(Palette.white, 0.06), M.Grass, false)
end

local function pineTree(m: Model, scale: number, color: Color3)
	cyl(m, 3 * scale, 1 * scale, CFrame.new(0, 1.5 * scale, 0), Palette.trunk, M.Wood)
	blob(m, Vector3.new(6, 4.2, 6) * scale, CFrame.new(0, 4.6 * scale, 0), color, M.Grass, false)
	blob(m, Vector3.new(4.6, 3.6, 4.6) * scale, CFrame.new(0, 7.2 * scale, 0), color:Lerp(Palette.white, 0.05), M.Grass, false)
	blob(m, Vector3.new(2.8, 3, 2.8) * scale, CFrame.new(0, 9.4 * scale, 0), color:Lerp(Palette.white, 0.1), M.Grass, false)
end

builders.tree = function(m, v, _extra)
	if v == 1 then
		pineTree(m, 1, Palette.pine[1])
	elseif v == 2 then
		roundTree(m, 0.9, Palette.blossom, v)
	else
		roundTree(m, 0.9, Palette.leaf[1], v)
	end
end

builders.bench = function(m, _v, _extra)
	box(m, Vector3.new(4.6, 0.4, 1.7), CFrame.new(0, 1.9, 0.2), Palette.woodLight, M.WoodPlanks)
	box(m, Vector3.new(4.6, 1.6, 0.3), CFrame.new(0, 3, -0.6) * CFrame.Angles(math.rad(-10), 0, 0), Palette.woodLight, M.WoodPlanks)
	for _, x in { -2, 2 } do
		box(m, Vector3.new(0.35, 1.9, 1.7), CFrame.new(x, 0.95, 0.2), Palette.woodDark, M.Wood)
	end
end

builders.crates = function(m, v, _extra)
	box(m, Vector3.new(2.6, 2.6, 2.6), CFrame.new(-0.9, 1.3, -0.6) * CFrame.Angles(0, 0.2, 0), Palette.wood, M.WoodPlanks)
	box(m, Vector3.new(2, 2, 2), CFrame.new(1.2, 1, 0.8) * CFrame.Angles(0, -0.3, 0), Palette.woodLight, M.WoodPlanks)
	box(m, Vector3.new(1.8, 1.8, 1.8), CFrame.new(-0.8, 3.5, -0.5) * CFrame.Angles(0, 0.6, 0), Palette.woodLight, M.WoodPlanks)
	if v % 2 == 0 then
		cyl(m, 2.2, 1.6, CFrame.new(1.6, 1.1, -1.6), rgb(130, 92, 60), M.Wood)
	end
end

builders.banner = function(m, v, _extra)
	cyl(m, 10, 0.45, CFrame.new(0, 5, 0), Palette.woodDark, M.Wood)
	ball(m, 0.8, CFrame.new(0, 10.3, 0), Palette.gold, M.Metal)
	box(m, Vector3.new(3.4, 0.25, 0.25), CFrame.new(0, 9.4, 0.3), Palette.woodDark, M.Wood, false)
	local cloth = pick(Palette.cloth, v)
	box(m, Vector3.new(3, 4.6, 0.15), CFrame.new(0, 6.9, 0.35), cloth, M.Fabric, false)
	wedge(m, Vector3.new(0.15, 1, 1.5), CFrame.new(-0.75, 4.1, 0.35) * CFrame.Angles(PI, PI / 2, 0), cloth, M.Fabric, false)
	wedge(m, Vector3.new(0.15, 1, 1.5), CFrame.new(0.75, 4.1, 0.35) * CFrame.Angles(PI, -PI / 2, 0), cloth, M.Fabric, false)
	box(m, Vector3.new(1.2, 1.2, 0.2), CFrame.new(0, 7.3, 0.4) * CFrame.Angles(0, 0, PI / 4), Palette.gold, M.Metal, false)
end

builders.well = function(m, _v, _extra)
	cyl(m, 2.4, 4.8, CFrame.new(0, 1.2, 0), Palette.stone, M.Cobblestone)
	cyl(m, 0.2, 4, CFrame.new(0, 2.2, 0), Palette.water, M.Glass, false).Transparency = 0.2
	for _, x in { -2, 2 } do
		box(m, Vector3.new(0.4, 4.2, 0.4), CFrame.new(x, 4, 0), Palette.woodDark, M.Wood)
	end
	gable(m, 3, 5.6, 1.6, CFrame.new(0, 6.1, 0) * CFrame.Angles(0, PI / 2, 0), Palette.roof[1], M.RoofShingles)
	rod(m, 4, 0.3, CFrame.new(0, 5.2, 0), Palette.wood, M.Wood, false)
	cyl(m, 0.9, 0.9, CFrame.new(0.6, 3.6, 0), Palette.wood, M.Wood, false)
end

builders.fountain = function(m, _v, _extra)
	cyl(m, 1.8, 11.2, CFrame.new(0, 0.9, 0), Palette.stone, M.Marble)
	local w1 = cyl(m, 0.3, 10, CFrame.new(0, 1.7, 0), Palette.water, M.Glass, false)
	w1.Transparency = 0.25
	cyl(m, 4.6, 1.8, CFrame.new(0, 3.9, 0), Palette.stone, M.Marble)
	cyl(m, 0.9, 5.4, CFrame.new(0, 6.3, 0), Palette.stone, M.Marble)
	local w2 = cyl(m, 0.2, 4.6, CFrame.new(0, 6.8, 0), Palette.water, M.Glass, false)
	w2.Transparency = 0.25
	local top = ball(m, 1, CFrame.new(0, 7.4, 0), Palette.gold, M.Metal, false)
	emitter(top, {
		rate = 40,
		lifetime = NumberRange.new(0.8, 1.1),
		speed = NumberRange.new(7, 9),
		spread = Vector2.new(22, 22),
		size = seq(0.35, 0.2),
		transparency = seq(0.2, 1),
		color = ColorSequence.new(rgb(200, 236, 255)),
		emission = 0.3,
		influence = 1,
		accel = Vector3.new(0, -26, 0),
	})
end

builders.statue = function(m, _v, _extra)
	local marble = rgb(232, 228, 220)
	box(m, Vector3.new(8, 2.4, 8), CFrame.new(0, 1.2, 0), Palette.stoneDark, M.Marble)
	box(m, Vector3.new(6.6, 1, 6.6), CFrame.new(0, 2.9, 0), marble, M.Marble)
	box(m, Vector3.new(2.6, 5, 1.8), CFrame.new(0, 5.9, 0), marble, M.Marble)
	wedge(m, Vector3.new(3.4, 3, 1.2), CFrame.new(0, 4.9, 1.2), marble, M.Marble, false)
	box(m, Vector3.new(4, 1.2, 1.4), CFrame.new(0, 8.6, 0), marble, M.Marble)
	ball(m, 2, CFrame.new(0, 10.2, 0), marble, M.Marble)
	cyl(m, 0.7, 1.6, CFrame.new(0, 11.4, 0), Palette.gold, M.Metal, false)
	box(m, Vector3.new(0.4, 6, 0.4), CFrame.new(2.4, 7.6, 0.6), Palette.gold, M.Metal, false)
	ball(m, 0.8, CFrame.new(2.4, 10.8, 0.6), Palette.lumen, M.Neon, false)
	box(m, Vector3.new(3.4, 5.4, 0.3), CFrame.new(0, 6.4, -1.1), rgb(150, 50, 60), M.Fabric, false)
end

builders.tower = function(m, _v, _extra)
	box(m, Vector3.new(5.4, 1.6, 5.4), CFrame.new(0, 0.8, 0), Palette.stoneDark, M.Slate)
	cyl(m, 11, 3.8, CFrame.new(0, 7, 0), Palette.stone, M.Cobblestone)
	cyl(m, 1, 5.2, CFrame.new(0, 12.9, 0), Palette.stoneDark, M.Slate)
	for i = 0, 3 do
		local a = i * PI / 2
		box(m, Vector3.new(1, 1.4, 1), CFrame.new(math.cos(a) * 2.2, 14, math.sin(a) * 2.2), Palette.stone, M.Slate)
	end
	local crystal = box(m, Vector3.new(1.6, 1.6, 1.6), CFrame.new(0, 15.6, 0) * CFrame.Angles(PI / 4, 0, PI / 4), Palette.lumen, M.Neon, false)
	crystal.Name = "Glow"
	light(crystal, (Catalog.Buildings.tower.light :: number) * TILE, 2, Palette.lumen, false)
	emitter(crystal, { rate = 6, lifetime = NumberRange.new(1, 2), speed = NumberRange.new(0.5, 1.5), spread = Vector2.new(180, 180), size = seq(0.5, 0), color = ColorSequence.new(Palette.lumen) })
	crystal:SetAttribute("Spin", true)
end

-- ─── building a model ──────────────────────────────────────────────────────
local assets: Instance? = nil
local function assetFor(id: string): Model?
	if not assets then
		assets = ReplicatedStorage:FindFirstChild("Assets")
	end
	local a = assets and assets:FindFirstChild(id)
	if a and a:IsA("Model") then
		return a
	end
	return nil
end

function Models.build(id: string, variant: number?, extra: Extra?): Model
	local def = Catalog.Buildings[id]
	local m = Instance.new("Model")
	m.Name = id
	local custom = assetFor(id)
	local ex: Extra = extra or {}
	if custom then
		local c = custom:Clone()
		c:PivotTo(CFrame.new())
		for _, ch in c:GetChildren() do
			ch.Parent = m
		end
		c:Destroy()
	else
		local b = builders[id]
		if b then
			b(m, variant or 0, ex)
		end
	end
	if def then
		local h = (def.surface and 1) or 8
		hitbox(m, def.w, def.d, h)
	end
	m.WorldPivot = CFrame.new()
	if ex.snuffed then
		Models.setSnuffed(m, true)
	end
	return m
end

-- Put a lamp out (or relight it).
function Models.setSnuffed(m: Model, snuffed: boolean)
	for _, d in m:GetDescendants() do
		if d:IsA("BasePart") and d.Name == "Glow" then
			d.Material = snuffed and M.Glass or M.Neon
			d.Color = snuffed and rgb(70, 64, 84) or Palette.lantern
			local l = d:FindFirstChild("Light")
			if l and l:IsA("PointLight") then
				l.Enabled = not snuffed
			end
		end
	end
	m:SetAttribute("Snuffed", snuffed)
end

-- A forest tree for the wild land outside the realm (bigger and darker than the decor trees).
function Models.forestTree(seed: number, scale: number): Model
	local m = Instance.new("Model")
	m.Name = "WildTree"
	if seed % 5 < 3 then
		pineTree(m, scale, Palette.pine[(seed % #Palette.pine) + 1])
	else
		roundTree(m, scale, Palette.leaf[(seed % #Palette.leaf) + 1], seed)
	end
	m.WorldPivot = CFrame.new()
	return m
end

-- A painted path tile.
function Models.pathTile(parent: Instance, cf: CFrame, seed: number): Part
	local p = box(parent, Vector3.new(TILE, 0.4, TILE), cf, Palette.path[(seed % #Palette.path) + 1], M.Cobblestone)
	p.Name = "Path"
	return p
end

return Models
