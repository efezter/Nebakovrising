"""Factory bootstrap data; editable settings live only in NebakovVoice/config."""
from copy import deepcopy
import json
from pathlib import Path

DEFAULT_SETTINGS = {'version': 1,
 'enabled': True,
 'randomEnabled': True,
 'nearbyDistance': 2,
 'searchRadius': 20,
 'randomMinSeconds': 120,
 'randomMaxSeconds': 240,
 'cooldownSeconds': 0,
 'npcCooldownSeconds': 0,
 'prepareBeforeMeeting': True,
 'generationTimeout': 240,
 'profileId': 'patrol-daily-talk',
 'prewarmModel': True}

DEFAULT_PROFILE = {'version': 1,
 'id': 'patrol-daily-talk',
 'template': 'Write four short, natural ambient dialogue lines between two colleagues at '
             '$location. Marek and Hertl are speaker aliases for the selected guards, not '
             'permanent names. Runtime identities: Marek=$guard_a ($guard_a_role), Hertl=$guard_b '
             '($guard_b_role). Their activity is patrol; the game hour is $hour ($time_of_day). '
             'Trigger: $trigger. Verified recent event: $event_kind â€” $event_text. If a verified '
             'event is supplied, let it guide the conversation; otherwise use this everyday topic: '
             '$topic. They will briefly meet and then resume their duties. Henry is an overhearer, '
             'not the addressee. Focus on ordinary human chitchat, with both voices responding to '
             'each other. Use one coherent topic, natural English and a restrained medieval '
             'Bohemian tone. Vary the opening and mood; do not routinely ask for reports or repeat '
             'guard-duty jokes. Do not invent current attacks, deaths, weather, quests or local '
             'incidents. Past memories can be modest and personal; do not contradict known '
             'character facts or invent precise permanent family biographies. Avoid modern slang, '
             'exposition, stage directions and movement instructions. Spoken lines only; alternate '
             'Marek/Hertl as required by the engine.',
 'topics': ['A small memory of home or something they miss about family life, without inventing '
            'named relatives.',
            'An ordinary inconvenience in castle life: food, sleep, laundry or a troublesome piece '
            'of equipment.',
            'A modest memory from an earlier campaign: a long march, a miserable camp or a '
            "comrade's harmless mistake; avoid invented historical specifics.",
            'Village celebrations, courting or tavern customs discussed generally, without '
            'claiming a new event actually happened.',
            'Small money worries, saving for something useful or the temptation to waste wages.',
            'A childhood habit or practical lesson remembered with mild embarrassment or '
            'affection.',
            'Friendly teasing about personal habits, followed by a natural response rather than a '
            'forced punchline.',
            'Hopes for a quieter life, a small plot of land or a trade they might learn someday.',
            'A practical household or camp skill that one of them swears by and the other '
            'questions.',
            'A reflective memory of an old friend or travelling companion, without inventing a '
            'recent death.']}


DEFAULT_PROFILE['template'] += (
    ' The actual spoken names are $guard_a_name (speaker label Marek) and '
    '$guard_b_name (speaker label Hertl). Keep those Marek/Hertl output labels '
    'for routing, but use the actual names inside spoken sentences. Open with '
    'a brief natural greeting addressing the other guard by name, such as '
    '"Hey, $guard_b_name!" or "$guard_b_name, a moment?", before the topic. '
    'Vary the greeting; do not repeat names in every line.')

DEFAULT_MEAL_PROFILE={
    'version':1,'id':'meal-daily-talk',
    'template': ('Write four short, natural ambient dialogue lines at $location. '
        'The actual names are $guard_a_name (speaker label Marek) and $guard_b_name (speaker label Hertl). '
        'Keep Marek/Hertl JSON speaker labels for audio routing; use actual names in spoken text. '
        'Their actual activities are $guard_a_activity and $guard_b_activity; at least one is seated eating. '
        'Both stay in their current posture, with no walking, standing up or forced turning. '
        'The game hour is $hour ($time_of_day). Verified event: $event_text. '
        'Begin with a short varied greeting addressing the other guard by name. '
        'Have a relaxed conversation about $topic. Do not narrate actions or address Henry. '
        'Do not invent current incidents or permanent family facts.'),
    'topics':['The taste of the food and a meal remembered from home.',
        'A small family memory or a familiar household habit.',
        'A modest story from an old journey or military campaign.',
        'Friendly teasing, tired feet, wages or plans for a quieter life.']}
DEFAULT_IDLE_PROFILE=deepcopy(DEFAULT_MEAL_PROFILE)
DEFAULT_IDLE_PROFILE['id']='idle-daily-talk'
DEFAULT_IDLE_PROFILE['template']=DEFAULT_IDLE_PROFILE['template'].replace(
    'at least one is seated eating.', 'they are resting or waiting nearby, not necessarily eating.')
DEFAULT_IDLE_PROFILE['topics']=deepcopy(DEFAULT_PROFILE['topics'])

NATURAL_CLOSING = (
    ' Conclude the exchange naturally within the four lines. The final (fourth) '
    'line must be a short closing response tied to the current topic: an '
    'acknowledgment, resolution, shared sentiment or gentle final joke that '
    'answers the previous speaker. Leave no unanswered question, new topic '
    'or cliffhanger in the final line. Vary the ending to fit the subject '
    'and mood. Do not routinely use a stock farewell or say they are leaving, '
    'returning to work or finishing their meal; the game controls their activity. '
    'Use spoken dialogue only, without narration or stage directions.')
for _profile in (DEFAULT_PROFILE, DEFAULT_MEAL_PROFILE, DEFAULT_IDLE_PROFILE):
    _profile['template'] += NATURAL_CLOSING

def ensure_defaults(root):
    root=Path(root)
    for relative,value in [("conversations.json",DEFAULT_SETTINGS),("prompts/patrol-daily-talk.json",DEFAULT_PROFILE),
            ("prompts/meal-daily-talk.json",DEFAULT_MEAL_PROFILE),("prompts/idle-daily-talk.json",DEFAULT_IDLE_PROFILE)]:
        path=root/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        try:
            with path.open("x",encoding="utf-8") as stream:
                json.dump(deepcopy(value),stream,indent=2,ensure_ascii=False)
                stream.write("\n")
        except FileExistsError:
            pass
    return root
