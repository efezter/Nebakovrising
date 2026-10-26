-- First off-duty pair after a completed meal. Native table owns seats/animation.
nebakovrising.Dice={used=false,serial=0}
local D=nebakovrising.Dice
local function castle() return nebakovrising.CastleUtils end
local function cfg() return nebakovrising.Config.dice or {} end
local function now() return System.GetCurrTime() end
local function log(text) nebakovrising.Utils.Log("[Dice] "..text) end
local function entityFor(p)
    local entity=System.GetEntity(p.id)
    return entity and entity:GetName()==p.name and entity.this
        and tostring(entity.this.id)==p.wuid and entity or nil
end
local function position(entity)
    local ok,pos=pcall(function() return entity:GetWorldPos() end)
    return ok and type(pos)=="table" and pos or nil
end
local function distance(a,b) return (a.x-b.x)^2+(a.y-b.y)^2+(a.z-b.z)^2 end
local function unavailable(entity)
    if not entity then return true end
    for _,method in ipairs({"IsDead","IsUnconscious"}) do
        if entity.actor and type(entity.actor[method])=="function" then
            local ok,value=pcall(entity.actor[method],entity.actor)
            if not ok or value==true then return true end
        end
    end
    if entity.soul and type(entity.soul.HasScriptContext)=="function" then
        local ok,value=pcall(entity.soul.HasScriptContext,entity.soul,"crime_interruptAttack")
        if not ok or value then return true end
    end
    if entity.human and type(entity.human.IsInDialog)=="function" then
        local ok,value=pcall(entity.human.IsInDialog,entity.human)
        if not ok or value then return true end
    end
    return false
end
local function links(wuid,tag)
    if not XGenAIModule or type(XGenAIModule.FindLinks)~="function" then return nil end
    local ok,result=pcall(XGenAIModule.FindLinks,wuid,tag)
    return ok and type(result)=="table" and result or nil
end
local function atTable(p,target)
    local result=links(p.nativeWuid,"dice_table")
    for _,value in pairs(result or {}) do if tostring(value)==tostring(target) then return true end end
    return false
end
function D.FindTable(entity)
    local here=position(entity);if not here then return nil end
    local closest=(cfg().searchRadius or 120)^2;local found
    D.probe={scanned=0,matching=0}
    for _,item in pairs(System.GetEntitiesByClass("SmartObjectHolder") or {}) do
        D.probe.scanned=D.probe.scanned+1
        local properties=item.Properties or {}
        local kind=tostring(properties.guidSmartObjectType or ""):lower():gsub("[%{%}%-]","")
        if kind=="9a3317b09c92466ebab6571f23356bca" then
            D.probe.matching=D.probe.matching+1
            local pos=position(item)
            local ok,wuid=pcall(XGenAIModule.GetMyWUID,item)
            if pos and ok and wuid and distance(pos,here)<closest then
                local valid=true
                for _,tag in ipairs({"seat1_SO","seat2_SO","cupSlot1","cupSlot2","hiddenSlot1","hiddenSlot2"}) do
                    local result=links(wuid,tag)
                    if not result or next(result)==nil then valid=false;D.probe.missingLink=tag;break end
                end
                if valid then closest=distance(pos,here);found={id=item.id,wuid=wuid,name=item:GetName()} end
            end
        end
    end
    return found
end
function D.Eligible(entity,token)
    if not entity or not entity.this or unavailable(entity) or not castle().OwnsNpcActivity(entity.this.id,token) then return false end
    local role=nebakovrising.Roles.Resolve(entity:GetName())
    local run=castle().activityRuns[tostring(entity.this.id)]
    return role and role.bedPool=="guard" and role.patrol and not run.conversationId
        and castle().GetMealProgress(entity)==nil and castle().IsPostMealIdle(entity)
