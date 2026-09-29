--!strict
-- The always-on HUD: level badge and XP bar, gold and Lumen, the clock and market status,
-- the quest card, the market strip (stock, appeal, residents), the menu buttons, the touch
-- combat buttons, and one stack for toasts and notification cards, plus banners.
--
-- Two layouts share the same pieces. On a desktop the status sits on the left under the chat
-- and the quest card on the right under the player list. On a phone (compact) everything moves
-- to the top edge and the right-hand column, clear of the thumbstick, and the combat buttons
-- sit beside Roblox's jump button.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Config = require(Shared.Config)
local DayCycle = require(Shared.DayCycle)
local Palette = require(Shared.Palette)

local State = require(script.Parent.Parent.State)
local Sky = require(script.Parent.Parent.Sky)
local Theme = require(script.Parent.Theme)

local HUD = {}

local C = Theme.C
local F = Theme.Font
local W = Palette.white

local gui: ScreenGui
HUD.buildButton = nil :: Theme.Button?
HUD.onBuild = function() end
HUD.onJournal = function(_tab: string?) end
HUD.onSettings = function() end
HUD.onAttack = function() end
HUD.onBurst = function() end
HUD.burstReadyAt = function(): number
	return 0
end

function HUD.gui(): ScreenGui
	return gui
end

local compact = false
local mode = "play"

-- ─── a counting number ─────────────────────────────────────────────────────
type Counter = { label: TextLabel, value: number, shown: number, prefix: string }
local counters: { Counter } = {}
local function counter(label: TextLabel, prefix: string): Counter
	local c: Counter = { label = label, value = 0, shown = 0, prefix = prefix }
	table.insert(counters, c)
	return c
end

-- ─── the notification stack (toasts and cards) ─────────────────────────────
local stack: Frame
local MAX_STACK = 4

local function fadeOut(f: GuiObject, t: number)
	Theme.tween(f, t, { BackgroundTransparency = 1 })
	for _, d in f:GetDescendants() do
		if d:IsA("TextLabel") then
			Theme.tween(d, t, { TextTransparency = 1 })
		elseif d:IsA("UIStroke") then
			Theme.tween(d, t, { Transparency = 1 })
		elseif d:IsA("Frame") and d.BackgroundTransparency < 1 then
			Theme.tween(d, t, { BackgroundTransparency = 1 })
		end
	end
end

local order = 0
local function push(f: GuiObject, hold: number)
	order += 1
	f.LayoutOrder = order
	local items: { GuiObject } = {}
	for _, k in stack:GetChildren() do
		if k:IsA("GuiObject") then
			table.insert(items, k)
		end
	end
	table.sort(items, function(a, b)
		return a.LayoutOrder < b.LayoutOrder
	end)
	-- only the newest few stay
	for i = 1, #items - MAX_STACK do
		items[i]:Destroy()
	end
	Theme.pop(f, 0.7)
	task.delay(hold, function()
		if f.Parent then
			fadeOut(f, 0.25)
			task.wait(0.27)
			f:Destroy()
		end
	end)
end

local function toast(text: string, icon: string?, tone: string?)
	if tone == "hurt" then
		local v = gui:FindFirstChild("Hurt")
		if v and v:IsA("Frame") then
			v.BackgroundTransparency = 0.55
			Theme.tween(v, 0.5, { BackgroundTransparency = 1 })
		end
		return
	end
	if text == "" then
		return
	end
	local color = tone == "warn" and C.red or (tone == "good" and C.green or C.royal)
	local f = Theme.frame(stack, UDim2.fromOffset(0, 44), nil, C.parchment)
	f.AutomaticSize = Enum.AutomaticSize.X
	Theme.corner(f, 22)
	Theme.stroke(f, color, 3)
	Theme.pad(f, 16, 0)
	Theme.list(f, false, 8, Enum.HorizontalAlignment.Left, Enum.VerticalAlignment.Center)
	local i = Theme.label(f, icon or (tone == "warn" and "⚠️" or "✨"), 24, C.ink, F.title)
	i.AutomaticSize = Enum.AutomaticSize.X
	i.Size = UDim2.fromOffset(0, 40)
	i.TextWrapped = false
	i.LayoutOrder = 1
	local l = Theme.label(f, text, 20, C.ink, F.body)
	l.AutomaticSize = Enum.AutomaticSize.X
	l.Size = UDim2.fromOffset(0, 40)
	l.TextWrapped = false
	l.TextYAlignment = Enum.TextYAlignment.Center
	l.LayoutOrder = 2
	push(f, 3.6)
