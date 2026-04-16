from flask import Flask, render_template, request, redirect, session, url_for
from dotenv import load_dotenv
import os
import sqlite3
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
app = Flask(__name__)
app.secret_key = "secretkey"

MAX_CREDITS = 24
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn
def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Students
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        branch TEXT,
        semester TEXT
    )
    """)

    # Admins
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    # Courses
    cur.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        code TEXT,
        credits INTEGER,
        instructor TEXT,
        semester TEXT
    )
    """)

    # Add category_id column safely (if not exists)
    try:
        cur.execute("ALTER TABLE courses ADD COLUMN category_id INTEGER")
    except:
        pass
    try:
     cur.execute("ALTER TABLE courses ADD COLUMN capacity INTEGER DEFAULT 30")
    except:
         pass
    # Categories
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    #reservations
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    course_id INTEGER,
    status TEXT DEFAULT 'pending',
    reserved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
    """)

    # Insert default categories safely
    default_categories = ["Core", "Elective", "Lab", "Non-credit"]

    for cat in default_categories:
        try:
            cur.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
        except:
            pass

    conn.commit()
    conn.close()
@app.route("/student_signup", methods=["GET", "POST"])
def student_signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form["email"]
        password = request.form["password"]
        branch = request.form["branch"]
        semester = request.form["semester"]

        conn = get_db()
        conn.execute(
            "INSERT INTO students (name,email,password,branch,semester) VALUES (?,?,?,?,?)",
            (name, email, password, branch, semester)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("student_login"))

    return render_template("studentregister.html")

@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM students WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session["student_id"] = user["id"]
            session["student_name"] = user["name"]
            return redirect(url_for("student_dashboard"))

    return render_template("studentlogin.html")

@app.route("/student_dashboard")
def student_dashboard():

    if "student_id" not in session:
        return redirect(url_for("student_login"))

    student_id = session["student_id"]

    conn = get_db()

    courses = conn.execute("""
    SELECT c.name, c.code, c.credits, r.status
    FROM courses c
    JOIN reservations r
    ON c.id = r.course_id
    WHERE r.student_id = ?
""", (student_id,)).fetchall()

    conn.close()

    return render_template("student_dashboard.html", courses=courses)
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin_signup", methods=["GET", "POST"])
def admin_signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        conn.execute(
            "INSERT INTO admins (name,email,password) VALUES (?,?,?)",
            (name, email, password)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("admin_login"))

    return render_template("adminregister.html")
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        admin = conn.execute(
            "SELECT * FROM admins WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if admin:
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["name"]
            return redirect(url_for("admin_dashboard"))

    return render_template("adminlogin.html")
@app.route("/admin_dashboard")
def admin_dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    total_students = conn.execute(
        "SELECT COUNT(*) as count FROM students"
    ).fetchone()["count"]

    total_courses = conn.execute(
        "SELECT COUNT(*) as count FROM courses"
    ).fetchone()["count"]

    total_reservations = conn.execute(
        "SELECT COUNT(*) as count FROM reservations"
    ).fetchone()["count"]

    # Students per course
    course_stats = conn.execute("""
SELECT c.name,
       COUNT(r.id) as enrolled
FROM courses c
LEFT JOIN reservations r
ON c.id = r.course_id
AND r.status IN ('pending','approved')
""").fetchall()

# Convert rows to normal Python list
    course_data = [
    {"name": row["name"], "enrolled": row["enrolled"]}
    for row in course_stats
]
    pending_reservations = conn.execute("""
    SELECT r.id, s.name as student_name, c.name as course_name
    FROM reservations r
    JOIN students s ON r.student_id = s.id
    JOIN courses c ON r.course_id = c.id
    WHERE r.status = 'pending'
""").fetchall()
    conn.close()

    return render_template(
    "admin_dashboard.html",
    total_students=total_students,
    total_courses=total_courses,
    total_reservations=total_reservations,
    course_data=course_data,
    pending_reservations=pending_reservations)



@app.route("/add_course", methods=["GET", "POST"])
def add_course():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        credits = request.form.get("credits")
        instructor = request.form.get("instructor")
        semester = request.form.get("semester")
        category_id = request.form.get("category_id")
        capacity = request.form.get("capacity")

        cur.execute("""
    INSERT INTO courses
    (name, code, credits, instructor, semester, category_id, capacity)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (name, code, credits, instructor, semester, category_id, capacity))
        

        conn.commit()
        conn.close()

        return redirect(url_for("admin_dashboard"))

    # GET request → fetch categories
    categories = cur.execute("SELECT * FROM categories").fetchall()
    conn.close()

    return render_template("admin_add_course.html", categories=categories)



