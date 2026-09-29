--!strict
-- Build mode: the tools (select, place, paint path, erase path, remove, move), the ghost preview
-- that turns green, yellow or red and says why, the light-radius preview for lamps, the realm's
-- edge, and every click, drag and tap. The server checks everything again.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Config = require(Shared.Config)
local Grid = require(Shared.Grid)
local Layout = require(Shared.Layout)
local Models = require(Shared.Models)
local Palette = require(Shared.Palette)

local State = require(script.Parent.State)
local Mirror = require(script.Parent.Mirror)
local BuildCamera = require(script.Parent.BuildCamera)
local Audio = require(script.Parent.Audio)
local WorldFx = require(script.Parent.WorldFx)

local Build = {}

local B = Catalog.Buildings
local TILE = Config.TILE
local GREEN = Color3.fromRGB(110, 235, 130)
local YELLOW = Color3.fromRGB(255, 214, 90)
local RED = Color3.fromRGB(255, 90, 80)

Build.tool = "select"
Build.item = nil :: string?
Build.rot = 0
Build.variant = 0
Build.moveId = nil :: number?
Build.changed = State.signal()
Build.info = State.signal() -- (text, colour) for the hint line

local plotIndex = 0
local plotCF = CFrame.identity
local preview = Instance.new("Folder")
preview.Name = "KingsbloomBuildPreview"
preview.Parent = Workspace

local ghost: Model? = nil
local ghostKey = ""
local ghostCF = CFrame.identity
local plate: Part? = nil
local disc: Part? = nil
local label: TextLabel? = nil
local labelGui: BillboardGui? = nil
local ghostOk = false
local ghostReason: string? = nil
local ghostAt = { x = 0, z = 0 }

local hoverHighlight = Instance.new("Highlight")
hoverHighlight.FillTransparency = 1
hoverHighlight.OutlineTransparency = 0
hoverHighlight.OutlineColor = Color3.new(1, 1, 1)
hoverHighlight.DepthMode = Enum.HighlightDepthMode.Occluded
hoverHighlight.Enabled = false
hoverHighlight.Parent = preview
local hoverId: number? = nil

local ringFolder = Instance.new("Folder")
ringFolder.Name = "Ring"
ringFolder.Parent = preview
local ringTier = 0

local pending = false
local inspectNewStall = false

-- pointer state
local pointerDown = false
local downAt = Vector2.zero
local downViewport = false
local dragging = false
local painting = false
local paintList: { { number } } = {}
local paintSet: { [number]: Part } = {}
local lastPaint: { number }? = nil

local function controls(): any
	local ps = Players.LocalPlayer:FindFirstChild("PlayerScripts")
	local pm = ps and ps:FindFirstChild("PlayerModule")
	if pm and pm:IsA("ModuleScript") then
		local ok, mod = pcall(require, pm)
		if ok and mod then
			return (mod :: any):GetControls()
		end
	end
	return nil
end

local function sim(): any
	return Mirror.sim
end

-- ─── the realm's edge ──────────────────────────────────────────────────────
local function drawRing()
	local s = sim()
	if not s then
		return
	end
	if ringTier == s.tier and #ringFolder:GetChildren() > 0 then
		return
	end
	ringTier = s.tier
	ringFolder:ClearAllChildren()
	local r = s:radius()
	local n = math.floor(r * 9)
	for i = 0, n - 1 do
		local a = i / n * math.pi * 2
		local pos = Layout.toWorld(plotCF, Grid.HEART_X + math.cos(a) * r, Grid.HEART_Z + math.sin(a) * r, 0.5)
		local dot = Models.ball(ringFolder, 0.9, CFrame.new(pos), Palette.gold, Enum.Material.Neon, false)
		dot.CanQuery = false
		dot.CastShadow = false
		dot.Transparency = 0.25
	end
end

-- ─── the ghost ─────────────────────────────────────────────────────────────
local function clearGhost()
	if ghost then
		ghost:Destroy()
	end
	ghost = nil
	ghostKey = ""
	plate = nil
	disc = nil
	label = nil
	labelGui = nil
