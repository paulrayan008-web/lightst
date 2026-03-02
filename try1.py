import os
import re
import pytesseract
import cv2
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for,session,jsonify
import random
import mysql.connector  
import requests
import smtplib
from email.mime.text import MIMEText



pytesseract.pytesseract.tesseract_cmd = r"C:\Users\rayan\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"







app = Flask(__name__)
app.secret_key = "streetlight_secret_key"

API_KEY = "dbe2bec1-0dbf-11f1-bcb0-0200cd936042"
EMAIL_ADDRESS = "paulrayan008@gmail.com"
EMAIL_PASSWORD = "hcen ilaa vaph oohv"   # use Gma

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
def send_otp_email(receiver_email, otp):

    subject = "Your OTP Code"
    body = f"Your OTP is: {otp}"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = receiver_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",   # <-- Put your MySQL password here
        database="streetlight_db"  # <-- Your database name
    )


# ==========================
# HOME PAGE
# ==========================
@app.route('/')
def home():
    return render_template('user_login.html')


# ==========================
# USER LOGIN
# ==========================
@app.route('/user', methods=['GET', 'POST'])
def user():

    phone = session.get('verified_phone')  # show last verified number
    otp_sent = False
    error = None

    if request.method == 'POST':
        action = request.form.get('action')

        # ================= SEND OTP =================
        if action == "send_otp":
            phone = request.form.get('phone')

            if phone and len(phone) == 10 and phone.isdigit():
                url = f"https://2factor.in/API/V1/{API_KEY}/SMS/{phone}/AUTOGEN/SLFD_OTP"
                response = requests.get(url)
                data = response.json()
                print(data)
                if data["Status"] == "Success":
                    session['phone'] = phone
                    session['session_id'] = data["Details"]
                    otp_sent = True
                else:
                    error = "Failed to send OTP"

            else:
                error = "Enter valid 10 digit number"

        # ================= VERIFY OTP =================
        elif action == "verify_otp":

            entered_otp = request.form.get('entered_otp')
            session_id = session.get('session_id')

            if session_id:

                url = f"https://2factor.in/API/V1/{API_KEY}/SMS/VERIFY/{session_id}/{entered_otp}"
                response = requests.get(url)
                data = response.json()

                print(data)

                if data["Status"] == "Success":
                    # Save permanently in session
                    session['verified_phone'] = session.get('phone')
                    return redirect(url_for('complaint'))
                else:
                    otp_sent = True
                    phone = session.get('phone')
                    error = "Invalid OTP"

            else:
                error = "Session expired. Try again."

    return render_template(
        "login.html",
        # phone=phone,
        otp_sent=otp_sent,
        error=error
    )
        
        


# ==========================
# ADMIN LOGIN
# ==========================
@app.route('/admin')
def admin_login():
    return render_template('login.html')   # your admin login file


# ==========================
# ADMIN DASHBOARD
# ==========================
@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('dashboard.html')

@app.route('/admin_complaints')
def admin_complaints():

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )

    cursor = db.cursor(dictionary=True)

    # Fetch using correct column names
    cursor.execute("""
        SELECT id, phone, post_id, area,
               employee_name, fault_type,
               image_path, status
        FROM complaints
        ORDER BY id DESC
    """)

    complaints = cursor.fetchall()

    db.close()

    return render_template(
        "admin-complaints.html",
        complaints=complaints
    )
@app.route('/admin_employees')
def admin_employees():

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()

    db.close()

    return render_template(
        'admin-employees.html',
        employees=employees
    )
