nebakovrising.Subtitles={}
local S=nebakovrising.Subtitles
local function cfg() return nebakovrising.Config.subtitles or {} end
local function log(text) nebakovrising.Utils.Log("[Subtitles] "..text) end
local function renderer()
    local entity=S.renderer and System.GetEntity(S.renderer)
    return entity and entity.GetName and entity:GetName()=="nebakov_subtitle_renderer" and entity or nil
end
function S.Stop(scene,line)
    local a=S.active
    if a and ((scene and scene~=a.scene) or (line and line~=a.line)) then return end
    S.active=nil
    local drawing=renderer()
    if drawing and drawing.Activate then drawing:Activate(0) end
end
function S.Pages(text)
    local pages,lines,line={}, {},""
    for word in text:gmatch("%S+") do
        if #line+#word+1>48 and line~="" then lines[#lines+1]=line;line="" end
        if #lines==2 then pages[#pages+1]=table.concat(lines,"\n");lines={} end
        line=line=="" and word or line.." "..word
    end
    if line~="" then lines[#lines+1]=line end
    if #lines>0 then pages[#pages+1]=table.concat(lines,"\n") end
    return pages
end
function S.Start(entity,scene,line,text,duration)
    S.Stop()
    if cfg().enabled==false or type(text)~="string" or text=="" then return false end
    if #text>2400 or text:find("[%z\1-\8\11\12\14-\31]") or not entity then return false end
    if not System or type(System.DrawLabel)~="function" then log("DrawLabel unavailable");return false end
    local drawing=renderer()
    if not drawing then
        local ok,result=pcall(System.SpawnEntity,{class="NebakovSubtitle",name="nebakov_subtitle_renderer",
            position={x=0,y=0,z=-100},properties={bSaved_by_game=0,bSerialize=0}})
        drawing=ok and result
        if not drawing then log("Renderer entity could not be created; restart with the updated pak");return false end
        S.renderer=drawing.id
    end
    local pages=S.Pages(text);if #pages==0 then return false end
    S.active={id=entity.id,name=entity:GetName(),scene=scene,line=line,pages=pages,started=System.GetCurrTime(),seconds=duration/1000}
    drawing:Activate(1)
    return true
end
function S.Render()
    local a=S.active
    if not a then return end
    local elapsed=System.GetCurrTime()-a.started
    local entity=System.GetEntity(a.id)
    local player=nebakovrising.Utils.GetPlayer()
    if elapsed<0 or elapsed>=a.seconds or not entity or entity:GetName()~=a.name or not player then S.Stop();return end
    local good,pos=pcall(entity.GetWorldPos,entity)
    local ok,here=pcall(player.GetWorldPos,player)
    if not good or not ok or not pos or not here then S.Stop();return end
    local radius=cfg().maxDistance or 24
    if (pos.x-here.x)^2+(pos.y-here.y)^2+(pos.z-here.z)^2>radius^2 then return end
    local index=math.min(#a.pages,math.floor(elapsed/a.seconds*#a.pages)+1)
    local at={x=pos.x,y=pos.y,z=pos.z+(cfg().height or 2.1)}
    local drawn,error=pcall(System.DrawLabel,at,cfg().fontSize or 1.15,a.pages[index],1,0.94,0.78,1)
    if not drawn then log("DrawLabel failed: "..tostring(error));S.Stop() end
    if drawn and not S.renderSeen then S.renderSeen=true;log("World label render callback active") end
end
function S.Test()
    local player=nebakovrising.Utils.GetPlayer()
    local here=player and player:GetWorldPos()
    local entity=nebakovrising.VoiceBridge.GetEntity("Marek")
    if entity and here then
        local pos=entity:GetWorldPos()
        if (pos.x-here.x)^2+(pos.y-here.y)^2+(pos.z-here.z)^2>20^2 then entity=nil end
    end
    if not entity then
        local best=20^2
        for _,run in pairs(nebakovrising.CastleUtils.activityRuns) do
            local id=System.GetEntityIdByName(run.npcKey);local npc=id and System.GetEntity(id)
            local pos=npc and npc:GetWorldPos()
            if pos and here then
                local d=(pos.x-here.x)^2+(pos.y-here.y)^2+(pos.z-here.z)^2
                if d<best then entity,best=npc,d end
            end
        end
    end
    if not entity then log("No guard within 20 m");return end
    S.Start(entity,"subtitle_test",1,"Hey! Can you read this above my head?",8000)
end