end
HUD.toast = toast

-- A bigger notification: a quest done, a feat, a new visitor for the Codex.
function HUD.card(icon: string, title: string, lines: { string }, color: Color3, hold: number)
	local f = Theme.panel(stack, UDim2.fromOffset(400, 0), nil, nil)
	f.AutomaticSize = Enum.AutomaticSize.Y
	local st = f:FindFirstChildOfClass("UIStroke")
	if st then
		st.Color = color
		st.Thickness = 4
	end
	Theme.pad(f, 12, 10)
	local ic = Theme.label(f, icon, 46, C.ink, F.title)
	ic.Size = UDim2.fromOffset(62, 62)
	ic.TextXAlignment = Enum.TextXAlignment.Center
	ic.TextYAlignment = Enum.TextYAlignment.Center
	local body = Theme.frame(f, UDim2.new(1, -72, 0, 0), UDim2.fromOffset(72, 0), W, 1)
	body.AutomaticSize = Enum.AutomaticSize.Y
	Theme.list(body, true, 2)
	local t = Theme.label(body, title, 22, C.royalDeep, F.title)
	t.AutomaticSize = Enum.AutomaticSize.Y
	t.Size = UDim2.new(1, 0, 0, 0)
	t.LayoutOrder = 0
	for i, line in lines do
		if line ~= "" then
			local l = Theme.label(body, line, 16, i == 1 and C.ink or C.inkSoft, i == 1 and F.title or F.body)
			l.AutomaticSize = Enum.AutomaticSize.Y
			l.Size = UDim2.new(1, 0, 0, 0)
			l.LayoutOrder = i
		end
	end
	push(f, hold)
end

-- ─── banners (phase changes, surges, news) ─────────────────────────────────
-- A banner takes the top slot under the clock and pushes the notification stack down.
local bannerHolder: Frame
local bannerUp = false
local baseY = 74

local function restack()
	local y = mode == "build" and 104 or baseY
	bannerHolder.Position = UDim2.new(0.5, 0, 0, y)
	stack.Position = UDim2.new(0.5, 0, 0, y + (bannerUp and 104 or 0))
end

function HUD.banner(title: string, sub: string?, color: Color3?, hold: number?)
	bannerHolder:ClearAllChildren()
	local f = Theme.frame(bannerHolder, UDim2.fromScale(1, 1), nil, C.royalDeep, 0.15)
	Theme.corner(f, 18)
	Theme.stroke(f, color or C.gold, 3)
	Theme.gradient(f, (color or C.royal):Lerp(Color3.new(0, 0, 0), 0.2), C.royalDeep, 90)
	local t = Theme.label(f, title, 38, W, F.title)
	t.Size = UDim2.new(1, -24, 0.58, 0)
	t.Position = UDim2.fromOffset(12, 0)
	t.TextXAlignment = Enum.TextXAlignment.Center
	t.TextYAlignment = Enum.TextYAlignment.Bottom
	t.TextWrapped = false
	Theme.textStroke(t, C.shadow, 2)
	if sub then
		local s = Theme.label(f, sub, 20, C.parchment, F.body)
		s.Position = UDim2.new(0, 12, 0.6, 0)
		s.Size = UDim2.new(1, -24, 0.36, 0)
		s.TextXAlignment = Enum.TextXAlignment.Center
	end
	bannerHolder.Visible = true
	bannerUp = true
	restack()
	Theme.pop(f, 0.5)
	local id = os.clock()
	bannerHolder:SetAttribute("Shown", id)
	task.delay(hold or 3.2, function()
		if bannerHolder:GetAttribute("Shown") == id then
			fadeOut(f, 0.3)
			task.wait(0.32)
			if bannerHolder:GetAttribute("Shown") == id then
				bannerHolder.Visible = false
				bannerUp = false
				restack()
			end
		end
	end)
end

