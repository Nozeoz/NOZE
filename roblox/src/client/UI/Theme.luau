--!strict
-- The Royal Storybook UI kit: parchment panels, chunky pressable buttons, progress bars, pills,
-- and the little tweens that make it feel alive. Every screen is built from these.

local TweenService = game:GetService("TweenService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Palette = require(Shared.Palette)

local Theme = {}

local C = Palette.ui
Theme.C = C
Theme.Font = {
	title = Enum.Font.FredokaOne,
	body = Enum.Font.BuilderSansBold,
	light = Enum.Font.BuilderSansMedium,
	fancy = Enum.Font.GrenzeGotisch,
}

-- Set by the audio controller so every button can click.
Theme.sound = function(_name: string) end

-- ─── screen size ───────────────────────────────────────────────────────────
-- Every screen is laid out for a 1360×780 window. Phones in landscape (short side under 500 px)
-- get the "compact" layout and a slightly bigger scale than a plain fit, so text stays readable.
Theme.TOPBAR = 58 -- Roblox's top bar; our ScreenGuis start below it

function Theme.isCompact(v: Vector2): boolean
	return math.min(v.X, v.Y) < 500
end

function Theme.scaleFor(v: Vector2): number
	local s = math.min(v.X / 1360, v.Y / 780) * 1.05
	if Theme.isCompact(v) then
		s = math.max(s, (v.Y - Theme.TOPBAR) / 500)
	end
	return math.clamp(s, 0.6, 1.25)
end

-- The size of a ScreenGui's canvas in its own (scaled) units.
function Theme.canvas(): Vector2
	local v = workspace.CurrentCamera.ViewportSize
	local s = Theme.scaleFor(v)
	return Vector2.new(v.X / s, (v.Y - Theme.TOPBAR) / s)
end

-- Gives a ScreenGui a UIScale that follows the window, and calls onLayout(compact, scale) now
-- and whenever the window changes size.
function Theme.autoScale(gui: ScreenGui, onLayout: ((boolean, number) -> ())?): UIScale
	local scale = Instance.new("UIScale")
	scale.Parent = gui
	local function update()
		local v = workspace.CurrentCamera.ViewportSize
		scale.Scale = Theme.scaleFor(v)
		if onLayout then
			onLayout(Theme.isCompact(v), scale.Scale)
		end
	end
	update()
	workspace.CurrentCamera:GetPropertyChangedSignal("ViewportSize"):Connect(update)
	return scale
end

function Theme.tween(inst: Instance, t: number, goals: { [string]: any }, style: Enum.EasingStyle?, dir: Enum.EasingDirection?): Tween
	local tw = TweenService:Create(inst, TweenInfo.new(t, style or Enum.EasingStyle.Quad, dir or Enum.EasingDirection.Out), goals)
	tw:Play()
	return tw
end

function Theme.corner(parent: Instance, radius: number?): UICorner
	local c = Instance.new("UICorner")
	c.CornerRadius = UDim.new(0, radius or 12)
	c.Parent = parent
	return c
end

function Theme.stroke(parent: Instance, color: Color3?, thickness: number?, transparency: number?): UIStroke
	local s = Instance.new("UIStroke")
	s.Color = color or C.inkSoft
	s.Thickness = thickness or 2
	s.Transparency = transparency or 0
	s.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
	s.Parent = parent
	return s
end

function Theme.textStroke(parent: Instance, color: Color3?, thickness: number?): UIStroke
	local s = Instance.new("UIStroke")
	s.Color = color or C.shadow
	s.Thickness = thickness or 1.5
	s.ApplyStrokeMode = Enum.ApplyStrokeMode.Contextual
	s.Parent = parent
	return s
end

function Theme.pad(parent: Instance, px: number, py: number?)
	local p = Instance.new("UIPadding")
	p.PaddingLeft = UDim.new(0, px)
	p.PaddingRight = UDim.new(0, px)
	p.PaddingTop = UDim.new(0, py or px)
	p.PaddingBottom = UDim.new(0, py or px)
	p.Parent = parent
end

function Theme.list(parent: Instance, vertical: boolean, padding: number?, align: Enum.HorizontalAlignment?, valign: Enum.VerticalAlignment?): UIListLayout
	local l = Instance.new("UIListLayout")
	l.FillDirection = vertical and Enum.FillDirection.Vertical or Enum.FillDirection.Horizontal
	l.Padding = UDim.new(0, padding or 8)
	l.SortOrder = Enum.SortOrder.LayoutOrder
	l.HorizontalAlignment = align or Enum.HorizontalAlignment.Left
	l.VerticalAlignment = valign or Enum.VerticalAlignment.Top
	l.Parent = parent
	return l
end

function Theme.gradient(parent: Instance, top: Color3, bottom: Color3, rotation: number?): UIGradient
	local g = Instance.new("UIGradient")
	g.Color = ColorSequence.new(top, bottom)
	g.Rotation = rotation or 90
	g.Parent = parent
	return g
end

function Theme.frame(parent: Instance, size: UDim2, pos: UDim2?, color: Color3?, transparency: number?): Frame
	local f = Instance.new("Frame")
	f.Size = size
	f.Position = pos or UDim2.new()
	f.BackgroundColor3 = color or C.parchment
	f.BackgroundTransparency = transparency or 0
	f.BorderSizePixel = 0
	f.Parent = parent
	return f
end

function Theme.label(parent: Instance, text: string, size: number, color: Color3?, font: Enum.Font?): TextLabel
	local l = Instance.new("TextLabel")
	l.BackgroundTransparency = 1
	l.Text = text
	l.TextSize = size
	l.Font = font or Theme.Font.body
	l.TextColor3 = color or C.ink
	l.TextWrapped = true
	l.RichText = true
	l.Size = UDim2.new(1, 0, 0, size + 6)
	l.TextXAlignment = Enum.TextXAlignment.Left
	l.Parent = parent
	return l
end

-- A soft drop shadow behind a frame.
function Theme.shadow(target: GuiObject, offset: number?, transparency: number?): Frame
	local s = Instance.new("Frame")
	s.Name = "Shadow"
	s.BackgroundColor3 = C.shadow
	s.BackgroundTransparency = transparency or 0.75
	s.BorderSizePixel = 0
	s.Size = target.Size
	s.Position = target.Position + UDim2.fromOffset(0, offset or 6)
	s.AnchorPoint = target.AnchorPoint
	s.ZIndex = math.max(0, target.ZIndex - 1)
	s.Parent = target.Parent
	local c = target:FindFirstChildOfClass("UICorner")
	Theme.corner(s, c and c.CornerRadius.Offset or 12)
	target:GetPropertyChangedSignal("Visible"):Connect(function()
		s.Visible = target.Visible
	end)
	return s
end

-- A parchment panel with an ink border.
function Theme.panel(parent: Instance, size: UDim2, pos: UDim2?, anchor: Vector2?): Frame
	local f = Theme.frame(parent, size, pos, C.parchment)
	f.AnchorPoint = anchor or Vector2.zero
	Theme.corner(f, 16)
	Theme.stroke(f, C.goldDeep, 3)
	Theme.gradient(f, C.parchment, C.parchmentDark, 90)
	return f
end

export type Button = {
	root: TextButton,
	item: GuiObject, -- what to lay out: the button, or the button with its caption
	label: TextLabel,
	setText: (string) -> (),
	setEnabled: (boolean) -> (),
	setColor: (Color3) -> (),
}

-- A chunky button with a lip that presses down. `color` is the face colour.
function Theme.button(parent: Instance, text: string, size: UDim2, color: Color3?, onClick: (() -> ())?, textSize: number?): Button
	local face = color or C.royal
	local holder = Instance.new("TextButton")
	holder.Name = "Button"
	holder.Text = ""
	holder.AutoButtonColor = false
	holder.BackgroundTransparency = 1
	holder.Size = size
	holder.Parent = parent
	local lip = Theme.frame(holder, UDim2.new(1, 0, 1, 0), UDim2.fromOffset(0, 4), face:Lerp(Color3.new(0, 0, 0), 0.35))
	Theme.corner(lip, 12)
	local top = Theme.frame(holder, UDim2.new(1, 0, 1, 0), UDim2.fromOffset(0, 0), face)
	top.Name = "Face"
	Theme.corner(top, 12)
	Theme.gradient(top, face:Lerp(Color3.new(1, 1, 1), 0.18), face, 90)
	Theme.stroke(top, face:Lerp(Color3.new(0, 0, 0), 0.45), 2)
	local label = Theme.label(top, text, textSize or 20, Palette.white, Theme.Font.title)
	label.Size = UDim2.fromScale(1, 1)
	label.TextXAlignment = Enum.TextXAlignment.Center
	label.TextYAlignment = Enum.TextYAlignment.Center
	label.TextScaled = false
	Theme.textStroke(label, face:Lerp(Color3.new(0, 0, 0), 0.6), 1.5)
	local scale = Instance.new("UIScale")
	scale.Parent = holder
	local enabled = true
	holder.MouseEnter:Connect(function()
		if enabled then
			Theme.tween(scale, 0.12, { Scale = 1.05 })
		end
	end)
	holder.MouseLeave:Connect(function()
		Theme.tween(scale, 0.12, { Scale = 1 })
		top.Position = UDim2.fromOffset(0, 0)
	end)
	holder.MouseButton1Down:Connect(function()
		if enabled then
			top.Position = UDim2.fromOffset(0, 3)
		end
	end)
	holder.MouseButton1Up:Connect(function()
		top.Position = UDim2.fromOffset(0, 0)
	end)
	holder.Activated:Connect(function()
		if not enabled then
			Theme.sound("error")
			return
		end
		Theme.sound("click")
		if onClick then
			onClick()
		end
	end)
	local b: Button = {
		root = holder,
		item = holder,
		label = label,
		setText = function(t: string)
			label.Text = t
		end,
		setEnabled = function(on: boolean)
			enabled = on
			top.BackgroundTransparency = on and 0 or 0.35
			label.TextTransparency = on and 0 or 0.35
		end,
		setColor = function(c: Color3)
			face = c
			top.BackgroundColor3 = c
			lip.BackgroundColor3 = c:Lerp(Color3.new(0, 0, 0), 0.35)
			local g = top:FindFirstChildOfClass("UIGradient")
			if g then
				g.Color = ColorSequence.new(c:Lerp(Color3.new(1, 1, 1), 0.18), c)
			end
			local st = top:FindFirstChildOfClass("UIStroke")
			if st then
				st.Color = c:Lerp(Color3.new(0, 0, 0), 0.45)
			end
		end,
	}
	return b
end

-- A round icon button. With a caption, `item` is a frame holding the button and the caption
-- under it, so lists and screen edges account for both.
function Theme.round(parent: Instance, icon: string, diameter: number, color: Color3?, onClick: (() -> ())?, hint: string?): Button
	local holder: Instance = parent
	local item: Frame? = nil
	if hint then
		local f = Theme.frame(parent, UDim2.fromOffset(diameter + 26, diameter + 24), nil, C.shadow, 1)
		f.Name = "Item"
		holder = f
		item = f
	end
	local b = Theme.button(holder, icon, UDim2.fromOffset(diameter, diameter), color, onClick, math.floor(diameter * 0.5))
	for _, d in b.root:GetDescendants() do
		if d:IsA("UICorner") then
			d.CornerRadius = UDim.new(1, 0)
		end
	end
	if hint and item then
		b.root.AnchorPoint = Vector2.new(0.5, 0)
		b.root.Position = UDim2.fromScale(0.5, 0)
		local k = Theme.label(item, hint, 13, Palette.white, Theme.Font.title)
		k.Name = "Caption"
		k.AnchorPoint = Vector2.new(0.5, 1)
		k.Position = UDim2.fromScale(0.5, 1)
		k.Size = UDim2.new(1, 12, 0, 16)
		k.TextXAlignment = Enum.TextXAlignment.Center
		k.TextWrapped = false
		Theme.textStroke(k, C.shadow, 1.5)
		b.item = item
	end
	return b
end

export type Bar = { root: Frame, fill: Frame, set: (number, boolean?) -> () }

function Theme.bar(parent: Instance, size: UDim2, color: Color3, back: Color3?): Bar
	local root = Theme.frame(parent, size, nil, back or C.shadow, back and 0 or 0.55)
	Theme.corner(root, 8)
	local fill = Theme.frame(root, UDim2.fromScale(0, 1), nil, color)
	fill.Name = "Fill"
	Theme.corner(fill, 8)
	Theme.gradient(fill, color:Lerp(Color3.new(1, 1, 1), 0.3), color, 90)
	local b: Bar = {
		root = root,
		fill = fill,
		set = function(f: number, animate: boolean?)
			local goal = UDim2.fromScale(math.clamp(f, 0, 1), 1)
			if animate then
				Theme.tween(fill, 0.45, { Size = goal }, Enum.EasingStyle.Quart)
			else
				fill.Size = goal
			end
		end,
	}
	return b
end

-- A bouncy "pop" on any GUI object (adds a UIScale if needed).
function Theme.pop(obj: GuiObject, from: number?)
	local sc = obj:FindFirstChildOfClass("UIScale")
	if not sc then
		local created = Instance.new("UIScale")
		created.Parent = obj
		sc = created
	end
	local scale = sc :: UIScale
	scale.Scale = from or 0.6
	Theme.tween(scale, 0.35, { Scale = 1 }, Enum.EasingStyle.Back)
end

function Theme.formatNumber(n: number): string
	n = math.floor(n)
	if n >= 1e6 then
		return string.format("%.1fM", n / 1e6)
	elseif n >= 1e4 then
		return string.format("%.1fK", n / 1e3)
	end
	local s = tostring(n)
	local out = s:reverse():gsub("(%d%d%d)", "%1,"):reverse()
	if out:sub(1, 1) == "," then
		out = out:sub(2)
	end
	return out
end

return Theme
