--!strict
-- A gentle guide for the current quest: a bouncing marker over the thing to go to and a thread
-- of light from you to it (a ripe field, your stall, the dark stretch of road, the nearest
-- Gloomling, the Heartflame...). It stays quiet in Build mode and when there's nothing to point at.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Config = require(Shared.Config)
local Grid = require(Shared.Grid)
local Layout = require(Shared.Layout)
local Palette = require(Shared.Palette)

local State = require(script.Parent.State)
local Mirror = require(script.Parent.Mirror)
local Entities = require(script.Parent.Entities)
local Sky = require(script.Parent.Sky)

local Guide = {}

local B = Catalog.Buildings
local player = Players.LocalPlayer

local anchor = Instance.new("Part")
anchor.Name = "KingsbloomGuide"
anchor.Anchored = true
anchor.CanCollide = false
anchor.CanQuery = false
anchor.CanTouch = false
anchor.Transparency = 1
anchor.Size = Vector3.new(0.2, 0.2, 0.2)
anchor.Parent = Workspace
local target = Instance.new("Attachment")
target.Parent = anchor

local marker = Instance.new("BillboardGui")
marker.Size = UDim2.fromOffset(64, 64)
marker.AlwaysOnTop = true
marker.LightInfluence = 0
marker.MaxDistance = 400
marker.Adornee = anchor
marker.Enabled = false
marker.Parent = anchor
local arrow = Instance.new("TextLabel")
arrow.Size = UDim2.fromScale(1, 1)
arrow.BackgroundTransparency = 1
arrow.Text = "⬇️"
arrow.TextScaled = true
arrow.Parent = marker

local beam = Instance.new("Beam")
beam.Attachment1 = target
beam.Width0 = 0.5
beam.Width1 = 0.5
beam.FaceCamera = true
beam.LightEmission = 1
beam.Color = ColorSequence.new(Palette.gold, Palette.lantern)
beam.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(0.8, 0.5), NumberSequenceKeypoint.new(1, 1) })
beam.Texture = "rbxasset://textures/particles/sparkles_main.dds"
beam.TextureMode = Enum.TextureMode.Wrap
beam.TextureLength = 4
beam.TextureSpeed = 1.5
beam.Segments = 12
beam.CurveSize0 = 6
beam.CurveSize1 = -2
beam.Enabled = false
beam.Parent = anchor

local function plotCF(): CFrame?
	local i = State.myPlot()
	return i and Layout.plotCFrame(i) or nil
end

local function objectPos(pred: (any) -> boolean): Vector3?
	local sim = Mirror.sim
	local cf = plotCF()
	if not sim or not cf then
		return nil
	end
	local best: any = nil
	for _, o in sim.objects do
		if pred(o) and (not best or o.id < best.id) then
			best = o
		end
	end
	if not best then
		return nil
	end
	return Layout.toWorld(cf, best.x + best.w / 2, best.z + best.d / 2, 9)
end

-- The first dark tile on the walk in (for "Light the Old Road").
local function darkRoad(): Vector3?
	local sim = Mirror.sim
	local cf = plotCF()
	if not sim or not cf then
		return nil
	end
	local L = sim:staticLight()
	for _, t in sim:route() do
		if L[Grid.idx(t[1], t[2])] < Config.LIT then
			return Layout.toWorld(cf, t[1] + 0.5, t[2] + 0.5, 5)
		end
	end
	return nil
end

local function goal(): (Vector3?, string?)
	local p = State.profile
	local q = p and p.quest
	if not q or q.ready then
		return nil, nil
	end
	local id = q.id
	if id == "tend" then
		return objectPos(function(o)
			return o.ripe == true
		end), "✨"
	elseif id == "sell" then
		return objectPos(function(o)
			return B[o.type].stall == true
		end), "🛒"
	elseif id == "lamps" then
		return darkRoad(), "🏮"
	elseif id == "night" or id == "surge" then
		local char = player.Character
		local root = char and char:FindFirstChild("HumanoidRootPart")
		if root and root:IsA("BasePart") then
			local _, _, pos = Entities.nearestGloom(root.Position, 160)
			if pos then
				return pos + Vector3.new(0, 5, 0), "⚔️"
			end
		end
		return nil, nil
	elseif id == "heart2" or id == "heart3" or id == "heart4" then
		return objectPos(function(o)
			return o.type == "heartflame"
		end), "🔥"
	end
	return nil, nil
end

function Guide.start()
	local t = 0
	local current: Vector3? = nil
	local icon = "⬇️"
	task.spawn(function()
		while true do
			if State.mode == "play" then
				local pos, ic = goal()
				current = pos
				icon = ic or "⬇️"
			else
				current = nil
			end
			task.wait(0.5)
		end
	end)
	RunService.RenderStepped:Connect(function(dt: number)
		t += dt
		local char = player.Character
		local root = char and char:FindFirstChild("HumanoidRootPart")
		local pos = current
		local show = pos ~= nil and root ~= nil and State.mode == "play" and not State.modal
		if show and pos and root then
			local far = ((root :: BasePart).Position - pos).Magnitude > 14
			anchor.CFrame = CFrame.new(pos + Vector3.new(0, math.abs(math.sin(t * 3)) * 1.5, 0))
			arrow.Text = icon
			marker.Enabled = true
			local a0 = (root :: Instance):FindFirstChild("GuideAttachment")
			if not a0 then
				local a = Instance.new("Attachment")
				a.Name = "GuideAttachment"
				a.Parent = root
				a0 = a
			end
			beam.Attachment0 = a0 :: Attachment
			beam.Enabled = far and Sky.clock ~= nil
		else
			marker.Enabled = false
			beam.Enabled = false
		end
	end)
end

return Guide
