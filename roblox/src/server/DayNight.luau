--!strict
-- One shared clock. The server publishes when the cycle started; everyone computes the same time
-- from Workspace:GetServerTimeNow(), so the sky animates smoothly on each client without traffic.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local DayCycle = require(Shared.DayCycle)
local Net = require(Shared.Net)

local DayNight = {}

local start = 0
local lastPhase = ""
local listeners: { (string, DayCycle.Clock) -> () } = {}

function DayNight.now(): DayCycle.Clock
	return DayCycle.at(Workspace:GetServerTimeNow() - start)
end

function DayNight.onPhase(fn: (string, DayCycle.Clock) -> ())
	table.insert(listeners, fn)
end

local function setMist(on: boolean)
	local root = Workspace:FindFirstChild("Kingsbloom")
	local mist = root and root:FindFirstChild("VeilMist")
	if not mist then
		return
	end
	for _, d in mist:GetDescendants() do
		if d:IsA("ParticleEmitter") then
			d.Enabled = on
		end
	end
end

function DayNight.start()
	-- Begin mid-morning so new servers open in daylight.
	start = Workspace:GetServerTimeNow() - 25
	Workspace:SetAttribute("CycleStart", start)
	local remotes = Net.get()
	RunService.Heartbeat:Connect(function()
		local clock = DayNight.now()
		if clock.phase ~= lastPhase then
			local first = lastPhase == ""
			lastPhase = clock.phase
			setMist(clock.phase == "night" or clock.phase == "dusk")
			if not first then
				remotes.Notice:FireAllClients({ k = "phase", phase = clock.phase, day = clock.day })
			end
			for _, fn in listeners do
				task.spawn(fn, clock.phase, clock)
			end
		end
	end)
end

return DayNight
