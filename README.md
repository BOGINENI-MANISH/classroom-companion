# 🎓 Classroom Companion

### *AI-Powered Educational Assistant for Modern Classrooms*

> **Transforming classroom management into a seamless conversational experience using AI, automation, and real-time collaboration.**

---

# 🌟 Overview

**Classroom Companion** is an intelligent Telegram-based educational assistant that bridges the communication gap between teachers and students through conversational AI.

Built with a **FastAPI backend**, **Groq-powered LLM routing**, and a **deterministic workflow engine**, the system enables educators to create assignments, monitor progress, and interact with students naturally — all through simple chat messages.

The platform combines:

* ⚡ **Low-latency AI inference**
* 🧠 **Natural Language Understanding**
* 🔄 **Deterministic state management**
* 📊 **Real-time assignment tracking**
* 🤖 **Automated reminders & progress monitoring**

into one unified ecosystem.

---

# ✨ Key Features

## 👩‍🏫 Teacher Capabilities

### 🔗 Smart Classroom Onboarding

Generate secure **Magic Invite Links** that instantly connect students to a teacher’s classroom using Telegram Deep Linking.

### 📝 Natural Language Assignment Creation

Teachers can simply type:

```text
Assign Riya a 500-word essay due Friday
```

The AI automatically extracts:

* Student Name
* Assignment Description
* Deadline
* Intent Type

### 📈 Real-Time Classroom Analytics

Ask conversational questions like:

```text
How is my class doing?
```

and receive structured progress summaries powered by database queries.

### 🖥️ Teacher Dashboard

A dedicated web interface built with **Tailwind CSS** visualizes:

* Active assignments
* Pending deadlines
* Student activity
* Submission status

---

## 👨‍🎓 Student Capabilities

### 🧾 Interactive Registration Flow

Students complete a guided onboarding process using invite codes tied directly to their teacher.

### 💬 Conversational Progress Updates

Students can naturally communicate progress:

```text
I'm halfway done with chapter 4
```

which automatically updates assignment status to:

```text
in-progress
```

### ✅ Automated Completion Tracking

Simple completion messages instantly update database records:

```text
I'm done!
```

### 🔔 AI-Generated Smart Reminders

Background reminder engines proactively notify students about:

* Upcoming deadlines
* Pending assignments
* Incomplete tasks

### 📊 Student Dashboard

Students receive a personal dashboard displaying:

* Current assignments
* Deadlines
* Progress history
* Interaction logs

---

# 🏗️ System Architecture

## 🧠 Architectural Philosophy

The system follows a **Procedural LLM Architecture** rather than a fully autonomous agentic system.

Instead of allowing the LLM to directly execute actions:

* The AI acts only as an **Intent Classifier**
* Structured outputs are validated
* Backend logic remains deterministic and secure
* SQL operations are strictly controlled

This approach provides:

| Advantage               | Benefit                       |
| ----------------------- | ----------------------------- |
| ⚡ Faster Response Time  | Minimal latency using Groq    |
| 🔒 Reliability          | Deterministic execution paths |
| 🧩 Structured Outputs   | JSON-based intent routing     |
| 💰 Low Operational Cost | SQLite + lightweight backend  |
| 🛠️ Easier Debugging    | Predictable backend workflows |

---

# 🔄 End-to-End Message Flow

```text
┌──────────────────┐
│  Telegram User   │
└────────┬─────────┘
         │ Message
         ▼
┌──────────────────┐
│ Telegram Webhook │
└────────┬─────────┘
         │ POST Request
         ▼
┌───────────────────────────┐
│ FastAPI Webhook Endpoint  │
│       (/webhook)          │
└────────┬──────────────────┘
         │
         ▼
┌───────────────────────────┐
│ State & Role Verification │
│   SQLite User Lookup      │
└────────┬──────────────────┘
         │
         ▼
┌───────────────────────────┐
│      Groq Llama 3 AI      │
│ Intent + Entity Extraction│
└────────┬──────────────────┘
         │ Structured JSON
         ▼
┌───────────────────────────┐
│ Deterministic Python Logic│
│  SQL Execution Layer      │
└────────┬──────────────────┘
         │
         ▼
┌───────────────────────────┐
│ Telegram Response Engine  │
└───────────────────────────┘
```

---

# ⚙️ Core Technology Stack

