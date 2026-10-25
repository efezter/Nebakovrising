-- Filename identities stored in the existing serialized NPC save store.
nebakovrising.Voices=nebakovrising.Voices or {}
local V=nebakovrising.Voices
local function castle() return nebakovrising.CastleUtils end
local function log(s) nebakovrising.Utils.Log("[Voices] "..s) end
local function valid(s)
    return type(s)=="string" and #s<=80 and string.lower(s):match("^guard[%w_-]*%.wav$")~=nil
end
function V.Reconcile()
    local records,state=castle().VoiceStore(false)
    if not records or not state or not state.ids or #state.ids==0 then return end
    V.ids,V.fallback,V.available=state.ids,state.fallback,{}
    for _,id in ipairs(V.ids) do V.available[id]=true end
    local used,pending={},{}
    for name,record in pairs(records) do
        local role=type(record)=="table" and record.managed and nebakovrising.Roles.Resolve(name)
        if role and role.bedPool=="guard" then
            local entityId=System.GetEntityIdByName(name)
            local entity=entityId and System.GetEntity(entityId)
            local dead=false
            if entity and entity.actor and type(entity.actor.IsDead)=="function" then
                local ok,value=pcall(entity.actor.IsDead,entity.actor);dead=ok and value==true
            end
            if dead then record.voicesampleid=nil
            elseif record.voicesampleid then used[record.voicesampleid]=true
            elseif entity then pending[#pending+1]={name=name,record=record} end
        end
    end
    table.sort(pending,function(a,b) return a.name<b.name end)
    for _,item in ipairs(pending) do
        local free={}
        for _,id in ipairs(V.ids) do if not used[id] then free[#free+1]=id end end
        local id=#free>0 and free[math.random(#free)] or V.fallback
        item.record.voicesampleid=id;used[id]=true;log(item.name.." -> "..id)
    end
end
function V.Apply(csv,fallback)
    if type(csv)~="string" or #csv>10400 or not valid(fallback) then return false end
    local ids,seen={},{}
    for id in csv:gmatch("[^,]+") do
        if not valid(id) or seen[string.lower(id)] then return false end
        ids[#ids+1]=id;seen[string.lower(id)]=true
    end
    if #ids==0 or #ids>128 or table.concat(ids,",")~=csv or not seen[string.lower(fallback)] then return false end
    local records,state=castle().VoiceStore(true)
    if not records or not state then return false end
    state.ids,state.fallback=ids,fallback;V.Reconcile()
    log("Ses havuzu: "..#ids..", fallback="..fallback);return true
end
function V.Get(name)
    local records=castle().VoiceStore(false)
    local assigned=records and records[name] and records[name].voicesampleid
    if not assigned then return nil end
    return V.available and V.available[assigned] and assigned or V.fallback
end
function V.Reset()
    V.ids,V.fallback,V.available=nil,nil,nil;V.Reconcile()
end
function V.Status()
    local records=castle().VoiceStore(false)
    log("Sample sayisi="..tostring(V.ids and #V.ids or 0))
    for name,record in pairs(records or {}) do
        if type(record)=="table" and record.voicesampleid then log(name.." -> "..record.voicesampleid) end
    end
end
if not V.commandsRegistered then
    System.AddCCommand("nebakov_voice_assignments","nebakovrising.Voices.Status()","Kalici guard ses atamalarini goster")
    V.commandsRegistered=true
end
