--!strict
-- Loads and saves profiles with DataStores. If DataStores are unavailable (for example in Studio
-- without "Enable Studio Access to API Services"), play continues and saving is switched off
-- for that session, so a bad load can never overwrite a good save.

local DataStoreService = game:GetService("DataStoreService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local Progress = require(Shared.Progress)

local DataService = {}

local store: DataStore? = nil
do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore(Config.DATASTORE)
	end)
	if ok then
		store = result
	else
		local why = tostring(result)
		warn("[Kingsbloom] DataStores unavailable, progress won't save this session: " .. why)
	end
end

local canSave: { [Player]: boolean } = {}

local function key(player: Player): string
	return "p_" .. player.UserId
end

-- Returns the profile and whether it will be saved.
function DataService.load(player: Player): (Progress.Profile, boolean)
	if not store then
		canSave[player] = false
		return Progress.newProfile(), false
	end
	for attempt = 1, 3 do
		local ok, result = pcall(function()
			return (store :: DataStore):GetAsync(key(player))
		end)
		if ok then
			canSave[player] = true
			return Progress.sanitize(result), true
		end
		warn(string.format("[Kingsbloom] load failed for %s (try %d): %s", player.Name, attempt, tostring(result)))
		task.wait(attempt)
	end
	canSave[player] = false
	return Progress.newProfile(), false
end

function DataService.save(player: Player, profile: Progress.Profile): boolean
	if not store or not canSave[player] then
		return false
	end
	for attempt = 1, 3 do
		local ok, err = pcall(function()
			(store :: DataStore):UpdateAsync(key(player), function()
				return profile
			end)
		end)
		if ok then
			return true
		end
		warn(string.format("[Kingsbloom] save failed for %s (try %d): %s", player.Name, attempt, tostring(err)))
		task.wait(attempt)
	end
	return false
end

function DataService.forget(player: Player)
	canSave[player] = nil
end

function DataService.savingEnabled(player: Player): boolean
	return canSave[player] == true
end

return DataService
