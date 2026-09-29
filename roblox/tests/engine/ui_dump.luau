-- Runs the client under the mock engine, opens each screen (HUD, Build drawer, Inspect, Journal,
-- level-up, Night Ledger...), and writes the PlayerGui tree to JSON for tools/preview/ui.mjs.
--
--   lune run tests/engine/ui_dump.luau <place.rbxlx> <out.json> [width] [height] [touch]
--
-- The viewport size is set before the client starts, so every ScreenGui's UIScale is the one the
-- game picks for that screen. Pass "touch" as the fifth argument for a phone (touch, no keyboard).

local fs = require("@lune/fs")
local process = require("@lune/process")
local serde = require("@lune/serde")
local Engine = require("./Engine")
local R = Engine.R

local placePath = process.args[1] or "tests/engine/Kingsbloom.rbxlx"
local outPath = process.args[2] or "ui.json"
local width = tonumber(process.args[3]) or 1366
local height = tonumber(process.args[4]) or 768
local touch = process.args[5] == "touch"

local game = Engine.load(placePath)
local function run(s: number)
	for _ = 1, math.floor(s / 0.1 + 0.5) do
		Engine.step(0.1)
		Engine.announceChildren()
	end
end
local server = Engine.newEnv("server")
local serverScript = game:GetService("ServerScriptService"):FindFirstChild("Server")
Engine.start(server, serverScript)
run(1)
local p1 = Engine.addPlayer("Aurelia", 11)
Engine.setLocalPlayer(p1)
run(0.5)
Engine.spawnCharacter(p1, R.Vector3.new(2, 4, 12))
run(1)
local workspace_ = game:GetService("Workspace")
workspace_.CurrentCamera.ViewportSize = R.Vector2.new(width, height)
if touch then
	local uis = game:GetService("UserInputService")
	uis.TouchEnabled = true
	uis.KeyboardEnabled = false
	uis.MouseEnabled = false
end
local client = Engine.newEnv("client")
local clientScript = game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts"):FindFirstChild("Client")
Engine.start(client, clientScript)
run(3)
local creq = client.globals.require
local State = creq(clientScript:FindFirstChild("State"))
local Build = creq(clientScript:FindFirstChild("Build"))
local Mirror = creq(clientScript:FindFirstChild("Mirror"))
local Panels = creq(clientScript:FindFirstChild("UI"):FindFirstChild("Panels"))
local sreq = server.globals.require
local ProgressService = sreq(serverScript:FindFirstChild("ProgressService"))
local profile = ProgressService.profile(p1)
profile.level = 4
profile.gold = 1234
profile.lumen = 27
profile.xp = 380
profile.welcomed = true
ProgressService.push(p1)
run(2)

-- ─── serialise the GUI ─────────────────────────────────────────────────────
local function udim2(u)
	return { u.X.Scale, u.X.Offset, u.Y.Scale, u.Y.Offset }
end
local function col(c)
	return { math.floor(c.R * 255 + 0.5), math.floor(c.G * 255 + 0.5), math.floor(c.B * 255 + 0.5) }
end
local function enum(e)
	return tostring(e):match("%.(%w+)$")
end
local function safe(inst, prop)
	local ok, v = pcall(function()
		return inst[prop]
	end)
	if ok then
		return v
	end
	return nil
end

