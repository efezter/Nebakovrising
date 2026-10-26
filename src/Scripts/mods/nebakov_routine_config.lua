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
    R.ranges=ranges
    local cfg=nebakovrising.Config
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
