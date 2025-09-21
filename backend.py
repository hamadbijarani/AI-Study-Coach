import os
import time
import shutil
import hashlib
import sqlite3
import datetime


def get_elapsed_time(start_time):
    """Returns the elapsed time in seconds since start_time."""
    elapsed = int(time.time() - start_time)
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def get_mermaid_html(mindmap_content: str):
    mermaid_html = f"""
            <html>
                <head>
                    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
                    <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom/dist/svg-pan-zoom.min.js"></script>
                    <style>
                        html, body {{
                            margin: 0; padding: 0; width: 100%; height: 100%;
                            overflow: hidden; background: #000000; 
                            font-family: Arial, sans-serif;
                        }}
                        .mermaid {{
                            width: 100%;
                            height: 100%;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                        }}
                        svg {{
                            width: 100%;
                            height: 100%;
                        }}
                        .node rect, .node polygon, .node ellipse {{
                            fill: #e8f0fe;      /* Light pastel background */
                            stroke: #1a73e8;    /* Google blue border */
                            stroke-width: 1.5px;
                        }}
                        .node text, .nodeLabel span {{
                            cursor: pointer;
                            fill: #202124;      /* Dark readable text */
                            font-weight: 500;
                        }}
                        .node text:hover, .nodeLabel span:hover {{
                            text-decoration: underline;
                            fill: #d93025;      /* Red on hover */
                        }}
                    </style>
                </head>
                <body>
                    <div class="mermaid">
                        {mindmap_content}
                    </div>
                    <script>
                        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});

                        document.addEventListener("DOMContentLoaded", function() {{
                            setTimeout(function() {{
                                var svg = document.querySelector('.mermaid > svg');
                                if (!svg) return;

                                var nodes = svg.querySelectorAll('.node .label, .nodeLabel span');

                                nodes.forEach(function(node) {{
                                    node.style.pointerEvents = "all";
                                    node.addEventListener('click', function(event) {{
                                        event.stopPropagation();
                                        var query = node.textContent.trim();
                                        if (query) {{
                                            if (window.confirm("Do you want to search Google for '" + query + "'?")) {{
                                                var url = "https://www.google.com/search?q=" + encodeURIComponent(query);
                                                window.open(url, "_blank");
                                            }}
                                        }}
                                    }});
                                }});

                                svgPanZoom(svg, {{
                                    zoomEnabled: true,
                                    panEnabled: true,
                                    controlIconsEnabled: true,
                                    fit: true,
                                    center: true
                                }});
                            }}, 1000);
                        }});
                    </script>
                </body>
            </html>
            """
    return mermaid_html


# Define the database file
DB_FILE = "study_app.db"

def create_db_file():
    """Creates the database file if it doesn't exist."""
    if not os.path.exists(DB_FILE):
        open(DB_FILE, 'w').close()
        print(f"Database file '{DB_FILE}' created.")
    else:
        print(f"Database file '{DB_FILE}' already exists.")

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    conn.execute("PRAGMA foreign_keys = ON;") # Enforce foreign key constraints
    return conn

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    create_db_file()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # --- Core Tables (Unchanged) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_hash TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(user_id, name)
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
                UNIQUE(subject_id, name)
            );
        ''')
        
        # --- Chat with AI history table ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                role TEXT CHECK(role IN ('user', 'assistant')) NOT NULL,
                message TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        ''')

        conn.commit()
    print("Database initialized successfully.")

# --- Helper function to get user ID ---def _get_user_id(cursor, sha1_of_username):
def _get_user_id(cursor, sha1_of_username):
    """Fetches user ID from a user hash. Returns None if not found."""
    cursor.execute("SELECT id FROM users WHERE user_hash = ?", (sha1_of_username,))
    user = cursor.fetchone()
    return user['id'] if user else None

def _get_chapter_id(cursor, sha1_of_username, subject_name, chapter_name):
    """Fetches chapter ID using user, subject, and chapter names. Returns None if not found."""
    query = """
        SELECT c.id FROM chapters c
        JOIN subjects s ON c.subject_id = s.id
        JOIN users u ON s.user_id = u.id
        WHERE u.user_hash = ? AND s.name = ? AND c.name = ?
    """
    cursor.execute(query, (sha1_of_username, subject_name, chapter_name))
    chapter = cursor.fetchone()
    return chapter['id'] if chapter else None



# --- (login_user, signup_user, generate_sha1_hash, change_password) ---
def generate_sha1_hash(input_string):
    sha1_hash = hashlib.sha1()
    sha1_hash.update(input_string.encode('utf-8'))
    return sha1_hash.hexdigest()

def signup_user(username: str, password: str):
    """Creates a new user in the database."""
    user_hash = generate_sha1_hash(username)
    password_hash = generate_sha1_hash(password)
    
    with get_db_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO users (user_hash, password_hash) VALUES (?, ?)",
                (user_hash, password_hash)
            )
            conn.commit()
            return "success"
        except sqlite3.IntegrityError:
            return "exists" # Username already taken

