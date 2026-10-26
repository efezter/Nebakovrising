NebakovSubtitle={Properties={bSaved_by_game=0,bSerialize=0}}
function NebakovSubtitle:OnInit() self:Activate(0) end
function NebakovSubtitle:OnSpawn() self:Activate(0) end
function NebakovSubtitle:OnUpdate(dt)
    if nebakovrising and nebakovrising.Subtitles then nebakovrising.Subtitles.Render() end
end
