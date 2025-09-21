# AI-Study-Coach

An interactive study assistant built with Python & Streamlit. Helps users learn by chatting with an AI, browsing chapters, saving temporary chats, and more.

---

## 🚀 Features

- User authentication: signup, login, password reset.  
- **Chat with AI** for study help.  
- **Open a chapter**: browse content by structured chapters.  
- **Temporary chat** mode: quick interactive discussions without saving.  
- Persistent session state & navigation.  

---

## 🗂️ Repo Structure

| File | Purpose |
|---|---|
| `app.py` | Main application: Streamlit UI flow, page routing. |
| `frontend.py` | UI components (buttons, layout, sidebar, navigation). |
| `backend.py` | Business logic: database, user authentication, chat handling. |
| `ai_features.py` | AI utilities: calls to AI model or prompt building. |
| `requirements.txt` | Lists Python dependencies. |

---

## ⚙️ Setup & Installation

1. Clone the repo:
  
```
git clone [https://github.com/hamadbijarani/AI-Study-Coach.git](https://github.com/hamadbijarani/AI-Study-Coach.git)
cd AI-Study-Coach
```

2. Create a virtual environment (optional but recommended):  
```bash
python -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
````

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure database and secrets:

   * Make sure `backend.py`’s `DB_FILE` (or whatever DB path you're using) is pointing to a writeable location.
   * If using environment variables (for API keys, etc.), create a `.env` or configure them in your environment.

5. Run the app:

   ```bash
   streamlit run app.py
   ```

---

## 🛠️ Deployment Notes

* **Filesystem permissions**: on hosting platforms (Hugging Face Spaces, Streamlit Cloud, etc.), filesystems are often read-only for certain paths. Ensure your app writes to a safe directory (like `./data/`, `/tmp/`, or a configured persistent storage).
* **Streamlit config directory**: set `STREAMLIT_CONFIG_DIR` to a writable folder to avoid permission errors (e.g. for `.streamlit`).
* **Initialize DB only when needed**: your app’s startup should check if database exists (or tables exist) rather than always writing files to restricted paths.

---

## 👤 Usage

1. Signup or login.
2. Use sidebar to navigate between:
   * Home
   * Temporary Chat
   * Chat with AI
   * Open a Chapter
3. To logout, click the logout button in the sidebar.

---

## ✅ TODO / Future Enhancements

* Improve UI/UX (themes, responsive design).
* More AI features: summarization, statistics, guidance on weak areas, etc.
* Better error handling.
* Tests & CI.

---

## 📄 License

This project is licensed under the MIT License.  


---

## 📫 Contributing

Pull requests are welcome. If you have suggestions or bug fixes, please open an issue first to discuss what you’d like to change.

