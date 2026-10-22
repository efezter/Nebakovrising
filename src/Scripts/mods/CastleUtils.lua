-- ============================================================
-- Scripts/mods/CastleUtils.lua
-- Nebakov kalesine ozel oyun ici yardimcilar.
-- Diger scriptler nebakovrising.CastleUtils.* uzerinden erisir.
-- ============================================================

nebakovrising = nebakovrising or {}
nebakovrising.CastleUtils = nebakovrising.CastleUtils or {}
local CastleUtils = nebakovrising.CastleUtils

CastleUtils.noLockEnts = CastleUtils.noLockEnts or {
    ["AnimDoor[structures/defensive/castles/unique/nebakov/nebakov_castle1:Door.door_village_right5[structures/defensive/castles/unique/nebakov/nebakov_castle1]_69d90da4-9b3b-0057-10b4-cb380f79543c]"] = true,
    ["AnimDoor[structures/defensive/castles/unique/nebakov/nebakov_castle1:Door.door_village_right7[structures/defensive/castles/unique/nebakov/nebakov_castle1]_5e601c42-b5da-0869-0664-0aa7ec4286f4]"] = true,
    ["AnimDoor[structures/defensive/watchtowers/unique/nebakov/watchtower1:Door/door_village_left13[structures/defensive/watchtowers/unique/nebakov/watchtower1]_ef07a548-57de-0841-1325-3200ece3554e]"] = true,
    ["AnimDoor[structures/industrial/smitheries/unique/nebakov/smithery1:Door/door_village_left36[structures/industrial/smitheries/unique/nebakov/smithery1]_30e2b0c2-f988-0366-3aa2-f8b830d59dd3]"] = true,
    ["AnimDoor[structures/living/houses/unique/nebakov/kitchen1:Door/door_village_right6[structures/living/houses/unique/nebakov/kitchen1]_6eaee056-9b18-48b3-8dfa-f975e9fd5888]"] = true,
    ["AnimDoor[structures/living/houses/unique/nebakov/kitchen1:Door.door_village_left12[structures/living/houses/unique/nebakov/kitchen1]_f75bd1f2-e549-08e7-104e-9515e5a86b9a]"] = true,
    ["AnimDoor[structures/living/houses/unique/nebakov/kitchen1:Door/door_village_left15[structures/living/houses/unique/nebakov/kitchen1]_5bd08fd6-2004-0fa4-1c5c-5bc660a5223e]"] = true,
    ["AnimDoor[Door/door_village_right5_8b891ceb-7882-4d28-b9bb-9564bf37535a]"] = true,
    ["AnimDoor[Door/door_village_right7_bd35e91f-6b99-4f73-be04-b6a9ec9a9879]"] = true,
    ["AnimDoor[Door/door_village_right17_b8b4b976-447e-4762-b51c-079120df79c5]"] = true,
    ["stash[Chest.chest1_5293b461-4714-4d8d-a552-5ce6f792a608]"] = true,
    ["stash[Chest.chest3_3c6c2d50-d9f0-485b-99a2-c6e803018ef2]"] = true,
    ["stash[Chest/chest7_ca54451d-a964-40ab-88f5-efe86ce76c03]"] = true,
    ["stash[Chest/chest10_28785e3e-d28d-4614-a3ee-c2927e269a39]"] = true,
    ["stash[Chest/chest11_2fea03b2-5abf-475c-9e6b-abc246ec73cb]"] = true,
    ["stash[Chest/chest12_b6edc5fa-3f5e-441f-986f-6e8fa8d8fa79]"] = true,
    ["stash[Chest/chest16_0767f5da-0831-499b-8152-2b03ecc3c58e]"] = true,
    ["stash[Chest/chest18_dcc05a41-9d9a-4b16-b3f2-315b981463ea]"] = true,
    ["stash[Chest/chest19_9ce5f9a9-ae54-46ed-955f-0fdd68c6546c]"] = true,
    ["stash[Chest/chest27_d626e0cc-5762-4b34-9e56-46b8b9a571c4]"] = true,
    ["stash[Chest/chest40_4649f0aa-24ec-49bd-8190-088569b39154]"] = true,
}

-- Yataklar rol havuzlarina gore ayrilir (Roles tanimindaki bedPool anahtari).
-- Su ana kadar kullanilan tum yataklar muhafiz yataklaridir; diger havuzlara
-- selector eklendikce o roller yatak almaya baslar.
CastleUtils.bedPools = CastleUtils.bedPools or {
    guard = {
        "smartObject[Bed/bed_low4_d9d626c4-dae2-416e-affd-96c3946151e3]",
        "smartObject[Bed/bed_low1_2bbd8cec-55ba-4034-bd0f-1785ff415b2d]",
        "smartObject[Bed/bed_low3_a01e9c19-d086-4728-ac1f-d26398043ba4]",
        "smartObject[Bed/bed_bench1_9d9d9e04-6c8e-46e3-b935-3afd2d105a4f]",
        "SO_LyingHarmed_Wounded2[special/lyingHarmed/lyingHarmed_healing1_200954b7-520b-4849-a8de-c928e4f3ba60]",
    },
    servant = {},
    blacksmith = {},
    quartermaster = {},
}
CastleUtils.bedEntities = CastleUtils.bedEntities or {}
CastleUtils.bedAssignments = CastleUtils.bedAssignments or {}
CastleUtils.bedOwners = CastleUtils.bedOwners or {}
CastleUtils.bedAssignmentsByWuid = CastleUtils.bedAssignmentsByWuid or {}
CastleUtils.mealBenchOwners = CastleUtils.mealBenchOwners or {}
CastleUtils.mealBenchAssignments = CastleUtils.mealBenchAssignments or {}
CastleUtils.mealBenchAttempts = CastleUtils.mealBenchAttempts or {}
CastleUtils.trackedBedOwners = CastleUtils.trackedBedOwners or {}
CastleUtils.trackedBedCandidates = CastleUtils.trackedBedCandidates or {}
CastleUtils.trackedBedCandidatesByWuid = CastleUtils.trackedBedCandidatesByWuid or {}
CastleUtils.deathMonitorWarnings = CastleUtils.deathMonitorWarnings or {}
CastleUtils.bedWalkStates = CastleUtils.bedWalkStates or {}
CastleUtils.restoredNpcNames = CastleUtils.restoredNpcNames or {}
CastleUtils._persistentStoreName = "nebakovrising_SaveStore"
CastleUtils.mealFireplaceSelector = CastleUtils.mealFireplaceSelector
    or "smartObject[Fireplace/fireplace_home11_c9b722b2-f2fa-4345-9f0d-b1038d95e8e7]"
CastleUtils.mealBenchSelectors = CastleUtils.mealBenchSelectors or {
    "smartObject2[Table/table_twoSides7:Bench/bench_2places_low_table2[Table/table_twoSides7]_db6f4e21-0c46-013d-301a-04c435ae7de9]",
    "smartObject[Table/table_twoSides7:Bench/bench_2places_low_table2[Table/table_twoSides7]_db6f4e21-0c46-013d-301a-04c435ae7de9]",
    "smartObject2[Table/table_twoSides7:Bench/bench_2places_low_table3[Table/table_twoSides7]_e5a98391-a268-056f-05cf-87e1e472a98c]",
    "smartObject[Table/table_twoSides7:Bench/bench_2places_low_table3[Table/table_twoSides7]_e5a98391-a268-056f-05cf-87e1e472a98c]",
    "smartObject2[Table/table_oneSide6:Bench/bench_2places_low_table4[Table/table_oneSide6]_c9c6d3f9-a350-0fa7-15a9-b96c3cd4e7d8]",
    "smartObject[Table/table_oneSide6:Bench/bench_2places_low_table4[Table/table_oneSide6]_c9c6d3f9-a350-0fa7-15a9-b96c3cd4e7d8]",
}
CastleUtils.mealBowlClassIds = CastleUtils.mealBowlClassIds or {
    "22910894-1c8e-4567-878a-8afc93ffd98b",
    "25f04aba-b197-426f-b849-be874521a1c0",
    "323bd9fb-3a36-4573-bb04-03dd79f16585",
    "578a6bb7-4eae-4d06-9272-bdf692b249c6",
    "6f6cdb4c-0382-49ab-bb2e-04ae2e254479",
    "b11b000d-c50e-4565-b8ec-1bf0ac518fc9",
}

CastleUtils.removeEnts = CastleUtils.removeEnts or {
    "tneb_homeFortressArea_1",
    "WH_TriggerArea2[structures/industrial/smitheries/unique/nebakov/smithery1_c343c555-50db-4057-909a-320e33f4f712]",
    "WH_TriggerArea4_2[structures/living/houses/unique/nebakov/kitchen1_e53bf46c-5c82-4ec9-9f30-0efe4061180e]",
    "tneb_courtFortressArea_2",
    "SmartArea33[structures/living/houses/unique/nebakov/house_a2_a5f94cee-28fa-41fd-a30c-db50f6cb3e1e]",
}

CastleUtils._targetChestName = CastleUtils._targetChestName or "chest18_dcc05a41-9d9a-4b16-b3f2-315b981463ea"
CastleUtils._triggerItemGuid = CastleUtils._triggerItemGuid or "19c2e221-91b9-439a-9db5-e56d867e1e6b"

local function log(message)
    if nebakovrising.Utils and nebakovrising.Utils.Log then
        nebakovrising.Utils.Log("[CastleUtils] " .. tostring(message))
    elseif System and System.LogAlways then
        System.LogAlways("[nebakovrising] [CastleUtils] " .. tostring(message))
    end
end

local function findPersistentStore()
    for _, entity in pairs(System.GetEntitiesByClass("BasicEntity") or {}) do
        if entity and entity.GetName then
            local ok, name = pcall(entity.GetName, entity)
            if ok and name == CastleUtils._persistentStoreName then
                return entity
            end
        end
    end
    return nil
end

