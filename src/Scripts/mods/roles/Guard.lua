-- ============================================================
-- Scripts/mods/roles/Guard.lua
-- Muhafiz rolleri: guard_melee (sadece kisa kilic) ve guard_ranged (arbalet).
-- ============================================================

nebakovrising = nebakovrising or {}
local Roles = nebakovrising.Roles

local guardClothingPreset = "a1b2c3d4-0005-4000-8000-100000000005"
local guardClothingItemIds = {
    "4c7218e8-78c2-49cf-b88a-06f567c24e5a",
    "ffe35c10-6a19-42f3-9960-1c4801fd1fbf",
    "7ae64aa3-444f-4f10-b05d-4a943c965551",
}

local function guardRole(overrides)
    local role = {
        faction = nebakovrising.Config.guardFaction,
        clothingPreset = guardClothingPreset,
        clothingItemIds = guardClothingItemIds,
        weaponDrawContext = true,
        bedPool = "guard",
        interaction = { label = "muhafiz", inventory = true, equipTransferred = true },
        behaviors = {},
    }
    for key, value in pairs(overrides) do
        role[key] = value
    end
    return role
end

Roles.Register(guardRole({
    id = "guard_melee",
    label = "Melee muhafiz",
    namePrefix = "nebakovrising_MeleeGuard_",
    command = "nebakovrising_spawn_melee_guard",
    commandDescription = "Oyuncunun yanina melee muhafiz (kilic) spawn et",
    -- weapon_preset__nebakovrising.xml: yalnizca kisa kilic
    weaponPreset = "a1b2c3d4-0006-4000-8000-100000000006",
    weaponClassId = "2f2095b6-ad4b-4002-9af3-96612f3e143c",
}))

Roles.Register(guardRole({
    id = "guard_ranged",
    label = "Ranged muhafiz",
    namePrefix = "nebakovrising_RangedGuard_",
    command = "nebakovrising_spawn_ranged_guard",
    commandDescription = "Oyuncunun yanina ranged muhafiz (arbalet) spawn et",
    -- vanilla preset: nebakovObrana_battle_crossbow (arbalet + ok + kisa kilic)
    weaponPreset = "05a2e19b-2e8c-43c8-b1af-a10f8e948725",
}))