-- ─── building the HUD ──────────────────────────────────────────────────────
local levelLabel: TextLabel
local rankLabel: TextLabel
local xpBar: Theme.Bar
local xpText: TextLabel
local goldCounter: Counter
local lumenCounter: Counter
local clockLabel: TextLabel
local statusLabel: TextLabel
local phaseBar: Theme.Bar
local questCard: Frame
local questTitle: TextLabel
local questGiver: TextLabel
local questText: TextLabel
local questBar: Theme.Bar
local questCount: TextLabel
local claimButton: Theme.Button
local ordersLabel: TextLabel
local ordersRoot: GuiObject
local stockLabels: { [string]: TextLabel } = {}
local appealLabel: TextLabel
local residentsLabel: TextLabel
local roadLabel: TextLabel
local mobile: Frame
local burstCooldown: Frame
local menuRow: Frame
local marketStrip: Frame
local statusCluster: Frame

local function pill(parent: Instance, icon: string, color: Color3, order: number): (Frame, TextLabel)
	local f = Theme.frame(parent, UDim2.fromOffset(150, 40), nil, C.royalDeep, 0.1)
	f.LayoutOrder = order
	Theme.corner(f, 20)
	Theme.stroke(f, color, 2)
	local ic = Theme.frame(f, UDim2.fromOffset(40, 40), UDim2.fromOffset(-4, 0), color)
	Theme.corner(ic, 20)
	Theme.stroke(ic, color:Lerp(Color3.new(0, 0, 0), 0.4), 2)
	local il = Theme.label(ic, icon, 22, W, F.title)
	il.Size = UDim2.fromScale(1, 1)
	il.TextXAlignment = Enum.TextXAlignment.Center
	il.TextYAlignment = Enum.TextYAlignment.Center
	local v = Theme.label(f, "0", 24, W, F.title)
	v.Position = UDim2.fromOffset(44, 0)
	v.Size = UDim2.new(1, -56, 1, 0)
	v.TextXAlignment = Enum.TextXAlignment.Right
	v.TextYAlignment = Enum.TextYAlignment.Center
	v.TextWrapped = false
	Theme.textStroke(v, C.shadow, 1.5)
	return f, v
end

local function buildStatus()
	local holder = Theme.frame(gui, UDim2.fromOffset(330, 134), nil, W, 1)
	holder.Name = "Status"
	statusCluster = holder
	-- level badge
	local badge = Theme.frame(holder, UDim2.fromOffset(72, 72), UDim2.fromOffset(0, 0), C.gold)
	Theme.corner(badge, 36)
	Theme.stroke(badge, C.goldDeep, 4)
	Theme.gradient(badge, Color3.fromRGB(255, 226, 140), C.goldDeep, 90)
	local lvCap = Theme.label(badge, "LEVEL", 11, C.ink, F.title)
	lvCap.Position = UDim2.fromOffset(0, 8)
	lvCap.Size = UDim2.new(1, 0, 0, 14)
	lvCap.TextXAlignment = Enum.TextXAlignment.Center
	levelLabel = Theme.label(badge, "1", 34, W, F.title)
	levelLabel.Position = UDim2.fromOffset(0, 20)
	levelLabel.Size = UDim2.new(1, 0, 0, 40)
	levelLabel.TextXAlignment = Enum.TextXAlignment.Center
	Theme.textStroke(levelLabel, C.goldDeep, 2)
	-- rank and XP
	rankLabel = Theme.label(holder, "⛺ Exile's Camp", 22, W, F.title)
	rankLabel.Position = UDim2.fromOffset(84, 6)
	rankLabel.Size = UDim2.fromOffset(240, 26)
	rankLabel.TextWrapped = false
	Theme.textStroke(rankLabel, C.shadow, 2)
	xpBar = Theme.bar(holder, UDim2.fromOffset(236, 18), C.lumen)
	xpBar.root.Position = UDim2.fromOffset(84, 38)
	Theme.stroke(xpBar.root, C.shadow, 2, 0.3)
	xpText = Theme.label(xpBar.root, "0 / 110 XP", 13, W, F.title)
	xpText.Size = UDim2.fromScale(1, 1)
	xpText.TextXAlignment = Enum.TextXAlignment.Center
	xpText.TextYAlignment = Enum.TextYAlignment.Center
	Theme.textStroke(xpText, C.shadow, 1.5)
	-- gold and Lumen
	local row = Theme.frame(holder, UDim2.fromOffset(320, 40), UDim2.fromOffset(4, 88), W, 1)
	Theme.list(row, false, 14)
	local _, g = pill(row, "🪙", C.gold, 1)
	local _, l = pill(row, "💠", C.lumen, 2)
	goldCounter = counter(g, "")
	lumenCounter = counter(l, "")