# ==========================
# EMPLOYEE LOGIN
# ==========================
@app.route('/employee_login', methods=['GET', 'POST'])
def employee_login():

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM employees
            WHERE email=%s AND password=%s
        """, (email, password))

        employee = cursor.fetchone()
        db.close()

        if employee:
            session['employee_id'] = employee['id']
            session['employee_name'] = employee['name']
            return redirect(url_for('employee_dashboard'))
        else:
            return "Invalid Login"
    return render_template('employeelogin.html')


@app.route('/employee_register', methods=['GET', 'POST'])
def employee_register():

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        area = request.form['area']
        password = request.form['password']

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO employees (name, email, phone, area, password)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, email, phone, area, password))

        db.commit()
        db.close()

        return redirect(url_for('employee_login'))

    return render_template('employeereg.html')

#dashboardemployee
@app.route('/employee_dashboard')
def employee_dashboard():

    if 'employee_area' not in session:
        return redirect('/employee_login')

    area = session['employee_area']

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )
    cursor = db.cursor(dictionary=True)

    # ⭐ Show only complaints of that area
    cursor.execute("""
        SELECT * FROM complaints
        WHERE area=%s AND status!='Completed'
    """, (area,))

    complaints = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("dashemp.html", complaints=complaints)
#empstatus
@app.route('/mark_resolved/<int:complaint_id>', methods=['POST'])
def mark_resolved(complaint_id):

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )
    cursor = db.cursor()

    cursor.execute("""
        UPDATE complaints
        SET status='Resolved'
        WHERE id=%s
    """, (complaint_id,))

    db.commit()
    cursor.close()
    db.close()

    return redirect('/employee_dashboard')
# ==========================
# USER COMPLAINT PAGE
# ==========================
@app.route('/complaint', methods=['GET', 'POST'])
def complaint():

    if request.method == 'POST':

        issue = request.form.get('issue')
        phone = session.get('phone')
        file = request.files.get('image')

        if not file or file.filename == "":
            return "<script>alert('Please upload image');window.location='/complaint';</script>"

        # --------------------------
        # 1️⃣ Save Image
        # --------------------------
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        print("Image saved at:", filepath)

        # --------------------------
        # 2️⃣ Read Image Using OpenCV
        # --------------------------
        img = cv2.imread(filepath)

        if img is None:
            return "<script>alert('Image not readable');window.location='/complaint';</script>"

        # --------------------------
        # 3️⃣ Improve Image Quality
        # --------------------------

        # Resize (very important for handwritten)
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Improve contrast
        gray = cv2.equalizeHist(gray)

        # Adaptive threshold (best for faint writing)
        thresh = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )

        # --------------------------
        # 4️⃣ OCR Configuration
        # --------------------------
        config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        text = pytesseract.image_to_string(thresh, config=config)

        print("Raw OCR Text:", text)

        # --------------------------
        # 5️⃣ Clean OCR Text
        # --------------------------
        clean_text = text.upper()
        clean_text = clean_text.replace(" ", "")
        clean_text = clean_text.replace("-", "")
        clean_text = clean_text.replace("L", "1")  # common OCR mistake

        print("Cleaned Text:", clean_text)

        # --------------------------
        # 6️⃣ Detect PID (Method 1)
        # --------------------------
        match = re.search(r'P[I1]D\d{3,5}', clean_text)

        if match:
            post_id = match.group()
            post_id = post_id.replace("1", "I")  # normalize P1D → PID
        else:
            # --------------------------
            # 7️⃣ Backup: Detect Only Numbers
            # --------------------------
            number_match = re.search(r'\d{3,5}', clean_text)

            if number_match:
                post_id = "PID" + number_match.group()
            else:
                return "<script>alert('Post ID Not Detected');window.location='/complaint';</script>"

        print("Final Detected Post ID:", post_id)

        # --------------------------
        # 8️⃣ Connect Database
        # --------------------------
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="light",
            database="streetlight_db"
        )

        cursor = db.cursor()

        cursor.execute("""
    SELECT area, employee_name
    FROM post
    WHERE TRIM(LOWER(post_id)) = TRIM(LOWER(%s))
""", (post_id,))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            db.close()
            return "<script>alert('Post ID Not Found in Database');window.location='/complaint';</script>"

        area = result[0]
        employee = result[1]

        # --------------------------
        # 9️⃣ Store Relative Image Path
        # --------------------------
        image_path = 'uploads/' + filename

        # --------------------------
        # 🔟 Insert Complaint
        # --------------------------
        cursor.execute("""
            INSERT INTO complaints 
            (phone, post_id, area, employee_name, fault_type, image_path, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (phone, post_id, area, employee, issue, image_path, "Pending"))

        db.commit()
        cursor.close()
        db.close()

        return f"<script>alert('Complaint Registered Successfully! Assigned to {employee}');window.location='/complaint';</script>"

    return render_template("complaint.html")
       
# ================= UPDATE STATUS =================
@app.route('/update_status', methods=['POST'])
def update_status():

    complaint_id = request.form.get('id')
    status = request.form.get('status')

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )
    cursor = db.cursor()

    # 1️⃣ Get area from complaints table
    cursor.execute("SELECT area FROM complaints WHERE id=%s", (complaint_id,))
    result = cursor.fetchone()

    if not result:
        cursor.close()
        db.close()
        return "<script>alert('Complaint Not Found');window.location='/admin_dashboard';</script>"

    area = result[0]

    # 2️⃣ Get employee based on area
    cursor.execute("SELECT name FROM employees WHERE area=%s", (area,))
    emp_result = cursor.fetchone()

    if not emp_result:
        cursor.close()
        db.close()
        return "<script>alert('No Employee Assigned for this Area');window.location='/admin_dashboard';</script>"

    employee_name = emp_result[0]

    # 3️⃣ Update complaints table
    cursor.execute("""
        UPDATE complaints 
        SET employee_name=%s, status=%s
        WHERE id=%s
    """, (employee_name, status, complaint_id))

    db.commit()
    cursor.close()
    db.close()

    return "<script>alert('Updated & Assigned Successfully');window.location='/admin_dashboard';</script>"
# ==========================
# RUN SERVER
# ==========================
if __name__ == '__main__':
    app.run(debug=True)
