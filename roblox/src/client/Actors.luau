--!strict
-- Client-side models for everything that moves: visitors, settlers, Veilkin and Gloomlings, plus
-- tip coins. They're plain anchored parts posed every frame (cheap, no physics, no Humanoids).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Codec = require(Shared.Codec)
local Models = require(Shared.Models)
local Palette = require(Shared.Palette)

local Actors = {}

local M = Enum.Material
local rgb = Color3.fromRGB

export type Actor = {
	model: Model,
	parts: { BasePart },
	offsets: { CFrame },
	legs: { number },
	arms: { number },
	head: BasePart,
	height: number,
	style: string, -- "person" | "hop" | "float"
	light: PointLight?,
}

local SKIN = { rgb(255, 224, 196), rgb(241, 194, 158), rgb(198, 140, 100), rgb(150, 100, 70), rgb(255, 210, 180) }
local HAIR = { rgb(60, 40, 30), rgb(120, 80, 40), rgb(230, 200, 120), rgb(180, 70, 40), rgb(40, 40, 50) }

local function part(model: Model, a: Actor, shape: string, size: Vector3, offset: CFrame, color: Color3, material: Enum.Material?): Part
	local p: Part
	if shape == "ball" then
		p = Models.ball(model, size.X, CFrame.new(), color, material or M.SmoothPlastic, false)
	elseif shape == "blob" then
		p = Models.blob(model, size, CFrame.new(), color, material or M.SmoothPlastic, false)
	else
		p = Models.box(model, size, CFrame.new(), color, material or M.SmoothPlastic, false)
	end
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = size.Magnitude > 1.2
	table.insert(a.parts, p)
	table.insert(a.offsets, offset)
	return p
end

local function newActor(name: string, style: string, height: number): (Model, Actor)
	local m = Instance.new("Model")
	m.Name = name
	local a: Actor = {
		model = m,
		parts = {},
		offsets = {},
		legs = {},
		arms = {},
		head = (nil :: any) :: BasePart,
		height = height,
		style = style,
		light = nil,
	}
	return m, a
end