end

local function makeGhost(typeId: string, variant: number, extra: Models.Extra?)
	local key = typeId .. "|" .. variant .. "|" .. Build.rot
	if ghost and ghostKey == key then
		return
	end
	local keepCF = ghost ~= nil
	clearGhost()
	local m = Models.build(typeId, variant, extra)
	for _, d in m:GetDescendants() do
		if d:IsA("BasePart") then
			d.CanCollide = false
			d.CanQuery = false
			d.CanTouch = false
			d.CastShadow = false
			if d.Transparency < 1 then
				d.Transparency = math.max(d.Transparency, 0.2)
			end
		elseif d:IsA("ParticleEmitter") then
			d.Enabled = false
		elseif d:IsA("Fire") then
			d.Enabled = false
		elseif d:IsA("ProximityPrompt") then
			d:Destroy()
		end
	end
	local def = B[typeId]
	local hl = Instance.new("Highlight")
	hl.Name = "Tint"
	hl.FillTransparency = 0.55
	hl.OutlineTransparency = 0.15
	hl.DepthMode = Enum.HighlightDepthMode.AlwaysOnTop
	hl.Parent = m
	local p = Models.box(m, Vector3.new(def.w * TILE - 0.4, 0.3, def.d * TILE - 0.4), CFrame.new(0, 0.3, 0), GREEN, Enum.Material.Neon, false)
	p.Name = "Plate"
	p.Transparency = 0.45
	p.CanQuery = false
	plate = p
	local radius = def.light or (def.lights and def.lights[1][3]) or nil
	if radius and (def.snuffable or def.tower) then
		local c = Models.cyl(m, 0.2, radius * TILE * 2, CFrame.new(0, 0.35, 0), Palette.lantern, Enum.Material.Neon, false)
		c.Name = "Reach"
		c.Transparency = 0.82
		c.CanQuery = false
		disc = c
	end
	local g = Instance.new("BillboardGui")
	g.Size = UDim2.fromOffset(260, 44)
	g.StudsOffset = Vector3.new(0, 11, 0)
	g.AlwaysOnTop = true
	g.LightInfluence = 0
	g.Adornee = p
	g.Parent = m
	local l = Instance.new("TextLabel")
	l.Size = UDim2.fromScale(1, 1)
	l.BackgroundTransparency = 1
	l.Font = Enum.Font.FredokaOne
	l.TextSize = 20
	l.TextColor3 = Color3.new(1, 1, 1)
	l.TextWrapped = true
	l.Parent = g
	local s = Instance.new("UIStroke")
	s.Thickness = 2
	s.Color = Color3.fromRGB(30, 20, 14)
	s.Parent = l
	label = l
	labelGui = g
	m.Parent = preview
	ghost = m
	ghostKey = key
	if not keepCF then
		ghostCF = CFrame.identity
	end
end

local function stallHasPath(s: any, typeId: string, x: number, z: number, rot: number): boolean
	local probe = { id = -1, type = typeId, x = x, z = z, rot = rot, w = 0, d = 0 }
	probe.w, probe.d = s:size(typeId, rot)
	for _, t in s:frontTiles(probe) do
		if s:visitorWalkable(t[1], t[2]) and s:reachable(t[1], t[2]) then
			return true
		end
	end
	return false
end

