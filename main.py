import os
import sqlite3
import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

from agents import process_incoming_message, generate_proactive_reminder

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

templates = Jinja2Templates(directory="templates")

def get_db_connection():
    # Utilizing SQLite to guarantee zero running costs for this student project
    conn = sqlite3.connect("classroom.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- TELEGRAM BOT LOGIC ---
ptb_app = Application.builder().token(TOKEN).build()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args 
    
    conn = get_db_connection()
    cursor = conn.cursor()

    if args:
        # --- STUDENT JOINED VIA LINK ---
        teacher_code = args[0]
        cursor.execute("SELECT name FROM users WHERE telegram_id = ? AND role = 'teacher'", (teacher_code,))
        teacher = cursor.fetchone()
        
        if teacher:
            # Save the ID and Teacher Link, but set the name to a flag
            cursor.execute('''
                INSERT INTO users (telegram_id, role, name, teacher_id) 
                VALUES (?, 'student', 'PENDING_NAME', ?)
                ON CONFLICT(telegram_id) DO UPDATE SET teacher_id=excluded.teacher_id, name='PENDING_NAME', role='student'
            ''', (user_id, teacher_code))
            conn.commit()
            
            await update.message.reply_text(
                f"Welcome! 👋 You have successfully connected to Teacher *{teacher['name']}*.\n\n"
                "To finish your registration, please type your **Full Official Name** below so your teacher can recognize you:"
            )
        else:
            await update.message.reply_text("Invalid invite code. Please ask your teacher for the correct link.")
    else:
        # --- UNKNOWN USER ONBOARDING MENU ---
        keyboard = [
            [
                InlineKeyboardButton("🎓 I am a Teacher", callback_data='register_teacher'),
                InlineKeyboardButton("🎒 I am a Student", callback_data='register_student')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        name = update.message.from_user.first_name
        await update.message.reply_text(
            f"Welcome to Classroom Companion, {name}! How would you like to use this bot?", 
            reply_markup=reply_markup
        )
    conn.close()

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    name = query.from_user.first_name
    
    if query.data == 'register_teacher':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (telegram_id, role, name) 
            VALUES (?, 'teacher', ?)
            ON CONFLICT(telegram_id) DO NOTHING
        ''', (user_id, name))
        conn.commit()
        conn.close()
        
        bot_username = (await context.bot.get_me()).username
        invite_link = f"[https://t.me/](https://t.me/){bot_username}?start={user_id}"
        
        await query.edit_message_text(
            f"Welcome, Teacher {name}! 🎓\n\nTo onboard your students, send them this magic link:\n{invite_link}"
        )
        
    elif query.data == 'register_student':
        await query.edit_message_text(
            "🎒 To register as a student, please ask your teacher for their specific Invite Link and click it!"
        )

async def handle_file_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Identify the student and their linked teacher
    cursor.execute("SELECT name, teacher_id FROM users WHERE telegram_id = ? AND role = 'student'", (user_id,))
    student = cursor.fetchone()
    
    if not student:
        await update.message.reply_text("Only registered students can submit files.")
        conn.close()
        return

    # 2. Find their most recent pending/in-progress assignment
    cursor.execute('''
        SELECT id, description FROM assignments 
        WHERE student_id = ? AND status != 'completed' 
        ORDER BY id DESC LIMIT 1
    ''', (user_id,))
    task = cursor.fetchone()

    if task:
        # Mark as completed
        cursor.execute("UPDATE assignments SET status = 'completed' WHERE id = ?", (task['id'],))
        
        # Log the submission
        cursor.execute('''
            INSERT INTO interactions (assignment_id, sender_id, message_text)
            VALUES (?, ?, ?)
        ''', (task['id'], user_id, "Student submitted a file/photo."))
        conn.commit()

        # 3. Forward the exact file to the Teacher
        teacher_id = student['teacher_id']
        await context.bot.send_message(
            chat_id=teacher_id, 
            text=f"📥 **New Submission from {student['name']}!**\nTask: {task['description']}\n\nPlease review the attached file and reply with feedback (e.g., 'Tell {student['name']} great job but fix the intro').",
            parse_mode="Markdown"
        )
        
        # Forward the actual document or photo
        if update.message.document:
            await context.bot.send_document(chat_id=teacher_id, document=update.message.document.file_id)
        elif update.message.photo:
            await context.bot.send_photo(chat_id=teacher_id, photo=update.message.photo[-1].file_id)

        await update.message.reply_text("🎉 Submission received! I have forwarded your file to your teacher.")
    else:
        await update.message.reply_text("You don't have any active assignments to submit right now.")
        
    conn.close()

async def handle_telegram_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    incoming_text = update.message.text.strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if this user exists and is currently setting up their name
    cursor.execute("SELECT name, role FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user and user['name'] == 'PENDING_NAME':
        # The text they sent IS their actual name! Let's update it.
        cursor.execute("UPDATE users SET name = ? WHERE telegram_id = ?", (incoming_text, user_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"Registration complete! 🎉 I've registered you as **{incoming_text}**.\n"
            "Your teacher can now assign you tasks directly through me. Stay tuned!"
        )
        return # STOP here so this text doesn't accidentally get processed by the AI Router!

    conn.close()

    if not user:
        await update.message.reply_text("Welcome! You aren't registered in the system yet.")
        return
        
    role = user['role']
    await context.bot.send_chat_action(chat_id=user_id, action='typing')
    
    # ============================================================
    # 🛠️ UPDATED AI ROUTING LOGIC 
    # ============================================================
    try:
        from llm_routing import classify_intent  
        llm_output_string = classify_intent(role, incoming_text)
        
        # Strip out Markdown backticks in case Llama 3 adds them
        clean_string = llm_output_string.replace("```json", "").replace("```", "").strip()
        
        parsed_json = json.loads(clean_string)
        intent = parsed_json.get("intent", "GENERAL_QUERY")
        extracted_data = parsed_json.get("extracted_data", {})
    except Exception as e:
        print(f"Error parsing LLM routing: {e}")
        intent = "GENERAL_QUERY"
        extracted_data = {}
    loop=asyncio.get_running_loop()

    # 2. Pass all variables safely into the processing engine
    reply = await asyncio.to_thread(
        process_incoming_message, 
        intent, 
        extracted_data, 
        user_id, 
        role, 
        incoming_text,
        context.bot,
        loop
    )
    
    await update.message.reply_text(reply)

# Register Handlers
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CallbackQueryHandler(button_callback)) # Added the missing button handler!
ptb_app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file_submission))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_message))

# --- FASTAPI LIFECYCLE & WEBHOOK ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Setting Webhook to: {WEBHOOK_URL}/webhook")
    await ptb_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    
    async with ptb_app:
        await ptb_app.start()
        yield
        await ptb_app.stop()

app = FastAPI(title="Classroom Companion Bot", lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    update_dict = await request.json()
    update = Update.de_json(update_dict, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"status": "ok"}

# --- UI ENDPOINTS ---
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return "<h1>Classroom Companion Backend Running</h1>"

@app.get("/teacher/{teacher_id}", response_class=HTMLResponse)
async def teacher_dashboard(request: Request, teacher_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.telegram_id as student_id, u.name as student_name, a.description, a.deadline, a.status 
        FROM assignments a
        JOIN users u ON a.student_id = u.telegram_id
        WHERE a.teacher_id = ?
        ORDER BY a.status DESC, a.id DESC
    ''', (teacher_id,))
    assignments = cursor.fetchall()
    conn.close()
    
    return templates.TemplateResponse(
        request=request,
        name="teacher.html", 
        context={"request": request, "teacher_id": teacher_id, "assignments": assignments}
    )

@app.get("/trigger-reminders")
async def trigger_reminders(request: Request):
    """Secret endpoint to trigger proactive reminders during a live demo."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Find all students with pending or in-progress assignments
    cursor.execute('''
        SELECT a.id, a.description, a.deadline, u.telegram_id, u.name
        FROM assignments a
        JOIN users u ON a.student_id = u.telegram_id
        WHERE a.status != 'completed'
    ''')
    active_tasks = cursor.fetchall()
    
    reminders_sent = 0
    for task in active_tasks:
        nudge_message = await asyncio.to_thread(
            generate_proactive_reminder, 
            task['name'], 
            task['description'], 
            task['deadline']
        )
        
        try:
            await ptb_app.bot.send_message(
                chat_id=task['telegram_id'], 
                text=f"🔔 *Automated Nudge*\n\n{nudge_message}",
                parse_mode="Markdown"
            )
            
            cursor.execute('''
                INSERT INTO interactions (assignment_id, sender_id, message_text)
                VALUES (?, ?, ?)
            ''', (task['id'], ptb_app.bot.id, f"System sent reminder: {nudge_message}"))
            
            reminders_sent += 1
        except Exception as e:
            print(f"Failed to send reminder to {task['name']}: {e}")
            
    conn.commit()
    conn.close()
    
    return {"status": "success", "reminders_sent": reminders_sent}

@app.get("/student/{student_id}", response_class=HTMLResponse)
async def student_dashboard(request: Request, student_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, description, deadline, status FROM assignments 
        WHERE student_id = ? ORDER BY id DESC
    ''', (student_id,))
    assignments = cursor.fetchall()
    
    cursor.execute('''
        SELECT assignment_id, sender_id, message_text, timestamp 
        FROM interactions 
        WHERE assignment_id IN (SELECT id FROM assignments WHERE student_id = ?)
        ORDER BY timestamp ASC
    ''', (student_id,))
    logs_raw = cursor.fetchall()
    conn.close()

    logs_by_assignment = {}
    for log in logs_raw:
        aid = log['assignment_id']
        if aid not in logs_by_assignment:
            logs_by_assignment[aid] = []
        logs_by_assignment[aid].append(log)

    return templates.TemplateResponse(
        request=request,
        name="student.html", 
        context={"request": request, "student_id": student_id, "assignments": assignments, "logs": logs_by_assignment}
    )