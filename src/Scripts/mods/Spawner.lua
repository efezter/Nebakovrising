-- ============================================================
-- Scripts/mods/Spawner.lua   (YAN SCRIPT 2)
-- NPC spawn ornegi. Utils ve Main'e nebakovrising.* uzerinden erisir.
-- ============================================================

nebakovrising = nebakovrising or {}
nebakovrising.Spawner = nebakovrising.Spawner or {}
local Spawner = nebakovrising.Spawner

Spawner._names   = Spawner._names or {}
Spawner._counter = Spawner._counter or 0

function Spawner.GetSpawnedCount() return #Spawner._names end
function Spawner.GetSpawnedNames() return Spawner._names end

local function scheduleEntityCallback(delay, callbackName, entityName, retriesLeft)
    if not Script or type(Script.SetTimerForFunction) ~= "function" then
        nebakovrising.Utils.Log("Gecikmeli NPC callback'i zamanlanamadi: Script.SetTimerForFunction API'si yok.")
        return false
    end

    local userData = {
        entityName = entityName,
        retriesLeft = retriesLeft,
    }
    local ok, timerId = pcall(
        Script.SetTimerForFunction,
        delay,
        callbackName,
        userData
    )
    if not ok then
        nebakovrising.Utils.Log("Gecikmeli NPC callback'i zamanlanamadi: "
            .. tostring(callbackName) .. ", sonuc=" .. tostring(timerId))
        return false
    end
    return true
end

local function readTimerUserData(userData, callbackName)
    if type(userData) ~= "table"
        or type(userData.entityName) ~= "string"
        or type(userData.retriesLeft) ~= "number" then
        nebakovrising.Utils.Log("Gecikmeli NPC callback'ine gecersiz veri verildi: "
            .. tostring(callbackName))
        return nil
    end
    return userData.entityName, userData.retriesLeft
end

local function readFactionState(entity)
    local actualFaction
    if type(AI.GetFactionOf) == "function" then
        local getFactionOk, faction = pcall(AI.GetFactionOf, entity.id)
        if getFactionOk then
            actualFaction = faction
        end
    end

    local player = nebakovrising.Utils.GetPlayer()
    local playerFaction
    local reaction
    if player and type(AI.GetFactionOf) == "function" then
        local playerFactionOk, faction = pcall(AI.GetFactionOf, player.id)
        if playerFactionOk then
            playerFaction = faction
        end
    end
    if player and type(AI.GetReactionOf) == "function" then
        local reactionOk, value = pcall(AI.GetReactionOf, entity.id, player.id)
        if reactionOk then
            reaction = value
        end
    end

    return actualFaction, playerFaction, reaction
end

local guardPresetItemIds = {
    "4c7218e8-78c2-49cf-b88a-06f567c24e5a",
    "ffe35c10-6a19-42f3-9960-1c4801fd1fbf",
    "7ae64aa3-444f-4f10-b05d-4a943c965551",
}

local function verifyGuardPresetItems(entity)
    if not entity.inventory or type(entity.inventory.FindItem) ~= "function" then
        nebakovrising.Utils.Log("Muhafiz preset esyalari dogrulanamadi: "
            .. "Inventory.FindItem API'si yok.")
        return
    end

    for _, itemClassId in ipairs(guardPresetItemIds) do
        local ok, itemId = pcall(function()
            return entity.inventory:FindItem(itemClassId)
        end)
        if not ok then
            nebakovrising.Utils.Log("Muhafiz preset esyasi sorgulanamadi: "
                .. tostring(itemClassId) .. ", hata=" .. tostring(itemId))
        else
            nebakovrising.Utils.Log("Muhafiz preset esyasi dogrulamasi: class="
                .. tostring(itemClassId) .. ", item=" .. tostring(itemId))
        end
    end
end

