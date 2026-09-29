--!strict
-- The remotes, created by the server and found by clients.
--   Request (RemoteFunction, client → server): building, claiming, settings. Returns { ok, reason, ... }.
--   Swing / Burst (RemoteEvent, client → server): the Lantern Staff.
--   Me (RemoteEvent, server → one client): the player's own profile, plot layout and ceremonies.
--   Fx (RemoteEvent, server → clients near a plot): what just happened on a plot (a batch per tick).
--   Snap (UnreliableRemoteEvent, server → clients near a plot): where visitors and Gloomlings are.
--   Notice (RemoteEvent, server → everyone): server-wide news.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Net = {}

export type Remotes = {
	Request: RemoteFunction,
	Swing: RemoteEvent,
	Burst: RemoteEvent,
	Me: RemoteEvent,
	Fx: RemoteEvent,
	Snap: UnreliableRemoteEvent,
	Notice: RemoteEvent,
}

local cached: Remotes? = nil

function Net.get(): Remotes
	if cached then
		return cached
	end
	local folder: Instance
	if RunService:IsServer() then
		local f = ReplicatedStorage:FindFirstChild("Remotes")
		if not f then
			f = Instance.new("Folder")
			f.Name = "Remotes"
			f.Parent = ReplicatedStorage
		end
		folder = f :: Instance
		local function ensure(name: string, class: string)
			if not folder:FindFirstChild(name) then
				local r = Instance.new(class)
				r.Name = name
				r.Parent = folder
			end
		end
		ensure("Request", "RemoteFunction")
		ensure("Swing", "RemoteEvent")
		ensure("Burst", "RemoteEvent")
		ensure("Me", "RemoteEvent")
		ensure("Fx", "RemoteEvent")
		ensure("Snap", "UnreliableRemoteEvent")
		ensure("Notice", "RemoteEvent")
	else
		folder = ReplicatedStorage:WaitForChild("Remotes")
	end
	local r: Remotes = {
		Request = folder:WaitForChild("Request") :: RemoteFunction,
		Swing = folder:WaitForChild("Swing") :: RemoteEvent,
		Burst = folder:WaitForChild("Burst") :: RemoteEvent,
		Me = folder:WaitForChild("Me") :: RemoteEvent,
		Fx = folder:WaitForChild("Fx") :: RemoteEvent,
		Snap = folder:WaitForChild("Snap") :: UnreliableRemoteEvent,
		Notice = folder:WaitForChild("Notice") :: RemoteEvent,
	}
	cached = r
	return r
end

return Net
