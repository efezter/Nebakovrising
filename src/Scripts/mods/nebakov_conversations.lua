-- Game-side owner of social reservations and behaviour. Python owns synthesis/audio.
nebakovrising.Conversations = nebakovrising.Conversations or {}
local D = nebakovrising.Conversations
D.generation = D.generation or 0
D.cooldowns = D.cooldowns or {}
D.handlers = D.handlers or {}
local function cfg() return nebakovrising.Config.conversations end
local function now() return System.GetCurrTime() end
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

local function currentRun(entity)
    return entity and entity.this and castle().activityRuns[tostring(entity.this.id)] or nil
end

function D.IsPatrolling(entity)
    local run = currentRun(entity)
    if not run or not run.started or run.kind ~= "patrol" or run.conversationId
        or now() - (run.heartbeat or 0) > cfg().patrolHeartbeatMaxAge then return false end
    if unavailable(entity) or castle().PatrolShouldStop(entity) then return false end
    local role = nebakovrising.Roles.Resolve(entity:GetName())
    return role ~= nil and role.patrol ~= nil
end

function D.Participant(npcWuid, token)
    if not D.active then return nil end
    for _, p in ipairs(D.active.participants) do
        if p.wuid == tostring(npcWuid) and p.token == token then return p end
    end
end

function D.HasRequest(npcWuid, token)
    return D.Participant(npcWuid, token) ~= nil
end

function D.Finish(reason, success)
    local active = D.active
    if not active then return end
    if nebakovrising.VoiceFace then nebakovrising.VoiceFace.Stop(active.id) end
    D.last = { id = active.id, phase = success and "finished" or "cancelled", reason = reason,
        behavior = active.behavior, arrived = active.arrived == true }
    D.nextAllowed = now() + (success and cfg().cooldownSeconds or 10)
    for _, p in ipairs(active.participants) do
        D.cooldowns[p.name] = now() + (success and cfg().npcCooldownSeconds or 10)
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
    if D.HasRequest(npcWuid, token) then D.Cancel("patrol_interrupted") end
end

function D.CheckActive()
    local active = D.active
    if not active then return false end
    if not D.InRegion() then D.Cancel("outside_nebakov"); return false end
    if not D.peer or D.peer.id ~= active.peer or now() - D.peer.lastSeen > cfg().peerTimeout then
        D.Cancel("python_disconnected"); return false
    end
    local playerPos = position(player())
    for _, p in ipairs(active.participants) do
        local entity = entityFor(p)
        local run = currentRun(entity)
        local pos = position(entity)
        if unavailable(entity) or not run or run.token ~= p.token or not run.started
            or run.kind ~= "patrol" or now()-(run.heartbeat or 0) > cfg().patrolHeartbeatMaxAge then
            D.Cancel("participant_unavailable"); return false
        end
        if castle().PatrolShouldStop(entity) then D.Cancel("higher_priority_activity"); return false end
        if not pos or not playerPos or distance(pos, playerPos) >= cfg().playerExitRadius then
            D.Cancel("player_out_of_range"); return false
        end
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
    context = "Two guards briefly pause their patrol at Nebakov Castle to exchange news about their watch.",
}

