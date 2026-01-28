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
    page_title="Solar Power Predictor",
    layout="wide",
    page_icon="🌞"
)
# ===============================
# CUSTOM UI STYLING
# ===============================
st.markdown("""
<style>
body {
    background-color: #f5f7fa;
}
h1, h2, h3 {
    color: #1f4e79;
}
.stButton > button {
    background-color: #1f77b4;
    color: white;
    border-radius: 8px;
    padding: 8px 20px;
    border: none;
    font-weight: bold;
}
.stButton > button:hover {
    background-color: #155a8a;
}
.stTextInput > div > div > input {
    border-radius: 6px;
}
.stMetric {
    background-color: #1e1e1e;
    color: white;
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0px 2px 10px rgba(0,0,0,0.3);
}

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

# Auto redirect after login
if st.session_state.logged_in and st.session_state.page == "Login / Signup":
    st.session_state.page = "Home"

st.markdown("---")
page = st.session_state.page

# ==========================================
# HOME (IMAGE SIZE FIXED HERE)
# ==========================================
if page == "Home":

  st.markdown("<h1 style='text-align:center;'>🌞 Solar Power Prediction System</h1>", unsafe_allow_html=True)
  st.markdown("<p style='text-align:center;'>AI-Based Solar Energy Estimation & Appliance Analysis</p>", unsafe_allow_html=True)

  col1, col2, col3 = st.columns([1, 3, 1])
  with col2:
        st.image(
            "https://images.unsplash.com/photo-1509391366360-2e959784a276",
            width=380
        )

  st.title("🌞 Solar Power Predictor")
  st.write(
    "Smart Solar Power Predictor is a user-friendly web application that predicts "
    "solar power generation using machine learning techniques. The system helps users "
    "understand how much solar energy can be generated under different weather conditions "
    "and whether common household appliances can operate using the available solar energy. "
    "By combining prediction, energy conversion, and appliance feasibility analysis, "
    "the application supports informed decision-making for efficient energy usage."
)


  st.markdown("### 🔑 Key Features")
  f1, f2, f3 = st.columns(3)

  with f1:
        st.markdown("⚡ **ML-based Power Prediction**")
  with f2:
        st.markdown("🌤️ **Weather-based Sunlight Profiles**")
  with f3:
        st.markdown("🏠 **Appliance Feasibility Analysis**")

elif page == "Login / Signup":
    st.title("🔐 Login / Signup")

    tab1, tab2 = st.tabs(["Login", "Signup"])

    # ===================== LOGIN TAB =====================
    with tab1:
        st.subheader("Login")

        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")

        if st.button("Login"):
            if authenticate(login_user, login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.session_state.page = "Home"
                st.success("Logged in successfully")
                st.rerun()
            else:
                st.error("Invalid username or password")

    # ===================== SIGNUP TAB =====================
    with tab2:
        st.subheader("Create New Account")

        new_user = st.text_input("New Username", key="signup_user")
        new_pass = st.text_input("New Password", type="password", key="signup_pass")
        confirm_pass = st.text_input("Confirm Password", type="password", key="signup_confirm")

        if st.button("Create Account"):
            if new_pass != confirm_pass:
                st.error("Passwords do not match")
            else:
                result = create_user(new_user, new_pass)
                if result is True:
                    st.session_state.logged_in = True
                    st.session_state.username = new_user
                    st.session_state.page = "Home"
                    st.success("Account created successfully")
                    st.rerun()
                else:
                    st.error(result)


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
            st.session_state.raw_pred = float(bundle["model"].predict(X)[0])

    raw_pred = st.session_state.raw_pred
    if raw_pred is None:
        raw_pred = st.number_input("Model Output (Dataset Scale)", 0.0, 5000.0, 500.0)

    pred_kw = raw_pred / UNIT_CONVERSION_FACTOR

    st.markdown("### 📊 Prediction Summary")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Original Output", f"{raw_pred:.2f}")
    with c2:
        st.metric("Converted Power (kW)", f"{pred_kw:.2f}")
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
            st.warning("⚠️ Energy is insufficient. Reduce usage hours or appliances.")

        st.caption(
            f"Energy Required: {required_energy:.2f} kWh | "
            f"Available Energy: {usable_energy:.2f} kWh"
        )
# ==========================================
# DASHBOARD
# ==========================================
elif page == "Dashboard":

    st.title("📊 Dashboard")

    if not st.session_state.logged_in:
        st.warning("Please login to view dashboard")
        st.stop()

    # ✅ FIX: Only show metrics if prediction exists
    if st.session_state.raw_pred is not None:

        pred_kw = st.session_state.raw_pred / UNIT_CONVERSION_FACTOR

        st.subheader("📊 Energy Summary")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("⚡ Power Output", f"{st.session_state.raw_pred:.2f} W")

        with col2:
            st.metric("🔌 Converted Power", f"{pred_kw:.2f} kW")

        with col3:
            status = "High" if pred_kw > 2 else "Moderate" if pred_kw > 1 else "Low"
            st.metric("📈 Status", status)

    else:
        st.info("👉 Please go to Predict page and generate prediction first.")



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