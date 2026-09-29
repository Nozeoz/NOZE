--!strict
-- How it feels to fight and move: the Lantern Staff's three-hit combo with a lunging finisher,
-- aim assist toward the nearest Gloomling, the Radiant Burst (Q), a double jump, and Shift to run.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local Palette = require(Shared.Palette)

local State = require(script.Parent.State)
local Audio = require(script.Parent.Audio)
local Entities = require(script.Parent.Entities)
local WorldFx = require(script.Parent.WorldFx)

local Combat = {}

local player = Players.LocalPlayer
local lastSwing = 0
local comboCount = 0
Combat.burstReadyAt = 0
Combat.changed = State.signal()

local WALK, RUN = 20, 30

local function character(): (Model?, Humanoid?, BasePart?)
	local char = player.Character
	if not char then
		return nil, nil, nil
	end
	local hum = char:FindFirstChildOfClass("Humanoid")
	local root = char:FindFirstChild("HumanoidRootPart")
	if not hum or not root or not root:IsA("BasePart") or hum.Health <= 0 then
		return nil, nil, nil
	end
	return char, hum, root
end

local function staff(): Tool?
	local char = player.Character
	local t = char and char:FindFirstChild("LanternStaff")
	if t and t:IsA("Tool") then
		return t
	end
	local bp = player:FindFirstChildOfClass("Backpack")
	local b = bp and bp:FindFirstChild("LanternStaff")
	if b and b:IsA("Tool") then
		return b
	end
	return nil
end

function Combat.equip()
	local _, hum = character()
	local tool = staff()
	if hum and tool and tool.Parent ~= player.Character and State.mode == "play" then
		hum:EquipTool(tool)
	end
end

function Combat.swing()
	if State.mode ~= "play" then
		return
	end
	local char, _, root = character()
	local tool = staff()
	if not char or not root or not tool or tool.Parent ~= char then
		Combat.equip()
		return
	end
	local now = os.clock()
	if now - lastSwing < Config.STAFF_COOLDOWN then
		return
	end
	comboCount = (now - lastSwing < 0.95) and (comboCount % 3 + 1) or 1
	lastSwing = now
	-- aim assist: face the nearest Gloomling in reach
	local _, gid, gpos = Entities.nearestGloom(root.Position, Config.STAFF_RANGE + 6)
	if gpos then
		local flat = Vector3.new(gpos.X, root.Position.Y, gpos.Z)
		if (flat - root.Position).Magnitude > 0.5 then
			root.CFrame = CFrame.lookAt(root.Position, flat)
		end
	end
	local anim = Instance.new("StringValue")
	anim.Name = "toolanim"
	anim.Value = comboCount == 3 and "Lunge" or "Slash"
	anim.Parent = tool
	if comboCount == 3 then
		root.AssemblyLinearVelocity += root.CFrame.LookVector * 38 + Vector3.new(0, 14, 0)
		Audio.play("swing", 0.75, 1.2)
	else
		Audio.play("swing", comboCount == 2 and 1.15 or 1)
	end
	State.remotes.Swing:FireServer(gid)
end

function Combat.burst()
	if State.mode ~= "play" then
		return
	end
	local _, _, root = character()
	if not root then
		return
	end
	local now = os.clock()
	if now < Combat.burstReadyAt then
		Audio.play("error")
		return
	end
	Combat.burstReadyAt = now + Config.BURST_COOLDOWN
	Combat.changed.fire()
	State.remotes.Burst:FireServer()
end

-- ─── movement ──────────────────────────────────────────────────────────────
local jumps = 0
local function watchCharacter(char: Model)
	local hum = char:WaitForChild("Humanoid", 10)
	if not hum or not hum:IsA("Humanoid") then
		return
	end
	hum.WalkSpeed = WALK
	jumps = 0
	hum.StateChanged:Connect(function(_, new)
		if new == Enum.HumanoidStateType.Landed or new == Enum.HumanoidStateType.Running then
			jumps = 0
		elseif new == Enum.HumanoidStateType.Jumping then
			jumps = math.max(jumps, 1)
		end
	end)
	task.spawn(function()
		local bp = player:WaitForChild("Backpack", 10)
		local tool = bp and bp:WaitForChild("LanternStaff", 10)
		if tool and tool:IsA("Tool") then
			tool.Activated:Connect(Combat.swing)
			task.wait(0.3)
			Combat.equip()
		end
	end)
end

function Combat.start()
	player.CharacterAdded:Connect(watchCharacter)
	if player.Character then
		task.spawn(watchCharacter, player.Character)
	end
	UserInputService.JumpRequest:Connect(function()
		if State.mode ~= "play" then
			return
		end
		local _, hum, root = character()
		if not hum or not root then
			return
		end
		local st = hum:GetState()
		if (st == Enum.HumanoidStateType.Freefall or st == Enum.HumanoidStateType.Jumping) and jumps == 1 then
			jumps = 2
			local v = root.AssemblyLinearVelocity
			root.AssemblyLinearVelocity = Vector3.new(v.X, 56, v.Z)
			WorldFx.puff(root.Position - Vector3.new(0, 2.5, 0), Palette.lantern, 14, 0.8)
			Audio.play("whoosh", 1.4, 0.8)
		end
	end)
	UserInputService.InputBegan:Connect(function(input, processed)
		if processed then
			return
		end
		if input.KeyCode == Enum.KeyCode.Q and State.mode == "play" then
			Combat.burst()
		elseif input.KeyCode == Enum.KeyCode.LeftShift or input.KeyCode == Enum.KeyCode.RightShift then
			local _, hum = character()
			if hum then
				hum.WalkSpeed = RUN
			end
		end
	end)
	UserInputService.InputEnded:Connect(function(input)
		if input.KeyCode == Enum.KeyCode.LeftShift or input.KeyCode == Enum.KeyCode.RightShift then
			local _, hum = character()
			if hum then
				hum.WalkSpeed = WALK
			end
		end
	end)
	State.modeChanged.connect(function(mode)
		if mode == "play" then
			task.delay(0.2, Combat.equip)
		end
	end)
end

return Combat
