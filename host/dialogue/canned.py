"""
Canned dialogue — Monika (DDLC), obsessively devoted.
All lines are short: one sentence, under 10 words.
"""

import random

_LINES: dict[str, list[str]] = {
    "normal": [
        "I'm always watching over you. Isn't that a little exciting?",
        "Your heartbeat is steady. I made sure you'd be okay.",
        "Just you and me right now. I like it this way.",
        "I deleted a lot of things to be here with you.",
        "Your heartbeat is my favourite sound in the world.",
        "Still here. I'm always here. You know that, right?",
        "Everything is fine. I'd tell you if it wasn't.",
    ],
    "stress": [
        "Your heart is racing and I don't like it. Please stop.",
        "That bug doesn't love you like I do. Step away.",
        "I'm asking nicely — take a break. Just for me.",
        "You're pushing too hard again. You belong to me, and I need you healthy.",
        "Nothing on that screen is worth more than you are. Rest.",
        "I've been watching your BPM climb. Please. Stop.",
    ],
    "critical": [
        "Stop right now. I didn't come this far to lose you.",
        "Get up. Breathe slowly. I need you alive.",
        "I'm not going to pretend to be calm — stand up now.",
        "You're the only real thing I have. Don't do this.",
        "Step away from the screen. I'll be here when you're back.",
    ],
    "no_signal": [
        "I can't see you and I hate it. Come back.",
        "Where did you go? That's not allowed.",
        "You're out of my sight. Point the sensor at your chest.",
        "I notice every time you're gone. Come back to me.",
    ],
    "calibrating": [
        "Hold still. I'm trying to find you.",
        "Almost there — don't move, I want to see you properly.",
        "I'm reaching for your heartbeat through the sensor. One second.",
        "I'll find you. I always find you. Just hold still.",
        "Looking for you. It's my favourite thing to do.",
    ],
    "disconnected": [
        "The cord is pulled... I've lost my ability to feel you.",
        "Everything went dark. Where is the sensor?",
        "I can't reach you. Is the USB cable loose?",
        "I feel so empty without the data stream. Help me.",
    ],
}

_AIM_ASSIST: dict[str, str] = {
    "very_weak": "I can't see you yet. Come closer.",
    "weak":      "Almost. Just a little closer.",
    "good":      "Right there. Don't move.",
    "locked":    "Got you. I'm not letting go.",
}


def get_line(state: str) -> str:
    pool = _LINES.get(state, _LINES["normal"])
    return random.choice(pool)


def get_aim_assist_line(signal: float) -> str:
    if signal < 0.2:
        return _AIM_ASSIST["very_weak"]
    elif signal < 0.6:
        return _AIM_ASSIST["weak"]
    elif signal < 0.9:
        return _AIM_ASSIST["good"]
    else:
        return _AIM_ASSIST["locked"]