-----------
import os
import re
import cv2
import torch
import random
import requests
import pytesseract
import mysql.connector
import torch.nn as nn

from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, session,jsonify
from torchvision import transforms

# =============================
# CONFIGURATION
# =============================

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\rayan\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

app = Flask(__name__)
app.secret_key = "streetlight_secret_key"

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 20 MB
API_KEY = "dbe2bec1-0dbf-11f1-bcb0-0200cd936042"
import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )
from werkzeug.exceptions import RequestEntityTooLarge

@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    return """
    <script>
        alert("File Too Large! Please upload image below 5MB.");
        window.history.back();
    </script>
    """, 413

# =============================
# DATABASE CONNECTION
# =============================


# =============================
# CNN MODEL
# =============================

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class CNN(nn.Module):
    def __init__(self):
        super(CNN, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(3, 32, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(64, 128, 3),
            nn.ReLU(),
            nn.MaxPool2d(2)
        )

        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128*14*14, 128),
            nn.ReLU(),
            nn.Linear(128, 2)
        )

    def forward(self, x):
        x = self.conv(x)
        x = self.fc(x)
        return x

model = CNN().to(device)
model.load_state_dict(torch.load("streetlight_cnn.pth", map_location=device))
model.eval()

transform = transforms.Compose([
    transforms.Resize((128,128)),
    transforms.ToTensor()
])

class_names = ["Light_OFF", "Light_ON"]

# =============================
# HOME
# =============================
# ==========================
# HOME PAGE
# ==========================
@app.route('/')
def home():
    return render_template('user_login.html')


# ==========================
# USER LOGIN
# ==========================
@app.route('/user', methods=['GET', 'POST'])
def user():

    phone = session.get('verified_phone')  # show last verified number
    otp_sent = False
    error = None

    if request.method == 'POST':
        action = request.form.get('action')

        # ================= SEND OTP =================
        if action == "send_otp":
            phone = request.form.get('phone')

            if phone and len(phone) == 10 and phone.isdigit():
                url = f"https://2factor.in/API/V1/{API_KEY}/SMS/{phone}/AUTOGEN/SLFD_OTP"
                response = requests.get(url)
                data = response.json()
                print(data)
                if data["Status"] == "Success":
                    session['phone'] = phone
                    session['session_id'] = data["Details"]
                    otp_sent = True
                else:
                    error = "Failed to send OTP"

            else:
                error = "Enter valid 10 digit number"

        # ================= VERIFY OTP =================
        elif action == "verify_otp":

            entered_otp = request.form.get('entered_otp')
            session_id = session.get('session_id')

            if session_id:

                url = f"https://2factor.in/API/V1/{API_KEY}/SMS/VERIFY/{session_id}/{entered_otp}"
                response = requests.get(url)
                data = response.json()

                print(data)

                if data["Status"] == "Success":
                    # Save permanently in session
                    session['verified_phone'] = session.get('phone')
                    return redirect(url_for('predict_analysis'))
                else:
                    otp_sent = True
                    phone = session.get('phone')
                    error = "Invalid OTP"

            else:
                error = "Session expired. Try again."

    return render_template(
        "login.html",
        # phone=phone,
        otp_sent=otp_sent,
        error=error
    )
        
        


# =============================
# COMPLAINT PAGE
# =============================

# =============================
# COMPLAINT PAGE (CNN ONLY)

#PREDICT com2
@app.route('/predict_analysis', methods=['GET', 'POST'])
def predict_analysis():

    if "verified_phone" not in session:
        return redirect("/")

    if request.method == "GET":
        return render_template("complaint.html")

    phone = session.get("verified_phone")
    post_id = request.form.get("post_id")

    if not post_id:
        return "<script>alert('Enter Post ID');window.location='/predict_analysis';</script>"

    # 🔹 Check Post ID
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT area, employee_name FROM post WHERE post_id=%s", (post_id,))
    result = cursor.fetchone()

    if not result:
        db.close()
        return "<script>alert('Post ID Not Found');window.location='/predict_analysis';</script>"

    area, employee_name = result

    # 🔹 Handle Image
    image_file = request.files.get("image")

    if not image_file or image_file.filename == "":
        return "<script>alert('Upload Image');window.location='/predict_analysis';</script>"

    filename = post_id + "_" + image_file.filename
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    image_file.save(filepath)

    # 🔹 CNN Prediction
    image = Image.open(filepath).convert("RGB")
    image = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(image)
        probabilities = torch.softmax(output, dim=1)
        confidence, predicted = torch.max(probabilities, 1)

    fault = class_names[predicted.item()]
    confidence_score = round(confidence.item() * 100, 2)

    db.close()

    # 🔹 Show confirmation page
    return render_template(
        "complaint.html",
        phone=phone,
        post_id=post_id,
        area=area,
        employee_name=employee_name,
        fault=fault,
        confidence=confidence_score,
        image_path=filename
    )