local function getPersistentRecords(createStore)
    local store = findPersistentStore()
    if not store and createStore then
        local ok, result = pcall(function()
            return System.SpawnEntity({
                class = "BasicEntity",
                name = CastleUtils._persistentStoreName,
                position = { x = 0, y = 0, z = -100 },
                properties = {
                    bSaved_by_game = 1,
                    bSerialize = 1,
                    Physics = { bPhysicalize = false, bRigidBody = false },
                },
            })
        end)
        if ok then
            store = result
            if store and type(store.health) ~= "table" then
                store.health = {}
            end
            if store and store.DestroyPhysics then
                pcall(store.DestroyPhysics, store)
            end
            if store then
                log("NPC save store olusturuldu: " .. tostring(store.id))
            else
                log("NPC save store olusturulamadi: SpawnEntity nil dondurdu.")
            end
        else
            log("NPC save store olusturulamadi: " .. tostring(result))
        end
    end

    if not store then return nil end
    if type(store.health) ~= "table" then
        store.health = {}
    end
    if type(store.health.nebakovNpcRecords) ~= "table" then
        if not createStore then return nil end
        store.health.nebakovNpcRecords = {}
    end
    return store.health.nebakovNpcRecords
end

local function readEntityPosition(entity)
    if not entity then return nil end
    local getPosition = entity.GetWorldPos or entity.GetPos
    if type(getPosition) ~= "function" then return nil end
    local ok, position = pcall(getPosition, entity)
    if not ok or type(position) ~= "table"
        or type(position.x) ~= "number"
        or type(position.y) ~= "number"
        or type(position.z) ~= "number" then
        return nil
    end
    return { x = position.x, y = position.y, z = position.z }
end

function CastleUtils.SaveManagedNpc(entityName, bedSelector, preserveEquipment)
    if type(entityName) ~= "string" or entityName == "" then
        log("NPC save kaydi yazilamadi: entity adi gecersiz.")
        return false
    end

    local records = getPersistentRecords(true)
    if not records then
        log("NPC save kaydi yazilamadi: kalici save store kullanilamiyor.")
        return false
    end

    local record = records[entityName] or {}
    if bedSelector then record.bedSelector = bedSelector end
    if not record.role then
        local role = nebakovrising.Roles and nebakovrising.Roles.Resolve(entityName)
        if role then record.role = role.id end
    end
    if preserveEquipment ~= nil then
        record.preserveEquipment = preserveEquipment == true
    end
    local entityId = System.GetEntityIdByName(entityName)
    local entity = entityId and System.GetEntity(entityId)
    local position = readEntityPosition(entity)
    if position then record.position = position end
    record.managed = true
    records[entityName] = record
    log("NPC save kaydi guncellendi: " .. entityName
        .. ", bed=" .. tostring(record.bedSelector)
        .. ", preserveEquipment=" .. tostring(record.preserveEquipment))
    return true
end

function CastleUtils.GetManagedNpcRole(entityName)
    local records = getPersistentRecords(false)
    local record = records and records[entityName]
    return type(record) == "table" and record.role or nil
end

function CastleUtils.SnapshotManagedNpcPositions()
    if CastleUtils._restoreInProgress then
        Script.SetTimerForFunction(
            2000,
            "nebakovrising.CastleUtils.SnapshotManagedNpcPositions"
        )
        return
    end

    local records = getPersistentRecords(false)
    for entityName, record in pairs(records or {}) do
        if type(record) == "table" and record.managed then
            local entityId = System.GetEntityIdByName(entityName)
            local entity = entityId and System.GetEntity(entityId)
            if entity then
                local position = readEntityPosition(entity)
                if position then record.position = position end
            end
        end
    end
    Script.SetTimerForFunction(
        2000,
        "nebakovrising.CastleUtils.SnapshotManagedNpcPositions"
    )
end

function CastleUtils.LogPersistentNpcState()
    local store = findPersistentStore()
    local records = getPersistentRecords(false)
    local recordCount = 0
    for entityName, record in pairs(records or {}) do
        recordCount = recordCount + 1
        log("Save kaydi: " .. tostring(entityName)
            .. ", managed=" .. tostring(type(record) == "table" and record.managed)
            .. ", bed=" .. tostring(type(record) == "table" and record.bedSelector)
            .. ", preserveEquipment="
            .. tostring(type(record) == "table" and record.preserveEquipment)
            .. ", position="
            .. tostring(type(record) == "table" and record.position
                and record.position.x or nil) .. ","
            .. tostring(type(record) == "table" and record.position
                and record.position.y or nil) .. ","
            .. tostring(type(record) == "table" and record.position
                and record.position.z or nil))
    end
    log("Kalici NPC save durumu: store=" .. tostring(store and store.id)
        .. ", kayitSayisi=" .. tostring(recordCount))
end

function CastleUtils.MarkNpcEquipmentModified(npc, receivedItemIds, removedItemIds)
    if not npc then return false end
    local entityName
    if npc.GetName then
        local ok, name = pcall(npc.GetName, npc)
        if ok then entityName = name end
    end
    entityName = entityName and tostring(entityName)
    if not entityName or entityName == "" then return false end

    local records = getPersistentRecords(false)
    local record = records and records[entityName]
    if not record then
        log("Oyuncu ekipman degisikligi save kaydina yazilamadi: NPC kaydi yok: "
            .. tostring(entityName))
        return false
    end
    record.preserveEquipment = true
    record.playerEquipmentClasses = type(record.playerEquipmentClasses) == "table"
        and record.playerEquipmentClasses or {}

    local function updateItemClasses(itemIds, delta)
        if type(itemIds) ~= "table" then return end
        if not ItemManager or type(ItemManager.GetItem) ~= "function" then
            log("Oyuncu ekipman siniflari kaydedilemedi: ItemManager.GetItem API'si kullanilamiyor.")
            return
        end

        for _, itemId in ipairs(itemIds) do
            local ok, item = pcall(ItemManager.GetItem, itemId)
            if not ok or type(item) ~= "table" or type(item.class) ~= "string" then
                log("Oyuncu ekipman sinifi kaydedilemedi: item="
                    .. tostring(itemId) .. ", sonuc=" .. tostring(item))
            else
                local classKey = string.lower(string.gsub(item.class, "%-", ""))
                local equipmentData = nebakovrising.EquipmentData
                local isEquipment = equipmentData
                    and ((equipmentData.items and equipmentData.items[classKey])
                        or (equipmentData.weaponClasses
                            and equipmentData.weaponClasses[classKey]))
                if isEquipment then
                    local entry = record.playerEquipmentClasses[classKey]
                    local count = type(entry) == "table"
                        and tonumber(entry.count) or 0
                    count = math.max(0, count + delta)
                    if count == 0 then
                        record.playerEquipmentClasses[classKey] = nil
                    else
                        record.playerEquipmentClasses[classKey] = {
                            class = item.class,
                            count = count,
                        }
                    end
                end
            end
        end
    end

    updateItemClasses(receivedItemIds, 1)
    updateItemClasses(removedItemIds, -1)
    log("NPC oyuncu ekipmani kalici kayda yazildi ve yeniden kusanim icin izlenecek: "
        .. entityName)
    return true
end

function CastleUtils.IsNpcEquipmentPreserved(entityName)
    if type(entityName) ~= "string" or entityName == "" then
        return false
    end
    local records = getPersistentRecords(false)
    local record = records and records[entityName]
    return type(record) == "table" and record.preserveEquipment == true
end

function CastleUtils.GetPreservedPlayerEquipmentClasses(entityName)
    if type(entityName) ~= "string" or entityName == "" then
        return nil
    end
    local records = getPersistentRecords(false)
    local record = records and records[entityName]
    if type(record) ~= "table" or record.preserveEquipment ~= true
        or type(record.playerEquipmentClasses) ~= "table" then
        return nil
    end
    return record.playerEquipmentClasses
end

function CastleUtils.MarkPlayerEquipmentEquipped(entityName, itemId)
    if type(entityName) ~= "string" or entityName == "" or itemId == nil then
        return
    end
    CastleUtils._playerEquipmentFallback =
        CastleUtils._playerEquipmentFallback or {}
    CastleUtils._playerEquipmentFallback[entityName] =
        CastleUtils._playerEquipmentFallback[entityName] or {}
    CastleUtils._playerEquipmentFallback[entityName][tostring(itemId)] = true
end

local function itemHasEquipmentSlot(item)
    if not item or type(item.GetSlot) ~= "function" then
        if not CastleUtils._playerEquipmentSlotWarningLogged then
            CastleUtils._playerEquipmentSlotWarningLogged = true
            log("Ekipman slotu kontrol edilemiyor: Item.GetSlot API'si kullanilamiyor; son kusandirma kaydi yedek olarak kullanilacak.")
        end
        return nil
    end

    local ok, slot = pcall(item.GetSlot, item, true)
    if not ok then
        if not CastleUtils._playerEquipmentSlotWarningLogged then
            CastleUtils._playerEquipmentSlotWarningLogged = true
            log("Ekipman slotu kontrol edilemiyor: Item.GetSlot cagrisinda hata: "
                .. tostring(slot))
        end
        return nil
    end
    if slot == nil or slot == false or slot == 0 then
        return false
    end

    local slotHandle = tostring(slot)
    local handleValue = string.match(slotHandle, "([%x]+)$")
    if handleValue and string.match(handleValue, "^0+$") then
        return false
    end
    return true
end