end

local function buildClock()
	local f = Theme.frame(gui, UDim2.fromOffset(300, 58), UDim2.new(0.5, 0, 0, 8), C.royalDeep, 0.1)
	f.Name = "Clock"
	f.AnchorPoint = Vector2.new(0.5, 0)
	Theme.corner(f, 16)
	Theme.stroke(f, C.gold, 2)
	clockLabel = Theme.label(f, "☀️ 09:00 · Day 1", 24, W, F.title)
	clockLabel.Size = UDim2.new(1, 0, 0, 30)
	clockLabel.Position = UDim2.fromOffset(0, 3)
	clockLabel.TextXAlignment = Enum.TextXAlignment.Center
	clockLabel.TextWrapped = false
	Theme.textStroke(clockLabel, C.shadow, 1.5)
	statusLabel = Theme.label(f, "Market day", 15, C.parchmentDark, F.body)
	statusLabel.Size = UDim2.new(1, 0, 0, 18)
	statusLabel.Position = UDim2.fromOffset(0, 30)
	statusLabel.TextXAlignment = Enum.TextXAlignment.Center
	statusLabel.TextWrapped = false
	phaseBar = Theme.bar(f, UDim2.new(1, -24, 0, 4), C.gold)
	phaseBar.root.Position = UDim2.new(0, 12, 1, -7)
end

local function buildQuest()
	questCard = Theme.panel(gui, UDim2.fromOffset(300, 150), nil, Vector2.new(1, 0))
	questCard.Name = "Quest"
	Theme.pad(questCard, 12, 10)
	questGiver = Theme.label(questCard, "🔥 Flicker", 16, C.inkSoft, F.title)
	questGiver.Size = UDim2.new(1, -60, 0, 18)
	questGiver.TextWrapped = false
	questCount = Theme.label(questCard, "1/20", 14, C.inkSoft, F.title)
	questCount.Size = UDim2.new(0, 60, 0, 18)
	questCount.Position = UDim2.new(1, -60, 0, 0)
	questCount.TextXAlignment = Enum.TextXAlignment.Right
	questTitle = Theme.label(questCard, "Your Realm Awaits", 21, C.royalDeep, F.title)
	questTitle.Position = UDim2.fromOffset(0, 18)
	questTitle.Size = UDim2.new(1, 0, 0, 24)
	questTitle.TextWrapped = false
	questText = Theme.label(questCard, "", 15, C.ink, F.light)
	questText.Position = UDim2.fromOffset(0, 44)
	questText.Size = UDim2.new(1, 0, 0, 52)
	questText.TextYAlignment = Enum.TextYAlignment.Top
	questBar = Theme.bar(questCard, UDim2.new(1, 0, 0, 14), C.green, C.parchmentDark)
	questBar.root.Position = UDim2.new(0, 0, 1, -16)
	claimButton = Theme.button(questCard, "✨ Claim reward!", UDim2.new(1, 0, 0, 36), C.gold, function()
		task.spawn(function()
			local res = State.request("claimQuest")
			if not res.ok then
				toast(res.reason or "Not yet.", "📜", "warn")
			end
		end)
	end, 18)
	claimButton.root.Position = UDim2.new(0, 0, 1, -40)
	claimButton.root.Visible = false
	claimButton.root.ZIndex = 3
	-- the rest of the card opens the Journal at the quest list
	local open = Instance.new("TextButton")
	open.Name = "Open"
	open.Text = ""
	open.AutoButtonColor = false
	open.BackgroundTransparency = 1
	open.Size = UDim2.new(1, 24, 1, 20)
	open.Position = UDim2.fromOffset(-12, -10)
	open.ZIndex = 2
	open.Parent = questCard
	open.Activated:Connect(function()
		Theme.sound("click")
		HUD.onJournal("quests")
	end)
	-- Royal Orders shortcut
	local orders = Theme.button(gui, "📜 Royal Orders", UDim2.fromOffset(300, 38), C.royal, function()
		HUD.onJournal("orders")
	end, 18)
	orders.root.AnchorPoint = Vector2.new(1, 0)
	orders.root.Name = "Orders"
	ordersRoot = orders.root
	ordersLabel = orders.label
