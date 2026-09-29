--!strict
-- Where things are in the world: six plots in two rows either side of the Royal Avenue.
-- Row A (plots 1-3) faces south; row B (plots 4-6) is turned 180° so every plot's entrance
-- (local +z edge) opens onto the avenue. Plot edges sit on multiples of 4 studs so terrain water lines up.

local Config = require(script.Parent.Config)

local Layout = {}

local TILE = Config.TILE
Layout.TILE = TILE
Layout.PLOT_SIZE = Config.PLOT_W * TILE -- 180 studs
Layout.AVENUE_HALF = 36 -- the avenue runs between z = -36 and z = 36
Layout.WORLD_X = { -292, 296 }
Layout.WORLD_Z = { -216, 216 }
Layout.MARGIN = 120 -- forest beyond the plots
Layout.HUB = Vector3.new(2, 0, 0)
Layout.SPAWN = Vector3.new(2, 4, 12)

function Layout.plotCFrame(i: number): CFrame
	local row = (i - 1) // 3
	local col = (i - 1) % 3
	if row == 0 then
		return CFrame.new(-292 + col * 204, 0, -216)
	end
	return CFrame.new(-112 + col * 204, 0, 216) * CFrame.Angles(0, math.pi, 0)
end

-- A point on a plot, given in tile units (x = 3.5 is the middle of tile 3).
function Layout.toWorld(cf: CFrame, x: number, z: number, y: number?): Vector3
	return cf:PointToWorldSpace(Vector3.new(x * TILE, y or 0, z * TILE))
end

function Layout.toTile(cf: CFrame, pos: Vector3): (number, number)
	local p = cf:PointToObjectSpace(pos)
	return p.X / TILE, p.Z / TILE
end

-- The CFrame of a building's footprint centre on the ground, rotated to face its front.
function Layout.objectCFrame(cf: CFrame, x: number, z: number, w: number, d: number, rot: number): CFrame
	return cf * CFrame.new((x + w / 2) * TILE, 0, (z + d / 2) * TILE) * CFrame.Angles(0, rot * math.pi / 2, 0)
end

-- Which plot (if any) a world position is on, and its tile coordinates there.
function Layout.plotAt(pos: Vector3): (number?, number, number)
	for i = 1, Config.PLOT_COUNT do
		local x, z = Layout.toTile(Layout.plotCFrame(i), pos)
		if x >= 0 and z >= 0 and x < Config.PLOT_W and z < Config.PLOT_H + 3 then
			return i, x, z
		end
	end
	return nil, 0, 0
end

-- The middle of a plot's entrance, just out on the avenue, facing in.
function Layout.gateCFrame(i: number): CFrame
	local cf = Layout.plotCFrame(i)
	local pos = Layout.toWorld(cf, Config.ENTRANCE.x, Config.PLOT_H + 2.2, 3)
	local look = Layout.toWorld(cf, Config.ENTRANCE.x, Config.PLOT_H - 4, 3)
	return CFrame.lookAt(pos, look)
end

return Layout