local function applyGuardClothingPreset(entity)
    if not entity or not entity.actor then
        nebakovrising.Utils.Log("Muhafiz kiyafet preset'i uygulanamadi: actor bulunamadi.")
        return false
    end

    local preset = nebakovrising.Config.defaultGuardClothingPreset
    if type(preset) ~= "string" or preset == "" then
        nebakovrising.Utils.Log("Muhafiz kiyafet preset'i uygulanamadi: preset GUID bos.")
        return false
    end
    if type(entity.actor.EquipClothingPreset) ~= "function" then
        nebakovrising.Utils.Log("Muhafiz kiyafet preset'i uygulanamadi: "
            .. "Actor.EquipClothingPreset API'si yok.")
        return false
    end

    pcall(function()
        if entity.actor.Undress then
            entity.actor:Undress()
        end
    end)

    local ok, result = pcall(function()
        entity.actor:EquipClothingPreset(preset)
    end)
    if not ok then
        nebakovrising.Utils.Log("Muhafiz kiyafet preset cagrisi hata verdi: "
            .. "entity=" .. tostring(entity.id) .. ", preset=" .. preset
            .. ", sonuc=" .. tostring(result))
        return false
    end

    entity._nebakovBaseClothingPreset = preset
    nebakovrising.Utils.Log("Muhafiz kiyafet preset cagrisi tamamlandi: "
        .. "entity=" .. tostring(entity.id) .. ", preset=" .. preset)
    verifyGuardPresetItems(entity)
    return true
end

local function applyGuardWeaponItem(entity)
    if not entity or not entity.actor then
        nebakovrising.Utils.Log("Muhafiz varsayilan silahi uygulanamadi: actor bulunamadi.")
        return false
    end
    local inventory = entity.inventory
    if not inventory or type(inventory.GetInventoryTable) ~= "function"
        or type(inventory.FindItem) ~= "function"
        or type(inventory.CreateItem) ~= "function"
        or type(inventory.DeleteItemOfClass) ~= "function" then
        nebakovrising.Utils.Log("Muhafiz varsayilan silahi uygulanamadi: envanter API'leri kullanilamiyor.")
        return false
    end
    if not ItemManager or type(ItemManager.GetItem) ~= "function" then
        nebakovrising.Utils.Log("Muhafiz varsayilan silahi uygulanamadi: ItemManager.GetItem API'si kullanilamiyor.")
        return false
    end
    if type(entity.actor.EquipInventoryItem) ~= "function"
        or type(entity.actor.UnequipInventoryItem) ~= "function" then
        nebakovrising.Utils.Log("Muhafiz varsayilan silahi uygulanamadi: Actor ekipman API'leri kullanilamiyor.")
        return false
    end
    local equipmentData = nebakovrising.EquipmentData
    if not equipmentData or type(equipmentData.weaponClasses) ~= "table" then
        nebakovrising.Utils.Log("Muhafiz varsayilan silahi uygulanamadi: silah sinifi indeksi kullanilamiyor.")
        return false
    end

    local itemClassId = nebakovrising.Config.defaultGuardWeaponClassId
    if type(itemClassId) ~= "string" or itemClassId == "" then
        nebakovrising.Utils.Log("Muhafiz varsayilan silahi uygulanamadi: item class ID bos.")
        return false
    end

    local itemClassKey = string.lower(string.gsub(itemClassId, "%-", ""))
    local ok, inventoryItems = pcall(inventory.GetInventoryTable, inventory)
    if not ok or type(inventoryItems) ~= "table" then
        nebakovrising.Utils.Log("Muhafiz varsayilan silahi uygulanamadi: envanter okunamadi: "
            .. tostring(inventoryItems))
        return false
    end
    local otherWeaponClasses = {}
    for _, itemId in pairs(inventoryItems) do
        local itemOk, item = pcall(ItemManager.GetItem, itemId)
        if itemOk and type(item) == "table" and type(item.class) == "string" then
            local classKey = string.lower(string.gsub(item.class, "%-", ""))
            if equipmentData.weaponClasses[classKey]
                and classKey ~= itemClassKey then
                otherWeaponClasses[item.class] = true
                local unequipOk, unequipResult = pcall(
                    entity.actor.UnequipInventoryItem,
                    entity.actor,
                    itemId
                )
                if not unequipOk or unequipResult == false then
                    nebakovrising.Utils.Log("Eski muhafiz silahi unequip cagrisi basarisiz; envanterden kaldirma denenecek: class="
                        .. tostring(item.class) .. ", item=" .. tostring(itemId)
                        .. ", sonuc=" .. tostring(unequipResult))
                end
            end
        end
    end

    for className in pairs(otherWeaponClasses) do
        local removeOk, removeResult = pcall(
            inventory.DeleteItemOfClass,
            inventory,
            className,
            99
        )
        if not removeOk or removeResult == false then
            nebakovrising.Utils.Log("Eski muhafiz silahi envanterden silinemedi: class="
                .. tostring(className) .. ", sonuc=" .. tostring(removeResult))
            return false
        end
    end

    local findOk, itemId = pcall(inventory.FindItem, inventory, itemClassId)
    if not findOk then
        nebakovrising.Utils.Log("Muhafiz varsayilan silahi aranirken hata olustu: "
            .. tostring(itemId))
        return false
    end
    if not itemId then
        local createOk, createResult = pcall(
            inventory.CreateItem,
            inventory,
            itemClassId,
            1,
            1
        )
        if not createOk or createResult == false then
            nebakovrising.Utils.Log("Muhafiz varsayilan silahi envantere eklenemedi: class="
                .. itemClassId .. ", sonuc=" .. tostring(createResult))
            return false
        end
        findOk, itemId = pcall(inventory.FindItem, inventory, itemClassId)
    end
    if not findOk or not itemId then
        nebakovrising.Utils.Log("Muhafiz varsayilan silahi envanterde dogrulanamadi: class="
            .. itemClassId .. ", sonuc=" .. tostring(itemId))
        return false
    end

    local equipOk, equipResult = pcall(
        entity.actor.EquipInventoryItem,
        entity.actor,
        itemId
    )
    if not equipOk or equipResult == false then
        nebakovrising.Utils.Log("Muhafiz varsayilan silahi kusanilamadi: class="
            .. itemClassId .. ", item=" .. tostring(itemId)
            .. ", sonuc=" .. tostring(equipResult))
        return false
    end

    nebakovrising.Utils.Log("Muhafiz varsayilan silahi olusturuldu ve kusanildi: "
        .. "entity=" .. tostring(entity.id) .. ", class=" .. itemClassId
        .. ", item=" .. tostring(itemId))
    return true