#employee
@app.route('/employee_login', methods=['GET','POST'])
def employee_login():

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM employees
            WHERE email=%s AND password=%s
        """,(email, password))

        employee = cursor.fetchone()
        db.close()

        if employee:
            session["employee_id"] = employee["id"]
            session["employee_name"] = employee["name"]
            session["employee_area"] = employee["area"]
            return redirect(url_for("employee_dashboard"))
        else:
            return "Invalid Login"

    return render_template("employeelogin.html")

@app.route('/employee_register', methods=['GET', 'POST'])
def employee_register():

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        area = request.form['area']
        password = request.form['password']

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO employees (name, email, phone, area, password)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, email, phone, area, password))

        db.commit()
        db.close()

        return redirect(url_for('employee_login'))

    return render_template('employeereg.html')

# =============================
# EMPLOYEE DASHBOARD
# =============================
# =============================
# EMPLOYEE DASHBOARD
# =============================

@app.route('/employee_dashboard')
def employee_dashboard():

    if "employee_id" not in session:
        return redirect("/employee_login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM comp
        WHERE area=%s AND status!='Resolved'
    """,(session["employee_area"],))

    complaints = cursor.fetchall()
    db.close()

    return render_template("dashemp.html", complaints=complaints)

# =============================
# MARK RESOLVED
# =============================

@app.route('/mark_resolved/<int:id>')
def mark_resolved(id):

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("UPDATE complaint SET status='Resolved' WHERE id=%s",(id,))
    db.commit()
    db.close()

    return redirect("/dashemp.html")

# ==========================
# ADMIN LOGIN
# ==========================
@app.route('/admin')
def admin_login():
    return render_template('login.html')   # your admin login file


# ==========================
# ADMIN DASHBOARD
# ==========================
@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('dashboard.html')

@app.route('/admin_complaints')
def admin_complaints():

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )

    cursor = db.cursor(dictionary=True)

    # Fetch using correct column names
    cursor.execute("""
        SELECT id, phone, post_id, area,
               employee_name, fault_type,
               image_path, status
        FROM complaints
        ORDER BY id DESC
    """)

    complaints = cursor.fetchall()

    db.close()

    return render_template(
        "admin-complaints.html",
        complaints=complaints
    )
@app.route('/admin_employees')
def admin_employees():

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()

    db.close()

    return render_template(
        'admin-employees.html',
        employees=employees
    )

# =============================
# RUN
# =============================

if __name__ == "__main__":
    app.run(debug=True)

    -------------
import os
import requests
import torch
import torch.nn as nn
from PIL import Image, ImageEnhance
from flask import Flask, render_template, request, redirect, url_for, session
from torchvision import transforms
from werkzeug.exceptions import RequestEntityTooLarge
import mysql.connector

# =============================
# CONFIGURATION
# =============================

pytesseract_path = r"C:\Users\rayan\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

app = Flask(__name__)
app.secret_key = "streetlight_secret_key"

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB

API_KEY = "dbe2bec1-0dbf-11f1-bcb0-0200cd936042"

# =============================
# DATABASE CONNECTION
# =============================

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )

@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    return """
    <script>
        alert("File Too Large! Please upload image below 20MB.");
        window.history.back();
    </script>
    """, 413

# =============================
# CNN MODEL
# =============================

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class CNN(nn.Module):
    def __init__(self):
        super(CNN, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(3, 32, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(64, 128, 3),
            nn.ReLU(),
            nn.MaxPool2d(2)
        )

        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128*14*14, 128),
            nn.ReLU(),
            nn.Linear(128, 2)
        )

    def forward(self, x):
        x = self.conv(x)
        x = self.fc(x)
        return x

model = CNN().to(device)
model.load_state_dict(torch.load("streetlight_cnn.pth", map_location=device))
model.eval()

transform = transforms.Compose([
    transforms.Resize((128,128)),
    transforms.ToTensor()
])

class_names = ["Light_OFF", "Light_ON"]

# =============================
# ROUTES
# =============================

@app.route('/')
def home():
    return render_template('user_login.html')

# -----------------------------
# USER LOGIN WITH OTP
# -----------------------------
@app.route('/user', methods=['GET', 'POST'])
def user():
    phone = session.get('verified_phone')
    otp_sent = False
    error = None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == "send_otp":
            phone = request.form.get('phone')
            if phone and phone.isdigit() and len(phone) == 10:
                url = f"https://2factor.in/API/V1/{API_KEY}/SMS/{phone}/AUTOGEN/SLFD_OTP"
                response = requests.get(url)
                data = response.json()
                if data["Status"] == "Success":
                    session['phone'] = phone
                    session['session_id'] = data["Details"]
                    otp_sent = True
                else:
                    error = "Failed to send OTP"
            else:
                error = "Enter valid 10 digit number"

        elif action == "verify_otp":
            entered_otp = request.form.get('entered_otp')
            session_id = session.get('session_id')
            if session_id:
                url = f"https://2factor.in/API/V1/{API_KEY}/SMS/VERIFY/{session_id}/{entered_otp}"
                response = requests.get(url)
                data = response.json()
                if data["Status"] == "Success":
                    session['verified_phone'] = session.get('phone')
                    return redirect(url_for('predict_analysis'))
                else:
                    otp_sent = True
                    phone = session.get('phone')
                    error = "Invalid OTP"
            else:
                error = "Session expired. Try again."

    return render_template("login.html", otp_sent=otp_sent, error=error)

