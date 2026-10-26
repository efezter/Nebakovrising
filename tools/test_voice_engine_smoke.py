"""Explicit live adapter check: one Gemini conversation and existing TTS service, no audio."""
import argparse
import multiprocessing as mp
from pathlib import Path
import time

from nebakov_voice_runtime import Worker
from nebakov_voice_playback import load_manifest
from nebakov_voice_config import load_config
from nebakov_voice_prompts import PromptProfiles
from nebakov_voice_samples import discover


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true", help="Authorize this test's one real Gemini request")
    args = parser.parse_args()
    if not args.generate:
        parser.error("Use --generate to make one real conversation request")
    settings=load_config()
    prompts=PromptProfiles();prompts.load(settings['profileId'])
    voices=discover(Path(r'D:\NebakovVoice\tts\voices'))['ids']
    worker = Worker(Path(r"D:\NebakovVoice\server"), lambda event, **kw: print(event, flush=True),
        prompts=prompts,prewarm=settings.get('prewarmModel',True))
    try:
        while not worker.ready:
            worker.poll()
            time.sleep(0.05)
        job = worker.submit({"session": "adapter_smoke_not_game", "seq": 1,
            "npcs":[{'name':'Marek','voicesampleid':voices[0]},{'name':'Hertl','voicesampleid':voices[1%len(voices)]}],
            "director":{"id":"smoke", "behavior":"patrol", "profile_id":settings['profileId'],
                "context":{"hour":14,"time_of_day":"afternoon","location":"Nebakov Castle",
                    "trigger":"adapter_smoke_not_game","guard_a":"fixture_guard_a","guard_b":"fixture_guard_b",
                    "guard_a_role":"guard_melee","guard_b_role":"guard_ranged"}}})
        while True:
            for result in worker.poll():
                if result["id"] != job or result["kind"] != "result":
                    raise RuntimeError(result.get("error", "Unexpected adapter result"))
                lines = load_manifest(Path(result["manifest"]))
                assert [l.speaker for l in lines] == ["Marek", "Hertl", "Marek", "Hertl"]
                print("PASS: one real conversation request, four valid WAVs, atomic manifest:", result["manifest"], flush=True)
                print("No in-game trigger or audio was exercised.", flush=True)
                return
            time.sleep(0.05)
    finally:
        worker.close()


if __name__ == "__main__":
    mp.freeze_support()
    main()