end

local function logFactionState(entity, requestedFaction)
    local actualFaction, playerFaction, reaction = readFactionState(entity)
    nebakovrising.Utils.Log("NPC faction requested=" .. tostring(requestedFaction)
        .. ", actual=" .. tostring(actualFaction)
        .. ", playerFaction=" .. tostring(playerFaction)
        .. ", reaction=" .. tostring(reaction))
    return actualFaction
end

function Spawner.ApplyGuardWeaponDrawContext(entityName, retriesLeft)
    retriesLeft = retriesLeft or 0
    local entity = System.GetEntityByName(entityName)
    if entity and entity.soul then
        local soul = entity.soul
        if type(soul.HasScriptContext) == "function" then
            local checkOk, hasContext = pcall(soul.HasScriptContext, soul, "crime_ignorePlayersDrawnWeapon")
            if checkOk and hasContext then
                entity._nebakovWeaponDrawContextApplied = true
                return
            end
        end

        if type(soul.SetScriptContext) == "function" then
            local setOk, setResult = pcall(soul.SetScriptContext, soul, "crime_ignorePlayersDrawnWeapon", true)
            if setOk and type(soul.HasScriptContext) == "function" then
                local checkOk, hasContext = pcall(soul.HasScriptContext, soul, "crime_ignorePlayersDrawnWeapon")
                if checkOk and hasContext then
                    entity._nebakovWeaponDrawContextApplied = true
                    nebakovrising.Utils.Log("Muhafiz silah-cekme tepki baglami uygulandi: "
                        .. tostring(entityName))
                    return
                end
            elseif not setOk and not entity._nebakovWeaponDrawContextWarned then
                entity._nebakovWeaponDrawContextWarned = true
                nebakovrising.Utils.Log("Muhafiz silah-cekme tepki baglami ayarlanamadi: "
                    .. tostring(setResult))
            end
        elseif not entity._nebakovWeaponDrawContextWarned then
            entity._nebakovWeaponDrawContextWarned = true
            nebakovrising.Utils.Log("Muhafiz silah-cekme tepki baglami ayarlanamadi: "
                .. "Soul.SetScriptContext API'si yok.")
        end
    end

    if retriesLeft > 0 and Script and type(Script.SetTimerForFunction) == "function" then
        scheduleEntityCallback(
            500,
            "nebakovrising.Spawner.RetryGuardWeaponDrawContext",
            entityName,
            retriesLeft - 1
        )
    elseif not entity and retriesLeft <= 0 then
        nebakovrising.Utils.Log("Muhafiz silah-cekme tepki baglami ayarlanamadi: entity bulunamadi: "
            .. tostring(entityName))
    elseif entity and not entity._nebakovWeaponDrawContextApplied
        and not entity._nebakovWeaponDrawContextWarned then
        entity._nebakovWeaponDrawContextWarned = true
        nebakovrising.Utils.Log("Muhafiz silah-cekme tepki baglami dogrulanamadi: "
            .. tostring(entityName))
    end
