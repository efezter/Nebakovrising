-- ============================================================
-- Scripts/mods/NpcInteraction.lua
-- Modun spawn ettigi muhafizlara envanter aktarim etkilesimi ekler.
-- ============================================================

nebakovrising = nebakovrising or {}
nebakovrising.NpcInteraction = nebakovrising.NpcInteraction or {}
NpcInteraction = nebakovrising.NpcInteraction

local Interaction = NpcInteraction

local function log(message)
    if nebakovrising.Utils and nebakovrising.Utils.Log then
        nebakovrising.Utils.Log("[NpcInteraction] " .. tostring(message))
    elseif System and System.LogAlways then
        System.LogAlways("[nebakovrising] [NpcInteraction] " .. tostring(message))
    end
end

local function getEntityWuid(entity)
    if XGenAIModule and type(XGenAIModule.GetMyWUID) == "function" then
        local ok, wuid = pcall(XGenAIModule.GetMyWUID, entity)
        if ok then
            return wuid
        end
        log("Entity WUID okunamadi: " .. tostring(wuid))
    end
    return nil
end

local function getInventoryId(entity)
    if not entity or not entity.inventory
        or type(entity.inventory.GetId) ~= "function" then
        return nil
    end
    local ok, inventoryId = pcall(entity.inventory.GetId, entity.inventory)
    if ok then
        return inventoryId
    end
    log("Inventory ID okunamadi: " .. tostring(inventoryId))
    return nil
end

local function readInventoryOwner(inventoryId)
    if not inventoryId or not EntityModule
        or type(EntityModule.GetInventoryOwner) ~= "function" then
        return nil, "EntityModule.GetInventoryOwner API'si kullanilamiyor"
    end

    local ok, owner = pcall(EntityModule.GetInventoryOwner, inventoryId)
    if not ok then
        return nil, "cagri hatasi: " .. tostring(owner)
    end
    return owner, "ok"
end

local function getInventoryItemIds(entity)
    if not entity or not entity.inventory
        or type(entity.inventory.GetInventoryTable) ~= "function" then
        return nil
    end

    local ok, inventoryItems = pcall(entity.inventory.GetInventoryTable, entity.inventory)
    if not ok or type(inventoryItems) ~= "table" then
        log("Envanter esyalari okunamadi: " .. tostring(inventoryItems))
        return nil
    end

    local itemIds = {}
    for _, itemId in pairs(inventoryItems) do
        itemIds[tostring(itemId)] = itemId
    end
    return itemIds
end

local function logItemOwner(itemId, recipient, expectedOwner)
    if not ItemManager or type(ItemManager.GetItemOwner) ~= "function" then
        log("Esya sahipligi okunamadi: ItemManager.GetItemOwner API'si kullanilamiyor; item="
            .. tostring(itemId) .. ", hedef=" .. tostring(recipient))
        return
    end

    local ok, owner = pcall(ItemManager.GetItemOwner, itemId)
    if not ok then
        log("Esya sahipligi okunamadi: item=" .. tostring(itemId)
            .. ", hedef=" .. tostring(recipient)
            .. ", hata=" .. tostring(owner))
        return
    end

    log("Transfer sonrasi esya sahibi: item=" .. tostring(itemId)
        .. ", hedef=" .. tostring(recipient)
        .. ", ownerWuid=" .. tostring(owner)
        .. ", beklenenWuid=" .. tostring(expectedOwner))
end

local function logInventoryOwner(label, inventoryId, expectedOwner, previousOwner)
    local owner, status = readInventoryOwner(inventoryId)
    log("Transfer sonrasi envanter sahibi: taraf=" .. tostring(label)
        .. ", inventory=" .. tostring(inventoryId)
        .. ", oncekiOwnerWuid=" .. tostring(previousOwner)
        .. ", ownerWuid=" .. tostring(owner)
        .. ", beklenenWuid=" .. tostring(expectedOwner)
        .. ", durum=" .. tostring(status))
end

