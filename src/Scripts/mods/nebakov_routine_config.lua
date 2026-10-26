-- Read once, validated atomically; no filesystem polling on the game thread.
nebakovrising.Routines=nebakovrising.Routines or {}
local R=nebakovrising.Routines
local keys={breakfast=true,eveningMeal=true,patrol=true,wakeStagger=true,eveningMealStagger=true}
function R.Apply(doc)
    if type(doc)~="table" or doc.version~=1 then return false end
    local ranges={}
    for key in pairs(keys) do
        local range=doc[key]
        if type(range)~="table" then return false end
        local a,b=range.minSeconds,range.maxSeconds
        if type(a)~="number" or type(b)~="number" or a~=math.floor(a) or b~=math.floor(b)
            or a<1 or b<a or b>86400 then return false end
        ranges[key]={minSeconds=a,maxSeconds=b}
    end
    local schedules
    if doc.shifts~=nil then
        if type(doc.shifts)~="table" then return false end
        schedules={}
        for _,group in ipairs({"day","night"}) do
            local t=doc.shifts[group]
            if type(t)~="table" then return false end
            local copy={}
            for _,key in ipairs({"wakeHour","mealHour","sleepHour"}) do
                local hour=t[key]
                if type(hour)~="number" or hour~=hour or hour<0 or hour>=24 then return false end
                copy[key]=hour
            end
            local work=(copy.mealHour-copy.wakeHour)%24
            local awake=(copy.sleepHour-copy.wakeHour)%24
            if work<=0 or awake<=work then return false end
            schedules[group]=copy
        end
    end
    local extras={}
    local schemas={subtitles={enabled="bool",maxDistance={1,100},fontSize={0.2,4},height={0.5,4}},
        dice={enabled="bool",firstPairOnly="bool",searchRadius={5,250},pairWaitSeconds={5,300},
            approachTimeout={10,300},playSeconds={5,600}}}
    for name,schema in pairs(schemas) do
        local source=doc[name]
        if source~=nil then
            if type(source)~="table" then return false end
            local copy={}
            for key,rule in pairs(schema) do
                local value=source[key]
                if rule=="bool" then
                    if type(value)~="boolean" then return false end
                elseif type(value)~="number" or value~=value or value<rule[1] or value>rule[2] then return false end
                copy[key]=value
            end
            extras[name]=copy
        end
    end
    R.ranges=ranges
    local cfg=nebakovrising.Config
    for name,value in pairs(extras) do cfg[name]=value end
    if schedules then cfg.shiftSchedules=schedules end
    cfg.wakeStaggerMin,cfg.wakeStaggerMax=ranges.wakeStagger.minSeconds,ranges.wakeStagger.maxSeconds
    cfg.eveningMealStaggerMin,cfg.eveningMealStaggerMax=ranges.eveningMealStagger.minSeconds,ranges.eveningMealStagger.maxSeconds
    return true
end
function R.Duration(kind,a,b)
    local range=R.ranges and R.ranges[kind]
    return math.random(range and range.minSeconds or a,range and range.maxSeconds or b)
end
function R.Load()
    if type(dofile)=="function" then
        local ok,doc=pcall(dofile,"Mods/nebakovrising/Config/routines.lua")
        if ok and R.Apply(doc) then
            nebakovrising.Utils.Log("Routine config: Mods/nebakovrising/Config/routines.lua")
            return true
        end
    end
    nebakovrising.Utils.Log("Routine config unavailable/invalid; keeping previous/default timings")
    return false
end
