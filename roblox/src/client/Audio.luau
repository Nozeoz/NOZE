--!strict
-- Sound effects, music and ambience. Music follows the time of day (and the midnight surge),
-- crossfading between two players; ambience layers birds, wind, night and the market crowd.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)

local Audio = {}

local groups: { [string]: SoundGroup } = {}
local pools: { [string]: { Sound } } = {}
local folder = Instance.new("Folder")
folder.Name = "KingsbloomAudio"
folder.Parent = SoundService

local function group(name: string, volume: number): SoundGroup
	local g = Instance.new("SoundGroup")
	g.Name = name
	g.Volume = volume
	g.Parent = SoundService
	groups[name] = g
	return g
end

group("Music", 0.5)
group("SFX", 0.8)
group("Ambience", 0.6)

-- How loud each effect is relative to the others.
local VOLUME: { [string]: number } = {
	click = 0.5, pop = 0.6, whoosh = 0.4, notify = 0.5, pickup = 0.5, coin = 0.45, coins = 0.6, place = 0.6,
	hammer = 0.5, remove = 0.5, error = 0.35, levelup = 0.9, rankup = 0.9, quest = 0.8, achievement = 0.7,
	sparkle = 0.5, swing = 0.55, hit = 0.6, burst = 0.8, poof = 0.5, gloom = 0.45, hurt = 0.5, bell = 0.7, tend = 0.55,
}

local function make(name: string): Sound?
	local id = (Config.SOUNDS :: any)[name]
	if typeof(id) ~= "string" or id == "" then
		return nil
	end
	local s = Instance.new("Sound")
	s.SoundId = id
	s.Volume = VOLUME[name] or 0.5
	s.SoundGroup = groups.SFX
	s.Parent = folder
	return s
end

-- Plays a 2D effect. `pitch` varies it a little so repeats don't grate.
function Audio.play(name: string, pitch: number?, volume: number?)
	local pool = pools[name]
	if not pool then
		pool = {}
		pools[name] = pool
	end
	local s: Sound? = nil
	for _, candidate in pool do
		if not candidate.IsPlaying then
			s = candidate
			break
		end
	end
	if not s and #pool < 6 then
		s = make(name)
		if s then
			table.insert(pool, s)
		end
	end
	if not s then
		return
	end
	local snd = s :: Sound
	snd.PlaybackSpeed = (pitch or 1) * (0.95 + math.random() * 0.1)
	snd.Volume = (VOLUME[name] or 0.5) * (volume or 1)
	snd.TimePosition = 0
	snd:Play()
end

-- Plays an effect at a place in the world (it fades with distance).
function Audio.at(name: string, pos: Vector3, pitch: number?, volume: number?)
	local id = (Config.SOUNDS :: any)[name]
	if typeof(id) ~= "string" or id == "" then
		return
	end
	local a = Instance.new("Attachment")
	a.WorldPosition = pos
	a.Parent = Workspace.Terrain
	local s = Instance.new("Sound")
	s.SoundId = id
	s.Volume = (VOLUME[name] or 0.5) * (volume or 1) * 1.4
	s.PlaybackSpeed = (pitch or 1) * (0.94 + math.random() * 0.12)
	s.RollOffMode = Enum.RollOffMode.InverseTapered
	s.RollOffMinDistance = 12
	s.RollOffMaxDistance = 140
	s.SoundGroup = groups.SFX
	s.Parent = a
	s:Play()
	s.Ended:Once(function()
		a:Destroy()
	end)
	task.delay(8, function()
		if a.Parent then
			a:Destroy()
		end
	end)
end

-- ─── music ─────────────────────────────────────────────────────────────────
local tracks: { Sound } = {}
for i = 1, 2 do
	local s = Instance.new("Sound")
	s.Name = "Music" .. i
	s.Volume = 0
	s.SoundGroup = groups.Music
	s.Parent = folder
	tracks[i] = s
end
local current = 1
local playlist = "day"
local lastId = ""

local function pickTrack(list: { string }): string
	if #list == 1 then
		return list[1]
	end
	local id = list[math.random(1, #list)]
	for _ = 1, 4 do
		if id ~= lastId then
			break
		end
		id = list[math.random(1, #list)]
	end
	return id
end

local function crossfade(id: string)
	lastId = id
	local old = tracks[current]
	current = current % 2 + 1
	local new = tracks[current]
	new.SoundId = id
	new.TimePosition = 0
	new.Volume = 0
	new:Play()
	TweenService:Create(new, TweenInfo.new(3), { Volume = 0.5 }):Play()
	local fade = TweenService:Create(old, TweenInfo.new(3), { Volume = 0 })
	fade:Play()
	fade.Completed:Once(function()
		if old.Volume < 0.01 then
			old:Stop()
		end
	end)
end

local function listFor(name: string): { string }
	if name == "night" then
		return Config.MUSIC_NIGHT
	elseif name == "surge" then
		return { Config.MUSIC_SURGE }
	end
	return Config.MUSIC_DAY
end

function Audio.setPlaylist(name: string)
	if playlist == name and tracks[current].IsPlaying then
		return
	end
	playlist = name
	crossfade(pickTrack(listFor(name)))
end

for i = 1, 2 do
	tracks[i].Ended:Connect(function()
		if i == current then
			crossfade(pickTrack(listFor(playlist)))
		end
	end)
end

-- ─── ambience ──────────────────────────────────────────────────────────────
local amb: { [string]: Sound } = {}
for _, name in { "ambDay", "ambNight", "ambWind", "ambCrowd" } do
	local s = Instance.new("Sound")
	s.Name = name
	s.SoundId = (Config.SOUNDS :: any)[name] or ""
	s.Looped = true
	s.Volume = 0
	s.SoundGroup = groups.Ambience
	s.Parent = folder
	amb[name] = s
end

-- night: 0..1; crowd: 0..1 (how busy the market near you is)
function Audio.setAmbience(night: number, crowd: number)
	local goals: { [string]: number } = {
		ambDay = (1 - night) * 0.35,
		ambNight = night * 0.4,
		ambWind = 0.12 + night * 0.08,
		ambCrowd = crowd * 0.25,
	}
	for name, v in goals do
		local s = amb[name]
		if s then
			s.Volume += (v - s.Volume) * 0.05
			if v > 0.01 and not s.IsPlaying then
				s:Play()
			end
		end
	end
end

function Audio.setVolumes(music: number, sfx: number, ambience: number)
	groups.Music.Volume = music
	groups.SFX.Volume = sfx
	groups.Ambience.Volume = ambience
end

return Audio
