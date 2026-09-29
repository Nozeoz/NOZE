local Engine = require("./Engine")
local R = Engine.R
local game = Engine.load("tests/engine/Kingsbloom.rbxlx")
local server = Engine.newEnv("server")
local serverScript = game:GetService("ServerScriptService"):FindFirstChild("Server")
Engine.start(server, serverScript)
local function run(s) for _ = 1, math.floor(s / 0.1 + 0.5) do Engine.step(0.1); Engine.announceChildren() end end
run(1)
local p1 = Engine.addPlayer("Tester", 101)
Engine.setLocalPlayer(p1)
run(0.5)
Engine.spawnCharacter(p1, R.Vector3.new(2, 4, 12))
run(1)
local client = Engine.newEnv("client")
local clientScript = game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts"):FindFirstChild("Client")
Engine.start(client, clientScript)
run(2)
local sreq = server.globals.require
local PlotService = sreq(serverScript:FindFirstChild("PlotService"))
local Layout = sreq(game:GetService("ReplicatedStorage").Shared:FindFirstChild("Layout"))
local Combat = client.globals.require(clientScript:FindFirstChild("Combat"))
local State = client.globals.require(clientScript:FindFirstChild("State"))
local hits, dies, swings = 0, 0, 0
local lowest = 100
State.fx.connect(function(_p, events)
	for _, e in events do
		if e.k == "hit" and e.by == 101 then hits += 1 end
		if e.k == "die" and e.by == 101 then dies += 1 end
	end
end)
-- skip to night
run(240)
local plot = PlotService.get(p1:GetAttribute("Plot"))
local sim = plot.sim
print("phase", sim.clock.phase, "gloom", #sim.gloom)
for i = 1, 400 do
	local g = sim.gloom[1]
	if g then
		local pos = Layout.toWorld(plot.cf, g.x, g.z, 3) + R.Vector3.new(2.5, 0, 0)
		local r = p1.Character.HumanoidRootPart
		r.CFrame = R.CFrame.lookAt(pos, Layout.toWorld(plot.cf, g.x, g.z, 3))
		r.Position = pos
		lowest = math.min(lowest, p1.Character.Humanoid.Health)
		p1.Character.Humanoid.Health = 100
		Combat.swing()
		swings += 1
	end
	run(0.4)
end
print("swings", swings, "hits", hits, "kills", dies, "gloom left", #sim.gloom, "phase", sim.clock.phase, "lowest health between swings", lowest)
for _, e in Engine.errors do print("ERR", e) end
-- second phase: trace one swing at a time
local fired = 0
local swingRemote = game:GetService("ReplicatedStorage").Remotes.Swing
Engine.signalOf(swingRemote, "OnServerEvent"):Connect(function() fired += 1 end)
run(200)
print("phase now", sim.clock.phase, "gloom", #sim.gloom)
local before = hits
for i = 1, 30 do
	local g = sim.gloom[1]
	if g then
		local pos = Layout.toWorld(plot.cf, g.x, g.z, 3) + R.Vector3.new(2.5, 0, 0)
		local r = p1.Character.HumanoidRootPart
		r.CFrame = R.CFrame.lookAt(pos, Layout.toWorld(plot.cf, g.x, g.z, 3))
		r.Position = pos
		local toolParent = p1.Character:FindFirstChild("LanternStaff") and "char" or "backpack"
		local f0, h0 = fired, hits
		Combat.swing()
		run(0.4)
		print(i, "tool", toolParent, "fired", fired - f0, "hits", hits - h0, "hp", g.hp)
	else
		run(0.4)
	end
end