end

local function buildMarketStrip()
	marketStrip = Theme.frame(gui, UDim2.fromOffset(0, 44), nil, C.royalDeep, 0.15)
	marketStrip.Name = "Market"
	marketStrip.AutomaticSize = Enum.AutomaticSize.X
	Theme.corner(marketStrip, 14)
	Theme.stroke(marketStrip, C.gold, 2)
	Theme.pad(marketStrip, 12, 0)
	Theme.list(marketStrip, false, 14, Enum.HorizontalAlignment.Left, Enum.VerticalAlignment.Center)
	local function item(text: string, order: number): TextLabel
		local l = Theme.label(marketStrip, text, 20, W, F.title)
		l.AutomaticSize = Enum.AutomaticSize.X
		l.Size = UDim2.fromOffset(0, 40)
		l.TextWrapped = false
		l.TextYAlignment = Enum.TextYAlignment.Center
		l.LayoutOrder = order
		Theme.textStroke(l, C.shadow, 1.5)
		return l
	end
	for i, g in Catalog.GoodsOrder do
		stockLabels[g] = item(Catalog.Goods[g].icon .. " 0", i)
	end
	appealLabel = item("🌸 0", 10)
	roadLabel = item("🏮 0%", 11)
	residentsLabel = item("👥 0/0", 12)
end

local function buildMenu()
	local touch = UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
	menuRow = Theme.frame(gui, UDim2.fromOffset(300, 96), nil, W, 1)
	menuRow.Name = "Menu"
	Theme.list(menuRow, false, 10, Enum.HorizontalAlignment.Right, Enum.VerticalAlignment.Bottom)
	local s = Theme.round(menuRow, "⚙️", 48, C.inkSoft, function()
		HUD.onSettings()
	end, "Settings")
	s.item.LayoutOrder = 1
	local j = Theme.round(menuRow, "📖", 60, C.royal, function()
		HUD.onJournal()
	end, touch and "Journal" or "Journal [J]")
	j.item.LayoutOrder = 2
	local b = Theme.round(menuRow, "🔨", 72, C.gold, function()
		HUD.onBuild()
	end, touch and "Build" or "Build [B]")
	b.item.LayoutOrder = 3
	HUD.buildButton = b
end

local function buildMobile()
	mobile = Theme.frame(gui, UDim2.fromOffset(190, 150), nil, W, 1)
	mobile.Name = "Mobile"
	mobile.AnchorPoint = Vector2.new(1, 1)
	local attack = Theme.round(mobile, "⚔️", 96, C.red, function()
		HUD.onAttack()
	end, nil)
	attack.root.AnchorPoint = Vector2.new(1, 1)
	attack.root.Position = UDim2.fromScale(1, 1)
	local burst = Theme.round(mobile, "✨", 66, C.lumen, function()
		HUD.onBurst()
	end, nil)
	burst.root.Position = UDim2.fromOffset(0, 0)
	burstCooldown = Theme.frame(burst.root, UDim2.fromScale(1, 1), nil, C.shadow, 0.35)
	Theme.corner(burstCooldown, 40)
	burstCooldown.ZIndex = 5
	burstCooldown.Visible = false
end

-- ─── layout ────────────────────────────────────────────────────────────────

-- Where Roblox puts its touch jump button: offset from the right, offset from the bottom, and
-- size, in screen pixels.
local function jumpButton(v: Vector2): (number, number, number)
	if math.min(v.X, v.Y) <= 500 then
		return 95, 90, 70
	end
	return 170, 210, 120
end

