import sqlite3
from database import init_db
from agents import process_incoming_message

def setup_mock_data():
    init_db()
    conn = sqlite3.connect("classroom.db")
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM users")
    cursor.execute("DELETE FROM assignments")
    cursor.execute("DELETE FROM interactions")
    
    # Mock data
    cursor.execute("INSERT INTO users (telegram_id, role, name) VALUES (101, 'teacher', 'Mr. Smith')")
    cursor.execute("INSERT INTO users (telegram_id, role, name, teacher_id) VALUES (202, 'student', 'Riya', 101)")
    
    conn.commit()
    conn.close()

def run_tests():
    print("Setting up database...")
    setup_mock_data()
    
    print("\n=== TEST 1: Teacher Assigns Work ===")
    response = process_incoming_message(101, "teacher", "Assign Riya a 500-word essay on photosynthesis, due Friday.")
    print(f"Bot Reply: {response}")
    
    print("\n=== TEST 2: Student Sends Progress Update ===")
    response = process_incoming_message(202, "student", "I am stuck on the intro paragraph.")
    print(f"Bot Reply: {response}")

    print("\n=== TEST 3: Student Completes Assignment ===")
    response = process_incoming_message(202, "student", "I just finished the essay, here is my submission.")
    print(f"Bot Reply: {response}")

    print("\n=== VERIFYING SQLITE STATE ===")
    conn = sqlite3.connect("classroom.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT status, description FROM assignments WHERE student_id = 202")
    assignment = cursor.fetchone()
    print(f"DB Assignment -> Status: {assignment[0]}, Task: {assignment[1][:30]}...")
    
    conn.close()

if __name__ == "__main__":
    run_tests()