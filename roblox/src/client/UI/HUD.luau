--!strict
-- The always-on HUD: level badge and XP bar, gold and Lumen, the clock and market status,
-- the quest card, the market strip (stock, appeal, residents), side buttons, mobile combat
-- buttons, toasts and banners.

local GuiService = game:GetService("GuiService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

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
local scale: UIScale
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

-- ─── a counting number ─────────────────────────────────────────────────────
type Counter = { label: TextLabel, value: number, shown: number, prefix: string }
local counters: { Counter } = {}
local function counter(label: TextLabel, prefix: string): Counter
	local c: Counter = { label = label, value = 0, shown = 0, prefix = prefix }
	table.insert(counters, c)
	return c
end

-- ─── toasts ────────────────────────────────────────────────────────────────
local toastHolder: Frame
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
	local f = Theme.frame(toastHolder, UDim2.fromOffset(0, 44), nil, C.parchment)
	f.AutomaticSize = Enum.AutomaticSize.X
	Theme.corner(f, 22)
	Theme.stroke(f, color, 3)
	Theme.pad(f, 16, 0)
	Theme.list(f, false, 8, Enum.HorizontalAlignment.Left, Enum.VerticalAlignment.Center)
	local i = Theme.label(f, icon or (tone == "warn" and "⚠️" or "✨"), 24, C.ink, F.title)
	i.AutomaticSize = Enum.AutomaticSize.X
	i.Size = UDim2.fromOffset(0, 40)
	i.TextWrapped = false
	local l = Theme.label(f, text, 20, C.ink, F.body)
	l.AutomaticSize = Enum.AutomaticSize.X
	l.Size = UDim2.fromOffset(0, 40)
	l.TextWrapped = false
	l.TextYAlignment = Enum.TextYAlignment.Center
	Theme.pop(f, 0.7)
	local kids = toastHolder:GetChildren()
	local frames = {}
	for _, k in kids do
		if k:IsA("Frame") then
			table.insert(frames, k)
		end
	end
	if #frames > 3 then
		frames[1]:Destroy()
	end
	task.delay(3.6, function()
		if f.Parent then
			Theme.tween(f, 0.25, { BackgroundTransparency = 1 })
			for _, d in f:GetDescendants() do
				if d:IsA("TextLabel") then
					Theme.tween(d, 0.25, { TextTransparency = 1 })
				elseif d:IsA("UIStroke") then
					Theme.tween(d, 0.25, { Transparency = 1 })
				end
			end
			task.wait(0.27)
			f:Destroy()
		end
	end)
end
HUD.toast = toast

-- ─── banners (phase changes, surges, news) ─────────────────────────────────
local bannerHolder: Frame
function HUD.banner(title: string, sub: string?, color: Color3?, hold: number?)
	bannerHolder:ClearAllChildren()
	local f = Theme.frame(bannerHolder, UDim2.fromScale(1, 1), nil, C.royalDeep, 0.15)
	Theme.corner(f, 18)
	Theme.stroke(f, color or C.gold, 3)
	Theme.gradient(f, (color or C.royal):Lerp(Color3.new(0, 0, 0), 0.2), C.royalDeep, 90)
	local t = Theme.label(f, title, 38, W, F.title)
	t.Size = UDim2.new(1, 0, 0.6, 0)
	t.TextXAlignment = Enum.TextXAlignment.Center
	t.TextYAlignment = Enum.TextYAlignment.Bottom
	Theme.textStroke(t, C.shadow, 2)
	if sub then
		local s = Theme.label(f, sub, 20, C.parchment, F.body)
		s.Position = UDim2.fromScale(0, 0.6)
		s.Size = UDim2.new(1, 0, 0.36, 0)
		s.TextXAlignment = Enum.TextXAlignment.Center
	end
	bannerHolder.Visible = true
	Theme.pop(f, 0.5)
	local id = os.clock()
	bannerHolder:SetAttribute("Shown", id)
	task.delay(hold or 3.2, function()
		if bannerHolder:GetAttribute("Shown") == id then
			Theme.tween(f, 0.3, { BackgroundTransparency = 1 })
			for _, d in f:GetDescendants() do
				if d:IsA("TextLabel") then
					Theme.tween(d, 0.3, { TextTransparency = 1 })
				elseif d:IsA("UIStroke") then
					Theme.tween(d, 0.3, { Transparency = 1 })
				end
			end
			task.wait(0.32)
			if bannerHolder:GetAttribute("Shown") == id then
				bannerHolder.Visible = false
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
local sideButtons: Frame
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
	local v = Theme.label(f, "0", 24, W, F.title)
	v.Position = UDim2.fromOffset(44, 0)
	v.Size = UDim2.new(1, -52, 1, 0)
	v.TextXAlignment = Enum.TextXAlignment.Right
	v.TextYAlignment = Enum.TextYAlignment.Center
	Theme.textStroke(v, C.shadow, 1.5)
	return f, v
end

local function buildTopLeft()
	local holder = Theme.frame(gui, UDim2.fromOffset(330, 140), UDim2.new(0, 14, 0.3, 0), W, 1)
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
	Theme.textStroke(rankLabel, C.shadow, 2)
	xpBar = Theme.bar(holder, UDim2.fromOffset(236, 16), C.lumen)
	xpBar.root.Position = UDim2.fromOffset(84, 38)
	Theme.stroke(xpBar.root, C.shadow, 2, 0.3)
	xpText = Theme.label(xpBar.root, "0 / 110 XP", 13, W, F.title)
	xpText.Size = UDim2.fromScale(1, 1)
	xpText.TextXAlignment = Enum.TextXAlignment.Center
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
	Theme.textStroke(clockLabel, C.shadow, 1.5)
	statusLabel = Theme.label(f, "Market day", 15, C.parchmentDark, F.body)
	statusLabel.Size = UDim2.new(1, 0, 0, 18)
	statusLabel.Position = UDim2.fromOffset(0, 30)
	statusLabel.TextXAlignment = Enum.TextXAlignment.Center
	phaseBar = Theme.bar(f, UDim2.new(1, -24, 0, 4), C.gold)
	phaseBar.root.Position = UDim2.new(0, 12, 1, -7)
end

local function buildQuest()
	questCard = Theme.panel(gui, UDim2.fromOffset(300, 150), UDim2.new(1, -14, 0.34, 0), Vector2.new(1, 0))
	questCard.Name = "Quest"
	Theme.pad(questCard, 12, 10)
	questGiver = Theme.label(questCard, "🔥 Flicker", 16, C.inkSoft, F.title)
	questGiver.Size = UDim2.new(1, -60, 0, 18)
	questCount = Theme.label(questCard, "1/20", 14, C.inkSoft, F.title)
	questCount.Size = UDim2.new(0, 60, 0, 18)
	questCount.Position = UDim2.new(1, -60, 0, 0)
	questCount.TextXAlignment = Enum.TextXAlignment.Right
	questTitle = Theme.label(questCard, "Your Realm Awaits", 21, C.royalDeep, F.title)
	questTitle.Position = UDim2.fromOffset(0, 18)
	questTitle.Size = UDim2.new(1, 0, 0, 24)
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
	end, 20)
	claimButton.root.Position = UDim2.new(0, 0, 1, -38)
	claimButton.root.Visible = false
	-- Royal Orders shortcut
	local orders = Theme.button(gui, "📜 Royal Orders", UDim2.fromOffset(300, 38), C.royal, function()
		HUD.onJournal("orders")
	end, 18)
	orders.root.AnchorPoint = Vector2.new(1, 0)
	orders.root.Position = UDim2.new(1, -14, 0.34, 160)
	orders.root.Name = "Orders"
	ordersRoot = orders.root
	ordersLabel = orders.label
end

local function buildMarketStrip()
	marketStrip = Theme.frame(gui, UDim2.fromOffset(0, 44), UDim2.new(0, 14, 1, -14), C.royalDeep, 0.15)
	marketStrip.Name = "Market"
	marketStrip.AnchorPoint = Vector2.new(0, 1)
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

local function buildSide()
	local touch = UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
	sideButtons = Theme.frame(gui, UDim2.fromOffset(84, 290), UDim2.new(1, -14, 1, touch and -250 or -14), W, 1)
	sideButtons.Name = "Side"
	sideButtons.AnchorPoint = Vector2.new(1, 1)
	Theme.list(sideButtons, true, 26, Enum.HorizontalAlignment.Center, Enum.VerticalAlignment.Bottom)
	local b = Theme.round(sideButtons, "🔨", 72, C.gold, function()
		HUD.onBuild()
	end, "Build [B]")
	b.root.LayoutOrder = 3
	HUD.buildButton = b
	local j = Theme.round(sideButtons, "📖", 58, C.royal, function()
		HUD.onJournal()
	end, "Journal [J]")
	j.root.LayoutOrder = 2
	local s = Theme.round(sideButtons, "⚙️", 48, C.inkSoft, function()
		HUD.onSettings()
	end, nil)
	s.root.LayoutOrder = 1
end

local function buildMobile()
	mobile = Theme.frame(gui, UDim2.fromOffset(230, 200), UDim2.new(1, -150, 1, -24), W, 1)
	mobile.Name = "Mobile"
	mobile.AnchorPoint = Vector2.new(1, 1)
	mobile.Visible = UserInputService.TouchEnabled
	local attack = Theme.round(mobile, "⚔️", 96, C.red, function()
		HUD.onAttack()
	end, nil)
	attack.root.AnchorPoint = Vector2.new(1, 1)
	attack.root.Position = UDim2.new(1, 0, 1, 0)
	local burst = Theme.round(mobile, "✨", 66, C.lumen, function()
		HUD.onBurst()
	end, nil)
	burst.root.AnchorPoint = Vector2.new(1, 1)
	burst.root.Position = UDim2.new(1, -110, 1, -40)
	burstCooldown = Theme.frame(burst.root, UDim2.fromScale(1, 1), nil, C.shadow, 0.35)
	Theme.corner(burstCooldown, 40)
	burstCooldown.ZIndex = 5
	burstCooldown.Visible = false
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
	if lastGold >= 0 and p.gold > lastGold + 0 then
		Theme.pop(goldCounter.label.Parent :: GuiObject, 0.92)
	end
	lastGold = p.gold
	local q = p.quest
	if q then
		questCard.Visible = true
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
		statusLabel.Text = "🏮 Lantern Market · prices +25% · beware the Veil"
		statusLabel.TextColor3 = Color3.fromRGB(255, 214, 150)
	elseif c.phase == "dusk" then
		statusLabel.Text = "The lanterns are lit: the Lantern Market opens"
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

function HUD.setMode(mode: string)
	local play = mode == "play"
	questCard.Visible = play and State.profile ~= nil and State.profile.quest ~= nil
	ordersRoot.Visible = play
	mobile.Visible = play and UserInputService.TouchEnabled
	marketStrip.Visible = play
	statusCluster.Visible = play
	if HUD.buildButton then
		HUD.buildButton.label.Text = play and "🔨" or "✖"
	end
end

function HUD.start(parent: Instance)
	gui = Instance.new("ScreenGui")
	gui.Name = "KingsbloomHUD"
	gui.ResetOnSpawn = false
	gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	gui.ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets
	gui.DisplayOrder = 1
	gui.Parent = parent
	scale = Instance.new("UIScale")
	scale.Parent = gui
	local function rescale()
		local v = Workspace.CurrentCamera.ViewportSize
		local s = math.min(v.X / 1360, v.Y / 780)
		scale.Scale = math.clamp(s * 1.05, 0.6, 1.2)
	end
	rescale()
	Workspace.CurrentCamera:GetPropertyChangedSignal("ViewportSize"):Connect(rescale)
	local hurt = Theme.frame(gui, UDim2.fromScale(1, 1), nil, Color3.fromRGB(200, 20, 30), 1)
	hurt.Name = "Hurt"
	hurt.ZIndex = 0
	local hg = Instance.new("UIGradient")
	hg.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(0.35, 1), NumberSequenceKeypoint.new(0.65, 1), NumberSequenceKeypoint.new(1, 0) })
	hg.Parent = hurt
	buildTopLeft()
	buildClock()
	buildQuest()
	buildMarketStrip()
	buildSide()
	buildMobile()
	toastHolder = Theme.frame(gui, UDim2.fromOffset(700, 200), UDim2.new(0.5, 0, 0, 74), W, 1)
	toastHolder.AnchorPoint = Vector2.new(0.5, 0)
	Theme.list(toastHolder, true, 6, Enum.HorizontalAlignment.Center)
	bannerHolder = Theme.frame(gui, UDim2.fromOffset(560, 96), UDim2.new(0.5, 0, 0.26, 0), W, 1)
	bannerHolder.AnchorPoint = Vector2.new(0.5, 0.5)
	bannerHolder.Visible = false
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
	local _ = GuiService
end

return HUD
