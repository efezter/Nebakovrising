-- Only validated data crosses the external settings channel; no Lua prompt code.
nebakovrising.ConversationConfig={}
function nebakovrising.ConversationConfig.Apply(csv,profile)
    if type(csv)~="string" or #csv>512 or type(profile)~="string" or #profile>64
        or not profile:match("^[a-z0-9][a-z0-9_-]*$") then return false end
    local values={}
    for part in csv:gmatch("[^,]+") do
        local n=tonumber(part)
        if not n or n~=n or n==math.huge or n==-math.huge then return false end
        values[#values+1]=n
    end
    if #values~=10 or csv:sub(1,1)=="," or csv:sub(-1)=="," or csv:find(",,",1,true) then return false end
    for _,i in ipairs({1,2,8}) do if values[i]~=0 and values[i]~=1 then return false end end
    if not (values[3]>=1 and values[3]<=100
        and values[4]>=1 and values[4]<=values[5] and values[5]<=86400
        and values[4]==math.floor(values[4]) and values[5]==math.floor(values[5])
        and values[6]>=0 and values[6]<=86400 and values[7]>=0 and values[7]<=86400
        and values[9]>=15 and values[9]<=600 and values[10]>=0.5 and values[10]<=5) then return false end
    local keys={"enabled","randomEnabled","searchRadius",
        "randomMinSeconds","randomMaxSeconds","cooldownSeconds","npcCooldownSeconds",
        "prepareBeforeMeeting","generationTimeout","nearbyDistance"}
    local settings=nebakovrising.Config.conversations
    for i,key in ipairs(keys) do
        if i==1 or i==2 or i==8 then settings[key]=values[i]==1 else settings[key]=values[i] end
    end
    settings.patrolStartHour,settings.patrolEndHour=nil,nil
    settings.profileId=profile
    settings.playerExitRadius=settings.searchRadius+10
    local director=nebakovrising.Conversations
    if director and not director.active then
        director.nextRandom=System.GetCurrTime()+math.random(settings.randomMinSeconds,settings.randomMaxSeconds)
    end
    return true
end
