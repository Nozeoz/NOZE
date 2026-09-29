--!strict
-- Packs a plot's moving things (visitors, settlers, Gloomlings) into a small buffer, 8 bytes each,
-- so ten snapshots a second fit easily under the UnreliableRemoteEvent payload limit.
-- Layout: u8 plot, u8 count, then per entity: u16 id, u8 kind, u16 x·256, u16 z·256, u8 info.

local Catalog = require(script.Parent.Catalog)

local Codec = {}

Codec.SETTLER_BASE = 20
Codec.GLOOM = 40
Codec.MAX = 100

-- visitor state codes (low 3 bits of info)
Codec.WALK = 0
Codec.IDLE = 1
Codec.LINGER = 2
Codec.FLEE = 3

local kindIndex: { [string]: number } = {}
for i, k in Catalog.VisitorOrder do
	kindIndex[k] = i
end
Codec.kindIndex = kindIndex

local function fixed(v: number): number
	return math.clamp(math.floor(v * 256 + 0.5), 0, 65535)
end

local function visitorInfo(v: any): number
	local st = v.state
	local code = Codec.WALK
	if st == "queue" or st == "buy" then
		code = Codec.IDLE
	elseif st == "linger" then
		code = Codec.LINGER
	elseif st == "flee" then
		code = Codec.FLEE
	end
	local info = code
	if v.mood == 1 then
		info += 8
	elseif v.mood == -1 then
		info += 16
	end
	if v.fear >= 18 then
		info += 32
	end
	info += (v.seed % 4) * 64
	return info
end

function Codec.encode(plot: number, sim: any): buffer
	local items = {}
	for _, v in sim.visitors do
		if v.state ~= "gone" then
			table.insert(items, { v.id, kindIndex[v.kind] or 1, v.x, v.z, visitorInfo(v) })
		end
	end
	local shown = 0
	for _, s in sim.settlers do
		if not s.inside and shown < 24 then
			shown += 1
			local moving = s.pi <= #s.path
			table.insert(items, { s.id, Codec.SETTLER_BASE + (kindIndex[s.kind] or 1), s.x, s.z, (moving and 0 or 1) + (s.seed % 32) * 8 })
		end
	end
	for _, g in sim.gloom do
		local hp = math.clamp(math.floor(g.hp / g.maxHp * 31 + 0.5), 0, 31)
		local info = hp + (g.snuff > 0 and 32 or 0) + (g.surge and 64 or 0) + (g.chasing and 128 or 0)
		table.insert(items, { g.id, Codec.GLOOM, g.x, g.z, info })
	end
	local n = math.min(#items, Codec.MAX)
	local b = buffer.create(2 + n * 8)
	buffer.writeu8(b, 0, plot)
	buffer.writeu8(b, 1, n)
	for i = 1, n do
		local it = items[i]
		local o = 2 + (i - 1) * 8
		buffer.writeu16(b, o, it[1])
		buffer.writeu8(b, o + 2, it[2])
		buffer.writeu16(b, o + 3, fixed(it[3]))
		buffer.writeu16(b, o + 5, fixed(it[4]))
		buffer.writeu8(b, o + 7, it[5])
	end
	return b
end

export type Entity = { id: number, kind: number, x: number, z: number, info: number }

function Codec.decode(b: buffer): (number, { Entity })
	local plot = buffer.readu8(b, 0)
	local n = buffer.readu8(b, 1)
	local out = table.create(n)
	for i = 1, n do
		local o = 2 + (i - 1) * 8
		out[i] = {
			id = buffer.readu16(b, o),
			kind = buffer.readu8(b, o + 2),
			x = buffer.readu16(b, o + 3) / 256,
			z = buffer.readu16(b, o + 5) / 256,
			info = buffer.readu8(b, o + 7),
		}
	end
	return plot, out
end

return Codec
