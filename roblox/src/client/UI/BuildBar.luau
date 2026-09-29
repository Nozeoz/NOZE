--!strict
-- The Build mode UI: category tabs, building cards (cost that rises as you build more, a lock
-- until the right level, how many you may own), the tool strip, the hint line and Done.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Palette = require(Shared.Palette)

local State = require(script.Parent.Parent.State)
local Mirror = require(script.Parent.Parent.Mirror)
local Build = require(script.Parent.Parent.Build)
local Theme = require(script.Parent.Theme)

local BuildBar = {}

local C = Theme.C
local F = Theme.Font
local W = Palette.white
local B = Catalog.Buildings

local gui: ScreenGui
local root: Frame
local tabsRow: Frame
local cardsFrame: ScrollingFrame
local toolStrip: Frame
local hint: TextLabel
local stats: TextLabel
local rotateButton: Theme.Button
local tab = "light"
local tabButtons: { [string]: Theme.Button } = {}
local toolButtons: { [string]: Theme.Button } = {}
type Card = { id: string, root: TextButton, stroke: UIStroke, cost: TextLabel, lock: Frame, lockText: TextLabel, limit: TextLabel }
local cards: { Card } = {}

local function level(): number
	return State.profile and State.profile.level or 1
end

local function refreshCards()
	local s = Mirror.sim
	for _, c in cards do
		local def = B[c.id]
		local gold, lumen = def.cost, def.lumen or 0
		local count = 0
		if s then
			gold, lumen = s:costOf(c.id)
			count = s:count(c.id)
		end
		c.cost.Text = string.format("%d 🪙%s", gold, lumen > 0 and string.format(" %d 💠", lumen) or "")
		local have = State.profile and State.profile.gold or 0
		c.cost.TextColor3 = have >= gold and C.ink or C.red
		local locked = level() < def.level
		c.lock.Visible = locked
		c.lockText.Text = "🔒 Lv " .. def.level
		local limit = Catalog.limitFor(c.id, level())
		if limit and not locked then
			c.limit.Visible = true
			c.limit.Text = string.format("%d/%d", count, limit)
			c.limit.TextColor3 = count >= limit and C.red or C.inkSoft
		else
			c.limit.Visible = false
		end
		local selected = (Build.tool == "place" and Build.item == c.id) or (c.id == "path" and Build.tool == "paint")
		c.stroke.Color = selected and C.gold or C.goldDeep
		c.stroke.Thickness = selected and 4 or 2
		c.root.BackgroundColor3 = selected and Color3.fromRGB(255, 246, 214) or C.parchment
	end
end

