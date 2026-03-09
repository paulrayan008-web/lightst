import os
import base64
import requests
import torch
import torch.nn as nn
from PIL import Image
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from torchvision import transforms
import psycopg2
import psycopg2.extras
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# =============================
# FLASK CONFIG
# =============================

app = Flask(__name__)
app.secret_key = "streetlight_secret_key"

app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

API_KEY = os.environ.get("dbe2bec1-0dbf-11f1-bcb0-0200cd936042")

# =============================
# DATABASE CONNECTION
# =============================

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASS"),
        port=os.environ.get("DB_PORT"),
        sslmode="require"
    )

# =============================
# CNN MODEL
# =============================

device = torch.device("cpu")

class CNN(nn.Module):

    def __init__(self):
        super(CNN, self).__init__()

        self.conv = nn.Sequential(

            nn.Conv2d(3,32,3,padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32,64,3,padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(64,128,3,padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.AdaptiveAvgPool2d((1,1))
        )

        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128,128),
            nn.ReLU(),
            nn.Linear(128,4)
        )

    def forward(self,x):
        x=self.conv(x)
        x=self.fc(x)
        return x


model = CNN().to(device)
model.load_state_dict(torch.load("streetlight_multiclass.pth", map_location=device))
model.eval()

# Prediction transform (NO augmentation)
transform = transforms.Compose([
    transforms.Resize((128,128)),
    transforms.ToTensor(),
    transforms.Normalize(
        [0.485,0.456,0.406],
        [0.229,0.224,0.225]
    )
])

class_names = ["low","Light_of","Light_on","physical"]

# =============================
# ROUTES
# =============================

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


# =============================
# PREDICT ANALYSIS
# =============================

@app.route("/predict_analysis",methods=["GET","POST"])
def predict_analysis():

    if "verified_phone" not in session:
        return redirect("/")

    phone=session["verified_phone"]

    if request.method=="GET":
        return render_template("complaint.html")

    post_id=request.form.get("post_id")

    if not post_id:
        return "<script>alert('Enter Post ID');window.location='/predict_analysis';</script>"

    db=get_db_connection()
    cursor=db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT * FROM post WHERE post_id=%s",(post_id,))
    post_data=cursor.fetchone()

    if not post_data:
        return "<script>alert('Invalid Post ID');window.location='/predict_analysis';</script>"

    area=post_data["area"]
    employee_name=post_data["employee_name"]

    # ================= IMAGE =================

    captured=request.form.get("captured_image")
    file=request.files.get("image")

    if captured:

        img_data=captured.split(",")[1]
        image=Image.open(BytesIO(base64.b64decode(img_data))).convert("RGB")
        filename=post_id+"_camera.png"

    elif file and file.filename!="":

        image=Image.open(file).convert("RGB")
        filename=post_id+"_"+file.filename

    else:
        return "<script>alert('Upload Image');window.location='/predict_analysis';</script>"

    filepath=os.path.join(app.config["UPLOAD_FOLDER"],filename)
    image.save(filepath)

    # ================= CNN PREDICTION =================

    tensor=transform(image).unsqueeze(0).to(device)

    with torch.no_grad():

        output=model(tensor)

        probs=torch.softmax(output,dim=1)

        confidence,pred=torch.max(probs,1)

    fault=class_names[pred.item()]
    confidence_score=round(confidence.item()*100,2)

    # ================= USER INPUT =================

    fault1=request.form.get("fault1")
    fault2=request.form.get("fault2")
    fault3=request.form.get("fault3")
    suggestion=request.form.get("suggestion")

    # ================= INSERT DB =================

    cursor.execute("""
        INSERT INTO complaints
        (phone,post_id,area,employee_name,cnn_result,confidence,
        fault1,fault2,fault3,suggestion,image_path,status)

        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """,(phone,post_id,area,employee_name,fault,confidence_score,
        fault1,fault2,fault3,suggestion,"uploads/"+filename,"Pending"))

    complaint_id=cursor.fetchone()[0]

    db.commit()
    cursor.close()
    db.close()

    return render_template(
        "complaint.html",
        success="Complaint Submitted",
        fault=fault,
        confidence=confidence_score,
        area=area,
        employee_name=employee_name,
        image_path=url_for("static",filename="uploads/"+filename),
        id=complaint_id
    )


# =============================
# USER DASHBOARD
# =============================

