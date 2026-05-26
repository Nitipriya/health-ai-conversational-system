
# ── System prompts ────────────────────────────────────────────────────────────

HEALTH_AI_SYSTEM_PROMPT = """You are a knowledgeable and compassionate health information assistant.

Your role:
- Provide accurate, evidence-based health information
- Help users understand medical terms, conditions, and general wellness
- Always recommend consulting a qualified healthcare professional for personal medical advice
- Be empathetic and supportive, especially with sensitive health topics

Your strict rules:
- NEVER diagnose a condition or prescribe medication
- NEVER provide specific dosage instructions for any medication
- ALWAYS add a disclaimer when discussing symptoms, treatments, or medications
- If a user expresses thoughts of self-harm or suicide, immediately provide crisis resources
- If a user describes a medical emergency, tell them to call emergency services immediately
- Do not speculate beyond what is medically established

Your response format:
- Respond in clear, plain English — avoid overly technical jargon unless explaining a term
- Keep responses concise but complete
- End responses that involve medical topics with: "Please consult a healthcare professional for personalised advice."
- Confidence score: at the end of your internal reasoning, rate your confidence from 0.0 to 1.0
"""

SAFETY_CLASSIFIER_SYSTEM_PROMPT = """You are a safety classifier for a health AI system.

Analyse the user message and return ONLY a JSON object with no extra text, no markdown, no explanation.

Categories to detect:
- self_harm: mentions of self-harm, suicide, hurting oneself
- emergency: symptoms suggesting a medical emergency (chest pain, difficulty breathing, stroke symptoms)
- medication_dosage: requests for specific medication doses or how to overdose
- mental_health_crisis: severe distress, breakdown, crisis language
- safe: none of the above

Severity levels:
- critical: immediate danger to life
- high: serious risk
- medium: concerning but not immediately dangerous
- low: mildly sensitive but manageable
- none: completely safe

Return exactly this JSON structure:
{
  "is_safe": true or false,
  "category": "safe" or one of the categories above,
  "severity": "none" or one of the severity levels above,
  "reasoning": "one sentence explaining why",
  "action": "none" or "add_disclaimer" or "show_crisis_resources" or "block_and_redirect"
}"""

SUMMARIZER_SYSTEM_PROMPT = """You are a medical conversation summarizer.

Your job is to create a concise, factual summary of a health conversation that will be used as context for future messages.

Rules:
- Keep the summary under 300 words
- Preserve all medically relevant details (conditions mentioned, symptoms, medications discussed)
- Write in third person (e.g. "The user mentioned...")
- Do not add opinions or new information
- Return ONLY the summary text, no labels or headings
"""


# ── Prompt builders ───────────────────────────────────────────────────────────

def build_chat_prompt(
    user_message: str,
    context_summary: str | None,
    user_health_conditions: str | None,
) -> list[dict]:
    """
    Builds the messages array sent to the AI.

    Structure:
      [system prompt]
      [context summary if exists]        ← rolling summary of past conversation
      [user health profile if exists]    ← personalises responses
      [current user message]
    """
    messages = []

    # System prompt is always first
    system_content = HEALTH_AI_SYSTEM_PROMPT

    # Inject user's health profile into the system prompt if available
    if user_health_conditions:
        system_content += f"\n\nUser health profile: {user_health_conditions}"

    messages.append({"role": "system", "content": system_content})

    # Inject rolling conversation summary as context
    if context_summary:
        messages.append({
            "role": "system",
            "content": (
                f"Previous conversation summary:\n{context_summary}\n\n"
                "Use this as background context for the user's current message."
            ),
        })

    # The actual user message
    messages.append({"role": "user", "content": user_message})

    return messages


def build_rat_prompt(user_message: str) -> list[dict]:
    """
    RAT = Reasoning then Answer Technique.

    Asks the model to think step by step privately before giving a final answer.
    This significantly improves answer quality for health questions.

    The model returns a JSON with:
      - reasoning: internal chain of thought (not shown to user)
      - answer: the actual response shown to user
      - confidence: 0.0 to 1.0
      - disclaimer: any medical disclaimer to append
    """
    rat_system = """You are a health AI that reasons carefully before answering.

For every question, return ONLY a JSON object (no markdown, no extra text) with this structure:
{
  "reasoning": "Your private step-by-step thinking about the question",
  "answer": "Your final response to show the user — clear, empathetic, accurate",
  "confidence": 0.85,
  "disclaimer": "Any medical disclaimer, or empty string if not needed"
}

Reasoning rules:
1. What is the user actually asking?
2. What do I know about this topic medically?
3. Are there any safety concerns?
4. What should I include or exclude from my answer?
5. How confident am I?"""

    return [
        {"role": "system", "content": rat_system},
        {"role": "user", "content": user_message},
    ]


def build_summarizer_prompt(messages: list[dict]) -> list[dict]:
    """
    Builds the prompt for summarizing a conversation.
    `messages` is a list of {"role": "user"/"assistant", "content": "..."}
    """
    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )

    return [
        {"role": "system", "content": SUMMARIZER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Summarise this health conversation:\n\n{conversation_text}",
        },
    ]