function CastleUtils.EnsurePlayerEquipmentEquipped()
    local records = getPersistentRecords(false)
    if not ItemManager or type(ItemManager.GetItem) ~= "function" then
        if not CastleUtils._playerEquipmentApiWarning then
            CastleUtils._playerEquipmentApiWarning = true
            log("Oyuncu ekipmani korunamiyor: ItemManager.GetItem API'si kullanilamiyor.")
        end
        Script.SetTimerForFunction(
            5000,
            "nebakovrising.CastleUtils.EnsurePlayerEquipmentEquipped"
        )
        return
    end

    for entityName, record in pairs(records or {}) do
        local preservedClasses = type(record) == "table"
            and record.playerEquipmentClasses
        if type(record) == "table" and record.managed
            and type(preservedClasses) == "table" then
            local entityId = System.GetEntityIdByName(entityName)
            local npc = entityId and System.GetEntity(entityId)
            local actor = npc and npc.actor
            local inventory = npc and npc.inventory
            local npcWuid = npc and npc.this and npc.this.id
            local bedState = npcWuid and CastleUtils.GetBedWalkState(npcWuid)

            if actor and inventory
                and bedState ~= "requested"
                and bedState ~= "active"
                and bedState ~= "completed"
                and bedState ~= "waking"
                and bedState ~= "meal"
                and bedState ~= "meal_pending"
                and bedState ~= "meal_ready"
                and bedState ~= "eating"
                and type(actor.EquipInventoryItem) == "function"
                and type(inventory.GetInventoryTable) == "function" then
                local isUnavailable = false
                if type(actor.IsDead) == "function" then
                    local ok, value = pcall(actor.IsDead, actor)
                    isUnavailable = ok and value == true
                end
                if not isUnavailable and type(actor.IsUnconscious) == "function" then
                    local ok, value = pcall(actor.IsUnconscious, actor)
                    isUnavailable = ok and value == true
                end

                if not isUnavailable then
                    local ok, inventoryItems = pcall(
                        inventory.GetInventoryTable,
                        inventory
                    )
                    if not ok or type(inventoryItems) ~= "table" then
                        log("Oyuncu ekipmani kontrol edilemedi: NPC="
                            .. tostring(entityName) .. ", sonuc="
                            .. tostring(inventoryItems))
                    else
                        local remaining = {}
                        for classKey, entry in pairs(preservedClasses) do
                            if type(entry) == "table" and type(entry.class) == "string" then
                                remaining[classKey] = math.max(
                                    0,
                                    tonumber(entry.count) or 0
                                )
                            end
                        end

                        local itemsToEquip = {}
                        local equipmentData = nebakovrising.EquipmentData
                        for _, itemId in pairs(inventoryItems) do
                            local itemOk, item = pcall(ItemManager.GetItem, itemId)
                            if itemOk and type(item) == "table"
                                and type(item.class) == "string" then
                                local classKey = string.lower(
                                    string.gsub(item.class, "%-", "")
                                )
                                if (remaining[classKey] or 0) > 0 then
                                    local hasSlot = itemHasEquipmentSlot(item)
                                    local itemKey = tostring(itemId)
                                    local wasEquipped = CastleUtils._playerEquipmentFallback
                                        and CastleUtils._playerEquipmentFallback[entityName]
                                        and CastleUtils._playerEquipmentFallback[entityName][itemKey]
                                    if not hasSlot
                                        and not (hasSlot == nil and wasEquipped) then
                                        local indexedItem = equipmentData
                                            and equipmentData.items
                                            and equipmentData.items[classKey]
                                        itemsToEquip[#itemsToEquip + 1] = {
                                            id = itemId,
                                            key = itemKey,
                                            class = item.class,
                                            slotOrder = indexedItem
                                                and equipmentData.slotOrder
                                                and equipmentData.slotOrder[indexedItem.slot]
                                                or 999,
                                        }
                                    end
                                    remaining[classKey] = remaining[classKey] - 1
                                end
                            end
                        end

                        table.sort(itemsToEquip, function(left, right)
                            if left.slotOrder ~= right.slotOrder then
                                return left.slotOrder < right.slotOrder
                            end
                            return tostring(left.class) < tostring(right.class)
                        end)

                        local equippedCount = 0
                        for _, item in ipairs(itemsToEquip) do
                            local equipOk, result = pcall(
                                actor.EquipInventoryItem,
                                actor,
                                item.id
                            )
                            if equipOk and result ~= false then
                                equippedCount = equippedCount + 1
                                CastleUtils._playerEquipmentFallback =
                                    CastleUtils._playerEquipmentFallback or {}
                                CastleUtils._playerEquipmentFallback[entityName] =
                                    CastleUtils._playerEquipmentFallback[entityName] or {}
                                CastleUtils._playerEquipmentFallback[entityName][item.key] = true
                            else
                                log("Oyuncu ekipmani yeniden kusanilamadi: NPC="
                                    .. tostring(entityName)
                                    .. ", class=" .. tostring(item.class)
                                    .. ", sonuc=" .. tostring(result))
                            end
                        end
                        if equippedCount > 0 then
                            log("Oyuncu ekipmani yeniden kusanildi: NPC="
                                .. tostring(entityName)
                                .. ", item=" .. tostring(equippedCount))
                        end
                    end
                end
            end
        end
    end

    -- NPCs can drop runtime gear during LOD changes; re-offer only tracked gear classes.
    Script.SetTimerForFunction(
        5000,
        "nebakovrising.CastleUtils.EnsurePlayerEquipmentEquipped"
    )
end

function CastleUtils.RemoveManagedNpcRecord(entityName)
    if type(entityName) ~= "string" then return false end
    local records = getPersistentRecords(false)
    if not records or not records[entityName] then return false end
    records[entityName] = nil
    log("NPC save kaydi olum nedeniyle silindi: " .. entityName)
    return true
end

function CastleUtils.ClearManagedNpcs()
    local records = getPersistentRecords(false)
    local clearedRecords = 0
    local managedNames = {}

    for entityName, record in pairs(records or {}) do
        managedNames[tostring(entityName)] = true
        records[entityName] = nil
        clearedRecords = clearedRecords + 1
    end

    for _, npc in pairs(System.GetEntitiesByClass("NPC") or {}) do
        local entityName
        if npc and npc.GetName then
            local ok, name = pcall(npc.GetName, npc)
            if ok and name and name ~= "" then
                entityName = tostring(name)
            end
        end
        if entityName and string.sub(entityName, 1, 14) == "nebakovrising_" then
            managedNames[entityName] = true
        end
    end

    local removedNpcs = 0
    for entityName in pairs(managedNames) do
        local entityId = System.GetEntityIdByName(entityName)
        if entityId then
            local ok, result = pcall(System.RemoveEntity, entityId)
            if ok and result ~= false then
                removedNpcs = removedNpcs + 1
            else
                log("NPC silinemedi: " .. entityName
                    .. ", sonuc=" .. tostring(result))
            end
        end
    end

    CastleUtils.ResetBedAssignments()
    CastleUtils.restoredNpcNames = {}
    CastleUtils._restoreInProgress = false
    if nebakovrising.Spawner then
        nebakovrising.Spawner._names = {}
    end

    log("Yonetilen NPC temizligi tamamlandi: silinenNPC="
        .. tostring(removedNpcs) .. ", silinenKayit=" .. tostring(clearedRecords))
    return removedNpcs, clearedRecords
end

function CastleUtils.IsNpcSleepTime()
    if not Calendar or type(Calendar.GetWorldHourOfDay) ~= "function" then
        if not CastleUtils._sleepTimeApiWarningLogged then
            CastleUtils._sleepTimeApiWarningLogged = true
            log("NPC uyku zamani belirlenemedi: Calendar.GetWorldHourOfDay API'si yok.")
        end
        return false, nil
    end

    local ok, hour = pcall(Calendar.GetWorldHourOfDay)
    if not ok or type(hour) ~= "number" then
        if not CastleUtils._sleepTimeApiWarningLogged then
            CastleUtils._sleepTimeApiWarningLogged = true
            log("NPC uyku zamani belirlenemedi: oyun saati okunamadi: " .. tostring(hour))
        end
        return false, nil
    end

    local startHour = nebakovrising.Config and nebakovrising.Config.npcSleepStartHour
    local wakeHour = nebakovrising.Config and nebakovrising.Config.npcWakeHour
    if type(startHour) ~= "number" or type(wakeHour) ~= "number"
        or startHour < 0 or startHour >= 24
        or wakeHour < 0 or wakeHour >= 24
        or startHour == wakeHour then
        if not CastleUtils._sleepTimeConfigWarningLogged then
            CastleUtils._sleepTimeConfigWarningLogged = true
            log("NPC uyku zamani belirlenemedi: baslangic/uyanma saati gecersiz.")
        end
        return false, hour
    end

    if startHour < wakeHour then
        return hour >= startHour and hour < wakeHour, hour
    end
    return hour >= startHour or hour < wakeHour, hour
end

local function getEntityKey(entity, fallbackId)
    if entity and entity.GetName then
        local ok, name = pcall(entity.GetName, entity)
        if ok and name and name ~= "" then
            return tostring(name)
        end
    end
    if entity and entity.id ~= nil then
        return tostring(entity.id)
    end
    return tostring(fallbackId)
end

local function findMealBowlItem(inventory)
    local ok, inventoryItems = pcall(
        inventory.GetInventoryTable,
        inventory
    )
    if not ok or type(inventoryItems) ~= "table" then
        log("NPC icin kase kontrol edilemedi: envanter okunamadi: "
            .. tostring(inventoryItems))
        return nil
    end

    local bowlClasses = {}
    for _, classId in ipairs(CastleUtils.mealBowlClassIds) do
        bowlClasses[string.lower(string.gsub(classId, "%-", ""))] = true
    end
    for _, itemId in pairs(inventoryItems) do
        local itemOk, item = pcall(ItemManager.GetItem, itemId)
        if itemOk and type(item) == "table" and type(item.class) == "string" then
            local classKey = string.lower(string.gsub(item.class, "%-", ""))
            if bowlClasses[classKey] then
                return itemId, item.class
            end
        end
    end
    return nil
end

