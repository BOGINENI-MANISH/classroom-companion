import sqlite3
import asyncio
from llm_routing import client, MODEL_NAME

DB_PATH = "classroom.db"

def get_db_connection():
    # Utilizing SQLite to guarantee zero running costs for this student project
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
    # Use the clean, extracted description instead of the raw message!
    clean_description = entities.get('description', message) 
    
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
    ''', (student['telegram_id'], teacher_id, clean_description, deadline))
    
    conn.commit()
    conn.close()
    
    context = "You are a helpful assistant confirming to a teacher that you recorded an assignment."
    return generate_conversational_reply(context, f"Confirm this task was created: {clean_description}")

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

def handle_status_check(teacher_id: int) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Grab the active tasks AND the most recent student chat logs
    cursor.execute('''
        SELECT u.name, a.description, a.status, 
               (SELECT message_text FROM interactions i WHERE i.assignment_id = a.id AND i.sender_id = u.telegram_id ORDER BY i.id DESC LIMIT 1) as last_update
        FROM assignments a
        JOIN users u ON a.student_id = u.telegram_id
        WHERE a.teacher_id = ? AND a.status != 'completed'
    ''', (teacher_id,))
    tasks = cursor.fetchall()
    conn.close()

    if not tasks:
        return "All your students are caught up! No pending assignments."

    # Build a raw data string to feed to Groq
    raw_data = "Here is the raw data of student progress:\n"
    for task in tasks:
        update_text = task['last_update'] if task['last_update'] else "No updates reported yet."
        raw_data += f"Student: {task['name']} | Task: {task['description']} | Status: {task['status']} | Last thing they said: {update_text}\n"

    # Ask Groq to summarize it naturally
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful teaching assistant. Read the raw data of student progress and write a short, friendly, readable summary for the teacher. Highlight anyone who is stuck."},
                {"role": "user", "content": raw_data}
            ],
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        return "I had trouble generating the AI summary, but your web dashboard has all the latest updates!"

def handle_student_status_check(student_id: int) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Look up only the tasks assigned to THIS specific student
    cursor.execute('''
        SELECT description, deadline, status
        FROM assignments
        WHERE student_id = ? AND status != 'completed'
    ''', (student_id,))
    tasks = cursor.fetchall()
    conn.close()

    if not tasks:
        return "🎉 You have no pending assignments! You are completely caught up."

    report = "📋 **Your Active Homework:**\n\n"
    for task in tasks:
        report += f"🔹 **{task['description']}**\n   Due: {task['deadline']} | Status: [{task['status'].upper()}]\n\n"

    return report

def generate_proactive_reminder(student_name: str, assignment_desc: str, deadline: str) -> str:
    context = """You are a supportive, friendly teacher's assistant. 
Your job is to write a very short, encouraging reminder to a student about their pending work.
Keep it casual, helpful, and under 3 sentences. Do not be scolding."""
    
    prompt = f"Student: {student_name}\nTask: {assignment_desc}\nDeadline: {deadline}"
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": context},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Hey {student_name}, just a quick automated nudge that your task '{assignment_desc}' is still pending!"

def process_incoming_message(intent: str, extracted_data: dict, sender_id: int, sender_role: str, incoming_text: str, bot, loop) -> str:
    print(f"--- Routed Intent: {intent} ---")
    
    if intent == "CREATE_ASSIGNMENT" and sender_role == "teacher":
        return handle_teacher_assignment(sender_id, incoming_text, extracted_data)
        
    elif intent == "PROGRESS_UPDATE" and sender_role == "student":
        return handle_student_update(sender_id, incoming_text, is_completion=False)
        
    elif intent == "COMPLETION" and sender_role == "student":
        return handle_student_update(sender_id, incoming_text, is_completion=True)
    
    elif intent == "CHECK_STATUS":
        if sender_role == "teacher":
            return handle_status_check(sender_id)
        elif sender_role == "student":
            return handle_student_status_check(sender_id)
            
    elif intent == "GIVE_FEEDBACK" and sender_role == "teacher":
        student_name = extracted_data.get("student_name")
        feedback_text = extracted_data.get("feedback")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find the student's Telegram ID
        cursor.execute("SELECT telegram_id FROM users WHERE name LIKE ? AND teacher_id = ?", (f"%{student_name}%", sender_id))
        student = cursor.fetchone()
        
        if student:
            # Push the feedback directly to the student's Telegram
            asyncio.create_task(
                bot.send_message(
                    chat_id=student['telegram_id'], 
                    text=f"📝 **Feedback from your Teacher:**\n\n{feedback_text}",
                    parse_mode="Markdown"
                ),
                loop
            )
            response = f"Feedback sent successfully to {student_name}!"
        else:
            response = f"I couldn't find a student named {student_name} in your roster."
            
        conn.close()
        return response
        
    else:
        # Softened anti-hallucination prompt
        strict_prompt = (
            "You are a helpful classroom assistant. "
            "CRITICAL RULE: DO NOT EVER make up, invent, or hallucinate an assignment. "
            "If a student asks a general question, answer politely. If they ask about assignments and the system didn't route it properly, ask them to type 'What is my status?'"
        )
        return generate_conversational_reply(strict_prompt, incoming_text)