local function pick<T>(list: { T }, i: number): T
	return list[(i % #list) + 1]
end

-- A little person. `coat` and `hat` vary by kind; `seed` varies skin, hair and tint.
local function person(kind: string, seed: number, settler: boolean): Actor
	local m, a = newActor(kind, "person", 4.3)
	local skin = pick(SKIN, seed)
	local hair = pick(HAIR, seed // 2)
	local coat = rgb(150, 110, 80)
	local trousers = rgb(80, 70, 70)
	if kind == "merchant" then
		coat = pick({ rgb(70, 130, 90), rgb(120, 80, 150), rgb(40, 100, 140) }, seed)
	elseif kind == "farmhand" then
		coat = pick({ rgb(90, 120, 170), rgb(170, 110, 70) }, seed)
		trousers = rgb(70, 90, 130)
	elseif kind == "monk" then
		coat = rgb(120, 130, 160)
		trousers = coat
	elseif kind == "knight" then
		coat = rgb(170, 176, 186)
		trousers = rgb(120, 126, 136)
	else
		coat = pick({ rgb(160, 100, 70), rgb(120, 90, 60), rgb(180, 140, 90), rgb(140, 70, 70) }, seed)
	end
	if settler then
		coat = coat:Lerp(rgb(240, 220, 170), 0.25)
	end
	local armor = kind == "knight" and M.Metal or M.SmoothPlastic
	for i, x in { -0.3, 0.3 } do
		part(m, a, "box", Vector3.new(0.45, 1.1, 0.45), CFrame.new(x, 1.1, 0), trousers, armor)
		table.insert(a.legs, #a.parts)
		local _ = i
	end
	if kind == "monk" then
		part(m, a, "box", Vector3.new(1.4, 2.2, 1), CFrame.new(0, 1.5, 0), coat, M.Fabric)
	else
		part(m, a, "box", Vector3.new(1.3, 1.5, 0.9), CFrame.new(0, 1.85, 0), coat, kind == "knight" and M.Metal or M.Fabric)
	end
	for _, x in { -0.85, 0.85 } do
		part(m, a, "box", Vector3.new(0.35, 1.1, 0.35), CFrame.new(x, 2.5, 0), coat, armor)
		table.insert(a.arms, #a.parts)
	end
	a.head = part(m, a, "ball", Vector3.new(1.3, 1.3, 1.3), CFrame.new(0, 3.25, 0), skin)
	part(m, a, "ball", Vector3.new(0.18, 0.18, 0.18), CFrame.new(-0.24, 3.32, -0.6), rgb(30, 24, 20))
	part(m, a, "ball", Vector3.new(0.18, 0.18, 0.18), CFrame.new(0.24, 3.32, -0.6), rgb(30, 24, 20))
	if kind == "farmhand" then
		part(m, a, "box", Vector3.new(2, 0.12, 2), CFrame.new(0, 3.85, 0), Palette.thatch, M.Fabric)
		part(m, a, "box", Vector3.new(0.9, 0.5, 0.9), CFrame.new(0, 4.1, 0), Palette.thatch, M.Fabric)
	elseif kind == "merchant" then
		part(m, a, "box", Vector3.new(1.5, 0.12, 1.5), CFrame.new(0, 3.85, 0), rgb(50, 40, 40), M.Fabric)
		part(m, a, "box", Vector3.new(0.95, 0.7, 0.95), CFrame.new(0, 4.2, 0), rgb(50, 40, 40), M.Fabric)
		part(m, a, "box", Vector3.new(0.9, 0.9, 0.5), CFrame.new(0.55, 1.6, 0.55), rgb(120, 80, 50), M.Leather)
	elseif kind == "monk" then
		part(m, a, "blob", Vector3.new(1.5, 1.4, 1.5), CFrame.new(0, 3.4, 0.1), coat, M.Fabric)
		local lantern = part(m, a, "box", Vector3.new(0.45, 0.6, 0.45), CFrame.new(0.95, 1.8, -0.35), Palette.lantern, M.Neon)
		local l = Instance.new("PointLight")
		l.Range = 11
		l.Brightness = 1.2
		l.Color = Palette.lantern
		l.Parent = lantern
		a.light = l
	elseif kind == "knight" then
		part(m, a, "box", Vector3.new(1.35, 0.5, 1.35), CFrame.new(0, 3.75, 0), rgb(170, 176, 186), M.Metal)
		part(m, a, "box", Vector3.new(0.2, 0.9, 1), CFrame.new(0, 4.3, 0.1), rgb(200, 50, 60), M.Fabric)
		part(m, a, "box", Vector3.new(1.1, 1.3, 0.2), CFrame.new(0, 1.9, 0.55), rgb(60, 80, 150), M.Metal)
	else
		part(m, a, "blob", Vector3.new(1.35, 0.7, 1.35), CFrame.new(0, 3.72, 0.08), hair)
		part(m, a, "box", Vector3.new(0.9, 1, 0.5), CFrame.new(0, 1.9, 0.62), rgb(120, 90, 60), M.Fabric)
	end
	if settler then
		part(m, a, "box", Vector3.new(1.32, 0.25, 0.92), CFrame.new(0, 1.55, 0), rgb(240, 220, 170), M.Fabric)
	end
	return a
end

local function critter(kind: string, seed: number): Actor
	local m, a = newActor(kind, "hop", 2.4)
	local body = rgb(110, 170, 90)
	local glow = false
	if kind == "puddlepup" then
		body = rgb(110, 170, 210)
	elseif kind == "emberkit" then
		body = rgb(240, 140, 60)
		glow = true
	elseif kind == "goldbun" then
		body = Palette.gold
		glow = true
	end
	local mat = kind == "goldbun" and M.Metal or M.SmoothPlastic
	a.head = part(m, a, "blob", Vector3.new(1.9, 1.5, 1.9), CFrame.new(0, 0.8, 0), body, kind == "mossbun" and M.Grass or mat)
	part(m, a, "ball", Vector3.new(0.22, 0.22, 0.22), CFrame.new(-0.35, 1.05, -0.85), rgb(20, 20, 26))
	part(m, a, "ball", Vector3.new(0.22, 0.22, 0.22), CFrame.new(0.35, 1.05, -0.85), rgb(20, 20, 26))
	if kind == "puddlepup" then
		part(m, a, "blob", Vector3.new(0.35, 0.8, 0.5), CFrame.new(-0.7, 1.3, 0) * CFrame.Angles(0, 0, 0.6), body:Lerp(rgb(0, 0, 0), 0.2))
		part(m, a, "blob", Vector3.new(0.35, 0.8, 0.5), CFrame.new(0.7, 1.3, 0) * CFrame.Angles(0, 0, -0.6), body:Lerp(rgb(0, 0, 0), 0.2))
		part(m, a, "blob", Vector3.new(0.3, 0.3, 0.9), CFrame.new(0, 1, 1) * CFrame.Angles(0.6, 0, 0), body)
	elseif kind == "emberkit" then
		part(m, a, "box", Vector3.new(0.4, 0.5, 0.2), CFrame.new(-0.5, 1.6, 0) * CFrame.Angles(0, 0, 0.3), body)
		part(m, a, "box", Vector3.new(0.4, 0.5, 0.2), CFrame.new(0.5, 1.6, 0) * CFrame.Angles(0, 0, -0.3), body)
		part(m, a, "blob", Vector3.new(0.3, 0.3, 1.2), CFrame.new(0, 1.1, 1.1) * CFrame.Angles(-0.8, 0, 0), rgb(255, 200, 80), M.Neon)
	else
		part(m, a, "blob", Vector3.new(0.4, 1.2, 0.3), CFrame.new(-0.35, 1.8, 0.1), body)
		part(m, a, "blob", Vector3.new(0.4, 1.2, 0.3), CFrame.new(0.35, 1.8, 0.1), body)
		if kind == "mossbun" then
			part(m, a, "blob", Vector3.new(0.6, 0.2, 0.4), CFrame.new(0.2, 1.62, -0.2) * CFrame.Angles(0, 0, 0.4), rgb(80, 150, 70))
		end
	end
	if glow then
		local l = Instance.new("PointLight")
		l.Range = kind == "goldbun" and 12 or 9
		l.Brightness = 1
		l.Color = kind == "goldbun" and Palette.gold or Palette.flame
		l.Parent = a.head
		a.light = l
		Models.emitter(a.head, {
			rate = 6,
			lifetime = NumberRange.new(0.6, 1.2),
			speed = NumberRange.new(0.5, 1.5),
			spread = Vector2.new(180, 180),
			size = Models.seq(0.25, 0),
			color = ColorSequence.new(kind == "goldbun" and Palette.gold or Palette.flame),
		})
	end
	local _ = seed
	return a
end

local function gloomling(seed: number, surge: boolean): Actor
	local scale = surge and 1.35 or 1
	local m, a = newActor("Gloomling", "float", 3 * scale)
	a.head = part(m, a, "ball", Vector3.new(2.3, 2.3, 2.3) * scale, CFrame.new(0, 2, 0), Palette.gloom)
	a.head.Transparency = 0.1
	local shell = part(m, a, "ball", Vector3.new(2.9, 2.9, 2.9) * scale, CFrame.new(0, 2, 0), Palette.veil, M.ForceField)
	shell.CastShadow = false
	local eye = surge and rgb(255, 90, 110) or Palette.gloomEye
	part(m, a, "ball", Vector3.new(0.42, 0.42, 0.42) * scale, CFrame.new(-0.42 * scale, 2.2, -1.05 * scale), eye, M.Neon)
	part(m, a, "ball", Vector3.new(0.42, 0.42, 0.42) * scale, CFrame.new(0.42 * scale, 2.2, -1.05 * scale), eye, M.Neon)
	part(m, a, "blob", Vector3.new(1.2, 1.6, 1.2) * scale, CFrame.new(0, 0.9, 0.5), Palette.gloom)
	local l = Instance.new("PointLight")
	l.Range = 9
	l.Brightness = 0.9
	l.Color = eye
	l.Parent = a.head
	a.light = l
	Models.emitter(a.head, {
		texture = "rbxasset://textures/particles/smoke_main.dds",
		rate = 10,
		lifetime = NumberRange.new(0.8, 1.4),
		speed = NumberRange.new(0.5, 1.2),
		spread = Vector2.new(180, 180),
		size = Models.seq(1.4 * scale, 2.6 * scale),
		transparency = Models.seq(0.4, 1),
		color = ColorSequence.new(Palette.veilDeep),
		emission = 0,
		influence = 0.5,
	})
	local _ = seed
	return a
end

function Actors.build(kindCode: number, info: number): Actor
	if kindCode == Codec.GLOOM then
		return gloomling(info, info >= 64 and info % 128 >= 64)
	end
	local settler = kindCode >= Codec.SETTLER_BASE and kindCode < Codec.GLOOM
	local index = settler and kindCode - Codec.SETTLER_BASE or kindCode
	local kind = Catalog.VisitorOrder[index] or "traveler"
	local seed = settler and (info // 8) or (info // 64)
	local def = Catalog.Visitors[kind]
	if def and def.creature then
		return critter(kind, seed)
	end
	return person(kind, seed + index, settler)
end

-- Poses every part of an actor around `cf` (its feet), with a walk cycle phase `t` and swing amount.
function Actors.pose(a: Actor, cf: CFrame, t: number, swing: number, parts: { BasePart }, cframes: { CFrame })
	local bob = 0
	if a.style == "hop" then
		bob = math.abs(math.sin(t * 2)) * 0.7 * swing
	elseif a.style == "float" then
		bob = 0.3 + math.sin(t * 0.6) * 0.3
	else
		bob = math.abs(math.sin(t * 2)) * 0.12 * swing
	end
	local base = cf * CFrame.new(0, bob, 0)
	for i, p in a.parts do
		local off = a.offsets[i]
		local legPos = table.find(a.legs, i)
		local armPos = table.find(a.arms, i)
		if legPos then
			local s = math.sin(t * 2 + (legPos == 1 and 0 or math.pi)) * 0.7 * swing
			off = CFrame.new(off.X, off.Y, off.Z) * CFrame.Angles(s, 0, 0) * CFrame.new(0, -0.55, 0)
		elseif armPos then
			local s = math.sin(t * 2 + (armPos == 1 and math.pi or 0)) * 0.6 * swing
			off = CFrame.new(off.X, off.Y + 0.5, off.Z) * CFrame.Angles(s, 0, 0) * CFrame.new(0, -0.5, 0)
		end
		table.insert(parts, p)
		table.insert(cframes, base * off)
	end
end

-- ─── tips ──────────────────────────────────────────────────────────────────
function Actors.coin(golden: boolean): Model
	local m = Instance.new("Model")
	m.Name = "Tip"
	local size = golden and 2.2 or 1.6
	local coin = Models.cyl(m, 0.3, size, CFrame.new(), Palette.gold, M.Metal, false)
	coin.Name = "Coin"
	coin.CanQuery = true
	coin.CanTouch = false
	coin.CastShadow = true
	local rim = Models.cyl(m, 0.32, size * 0.7, CFrame.new(), rgb(255, 230, 140), M.Neon, false)
	rim.CanQuery = false
	rim.CanTouch = false
	Models.emitter(coin, {
		rate = golden and 8 or 3,
		lifetime = NumberRange.new(0.6, 1.1),
		speed = NumberRange.new(0.5, 1.2),
		spread = Vector2.new(180, 180),
		size = Models.seq(golden and 0.5 or 0.3, 0),
		color = ColorSequence.new(Palette.gold),
	})
	m.PrimaryPart = coin
	return m
end

return Actors
