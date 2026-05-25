from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

import sqlite3
import os
import asyncio
from dotenv import load_dotenv

from agents import process_incoming_message 

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

templates = Jinja2Templates(directory="templates")

def get_db_connection():
    conn = sqlite3.connect("classroom.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- TELEGRAM BOT LOGIC ---
ptb_app = Application.builder().token(TOKEN).build()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    name = update.message.from_user.first_name
    args = context.args 
    
    conn = get_db_connection()
    cursor = conn.cursor()

    if args:
        # --- STUDENT ONBOARDING VIA DEEP LINK ---
        teacher_code = args[0]
        cursor.execute("SELECT name FROM users WHERE telegram_id = ? AND role = 'teacher'", (teacher_code,))
        teacher = cursor.fetchone()
        
        if teacher:
            cursor.execute('''
                INSERT INTO users (telegram_id, role, name, teacher_id) 
                VALUES (?, 'student', ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET teacher_id=excluded.teacher_id, role='student'
            ''', (user_id, name, teacher_code))
            conn.commit()
            await update.message.reply_text(f"Success! 🎒 You are linked to Teacher {teacher['name']}.")
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
        invite_link = f"https://t.me/{bot_username}?start={user_id}"
        
        await query.edit_message_text(
            f"Welcome, Teacher {name}! 🎓\n\nTo onboard your students, send them this magic link:\n{invite_link}"
        )
        
    elif query.data == 'register_student':
        await query.edit_message_text(
            "🎒 To register as a student, please ask your teacher for their specific Invite Link and click it!"
        )

# Make sure to register the callback handler down where your other handlers are:
# ptb_app.add_handler(CallbackQueryHandler(button_callback))
    else:
        # --- TEACHER ONBOARDING ---
        # Register the teacher (if they don't already exist)
        cursor.execute('''
            INSERT INTO users (telegram_id, role, name) 
            VALUES (?, 'teacher', ?)
            ON CONFLICT(telegram_id) DO NOTHING
        ''', (user_id, name))
        conn.commit()
        
        # Generate the magic invite link
        bot_username = (await context.bot.get_me()).username
        invite_link = f"https://t.me/{bot_username}?start={user_id}"
        
        await update.message.reply_text(
            f"Welcome, Teacher {name}! 🎓\n\n"
            f"To onboard your students, simply send them this magic link:\n"
            f"{invite_link}\n\n"
            f"Once they click it, they will be instantly linked to your classroom."
        )
        
    conn.close()

async def handle_telegram_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    
    # Edge Case: Handle non-text messages (images, stickers) gracefully
    if not text:
        await update.message.reply_text("I only understand text messages right now! Please type out your request.")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        await update.message.reply_text("Welcome! You aren't registered in the system yet.")
        return
        
    role = user['role']
    await context.bot.send_chat_action(chat_id=user_id, action='typing')
    
    # Run AI logic asynchronously
    reply = await asyncio.to_thread(process_incoming_message, user_id, role, text)
    await update.message.reply_text(reply)

ptb_app.add_handler(CommandHandler("start", start_command))
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
from agents import generate_proactive_reminder

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
        # Generate the friendly AI nudge
        nudge_message = await asyncio.to_thread(
            generate_proactive_reminder, 
            task['name'], 
            task['description'], 
            task['deadline']
        )
        
        # Send it directly to the student's Telegram
        try:
            await ptb_app.bot.send_message(
                chat_id=task['telegram_id'], 
                text=f"🔔 *Automated Nudge*\n\n{nudge_message}",
                parse_mode="Markdown"
            )
            
            # Log the interaction in the database so the student/teacher can see it in the UI
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