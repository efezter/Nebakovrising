-- Game-side owner of social reservations and behaviour. Python owns synthesis/audio.
nebakovrising.Conversations = nebakovrising.Conversations or {}
local D = nebakovrising.Conversations
D.generation = D.generation or 0
D.cooldowns = D.cooldowns or {}
D.handlers = D.handlers or {}
local function cfg() return nebakovrising.Config.conversations end
local function now() return System.GetCurrTime() end
local function randomDelay()
    return math.random(cfg().randomMinSeconds, cfg().randomMaxSeconds)
end
local function castle() return nebakovrising.CastleUtils end
local function bridge() return nebakovrising.VoiceBridge end
local function log(text) nebakovrising.Utils.Log("[Conversation] " .. text) end
local function distance(a, b)
    local dx, dy, dz = a.x-b.x, a.y-b.y, a.z-b.z
    return math.sqrt(dx*dx + dy*dy + dz*dz)
end
local function position(entity)
    local ok, value = pcall(function() return entity:GetWorldPos() end)
    if ok and type(value) == "table" and type(value.x) == "number"
        and type(value.y) == "number" and type(value.z) == "number" then return value end
end
local function player() return nebakovrising.Utils.GetPlayer() end
local function entityFor(p)
    local entity = System.GetEntity(p.entityId)
    if entity and entity:GetName() == p.name and entity.this
        and tostring(entity.this.id) == p.wuid then return entity end
end
local function unavailable(entity)
    if not entity then return true end
    for _, method in ipairs({"IsDead", "IsUnconscious"}) do
        if entity.actor and type(entity.actor[method]) == "function" then
            local ok, value = pcall(entity.actor[method], entity.actor)
            if not ok or value == true then return true end
        end
    end
    if entity.soul and type(entity.soul.HasScriptContext) == "function" then
        local ok, combat = pcall(entity.soul.HasScriptContext, entity.soul, "crime_interruptAttack")
        if not ok or combat then return true end
    end
    if entity.human and type(entity.human.IsInDialog) == "function" then
        local ok, talking = pcall(entity.human.IsInDialog, entity.human)
        if not ok or talking then return true end
    end
    return false
end

function D.InRegion()
    local pos = position(player())
    if not pos or not System.GetEntityIdByName("trosecko") then return false end
    local settings = cfg()
    local radius = D.inRegion and settings.regionExitRadius or settings.regionRadius
    return math.abs(pos.z-settings.regionCenter.z) <= settings.regionHeight
        and distance(pos, settings.regionCenter) <= radius
end

-- Compatibility entry point: ambient conversations have no clock restriction.
function D.InPatrolHours() return true end

function D.SetEventContext(kind,text,ttl)
    if type(kind)~="string" or #kind>64 or not kind:match("^[%w_-]+$")
        or type(text)~="string" or #text>500 or type(ttl)~="number" or ttl~=ttl or ttl<0 or ttl>300 then return false end
    D.eventRevision=(D.eventRevision or 0)+1
    D.recentEvent=ttl>0 and {kind=kind,text=text,expiresAt=now()+ttl} or nil
    return true
end

function D.BuildContext(first,second,manual,behavior)
    local ok,hour=pcall(function() return Calendar.GetWorldHourOfDay() end)
    ok=ok and type(hour)=="number"
    local a,b=nebakovrising.Roles.Resolve(first:GetName()),nebakovrising.Roles.Resolve(second:GetName())
    local event=D.recentEvent
    if event and now()>=event.expiresAt then event=nil end
    return {behavior=behavior or "patrol",location="Nebakov Castle",hour=ok and hour or nil,
        time_of_day=ok and (hour<6 and "night" or hour<12 and "morning" or hour<17 and "afternoon" or hour<22 and "evening" or "night") or "unknown",
        trigger=manual and "console_test" or "random_patrol",guard_a=first:GetName(),guard_b=second:GetName(),
        guard_a_name=nebakovrising.Names and nebakovrising.Names.Get(first) or "Marek",
        guard_b_name=nebakovrising.Names and nebakovrising.Names.Get(second) or "Hertl",
        guard_a_activity=D.Activity(first),guard_b_activity=D.Activity(second),
        guard_a_role=a and a.id or "guard",guard_b_role=b and b.id or "guard",
        event_kind=event and event.kind or "none",event_text=event and event.text or "No verified recent event supplied."},
        event and event.expiresAt or nil
