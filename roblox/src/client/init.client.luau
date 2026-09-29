--!strict
-- Kingsbloom: Lantern Market, client entry point.
-- Starts the sky, sound, the renderers, the controllers and the UI, then wires the remotes.

local Players = game:GetService("Players")
local StarterGui = game:GetService("StarterGui")
local UserInputService = game:GetService("UserInputService")

local State = require(script.State)
local Audio = require(script.Audio)
local Sky = require(script.Sky)
local Mirror = require(script.Mirror)
local Entities = require(script.Entities)
local WorldFx = require(script.WorldFx)
local Shake = require(script.Shake)
local Build = require(script.Build)
local Combat = require(script.Combat)
local Guide = require(script.Guide)
local Theme = require(script.UI.Theme)
local HUD = require(script.UI.HUD)
local BuildBar = require(script.UI.BuildBar)
local Panels = require(script.UI.Panels)
local Ceremony = require(script.UI.Ceremony)

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")

Theme.sound = function(name: string)
	Audio.play(name)
end
-- We equip the Lantern Staff ourselves, so the hotbar would only get in the way.
pcall(function()
	StarterGui:SetCoreGuiEnabled(Enum.CoreGuiType.Backpack, false)
end)

-- ─── remotes (connected first so nothing is missed) ────────────────────────
local surging = false
State.remotes.Me.OnClientEvent:Connect(function(kind: any, data: any)
	if kind == "profile" then
		State.profile = data
		if typeof(data) == "table" and typeof(data.settings) == "table" then
			Audio.setVolumes(data.settings.music or 0.5, data.settings.sfx or 0.8, data.settings.amb or 0.6)
		end
		State.profileChanged.fire(data)
	elseif kind == "plot" then
		State.plot = data
		State.plotChanged.fire(data)
	elseif kind == "layout" then
		State.layout = data
		State.layoutChanged.fire(data)
	elseif typeof(kind) == "string" then
		if kind == "surge" then
			surging = true
		elseif kind == "surgeWon" or kind == "ledger" then
			surging = false
		end
		State.message.fire(kind, data)
	end
end)
State.remotes.Fx.OnClientEvent:Connect(function(plot: any, events: any)
	if typeof(plot) == "number" and typeof(events) == "table" then
		WorldFx.handle(plot, events)
		State.fx.fire(plot, events)
	end
end)
State.remotes.Notice.OnClientEvent:Connect(function(d: any)
	if typeof(d) == "table" then
		if d.k == "phase" and d.phase == "dawn" then
			surging = false
		end
		State.notice.fire(d)
	end
end)

-- ─── start everything ──────────────────────────────────────────────────────
local _ = Mirror
Sky.start()
Entities.start()
Shake.start(function()
	return State.mode == "build"
end)
HUD.start(playerGui)
BuildBar.start(playerGui)
Panels.start(playerGui)
Ceremony.start(playerGui)
Build.start()
Combat.start()
task.spawn(WorldFx.start)
Guide.start()

HUD.onBuild = Build.toggle
HUD.onJournal = function(tab: string?)
	Panels.open("journal", tab)
end
HUD.onSettings = function()
	Panels.open("settings")
end
HUD.onAttack = Combat.swing
HUD.onBurst = Combat.burst
HUD.burstReadyAt = function(): number
	return Combat.burstReadyAt
end

UserInputService.InputBegan:Connect(function(input, processed)
	if processed then
		return
	end
	if input.KeyCode == Enum.KeyCode.B then
		if not State.modal then
			Build.toggle()
		end
	elseif input.KeyCode == Enum.KeyCode.J then
		if Panels.isOpen() then
			Panels.close()
		elseif not State.modal then
			Panels.open("journal")
		end
	end
end)

-- A roomier camera to start with, so the diorama shows.
local function roomyCamera()
	player.CameraMinZoomDistance = 26
	task.delay(0.3, function()
		player.CameraMinZoomDistance = 6
	end)
end
player.CharacterAdded:Connect(roomyCamera)
if player.Character then
	roomyCamera()
end

-- ─── music and ambience follow the day ─────────────────────────────────────
task.spawn(function()
	while true do
		local c = Sky.clock
		if surging and c.phase == "night" then
			Audio.setPlaylist("surge")
		elseif c.phase == "night" or c.phase == "dusk" then
			Audio.setPlaylist("night")
		else
			Audio.setPlaylist("day")
		end
		local char = player.Character
		local root = char and char:FindFirstChild("HumanoidRootPart")
		local people = 0
		if root and root:IsA("BasePart") then
			people = Entities.crowdNear(root.Position, 90)
		end
		for _ = 1, 10 do
			Audio.setAmbience(Sky.clock.night, math.clamp(people / 10, 0, 1))
			task.wait(0.1)
		end
	end
end)

-- Ask the server for everything once we're listening.
task.spawn(State.request, "sync", {})
