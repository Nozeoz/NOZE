--!strict
-- The Build mode UI: category tabs, building cards (cost that rises as you build more, a lock
-- until the right level, how many you may own), the tool column, the hint line, Done, and on
-- touch screens a ✔ Build bar (tap to put the ghost somewhere, then confirm).
--
-- Layout: the drawer runs along the bottom; the tools stand in the margin to its left and Done
-- in the margin to its right, so nothing covers the chat, the clock or the player list. While a
-- building is being inspected the drawer slides away to make room for its card.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

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

local DRAWER_H = 212
local gui: ScreenGui
local root: Frame
local tabsRow: Frame
local cardsFrame: ScrollingFrame
local toolColumn: Frame
local confirmBar: Frame
local hint: TextLabel
local stats: TextLabel
local rotateButton: Theme.Button
local tab = "light"
local drawerOpen = true
local inspecting = false
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
	icon.TextYAlignment = Enum.TextYAlignment.Center
	local name = Theme.label(b, def.name, 15, C.royalDeep, F.title)
	name.Size = UDim2.new(1, -8, 0, 36)
	name.Position = UDim2.fromOffset(4, 60)
	name.TextXAlignment = Enum.TextXAlignment.Center
	name.TextYAlignment = Enum.TextYAlignment.Center
	local cost = Theme.label(b, "", 16, C.ink, F.title)
	cost.Size = UDim2.new(1, 0, 0, 20)
	cost.Position = UDim2.new(0, 0, 1, -26)
	cost.TextXAlignment = Enum.TextXAlignment.Center
	cost.TextWrapped = false
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
	lockText.TextYAlignment = Enum.TextYAlignment.Center
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

-- The drawer slides down out of the way while a building is inspected.
local function setDrawer(open: boolean)
	if open == drawerOpen then
		return
	end
	drawerOpen = open
	Theme.tween(root, 0.3, { Position = UDim2.new(0.5, 0, 1, open and -10 or DRAWER_H + 40) }, open and Enum.EasingStyle.Back or Enum.EasingStyle.Quad)
end

local function refreshTools()
	for id, b in toolButtons do
		b.setColor(Build.tool == id and C.gold or C.royal)
	end
	local placing = Build.tool == "place" or Build.tool == "move"
	rotateButton.item.Visible = placing
	confirmBar.Visible = placing and Build.isTouch() and not inspecting
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

	-- the drawer
	root = Theme.panel(gui, UDim2.new(1, -236, 0, DRAWER_H), UDim2.new(0.5, 0, 1, -10), Vector2.new(0.5, 1))
	root.Name = "Drawer"
	root.Active = true -- a click between the cards must not build behind the drawer
	tabsRow = Theme.frame(root, UDim2.new(1, -24, 0, 40), UDim2.fromOffset(12, 10), W, 1)
	Theme.list(tabsRow, false, 8)
	for i, cat in Catalog.Categories do
		local b = Theme.button(tabsRow, cat.icon .. " " .. cat.name, UDim2.fromOffset(176, 36), C.royal, function()
			showTab(cat.id)
		end, 17)
		b.root.LayoutOrder = i
		tabButtons[cat.id] = b
	end
	stats = Theme.label(root, "", 16, W, F.title)
	stats.Size = UDim2.new(1, -28, 0, 22)
	stats.AnchorPoint = Vector2.new(1, 1)
	stats.Position = UDim2.new(1, -14, 0, -6)
	stats.TextXAlignment = Enum.TextXAlignment.Right
	stats.TextWrapped = false
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
	Theme.list(cardsFrame, false, 10, Enum.HorizontalAlignment.Left, Enum.VerticalAlignment.Center)
	Theme.pad(cardsFrame, 6, 8)

	-- the tools, in the margin left of the drawer
	toolColumn = Theme.frame(gui, UDim2.fromOffset(84, 440), UDim2.new(0, 12, 1, -12), W, 1)
	toolColumn.Name = "Tools"
	toolColumn.Active = true
	toolColumn.AnchorPoint = Vector2.new(0, 1)
	Theme.list(toolColumn, true, 6, Enum.HorizontalAlignment.Center, Enum.VerticalAlignment.Bottom)
	local touch = Build.isTouch()
	local tools = {
		{ "select", "👆", "Select" },
		{ "paint", "🪨", "Path" },
		{ "erase", "🧽", "Erase" },
		{ "remove", "🧹", touch and "Remove" or "Remove [X]" },
	}
	for i, t in tools do
		local b = Theme.round(toolColumn, t[2], 54, C.royal, function()
			Build.setTool(t[1])
		end, t[3])
		b.item.LayoutOrder = i + 1
		toolButtons[t[1]] = b
	end
	rotateButton = Theme.round(toolColumn, "↻", 54, C.green, function()
		Build.rotate()
	end, touch and "Turn" or "Turn [R]")
	rotateButton.item.LayoutOrder = 1

	-- Done, in the margin right of the drawer
	local done = Theme.round(gui, "✔", 72, C.green, function()
		Build.exit()
	end, touch and "Done" or "Done [B]")
	done.item.AnchorPoint = Vector2.new(1, 1)
	done.item.Position = UDim2.new(1, -12, 1, -10)
	done.item.Name = "Done"

	-- touch: confirm where the ghost stands
	confirmBar = Theme.frame(gui, UDim2.fromOffset(330, 56), UDim2.new(0.5, 0, 1, -(DRAWER_H + 44)), W, 1)
	confirmBar.Name = "Confirm"
	confirmBar.Active = true
	confirmBar.AnchorPoint = Vector2.new(0.5, 1)
	confirmBar.Visible = false
	Theme.list(confirmBar, false, 12, Enum.HorizontalAlignment.Center, Enum.VerticalAlignment.Center)
	local cancel = Theme.button(confirmBar, "✖", UDim2.fromOffset(64, 52), C.red, function()
		Build.setTool("select")
	end, 24)
	cancel.root.LayoutOrder = 1
	local ok = Theme.button(confirmBar, "✔ Build here", UDim2.fromOffset(220, 52), C.green, function()
		Build.confirm()
	end, 22)
	ok.root.LayoutOrder = 2

	hint = Theme.label(gui, "", 18, W, F.title)
	hint.Name = "Hint"
	hint.AnchorPoint = Vector2.new(0.5, 0)
	hint.Position = UDim2.new(0.5, 0, 0, 72)
	hint.Size = UDim2.fromOffset(820, 24)
	hint.TextXAlignment = Enum.TextXAlignment.Center
	Theme.textStroke(hint, C.shadow, 2)

	Theme.autoScale(gui)
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
	State.inspect.connect(function(id)
		inspecting = id ~= nil and State.mode == "build"
		setDrawer(not inspecting)
		refreshTools()
	end)
	State.modeChanged.connect(function(mode)
		gui.Enabled = mode == "build"
		if mode == "build" then
			showTab(tab)
			refreshTools()
			refreshStats()
			inspecting = false
			drawerOpen = true
			root.Position = UDim2.new(0.5, 0, 1, DRAWER_H + 40)
			Theme.tween(root, 0.35, { Position = UDim2.new(0.5, 0, 1, -10) }, Enum.EasingStyle.Back)
		end
	end)
end

return BuildBar