local function updateGhost(dt: number, tx: number, tz: number)
	local s = sim()
	if not s then
		return
	end
	local typeId: string
	local extra: Models.Extra = {}
	local variant = Build.variant
	if Build.tool == "move" then
		local o = Build.moveId and s.objects[Build.moveId]
		if not o then
			Build.setTool("select")
			return
		end
		typeId = o.type
		variant = o.variant or 0
		extra = { level = o.level, goods = o.goods, tier = s.tier }
	else
		typeId = Build.item or "lamp"
		extra = { tier = s.tier }
	end
	makeGhost(typeId, variant, extra)
	local m = ghost
	if not m then
		return
	end
	local w, d = s:size(typeId, Build.rot)
	local x = tx - (w - 1) // 2
	local z = tz - (d - 1) // 2
	ghostAt.x, ghostAt.z = x, z
	local ok, reason
	if Build.tool == "move" then
		ok, reason = s:fits(typeId, x, z, Build.rot, Build.moveId)
	else
		ok, reason = s:canPlace(typeId, x, z, Build.rot)
	end
	local color = ok and GREEN or RED
	local text: string
	if ok then
		if Build.tool == "move" then
			text = "Move here"
		else
			local gold, lumen = s:costOf(typeId)
			text = string.format("%s  %d 🪙%s", B[typeId].name, gold, lumen > 0 and string.format("  %d 💠", lumen) or "")
		end
		if B[typeId].stall and not stallHasPath(s, typeId, x, z, Build.rot) then
			color = YELLOW
			text ..= "\n⚠ Needs a path in front (R to turn)"
		end
	else
		text = reason or "Can't build here"
	end
	ghostOk = ok
	ghostReason = reason
	local target = Layout.objectCFrame(plotCF, x, z, w, d, Build.rot)
	if ghostCF == CFrame.identity then
		ghostCF = target
	else
		ghostCF = ghostCF:Lerp(target, 1 - math.exp(-dt * 22))
	end
	m:PivotTo(ghostCF)
	local hl = m:FindFirstChild("Tint")
	if hl and hl:IsA("Highlight") then
		hl.FillColor = color
		hl.OutlineColor = color
	end
	if plate then
		plate.Color = color
	end
	if label then
		label.Text = text
		label.TextColor3 = ok and Color3.new(1, 1, 1) or Color3.fromRGB(255, 190, 180)
	end
	local _ = disc
	local _2 = labelGui
end

-- ─── path painting ─────────────────────────────────────────────────────────
local function clearPaint()
	for _, p in paintSet do
		p:Destroy()
	end
	paintSet = {}
	paintList = {}
	lastPaint = nil
end