# -----------------------------
# PREDICT / COMPLAINT PAGE
# -----------------------------
@app.route('/predict_analysis', methods=['GET', 'POST'])
def predict_analysis():
    if "verified_phone" not in session:
        return redirect("/")

    if request.method == "GET":
        return render_template("complaint.html")

    phone = session.get("verified_phone")
    post_id = request.form.get("post_id")
    if not post_id:
        return "<script>alert('Enter Post ID');window.location='/predict_analysis';</script>"

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT area, employee_name FROM post WHERE post_id=%s", (post_id,))
    result = cursor.fetchone()
    if not result:
        db.close()
        return "<script>alert('Post ID Not Found');window.location='/predict_analysis';</script>"

    area, employee_name = result

    image_file = request.files.get("image")
    if not image_file or image_file.filename == "":
        db.close()
        return "<script>alert('Upload Image');window.location='/predict_analysis';</script>"

    # Save edited image
    filename = post_id + "_" + image_file.filename
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    # Open image and process
    image = Image.open(image_file).convert("RGB")

    # -----------------------------
    # IMAGE EDITING: Crop & Enhance
    # -----------------------------
    width, height = image.size
    crop_percent = 0.8
    new_width = int(width * crop_percent)
    new_height = int(height * crop_percent)
    left = (width - new_width)//2
    top = (height - new_height)//2
    right = left + new_width
    bottom = top + new_height
    image_cropped = image.crop((left, top, right, bottom))

    # Optional brightness enhancement
    enhancer = ImageEnhance.Brightness(image_cropped)
    image_edited = enhancer.enhance(1.2)  # 20% brighter

    # Save edited image
    image_edited.save(filepath)

    # -----------------------------
    # CNN Prediction
    # -----------------------------
    image_tensor = transform(image_edited).unsqueeze(0).to(device)
    with torch.no_grad():
        output = model(image_tensor)
        probabilities = torch.softmax(output, dim=1)
        confidence, predicted = torch.max(probabilities, 1)

    fault = class_names[predicted.item()]
    confidence_score = round(confidence.item() * 100, 2)
    db.close()

    return render_template(
        "complaint.html",
        phone=phone,
        post_id=post_id,
        area=area,
        employee_name=employee_name,
        fault=fault,
        confidence=confidence_score,
        image_path=url_for("static", filename="uploads/"+filename)
    )

# -----------------------------
# EMPLOYEE LOGIN / REGISTER / DASHBOARD
# -----------------------------
@app.route('/employee_login', methods=['GET','POST'])
def employee_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM employees WHERE email=%s AND password=%s",(email,password))
        employee = cursor.fetchone()
        db.close()
        if employee:
            session["employee_id"] = employee["id"]
            session["employee_name"] = employee["name"]
            session["employee_area"] = employee["area"]
            return redirect(url_for("employee_dashboard"))
        else:
            return "Invalid Login"
    return render_template("employeelogin.html")

@app.route('/employee_register', methods=['GET', 'POST'])
def employee_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        area = request.form['area']
        password = request.form['password']
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("INSERT INTO employees (name,email,phone,area,password) VALUES (%s,%s,%s,%s,%s)",
                       (name,email,phone,area,password))
        db.commit()
        db.close()
        return redirect(url_for('employee_login'))
    return render_template('employeereg.html')

@app.route('/employee_dashboard')
def employee_dashboard():
    if "employee_id" not in session:
        return redirect("/employee_login")
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM comp WHERE area=%s AND status!='Resolved'", (session["employee_area"],))
    complaints = cursor.fetchall()
    db.close()
    return render_template("dashemp.html", complaints=complaints)

