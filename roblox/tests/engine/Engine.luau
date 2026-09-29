-- A small stand-in for the Roblox engine, so the real server and client scripts can run under Lune.
-- It loads the built place (Kingsbloom.rbxlx), gives every script its own environment, runs a
-- simulated clock with a task scheduler, fakes signals, remotes, DataStores, tweens and terrain,
-- and checks what crosses the network the way Roblox would (mixed tables, the 900-byte limit).
-- Instances and their properties are Lune's, so a wrong property name or type fails like in Roblox.

local fs = require("@lune/fs")
local luau = require("@lune/luau")
local roblox = require("@lune/roblox")
local serde = require("@lune/serde")

local Engine = {}

local R = roblox
local Instance = R.Instance

Engine.errors = {} :: { string }
Engine.warnings = {} :: { string }
Engine.network = { sent = 0, bytes = 0, maxSnap = 0, problems = {} :: { string } }

local function report(kind: string, msg: string)
	if kind == "error" then
		if #Engine.errors < 3 then
			print("\n  !! " .. msg .. "\n")
		end
		table.insert(Engine.errors, msg)
	else
		table.insert(Engine.warnings, msg)
	end
end

-- ─── the scheduler (simulated time) ────────────────────────────────────────
local Sched = { now = 0, queue = {} :: { any }, seq = 0 }
Engine.sched = Sched

local function resume(co: thread, ...: any)
	local ok, err = coroutine.resume(co, ...)
	if not ok then
		report("error", debug.traceback(co, tostring(err)))
	end
end

local function push(at: number, co: thread, args: { any }?)
	Sched.seq += 1
	table.insert(Sched.queue, { at = at, co = co, args = args or {}, seq = Sched.seq })
end

local task = {}
function task.spawn(f: any, ...: any): thread
	local co = type(f) == "thread" and f or coroutine.create(f)
	resume(co, ...)
	return co
end
function task.defer(f: any, ...: any): thread
	local co = type(f) == "thread" and f or coroutine.create(f)
	push(Sched.now, co, table.pack(...))
	return co
end
function task.delay(t: number?, f: any, ...: any): thread
	local co = type(f) == "thread" and f or coroutine.create(f)
	push(Sched.now + (t or 0), co, table.pack(...))
	return co
end
function task.wait(t: number?): number
	local co = coroutine.running()
	local d = math.max(t or 0.03, 0.001)
	push(Sched.now + d, co, {})
	coroutine.yield()
	return d
end
function task.cancel(_co: thread) end
Engine.task = task