local function addPaintTile(x: number, z: number)
	local s = sim()
	if not s or not Grid.inBounds(x, z) then
		return
	end
	local i = Grid.idx(x, z)
	if paintSet[i] then
		return
	end
	local erase = Build.tool == "erase"
	if erase then
		if s.surface[i] ~= 1 then
			return
		end
	else
		local cost = (#paintList + 1) * B.path.cost
		if cost > (State.profile and State.profile.gold or 0) then
			return
		end
		-- pretend the earlier tiles are already paved, so a stroke can run out from the road
		local ok = s:canPaint(x, z)
		if not ok then
			local joined = false
			for _, n in Grid.N4 do
				local ni = Grid.idx(x + n[1], z + n[2])
				if Grid.inBounds(x + n[1], z + n[2]) and paintSet[ni] then
					joined = true
				end
			end
			local t = s.terrain[i]
			local occ = s:objectAt(x, z)
			if not (joined and t == Grid.T.OPEN and s.surface[i] ~= 1 and (not occ or B[occ.type].walkable)) then
				return
			end
		end
	end
	local p = Models.box(preview, Vector3.new(TILE - 0.6, 0.35, TILE - 0.6), plotCF * CFrame.new((x + 0.5) * TILE, 0.35, (z + 0.5) * TILE), erase and RED or Palette.path[1], Enum.Material.Neon, false)
	p.Transparency = 0.35
	p.CanQuery = false
	p.CastShadow = false
	paintSet[i] = p
	table.insert(paintList, { x, z })
	Audio.play("click", 1.4, 0.5)
end

local function paintLine(x1: number, z1: number)
	local last = lastPaint
	if not last then
		addPaintTile(x1, z1)
		lastPaint = { x1, z1 }
		return
	end
	local x0, z0 = last[1], last[2]
	local dx, dz = math.abs(x1 - x0), math.abs(z1 - z0)
	local sx, sz = x0 < x1 and 1 or -1, z0 < z1 and 1 or -1
	local err = dx - dz
	local x, z = x0, z0
	for _ = 1, 64 do
		addPaintTile(x, z)
		if x == x1 and z == z1 then
			break
		end
		local e2 = 2 * err
		-- step one axis at a time so paths stay connected edge to edge
		if e2 > -dz then
			err -= dz
			x += sx
		elseif e2 < dx then
			err += dx
			z += sz
		end
	end
	lastPaint = { x1, z1 }
end

local function commitPaint()
	local list = paintList
	local erase = Build.tool == "erase"
	if #list == 0 then
		clearPaint()
		return
	end
	local keep = paintSet
	paintSet = {}
	paintList = {}
	lastPaint = nil
	task.spawn(function()
		local done = 0
		local reason: string? = nil
		for i = 1, #list, 80 do
			local chunk = {}
			for j = i, math.min(#list, i + 79) do
				table.insert(chunk, list[j])
			end
			local res = State.request(erase and "erase" or "paint", { tiles = chunk })
			done += res.n or 0
			if not res.ok then
				reason = res.reason
			end
		end
		task.wait(0.25)
		for _, p in keep do
			p:Destroy()
		end
		if done == 0 then
			Audio.play("error")
			State.toast.fire(reason or "No path could go there.", "🪨", "warn")
		elseif erase then
			Audio.play("remove", 1.2)
		end
	end)
end

-- ─── hovering and clicking buildings ───────────────────────────────────────
local rayParams = RaycastParams.new()
rayParams.FilterType = Enum.RaycastFilterType.Include

local function objectUnder(screen: Vector2, viewport: boolean): number?
	local root = Workspace:FindFirstChild("Kingsbloom")
	local plots = root and root:FindFirstChild("Plots")
	local f = plots and plots:FindFirstChild("Plot" .. plotIndex)
	local buildings = f and f:FindFirstChild("Buildings")
	if buildings then
		rayParams.FilterDescendantsInstances = { buildings }
		local cam = Workspace.CurrentCamera
		local ray = viewport and cam:ViewportPointToRay(screen.X, screen.Y) or cam:ScreenPointToRay(screen.X, screen.Y)
		local hit = Workspace:Raycast(ray.Origin, ray.Direction * 800, rayParams)
		if hit then
			local m: Instance? = hit.Instance
			while m and m ~= buildings do
				local id = m:GetAttribute("ObjId")
				if typeof(id) == "number" then
					return id
				end
				m = m.Parent
			end
		end
	end
	-- fall back to whatever stands on the tile under the pointer
	local g = BuildCamera.ground(screen, viewport)
	local s = sim()
	if g and s then
		local x, z = Layout.toTile(plotCF, g)
		local o = s:objectAt(math.floor(x), math.floor(z))
		return o and o.id or nil
	end
	return nil
end

local function setHover(id: number?)
	hoverId = id
	local m = id and WorldFx.model(plotIndex, id)
	local def = id and sim() and sim().objects[id] and B[sim().objects[id].type]
	if m and def and not (Build.tool == "remove" and def.fixed) then
		hoverHighlight.Adornee = m
		hoverHighlight.Enabled = true
		if Build.tool == "remove" then
			hoverHighlight.FillColor = RED
			hoverHighlight.FillTransparency = 0.55
			hoverHighlight.OutlineColor = RED
		else
			hoverHighlight.FillTransparency = 0.85
			hoverHighlight.FillColor = Color3.new(1, 1, 1)
			hoverHighlight.OutlineColor = Color3.new(1, 1, 1)
		end
	else
		hoverHighlight.Enabled = false
	end
end

local function place()
	if pending then
		return
	end
	local s = sim()
	if not s then
		return
	end
	if not ghostOk then
		Audio.play("error")
		State.toast.fire(ghostReason or "Can't build there.", "⚠️", "warn")
		return
	end
	pending = true
	local tool, item, x, z, rot, variant, moveId = Build.tool, Build.item, ghostAt.x, ghostAt.z, Build.rot, Build.variant, Build.moveId
	task.spawn(function()
		local res
		if tool == "move" then
			res = State.request("move", { id = moveId, x = x, z = z, r = rot })
		else
			res = State.request("place", { t = item, x = x, z = z, r = rot, v = variant })
		end
		pending = false
		if res.ok then
			Audio.play("place")
			if tool == "move" then
				Build.setTool("select")
			elseif item then
				local def = B[item]
				if def.variants and def.variants > 1 and def.cat == "decor" then
					Build.variant = math.random(0, def.variants - 1)
				end
				if def.stall then
					inspectNewStall = true
				end
			end
		else
			Audio.play("error")
			State.toast.fire(res.reason or "Can't build there.", "⚠️", "warn")
		end
	end)
end

local function click(screen: Vector2, viewport: boolean)
	local tool = Build.tool
	if tool == "place" or tool == "move" then
		place()
	elseif tool == "select" then
		local id = objectUnder(screen, viewport)
		if id then
			Audio.play("click")
			State.inspect.fire(id)
		else
			State.inspect.fire(nil)
		end
	elseif tool == "remove" then
		local id = objectUnder(screen, viewport)
		local o = id and sim() and sim().objects[id]
		if o and not B[o.type].fixed then
			State.openPanel.fire("confirmRemove", id)
		elseif o then
			State.toast.fire("The Heartflame stays. Click it with 👆 Select to raise it.", "🔥", "warn")
		end
	end
end

-- ─── tools ─────────────────────────────────────────────────────────────────
function Build.setTool(tool: string, item: string?)
	if Build.tool ~= tool or Build.item ~= item then
		clearGhost()
		clearPaint()
	end
	Build.tool = tool
	Build.item = item
	if tool ~= "move" then
		Build.moveId = nil
	end
	if item and B[item] and B[item].variants then
		Build.variant = math.random(0, (B[item].variants :: number) - 1)
	else
		Build.variant = 0
	end
	hoverHighlight.Enabled = false
	Build.changed.fire()
	local hints = {
		select = "Click a building to inspect it  •  Drag to look around  •  Right-drag to turn  •  Scroll to zoom",
		place = "Click to build  •  R to turn  •  Esc to stop  •  Drag to look around",
		paint = "Hold and drag to paint a stone path (2 🪙 a tile)",
		erase = "Hold and drag over paths to remove them",
		remove = "Click a building to remove it (half the cost back)",
		move = "Click where it should go  •  R to turn  •  Esc to cancel",
	}
	Build.info.fire(hints[tool] or "")
end

function Build.select(item: string)
	local def = B[item]
	if not def then
		return
	end
	if def.surface then
		Build.setTool("paint")
	else
		Build.setTool("place", item)
	end
	Audio.play("pop")
end

function Build.startMove(id: number)
	local o = sim() and sim().objects[id]
	if not o then
		return
	end
	Build.rot = o.rot
	Build.setTool("move")
	Build.moveId = id
	Build.changed.fire()
end

function Build.rotate()
	Build.rot = (Build.rot + 1) % 4
	Audio.play("whoosh", 1.3, 0.6)
	Build.changed.fire()
end

function Build.enter()
	if State.mode == "build" then
		return
	end
	local index = State.myPlot()
	if not index then
		State.toast.fire("You need a plot to build. Wait for a clearing to free up.", "🌲", "warn")
		return
	end
	plotIndex = index
	plotCF = Layout.plotCFrame(index)
	State.setMode("build")
	local char = Players.LocalPlayer.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if hum then
		hum:UnequipTools()
	end
	local c = controls()
	if c then
		c:Disable()
	end
	local root = char and char:FindFirstChild("HumanoidRootPart")
	BuildCamera.enter(index, root and (root :: BasePart).Position or nil)
	ringTier = 0
	drawRing()
	Build.setTool("select")
	Audio.play("whoosh")
end

function Build.exit()
	if State.mode ~= "build" then
		return
	end
	State.setMode("play")
	BuildCamera.exit()
	local c = controls()
	if c then
		c:Enable()
	end
	clearGhost()
	clearPaint()
	ringFolder:ClearAllChildren()
	hoverHighlight.Enabled = false
	State.inspect.fire(nil)
	Audio.play("whoosh", 0.8)
end

function Build.toggle()
	if State.mode == "build" then
		Build.exit()
	else
		Build.enter()
	end
end

-- ─── input ─────────────────────────────────────────────────────────────────
local function pointerPos(input: InputObject): (Vector2, boolean)
	if input.UserInputType == Enum.UserInputType.Touch then
		return Vector2.new(input.Position.X, input.Position.Y), false
	end
	return UserInputService:GetMouseLocation(), true
end

local function isPointer(input: InputObject): boolean
	return input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch
end

local function hoverTile(screen: Vector2, viewport: boolean): (number?, number?)
	local g = BuildCamera.ground(screen, viewport)
	if not g then
		return nil, nil
	end
	local x, z = Layout.toTile(plotCF, g)
	return math.floor(x), math.floor(z)
end

local lastPointer = Vector2.zero
local lastViewport = true

function Build.start()
	BuildCamera.start()
	State.layoutChanged.connect(function()
		if State.mode == "build" then
			drawRing()
		end
		if inspectNewStall then
			inspectNewStall = false
			local s = sim()
			local best: number? = nil
			if s then
				for id, o in s.objects do
					if B[o.type].stall and (not best or id > best) then
						best = id
					end
				end
			end
			if best then
				State.inspect.fire(best)
			end
		end
	end)
	UserInputService.InputBegan:Connect(function(input, processed)
		if State.mode ~= "build" then
			return
		end
		if input.KeyCode == Enum.KeyCode.R and not processed then
			if Build.tool == "place" or Build.tool == "move" then
				Build.rotate()
			end
			return
		elseif input.KeyCode == Enum.KeyCode.Escape or input.KeyCode == Enum.KeyCode.Backspace then
			if Build.tool ~= "select" then
				Build.setTool("select")
			else
				State.inspect.fire(nil)
			end
			return
		elseif input.KeyCode == Enum.KeyCode.X and not processed then
			Build.setTool(Build.tool == "remove" and "select" or "remove")
			return
		end
		if processed or not isPointer(input) or State.modal then
			return
		end
		if input.UserInputType == Enum.UserInputType.Touch and BuildCamera.touchCount() >= 2 then
			-- a second finger: hand over to the camera
			pointerDown = false
			BuildCamera.endPan()
			clearPaint()
			return
		end
		local pos, viewport = pointerPos(input)
		pointerDown = true
		downAt = pos
		downViewport = viewport
		dragging = false
		lastPointer, lastViewport = pos, viewport
		if Build.tool == "paint" or Build.tool == "erase" then
			painting = true
			local x, z = hoverTile(pos, viewport)
			if x and z then
				paintLine(x, z)
			end
		else
			BuildCamera.beginPan(pos, viewport)
		end
	end)
	UserInputService.InputChanged:Connect(function(input)
		if State.mode ~= "build" then
			return
		end
		if input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then
			local pos, viewport = pointerPos(input)
			lastPointer, lastViewport = pos, viewport
			if pointerDown then
				if (pos - downAt).Magnitude > 7 then
					dragging = true
				end
				if painting then
					local x, z = hoverTile(pos, viewport)
					if x and z then
						paintLine(x, z)
					end
				elseif dragging then
					BuildCamera.panTo(pos, viewport)
				end
			end
		end
	end)
	UserInputService.InputEnded:Connect(function(input)
		if State.mode ~= "build" or not isPointer(input) or not pointerDown then
			return
		end
		pointerDown = false
		if painting then
			painting = false
			commitPaint()
			return
		end
		BuildCamera.endPan()
		if not dragging then
			click(downAt, downViewport)
		end
	end)
	RunService.RenderStepped:Connect(function(dt)
		if State.mode ~= "build" then
			return
		end
		local x, z = hoverTile(lastPointer, lastViewport)
		if Build.tool == "place" or Build.tool == "move" then
			if x and z then
				updateGhost(dt, x, z)
			end
		elseif Build.tool == "select" or Build.tool == "remove" then
			if not pointerDown then
				local id = objectUnder(lastPointer, lastViewport)
				if id ~= hoverId or (id and not hoverHighlight.Enabled) then
					setHover(id)
				end
			end
		end
	end)
end

return Build
