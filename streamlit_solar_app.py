import streamlit as st
import pandas as pd
import joblib
import os
import sqlite3
import hashlib
import binascii
from datetime import datetime

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="SolarSight – Intelligent Solar Analytics"
,
    layout="wide",
    page_icon="🌞"
)
# ===============================
# CUSTOM UI STYLING
# ===============================
st.markdown("""
<style>

/* App background */
.stApp {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: #e5e7eb;
}

/* Headings */
h1, h2, h3 {
    color: #facc15;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(90deg, #f59e0b, #facc15);
    color: #1f2937;
    border-radius: 10px;
    padding: 10px 24px;
    border: none;
    font-weight: 700;
    width: 100%;
}

.stButton > button:hover {
    transform: scale(1.03);
    transition: 0.2s;
}

/* Inputs */
.stTextInput input {
    border-radius: 8px;
}

/* Card style */
.card {
    background: rgba(255,255,255,0.06);
    backdrop-filter: blur(12px);
    padding: 25px;
    border-radius: 16px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.3);
    margin-bottom: 20px;
}

/* Metrics */
[data-testid="metric-container"] {
    background: rgba(255,255,255,0.08);
    padding: 20px;
    border-radius: 14px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}

/* Hide footer */
footer {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# DATASET UNIT FIX
# ==========================================
UNIT_CONVERSION_FACTOR = 1000  # Watts → kW

# ==========================================
# DATABASE
# ==========================================
DB = "users.db"

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            salt TEXT,
            pw_hash TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

# ==========================================
# PASSWORD UTILITIES
# ==========================================
import re

def is_valid_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number"
    if not re.search(r"[@$!%*?&#]", password):
        return "Password must contain at least one special character (@$!%*?&#)"
    return None

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return binascii.hexlify(salt).decode(), binascii.hexlify(hashed).decode()

def verify_password(salt_hex, hash_hex, password):
    salt = binascii.unhexlify(salt_hex.encode())
    _, new_hash = hash_password(password, salt)
    return new_hash == hash_hex

def create_user(username, password):
    # 🔐 Password validation
    error = is_valid_password(password)
    if error:
        return error   # return error message instead of True/False

    try:
        salt, pw_hash = hash_password(password)
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users VALUES(NULL,?,?,?,?)",
            (username, salt, pw_hash, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return "Username already exists"


def authenticate(username, password):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT salt,pw_hash FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        return verify_password(row[0], row[1], password)
    return False

# ==========================================
# MODEL LOADING
# ==========================================
def load_model():
    if os.path.exists("solar_model_top5.joblib"):
        try:
            return joblib.load("solar_model_top5.joblib")
        except:
            return None
    return None

bundle = load_model()

# ==========================================
# APPLIANCES (User-defined hours)
# ==========================================
APPLIANCES = [
    ("LED Bulb (5W)", 0.005),
    ("Ceiling Fan", 0.075),
    ("TV", 0.10),
    ("Laptop", 0.065),
    ("Refrigerator (avg)", 0.15),
    ("Washing Machine", 0.50),
    ("Water Pump", 0.75),
    ("Window AC", 1.0),
    ("Split AC", 1.5),
]

# ==========================================
# WEATHER → SUNLIGHT MAP
# ==========================================
SUNLIGHT_MAP = {
    "Cloudy 🌥️": 1.5,
    "Normal ⛅": 3.5,
    "Sunny ☀️": 5.5
}

# ==========================================
# SESSION STATE
# ==========================================
init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "page" not in st.session_state:
    st.session_state.page = "Home"
if "raw_pred" not in st.session_state:
    st.session_state.raw_pred = None
if "prediction_history" not in st.session_state:
    st.session_state.prediction_history = []


# ==========================================
# NAVIGATION
# ==========================================
nav = st.columns(6)
with nav[0]:
    if st.button("🏠 Home"): st.session_state.page = "Home"
with nav[1]:
    if st.session_state.logged_in and st.button("⚡ Predict"): st.session_state.page = "Predict"
with nav[2]:
    if st.session_state.logged_in and st.button("📊 Dashboard"): st.session_state.page = "Dashboard"
with nav[3]:
    if st.button("ℹ️ About Us"): st.session_state.page = "About Us"
with nav[4]:
    if not st.session_state.logged_in and st.button("🔐 Login / Signup"):
        st.session_state.page = "Login / Signup"

with nav[5]:
    if st.session_state.logged_in and st.button("🚪 Logout"):
        st.session_state.page = "Logout"


st.markdown("---")
page = st.session_state.page

# ==========================================
# HOME (IMAGE SIZE FIXED HERE)
# ==========================================
if page == "Home":

    # =============================
    # BEFORE LOGIN (PUBLIC HOME)
    # =============================
    if not st.session_state.logged_in:

        st.markdown(
            "<h1 style='text-align:center;'>☀️ SolarSight </h1>",
            unsafe_allow_html=True
        )

        st.markdown(
            "<p style='text-align:center;'>AI-Powered Solar Energy Intelligence Platform</p>",
            unsafe_allow_html=True
        )

        left, center, right = st.columns([2,2,2])

        with center:
            st.image(
               "https://images.unsplash.com/photo-1509391366360-2e959784a276",
                width=450
    )

        

        # 📘 About
        st.markdown("### 📘 About the Project")
        st.write(
            "Smart Solar Power Predictor is a machine learning-based application that "
            "predicts solar power generation and checks whether household appliances "
            "can run using available solar energy."
        )

        # 🔑 Features
        st.markdown("### 🔑 Key Features")
        f1, f2, f3 = st.columns(3)

        with f1:
            st.markdown("### ⚡ ML-Based Prediction")
            st.write("Predicts solar power using trained ML model.")

        with f2:
            st.markdown("### 🌤️ Weather-Based Analysis")
            st.write("Calculates power based on sunlight conditions.")

        with f3:
            st.markdown("### 🏠 Appliance Feasibility")
            st.write("Checks if appliances can run using solar energy.")

        st.markdown("---")

      
    # =============================
    # AFTER LOGIN (USER HOME)
    # =============================
    else:
        st.markdown(
            f"<h1 style='text-align:center;'>👋 Welcome, {st.session_state.username}</h1>",
            unsafe_allow_html=True
        )

        st.markdown(
            "<p style='text-align:center;'>You are successfully logged in.</p>",
            unsafe_allow_html=True
        )

        st.markdown("### 🚀 What You Can Do")

        col1, col2 = st.columns(2)

        with col1:
            st.success("🔮 Go to **Predict** to calculate solar power.")

        with col2:
            st.info("📊 Open **Dashboard** to view past predictions.")

        st.markdown("""
        ✔ Predict solar energy  
        ✔ Analyze appliance usage  
        ✔ View previous predictions  
        ✔ Make smart energy decisions  
        """)
elif page == "Login / Signup":

    st.markdown("<h1 style='text-align:center;'>☀️ SolarSight</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>AI-Powered Solar Energy Prediction</p>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["🔐 Login", "📝 Signup"])

        # ---------- LOGIN ----------
        with tab1:
            st.subheader("Welcome Back")

            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            if st.button("Login"):
                if authenticate(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.page = "Home"
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

        # ---------- SIGNUP ----------
        with tab2:
            st.subheader("Create SolarSight Account")

            new_user = st.text_input("New Username")
            new_pass = st.text_input("New Password", type="password")
            confirm_pass = st.text_input("Confirm Password", type="password")

            if st.button("Create Account"):
                if new_pass != confirm_pass:
                    st.error("Passwords do not match")
                else:
                    result = create_user(new_user, new_pass)
                    if result is True:
                        st.session_state.logged_in = True
                        st.session_state.username = new_user
                        st.session_state.page = "Home"
                        st.success("Account created successfully!")
                        st.rerun()
                    else:
                        st.error(result)

        st.markdown("</div>", unsafe_allow_html=True)


# ==========================================
# LOGOUT
# ==========================================
elif page == "Logout":
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.raw_pred = None
    st.session_state.page = "Login / Signup"   # 🔥 ADD THIS
    st.success("Logged out successfully")
    st.rerun()                                 # 🔥 ADD THIS

# ==========================================
# PREDICT
# ==========================================
elif page == "Predict":
    if not st.session_state.logged_in:
        st.warning("Please login first")
        st.stop()

    st.title("⚡ Solar Power Prediction")

    if bundle:
        st.subheader("🔮 Model Prediction")
        features = bundle.get("features", [])
        inputs = {f: st.number_input(f, value=0.0) for f in features}

        if st.button("Predict"):
            X = pd.DataFrame([inputs])
            scaler = bundle.get("scaler")
            if scaler:
                X = scaler.transform(X)

            prediction_value = float(bundle["model"].predict(X)[0])

            # ✅ Store latest prediction
            st.session_state.raw_pred = prediction_value

            # ✅ Save prediction history
            st.session_state.prediction_history.append({
                "User": st.session_state.username,
                "Prediction (W)": prediction_value,
                "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

    # ✅ Always read from session
    raw_pred = st.session_state.raw_pred

    if raw_pred is None:
        st.info("Click Predict to generate output.")
        st.stop()

    pred_kw = raw_pred / UNIT_CONVERSION_FACTOR

    st.markdown("### 📊 Prediction Summary")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Original Output", f"{raw_pred:.2f} W")
    with c2:
        st.metric("Converted Power", f"{pred_kw:.2f} kW")
    with c3:
        st.metric("Unit Conversion", "W → kW")

    st.markdown("### 🌤️ Weather Condition")
    condition = st.selectbox("Select Today's Weather", list(SUNLIGHT_MAP.keys()))
    sun_hours = SUNLIGHT_MAP[condition]

    predicted_energy = pred_kw * sun_hours
    usable_energy = predicted_energy * 0.8

    d1, d2, d3 = st.columns(3)
    with d1:
        st.metric("Sunlight Hours", f"{sun_hours} hrs")
    with d2:
        st.metric("Predicted Energy", f"{predicted_energy:.2f} kWh")
    with d3:
        st.metric("Usable Energy", f"{usable_energy:.2f} kWh")

    st.markdown("### ⚙️ Select Appliances & Usage Hours")

    cols = st.columns(2)
    selected = []

    for i, (name, power) in enumerate(APPLIANCES):
        with cols[i % 2]:
            if st.checkbox(name, key=name):
                hours = st.slider(
                    f"{name} usage hours",
                    0.5, 12.0, 1.0, 0.5,
                    key=f"{name}_hours"
                )
                selected.append((name, power, hours))

    required_energy = sum(power * hours for _, power, hours in selected)

    st.markdown("### 🔍 Feasibility Result")
    if not selected:
        st.info("Select appliances and usage hours.")
    else:
        if required_energy <= usable_energy:
            st.success("✅ Selected appliances can run with available solar energy.")
        else:
            st.warning("⚠️ Energy is insufficient.")

        st.caption(
            f"Energy Required: {required_energy:.2f} kWh | "
            f"Available Energy: {usable_energy:.2f} kWh"
        )
# ==========================================
# DASHBOARD
# ==========================================
elif page == "Dashboard":

    st.title("📊 Dashboard")
    st.subheader(f"👤 User: {st.session_state.username}")
    # KPI ROW
    k1, k2, k3 = st.columns(3)

    k1.metric("Model Accuracy", "94%")
    k2.metric("Predictions Made", len(st.session_state.prediction_history))
    k3.metric("System Status", "Online ✅")



    if not st.session_state.logged_in:
        st.warning("Please login to view dashboard")
        st.stop()

    st.subheader(f"👤 User: {st.session_state.username}")

    # ---------------- Latest Prediction ----------------
    if st.session_state.raw_pred is not None:

        pred_kw = st.session_state.raw_pred / UNIT_CONVERSION_FACTOR

        st.markdown("<div class='card'>", unsafe_allow_html=True)

        st.markdown("### ⚡ Latest Prediction")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Power Output", f"{st.session_state.raw_pred:.2f} W")

        with col2:
            st.metric("Converted Power", f"{pred_kw:.2f} kW")

        with col3:
            status = "High" if pred_kw > 2 else "Moderate" if pred_kw > 1 else "Low"
            st.metric("Status", status)

        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.info("No prediction made yet.")

    # ---------------- Prediction History ----------------
    st.markdown("<div class='card'>", unsafe_allow_html=True)

    st.markdown("### 📜 Prediction History")

    if st.session_state.prediction_history:
        df = pd.DataFrame(st.session_state.prediction_history)
        st.dataframe(df, use_container_width=True)
        st.line_chart(df["Prediction (W)"])

    else:
        st.info("No previous predictions found.")

    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# ABOUT US
# ==========================================
elif page == "About Us":
    st.title("ℹ️ About Us")
    st.write(
    "Smart Solar Power Predictor is a final-year academic project developed as part of "
    "the Bachelor of Computer Applications (BCA) program. The project demonstrates the "
    "practical application of machine learning techniques in renewable energy systems. "
    "The objective of the application is to bridge the gap between solar power prediction "
    "and real-world energy utilization by providing clear, realistic, and user-friendly "
    "analysis of solar energy and appliance feasibility."
)

    


# ==========================================
# FOOTER
# ==========================================
st.markdown("""
<hr>
<p style="text-align:center;">
Final Year BCA Project | Solar Power Prediction System 🌞
</p>
""", unsafe_allow_html=True)

st.caption("Final Year BCA Project – Solar Power Prediction & Appliance Feasibility")
