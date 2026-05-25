import json
import os
import openai  # type: ignore[import]
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL") 
MODEL_NAME = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

client = openai.OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL if BASE_URL else None
)

def classify_intent(sender_role: str, user_message: str) -> dict:
    system_prompt = """You are the Intent Classification Agent for the "Classroom Companion" Telegram bot. 
Your sole responsibility is to analyze incoming messages from either a 'Teacher' or a 'Student' and classify the user's intent.

AVAILABLE INTENTS:
1. "CREATE_ASSIGNMENT": A teacher assigns new work.
2. "PROGRESS_UPDATE": A student shares a status update.
3. "COMPLETION": A student explicitly states they have finished.
4. "GIVE_FEEDBACK": A teacher provides feedback on a submission.
5. "CHECK_STATUS": A teacher asks for an update on their students' progress.
6. "GENERAL_QUERY": Greetings or general questions.

RULES:
- You must ONLY output valid JSON. No markdown, no conversational filler.
- Extract the 'student_name' and 'deadline' if present, otherwise set to null.

OUTPUT FORMAT:
{
  "intent": "<EXACT_INTENT_NAME>",
  "confidence_score": 0.95,
  "extracted_entities": {
    "student_name": "name or null",
    "deadline": "deadline or null"
  }
}"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"SENDER ROLE: {sender_role}\nMESSAGE: {user_message}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        print(f"Routing Error: {e}")
        return {
            "intent": "GENERAL_QUERY",
            "confidence_score": 0.0,
            "extracted_entities": {"student_name": None, "deadline": None}
        }