function Interaction.LogTransferOwnership(entity)
    local snapshot = entity and entity._nebakovTransferOwnershipSnapshot
    if not entity or type(snapshot) ~= "table" then
        return
    end
    entity._nebakovTransferOwnershipSnapshot = nil

    local npcItemIds = getInventoryItemIds(entity)
    local player = snapshot.player
    local playerItemIds = getInventoryItemIds(player)
    if not npcItemIds or not playerItemIds then
        log("Transfer sahipligi karsilastirilamadi: aktarim sonrasi envanter snapshot'i okunamadi.")
        return
    end

    local npcWuid = snapshot.npcWuid
    local playerWuid = snapshot.playerWuid
    logInventoryOwner(
        "muhafiz",
        snapshot.npcInventoryId,
        npcWuid,
        snapshot.npcInventoryOwner
    )
    logInventoryOwner(
        "oyuncu",
        snapshot.playerInventoryId,
        playerWuid,
        snapshot.playerInventoryOwner
    )

    local playerReceived = {}
    for itemKey, itemId in pairs(snapshot.npcItemIds) do
        if not npcItemIds[itemKey] and playerItemIds[itemKey] then
            playerReceived[#playerReceived + 1] = itemId
        end
    end

    local npcReceived = {}
    for itemKey, itemId in pairs(snapshot.playerItemIds or {}) do
        if not playerItemIds[itemKey] and npcItemIds[itemKey] then
            npcReceived[#npcReceived + 1] = itemId
        end
    end

    log("Transfer sahiplik farki: oyuncunun aldigi esya adedi="
        .. tostring(#playerReceived) .. ", muhafizin aldigi esya adedi="
        .. tostring(#npcReceived))
    if #playerReceived > 0 or #npcReceived > 0 then
        local castleUtils = nebakovrising.CastleUtils
        if castleUtils and castleUtils.MarkNpcEquipmentModified then
            castleUtils.MarkNpcEquipmentModified(entity)
        end
    end

    for _, itemId in ipairs(playerReceived) do
        logItemOwner(itemId, "oyuncu", playerWuid)
    end
    for _, itemId in ipairs(npcReceived) do
        logItemOwner(itemId, "muhafiz", npcWuid)
    end
    if #playerReceived == 0 and #npcReceived == 0 then
        log("Envanter ID farkinda aktarilan esya bulunamadi; stack birlesmesi veya callback zamani kontrol edilmeli.")
    end
end

local function getTransferredItemDetails(itemId)
    if not ItemManager or type(ItemManager.GetItem) ~= "function" then
        log("Aktarilan esya okunamadi: ItemManager.GetItem API'si kullanilamiyor.")
        return nil
    end

    local ok, item = pcall(ItemManager.GetItem, itemId)
    if not ok or type(item) ~= "table" or type(item.class) ~= "string" then
        log("Aktarilan esya sinifi okunamadi: " .. tostring(itemId)
            .. ", sonuc=" .. tostring(item))
        return nil
    end

    local classKey = string.lower(string.gsub(item.class, "%-", ""))
    local equipmentData = nebakovrising.EquipmentData
    local indexedItem = equipmentData and equipmentData.items
        and equipmentData.items[classKey]

    return {
        id = itemId,
        class = item.class,
        slot = indexedItem and indexedItem.slot,
        slotOrder = indexedItem and equipmentData.slotOrder[indexedItem.slot] or 999,
    }
end

function Interaction.ApplyTransferredEquipment(entity)
    local previousItemIds = entity and entity._nebakovInventorySnapshot
    if not entity or type(previousItemIds) ~= "table" then
        return
    end
    entity._nebakovInventorySnapshot = nil

    local currentItemIds = getInventoryItemIds(entity)
    if not currentItemIds then
        return
    end

    local transferredItems = {}
    for itemKey, itemId in pairs(currentItemIds) do
        if not previousItemIds[itemKey] then
            local details = getTransferredItemDetails(itemId)
            if details then
                transferredItems[#transferredItems + 1] = details
            end
        end
    end

    if #transferredItems == 0 then
        log("Muhafiza yeni esya aktarilmadi; kusanma gerekmiyor.")
        return
    end

    table.sort(transferredItems, function(left, right)
        if left.slotOrder ~= right.slotOrder then
            return left.slotOrder < right.slotOrder
        end
        return tostring(left.class) < tostring(right.class)
    end)

    local actor = entity.actor
    if not actor or type(actor.EquipInventoryItem) ~= "function" then
        log("Aktarilan esyalar kusanilamadi: EquipInventoryItem API'si kullanilamiyor.")
        return
    end
    if (actor.IsDead and actor:IsDead())
        or (actor.IsUnconscious and actor:IsUnconscious()) then
        log("Aktarilan esyalar kusanilmadi: muhafiz olu veya bilincsiz.")
        return
    end

    local equippedCalls = 0
    for _, item in ipairs(transferredItems) do
        local ok, result = pcall(actor.EquipInventoryItem, actor, item.id)
        if ok and result ~= false then
            equippedCalls = equippedCalls + 1
        else
            log("Yeni aktarilan esya kusanilamadi: sinif=" .. tostring(item.class)
                .. ", slot=" .. tostring(item.slot)
                .. ", sonuc=" .. tostring(result))
        end
    end

    log("Yeni aktarilan esyalar icin kusanma cagrisi: "
        .. tostring(equippedCalls) .. "/" .. tostring(#transferredItems))
end

function Interaction.OpenInventory(npc, user)
    if not npc or not npc.id then
        log("Envanter acilamadi: NPC entity'si bulunamadi.")
        return
    end
    if not npc.inventory or type(npc.inventory.GetId) ~= "function" then
        log("Envanter acilamadi: NPC inventory ID'si bulunamadi.")
        return
    end
    if not user or not user.actor then
        log("Envanter acilamadi: etkilesim kuran actor bulunamadi.")
        return
    end
    if type(user.actor.OpenItemTransferStore) ~= "function" then
        log("Envanter acilamadi: OpenItemTransferStore API'si kullanilamiyor.")
        return
    end

    local inventoryId = npc.inventory:GetId()
    if not inventoryId or inventoryId == 0 then
        log("Envanter acilamadi: NPC inventory ID'si gecersiz.")
        return
    end

    local previousItemIds = getInventoryItemIds(npc)
    if not previousItemIds then
        log("Envanter acilamadi: aktarim oncesi envanter snapshot'i okunamadi.")
        return
    end
    npc._nebakovInventorySnapshot = previousItemIds
    local playerInventoryId = getInventoryId(user)
    local npcInventoryOwner, npcOwnerStatus = readInventoryOwner(inventoryId)
    local playerInventoryOwner, playerOwnerStatus = readInventoryOwner(playerInventoryId)
    npc._nebakovTransferOwnershipSnapshot = {
        npcInventoryId = inventoryId,
        playerInventoryId = playerInventoryId,
        npcItemIds = previousItemIds,
        playerItemIds = getInventoryItemIds(user),
        player = user,
        npcWuid = getEntityWuid(npc),
        playerWuid = getEntityWuid(user),
        npcInventoryOwner = npcInventoryOwner,
        playerInventoryOwner = playerInventoryOwner,
    }

    log("Muhafiz envanter aktarimi aciliyor: NPC=" .. tostring(npc.id)
        .. ", inventory=" .. tostring(inventoryId)
        .. ", oyuncu=" .. tostring(user.id))
    log("Sahiplik tani API'leri: GetItemOwner="
        .. tostring(ItemManager and type(ItemManager.GetItemOwner) == "function")
        .. ", SetItemOwner="
        .. tostring(ItemManager and type(ItemManager.SetItemOwner) == "function")
        .. ", GetInventoryOwner="
        .. tostring(EntityModule and type(EntityModule.GetInventoryOwner) == "function"))
    log("Transfer oncesi envanter sahibi: muhafiz="
        .. tostring(npcInventoryOwner) .. " (" .. tostring(npcOwnerStatus) .. ")"
        .. ", oyuncu=" .. tostring(playerInventoryOwner) .. " (" .. tostring(playerOwnerStatus) .. ")")
    local ok, result = pcall(
        user.actor.OpenItemTransferStore,
        user.actor,
        npc.id,
        inventoryId,
        "",
        ""
    )
    if not ok or result == false then
        npc._nebakovInventorySnapshot = nil
        npc._nebakovTransferOwnershipSnapshot = nil
        log("Envanter aktarimi baslatilamadi: " .. tostring(result))
    end
end

function Interaction.Inject(entity)
    if not entity then
        log("Etkilesim eklenemedi: NPC entity yok.")
        return false
    end

    if entity._nebakovInteractionInjected
        and entity.GetActions == entity._nebakovInjectedGetActions then
        entity._nebakovManagedGuard = true
        return true
    end

    local originalGetActions = entity.GetActions
        or (BasicAIActions and BasicAIActions.GetActions)
    if type(originalGetActions) ~= "function" then
        log("NPC'nin vanilla GetActions fonksiyonu bulunamadi; olum sonrasi loot etkilesimi korunamayacak.")
        return false
    end

    entity._nebakovInteractionInjected = true
    entity._nebakovManagedGuard = true

    local originalOnInventoryClosed = entity.OnInventoryClosed
    entity.OnInventoryClosed = function(selfEnt, ...)
        if type(originalOnInventoryClosed) == "function" then
            local ok, result = pcall(originalOnInventoryClosed, selfEnt, ...)
            if not ok then
                log("Vanilla envanter kapatma callback'i hata verdi: " .. tostring(result))
            end
        end
        Interaction.LogTransferOwnership(selfEnt)
        Interaction.ApplyTransferredEquipment(selfEnt)
    end

    entity.GetActions = function(selfEnt, userEnt, firstFast)
        local actor = selfEnt.actor
        if not actor
            or (actor.IsDead and actor:IsDead())
            or (actor.IsUnconscious and actor:IsUnconscious()) then
            return originalGetActions(selfEnt, userEnt, firstFast)
        end

        local output = originalGetActions(selfEnt, userEnt, firstFast) or {}
        if firstFast and #output > 0 then
            return output
        end
        if not selfEnt._nebakovManagedGuard then
            return output
        end

        if not AddInteractorAction or not Action or AHT_RELEASE == nil
            or (inr_stashOpen == nil and inr_loot == nil) then
            log("NPC etkilesimleri olusturulamadi: Action API kullanilamiyor.")
            return output
        end

        AddInteractorAction(
            output,
            firstFast,
            Action()
                :hint("@ui_open_stash")
                :hintType(AHT_RELEASE)
                :action("use")
                :uiOrder(1)
                :func(function(_, user)
                    Interaction.OpenInventory(selfEnt, user)
                end)
                :interaction(inr_stashOpen or inr_loot)
        )

        return output
    end
    entity._nebakovInjectedGetActions = entity.GetActions

    return true
end
