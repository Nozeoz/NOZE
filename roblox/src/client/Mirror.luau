--!strict
-- A local copy of our plot's layout, rebuilt from the server's "layout" messages, so the build
-- ghost can say green or red (and why) instantly. The server still has the final word.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Grid = require(Shared.Grid)
local PlotSim = require(Shared.PlotSim)

local State = require(script.Parent.State)

local Mirror = {}

local profileStub = { gold = 0, lumen = 0, level = 1 }
Mirror.sim = nil :: any

local function syncProfile()
	local p = State.profile
	if p then
		profileStub.gold = p.gold
		profileStub.lumen = p.lumen
		profileStub.level = p.level
	end
end

function Mirror.apply(layout: any)
	syncProfile()
	local sim: any = PlotSim.new(profileStub, 1)
	sim.tier = math.clamp(layout.tier or 1, 1, #Catalog.Heartflame)
	sim.terrain = Grid.makeTerrain(sim:radius())
	for _, i in layout.paths or {} do
		sim.surface[i] = 1
	end
	for _, r in layout.objs or {} do
		local def = Catalog.Buildings[r[2]]
		if def then
			local o: any = {
				id = r[1],
				type = r[2],
				x = r[3],
				z = r[4],
				rot = r[5],
				variant = r[6],
				level = r[7] ~= 0 and r[7] or nil,
				goods = r[8] ~= "" and r[8] or nil,
				snuffed = r[9],
				ripe = r[10],
				worker = r[11] ~= "" and r[11] or nil,
			}
			o.w, o.d = sim:size(o.type, o.rot)
			if def.stall then
				o.queue = {}
			end
			sim:stamp(o, o.id)
			sim.objects[o.id] = o
		end
	end
	for _, s in layout.settlers or {} do
		table.insert(sim.settlers, { id = s[1], name = s[2], kind = s[3], path = {}, pi = 1 })
	end
	sim.nextId = layout.nextId or 1
	sim.cache = {}
	Mirror.sim = sim
end

function Mirror.object(id: number): any
	local sim = Mirror.sim
	return sim and sim.objects[id]
end

State.profileChanged.connect(syncProfile)
State.layoutChanged.connect(function(layout)
	Mirror.apply(layout)
end)

return Mirror