local function layout(isCompact: boolean, scale: number)
	compact = isCompact
	local v = workspace.CurrentCamera.ViewportSize
	if compact then
		statusCluster.Position = UDim2.fromOffset(14, 8)
		questCard.Position = UDim2.new(1, -14, 0, 8)
		ordersRoot.Position = UDim2.new(1, -14, 0, 166)
		menuRow.AnchorPoint = Vector2.new(1, 0)
		menuRow.Position = UDim2.new(1, -14, 0, 212)
		marketStrip.AnchorPoint = Vector2.new(0.5, 0)
		marketStrip.Position = UDim2.new(0.5, 0, 0, 72)
		baseY = 124
	else
		statusCluster.Position = UDim2.new(0, 14, 0.3, 0)
		questCard.Position = UDim2.new(1, -14, 0.4, 0)
		ordersRoot.Position = UDim2.new(1, -14, 0.4, 158)
		menuRow.AnchorPoint = Vector2.new(1, 1)
		menuRow.Position = UDim2.new(1, -14, 1, -10)
		marketStrip.AnchorPoint = Vector2.new(0, 1)
		marketStrip.Position = UDim2.new(0, 14, 1, -14)
		baseY = 74
	end
	-- the combat buttons sit just left of the jump button, bottoms lined up
	local right, bottom, size = jumpButton(v)
	mobile.Position = UDim2.new(1, -(right / scale) - 10, 1, -((bottom - size) / scale))
	restack()
end