@app.route("/register_course/<int:course_id>")
def register_course(course_id):

    if "student_id" not in session:
        return redirect(url_for("student_login"))

    student_id = session["student_id"]
    conn = get_db()

    # 1️⃣ Check duplicate registration
    existing = conn.execute(
    """
    SELECT * FROM reservations
    WHERE student_id=? AND course_id=?
    AND status IN ('pending','confirmed')
    """,
    (student_id, course_id)
).fetchone()

    if existing:
        conn.close()
        return "Already registered for this course."

    # 2️⃣ Check capacity
    count = conn.execute(
    """SELECT COUNT(*) as total
       FROM reservations
       WHERE course_id=? AND status IN ('pending','confirmed')
    """,
    (course_id,)
).fetchone()["total"]

    course = conn.execute(
        "SELECT capacity, credits FROM courses WHERE id=?",
        (course_id,)
    ).fetchone()

    if count < course["capacity"]:
     status = "pending"
    else:
     status = "waitlist"

    conn.execute(
    "INSERT INTO reservations (student_id, course_id, status) VALUES (?, ?, ?)",
    (student_id, course_id, status)
)

    conn.commit()
    conn.close()

    return redirect(url_for("student_view_courses"))

@app.route("/edit_course/<int:course_id>", methods=["GET", "POST"])
def edit_course(course_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    if request.method == "POST":
        conn.execute("""
            UPDATE courses
            SET name=?, code=?, credits=?, instructor=?, semester=?
            WHERE id=?
        """, (
            request.form["name"],
            request.form["code"],
            request.form["credits"],
            request.form["instructor"],
            request.form["semester"],
            course_id
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("view_courses"))

    course = conn.execute(
        "SELECT * FROM courses WHERE id=?",
        (course_id,)
    ).fetchone()

    conn.close()

    return render_template("admin_edit_course.html", course=course)
@app.route("/delete_course/<int:course_id>")
def delete_course(course_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()
    conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("view_courses"))
print(app.url_map)
@app.route("/my_courses")
def my_courses():

    if "student_id" not in session:
        return redirect(url_for("student_login"))

    student_id = session["student_id"]

    conn = get_db()

    courses = conn.execute("""
        SELECT courses.name, courses.code, courses.credits
        FROM courses
        JOIN reservations
        ON courses.id = reservations.course_id
        WHERE reservations.student_id = ?
    """, (student_id,)).fetchall()

    conn.close()

    return render_template("student_dashboard.html", courses=courses)
@app.route("/")
def home():
    return render_template("mains.html")
@app.route("/approve/<int:res_id>")
def approve(res_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    conn.execute(
        "UPDATE reservations SET status='approved' WHERE id=?",
        (res_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))



@app.route("/reject/<int:res_id>")
def reject(res_id):

    conn = get_db()

    # 1️⃣ Get course_id of this reservation
    res = conn.execute(
        "SELECT course_id FROM reservations WHERE id=?",
        (id,)
    ).fetchone()

    course_id = res["course_id"]

    # 2️⃣ Reject current reservation
    conn.execute(
        "UPDATE reservations SET status='rejected' WHERE id=?",
        (id,)
    )

    # 3️⃣ Check next waitlisted student
    waitlisted = conn.execute("""
        SELECT id FROM reservations
        WHERE course_id=? AND status='waitlist'
        ORDER BY reserved_at ASC
        LIMIT 1
    """, (course_id,)).fetchone()

    # 4️⃣ Promote to approved
    if waitlisted:
        conn.execute(
            "UPDATE reservations SET status='approved' WHERE id=?",
            (waitlisted["id"],)
        )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_reservations"))
@app.route("/admin/view_courses")
def admin_view_courses():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    courses = conn.execute("""
        SELECT courses.*, categories.name AS category_name
        FROM courses
        LEFT JOIN categories
        ON courses.category_id = categories.id
    """).fetchall()

    conn.close()

    return render_template("admin_view_courses.html", courses=courses)
@app.route("/student/view_courses")
def student_view_courses():

    if "student_id" not in session:
        return redirect(url_for("student_login"))

    conn = get_db()

    courses = conn.execute("""
        SELECT courses.*, categories.name AS category_name
        FROM courses
        LEFT JOIN categories
        ON courses.category_id = categories.id
    """).fetchall()

    conn.close()

    return render_template("student_view_courses.html", courses=courses)
@app.route("/api/courses")
def api_courses():

    conn = get_db()

    courses = conn.execute("""
        SELECT name, code, credits
        FROM courses
    """).fetchall()

    conn.close()

    return {"courses": [dict(row) for row in courses]}
@app.route("/api/reserve", methods=["POST"])
def api_reserve():

    student_id = session["student_id"]
    course_id = request.json["course_id"]

    conn = get_db()

    conn.execute(
        "INSERT INTO reservations(student_id, course_id) VALUES (?,?)",
        (student_id, course_id)
    )

    conn.commit()
    conn.close()

    return {"message": "Course reserved"}

@app.route("/admin/reservations")
def admin_reservations():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    reservations = conn.execute("""
        SELECT r.id, s.name as student_name, c.name as course_name, r.status
        FROM reservations r
        JOIN students s ON r.student_id = s.id
        JOIN courses c ON r.course_id = c.id
    """).fetchall()

    conn.close()

    return render_template("admin_reservations.html", reservations=reservations)
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
