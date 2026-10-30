"""Multilingual AI Voice Assistant Service for SafarSetu Transit.

Provides:
1. Google Gemini Generative AI Integration (when GEMINI_API_KEY is configured in backend/.env).
2. Advanced Built-in Multilingual Transit NLU (zero external API keys needed, always active as reliable fallback).
3. Timetable-aware route planning & conversational follow-ups across English, Hindi (Devanagari), and Hinglish.
4. Voice-activated emergency rerouting for missed stops, vehicle cancellations, or lost commuters.
5. Spoken step-by-step navigation guidance (walking, boarding, interchanges, intermediate stops, arrival).
6. Delhi transit FAQ intelligence (Metro timings, smart card discounts, luggage limits, tourist monument gates).
"""
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import google.generativeai as genai

from app.core.config import settings
from app.models.journey import RouteRankCriterion
from app.models.transit import StopTime
from app.schemas.voice import (
    VoiceQueryRequest,
    VoiceQueryResponse,
    VoiceStepGuidance,
    VoiceStepGuidanceRequest,
)
from app.services.data_source_service import get_transit_context
from app.repositories.safety_repository import SafetyRepository
from app.services.route_ranker import RouteRanker
from app.utils.geo import haversine_meters


# Known transit aliases and major landmarks for Delhi Commuters & Tourists
STATION_ALIASES: Dict[str, Dict[str, Any]] = {
    "cp": {"stop_id": "metro_122", "name": "Rajiv Chowk (Connaught Place)"},
    "connaught place": {"stop_id": "metro_122", "name": "Rajiv Chowk (Connaught Place)"},
    "rajiv chowk": {"stop_id": "metro_122", "name": "Rajiv Chowk"},
    "कनॉट प्लेस": {"stop_id": "metro_122", "name": "Rajiv Chowk (Connaught Place)"},
    "राजीव चौक": {"stop_id": "metro_122", "name": "Rajiv Chowk"},

    "ndls": {"stop_id": "metro_110", "name": "New Delhi Metro Station"},
    "new delhi": {"stop_id": "metro_110", "name": "New Delhi Metro Station"},
    "new delhi railway station": {"stop_id": "metro_110", "name": "New Delhi Metro Station"},
    "new delhi station": {"stop_id": "metro_110", "name": "New Delhi Metro Station"},
    "नई दिल्ली रेलवे स्टेशन": {"stop_id": "metro_110", "name": "New Delhi Metro Station"},
    "नई दिल्ली": {"stop_id": "metro_110", "name": "New Delhi Metro Station"},

    "india gate": {"stop_id": "metro_80", "name": "Central Secretariat (India Gate)"},
    "इंडिया गेट": {"stop_id": "metro_80", "name": "Central Secretariat (India Gate)"},
    "central secretariat": {"stop_id": "metro_80", "name": "Central Secretariat"},
    "केंद्रीय सचिवालय": {"stop_id": "metro_80", "name": "Central Secretariat"},

    "qutub minar": {"stop_id": "metro_119", "name": "Qutab Minar"},
    "qutab minar": {"stop_id": "metro_119", "name": "Qutab Minar"},
    "कुतुब मीनार": {"stop_id": "metro_119", "name": "Qutab Minar"},

    "hauz khas": {"stop_id": "metro_91", "name": "Hauz Khas"},
    "हौज खास": {"stop_id": "metro_91", "name": "Hauz Khas"},
    "हौज़ खास": {"stop_id": "metro_91", "name": "Hauz Khas"},

    "kashmere gate": {"stop_id": "metro_99", "name": "Kashmere Gate ISBT"},
    "isbt": {"stop_id": "metro_99", "name": "Kashmere Gate ISBT"},
    "isbt kashmere gate": {"stop_id": "metro_99", "name": "Kashmere Gate ISBT"},
    "कश्मीरी गेट": {"stop_id": "metro_99", "name": "Kashmere Gate ISBT"},

    "aiims": {"stop_id": "metro_72", "name": "AIIMS"},
    "aims": {"stop_id": "metro_72", "name": "AIIMS"},
    "एम्स": {"stop_id": "metro_72", "name": "AIIMS"},

    "akshardham": {"stop_id": "metro_74", "name": "Akshardham"},
    "akshardham temple": {"stop_id": "metro_74", "name": "Akshardham"},
    "अक्षरधाम": {"stop_id": "metro_74", "name": "Akshardham"},

    "red fort": {"stop_id": "metro_102", "name": "Lal Quila (Red Fort)"},
    "lal quila": {"stop_id": "metro_102", "name": "Lal Quila"},
    "lal qila": {"stop_id": "metro_102", "name": "Lal Quila"},
    "लाल किला": {"stop_id": "metro_102", "name": "Lal Quila"},

    "chandni chowk": {"stop_id": "metro_83", "name": "Chandni Chowk"},
    "old delhi railway station": {"stop_id": "metro_83", "name": "Chandni Chowk (Old Delhi)"},
    "old delhi": {"stop_id": "metro_83", "name": "Chandni Chowk (Old Delhi)"},
    "चाँदनी चौक": {"stop_id": "metro_83", "name": "Chandni Chowk"},

    "lotus temple": {"stop_id": "metro_97", "name": "Kalkaji Mandir (Lotus Temple)"},
    "लोटस टेम्पल": {"stop_id": "metro_97", "name": "Kalkaji Mandir (Lotus Temple)"},
    "kalkaji mandir": {"stop_id": "metro_97", "name": "Kalkaji Mandir"},

    "delhi university": {"stop_id": "metro_140", "name": "Vishwavidyalaya (Delhi University)"},
    "du": {"stop_id": "metro_140", "name": "Vishwavidyalaya (Delhi University)"},
    "vishwa vidyalaya": {"stop_id": "metro_140", "name": "Vishwavidyalaya"},
    "vishwavidyalaya": {"stop_id": "metro_140", "name": "Vishwavidyalaya"},
    "विश्वविद्यालय": {"stop_id": "metro_140", "name": "Vishwavidyalaya"},

    "airport": {"stop_id": "metro_92", "name": "IGI Airport Terminal 3"},
    "igi airport": {"stop_id": "metro_92", "name": "IGI Airport Terminal 3"},
    "t3": {"stop_id": "metro_92", "name": "IGI Airport Terminal 3"},
    "terminal 3": {"stop_id": "metro_92", "name": "IGI Airport Terminal 3"},
    "aerocity": {"stop_id": "metro_71", "name": "Delhi Aerocity"},

    "saket": {"stop_id": "metro_127", "name": "Saket"},
    "साकेत": {"stop_id": "metro_127", "name": "Saket"},

    "lajpat nagar": {"stop_id": "metro_101", "name": "Lajpat Nagar"},
    "लाजपत नगर": {"stop_id": "metro_101", "name": "Lajpat Nagar"},

    "karol bagh": {"stop_id": "metro_98", "name": "Karol Bagh"},
    "करोल बाग": {"stop_id": "metro_98", "name": "Karol Bagh"},

    "anand vihar": {"stop_id": "metro_77", "name": "Anand Vihar ISBT"},
    "आनंद विहार": {"stop_id": "metro_77", "name": "Anand Vihar ISBT"},

    "noida": {"stop_id": "metro_137", "name": "Wave City Center Noida"},
    "noida city centre": {"stop_id": "metro_137", "name": "Wave City Center Noida"},
    "sector 18": {"stop_id": "metro_137", "name": "Noida Sector 18"},
    "नोएडा": {"stop_id": "metro_137", "name": "Wave City Center Noida"},

    "dwarka": {"stop_id": "metro_88", "name": "Dwarka Sector 21"},
    "द्वारका": {"stop_id": "metro_88", "name": "Dwarka Sector 21"},

    "gurugram": {"stop_id": "metro_90", "name": "Millennium City Centre Gurugram"},
    "gurgaon": {"stop_id": "metro_90", "name": "Millennium City Centre Gurugram"},
    "cyber city": {"stop_id": "metro_90", "name": "Millennium City Centre Gurugram"},
    "huda city centre": {"stop_id": "metro_90", "name": "Millennium City Centre Gurugram"},

    "rohini": {"stop_id": "metro_124", "name": "Rohini West"},
    "रोहिणी": {"stop_id": "metro_124", "name": "Rohini West"},

    "janakpuri": {"stop_id": "metro_94", "name": "Janakpuri West"},
    "जनकपुरी": {"stop_id": "metro_94", "name": "Janakpuri West"},

    "iit": {"stop_id": "metro_93", "name": "IIT Delhi"},
    "iit delhi": {"stop_id": "metro_93", "name": "IIT Delhi"},
    "आईआईटी": {"stop_id": "metro_93", "name": "IIT Delhi"},

    "dilli haat": {"stop_id": "metro_85", "name": "Dilli Haat INA"},
    "ina": {"stop_id": "metro_85", "name": "Dilli Haat INA"},

    "jama masjid": {"stop_id": "metro_95", "name": "Jama Masjid"},
    "जामा मस्जिद": {"stop_id": "metro_95", "name": "Jama Masjid"},

    "mandi house": {"stop_id": "metro_107", "name": "Mandi House"},
}

