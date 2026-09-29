--!strict
-- Draws every plot's visitors, settlers and Gloomlings from the server's snapshots: smooth
-- interpolation, walk cycles, speech bubbles, emotes and Gloomling health bars.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Codec = require(Shared.Codec)
local Layout = require(Shared.Layout)
local Palette = require(Shared.Palette)

local State = require(script.Parent.State)
local Actors = require(script.Parent.Actors)

local Entities = {}

type Ent = {
	id: number,
	plot: number,
	kind: number,
	info: number,
	actor: Actors.Actor,
	pos: Vector3,
	target: Vector3,
	facing: Vector3,
	t: number,
	swing: number,
	seen: number,
	bubble: BillboardGui?,
	hpGui: BillboardGui?,
	lastState: number,
	baseColor: Color3,
	dying: boolean,
}

local folder = Instance.new("Folder")
folder.Name = "KingsbloomActors"
folder.Parent = Workspace

local byPlot: { [number]: { [number]: Ent } } = {}
local plotCF: { [number]: CFrame } = {}

local function cfOf(i: number): CFrame
	local cf = plotCF[i]
	if not cf then
		cf = Layout.plotCFrame(i)
		plotCF[i] = cf
	end
	return cf
end

local function isGloom(e: Ent): boolean
	return e.kind == Codec.GLOOM
end

local function destroy(e: Ent)
	local m = e.actor.model
	for _, p in e.actor.parts do
		TweenService:Create(p, TweenInfo.new(0.35), { Transparency = 1 }):Play()
	end
	task.delay(0.4, function()
		m:Destroy()
	end)
end

local function hpBar(e: Ent): BillboardGui
	local g = Instance.new("BillboardGui")
	g.Name = "HP"
	g.Size = UDim2.fromOffset(70, 9)
	g.StudsOffset = Vector3.new(0, 2.2, 0)
	g.MaxDistance = 80
	g.LightInfluence = 0
	g.AlwaysOnTop = true
	g.Adornee = e.actor.head
	g.Parent = e.actor.model
	local back = Instance.new("Frame")
	back.Size = UDim2.fromScale(1, 1)
	back.BackgroundColor3 = Color3.fromRGB(20, 12, 30)
	back.BackgroundTransparency = 0.2
	back.BorderSizePixel = 0
	back.Parent = g
	local c = Instance.new("UICorner")
	c.CornerRadius = UDim.new(1, 0)
	c.Parent = back
	local fill = Instance.new("Frame")
	fill.Name = "Fill"
	fill.Size = UDim2.fromScale(1, 1)
	fill.BackgroundColor3 = Palette.gloomEye
	fill.BorderSizePixel = 0
	fill.Parent = back
	local c2 = Instance.new("UICorner")
	c2.CornerRadius = UDim.new(1, 0)
	c2.Parent = fill
	return g
end

local function onSnap(buf: any)
	if typeof(buf) ~= "buffer" then
		return
	end
	local ok, plot, list = pcall(Codec.decode, buf)
	if not ok or typeof(plot) ~= "number" or plot < 1 or plot > 6 then
		return
	end
	local now = os.clock()
	local map = byPlot[plot]
	if not map then
		map = {}
		byPlot[plot] = map
	end
	local cf = cfOf(plot)
	for _, s in list :: { Codec.Entity } do
		local world = Layout.toWorld(cf, s.x, s.z, 0.22)
		local e: Ent? = map[s.id]
		if e and e.kind ~= s.kind then
			destroy(e)
			map[s.id] = nil
			e = nil
		end
		if not e then
			local actor = Actors.build(s.kind, s.info)
			actor.model.Parent = folder
			local ne: Ent = {
				id = s.id,
				plot = plot,
				kind = s.kind,
				info = s.info,
				actor = actor,
				pos = world,
				target = world,
				facing = cf:VectorToWorldSpace(Vector3.new(0, 0, -1)),
				t = math.random() * 6,
				swing = 0,
				seen = now,
				bubble = nil,
				hpGui = nil,
				lastState = -1,
				baseColor = actor.head.Color,
				dying = false,
			}
			map[s.id] = ne
			e = ne
			-- fade in
			for _, p in actor.parts do
				local goal = p.Transparency
				p.Transparency = 1
				TweenService:Create(p, TweenInfo.new(0.4), { Transparency = goal }):Play()
			end
		end
		local ent = e :: Ent
		ent.target = world
		ent.info = s.info
		ent.seen = now
	end