local function card(id: string, order: number): Card
	local def = B[id]
	local b = Instance.new("TextButton")
	b.Name = id
	b.Text = ""
	b.AutoButtonColor = false
	b.LayoutOrder = order
	b.Size = UDim2.fromOffset(126, 128)
	b.BackgroundColor3 = C.parchment
	b.BorderSizePixel = 0
	b.Parent = cardsFrame
	Theme.corner(b, 14)
	local stroke = Theme.stroke(b, C.goldDeep, 2)
	Theme.gradient(b, C.parchment, C.parchmentDark, 90)
	local icon = Theme.label(b, def.icon, 44, C.ink, F.title)
	icon.Size = UDim2.new(1, 0, 0, 56)
	icon.Position = UDim2.fromOffset(0, 4)
	icon.TextXAlignment = Enum.TextXAlignment.Center
	local name = Theme.label(b, def.name, 15, C.royalDeep, F.title)
	name.Size = UDim2.new(1, -8, 0, 34)
	name.Position = UDim2.fromOffset(4, 58)
	name.TextXAlignment = Enum.TextXAlignment.Center
	name.TextYAlignment = Enum.TextYAlignment.Center
	local cost = Theme.label(b, "", 16, C.ink, F.title)
	cost.Size = UDim2.new(1, 0, 0, 20)
	cost.Position = UDim2.new(0, 0, 1, -26)
	cost.TextXAlignment = Enum.TextXAlignment.Center
	local limit = Theme.label(b, "", 13, C.inkSoft, F.title)
	limit.Size = UDim2.fromOffset(50, 16)
	limit.Position = UDim2.new(1, -54, 0, 6)
	limit.TextXAlignment = Enum.TextXAlignment.Right
	local lock = Theme.frame(b, UDim2.fromScale(1, 1), nil, C.shadow, 0.45)
	Theme.corner(lock, 14)
	lock.ZIndex = 3
	local lockText = Theme.label(lock, "🔒", 20, W, F.title)
	lockText.Size = UDim2.fromScale(1, 1)
	lockText.TextXAlignment = Enum.TextXAlignment.Center
	lockText.ZIndex = 4
	Theme.textStroke(lockText, C.shadow, 2)
	local sc = Instance.new("UIScale")
	sc.Parent = b
	b.MouseEnter:Connect(function()
		Theme.tween(sc, 0.12, { Scale = 1.06 })
		Build.info.fire(def.desc)
	end)
	b.MouseLeave:Connect(function()
		Theme.tween(sc, 0.12, { Scale = 1 })
	end)
	b.Activated:Connect(function()
		if level() < def.level then
			Theme.sound("error")
			State.toast.fire(def.name .. " unlocks at level " .. def.level .. ".", "🔒", "warn")
			return
		end
		Build.select(id)
		Build.info.fire(def.desc)
		refreshCards()
	end)
	return { id = id, root = b, stroke = stroke, cost = cost, lock = lock, lockText = lockText, limit = limit }
end

local function showTab(id: string)
	tab = id
	for tid, b in tabButtons do
		b.setColor(tid == id and C.gold or C.royal)
	end
	for _, c in cards do
		c.root:Destroy()
	end
	cards = {}
	local n = 0
	for _, bid in Catalog.BuildOrder do
		if B[bid].cat == id then
			n += 1
			table.insert(cards, card(bid, n))
		end
	end
	cardsFrame.CanvasPosition = Vector2.zero
	refreshCards()
end

local function refreshTools()
	for id, b in toolButtons do
		b.setColor(Build.tool == id and C.gold or C.royal)
	end
	rotateButton.root.Visible = Build.tool == "place" or Build.tool == "move"
	refreshCards()
end

local function refreshStats()
	local s = State.plot
	if not s then
		return
	end
	local tier = Catalog.Heartflame[s.tier or 1]
	stats.Text = string.format("🏮 Road lit %d%%   🌸 Appeal %d   🔥 %s   🪙 %s", s.roadLit or 0, s.appeal or 0, tier and tier.name or "", Theme.formatNumber(State.profile and State.profile.gold or 0))
end

