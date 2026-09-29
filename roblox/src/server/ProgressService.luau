--!strict
-- XP, levels and ranks, the quest chain, daily Royal Orders, achievements, the Codex, name tags,
-- leaderstats and the Royal Ledger board. Wraps the pure rules in shared/Progress with remotes and fanfare.

local BadgeService = game:GetService("BadgeService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Config = require(Shared.Config)
local Net = require(Shared.Net)
local Palette = require(Shared.Palette)
local PlotSim = require(Shared.PlotSim)
local Progress = require(Shared.Progress)

local ProgressService = {}

type Entry = {
	profile: Progress.Profile,
	saving: boolean,
	dirty: boolean,
	questReadySent: boolean,
	lastAch: number,
	leaderstats: Folder?,
	nightXp: number,
	nightLumen: number,
}

local entries: { [Player]: Entry } = {}
local liveFor: (Player) -> Progress.Live? = function(_p)
	return nil
end
local levelListeners: { (Player, number) -> () } = {}
local remotes = Net.get()

function ProgressService.setLive(fn: (Player) -> Progress.Live?)
	liveFor = fn
end

function ProgressService.onLevel(fn: (Player, number) -> ())
	table.insert(levelListeners, fn)
end

function ProgressService.profile(player: Player): Progress.Profile?
	local e = entries[player]
	return e and e.profile
end

function ProgressService.send(player: Player, kind: string, data: any)
	if player.Parent then
		remotes.Me:FireClient(player, kind, data)
	end
end

function ProgressService.toast(player: Player, text: string, icon: string?, tone: string?)
	ProgressService.send(player, "toast", { text = text, icon = icon, tone = tone })
end

function ProgressService.markDirty(player: Player)
	local e = entries[player]
	if e then
		e.dirty = true
	end
end

-- ─── name tags and the player list ─────────────────────────────────────────
local function tagText(player: Player, level: number): string
	local rank, _, icon = Catalog.rankFor(level)
	return string.format("%s Lv %d · %s", icon, level, rank)
end

local function updateTag(player: Player)
	local e = entries[player]
	local char = player.Character
	if not e or not char then
		return
	end
	local head = char:FindFirstChild("Head")
	if not head then
		return
	end
	local gui = head:FindFirstChild("RankTag")
	if not gui then
		local g = Instance.new("BillboardGui")
		g.Name = "RankTag"
		g.Size = UDim2.fromOffset(220, 54)
		g.StudsOffset = Vector3.new(0, 2.6, 0)
		g.MaxDistance = 90
		g.LightInfluence = 0
		g.Parent = head
		local name = Instance.new("TextLabel")
		name.Name = "Name"
		name.BackgroundTransparency = 1
		name.Size = UDim2.fromScale(1, 0.55)
		name.Font = Enum.Font.FredokaOne
		name.TextScaled = true
		name.TextColor3 = Palette.white
		name.TextStrokeTransparency = 0.4
		name.Parent = g
		local rank = Instance.new("TextLabel")
		rank.Name = "Rank"
		rank.BackgroundTransparency = 1
		rank.Position = UDim2.fromScale(0, 0.55)
		rank.Size = UDim2.fromScale(1, 0.45)
		rank.Font = Enum.Font.FredokaOne
		rank.TextScaled = true
		rank.TextColor3 = Palette.ui.gold
		rank.TextStrokeTransparency = 0.5
		rank.Parent = g
		gui = g
	end
	local nameLabel = (gui :: Instance):FindFirstChild("Name") :: TextLabel?
	local rankLabel = (gui :: Instance):FindFirstChild("Rank") :: TextLabel?
	if nameLabel then
		nameLabel.Text = player.DisplayName
	end
	if rankLabel then
		rankLabel.Text = tagText(player, e.profile.level)
	end
	local hum = char:FindFirstChildOfClass("Humanoid")
	if hum then
		hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	end
end

local function makeLeaderstats(player: Player, e: Entry)
	local ls = Instance.new("Folder")
	ls.Name = "leaderstats"
	local lv = Instance.new("IntValue")
	lv.Name = "Level"
	lv.Parent = ls
	local gold = Instance.new("IntValue")
	gold.Name = "Gold"
	gold.Parent = ls
	ls.Parent = player
	e.leaderstats = ls
end

local function updateLeaderstats(e: Entry)
	local ls = e.leaderstats
	if not ls then
		return
	end
	local lv = ls:FindFirstChild("Level") :: IntValue?
	local gold = ls:FindFirstChild("Gold") :: IntValue?
	if lv then
		lv.Value = e.profile.level
	end
	if gold then
		gold.Value = math.floor(e.profile.gold)
	end
end

local function award(player: Player, badge: number?)
	if badge and badge ~= 0 then
		task.spawn(function()
			pcall(function()
				BadgeService:AwardBadgeAsync(player.UserId, badge)
			end)
		end)
	end
end

-- ─── the view the client draws ─────────────────────────────────────────────
local function view(player: Player, e: Entry)
	local p = e.profile
	local live = liveFor(player)
	local q = Progress.quest(p, live)
	local quest = nil
	if q then
		quest = {
			id = q.def.id,
			giver = q.def.giver,
			title = q.def.title,
			text = q.def.text,
			progress = q.progress,
			target = q.target,
			ready = q.ready,
			index = q.index,
			total = #Catalog.Quests,
			gold = q.def.gold or 0,
			lumen = q.def.lumen or 0,
			xp = q.def.xp or 0,
		}
	end
	local orders = {}
	for i, o in p.orders.list do
		local def
		for _, od in Catalog.Orders do
			if od.id == o.id then
				def = od
			end
		end
		local gold, xp = Catalog.orderReward(p.level)
		table.insert(orders, {
			i = i,
			text = def and string.format(def.text, o.target) or o.id,
			progress = Progress.orderProgress(p, o),
			target = o.target,
			claimed = o.claimed,
			gold = gold,
			xp = xp,
		})
	end
	local rank, rankIndex, rankIcon = Catalog.rankFor(p.level)
	return {
		gold = math.floor(p.gold),
		lumen = math.floor(p.lumen),
		level = p.level,
		xp = p.xp,
		need = Catalog.xpForLevel(p.level),
		rank = rank,
		rankIndex = rankIndex,
		rankIcon = rankIcon,
		quest = quest,
		orders = orders,
		sealed = p.orders.sealed,
		ach = p.ach,
		codex = p.codex,
		stats = p.stats,
		settings = p.settings,
		welcomed = p.welcomed,
		saving = e.saving,
		day = p.day,
	}
end

function ProgressService.push(player: Player)
	local e = entries[player]
	if not e then
		return
	end
	e.dirty = false
	updateLeaderstats(e)
	ProgressService.send(player, "profile", view(player, e))
end

-- ─── XP and levels ─────────────────────────────────────────────────────────
function ProgressService.grant(player: Player, xp: number, lumen: number?)
	local e = entries[player]
	if not e then
		return
	end
	local p = e.profile
	if lumen and lumen ~= 0 then
		p.lumen += lumen
		e.nightLumen += lumen
	end
	if xp > 0 then
		e.nightXp += xp
		local oldRank = select(2, Catalog.rankFor(p.level))
		local gained = Progress.addXP(p, xp)
		for _, level in gained do
			local rank, rankIndex, rankIcon = Catalog.rankFor(level)
			local rankUp = rankIndex > oldRank
			oldRank = rankIndex
			ProgressService.send(player, "levelup", {
				level = level,
				rank = rank,
				rankIcon = rankIcon,
				rankUp = rankUp,
				cards = Progress.unlocksAt(level),
				need = Catalog.xpForLevel(level),
			})
			if rankUp then
				remotes.Notice:FireAllClients({ k = "rank", name = player.DisplayName, rank = rank, icon = rankIcon })
				if rank == "Village" then
					award(player, Config.BADGES.village)
				elseif rank == "Kingdom" then
					award(player, Config.BADGES.kingdom)
				end
			end
			for _, fn in levelListeners do
				task.spawn(fn, player, level)
			end
		end
		if #gained > 0 then
			updateTag(player)
		end
	end
	e.dirty = true
end

function ProgressService.discovered(player: Player, kind: string)
	local def = Catalog.Visitors[kind]
	if not def then
		return
	end
	ProgressService.send(player, "discovery", { kind = kind, name = def.name, icon = def.icon, rarity = def.rarity, desc = def.desc })
	if def.rarity == "Legendary" or def.rarity == "Rare" then
		remotes.Notice:FireAllClients({ k = "rare", name = player.DisplayName, visitor = def.name, icon = def.icon, rarity = def.rarity })
	end
end

function ProgressService.nightStart(player: Player)
	local e = entries[player]
	if e then
		e.nightXp = 0
		e.nightLumen = 0
	end
end

function ProgressService.nightTotals(player: Player): (number, number)
	local e = entries[player]
	if not e then
		return 0, 0
	end
	return e.nightXp, e.nightLumen
end

-- ─── quests, orders, achievements ──────────────────────────────────────────
local function checkQuest(player: Player, e: Entry)
	local q = Progress.quest(e.profile, liveFor(player))
	if q and q.ready and not e.questReadySent then
		e.questReadySent = true
		ProgressService.send(player, "questReady", { title = q.def.title, giver = q.def.giver })
		e.dirty = true
	end
end

local function checkAchievements(player: Player, e: Entry)
	local unlocked = Progress.checkAchievements(e.profile, liveFor(player))
	for _, a in unlocked do
		ProgressService.send(player, "achievement", {
			name = a.def.name,
			icon = a.def.icon,
			tier = a.tier,
			tierName = Catalog.TierNames[a.tier],
			desc = a.def.desc,
			lumen = a.lumen,
		})
		if a.def.id == "warden" and a.tier == 1 then
			award(player, Config.BADGES.nightWarden)
		end
		e.dirty = true
	end
end

function ProgressService.claimQuest(player: Player): (boolean, string?)
	local e = entries[player]
	if not e then
		return false, "Not ready."
	end
	local def, reward = Progress.claimQuest(e.profile, liveFor(player))
	if not def or not reward then
		return false, "Not finished yet."
	end
	e.questReadySent = false
	ProgressService.send(player, "questDone", { title = def.title, giver = def.giver, gold = reward.gold, lumen = reward.lumen, xp = reward.xp })
	ProgressService.grant(player, reward.xp, 0)
	checkQuest(player, e)
	return true, nil
end

function ProgressService.claimOrder(player: Player, i: number): (boolean, string?)
	local e = entries[player]
	if not e then
		return false, "Not ready."
	end
	local reward, sealed = Progress.claimOrder(e.profile, i)
	if not reward then
		return false, "Not finished yet."
	end
	ProgressService.send(player, "orderDone", { gold = reward.gold, xp = reward.xp, lumen = reward.lumen, sealed = sealed })
	ProgressService.grant(player, reward.xp, 0)
	return true, nil
end

function ProgressService.newDay()
	for player, e in entries do
		e.profile.day += 1
		Progress.rollOrders(e.profile, PlotSim.makeRng(player.UserId % 100000 + e.profile.day * 7919))
		ProgressService.send(player, "orders", { day = e.profile.day })
		e.dirty = true
	end
end

function ProgressService.settings(player: Player, s: any)
	local e = entries[player]
	if not e or type(s) ~= "table" then
		return
	end
	for _, k in { "music", "sfx", "amb" } do
		local v = s[k]
		if type(v) == "number" and v == v then
			(e.profile.settings :: any)[k] = math.clamp(v, 0, 1)
		end
	end
	if s.welcomed == true then
		e.profile.welcomed = true
	end
	e.dirty = true
end

-- ─── the Royal Ledger board in the hub ─────────────────────────────────────
local function updateBoard()
	local root = Workspace:FindFirstChild("Kingsbloom")
	local hub = root and root:FindFirstChild("Hub")
	local board = hub and hub:FindFirstChild("LedgerBoard")
	local gui = board and board:FindFirstChild("Board")
	local body = gui and gui:FindFirstChild("Body") :: TextLabel?
	if not body then
		return
	end
	local rows = {}
	for player, e in entries do
		table.insert(rows, { name = player.DisplayName, level = e.profile.level, gold = e.profile.stats.earned or 0 })
	end
	table.sort(rows, function(a, b)
		if a.level ~= b.level then
			return a.level > b.level
		end
		return a.gold > b.gold
	end)
	local lines = {}
	for i, r in rows do
		local rank, _, icon = Catalog.rankFor(r.level)
		table.insert(lines, string.format("<b>%d.</b> %s  %s Lv %d %s", i, r.name, icon, r.level, rank))
		if i >= 6 then
			break
		end
	end
	body.Text = #lines > 0 and table.concat(lines, "\n") or "No Sovereigns yet."
end

-- ─── players ───────────────────────────────────────────────────────────────
function ProgressService.add(player: Player, profile: Progress.Profile, saving: boolean)
	local e: Entry = {
		profile = profile,
		saving = saving,
		dirty = true,
		questReadySent = false,
		lastAch = 0,
		leaderstats = nil,
		nightXp = 0,
		nightLumen = 0,
	}
	entries[player] = e
	makeLeaderstats(player, e)
	if profile.quest.i == 1 and profile.quest.base == 0 and (profile.stats.placed or 0) > 0 then
		Progress.startQuest(profile, 1, nil)
	end
	if profile.orders.day ~= profile.day or #profile.orders.list == 0 then
		Progress.rollOrders(profile, PlotSim.makeRng(player.UserId % 100000 + profile.day * 7919))
	end
	player.CharacterAdded:Connect(function(char)
		char:WaitForChild("Head", 10)
		updateTag(player)
	end)
	if player.Character then
		task.spawn(updateTag, player)
	end
	ProgressService.push(player)
	updateBoard()
end

function ProgressService.remove(player: Player)
	entries[player] = nil
	updateBoard()
end

function ProgressService.start()
	task.spawn(function()
		local t = 0
		while true do
			task.wait(0.25)
			t += 1
			for player, e in entries do
				if player.Parent then
					checkQuest(player, e)
					if t % 4 == 0 then
						checkAchievements(player, e)
					end
					if e.dirty then
						ProgressService.push(player)
					end
				end
			end
			if t % 40 == 0 then
				updateBoard()
			end
		end
	end)
end

return ProgressService