end

-- ─── speech, emotes, hits ──────────────────────────────────────────────────
function Entities.get(plot: number, id: number): Ent?
	local map = byPlot[plot]
	return map and map[id]
end

function Entities.worldPos(plot: number, id: number): Vector3?
	local e = Entities.get(plot, id)
	return e and e.pos
end

function Entities.say(plot: number, id: number, text: string)
	local e = Entities.get(plot, id)
	if not e then
		return
	end
	if e.bubble then
		e.bubble:Destroy()
	end
	local g = Instance.new("BillboardGui")
	g.Name = "Bubble"
	g.Size = UDim2.fromOffset(240, 80)
	g.StudsOffset = Vector3.new(0, 2.8, 0)
	g.MaxDistance = 120
	g.LightInfluence = 0
	g.Adornee = e.actor.head
	g.Parent = e.actor.model
	local frame = Instance.new("Frame")
	frame.AnchorPoint = Vector2.new(0.5, 1)
	frame.Position = UDim2.fromScale(0.5, 1)
	frame.AutomaticSize = Enum.AutomaticSize.XY
	frame.Size = UDim2.fromOffset(0, 0)
	frame.BackgroundColor3 = Palette.ui.parchment
	frame.BorderSizePixel = 0
	frame.Parent = g
	local corner = Instance.new("UICorner")
	corner.CornerRadius = UDim.new(0, 12)
	corner.Parent = frame
	local stroke = Instance.new("UIStroke")
	stroke.Color = Palette.ui.goldDeep
	stroke.Thickness = 2
	stroke.Parent = frame
	local pad = Instance.new("UIPadding")
	pad.PaddingLeft = UDim.new(0, 10)
	pad.PaddingRight = UDim.new(0, 10)
	pad.PaddingTop = UDim.new(0, 5)
	pad.PaddingBottom = UDim.new(0, 5)
	pad.Parent = frame
	local label = Instance.new("TextLabel")
	label.AutomaticSize = Enum.AutomaticSize.XY
	label.Size = UDim2.fromOffset(0, 0)
	label.BackgroundTransparency = 1
	label.Font = Enum.Font.BuilderSansBold
	label.TextSize = 17
	label.TextColor3 = Palette.ui.ink
	label.TextWrapped = true
	label.Text = text
	label.Parent = frame
	local limit = Instance.new("UISizeConstraint")
	limit.MaxSize = Vector2.new(210, 200)
	limit.Parent = label
	local scale = Instance.new("UIScale")
	scale.Scale = 0.3
	scale.Parent = frame
	TweenService:Create(scale, TweenInfo.new(0.25, Enum.EasingStyle.Back), { Scale = 1 }):Play()
	e.bubble = g
	task.delay(3.2, function()
		if e.bubble == g and g.Parent then
			TweenService:Create(scale, TweenInfo.new(0.2), { Scale = 0 }):Play()
			task.wait(0.22)
			g:Destroy()
			if e.bubble == g then
				e.bubble = nil
			end
		end
	end)
end

function Entities.emote(plot: number, id: number, emoji: string)
	local e = Entities.get(plot, id)
	if not e then
		return
	end
	local g = Instance.new("BillboardGui")
	g.Size = UDim2.fromOffset(44, 44)
	g.StudsOffset = Vector3.new(0, 2, 0)
	g.MaxDistance = 100
	g.LightInfluence = 0
	g.Adornee = e.actor.head
	g.Parent = e.actor.model
	local l = Instance.new("TextLabel")
	l.Size = UDim2.fromScale(1, 1)
	l.BackgroundTransparency = 1
	l.Text = emoji
	l.TextScaled = true
	l.Parent = g
	TweenService:Create(g, TweenInfo.new(1.3, Enum.EasingStyle.Quad), { StudsOffset = Vector3.new(0, 4.5, 0) }):Play()
	TweenService:Create(l, TweenInfo.new(1.3, Enum.EasingStyle.Quad, Enum.EasingDirection.In), { TextTransparency = 1 }):Play()
	task.delay(1.35, function()
		g:Destroy()
	end)
end

function Entities.flash(plot: number, id: number)
	local e = Entities.get(plot, id)
	if not e then
		return
	end
	local head = e.actor.head
	head.Color = Color3.new(1, 1, 1)
	TweenService:Create(head, TweenInfo.new(0.25), { Color = e.baseColor }):Play()
end

