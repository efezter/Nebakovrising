-- ============================================================
-- Scripts/mods/roles/Blacksmith.lua
-- Demirci. Yatak havuzu: blacksmith (selector'lar CastleUtils.bedPools icinde).
-- ============================================================

nebakovrising = nebakovrising or {}
local Roles = nebakovrising.Roles

Roles.Register({
    id = "blacksmith",
    label = "Demirci",
    namePrefix = "nebakovrising_Blacksmith_",
    command = "nebakovrising_spawn_blacksmith",
    commandDescription = "Oyuncunun yanina demirci spawn et",
    faction = nebakovrising.Config.guardFaction,
    clothingPreset = "a1b2c3d4-0005-4000-8000-100000000005",
    weaponDrawContext = true,
    bedPool = "blacksmith",
    interaction = { label = "demirci", inventory = true, equipTransferred = true },
    behaviors = {},
})
