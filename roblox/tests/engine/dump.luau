-- Builds a well-grown plot and a showcase of every model under the mock engine, then writes every
-- visible part to JSON so tools/preview can render it (a way to eyeball the models without Studio).
--
--   lune run tests/engine/dump.luau <place.rbxlx> <out.json> [hours]

local fs = require("@lune/fs")
local process = require("@lune/process")
local serde = require("@lune/serde")
local Engine = require("./Engine")
local R = Engine.R
local V3 = R.Vector3.new

local placePath = process.args[1] or "tests/engine/Kingsbloom.rbxlx"
local outPath = process.args[2] or "preview.json"
local untilSeconds = tonumber(process.args[3]) or 150

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
local p1 = Engine.addPlayer("Sovereign", 7)
Engine.setLocalPlayer(p1)
run(0.5)
Engine.spawnCharacter(p1, V3(2, 4, 12))
run(1)
local client = Engine.newEnv("client")
local clientScript = game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts"):FindFirstChild("Client")
Engine.start(client, clientScript)
run(2)

local sreq = server.globals.require
local ProgressService = sreq(serverScript:FindFirstChild("ProgressService"))
local State = client.globals.require(clientScript:FindFirstChild("State"))
local profile = ProgressService.profile(p1)
profile.level = 16
profile.gold = 99999
profile.lumen = 999
ProgressService.push(p1)
run(0.5)

local function req(action: string, args: any): any
	local res = nil
	Engine.task.spawn(function()
		res = State.request(action, args)
	end)
	run(0.1)
	if res and not res.ok then
		print("  (" .. action .. " " .. serde.encode("json", args) .. " → " .. tostring(res.reason) .. ")")
	end
	return res
end

-- grow the realm and lay out a lively market
req("heart", {})
req("heart", {})
-- paths: a loop east of the road and a lane west
local tiles = {}
for x = 16, 22 do
	table.insert(tiles, { x, 20 })
end
for z = 16, 20 do
	table.insert(tiles, { 22, z })
end
for x = 7, 13 do
	table.insert(tiles, { x, 18 })
end
req("paint", { tiles = tiles })
local builds = {
	{ "stall", 16, 21, 0, 1 }, { "stall", 18, 21, 0, 2 }, { "stall", 20, 21, 0, 3 },
	{ "stall", 13, 19, 1, 0 },
	{ "field_turnip", 9, 12, 0, 0 }, { "field_wheat", 5, 13, 0, 0 },
	{ "fishery", 12, 7, 0, 0 },
	{ "cookhouse", 17, 8, 0, 0 },
	{ "granary", 20, 9, 0, 0 },
	{ "tent", 18, 16, 0, 0 }, { "hut", 23, 17, 0, 1 }, { "cottage", 23, 12, 0, 2 },
	{ "lamp", 13, 20, 0, 0 }, { "lamp", 16, 23, 0, 0 }, { "lamp", 13, 24, 0, 0 }, { "lamp", 16, 27, 0, 0 },
	{ "string", 14, 17, 0, 0 },
	{ "arch", 22, 13, 0, 0 },
	{ "tower", 13, 27, 0, 0 },
	{ "flowers", 17, 19, 0, 0 }, { "flowers", 19, 19, 0, 1 }, { "flowers", 21, 19, 0, 2 },
	{ "bench", 12, 16, 0, 0 }, { "tree", 8, 17, 0, 0 }, { "tree", 11, 17, 0, 1 }, { "tree", 6, 17, 0, 2 },
	{ "banner", 12, 10, 0, 0 }, { "banner", 18, 10, 0, 1 }, { "well", 19, 14, 0, 0 },
	{ "fountain", 9, 20, 0, 0 }, { "statue", 20, 23, 0, 0 }, { "crates", 21, 16, 0, 0 }, { "hedge", 22, 21, 0, 0 },
}
for _, b in builds do
	req("place", { t = b[1], x = b[2], z = b[3], r = b[4], v = b[5] })
end
run(untilSeconds)

