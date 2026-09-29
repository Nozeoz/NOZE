--!strict
-- Panels: the Inspect card for a selected building (stall goods and upgrades, the Heartflame,
-- fields, homes, lamps), the Journal (quests, Royal Orders, achievements, the visitor Codex),
-- Settings, and the remove confirmation.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Palette = require(Shared.Palette)

local State = require(script.Parent.Parent.State)
local Mirror = require(script.Parent.Parent.Mirror)
local Build = require(script.Parent.Parent.Build)
local Audio = require(script.Parent.Parent.Audio)
local Theme = require(script.Parent.Theme)

local Panels = {}

local C = Theme.C
local F = Theme.Font
local W = Palette.white
local B = Catalog.Buildings

local gui: ScreenGui
local inspectFrame: Frame
local inspectBody: Frame
local inspectId: number? = nil
local dim: GuiObject? = nil
local modalName: string? = nil
local modalArg: any = nil
local journalTab = "quests"
local journalShow: ((string) -> ())? = nil
local journalAt = 0

local function request(action: string, args: { [string]: any }?, okSound: string?)
	task.spawn(function()
		local res = State.request(action, args)
		if res.ok then
			if okSound then
				Audio.play(okSound)
			end
		else
			Audio.play("error")
			State.toast.fire(res.reason or "That didn't work.", "⚠️", "warn")
		end
	end)
end

local function row(parent: Instance, height: number, order: number): Frame
	local f = Theme.frame(parent, UDim2.new(1, 0, 0, height), nil, W, 1)
	f.LayoutOrder = order
	return f
end

local function text(parent: Instance, s: string, size: number, color: Color3?, font: Enum.Font?, order: number?): TextLabel
	local l = Theme.label(parent, s, size, color or C.ink, font or F.body)
	l.AutomaticSize = Enum.AutomaticSize.Y
	l.Size = UDim2.new(1, 0, 0, 0)
	l.LayoutOrder = order or 0
	return l
end

-- ─── modals ────────────────────────────────────────────────────────────────
function Panels.close()
	if dim then
		dim:Destroy()
	end
	dim = nil
	modalName = nil
	journalShow = nil
	State.modal = false
end

local function openModal(name: string, title: string, size: Vector2): Frame
	Panels.close()
	State.modal = true
	modalName = name
	-- the dimmed backdrop is a button: a click or tap outside the panel closes it
	local d = Instance.new("TextButton")
	d.Name = "Backdrop"
	d.Text = ""
	d.AutoButtonColor = false
	d.Size = UDim2.fromScale(1, 1)
	d.BackgroundColor3 = C.shadow
	d.BackgroundTransparency = 0.45
	d.BorderSizePixel = 0
	d.ZIndex = 10
	d.Parent = gui
	d.Activated:Connect(Panels.close)
	dim = d
	-- never taller or wider than the screen (phones): the bodies scroll or wrap instead
	local canvas = Theme.canvas()
	local w = math.min(size.X, canvas.X - 24)
	local h = math.min(size.Y, canvas.Y - 16)
	local panel = Theme.panel(d, UDim2.fromOffset(w, h), UDim2.fromScale(0.5, 0.5), Vector2.new(0.5, 0.5))
	panel.ZIndex = 11
	panel.Active = true -- clicks on the panel itself stay there
	local head = Theme.frame(panel, UDim2.new(1, 0, 0, 56), nil, C.royal)
	Theme.corner(head, 16)
	Theme.gradient(head, C.royal, C.royalDeep, 90)
	local t = Theme.label(head, title, 30, W, F.title)
	t.Size = UDim2.new(1, -70, 1, 0)
	t.Position = UDim2.fromOffset(20, 0)
	t.TextYAlignment = Enum.TextYAlignment.Center
	Theme.textStroke(t, C.shadow, 2)
	local x = Theme.round(head, "✖", 40, C.red, Panels.close, nil)
	x.root.AnchorPoint = Vector2.new(1, 0.5)
	x.root.Position = UDim2.new(1, -10, 0.5, 0)
	local body = Theme.frame(panel, UDim2.new(1, -32, 1, -76), UDim2.fromOffset(16, 66), W, 1)
	body.Name = "Body"
	Theme.pop(panel, 0.8)
	Audio.play("whoosh", 1.2, 0.6)
	return body
end

