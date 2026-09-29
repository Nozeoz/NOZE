--!strict
-- Kingsbloom: Lantern Market, server entry point.
-- Builds the world, starts the services, and walks each player through join → play → save → leave.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local Net = require(Shared.Net)

local World = require(script.World)
local DayNight = require(script.DayNight)
local DataService = require(script.DataService)
local ProgressService = require(script.ProgressService)
local PlotService = require(script.PlotService)
local CombatService = require(script.CombatService)

Net.get()
World.build()
DayNight.start()
ProgressService.start()
PlotService.start()
CombatService.start()

DayNight.onPhase(function(phase)
	if phase == "day" then
		ProgressService.newDay()
	end
end)

local sessions: { [Player]: any } = {}

local function onCharacter(player: Player, char: Model)
	char:WaitForChild("HumanoidRootPart", 10)
	local hum = char:FindFirstChildOfClass("Humanoid")
	if hum then
		hum.WalkSpeed = 20
	end
	task.wait()
	if player:GetAttribute("Plot") then
		PlotService.sendHome(player)
	end
end

local function onJoin(player: Player)
	player.CharacterAdded:Connect(function(char)
		onCharacter(player, char)
	end)
	local profile, saving = DataService.load(player)
	if not player.Parent then
		return
	end
	sessions[player] = profile
	ProgressService.add(player, profile, saving)
	local index = PlotService.claim(player, profile)
	if not index then
		ProgressService.toast(player, "Every clearing here is taken. Look around, then try another server!", "🌲", "warn")
	elseif player.Character then
		task.spawn(onCharacter, player, player.Character)
	end
	if not saving then
		ProgressService.toast(player, "Saving is off this session (Studio: turn on API access to save).", "💾", "warn")
	end
end

local function onLeave(player: Player)
	local profile = sessions[player]
	sessions[player] = nil
	PlotService.release(player)
	ProgressService.remove(player)
	if profile then
		DataService.save(player, profile)
	end
	DataService.forget(player)
end

Players.PlayerAdded:Connect(onJoin)
Players.PlayerRemoving:Connect(onLeave)
for _, p in Players:GetPlayers() do
	task.spawn(onJoin, p)
end

-- Autosave.
task.spawn(function()
	while true do
		task.wait(Config.AUTOSAVE)
		for player, profile in sessions do
			PlotService.store(player)
			task.spawn(DataService.save, player, profile)
		end
	end
end)

game:BindToClose(function()
	local pending = 0
	for player, profile in sessions do
		PlotService.store(player)
		pending += 1
		task.spawn(function()
			DataService.save(player, profile)
			pending -= 1
		end)
	end
	local t = os.clock()
	while pending > 0 and os.clock() - t < 25 do
		task.wait(0.2)
	end
end)
