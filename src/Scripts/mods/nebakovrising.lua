-- ============================================================
-- Scripts/mods/nebakovrising.lua   (ANA SCRIPT)
-- Oyun acilirken otomatik calisir (Startup klasoru).
-- Tum scriptler tek bir global tablo uzerinden birbirine erisir:
--   nebakovrising.Config, nebakovrising.Main, nebakovrising.Utils, nebakovrising.Spawner
-- ============================================================

nebakovrising = nebakovrising or {}
nebakovrising.Version = "0.1.0"

nebakovrising.Config = {
    debug  = true,
    prefix = "[nebakovrising]",
    bedBehaviorEnabled = true,
    npcSleepStartHour = 0,
    npcWakeHour = 8,
    -- Uyanma siralamasi: NPC'ler arasi rastgele gecikme (saniye).
    wakeStaggerMin = 5,
    wakeStaggerMax = 10,
    -- eveningMeal=true rollerde bu saatten uyku saatine kadar aksam yemegi tetiklenir.
    eveningMealHour = 20,
    -- Aksam yemegine giden iki NPC arasindaki rastgele gecikme (saniye).
    eveningMealStaggerMin = 10,
    eveningMealStaggerMax = 30,
    -- System.GetCurrTime ile olculen davranis/koltuk zaman asimlari (saniye).
    activityRequestTimeout = 10,
    activityHeartbeatTimeout = 15,
    activityMoveTimeout = 120,
    stanceTransitionTimeout = 20,
    mealSeatTimeout = 30,
    mealTargetReadyTimeout = 10,
    mealSeatRetryCooldown = 60,
    guardFaction = "trosecko_settlements_tvrzNebakov_soldiers",
    -- Spawner icin varsayilan NPC ayarlari (kendi GUID'lerini doldur)
    npcDefaults = {
        guidSharedSoulId      = "0e118323-c699-4e4f-8bfa-15e1681e154f",
        sWH_AI_EntityCategory = "",
        bWH_PerceptorObject   = true,
        bWH_PerceptibleObject = true,
        bInvulnerable         = false,
    },
}

nebakovrising.Main = nebakovrising.Main or {}
local Main = nebakovrising.Main

-- Yan scriptleri yukle (yol, pak icindeki yoldur)
-- local modules = {
--     "Scripts/mods/Utils.lua",
--     "Scripts/mods/Spawner.lua",
-- }

function Main.LoadModules()
    Script.ReloadScript("Scripts/mods/Utils.lua")
    Script.ReloadScript("Scripts/mods/EquipmentData.lua")
    Script.ReloadScript("Scripts/mods/Roles.lua")
    Script.ReloadScript("Scripts/mods/AppearancePools.lua")
    Script.ReloadScript("Scripts/mods/roles/Guard.lua")
    Script.ReloadScript("Scripts/mods/roles/Quartermaster.lua")
    Script.ReloadScript("Scripts/mods/roles/Servant.lua")
    Script.ReloadScript("Scripts/mods/roles/Blacksmith.lua")
    Script.ReloadScript("Scripts/mods/NpcInteraction.lua")
    Script.ReloadScript("Scripts/mods/Spawner.lua")
    Script.ReloadScript("Scripts/mods/CastleUtils.lua")
end

-- Konsol komutlari: oyun icinde ~ ile ac, ornegin:  nebakovrising_status
-- Spawn komutlari rol tanimlarindan uretilir (Scripts/mods/roles/*.lua).
function Main.RegisterCommands()
    if nebakovrising._cmdsRegistered then return end
    nebakovrising._cmdsRegistered = true
    System.AddCCommand("nebakovrising_status", "nebakovrising.Main.Status()", "nebakovrising durumunu yazdir")
    System.AddCCommand("nebakovrising_patrol_status", "nebakovrising.CastleUtils.LogPatrolStatus()", "Guard patrol atama durumunu yazdir")
    for _, role in ipairs(nebakovrising.Roles.List()) do
        if role.command then
            System.AddCCommand(
                role.command,
                "nebakovrising.Spawner.SpawnRole('" .. role.id .. "')",
                role.commandDescription or ("Oyuncunun yanina " .. role.id .. " spawn et")
            )
        end
    end
    System.AddCCommand("nebakovrising_clear_npcs", "nebakovrising.CastleUtils.ClearManagedNpcs()", "Yonetilen NPC'leri ve kayitlarini sil")
end

-- Yan scriptlerin ana scripte geri bildirim yapabilecegini gosteren callback
function Main.OnEntitySpawned(entity, name)
    local assignedBed
    local bedSelector
    if nebakovrising.CastleUtils and nebakovrising.CastleUtils.AssignBedToNpc then
        assignedBed, bedSelector = nebakovrising.CastleUtils.AssignBedToNpc(entity)
        if nebakovrising.CastleUtils.SaveManagedNpc then
            nebakovrising.CastleUtils.SaveManagedNpc(name, bedSelector, false)
        end
        if assignedBed and nebakovrising.CastleUtils.TrackBedOwner then
            nebakovrising.CastleUtils.TrackBedOwner(entity, name)
        end
        if assignedBed and not nebakovrising.CastleUtils.BindBedAssignmentToWuid(entity) then
            Script.SetTimerForFunction(
                500,
                "nebakovrising.CastleUtils.RetryBedAssignmentBinding",
                name,
                12
            )
        end
        if not assignedBed and nebakovrising.CastleUtils.TrackUnassignedNpc then
            nebakovrising.CastleUtils.TrackUnassignedNpc(entity, name)
        end
    elseif nebakovrising.CastleUtils and nebakovrising.CastleUtils.SaveManagedNpc then
        nebakovrising.CastleUtils.SaveManagedNpc(name, nil, false)
    end
    nebakovrising.Utils.Log("Spawn edildi: " .. tostring(name) .. " (toplam: " .. nebakovrising.Spawner.GetSpawnedCount() .. ")")
    local bedName
    if assignedBed and assignedBed.GetName then
        local nameOk, result = pcall(assignedBed.GetName, assignedBed)
        if nameOk then
            bedName = result
        end
    end
    nebakovrising.Utils.Log("Atanan yatak: " .. tostring(bedName or bedSelector or "yok"))
end

function Main.Status()
    nebakovrising.Utils.Log("v" .. nebakovrising.Version .. " calisiyor.")
    if nebakovrising.CastleUtils
        and nebakovrising.CastleUtils.LogPersistentNpcState then
        nebakovrising.CastleUtils.LogPersistentNpcState()
    end
    local managedNpcCount = 0
    for _, npc in pairs(System.GetEntitiesByClass("NPC") or {}) do
        local name
        if npc and npc.GetName then
            local ok, result = pcall(npc.GetName, npc)
            if ok then name = result end
        end
        if name and string.sub(name, 1, 14) == "nebakovrising_" then
            managedNpcCount = managedNpcCount + 1
            local position
            if npc.GetWorldPos then
                local positionOk, positionResult = pcall(npc.GetWorldPos, npc)
                if positionOk then position = positionResult end
            end
            nebakovrising.Utils.Log("Yonetilen NPC: " .. tostring(name)
                .. ", entityId=" .. tostring(npc.id)
                .. ", saved=" .. tostring(npc.bSaved_by_game)
                .. ", serialize=" .. tostring(npc.bSerialize)
                .. ", position=" .. tostring(position))
        end
    end
    nebakovrising.Utils.Log("Yuklu yonetilen NPC sayisi: " .. tostring(managedNpcCount))
end

-- Oyun/dunya yuklendikten sonra calistirmak istedigin kod buraya.
-- NOT: Startup scriptleri oyun acilisinda calisir, o an 'player' henuz yoktur.
-- Bu fonksiyonu dunya yuklenince tetikleyen bir hook bagla (README'ye bak).
function Main.OnGameStart()
    nebakovrising.Utils.Log("OnGameStart cagrildi")
end

function Main.Init()
    Main.LoadModules()
    if not nebakovrising.Utils or type(nebakovrising.Utils.Log) ~= "function" then
        System.LogAlways((nebakovrising.Config.prefix or "[nebakovrising]") ..
            " Baslatilamadi: Utils.lua yuklenemedi.")
        return
    end
    Main.RegisterCommands()
    if System and type(System.ExecuteCommand) == "function" then
        local ok, result = pcall(System.ExecuteCommand, "wh_sys_NoSavePotion = 1")
        if not ok then
            nebakovrising.Utils.Log("Kayit iksiri konsol komutu calistirilamadi: " .. tostring(result))
        else
            nebakovrising.Utils.Log("Kayit iksiri etkin: wh_sys_NoSavePotion = 1")
        end
    else
        nebakovrising.Utils.Log("Kayit iksiri etkinlestirilemedi: System.ExecuteCommand API'si yok.")
    end
    nebakovrising.Utils.Log("Yuklendi. Konsolda 'nebakovrising_status' dene.")
end

Main.Init()
