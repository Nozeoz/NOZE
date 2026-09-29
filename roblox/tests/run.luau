-- Runs the pure-Luau tests with Lune:   cd roblox && lune run tests/run.luau
-- Roblox modules require each other with `require(script.Parent.X)`; Lune uses file paths, so the
-- shared modules are first copied to tests/.build with those requires rewritten.

local fs = require("@lune/fs")
local process = require("@lune/process")

local SRC = "src/shared"
local OUT = "tests/.build/shared"

if fs.isDir("tests/.build") then
	fs.removeDir("tests/.build")
end
fs.writeDir(OUT)
for _, name in fs.readDir(SRC) do
	if string.match(name, "%.luau$") then
		local code = fs.readFile(SRC .. "/" .. name)
		code = string.gsub(code, "require%(script%.Parent%.([%w_]+)%)", 'require("./%1")')
		fs.writeFile(OUT .. "/" .. name, code)
	end
end

local T = require("./lib")
require("./spec_sim")
require("./spec_progress")
require("./spec_pacing")

local failed = T.summary()
process.exit(failed > 0 and 1 or 0)
