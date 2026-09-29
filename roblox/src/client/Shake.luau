--!strict
-- A little camera shake for impacts, bursts and big moments. Both cameras apply `offset`.

local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shake = {}

local amount = 0
local t = 0

function Shake.add(a: number)
	amount = math.min(1.4, amount + a)
end

function Shake.offset(dt: number): CFrame
	if amount <= 0.001 then
		amount = 0
		return CFrame.identity
	end
	t += dt
	local a = amount * amount
	amount = math.max(0, amount - dt * 2.4)
	local x = math.noise(t * 22, 0.3) * a * 0.9
	local y = math.noise(0.7, t * 22) * a * 0.9
	local r = math.noise(t * 18, 5.1) * a * 0.02
	return CFrame.new(x, y, 0) * CFrame.Angles(0, 0, r)
end

-- In play mode the default camera runs first; this nudges it afterwards.
function Shake.start(isBuilding: () -> boolean)
	RunService:BindToRenderStep("KingsbloomShake", Enum.RenderPriority.Camera.Value + 2, function(dt)
		if isBuilding() or amount <= 0 then
			return
		end
		local cam = Workspace.CurrentCamera
		cam.CFrame *= Shake.offset(dt)
	end)
end

return Shake