| Layer                 | Technology                        |
| --------------------- | --------------------------------- |
| 🚀 Backend Framework  | FastAPI                           |
| 🧠 AI Engine          | Groq API (`llama-3.1-8b-instant`) |
| 🗄️ Database          | SQLite                            |
| 💬 Messaging Platform | Telegram Bot API                  |
| 🌐 Webhook Tunneling  | ngrok                             |
| 🎨 Frontend           | Jinja2 + Tailwind CSS             |
| 🔄 Async Runtime      | Uvicorn                           |

---

# 🗄️ Database Design

The system is powered by a relational SQLite schema optimized for role-based classroom management.

## 👤 `users` Table

| Column        | Description         |
| ------------- | ------------------- |
| `telegram_id` | Primary Key         |
| `role`        | teacher / student   |
| `name`        | User display name   |
| `teacher_id`  | Foreign key mapping |

---

## 📚 `assignments` Table

| Column        | Description                       |
| ------------- | --------------------------------- |
| `id`          | Assignment ID                     |
| `teacher_id`  | Creator                           |
| `student_id`  | Assigned Student                  |
| `description` | Assignment details                |
| `deadline`    | Submission deadline               |
| `status`      | pending / in-progress / completed |

---

## 💬 `interactions` Table

| Column          | Description          |
| --------------- | -------------------- |
| `id`            | Interaction ID       |
| `assignment_id` | Linked assignment    |
| `sender_id`     | Message sender       |
| `message_text`  | Conversation content |
| `timestamp`     | Interaction time     |

---

# 🚀 Setup & Installation

## 1️⃣ Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/classroom-companion.git
cd classroom-companion
```

---

## 2️⃣ Create Virtual Environment

### Mac/Linux

```bash
python -m venv venv
source venv/bin/activate
```

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

---

## 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4️⃣ Configure Environment Variables

Create a `.env` file:

```env
TELEGRAM_BOT_TOKEN="your_botfather_token_here"

WEBHOOK_URL="https://your-ngrok-url.ngrok-free.app"

LLM_API_KEY="gsk_your_groq_api_key_here"

LLM_BASE_URL="https://api.groq.com/openai/v1"

LLM_MODEL="llama-3.1-8b-instant"
```

---

# ▶️ Running the Application

## Terminal 1 — Start ngrok

```bash
ngrok http 8000
```

Copy the generated forwarding URL into `.env`.

---

## Terminal 2 — Start FastAPI Server

```bash
uvicorn main:app --reload
```

---

# 🧪 Testing the Workflow

## 👩‍🏫 Teacher Initialization

```text
/start
```

Select:

```text
I am a Teacher
```

to generate your classroom invite link.

---

## 👨‍🎓 Student Registration

Open the invite link from another Telegram account and complete onboarding.

---

## 📝 Assignment Creation

Teacher message:

```text
Assign Riya chapter 4 reading due tomorrow
```

---

## 📈 Progress Updates

Student message:

```text
I'm halfway done with chapter 4
```

---

## 🌐 Dashboard Access

```text
http://localhost:8000/teacher/<your_telegram_id>
```

---

## 🔔 Trigger Reminder Engine

```text
http://localhost:8000/trigger-reminders
```

---

# 🔮 Future Enhancements

## 🤖 Transition to Multi-Agent Architecture

The platform is intentionally designed for future migration toward an autonomous agent ecosystem using frameworks like:

* LangGraph
* CrewAI
* AutoGen

### Proposed Agent Ecosystem

```text
┌──────────────────┐
│   Router Agent   │
└────────┬─────────┘
         │
 ┌───────┴────────┐
 ▼                ▼
Teacher Agent   Student Agent
        │
        ▼
 Summariser Agent
        │
        ▼
 Retrieval & Analytics
```

---

# 📌 Why This Project Matters

Classroom Companion demonstrates the practical integration of:

* Conversational AI
* State Machines
* Webhook Architectures
* Real-Time Messaging Systems
* AI-Assisted Workflow Automation
* Deterministic LLM Routing

while maintaining:

* scalability
* reliability
* explainability
* low operational cost

making it highly suitable for real-world EdTech deployment.

---

# 💡 Built For

* AI/ML Portfolio Projects
* EdTech Platforms
* Conversational Automation Systems
* Telegram Bot Ecosystems
* AI Workflow Orchestration Demonstrations
* Full-Stack AI Engineering Showcases

---

# ⭐ Final Vision

> *“Making classroom communication as simple as having a conversation.”*

**Classroom Companion** combines the intelligence of modern LLMs with the reliability of deterministic backend systems to create an educational assistant that feels intuitive, scalable, and production-ready.