-- Removes a Gloomling at once (it was defeated); returns where it was.
function Entities.kill(plot: number, id: number): Vector3?
	local map = byPlot[plot]
	local e = map and map[id]
	if not e then
		return nil
	end
	map[id] = nil
	e.dying = true
	local m = e.actor.model
	for _, p in e.actor.parts do
		TweenService:Create(p, TweenInfo.new(0.25), { Transparency = 1, Size = p.Size * 1.6 }):Play()
	end
	task.delay(0.3, function()
		m:Destroy()
	end)
	return e.pos
end

function Entities.nearestGloom(pos: Vector3, maxDist: number): (number?, number?, Vector3?)
	local bestPlot, bestId, bestPos, bestD = nil, nil, nil, maxDist
	for plot, map in byPlot do
		for id, e in map do
			if isGloom(e) then
				local d = (Vector3.new(e.pos.X, pos.Y, e.pos.Z) - pos).Magnitude
				if d < bestD then
					bestPlot, bestId, bestPos, bestD = plot, id, e.pos, d
				end
			end
		end
	end
	return bestPlot, bestId, bestPos
end

-- How many visitors are near a point (for the crowd ambience).
function Entities.crowdNear(pos: Vector3, radius: number): (number, number)
	local people, gloom = 0, 0
	for _, map in byPlot do
		for _, e in map do
			if (e.pos - pos).Magnitude < radius then
				if isGloom(e) then
					gloom += 1
				else
					people += 1
				end
			end
		end
	end
	return people, gloom
end

-- ─── every frame ───────────────────────────────────────────────────────────
local parts: { BasePart } = {}
local cframes: { CFrame } = {}

local function step(dt: number)
	table.clear(parts)
	table.clear(cframes)
	local now = os.clock()
	local cam = Workspace.CurrentCamera
	local camPos = cam and cam.CFrame.Position or Vector3.zero
	local k = 1 - math.exp(-dt * 11)
	for _, map in byPlot do
		for id, e in map do
			if now - e.seen > 0.6 then
				map[id] = nil
				destroy(e)
				continue
			end
			local delta = e.target - e.pos
			if delta.Magnitude > 40 then
				e.pos = e.target
			else
				e.pos = e.pos:Lerp(e.target, k)
			end
			local flat = Vector3.new(delta.X, 0, delta.Z)
			local speed = flat.Magnitude * 11
			if flat.Magnitude > 0.03 then
				e.facing = e.facing:Lerp(flat.Unit, math.min(1, dt * 10))
			end
			local gloom = isGloom(e)
			local state = gloom and 0 or e.info % 8
			if not gloom and state ~= e.lastState then
				if state == Codec.FLEE and e.lastState ~= -1 then
					Entities.emote(e.plot, id, "😱")
				end
				e.lastState = state
			end
			e.swing += ((speed > 0.6 and 1 or 0) - e.swing) * math.min(1, dt * 8)
			local rate = gloom and 1 or (state == Codec.FLEE and 1.6 or 1)
			e.t += dt * (gloom and 3 or math.max(2, speed * 0.9)) * rate
			if (e.pos - camPos).Magnitude > 420 then
				continue
			end
			local face = e.facing.Magnitude > 0.01 and e.facing.Unit or Vector3.new(0, 0, -1)
			local cf = CFrame.lookAt(e.pos, e.pos + face)
			if gloom then
				local hp = e.info % 32
				if hp < 31 then
					if not e.hpGui then
						e.hpGui = hpBar(e)
					end
					local gui = e.hpGui :: BillboardGui
					local fill = gui:FindFirstChild("Fill", true)
					if fill and fill:IsA("Frame") then
						fill.Size = UDim2.fromScale(hp / 31, 1)
					end
				end
				local snuffing = (e.info // 32) % 2 == 1
				if snuffing then
					cf *= CFrame.new(math.sin(e.t * 18) * 0.15, 0, 0)
				end
				cf *= CFrame.Angles(0, 0, math.sin(e.t * 0.9) * 0.12)
			end
			Actors.pose(e.actor, cf, e.t, e.swing, parts, cframes)
		end
	end
	if #parts > 0 then
		Workspace:BulkMoveTo(parts, cframes, Enum.BulkMoveMode.FireCFrameChanged)
	end
end

function Entities.start()
	State.remotes.Snap.OnClientEvent:Connect(onSnap)
	RunService.RenderStepped:Connect(step)
end

return Entities
