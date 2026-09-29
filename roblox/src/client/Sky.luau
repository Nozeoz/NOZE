--!strict
-- Animates the sky every frame from the shared clock: warm storybook days, a golden dusk,
-- and violet Veil nights where the lanterns glow. Also runs the tilt-shift blur in Build mode.

local Lighting = game:GetService("Lighting")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local DayCycle = require(Shared.DayCycle)

local Sky = {}

local rgb = Color3.fromRGB
local DAY = {
	ambient = rgb(78, 70, 86),
	outdoor = rgb(156, 146, 150),
	brightness = 2.4,
	atmoColor = rgb(214, 206, 196),
	atmoDecay = rgb(120, 110, 140),
	density = 0.3,
	haze = 1.4,
	tint = rgb(255, 248, 236),
	saturation = 0.14,
	contrast = 0.08,
	bloom = 0.7,
}
local NIGHT = {
	ambient = rgb(40, 34, 70),
	outdoor = rgb(70, 62, 124),
	brightness = 0.9,
	atmoColor = rgb(82, 66, 138),
	atmoDecay = rgb(40, 30, 80),
	density = 0.42,
	haze = 2.4,
	tint = rgb(208, 198, 255),
	saturation = 0.04,
	contrast = 0.16,
	bloom = 1.15,
}
local GOLD = rgb(255, 196, 150)

local function lerp(a: number, b: number, t: number): number
	return a + (b - a) * t
end

Sky.clock = DayCycle.at(0)

function Sky.now(): DayCycle.Clock
	local start = Workspace:GetAttribute("CycleStart")
	local s = typeof(start) == "number" and start or 0
	return DayCycle.at(Workspace:GetServerTimeNow() - s)
end

local dof: DepthOfFieldEffect? = nil
local building = false
local focusDistance = 80

function Sky.setBuildFocus(on: boolean, distance: number?)
	building = on
	focusDistance = distance or focusDistance
end

function Sky.start()
	local atmosphere = Lighting:FindFirstChildOfClass("Atmosphere")
	local grade = Lighting:FindFirstChild("Grade")
	local bloom = Lighting:FindFirstChildOfClass("BloomEffect")
	local camera = Workspace.CurrentCamera
	local d = Instance.new("DepthOfFieldEffect")
	d.Name = "TiltShift"
	d.Enabled = false
	d.FarIntensity = 0
	d.NearIntensity = 0
	d.Parent = camera
	dof = d
	RunService.RenderStepped:Connect(function()
		local c = Sky.now()
		Sky.clock = c
		local n = c.night
		-- golden light around dusk and dawn
		local golden = 0
		if c.phase == "dusk" then
			golden = math.sin(c.progress * math.pi)
		elseif c.phase == "dawn" then
			golden = math.sin(c.progress * math.pi) * 0.8
		elseif c.phase == "day" and c.progress > 0.85 then
			golden = (c.progress - 0.85) / 0.15 * 0.6
		end
		Lighting.ClockTime = c.hours
		Lighting.Ambient = DAY.ambient:Lerp(NIGHT.ambient, n)
		Lighting.OutdoorAmbient = DAY.outdoor:Lerp(NIGHT.outdoor, n):Lerp(GOLD, golden * 0.25)
		Lighting.Brightness = lerp(DAY.brightness, NIGHT.brightness, n)
		if atmosphere and atmosphere:IsA("Atmosphere") then
			atmosphere.Color = DAY.atmoColor:Lerp(NIGHT.atmoColor, n):Lerp(GOLD, golden * 0.4)
			atmosphere.Decay = DAY.atmoDecay:Lerp(NIGHT.atmoDecay, n)
			atmosphere.Density = lerp(DAY.density, NIGHT.density, n)
			atmosphere.Haze = lerp(DAY.haze, NIGHT.haze, n)
		end
		if grade and grade:IsA("ColorCorrectionEffect") then
			grade.TintColor = DAY.tint:Lerp(NIGHT.tint, n):Lerp(GOLD, golden * 0.3)
			grade.Saturation = lerp(DAY.saturation, NIGHT.saturation, n)
			grade.Contrast = lerp(DAY.contrast, NIGHT.contrast, n)
		end
		if bloom then
			bloom.Intensity = lerp(DAY.bloom, NIGHT.bloom, n)
		end
		local e = dof
		if e then
			e.Enabled = building
			if building then
				e.FocusDistance = focusDistance
				e.InFocusRadius = focusDistance * 0.55
				e.FarIntensity = 0.32
				e.NearIntensity = 0.55
			end
		end
	end)
end

return Sky
