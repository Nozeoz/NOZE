--!strict
-- The client's shared state: what the server told us (profile, plot summary, layout), which mode
-- we're in, and small signals so controllers and UI can react without knowing about each other.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Net = require(Shared.Net)

export type Signal = {
	connect: (fn: (...any) -> ()) -> () -> (),
	fire: (...any) -> (),
}

local function signal(): Signal
	local listeners: { (...any) -> () } = {}
	local s = {}
	function s.connect(fn: (...any) -> ()): () -> ()
		table.insert(listeners, fn)
		return function()
			local i = table.find(listeners, fn)
			if i then
				table.remove(listeners, i)
			end
		end
	end
	function s.fire(...: any)
		for _, fn in table.clone(listeners) do
			task.spawn(fn, ...)
		end
	end
	return s :: Signal
end

local State = {}

State.signal = signal
State.player = Players.LocalPlayer
State.remotes = Net.get()

State.profile = nil :: any -- the server's view of our profile
State.plot = nil :: any -- our plot's summary (stock, appeal, stalls...)
State.layout = nil :: any -- our plot's layout (for placement previews)
State.mode = "play" -- "play" | "build"
State.modal = false -- a panel or ceremony is open (blocks world clicks)

State.profileChanged = signal()
State.plotChanged = signal()
State.layoutChanged = signal()
State.modeChanged = signal()
State.message = signal() -- (kind, data) from the Me remote
State.fx = signal() -- (plotIndex, events) from the Fx remote
State.notice = signal() -- (data) from the Notice remote
State.toast = signal() -- (text, icon, tone)
State.openPanel = signal() -- (name, arg)
State.inspect = signal() -- (objId)

function State.myPlot(): number?
	local v = State.player:GetAttribute("Plot")
	return typeof(v) == "number" and v or nil
end

export type Result = { ok: boolean, reason: string?, n: number? }

-- Calls the server. Never throws; failures come back as { ok = false, reason = ... }.
function State.request(action: string, args: { [string]: any }?): Result
	local ok, res = pcall(function()
		return State.remotes.Request:InvokeServer(action, args or {})
	end)
	if not ok or typeof(res) ~= "table" then
		return { ok = false, reason = "The royal courier got lost. Try again." }
	end
	return res :: Result
end

function State.setMode(mode: string)
	if State.mode == mode then
		return
	end
	State.mode = mode
	State.modeChanged.fire(mode)
	task.spawn(State.request, "mode", { build = mode == "build" })
end

return State