HINGLISH_MARKERS = {
    "mujhe", "mera", "meri", "humko", "jaana", "jana", "hai", "batao", "bataiye",
    "kaise", "kaha", "kahan", "pahuchu", "pahuchna", "sasta", "sabse", "tez",
    "jaldi", "kam", "paise", "kiraya", "kharcha", "kitna", "lagega", "chhut", "chut",
    "gaya", "chhoot", "madad", "chahiye", "roko", "agla", "pehle", "chhod", "bhatak",
    "galat", "station", "pe", "par", "se", "tak", "karo", "aur", "dono", "nahi", "ruk"
}


class MultilingualVoiceAssistant:
    """Intelligent multilingual conversational engine for SafarSetu transit."""

    @classmethod
    def get_configured_gemini_key(cls) -> Optional[str]:
        """Check for user-configured Gemini API key."""
        k = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if k and k.strip():
            return k.strip()
        return None

    @classmethod
    def detect_language(cls, text: str, user_hint: Optional[str] = "auto") -> str:
        """Detect the input language from text patterns."""
        if user_hint and user_hint != "auto":
            return user_hint.lower()

        # Check for Devanagari Unicode block
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"

        text_lower = text.lower()
        words = set(re.findall(r"\b\w+\b", text_lower))

        # Check for Hinglish markers
        if len(words.intersection(HINGLISH_MARKERS)) >= 2 or any(w in words for w in ["jaana", "batao", "sasta", "chhut"]):
            return "hinglish"

        if any(w in words for w in ["bonjour", "comment", "merci", "aller"]):
            return "fr"
        if any(w in words for w in ["hola", "gracias", "como"]):
            return "es"
        if any(w in words for w in ["guten", "danke", "wie"]):
            return "de"

        return "en"

    @classmethod
    def resolve_target_language(cls, detected: str, user_pref: Optional[str] = "auto") -> str:
        """Determine what language to respond in."""
        if user_pref and user_pref != "auto":
            return user_pref.lower()
        return detected

    @classmethod
    def find_stop_by_name(cls, query_name: str) -> Optional[Tuple[str, str]]:
        """Resolve a freeform text landmark/stop to a verified Stop ID and Name in GTFS."""
        q = query_name.strip().lower()
        if not q:
            return None

        # 1. Exact alias match
        if q in STATION_ALIASES:
            item = STATION_ALIASES[q]
            return item["stop_id"], item["name"]

        # 2. Check sorted aliases (longest substring match first)
        for alias in sorted(STATION_ALIASES.keys(), key=len, reverse=True):
            if alias in q or q in alias:
                item = STATION_ALIASES[alias]
                return item["stop_id"], item["name"]

        # 3. Query GTFS database stops
        ctx = get_transit_context()
        if ctx.repository:
            results = ctx.repository.search_stops(q, limit=5)
            if results:
                metro_matches = [s for s in results if s.stop_id.startswith("metro_")]
                chosen = metro_matches[0] if metro_matches else results[0]
                return chosen.stop_id, chosen.stop_name

        return None

    @classmethod
    def scan_for_destination(cls, text: str) -> Optional[Tuple[str, str]]:
        """Scan freeform text for any mentioned Delhi landmark or metro stop."""
        t = text.lower()
        for alias in sorted(STATION_ALIASES.keys(), key=len, reverse=True):
            if alias in t:
                item = STATION_ALIASES[alias]
                return item["stop_id"], item["name"]

        # Try GTFS search on words
        words = [w for w in re.findall(r"[\w\u0900-\u097F]+", t) if len(w) >= 4 and w not in HINGLISH_MARKERS]
        ctx = get_transit_context()
        if ctx.repository:
            for w in words:
                res, _ = ctx.repository.search_stops(w, page=1, page_size=3)
                if res:
                    m = [s for s in res if s.stop_id.startswith("metro_")]
                    chosen = m[0] if m else res[0]
                    return chosen.stop_id, chosen.stop_name

        return None

    @classmethod
    def extract_entities_and_intent(cls, text: str) -> Dict[str, Any]:
        """Extract commuter intent, route origin/destination, and transit preferences."""
        t = text.lower()

        # 1. Reroute / Emergency / Lost intent
        is_reroute = (
            ("missed" in t and any(w in t for w in ["stop", "metro", "bus", "station", "train"]))
            or any(p in t for p in [
                "bus cancelled", "bus got cancelled", "cancelled", "break down", "broke down",
                "i'm lost", "im lost", "lost my way", "wrong stop", "wrong station", "reroute", "re-route",
                "chhut gaya", "chut gaya", "miss ho gaya", "bus cancel", "bhatak gaya",
                "galat station", "galat stop", "madad karo", "naya route", "emergency",
                "स्टॉप छूट गया", "बस रद्द", "भटक गया", "गलत स्टेशन", "नया रास्ता"
            ])
        )
        if is_reroute:
            return {"intent": "reroute", "action": "REROUTE"}

        # 2. Next stop query
        next_stop_patterns = [
            "what's my next stop", "what is my next stop", "next stop", "next station",
            "where do i alight", "where to get off", "when to get down",
            "agla stop kya hai", "agla station", "kaha utarna hai", "kab utarna",
            "अगला स्टॉप", "अगला स्टेशन", "कहाँ उतरना है", "कब उतरना है", "prochain arrêt", "siguiente parada"
        ]
        if any(p in t for p in next_stop_patterns):
            return {"intent": "next_step", "action": "STEP_GUIDANCE"}

        # 3. Repeat guidance
        repeat_patterns = [
            "repeat", "repeat that", "say again", "say that again", "what did you say",
            "dobara bolo", "fir se batao", "kya kaha", "repeat karo",
            "दोबारा बोलो", "फिर से बताओ", "क्या कहा"
        ]
        if any(p in t for p in repeat_patterns):
            return {"intent": "repeat", "action": "STEP_GUIDANCE"}

        # 4. Fare / Cost query for active journey
        fare_patterns = [
            "how much will it cost", "how much will this route cost", "how much is the fare", "route cost", "ticket price", "what is the cost",
            "kitna kharcha", "kitna kiraya", "kitne paise", "fare kya hai",
            "kiraya kitna", "सस्ता", "कितना किराया", "कितने पैसे"
        ]
        if any(p in t for p in fare_patterns) and not ("from" in t or "se" in t or "to" in t):
            return {"intent": "fare_query", "action": "NONE"}

        # 5. Duration query
        duration_patterns = [
            "how long will it take", "how much time", "travel time", "when will i arrive",
            "kitna time lagega", "kitni der lagegi", "kab tak pahuchenge",
            "कितना समय लगेगा", "कितनी देर लगेगी"
        ]
        if any(p in t for p in duration_patterns) and not ("from" in t or "se" in t or "to" in t):
            return {"intent": "duration_query", "action": "NONE"}

        # 6. Language switch command
        if any(p in t for p in ["in hindi", "hindi me batao", "speak hindi", "हिंदी में", "hindi please"]):
            return {"intent": "switch_language", "action": "NONE", "switch_to": "hi"}
        if any(p in t for p in ["in hinglish", "hinglish me batao", "hinglish please"]):
            return {"intent": "switch_language", "action": "NONE", "switch_to": "hinglish"}
        if any(p in t for p in ["in english", "english please", "speak english"]):
            return {"intent": "switch_language", "action": "NONE", "switch_to": "en"}

        # 7. Metro Timings & Schedules FAQ
        if any(p in t for p in ["first metro", "last metro", "metro timing", "metro timings", "operating hours", "start time", "close time", "kab chalti hai", "kitne baje start", "timing kya hai"]):
            return {"intent": "faq_timing", "action": "NONE"}

        # 8. Smart Card & Recharge FAQ
        if any(p in t for p in ["smart card", "metro card", "token", "discount", "recharge", "card discount", "delhi metro card"]):
            return {"intent": "faq_card", "action": "NONE"}

        # 9. Metro Rules & Luggage Limit FAQ
        if any(p in t for p in ["luggage", "baggage", "rules", "alcohol", "pets", "fine", "penalty", "limit"]):
            return {"intent": "faq_rules", "action": "NONE"}

        # 10. Tourist Monument & Sightseeing FAQ
        if any(p in t for p in ["tourist", "sightseeing", "places to visit", "monuments", "attractions", "delhi darshan"]):
            return {"intent": "faq_tourist", "action": "NONE"}

        # 11. Nearest Metro FAQ
        if any(p in t for p in ["nearest metro", "closest metro", "near me", "pass ka station", "closest station"]):
            return {"intent": "faq_nearest", "action": "NONE"}

        # 12. Route Planning Extraction
        criterion = "fastest"
        if any(w in t for w in ["sasta", "cheapest", "cheaper", "kam paise", "सस्ता", "low cost", "budget"]):
            criterion = "cheapest"
        elif any(w in t for w in ["balanced", "normal", "accha", "अच्छा", "best"]):
            criterion = "balanced"
        elif any(w in t for w in ["jaldi", "fast", "fastest", "tez", "quick", "जल्दी", "तेज़"]):
            criterion = "fastest"

        mode = "all"
        if any(w in t for w in ["metro only", "metro se", "by metro", "मेट्रो", "train"]):
            mode = "metro"
        elif any(w in t for w in ["bus only", "bus se", "by bus", "बस"]):
            mode = "bus"
        elif any(w in t for w in ["dono", "both", "bus aur metro", "multimodal"]):
            mode = "multimodal"
        elif any(w in t for w in ["auto", "ऑटो"]):
            mode = "auto"
        elif any(w in t for w in ["cab", "taxi", "कैब"]):
            mode = "cab"

        # Explicit Origin & Destination Parsing
        match_en = re.search(r"(?:from|start from)\s+([a-zA-Z0-9\s]+?)\s+(?:to|towards)\s+([a-zA-Z0-9\s]+?)(?:using|by|with|via|$)", t)
        match_hi = re.search(r"([a-zA-Z0-9\u0900-\u097F\s]+?)\s+(?:se|से)\s+([a-zA-Z0-9\u0900-\u097F\s]+?)(?:\s+jaana|\s+jana|\s+जाना|\s+तक|\s+ka|\s+ke|\s+route|\s+kaise|$)", t)
        match_to = re.search(r"(?:take me to|go to|reach|directions to|how to reach|way to|how do i reach)\s+([a-zA-Z0-9\s]+?)(?:from|using|by|$)", t)
        match_to_hi = re.search(r"(?:mujhe|मुझे\s+)?([a-zA-Z0-9\u0900-\u097F\s]+?)\s+(?:jaana|jana|जाना)\s+(?:hai|है)", t)

        origin_name = None
        dest_name = None

        if match_en:
            origin_name = match_en.group(1).strip()
            dest_name = match_en.group(2).strip()
        elif match_hi:
            origin_name = match_hi.group(1).strip()
            dest_name = match_hi.group(2).strip()
        elif match_to:
            dest_name = match_to.group(1).strip()
        elif match_to_hi:
            dest_name = match_to_hi.group(1).strip()

        # Clean words from parsed names
        clean_words = [
            "the", "sabse", "sasta", "route", "me", "jaana", "hai", "batao", "please", "using", "cheapest", "fastest",
            "मुझे", "से", "तक", "जाना", "है", "बताओ", "रास्ता", "रूट", "सबसे", "सस्ता", "तेज़", "जल्दी", "कृपया"
        ]
        if origin_name:
            origin_name = re.sub(r"^(?:mujhe|मुझे|the)\s+", "", origin_name, flags=re.IGNORECASE).strip()
            for w in clean_words:
                origin_name = re.sub(rf"(?:^|\s+){re.escape(w)}(?:\s+|$)", " ", origin_name, flags=re.IGNORECASE).strip()
        if dest_name:
            dest_name = re.sub(r"^(?:mujhe|मुझे|the)\s+", "", dest_name, flags=re.IGNORECASE).strip()
            for w in clean_words:
                dest_name = re.sub(rf"(?:^|\s+){re.escape(w)}(?:\s+|$)", " ", dest_name, flags=re.IGNORECASE).strip()

        # Fallback Landmark Scanner: If no destination captured yet, scan freeform speech for any known Delhi stop!
        if not dest_name:
            scanned = cls.scan_for_destination(t)
            if scanned:
                dest_name = scanned[1]

        if dest_name:
            return {
                "intent": "plan_route",
                "action": "NAVIGATE",
                "origin_raw": origin_name,
                "dest_raw": dest_name,
                "criterion": criterion,
                "mode": mode,
            }

        # General Greetings
        if any(w in t for w in ["hello", "hi", "namaste", "hey", "help", "safarsetu"]):
            return {"intent": "general_help", "action": "NONE"}

        return {"intent": "general_chat", "action": "NONE"}

    @classmethod
    def call_gemini_agent(cls, query: str, target_lang: str) -> Optional[Dict[str, Any]]:
        """Call Google Gemini 1.5 Flash if GEMINI_API_KEY is configured in backend/.env."""
        api_key = cls.get_configured_gemini_key()
        if not api_key:
            return None

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=(
                    "You are SafarSetu AI, the intelligent multimodal voice navigation assistant for Delhi/NCR. "
                    "Your job is to assist commuters and tourists with Delhi Metro, DTC Buses, Auto, and Cab travel. "
                    "Always keep station names, metro line colors (Yellow, Blue, Red, Violet, Pink, Magenta, etc.), "
                    "and landmarks accurate and factual. Do not invent fake delays. "
                    "If the user asks for travel or directions between places, respond with valid JSON: "
                    '{"intent": "plan_route", "origin": "<Origin Station/Landmark>", "destination": "<Destination Station/Landmark>", "criterion": "fastest"|"cheapest"|"balanced", "mode": "all"|"metro"|"bus", "spoken_text": "<Clear verbal response in target language>"}. '
                    "If the user asks a general transit question (timings, smart cards, rules, monument tourist tips), respond with valid JSON: "
                    '{"intent": "chat", "spoken_text": "<Concise 2-3 sentence verbal answer in target language>", "display_text": "<Detailed markdown answer with tips>"} '
                    f"Target language code: {target_lang} (en=English, hi=Hindi Devanagari, hinglish=Hinglish Latin script)."
                ),
            )
            resp = model.generate_content(query)
            text_resp = resp.text.strip()
            # Try parsing JSON
            json_match = re.search(r"\{.*\}", text_resp, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return {"intent": "chat", "spoken_text": text_resp, "display_text": text_resp}
        except Exception as e:
            print(f"[VoiceAssistant] Gemini API call note: {e}. Falling back to built-in transit engine.")
            return None

    @classmethod
    def generate_step_guidance(
        cls,
        journey: Dict[str, Any],
        leg_index: int = 0,
        sub_step: str = "board",
        target_lang: str = "en",
    ) -> VoiceStepGuidance:
        """Generate crystal-clear spoken & visual guidance for a specific journey leg."""
        legs = journey.get("legs", [])
        total_steps = len(legs)
        if not legs or leg_index >= total_steps:
            return VoiceStepGuidance(
                step_number=1,
                total_steps=1,
                step_type="destination",
                spoken_instruction="You have arrived at your destination.",
                display_instruction="You have arrived at your destination.",
                stop_name="Destination",
            )

        leg = legs[leg_index]
        mode = leg.get("mode", "walking")
        from_name = leg.get("from_stop_name", "Origin")
        to_name = leg.get("to_stop_name", "Destination")
        duration = leg.get("duration_minutes", 0)
        dist_m = leg.get("distance_meters", 0)
        headsign = leg.get("headsign") or "scheduled direction"
        route_name = leg.get("route_short_name") or leg.get("route_id") or ""
        fare = leg.get("fare_inr")

        is_metro = mode == "metro"
        is_bus = mode in ("bus", "transit")
        is_walking = mode in ("walking", "walk")

        line_desc = f"{route_name} Metro" if is_metro else f"Bus {route_name}" if is_bus else "Walking"

        if is_walking:
            step_type = "walk"
        elif leg_index == 0:
            step_type = "board_metro" if is_metro else "board_bus"
        elif leg_index > 0 and legs[leg_index - 1].get("mode") in ("metro", "bus", "transit"):
            step_type = "transfer"
        else:
            step_type = "board_metro" if is_metro else "board_bus"

        if target_lang == "hi":
            if is_walking:
                spoken = f"{to_name} की ओर लगभग {int(dist_m)} मीटर पैदल चलें। इसमें करीब {round(duration)} मिनट लगेंगे।"
                display = f"🚶 **पैदल चलें:** {to_name} की तरफ ({int(dist_m)}m, ~{round(duration)} मिनट)"
            elif step_type == "transfer":
                spoken = f"{from_name} पर उतरें और {headsign} की तरफ जाने वाली {line_desc} के लिए इंटरचेंज करें।"
                display = f"🔄 **इंटरचेंज:** {from_name} पर {line_desc} पकड़ें (दिशा: {headsign})"
            else:
                spoken = f"{from_name} पर {headsign} की तरफ जाने वाली {line_desc} में सवार हों।"
                display = f"🚆 **सवार हों:** {from_name} पर {line_desc} (दिशा: {headsign})"
        elif target_lang == "hinglish":
            if is_walking:
                spoken = f"{to_name} ki taraf lagbhag {int(dist_m)} meters pedal chalein, lagbhag {round(duration)} minutes lagenge."
                display = f"🚶 **Walk:** {to_name} ki taraf ({int(dist_m)}m, ~{round(duration)} mins)"
            elif step_type == "transfer":
                spoken = f"{from_name} par transfer karein aur {headsign} ki taraf jaane wali {line_desc} board karein."
                display = f"🔄 **Transfer:** {from_name} par {line_desc} board karein (towards {headsign})"
            else:
                spoken = f"{from_name} par {headsign} ki taraf jaane wali {line_desc} board karein."
                display = f"🚆 **Board:** {from_name} par {line_desc} (towards {headsign})"
        else:
            if is_walking:
                spoken = f"Walk approximately {int(dist_m)} meters towards {to_name}. It takes about {round(duration)} minutes."
                display = f"🚶 **Walk:** Towards {to_name} ({int(dist_m)}m, ~{round(duration)} mins)"
            elif step_type == "transfer":
                spoken = f"At {from_name}, interchange and board the {line_desc} heading towards {headsign}."
                display = f"🔄 **Transfer:** At {from_name} to {line_desc} towards {headsign}"
            else:
                spoken = f"Board the {line_desc} towards {headsign} at {from_name}."
                display = f"🚆 **Board:** At {from_name} on {line_desc} towards {headsign}"

        return VoiceStepGuidance(
            step_number=leg_index + 1,
            total_steps=total_steps,
            step_type=step_type,
            spoken_instruction=spoken,
            display_instruction=display,
            stop_name=from_name,
            line_name=route_name or ("Metro" if is_metro else "Transit"),
            headsign=headsign,
            duration_minutes=round(duration, 1),
            distance_meters=round(dist_m, 1) if dist_m else None,
            next_stop_name=to_name,
            fare_inr=fare,
        )

    @classmethod
    def handle_interaction(cls, req: VoiceQueryRequest) -> VoiceQueryResponse:
        """Process conversational voice request end-to-end with Gemini or Smart Built-in Engine."""
        detected_lang = cls.detect_language(req.query, req.language)
        target_lang = cls.resolve_target_language(detected_lang, req.target_language)
        ctx = get_transit_context()

        # Step A: Check if Google Gemini API key is configured
        gemini_result = cls.call_gemini_agent(req.query, target_lang)
        if gemini_result and gemini_result.get("intent") == "chat":
            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent="gemini_chat",
                spoken_text=gemini_result.get("spoken_text", ""),
                display_text=gemini_result.get("display_text") or gemini_result.get("spoken_text", ""),
                action="NONE",
                suggested_followups=["Show fastest route", "How much is the fare?", "What's my next stop?"],
            )

        # Step B: Advanced Local NLU Intent & Entity Parser
        parsed = cls.extract_entities_and_intent(req.query)
        # If Gemini returned plan_route entities, merge them
        if gemini_result and gemini_result.get("intent") == "plan_route":
            if gemini_result.get("destination"):
                parsed["dest_raw"] = gemini_result["destination"]
                parsed["intent"] = "plan_route"
            if gemini_result.get("origin"):
                parsed["origin_raw"] = gemini_result["origin"]
            if gemini_result.get("criterion"):
                parsed["criterion"] = gemini_result["criterion"]

        intent = parsed.get("intent", "general_chat")

        # 1. Handle Language Switch
        if intent == "switch_language":
            new_lang = parsed.get("switch_to", "en")
            target_lang = new_lang
            if new_lang == "hi":
                sp = "नमस्ते! अब से मैं आपसे हिंदी में बात करूँगा। आप कहाँ जाना चाहते हैं?"
                dp = "🌐 **भाषा बदलकर हिंदी की गई।** पूछिए: *'मुझे कश्मीरी गेट से राजीव चौक जाना है'*"
            elif new_lang == "hinglish":
                sp = "Sure! Ab se hum Hinglish me baat karenge. Aapko kaha jaana hai?"
                dp = "🌐 **Language switched to Hinglish.** Ask: *'Mujhe CP se India Gate jaana hai'*"
            else:
                sp = "Language switched to English. How can I assist with your transit journey today?"
                dp = "🌐 **Language set to English.** Ask: *'Take me from New Delhi to India Gate'*"

            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent=intent,
                spoken_text=sp,
                display_text=dp,
                action="SET_FILTER",
                suggested_followups=["Take me to India Gate", "Show cheapest route", "What's my next stop?"],
            )

        # 2. Handle Repeat Guidance
        if intent == "repeat":
            if req.current_journey:
                leg_idx = req.current_leg_index or 0
                step_guidance = cls.generate_step_guidance(req.current_journey, leg_idx, target_lang=target_lang)
                return VoiceQueryResponse(
                    transcript=req.query,
                    detected_language=detected_lang,
                    response_language=target_lang,
                    intent=intent,
                    spoken_text=step_guidance.spoken_instruction,
                    display_text=step_guidance.display_instruction,
                    action="STEP_GUIDANCE",
                    step_guidance=step_guidance,
                    suggested_followups=["Next stop", "How much will this cost?", "I missed my stop"],
                )
            else:
                msg_en = "You don't have an active journey in progress right now. Where would you like to travel?"
                msg_hi = "अभी आपका कोई सक्रिय रूट शुरू नहीं हुआ है। आप कहाँ जाना चाहते हैं?"
                msg_hing = "Abhi koi active journey nahi chal rahi hai. Aapko kahan travel karna hai?"
                sp = msg_hi if target_lang == "hi" else msg_hing if target_lang == "hinglish" else msg_en
                return VoiceQueryResponse(
                    transcript=req.query,
                    detected_language=detected_lang,
                    response_language=target_lang,
                    intent=intent,
                    spoken_text=sp,
                    display_text=sp,
                    action="NONE",
                    suggested_followups=["Take me to India Gate", "Plan route to Rajiv Chowk"],
                )

        # 3. Handle Next Stop Query
        if intent == "next_step":
            if req.current_journey:
                cur_idx = req.current_leg_index or 0
                legs = req.current_journey.get("legs", [])
                if cur_idx < len(legs):
                    leg = legs[cur_idx]
                    to_stop = leg.get("to_stop_name", "Destination")
                    route_name = leg.get("route_short_name", "Transit")
                    mins = round(leg.get("duration_minutes", 5))

                    if target_lang == "hi":
                        sp = f"आपका अगला स्टॉप {to_stop} है। इसमें लगभग {mins} मिनट लगेंगे।"
                        dp = f"📍 **अगला स्टॉप:** {to_stop} (~{mins} मिनट, {route_name})"
                    elif target_lang == "hinglish":
                        sp = f"Aapka agla stop {to_stop} hai, lagbhag {mins} minutes me aane wala hai."
                        dp = f"📍 **Next Stop:** {to_stop} (~{mins} mins, {route_name})"
                    else:
                        sp = f"Your next scheduled stop is {to_stop}. Remaining time is about {mins} minutes."
                        dp = f"📍 **Next Stop:** {to_stop} (~{mins} mins on {route_name})"

                    step_guidance = cls.generate_step_guidance(req.current_journey, cur_idx, target_lang=target_lang)
                    return VoiceQueryResponse(
                        transcript=req.query,
                        detected_language=detected_lang,
                        response_language=target_lang,
                        intent=intent,
                        spoken_text=sp,
                        display_text=dp,
                        action="STEP_GUIDANCE",
                        step_guidance=step_guidance,
                        suggested_followups=["Repeat", "How much fare remaining?", "I missed my stop"],
                    )
            sp = "No active navigation session. You can say 'Take me to Connaught Place' to plan a trip."
            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent=intent,
                spoken_text=sp,
                display_text=sp,
                action="NONE",
            )

        # 4. Handle Fare Query for current journey
        if intent == "fare_query":
            if req.current_journey and req.current_journey.get("fare_inr") is not None:
                fare = req.current_journey["fare_inr"]
                criterion = req.current_journey.get("rank_criterion", "standard")
                if target_lang == "hi":
                    sp = f"इस यात्रा का कुल किराया ₹{int(fare)} है।"
                    dp = f"💳 **कुल किराया:** ₹{int(fare)} ({criterion.capitalize()} विकल्प)"
                elif target_lang == "hinglish":
                    sp = f"Is journey ka total fare ₹{int(fare)} hai."
                    dp = f"💳 **Total Fare:** ₹{int(fare)} ({criterion.capitalize()} option)"
                else:
                    sp = f"The total verified fare for this journey is ₹{int(fare)}."
                    dp = f"💳 **Total Fare:** ₹{int(fare)} ({criterion.capitalize()} option)"

                return VoiceQueryResponse(
                    transcript=req.query,
                    detected_language=detected_lang,
                    response_language=target_lang,
                    intent=intent,
                    spoken_text=sp,
                    display_text=dp,
                    action="NONE",
                    suggested_followups=["Is there a cheaper option?", "What's my next stop?", "Can I avoid walking?"],
                )

        # 5. Handle Duration Query for current journey
        if intent == "duration_query":
            if req.current_journey and req.current_journey.get("total_duration_minutes"):
                dur = round(req.current_journey["total_duration_minutes"])
                raw_arr = str(req.current_journey.get("arrival_time", ""))
                arr = raw_arr[:5] if len(raw_arr) >= 5 else raw_arr
                if target_lang == "hi":
                    sp = f"इस रूट में कुल {dur} मिनट लगेंगे, और आप लगभग {arr} तक पहुँचेंगे।"
                    dp = f"⏱️ **कुल समय:** {dur} मिनट (पहुँचने का समय: {arr})"
                elif target_lang == "hinglish":
                    sp = f"Is route me lagbhag {dur} minutes lagenge aur expected arrival {arr} hai."
                    dp = f"⏱️ **Total Duration:** {dur} mins (Expected arrival: {arr})"
                else:
                    sp = f"This route takes approximately {dur} minutes, arriving around {arr}."
                    dp = f"⏱️ **Total Duration:** {dur} mins (Expected arrival: {arr})"

                return VoiceQueryResponse(
                    transcript=req.query,
                    detected_language=detected_lang,
                    response_language=target_lang,
                    intent=intent,
                    spoken_text=sp,
                    display_text=dp,
                    action="NONE",
                    suggested_followups=["What's my next stop?", "How much will this cost?"],
                )

        # 5b. Handle Women's Safety & HerRoute Feedback Queries
        if intent == "safety_query":
            # Determine route and segments
            route_id = "general_route"
            segment_ids = []
            if req.current_journey:
                legs = req.current_journey.get("legs", [])
                for leg in legs:
                    if isinstance(leg, dict):
                        if leg.get("from_stop_id"):
                            segment_ids.append(leg["from_stop_id"])
                        if leg.get("to_stop_id"):
                            segment_ids.append(leg["to_stop_id"])
                if segment_ids:
                    route_id = f"route_{segment_ids[0]}_{segment_ids[-1]}"

            # Query safety repository
            curr_hour = datetime.now().hour
            t_cat = "nighttime" if (curr_hour >= 20 or curr_hour < 6) else "daytime"
            overall, seg_dict = SafetyRepository.get_route_insights(route_id, segment_ids, time_filter=t_cat)

            if overall.has_sufficient_data:
                concerns_str = ", ".join([f"{c.label} ({c.count})" for c in overall.frequent_concerns[:3]])
                if not concerns_str:
                    concerns_str = "No major safety concerns reported"

                if target_lang == "hi":
                    sp = f"हररूट (HerRoute) समुदाय के अनुसार, इस रूट पर {overall.comfortable_count} सकारात्मक अनुभव और {overall.uncomfortable_count} असहज अनुभव दर्ज हैं। ध्यान दें कि ये यात्रियों के पूर्व अनुभव हैं और सुरक्षा की कोई गारंटी नहीं हैं।"
                    dp = f"🛡️ **HerRoute महिला सुरक्षा इनसाइट्स ({t_cat.capitalize()} फीडबैक):**\n• 🟢 **सकारात्मक अनुभव:** {overall.comfortable_count} रिपोर्ट\n• 🔴 **असहज रिपोर्ट:** {overall.uncomfortable_count}\n• ⚠️ **मुख्य बिंदु:** {concerns_str}\n\n*सूचना: ये महिला यात्रियों द्वारा साझा किए गए व्यक्तिगत अनुभव हैं। ये ऐतिहासिक जानकारी हैं और सुरक्षा की गारंटी नहीं देते।*"
                elif target_lang == "hinglish":
                    sp = f"HerRoute community feedback ke mutabik, is route par {overall.comfortable_count} comfortable aur {overall.uncomfortable_count} uncomfortable experiences report huye hain. Please note ki ye past traveler reports hain aur absolute safety guarantee nahi karte."
                    dp = f"🛡️ **HerRoute Community Safety Insights ({t_cat.capitalize()}):**\n• 🟢 **Comfortable Reports:** {overall.comfortable_count}\n• 🔴 **Uncomfortable Reports:** {overall.uncomfortable_count}\n• ⚠️ **Frequent Concerns:** {concerns_str}\n\n*Notice: Self-reported community feedback from women commuters. These reflect past experiences and do not guarantee safety.*"
                else:
                    sp = f"Based on community feedback from women travelers on HerRoute, this route has {overall.comfortable_count} positive experiences and {overall.uncomfortable_count} uncomfortable experiences recorded. Please note these are self-reported community experiences and do not guarantee safety."
                    dp = f"🛡️ **HerRoute Community Safety Insights ({t_cat.capitalize()}):**\n• 🟢 **Comfortable Reports:** {overall.comfortable_count}\n• 🔴 **Uncomfortable Reports:** {overall.uncomfortable_count}\n• ⚠️ **Reported Factors:** {concerns_str}\n\n*Notice: Self-reported community experiences from women travelers. These reflect past observations and cannot guarantee safety or replace personal caution.*"
            else:
                if target_lang == "hi":
                    sp = "इस रूट के लिए हररूट पर अभी पर्याप्त सामुदायिक सुरक्षा फीडबैक उपलब्ध नहीं है। हमेशा अपनी सतर्कता बनाए रखें।"
                    dp = "🛡️ **HerRoute सूचना:** इस रूट के लिए अभी पर्याप्त सामुदायिक फीडबैक उपलब्ध नहीं है।\n\n*सामुदायिक रिपोर्टें यात्रियों के पूर्व अनुभवों पर आधारित होती हैं और सुरक्षा की गारंटी नहीं देतीं।*"
                elif target_lang == "hinglish":
                    sp = "Is route ke liye abhi HerRoute par sufficient community safety feedback available nahi hai."
                    dp = "🛡️ **HerRoute Notice:** Not enough community feedback available for this route yet.\n\n*Community reports reflect past observations and do not guarantee safety.*"
                else:
                    sp = "Not enough community feedback is available for this route yet on HerRoute. Community reports reflect past traveler experiences and cannot guarantee safety."
                    dp = "🛡️ **HerRoute Notice:** Not enough community feedback available for this route yet.\n\n*Community reports reflect past traveler observations and do not guarantee safety.*"

            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent=intent,
                spoken_text=sp,
                display_text=dp,
                action="NONE",
                suggested_followups=["Share Journey Feedback", "Is there a cheaper option?", "What's my next stop?"],
            )

        # 6. Transit FAQ: Metro Timings
        if intent == "faq_timing":
            if target_lang == "hi":
                sp = "दिल्ली मेट्रो सुबह 5:30 बजे से रात 11:30 बजे तक चलती है। व्यस्त समय में ट्रेन हर 2 से 3 मिनट में उपलब्ध होती है।"
                dp = "🕒 **दिल्ली मेट्रो समय सारणी:**\n• परिचालन समय: सुबह 5:30 बजे से रात 11:30 बजे तक\n• पीक ऑवर्स में हर 2.5 - 3.5 मिनट में ट्रेन\n• एयरपोर्ट एक्सप्रेस सुबह 4:45 बजे से शुरू होती है"
            elif target_lang == "hinglish":
                sp = "Delhi Metro subah 5:30 AM se raat 11:30 PM tak chalti hai, aur peak hours me train frequency 2 se 3 minutes hoti hai."
                dp = "🕒 **Delhi Metro Timings:**\n• Operating Hours: 5:30 AM to 11:30 PM\n• Peak Headway: 2.5 - 3.5 mins frequency\n• Airport Express line starts at 4:45 AM"
            else:
                sp = "Delhi Metro runs daily from 5:30 AM to 11:30 PM across all major lines with peak frequency of 2.5 to 3.5 minutes."
                dp = "🕒 **Delhi Metro Schedule:**\n• Operating Hours: 5:30 AM – 11:30 PM\n• Peak Headway: ~2.5 - 3.5 minutes\n• Airport Express starts at 4:45 AM"

            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent=intent,
                spoken_text=sp,
                display_text=dp,
                action="NONE",
                suggested_followups=["Take me to Rajiv Chowk", "How much is smart card discount?", "What's my next stop?"],
            )

        # 7. Transit FAQ: Smart Card & Recharge
        if intent == "faq_card":
            if target_lang == "hi":
                sp = "दिल्ली मेट्रो स्मार्ट कार्ड पर हर यात्रा में 10% की छूट मिलती है, और नॉन-पीक घंटों में अतिरिक्त 10% की छूट मिलती है। न्यूनतम रिचार्ज ₹100 है।"
                dp = "💳 **स्मार्ट कार्ड छूट व नियम:**\n• नियमित यात्रा पर 10% की छूट\n• नॉन-पीक घंटों में अतिरिक्त 10% छूट (कुल 20% तक)\n• न्यूनतम नया कार्ड मूल्य: ₹150 (₹50 सिक्योरिटी)"
            elif target_lang == "hinglish":
                sp = "Delhi Metro smart card use karne par standard 10% discount milta hai, plus non-peak hours me extra 10% off milta hai. Minimum recharge ₹100 hai."
                dp = "💳 **Smart Card Benefits:**\n• Flat 10% discount on every trip\n• Additional 10% off during non-peak hours (total 20% savings)\n• Recharge via UPI, PayTM, or station TVM"
            else:
                sp = "Delhi Metro smart cards provide an automatic 10% discount on every ride, plus an extra 10% discount during off-peak hours."
                dp = "💳 **DMRC Smart Card Benefits:**\n• 10% discount on every ride\n• Additional 10% non-peak bonus (before 8 AM, 12-5 PM, after 9 PM)\n• Available at all station customer care counters"

            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent=intent,
                spoken_text=sp,
                display_text=dp,
                action="NONE",
                suggested_followups=["Metro timings kya hain?", "Take me to India Gate", "Show cheapest route"],
            )

        # 8. Transit FAQ: Metro Rules & Luggage Limit
        if intent == "faq_rules":
            if target_lang == "hi":
                sp = "दिल्ली मेट्रो में प्रति यात्री 25 किलोग्राम तक का सामान ले जाने की अनुमति है। मेट्रो परिसर में धूम्रपान, शराब और भोजन करना सख्त मना है।"
                dp = "🛡️ **दिल्ली मेट्रो दिशानिर्देश:**\n• सामान सीमा: 25 किलोग्राम तक\n• शराब या ज्वलनशील पदार्थ वर्जित\n• महिला कोच प्रत्येक ट्रेन का पहला डिब्बा है"
            else:
                sp = "Passengers can carry luggage up to 25 kg on Delhi Metro. Alcohol, open food, and smoking are strictly prohibited."
                dp = "🛡️ **DMRC Commuter Guidelines:**\n• Luggage limit: Up to 25 kg (80cm x 50cm x 30cm)\n• First coach in the direction of travel is reserved for women\n• Prohibited: Alcohol, open eatables, inflammable items"

            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent=intent,
                spoken_text=sp,
                display_text=dp,
                action="NONE",
            )

        # 9. Transit FAQ: Tourist Sightseeing & Delhi Darshan
        if intent == "faq_tourist":
            sp_en = "Delhi has iconic transit-connected landmarks: India Gate at Central Secretariat, Red Fort at Lal Quila station, and Qutub Minar at Qutab Minar station. Where would you like to go?"
            sp_hi = "दिल्ली में प्रमुख दर्शनीय स्थल मेट्रो से सीधे जुड़े हैं: इंडिया गेट के लिए केंद्रीय सचिवालय, लाल किले के लिए लाल किला स्टेशन, और कुतुब मीनार। आप कहाँ जाना चाहते हैं?"
            dp = (
                "🏛️ **Delhi Top Transit Attractions:**\n"
                "• **India Gate:** Central Secretariat (Yellow/Violet Line, Gate 3)\n"
                "• **Red Fort (Lal Qila):** Lal Quila Station (Violet Line, Gate 4)\n"
                "• **Qutub Minar:** Qutab Minar Station (Yellow Line)\n"
                "• **Akshardham Temple:** Akshardham Station (Blue Line)\n"
                "• **Lotus Temple:** Kalkaji Mandir Station (Violet/Magenta Line)"
            )
            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent=intent,
                spoken_text=sp_hi if target_lang == "hi" else sp_en,
                display_text=dp,
                action="NONE",
                suggested_followups=["Take me to India Gate", "Take me to Akshardham", "Take me to Red Fort"],
            )

        # 10. Transit FAQ: Nearest Station
        if intent == "faq_nearest":
            if req.user_lat and req.user_lon and ctx.repository:
                nearby = ctx.repository.find_nearby_stops(req.user_lat, req.user_lon, radius_meters=3500.0, limit=3)
                if nearby:
                    st = nearby[0][0]
                    dist_km = round(nearby[0][1] / 1000.0, 1) if isinstance(nearby[0][1], (int, float)) else 0.5
                    sp = f"The closest verified transit stop to your location is {st.stop_name}, approximately {dist_km} km away."
                    dp = f"📍 **Nearest Transit Stop:** {st.stop_name} (~{dist_km} km from your GPS)"
                    return VoiceQueryResponse(
                        transcript=req.query,
                        detected_language=detected_lang,
                        response_language=target_lang,
                        intent=intent,
                        spoken_text=sp,
                        display_text=dp,
                        action="NONE",
                        suggested_followups=[f"Take me from {st.stop_name} to India Gate", "Show routes"],
                    )
            sp = "You can share your GPS location or click any station on the live map to set your origin point."
            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent=intent,
                spoken_text=sp,
                display_text=sp,
                action="NONE",
            )

        # 11. Handle Emergency Reroute
        if intent == "reroute":
            origin_id = None
            origin_name = None
            dest_id = None
            dest_name = None

            if req.current_journey:
                legs = req.current_journey.get("legs", [])
                cur_leg_idx = req.current_leg_index or 0
                if cur_leg_idx < len(legs):
                    origin_id = legs[cur_leg_idx].get("from_stop_id")
                    origin_name = legs[cur_leg_idx].get("from_stop_name")
                if legs:
                    dest_id = legs[-1].get("to_stop_id")
                    dest_name = legs[-1].get("to_stop_name")

            if req.user_lat and req.user_lon and ctx.repository:
                nearby = ctx.repository.find_nearby_stops(req.user_lat, req.user_lon, radius_meters=3000.0, limit=1)
                if nearby:
                    closest_stop = nearby[0][0]
                    origin_id = closest_stop.stop_id
                    origin_name = closest_stop.stop_name

            if not origin_id:
                origin_id = "metro_122"
                origin_name = "Rajiv Chowk"
            if not dest_id:
                dest_id = "metro_80"
                dest_name = "Central Secretariat"

            now_dt = datetime.now()
            dep_seconds = now_dt.hour * 3600 + now_dt.minute * 60 + now_dt.second
            dep_str = now_dt.strftime("%H:%M:%S")
            today_str = now_dt.strftime("%Y-%m-%d")

            planned_journeys = []
            if ctx.router:
                raw_journeys, _ = ctx.router.plan_journey(
                    origin_stop_id=origin_id,
                    destination_stop_id=dest_id,
                    departure_date=now_dt.date(),
                    departure_seconds=dep_seconds,
                    max_transfers=3,
                    criterion=RouteRankCriterion.FASTEST,
                    mode_filter="all",
                )
                ranked = RouteRanker.rank(raw_journeys, criterion=RouteRankCriterion.FASTEST)
                for rj in ranked[:3]:
                    legs_data = []
                    for leg in rj.legs:
                        fs = ctx.dataset.stops.get(leg.from_stop_id) if ctx.dataset else None
                        ts = ctx.dataset.stops.get(leg.to_stop_id) if ctx.dataset else None
                        legs_data.append({
                            "mode": leg.mode.value,
                            "from_stop_id": leg.from_stop_id,
                            "to_stop_id": leg.to_stop_id,
                            "from_stop_name": fs.stop_name if fs else leg.from_stop_id,
                            "to_stop_name": ts.stop_name if ts else leg.to_stop_id,
                            "departure_time": leg.departure_time_str,
                            "arrival_time": leg.arrival_time_str,
                            "duration_minutes": round(leg.duration_seconds / 60.0, 1),
                            "route_id": leg.route_id,
                            "route_short_name": leg.route_short_name,
                            "route_long_name": leg.route_long_name,
                            "headsign": leg.headsign,
                            "fare_inr": leg.fare_inr,
                            "distance_meters": leg.distance_meters,
                        })
                    planned_journeys.append({
                        "departure_time": rj.departure_time_str,
                        "arrival_time": rj.arrival_time_str,
                        "total_duration_minutes": round(rj.total_duration_seconds / 60.0, 1),
                        "total_walk_meters": round(rj.total_walk_meters, 1),
                        "num_transfers": rj.num_transfers,
                        "initial_wait_minutes": round(rj.initial_wait_seconds / 60.0, 1),
                        "fare_inr": rj.total_fare_inr,
                        "fare_complete": rj.fare_complete,
                        "rank_criterion": "fastest",
                        "legs": legs_data,
                        "warnings": rj.warnings,
                        "data_sources": rj.provenance_sources,
                    })

            if target_lang == "hi":
                sp = f"घबराइए मत! हमने {origin_name} से {dest_name} के लिए तुरंत वैकल्पिक रूट ढूंढ लिया है।"
                dp = f"🚨 **आपातकालीन री-रूटिंग सक्रिय:** {origin_name} से {dest_name} के लिए नया रूट तैयार है।"
            elif target_lang == "hinglish":
                sp = f"Fret not! Maine {origin_name} se {dest_name} ke liye turant fail-safe alternate route recalculate kar diya hai."
                dp = f"🚨 **Emergency Reroute:** Recalculated from **{origin_name}** to **{dest_name}**."
            else:
                sp = f"Don't worry! I have recalculated an updated alternative route from {origin_name} to {dest_name}."
                dp = f"🚨 **Emergency Reroute Activated:** Fresh route calculated from **{origin_name}** to **{dest_name}**."

            plan_dict = {
                "origin_stop_id": origin_id,
                "destination_stop_id": dest_id,
                "departure_date": today_str,
                "requested_time": dep_str,
                "criterion": "fastest",
                "journeys": planned_journeys,
                "data_freshness_warnings": ["Voice-activated emergency reroute applied."],
            } if planned_journeys else None

            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent="reroute",
                spoken_text=sp,
                display_text=dp,
                action="REROUTE",
                entities={"origin": origin_name, "destination": dest_name, "origin_id": origin_id, "dest_id": dest_id},
                planned_route=plan_dict,
                suggested_followups=["What's my next stop?", "How much will this cost?", "Repeat instructions"],
            )

        # 12. Handle Route Planning
        if intent == "plan_route":
            dest_raw = parsed.get("dest_raw", "")
            orig_raw = parsed.get("origin_raw")
            criterion = parsed.get("criterion", "fastest")
            mode = parsed.get("mode", "all")

            # Resolve Destination
            dest_res = cls.find_stop_by_name(dest_raw)
            if not dest_res:
                if target_lang == "hi":
                    sp = f"मुझे '{dest_raw}' नाम का दिल्ली ट्रांजिट स्टॉप नहीं मिला। कृपया स्टेशन का सही नाम बताएं।"
                    dp = f"⚠️ स्टेशन नहीं मिला: '{dest_raw}'. कृपया राजीव चौक, कश्मीरी गेट या कुतुब मीनार जैसा स्टेशन चुनें।"
                elif target_lang == "hinglish":
                    sp = f"Mujhe '{dest_raw}' ka verified stop nahi mila. Kripya station name dobara bolein."
                    dp = f"⚠️ Stop not found: '{dest_raw}'. Please mention a verified hub like Rajiv Chowk or Hauz Khas."
                else:
                    sp = f"I couldn't locate a verified Delhi transit stop for '{dest_raw}'. Please confirm your destination station."
                    dp = f"⚠️ Could not resolve destination '{dest_raw}'. Please choose a known Delhi stop."

                return VoiceQueryResponse(
                    transcript=req.query,
                    detected_language=detected_lang,
                    response_language=target_lang,
                    intent=intent,
                    spoken_text=sp,
                    display_text=dp,
                    action="NONE",
                    suggested_followups=["Take me to Rajiv Chowk", "Take me to India Gate", "Take me to Qutub Minar"],
                )

            dest_id, dest_name = dest_res

            # Resolve Origin
            orig_id = None
            orig_name = None
            if orig_raw:
                orig_res = cls.find_stop_by_name(orig_raw)
                if orig_res:
                    orig_id, orig_name = orig_res

            # If no origin specified in query, check GPS or fallback to central hub
            if not orig_id:
                if req.user_lat and req.user_lon and ctx.repository:
                    nearby = ctx.repository.find_nearby_stops(req.user_lat, req.user_lon, radius_meters=3500.0, limit=1)
                    if nearby:
                        closest = nearby[0][0]
                        orig_id = closest.stop_id
                        orig_name = closest.stop_name

            if not orig_id:
                orig_id = "metro_122" if dest_id != "metro_122" else "metro_99"
                orig_name = "Rajiv Chowk" if orig_id == "metro_122" else "Kashmere Gate"

            now_dt = datetime.now()
            dep_seconds = now_dt.hour * 3600 + now_dt.minute * 60 + now_dt.second
            dep_str = now_dt.strftime("%H:%M:%S")
            today_str = now_dt.strftime("%Y-%m-%d")
            crit_enum = RouteRankCriterion(criterion)

            planned_journeys = []
            no_route_reason = None
            if ctx.router:
                raw_journeys, no_route_reason = ctx.router.plan_journey(
                    origin_stop_id=orig_id,
                    destination_stop_id=dest_id,
                    departure_date=now_dt.date(),
                    departure_seconds=dep_seconds,
                    max_transfers=3,
                    criterion=crit_enum,
                    mode_filter=mode,
                )
                ranked = RouteRanker.rank(raw_journeys, criterion=crit_enum)
                for rj in ranked[:5]:
                    legs_data = []
                    for leg in rj.legs:
                        fs = ctx.dataset.stops.get(leg.from_stop_id) if ctx.dataset else None
                        ts = ctx.dataset.stops.get(leg.to_stop_id) if ctx.dataset else None
                        legs_data.append({
                            "mode": leg.mode.value,
                            "from_stop_id": leg.from_stop_id,
                            "to_stop_id": leg.to_stop_id,
                            "from_stop_name": fs.stop_name if fs else leg.from_stop_id,
                            "to_stop_name": ts.stop_name if ts else leg.to_stop_id,
                            "departure_time": leg.departure_time_str,
                            "arrival_time": leg.arrival_time_str,
                            "duration_minutes": round(leg.duration_seconds / 60.0, 1),
                            "route_id": leg.route_id,
                            "route_short_name": leg.route_short_name,
                            "route_long_name": leg.route_long_name,
                            "headsign": leg.headsign,
                            "fare_inr": leg.fare_inr,
                            "distance_meters": leg.distance_meters,
                        })
                    planned_journeys.append({
                        "departure_time": rj.departure_time_str,
                        "arrival_time": rj.arrival_time_str,
                        "total_duration_minutes": round(rj.total_duration_seconds / 60.0, 1),
                        "total_walk_meters": round(rj.total_walk_meters, 1),
                        "num_transfers": rj.num_transfers,
                        "initial_wait_minutes": round(rj.initial_wait_seconds / 60.0, 1),
                        "fare_inr": rj.total_fare_inr,
                        "fare_complete": rj.fare_complete,
                        "rank_criterion": criterion,
                        "legs": legs_data,
                        "warnings": rj.warnings,
                        "data_sources": rj.provenance_sources,
                    })

            plan_dict = {
                "origin_stop_id": orig_id,
                "destination_stop_id": dest_id,
                "departure_date": today_str,
                "requested_time": dep_str,
                "criterion": criterion,
                "journeys": planned_journeys,
                "data_freshness_warnings": [],
                "no_route_reason": no_route_reason,
            }

            if planned_journeys:
                best = planned_journeys[0]
                dur = round(best["total_duration_minutes"])
                fare = best.get("fare_inr")
                fare_txt = f"₹{int(fare)}" if fare is not None else "normal fare"

                if target_lang == "hi":
                    sp = f"मैंने {orig_name} से {dest_name} के लिए {criterion} रूट ढूंढ लिया है। इसमें लगभग {dur} मिनट लगेंगे और किराया {fare_txt} है।"
                    dp = f"✅ **रूट तैयार:** {orig_name} ➔ {dest_name} ({dur} मिनट, {fare_txt})"
                elif target_lang == "hinglish":
                    sp = f"Maine {orig_name} se {dest_name} ka {criterion} route dhundh liya hai. Isme lagbhag {dur} minutes lagenge aur fare {fare_txt} hoga."
                    dp = f"✅ **Route Ready:** {orig_name} ➔ {dest_name} ({dur} mins, {fare_txt})"
                else:
                    sp = f"I've found the {criterion} route from {orig_name} to {dest_name}. It takes about {dur} minutes with a fare of {fare_txt}."
                    dp = f"✅ **Route Planned:** {orig_name} ➔ {dest_name} (~{dur} mins, {fare_txt})"
            else:
                if target_lang == "hi":
                    sp = f"{orig_name} से {dest_name} के लिए कोई सीधा ट्रांजिट रूट नहीं मिला।"
                    dp = f"⚠️ {orig_name} से {dest_name} के बीच रूट उपलब्ध नहीं है। कृपया नजदीकी मेट्रो स्टेशन चुनें।"
                else:
                    sp = f"No direct transit route found between {orig_name} and {dest_name}. Try selecting nearby interchange stations."
                    dp = f"⚠️ No route found between {orig_name} and {dest_name}."

            return VoiceQueryResponse(
                transcript=req.query,
                detected_language=detected_lang,
                response_language=target_lang,
                intent="plan_route",
                spoken_text=sp,
                display_text=dp,
                action="NAVIGATE",
                entities={
                    "origin": orig_name,
                    "destination": dest_name,
                    "origin_id": orig_id,
                    "dest_id": dest_id,
                    "criterion": criterion,
                    "mode": mode,
                },
                planned_route=plan_dict,
                suggested_followups=["What's my next stop?", "Is there a cheaper route?", "Explain in Hindi", "Repeat"],
            )

        # 13. Dynamic Contextual Conversational Responses
        q_lower = req.query.lower()
        if target_lang == "hi":
            if any(w in q_lower for w in ["नमस्ते", "हेलो", "हाय"]):
                sp = "नमस्ते! मैं सफ़रसेतु वॉयस असिस्टेंट हूँ। आप दिल्ली में कहाँ जाना चाहते हैं?"
            else:
                sp = f"मैं आपकी दिल्ली ट्रांजिट यात्रा में मदद कर सकता हूँ। आप किसी भी स्टेशन, जैसे राजीव चौक, कुतुब मीनार या इंडिया गेट का रूट पूछ सकते हैं।"
            dp = "🎙️ **सफ़रसेतु वॉयस असिस्टेंट:** पूछें: *'कुतुब मीनार कैसे पहुँचें?'* या *'मेट्रो की टाइमिंग क्या है?'*"
        elif target_lang == "hinglish":
            if any(w in q_lower for w in ["hello", "hi", "hey"]):
                sp = "Hello! Main aapka SafarSetu transit assistant hoon. Aapko Delhi me kahan jaana hai?"
            else:
                sp = "Main aapki journey plan karne me help kar sakta hoon. Aap kisi bhi stop jaise Qutub Minar, Akshardham ya India Gate ka route pooch sakte hain."
            dp = "🎙️ **SafarSetu AI Voice:** Try: *'India Gate kaise jaye?'* or *'Metro timing kya hai?'*"
        else:
            if any(w in q_lower for w in ["hello", "hi", "hey"]):
                sp = "Hello! I am your SafarSetu transit assistant. Where would you like to travel in Delhi today?"
            else:
                sp = "I can guide you anywhere across Delhi Metro and DTC bus networks. Try asking for directions to India Gate, Qutub Minar, or Connaught Place."
            dp = "🎙️ **SafarSetu Assistant:** Ask for directions, metro timings, smart card discounts, or next stop."

        return VoiceQueryResponse(
            transcript=req.query,
            detected_language=detected_lang,
            response_language=target_lang,
            intent="general_help",
            spoken_text=sp,
            display_text=dp,
            action="NONE",
            suggested_followups=[
                "Take me from New Delhi to India Gate",
                "What time does Delhi Metro start?",
                "How much is smart card discount?",
                "Mujhe Qutub Minar jaana hai",
            ],
        )
