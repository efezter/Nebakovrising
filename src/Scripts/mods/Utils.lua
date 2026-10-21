-- ============================================================
-- Scripts/nebakovrising/Utils.lua   (YAN SCRIPT 1)
-- Ortak yardimcilar. Diger scriptler nebakovrising.Utils.* ile cagirir.
-- ============================================================

nebakovrising = nebakovrising or {}
nebakovrising.Utils = nebakovrising.Utils or {}
local Utils = nebakovrising.Utils

function Utils.Log(msg)
    local cfg = nebakovrising.Config or {}
    if cfg.debug == false then return end
    System.LogAlways((cfg.prefix or "[nebakovrising]") .. " " .. tostring(msg))
end

function Utils.GetPlayerPos()
    local p = rawget(_G, "player")
    if p and p.GetWorldPos then
        return p:GetWorldPos()
    end
    return nil
end

function Utils.GetPlayer()
    local currentPlayer = rawget(_G, "player")
    if currentPlayer then return currentPlayer end

    local localActor = rawget(_G, "g_localActor")
    if localActor then return localActor end

    if Game and Game.GetPlayer then
        return Game.GetPlayer()
    end
    return nil
end

-- Oyuncunun yakinindaki entity'leri isim parcasina gore bul
function Utils.FindNear(namePart, radius)
    local pos = Utils.GetPlayerPos()
    if not pos then return {} end
    local found = {}
    local list = System.GetEntitiesInSphere(pos, radius or 10) or {}
    for _, e in ipairs(list) do
        local n = e:GetName()
        if n and n:find(namePart, 1, true) then
            table.insert(found, e)
        end
    end
    return found
end

-- Ornek: Utils, Spawner'a erisiyor (karsilikli erisim)
function Utils.PrintSpawned()
    for _, name in ipairs(nebakovrising.Spawner.GetSpawnedNames()) do
        Utils.Log(" - " .. name)
    end
end