-- ─── updates ───────────────────────────────────────────────────────────────
local lastLevel = 0
local lastGold = -1
local function onProfile(p: any)
	if not p then
		return
	end
	levelLabel.Text = tostring(p.level)
	rankLabel.Text = string.format("%s %s", p.rankIcon or "⛺", p.rank or "")
	local need = math.max(1, p.need or 1)
	xpBar.set(p.xp / need, lastLevel == p.level)
	xpText.Text = string.format("%s / %s XP", Theme.formatNumber(p.xp), Theme.formatNumber(need))
	if lastLevel ~= 0 and p.level > lastLevel then
		Theme.pop(levelLabel.Parent :: GuiObject, 0.5)
	end
	lastLevel = p.level
	goldCounter.value = p.gold
	lumenCounter.value = p.lumen
	if lastGold >= 0 and p.gold > lastGold then
		Theme.pop(goldCounter.label.Parent :: GuiObject, 0.92)
	end
	lastGold = p.gold
	local q = p.quest
	if q then
		questCard.Visible = mode == "play"
		local npc = Catalog.Npcs[q.giver]
		questGiver.Text = string.format("%s %s", npc and npc.icon or "📜", q.giver)
		questTitle.Text = q.title
		questText.Text = q.text
		questCount.Text = string.format("%d/%d", q.index, q.total)
		questBar.set(q.progress / math.max(1, q.target), true)
		claimButton.root.Visible = q.ready
		questBar.root.Visible = not q.ready
		if q.ready then
			claimButton.setText(string.format("✨ Claim  %s%s%s", q.gold > 0 and ("+" .. q.gold .. "🪙 ") or "", q.lumen > 0 and ("+" .. q.lumen .. "💠 ") or "", q.xp > 0 and ("+" .. q.xp .. " XP") or ""))
		end
	else
		questCard.Visible = false
	end
	local done, ready = 0, 0
	for _, o in p.orders or {} do
		if o.claimed then
			done += 1
		elseif o.progress >= o.target then
			ready += 1
		end
	end
	ordersLabel.Text = ready > 0 and string.format("📜 Royal Orders  ✨%d ready!", ready) or string.format("📜 Royal Orders  %d/%d", done, #(p.orders or {}))
end

local function onPlot(s: any)
	if not s then
		return
	end
	for g, l in stockLabels do
		local n = s.stock and s.stock[g] or 0
		local def = Catalog.Goods[g]
		local unlocked = State.profile == nil or (State.profile.level or 1) >= def.level
		l.Visible = unlocked
		l.Text = string.format("%s %d", def.icon, n)
		l.TextColor3 = n <= 0 and Color3.fromRGB(255, 150, 140) or (n >= (s.cap or 60) and Color3.fromRGB(180, 255, 180) or W)
	end
	appealLabel.Text = "🌸 " .. tostring(s.appeal)
	roadLabel.Text = "🏮 " .. tostring(s.roadLit) .. "%"
	residentsLabel.Text = string.format("👥 %d/%d", s.settlers or 0, s.beds or 0)
end

local phaseIcon = { day = "☀️", dusk = "🌆", night = "🌙", dawn = "🌅" }
local function updateClock()
	local c = Sky.clock
	clockLabel.Text = string.format("%s %s · Day %d", phaseIcon[c.phase] or "☀️", DayCycle.clockText(c.hours), c.day)
	phaseBar.set(c.progress, false)
	if c.phase == "night" then
		statusLabel.Text = "🏮 Lantern Market · prices +25%"
		statusLabel.TextColor3 = Color3.fromRGB(255, 214, 150)
	elseif c.phase == "dusk" then
		statusLabel.Text = "The Lantern Market opens"
		statusLabel.TextColor3 = Color3.fromRGB(255, 200, 160)
	elseif c.phase == "dawn" then
		statusLabel.Text = "Dawn: the Veil retreats"
		statusLabel.TextColor3 = C.parchmentDark
	else
		local left = DayCycle.untilNext(c.t)
		statusLabel.Text = string.format("Market day · dusk in %d:%02d", left // 60, math.floor(left % 60))
		statusLabel.TextColor3 = C.parchmentDark
	end
end

function HUD.setMode(m: string)
	mode = m
	local play = m == "play"
	questCard.Visible = play and State.profile ~= nil and State.profile.quest ~= nil
	ordersRoot.Visible = play
	mobile.Visible = play and UserInputService.TouchEnabled
	marketStrip.Visible = play
	statusCluster.Visible = play
	menuRow.Visible = play
	restack()
end

function HUD.start(parent: Instance)
	gui = Instance.new("ScreenGui")
	gui.Name = "KingsbloomHUD"
	gui.ResetOnSpawn = false
	gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	gui.DisplayOrder = 1
	gui.Parent = parent
	local hurt = Theme.frame(gui, UDim2.fromScale(1, 1), nil, Color3.fromRGB(200, 20, 30), 1)
	hurt.Name = "Hurt"
	hurt.ZIndex = 0
	local hg = Instance.new("UIGradient")
	hg.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(0.35, 1), NumberSequenceKeypoint.new(0.65, 1), NumberSequenceKeypoint.new(1, 0) })
	hg.Parent = hurt
	buildStatus()
	buildClock()
	buildQuest()
	buildMarketStrip()
	buildMenu()
	buildMobile()
	mobile.Visible = UserInputService.TouchEnabled
	stack = Theme.frame(gui, UDim2.fromOffset(700, 0), nil, W, 1)
	stack.Name = "Notifications"
	stack.AnchorPoint = Vector2.new(0.5, 0)
	Theme.list(stack, true, 6, Enum.HorizontalAlignment.Center)
	bannerHolder = Theme.frame(gui, UDim2.fromOffset(600, 96), nil, W, 1)
	bannerHolder.Name = "Banner"
	bannerHolder.AnchorPoint = Vector2.new(0.5, 0)
	bannerHolder.Visible = false
	Theme.autoScale(gui, layout)
	State.profileChanged.connect(onProfile)
	State.plotChanged.connect(onPlot)
	State.toast.connect(toast)
	State.modeChanged.connect(HUD.setMode)
	local acc = 0
	RunService.RenderStepped:Connect(function(dt: number)
		for _, c in counters do
			if c.shown ~= c.value then
				local diff = c.value - c.shown
				local stepSize = math.max(1, math.abs(diff) * math.min(1, dt * 8))
				if math.abs(diff) <= stepSize then
					c.shown = c.value
				else
					c.shown += math.sign(diff) * stepSize
				end
				c.label.Text = c.prefix .. Theme.formatNumber(c.shown)
			end
		end
		acc += dt
		if acc > 0.25 then
			acc = 0
			updateClock()
			local ready = HUD.burstReadyAt()
			local left = ready - os.clock()
			burstCooldown.Visible = left > 0
			if left > 0 then
				burstCooldown.Size = UDim2.fromScale(1, math.clamp(left / Config.BURST_COOLDOWN, 0, 1))
			end
		end
	end)
end

return HUD