end
function D.Finish(reason)
    local active=D.active;if not active then return end
    D.active=nil;D.last={reason=reason,participants=#active.participants}
    for _,p in ipairs(active.participants) do
        local run=castle().activityRuns[p.wuid]
        if run and run.token==p.token and run.diceScene==active.id then
            run.diceScene=nil;run.socialStationary=false;run.socialPose=nil
        end
    end
    log("Finished: "..reason)
end
function D.Reset()
    D.Finish("reset");D.used=false;D.last=nil;D.missingLogged=false
end
function D.Check()
    local active=D.active;if not active then return false end
    if now()>=active.deadline then D.Finish(#active.participants<2 and "partner_timeout" or "time_limit");return false end
    local tableEntity=System.GetEntity(active.table.id)
    if not tableEntity or tableEntity:GetName()~=active.table.name then D.Finish("table_missing");return false end
    for _,p in ipairs(active.participants) do
        local entity=entityFor(p)
        if not D.Eligible(entity,p.token) then D.Finish("participant_unavailable_or_shift_ended");return false end
        local run=castle().activityRuns[p.wuid]
        if now()-(run.heartbeat or now())>(nebakovrising.Config.activityHeartbeatTimeout or 15) then
            D.Finish("activity_stale");return false
        end
    end
    if #active.participants==2 and not active.playing
        and atTable(active.participants[1],active.table.wuid) and atTable(active.participants[2],active.table.wuid) then
        active.playing=true;active.deadline=now()+(cfg().playSeconds or 120)
        log("Both guards attached to native dice table")
    end
    return true
end
function D.Offer(entity,token)
    if cfg().enabled==false or (D.used and cfg().firstPairOnly~=false) or not D.Eligible(entity,token) then return false end
    if D.active then D.Check() end
    local active=D.active
    if active then
        for _,p in ipairs(active.participants) do if p.name==entity:GetName() then return true end end
        if #active.participants>=2 then return false end
        local at=position(System.GetEntity(active.table.id));local here=position(entity)
        if not at or not here or distance(at,here)>(cfg().searchRadius or 120)^2 then return false end
    else
        local tableInfo=D.FindTable(entity)
        if not tableInfo then
            if not D.missingLogged then
                log("No linked dice table within search radius; matches="..tostring(D.probe and D.probe.matching)
                    ..", missingLink="..tostring(D.probe and D.probe.missingLink).."; meal routine continues")
                D.missingLogged=true
            end
            return false
        end
        D.serial=D.serial+1
        active={id=D.serial,table=tableInfo,participants={},deadline=now()+(cfg().pairWaitSeconds or 90)}
        D.active=active
    end
    local p={id=entity.id,name=entity:GetName(),wuid=tostring(entity.this.id),nativeWuid=entity.this.id,token=token}
    active.participants[#active.participants+1]=p
    local run=castle().activityRuns[p.wuid]
    run.diceScene=active.id;run.socialStationary=false;run.socialPose=nil
    castle().SetActivityPhase(entity,token,"dice_wait")
    if #active.participants==2 then
        D.used=true;active.deadline=now()+(cfg().approachTimeout or 90)
        log("Pair: "..active.participants[1].name.." + "..p.name.." -> "..active.table.name)
    else log("First off-duty diner: "..p.name) end
    return true
end
function D.Participant(entity,token)
    if not D.active then return nil end
    for i,p in ipairs(D.active.participants) do
        if p.id==entity.id and p.token==token then return p,i end
    end
end
function D.HasRequest(entity,token) return D.Participant(entity,token)~=nil end
function D.Plan(entity,token)
    local p,index=D.Participant(entity,token)
    if not p or not D.Check() then return nil end
    if #D.active.participants<2 then return {waiting=true} end
    if index==2 then
        local lead=D.active.participants[1]
        if not atTable(lead,D.active.table.wuid) then return {waiting=true} end
    end
    return {waiting=false,target=D.active.table.wuid,behavior=index==1 and "use_challenger" or "use_opponent"}
end
function D.NativeBegin(entity,token)
    local p=D.Participant(entity,token);if not p or not D.Check() then return false end
    if not p.entered then log("Requesting native behavior for "..p.name) end
    p.entered=true;castle().SetActivityPhase(entity,token,"dice_native")
    return true
end
function D.NativeResult(entity,token,success)
    local p=D.Participant(entity,token);if not p then return end
    if success then D.Finish("native_completed")
    elseif not p.failed then p.failed=true;log("Native behavior not yet available; retrying within scene timeout: "..p.name) end
end
function D.Alive(entity,token) return D.Participant(entity,token)~=nil and D.Check() end
function D.Leave(entity,token)
    if D.Participant(entity,token) then D.Finish("behavior_ended") end
end
function D.Status()
    if D.active then
        D.Check()
        if D.active then log("participants="..#D.active.participants..", table="..D.active.table.name
            ..", remaining="..math.max(0,D.active.deadline-now()));return end
    end
    log("idle; first pair used="..tostring(D.used)..", last="..tostring(D.last and D.last.reason))
    if D.probe then log("table scan="..D.probe.scanned..", matches="..D.probe.matching..", missingLink="..tostring(D.probe.missingLink)) end
end