end

local function currentRun(entity)
    return entity and entity.this and castle().activityRuns[tostring(entity.this.id)] or nil
end

local function moving(entity)
    if type(entity.GetVelocity)~="function" then return false end -- verified BT marker is the fallback
    local ok,v=pcall(entity.GetVelocity,entity)
    if not ok or type(v)~="table" or type(v.x)~="number" or type(v.y)~="number" or type(v.z)~="number" then return true end
    local speed=v.x*v.x+v.y*v.y+v.z*v.z
    return speed~=speed or speed>0.0225
end
function D.Activity(entity)
    local run=currentRun(entity)
    if not run then return nil end
    if run.phase=="eating" then return "meal" end
    if run.phase=="evening_idle" then return "idle" end
    if run.kind=="patrol" then return "patrol" end
end
function D.IsEligible(entity,ownReservation)
    local run=currentRun(entity)
    if not run or not run.started or not run.socialStationary
        or (run.conversationId and run.conversationId~=ownReservation)
        or now()-(run.heartbeat or 0)>cfg().patrolHeartbeatMaxAge or unavailable(entity) or moving(entity) then return false end
    local role=nebakovrising.Roles.Resolve(entity:GetName())
    if not role or not role.patrol then return false end
    local activity=D.Activity(entity)
    if activity=="patrol" then
        return run.phase=="patrol_wait" and not castle().PatrolShouldStop(entity)
    elseif activity=="meal" then
        return run.socialPose=="sit" and not castle().HasEatenMeal(entity)
            and not castle().IsNpcSleepTime(entity.this.id, true) and not castle().ActivityPhaseExpired(entity.this.id,run.token)
    elseif activity=="idle" then
        return castle().IsPostMealIdle(entity)
    end
    return false
end
function D.IsPatrolling(entity) return D.Activity(entity)=="patrol" and D.IsEligible(entity) end

function D.Participant(npcWuid, token)
    if not D.active then return nil end
    for _, p in ipairs(D.active.participants) do
        if p.wuid == tostring(npcWuid) and p.token == token then return p end
    end
end

function D.HasRequest(npcWuid, token)
    local p=D.Participant(npcWuid,token)
    return D.active~=nil and D.active.phase~="preparing_audio" and p~=nil and not p.preservePose
end

-- Written by the BT only after the sit/lean action has completed. Assignments
-- alone do not prove that the actor has physically reached that posture.
function D.SetPatrolPose(entity,token,kind)
    local run=currentRun(entity)
    if not run or run.token~=token then return false end
    run.socialPose=(kind=="sit" or kind=="lean") and kind or nil
    run.socialStationary=kind=="sit" or kind=="lean" or kind=="guard"
    if run.socialStationary and run.kind=="patrol" and run.phase~="conversation_wait" then
        castle().SetActivityPhase(entity,token,"patrol_wait")
    end
    return true
end

function D.ReceiverRequested(npcWuid,token)
    local p=D.Participant(npcWuid,token)
    return D.active~=nil and p~=nil and (D.active.inPlace==true or (D.active.phase~="preparing_audio" and p.preservePose==true))
end

function D.Finish(reason, success)
    local active = D.active
    if not active then return end
    if nebakovrising.VoiceFace then nebakovrising.VoiceFace.Stop(active.id) end
    if nebakovrising.Subtitles then nebakovrising.Subtitles.Stop(active.id) end
    D.last = { id = active.id, phase = success and "finished" or "cancelled", reason = reason,
        behavior = active.behavior, arrived = active.arrived == true }
    D.nextAllowed = now() + (success and cfg().cooldownSeconds or 10)
    -- The configured interval starts after completion, not midway through speech.
    D.nextRandom = now()+randomDelay()
    for _, p in ipairs(active.participants) do
        D.cooldowns[p.name] = now() + (success and cfg().npcCooldownSeconds or 10)
        if p.preservePose or active.inPlace then
            local entity=entityFor(p)
            local run=currentRun(entity) or castle().activityRuns[p.wuid]
            if run and run.token==p.token and run.conversationId==active.id then
                run.conversationId=nil
                if active.inPlace then
                    run.phase=p.savedPhase
                    run.deadline=p.remainingDeadline and (now()+p.remainingDeadline) or nil
                elseif entity then castle().SetActivityPhase(entity,p.token,"patrol_wait")
                else run.phase,run.deadline="patrol_wait",nil end
            end
        end
        -- Keep run.conversationId until that BT's cleanup; voluntary social exits
        -- must not blacklist the patrol point as a failed path.
    end
    D.active = nil
    D.reason = reason
    log((success and "Bitti: " or "Iptal: ") .. reason .. ", id=" .. active.id)
    bridge().Emit("director_status")
