--!strict
-- The big moments: level-ups with rays, confetti and unlock cards; quest rewards; achievements;
-- new visitor kinds; the Night Ledger at dawn; the Heartflame rising; phase and server news;
-- and the welcome for new Sovereigns.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Catalog = require(Shared.Catalog)
local Palette = require(Shared.Palette)

local State = require(script.Parent.Parent.State)
local Audio = require(script.Parent.Parent.Audio)
local WorldFx = require(script.Parent.Parent.WorldFx)
local Theme = require(script.Parent.Theme)
local HUD = require(script.Parent.HUD)

local Ceremony = {}

local C = Theme.C
local F = Theme.Font
local W = Palette.white

local gui: ScreenGui
local queue: { () -> () } = {}
local busy = false

local function nextInQueue()
	if busy or #queue == 0 then
		return
	end
	busy = true
	local fn = table.remove(queue, 1) :: () -> ()
	task.spawn(fn)
end

local function enqueue(fn: () -> ())
	table.insert(queue, fn)
	nextInQueue()
end

local function done()
	busy = false
	task.defer(nextInQueue)
end

local function confetti(parent: GuiObject, n: number)
	local colors = { C.gold, C.red, C.green, C.lumen, Color3.fromRGB(255, 160, 200), W }
	for _ = 1, n do
		local f = Theme.frame(parent, UDim2.fromOffset(math.random(8, 14), math.random(12, 20)), UDim2.new(math.random(), 0, -0.05, 0), colors[math.random(1, #colors)])
		f.Rotation = math.random(0, 360)
		f.ZIndex = 30
		local t = 1.6 + math.random() * 1.4
		Theme.tween(f, t, { Position = UDim2.new(f.Position.X.Scale + (math.random() - 0.5) * 0.3, 0, 1.05, 0), Rotation = f.Rotation + math.random(-400, 400) }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
		task.delay(t, function()
			f:Destroy()
		end)
	end
end

-- ─── level up ──────────────────────────────────────────────────────────────
local function levelUp(data: any)
	enqueue(function()
		local compact = Theme.isCompact(workspace.CurrentCamera.ViewportSize)
		local overlay = Theme.frame(gui, UDim2.fromScale(1, 1), nil, C.shadow, 0.35)
		overlay.ZIndex = 20
		overlay.Active = true
		State.modal = true
		-- one centred column: title, badge (with its rays), what you are now, the unlock cards, OK
		local column = Theme.frame(overlay, UDim2.new(1, 0, 1, -16), UDim2.fromScale(0.5, 0.5), W, 1)
		column.AnchorPoint = Vector2.new(0.5, 0.5)
		column.ZIndex = 21
		Theme.list(column, true, compact and 6 or 14, Enum.HorizontalAlignment.Center, Enum.VerticalAlignment.Center)
		local title = Theme.label(column, data.rankUp and "RANK UP!" or "LEVEL UP!", compact and 54 or 64, C.gold, F.title)
		title.Size = UDim2.fromOffset(800, compact and 62 or 76)
		title.TextXAlignment = Enum.TextXAlignment.Center
		title.TextYAlignment = Enum.TextYAlignment.Center
		title.TextWrapped = false
		title.LayoutOrder = 1
		title.ZIndex = 25
		Theme.textStroke(title, C.goldDeep, 4)
		local size = compact and 146 or 170
		local holder = Theme.frame(column, UDim2.fromOffset(size, size), nil, W, 1)
		holder.LayoutOrder = 2
		holder.ZIndex = 21
		local rays = Theme.frame(holder, UDim2.fromOffset(1400, 1400), UDim2.fromScale(0.5, 0.5), W, 1)
		rays.AnchorPoint = Vector2.new(0.5, 0.5)
		rays.ZIndex = 21
		for i = 0, 11 do
			local r = Theme.frame(rays, UDim2.new(0, 70, 0.5, 0), UDim2.fromScale(0.5, 0.5), C.gold, 0.55)
			r.AnchorPoint = Vector2.new(0.5, 1)
			r.Rotation = i * 30
			r.ZIndex = 21
			local g = Instance.new("UIGradient")
			g.Transparency = NumberSequence.new(1, 0.2)
			g.Rotation = 90
			g.Parent = r
		end
		local spin = RunService.RenderStepped:Connect(function(dt: number)
			rays.Rotation += dt * 12
		end)
		local badge = Theme.frame(holder, UDim2.fromScale(1, 1), nil, C.gold)
		badge.ZIndex = 24
		Theme.corner(badge, size // 2)
		Theme.stroke(badge, C.goldDeep, 6)
		Theme.gradient(badge, Color3.fromRGB(255, 230, 150), C.goldDeep, 90)
		local num = Theme.label(badge, tostring(data.level), compact and 82 or 96, W, F.title)
		num.Size = UDim2.fromScale(1, 1)
		num.TextXAlignment = Enum.TextXAlignment.Center
		num.TextYAlignment = Enum.TextYAlignment.Center
		num.ZIndex = 25
		Theme.textStroke(num, C.goldDeep, 4)
		Theme.pop(badge, 0.2)
		Theme.pop(title, 0.5)
		local sub = Theme.label(column, data.rankUp and string.format("Your realm is now a %s %s!", data.rank, data.rankIcon or "") or string.format("%s %s", data.rankIcon or "", data.rank or ""), 28, W, F.title)
		sub.Size = UDim2.fromOffset(900, 36)
		sub.TextXAlignment = Enum.TextXAlignment.Center
		sub.LayoutOrder = 3
		sub.ZIndex = 25
		Theme.textStroke(sub, C.shadow, 2)
		-- the unlock cards
		local row = Theme.frame(column, UDim2.fromOffset(1100, 146), nil, W, 1)
		row.LayoutOrder = 4
		row.ZIndex = 25
		Theme.list(row, false, 12, Enum.HorizontalAlignment.Center, Enum.VerticalAlignment.Center)
		local cards = data.cards or {}
		for i, c in cards do
			if i > 6 then
				break
			end
			local card = Theme.panel(row, UDim2.fromOffset(170, 140), nil, nil)
			card.LayoutOrder = i
			card.ZIndex = 26
			card.Visible = false
			local ic = Theme.label(card, c.icon, 46, C.ink, F.title)
			ic.Size = UDim2.new(1, 0, 0, 58)
			ic.Position = UDim2.fromOffset(0, 6)
			ic.TextXAlignment = Enum.TextXAlignment.Center
			ic.ZIndex = 27
			local t = Theme.label(card, c.title, 18, C.royalDeep, F.title)
			t.Size = UDim2.new(1, -10, 0, 24)
			t.Position = UDim2.fromOffset(5, 66)
			t.TextXAlignment = Enum.TextXAlignment.Center
			t.ZIndex = 27
			local d = Theme.label(card, c.text, 13, C.inkSoft, F.body)
			d.Size = UDim2.new(1, -12, 0, 40)
			d.Position = UDim2.fromOffset(6, 92)
			d.TextXAlignment = Enum.TextXAlignment.Center
			d.TextYAlignment = Enum.TextYAlignment.Top
			d.ZIndex = 27
			task.delay(0.5 + i * 0.14, function()
				card.Visible = true
				Theme.pop(card, 0.3)
				Audio.play("pop", 1 + i * 0.05, 0.6)
			end)
		end
		Audio.play(data.rankUp and "rankup" or "levelup")
		confetti(overlay, 60)
		local char = Players.LocalPlayer.Character
		local root = char and char:FindFirstChild("HumanoidRootPart")
		if root and root:IsA("BasePart") then
			WorldFx.puff(root.Position, Palette.gold, 60, 1.4)
		end
		local closed = false
		local function close()
			if closed then
				return
			end
			closed = true
			spin:Disconnect()
			Theme.tween(overlay, 0.25, { BackgroundTransparency = 1 })
			for _, d in overlay:GetDescendants() do
				if d:IsA("GuiObject") then
					d.Visible = false
				end
			end
			task.wait(0.26)
			overlay:Destroy()
			State.modal = false
			done()
		end
		local btn = Theme.button(column, "Wonderful!", UDim2.fromOffset(240, 56), C.green, function()
			task.spawn(close)
		end, 24)
		btn.root.LayoutOrder = 5
		btn.root.ZIndex = 26
		for _, d in btn.root:GetDescendants() do
			if d:IsA("GuiObject") then
				d.ZIndex = 27
			end
		end
		task.delay(9, function()
			task.spawn(close)
		end)
	end)
end

-- ─── notification cards (they share the HUD's stack with the toasts) ───────
local function slideCard(icon: string, title: string, lines: { string }, color: Color3, hold: number)
	HUD.card(icon, title, lines, color, hold)
end

local function questDone(d: any)
	local npc = Catalog.Npcs[d.giver]
	local reward = {}
	if (d.gold or 0) > 0 then
		table.insert(reward, "+" .. d.gold .. " 🪙")
	end
	if (d.lumen or 0) > 0 then
		table.insert(reward, "+" .. d.lumen .. " 💠")
	end
	if (d.xp or 0) > 0 then
		table.insert(reward, "+" .. d.xp .. " XP")
	end
	slideCard(npc and npc.icon or "📜", "Quest complete!", { d.title, table.concat(reward, "   ") }, C.green, 4.5)
	Audio.play("quest")
end

local function achievement(d: any)
	local medals = { "🥉", "🥈", "🥇" }
	slideCard(d.icon, "Feat: " .. d.name, { string.format("%s %s  ·  %s", medals[d.tier] or "", d.tierName or "", d.desc or ""), "+" .. (d.lumen or 0) .. " 💠 Lumen" }, C.gold, 4)
	Audio.play("achievement")
end

local function discovery(d: any)
	local rc = Catalog.RarityColor[d.rarity] or { 255, 255, 255 }
	slideCard(d.icon, "New visitor: " .. d.name, { d.rarity .. " · added to your Codex", d.desc or "" }, Color3.fromRGB(rc[1], rc[2], rc[3]), 5)
	Audio.play("sparkle")
end

-- ─── the Night Ledger ──────────────────────────────────────────────────────
local function ledger(d: any)
	enqueue(function()
		State.modal = true
		local overlay = Theme.frame(gui, UDim2.fromScale(1, 1), nil, C.shadow, 0.4)
		overlay.ZIndex = 20
		overlay.Active = true
		local height = math.min(540, Theme.canvas().Y - 16)
		local panel = Theme.panel(overlay, UDim2.fromOffset(560, height), UDim2.fromScale(0.5, 0.5), Vector2.new(0.5, 0.5))
		panel.ZIndex = 21
		local head = Theme.frame(panel, UDim2.new(1, 0, 0, 64), nil, C.royal)
		head.ZIndex = 22
		Theme.corner(head, 16)
		Theme.gradient(head, Color3.fromRGB(255, 176, 120), C.royal, 90)
		local t = Theme.label(head, "🌅 The Night Ledger", 32, W, F.title)
		t.Size = UDim2.fromScale(1, 1)
		t.TextXAlignment = Enum.TextXAlignment.Center
		t.TextYAlignment = Enum.TextYAlignment.Center
		t.ZIndex = 23
		Theme.textStroke(t, C.shadow, 2)
		-- the rows scroll when the screen is short (phones)
		local body = Instance.new("ScrollingFrame")
		body.Size = UDim2.new(1, -40, 1, -212)
		body.Position = UDim2.fromOffset(20, 74)
		body.BackgroundTransparency = 1
		body.BorderSizePixel = 0
		body.AutomaticCanvasSize = Enum.AutomaticSize.Y
		body.CanvasSize = UDim2.new()
		body.ScrollBarThickness = 6
		body.ScrollBarImageColor3 = C.goldDeep
		body.ZIndex = 22
		body.Parent = panel
		Theme.list(body, true, 6)
		local visitors = d.visitors or 0
		local happy, content, unhappy = d.happy or 0, d.content or 0, d.unhappy or 0
		local sold = {}
		local soldCount = 0
		for _, g in Catalog.GoodsOrder do
			local n = d.sold and d.sold[g] or 0
			if n > 0 then
				soldCount += n
				table.insert(sold, Catalog.Goods[g].icon .. " ×" .. n)
			end
		end
		local missing = {}
		for g, n in d.missing or {} do
			local gd = Catalog.Goods[g]
			if gd and n > 0 then
				table.insert(missing, gd.icon .. " " .. n)
			end
		end
		local rows = {
			{ "🧳 Visitors", tostring(visitors) },
			{ "😊 Moods", string.format("💛 %d   🙂 %d   😞 %d", happy, content, unhappy) },
			{ "🛒 Sold", #sold > 0 and table.concat(sold, "  ") or "nothing" },
			{ "🪙 Gold earned", string.format("%d  (%d in tips)", d.gold or 0, d.tips or 0) },
			{ "⚔️ Gloomlings defeated", tostring(d.kills or 0) },
			{ "🌫️ Lamps snuffed", tostring(d.snuffed or 0) },
			{ "😱 Turned back", tostring(d.fled or 0) },
			{ "✨ Rewards", string.format("+%d XP   +%d 💠", d.xp or 0, d.lumen or 0) },
		}
		if #missing > 0 then
			table.insert(rows, { "❓ Asked for (not sold)", table.concat(missing, "  ") })
		end
		if d.settled and #d.settled > 0 then
			table.insert(rows, { "🏠 Moved in", table.concat(d.settled, ", ") })
		end
		if d.surge then
			table.insert(rows, { "🌀 Veil Surge", "Repelled! ✅" })
		end
		for i, r in rows do
			local rowF = Theme.frame(body, UDim2.new(1, -8, 0, 30), nil, i % 2 == 0 and C.parchmentDark or W, i % 2 == 0 and 0.4 or 1)
			rowF.LayoutOrder = i
			rowF.ZIndex = 22
			Theme.corner(rowF, 8)
			local a = Theme.label(rowF, r[1], 17, C.ink, F.title)
			a.Size = UDim2.new(0.58, 0, 1, 0)
			a.Position = UDim2.fromOffset(8, 0)
			a.TextYAlignment = Enum.TextYAlignment.Center
			a.ZIndex = 23
			local b = Theme.label(rowF, r[2], 17, C.royalDeep, F.title)
			b.Size = UDim2.new(0.42, -16, 1, 0)
			b.Position = UDim2.new(0.58, 0, 0, 0)
			b.TextXAlignment = Enum.TextXAlignment.Right
			b.TextYAlignment = Enum.TextYAlignment.Center
			b.ZIndex = 23
		end
		local verdict: string
		if visitors == 0 then
			verdict = "A quiet night. Light the road so travelers dare to come."
		elseif happy >= visitors * 0.5 then
			verdict = "A glowing night! The realm talks of your market."
		elseif (d.fled or 0) > visitors * 0.3 then
			verdict = "Too many turned back in the dark. More lamps on the road!"
		elseif #missing > 0 then
			verdict = "People asked for things you don't sell yet."
		else
			verdict = "A good night's trade. Decor and benches make visitors happier."
		end
		local v = Theme.label(panel, verdict, 18, C.inkSoft, F.title)
		v.Position = UDim2.new(0, 20, 1, -132)
		v.Size = UDim2.new(1, -40, 0, 44)
		v.TextXAlignment = Enum.TextXAlignment.Center
		v.TextYAlignment = Enum.TextYAlignment.Center
		v.ZIndex = 22
		local closed = false
		local btn = Theme.button(panel, "☀️ Good morning!", UDim2.fromOffset(240, 54), C.gold, function()
			if closed then
				return
			end
			closed = true
			overlay:Destroy()
			State.modal = false
			done()
		end, 22)
		btn.root.AnchorPoint = Vector2.new(0.5, 1)
		btn.root.Position = UDim2.new(0.5, 0, 1, -16)
		for _, dd in btn.root:GetDescendants() do
			if dd:IsA("GuiObject") then
				dd.ZIndex = 24
			end
		end
		btn.root.ZIndex = 24
		Theme.pop(panel, 0.7)
		Audio.play("bell")
		if soldCount > 0 then
			task.delay(0.4, function()
				Audio.play("coins")
			end)
		end
	end)
end

-- ─── welcome ───────────────────────────────────────────────────────────────
local function welcome()
	enqueue(function()
		State.modal = true
		local overlay = Theme.frame(gui, UDim2.fromScale(1, 1), nil, C.shadow, 0.35)
		overlay.ZIndex = 20
		overlay.Active = true
		local panel = Theme.panel(overlay, UDim2.fromOffset(820, 484), UDim2.fromScale(0.5, 0.5), Vector2.new(0.5, 0.5))
		panel.ZIndex = 21
		local t = Theme.label(panel, "Welcome to Kingsbloom", 44, C.royalDeep, F.fancy)
		t.Position = UDim2.fromOffset(0, 14)
		t.Size = UDim2.new(1, 0, 0, 52)
		t.TextXAlignment = Enum.TextXAlignment.Center
		t.ZIndex = 22
		local s = Theme.label(panel, "This clearing is yours, Sovereign. Grow a market that glows through the night.", 19, C.inkSoft, F.body)
		s.Position = UDim2.fromOffset(40, 68)
		s.Size = UDim2.new(1, -80, 0, 46)
		s.TextXAlignment = Enum.TextXAlignment.Center
		s.TextYAlignment = Enum.TextYAlignment.Center
		s.ZIndex = 22
		local row = Theme.frame(panel, UDim2.new(1, -40, 0, 240), UDim2.fromOffset(20, 120), W, 1)
		row.ZIndex = 22
		Theme.list(row, false, 16, Enum.HorizontalAlignment.Center)
		local touch = UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
		local cards = {
			{ "🔨", "Build", (touch and "Tap 🔨 Build." or "Press B.") .. " Place stalls, fields, homes and decor. Visitors only walk on paths." },
			{ "🏮", "Light the road", "At night travelers turn back in the dark. Lamps keep them coming (and happy)." },
			{ "⚔️", "Guard the night", "Gloomlings snuff lamps and scare visitors. " .. (touch and "Tap ⚔️ to swing your Lantern Staff, ✨ to burst." or "Click to swing your Lantern Staff, Q to burst.") },
		}
		for i, c in cards do
			local card = Theme.frame(row, UDim2.fromOffset(240, 240), nil, Color3.fromRGB(255, 246, 214))
			card.LayoutOrder = i
			card.ZIndex = 23
			Theme.corner(card, 14)
			Theme.stroke(card, C.goldDeep, 2)
			local ic = Theme.label(card, c[1], 56, C.ink, F.title)
			ic.Size = UDim2.new(1, 0, 0, 76)
			ic.Position = UDim2.fromOffset(0, 10)
			ic.TextXAlignment = Enum.TextXAlignment.Center
			ic.ZIndex = 24
			local ct = Theme.label(card, c[2], 24, C.royalDeep, F.title)
			ct.Size = UDim2.new(1, 0, 0, 30)
			ct.Position = UDim2.fromOffset(0, 88)
			ct.TextXAlignment = Enum.TextXAlignment.Center
			ct.ZIndex = 24
			local cd = Theme.label(card, c[3], 16, C.ink, F.body)
			cd.Size = UDim2.new(1, -24, 0, 100)
			cd.Position = UDim2.fromOffset(12, 122)
			cd.TextXAlignment = Enum.TextXAlignment.Center
			cd.TextYAlignment = Enum.TextYAlignment.Top
			cd.ZIndex = 24
			card.Visible = false
			task.delay(0.2 + i * 0.15, function()
				card.Visible = true
				Theme.pop(card, 0.4)
			end)
		end
		local closed = false
		local btn = Theme.button(panel, "Let's begin!", UDim2.fromOffset(260, 58), C.green, function()
			if closed then
				return
			end
			closed = true
			overlay:Destroy()
			State.modal = false
			task.spawn(State.request, "settings", { welcomed = true })
			done()
		end, 24)
		btn.root.AnchorPoint = Vector2.new(0.5, 1)
		btn.root.Position = UDim2.new(0.5, 0, 1, -18)
		btn.root.ZIndex = 24
		for _, dd in btn.root:GetDescendants() do
			if dd:IsA("GuiObject") then
				dd.ZIndex = 25
			end
		end
		Theme.pop(panel, 0.7)
		Audio.play("quest")
	end)
end

-- ─── routing ───────────────────────────────────────────────────────────────
local welcomed = false

function Ceremony.start(parent: Instance)
	gui = Instance.new("ScreenGui")
	gui.Name = "KingsbloomCeremony"
	gui.ResetOnSpawn = false
	gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	gui.DisplayOrder = 8
	gui.Parent = parent
	Theme.autoScale(gui)

	State.message.connect(function(kind: string, d: any)
		if kind == "levelup" then
			levelUp(d)
		elseif kind == "questDone" then
			questDone(d)
		elseif kind == "questReady" then
			HUD.toast("Quest ready: " .. tostring(d.title) .. "! Claim your reward.", "⭐", "good")
			Audio.play("notify")
		elseif kind == "achievement" then
			achievement(d)
		elseif kind == "discovery" then
			discovery(d)
		elseif kind == "ledger" then
			ledger(d)
		elseif kind == "tier" then
			HUD.banner("🔥 The Heartflame rises!", d.name .. ": the forest falls back.", C.gold, 4.5)
		elseif kind == "orders" then
			HUD.toast("New Royal Orders have arrived!", "📜", "good")
		elseif kind == "orderDone" then
			HUD.toast(string.format("Order complete: +%d 🪙  +%d XP", d.gold or 0, d.xp or 0), "📜", "good")
			Audio.play("coins")
			if d.sealed then
				HUD.banner("🏅 Royal Seal!", "All three orders done today: +5 💠", C.gold, 3.5)
			end
		elseif kind == "surge" then
			HUD.banner("🌀 The Veil surges!", "Gloomlings come for your lamps. Hold the line!", Palette.veil, 4)
			Audio.setPlaylist("surge")
		elseif kind == "surgeWon" then
			HUD.banner("✨ Surge repelled!", "The Veil falls back. +5 💠", C.green, 3.5)
			Audio.setPlaylist("night")
		elseif kind == "toast" then
			HUD.toast(d.text or "", d.icon, d.tone)
		elseif kind == "welcome" then
			welcome()
		end
	end)
	State.profileChanged.connect(function(p)
		if p and not p.welcomed and not welcomed then
			welcomed = true
			welcome()
		end
	end)
	State.notice.connect(function(d: any)
		if d.k == "phase" then
			if d.phase == "day" then
				HUD.banner("☀️ Morning · Day " .. tostring(d.day), "New Royal Orders are in. Tend the fields!", C.gold, 3.5)
				Audio.play("bell", 1.1)
			elseif d.phase == "dusk" then
				HUD.banner("🏮 The Lantern Market opens", "Prices +25% tonight. Keep the road lit!", Color3.fromRGB(255, 150, 90), 4)
				Audio.play("bell")
			elseif d.phase == "night" then
				HUD.banner("🌙 Night falls", "The Veil sends Gloomlings. Guard your lamps!", Palette.veil, 4)
			end
		elseif d.k == "rank" then
			HUD.toast(string.format("%s's realm is now a %s %s", d.name, d.rank, d.icon or ""), "🎉", "good")
		elseif d.k == "rare" then
			HUD.toast(string.format("A %s %s visited %s's market!", d.icon or "", d.visitor, d.name), "✨", "good")
		end
	end)
end

return Ceremony
