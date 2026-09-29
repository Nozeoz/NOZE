-- Plays the real game under the mock engine: the server boots, a player joins, the client runs,
-- and a scripted Sovereign builds, serves, tends, fights through two days and nights, opens the
-- UI, leaves (saving), and comes back. Any script error, bad remote payload or unsaveable data fails.
--
--   cd roblox && rojo build default.project.json -o tests/engine/Kingsbloom.rbxlx && lune run tests/engine/play.luau

local process = require("@lune/process")
local Engine = require("./Engine")
local R = Engine.R
local V3 = R.Vector3.new

local placePath = process.args[1] or "tests/engine/Kingsbloom.rbxlx"
local game = Engine.load(placePath)

local failures = {}
local function check(cond: any, msg: string)
	if cond then
		print("  ✓ " .. msg)
	else
		print("  ✗ " .. msg)
		table.insert(failures, msg)
	end
end

local function run(seconds: number)
	local steps = math.floor(seconds / 0.1 + 0.5)
	for _ = 1, steps do
		Engine.step(0.1)
		Engine.announceChildren()
	end
end

print("\nBoot")
local server = Engine.newEnv("server")
local serverScript = game:GetService("ServerScriptService"):FindFirstChild("Server")
Engine.start(server, serverScript)
run(1)
local ws = game:GetService("Workspace")
local root = ws:FindFirstChild("Kingsbloom")
check(root and root:FindFirstChild("Plots") and #root.Plots:GetChildren() == 6, "the world has six plots")
check(root and root:FindFirstChild("Hub") and root.Hub:FindFirstChild("LedgerBoard"), "the hub and the Royal Ledger board exist")
check(game:GetService("ReplicatedStorage"):FindFirstChild("Remotes"), "remotes created")
check(game:GetService("StarterPack"):FindFirstChild("LanternStaff"), "the Lantern Staff is in the StarterPack")
local forest = root and root:FindFirstChild("Forest")
print(string.format("    forest trees: %d, terrain fills: %d", forest and #forest:GetChildren() or 0, Engine.terrain.fills))

print("\nJoin")
local p1 = Engine.addPlayer("Tester", 101)
Engine.setLocalPlayer(p1)
run(0.5)
Engine.spawnCharacter(p1, V3(2, 4, 12))
run(1.5)
local plotIndex = p1:GetAttribute("Plot")
check(type(plotIndex) == "number", "the player got a plot (" .. tostring(plotIndex) .. ")")
local leaderstats = p1:FindFirstChild("leaderstats")
check(leaderstats and leaderstats:FindFirstChild("Level"), "leaderstats exist")

print("\nClient")
local client = Engine.newEnv("client")
local clientScript = game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts"):FindFirstChild("Client")
Engine.start(client, clientScript)
run(3)
local creq = client.globals.require
local State = creq(clientScript:FindFirstChild("State"))
local Mirror = creq(clientScript:FindFirstChild("Mirror"))
local Build = creq(clientScript:FindFirstChild("Build"))
local Combat = creq(clientScript:FindFirstChild("Combat"))
local UI = clientScript:FindFirstChild("UI")
local Panels = creq(UI:FindFirstChild("Panels"))
check(State.profile ~= nil, "the client received the profile")
check(State.layout ~= nil and Mirror.sim ~= nil, "the client mirrored the plot layout")
check(State.plot ~= nil, "the client received the plot summary")
local gui = p1:FindFirstChild("PlayerGui")
check(gui and gui:FindFirstChild("KingsbloomHUD") and gui:FindFirstChild("KingsbloomBuild") and gui:FindFirstChild("KingsbloomPanels"), "the UI was built")

local messages = {}
State.message.connect(function(kind)
	messages[kind] = (messages[kind] or 0) + 1
end)
local fxCount = 0
State.fx.connect(function(_plot, events)
	fxCount += #events
end)

-- helpers
local Layout = creq(game:GetService("ReplicatedStorage").Shared:FindFirstChild("Layout"))
local plotCF = Layout.plotCFrame(plotIndex)
local function hrp()
	return p1.Character and p1.Character:FindFirstChild("HumanoidRootPart")
end
local function standAt(tx: number, tz: number)
	local r = hrp()
	if r then
		local pos = Layout.toWorld(plotCF, tx, tz, 3)
		r.CFrame = R.CFrame.new(pos)
		r.Position = pos
	end
end
local function request(action: string, args: any): any
	local result = nil
	Engine.task.spawn(function()
		result = State.request(action, args)
	end)
	run(0.1)
	return result or { ok = false, reason = "no reply" }
end

print("\nBuilding")
local r = request("place", { t = "flowers", x = 18, z = 11, r = 0, v = 1 })
check(r.ok, "placed a Flower Bed" .. (r.ok and "" or (": " .. tostring(r.reason))))
run(1)
local plotFolder = root.Plots:FindFirstChild("Plot" .. plotIndex)
local count = 0
for _, m in plotFolder.Buildings:GetChildren() do
	if m:GetAttribute("Type") == "flowers" then
		count += 1
	end
end
check(count >= 2, "the new building's model appeared (" .. count .. " flower beds)")
r = request("place", { t = "flowers", x = 14, z = 20, r = 0, v = 0 })
check(not r.ok and r.reason, "building on the road is refused: " .. tostring(r.reason))
r = request("paint", { tiles = { { 11, 15 }, { 11, 16 }, { 11, 17 } } })
check(r.ok and r.n == 3, "painted three path tiles")
run(0.5)
check(#plotFolder.Paths:GetChildren() >= 3, "path tiles appeared")
for _, z in { 20, 23, 26, 29 } do
	request("place", { t = "lamp", x = 13, z = z, r = 0, v = 0 })
end
run(1)
check(State.plot and State.plot.roadLit > 50, "lamps light the road (" .. tostring(State.plot and State.plot.roadLit) .. "%)")
r = request("claimQuest", {})
check(r.ok, "claimed the first quest" .. (r.ok and "" or (": " .. tostring(r.reason))))
run(1)
check((messages.questDone or 0) >= 1, "the quest reward ceremony fired")

print("\nBuild mode UI")
Engine.task.spawn(function()
	Build.enter()
end)
run(0.5)
check(State.mode == "build", "entered Build mode")
Build.select("lamp")
run(0.5)
Build.setTool("paint")
run(0.2)
Build.setTool("select")
local heart = nil
for id, o in Mirror.sim.objects do
	if o.type == "heartflame" then
		heart = id
	end
end
State.inspect.fire(heart)
run(0.3)
local stallId = nil
for id, o in Mirror.sim.objects do
	if o.type == "stall" then
		stallId = id
	end
end
State.inspect.fire(stallId)
run(0.3)
check(gui.KingsbloomPanels:FindFirstChild("Inspect", true) ~= nil, "the Inspect card opened")
Panels.open("journal")
run(0.3)
Panels.open("journal", "achievements")
run(0.3)
Panels.open("journal", "codex")
run(0.3)
Panels.open("settings")
run(0.3)
Panels.close()
Engine.task.spawn(function()
	Build.exit()
end)
run(0.5)
check(State.mode == "play", "left Build mode")

print("\nA day and a night")
local stall = Mirror.sim.objects[stallId]
local tile = stall and Mirror.sim:serviceTile(stall)
local swings, tends, bursts, deaths = 0, 0, 0, 0
local seconds = 0
local ripePrompts = 0
local function tendRipe()
	for _, m in plotFolder.Buildings:GetChildren() do
		local hb = m:FindFirstChild("Hitbox")
		local pr = hb and hb:FindFirstChild("TendPrompt")
		if pr and pr.Enabled then
			ripePrompts += 1
			Engine.signalOf(pr, "Triggered"):Fire(p1)
			tends += 1
		end
	end
end
local DayCycle = creq(game:GetService("ReplicatedStorage").Shared:FindFirstChild("DayCycle"))
local Entities = creq(clientScript:FindFirstChild("Entities"))
while seconds < DayCycle.LENGTH * 2 do
	local clock = DayCycle.at(Engine.sched.now + 25)
	if clock.phase == "night" or clock.phase == "dusk" then
		-- hunt Gloomlings: stand next to the nearest one and swing
		local r0 = hrp()
		local _, gid, gpos = Entities.nearestGloom(r0 and r0.CFrame.Position or V3(), 400)
		if gid and gpos and r0 then
			r0.CFrame = R.CFrame.new(gpos + V3(3, 3, 0))
			r0.Position = gpos + V3(3, 3, 0)
			Combat.swing()
			swings += 1
			if swings % 25 == 0 then
				Combat.burst()
				bursts += 1
			end
		elseif tile then
			standAt(tile[1] + 0.5, tile[2] + 0.5)
		end
	elseif tile then
		standAt(tile[1] + 0.5, tile[2] + 0.5)
		if seconds % 10 < 0.1 then
			tendRipe()
		end
	end
	local hum0 = p1.Character and p1.Character:FindFirstChildOfClass("Humanoid")
	if hum0 and hum0.Health <= 0 then
		deaths += 1
		run(3)
		Engine.spawnCharacter(p1, V3(2, 4, 12))
	end
	run(0.4)
	seconds += 0.4
	if seconds % 60 < 0.4 then
		request("claimQuest", {})
		for i = 1, 3 do
			request("claimOrder", { i = i })
		end
	end
end
local p = State.profile
print(string.format("    level %d  gold %d  lumen %d  xp %d  swings %d  bursts %d  tends %d  deaths %d  fx %d", p.level, p.gold, p.lumen, p.xp, swings, bursts, tends, deaths, fxCount))
local kinds = {}
for k, n in messages do
	table.insert(kinds, k .. "×" .. n)
end
table.sort(kinds)
print("    messages: " .. table.concat(kinds, ", "))
check(p.level >= 3, "reached level 3 or more (" .. p.level .. ")")
check((messages.levelup or 0) >= 1, "level-up ceremonies fired")
check((messages.ledger or 0) >= 1, "the Night Ledger arrived at dawn")
check((p.stats.sales or 0) > 5, "goods were sold (" .. tostring(p.stats.sales) .. ")")
check((p.stats.kills or 0) > 0, "Gloomlings were defeated (" .. tostring(p.stats.kills) .. ")")
check(ripePrompts > 0, "ripe fields could be tended (" .. ripePrompts .. ")")
check((p.stats.served or 0) > 0, "the Sovereign served customers (" .. tostring(p.stats.served) .. ")")
check((messages.discovery or 0) >= 1, "visitor discoveries were announced")

print("\nLeave and return")
local layoutBefore = #Mirror.sim.objects
local objsBefore = 0
for _ in Mirror.sim.objects do
	objsBefore += 1
end
local _ = layoutBefore
Engine.removePlayer(p1)
run(2)
local saved = Engine.store["KingsbloomLanternMarket_v1/p_101"]
check(saved ~= nil and #saved > 100, "the profile was saved (" .. (saved and #saved or 0) .. " bytes)")
check(root.Plots:FindFirstChild("Plot" .. plotIndex):GetAttribute("Owner") == nil, "the plot was released")
local p2 = Engine.addPlayer("Tester", 101)
Engine.setLocalPlayer(p2)
run(0.5)
Engine.spawnCharacter(p2, V3(2, 4, 12))
run(2)
local plotAgain = p2:GetAttribute("Plot")
local objsAfter = 0
local f2 = root.Plots:FindFirstChild("Plot" .. tostring(plotAgain))
if f2 then
	objsAfter = #f2.Buildings:GetChildren()
end
check(plotAgain ~= nil and objsAfter >= objsBefore, string.format("the plot came back (%d → %d buildings)", objsBefore, objsAfter))

print("\nShutdown")
if Engine.onClose then
	Engine.task.spawn(Engine.onClose)
	run(2)
end
check(Engine.storeWrites >= 2, "saved on leave and on shutdown (" .. Engine.storeWrites .. " writes)")

print("\nHealth")
print(string.format("    remote messages %d, largest snapshot %d bytes, tweens %d", Engine.network.sent, Engine.network.maxSnap, Engine.tweenCount))
for _, w in Engine.warnings do
	print("    warn: " .. w)
end
for _, prob in Engine.network.problems do
	print("    network: " .. prob)
end
for _, e in Engine.errors do
	print("    ERROR: " .. e)
end
check(#Engine.errors == 0, "no script errors (" .. #Engine.errors .. ")")
check(#Engine.network.problems == 0, "every remote payload and save is valid (" .. #Engine.network.problems .. " problems)")

print(string.format("\n%d failed", #failures))
process.exit(#failures > 0 and 1 or 0)