end

function D.Cancel(reason) D.Finish(reason or "cancelled", false) end

function D.ActivityEnded(npcWuid, token)
    if D.active and (D.active.inPlace or D.active.phase~="preparing_audio") and D.Participant(npcWuid,token) then D.Cancel("patrol_interrupted") end
end

function D.CheckActive()
    local active = D.active
    if not active then return false end
    if not D.InRegion() then D.Cancel("outside_nebakov"); return false end
    local pending=active.phase=="preparing_audio"
    if pending and (active.eventRevision~=(D.eventRevision or 0) or (active.eventExpiresAt and now()>=active.eventExpiresAt)) then
        D.Cancel("context_changed");return false
    end
    if not D.peer or D.peer.id ~= active.peer or now() - D.peer.lastSeen > cfg().peerTimeout then
        D.Cancel("python_disconnected"); return false
    end
    local playerPos = position(player())
    for _, p in ipairs(active.participants) do
        local entity = entityFor(p)
        local run = currentRun(entity)
        local pos = position(entity)
        local invalidRun
        if active.inPlace then
            invalidRun=not run or run.token~=p.token or run.conversationId~=active.id
                or not D.IsEligible(entity,active.id) or run.socialPose~=p.pose
        elseif pending then invalidRun=not D.IsEligible(entity)
        else invalidRun=not run or run.token~=p.token or not run.started or run.kind~="patrol"
            or now()-(run.heartbeat or 0)>cfg().patrolHeartbeatMaxAge end
        if unavailable(entity) or invalidRun then D.Cancel("participant_unavailable");return false end
        if not active.inPlace and not pending and p.preservePose and run.socialPose~=p.pose then
            D.Cancel("receiver_posture_changed");return false
        end
        if not active.inPlace and castle().PatrolShouldStop(entity) then D.Cancel("higher_priority_activity");return false end
        local radius=pending and cfg().searchRadius or cfg().playerExitRadius
        if not pos or not playerPos or distance(pos,playerPos)>radius
            or (pending and math.abs(pos.z-playerPos.z)>3) then
            D.Cancel("player_out_of_range"); return false
        end
    end
    if active.inPlace then
        local a,b=position(entityFor(active.participants[1])),position(entityFor(active.participants[2]))
        if not a or not b or distance(a,b)>(cfg().nearbyDistance or 2)+0.1 then D.Cancel("pair_separated");return false end
    end
    if active.faceDeadline and not active.arrived and now() >= active.faceDeadline then
        for _,p in ipairs(active.participants) do
            log("Donme: NPC=" .. p.name .. ", aci=" .. tostring(p.facingError)
                .. ", API=" .. tostring(p.turnMethod) .. ", hedef=" .. tostring(p.turnTarget)
                .. ", nativeTamam=" .. tostring(p.nativeTurnComplete))
        end
        D.Cancel("facing_timeout");return false
    end
    if now() >= active.deadline then D.Cancel(active.phase .. "_timeout"); return false end
    return true
end

function D.ParticipantAlive(npcWuid, token)
    return D.Participant(npcWuid, token) ~= nil and D.CheckActive()
end

D.handlers.patrol = {
    eligible = function(entity) return D.IsPatrolling(entity) end,
    profile = "patrol-daily-talk",
}

