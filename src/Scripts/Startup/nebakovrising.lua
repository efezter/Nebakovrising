if System and System.LogAlways then
    System.LogAlways("[nebakovrising] Startup girisi calisti.")
end

if not Script or type(Script.ReloadScript) ~= "function" then
    if System and System.LogAlways then
        System.LogAlways("[nebakovrising] Baslatilamadi: Script.ReloadScript bulunamadi.")
    end
    return
end

local ok, err = pcall(function()
    Script.ReloadScript("Scripts/mods/nebakovrising.lua")
end)

if not ok and System and System.LogAlways then
    System.LogAlways("[nebakovrising] Ana script yuklenemedi: " .. tostring(err))
end
