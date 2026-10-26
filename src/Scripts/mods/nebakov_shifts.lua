-- Stable guard shifts stored in the existing NPC save records.
nebakovrising.Shifts = nebakovrising.Shifts or {}
local S = nebakovrising.Shifts
S.defaults = {day={wakeHour=8,mealHour=20,sleepHour=0},
    night={wakeHour=19,mealHour=8,sleepHour=11}}
S.assignments = {}

function S.InWindow(hour, first, last)
    if first < last then return hour >= first and hour < last end
    return hour >= first or hour < last
end

local function npcName(value)
    if type(value)=="table" and value.GetName then return value:GetName() end
    if type(value)=="string" and (S.assignments[value] or value:sub(1,14)=="nebakovrising_") then return value end
    if XGenAIModule and type(XGenAIModule.GetEntityByWUID)=="function" then
        local ok,entity=pcall(XGenAIModule.GetEntityByWUID,value)
        if ok and entity and entity.GetName then return entity:GetName() end
    end
    return value and tostring(value)
end

function S.Get(value)
    local name=npcName(value)
    if not name then return "day" end
    if S.assignments[name] then return S.assignments[name] end
    local records=nebakovrising.CastleUtils.ManagedRecords(false)
    local record=records and records[name]
    return record and record.guardShift=="night" and "night" or "day"
end

function S.Schedule(value)
    local group=S.Get(value)
    local schedules=nebakovrising.Config.shiftSchedules or S.defaults
    return schedules[group],group
end

function S.AfterDuty(value,hour)
    local schedule=S.Schedule(value)
    return S.InWindow(hour,schedule.mealHour,schedule.sleepHour)
end

function S.NightCount(total)
    if total<2 then return 0 end
    if total<4 then return 1 end
    return math.ceil(total*0.30)
end

local function shuffle(list)
    for i=#list,2,-1 do
        local j=math.random(i);list[i],list[j]=list[j],list[i]
    end
end

function S.Reconcile()
    local castle=nebakovrising.CastleUtils
    if castle._restoreInProgress then return end -- wait for legacy registration to finish
    local records=castle.ManagedRecords(false) or {}
    local candidates,day,night,fresh={},{},{},{}
    for name,record in pairs(records) do
        local roles=nebakovrising.Roles
        local role=type(record)=="table" and record.managed and roles.Resolve(name)
        local id=System.GetEntityIdByName(name)
        local entity=id and System.GetEntity(id)
        local dead=false
        if entity and entity.actor and type(entity.actor.IsDead)=="function" then
            local ok,value=pcall(entity.actor.IsDead,entity.actor);dead=ok and value==true
        end
        -- An unloaded guard still belongs to the garrison.
        if role and role.bedPool=="guard" and role.patrol and not dead then
            candidates[#candidates+1]=name
            local list=record.guardShift=="night" and night or record.guardShift=="day" and day or fresh
            list[#list+1]=name
        end
    end
    table.sort(candidates);table.sort(day);table.sort(night);table.sort(fresh)
    local wanted=S.NightCount(#candidates)
    shuffle(fresh)
    for _,name in ipairs(fresh) do
        local group=#night<wanted and "night" or "day"
        records[name].guardShift=group
        local list=group=="night" and night or day;list[#list+1]=name
    end
    local function transfer(from,to,group)
        shuffle(from)
        local name=table.remove(from)
        records[name].guardShift=group
        records[name].eveningMealDone=nil
        castle.eveningMealSchedule[name]=nil
        local id=System.GetEntityIdByName(name)
        local entity=id and System.GetEntity(id)
        if entity and entity.this then
            castle.npcWakeSlots[tostring(entity.this.id)]=nil
        end
        to[#to+1]=name
    end
    while #night<wanted do transfer(day,night,"night") end
    while #night>wanted do transfer(night,day,"day") end
    local assignments={}
    for _,name in ipairs(candidates) do assignments[name]=records[name].guardShift end
    S.assignments=assignments
end

function S.LogStatus()
    S.Reconcile()
    local names={};for name in pairs(S.assignments) do names[#names+1]=name end
    table.sort(names)
    local night=0;for _,group in pairs(S.assignments) do if group=="night" then night=night+1 end end
    nebakovrising.Utils.Log("[Shifts] total="..#names..", day="..(#names-night)..", night="..night)
    for _,name in ipairs(names) do
        local t,group=S.Schedule(name)
        nebakovrising.Utils.Log("[Shifts] "..name.." = "..group..", wake="..t.wakeHour
            ..", dutyEnd="..t.mealHour..", sleep="..t.sleepHour)
    end
end