local function node(inst)
	local n = { class = inst.ClassName, name = inst.Name, children = {} }
	if inst:IsA("GuiObject") then
		n.pos = udim2(inst.Position)
		n.size = udim2(inst.Size)
		n.anchor = { inst.AnchorPoint.X, inst.AnchorPoint.Y }
		n.visible = inst.Visible
		n.bg = col(inst.BackgroundColor3)
		n.bgT = inst.BackgroundTransparency
		n.z = inst.ZIndex
		n.order = inst.LayoutOrder
		n.rot = inst.Rotation
		n.auto = enum(inst.AutomaticSize)
		if inst:IsA("TextLabel") or inst:IsA("TextButton") then
			n.text = inst.Text
			local f = safe(inst, "Font")
			n.font = f and enum(f) or "BuilderSansBold"
			n.textSize = inst.TextSize
			n.textColor = col(inst.TextColor3)
			n.textT = inst.TextTransparency
			n.scaled = inst.TextScaled
			n.wrapped = inst.TextWrapped
			n.xa = enum(inst.TextXAlignment)
			n.ya = enum(inst.TextYAlignment)
			n.rich = inst.RichText
		end
		if inst:IsA("ScrollingFrame") then
			n.scroll = true
			local a = safe(inst, "AutomaticCanvasSize")
			n.canvasAuto = a and enum(a) or "None"
		end
		n.clips = safe(inst, "ClipsDescendants") == true
	elseif inst:IsA("ScreenGui") then
		n.enabled = inst.Enabled
		n.order = inst.DisplayOrder
		n.ignoreInset = safe(inst, "IgnoreGuiInset") == true
		local ins = safe(inst, "ScreenInsets")
		n.insets = ins and enum(ins) or "CoreUISafeInsets"
	elseif inst:IsA("UICorner") then
		n.radius = { inst.CornerRadius.Scale, inst.CornerRadius.Offset }
	elseif inst:IsA("UIStroke") then
		n.color = col(inst.Color)
		n.thickness = inst.Thickness
		n.t = inst.Transparency
		n.mode = enum(inst.ApplyStrokeMode)
	elseif inst:IsA("UIGradient") then
		local kp = inst.Color.Keypoints
		n.from = col(kp[1].Value)
		n.to = col(kp[#kp].Value)
		local tk = inst.Transparency.Keypoints
		n.tFrom = tk[1].Value
		n.tTo = tk[#tk].Value
		n.rotation = inst.Rotation
	elseif inst:IsA("UIPadding") then
		n.pad = { inst.PaddingLeft.Offset, inst.PaddingRight.Offset, inst.PaddingTop.Offset, inst.PaddingBottom.Offset }
	elseif inst:IsA("UIListLayout") then
		n.dir = enum(inst.FillDirection)
		n.gap = inst.Padding.Offset
		n.ha = enum(inst.HorizontalAlignment)
		n.va = enum(inst.VerticalAlignment)
	elseif inst:IsA("UIGridLayout") then
		n.cell = udim2(inst.CellSize)
		n.cellPad = udim2(inst.CellPadding)
	elseif inst:IsA("UIScale") then
		n.scale = inst.Scale
	elseif inst:IsA("UISizeConstraint") then
		n.max = { inst.MaxSize.X, inst.MaxSize.Y }
	elseif inst:IsA("UITextSizeConstraint") then
		n.maxText = inst.MaxTextSize
	end
	for _, c in inst:GetChildren() do
		table.insert(n.children, node(c))
	end
	return n
end

local screens: { [string]: any } = { __modes = {} }
local function snap(name: string)
	local list = {}
	for _, g in p1.PlayerGui:GetChildren() do
		if g:IsA("ScreenGui") then
			table.insert(list, node(g))
		end
	end
	screens[name] = list
	-- Roblox hides the thumbstick and jump button while Build mode has the controls off
	screens.__modes[name] = State.mode
end

local function find(root: any, text: string): any
	for _, d in root:GetDescendants() do
		if d:IsA("TextLabel") and d.Text == text then
			local b = d:FindFirstAncestorWhichIsA("TextButton")
			if b then
				return b
			end
		end
	end
	return nil
end
local function click(text: string)
	local b = find(p1.PlayerGui, text)
	assert(b, "no button " .. text)
	Engine.signalOf(b, "Activated"):Fire()
	run(0.5)
end

run(1.5)
snap("welcome")
click("Let's begin!")
run(6)
snap("hud")

-- a busy moment: toasts, a banner, a slide-in card, and a quest ready to claim
State.toast.fire("Sold 🥬 Turnips for 12 🪙", "🛒", "good")
State.toast.fire("A lamp was snuffed by the Veil!", "🌫️", "warn")
State.message.fire("discovery", { icon = "🛡️", name = "Wandering Knight", rarity = "Rare", desc = "Pays well for stew. Guards your road at night." })
local HUD = creq(clientScript:FindFirstChild("UI"):FindFirstChild("HUD"))
HUD.banner("🏮 The Lantern Market opens", "Prices +25% tonight. Keep the road lit!", nil, 6)
local q = State.profile.quest
q.ready = true
q.progress = q.target
q.gold = 40
q.xp = 30
State.profileChanged.fire(State.profile)
run(1)
snap("busy")
run(8)

Engine.task.spawn(Build.enter)
run(1)
Build.select("lamp")
run(0.3)
snap("build")
local stall
for id, o in Mirror.sim.objects do
	if o.type == "stall" then
		stall = id
	end
end
State.inspect.fire(stall)
run(0.5)
snap("inspect")
local heart
for id, o in Mirror.sim.objects do
	if o.type == "heartflame" then
		heart = id
	end
end
State.inspect.fire(heart)
run(0.5)
snap("heartflame")
State.inspect.fire(nil)
Panels.open("confirmRemove", stall)
run(0.5)
snap("remove")
Panels.close()
Engine.task.spawn(Build.exit)
run(1)
Panels.open("journal", "quests")
run(0.5)
snap("journal")
Panels.open("journal", "orders")
run(0.5)
snap("orders")
Panels.open("journal", "achievements")
run(0.5)
snap("feats")
Panels.open("journal", "codex")
run(0.5)
snap("codex")
Panels.open("settings")
run(0.5)
snap("settings")
Panels.close()
run(0.3)
State.message.fire("levelup", {
	level = 6,
	rank = "Village",
	rankIcon = "🏡",
	rankUp = true,
	cards = {
		{ icon = "🏡", title = "Village", text = "Your realm is now a Village!", kind = "rank" },
		{ icon = "🗼", title = "Lumen Tower", text = "New building", kind = "building" },
		{ icon = "🛒", title = "+1 Market Stall", text = "You can own 4", kind = "limit" },
		{ icon = "🛡️", title = "Wandering Knight", text = "May visit your market now", kind = "visitor" },
	},
	need = 1934,
})
run(1.5)
snap("levelup")
run(12)
State.message.fire("ledger", {
	visitors = 23,
	happy = 11,
	content = 9,
	unhappy = 3,
	fled = 2,
	sold = { harvest = 14, catch = 6 },
	revenue = 118,
	tips = 34,
	kills = 7,
	snuffed = 1,
	soldOut = 2,
	noBed = 0,
	missing = { grain = 4 },
	settled = { "Wren" },
	surge = true,
	xp = 212,
	lumen = 9,
	gold = 152,
})
run(1)
snap("ledger")

fs.writeFile(outPath, serde.encode("json", screens))
print("wrote " .. outPath .. "; errors " .. #Engine.errors)
for _, e in Engine.errors do
	print("ERROR " .. e)
end
