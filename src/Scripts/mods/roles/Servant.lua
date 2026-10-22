-- ============================================================
-- Scripts/mods/roles/Servant.lua
-- Hizmetkar. Yatak havuzu: servant (selector'lar CastleUtils.bedPools icinde).
--
-- Role ozel davranis ornegi (yemek pisirme, ileride eklenecek):
--   behaviors = {
--       {
--           id = "cook",
--           interrupt = "nebakovrising_cook",       -- AI/*.xml agac adi + SmartEntity sablonu
--           poll = function(entity, context) return false end,
--       },
--   }
-- ============================================================

nebakovrising = nebakovrising or {}
local Roles = nebakovrising.Roles

Roles.Register({
    id = "servant",
    label = "Hizmetkar",
    namePrefix = "nebakovrising_Servant_",
    command = "nebakovrising_spawn_servant",
    commandDescription = "Oyuncunun yanina hizmetkar spawn et",
    faction = nebakovrising.Config.guardFaction,
    clothingPreset = "a1b2c3d4-0005-4000-8000-100000000005",
    weaponDrawContext = true,
    bedPool = "servant",
    interaction = { label = "hizmetkar", inventory = true, equipTransferred = true },
    behaviors = {},
})