function CastleUtils.EnsureNpcHasMealBowl(npcWuid)
    if npcWuid == nil then
        log("NPC icin kase kontrol edilemedi: WUID yok.")
        return false
    end

    local npc
    if XGenAIModule and type(XGenAIModule.GetEntityByWUID) == "function" then
        local entityOk, entity = pcall(XGenAIModule.GetEntityByWUID, npcWuid)
        if entityOk then
            npc = entity
        end
    end
    if not npc then
        npc = System.GetEntity(npcWuid)
    end
    local inventory = npc and npc.inventory
    if not inventory or type(inventory.GetInventoryTable) ~= "function" then
        log("NPC icin kase kontrol edilemedi: Inventory.GetInventoryTable kullanilamiyor.")
        return false
    end
    if not ItemManager or type(ItemManager.GetItem) ~= "function" then
        log("NPC icin kase kontrol edilemedi: ItemManager.GetItem kullanilamiyor.")
        return false
    end

    local bowlItemId, bowlClass = findMealBowlItem(inventory)
    if bowlItemId then
        log("NPC kazan davranisi icin kase envanterde mevcut: NPC="
            .. tostring(npcWuid) .. ", item=" .. tostring(bowlItemId)
            .. ", class=" .. tostring(bowlClass))
        return bowlItemId
    end

    if type(inventory.CreateItem) ~= "function" then
        log("NPC icin kase olusturulamadi: Inventory.CreateItem kullanilamiyor.")
        return false
    end
    local bowlClassId = "6f6cdb4c-0382-49ab-bb2e-04ae2e254479"
    local createOk, bowlItemId = pcall(
        inventory.CreateItem,
        inventory,
        bowlClassId,
        1,
        1
    )
    if not createOk or bowlItemId == nil or bowlItemId == false then
        log("NPC icin bos corba kasesi olusturulamadi: NPC="
            .. tostring(npcWuid) .. ", sonuc=" .. tostring(bowlItemId))
        return false
    end

    local addedItemId, addedClass = findMealBowlItem(inventory)
    if not addedItemId then
        log("NPC icin CreateItem basarili gorundu ancak kase envanterde dogrulanamadi: NPC="
            .. tostring(npcWuid) .. ", sonuc=" .. tostring(bowlItemId))
        return false
    end

    log("NPC icin bos corba kasesi eklendi ve dogrulandi: NPC="
        .. tostring(npcWuid) .. ", item=" .. tostring(addedItemId)
        .. ", class=" .. tostring(addedClass))
    return addedItemId
end

function CastleUtils.SetMealProgress(npc, stage)
    if not npc then
        log("NPC yemek asamasi kaydedilemedi: entity yok.")
        return false
    end

    local entityName = getEntityKey(npc, npc.this and npc.this.id)
    local records = getPersistentRecords(stage ~= nil)
    local record = records and records[entityName]
    if not record then
        log("NPC yemek asamasi kaydedilemedi: kalici NPC kaydi yok: "
            .. tostring(entityName))
        return false
    end

    record.mealStage = stage
    if stage == "meal_ready" then
        record.mealCollected = true
    elseif stage == nil or stage == "walking_to_cauldron"
        or stage == "meal_pending" then
        record.mealCollected = false
    end
    log("NPC yemek asamasi save'e yazildi: " .. entityName
        .. ", stage=" .. tostring(stage))
    return true
end

function CastleUtils.GetMealProgress(npc)
    if not npc then return nil end
    local entityName = getEntityKey(npc, npc.this and npc.this.id)
    local records = getPersistentRecords(false)
    local record = records and records[entityName]
    return type(record) == "table" and record.mealStage or nil
end

function CastleUtils.HasCollectedMeal(npc)
    if not npc then return false end
    local entityName = getEntityKey(npc, npc.this and npc.this.id)
    local records = getPersistentRecords(false)
    local record = records and records[entityName]
    return type(record) == "table" and record.mealCollected == true
end

local function getAiWuid(entity)
    if not entity or not XGenAIModule or not XGenAIModule.GetMyWUID then
        return nil
    end

    local ok, wuid = pcall(XGenAIModule.GetMyWUID, entity)
    if ok and wuid then
        return wuid
    end
    return nil
end

function CastleUtils.GetMealFireplace()
    local selector = CastleUtils.mealFireplaceSelector
    local entityId = System.GetEntityIdByName(selector)
    local entity = entityId and System.GetEntity(entityId)
    local wuid = entity and getAiWuid(entity)
    local position = entity and readEntityPosition(entity)
    if entity and wuid and position then
        return entity, wuid, position
    end

    log("Yemek fireplace'i bulunamadi veya smartobject WUID/konumu hazir degil: "
        .. tostring(selector))
    return nil
end

local function resolveMealBench(selector)
    local entityId = System.GetEntityIdByName(selector)
    local entity = entityId and System.GetEntity(entityId)
    local wuid = entity and getAiWuid(entity)
    local position = entity and readEntityPosition(entity)
    if entity and wuid and position then
        return {
            id = selector,
            entity = entity,
            selector = selector,
            wuid = wuid,
            position = position,
        }
    end

    log("Yemek bench'i bulunamadi veya smartobject WUID/konumu hazir degil: "
        .. tostring(selector) .. ", WUID=" .. tostring(wuid))
    return nil
end

-- Atamalar save'de kalici olsun diye anahtar WUID degil entity adidir.
local function getMealNpcKey(npcWuid)
    if npcWuid == nil then return nil end
    if XGenAIModule and type(XGenAIModule.GetEntityByWUID) == "function" then
        local ok, entity = pcall(XGenAIModule.GetEntityByWUID, npcWuid)
        if ok and entity and entity.GetName then
            local nameOk, name = pcall(entity.GetName, entity)
            if nameOk and type(name) == "string" and name ~= "" then
                return name
            end
        end
    end
    return tostring(npcWuid)
end

local function getMealRecord(npcKey, createStore)
    local records = getPersistentRecords(createStore)
    local record = records and records[npcKey]
    return type(record) == "table" and record or nil
end

local function persistMealBench(npcKey, selector)
    local record = getMealRecord(npcKey, false)
    if record then record.mealBenchSelector = selector end
end

function CastleUtils.ReserveMealBenches()
    local records = getPersistentRecords(false)
    if not records then return 0 end

    local reserved = 0
    for entityName, record in pairs(records) do
        if type(record) == "table" and record.managed and record.mealBenchSelector then
            local selector = record.mealBenchSelector
            local owner = CastleUtils.mealBenchOwners[selector]
            if record.mealStage == nil then
                record.mealBenchSelector = nil
            elseif not owner or owner == entityName then
                CastleUtils.mealBenchOwners[selector] = entityName
                reserved = reserved + 1
                log("Save'den yemek bench'i rezerve edildi: "
                    .. tostring(entityName) .. " -> " .. tostring(selector))
            end
        end
    end
    return reserved
end

