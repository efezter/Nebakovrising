-- UI names are attached to our Skald identities; never rename runtime entities.
nebakovrising.Names=nebakovrising.Names or {}
local N=nebakovrising.Names
N.pending=N.pending or {}
local function record(entity)
    local castle=nebakovrising.CastleUtils
    local records=castle and castle.VoiceStore and castle.VoiceStore(false)
    return records and records[entity:GetName()]
end
function N.Assign(entity,soulId)
    if not entity then return nil end
    local data=nebakovrising.NpcNamesData
    local properties=entity.Properties or entity.properties or {}
    soulId=soulId or properties.guidSharedSoulId
    local entry=data and type(soulId)=="string" and data.souls[soulId:lower()]
    if not entry and data and entity.soul and type(entity.soul.GetNameStringId)=="function" then
        local ok,key=pcall(entity.soul.GetNameStringId,entity.soul)
        if ok and type(key)=="string" then
            key=key:gsub("^@","")
            if data.keys[key] then entry={name=data.keys[key],key=key} end
        end
    end
    entry=entry or N.pending[entity:GetName()]
    local saved=record(entity)
    if entry then
        N.pending[entity:GetName()]=entry
        if saved then saved.displayName,saved.displayNameKey=entry.name,entry.key end
        return entry.name
    end
    return saved and saved.displayName or nil
end
function N.Get(entity) return N.Assign(entity) or "Guard" end
