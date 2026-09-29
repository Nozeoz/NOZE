local PlotSim = require("./.build/shared/PlotSim")
local DayCycle = require("./.build/shared/DayCycle")
local Progress = require("./.build/shared/Progress")
local p = Progress.newProfile()
p.level = 3
p.gold = 2000
local sim = PlotSim.new(p, 5)
sim:layStarter()
-- make everyone happy
local t = 0
local homeStates, settles, happy = 0, 0, 0
for _ = 1, 3000 do
	t += 0.1
	for _, v in sim.visitors do v.sat = 95 end
	sim:update(0.1, DayCycle.at(t), { })
	for _, e in sim:drain() do
		if e.k == "settle" then settles += 1 end
		if e.k == "happy" then happy += 1 end
	end
	for _, v in sim.visitors do
		if v.state == "home" and not v._seen then
			v._seen = true
			homeStates += 1
			print("heading home", v.name, v.tx, v.tz, #v.path, v.homeId, v.path[#v.path][1], v.path[#v.path][2])
		end
	end
end
print("happy", happy, "home", homeStates, "settles", settles, "settlers", #sim.settlers)
