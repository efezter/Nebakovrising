"""Project runtime + actual Lua/BT protocol + real WAVs; mock navigation/dummy audio.

Run with the development Python (lupa installed). No game or Gemini calls.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import sys
import wave

from nebakov_voice_runtime import latest_manifest
from nebakov_voice_playback import load_manifest
from test_patrol_conversations import LuaDirectorTests, ConversationDriver


def main():
    server=Path(r'D:\NebakovVoice\server')
    fixture=LuaDirectorTests();fixture.setUp()
    lua=fixture.lua;lua.execute('D.peer=nil')
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
        folder=Path(temp);game_log=folder/'game.log';console=folder/'console.log';command=folder/'command.lua'
        if '--fixture' in sys.argv:
            rows=[]
            for i in range(1,5):
                name=f'{i}.wav'
                with wave.open(str(folder/name),'wb') as f:
                    f.setparams((1,2,24000,0,'NONE','not compressed'));f.writeframes(b'\0\0'*4800)
                rows.append({'index':i,'speaker':'Marek' if i%2 else 'Hertl','audio_file':name})
            manifest=folder/'conversation.json';manifest.write_text(json.dumps({'lines':rows}))
        else:
            manifest=latest_manifest()
        lines=load_manifest(manifest)
        hashes={line.path:hashlib.sha256(line.path.read_bytes()).hexdigest() for line in lines}
        def read_control(path):
            if path != 'Data/Scripts/nebakov_voice/command.lua':raise FileNotFoundError(path)
            return command.read_text('ascii')
        lua.globals().read_control=read_control
        lua.execute('dofile=function(path) return assert(loadstring(read_control(path)))() end')
        game_log.write_bytes(b'old\n')
        with console.open('w',encoding='utf-8') as output:
            process=subprocess.Popen([str(server/'.venv/Scripts/python.exe'),'-B','-u',str(Path(__file__).with_name('nebakov_voice_runtime.py')),
                '--director','--manifest',str(manifest),'--command-file',str(command),'--game-log',str(game_log),
                '--output-dir',str(folder),'--engine-dir',str(folder),'--once','--stale-after','4'],
                env={**os.environ,'SDL_AUDIODRIVER':'dummy','PYGAME_HIDE_SUPPORT_PROMPT':'1'},
                stdout=output,stderr=subprocess.STDOUT)
        try:
            start=time.monotonic();selected=None;drivers=[]
            while 'READY:' not in console.read_text('utf-8'):
                if process.poll() is not None or time.monotonic()-start>10:
                    raise RuntimeError(console.read_text('utf-8'))
                time.sleep(.05)
            while process.poll() is None:
                elapsed=time.monotonic()-start
                if elapsed>sum(line.seconds for line in lines)+20:
                    raise RuntimeError('Patrol smoke timed out: '+console.read_text('utf-8'))
                lua.globals().clock=100+elapsed
                lua.execute('C.ActivityHeartbeat(a.this.id,ta); C.ActivityHeartbeat(b.this.id,tb)')
                if selected is None and lua.eval('D.peer ~= nil and D.peer.ready == true'):
                    lua.execute('assert(D.TryStart(true));p1=D.active.participants[1];p2=D.active.participants[2]')
                    selected=elapsed;g=lua.globals()
                    drivers=[ConversationDriver(lua,g.System.GetEntity(g.p1.entityId),g.p1.token),
                             ConversationDriver(lua,g.System.GetEntity(g.p2.entityId),g.p2.token,blocked=True)]
                if drivers and elapsed-selected>=3:drivers[1].blocked=False
                for driver in drivers:
                    if driver.generator:
                        try:next(driver.generator)
                        except StopIteration as result:
                            assert result.value
                            driver.generator=None
                            lua.globals().C.FinishNpcActivity(driver.entity.this.id,driver.token)
                lua.execute('D.Tick({generation=D.generation})')
                packet=fixture.packet()
                with game_log.open('ab') as stream:
                    stream.write(b'NEBAKOV_VOICE_V1 '+json.dumps(packet).encode()+b'\n')
                journal=folder/'bridge_events.jsonl'
                events=[json.loads(s) for s in journal.read_text().splitlines()] if journal.exists() else []
                if drivers and elapsed-selected<3:
                    assert not any(e['event']=='line_started' for e in events)
                time.sleep(.1)
            if process.returncode:raise RuntimeError(console.read_text('utf-8'))
            events=[json.loads(s) for s in (folder/'bridge_events.jsonl').read_text().splitlines()]
            assert [e['speaker'] for e in events if e['event']=='line_started']==['Marek','Hertl','Marek','Hertl']
            assert any(e['event']=='control_ack' and e['accepted'] for e in events)
            assert any(e['event']=='conversation_finished' for e in events)
            assert lua.eval("D.active==nil and D.last.phase=='finished'")
            assert lua.eval("nebakovrising.VoiceFace.current==nil and #a.faceStarts+#b.faceStarts==4")
            assert len([e for e in events if e['event']=='control_ack' and e['kind']=='line_start' and e['accepted']])==4
            for path,digest in hashes.items():assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
            print('PASS: project runtime + Lua command/ACK + BT stand/approach/turn gates + four WAVs on dummy audio; no premature playback. Fixture audio='+str('--fixture' in sys.argv))
            print('Game APIs/navigation were mocked; in-game approach/control-channel validation remains required.')
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