-- a showcase row of every building and actor, out past the south forest
local Shared = game:GetService("ReplicatedStorage"):FindFirstChild("Shared")
local Models = sreq(Shared:FindFirstChild("Models"))
local Catalog = sreq(Shared:FindFirstChild("Catalog"))
local show = Engine.Instance.new("Folder")
show.Name = "Showcase"
show.Parent = game:GetService("Workspace")
local x = -200
for _, id in Catalog.BuildOrder do
	local def = Catalog.Buildings[id]
	if not def.surface then
		for v = 0, (def.variants or 1) - 1 do
			local m = Models.build(id, v, { level = (v % 4) + 1, goods = Catalog.GoodsOrder[(v % 4) + 1], tier = 1 })
			m:PivotTo(R.CFrame.new(x + def.w * 3, 0, 420))
			m.Parent = show
			x += def.w * 6 + 6
		end
	end
end
for tier = 1, 4 do
	local m = Models.build("heartflame", 0, { tier = tier })
	m:PivotTo(R.CFrame.new(-200 + (tier - 1) * 20, 0, 460))
	m.Parent = show
end
local Actors = client.globals.require(clientScript:FindFirstChild("Actors"))
local Codec = sreq(Shared:FindFirstChild("Codec"))
local ax = -200
local posed = { parts = {}, cfs = {} }
local function actor(kind: number, info: number)
	local a = Actors.build(kind, info)
	a.model.Parent = show
	Actors.pose(a, R.CFrame.new(ax, 0.2, 490), 0.6, 1, posed.parts, posed.cfs)
	ax += 7
end
for i = 1, #Catalog.VisitorOrder do
	actor(i, i * 64 % 256)
end
for i = 1, 4 do
	actor(Codec.SETTLER_BASE + i, i * 8)
end
actor(Codec.GLOOM, 20)
actor(Codec.GLOOM, 64 + 20)
for i, p in posed.parts do
	p.CFrame = posed.cfs[i]
end
local coin = Actors.coin(true)
coin:PivotTo(R.CFrame.new(ax + 4, 2, 490))
coin.Parent = show

-- dump
local out = {}
local function colorOf(c)
	return { math.floor(c.R * 255 + 0.5), math.floor(c.G * 255 + 0.5), math.floor(c.B * 255 + 0.5) }
end
for _, d in game:GetService("Workspace"):GetDescendants() do
	if d:IsA("BasePart") and not d:IsA("Terrain") and d.Transparency < 0.98 and d.Name ~= "HumanoidRootPart" and d.Name ~= "Head" then
		local shape = "B"
		if d:IsA("WedgePart") then
			shape = "W"
		elseif d:IsA("CornerWedgePart") then
			shape = "C"
		elseif d:IsA("Part") then
			local s = d.Shape
			if s == R.Enum.PartType.Ball then
				shape = "S"
			elseif s == R.Enum.PartType.Cylinder then
				shape = "Y"
			elseif s == R.Enum.PartType.Wedge then
				shape = "W"
			end
		end
		local mesh = d:FindFirstChildOfClass("SpecialMesh")
		if mesh and mesh.MeshType == R.Enum.MeshType.Sphere then
			shape = "E"
		end
		local cf = d.CFrame
		local comps = { cf:GetComponents() }
		local rounded = {}
		for i, c in comps do
			rounded[i] = math.floor(c * 1000 + 0.5) / 1000
		end
		local material = tostring(d.Material):match("%.(%w+)$") or "Plastic"
		local light = d:FindFirstChildOfClass("PointLight")
		table.insert(out, {
			s = shape,
			z = { d.Size.X, d.Size.Y, d.Size.Z },
			f = rounded,
			c = colorOf(d.Color),
			m = material,
			t = d.Transparency,
			l = light and light.Enabled and { light.Range, light.Brightness, colorOf(light.Color) } or nil,
		})
	end
end
local ws = game:GetService("Workspace")
local plotIndex = p1:GetAttribute("Plot")
fs.writeFile(outPath, serde.encode("json", { parts = out, plot = plotIndex, time = Engine.sched.now }))
print(string.format("wrote %d parts (plot %s) to %s; errors %d", #out, tostring(plotIndex), outPath, #Engine.errors))
for _, e in Engine.errors do
	print("ERROR " .. e)
end
local _ = ws
