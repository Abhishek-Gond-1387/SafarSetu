with open('d:/SafarSetu/backend/app/services/voice_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import
if 'from app.repositories.safety_repository import SafetyRepository' not in content:
    content = content.replace(
        "from app.services.route_ranker import RouteRanker",
        "from app.repositories.safety_repository import SafetyRepository\nfrom app.services.route_ranker import RouteRanker"
    )

# 2. Add intent detection in extract_intent
safety_intent_code = """        # 5b. Women's Safety & HerRoute Feedback Query
        if any(w in t for w in ["safe", "safety", "women", "ladies", "herroute", "surakshit", "suraksha", "mahila", "सुरक्षित", "सुरक्षा", "महिला", "uncomfortable", "night safe", "feedback", "rating"]):
            return {"intent": "safety_query", "action": "NONE"}

        # 6. Reroute / Emergency Triggers"""

content = content.replace("        # 6. Reroute / Emergency Triggers", safety_intent_code)

# 3. Add handler for safety_query
safety_handler_code = """        # 5b. Handle Women's Safety & HerRoute Feedback Queries
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
                    dp = f"🛡️ **HerRoute महिला सुरक्षा इनसाइट्स ({t_cat.capitalize()} फीडबैक):**\\n• 🟢 **सकारात्मक अनुभव:** {overall.comfortable_count} रिपोर्ट\\n• 🔴 **असहज रिपोर्ट:** {overall.uncomfortable_count}\\n• ⚠️ **मुख्य बिंदु:** {concerns_str}\\n\\n*सूचना: ये महिला यात्रियों द्वारा साझा किए गए व्यक्तिगत अनुभव हैं। ये ऐतिहासिक जानकारी हैं और सुरक्षा की गारंटी नहीं देते।*"
                elif target_lang == "hinglish":
                    sp = f"HerRoute community feedback ke mutabik, is route par {overall.comfortable_count} comfortable aur {overall.uncomfortable_count} uncomfortable experiences report huye hain. Please note ki ye past traveler reports hain aur absolute safety guarantee nahi karte."
                    dp = f"🛡️ **HerRoute Community Safety Insights ({t_cat.capitalize()}):**\\n• 🟢 **Comfortable Reports:** {overall.comfortable_count}\\n• 🔴 **Uncomfortable Reports:** {overall.uncomfortable_count}\\n• ⚠️ **Frequent Concerns:** {concerns_str}\\n\\n*Notice: Self-reported community feedback from women commuters. These reflect past experiences and do not guarantee safety.*"
                else:
                    sp = f"Based on community feedback from women travelers on HerRoute, this route has {overall.comfortable_count} positive experiences and {overall.uncomfortable_count} uncomfortable experiences recorded. Please note these are self-reported community experiences and do not guarantee safety."
                    dp = f"🛡️ **HerRoute Community Safety Insights ({t_cat.capitalize()}):**\\n• 🟢 **Comfortable Reports:** {overall.comfortable_count}\\n• 🔴 **Uncomfortable Reports:** {overall.uncomfortable_count}\\n• ⚠️ **Reported Factors:** {concerns_str}\\n\\n*Notice: Self-reported community experiences from women travelers. These reflect past observations and cannot guarantee safety or replace personal caution.*"
            else:
                if target_lang == "hi":
                    sp = "इस रूट के लिए हररूट पर अभी पर्याप्त सामुदायिक सुरक्षा फीडबैक उपलब्ध नहीं है। हमेशा अपनी सतर्कता बनाए रखें।"
                    dp = "🛡️ **HerRoute सूचना:** इस रूट के लिए अभी पर्याप्त सामुदायिक फीडबैक उपलब्ध नहीं है।\\n\\n*सामुदायिक रिपोर्टें यात्रियों के पूर्व अनुभवों पर आधारित होती हैं और सुरक्षा की गारंटी नहीं देतीं।*"
                elif target_lang == "hinglish":
                    sp = "Is route ke liye abhi HerRoute par sufficient community safety feedback available nahi hai."
                    dp = "🛡️ **HerRoute Notice:** Not enough community feedback available for this route yet.\\n\\n*Community reports reflect past observations and do not guarantee safety.*"
                else:
                    sp = "Not enough community feedback is available for this route yet on HerRoute. Community reports reflect past traveler experiences and cannot guarantee safety."
                    dp = "🛡️ **HerRoute Notice:** Not enough community feedback available for this route yet.\\n\\n*Community reports reflect past traveler observations and do not guarantee safety.*"

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

        # 6. Transit FAQ: Metro Timings"""

content = content.replace("        # 6. Transit FAQ: Metro Timings", safety_handler_code)

with open('d:/SafarSetu/backend/app/services/voice_assistant.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully updated voice_assistant.py with HerRoute integration.")
