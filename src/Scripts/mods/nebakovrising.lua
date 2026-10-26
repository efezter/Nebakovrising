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
    -- Legacy fallback; guard shift hours are configured in Config/routines.lua.
    npcSleepStartHour = 0,
    npcWakeHour = 8,
    -- Uyanma siralamasi: NPC'ler arasi rastgele gecikme (saniye).
    wakeStaggerMin = 5,
    wakeStaggerMax = 15,
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
    -- Milestone 1: outbound position telemetry only; generation/playback stay external.
    voiceBridge = { sampleIntervalMs = 250 },
    conversations = {
        enabled = true, randomEnabled = true, searchRadius = 20, playerExitRadius = 30,
        patrolStartHour = 8, patrolEndHour = 20,
        prepareBeforeMeeting = true, runtimeConfigRequired = true,
        profileId = "patrol-daily-talk",
        -- Gate position observed in live telemetry; adjustable castle region.
        regionCenter = { x = 1895, y = 1213, z = 52 },
        regionRadius = 250, regionExitRadius = 280, regionHeight = 80,
        randomMinSeconds = 120, randomMaxSeconds = 240,
        cooldownSeconds = 0, npcCooldownSeconds = 0,
        -- Move braking may stop short of the 1.3m target; accept a 2m meeting.
        approachDistance = 1.3, arrivalDistance = 2,
        faceTimeout = 8,
        arrivalSettleSeconds = 2,
        preparationTimeout = 30, approachTimeout = 35, conversationTimeout = 150,
        generationTimeout = 240,
        peerTimeout = 12, patrolHeartbeatMaxAge = 2.5,
        face = {enabled=true, clip="fa_cin_talk_neutral_01", layer=12},
    },
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
    Script.ReloadScript("Scripts/mods/nebakov_routine_config.lua")
    nebakovrising.Routines.Load()
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
    Script.ReloadScript("Scripts/mods/nebakov_shifts.lua")
    Script.ReloadScript("Scripts/mods/nebakov_subtitles.lua")
    Script.ReloadScript("Scripts/mods/nebakov_dice.lua")
    Script.ReloadScript("Scripts/mods/NpcNamesData.lua")
    Script.ReloadScript("Scripts/mods/nebakov_npc_names.lua")
    Script.ReloadScript("Scripts/mods/nebakov_voice_bridge.lua")
    Script.ReloadScript("Scripts/mods/nebakov_conversation_config.lua")
    Script.ReloadScript("Scripts/mods/nebakov_voice_registry.lua")
    Script.ReloadScript("Scripts/mods/nebakov_voice_face.lua")
    Script.ReloadScript("Scripts/mods/nebakov_conversations.lua")
end

-- Konsol komutlari: oyun icinde ~ ile ac, ornegin:  nebakovrising_status
-- Spawn komutlari rol tanimlarindan uretilir (Scripts/mods/roles/*.lua).
function Main.RegisterCommands()
    if nebakovrising._cmdsRegistered then return end
    nebakovrising._cmdsRegistered = true
    System.AddCCommand("nebakovrising_status", "nebakovrising.Main.Status()", "nebakovrising durumunu yazdir")
    System.AddCCommand("nebakovrising_patrol_status", "nebakovrising.CastleUtils.LogPatrolStatus()", "Guard patrol atama durumunu yazdir")
    System.AddCCommand("nebakovrising_shift_status", "nebakovrising.Shifts.LogStatus()", "Muhafiz vardiyalarini ve saatlerini yazdir")
    System.AddCCommand("nebakov_subtitle_test", "nebakovrising.Subtitles.Test()", "Muhafizin ustunde 8 saniye yazi goster")
    System.AddCCommand("nebakov_dice_status", "nebakovrising.Dice.Status()", "Ilk yemek sonrasi zar ciftinin durumunu yazdir")
    System.AddCCommand("nebakov_dice_reset", "nebakovrising.Dice.Reset()", "Sonraki yemek sonrasi ilk iki bos muhafiz icin zar testini yeniden kur")
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
    if nebakovrising.Voices then nebakovrising.Voices.Reconcile() end
    local role=nebakovrising.Roles.Resolve(name)
    if role and role.bedPool=="guard" and nebakovrising.Conversations and nebakovrising.Conversations.SetEventContext then
        nebakovrising.Conversations.SetEventContext("garrison_arrival","Another guard has recently joined the castle garrison on duty.",180)
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
