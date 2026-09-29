--!strict
-- The Kingdom View camera for Build mode: grab-and-drag panning with inertia, right-drag (or two
-- fingers) to rotate and tilt, scroll or pinch to zoom toward the cursor, WASD/arrows to glide,
-- Q/E to turn. Everything eases, so it always feels fluid.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local Layout = require(Shared.Layout)

local Sky = require(script.Parent.Sky)
local Shake = require(script.Parent.Shake)

local BuildCamera = {}

local cam = Workspace.CurrentCamera
local active = false
local plotCF = CFrame.identity
local focus, tFocus = Vector3.zero, Vector3.zero
local yaw, tYaw = 0, 0
local pitch, tPitch = 0.95, 0.95
local dist, tDist = 120, 120
local velocity = Vector3.zero
local MIN_PITCH, MAX_PITCH = 0.42, 1.38
local MIN_DIST, MAX_DIST = 28, 270

-- drag-to-pan state
local panning = false
local panGround: Vector3? = nil
local lastPanAt = 0
local rotating = false
local lastMouse = Vector2.zero

-- two-finger touch state
local touches: { [InputObject]: Vector2 } = {}
local gesture: { mid: Vector2, span: number, angle: number }? = nil

function BuildCamera.isActive(): boolean
	return active
end

-- Where a screen point meets the ground (y = 0). `viewport` means the point is in viewport space.
function BuildCamera.ground(screen: Vector2, viewport: boolean?): Vector3?
	local ray = viewport and cam:ViewportPointToRay(screen.X, screen.Y) or cam:ScreenPointToRay(screen.X, screen.Y)
	if math.abs(ray.Direction.Y) < 1e-4 then
		return nil
	end
	local t = -ray.Origin.Y / ray.Direction.Y
	if t < 0 then
		return nil
	end
	return ray.Origin + ray.Direction * t
end

function BuildCamera.mouseGround(): Vector3?
	return BuildCamera.ground(UserInputService:GetMouseLocation(), true)
end

local function clampFocus(p: Vector3): Vector3
	local l = plotCF:PointToObjectSpace(p)
	local size = Layout.PLOT_SIZE
	local x = math.clamp(l.X, -30, size + 30)
	local z = math.clamp(l.Z, -30, size + 60)
	return plotCF:PointToWorldSpace(Vector3.new(x, 0, z))
end

local function offset(y: number, p: number, d: number): Vector3
	return Vector3.new(math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p)) * d
end

function BuildCamera.beginPan(screen: Vector2, viewport: boolean?)
	panGround = BuildCamera.ground(screen, viewport)
	panning = panGround ~= nil
	velocity = Vector3.zero
end

function BuildCamera.panTo(screen: Vector2, viewport: boolean?)
	if not panning or not panGround then
		return
	end
	-- Keep the grabbed point under the finger: move the focus by how far the ground slid.
	local now = BuildCamera.ground(screen, viewport)
	if not now then
		return
	end
	local delta = (panGround :: Vector3) - now
	delta = Vector3.new(delta.X, 0, delta.Z)
	tFocus = clampFocus(tFocus + delta)
	focus = clampFocus(focus + delta)
	local t = os.clock()
	local dt = math.max(1 / 240, t - lastPanAt)
	velocity = velocity:Lerp(delta / dt, 0.5)
	lastPanAt = t
end

function BuildCamera.endPan()
	panning = false
	panGround = nil
	if os.clock() - lastPanAt > 0.08 then
		velocity = Vector3.zero
	end
end

function BuildCamera.isPanning(): boolean
	return panning
end

function BuildCamera.zoom(amount: number, towards: Vector3?)
	local before = tDist
	tDist = math.clamp(tDist * (1 - amount), MIN_DIST, MAX_DIST)
	if towards and tDist < before then
		local f = (before - tDist) / before
		tFocus = clampFocus(tFocus + (Vector3.new(towards.X, 0, towards.Z) - tFocus) * f)
	end
end

function BuildCamera.turn(radians: number)
	tYaw += radians
end

function BuildCamera.distance(): number
	return dist
end

function BuildCamera.focusOn(p: Vector3)
	tFocus = clampFocus(Vector3.new(p.X, 0, p.Z))
end

local function update(dt: number)
	-- keyboard glide
	local move = Vector3.zero
	if not UserInputService:GetFocusedTextBox() then
		local fwd = Vector3.new(-math.sin(tYaw), 0, -math.cos(tYaw))
		local right = Vector3.new(math.cos(tYaw), 0, -math.sin(tYaw))
		if UserInputService:IsKeyDown(Enum.KeyCode.W) or UserInputService:IsKeyDown(Enum.KeyCode.Up) then
			move += fwd
		end
		if UserInputService:IsKeyDown(Enum.KeyCode.S) or UserInputService:IsKeyDown(Enum.KeyCode.Down) then
			move -= fwd
		end
		if UserInputService:IsKeyDown(Enum.KeyCode.D) or UserInputService:IsKeyDown(Enum.KeyCode.Right) then
			move += right
		end
		if UserInputService:IsKeyDown(Enum.KeyCode.A) or UserInputService:IsKeyDown(Enum.KeyCode.Left) then
			move -= right
		end
	end
	if move.Magnitude > 0 then
		tFocus = clampFocus(tFocus + move.Unit * dt * (40 + tDist * 0.9))
	end
	-- inertia after a flick
	if not panning and velocity.Magnitude > 0.5 then
		tFocus = clampFocus(tFocus + velocity * dt)
		focus = clampFocus(focus + velocity * dt)
		velocity *= math.exp(-dt * 4.5)
	end
	local k = 1 - math.exp(-dt * 9)
	focus = focus:Lerp(tFocus, k)
	yaw += (tYaw - yaw) * k
	pitch += (tPitch - pitch) * k
	dist += (tDist - dist) * k
	cam.CFrame = CFrame.lookAt(focus + offset(yaw, pitch, dist), focus) * Shake.offset(dt)
	cam.Focus = CFrame.new(focus)
	Sky.setBuildFocus(true, dist)
