import sqlite3
from llm_routing import client, MODEL_NAME, classify_intent

DB_PATH = "classroom.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_conversational_reply(system_context: str, user_message: str) -> str:
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_context},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return "I processed your request, but had trouble generating a custom reply."

def handle_teacher_assignment(teacher_id: int, message: str, entities: dict) -> str:
    student_name = entities.get('student_name')
    deadline = entities.get('deadline')
    
    if not student_name:
        return "I couldn't catch the student's name. Could you rephrase the assignment?"

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT telegram_id FROM users WHERE name LIKE ? AND role = 'student'", (f"%{student_name}%",))
    student = cursor.fetchone()
    
    if not student:
        conn.close()
        return f"I couldn't find a student named {student_name} in your roster."
    
    cursor.execute('''
        INSERT INTO assignments (student_id, teacher_id, description, deadline, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (student['telegram_id'], teacher_id, message, deadline))
    
    conn.commit()
    conn.close()
    
    context = "You are a helpful assistant confirming to a teacher that you recorded an assignment."
    return generate_conversational_reply(context, f"Confirm this task was created: {message}")

def handle_student_update(student_id: int, message: str, is_completion: bool = False) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM assignments 
        WHERE student_id = ? AND status != 'completed' 
        ORDER BY id DESC LIMIT 1
    ''', (student_id,))
    assignment = cursor.fetchone()
    
    if not assignment:
        conn.close()
        return "I don't see any active assignments for you right now."
    
    assignment_id = assignment['id']
    
    cursor.execute('''
        INSERT INTO interactions (assignment_id, sender_id, message_text)
        VALUES (?, ?, ?)
    ''', (assignment_id, student_id, message))
    
    if is_completion:
        cursor.execute("UPDATE assignments SET status = 'completed' WHERE id = ?", (assignment_id,))
        context = "You are an encouraging assistant. Congratulate the student on finishing their work."
    else:
        cursor.execute("UPDATE assignments SET status = 'in-progress' WHERE id = ?", (assignment_id,))
        context = "You are an encouraging assistant. Acknowledge the student's progress update."
        
    conn.commit()
    conn.close()
    
    return generate_conversational_reply(context, f"Student said: {message}")

def process_incoming_message(sender_id: int, sender_role: str, message: str) -> str:
    intent_data = classify_intent(sender_role, message)
    intent = intent_data.get("intent")
    entities = intent_data.get("extracted_entities", {})
    
    print(f"--- Routed Intent: {intent} ---")
    
    if intent == "CREATE_ASSIGNMENT" and sender_role == "teacher":
        return handle_teacher_assignment(sender_id, message, entities)
        
    elif intent == "PROGRESS_UPDATE" and sender_role == "student":
        return handle_student_update(sender_id, message, is_completion=False)
        
    elif intent == "COMPLETION" and sender_role == "student":
        return handle_student_update(sender_id, message, is_completion=True)
        
    else:
        return generate_conversational_reply("You are a helpful classroom assistant. Answer generally.", message)