from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
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
        SELECT u.name as student_name, a.description, a.deadline, a.status 
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