function BuildBar.start(parent: Instance)
	gui = Instance.new("ScreenGui")
	gui.Name = "KingsbloomBuild"
	gui.ResetOnSpawn = false
	gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	gui.DisplayOrder = 2
	gui.Enabled = false
	gui.Parent = parent
	local scale = Instance.new("UIScale")
	scale.Parent = gui
	local function rescale()
		local v = workspace.CurrentCamera.ViewportSize
		scale.Scale = math.clamp(math.min(v.X / 1360, v.Y / 780) * 1.05, 0.55, 1.2)
	end
	rescale()
	workspace.CurrentCamera:GetPropertyChangedSignal("ViewportSize"):Connect(rescale)

	-- the drawer
	root = Theme.panel(gui, UDim2.new(1, -220, 0, 212), UDim2.new(0.5, 0, 1, -10), Vector2.new(0.5, 1))
	root.Name = "Drawer"
	tabsRow = Theme.frame(root, UDim2.new(1, -24, 0, 40), UDim2.fromOffset(12, 10), W, 1)
	Theme.list(tabsRow, false, 8)
	for i, cat in Catalog.Categories do
		local b = Theme.button(tabsRow, cat.icon .. " " .. cat.name, UDim2.fromOffset(176, 36), C.royal, function()
			showTab(cat.id)
		end, 17)
		b.root.LayoutOrder = i
		tabButtons[cat.id] = b
	end
	stats = Theme.label(root, "", 16, C.inkSoft, F.title)
	stats.Size = UDim2.new(0, 520, 0, 20)
	stats.AnchorPoint = Vector2.new(1, 0)
	stats.Position = UDim2.new(1, -14, 0, -26)
	stats.TextXAlignment = Enum.TextXAlignment.Right
	stats.TextColor3 = W
	Theme.textStroke(stats, C.shadow, 2)
	cardsFrame = Instance.new("ScrollingFrame")
	cardsFrame.Size = UDim2.new(1, -24, 0, 150)
	cardsFrame.Position = UDim2.fromOffset(12, 56)
	cardsFrame.BackgroundTransparency = 1
	cardsFrame.BorderSizePixel = 0
	cardsFrame.ScrollingDirection = Enum.ScrollingDirection.X
	cardsFrame.AutomaticCanvasSize = Enum.AutomaticSize.X
	cardsFrame.CanvasSize = UDim2.new()
	cardsFrame.ScrollBarThickness = 6
	cardsFrame.ScrollBarImageColor3 = C.goldDeep
	cardsFrame.Parent = root
	local l = Theme.list(cardsFrame, false, 10, Enum.HorizontalAlignment.Left, Enum.VerticalAlignment.Center)
	local _ = l
	Theme.pad(cardsFrame, 6, 8)

	-- the tool strip
	toolStrip = Theme.frame(gui, UDim2.fromOffset(76, 390), UDim2.new(0, 14, 0.5, -60), W, 1)
	toolStrip.AnchorPoint = Vector2.new(0, 0.5)
	Theme.list(toolStrip, true, 14, Enum.HorizontalAlignment.Center)
	local tools = {
		{ "select", "👆", "Select" },
		{ "paint", "🪨", "Path" },
		{ "erase", "🧽", "Erase" },
		{ "remove", "🧹", "Remove [X]" },
	}
	for i, t in tools do
		local b = Theme.round(toolStrip, t[2], 58, C.royal, function()
			Build.setTool(t[1])
		end, t[3])
		b.root.LayoutOrder = i
		toolButtons[t[1]] = b
	end
	rotateButton = Theme.round(toolStrip, "↻", 58, C.green, function()
		Build.rotate()
	end, "Turn [R]")
	rotateButton.root.LayoutOrder = 10

	-- Done and the hint line
	local done = Theme.button(gui, "✔ Done  [B]", UDim2.fromOffset(160, 46), C.green, function()
		Build.exit()
	end, 20)
	done.root.Position = UDim2.new(0, 14, 0.14, 0)
	hint = Theme.label(gui, "", 18, W, F.title)
	hint.AnchorPoint = Vector2.new(0.5, 0)
	hint.Position = UDim2.new(0.5, 0, 0, 72)
	hint.Size = UDim2.fromOffset(820, 24)
	hint.TextXAlignment = Enum.TextXAlignment.Center
	Theme.textStroke(hint, C.shadow, 2)

	showTab("light")
	refreshTools()
	Build.changed.connect(refreshTools)
	Build.info.connect(function(text: string)
		hint.Text = text
	end)
	State.profileChanged.connect(function()
		refreshCards()
		refreshStats()
	end)
	State.layoutChanged.connect(function()
		task.defer(refreshCards)
	end)
	State.plotChanged.connect(refreshStats)
	State.modeChanged.connect(function(mode)
		gui.Enabled = mode == "build"
		if mode == "build" then
			showTab(tab)
			refreshTools()
			refreshStats()
			root.Position = UDim2.new(0.5, 0, 1, 230)
			Theme.tween(root, 0.35, { Position = UDim2.new(0.5, 0, 1, -10) }, Enum.EasingStyle.Back)
		end
	end)
	local _ = UserInputService
end

return BuildBar
