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
        eveningMeal = true,
        interaction = { label = "muhafiz", inventory = true, equipTransferred = true },
        behaviors = {},
    }
    for key, value in pairs(overrides) do
        role[key] = value
    end
    return role
end

-- Patrol noktalari. fixed: kritik sabit noktalar (guard sayisi >= sabit nokta sayisi ise
-- sabit noktadaki guard kalici durur). roaming: agirlikli gruplar; yalniz fazla guardlar gezer.
local function point(name) return "smartObject[" .. name .. "]" end

local meleePatrol = {
    waitMin = 30,
    waitMax = 180,
    fixed = {
        point("profession/guard/guardPoint_normal27_5ba34321-f9c2-45d3-a881-bd6e32b0cd32"),
    },
    roaming = {
        {
            weight = 70,
            points = {
                point("profession/guard/guardPoint_normal1_f78b98b5-d9a5-4d1c-8e7b-24e6f3697d91"),
                point("Bench/bench_1place_low11_e16ab7d7-fe58-452a-bb1a-daecca10f3df"),
                point("profession/guard/guardPoint_normal17_a853b515-ffce-4b6e-8501-e83662145dba"),
                point("profession/guard/guardPoint_normal9_caccf9a8-fe9e-4162-a7cd-f13b8bfa2b15"),
                point("Idle/leaningSpot_back24_dc89954d-d964-450c-ad97-137a14bb62a4"),
            },
        },
        {
            weight = 30,
            points = {
                point("guardingMiddlePalisade_3_c4e1c46d-17c5-4846-bef0-0f3734953ae7"),
                point("guardingMiddlePalisade_2_afda14e5-8e90-4e71-b733-8e98c591805a"),
                point("guardingMiddlePalisade_4_14d35319-cf40-4908-b41a-292f9b816712"),
                point("guardingMiddlePalisade_1_c7c53f34-711d-4d61-ad3b-de9129b83472"),
                point("Bench/bench_1place_low23_aa9fa503-57bb-4f11-83e3-4f0941d4c675"),
                point("profession/guard/guardPoint_normal10_57170271-9c07-4e91-bbcf-12bcca5c7dae"),
                point("profession/guard/guardPoint_lowerTower_normal23_adda19b1-7eba-4b88-9ad0-b897b46b5fe2"),
                point("profession/guard/guardPoint_normal_lowerTower_24_85337871-b4b9-435d-996e-65fbde4790d9"),
                point("profession/guard/guardPoint_normal3_9099218d-e22b-4767-a64c-423235f1240a"),
                point("Idle/leaningSpot_back6_a8610e34-a08e-4456-b4ed-d3d8906a7ae6"),
                point("watchingUpperPalisade_1_e8e90a9c-d299-4e47-bed3-78a01a0643f4"),
                point("guardingJail_61004308-937e-495b-8765-1f93285a865c"),
                point("Bench/bench_2places_low44_10a4df56-b806-47ac-af05-4abcb87c94ea"),
            },
        },
    },
}

local rangedPatrol = {
    waitMin = 10,
    waitMax = 20,
    crossbow = true,
    fixed = {
        point("profession/guard/guardPoint_normal19_dbd8a54b-72fd-43a7-ae51-27a7c7dcb92e"),
    },
    roaming = {
        {
            weight = 1,
            points = {
                point("watchingUpperPalisade_3_e5afb938-3210-4c0e-b7fc-2756e470e424"),
                point("watchingPalace_1_3be6e95d-4075-4561-8fae-116031b7564c"),
                point("watchingUpperPalisade_4_b6c5521d-a9c5-4775-8c23-7e09f5165508"),
            },
        },
    },
}

Roles.Register(guardRole({
    id = "guard_melee",
    patrol = meleePatrol,
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
    patrol = rangedPatrol,
    label = "Ranged muhafiz",
    namePrefix = "nebakovrising_RangedGuard_",
    command = "nebakovrising_spawn_ranged_guard",
    commandDescription = "Oyuncunun yanina ranged muhafiz (arbalet) spawn et",
    -- vanilla preset: nebakovObrana_battle_crossbow (arbalet + ok + kisa kilic)
    weaponPreset = "05a2e19b-2e8c-43c8-b1af-a10f8e948725",
}))
