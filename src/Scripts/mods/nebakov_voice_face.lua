-- Lip-sync-lite: an existing facial CAF on its own animation layer.
nebakovrising.VoiceFace = nebakovrising.VoiceFace or {}
local F = nebakovrising.VoiceFace
F.generation = F.generation or 0
local function settings() return nebakovrising.Config.conversations.face or {} end
local function log(s) nebakovrising.Utils.Log("[VoiceFace] " .. s) end
local function sameEntity(active)
    local e = active and System.GetEntity(active.entityId)
    return e and e:GetName() == active.name and e.this
        and tostring(e.this.id) == active.wuid and e or nil
end

function F.Stop(conversation, line)
    local active = F.current
    if not active or (conversation and active.conversation ~= conversation)
        or (line and active.line ~= line) then return end
    F.current, F.generation = nil, F.generation + 1
    local e = sameEntity(active)
    if e and type(e.StopAnimation) == "function" then
        pcall(e.StopAnimation, e, 0, active.layer)
    end
    F.last = {status="stopped", line=active.line, speaker=active.speaker}
end

function F.Expire(data)
    if data and data.generation == F.generation then F.Stop() end
end

function F.Start(entity, speaker, conversation, line, durationMs)
    F.Stop()
    local config = settings()
    if config.enabled == false then return false end
    local clip, layer = config.clip or "fa_cin_talk_neutral_01", config.layer or 12
    local function fail(reason)
        F.last = {status=reason, speaker=speaker, clip=clip, line=line}
        log(reason .. "; NPC=" .. tostring(entity and entity:GetName()) .. ", clip=" .. clip)
        return false
    end
    if not entity or type(entity.StartAnimation) ~= "function"
        or type(entity.StopAnimation) ~= "function" then return fail("animation_api_unavailable") end
    if type(entity.GetAnimationLength) == "function" then
        local ok, seconds = pcall(entity.GetAnimationLength, entity, 0, clip)
        if ok and type(seconds) == "number" and seconds <= 0 then return fail("clip_not_loaded") end
    end
    -- Facial-only CAF, slot 0/layer 12; never stop the NPC's body animation.
    local ok, result = pcall(entity.StartAnimation, entity, 0, clip, layer, 0.1, 1, true)
    if not ok or result == false then return fail("animation_start_failed") end
    F.current = {entityId=entity.id, name=entity:GetName(), speaker=speaker,
        wuid=tostring(entity.this.id),
        conversation=conversation, line=line, layer=layer}
    F.generation = F.generation + 1
    F.last = {status="requested", speaker=speaker, clip=clip, line=line}
    -- Safety cleanup also covers an interrupted external player or missing end cue.
    Script.SetTimerForFunction(durationMs+1000, "nebakovrising.VoiceFace.Expire", {generation=F.generation})
    log("Baslatildi: " .. speaker .. ", satir=" .. line .. ", clip=" .. clip
        .. ", API sonucu=" .. tostring(result))
    return true
end

function F.Test()
    local entity = nebakovrising.VoiceBridge.GetEntity("Marek")
    if not entity then
        local player = nebakovrising.Utils.GetPlayer()
        local pos = player and player:GetWorldPos()
        local closest = 20*20
        for _, run in pairs(nebakovrising.CastleUtils.activityRuns) do
            if run.kind == "patrol" and run.started and pos then
                local id = System.GetEntityIdByName(run.npcKey)
                local e = id and System.GetEntity(id)
                local p = e and e:GetWorldPos()
                if p then
                    local d = (p.x-pos.x)^2+(p.y-pos.y)^2+(p.z-pos.z)^2
                    if d < closest then closest, entity = d, e end
                end
            end
        end
    end
    if not entity then log("20 metre icinde test edilecek patrol NPC bulunamadi"); return end
    F.Start(entity, entity:GetName(), "face_test", 1, 5000)
end

if not F.commandsRegistered then
    System.AddCCommand("nebakov_voice_face_test", "nebakovrising.VoiceFace.Test()", "Tek guard'da 5 saniye agiz animasyonu dene")
    System.AddCCommand("nebakov_voice_face_stop", "nebakovrising.VoiceFace.Stop()", "Agiz animasyon testini durdur")
    F.commandsRegistered = true
end
