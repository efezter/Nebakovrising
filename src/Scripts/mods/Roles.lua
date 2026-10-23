-- ============================================================
-- Scripts/mods/Roles.lua
-- NPC rol kayit defteri. Her rol Scripts/mods/roles/*.lua icinde
-- Roles.Register ile tanimlanir; Spawner, NpcInteraction ve CastleUtils
-- rol ayarlarini buradan okur.
--
-- Rol alanlari:
--   id, label, namePrefix, command, commandDescription
--   faction, clothingPreset, clothingItemIds (dogrulama icin, opsiyonel)
--   weaponPreset, weaponClassId (opsiyonel; yalniz bu silah sinifi tutulur)
--   weaponDrawContext (bool), bedPool (CastleUtils.bedPools anahtari)
--   interaction = { label, inventory, equipTransferred, extraActions }
--   appearancePool (AppearancePools.lua anahtari; varsayilan: rol id)
--   patrol = { waitMin, waitMax, crossbow, fixed = {selector}, roaming = { {weight, points = {selector}} } }
--            (yemekten sonra patrol sistemi; bkz. CastleUtils.AssignPatrolPoint)
--   behaviors   = { { id, interrupt, poll } }  -- role ozel davranislar
--   onSpawned(entity, name)
-- ============================================================

nebakovrising = nebakovrising or {}
nebakovrising.Roles = nebakovrising.Roles or {}
local Roles = nebakovrising.Roles

Roles.defaultRoleId = "guard_melee"
Roles._defs = Roles._defs or {}
Roles._order = Roles._order or {}
Roles._byEntityName = Roles._byEntityName or {}

local function log(message)
    if nebakovrising.Utils and nebakovrising.Utils.Log then
        nebakovrising.Utils.Log("[Roles] " .. tostring(message))
    elseif System and System.LogAlways then
        System.LogAlways("[nebakovrising] [Roles] " .. tostring(message))
    end
end

function Roles.Register(def)
    if type(def) ~= "table" or type(def.id) ~= "string" or def.id == ""
        or type(def.namePrefix) ~= "string" or def.namePrefix == "" then
        log("Rol kaydedilemedi: id veya namePrefix gecersiz.")
        return false
    end
    if not Roles._defs[def.id] then
        Roles._order[#Roles._order + 1] = def.id
    end
    Roles._defs[def.id] = def
    return true
end

function Roles.Get(roleId)
    return roleId and Roles._defs[roleId] or nil
end

function Roles.GetDefault()
    return Roles._defs[Roles.defaultRoleId]
end

function Roles.List()
    local list = {}
    for _, roleId in ipairs(Roles._order) do
        list[#list + 1] = Roles._defs[roleId]
    end
    return list
end

function Roles.Assign(entityName, roleId)
    if type(entityName) == "string" and Roles._defs[roleId] then
        Roles._byEntityName[entityName] = roleId
        return true
    end
    return false
end

-- Cozum sirasi: bellek -> save kaydi -> isim oneki -> varsayilan rol.
-- Rolu olmayan eski kayitlar varsayilan (guard_melee) role duser.
function Roles.Resolve(entityName)
    if type(entityName) ~= "string" then
        return Roles.GetDefault()
    end

    local cached = Roles._defs[Roles._byEntityName[entityName]]
    if cached then return cached end

    local castle = nebakovrising.CastleUtils
    if castle and castle.GetManagedNpcRole then
        local savedRole = Roles._defs[castle.GetManagedNpcRole(entityName)]
        if savedRole then
            Roles._byEntityName[entityName] = savedRole.id
            return savedRole
        end
    end

    for _, roleId in ipairs(Roles._order) do
        local def = Roles._defs[roleId]
        if string.sub(entityName, 1, #def.namePrefix) == def.namePrefix then
            Roles._byEntityName[entityName] = def.id
            return def
        end
    end

    return Roles.GetDefault()
end

-- switch.xml dongusunden cagrilir. Hazir bir role ozel davranis varsa
-- interrupt adini, yoksa nil dondurur.
function Roles.PollBehavior(entity, context)
    if not entity or not entity.GetName then return nil end
    local nameOk, entityName = pcall(entity.GetName, entity)
    if not nameOk then return nil end

    local role = Roles.Resolve(entityName)
    if not role or type(role.behaviors) ~= "table" then return nil end

    for _, behavior in ipairs(role.behaviors) do
        if type(behavior.poll) == "function" and type(behavior.interrupt) == "string" then
            local ok, ready = pcall(behavior.poll, entity, context or {})
            if ok and ready then
                return behavior.interrupt
            end
        end
    end
    return nil
end
