--!strict
-- The shared day: one global clock for the whole server (Roblox has one sky).
-- Day (the market trickles) → dusk (the Lantern Market opens) → night (the Veil) → dawn (the Night Ledger).

local Config = require(script.Parent.Config)

local DayCycle = {}

local D, DU, N, DA = Config.DAY_LENGTH, Config.DUSK_LENGTH, Config.NIGHT_LENGTH, Config.DAWN_LENGTH
DayCycle.LENGTH = D + DU + N + DA

export type Clock = { phase: string, progress: number, night: number, hours: number, day: number, t: number }

function DayCycle.at(t: number): Clock
	local cycle = t % DayCycle.LENGTH
	local day = t // DayCycle.LENGTH + 1
	if cycle < D then
		local p = cycle / D
		return { phase = "day", progress = p, night = 0, hours = 7 + 10 * p, day = day, t = t }
	elseif cycle < D + DU then
		local p = (cycle - D) / DU
		return { phase = "dusk", progress = p, night = p, hours = 17 + 2 * p, day = day, t = t }
	elseif cycle < D + DU + N then
		local p = (cycle - D - DU) / N
		return { phase = "night", progress = p, night = 1, hours = (19 + 10 * p) % 24, day = day, t = t }
	end
	local p = (cycle - D - DU - N) / DA
	return { phase = "dawn", progress = p, night = 1 - p, hours = 5 + 2 * p, day = day, t = t }
end

-- Seconds until the next phase starts.
function DayCycle.untilNext(t: number): number
	local cycle = t % DayCycle.LENGTH
	for _, edge in { D, D + DU, D + DU + N, DayCycle.LENGTH } do
		if cycle < edge then
			return edge - cycle
		end
	end
	return 0
end

function DayCycle.clockText(hours: number): string
	local h = math.floor(hours) % 24
	local m = math.floor((hours % 1) * 60 / 10) * 10
	return string.format("%02d:%02d", h, m)
end

return DayCycle