@app.route('/mark_resolved/<int:id>')
def mark_resolved(id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE complaint SET status='Resolved' WHERE id=%s",(id,))
    db.commit()
    db.close()
    return redirect("/employee_dashboard")

# -----------------------------
# ADMIN LOGIN / DASHBOARD
# -----------------------------
@app.route('/admin')
def admin_login():
    return render_template('login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('dashboard.html')

@app.route('/admin_complaints')
def admin_complaints():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, phone, post_id, area, employee_name, fault_type, image_path, status FROM complaints ORDER BY id DESC")
    complaints = cursor.fetchall()
    db.close()
    return render_template("admin-complaints.html", complaints=complaints)

@app.route('/admin_employees')
def admin_employees():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()
    db.close()
    return render_template('admin-employees.html', employees=employees)

# =============================
# RUN APP
# =============================
if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
    -----------------
    import os
import requests
import torch
import torch.nn as nn
from PIL import Image, ImageEnhance
from flask import Flask, render_template, request, redirect, url_for, session
from torchvision import transforms
from werkzeug.exceptions import RequestEntityTooLarge
import mysql.connector

# =============================
# CONFIGURATION
# =============================

pytesseract_path = r"C:\Users\rayan\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

app = Flask(__name__)
app.secret_key = "streetlight_secret_key"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
 # ✅ Store this in DB

API_KEY = "dbe2bec1-0dbf-11f1-bcb0-0200cd936042"

# =============================
# DATABASE CONNECTION
# =============================

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )

@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    return """
    <script>
        alert("File Too Large! Please upload image below 20MB.");
        window.history.back();
    </script>
    """, 413

# =============================
# CNN MODEL
# =============================

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class CNN(nn.Module):
    def __init__(self):
        super(CNN, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(3, 32, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(64, 128, 3),
            nn.ReLU(),
            nn.MaxPool2d(2)
        )

        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128*14*14, 128),
            nn.ReLU(),
            nn.Linear(128, 2)
        )

    def forward(self, x):
        x = self.conv(x)
        x = self.fc(x)
        return x

model = CNN().to(device)
model.load_state_dict(torch.load("streetlight_cnn.pth", map_location=device))
model.eval()

transform = transforms.Compose([
    transforms.Resize((128,128)),
    transforms.ToTensor()
])

class_names = ["Light_OFF", "Light_ON"]

# =============================
# ROUTES
# =============================

@app.route('/')
def home():
    return render_template('user_login.html')

# -----------------------------
# USER LOGIN WITH OTP
# -----------------------------
@app.route('/user', methods=['GET', 'POST'])
def user():
    phone = session.get('verified_phone')
    otp_sent = False
    error = None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == "send_otp":
            phone = request.form.get('phone')
            if phone and phone.isdigit() and len(phone) == 10:
                url = f"https://2factor.in/API/V1/{API_KEY}/SMS/{phone}/AUTOGEN/SLFD_OTP"
                response = requests.get(url)
                data = response.json()
                if data["Status"] == "Success":
                    session['phone'] = phone
                    session['session_id'] = data["Details"]
                    otp_sent = True
                else:
                    error = "Failed to send OTP"
            else:
                error = "Enter valid 10 digit number"

        elif action == "verify_otp":
            entered_otp = request.form.get('entered_otp')
            session_id = session.get('session_id')
            if session_id:
                url = f"https://2factor.in/API/V1/{API_KEY}/SMS/VERIFY/{session_id}/{entered_otp}"
                response = requests.get(url)
                data = response.json()
                if data["Status"] == "Success":
                    session['verified_phone'] = session.get('phone')
                    return redirect(url_for('predict_analysis'))
                else:
                    otp_sent = True
                    phone = session.get('phone')
                    error = "Invalid OTP"
            else:
                error = "Session expired. Try again."

    return render_template("login.html", otp_sent=otp_sent, error=error)

