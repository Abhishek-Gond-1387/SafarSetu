"""Tests for Multilingual Voice Assistant Service and API."""
from fastapi.testclient import TestClient
from app.main import app
from app.services.data_source_service import TransitContext
from app.services.voice_assistant import MultilingualVoiceAssistant
from app.schemas.voice import VoiceQueryRequest


def test_language_detection():
    # English
    assert MultilingualVoiceAssistant.detect_language("Take me from New Delhi to India Gate") == "en"
    # Hindi (Devanagari)
    assert MultilingualVoiceAssistant.detect_language("मुझे नई दिल्ली से इंडिया गेट जाना है") == "hi"
    # Hinglish
    assert MultilingualVoiceAssistant.detect_language("Mujhe Qutub Minar jaana hai, sabse sasta route batao") == "hinglish"
    # French
    assert MultilingualVoiceAssistant.detect_language("Bonjour comment aller au metro") == "fr"


def test_entity_intent_extraction():
    parsed = MultilingualVoiceAssistant.extract_entities_and_intent(
        "Take me from New Delhi Railway Station to India Gate using the cheapest route"
    )
    assert parsed["intent"] == "plan_route"
    assert parsed["criterion"] == "cheapest"

    parsed_hi = MultilingualVoiceAssistant.extract_entities_and_intent(
        "Mujhe Qutub Minar jaana hai, sabse sasta route batao"
    )
    assert parsed_hi["intent"] == "plan_route"
    assert parsed_hi["criterion"] == "cheapest"

    # Reroute intent
    parsed_re = MultilingualVoiceAssistant.extract_entities_and_intent("I missed my metro stop. Help me reach my destination.")
    assert parsed_re["intent"] == "reroute"

    # Next stop intent
    parsed_next = MultilingualVoiceAssistant.extract_entities_and_intent("What's my next stop?")
    assert parsed_next["intent"] == "next_step"

    # Fare intent
    parsed_fare = MultilingualVoiceAssistant.extract_entities_and_intent("How much will this route cost?")
    assert parsed_fare["intent"] == "fare_query"


def test_step_guidance_generation():
    fake_journey = {
        "legs": [
            {
                "mode": "metro",
                "from_stop_name": "Rajiv Chowk",
                "to_stop_name": "Central Secretariat",
                "duration_minutes": 6.0,
                "distance_meters": 2400.0,
                "route_short_name": "Yellow Line",
                "headsign": "HUDA City Centre",
                "fare_inr": 20.0,
            }
        ]
    }
    # English guidance
    g_en = MultilingualVoiceAssistant.generate_step_guidance(fake_journey, leg_index=0, target_lang="en")
    assert "Rajiv Chowk" in g_en.spoken_instruction
    assert "Yellow Line" in g_en.spoken_instruction

    # Hindi guidance
    g_hi = MultilingualVoiceAssistant.generate_step_guidance(fake_journey, leg_index=0, target_lang="hi")
    assert "Rajiv Chowk" in g_hi.spoken_instruction
    assert "Yellow Line" in g_hi.spoken_instruction


def test_voice_interact_api_endpoints():
    TransitContext.initialize()
    client = TestClient(app)
    # 1. Languages endpoint
    res = client.get("/api/v1/voice/languages")
    assert res.status_code == 200
    langs = res.json()
    assert len(langs["supported_languages"]) >= 3
    codes = [l["code"] for l in langs["supported_languages"]]
    assert "en" in codes and "hi" in codes and "hinglish" in codes

    # 2. English route planning voice query
    res = client.post(
        "/api/v1/voice/interact",
        json={"query": "Take me from New Delhi Railway Station to India Gate using the cheapest route"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "plan_route"
    assert data["action"] == "NAVIGATE"
    assert "spoken_text" in data
    assert len(data["spoken_text"]) > 10

    # 3. Hindi route planning voice query
    res_hi = client.post(
        "/api/v1/voice/interact",
        json={"query": "मुझे कश्मीरी गेट से राजीव चौक जाना है"}
    )
    assert res_hi.status_code == 200
    data_hi = res_hi.json()
    assert data_hi["intent"] == "plan_route"
    assert data_hi["detected_language"] == "hi"

    # 4. Emergency Reroute voice query
    res_re = client.post(
        "/api/v1/voice/interact",
        json={"query": "I missed my metro stop. Help me reach my destination."}
    )
    assert res_re.status_code == 200
    data_re = res_re.json()
    assert data_re["intent"] == "reroute"
    assert data_re["action"] == "REROUTE"

    # 5. Language Switch
    res_sw = client.post(
        "/api/v1/voice/interact",
        json={"query": "Explain in Hindi"}
    )
    assert res_sw.status_code == 200
    data_sw = res_sw.json()
    assert data_sw["intent"] == "switch_language"
    assert data_sw["response_language"] == "hi"
