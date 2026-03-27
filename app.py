from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os
from PyPDF2 import PdfReader

app = Flask(__name__)
app.secret_key = "secretkey"

# 📁 Resume Upload Folder
UPLOAD_FOLDER = "static/resumes"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ==============================
# 🔌 DATABASE CONNECTION
# ==============================
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="jobportal"
    )


# ==============================
# 🏠 HOME PAGE + SEARCH
# ==============================
@app.route("/")
def index():
    q = request.args.get("q")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    if q:
        like = f"%{q}%"
        cursor.execute(
            "SELECT * FROM jobs WHERE title LIKE %s OR company LIKE %s OR location LIKE %s",
            (like, like, like),
        )
    else:
        cursor.execute("SELECT * FROM jobs")

    jobs = cursor.fetchall()
    return render_template("index.html", jobs=jobs)


# ==============================
# 📝 REGISTER
# ==============================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor(buffered=True)

        cursor.execute(
            "INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,%s)",
            (
                request.form["name"],
                request.form["email"],
                request.form["password"],
                request.form["role"],
            ),
        )
        db.commit()
        return redirect("/login")

    return render_template("register.html")


# ==============================
# 🔐 LOGIN
# ==============================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor(dictionary=True, buffered=True)

        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (request.form["email"], request.form["password"]),
        )

        user = cursor.fetchone()

        if user:
            session["user"] = user["name"]
            session["role"] = user["role"]
            return redirect("/dashboard")

    return render_template("login.html")


# ==============================
# 🏠 DASHBOARD
# ==============================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    return render_template("dashboard.html")


# ==============================
# 🏢 POST JOB (Recruiter Only)
# ==============================
@app.route("/post-job", methods=["GET", "POST"])
def post_job():
    if "user" not in session or session["role"] != "recruiter":
        return redirect("/login")

    if request.method == "POST":
        db = get_db()
        cursor = db.cursor(buffered=True)

        cursor.execute(
            "INSERT INTO jobs (title,company,location,description) VALUES (%s,%s,%s,%s)",
            (
                request.form["title"],
                request.form["company"],
                request.form["location"],
                request.form["description"],
            ),
        )
        db.commit()
        return redirect("/")

    return render_template("post_job.html")


# ==============================
# 📄 APPLY JOB
# ==============================
@app.route("/apply/<int:job_id>", methods=["GET", "POST"])
def apply(job_id):
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        file = request.files["resume"]
        filename = file.filename

        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        db = get_db()
        cursor = db.cursor(buffered=True)

        cursor.execute(
            "INSERT INTO applications (job_id, applicant_name, resume) VALUES (%s,%s,%s)",
            (job_id, session["user"], filename),
        )
        db.commit()

        return redirect("/")

    return render_template("apply_job.html")


# ==============================
# 📬 VIEW MESSAGES
# ==============================
@app.route("/messages")
def messages():
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute(
        "SELECT * FROM messages WHERE receiver=%s ORDER BY created_at DESC",
        (session["user"],)
    )

    msgs = cursor.fetchall()
    return render_template("messages.html", msgs=msgs)


# ==============================
# ✉️ SEND MESSAGE
# ==============================
@app.route("/send-message", methods=["GET", "POST"])
def send_message():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        db = get_db()
        cursor = db.cursor(buffered=True)

        cursor.execute(
            "INSERT INTO messages (sender, receiver, message) VALUES (%s,%s,%s)",
            (
                session["user"],
                request.form["receiver"],
                request.form["message"]
            ),
        )
        db.commit()

        return redirect("/messages")

    return render_template("send_message.html")


# ==============================
# 🤖 AI RESUME ANALYSIS
# ==============================
def analyze_resume(file_path):

    text = ""
    reader = PdfReader(file_path)

    for page in reader.pages:
        text += page.extract_text() or ""

    text = text.lower()

    skills = [
        "python","java","c++","flask","django","sql",
        "machine learning","ai","data science",
        "react","javascript","html","css"
    ]

    found = [s for s in skills if s in text]
    score = min(len(found) * 10, 100)

    if "machine learning" in text or "ai" in text:
        role = "AI Engineer"
    elif "react" in text or "javascript" in text:
        role = "Frontend Developer"
    elif "sql" in text or "django" in text:
        role = "Backend Developer"
    else:
        role = "Software Engineer"

    return found, score, role


# ==============================
# 👤 PROFILE PAGE
# ==============================
@app.route("/profile", methods=["GET", "POST"])
def profile():

    if "user" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute(
        "SELECT * FROM users WHERE name=%s",
        (session["user"],)
    )

    user = cursor.fetchone()
    analysis = None

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]

        file = request.files.get("resume")

        if file and file.filename != "":
            filename = file.filename
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(path)

            skills, score, role = analyze_resume(path)

            analysis = {
                "skills": skills,
                "score": score,
                "role": role
            }

            cursor.execute(
                "UPDATE users SET name=%s, email=%s, resume=%s WHERE id=%s",
                (name, email, filename, user["id"])
            )

        else:
            cursor.execute(
                "UPDATE users SET name=%s, email=%s WHERE id=%s",
                (name, email, user["id"])
            )

        db.commit()

        cursor.execute(
            "SELECT * FROM users WHERE id=%s",
            (user["id"],)
        )
        user = cursor.fetchone()

    return render_template("profile.html", user=user, analysis=analysis)


# ==============================
# 🚪 LOGOUT
# ==============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ==============================
# ▶️ RUN APP
# ==============================
if __name__ == "__main__":
    app.run(debug=True)