function D.TryStart(manual)
    local function reject(reason)
        D.reason = reason
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
    if now() < (D.nextAllowed or 0) then return reject("global_cooldown") end
    local nearby, playerPos = {}, position(player())
    for wuid, run in pairs(castle().activityRuns) do
        if run.started and run.kind == "patrol" and not run.conversationId then
            -- WUID map keys are strings like "userdata: ..." in the real game.
            -- Resolve the saved runtime entity name, never pass that string as a WUID.
            local entityId = System.GetEntityIdByName(run.npcKey)
            local entity = entityId and System.GetEntity(entityId)
            local pos = position(entity)
            if entity and entity.this and tostring(entity.this.id) == wuid
                and pos and distance(pos, playerPos) <= cfg().searchRadius
                and math.abs(pos.z-playerPos.z) <= 3
                and now() >= (D.cooldowns[entity:GetName()] or 0)
                and D.handlers.patrol.eligible(entity) then
                nearby[#nearby+1] = entity
            end
        end
    end
    if #nearby < 2 then return reject("two_eligible_patrol_npcs_required") end
    local firstIndex = math.random(1, #nearby)
    local first = table.remove(nearby, firstIndex)
    local second = nearby[math.random(1, #nearby)]
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
        run.conversationId = id
        participants[i] = {entityId=entity.id, wuid=tostring(entity.this.id), name=entity:GetName(),
            token=run.token, mover=i==2, prepared=false, arrived=false}
    end
    D.active = {id=id, peer=D.peer.id, behavior="patrol", phase="reserved", participants=participants,
        deadline=now()+cfg().preparationTimeout, context=D.handlers.patrol.context}
    -- A new session needs a fresh control heartbeat before the reserved BTs run.
    -- Preserve the connected peer, but commands from the previous session cannot apply.
    D.reason = nil
    log("Patrol sohbeti ayrildi: " .. participants[1].name .. " + " .. participants[2].name .. ", id=" .. id)
    bridge().Emit("director_status")
    return true
end

function D.Prepare(entity, token)
    local p = D.Participant(entity.this.id, token)
    if not p or not D.CheckActive() then return nil end
    p.prepared = true
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
    p.nativeTurnComplete=true
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
    playing=true, finished=true, cancel=true, error=true, line_start=true, line_end=true, voice_catalog=true}
function D.Receive(peer, seq, kind, session, conversation, line, duration)
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
    if kind == "voice_catalog" then
        accepted = nebakovrising.Voices ~= nil and nebakovrising.Voices.Apply(line,duration)
        if accepted then D.peer.lastSeen=now();D.peer.hasCatalog=true end
    elseif kind == "heartbeat_ready" or kind == "heartbeat_busy" then
        D.peer.lastSeen, D.peer.ready, accepted = now(), kind=="heartbeat_ready", true
        if D.reason == "python_not_connected" or D.reason == "python_not_ready" then D.reason = nil end
    elseif D.active and D.active.id == conversation then
        if kind == "cancel" or kind == "error" then
            D.Cancel("python_" .. kind); accepted = true
        elseif D.CheckActive() then
            if kind == "audio_ready" then
                D.active.audioReady, accepted = true, true
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
                    D.active.speechLine, accepted = line, true
                elseif kind == "line_end" and line == D.active.speechLine then
                    if nebakovrising.VoiceFace then nebakovrising.VoiceFace.Stop(conversation, line) end
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
        phase=active and active.phase or (D.last and D.last.phase or "idle"), behavior="patrol",
        in_nebakov=D.inRegion==true, arrived=active and active.arrived==true or false,
        audio_ready=active and active.audioReady==true or false, control=D.ack,
        owner=active and active.peer or nil,
        meeting_distance=active and active.meetingDistance,
        voice_catalog_required=D.peer and D.peer.hasCatalog==true or false,
        control_io=D.controlIO,
        face=nebakovrising.VoiceFace and nebakovrising.VoiceFace.last,
        reason=D.reason or (D.last and D.last.reason), enabled=D.running==true}
    if active then
        local hourOk, hour = pcall(Calendar.GetWorldHourOfDay)
        info.context = {behavior="patrol", situation=active.context, hour=hourOk and hour or nil,
            anchor=active.participants[1].name, approaching=active.participants[2].name}
    end
    return info
end

local function randomDelay()
    return math.random(cfg().randomMinSeconds, cfg().randomMaxSeconds)
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
    D.Stop()
    D.peer, D.ack, D.last, D.active = nil, nil, nil, nil
    D.readerMethod, D.readerPath, D.readerErrorLogged, D.controlIO, D.receiveCalls = nil, nil, nil, nil, 0
    D.cooldowns, D.nextAllowed, D.inRegion = {}, 0, false
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
