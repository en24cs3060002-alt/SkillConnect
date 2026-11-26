from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
DB = os.path.join(os.path.dirname(__file__), "skillconnect.db")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, college TEXT DEFAULT '',
            bio TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            skill TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('know','learn'))
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL, description TEXT NOT NULL,
            required_skills TEXT NOT NULL, status TEXT DEFAULT 'Open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            receiver_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            message TEXT DEFAULT '', status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER NOT NULL REFERENCES users(id),
            to_user INTEGER NOT NULL REFERENCES users(id),
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
init_db()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    with db() as con:
        projects = con.execute("""SELECT p.*, u.name owner_name FROM projects p
                                  JOIN users u ON u.id=p.owner_id
                                  ORDER BY p.created_at DESC LIMIT 3""").fetchall()
    return render_template("home.html", projects=projects)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name=request.form.get("name","").strip()
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        college=request.form.get("college","").strip()
        if not name or not email or len(password) < 8:
            flash("Enter all required fields. Password must be at least 8 characters.", "danger")
            return render_template("register.html")
        try:
            with db() as con:
                con.execute("INSERT INTO users(name,email,password,college) VALUES(?,?,?,?)",
                            (name,email,generate_password_hash(password),college))
            flash("Account created. You can now sign in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("An account with this email already exists.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        with db() as con:
            user=con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"]=user["id"]
            session["name"]=user["name"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    uid=session["user_id"]
    with db() as con:
        known=con.execute("SELECT COUNT(*) n FROM skills WHERE user_id=? AND kind='know'",(uid,)).fetchone()["n"]
        learning=con.execute("SELECT COUNT(*) n FROM skills WHERE user_id=? AND kind='learn'",(uid,)).fetchone()["n"]
        projects=con.execute("SELECT COUNT(*) n FROM projects WHERE owner_id=?",(uid,)).fetchone()["n"]
        incoming=con.execute("SELECT COUNT(*) n FROM requests WHERE receiver_id=? AND status='Pending'",(uid,)).fetchone()["n"]
        latest=con.execute("""SELECT p.*,u.name owner_name FROM projects p JOIN users u ON u.id=p.owner_id
                              WHERE p.owner_id != ? ORDER BY p.created_at DESC LIMIT 4""",(uid,)).fetchall()
        me=con.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
    return render_template("dashboard.html", known=known, learning=learning, projects=projects,
                           incoming=incoming, latest=latest, me=me)

@app.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    uid=session["user_id"]
    with db() as con:
        if request.method=="POST":
            con.execute("UPDATE users SET name=?,college=?,bio=? WHERE id=?",
                        (request.form.get("name","").strip(),request.form.get("college","").strip(),
                         request.form.get("bio","").strip(),uid))
            session["name"]=request.form.get("name","").strip()
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))
        user=con.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
        known=con.execute("SELECT * FROM skills WHERE user_id=? AND kind='know'",(uid,)).fetchall()
        learn=con.execute("SELECT * FROM skills WHERE user_id=? AND kind='learn'",(uid,)).fetchall()
        avg=con.execute("SELECT AVG(rating) a,COUNT(*) n FROM feedback WHERE to_user=?",(uid,)).fetchone()
    return render_template("profile.html", user=user, known=known, learn=learn, avg=avg)

@app.route("/skills", methods=["GET","POST"])
@login_required
def skills():
    uid=session["user_id"]
    with db() as con:
        if request.method=="POST":
            skill=request.form.get("skill","").strip()
            kind=request.form.get("kind","know")
            if skill and kind in ("know","learn"):
                exists=con.execute("SELECT id FROM skills WHERE user_id=? AND skill=? COLLATE NOCASE AND kind=?",
                                   (uid,skill,kind)).fetchone()
                if not exists:
                    con.execute("INSERT INTO skills(user_id,skill,kind) VALUES(?,?,?)",(uid,skill,kind))
                flash("Skill saved.", "success")
            return redirect(url_for("skills"))
        if request.args.get("delete"):
            con.execute("DELETE FROM skills WHERE id=? AND user_id=?",(request.args["delete"],uid))
            return redirect(url_for("skills"))
        known=con.execute("SELECT * FROM skills WHERE user_id=? AND kind='know' ORDER BY skill",(uid,)).fetchall()
        learn=con.execute("SELECT * FROM skills WHERE user_id=? AND kind='learn' ORDER BY skill",(uid,)).fetchall()
    return render_template("skills.html", known=known, learn=learn)

