-- Small overwritten snapshot when verified available; game log bootstrap/fallback.
nebakovrising = nebakovrising or {}
nebakovrising.VoiceBridge = nebakovrising.VoiceBridge or {}
local Bridge = nebakovrising.VoiceBridge
local speakers = { "Marek", "Hertl" }
local marker = "NEBAKOV_VOICE_V1 "
Bridge.bindings = Bridge.bindings or {}
Bridge.generation = Bridge.generation or 0
Bridge.sequence = Bridge.sequence or 0

local function finite(value)
    return type(value) == "number" and value == value
        and value ~= math.huge and value ~= -math.huge
end

local function vector(value)
    if type(value) ~= "table" or not finite(value.x)
        or not finite(value.y) or not finite(value.z) then return nil end
    return { x = value.x, y = value.y, z = value.z }
end

local function quote(value)
    local escapes = { ['"'] = '\\"', ['\\'] = '\\\\', ['\n'] = '\\n',
        ['\r'] = '\\r', ['\t'] = '\\t', ['\b'] = '\\b', ['\f'] = '\\f' }
    return '"' .. tostring(value):gsub('[%z\1-\31\\"]', function(char)
        return escapes[char] or string.format('\\u%04x', string.byte(char))
    end) .. '"'
end

local function encode(value)
    if value == nil then return "null" end
    if type(value) == "boolean" then return value and "true" or "false" end
    if type(value) == "number" then
        if not finite(value) then return "null" end
        if value == math.floor(value) then return string.format("%.0f", value) end
        return (string.format("%.6f", value):gsub(",", "."))
    end
    if type(value) == "string" then return quote(value) end
    if type(value) ~= "table" then return "null" end
    local items = {}
    if #value > 0 then
        for _, item in ipairs(value) do items[#items + 1] = encode(item) end
        return "[" .. table.concat(items, ",") .. "]"
    end
    local keys = {}
    for key in pairs(value) do keys[#keys + 1] = key end
    table.sort(keys)
    for _, key in ipairs(keys) do items[#items + 1] = quote(key) .. ":" .. encode(value[key]) end
    return "{" .. table.concat(items, ",") .. "}"
end

local function log(message)
    if System and type(System.LogAlways) == "function" then
        System.LogAlways("[nebakovrising] [VoiceBridge] " .. message)
    end
end

local function session()
    Bridge.generation = Bridge.generation + 1
    Bridge.session = tostring(math.random(1000000, 1000000000)) .. "-" .. Bridge.generation
    Bridge.sequence = 0
end

local function readPosition(entity)
    if not entity then return nil end
    local ok, position = pcall(function() return entity:GetWorldPos() end)
    return ok and vector(position) or nil
end

function Bridge.Register(name, entity)
    if name ~= "Marek" and name ~= "Hertl" then return false, "unknown_speaker" end
    local ok, id, entityName = pcall(function() return entity.id, entity:GetName() end)
    if not ok or id == nil or type(entityName) ~= "string" or entityName == "" then
        return false, "invalid_entity_reference"
    end
    for speaker, binding in pairs(Bridge.bindings) do
        if speaker ~= name and (binding.id == id or binding.entityName == entityName) then
            return false, "duplicate_entity"
        end
    end
    Bridge.bindings[name] = { entity = entity, id = id, entityName = entityName }
    log(name .. " -> " .. entityName)
    return true
end

function Bridge.GetEntity(name)
    local binding = Bridge.bindings[name]
    if not binding then return nil, "unregistered" end
    if not System or type(System.GetEntity) ~= "function" then return nil, "lookup_unavailable" end
    local ok, entity = pcall(System.GetEntity, binding.id)
    if not ok or not entity then return nil, "despawned" end
    local valid, sameName, dead = pcall(function()
        return entity:GetName() == binding.entityName,
            entity.actor and type(entity.actor.IsDead) == "function" and entity.actor:IsDead() == true
    end)
    if not valid or not sameName then return nil, "entity_replaced" end
    if dead then return nil, "dead" end
    return entity
end

function Bridge.GetPosition(name)
    local entity, reason = Bridge.GetEntity(name)
    if not entity then return nil, reason end
    local position = readPosition(entity)
    if position then return position end
    return nil, "position_unavailable"
end

function Bridge.Snapshot(event)
    local npcs = {}
    for _, name in ipairs(speakers) do
        local position, reason = Bridge.GetPosition(name)
        local binding = Bridge.bindings[name]
        npcs[#npcs + 1] = { name = name, entity_name = binding and binding.entityName or "",
            voicesampleid = binding and nebakovrising.Voices and nebakovrising.Voices.Get(binding.entityName),
            available = position ~= nil, position = position, reason = reason }
    end
    local ok, player = pcall(function() return nebakovrising.Utils.GetPlayer() end)
    local playerPosition = ok and readPosition(player) or nil
    local forwardOk, forward = pcall(function() return player:GetDirectionVector(1) end)
    local forwardSource = "entity"
    if System and type(System.GetViewCameraDir) == "function" then
        local cameraOk, camera = pcall(System.GetViewCameraDir)
        if cameraOk and vector(camera) then
            forwardOk, forward, forwardSource = true, camera, "camera"
        end
    end
    local gameTimeOk, gameTime = pcall(function() return System.GetCurrTime() end)
    local triggerOk, hasTrigger = pcall(function()
        return type(player.ExecuteAudioTrigger) == "function"
    end)
    return { protocol = "nebakov_voice.v1", session = Bridge.session,
        seq = Bridge.sequence, event = event or "positions",
        game_time = gameTimeOk and finite(gameTime) and gameTime or 0,
        npcs = npcs,
        player = { name = "Henry", available = playerPosition ~= nil,
            position = playerPosition, forward = forwardOk and vector(forward) or nil,
            forward_source = forwardOk and forwardSource or "unavailable" },
        capabilities = {
            log = System ~= nil and type(System.LogAlways) == "function",
            file_io = type(io)=="table" and type(io.open)=="function",
            timer = Script ~= nil and type(Script.SetTimerForFunction) == "function",
            native_audio_trigger = triggerOk and hasTrigger or false,
            legacy_raw_wav_loader = Sound ~= nil and type(Sound.LoadSound) == "function",
            rom_file_audio = rom ~= nil and rom.audio ~= nil and type(rom.audio.play_file_3d) == "function",
        },
        director = nebakovrising.Conversations and nebakovrising.Conversations.Snapshot() or nil }
end

function Bridge.ConfigureTelemetry(path,confirm)
    if type(path)~="string" or #path>1024 or path:find("[%z\1-\31]") then return false end
    path=path:gsub("\\","/")
    if not path:match("/nebakov_voice/telemetry%.json$") then return false end
    if confirm then
        if path~=Bridge.filePath or not Bridge.fileReady then return false end
        if not Bridge.fileConfirmed then log("Telemetry channel=file (console packets disabled)") end
        Bridge.fileConfirmed=true
        return true
    end
    local keep=Bridge.fileConfirmed and Bridge.filePath==path
    Bridge.filePath,Bridge.fileConfirmed=path,keep==true
    Bridge.fileErrorLogged=false
    return true
end

local function transportStatus()
    return {mode=Bridge.fileConfirmed and "file" or "log",
        file_status=Bridge.fileConfirmed and "confirmed" or Bridge.fileError and "unavailable"
            or Bridge.filePath and "probing" or "not_requested",error=Bridge.fileError}
end

local function writeTelemetry(payload)
    if #payload>16384 then return false,"telemetry packet exceeds size limit" end
    if type(io)~="table" or type(io.open)~="function" then return false,"io.open unavailable" end
    local ok,failure=pcall(function()
        local stream,reason=io.open(Bridge.filePath,"w")
        if not stream then error(reason or "telemetry file open failed") end
        local wrote,result,why=pcall(stream.write,stream,payload.."\n")
        local closed,closeResult,closeError=pcall(stream.close,stream)
        if not wrote or not result or not closed or not closeResult then
            error(tostring(why or closeError or result or "telemetry write failed"))
        end
    end)
    return ok,not ok and tostring(failure):sub(1,180) or nil
end

function Bridge.NewSession()
    Bridge.Stop(true)
    session()
end

function Bridge.Emit(event)
    if not Bridge.session then session() end
    Bridge.sequence=Bridge.sequence+1
    if Bridge.filePath and type(io)=="table" and type(io.open)=="function" then Bridge.fileError=nil end
    local packet=Bridge.Snapshot(event)
    packet.transport=transportStatus()
    local payload=encode(packet)
    if Bridge.filePath then
        local ok,reason=writeTelemetry(payload)
        Bridge.fileReady=ok
        if ok and Bridge.fileConfirmed then return true end
        if not ok then
            Bridge.fileConfirmed=false;Bridge.fileError=reason
            packet.transport=transportStatus();payload=encode(packet)
            if not Bridge.fileErrorLogged then
                Bridge.fileErrorLogged=true;log("File telemetry unavailable; retaining log transport: "..tostring(reason))
            end
        end
    end
    if not System or type(System.LogAlways)~="function" then return false,"log_unavailable" end
    System.LogAlways(marker..payload)
    return true
end

function Bridge.Stop(quiet)
    Bridge.running = false
    Bridge.generation = Bridge.generation + 1
    if not quiet then
        if nebakovrising.Conversations then nebakovrising.Conversations.Stop() end
        Bridge.Emit("bridge_stopped")
    end
end

local function schedule()
    local config = nebakovrising.Config.voiceBridge or {}
    local delay = tonumber(config.sampleIntervalMs) or 1000
    delay = math.max(250, math.min(10000, delay))
    local ok = pcall(Script.SetTimerForFunction, delay,
        "nebakovrising.VoiceBridge.Tick", { generation = Bridge.generation })
    if not ok then Bridge.Stop(true); log("Timer baslatilamadi.") end
    return ok
end

function Bridge.Tick(data)
    if not Bridge.running or type(data) ~= "table" or data.generation ~= Bridge.generation then return end
    Bridge.Emit("positions")
    schedule()
end

function Bridge.Start()
    if not System or type(System.LogAlways) ~= "function" then return false end
    if not Script or type(Script.SetTimerForFunction) ~= "function" then
        log("Script.SetTimerForFunction kullanilamiyor.")
        return false
    end
    Bridge.Stop(true)
    session()
    Bridge.running = true
    Bridge.Emit("positions")
    return schedule()
end

-- Only labels existing guard references; does not spawn, rename or change roles.
function Bridge.BindExistingPair()
    if nebakovrising.Conversations then nebakovrising.Conversations.Stop() end
    local candidates, seen = {}, {}
    local function add(entity)
        if not entity then return end
        local ok, name = pcall(function() return entity:GetName() end)
        if not ok or seen[name] then return end
        local managed = string.sub(name, 1, 14) == "nebakovrising_"
            or (nebakovrising.CastleUtils and nebakovrising.CastleUtils.GetManagedNpcRole(name) ~= nil)
        if not managed then return end
        local role = nebakovrising.Roles.Resolve(name)
        local aliveOk, dead = pcall(function()
            return entity.actor and type(entity.actor.IsDead) == "function" and entity.actor:IsDead() == true
        end)
        if role and role.patrol and aliveOk and not dead and readPosition(entity) then
            candidates[#candidates + 1] = entity
            seen[name] = true
        end
    end
    for _, name in ipairs(nebakovrising.Spawner.GetSpawnedNames() or {}) do
        local id = System.GetEntityIdByName(name)
        add(id and System.GetEntity(id))
    end
    if #candidates < 2 then
        local loaded = {}
        for _, entity in pairs(System.GetEntitiesByClass("NPC") or {}) do
            local ok, name = pcall(function() return entity:GetName() end)
            if ok and type(name) == "string" then
                loaded[#loaded + 1] = { name = name, entity = entity }
            end
        end
        table.sort(loaded, function(a, b) return a.name < b.name end)
        for _, entry in ipairs(loaded) do add(entry.entity) end
    end
    if #candidates < 2 then log("En az iki yuklu mod guard'i gerekli; NPC spawn edilmedi."); return false end
    Bridge.Stop(true)
    Bridge.bindings = {}
    local first = Bridge.Register("Marek", candidates[1])
    local second = Bridge.Register("Hertl", candidates[2])
    if not first or not second then log("Iki farkli NPC kaydedilemedi."); return false end
    return Bridge.Start()
end

function Bridge.OnGameplayStarted()
    Bridge.Stop(true)
    Bridge.bindings = {}
    session()
    Bridge.Emit("world_reset")
    if nebakovrising.Conversations then nebakovrising.Conversations.OnGameplayStarted() end
end

-- Optional native backend probe. The installer supplies one existing WAV as a
-- Sound Framework pack; this never claims native success or replaces playback.
function Bridge.TestNativeAudio()
    local position, reason = Bridge.GetPosition("Marek")
    if not position then log("Native test: " .. tostring(reason)); return false end
    if not System or type(System.ExecuteCommand) ~= "function" then
        log("Native test: System.ExecuteCommand kullanilamiyor."); return false
    end
    local command = string.format("sfw_play nebakov_voice_probe %.6f %.6f %.6f",
        position.x, position.y, position.z):gsub(",", ".")
    local ok = pcall(System.ExecuteCommand, command)
    log("Native test komutu gonderildi=" .. tostring(ok) .. "; sesi ve Sound Framework logunu kontrol et.")
    return ok
end

if System and type(System.AddCCommand) == "function" and not Bridge.commandsRegistered then
    System.AddCCommand("nebakov_voice_bind_pair", "nebakovrising.VoiceBridge.BindExistingPair()", "Iki mevcut guard'i Marek/Hertl etiketle ve konum aktarimini baslat")
    System.AddCCommand("nebakov_voice_snapshot", "nebakovrising.VoiceBridge.Emit('positions')", "Bir konum paketi gonder")
    System.AddCCommand("nebakov_voice_trigger_test", "nebakovrising.VoiceBridge.Emit('conversation_trigger')", "Test olayi gonder; Gemini/TTS calistirmaz")
    System.AddCCommand("nebakov_voice_talk", "nebakovrising.VoiceBridge.Emit('conversation_requested')", "Python runtime'a konusma istegi gonder; yakinlik ve cooldown kontrol edilir")
    System.AddCCommand("nebakov_voice_native_test", "nebakovrising.VoiceBridge.TestNativeAudio()", "Sound Framework ile Marek konumunda tek WAV denemesi; runtime'i once durdur")
    System.AddCCommand("nebakov_voice_stop", "nebakovrising.VoiceBridge.Stop()", "Konum aktarimini durdur")
    Bridge.commandsRegistered = true
end
if UIAction and type(UIAction.RegisterEventSystemListener) == "function" and not Bridge.listenerRegistered then
    UIAction.RegisterEventSystemListener(Bridge, "System", "OnGameplayStarted", "OnGameplayStarted")
    Bridge.listenerRegistered = true
end