def login_user(username: str, password: str):
    """Logs in a user by checking credentials against the database."""
    user_hash = generate_sha1_hash(username)
    password_hash = generate_sha1_hash(password)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE user_hash = ? AND password_hash = ?",
            (user_hash, password_hash)
        )
        user = cursor.fetchone()
        
        if user:
            # Create user directories upon successful login
            if not os.path.exists(user_hash):
                os.makedirs(user_hash)
                os.makedirs(os.path.join(user_hash, "materials"))
                os.makedirs(os.path.join(user_hash, "data"))
            return True
    return False

def change_password(username: str, oldPassword: str, newPassword: str):
    """Changes a user's password if the old password matches."""
    user_hash = generate_sha1_hash(username)
    old_password_hash = generate_sha1_hash(oldPassword)
    new_password_hash = generate_sha1_hash(newPassword)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Step 1: Verify old password
        cursor.execute(
            "SELECT id FROM users WHERE user_hash = ? AND password_hash = ?",
            (user_hash, old_password_hash)
        )
        user = cursor.fetchone()

        if not user:
            return "invalid"  # username/password combo doesn't match

        # Step 2: Update to new password
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE user_hash = ?",
            (new_password_hash, user_hash)
        )
        conn.commit()
        return "success"


# ... get_subjects, get_chapters, add_subject and add_chapter ...

def get_subjects(sha1_of_username: str):
    """Retrieves a list of subjects for a user from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        user_id = _get_user_id(cursor, sha1_of_username)
        if not user_id:
            return []
            
        cursor.execute("SELECT name FROM subjects WHERE user_id = ?", (user_id,))
        subjects = [row['name'] for row in cursor.fetchall()]
        return subjects

def get_chapters(sha1_of_username: str, subject: str):
    """Retrieves a list of chapters for a given subject from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT c.name FROM chapters c
            JOIN subjects s ON c.subject_id = s.id
            JOIN users u ON s.user_id = u.id
            WHERE u.user_hash = ? AND s.name = ?
        """
        cursor.execute(query, (sha1_of_username, subject))
        chapters = [row['name'] for row in cursor.fetchall()]
        return chapters

def add_subject(sha1_of_username: str, subject: str):
    """Adds a new subject for a user in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        user_id = _get_user_id(cursor, sha1_of_username)
        
        if not user_id:
            return "user_not_found" 

        try:
            cursor.execute(
                "INSERT INTO subjects (user_id, name) VALUES (?, ?)",
                (user_id, subject)
            )
            conn.commit()
            return "success"
        except sqlite3.IntegrityError:
            return "exists"

def add_chapter(sha1_of_username: str, subject: str, chapter: str):
    """Adds a new chapter to a subject for a user in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        user_id = _get_user_id(cursor, sha1_of_username)
        if not user_id:
            return "user_not_found"

        cursor.execute("SELECT id FROM subjects WHERE user_id = ? AND name = ?", (user_id, subject))
        subject_row = cursor.fetchone()
        
        if subject_row:
            subject_id = subject_row['id']
        else:
            cursor.execute("INSERT INTO subjects (user_id, name) VALUES (?, ?)", (user_id, subject))
            subject_id = cursor.lastrowid

        try:
            cursor.execute(
                "INSERT INTO chapters (subject_id, name) VALUES (?, ?)",
                (subject_id, chapter)
            )
            conn.commit()
            return "success"
        except sqlite3.IntegrityError:
            return "exists"

def get_chat_history(sha1_of_username: str):
    """Retrieves the chat history for a user from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        user_id = _get_user_id(cursor, sha1_of_username)
        if not user_id:
            return []
        
        cursor.execute(
            "SELECT role, message, timestamp FROM chat_history WHERE user_id = ? ORDER BY timestamp ASC",
            (user_id,)
        )
        history = [{"role": row['role'], "content": row['message'], "timestamp": row['timestamp']} for row in cursor.fetchall()]
        return history

def add_chat_message(sha1_of_username: str, role: str, message: str):
    """Adds a new chat message to the user's chat history in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        user_id = _get_user_id(cursor, sha1_of_username)
        if not user_id:
            return "user_not_found"
        
        cursor.execute(
            "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
            (user_id, role, message)
        )
        conn.commit()
        return "success"

# --- File Management Functions ---

def upload_material(sha1_of_username: str, subject: str, chapter: str, file):
    sha1 = sha1_of_username
    base_dir = os.path.join(sha1, "materials")
    subject_dir = os.path.join(base_dir, subject)
    chapter_dir = os.path.join(subject_dir, chapter)

    os.makedirs(chapter_dir, exist_ok=True)
    
    try:
        file_path = os.path.join(chapter_dir, file.name)
        if os.path.exists(file_path):
            return "duplicate"

        with open(file_path, "wb") as f:
            f.write(file.read())

        return "success"
    except Exception as e:
        return ("error", str(e))

def get_material(sha1_of_username: str, subject: str, chapter: str):
    materials_dir = os.path.join(sha1_of_username, "materials", subject, chapter)
    if not os.path.exists(materials_dir):
        return []
    else:
        return os.listdir(materials_dir)

def delete_temporary_chat(sha1_of_username: str):
    temp = ["materials", "data"]
    for t in temp:
        dir_path = os.path.join(sha1_of_username, t, "Temporary", "Temporary Chat")
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
            except Exception as e:
                return ("error", str(e))
    return "success"