end

function Spawner.RetryGuardWeaponDrawContext(userData)
    local entityName, retriesLeft = readTimerUserData(
        userData,
        "RetryGuardWeaponDrawContext"
    )
    if entityName then
        Spawner.ApplyGuardWeaponDrawContext(entityName, retriesLeft)
    end
end

function Spawner.ApplyGuardClothingPreset(entityName, retriesLeft, enforceLater)
    retriesLeft = retriesLeft or 0
    local entity
    if System and type(System.GetEntity) == "function" then
        entity = System.GetEntity(entityName)
    end
    if not entity and System and type(System.GetEntityByName) == "function" then
        entity = System.GetEntityByName(entityName)
    end
    if entity then
        local castleUtils = nebakovrising.CastleUtils
        if castleUtils and castleUtils.IsNpcEquipmentPreserved
            and castleUtils.IsNpcEquipmentPreserved(entityName) then
            nebakovrising.Utils.Log("NPC oyuncu ekipmani korundugu icin varsayilan ekipman preset'i uygulanmadi: "
                .. tostring(entityName))
            return true
        end

        local applied = applyGuardClothingPreset(entity)
        if applied then
            applyGuardWeaponItem(entity)
        end

        if applied and enforceLater ~= false
            and not entity._nebakovFinalClothingEnforcementScheduled then
            entity._nebakovFinalClothingEnforcementScheduled = true
            if not scheduleEntityCallback(
                3000,
                "nebakovrising.Spawner.ReapplyGuardClothingPreset",
                entityName,
                0
            ) then
                entity._nebakovFinalClothingEnforcementScheduled = nil
            end
        end
        if not applied and retriesLeft > 0 then
            scheduleEntityCallback(
                1000,
                "nebakovrising.Spawner.RetryGuardClothingPreset",
                entityName,
                retriesLeft - 1
            )
        end
        return applied
    end

    if retriesLeft > 0 and Script and type(Script.SetTimerForFunction) == "function" then
        scheduleEntityCallback(
            500,
            "nebakovrising.Spawner.RetryGuardClothingPreset",
            entityName,
            retriesLeft - 1
        )
    elseif not entity and retriesLeft <= 0 then
        nebakovrising.Utils.Log("Muhafiz varsayilan kiyafet preset'i uygulanamadi: entity bulunamadi: "
            .. tostring(entityName))
    end
end

function Spawner.ReapplyGuardClothingPreset(userData)
    local entityName = type(userData) == "table" and userData.entityName or nil
    if type(entityName) ~= "string" then
        nebakovrising.Utils.Log("Gecikmeli kiyafet preset'i tekrar uygulamasi gecersiz veri aldi.")
        return
    end
    Spawner.ApplyGuardClothingPreset(entityName, 0, false)
end

function Spawner.RetryGuardClothingPreset(userData)
    local entityName, retriesLeft = readTimerUserData(
        userData,
        "RetryGuardClothingPreset"
    )
    if entityName then
        Spawner.ApplyGuardClothingPreset(entityName, retriesLeft)
    end
end

function Spawner.ScheduleGuardClothingPreset(entityName, retriesLeft)
    local scheduled = scheduleEntityCallback(
        1000,
        "nebakovrising.Spawner.ApplyGuardClothingPresetDeferred",
        entityName,
        retriesLeft or 0
    )
    if not scheduled then
        nebakovrising.Utils.Log("Muhafiz kiyafet preset'i geciktirilemedi; varsayilan preset korunuyor: "
            .. tostring(entityName))
    end
    return scheduled
end

function Spawner.ApplyGuardClothingPresetDeferred(userData)
    local entityName, retriesLeft = readTimerUserData(
        userData,
        "ApplyGuardClothingPresetDeferred"
    )
    if entityName then
        Spawner.ApplyGuardClothingPreset(entityName, retriesLeft)
    end
end

