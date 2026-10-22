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

local function getRole(entityName)
    return nebakovrising.Roles.Resolve(entityName)
end

local function verifyPresetItems(entity, itemClassIds)
    if type(itemClassIds) ~= "table" then
        return
    end
    if not entity.inventory or type(entity.inventory.FindItem) ~= "function" then
        nebakovrising.Utils.Log("NPC preset esyalari dogrulanamadi: "
            .. "Inventory.FindItem API'si yok.")
        return
    end

    for _, itemClassId in ipairs(itemClassIds) do
        local ok, itemId = pcall(function()
            return entity.inventory:FindItem(itemClassId)
        end)
        if not ok then
            nebakovrising.Utils.Log("NPC preset esyasi sorgulanamadi: "
                .. tostring(itemClassId) .. ", hata=" .. tostring(itemId))
        else
            nebakovrising.Utils.Log("NPC preset esyasi dogrulamasi: class="
                .. tostring(itemClassId) .. ", item=" .. tostring(itemId))
        end
    end
end

local function applyClothingPreset(entity, role)
    if not entity or not entity.actor then
        nebakovrising.Utils.Log("NPC kiyafet preset'i uygulanamadi: actor bulunamadi.")
        return false
    end

    local preset = role and role.clothingPreset
    if type(preset) ~= "string" or preset == "" then
        nebakovrising.Utils.Log("NPC kiyafet preset'i uygulanamadi: preset GUID bos.")
        return false
    end
    if type(entity.actor.EquipClothingPreset) ~= "function" then
        nebakovrising.Utils.Log("NPC kiyafet preset'i uygulanamadi: "
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
        nebakovrising.Utils.Log("NPC kiyafet preset cagrisi hata verdi: "
            .. "entity=" .. tostring(entity.id) .. ", preset=" .. preset
            .. ", sonuc=" .. tostring(result))
        return false
    end

    entity._nebakovBaseClothingPreset = preset
    nebakovrising.Utils.Log("NPC kiyafet preset cagrisi tamamlandi: "
        .. "entity=" .. tostring(entity.id) .. ", preset=" .. preset)
    verifyPresetItems(entity, role.clothingItemIds)
    return true
end

-- Rolun weaponPreset'i uygulanir; weaponClassId varsa yalnizca o silah sinifi
-- envanterde tutulur (diger silahlar kaldirilir).
local function applyWeapon(entity, role)
    if not entity or not entity.actor then
        nebakovrising.Utils.Log("NPC silahi uygulanamadi: actor bulunamadi.")
        return false
    end
    local weaponPreset = role and role.weaponPreset
    local itemClassId = role and role.weaponClassId
    if not weaponPreset and not itemClassId then
        return true
    end

    local presetApplied = false
    if type(weaponPreset) == "string" and weaponPreset ~= ""
        and type(entity.actor.EquipWeaponPreset) == "function" then
        local presetOk, presetResult = pcall(entity.actor.EquipWeaponPreset, entity.actor, weaponPreset)
        if presetOk and presetResult ~= false then
            presetApplied = true
            nebakovrising.Utils.Log("NPC silah preset'i uygulandi: entity=" .. tostring(entity.id)
                .. ", preset=" .. weaponPreset)
        else
            nebakovrising.Utils.Log("NPC silah preset'i uygulanamadi: preset=" .. weaponPreset
                .. ", sonuc=" .. tostring(presetResult))
        end
    end
    if not itemClassId then
        return presetApplied
    end

    local inventory = entity.inventory
    if not inventory or type(inventory.GetInventoryTable) ~= "function"
        or type(inventory.FindItem) ~= "function"
        or type(inventory.CreateItem) ~= "function"
        or type(inventory.DeleteItemOfClass) ~= "function" then
        nebakovrising.Utils.Log("NPC silahi uygulanamadi: envanter API'leri kullanilamiyor.")
        return presetApplied
    end
    if not ItemManager or type(ItemManager.GetItem) ~= "function" then
        nebakovrising.Utils.Log("NPC silahi uygulanamadi: ItemManager.GetItem API'si kullanilamiyor.")
        return presetApplied
    end
    if type(entity.actor.EquipInventoryItem) ~= "function"
        or type(entity.actor.UnequipInventoryItem) ~= "function" then
        nebakovrising.Utils.Log("NPC silahi uygulanamadi: Actor ekipman API'leri kullanilamiyor.")
        return presetApplied
    end
    local equipmentData = nebakovrising.EquipmentData
    if not equipmentData or type(equipmentData.weaponClasses) ~= "table" then
        nebakovrising.Utils.Log("NPC silahi uygulanamadi: silah sinifi indeksi kullanilamiyor.")
        return presetApplied
    end

    local itemClassKey = string.lower(string.gsub(itemClassId, "%-", ""))
    local ok, inventoryItems = pcall(inventory.GetInventoryTable, inventory)
    if not ok or type(inventoryItems) ~= "table" then
        nebakovrising.Utils.Log("NPC silahi uygulanamadi: envanter okunamadi: "
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
                    nebakovrising.Utils.Log("Eski NPC silahi unequip cagrisi basarisiz; envanterden kaldirma denenecek: class="
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
            nebakovrising.Utils.Log("Eski NPC silahi envanterden silinemedi: class="
                .. tostring(className) .. ", sonuc=" .. tostring(removeResult))
            return false
        end
    end

    local findOk, itemId = pcall(inventory.FindItem, inventory, itemClassId)
    if not findOk then
        nebakovrising.Utils.Log("NPC silahi aranirken hata olustu: "
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
            nebakovrising.Utils.Log("NPC silahi envantere eklenemedi: class="
                .. itemClassId .. ", sonuc=" .. tostring(createResult))
            return false
        end
        findOk, itemId = pcall(inventory.FindItem, inventory, itemClassId)
    end
    if not findOk or not itemId then
        nebakovrising.Utils.Log("NPC silahi envanterde dogrulanamadi: class="
            .. itemClassId .. ", sonuc=" .. tostring(itemId))
        return false
    end

    local equipOk, equipResult = pcall(
        entity.actor.EquipInventoryItem,
        entity.actor,
        itemId
    )
    if not equipOk or equipResult == false then
        nebakovrising.Utils.Log("NPC silahi kusanilamadi: class="
            .. itemClassId .. ", item=" .. tostring(itemId)
            .. ", sonuc=" .. tostring(equipResult))
        return false
    end

    nebakovrising.Utils.Log("NPC silahi olusturuldu ve kusanildi: "
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

function Spawner.ApplyWeaponDrawContext(entityName, retriesLeft)
    retriesLeft = retriesLeft or 0
    local role = getRole(entityName)
    if role and role.weaponDrawContext == false then
        return
    end
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
                    nebakovrising.Utils.Log("NPC silah-cekme tepki baglami uygulandi: "
                        .. tostring(entityName))
                    return
                end
            elseif not setOk and not entity._nebakovWeaponDrawContextWarned then
                entity._nebakovWeaponDrawContextWarned = true
                nebakovrising.Utils.Log("NPC silah-cekme tepki baglami ayarlanamadi: "
                    .. tostring(setResult))
            end
        elseif not entity._nebakovWeaponDrawContextWarned then
            entity._nebakovWeaponDrawContextWarned = true
            nebakovrising.Utils.Log("NPC silah-cekme tepki baglami ayarlanamadi: "
                .. "Soul.SetScriptContext API'si yok.")
        end
    end

    if retriesLeft > 0 and Script and type(Script.SetTimerForFunction) == "function" then
        scheduleEntityCallback(
            500,
            "nebakovrising.Spawner.RetryWeaponDrawContext",
            entityName,
            retriesLeft - 1
        )
    elseif not entity and retriesLeft <= 0 then
        nebakovrising.Utils.Log("NPC silah-cekme tepki baglami ayarlanamadi: entity bulunamadi: "
            .. tostring(entityName))
    elseif entity and not entity._nebakovWeaponDrawContextApplied
        and not entity._nebakovWeaponDrawContextWarned then
        entity._nebakovWeaponDrawContextWarned = true
        nebakovrising.Utils.Log("NPC silah-cekme tepki baglami dogrulanamadi: "
            .. tostring(entityName))
    end
end

function Spawner.RetryWeaponDrawContext(userData)
    local entityName, retriesLeft = readTimerUserData(
        userData,
        "RetryWeaponDrawContext"
    )
    if entityName then
        Spawner.ApplyWeaponDrawContext(entityName, retriesLeft)
    end
end

local function reequipPreservedPlayerItems(entity, entityName, preservedClasses)
    if type(preservedClasses) ~= "table" then
        return false
    end

    local inventory = entity and entity.inventory
    local actor = entity and entity.actor
    if not inventory or type(inventory.GetInventoryTable) ~= "function"
        or not actor or type(actor.EquipInventoryItem) ~= "function"
        or not ItemManager or type(ItemManager.GetItem) ~= "function" then
        nebakovrising.Utils.Log("Oyuncu ekipmani preset sonrasi geri kusanilamadi: "
            .. "envanter veya Actor API'si kullanilamiyor: " .. tostring(entityName))
        return false
    end

    local ok, inventoryItems = pcall(inventory.GetInventoryTable, inventory)
    if not ok or type(inventoryItems) ~= "table" then
        nebakovrising.Utils.Log("Oyuncu ekipmani preset sonrasi geri kusanilamadi: "
            .. "envanter okunamadi: " .. tostring(inventoryItems))
        return false
    end

    local remaining = {}
    for classKey, entry in pairs(preservedClasses) do
        if type(entry) == "table" and type(entry.class) == "string" then
            remaining[classKey] = math.max(0, tonumber(entry.count) or 0)
        end
    end

    local equipmentData = nebakovrising.EquipmentData
    local itemsToEquip = {}
    for _, itemId in pairs(inventoryItems) do
        local itemOk, item = pcall(ItemManager.GetItem, itemId)
        if itemOk and type(item) == "table" and type(item.class) == "string" then
            local classKey = string.lower(string.gsub(item.class, "%-", ""))
            if (remaining[classKey] or 0) > 0 then
                local indexedItem = equipmentData and equipmentData.items
                    and equipmentData.items[classKey]
                itemsToEquip[#itemsToEquip + 1] = {
                    id = itemId,
                    class = item.class,
                    slotOrder = indexedItem and equipmentData.slotOrder
                        and equipmentData.slotOrder[indexedItem.slot] or 999,
                }
                remaining[classKey] = remaining[classKey] - 1
            end
        end
    end

    local missingCount = 0
    for _, count in pairs(remaining) do
        missingCount = missingCount + count
    end
    if missingCount > 0 then
        nebakovrising.Utils.Log("Oyuncu ekipmani preset sonrasi envanterde bulunamadi: NPC="
            .. tostring(entityName) .. ", eksik=" .. tostring(missingCount))
    end

    table.sort(itemsToEquip, function(left, right)
        if left.slotOrder ~= right.slotOrder then
            return left.slotOrder < right.slotOrder
        end
        return tostring(left.class) < tostring(right.class)
    end)

    local equippedCount = 0
    for _, item in ipairs(itemsToEquip) do
        local equipOk, result = pcall(actor.EquipInventoryItem, actor, item.id)
        if equipOk and result ~= false then
            equippedCount = equippedCount + 1
            local castleUtils = nebakovrising.CastleUtils
            if castleUtils and castleUtils.MarkPlayerEquipmentEquipped then
                castleUtils.MarkPlayerEquipmentEquipped(entityName, item.id)
            end
        else
            nebakovrising.Utils.Log("Oyuncu ekipmani preset sonrasi kusanilamadi: NPC="
                .. tostring(entityName) .. ", class=" .. tostring(item.class)
                .. ", sonuc=" .. tostring(result))
        end
    end
    nebakovrising.Utils.Log("Oyuncu ekipmani kiyafet preset'i ardindan geri kusanildi: NPC="
        .. tostring(entityName) .. ", item=" .. tostring(equippedCount))
    return missingCount == 0 and equippedCount == #itemsToEquip
end

function Spawner.ApplyClothingPreset(entityName, retriesLeft, enforceLater)
    retriesLeft = retriesLeft or 0
    local role = getRole(entityName)
    local entity
    if System and type(System.GetEntity) == "function" then
        entity = System.GetEntity(entityName)
    end
    if not entity and System and type(System.GetEntityByName) == "function" then
        entity = System.GetEntityByName(entityName)
    end
    if entity then
        local castleUtils = nebakovrising.CastleUtils
        local preservePlayerEquipment = castleUtils
            and castleUtils.IsNpcEquipmentPreserved
            and castleUtils.IsNpcEquipmentPreserved(entityName)
        local preservedClasses = preservePlayerEquipment
            and castleUtils.GetPreservedPlayerEquipmentClasses
            and castleUtils.GetPreservedPlayerEquipmentClasses(entityName)
        if preservePlayerEquipment and type(preservedClasses) ~= "table" then
            nebakovrising.Utils.Log("NPC ekipman preset'i atlandi; save kaydinda oyuncu esya siniflari bulunamadi: "
                .. tostring(entityName))
            return true
        end

        local applied = applyClothingPreset(entity, role)
        if applied then
            if preservePlayerEquipment then
                applied = reequipPreservedPlayerItems(
                    entity,
                    entityName,
                    preservedClasses
                )
            else
                applyWeapon(entity, role)
            end
        end

        if applied and enforceLater ~= false
            and not entity._nebakovFinalClothingEnforcementScheduled then
            entity._nebakovFinalClothingEnforcementScheduled = true
            if not scheduleEntityCallback(
                1,
                "nebakovrising.Spawner.ReapplyClothingPreset",
                entityName,
                0
            ) then
                entity._nebakovFinalClothingEnforcementScheduled = nil
            end
        end
        if not applied and retriesLeft > 0 then
            scheduleEntityCallback(
                1000,
                "nebakovrising.Spawner.RetryClothingPreset",
                entityName,
                retriesLeft - 1
            )
        end
        return applied
    end

    if retriesLeft > 0 and Script and type(Script.SetTimerForFunction) == "function" then
        scheduleEntityCallback(
            500,
            "nebakovrising.Spawner.RetryClothingPreset",
            entityName,
            retriesLeft - 1
        )
    elseif not entity and retriesLeft <= 0 then
        nebakovrising.Utils.Log("NPC kiyafet preset'i uygulanamadi: entity bulunamadi: "
            .. tostring(entityName))
    end
end

function Spawner.ReapplyClothingPreset(userData)
    local entityName = type(userData) == "table" and userData.entityName or nil
    if type(entityName) ~= "string" then
        nebakovrising.Utils.Log("Gecikmeli kiyafet preset'i tekrar uygulamasi gecersiz veri aldi.")
        return
    end
    Spawner.ApplyClothingPreset(entityName, 0, false)
end

function Spawner.RetryClothingPreset(userData)
    local entityName, retriesLeft = readTimerUserData(
        userData,
        "RetryClothingPreset"
    )
    if entityName then
        Spawner.ApplyClothingPreset(entityName, retriesLeft)
    end
end

function Spawner.ScheduleClothingPreset(entityName, retriesLeft)
    local scheduled = scheduleEntityCallback(
        1000,
        "nebakovrising.Spawner.ApplyClothingPresetDeferred",
        entityName,
        retriesLeft or 0
    )
    if not scheduled then
        nebakovrising.Utils.Log("NPC kiyafet preset'i geciktirilemedi; varsayilan preset korunuyor: "
            .. tostring(entityName))
    end
    return scheduled
end

function Spawner.ApplyClothingPresetDeferred(userData)
    local entityName, retriesLeft = readTimerUserData(
        userData,
        "ApplyClothingPresetDeferred"
    )
    if entityName then
        Spawner.ApplyClothingPreset(entityName, retriesLeft)
    end
end

function Spawner.ApplyFaction(entityName, retriesLeft)
    retriesLeft = retriesLeft or 0
    local role = getRole(entityName)
    local faction = role and role.faction
    if not faction or not AI or type(AI.SetFactionOf) ~= "function" then
        nebakovrising.Utils.Log("NPC faction'i ayarlanamadi: AI.SetFactionOf API'si kullanilamiyor.")
        return
    end

    local entity = System.GetEntityByName(entityName)
    if not entity then
        if retriesLeft > 0 and Script and type(Script.SetTimerForFunction) == "function" then
            scheduleEntityCallback(
                500,
                "nebakovrising.Spawner.RetryFaction",
                entityName,
                retriesLeft - 1
            )
        else
            nebakovrising.Utils.Log("NPC faction'i ayarlanamadi: entity bulunamadi: " .. tostring(entityName))
        end
        return
    end

    local setOk, setResult = pcall(AI.SetFactionOf, entity.id, faction)
    local actualFaction = readFactionState(entity)
    if actualFaction == faction then
        logFactionState(entity, faction)
        return
    end
    if retriesLeft > 0 and Script and type(Script.SetTimerForFunction) == "function" then
        scheduleEntityCallback(
            500,
            "nebakovrising.Spawner.RetryFaction",
            entityName,
            retriesLeft - 1
        )
    else
        nebakovrising.Utils.Log("NPC faction'i dogrulanamadi: " .. tostring(entityName)
            .. ", actual=" .. tostring(actualFaction)
            .. ", set-error=" .. tostring(setOk and "" or setResult))
        logFactionState(entity, faction)
    end
end

function Spawner.RetryFaction(userData)
    local entityName, retriesLeft = readTimerUserData(userData, "RetryFaction")
    if entityName then
        Spawner.ApplyFaction(entityName, retriesLeft)
    end
end

Spawner._lastSoul = Spawner._lastSoul or {}

-- Rolun havuzundan (AppearancePools.lua) rastgele soul GUID'i; bir onceki secimi tekrarlamaz.
function Spawner.PickAppearanceSoul(role)
    local pools = nebakovrising.AppearancePools
    local pool = pools and role and pools[role.appearancePool or role.id]
    if type(pool) ~= "table" or #pool == 0 then return nil end
    local last = Spawner._lastSoul[role.id]
    local index = math.random(#pool)
    if #pool > 1 and pool[index] == last then
        index = index % #pool + 1
    end
    Spawner._lastSoul[role.id] = pool[index]
    return pool[index]
end

-- Ortak spawn akisi. Rol, isimden Roles.Resolve ile cozulur; rol onceden
-- Roles.Assign ile kaydedilmelidir (SpawnRole bunu yapar).
function Spawner.SpawnNpc(name, pos, dir, props)
    local role = getRole(name)
    local spawnProperties = {}
    for key, value in pairs(nebakovrising.Config.npcDefaults or {}) do
        spawnProperties[key] = value
    end
    for key, value in pairs(props or {}) do
        spawnProperties[key] = value
    end
    -- Gorunum soul'a bagli (Storm appearance kurallari); havuzdan rastgele soul sec.
    if not (props and props.guidSharedSoulId) then
        local soul = Spawner.PickAppearanceSoul(role)
        if soul then spawnProperties.guidSharedSoulId = soul end
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
    if role.weaponDrawContext ~= false then
        Spawner.ApplyWeaponDrawContext(name, 12)
    end
    Spawner.ScheduleClothingPreset(name, 12)
    if role.faction then
        if not scheduleEntityCallback(
                500,
                "nebakovrising.Spawner.RetryFaction",
                name,
                12
            ) then
            nebakovrising.Utils.Log("NPC faction'i geciktirilemedi: " .. tostring(name))
        end
    end

    if NpcInteraction and NpcInteraction.Inject then
        local injectOk, injected = pcall(NpcInteraction.Inject, result, role.interaction)
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
    applyClothingPreset(spawnedEntity, role)

    if type(role.onSpawned) == "function" then
        local hookOk, hookResult = pcall(role.onSpawned, spawnedEntity, name)
        if not hookOk then
            nebakovrising.Utils.Log("Rol onSpawned kancasi hata verdi: " .. tostring(hookResult))
        end
    end

    return result
end

function Spawner.SpawnRole(roleId)
    local role = nebakovrising.Roles.Get(roleId)
    if not role then
        nebakovrising.Utils.Log("Bilinmeyen rol: " .. tostring(roleId))
        return nil
    end
    local pos = nebakovrising.Utils.GetPlayerPos()
    if not pos then
        nebakovrising.Utils.Log("Oyuncu bulunamadi, once bir save yukle.")
        return nil
    end
    local name
    repeat
        Spawner._counter = Spawner._counter + 1
        name = role.namePrefix .. Spawner._counter
    until not System.GetEntityIdByName(name)
    nebakovrising.Roles.Assign(name, role.id)
    return Spawner.SpawnNpc(name, { x = pos.x + 2, y = pos.y, z = pos.z })
end