function CastleUtils.GetMealBench(npcWuid)
    if npcWuid == nil then
        log("Yemek bench'i atanamadi: NPC WUID yok.")
        return nil
    end

    local npcKey = getMealNpcKey(npcWuid)
    local assignment = CastleUtils.mealBenchAssignments[npcKey]
    if assignment then
        local bench = resolveMealBench(assignment.selector)
        if bench then
            return bench.entity, bench.wuid, bench.position, bench.selector
        end
        return nil
    end

    -- Save'den gelen kayitli koltuk varsa baska koltuga dusme; hazir olana kadar bekle.
    local record = getMealRecord(npcKey, false)
    local savedSelector = record and record.mealBenchSelector
    if savedSelector then
        local owner = CastleUtils.mealBenchOwners[savedSelector]
        if not owner or owner == npcKey then
            local bench = resolveMealBench(savedSelector)
            if bench then
                CastleUtils.mealBenchOwners[savedSelector] = npcKey
                CastleUtils.mealBenchAssignments[npcKey] = bench
                log("Kayitli yemek bench'i geri yuklendi: NPC=" .. npcKey .. " -> " .. savedSelector)
                return bench.entity, bench.wuid, bench.position, bench.selector
            end
            return nil
        end
        record.mealBenchSelector = nil
    end

    -- Yataklardaki gibi: dizideki ilk bos koltuk, sirayla.
    for _, selector in ipairs(CastleUtils.mealBenchSelectors) do
        if not CastleUtils.mealBenchOwners[selector] then
            local bench = resolveMealBench(selector)
            if bench then
                CastleUtils.mealBenchOwners[selector] = npcKey
                CastleUtils.mealBenchAssignments[npcKey] = bench
                persistMealBench(npcKey, selector)
                log("Yemek bench'i NPC'ye atandi: NPC=" .. npcKey .. " -> " .. selector)
                return bench.entity, bench.wuid, bench.position, bench.selector
            end
        end
    end

    local occupied = {}
    for selector, owner in pairs(CastleUtils.mealBenchOwners) do
        occupied[#occupied + 1] = string.sub(selector, 1, 60) .. " -> " .. tostring(owner)
    end
    log("NPC icin bos yemek bench'i yok: " .. npcKey .. " (dolu: "
        .. (#occupied > 0 and table.concat(occupied, "; ") or "yok") .. ")")
    return nil
end

function CastleUtils.RetryMealBench(npcWuid)
    if npcWuid == nil then return false end

    local npcKey = getMealNpcKey(npcWuid)
    persistMealBench(npcKey, nil)
    local assignment = CastleUtils.mealBenchAssignments[npcKey]
    if not assignment then
        log("Yemek bench'i yeniden atanamadi: mevcut atama yok: " .. npcKey)
        return false
    end

    local attempts = CastleUtils.mealBenchAttempts[npcKey]
    if type(attempts) ~= "table" then
        attempts = {}
        CastleUtils.mealBenchAttempts[npcKey] = attempts
    end
    attempts[assignment.selector] = true
    if CastleUtils.mealBenchOwners[assignment.selector] == npcKey then
        CastleUtils.mealBenchOwners[assignment.selector] = nil
    end
    CastleUtils.mealBenchAssignments[npcKey] = nil

    log("NPC oturamadigi yemek bench'ini bir sonraki deneme icin birakti: NPC="
        .. npcKey .. " -> " .. tostring(assignment.selector))
    return true
end

function CastleUtils.ReleaseMealBenchForNpc(npcWuid)
    if npcWuid == nil then return false end

    local npcKey = getMealNpcKey(npcWuid)
    persistMealBench(npcKey, nil)
    local assignment = CastleUtils.mealBenchAssignments[npcKey]
    if not assignment then return false end

    if CastleUtils.mealBenchOwners[assignment.selector] == npcKey then
        CastleUtils.mealBenchOwners[assignment.selector] = nil
    end
    CastleUtils.mealBenchAssignments[npcKey] = nil
    CastleUtils.mealBenchAttempts[npcKey] = nil
    log("NPC yemek bench atamasi serbest birakildi: NPC=" .. npcKey
        .. " -> " .. tostring(assignment.selector))
    return true
end

local function isNpcDead(npc)
    if not npc then return true end

    local actor = npc.actor
    if actor and type(actor.IsDead) == "function" then
        local ok, isDead = pcall(actor.IsDead, actor)
        if ok and isDead then
            return true
        end
    end

    local soul = npc.soul
    if soul and type(soul.GetState) == "function" then
        local ok, health = pcall(soul.GetState, soul, "health")
        if ok and health ~= nil and health <= 0 then
            return true
        end
    end

    return false
end

function CastleUtils.RefreshBeds()
    local discoveredBeds = {}
    local seen = {}

    for poolName, selectors in pairs(CastleUtils.bedPools) do
        for _, selector in pairs(selectors) do
            if type(selector) == "string" then
                local entityId = System.GetEntityIdByName(selector)
                local entity = entityId and System.GetEntity(entityId)
                if entity then
                    local key = selector
                    if not seen[key] then
                        seen[key] = true
                        local position
                        local positionOk, positionResult = pcall(function()
                            return entity:GetWorldPos()
                        end)
                        if positionOk then
                            position = positionResult
                        end

                        discoveredBeds[#discoveredBeds + 1] = {
                            id = key,
                            entity = entity,
                            selector = selector,
                            pool = poolName,
                            wuid = getAiWuid(entity),
                            position = position,
                        }
                    end
                else
                    log("Yatak entity'si bulunamadi: " .. selector)
                end
            end
        end
    end

    CastleUtils.bedEntities = discoveredBeds
    log("Bulunan yatak sayisi: " .. tostring(#discoveredBeds))
    return #discoveredBeds
end

function CastleUtils.ReservePersistentBeds()
    local records = getPersistentRecords(false)
    if not records then return 0 end

    local reserved = 0
    for entityName, record in pairs(records) do
        if type(record) == "table" and record.managed and record.bedSelector then
            local bedFound = false
            for _, bed in ipairs(CastleUtils.bedEntities) do
                if bed.selector == record.bedSelector then
                    bedFound = true
                    local currentOwner = CastleUtils.bedOwners[bed.id]
                    if not currentOwner or currentOwner == entityName then
                        CastleUtils.bedOwners[bed.id] = entityName
                        reserved = reserved + 1
                        local entityId = System.GetEntityIdByName(entityName)
                        local npc = entityId and System.GetEntity(entityId)
                        if npc and not isNpcDead(npc) then
                            local npcWuid = getAiWuid(npc)
                            local npcWuidKey = npcWuid and tostring(npcWuid)
                            local entityWuid = npc.this and npc.this.id
                            CastleUtils.bedAssignments[entityName] = bed
                            if npcWuidKey then
                                CastleUtils.bedAssignments[npcWuidKey] = bed
                                CastleUtils.bedAssignmentsByWuid[npcWuidKey] = bed
                            end
                            if entityWuid then
                                CastleUtils.bedAssignmentsByWuid[tostring(entityWuid)] = bed
                            end
                            if npcWuidKey or entityWuid then
                                log("Kayitli NPC yatagi yukleme basinda baglandi: "
                                    .. tostring(entityName) .. " -> "
                                    .. tostring(record.bedSelector))
                            else
                                log("Kayitli NPC yatagi rezerve; WUID baglantisi bekleniyor: "
                                    .. tostring(entityName))
                            end
                        else
                            log("Kayitli NPC yatagi rezerve; NPC entity'si henuz hazir degil: "
                                .. tostring(entityName))
                        end
                        log("Save'den NPC yatagi rezerve edildi: "
                            .. tostring(entityName) .. " -> " .. tostring(record.bedSelector))
                    else
                        log("Kayitli NPC yatagi baska kayda rezerve: bed="
                            .. tostring(record.bedSelector) .. ", owner="
                            .. tostring(currentOwner) .. ", ignored="
                            .. tostring(entityName))
                    end
                    break
                end
            end
            if not bedFound then
                log("Kayitli NPC yatagi bu bolgede bulunamadi: "
                    .. tostring(entityName) .. " -> " .. tostring(record.bedSelector))
            end
        end
    end
    log("Save'den yatak rezervasyonu yapildi: " .. tostring(reserved))
    return reserved
end

function CastleUtils.AssignBedToNpc(npc, poolName)
    if not npc then
        log("Yatak atanamadi: NPC entity yok.")
        return nil
    end

    CastleUtils.RefreshBeds()

    local npcWuid = getAiWuid(npc)
    local npcWuidKey = npcWuid and tostring(npcWuid)
    local npcId = getEntityKey(npc, npcWuidKey)
    if not poolName then
        local role = nebakovrising.Roles and nebakovrising.Roles.Resolve(npcId)
        poolName = role and role.bedPool
    end
    local assignment = CastleUtils.bedAssignments[npcId]
        or (npcWuidKey and CastleUtils.bedAssignments[npcWuidKey])
    if assignment then
        local bed = assignment
        return bed.entity, bed.selector
    end

    local poolBeds = {}
    for _, candidate in ipairs(CastleUtils.bedEntities) do
        if candidate.pool == poolName then
            poolBeds[#poolBeds + 1] = candidate
        end
    end
    if #poolBeds == 0 then
        log("NPC icin yatak havuzu bos: " .. npcId .. " (havuz=" .. tostring(poolName) .. ")")
        return nil
    end

    for _, bed in ipairs(poolBeds) do
        local ownerName = CastleUtils.bedOwners[bed.id]
        if ownerName then
            local ownerEntityId = System.GetEntityIdByName(ownerName)
            local ownerEntity = ownerEntityId and System.GetEntity(ownerEntityId)
            local records = getPersistentRecords(false)
            local persistentRecord = records and records[ownerName]
            if ownerEntity and isNpcDead(ownerEntity) then
                CastleUtils.ReleaseBedAssignmentForNpc(ownerName)
                ownerName = nil
            elseif not ownerEntity and not persistentRecord then
                CastleUtils.ReleaseBedAssignmentForNpc(ownerName)
                ownerName = nil
            end
        end
        if not ownerName then
            if not bed.wuid or not bed.position then
                log("Yatak uyku icin hazir degil (WUID/konum eksik): "
                    .. bed.selector .. ", WUID=" .. tostring(bed.wuid)
                    .. ", konum=" .. tostring(bed.position))
            else
                CastleUtils.bedOwners[bed.id] = npcId
                CastleUtils.bedAssignments[npcId] = bed
                if npcWuidKey then
                    CastleUtils.bedAssignments[npcWuidKey] = bed
                    CastleUtils.bedAssignmentsByWuid[npcWuidKey] = bed
                end
                local entityWuid = npc.this and npc.this.id
                if entityWuid then
                    CastleUtils.bedAssignmentsByWuid[tostring(entityWuid)] = bed
                end
                log("Yatak " .. bed.selector .. " NPC'ye atandi: " .. npcId)
                return bed.entity, bed.selector
            end
        end
    end

    local occupied = {}
    for bedId, owner in pairs(CastleUtils.bedOwners) do
        occupied[#occupied + 1] = tostring(bedId) .. " -> " .. tostring(owner)
    end
    log("NPC icin musait yatak yok: " .. npcId .. " (atanmis yataklar: "
        .. (#occupied > 0 and table.concat(occupied, "; ") or "yok") .. ")")
    return nil
end

function CastleUtils.ResetBedAssignments()
    CastleUtils.bedOwners = {}
    CastleUtils.bedAssignments = {}
    CastleUtils.bedAssignmentsByWuid = {}
    CastleUtils.mealBenchOwners = {}
    CastleUtils.mealBenchAssignments = {}
    CastleUtils.mealBenchAttempts = {}
    CastleUtils.trackedBedOwners = {}
    CastleUtils.trackedBedCandidates = {}
    CastleUtils.trackedBedCandidatesByWuid = {}
    CastleUtils.deathMonitorWarnings = {}
    CastleUtils.bedWalkStates = {}
    log("Gecici yatak/yemek yeri atamalari temizlendi; kayitli NPC yataklari yeniden kurulacak.")
end

function CastleUtils.ReleaseBedAssignmentForNpc(entityName)
    if not entityName then return false end

    entityName = tostring(entityName)
    local bed = CastleUtils.bedAssignments[entityName]
    local released = false

    if bed then
        for bedId, ownerName in pairs(CastleUtils.bedOwners) do
            if ownerName == entityName then
                CastleUtils.bedOwners[bedId] = nil
                released = true
            end
        end

        for key, assignment in pairs(CastleUtils.bedAssignments) do
            if key == entityName or assignment == bed then
                CastleUtils.bedAssignments[key] = nil
            end
        end

        for wuid, assignment in pairs(CastleUtils.bedAssignmentsByWuid) do
            if assignment == bed then
                CastleUtils.bedAssignmentsByWuid[wuid] = nil
            end
        end
    else
        for bedId, ownerName in pairs(CastleUtils.bedOwners) do
            if ownerName == entityName then
                CastleUtils.bedOwners[bedId] = nil
                released = true
            end
        end
    end

    CastleUtils.trackedBedOwners[entityName] = nil
    CastleUtils.deathMonitorWarnings[entityName] = nil
    CastleUtils.RemoveManagedNpcRecord(entityName)
    if released then
        log("NPC yatak atamasi serbest birakildi: " .. entityName)
    end
    return released
end

function CastleUtils.CheckTrackedBedOwner(entityName)
    entityName = tostring(entityName)
    if not CastleUtils.trackedBedOwners[entityName] then return end

    local entityId = System.GetEntityIdByName(entityName)
    local npc = entityId and System.GetEntity(entityId)
    if not npc then
        CastleUtils.trackedBedOwners[entityName] = nil
        log("NPC su an yuklu degil; yatak kaydi korunuyor: " .. entityName)
        return
    end

    local actor = npc.actor
    if isNpcDead(npc) then
        CastleUtils.ReleaseBedAssignmentForNpc(entityName)
        return
    end

    if not actor or type(actor.IsDead) ~= "function" then
        if not CastleUtils.deathMonitorWarnings[entityName] then
            CastleUtils.deathMonitorWarnings[entityName] = true
            log("NPC olum kontrolu bekleniyor; actor/IsDead hazir degil: " .. entityName)
        end
    end

    Script.SetTimerForFunction(
        1000,
        "nebakovrising.CastleUtils.CheckTrackedBedOwner",
        entityName
    )
end

function CastleUtils.RestoreNpcRuntimeState(userData)
    if type(userData) ~= "table"
        or type(userData.entityName) ~= "string"
        or type(userData.attemptsLeft) ~= "number" then
        log("NPC runtime restore callback'ine gecersiz veri verildi.")
        return
    end

    local entityName = userData.entityName
    local attemptsLeft = userData.attemptsLeft
    local entityId = System.GetEntityIdByName(entityName)
    local npc = entityId and System.GetEntity(entityId)
    local retry = false

    if not npc then
        retry = true
    else
        local interaction = nebakovrising.NpcInteraction
        if interaction and interaction.Inject then
            local ok, injected = pcall(interaction.Inject, npc)
            if not ok or not injected then
                retry = true
                log("Gecikmeli NPC etkilesim restore basarisiz: "
                    .. entityName .. ", sonuc=" .. tostring(injected))
            else
                log("Gecikmeli NPC etkilesim restore tamamlandi: " .. entityName)
            end
        else
            retry = true
            log("NPC etkilesim modulu hazir degil: " .. entityName)
        end

        local records = getPersistentRecords(false)
        local record = records and records[entityName]
        if record
            and nebakovrising.Spawner
            and nebakovrising.Spawner.ApplyClothingPreset then
            local applied = nebakovrising.Spawner.ApplyClothingPreset(
                entityName,
                attemptsLeft,
                true
            )
            if not applied then
                log("Gecikmeli NPC kiyafet preset'i henuz uygulanamadi: "
                    .. entityName)
            end
        end

        local spawner = nebakovrising.Spawner
        if spawner and spawner.ApplyFaction then
            spawner.ApplyFaction(entityName, attemptsLeft)
        end
        if spawner and spawner.ApplyWeaponDrawContext then
            spawner.ApplyWeaponDrawContext(entityName, attemptsLeft)
        end
    end

    if retry and attemptsLeft > 0 then
        Script.SetTimerForFunction(
            1000,
            "nebakovrising.CastleUtils.RestoreNpcRuntimeState",
            {
                entityName = entityName,
                attemptsLeft = attemptsLeft - 1,
            }
        )
    elseif retry then
        log("NPC runtime restore icin tekrar deneme hakki bitti: " .. entityName)
    end
end

function CastleUtils.RestoreManagedNpcs(attemptsLeft)
    attemptsLeft = attemptsLeft or 0
    local records = getPersistentRecords(false)
    if #CastleUtils.bedEntities == 0 then
        CastleUtils.RefreshBeds()
    end

    local legacyNpcs = {}
    for _, npc in pairs(System.GetEntitiesByClass("NPC") or {}) do
        local entityName = npc and getEntityKey(npc)
        if entityName and string.sub(entityName, 1, 14) == "nebakovrising_" then
            legacyNpcs[#legacyNpcs + 1] = { name = entityName, entity = npc }
        end
    end
    table.sort(legacyNpcs, function(left, right)
        return left.name < right.name
    end)

    for _, legacyNpc in ipairs(legacyNpcs) do
        records = getPersistentRecords(false)
        if not records or not records[legacyNpc.name] then
            local bed, bedSelector = CastleUtils.AssignBedToNpc(legacyNpc.entity)
            CastleUtils.SaveManagedNpc(legacyNpc.name, bedSelector, true)
            records = getPersistentRecords(false)
            if bed then
                CastleUtils.TrackBedOwner(legacyNpc.entity, legacyNpc.name)
                CastleUtils.BindBedAssignmentToWuid(legacyNpc.entity)
            else
                CastleUtils.TrackUnassignedNpc(legacyNpc.entity, legacyNpc.name)
            end
            log("Eski save'deki NPC kaydi ilk kez olusturuldu; mevcut ekipman korunacak: "
                .. legacyNpc.name)
        end

        if nebakovrising.NpcInteraction
            and nebakovrising.NpcInteraction.Inject then
            local injectOk, injected = pcall(
                nebakovrising.NpcInteraction.Inject,
                legacyNpc.entity
            )
            if not injectOk or not injected then
                log("Eski save NPC etkilesimi geri kurulamadi: "
                    .. legacyNpc.name .. ", sonuc=" .. tostring(injected))
            else
                log("Eski save NPC etkilesimi geri kuruldu: " .. legacyNpc.name)
            end
        end
    end

    records = getPersistentRecords(false)
    if not records then
        if attemptsLeft > 0 then
            Script.SetTimerForFunction(
                1000,
                "nebakovrising.CastleUtils.RestoreManagedNpcs",
                attemptsLeft - 1
            )
        else
            log("Save-load NPC geri yuklemesi atlandi: yonetilen NPC veya kayitli veri bulunamadi.")
            CastleUtils._restoreInProgress = false
        end
        return
    end

    local pending = false
    for entityName, record in pairs(records) do
        if type(record) == "table" and record.managed then
            local entityId = System.GetEntityIdByName(entityName)
            local npc = entityId and System.GetEntity(entityId)
            if not npc then
                pending = true
            elseif isNpcDead(npc) then
                CastleUtils.ReleaseBedAssignmentForNpc(entityName)
            elseif not CastleUtils.restoredNpcNames[entityName] then
                local pendingEntity = false
                local bed
                for _, discoveredBed in ipairs(CastleUtils.bedEntities) do
                    if discoveredBed.selector == record.bedSelector then
                        bed = discoveredBed
                        break
                    end
                end

                if bed then
                    local npcWuid = getAiWuid(npc)
                    local npcWuidKey = npcWuid and tostring(npcWuid)
                    local entityWuid = npc.this and npc.this.id
                    local currentOwner = CastleUtils.bedOwners[bed.id]
                    if currentOwner and currentOwner ~= entityName then
                        pendingEntity = true
                        log("Save'den yatak atamasi cakismasi; mevcut sahip korunuyor: yatak="
                            .. tostring(record.bedSelector) .. ", owner="
                            .. tostring(currentOwner) .. ", bekleyen=" .. entityName)
                    else
                        CastleUtils.bedOwners[bed.id] = entityName
                        CastleUtils.bedAssignments[entityName] = bed
                        if npcWuidKey then
                            CastleUtils.bedAssignments[npcWuidKey] = bed
                            CastleUtils.bedAssignmentsByWuid[npcWuidKey] = bed
                        else
                            pendingEntity = true
                            log("NPC yatagi bulundu fakat NPC AI WUID henuz hazir degil: "
                                .. entityName)
                        end
                        if entityWuid then
                            CastleUtils.bedAssignmentsByWuid[tostring(entityWuid)] = bed
                        else
                            pendingEntity = true
                            log("NPC yatagi bulundu fakat Behavior Tree entity WUID hazir degil: "
                                .. entityName)
                        end
                        CastleUtils.TrackBedOwner(npc, entityName)
                        if not pendingEntity then
                            log("NPC yatak atamasi save'den geri yuklendi: "
                                .. entityName .. " -> " .. tostring(record.bedSelector))
                        else
                            log("NPC yatagi rezerve edildi; WUID baglantisi tamamlanmayi bekliyor: "
                                .. entityName .. " -> " .. tostring(record.bedSelector))
                        end
                    end
                elseif record.bedSelector then
                    pendingEntity = true
                    log("Save'deki NPC yatagi henuz bulunamadi: "
                        .. tostring(record.bedSelector))
                elseif CastleUtils.TrackUnassignedNpc then
                    CastleUtils.TrackUnassignedNpc(npc, entityName)
                end

                if nebakovrising.NpcInteraction
                    and nebakovrising.NpcInteraction.Inject then
                    local injectOk, injected = pcall(
                        nebakovrising.NpcInteraction.Inject,
                        npc
                    )
                    if not injectOk or not injected then
                        log("Save'den yuklenen NPC etkilesimi geri kurulamadi: "
                            .. entityName .. ", sonuc=" .. tostring(injected))
                        pendingEntity = true
                    else
                        log("Save'den yuklenen NPC etkilesimi geri kuruldu: " .. entityName)
                    end
                end

                if nebakovrising.Spawner
                    and nebakovrising.Spawner.ApplyClothingPreset then
                    log("NPC kiyafet preset'i gecikmeli olarak geri uygulanacak: "
                        .. entityName)
                else
                    log("Save'den yuklenen NPC icin kiyafet preset'i geri yuklenecek: "
                        .. entityName)
                end
                Script.SetTimerForFunction(
                    1000,
                    "nebakovrising.CastleUtils.RestoreNpcRuntimeState",
                    {
                        entityName = entityName,
                        attemptsLeft = 12,
                    }
                )

                if pendingEntity then
                    pending = true
                else
                    CastleUtils.restoredNpcNames[entityName] = true
                end
            end
        end
    end

    if pending and attemptsLeft > 0 then
        Script.SetTimerForFunction(
            1000,
            "nebakovrising.CastleUtils.RestoreManagedNpcs",
            attemptsLeft - 1
        )
    elseif pending then
        log("NPC save-load geri yuklemesinde hala eksik kayit var; yataklar/etkilesimler icin yeniden deneyin.")
        CastleUtils._restoreInProgress = false
    else
        CastleUtils._restoreInProgress = false
    end
end

function CastleUtils.TrackBedOwner(npc, entityName)
    if not npc then return false end

    entityName = entityName or getEntityKey(npc)
    if not entityName then
        log("NPC yatak sahipligi izlenemedi: entity adi yok.")
        return false
    end

    entityName = tostring(entityName)
    if CastleUtils.trackedBedOwners[entityName] then return true end

    CastleUtils.trackedBedOwners[entityName] = true
    CastleUtils.deathMonitorWarnings[entityName] = nil
    Script.SetTimerForFunction(
        1000,
        "nebakovrising.CastleUtils.CheckTrackedBedOwner",
        entityName
    )
    return true
end

function CastleUtils.BindBedAssignmentToWuid(npc)
    if not npc then return false end

    local npcWuid = getAiWuid(npc)
    local npcWuidKey = npcWuid and tostring(npcWuid)
    local entityWuid = npc.this and npc.this.id
    if not npcWuidKey and not entityWuid then return false end

    local npcId = getEntityKey(npc, npcWuidKey or entityWuid)
    local bed = CastleUtils.bedAssignments[npcId]
        or (npcWuidKey and CastleUtils.bedAssignments[npcWuidKey])
    if not bed then return false end

    if npcWuidKey then
        CastleUtils.bedAssignments[npcWuidKey] = bed
        CastleUtils.bedAssignmentsByWuid[npcWuidKey] = bed
    end
    if entityWuid then
        CastleUtils.bedAssignmentsByWuid[tostring(entityWuid)] = bed
    end

    -- The behavior tree looks assignments up by entity.this.id, not the AI WUID.
    return entityWuid ~= nil
end

function CastleUtils.RetryBedAssignmentBinding(entityName, attemptsLeft)
    local entityId = System.GetEntityIdByName(entityName)
    local npc = entityId and System.GetEntity(entityId)
    if npc and CastleUtils.BindBedAssignmentToWuid(npc) then
        return
    end

    attemptsLeft = (attemptsLeft or 0) - 1
    if attemptsLeft > 0 then
        Script.SetTimerForFunction(
            500,
            "nebakovrising.CastleUtils.RetryBedAssignmentBinding",
            entityName,
            attemptsLeft
        )
    else
        log("NPC Behavior Tree entity ID'si bulunamadi; uyku atamasi baglanamadi: "
            .. tostring(entityName))
    end
end

function CastleUtils.TryAssignBedToNpcByWuid(npcWuid)
    if npcWuid == nil then return false end
    local npcWuidKey = tostring(npcWuid)
    local entityName = CastleUtils.trackedBedCandidatesByWuid[npcWuidKey]
    if not entityName or not CastleUtils.trackedBedCandidates[entityName] then return false end

    local entityId = System.GetEntityIdByName(entityName)
    local npc = entityId and System.GetEntity(entityId)
    if not npc or isNpcDead(npc) then
        CastleUtils.trackedBedCandidates[entityName] = nil
        CastleUtils.trackedBedCandidatesByWuid[npcWuidKey] = nil
        return false
    end

    local entityWuid = npc.this and npc.this.id
    local aiWuid = getAiWuid(npc)
    if (aiWuid and CastleUtils.GetBedAssignment(aiWuid))
        or (entityWuid and CastleUtils.GetBedAssignment(entityWuid)) then
        CastleUtils.trackedBedCandidates[entityName] = nil
        CastleUtils.trackedBedCandidatesByWuid[npcWuidKey] = nil
        return false
    end

    local bed = CastleUtils.AssignBedToNpc(npc)
    if bed then
        CastleUtils.SaveManagedNpc(entityName, bed.selector)
        CastleUtils.trackedBedCandidates[entityName] = nil
        CastleUtils.trackedBedCandidatesByWuid[npcWuidKey] = nil
        CastleUtils.TrackBedOwner(npc, entityName)
        if not CastleUtils.BindBedAssignmentToWuid(npc) then
            Script.SetTimerForFunction(
                500,
                "nebakovrising.CastleUtils.RetryBedAssignmentBinding",
                entityName,
                12
            )
        end
        return true
    end

    return false
end

function CastleUtils.TrackUnassignedNpc(npc, entityName)
    if not npc then return false end

    entityName = entityName or getEntityKey(npc)
    if not entityName then
        log("Atamasiz NPC yatak kontrolune alinmadi: entity adi yok.")
        return false
    end

    entityName = tostring(entityName)
    if CastleUtils.trackedBedCandidates[entityName] then return true end

    local entityWuid = npc.this and npc.this.id
    if not entityWuid then
        log("Atamasiz NPC yatak kontrolune alinmadi: Behavior Tree entity ID'si yok: " .. entityName)
        return false
    end

    CastleUtils.trackedBedCandidates[entityName] = true
    CastleUtils.trackedBedCandidatesByWuid[tostring(entityWuid)] = entityName
    log("Atamasiz NPC icin yatak kontrolu baslatildi: " .. entityName)
    return true
end

function CastleUtils.GetBedAssignment(npcWuid)
    if npcWuid == nil then return nil end
    return CastleUtils.bedAssignmentsByWuid[tostring(npcWuid)]
end

function CastleUtils.GetBedWalkState(npcWuid)
    if npcWuid == nil then return nil end
    return CastleUtils.bedWalkStates[tostring(npcWuid)]
end

function CastleUtils.SetBedWalkState(npcWuid, state)
    if npcWuid == nil then return false end
    CastleUtils.bedWalkStates[tostring(npcWuid)] = state
    return true
end

local sleepingArmorSlots = {
    [22] = true, [31] = true, [32] = true, [33] = true,
    [34] = true, [37] = true, [38] = true, [39] = true,
    [41] = true, [42] = true,
}

local function isSleepingEquipment(equipmentData, classKey)
    local indexedItem = equipmentData.items[classKey]
    local slot = indexedItem and indexedItem.slot
    return (slot and sleepingArmorSlots[slot])
        or (equipmentData.weaponClasses
            and equipmentData.weaponClasses[classKey] == true)
end

function CastleUtils.EquipSleepingEquipment(entity)
    local actor = entity and entity.actor
    local inventory = entity and entity.inventory
    if not actor or type(actor.EquipInventoryItem) ~= "function" then
        log("Uyanma sonrasi ekipman kusanilamadi: Actor.EquipInventoryItem API'si kullanilamiyor.")
        return false
    end
    for _, statusMethodName in ipairs({ "IsDead", "IsUnconscious" }) do
        local statusMethod = actor[statusMethodName]
        if type(statusMethod) == "function" then
            local statusOk, unavailable = pcall(statusMethod, actor)
            if not statusOk then
                log("Uyanma sonrasi ekipman durumu okunamadi: "
                    .. statusMethodName .. ", sonuc=" .. tostring(unavailable))
                return false
            end
            if unavailable then
                log("Uyanma sonrasi ekipman kusanilmadi: NPC olu veya bilincsiz.")
                return false
            end
        end
    end
    if not inventory or type(inventory.GetInventoryTable) ~= "function" then
        log("Uyanma sonrasi ekipman kusanilamadi: Inventory.GetInventoryTable API'si kullanilamiyor.")
        return false
    end
    if not ItemManager or type(ItemManager.GetItem) ~= "function" then
        log("Uyanma sonrasi ekipman kusanilamadi: ItemManager.GetItem API'si kullanilamiyor.")
        return false
    end

    local equipmentData = nebakovrising.EquipmentData
    if not equipmentData or type(equipmentData.items) ~= "table" then
        log("Uyanma sonrasi ekipman kusanilamadi: EquipmentData indeksi kullanilamiyor.")
        return false
    end

    local inventoryOk, inventoryItems = pcall(
        inventory.GetInventoryTable,
        inventory
    )
    if not inventoryOk or type(inventoryItems) ~= "table" then
        log("Uyanma sonrasi ekipman kusanilamadi: envanter okunamadi: "
            .. tostring(inventoryItems))
        return false
    end

    local itemsToEquip = {}
    local failedCount = 0
    for _, itemId in pairs(inventoryItems) do
        local itemOk, item = pcall(ItemManager.GetItem, itemId)
        if not itemOk or type(item) ~= "table" or type(item.class) ~= "string" then
            failedCount = failedCount + 1
            log("Uyanma sonrasi esya sinifi okunamadi: item="
                .. tostring(itemId) .. ", sonuc=" .. tostring(item))
        else
            local classKey = string.lower(string.gsub(item.class, "%-", ""))
            if isSleepingEquipment(equipmentData, classKey) then
                local indexedItem = equipmentData.items[classKey]
                itemsToEquip[#itemsToEquip + 1] = {
                    id = itemId,
                    class = item.class,
                    slotOrder = indexedItem and equipmentData.slotOrder
                        and equipmentData.slotOrder[indexedItem.slot] or 999,
                }
            end
        end
    end

    table.sort(itemsToEquip, function(left, right)
        if left.slotOrder ~= right.slotOrder then
            return left.slotOrder < right.slotOrder
        end
        return tostring(left.class) < tostring(right.class)
    end)

    for _, item in ipairs(itemsToEquip) do
        local equipOk, result = pcall(
            actor.EquipInventoryItem,
            actor,
            item.id
        )
        if not equipOk or result == false then
            failedCount = failedCount + 1
            log("Uyanma sonrasi esya kusanilamadi: class="
                .. tostring(item.class) .. ", item=" .. tostring(item.id)
                .. ", sonuc=" .. tostring(result))
        end
    end

    log("Uyanma sonrasi ekipman geri kusanildi: entity="
        .. tostring(entity.id) .. ", hedef esya=" .. tostring(#itemsToEquip)
        .. ", hata=" .. tostring(failedCount))
    return failedCount == 0
end

function CastleUtils.UnequipSleepingArmor(entity)
    local actor = entity and entity.actor
    local inventory = entity and entity.inventory
    if not actor or type(actor.UnequipInventoryItem) ~= "function" then
        log("Uyku oncesi ekipman cikarilamadi: Actor.UnequipInventoryItem API'si kullanilamiyor.")
        return false
    end

    if not inventory or type(inventory.GetInventoryTable) ~= "function" then
        log("Uyku oncesi ekipman cikarilamadi: Inventory.GetInventoryTable API'si kullanilamiyor.")
        return false
    end
    if not ItemManager or type(ItemManager.GetItem) ~= "function" then
        log("Uyku oncesi ekipman cikarilamadi: ItemManager.GetItem API'si kullanilamiyor.")
        return false
    end

    local ok, inventoryItems = pcall(inventory.GetInventoryTable, inventory)
    if not ok or type(inventoryItems) ~= "table" then
        log("Uyku oncesi ekipman cikarilamadi: envanter okunamadi: "
            .. tostring(inventoryItems))
        return false
    end

    local equipmentData = nebakovrising.EquipmentData
    if not equipmentData or type(equipmentData.items) ~= "table" then
        log("Uyku oncesi ekipman cikarilamadi: EquipmentData indeksi kullanilamiyor.")
        return false
    end

    local itemCount = 0
    local failedCount = 0
    for _, itemId in pairs(inventoryItems) do
        local itemOk, item = pcall(ItemManager.GetItem, itemId)
        if not itemOk or type(item) ~= "table" or type(item.class) ~= "string" then
            failedCount = failedCount + 1
            log("Uyku oncesi esya sinifi okunamadi: item="
                .. tostring(itemId) .. ", sonuc=" .. tostring(item))
        else
            local classKey = string.lower(string.gsub(item.class, "%-", ""))
            local indexedItem = equipmentData.items[classKey]
            local slot = indexedItem and indexedItem.slot
            local isWeapon = equipmentData.weaponClasses[classKey] == true
            if isSleepingEquipment(equipmentData, classKey) then
                itemCount = itemCount + 1
                local unequipOk, result = pcall(
                    actor.UnequipInventoryItem,
                    actor,
                    itemId
                )
                if not unequipOk or result == false then
                    failedCount = failedCount + 1
                    log("Uyku oncesi esya cikarilamadi: tur="
                        .. (isWeapon and "weapon" or "armor")
                        .. ", class=" .. tostring(item.class)
                        .. ", slot=" .. tostring(slot)
                        .. ", item=" .. tostring(itemId)
                        .. ", sonuc=" .. tostring(result))
                else
                    log("Uyku oncesi esya cikarildi: tur="
                        .. (isWeapon and "weapon" or "armor")
                        .. ", class=" .. tostring(item.class)
                        .. ", slot=" .. tostring(slot)
                        .. ", item=" .. tostring(itemId))
                end
            end
        end
    end

    log("Uyku oncesi ekipman cikarimi tamamlandi: entity="
        .. tostring(entity.id) .. ", hedef esya=" .. tostring(itemCount)
        .. ", hata=" .. tostring(failedCount))
    return failedCount == 0
end

function CastleUtils.MarkBedWalkInterrupted(npcWuid)
    if npcWuid == nil then return false end
    local key = tostring(npcWuid)
    local state = CastleUtils.bedWalkStates[key]
    if state ~= "completed" and state ~= "meal_pending"
        and state ~= "meal_ready" and state ~= "eating" then
        CastleUtils.bedWalkStates[key] = "idle"
    end
    return true
end

function CastleUtils.GetPlayerMasterChest()
    log("Oyuncu ana sandigi araniyor.")
    for _, stash in pairs(System.GetEntitiesByClass("Stash") or {}) do
        local name = stash.GetName and stash:GetName()
        if name and string.find(string.lower(name), "playermasterchest", 1, true) then
            return stash
        end
    end

    log("Oyuncu ana sandigi bulunamadi.")
    return nil
end

function CastleUtils.AssignPlayerChest()
    log("Oyuncu sandigi baglantisi kuruluyor.")

    local chest
    local ok, err = pcall(function()
        for _, stash in pairs(System.GetEntitiesByClass("Stash") or {}) do
            local name = stash.GetName and stash:GetName()
            if name and string.find(name, CastleUtils._targetChestName, 1, true) then
                chest = stash
                break
            end
        end
    end)

    if not ok then
        log("Hedef sandik aranirken hata: " .. tostring(err))
        return
    end
    if not chest then
        log("Hedef sandik bulunamadi.")
        return
    end

    local masterOk, master = pcall(CastleUtils.GetPlayerMasterChest)
    if not masterOk or not master then
        log("Oyuncu ana sandigi bulunamadi: " .. tostring(master))
        return
    end

    local linkOk, linkErr = pcall(function()
        chest:CreateLink("masterStash", master.id)
    end)
    if not linkOk then
        log("Sandik baglantisi kurulamadi: " .. tostring(linkErr))
        return
    end

    chest.GetInventoryToOpen = function(self)
        local masterInventory
        pcall(function()
            masterInventory = self.stash:GetMasterInventory()
        end)

        if masterInventory and masterInventory ~= 0 then
            local valid = false
            pcall(function()
                valid = Framework.IsValidWUID(masterInventory) and true or false
            end)
            if valid then return masterInventory end
        end

        local masterChest = CastleUtils.GetPlayerMasterChest()
        if masterChest and masterChest.GetInventoryToOpen then
            local inventoryId
            pcall(function()
                inventoryId = masterChest:GetInventoryToOpen()
            end)
            if inventoryId and inventoryId ~= 0 then return inventoryId end
        end
        return self.inventoryId
    end

    CastleUtils.TestSharedChest = chest
    log("Sandik baglantisi tamamlandi.")
end

function CastleUtils.OnGameplayStarted()
    if System.GetEntityIdByName("trosecko") then
        for _, entityName in ipairs(CastleUtils.removeEnts) do
            local entityId = System.GetEntityIdByName(entityName)
            if entityId then
                System.RemoveEntity(entityId)
            end
        end
    end
    CastleUtils.ResetBedAssignments()
    CastleUtils.restoredNpcNames = {}
    CastleUtils._restoreInProgress = true
    CastleUtils.RefreshBeds()
    CastleUtils.ReservePersistentBeds()
    CastleUtils.ReserveMealBenches()
    CastleUtils.LogPersistentNpcState()
    CastleUtils.AssignPlayerChest()
    Script.SetTimerForFunction(
        1,
        "nebakovrising.CastleUtils.RestoreManagedNpcs",
        30
    )
    Script.SetTimerForFunction(
        10000,
        "nebakovrising.CastleUtils.SnapshotManagedNpcPositions"
    )
    Script.SetTimerForFunction(
        5000,
        "nebakovrising.CastleUtils.EnsurePlayerEquipmentEquipped"
    )
end

function CastleUtils.AddTriggerItem()
    local currentPlayer = nebakovrising.Utils.GetPlayer()
    local inventory = currentPlayer and currentPlayer.inventory
    if not inventory then
        log("Envanter hazir degil; tekrar denenecek.")
        Script.SetTimerForFunction(1000, "nebakovrising.CastleUtils.AddTriggerItem")
        return
    end

    local ok, result = pcall(function()
        return inventory:CreateItem(CastleUtils._triggerItemGuid, 1, 1)
    end)
    log("Tetikleyici esya olusturma: ok=" .. tostring(ok) .. ", sonuc=" .. tostring(result))
    Script.SetTimerForFunction(1000, "nebakovrising.CastleUtils.RemoveTriggerItem")
end

function CastleUtils.RemoveTriggerItem()
    local currentPlayer = nebakovrising.Utils.GetPlayer()
    local inventory = currentPlayer and currentPlayer.inventory
    if not inventory then
        log("Tetikleyici esya silinemedi: envanter kullanilamiyor.")
        return
    end

    local ok, result = pcall(function()
        return inventory:DeleteItemOfClass(CastleUtils._triggerItemGuid, 1)
    end)
    log("Tetikleyici esya silme: ok=" .. tostring(ok) .. ", sonuc=" .. tostring(result))
end

if AnimDoor then
    CastleUtils._originalGetDoorActions = CastleUtils._originalGetDoorActions or AnimDoor.GetActions
    CastleUtils._originalOnDoorUsed = CastleUtils._originalOnDoorUsed or AnimDoor.OnUsed
    CastleUtils._originalSpawnSuspiciousVolume = CastleUtils._originalSpawnSuspiciousVolume or AnimDoor.SpawnSuspiciousVolume

    if CastleUtils._originalGetDoorActions then
        function AnimDoor:GetActions(user, firstFast)
            local entityName = EntityUtils.GetName(self)
            if CastleUtils.noLockEnts[entityName] then
                self.bLocked = false
            end
            return CastleUtils._originalGetDoorActions(self, user, firstFast)
        end
    end

    if CastleUtils._originalOnDoorUsed then
        function AnimDoor:OnUsed(user, slot)
            local entityName = EntityUtils.GetName(self)
            if CastleUtils.noLockEnts[entityName] then
                self.bLocked = false
            end
            return CastleUtils._originalOnDoorUsed(self, user, slot)
        end
    end

    if CastleUtils._originalSpawnSuspiciousVolume then
        function AnimDoor:SpawnSuspiciousVolume()
            local entityName = EntityUtils.GetName(self)
            if not CastleUtils.noLockEnts[entityName] then
                return CastleUtils._originalSpawnSuspiciousVolume(self)
            end
        end
    end
end

if Stash then
    CastleUtils._originalGetStashActions = CastleUtils._originalGetStashActions or Stash.GetActions
    CastleUtils._originalStashOpen = CastleUtils._originalStashOpen or Stash.Open

    if CastleUtils._originalGetStashActions then
        function Stash:GetActions(user, firstFast)
            local entityName = EntityUtils.GetName(self)
            if CastleUtils.noLockEnts[entityName] then
                self.bLocked = false
            end
            return CastleUtils._originalGetStashActions(self, user, firstFast)
        end
    end

    if CastleUtils._originalStashOpen then
        function Stash:Open(user)
            local entityName = EntityUtils.GetName(self)
            local originalProduceSound = Crime.ProduceAiSoundOnDudePosition

            if CastleUtils.noLockEnts[entityName] then
                Crime.ProduceAiSoundOnDudePosition = function() end
            end

            local ok, result = pcall(CastleUtils._originalStashOpen, self, user)
            Crime.ProduceAiSoundOnDudePosition = originalProduceSound
            if not ok then
                error(result)
            end
            return result
        end
    end
end

if UIAction and UIAction.RegisterEventSystemListener and not CastleUtils._gameplayListenerRegistered then
    UIAction.RegisterEventSystemListener(CastleUtils, "System", "OnGameplayStarted", "OnGameplayStarted")
    CastleUtils._gameplayListenerRegistered = true
end

log("Yuklendi.")