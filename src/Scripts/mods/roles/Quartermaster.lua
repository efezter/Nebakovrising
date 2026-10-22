-- ============================================================
-- Scripts/mods/roles/Quartermaster.lua
-- Levazim subayi. Yatak havuzu: quartermaster (selector'lar CastleUtils.bedPools icinde).
-- ============================================================

nebakovrising = nebakovrising or {}
local Roles = nebakovrising.Roles

Roles.Register({
    id = "quartermaster",
    label = "Levazim subayi",
    namePrefix = "nebakovrising_Quartermaster_",
    command = "nebakovrising_spawn_quartermaster",
    commandDescription = "Oyuncunun yanina levazim subayi spawn et",
    faction = nebakovrising.Config.guardFaction,
    clothingPreset = "a1b2c3d4-0005-4000-8000-100000000005",
    weaponDrawContext = true,
    bedPool = "quartermaster",
    interaction = { label = "levazim subayi", inventory = true, equipTransferred = true },
    behaviors = {},
})