@app.route("/discover")
@login_required
def discover():
    uid=session["user_id"]
    q=request.args.get("q","").strip()
    with db() as con:
        people=con.execute("""SELECT u.id,u.name,u.college,u.bio,
            GROUP_CONCAT(CASE WHEN s.kind='know' THEN s.skill END) known,
            GROUP_CONCAT(CASE WHEN s.kind='learn' THEN s.skill END) learn
            FROM users u LEFT JOIN skills s ON s.user_id=u.id
            WHERE u.id != ? AND (u.name LIKE ? OR u.college LIKE ? OR s.skill LIKE ?)
            GROUP BY u.id ORDER BY u.name""",(uid,f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
        my_learn=[r["skill"].lower() for r in con.execute("SELECT skill FROM skills WHERE user_id=? AND kind='learn'",(uid,))]
        my_know=[r["skill"].lower() for r in con.execute("SELECT skill FROM skills WHERE user_id=? AND kind='know'",(uid,))]
    matches=[]
    for p in people:
        p=dict(p)
        known=[x.strip() for x in (p["known"] or "").split(",") if x.strip()]
        learn=[x.strip() for x in (p["learn"] or "").split(",") if x.strip()]
        gives=[x for x in known if x.lower() in my_learn]
        receives=[x for x in learn if x.lower() in my_know]
        p["gives"]=gives; p["receives"]=receives
        p["score"]=len(gives)+len(receives)
        matches.append(p)
    matches.sort(key=lambda x:x["score"],reverse=True)
    return render_template("discover.html", people=matches, q=q)

@app.route("/swap/<int:user_id>", methods=["POST"])
@login_required
def swap(user_id):
    if user_id==session["user_id"]:
        return redirect(url_for("discover"))
    with db() as con:
        con.execute("INSERT INTO requests(sender_id,receiver_id,message) VALUES(?,?,?)",
                    (session["user_id"],user_id,request.form.get("message","I'd like to explore a skill swap.")))
    flash("Skill Swap request sent.", "success")
    return redirect(url_for("discover"))

@app.route("/projects")
@login_required
def projects():
    q=request.args.get("q","").strip()
    with db() as con:
        rows=con.execute("""SELECT p.*,u.name owner_name FROM projects p JOIN users u ON u.id=p.owner_id
                            WHERE p.title LIKE ? OR p.required_skills LIKE ? OR p.description LIKE ?
                            ORDER BY p.created_at DESC""",(f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
    return render_template("projects.html", projects=rows, q=q)

@app.route("/projects/new", methods=["GET","POST"])
@login_required
def new_project():
    if request.method=="POST":
        title=request.form.get("title","").strip()
        desc=request.form.get("description","").strip()
        req=request.form.get("required_skills","").strip()
        if title and desc and req:
            with db() as con:
                con.execute("INSERT INTO projects(owner_id,title,description,required_skills) VALUES(?,?,?,?)",
                            (session["user_id"],title,desc,req))
            flash("Project published.", "success")
            return redirect(url_for("projects"))
        flash("Please complete all fields.", "danger")
    return render_template("new_project.html")

@app.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    with db() as con:
        p=con.execute("""SELECT p.*,u.name owner_name FROM projects p JOIN users u ON u.id=p.owner_id
                         WHERE p.id=?""",(project_id,)).fetchone()
        if not p:
            return "Project not found",404
        members=con.execute("""SELECT u.name FROM requests r JOIN users u ON u.id=r.sender_id
                               WHERE r.project_id=? AND r.status='Accepted'""",(project_id,)).fetchall()
    return render_template("project_detail.html", p=p, members=members)

@app.route("/projects/<int:project_id>/join", methods=["POST"])
@login_required
def join_project(project_id):
    with db() as con:
        p=con.execute("SELECT owner_id FROM projects WHERE id=?",(project_id,)).fetchone()
        if not p:
            return "Project not found",404
        if p["owner_id"]==session["user_id"]:
            flash("This is your project.", "warning")
        else:
            exists=con.execute("SELECT id FROM requests WHERE sender_id=? AND project_id=? AND status='Pending'",
                               (session["user_id"],project_id)).fetchone()
            if not exists:
                con.execute("INSERT INTO requests(sender_id,receiver_id,project_id,message) VALUES(?,?,?,?)",
                            (session["user_id"],p["owner_id"],project_id,request.form.get("message","I'd like to join your project.")))
                flash("Join request sent to the project owner.", "success")
    return redirect(url_for("project_detail",project_id=project_id))

@app.route("/requests")
@login_required
def requests_page():
    uid=session["user_id"]
    with db() as con:
        incoming=con.execute("""SELECT r.*,u.name sender_name,p.title project_title FROM requests r
            JOIN users u ON u.id=r.sender_id LEFT JOIN projects p ON p.id=r.project_id
            WHERE r.receiver_id=? ORDER BY r.created_at DESC""",(uid,)).fetchall()
        outgoing=con.execute("""SELECT r.*,u.name receiver_name,p.title project_title FROM requests r
            LEFT JOIN users u ON u.id=r.receiver_id LEFT JOIN projects p ON p.id=r.project_id
            WHERE r.sender_id=? ORDER BY r.created_at DESC""",(uid,)).fetchall()
    return render_template("requests.html", incoming=incoming, outgoing=outgoing)

@app.route("/requests/<int:req_id>/<action>", methods=["POST"])
@login_required
def request_action(req_id,action):
    if action not in ("Accepted","Declined"):
        return "Invalid action",400
    with db() as con:
        con.execute("UPDATE requests SET status=? WHERE id=? AND receiver_id=?",(action,req_id,session["user_id"]))
    flash(f"Request {action.lower()}.", "success")
    return redirect(url_for("requests_page"))

@app.route("/feedback", methods=["GET","POST"])
@login_required
def feedback_page():
    with db() as con:
        if request.method=="POST":
            try:
                target=int(request.form.get("to_user"))
                rating=int(request.form.get("rating"))
                comment=request.form.get("comment","").strip()
                if target != session["user_id"] and 1 <= rating <= 5:
                    con.execute("INSERT INTO feedback(from_user,to_user,rating,comment) VALUES(?,?,?,?)",
                                (session["user_id"],target,rating,comment))
                    flash("Feedback submitted.", "success")
            except (ValueError,TypeError):
                flash("Please select a valid user and rating.", "danger")
            return redirect(url_for("feedback_page"))
        users=con.execute("SELECT id,name FROM users WHERE id != ? ORDER BY name",(session["user_id"],)).fetchall()
        received=con.execute("""SELECT f.*,u.name from_name FROM feedback f JOIN users u ON u.id=f.from_user
                                WHERE f.to_user=? ORDER BY f.created_at DESC""",(session["user_id"],)).fetchall()
    return render_template("feedback.html", users=users, received=received)

if __name__ == "__main__":
    app.run(debug=True)