function Sched.run()
	-- run everything that is due (including things that become due while running)
	local guard = 0
	while true do
		guard += 1
		if guard > 100000 then
			report("error", "scheduler: runaway loop")
			return
		end
		local best, bestIndex = nil, nil
		for i, item in Sched.queue do
			if item.at <= Sched.now + 1e-9 and (not best or item.at < best.at or (item.at == best.at and item.seq < best.seq)) then
				best, bestIndex = item, i
			end
		end
		if not best then
			return
		end
		table.remove(Sched.queue, bestIndex)
		if coroutine.status(best.co) == "suspended" then
			resume(best.co, table.unpack(best.args, 1, best.args.n or #best.args))
		end
	end
end

-- ─── signals ───────────────────────────────────────────────────────────────
local Signal = {}
Signal.__index = Signal
function Signal.new()
	return setmetatable({ handlers = {} }, Signal)
end
function Signal:Connect(fn)
	local c = { fn = fn, Connected = true }
	function c.Disconnect(conn)
		conn.Connected = false
	end
	table.insert(self.handlers, c)
	return c
end
function Signal:Once(fn)
	local c
	c = self:Connect(function(...)
		c:Disconnect()
		fn(...)
	end)
	return c
end
function Signal:Wait()
	local co = coroutine.running()
	self:Once(function(...)
		push(Sched.now, co, table.pack(...))
	end)
	return coroutine.yield()
end
function Signal:Fire(...)
	for _, c in table.clone(self.handlers) do
		if c.Connected then
			task.spawn(c.fn, ...)
		end
	end
end
Engine.Signal = Signal

local signals = setmetatable({}, { __mode = "k" })
local function signalOf(inst: any, name: string)
	local t = signals[inst]
	if not t then
		t = {}
		signals[inst] = t
	end
	local s = t[name]
	if not s then
		s = Signal.new()
		t[name] = s
	end
	return s
end
Engine.signalOf = signalOf

local function event(className: string, name: string)
	R.implementProperty(className, name, function(inst)
		return signalOf(inst, name)
	end)
end

for _, pair in {
	{ "RunService", "Heartbeat" }, { "RunService", "RenderStepped" }, { "RunService", "Stepped" },
	{ "Players", "PlayerAdded" }, { "Players", "PlayerRemoving" },
	{ "Player", "CharacterAdded" }, { "Player", "CharacterRemoving" },
	{ "RemoteEvent", "OnServerEvent" }, { "RemoteEvent", "OnClientEvent" },
	{ "UnreliableRemoteEvent", "OnServerEvent" }, { "UnreliableRemoteEvent", "OnClientEvent" },
	{ "ProximityPrompt", "Triggered" }, { "Tool", "Activated" }, { "Tool", "Equipped" }, { "Tool", "Unequipped" },
	{ "Humanoid", "StateChanged" }, { "Humanoid", "Died" },
	{ "UserInputService", "InputBegan" }, { "UserInputService", "InputEnded" }, { "UserInputService", "InputChanged" },
	{ "UserInputService", "JumpRequest" }, { "UserInputService", "TouchStarted" },
	{ "Sound", "Ended" }, { "NumberValue", "Changed" },
} do
	event(pair[1], pair[2])
end
for _, cls in { "TextButton", "ImageButton" } do
	for _, name in { "Activated", "MouseButton1Click", "MouseButton1Down", "MouseButton1Up", "MouseEnter", "MouseLeave" } do
		event(cls, name)
	end
end

-- ChildAdded / ChildRemoved for the folders the game watches.
local watched = setmetatable({}, { __mode = "k" })
for _, cls in { "Folder", "Model", "Workspace", "ReplicatedStorage", "Backpack", "PlayerGui" } do
	for _, name in { "ChildAdded", "ChildRemoved", "DescendantAdded" } do
		R.implementProperty(cls, name, function(inst)
			watched[inst] = true
			return signalOf(inst, name)
		end)
	end
end

-- ─── engine methods ────────────────────────────────────────────────────────
local function method(className: string, name: string, fn: (...any) -> ...any)
	R.implementMethod(className, name, fn)
end

local function allClasses(): { string }
	local db = R.getReflectionDatabase()
	return db:GetClassNames()
end

local function isA(className: string, base: string): boolean
	local db = R.getReflectionDatabase()
	local c = db:GetClass(className)
	while c do
		if c.Name == base then
			return true
		end
		c = c.Superclass and db:GetClass(c.Superclass) or nil
	end
	return false
end

local instanceClasses = {}
for _, name in allClasses() do
	table.insert(instanceClasses, name)
end

local function forEach(base: string, fn: (string) -> ())
	for _, name in instanceClasses do
		if isA(name, base) then
			fn(name)
		end
	end
end

-- WaitForChild: yields (simulated time) until the child appears or the timeout passes.
forEach("Instance", function(cls)
	pcall(method, cls, "WaitForChild", function(self, name: string, timeout: number?)
		local found = self:FindFirstChild(name)
		local waited = 0
		while not found do
			if not coroutine.isyieldable() then
				error("WaitForChild(" .. name .. ") on " .. self:GetFullName() .. " outside a coroutine")
			end
			task.wait(0.1)
			waited += 0.1
			found = self:FindFirstChild(name)
			if not found and waited >= (timeout or 15) then
				if not timeout then
					report("warn", "Infinite yield possible on " .. self:GetFullName() .. ":WaitForChild(\"" .. name .. "\")")
				end
				return nil
			end
		end
		return found
	end)
	pcall(method, cls, "GetPropertyChangedSignal", function(self, prop: string)
		return signalOf(self, "Prop:" .. prop)
	end)
	pcall(method, cls, "FindFirstAncestorOfClass", function(self, className: string)
		local p = self.Parent
		while p do
			if p.ClassName == className then
				return p
			end
			p = p.Parent
		end
		return nil
	end)
	pcall(method, cls, "FindFirstAncestorWhichIsA", function(self, className: string)
		local p = self.Parent
		while p do
			if p:IsA(className) then
				return p
			end
			p = p.Parent
		end
		return nil
	end)
end)

-- Parent changes fire ChildAdded/ChildRemoved on watched folders: wrap the Parent setter by polling
-- is impossible, so the game-side helpers below call Engine.touchChildren after big syncs instead.

local function pivotOf(self): any
	if self:IsA("BasePart") then
		return self.CFrame
	end
	local pp = self.PrimaryPart
	if pp then
		return pp.CFrame
	end
	local ok, wp = pcall(function()
		return self.WorldPivot
	end)
	if ok and wp then
		return wp
	end
	return R.CFrame.new()
end

local function parts(self): { any }
	local out = {}
	if self:IsA("BasePart") then
		table.insert(out, self)
	end
	for _, d in self:GetDescendants() do
		if d:IsA("BasePart") then
			table.insert(out, d)
		end
	end
	return out
end

forEach("PVInstance", function(cls)
	pcall(method, cls, "GetPivot", function(self)
		return pivotOf(self)
	end)
	pcall(method, cls, "PivotTo", function(self, cf)
		assert(typeof(cf) == "CFrame", "PivotTo expects a CFrame, got " .. typeof(cf))
		local old = pivotOf(self)
		local delta = cf * old:Inverse()
		for _, p in parts(self) do
			p.CFrame = delta * p.CFrame
		end
		if not self:IsA("BasePart") and not self.PrimaryPart then
			self.WorldPivot = cf
		end
	end)
end)

local scales = setmetatable({}, { __mode = "k" })
method("Model", "GetScale", function(self)
	return scales[self] or 1
end)
method("Model", "ScaleTo", function(self, s: number)
	assert(type(s) == "number" and s > 0, "ScaleTo expects a positive number")
	local old = scales[self] or 1
	local f = s / old
	local pivot = pivotOf(self)
	for _, p in parts(self) do
		local rel = pivot:ToObjectSpace(p.CFrame)
		p.Size = p.Size * f
		p.CFrame = pivot * (rel - rel.Position + rel.Position * f)
	end
	scales[self] = s
end)
method("Model", "GetBoundingBox", function(self)
	local ps = parts(self)
	if #ps == 0 then
		return pivotOf(self), R.Vector3.new(0, 0, 0)
	end
	local min, max = nil, nil
	for _, p in ps do
		local pos, half = p.CFrame.Position, p.Size / 2
		local a, b = pos - half, pos + half
		min = min and R.Vector3.new(math.min(min.X, a.X), math.min(min.Y, a.Y), math.min(min.Z, a.Z)) or a
		max = max and R.Vector3.new(math.max(max.X, b.X), math.max(max.Y, b.Y), math.max(max.Z, b.Z)) or b
	end
	return R.CFrame.new((min + max) / 2), max - min
end)

Engine.terrain = { fills = 0 }
local function checkFill(cf, size, mat)
	assert(typeof(cf) == "CFrame", "terrain fill: bad CFrame")
	assert(typeof(mat) == "EnumItem", "terrain fill: bad material")
	Engine.terrain.fills += 1
	local _ = size
end
method("Terrain", "FillBlock", function(_self, cf, size, mat)
	assert(typeof(size) == "Vector3", "FillBlock: size must be a Vector3")
	checkFill(cf, size, mat)
end)
method("Terrain", "FillCylinder", function(_self, cf, height, radius, mat)
	assert(type(height) == "number" and type(radius) == "number", "FillCylinder: bad height/radius")
	checkFill(cf, height, mat)
end)
method("Terrain", "SetMaterialColor", function(_self, mat, color)
	assert(typeof(mat) == "EnumItem" and typeof(color) == "Color3", "SetMaterialColor: bad args")
end)
method("Terrain", "Clear", function() end)

method("Workspace", "GetServerTimeNow", function()
	return 1700000000 + Sched.now
end)
method("Workspace", "Raycast", function()
	return nil
end)
method("Workspace", "BulkMoveTo", function(_self, list, cfs, _mode)
	assert(#list == #cfs, "BulkMoveTo: lists differ")
	for i, p in list do
		p.CFrame = cfs[i]
	end
end)

forEach("BasePart", function(cls)
	pcall(method, cls, "GetMass", function()
		return 1
	end)
end)

method("ParticleEmitter", "Emit", function() end)
method("Sound", "Play", function() end)
method("Sound", "Stop", function() end)
method("Sound", "Pause", function() end)

method("Humanoid", "TakeDamage", function(self, n: number)
	self.Health = math.max(0, self.Health - n)
end)
method("Humanoid", "EquipTool", function(self, tool)
	assert(tool and tool:IsA("Tool"), "EquipTool expects a Tool")
	tool.Parent = self.Parent
end)
method("Humanoid", "UnequipTools", function(self)
	local char = self.Parent
	local player = Engine.playerOf(char)
	local bp = player and player:FindFirstChildOfClass("Backpack")
	for _, t in char:GetChildren() do
		if t:IsA("Tool") and bp then
			t.Parent = bp
		end
	end
end)
method("Humanoid", "GetState", function()
	return R.Enum.HumanoidStateType.Running
end)
method("Humanoid", "ChangeState", function() end)

-- ─── services that need behaviour ──────────────────────────────────────────
local tweens = {}
Engine.tweenCount = 0
local TweenInfo = {}
function TweenInfo.new(t, style, dir, repeatCount, reverses, delayTime)
	return { Time = t or 1, EasingStyle = style, EasingDirection = dir, RepeatCount = repeatCount or 0, Reverses = reverses or false, DelayTime = delayTime or 0 }
end
Engine.TweenInfo = TweenInfo

method("TweenService", "Create", function(_self, inst, info, goals)
	assert(typeof(inst) == "Instance", "TweenService:Create needs an Instance")
	assert(type(info) == "table" and info.Time, "TweenService:Create needs a TweenInfo")
	assert(type(goals) == "table", "TweenService:Create needs goals")
	-- validate now, like Roblox does
	for k, v in goals do
		local ok, err = pcall(function()
			local cur = inst[k]
			if typeof(cur) ~= typeof(v) and not (type(cur) == "number" and type(v) == "number") then
				error(string.format("can't tween %s.%s (%s) to a %s", inst.ClassName, k, typeof(cur), typeof(v)))
			end
		end)
		if not ok then
			report("error", "Tween: " .. tostring(err))
		end
	end
	local tw = { Completed = Signal.new(), PlaybackState = "Begin" }
	function tw.Play(t)
		Engine.tweenCount += 1
		task.delay(info.Time + (info.DelayTime or 0), function()
			if inst.Parent ~= nil or inst:IsA("NumberValue") then
				for k, v in goals do
					pcall(function()
						inst[k] = v
					end)
				end
				if inst:IsA("NumberValue") and goals.Value then
					signalOf(inst, "Changed"):Fire(goals.Value)
				end
			end
			t.Completed:Fire(R.Enum.PlaybackState.Completed)
		end)
	end
	function tw.Cancel() end
	function tw.Pause() end
	table.insert(tweens, tw)
	return tw
end)

-- HttpService JSON
method("HttpService", "JSONEncode", function(_self, v)
	return serde.encode("json", v)
end)
method("HttpService", "JSONDecode", function(_self, s)
	return serde.decode("json", s)
end)

-- ─── what may cross the network (and go into a DataStore) ──────────────────
local function checkValue(v: any, path: string, forStore: boolean, seen: { [any]: boolean }, problems: { string })
	local t = typeof(v)
	if t == "table" then
		if seen[v] then
			table.insert(problems, path .. ": cyclic table")
			return
		end
		seen[v] = true
		local n = #v
		local count, stringKeys, numberKeys = 0, 0, 0
		for k, child in v do
			count += 1
			if type(k) == "string" then
				stringKeys += 1
			elseif type(k) == "number" then
				numberKeys += 1
			else
				table.insert(problems, path .. ": key of type " .. typeof(k))
			end
			checkValue(child, path .. "." .. tostring(k), forStore, seen, problems)
		end
		if stringKeys > 0 and numberKeys > 0 then
			table.insert(problems, path .. ": mixed table (string and number keys)")
		elseif numberKeys > 0 and numberKeys ~= n then
			table.insert(problems, path .. ": sparse array (holes or non-sequential number keys)")
		end
		seen[v] = nil
	elseif t == "number" then
		if v ~= v then
			table.insert(problems, path .. ": NaN")
		elseif forStore and (v == math.huge or v == -math.huge) then
			table.insert(problems, path .. ": infinity can't be saved")
		end
	elseif t == "function" or t == "thread" or t == "userdata" then
		table.insert(problems, path .. ": can't send a " .. t)
	elseif forStore and (t == "Instance" or t == "buffer" or (t ~= "string" and t ~= "boolean" and t ~= "nil")) then
		table.insert(problems, path .. ": can't save a " .. t)
	end
end
Engine.checkValue = checkValue

local function deepCopy(v: any): any
	if type(v) ~= "table" then
		if typeof(v) == "buffer" then
			local b = buffer.create(buffer.len(v))
			buffer.copy(b, 0, v)
			return b
		end
		return v
	end
	local out = {}
	for k, child in v do
		out[deepCopy(k)] = deepCopy(child)
	end
	return out
end

local function inspectArgs(name: string, args: { any })
	local problems = {}
	for i = 1, args.n or #args do
		checkValue(args[i], name .. "[" .. i .. "]", false, {}, problems)
	end
	for _, p in problems do
		if #Engine.network.problems < 50 then
			table.insert(Engine.network.problems, p)
		end
	end
	Engine.network.sent += 1
end

local function copyArgs(args: { any }): { any }
	local out = { n = args.n }
	for i = 1, args.n or #args do
		out[i] = deepCopy(args[i])
	end
	return out
end

Engine.localPlayer = nil :: any
function Engine.setLocalPlayer(p: any)
	Engine.localPlayer = p
	pcall(function()
		(Engine.game :: any):GetService("Players").LocalPlayer = p
	end)
end

local function deliverToClient(remote, player, args)
	if player ~= Engine.localPlayer then
		return
	end
	local copy = copyArgs(args)
	signalOf(remote, "OnClientEvent"):Fire(table.unpack(copy, 1, copy.n))
end

for _, cls in { "RemoteEvent", "UnreliableRemoteEvent" } do
	method(cls, "FireClient", function(self, player, ...)
		assert(typeof(player) == "Instance" and player:IsA("Player"), self.Name .. ":FireClient needs a Player")
		local args = table.pack(...)
		inspectArgs(self.Name, args)
		if cls == "UnreliableRemoteEvent" then
			local size = 0
			for i = 1, args.n do
				if typeof(args[i]) == "buffer" then
					size += buffer.len(args[i])
				else
					size += #serde.encode("json", args[i] == nil and 0 or args[i])
				end
			end
			Engine.network.maxSnap = math.max(Engine.network.maxSnap, size)
			if size > 900 then
				table.insert(Engine.network.problems, self.Name .. ": unreliable payload " .. size .. " bytes (> 900)")
			end
		end
		deliverToClient(self, player, args)
	end)
	method(cls, "FireAllClients", function(self, ...)
		local args = table.pack(...)
		inspectArgs(self.Name, args)
		if Engine.localPlayer then
			deliverToClient(self, Engine.localPlayer, args)
		end
	end)
	method(cls, "FireServer", function(self, ...)
		local args = table.pack(...)
		inspectArgs(self.Name .. "(to server)", args)
		local copy = copyArgs(args)
		signalOf(self, "OnServerEvent"):Fire(Engine.localPlayer, table.unpack(copy, 1, copy.n))
	end)
end

local invokeHandlers = setmetatable({}, { __mode = "k" })
R.implementProperty("RemoteFunction", "OnServerInvoke", function(inst)
	return invokeHandlers[inst]
end, function(inst, fn)
	invokeHandlers[inst] = fn
end)
method("RemoteFunction", "InvokeServer", function(self, ...)
	local fn = invokeHandlers[self]
	if not fn then
		error("InvokeServer: no OnServerInvoke on " .. self.Name)
	end
	local args = table.pack(...)
	inspectArgs(self.Name .. "(invoke)", args)
	local copy = copyArgs(args)
	local results = table.pack(fn(Engine.localPlayer, table.unpack(copy, 1, copy.n)))
	inspectArgs(self.Name .. "(result)", results)
	local out = copyArgs(results)
	return table.unpack(out, 1, out.n)
end)

-- ─── DataStores ────────────────────────────────────────────────────────────
Engine.store = {} :: { [string]: string }
Engine.storeWrites = 0
local function makeStore(name: string)
	local store = {}
	function store.GetAsync(_s, key: string)
		local raw = Engine.store[name .. "/" .. key]
		return raw and serde.decode("json", raw) or nil
	end
	function store.SetAsync(_s, key: string, value: any)
		local problems = {}
		checkValue(value, "DataStore:" .. key, true, {}, problems)
		for _, p in problems do
			table.insert(Engine.network.problems, p)
		end
		Engine.store[name .. "/" .. key] = serde.encode("json", value)
		Engine.storeWrites += 1
	end
	function store.UpdateAsync(s, key: string, fn: (any) -> any)
		local new = fn(s:GetAsync(key))
		s:SetAsync(key, new)
		return new
	end
	return store
end
local stores = {}
method("DataStoreService", "GetDataStore", function(_self, name: string)
	stores[name] = stores[name] or makeStore(name)
	return stores[name]
end)
method("BadgeService", "AwardBadgeAsync", function() end)

-- ─── players ───────────────────────────────────────────────────────────────
local playersList = {}
local playerByChar = setmetatable({}, { __mode = "k" })
function Engine.playerOf(char: any): any
	return playerByChar[char]
end
method("Players", "GetPlayers", function()
	return table.clone(playersList)
end)
method("Players", "GetPlayerByUserId", function(_self, id: number)
	for _, p in playersList do
		if p.UserId == id then
			return p
		end
	end
	return nil
end)
R.implementProperty("Players", "LocalPlayer", function()
	return Engine.localPlayer
end)

method("UserInputService", "GetMouseLocation", function()
	return R.Vector2.new(640, 360)
end)
method("UserInputService", "IsKeyDown", function()
	return false
end)
method("UserInputService", "GetFocusedTextBox", function()
	return nil
end)
method("RunService", "IsServer", function()
	return true
end)
method("RunService", "IsClient", function()
	return true
end)
method("RunService", "IsStudio", function()
	return true
end)
local renderSteps = {}
method("RunService", "BindToRenderStep", function(_self, name, _priority, fn)
	renderSteps[name] = fn
end)
method("RunService", "UnbindFromRenderStep", function(_self, name)
	renderSteps[name] = nil
end)
method("StarterGui", "SetCoreGuiEnabled", function() end)
method("StarterGui", "SetCore", function() end)
method("Camera", "ViewportPointToRay", function(self, x, y)
	local _ = x + y
	return R.Ray.new(self.CFrame.Position, self.CFrame.LookVector)
end)
method("Camera", "ScreenPointToRay", function(self, x, y)
	local _ = x + y
	return R.Ray.new(self.CFrame.Position, self.CFrame.LookVector)
end)
method("DataModel", "BindToClose", function(_self, fn)
	Engine.onClose = fn
end)

-- ─── loading scripts ───────────────────────────────────────────────────────
local game: any = nil
Engine.game = nil :: any

-- Properties the real engine derives or defaults, which Lune leaves unset until written.
local function initDefaults(inst: any)
	local function try(prop: string, value: any)
		pcall(function()
			inst[prop] = value
		end)
	end
	if inst:IsA("BasePart") then
		try("Position", R.Vector3.new(0, 0, 0))
		try("AssemblyLinearVelocity", R.Vector3.new(0, 0, 0))
	elseif inst:IsA("Model") then
		try("WorldPivot", R.CFrame.new())
	elseif inst:IsA("Sound") then
		try("IsPlaying", false)
		try("TimeLength", 0)
	elseif inst:IsA("Camera") then
		try("ViewportSize", R.Vector2.new(1280, 720))
	elseif inst:IsA("GuiObject") then
		try("AbsoluteSize", R.Vector2.new(100, 40))
		try("AbsolutePosition", R.Vector2.new(0, 0))
	end
end
Engine.initDefaults = initDefaults

local InstanceWrap = {
	new = function(className: string, parent: any?)
		local inst = R.Instance.new(className)
		initDefaults(inst)
		if parent then
			inst.Parent = parent
		end
		return inst
	end,
}

local RaycastParams = {
	new = function()
		return { FilterType = R.Enum.RaycastFilterType.Exclude, FilterDescendantsInstances = {}, IgnoreWater = false }
	end,
}

local baseGlobals = {
	Instance = InstanceWrap,
	RaycastParams = RaycastParams, Vector3 = R.Vector3, Vector2 = R.Vector2, CFrame = R.CFrame, Color3 = R.Color3,
	UDim = R.UDim, UDim2 = R.UDim2, NumberRange = R.NumberRange, NumberSequence = R.NumberSequence,
	NumberSequenceKeypoint = R.NumberSequenceKeypoint, ColorSequence = R.ColorSequence,
	ColorSequenceKeypoint = R.ColorSequenceKeypoint, Enum = R.Enum, Ray = R.Ray, Rect = R.Rect,
	BrickColor = R.BrickColor, Font = R.Font, TweenInfo = TweenInfo, task = task,
}

local osClock = setmetatable({
	clock = function()
		return Sched.now
	end,
	time = function()
		return 1700000000 + math.floor(Sched.now)
	end,
}, { __index = os })

export type Env = { name: string, cache: { [any]: any }, globals: { [string]: any } }

local function makeRequire(env: Env)
	local function req(target: any): any
		if typeof(target) ~= "Instance" or not target:IsA("ModuleScript") then
			error("require expects a ModuleScript, got " .. typeof(target))
		end
		local cached = env.cache[target]
		if cached ~= nil then
			if cached == "__loading" then
				error("require cycle at " .. target:GetFullName())
			end
			return cached
		end
		env.cache[target] = "__loading"
		local ok, result = pcall(Engine.runSource, env, target)
		if not ok then
			env.cache[target] = nil
			error("requiring " .. target:GetFullName() .. " failed: " .. tostring(result), 0)
		end
		env.cache[target] = result
		return result
	end
	return req
end

function Engine.newEnv(name: string): Env
	local env: Env = { name = name, cache = {}, globals = {} }
	local g = env.globals
	for k, v in baseGlobals do
		g[k] = v
	end
	g.game = game
	g.workspace = game:GetService("Workspace")
	g.os = osClock
	g.tick = function()
		return 1700000000 + Sched.now
	end
	g.warn = function(...)
		local parts = {}
		for i = 1, select("#", ...) do
			table.insert(parts, tostring((select(i, ...))))
		end
		report("warn", "[" .. name .. "] " .. table.concat(parts, " "))
	end
	g.print = function(...)
		local _ = ...
	end
	g.require = makeRequire(env)
	return env
end

function Engine.runSource(env: Env, scriptInst: any): any
	local source = scriptInst.Source
	-- a flat table: Lune copies the environment's own fields
	local vars = { script = scriptInst }
	for k, v in env.globals do
		vars[k] = v
	end
	local fn = luau.load(source, { debugName = scriptInst:GetFullName(), environment = vars })
	return fn()
end

-- Starts a Script/LocalScript in its own coroutine.
function Engine.start(env: Env, scriptInst: any)
	task.spawn(function()
		Engine.runSource(env, scriptInst)
	end)
end

function Engine.load(placePath: string)
	game = R.deserializePlace(fs.readFile(placePath))
	Engine.game = game
	for _, s in { "Players", "RunService", "TweenService", "HttpService", "DataStoreService", "BadgeService", "UserInputService", "SoundService", "StarterGui", "StarterPack", "GuiService", "ContentProvider", "Debris" } do
		pcall(function()
			game:GetService(s)
		end)
	end
	local ws = game:GetService("Workspace")
	local okCam, current = pcall(function()
		return ws.CurrentCamera
	end)
	if not okCam or not current then
		local cam = Instance.new("Camera")
		cam.Parent = ws
		ws.CurrentCamera = cam
		current = cam
	end
	initDefaults(current)
	current.CFrame = R.CFrame.new(0, 60, 80)
	local uis = game:GetService("UserInputService")
	pcall(function()
		uis.TouchEnabled = false
		uis.KeyboardEnabled = true
		uis.MouseEnabled = true
	end)
	pcall(function()
		(game:GetService("Lighting") :: any).ClockTime = 9
	end)
	if not ws:FindFirstChildOfClass("Terrain") then
		local t = Instance.new("Terrain")
		t.Parent = ws
	end
	return game
end

-- ─── players joining ───────────────────────────────────────────────────────
function Engine.makeCharacter(player: any, pos: any): any
	local char = Instance.new("Model")
	char.Name = player.Name
	initDefaults(char)
	local hrp = Instance.new("Part")
	initDefaults(hrp)
	hrp.Name = "HumanoidRootPart"
	hrp.Size = R.Vector3.new(2, 2, 1)
	hrp.CFrame = R.CFrame.new(pos)
	hrp.Position = pos
	hrp.Parent = char
	local head = Instance.new("Part")
	initDefaults(head)
	head.Name = "Head"
	head.CFrame = R.CFrame.new(pos + R.Vector3.new(0, 1.5, 0))
	head.Parent = char
	local hum = Instance.new("Humanoid")
	hum.MaxHealth = 100
	hum.Health = 100
	hum.Parent = char
	char.PrimaryPart = hrp
	char.Parent = game:GetService("Workspace")
	playerByChar[char] = player
	return char
end

function Engine.addPlayer(name: string, userId: number): any
	local players = game:GetService("Players")
	local p = Instance.new("Player")
	p.Name = name
	p.DisplayName = name
	p.UserId = userId
	local bp = Instance.new("Backpack")
	bp.Parent = p
	local pg = Instance.new("PlayerGui")
	pg.Parent = p
	local ps = Instance.new("PlayerScripts")
	ps.Parent = p
	p.Parent = players
	table.insert(playersList, p)
	signalOf(players, "PlayerAdded"):Fire(p)
	return p
end

function Engine.spawnCharacter(p: any, pos: any): any
	local char = Engine.makeCharacter(p, pos)
	-- StarterPack tools go into the Backpack on spawn
	local bp = p:FindFirstChildOfClass("Backpack")
	for _, t in game:GetService("StarterPack"):GetChildren() do
		t:Clone().Parent = bp
	end
	p.Character = char
	signalOf(p, "CharacterAdded"):Fire(char)
	return char
end

function Engine.removePlayer(p: any)
	local players = game:GetService("Players")
	signalOf(players, "PlayerRemoving"):Fire(p)
	local i = table.find(playersList, p)
	if i then
		table.remove(playersList, i)
	end
	p.Parent = nil
end

-- ─── the clock ─────────────────────────────────────────────────────────────
function Engine.step(dt: number)
	Sched.now += dt
	local rs = game:GetService("RunService")
	signalOf(rs, "Stepped"):Fire(Sched.now, dt)
	for _, fn in renderSteps do
		task.spawn(fn, dt)
	end
	signalOf(rs, "RenderStepped"):Fire(dt)
	signalOf(rs, "Heartbeat"):Fire(dt)
	Sched.run()
end

function Engine.run(seconds: number, dt: number?)
	local d = dt or 0.1
	for _ = 1, math.floor(seconds / d + 0.5) do
		Engine.step(d)
	end
end

-- Fires ChildAdded for everything under a watched folder that we haven't announced yet
-- (Lune instances don't raise it on their own when parented).
local announced = setmetatable({}, { __mode = "k" })
function Engine.announceChildren()
	for inst in watched do
		for _, c in inst:GetChildren() do
			if not announced[c] then
				announced[c] = true
				signalOf(inst, "ChildAdded"):Fire(c)
			end
		end
	end
end

Engine.Instance = Instance
Engine.R = R

return Engine