-- ─── the Inspect card ──────────────────────────────────────────────────────
local function stallInfo(id: number): any
	local plot = State.plot
	if not plot or not plot.stalls then
		return nil
	end
	for _, s in plot.stalls do
		if s[1] == id then
			return { goods = s[2], level = s[3], queue = s[4], sold = s[5], noPath = s[6] }
		end
	end
	return nil
end

local function renderInspect()
	for _, c in inspectBody:GetChildren() do
		if not c:IsA("UIListLayout") then
			c:Destroy()
		end
	end
	local id = inspectId
	local o = id and Mirror.object(id)
	if not id or not o then
		inspectFrame.Visible = false
		return
	end
	local def = B[o.type]
	local profile = State.profile or {}
	local lvl = profile.level or 1
	local n = 0
	local function nextOrder(): number
		n += 1
		return n
	end
	local head = row(inspectBody, 48, nextOrder())
	local icon = Theme.label(head, def.icon, 40, C.ink, F.title)
	icon.Size = UDim2.fromOffset(48, 48)
	icon.TextXAlignment = Enum.TextXAlignment.Center
	local name = Theme.label(head, def.name, 24, C.royalDeep, F.title)
	name.Position = UDim2.fromOffset(54, 0)
	name.Size = UDim2.new(1, -54, 1, 0)
	name.TextYAlignment = Enum.TextYAlignment.Center
	text(inspectBody, def.desc, 16, C.inkSoft, F.light, nextOrder())

	if def.stall then
		local info = stallInfo(id) or { goods = o.goods, level = o.level or 1, queue = 0, sold = 0, noPath = false }
		local lv = info.level or 1
		local st = Catalog.StallLevels[lv]
		text(inspectBody, string.format("%s  Price ×%.1f · %.1fs a customer", string.rep("⭐", lv) .. string.rep("☆", #Catalog.StallLevels - lv), st.mult, st.service), 17, C.ink, F.title, nextOrder())
		text(inspectBody, string.format("In line: %d   Sold since dusk: %d", info.queue or 0, info.sold or 0), 16, C.inkSoft, F.body, nextOrder())
		if info.noPath then
			text(inspectBody, "⚠ No path runs past the counter. Paint one, or turn the stall.", 16, C.red, F.title, nextOrder())
		end
		text(inspectBody, "Sells:", 16, C.ink, F.title, nextOrder())
		local goodsRow = row(inspectBody, 50, nextOrder())
		Theme.list(goodsRow, false, 8)
		for i, g in Catalog.GoodsOrder do
			local gd = Catalog.Goods[g]
			local locked = lvl < gd.level
			local b = Theme.button(goodsRow, gd.icon, UDim2.fromOffset(62, 46), info.goods == g and C.gold or C.royal, function()
				if locked then
					State.toast.fire(gd.name .. " unlocks at level " .. gd.level .. ".", "🔒", "warn")
					return
				end
				request("goods", { id = id, g = g }, "pop")
			end, 26)
			b.root.LayoutOrder = i
			if locked then
				b.setEnabled(false)
			end
		end
		local nxt = Catalog.StallLevels[lv + 1]
		if nxt then
			local b = Theme.button(inspectBody, string.format("⭐ Upgrade  %d 🪙  (×%.1f price)", nxt.cost, nxt.mult), UDim2.new(1, 0, 0, 44), C.green, function()
				request("upgrade", { id = id }, "achievement")
			end, 18)
			b.root.LayoutOrder = nextOrder()
			b.setEnabled((profile.gold or 0) >= nxt.cost)
		end
	elseif o.type == "heartflame" then
		local s = Mirror.sim
		local tier = s and s.tier or 1
		local t = Catalog.Heartflame[tier]
		text(inspectBody, string.format("🔥 %s  ·  realm %d tiles wide", t.name, math.floor(t.radius * 2)), 18, C.ink, F.title, nextOrder())
		local nt = Catalog.Heartflame[tier + 1]
		if nt then
			text(inspectBody, "Raise it to " .. nt.name .. ":", 17, C.royalDeep, F.title, nextOrder())
			local okL = lvl >= nt.level
			local okG = (profile.gold or 0) >= nt.gold
			local okM = (profile.lumen or 0) >= nt.lumen
			text(inspectBody, string.format("%s Level %d", okL and "✅" or "❌", nt.level), 17, okL and C.green or C.red, F.title, nextOrder())
			text(inspectBody, string.format("%s %s 🪙", okG and "✅" or "❌", Theme.formatNumber(nt.gold)), 17, okG and C.green or C.red, F.title, nextOrder())
			text(inspectBody, string.format("%s %d 💠 Lumen (from Gloomlings)", okM and "✅" or "❌", nt.lumen), 17, okM and C.green or C.red, F.title, nextOrder())
			text(inspectBody, "The forest falls back, the realm grows and the light reaches farther.", 15, C.inkSoft, F.light, nextOrder())
			local b = Theme.button(inspectBody, "🔥 Raise the Heartflame", UDim2.new(1, 0, 0, 48), C.gold, function()
				request("heart", {}, nil)
			end, 20)
			b.root.LayoutOrder = nextOrder()
			b.setEnabled(okL and okG and okM)
		else
			text(inspectBody, "It burns at its greatest.", 17, C.green, F.title, nextOrder())
		end
	elseif def.produce or def.convert then
		if def.tendable then
			text(inspectBody, o.ripe and "✨ Ripe! Walk up to it and press E." or "🌱 Growing… it sparkles when ready.", 17, o.ripe and C.green or C.ink, F.title, nextOrder())
		end
		if o.worker then
			text(inspectBody, "👷 " .. o.worker .. " works here (twice as fast).", 16, C.ink, F.body, nextOrder())
		else
			text(inspectBody, "No worker yet. A settler would double its output.", 16, C.inkSoft, F.body, nextOrder())
		end
		local secs = def.seconds or 14
		local out = def.produce and next(def.produce) or (def.convert and next(def.convert.output))
		local g = out and Catalog.Goods[out]
		if g then
			text(inspectBody, string.format("Makes 1 %s %s every %ds by day.", g.icon, g.name, o.worker and secs // 2 or secs), 16, C.inkSoft, F.body, nextOrder())
		end
	elseif def.beds then
		text(inspectBody, string.format("🛏️ %d bed%s. Happy visitors move in when a bed is free.", def.beds, def.beds > 1 and "s" or ""), 16, C.ink, F.body, nextOrder())
	end
	if def.snuffable then
		if o.snuffed then
			text(inspectBody, "🌫️ The Veil snuffed it. Walk up and press E, or relight it from here.", 16, C.red, F.title, nextOrder())
			local b = Theme.button(inspectBody, "🏮 Relight  5 🪙", UDim2.new(1, 0, 0, 44), C.gold, function()
				request("relight", { id = id }, "sparkle")
			end, 18)
			b.root.LayoutOrder = nextOrder()
		else
			text(inspectBody, "🏮 Lit. Gloomlings will try to snuff it at night.", 16, C.inkSoft, F.body, nextOrder())
		end
	end
	if def.appeal then
		text(inspectBody, string.format("🌸 Appeal +%d nearby", def.appeal[1]), 16, C.inkSoft, F.body, nextOrder())
	end
	if not def.fixed then
		local actions = row(inspectBody, 46, nextOrder())
		Theme.list(actions, false, 8)
		local mv = Theme.button(actions, "✥ Move", UDim2.fromOffset(104, 44), C.royal, function()
			Build.startMove(id)
			Panels.inspect(nil)
		end, 17)
		mv.root.LayoutOrder = 1
		if def.variants and def.variants > 1 then
			local st = Theme.button(actions, "🎨 Style", UDim2.fromOffset(104, 44), C.royal, function()
				request("variant", { id = id, v = ((o.variant or 0) + 1) % (def.variants :: number) }, "pop")
			end, 17)
			st.root.LayoutOrder = 2
		end
		local rm = Theme.button(actions, "🧹 Remove", UDim2.fromOffset(110, 44), C.red, function()
			Panels.open("confirmRemove", id)
		end, 17)
		rm.root.LayoutOrder = 3
	end
	inspectFrame.Visible = true
end

function Panels.inspect(id: number?)
	local changed = inspectId ~= id
	inspectId = id
	renderInspect()
	if id and changed then
		Theme.pop(inspectFrame, 0.85)
	end
end

-- ─── the Journal ───────────────────────────────────────────────────────────
local function scroller(body: Frame): ScrollingFrame
	local list = Instance.new("ScrollingFrame")
	list.Size = UDim2.fromScale(1, 1)
	list.BackgroundTransparency = 1
	list.BorderSizePixel = 0
	list.AutomaticCanvasSize = Enum.AutomaticSize.Y
	list.CanvasSize = UDim2.new()
	list.ScrollBarThickness = 6
	list.ScrollBarImageColor3 = C.goldDeep
	list.Parent = body
	return list
end

local function questsTab(body: Frame)
	local p = State.profile
	if not p then
		return
	end
	local list = scroller(body)
	Theme.list(list, true, 8)
	local current = p.quest and p.quest.index or (#Catalog.Quests + 1)
	for i, q in Catalog.Quests do
		local done = i < current
		local active = i == current
		local f = Theme.frame(list, UDim2.new(1, -12, 0, active and 104 or 44), nil, active and Color3.fromRGB(255, 246, 214) or C.parchmentDark, active and 0 or 0.4)
		f.LayoutOrder = i
		Theme.corner(f, 12)
		if active then
			Theme.stroke(f, C.gold, 3)
		end
		local npc = Catalog.Npcs[q.giver]
		local title = Theme.label(f, string.format("%s  %s %s", done and "✅" or (active and "⭐" or "🔒"), npc and npc.icon or "", (done or active) and q.title or "???"), 19, done and C.inkSoft or C.royalDeep, F.title)
		title.Position = UDim2.fromOffset(12, 10)
		title.Size = UDim2.new(1, -24, 0, 24)
		if active and p.quest then
			local t = Theme.label(f, q.text, 15, C.ink, F.light)
			t.Position = UDim2.fromOffset(12, 36)
			t.Size = UDim2.new(1, -24, 0, 40)
			t.TextYAlignment = Enum.TextYAlignment.Top
			local bar = Theme.bar(f, UDim2.new(1, -24, 0, 12), C.green, C.parchmentDark)
			bar.root.Position = UDim2.new(0, 12, 1, -20)
			bar.set(p.quest.progress / math.max(1, p.quest.target))
		end
	end
end

local function ordersTab(body: Frame)
	local p = State.profile
	if not p then
		return
	end
	local list = scroller(body)
	Theme.list(list, true, 12)
	local intro = text(list, "Three fresh orders from the crown every dawn. Finish all three for a Royal Seal: +5 💠.", 16, C.inkSoft, F.body, 0)
	intro.Size = UDim2.new(1, -12, 0, 0)
	for i, o in p.orders or {} do
		local f = Theme.frame(list, UDim2.new(1, -12, 0, 92), nil, o.claimed and C.parchmentDark or Color3.fromRGB(255, 246, 214))
		f.LayoutOrder = i
		Theme.corner(f, 12)
		Theme.stroke(f, o.claimed and C.inkSoft or C.goldDeep, 2)
		local t = Theme.label(f, (o.claimed and "✅ " or "📜 ") .. o.text, 20, C.royalDeep, F.title)
		t.Position = UDim2.fromOffset(14, 10)
		t.Size = UDim2.new(1, -170, 0, 24)
		local r = Theme.label(f, string.format("+%d 🪙  +%d XP", o.gold, o.xp), 16, C.inkSoft, F.title)
		r.Position = UDim2.fromOffset(14, 36)
		r.Size = UDim2.new(1, -170, 0, 20)
		local bar = Theme.bar(f, UDim2.new(1, -184, 0, 14), C.green, C.parchmentDark)
		bar.root.Position = UDim2.new(0, 14, 1, -24)
		bar.set(o.progress / math.max(1, o.target))
		local pl = Theme.label(bar.root, string.format("%d / %d", o.progress, o.target), 12, W, F.title)
		pl.Size = UDim2.fromScale(1, 1)
		pl.TextXAlignment = Enum.TextXAlignment.Center
		Theme.textStroke(pl, C.shadow, 1.5)
		if not o.claimed then
			local ready = o.progress >= o.target
			local b = Theme.button(f, ready and "Claim!" or "In progress", UDim2.fromOffset(140, 48), ready and C.gold or C.inkSoft, function()
				request("claimOrder", { i = o.i }, nil)
			end, 18)
			b.root.AnchorPoint = Vector2.new(1, 0.5)
			b.root.Position = UDim2.new(1, -14, 0.5, 0)
			b.setEnabled(ready)
		end
	end
	if p.sealed then
		text(list, "🏅 Royal Seal earned today!", 18, C.green, F.title, 10)
	end
end

local function achievementsTab(body: Frame)
	local p = State.profile
	if not p then
		return
	end
	local grid = scroller(body)
	local layout = Instance.new("UIGridLayout")
	layout.CellSize = UDim2.fromOffset(216, 104)
	layout.CellPadding = UDim2.fromOffset(10, 10)
	layout.SortOrder = Enum.SortOrder.LayoutOrder
	layout.Parent = grid
	local medals = { "🥉", "🥈", "🥇" }
	for i, a in Catalog.Achievements do
		local have = p.ach and p.ach[a.id] or 0
		local f = Theme.frame(grid, UDim2.new(), nil, have > 0 and Color3.fromRGB(255, 246, 214) or C.parchmentDark)
		f.LayoutOrder = i
		Theme.corner(f, 12)
		Theme.stroke(f, have >= 3 and C.gold or C.goldDeep, have >= 3 and 3 or 1.5)
		local ic = Theme.label(f, a.icon, 34, C.ink, F.title)
		ic.Size = UDim2.fromOffset(46, 46)
		ic.Position = UDim2.fromOffset(8, 8)
		ic.TextXAlignment = Enum.TextXAlignment.Center
		local nm = Theme.label(f, a.name, 18, C.royalDeep, F.title)
		nm.Position = UDim2.fromOffset(60, 8)
		nm.Size = UDim2.new(1, -66, 0, 22)
		nm.TextWrapped = false
		local ds = Theme.label(f, a.desc, 14, C.inkSoft, F.body)
		ds.Position = UDim2.fromOffset(60, 31)
		ds.Size = UDim2.new(1, -66, 0, 34)
		ds.TextYAlignment = Enum.TextYAlignment.Top
		local m = ""
		for t = 1, 3 do
			m ..= t <= have and medals[t] or "⚪"
		end
		local ml = Theme.label(f, m, 18, C.ink, F.title)
		ml.Position = UDim2.fromOffset(8, 72)
		ml.Size = UDim2.fromOffset(90, 22)
		local target = a.tiers[math.min(3, have + 1)]
		local value = a.stat == "level" and p.level or (p.stats and p.stats[a.stat] or 0)
		if a.stat == "discovered" then
			local count = 0
			for _ in p.codex or {} do
				count += 1
			end
			value = count
		end
		local pr = Theme.label(f, have >= 3 and "Complete!" or string.format("%s / %s", Theme.formatNumber(value), Theme.formatNumber(target)), 14, have >= 3 and C.green or C.inkSoft, F.title)
		pr.Position = UDim2.fromOffset(100, 74)
		pr.Size = UDim2.new(1, -110, 0, 18)
		pr.TextXAlignment = Enum.TextXAlignment.Right
	end
end

local function codexTab(body: Frame)
	local p = State.profile
	if not p then
		return
	end
	local grid = scroller(body)
	local layout = Instance.new("UIGridLayout")
	layout.CellSize = UDim2.fromOffset(216, 150)
	layout.CellPadding = UDim2.fromOffset(10, 10)
	layout.SortOrder = Enum.SortOrder.LayoutOrder
	layout.Parent = grid
	for i, k in Catalog.VisitorOrder do
		local def = Catalog.Visitors[k]
		local seen = p.codex and p.codex[k]
		local rc = Catalog.RarityColor[def.rarity]
		local rarity = Color3.fromRGB(rc[1], rc[2], rc[3])
		local f = Theme.frame(grid, UDim2.new(), nil, seen and Color3.fromRGB(255, 246, 214) or C.parchmentDark)
		f.LayoutOrder = i
		Theme.corner(f, 12)
		Theme.stroke(f, rarity, seen and 3 or 1.5)
		local ic = Theme.label(f, seen and def.icon or "❔", 40, C.ink, F.title)
		ic.Size = UDim2.new(1, 0, 0, 48)
		ic.Position = UDim2.fromOffset(0, 6)
		ic.TextXAlignment = Enum.TextXAlignment.Center
		local nm = Theme.label(f, seen and def.name or "???", 18, C.royalDeep, F.title)
		nm.Position = UDim2.fromOffset(0, 54)
		nm.Size = UDim2.new(1, 0, 0, 22)
		nm.TextXAlignment = Enum.TextXAlignment.Center
		local rl = Theme.label(f, def.rarity .. (seen and string.format(" · met %d×", seen) or ""), 13, rarity:Lerp(C.ink, 0.35), F.title)
		rl.Position = UDim2.fromOffset(0, 76)
		rl.Size = UDim2.new(1, 0, 0, 16)
		rl.TextXAlignment = Enum.TextXAlignment.Center
		local ds = Theme.label(f, seen and def.desc or (def.minLevel > (p.level or 1) and ("Appears from level " .. def.minLevel) or "Not met yet"), 13, C.inkSoft, F.light)
		ds.Position = UDim2.fromOffset(8, 94)
		ds.Size = UDim2.new(1, -16, 0, 50)
		ds.TextXAlignment = Enum.TextXAlignment.Center
		ds.TextYAlignment = Enum.TextYAlignment.Top
	end
end

local function journal(tab: string?)
	journalTab = tab or journalTab
	local body = openModal("journal", "📖 Royal Journal", Vector2.new(720, 560))
	local tabs = Theme.frame(body, UDim2.new(1, 0, 0, 44), nil, W, 1)
	Theme.list(tabs, false, 8)
	local content = Theme.frame(body, UDim2.new(1, 0, 1, -54), UDim2.fromOffset(0, 54), W, 1)
	local defs = { { "quests", "⭐ Quests" }, { "orders", "📜 Orders" }, { "achievements", "🏆 Feats" }, { "codex", "📖 Codex" } }
	local buttons: { [string]: Theme.Button } = {}
	local function show(id: string)
		journalTab = id
		for tid, b in buttons do
			b.setColor(tid == id and C.gold or C.royal)
		end
		content:ClearAllChildren()
		if id == "quests" then
			questsTab(content)
		elseif id == "orders" then
			ordersTab(content)
		elseif id == "achievements" then
			achievementsTab(content)
		else
			codexTab(content)
		end
	end
	for i, d in defs do
		local b = Theme.button(tabs, d[2], UDim2.fromOffset(164, 40), C.royal, function()
			show(d[1])
		end, 18)
		b.root.LayoutOrder = i
		buttons[d[1]] = b
	end
	journalShow = show
	show(journalTab)
end

-- ─── settings ──────────────────────────────────────────────────────────────
local function settings()
	local body = openModal("settings", "⚙️ Settings", Vector2.new(520, 470))
	Theme.list(body, true, 12)
	local p = State.profile
	local values = { music = p and p.settings and p.settings.music or 0.5, sfx = p and p.settings and p.settings.sfx or 0.8, amb = p and p.settings and p.settings.amb or 0.6 }
	local function slider(key: string, label: string, order: number)
		local r = row(body, 44, order)
		local l = Theme.label(r, label, 20, C.ink, F.title)
		l.Size = UDim2.new(0, 150, 1, 0)
		l.TextYAlignment = Enum.TextYAlignment.Center
		local bar = Theme.bar(r, UDim2.new(1, -270, 0, 18), C.royal, C.parchmentDark)
		bar.root.Position = UDim2.new(0, 160, 0.5, -9)
		bar.set(values[key])
		local function set(v: number)
			values[key] = math.clamp(math.floor(v * 10 + 0.5) / 10, 0, 1)
			bar.set(values[key], true)
			request("settings", { [key] = values[key] }, nil)
			State.profileChanged.fire(State.profile)
			if State.profile and State.profile.settings then
				State.profile.settings[key] = values[key]
			end
		end
		local minus = Theme.button(r, "−", UDim2.fromOffset(44, 40), C.royal, function()
			set(values[key] - 0.1)
		end, 24)
		minus.root.Position = UDim2.new(1, -100, 0, 0)
		local plus = Theme.button(r, "+", UDim2.fromOffset(44, 40), C.royal, function()
			set(values[key] + 0.1)
		end, 24)
		plus.root.Position = UDim2.new(1, -48, 0, 0)
	end
	slider("music", "🎵 Music", 1)
	slider("sfx", "🔔 Effects", 2)
	slider("amb", "🌿 Ambience", 3)
	local touch = UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
	local controls = touch
			and "<b>Play:</b> stick to move · jump (tap twice to double jump) · ⚔️ swing · ✨ Radiant Burst · tap a prompt to tend or relight\n<b>Build (🔨):</b> one finger drags · two fingers pinch and turn · tap to place, then ✔"
		or "<b>Play:</b> WASD move · Space jump (twice to double jump) · Shift run · Click swing · Q Radiant Burst · E tend/relight\n<b>Build (B):</b> drag to look · right-drag turn · scroll zoom · R rotate · X remove · Esc cancel"
	text(body, controls, 15, C.inkSoft, F.body, 4)
	local tips = Theme.button(body, "💡 Show the welcome tips again", UDim2.new(1, 0, 0, 44), C.royal, function()
		Panels.close()
		State.message.fire("welcome", {})
	end, 18)
	tips.root.LayoutOrder = 5
	local home = Theme.button(body, "🏠 Take me home", UDim2.new(1, 0, 0, 44), C.green, function()
		Panels.close()
		request("home", {}, "whoosh")
	end, 18)
	home.root.LayoutOrder = 6
	if p and not p.saving then
		text(body, "💾 Saving is off this session (in Studio, turn on API access).", 14, C.red, F.title, 7)
	end
end

local function confirmRemove(id: number)
	local o = Mirror.object(id)
	if not o then
		return
	end
	local def = B[o.type]
	local body = openModal("confirmRemove", "🧹 Remove " .. def.name .. "?", Vector2.new(480, 206))
	Theme.list(body, true, 14)
	text(body, "You get half of what it cost back.", 18, C.ink, F.body, 1)
	local r = row(body, 50, 2)
	Theme.list(r, false, 12, Enum.HorizontalAlignment.Center)
	local keep = Theme.button(r, "Keep it", UDim2.fromOffset(170, 48), C.royal, Panels.close, 20)
	keep.root.LayoutOrder = 1
	local rm = Theme.button(r, "🧹 Remove", UDim2.fromOffset(170, 48), C.red, function()
		Panels.close()
		Panels.inspect(nil)
		request("remove", { id = id }, nil)
	end, 20)
	rm.root.LayoutOrder = 2
end

function Panels.open(name: string, arg: any)
	modalArg = arg
	if name == "journal" or name == "orders" then
		journal(name == "orders" and "orders" or arg)
	elseif name == "settings" then
		settings()
	elseif name == "confirmRemove" then
		confirmRemove(arg)
	end
end

function Panels.isOpen(): boolean
	return dim ~= nil
end

function Panels.start(parent: Instance)
	gui = Instance.new("ScreenGui")
	gui.Name = "KingsbloomPanels"
	gui.ResetOnSpawn = false
	gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	gui.DisplayOrder = 5
	gui.Parent = parent
	Theme.autoScale(gui)

	-- bottom right, next to Done; the Build drawer steps aside while it is open
	inspectFrame = Theme.panel(gui, UDim2.fromOffset(350, 0), UDim2.new(1, -120, 1, -16), Vector2.new(1, 1))
	inspectFrame.Name = "Inspect"
	inspectFrame.Active = true -- clicks on the card must not reach the world behind it
	inspectFrame.AutomaticSize = Enum.AutomaticSize.Y
	inspectFrame.Visible = false
	Theme.pad(inspectFrame, 14, 12)
	inspectBody = Theme.frame(inspectFrame, UDim2.new(1, 0, 0, 0), nil, W, 1)
	inspectBody.AutomaticSize = Enum.AutomaticSize.Y
	Theme.list(inspectBody, true, 8)
	local x = Theme.round(inspectFrame, "✖", 34, C.red, function()
		Panels.inspect(nil)
	end, nil)
	x.root.AnchorPoint = Vector2.new(0.5, 0.5)
	x.root.Position = UDim2.new(1, 0, 0, 0)
	x.root.ZIndex = 5

	State.inspect.connect(function(id)
		if State.mode == "build" or id == nil then
			Panels.inspect(id)
		end
	end)
	State.openPanel.connect(function(name, arg)
		Panels.open(name, arg)
	end)
	State.layoutChanged.connect(function()
		if inspectId then
			task.defer(renderInspect)
		end
	end)
	State.plotChanged.connect(function()
		if inspectId then
			renderInspect()
		end
	end)
	State.profileChanged.connect(function()
		-- keep the Journal's quests and orders fresh (claims, progress), without reopening it
		local show = journalShow
		if modalName == "journal" and dim and show and (journalTab == "orders" or journalTab == "quests") and os.clock() - journalAt > 0.8 then
			journalAt = os.clock()
			show(journalTab)
		end
	end)
	State.modeChanged.connect(function(mode)
		if mode ~= "build" then
			Panels.inspect(nil)
		end
	end)
	UserInputService.InputBegan:Connect(function(input)
		if input.KeyCode == Enum.KeyCode.Escape and dim then
			Panels.close()
		end
	end)
	local _ = modalArg
end

return Panels
