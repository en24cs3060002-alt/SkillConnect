# SkillConnect

A student-focused skill discovery, skill exchange and project collaboration platform.

## Technology
- Frontend: HTML, CSS, JavaScript
- Backend: Python Flask
- Database: SQLite
- Version control: Git / GitHub

## Features
- Student registration and login (hashed passwords)
- Profile and college information
- Separate Skills I Know / Skills I Want to Learn lists
- Skill discovery with complementary-skill matching
- Smart Skill Swap requests
- Project creation, discovery and join requests
- Accept / decline collaboration requests
- Basic Skill Reputation feedback (1–5 stars)

## Run locally
1. Install Python 3.10 or newer.
2. Open this folder in VS Code.
3. Create and activate a virtual environment (recommended).
4. Install dependencies:
   `pip install -r requirements.txt`
5. Start the app:
   `python app.py`
6. Open `http://127.0.0.1:5000` in your browser.

The SQLite database (`skillconnect.db`) is created automatically on first run.

## Notes
- This is a mini-project implementation for local demonstration.
- Before public deployment, set a strong `SECRET_KEY`, disable Flask debug mode, add CSRF protection, rate limiting, email verification, and stronger moderation/reporting controls.
- The current skill matching is rule-based, not AI-based. AI matching is listed as future scope in the synopsis.