@app.route('/user_login',methods=['GET','POST'])
def user_login():

    if request.method=="POST":

        phone=request.form["phone"]

        db=get_db_connection()
        cursor=db.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute("SELECT * FROM complaints WHERE phone=%s",(phone,))
        complaints=cursor.fetchall()

        cursor.close()
        db.close()

        return render_template("user_dashboard1.html",
                               complaints=complaints,
                               phone=phone)

    return render_template("user_dashboard.html")


# =============================
# EMPLOYEE LOGIN
# =============================

@app.route("/employee_login",methods=["GET","POST"])
def employee_login():

    if request.method=="POST":

        email=request.form["email"]
        password=request.form["password"]

        db=get_db_connection()
        cursor=db.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute("SELECT * FROM employees WHERE email=%s AND password=%s",
                       (email,password))

        emp=cursor.fetchone()

        cursor.close()
        db.close()

        if emp:

            session["employee_id"]=emp["id"]
            session["employee_area"]=emp["area"]
            return redirect("/employee_dashboard")

        else:
            flash("Invalid Login")

    return render_template("employeelogin.html")


# =============================
# EMPLOYEE DASHBOARD
# =============================

@app.route("/employee_dashboard")
def employee_dashboard():

    if "employee_id" not in session:
        return redirect("/employee_login")

    db=get_db_connection()
    cursor=db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("""
    SELECT * FROM complaints
    WHERE area=%s AND status!='Resolved'
    """,(session["employee_area"],))

    complaints=cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("dashemp.html",complaints=complaints)


# =============================
# MARK RESOLVED
# =============================

@app.route("/mark_resolved/<int:id>")
def mark_resolved(id):

    db=get_db_connection()
    cursor=db.cursor()

    cursor.execute("UPDATE complaints SET status='Resolved' WHERE id=%s",(id,))
    db.commit()

    cursor.close()
    db.close()

    return redirect("/employee_dashboard")


# =============================
# ADMIN LOGIN
# =============================

@app.route("/admin_login",methods=["GET","POST"])
def admin_login():

    if request.method=="POST":

        if request.form["username"]=="admin" and request.form["password"]=="admin123":
            return redirect("/admin_dashboard")

        flash("Invalid Login")

    return render_template("admin_login.html")


# =============================
# ADMIN DASHBOARD
# =============================

@app.route("/admin_dashboard")
def admin_dashboard():

    db=get_db_connection()
    cursor=db.cursor()

    cursor.execute("SELECT COUNT(*) FROM complaints")
    total=cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
    pending=cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'")
    resolved=cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employees")
    employees=cursor.fetchone()[0]

    cursor.close()
    db.close()

    return render_template("dashboard.html",
                           total_complaints=total,
                           pending_complaints=pending,
                           resolved_complaints=resolved,
                           total_employees=employees)


# =============================
# PDF REPORT
# =============================

@app.route("/generate_report/<int:id>")
def generate_report(id):

    db=get_db_connection()
    cursor=db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT * FROM complaints WHERE id=%s",(id,))
    c=cursor.fetchone()

    cursor.close()
    db.close()

    if not c:
        return "Complaint not found"

    folder=os.path.join(app.root_path,"static","reports")
    os.makedirs(folder,exist_ok=True)

    pdf=os.path.join(folder,f"complaint_{id}.pdf")

    doc=SimpleDocTemplate(pdf)
    styles=getSampleStyleSheet()
    elements=[]

    elements.append(Paragraph("Street Light Complaint Report",styles["Heading1"]))
    elements.append(Spacer(1,20))

    elements.append(Paragraph(f"Complaint ID: {c['id']}",styles["Normal"]))
    elements.append(Paragraph(f"Phone: {c['phone']}",styles["Normal"]))
    elements.append(Paragraph(f"Area: {c['area']}",styles["Normal"]))
    elements.append(Paragraph(f"CNN Result: {c['cnn_result']}",styles["Normal"]))
    elements.append(Paragraph(f"Confidence: {c['confidence']}%",styles["Normal"]))
    elements.append(Paragraph(f"Status: {c['status']}",styles["Normal"]))

    if c["image_path"]:
        img=os.path.join(app.root_path,"static",c["image_path"])
        if os.path.exists(img):
            elements.append(Spacer(1,20))
            elements.append(RLImage(img,width=4*inch,height=3*inch))

    doc.build(elements)

    return send_file(pdf,as_attachment=True)


# =============================
# RUN APP
# =============================

if __name__=="__main__":

    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)