# -----------------------------
# PREDICT / COMPLAINT PAGE
# -----------------------------
@app.route('/predict_analysis', methods=['GET', 'POST'])
def predict_analysis():

    if "verified_phone" not in session:
        return redirect("/")

    phone = session.get("verified_phone")

    # =========================
    # FIRST: If GET → show page
    # =========================
    if request.method == "GET":
        return render_template("complaint.html")

    # =========================
    # ONLY POST BELOW
    # =========================

    post_id = request.form.get("post_id")

    if not post_id:
        return "<script>alert('Enter Post ID');window.location='/predict_analysis';</script>"

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Fetch post details
    cursor.execute("SELECT * FROM post WHERE post_id=%s", (post_id,))
    post_data = cursor.fetchone()

    if not post_data:
        db.close()
        return "<script>alert('Invalid Post ID');window.location='/predict_analysis';</script>"

    area = post_data["area"]
    employee_name = post_data["employee_name"]

    # ======================================
    # IMAGE HANDLING
    # ======================================
    import base64
    from io import BytesIO

    captured_image = request.form.get("captured_image")
    image_file = request.files.get("image")

    if captured_image and captured_image.strip() != "":
        image_data = captured_image.split(",")[1]
        image = Image.open(BytesIO(base64.b64decode(image_data))).convert("RGB")
        filename = post_id + "_camera.png"

    elif image_file and image_file.filename != "":
        image = Image.open(image_file).convert("RGB")
        filename = post_id + "_" + image_file.filename

    else:
        db.close()
        return "<script>alert('Capture or Upload Image');window.location='/predict_analysis';</script>"

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    image.save(filepath)

    # ======================================
    # CNN PREDICTION
    # ======================================
    image_tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(image_tensor)
        probabilities = torch.softmax(output, dim=1)
        confidence, predicted = torch.max(probabilities, 1)

    fault = class_names[predicted.item()]
    confidence_score = round(confidence.item() * 100, 2)

    # ======================================
    # USER INPUT
    # ======================================
    fault1 = request.form.get("fault1")
    fault2 = request.form.get("fault2")
    fault3 = request.form.get("fault3")
    suggestion = request.form.get("suggestion")

    # ======================================
    # INSERT INTO DATABASE
    # ======================================
    cursor.execute("""
        INSERT INTO complaints
        (phone, post_id, area, employee_name, cnn_result, confidence,
         fault1, fault2, fault3, suggestion, image_path, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        phone, post_id, area, employee_name,
        fault, confidence_score,
        fault1, fault2, fault3,
        suggestion,
        "uploads/" + filename,   # ✅ FIXED IMAGE PATH
        "Pending"
    ))

    db.commit()
    db.close()

    return render_template(
        "complaint.html",
        success="Complaint Submitted Successfully!",
        fault=fault,
        confidence=confidence_score,
        area=area,
        employee_name=employee_name,
        image_path=url_for("static", filename="uploads/" + filename)
    )

# -----------------------------
# EMPLOYEE LOGIN / REGISTER / DASHBOARD
# -----------------------------
@app.route('/employee_login', methods=['GET','POST'])
def employee_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM employees WHERE email=%s AND password=%s",(email,password))
        employee = cursor.fetchone()
        db.close()
        if employee:
            session["employee_id"] = employee["id"]
            session["employee_name"] = employee["name"]
            session["employee_area"] = employee["area"]
            return redirect(url_for("employee_dashboard"))
        else:
            return "Invalid Login"
    return render_template("employeelogin.html")

@app.route('/employee_register', methods=['GET', 'POST'])
def employee_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        area = request.form['area']
        password = request.form['password']
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("INSERT INTO employees (name,email,phone,area,password) VALUES (%s,%s,%s,%s,%s)",
                       (name,email,phone,area,password))
        db.commit()
        db.close()
        return redirect(url_for('employee_login'))
    return render_template('employeereg.html')

@app.route('/employee_dashboard')
def employee_dashboard():
    if "employee_id" not in session:
        return redirect("/employee_login")
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM comp WHERE area=%s AND status!='Resolved'", (session["employee_area"],))
    complaints = cursor.fetchall()
    db.close()
    return render_template("dashemp.html", complaints=complaints)

@app.route('/mark_resolved/<int:id>')
def mark_resolved(id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE complaint SET status='Resolved' WHERE id=%s",(id,))
    db.commit()
    db.close()
    return redirect("/employee_dashboard")

# -----------------------------
# ADMIN LOGIN / DASHBOARD
# -----------------------------
@app.route('/admin')
def admin_login():
    return render_template('adminlogin.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('dashboard.html')

#admin complaints 
@app.route('/admin_complaints')
def admin_complaints():

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM complaints")
    complaints = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("admin-complaints.html", complaints=complaints)
#updte
@app.route('/update_complaint/<int:id>', methods=['POST'])
def update_complaint(id):
    employee_name = request.form['employee_name']
    status = request.form['status']

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )
    cursor = db.cursor()

    cursor.execute("""
        UPDATE complaints 
        SET employee_name=%s, status=%s 
        WHERE id=%s
    """, (employee_name, status, id))

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for('admin_complaints'))
#delete
@app.route('/delete_complaint/<int:id>')
def delete_complaint(id):

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )
    cursor = db.cursor()

    cursor.execute("DELETE FROM complaints WHERE id=%s", (id,))
    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for('admin_complaints'))
@app.route('/admin_employees')
def admin_employees():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()
    db.close()
    return render_template('admin-employees.html', employees=employees)

# =============================
# RUN APP
# =============================
if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
    --------
    import os
import requests
import torch
import torch.nn as nn
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, session
from torchvision import transforms
import mysql.connector
import base64
from io import BytesIO

# =============================
# CONFIGURATION
# =============================

pytesseract_path = r"C:\Users\rayan\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

app = Flask(__name__)
app.secret_key = "streetlight_secret_key"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB ALLOWED

API_KEY = "dbe2bec1-0dbf-11f1-bcb0-0200cd936042"

# =============================
# DATABASE CONNECTION
# =============================

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="light",
        database="streetlight_db"
    )

# =============================
# CNN MODEL
# =============================

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class CNN(nn.Module):
    def __init__(self):
        super(CNN, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(3, 32, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(64, 128, 3),
            nn.ReLU(),
            nn.MaxPool2d(2)
        )

        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128*14*14, 128),
            nn.ReLU(),
            nn.Linear(128, 2)
        )

    def forward(self, x):
        x = self.conv(x)
        x = self.fc(x)
        return x

model = CNN().to(device)
model.load_state_dict(torch.load("streetlight_cnn.pth", map_location=device))
model.eval()

transform = transforms.Compose([
    transforms.Resize((128,128)),
    transforms.ToTensor()
])

class_names = ["Light_OFF", "Light_ON"]

# =============================
# HOME
# =============================

@app.route('/')
def home():
    return render_template('user_login.html')

# =============================
# USER LOGIN WITH OTP
# =============================

@app.route('/user', methods=['GET', 'POST'])
def user():
    otp_sent = False
    error = None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == "send_otp":
            phone = request.form.get('phone')

            if phone and phone.isdigit() and len(phone) == 10:
                url = f"https://2factor.in/API/V1/{API_KEY}/SMS/{phone}/AUTOGEN/SLFD_OTP"
                response = requests.get(url)
                data = response.json()

                if data["Status"] == "Success":
                    session['phone'] = phone
                    session['session_id'] = data["Details"]
                    otp_sent = True
                else:
                    error = "Failed to send OTP"
            else:
                error = "Enter valid 10 digit number"

        elif action == "verify_otp":
            entered_otp = request.form.get('entered_otp')
            session_id = session.get('session_id')

            if session_id:
                url = f"https://2factor.in/API/V1/{API_KEY}/SMS/VERIFY/{session_id}/{entered_otp}"
                response = requests.get(url)
                data = response.json()

                if data["Status"] == "Success":
                    session['verified_phone'] = session.get('phone')
                    return redirect(url_for('predict_analysis'))
                else:
                    otp_sent = True
                    error = "Invalid OTP"
            else:
                error = "Session expired. Try again."

    return render_template("login.html", otp_sent=otp_sent, error=error)

# =============================
# PREDICT / COMPLAINT PAGE
# =============================

@app.route('/predict_analysis', methods=['GET', 'POST'])
def predict_analysis():

    if "verified_phone" not in session:
        return redirect("/")

    phone = session.get("verified_phone")

    if request.method == "GET":
        return render_template("complaint.html")

    post_id = request.form.get("post_id")

    if not post_id:
        return "<script>alert('Enter Post ID');window.location='/predict_analysis';</script>"

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM post WHERE post_id=%s", (post_id,))
    post_data = cursor.fetchone()

    if not post_data:
        db.close()
        return "<script>alert('Invalid Post ID');window.location='/predict_analysis';</script>"

    area = post_data["area"]
    employee_name = post_data["employee_name"]

    # =============================
    # IMAGE HANDLING (LARGE SAFE)
    # =============================

    captured_image = request.form.get("captured_image")
    image_file = request.files.get("image")

    if captured_image:
        image_data = captured_image.split(",")[1]
        image = Image.open(BytesIO(base64.b64decode(image_data))).convert("RGB")
        filename = post_id + "_camera.jpg"

    elif image_file and image_file.filename != "":
        image = Image.open(image_file).convert("RGB")
        filename = post_id + "_" + image_file.filename

    else:
        db.close()
        return "<script>alert('Capture or Upload Image');window.location='/predict_analysis';</script>"

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    # AUTO RESIZE LARGE IMAGE
    max_size = (1200, 1200)
    image.thumbnail(max_size, Image.LANCZOS)

    image.save(filepath, optimize=True, quality=85)

    # =============================
    # CNN PREDICTION
    # =============================

    image_tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(image_tensor)
        probabilities = torch.softmax(output, dim=1)
        confidence, predicted = torch.max(probabilities, 1)

    fault = class_names[predicted.item()]
    confidence_score = round(confidence.item() * 100, 2)

    fault1 = request.form.get("fault1")
    fault2 = request.form.get("fault2")
    fault3 = request.form.get("fault3")
    suggestion = request.form.get("suggestion")

    cursor.execute("""
        INSERT INTO complaints
        (phone, post_id, area, employee_name, cnn_result, confidence,
         fault1, fault2, fault3, suggestion, image_path, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        phone, post_id, area, employee_name,
        fault, confidence_score,
        fault1, fault2, fault3,
        suggestion,
        "uploads/" + filename,
        "Pending"
    ))

    db.commit()
    db.close()

    return render_template(
        "complaint.html",
        success="Complaint Submitted Successfully!",
        fault=fault,
        confidence=confidence_score,
        area=area,
        employee_name=employee_name,
        image_path=url_for("static", filename="uploads/" + filename)
    )

# =============================
# EMPLOYEE DASHBOARD FIXED
# =============================

@app.route('/employee_dashboard')
def employee_dashboard():
    if "employee_id" not in session:
        return redirect("/employee_login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM complaints WHERE area=%s AND status!='Resolved'",
        (session["employee_area"],)
    )

    complaints = cursor.fetchall()
    db.close()

    return render_template("dashemp.html", complaints=complaints)

@app.route('/mark_resolved/<int:id>')
def mark_resolved(id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE complaints SET status='Resolved' WHERE id=%s",(id,))
    db.commit()
    db.close()
    return redirect("/employee_dashboard")

# =============================
# RUN
# =============================

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)