function Spawner.ApplyGuardFaction(entityName, retriesLeft)
    retriesLeft = retriesLeft or 0
    local guardFaction = nebakovrising.Config.guardFaction
    if not guardFaction or not AI or type(AI.SetFactionOf) ~= "function" then
        nebakovrising.Utils.Log("NPC faction'i ayarlanamadi: AI.SetFactionOf API'si kullanilamiyor.")
        return
    end

    local entity = System.GetEntityByName(entityName)
    if not entity then
        if retriesLeft > 0 and Script and type(Script.SetTimerForFunction) == "function" then
            scheduleEntityCallback(
                500,
                "nebakovrising.Spawner.RetryGuardFaction",
                entityName,
                retriesLeft - 1
            )
        else
            nebakovrising.Utils.Log("NPC faction'i ayarlanamadi: entity bulunamadi: " .. tostring(entityName))
        end
        return
    end

    local setOk, setResult = pcall(AI.SetFactionOf, entity.id, guardFaction)
    local actualFaction = readFactionState(entity)
    if actualFaction == guardFaction then
        logFactionState(entity, guardFaction)
        return
    end
    if retriesLeft > 0 and Script and type(Script.SetTimerForFunction) == "function" then
        scheduleEntityCallback(
            500,
            "nebakovrising.Spawner.RetryGuardFaction",
            entityName,
            retriesLeft - 1
        )
    else
        nebakovrising.Utils.Log("NPC faction'i dogrulanamadi: " .. tostring(entityName)
            .. ", actual=" .. tostring(actualFaction)
            .. ", set-error=" .. tostring(setOk and "" or setResult))
        logFactionState(entity, guardFaction)
    end
end

function Spawner.RetryGuardFaction(userData)
    local entityName, retriesLeft = readTimerUserData(userData, "RetryGuardFaction")
    if entityName then
        Spawner.ApplyGuardFaction(entityName, retriesLeft)
    end
end

function Spawner.SpawnNpc(name, pos, dir, props)
    local spawnProperties = {}
    for key, value in pairs(nebakovrising.Config.npcDefaults or {}) do
        spawnProperties[key] = value
    end
    for key, value in pairs(props or {}) do
        spawnProperties[key] = value
    end
    spawnProperties.bSaved_by_game = 1
    spawnProperties.bSerialize = 1

    local ok, result = pcall(function()
        return System.SpawnEntity({
            class       = "NPC",
            name        = name,
            position    = pos,
            orientation = dir or { x = 0, y = 1, z = 0 },
            properties  = spawnProperties,
        })
    end)

    if not ok or not result then
        nebakovrising.Utils.Log("Spawn HATASI: " .. tostring(result))
        return nil
    end
    Spawner.ApplyGuardWeaponDrawContext(name, 12)
    Spawner.ApplyGuardWeaponDrawContext(name, 12)
    Spawner.ScheduleGuardClothingPreset(name, 12)
    if nebakovrising.Config.guardFaction then
        if not scheduleEntityCallback(
                500,
                "nebakovrising.Spawner.RetryGuardFaction",
                name,
                12
            ) then
            nebakovrising.Utils.Log("NPC faction'i geciktirilemedi: " .. tostring(name))
        end
    end

    if NpcInteraction and NpcInteraction.Inject then
        local injectOk, injected = pcall(NpcInteraction.Inject, result)
        if not injectOk or not injected then
            nebakovrising.Utils.Log("NPC etkilesimi eklenemedi: " .. tostring(injected))
        end
    end

    table.insert(Spawner._names, name)
    nebakovrising.Main.OnEntitySpawned(result, name)   -- ana scripte bildir

    local spawnedEntity = result
    if System and type(System.GetEntity) == "function" then
        spawnedEntity = System.GetEntity(result.id) or result
    end
    applyGuardClothingPreset(spawnedEntity)

    return result
end

function Spawner.SpawnTestNpc()
    local pos = nebakovrising.Utils.GetPlayerPos()
    if not pos then
        nebakovrising.Utils.Log("Oyuncu bulunamadi, once bir save yukle.")
        return
    end
    local name
    repeat
        Spawner._counter = Spawner._counter + 1
        name = "nebakovrising_TestNpc_" .. Spawner._counter
    until not System.GetEntityIdByName(name)
    Spawner.SpawnNpc(name, { x = pos.x + 2, y = pos.y, z = pos.z })
end
