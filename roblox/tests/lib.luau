-- A tiny test library for the Lune tests.

local T = {}
local passed, failed = 0, 0

function T.describe(name: string)
	print("\n" .. name)
end

function T.test(name: string, fn: () -> ())
	local ok, err = pcall(fn)
	if ok then
		passed += 1
		print("  ✓ " .. name)
	else
		failed += 1
		print("  ✗ " .. name .. "\n      " .. tostring(err))
	end
end

function T.expect(cond: any, msg: string?)
	if not cond then
		error(msg or "expectation failed", 2)
	end
end

function T.eq(a: any, b: any, msg: string?)
	if a ~= b then
		error(string.format("%s: expected %s, got %s", msg or "values differ", tostring(b), tostring(a)), 2)
	end
end

function T.summary(): number
	print(string.format("\n%d passed, %d failed", passed, failed))
	return failed
end

return T
