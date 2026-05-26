import json
import os
import openai  # type: ignore[import]
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL") 
MODEL_NAME = os.getenv("LLM_MODEL", "llama-3.1-8b-instant") # Defaulting to the fast model

client = openai.OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL if BASE_URL else None
)

# Changed return type from dict to str to match main.py!
def classify_intent(sender_role: str, user_message: str) -> str: 
    system_prompt = """You are a STRICT Intent Classification and Entity Extraction API for a classroom Telegram bot. 
Your ONLY job is to read the message, determine the user's intent, and extract the assignment metadata into a JSON object.

CRITICAL OVERRIDE RULE (THE "ROUTER" RULE): 
You are a software router, NOT a student. You MUST NEVER actually fulfill the task the teacher is assigning. 
- If the teacher says "Assign an essay", DO NOT write the essay.
- If the teacher says "Assign math problems 1-10", DO NOT solve the math problems.
- If the teacher says "Assign a Python script", DO NOT write the code.
Your job is purely to capture the text of what the teacher said and place it in the "description" field. DO NOT output conversational text. OUTPUT VALID JSON ONLY.

AVAILABLE INTENTS:
1. "CREATE_ASSIGNMENT": A teacher assigns new work to a student.
2. "PROGRESS_UPDATE": A student shares a status update on their work.
3. "COMPLETION": A student explicitly states they have finished the work.
4. "GIVE_FEEDBACK": A teacher provides feedback on a submission.
5. "CHECK_STATUS": A teacher asks for an overall summary of their students' progress, OR a student asks to see their own pending assignments, homework, or progress.
6. "GENERAL_QUERY": Greetings, unidentifiable text, or general questions.

EXPECTED JSON FORMAT:
{
  "intent": "INTENT_NAME_HERE",
  "extracted_data": {
     "student_name": "Name of student (if applicable)",
     "deadline": "Deadline (if applicable)",
     "description": "The exact description of the task or feedback being given (if applicable)"
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
        # Return the RAW STRING so main.py can clean it up before parsing
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Routing Error: {e}")
        # Return a safe fallback JSON string
        return json.dumps({
            "intent": "GENERAL_QUERY",
            "extracted_data": {}
        })