function D.TryStart(manual)
    D.attemptSerial=(D.attemptSerial or 0)+1
    D.lastAttempt={seq=D.attemptSerial,game_time=now(),manual=manual==true,started=false}
    local function reject(reason)
        D.reason = reason
        D.lastAttempt.reason=reason
        if manual then log("Baslatilamadi: " .. reason); bridge().Emit("director_status") end
        return false, reason
    end
    if not D.running then D.Start() end
    if not cfg().enabled then return reject("disabled") end
    D.inRegion = D.InRegion()
    if not D.inRegion then return reject("outside_nebakov") end
    if D.active then return reject("conversation_active") end
    if not D.peer or now()-D.peer.lastSeen > cfg().peerTimeout then return reject("python_not_connected") end
    if not D.peer.ready then return reject("python_not_ready") end
    if cfg().runtimeConfigRequired and not D.peer.hasSettings then return reject("python_config_not_ready") end
    if now() < (D.nextAllowed or 0) then return reject("global_cooldown") end
    local nearby, playerPos = {}, position(player())
    for wuid, run in pairs(castle().activityRuns) do
        if run.started and not run.conversationId then
            -- WUID map keys are strings like "userdata: ..." in the real game.
            -- Resolve the saved runtime entity name, never pass that string as a WUID.
            local entityId = System.GetEntityIdByName(run.npcKey)
            local entity = entityId and System.GetEntity(entityId)
            local pos = position(entity)
            if entity and entity.this and tostring(entity.this.id) == wuid
                and pos and distance(pos, playerPos) <= cfg().searchRadius
                and math.abs(pos.z-playerPos.z) <= 3
                and now() >= (D.cooldowns[entity:GetName()] or 0)
                and D.IsEligible(entity) then
                nearby[#nearby+1] = entity
            end
        end
    end
    if #nearby < 2 then return reject("two_eligible_patrol_npcs_required") end
    local pairs={}
    for i=1,#nearby-1 do
        for j=i+1,#nearby do
            local a,b=nearby[i],nearby[j]
            local close=distance(position(a),position(b))<=(cfg().nearbyDistance or 2)
            if close or (D.Activity(a)=="patrol" and D.Activity(b)=="patrol") then pairs[#pairs+1]={a,b,close} end
        end
    end
    if #pairs==0 then return reject("no_compatible_stationary_pair") end
    local pair=pairs[math.random(1,#pairs)]
    local first,second,inPlace=pair[1],pair[2],pair[3]
    if math.random(1,2)==2 then first,second=second,first end
    if not inPlace and not currentRun(first).socialPose and currentRun(second).socialPose then first,second=second,first end
    local a,b=D.Activity(first),D.Activity(second)
    local behavior=(a=="meal" or b=="meal") and "meal" or (a=="idle" or b=="idle") and "idle" or "patrol"
    if D.peer.hasCatalog then
        nebakovrising.Voices.Reconcile()
        if not nebakovrising.Voices.Get(first:GetName()) or not nebakovrising.Voices.Get(second:GetName()) then
            return reject("voice_assignment_pending")
        end
    end
    bridge().NewSession()
    bridge().bindings = {}
    if not bridge().Register("Marek", first) or not bridge().Register("Hertl", second) then
        return reject("binding_failed")
    end
    local id = tostring(math.random(1000000, 1000000000)) .. "-" .. tostring(D.serial or 0)
    D.serial = (D.serial or 0)+1
    local participants = {}
    for i, entity in ipairs({first, second}) do
        local run = currentRun(entity)
        if inPlace or not cfg().prepareBeforeMeeting then run.conversationId = id end
        participants[i] = {entityId=entity.id, wuid=tostring(entity.this.id), name=entity:GetName(),
            token=run.token, mover=i==2, prepared=false, arrived=false,
            preservePose=inPlace or (i==1 and run.socialPose~=nil),pose=(inPlace or i==1) and run.socialPose or nil,
            savedPhase=run.phase,remainingDeadline=run.deadline and math.max(0,run.deadline-now()) or nil}
        if inPlace then run.deadline=nil end
    end
    local context,eventExpiresAt=D.BuildContext(first,second,manual,behavior)
    local pending=inPlace or cfg().prepareBeforeMeeting==true
    D.active = {id=id, peer=D.peer.id, behavior=behavior, inPlace=inPlace, phase=pending and "preparing_audio" or "reserved", participants=participants,
        deadline=now()+(pending and (cfg().generationTimeout or 240) or cfg().preparationTimeout),
        context=context,profileId=behavior=="meal" and "meal-daily-talk" or behavior=="idle" and "idle-daily-talk" or cfg().profileId,eventRevision=D.eventRevision or 0,eventExpiresAt=eventExpiresAt}
    -- A new session needs a fresh control heartbeat before the reserved BTs run.
    -- Preserve the connected peer, but commands from the previous session cannot apply.
    D.reason = nil
    D.lastAttempt.started=true
    log("Patrol sohbeti ayrildi: " .. participants[1].name .. " + " .. participants[2].name .. ", id=" .. id)
    bridge().Emit("director_status")
    return true
end

function D.CommitMeeting()
    local active=D.active
    if not active or not D.CheckActive() then return false end
    if active.inPlace then
        active.audioReady=true
        active.phase,active.deadline="reserved",now()+cfg().preparationTimeout
        D.UpdateInPlaceReady()
        return true
    end
    if active.phase~="preparing_audio" then return true end
    local runs={}
    for i,p in ipairs(active.participants) do
        local entity=entityFor(p)
        if not entity or not D.IsPatrolling(entity) then D.Cancel("pair_no_longer_available");return false end
        runs[i]=currentRun(entity)
    end
    for i,p in ipairs(active.participants) do
        p.token=runs[i].token
        p.pose=i==1 and runs[i].socialPose or nil
        p.preservePose=p.pose~=nil
        runs[i].conversationId=active.id
    end
    active.phase,active.deadline="reserved",now()+cfg().preparationTimeout
    log("Sesler hazir; bulusma basliyor: "..active.id)
    return true
end

function D.UpdateInPlaceReady()
    local active=D.active
    if active and active.inPlace and active.audioReady and active.participants[1].prepared and active.participants[2].prepared then
        active.met,active.arrived,active.phase=true,true,"waiting_audio"
        active.deadline=now()+cfg().conversationTimeout
        bridge().Emit("director_status")
    end
end

function D.Prepare(entity, token)
    local p = D.Participant(entity.this.id, token)
    if not p or not D.CheckActive() then return nil end
    p.prepared = true
    if D.active.inPlace then
        p.arrived,p.faced=true,true
        D.UpdateInPlaceReady()
        return {mover=false}
    end
    castle().SetActivityPhase(entity, token, "conversation_wait")
    local active = D.active
    if not p.mover then p.arrived = true end
    if active.participants[1].prepared and active.participants[2].prepared then
        active.phase, active.deadline = "approaching", now()+cfg().approachTimeout
    end
    if not p.mover then return { mover=false } end
    local anchor = position(entityFor(active.participants[1]))
    local here = position(entity)
    local dx, dy = here.x-anchor.x, here.y-anchor.y
    if active.participants[1].preservePose then
        local receiver=entityFor(active.participants[1])
        local ok,forward=pcall(receiver.GetDirectionVector,receiver)
        if not ok or type(forward)~="table" or type(forward.x)~="number" or type(forward.y)~="number" then
            D.Cancel("receiver_direction_unavailable");return nil
        end
        dx,dy=forward.x,forward.y
        if dx*dx+dy*dy<0.001 then D.Cancel("receiver_direction_unavailable");return nil end
    end
    local length = math.sqrt(dx*dx+dy*dy)
    if length < 0.1 then dx, dy, length = 1, 0, 1 end
    return {mover=true, target={x=anchor.x+dx/length*cfg().approachDistance,
        y=anchor.y+dy/length*cfg().approachDistance, z=anchor.z}}
end

function D.AnchorReady(npcWuid, token)
    local p = D.Participant(npcWuid, token)
    return p ~= nil and D.active.participants[1].prepared == true
end

-- Native Move can report success before its last braking/root-motion frame.
-- Keep both reservations while checking the actual distance asynchronously.
function D.ConfirmArrival(data)
    local active=D.active
    if not data or not active or data.generation~=D.generation or data.id~=active.id then return false end
    local p=active.participants[2]
    if p.token~=data.token or not D.CheckActive() then return false end
    if active.met then return true end
    local anchor=position(entityFor(active.participants[1]))
    local here=position(entityFor(p))
    if not anchor or not here or math.abs(anchor.z-here.z)>1.5 then
        D.Cancel("arrival_not_confirmed");return false
    end
    local gap=distance(anchor,here)
    active.meetingDistance=gap
    if gap>cfg().arrivalDistance then
        if p.arrivalDeadline and now()<p.arrivalDeadline then
            Script.SetTimerForFunction(100,"nebakovrising.Conversations.ConfirmArrival",data)
            return false
        end
        log("Varis dogrulanamadi: mesafe=" .. tostring(gap) .. ", sinir=" .. tostring(cfg().arrivalDistance))
        D.Cancel("arrival_not_confirmed");return false
    end
    p.arrived,active.met,active.phase=true,true,"waiting_audio"
    active.faceDeadline=now()+(cfg().faceTimeout or 8)
    active.deadline=now()+(cfg().generationTimeout or 240)
    log("Varis dogrulandi: mesafe=" .. tostring(gap))
    bridge().Emit("director_status")
    return true
end

function D.Arrived(entity, token)
    local p=D.Participant(entity.this.id,token)
    if not p or not p.mover or not D.CheckActive() then return false end
    p.arrivalDeadline=p.arrivalDeadline or now()+(cfg().arrivalSettleSeconds or 2)
    D.active.deadline=math.max(D.active.deadline,p.arrivalDeadline)
    local id=D.active.id
    D.ConfirmArrival({generation=D.generation,id=id,token=token})
    -- This return keeps the BT alive; active.met is the physical arrival gate.
    return D.active~=nil and D.active.id==id
end

function D.Partner(entity, token)
    local p=D.Participant(entity.this.id,token)
    if not p then return nil end
    local target=entityFor(D.active.participants[p.mover and 1 or 2])
    return target and target.this.id
end
function D.HasMet(entity, token)
    return D.ParticipantAlive(entity.this.id,token) and D.active.met==true
end
function D.TurnStarted(entity, token)
    local p=D.Participant(entity.this.id,token)
    if not p or not D.HasMet(entity,token) then return false end
    p.turnMethod="BT.Turn"
    p.turnTarget=tostring(D.Partner(entity,token))
    p.nativeTurnComplete=false
    return true
end
function D.Faced(entity, token)
    local p=D.Participant(entity.this.id,token)
    if not p or not D.HasMet(entity,token) then return false end
    if D.active.inPlace then p.faced=true;return true end
    p.nativeTurnComplete=not p.preservePose
    if p.preservePose then p.turnMethod="preserved_"..p.pose end
    local other=entityFor(D.active.participants[p.mover and 1 or 2])
    local a,b=position(entity),position(other)
    local ok,f=pcall(entity.GetDirectionVector,entity)
    if not a or not b or not ok or type(f)~="table" or type(f.x)~="number" or type(f.y)~="number" then return false end
    local dx,dy=b.x-a.x,b.y-a.y
    local length=math.sqrt(dx*dx+dy*dy)*math.sqrt(f.x*f.x+f.y*f.y)
    if length>0.001 then p.facingError=math.deg(math.acos(math.max(-1,math.min(1,(dx*f.x+dy*f.y)/length)))) end
    if length<0.001 or (dx*f.x+dy*f.y)/length<math.cos(math.rad(20)) then return false end
    p.faced=true
    if D.active.participants[1].faced and D.active.participants[2].faced then
        D.active.arrived=true;bridge().Emit("director_status")
    end
    return true
end

local validKinds = {heartbeat_ready=true, heartbeat_busy=true, audio_ready=true,
    playing=true, finished=true, cancel=true, error=true, line_start=true, line_end=true, voice_catalog=true, conversation_config=true, telemetry_probe=true, telemetry_confirm=true}
function D.Receive(peer, seq, kind, session, conversation, line, duration, text)
    -- A non-throwing LoadScript call does not prove a file was executed (it may
    -- return false or reuse a cached script). PollControl observes this counter.
    D.receiveCalls = (D.receiveCalls or 0)+1
    if not D.running or type(peer) ~= "string" or #peer > 80 or type(seq) ~= "number"
        or seq ~= math.floor(seq) or seq < 1 or not validKinds[kind]
        or session ~= bridge().session then return false end
    if D.peer and D.peer.id ~= peer and now()-D.peer.lastSeen <= cfg().peerTimeout then return false end
    if not D.peer or D.peer.id ~= peer then D.peer = {id=peer, seq=0, lastSeen=now(), ready=false} end
    if seq <= D.peer.seq then return false end
    local accepted = false
    if kind=="telemetry_probe" or kind=="telemetry_confirm" then
        accepted=bridge().ConfigureTelemetry(line,kind=="telemetry_confirm")
        if accepted then D.peer.lastSeen=now() end
    elseif kind == "conversation_config" then
        accepted=nebakovrising.ConversationConfig~=nil and nebakovrising.ConversationConfig.Apply(line,duration)
        if accepted then D.peer.lastSeen=now();D.peer.hasSettings=true end
    elseif kind == "voice_catalog" then
        accepted = nebakovrising.Voices ~= nil and nebakovrising.Voices.Apply(line,duration)
        if accepted then D.peer.lastSeen=now();D.peer.hasCatalog=true end
    elseif kind == "heartbeat_ready" or kind == "heartbeat_busy" then
        D.peer.lastSeen, D.peer.ready, accepted = now(), kind=="heartbeat_ready", true
        if D.reason == "python_not_connected" or D.reason == "python_not_ready" or D.reason == "python_config_not_ready" then D.reason = nil end
    elseif D.active and D.active.id == conversation then
        if kind == "cancel" or kind == "error" then
            D.Cancel("python_" .. kind); accepted = true
        elseif D.CheckActive() then
            if kind == "audio_ready" then
                if D.CommitMeeting() then D.active.audioReady,accepted=true,true end
            elseif kind == "playing" and D.active.arrived and D.active.audioReady then
                D.active.phase, D.active.deadline, accepted = "playing", now()+cfg().conversationTimeout, true
            elseif kind == "finished" and D.active.phase == "playing" then
                D.Finish("playback_finished", true); accepted = true
            elseif (kind == "line_start" or kind == "line_end") and D.active.phase == "playing"
                and type(line) == "number" and line == math.floor(line) and line >= 1 and line <= 4 then
                if kind == "line_start" and line == (D.active.speechLine or 0)+1
                    and type(duration) == "number" and duration == math.floor(duration)
                    and duration > 0 and duration <= 100000 then
                    local p = D.active.participants[line%2 == 1 and 1 or 2]
                    local face = nebakovrising.VoiceFace
                    if face then face.Start(entityFor(p), line%2 == 1 and "Marek" or "Hertl", conversation, line, duration) end
                    if nebakovrising.Subtitles then nebakovrising.Subtitles.Start(entityFor(p),conversation,line,text,duration) end
                    D.active.speechLine, accepted = line, true
                elseif kind == "line_end" and line == D.active.speechLine then
                    if nebakovrising.VoiceFace then nebakovrising.VoiceFace.Stop(conversation, line) end
                    if nebakovrising.Subtitles then nebakovrising.Subtitles.Stop(conversation,line) end
                    accepted = true
                end
            end
        end
    end
    D.peer.seq = seq
    D.ack = {peer=peer, seq=seq, accepted=accepted, kind=kind}
    return accepted
end

function D.Snapshot()
    local active = D.active
    local info = {version=1, id=active and active.id or (D.last and D.last.id or ""),
        phase=active and active.phase or (D.last and D.last.phase or "idle"), behavior=active and active.behavior or (D.last and D.last.behavior) or "patrol",
        in_place=active and active.inPlace==true or false,
        in_nebakov=D.inRegion==true, arrived=active and active.arrived==true or false,
        audio_ready=active and active.audioReady==true or false, control=D.ack,
        owner=active and active.peer or nil,
        profile_id=active and active.profileId,
        last_attempt=D.lastAttempt,
        meeting_distance=active and active.meetingDistance,
        voice_catalog_required=D.peer and D.peer.hasCatalog==true or false,
        control_io=D.controlIO,
        face=nebakovrising.VoiceFace and nebakovrising.VoiceFace.last,
        reason=D.reason or (D.last and D.last.reason), enabled=D.running==true}
    if active then info.context=active.context end
    return info
end

function D.PollControl()
    local info = D.controlIO or {}
    D.controlIO = info
    info.dofile_available = type(dofile) == "function"
    info.reload_available = Script ~= nil and type(Script.ReloadScript) == "function"
    info.load_available = Script ~= nil and type(Script.LoadScript) == "function"
    local paths = {"Data/Scripts/nebakov_voice/command.lua", "Scripts/nebakov_voice/command.lua",
        "../../Data/Scripts/nebakov_voice/command.lua", "data/scripts/nebakov_voice/command.lua"}
    local function attempt(method, path)
        local before = D.receiveCalls or 0
        local ok, result
        if method == "dofile" then ok, result = pcall(dofile, path)
        elseif method == "reload" then ok, result = pcall(Script.ReloadScript, path)
        else ok, result = pcall(Script.LoadScript, path) end
        info.receive_calls = D.receiveCalls or 0
        if info.receive_calls > before then
            info.method, info.path, info.executed, info.last_error = method, path, true, nil
            if D.readerMethod ~= method or D.readerPath ~= path then
                log("Python kontrol dosyasi calistirildi: " .. method .. " " .. path)
            end
            D.readerMethod, D.readerPath = method, path
            return true
        end
        info.last_error = ok and ("No Receive call; return=" .. tostring(result))
            or string.sub(tostring(result), 1, 180)
        if method == "dofile" then info.dofile_error = info.last_error end
        return false
    end
    if D.readerMethod and ((D.readerMethod == "dofile" and info.dofile_available)
        or (D.readerMethod == "reload" and info.reload_available)
        or (D.readerMethod == "load" and info.load_available)) then
        if attempt(D.readerMethod, D.readerPath) then return true end
    end
    -- Match the working reference mod's dofile response path; it re-reads the
    -- physical file instead of trusting LoadScript's optional reload argument.
    if info.dofile_available then
        for _, path in ipairs(paths) do if attempt("dofile", path) then return true end end
    end
    local scriptPath = "Scripts/nebakov_voice/command.lua"
    if info.reload_available and attempt("reload", scriptPath) then return true end
    if info.load_available and attempt("load", scriptPath) then return true end
    if info.reload_available and attempt("reload", scriptPath) then return true end
    info.executed = false
    if not D.readerErrorLogged then
        D.readerErrorLogged = true
        log("Python kontrol komutu henuz calistirilmadi; dofile=" .. tostring(info.dofile_available)
            .. ", reload=" .. tostring(info.reload_available) .. ", sonuc=" .. tostring(info.last_error))
    end
    return false
end

function D.Tick(data)
    if not D.running or not data or data.generation ~= D.generation then return end
    D.PollControl()
    D.inRegion = D.InRegion()
    if D.active then D.CheckActive() end
    if cfg().randomEnabled ~= false and not D.active and D.inRegion and now() >= (D.nextRandom or 0) then
        D.nextRandom = now()+randomDelay()
        D.TryStart(false)
    end
    bridge().Emit("director_status")
    local delay = D.active and 250 or (D.inRegion and 1000 or 3000)
    Script.SetTimerForFunction(delay, "nebakovrising.Conversations.Tick", {generation=D.generation})
end

function D.Start()
    if D.running then return end
    D.running, D.generation = true, D.generation+1
    D.nextRandom = now()+randomDelay()
    Script.SetTimerForFunction(1, "nebakovrising.Conversations.Tick", {generation=D.generation})
end
function D.Stop()
    D.Cancel("manager_stopped")
    D.running, D.generation = false, D.generation+1
end
function D.OnGameplayStarted()
    if nebakovrising.VoiceFace then nebakovrising.VoiceFace.Stop() end
    if nebakovrising.Subtitles then nebakovrising.Subtitles.Stop() end
    D.Stop()
    D.peer, D.ack, D.last, D.active = nil, nil, nil, nil
    D.readerMethod, D.readerPath, D.readerErrorLogged, D.controlIO, D.receiveCalls = nil, nil, nil, nil, 0
    D.cooldowns, D.nextAllowed, D.inRegion = {}, 0, false
    D.recentEvent,D.eventRevision=nil,0
    D.lastAttempt,D.attemptSerial=nil,0
    D.Start()
end
function D.Status()
    D.inRegion = D.InRegion()
    log("Nebakov=" .. tostring(D.inRegion) .. ", aktif=" .. tostring(D.active ~= nil)
        .. ", Python=" .. tostring(D.peer ~= nil and now()-D.peer.lastSeen<=cfg().peerTimeout)
        .. ", hazir=" .. tostring(D.peer ~= nil and D.peer.ready == true)
        .. ", okuyucu=" .. tostring(D.controlIO and D.controlIO.method or "bekleniyor")
        .. ", neden=" .. tostring(D.reason))
    bridge().Emit("director_status")
end

if not D.commandsRegistered then
    System.AddCCommand("nebakov_conversation_test", "nebakovrising.Conversations.TryStart(true)", "Iki uygun patrol guard'i yaklastirip sohbet baslat")
    System.AddCCommand("nebakov_conversation_status", "nebakovrising.Conversations.Status()", "Bolge, Python baglantisi ve sohbet durumunu yaz")
    System.AddCCommand("nebakov_conversation_start", "nebakovrising.Conversations.Start()", "Rastgele patrol sohbet yoneticisini baslat")
    System.AddCCommand("nebakov_conversation_stop", "nebakovrising.Conversations.Stop()", "Patrol sohbet yoneticisini durdur")
    D.commandsRegistered = true
end
