--!strict
-- Plot geometry in tile units. Pure Luau (no Roblox types) so the Lune tests can use it.
-- A plot is PLOT_W × PLOT_H tiles. Tile (x, z) covers [x, x+1) × [z, z+1); its centre is (x+0.5, z+0.5).
-- Local +z points toward the plot's entrance (the Royal Avenue side).

local Config = require(script.Parent.Config)

local Grid = {}

local W = Config.PLOT_W
local H = Config.PLOT_H
Grid.W = W
Grid.H = H

Grid.T = { OPEN = 1, ROAD = 2, WATER = 3, FOREST = 4 }
local T = Grid.T

Grid.N4 = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }
Grid.N8 = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 }, { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } }
-- Which way the front of a building faces for each rotation (0..3). Rotation r turns local +z toward +x.
Grid.FRONT = { [0] = { 0, 1 }, [1] = { 1, 0 }, [2] = { 0, -1 }, [3] = { -1, 0 } }

-- The Heartflame's centre (a tile corner) and its 2×2 footprint origin.
Grid.HEART_X = Config.HEARTFLAME.x
Grid.HEART_Z = Config.HEARTFLAME.z
Grid.HEART_TILE = { x = Config.HEARTFLAME.x - 1, z = Config.HEARTFLAME.z - 1 }
Grid.ENTRANCE = { x = Config.ENTRANCE.x, z = Config.ENTRANCE.z }
-- Visitors walk in from the avenue through these tiles (outside the grid) before the entrance.
Grid.APPROACH = { { Config.ENTRANCE.x, Config.ENTRANCE.z + 3 }, { Config.ENTRANCE.x, Config.ENTRANCE.z + 2 }, { Config.ENTRANCE.x, Config.ENTRANCE.z + 1 } }
Grid.PLAZA = { x = Config.HEARTFLAME.x, z = Config.HEARTFLAME.z + 2 }

-- The pond (4×4, aligned to even tiles so terrain water lines up).
Grid.POND = { x0 = 8, z0 = 6, x1 = 11, z1 = 9 }

function Grid.idx(x: number, z: number): number
	return z * W + x + 1
end

function Grid.fromIdx(i: number): (number, number)
	local k = i - 1
	return k % W, k // W
end

function Grid.inBounds(x: number, z: number): boolean
	return x >= 0 and z >= 0 and x < W and z < H
end

function Grid.realmRadius(tier: number, tiers: { { radius: number } }): number
	local t = tiers[math.clamp(tier, 1, #tiers)]
	return t.radius
end

function Grid.distToHeart(x: number, z: number): number
	local dx = x + 0.5 - Grid.HEART_X
	local dz = z + 0.5 - Grid.HEART_Z
	return math.sqrt(dx * dx + dz * dz)
end

function Grid.isHeartTile(x: number, z: number): boolean
	return x >= Grid.HEART_TILE.x and x <= Grid.HEART_TILE.x + 1 and z >= Grid.HEART_TILE.z and z <= Grid.HEART_TILE.z + 1
end

-- The starting plaza (a paved ring around the Heartflame) and the Old Road down to the entrance.
function Grid.isRoadTile(x: number, z: number): boolean
	local hx, hz = Grid.HEART_TILE.x, Grid.HEART_TILE.z
	local inPlaza = x >= hx - 2 and x <= hx + 3 and z >= hz - 2 and z <= hz + 3
	if inPlaza and not Grid.isHeartTile(x, z) then
		return true
	end
	local ex = Grid.ENTRANCE.x
	return (x == ex - 1 or x == ex) and z > hz + 3 and z <= Grid.ENTRANCE.z
end

function Grid.isPond(x: number, z: number): boolean
	local p = Grid.POND
	return x >= p.x0 and x <= p.x1 and z >= p.z0 and z <= p.z1
end

-- Terrain for a given realm radius: the road and pond are fixed; the forest covers everything
-- outside the realm except the verges right beside the road.
function Grid.makeTerrain(radius: number): { number }
	local terrain = table.create(W * H, T.OPEN)
	for z = 0, H - 1 do
		for x = 0, W - 1 do
			local i = Grid.idx(x, z)
			if Grid.isRoadTile(x, z) then
				terrain[i] = T.ROAD
			elseif Grid.isPond(x, z) then
				terrain[i] = T.WATER
			elseif Grid.distToHeart(x, z) > radius then
				local verge = false
				for _, d in Grid.N8 do
					if Grid.isRoadTile(x + d[1], z + d[2]) then
						verge = true
						break
					end
				end
				if not verge then
					terrain[i] = T.FOREST
				end
			end
		end
	end
	return terrain
end

-- Wild trees stand on some forest tiles (the same ones on every machine).
Grid.TREE_DENSITY = 0.42
function Grid.hasTree(terrain: { number }, i: number): boolean
	if terrain[i] ~= T.FOREST then
		return false
	end
	local x, z = Grid.fromIdx(i)
	return Grid.hash(x, z, 3) < Grid.TREE_DENSITY
end

-- Deterministic 0..1 hash for a tile (tree placement, jitter, colours).
function Grid.hash(x: number, z: number, salt: number?): number
	-- Park–Miller steps; every product stays below 2^53 so it is exact on every machine.
	local n = (x * 73856093 + z * 19349663 + (salt or 0) * 83492791 + 1) % 2147483647
	n = (n * 48271) % 2147483647
	n = (n * 48271) % 2147483647
	n = (n * 48271) % 2147483647
	return n / 2147483647
end

return Grid