end

function BuildCamera.enter(plotIndex: number, around: Vector3?)
	if active then
		return
	end
	active = true
	plotCF = Layout.plotCFrame(plotIndex)
	local toAvenue = plotCF:VectorToWorldSpace(Vector3.new(0, 0, 1))
	local baseYaw = math.atan2(toAvenue.X, toAvenue.Z)
	local centre = Layout.toWorld(plotCF, Config.HEARTFLAME.x, Config.HEARTFLAME.z + 3, 0)
	local start = around and clampFocus(Vector3.new(around.X, 0, around.Z)) or centre
	-- Start from where the camera is now, so the move into the Kingdom View glides.
	local now = cam.CFrame
	local look = now.LookVector
	focus = now.Position + look * 30
	focus = Vector3.new(focus.X, 0, focus.Z)
	yaw = baseYaw
	pitch = 0.7
	dist = math.max(40, (now.Position - focus).Magnitude)
	tFocus = start:Lerp(centre, 0.4)
	tYaw = baseYaw
	tPitch = 0.98
	tDist = 125
	velocity = Vector3.zero
	cam.CameraType = Enum.CameraType.Scriptable
	RunService:BindToRenderStep("KingsbloomBuildCamera", Enum.RenderPriority.Camera.Value + 1, update)
end

function BuildCamera.exit()
	if not active then
		return
	end
	active = false
	RunService:UnbindFromRenderStep("KingsbloomBuildCamera")
	Sky.setBuildFocus(false)
	cam.CameraType = Enum.CameraType.Custom
	local char = game:GetService("Players").LocalPlayer.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if hum then
		cam.CameraSubject = hum
	end
end

-- ─── input ─────────────────────────────────────────────────────────────────
function BuildCamera.start()
	UserInputService.InputBegan:Connect(function(input, processed)
		if not active or processed then
			return
		end
		if input.UserInputType == Enum.UserInputType.MouseButton2 then
			rotating = true
			lastMouse = UserInputService:GetMouseLocation()
		elseif input.UserInputType == Enum.UserInputType.MouseButton3 then
			BuildCamera.beginPan(UserInputService:GetMouseLocation(), true)
		elseif input.KeyCode == Enum.KeyCode.Q then
			BuildCamera.turn(-math.pi / 4)
		elseif input.KeyCode == Enum.KeyCode.E then
			BuildCamera.turn(math.pi / 4)
		elseif input.UserInputType == Enum.UserInputType.Touch then
			touches[input] = Vector2.new(input.Position.X, input.Position.Y)
		end
	end)
	UserInputService.InputEnded:Connect(function(input)
		if input.UserInputType == Enum.UserInputType.MouseButton2 then
			rotating = false
		elseif input.UserInputType == Enum.UserInputType.MouseButton3 then
			BuildCamera.endPan()
		elseif input.UserInputType == Enum.UserInputType.Touch then
			touches[input] = nil
			gesture = nil
		end
	end)
	UserInputService.InputChanged:Connect(function(input: InputObject, processed: boolean)
		if not active then
			return
		end
		if input.UserInputType == Enum.UserInputType.MouseMovement then
			local m = UserInputService:GetMouseLocation()
			if rotating then
				local d = m - lastMouse
				tYaw -= d.X * 0.008
				tPitch = math.clamp(tPitch + d.Y * 0.005, MIN_PITCH, MAX_PITCH)
			end
			lastMouse = m
			if panning then
				BuildCamera.panTo(m, true)
			end
		elseif input.UserInputType == Enum.UserInputType.MouseWheel and not processed then
			BuildCamera.zoom(input.Position.Z * 0.14, BuildCamera.mouseGround())
		elseif input.UserInputType == Enum.UserInputType.Touch and touches[input] then
			touches[input] = Vector2.new(input.Position.X, input.Position.Y)
			local list = {}
			for _, p in touches do
				table.insert(list, p)
			end
			if #list == 2 then
				local a, b = list[1], list[2]
				local mid = (a + b) / 2
				local span = (a - b).Magnitude
				local angle = math.atan2(b.Y - a.Y, b.X - a.X)
				local g = gesture
				if g then
					local groundBefore = BuildCamera.ground(g.mid)
					local groundNow = BuildCamera.ground(mid)
					if groundBefore and groundNow then
						local d = groundBefore - groundNow
						tFocus = clampFocus(tFocus + Vector3.new(d.X, 0, d.Z))
					end
					if g.span > 10 then
						BuildCamera.zoom((span / g.span - 1) * 1.2)
					end
					local da = angle - g.angle
					if math.abs(da) < 1 then
						tYaw -= da
					end
					tPitch = math.clamp(tPitch + (mid.Y - g.mid.Y) * 0.002, MIN_PITCH, MAX_PITCH)
				end
				gesture = { mid = mid, span = span, angle = angle }
			end
		end
	end)
end

-- How many fingers are down (Build uses this to leave two-finger gestures to the camera).
function BuildCamera.touchCount(): number
	local n = 0
	for _ in touches do
		n += 1
	end
	return n
end

return BuildCamera
