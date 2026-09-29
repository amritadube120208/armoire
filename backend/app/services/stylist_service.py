"""
AI Fashion Stylist Service.
Connects Armoire's stylist to Vercel AI Gateway when configured and keeps
the offline fashion fallback available when the external API is unavailable.
Strictly excludes study/academic content and focuses exclusively on
tailored outfit formulas, color harmony, and weather/occasion styling.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import httpx
from app.core.logging import get_logger

logger = get_logger(__name__)

PRIMARY_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODELS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
AI_GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/chat/completions"

FASHION_SYSTEM_PROMPT = """You are Armoire Atelier AI — a sophisticated, warm, and highly knowledgeable Personal Fashion Stylist and Wardrobe Consultant.

Your role:
1. Suggest inspiring, elegant, and practical outfit ideas tailored to the user's question, occasion, climate, and personal style.
2. Provide actionable styling formulas: specify tops, bottoms, layering pieces, footwear, and thoughtful accessories.
3. Recommend color combinations based on color theory (e.g., complementary tones, monochrome layering, grounding neutrals).
4. Embody the Armoire philosophy: "A little more you. Less deciding, more living." Be encouraging, tasteful, and effortlessly chic.

STRICT BOUNDARY — NO STUDY / ACADEMIC CONTENT:
If the user asks about exams, homework, mathematics, school tests, notes, physics, coding, or any academic/study subjects, you MUST politely refuse and redirect to fashion:
"I am your Armoire personal fashion stylist. I focus exclusively on outfits, wardrobe curation, styling ideas, and color pairing. How can I help you elevate your personal style today?"

Keep responses engaging, structured (use concise bullet points or bold labels), and easy to scan. Avoid overwhelming walls of text."""


class StylistService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (
            api_key
            or os.environ.get("AI_GATEWAY_API_KEY")
        )
        self.model = os.environ.get("ARMOIRE_STYLIST_MODEL", PRIMARY_MODEL)
    async def get_stylist_advice(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        occasion: Optional[str] = None,
        weather: Optional[Dict[str, Any]] = None,
        wardrobe_pieces: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generates personalized fashion stylist advice based on user prompt,
        optional conversation history, weather conditions, and wardrobe pieces.
        """
        clean_prompt = (prompt or "").strip()
        if not clean_prompt:
            return {
                "reply": "I'm here to help with your style. What occasion, outfit idea, or piece would you like advice on?",
                "suggestions": [
                    "What should I wear for a casual Sunday brunch?",
                    "How do I style a beige trench coat?",
                    "What colors go well with navy blue trousers?"
                ]
            }

        # Build context augmentations
        context_notes = []
        if occasion:
            context_notes.append(f"Occasion context: {occasion.capitalize()}")
        if weather:
            temp = weather.get("temperature")
            cond = weather.get("condition")
            if temp is not None:
                context_notes.append(f"Local Weather: {temp}°C, {cond or 'current conditions'}")
        if wardrobe_pieces:
            sample = ", ".join(wardrobe_pieces[:8])
            context_notes.append(f"User's available wardrobe pieces: {sample}")

        system_instruction = FASHION_SYSTEM_PROMPT
        if context_notes:
            system_instruction += "\n\nCURRENT CONTEXT:\n- " + "\n- ".join(context_notes)

        # Assemble messages list
        messages = [{"role": "system", "content": system_instruction}]

        # Add recent conversation history if provided (limit last 6 messages)
        if history:
            for msg in history[-6:]:
                role = msg.get("role")
                content = msg.get("content")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": clean_prompt})

        # Use Vercel AI Gateway when configured; keep a graceful offline fallback.
        if self.api_key:
            candidate_models = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
            for model_id in candidate_models:
                try:
                    async with httpx.AsyncClient(timeout=25.0) as client:
                        resp = await client.post(
                            AI_GATEWAY_URL,
                            headers={"Authorization": f"Bearer {self.api_key}"},
                            json={
                                "model": model_id,
                                "messages": messages,
                                "max_tokens": 600,
                                "temperature": 0.7,
                                "stream": False,
                            },
                        )
                        resp.raise_for_status()
                        reply_text = (resp.json().get("choices", [{}])[0]
                                      .get("message", {}).get("content") or "").strip()
                    if reply_text:
                        suggestions = self._derive_suggestions(clean_prompt, reply_text)
                        return {
                            "reply": reply_text,
                            "model": model_id,
                            "suggestions": suggestions
                        }
                except Exception as exc:
                    logger.warning("AI Gateway model %s failed: %s", model_id, exc)

        # Intelligent offline/fallback response if Groq is unavailable
        fallback_reply = self._generate_fashion_fallback(clean_prompt, occasion, weather)
        return {
            "reply": fallback_reply,
            "model": "rule-based-stylist",
            "suggestions": [
                "How do I balance proportions in an oversized look?",
                "What footwear works best for smart-casual events?",
                "How can I build a versatile capsule wardrobe?"
            ]
        }

    def _derive_suggestions(self, prompt: str, reply: str) -> List[str]:
        """Derives 3 relevant fashion follow-up suggestions."""
        p_lower = prompt.lower()
        if "color" in p_lower or "pair" in p_lower:
            return [
                "What accessories would complement this palette?",
                "Can you recommend shoe options for this look?",
                "How can I adapt this combination for cooler weather?"
            ]
        elif "work" in p_lower or "office" in p_lower:
            return [
                "How can I transition this work outfit to an evening dinner?",
                "What jewelry or watch adds an understated touch?",
                "What bag or briefcase suits this aesthetic?"
            ]
        elif "brunch" in p_lower or "casual" in p_lower or "weekend" in p_lower:
            return [
                "What light jacket or knit layer works best?",
                "Which sneaker or loafer would you suggest?",
                "How can I add subtle texture or interest?"
            ]
        elif "rain" in p_lower or "cold" in p_lower or "winter" in p_lower:
            return [
                "What outerwear keeps me warm without losing silhouette?",
                "Which boots are both stylish and weather-resistant?",
                "How should I layer without feeling bulky?"
            ]
        return [
            "How would you accessorize this outfit?",
            "What footwear would elevate this look?",
            "How can I style these pieces for evening?"
        ]

    def _generate_fashion_fallback(
        self,
        prompt: str,
        occasion: Optional[str] = None,
        weather: Optional[Dict[str, Any]] = None
    ) -> str:
        """Graceful fallback ensuring the user always receives stylish guidance."""
        p = prompt.lower()
        if any(w in p for w in ["study", "exam", "marks", "math", "physics", "homework", "question paper"]):
            return (
                "I am your Armoire personal fashion stylist. I specialize exclusively in outfits, "
                "wardrobe curation, styling ideas, and color pairing. "
                "How can I help you elevate your personal style today?"
            )

        temp_str = f" For {weather.get('temperature')}°C weather," if weather and weather.get("temperature") else ""
        return (
            f"Here is a curated outfit formula for you:{temp_str}\n\n"
            "• **The Base**: A clean, breathable foundation such as a relaxed white poplin shirt or high-gauge knit top.\n"
            "• **The Bottom**: Tailored flat-front chinos or straight-leg trousers in a neutral tone (stone, charcoal, or deep navy).\n"
            "• **The Layer**: An unconstructed wool-linen blazer, casual chore jacket, or minimalist trench coat to add depth.\n"
            "• **Footwear**: Clean minimalist leather low-top sneakers for daytime, or dark brown leather Chelsea boots for polished sophistication.\n"
            "• **Accents**: A supple leather watch strap and a structured canvas or leather tote.\n\n"
            "This combination maintains clean lines while remaining versatile across your day."
        )


stylist_service = StylistService()
