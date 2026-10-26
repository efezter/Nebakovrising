"""Editable prompt profiles, filled only with bounded Lua context data."""
import json
from pathlib import Path
import random
import math
import re
from string import Template
from nebakov_voice_config import PROFILE_ID

DEFAULT_PROFILES = Path(r"D:\NebakovVoice\config\prompts")

class PromptProfiles:
    def __init__(self, directory=DEFAULT_PROFILES, rng=None):
        self.directory = Path(directory)
        self.rng = rng or random.Random()
        self.profiles, self.bags, self.last = {}, {}, {}

    def load(self, profile):
        if not isinstance(profile, str) or not PROFILE_ID.fullmatch(profile): raise ValueError("Invalid prompt profile ID")
        if profile not in self.profiles:
            path = self.directory / (profile + ".json")
            if path.stat().st_size > 32768: raise ValueError("Prompt profile exceeds 32 KB")
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
            if doc.get("version") != 1 or doc.get("id") != profile: raise ValueError("Prompt profile ID/version mismatch")
            if not isinstance(doc.get("template"), str) or not 1 <= len(doc["template"]) <= 16000: raise ValueError("Invalid prompt template")
            topics = doc.get("topics")
            if not isinstance(topics, list) or not 1 <= len(topics) <= 100 or any(not isinstance(t,str) or not 1 <= len(t) <= 1000 for t in topics):
                raise ValueError("Invalid prompt topics")
            self.profiles[profile] = doc
        return self.profiles[profile]

    def prepare(self, packet):
        director = packet.get("director") or {}
        if director.get("behavior") not in {"patrol","meal","idle"}: raise ValueError("No prompt handler for this behavior")
        profile = director.get("profile_id")
        doc = self.load(profile)
        context = director.get("context") or {}
        if not isinstance(context,dict): raise ValueError("Invalid Lua context")
        bag = self.bags.setdefault(profile, [])
        if not bag:
            bag.extend(doc["topics"]); self.rng.shuffle(bag)
            if len(bag)>1 and bag[-1] == self.last.get(profile): bag[0],bag[-1] = bag[-1],bag[0]
        topic = bag.pop(); self.last[profile] = topic
        def plain(key, default="unknown", limit=500):
            value = context.get(key, default)
            if not isinstance(value,(str,int,float)) or isinstance(value,bool): raise ValueError(f"Invalid context {key}")
            return str(value)[:limit]
        params = {key:plain(key) for key in ("location","hour","time_of_day","trigger","guard_a","guard_b","guard_a_role","guard_b_role")}
        params.update(guard_a_name=plain('guard_a_name','Marek',80),guard_b_name=plain('guard_b_name','Hertl',80),
                      guard_a_activity=plain('guard_a_activity','patrol',80),guard_b_activity=plain('guard_b_activity','patrol',80))
        for key,value in context.items():
            if isinstance(key,str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}",key):
                if isinstance(value,str) or (type(value) in (int,float) and math.isfinite(value)):
                    params[key]=str(value)[:500]
        params.update(event_kind=plain("event_kind","none"), event_text=plain("event_text","No verified recent event supplied."), topic=topic)
        try: text = Template(doc["template"]).substitute(params)
        except (KeyError, ValueError) as error: raise ValueError(f"Invalid prompt placeholder: {error}") from error
        return {"text":text, "profile_id":profile, "prompt_parameters":params}
