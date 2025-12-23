import streamlit as st
import pandas as pd
import joblib
import os
import sqlite3
import hashlib
import binascii
from datetime import datetime

# ------------------------------------------
# PAGE CONFIG
# ------------------------------------------
st.set_page_config(page_title="Solar Power Predictor", layout="wide")

# ------------------------------------------
# PASSWORD UTILITIES
# ------------------------------------------
def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return binascii.hexlify(salt).decode(), binascii.hexlify(hashed).decode()

def verify_password(salt_hex, hash_hex, password):
    salt = binascii.unhexlify(salt_hex.encode())
    _, new_hash = hash_password(password, salt)
    return new_hash == hash_hex

# ------------------------------------------
# DATABASE
# ------------------------------------------
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

def create_user(username, password):
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
        return False

def authenticate(username, password):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT salt,pw_hash FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        return verify_password(row[0], row[1], password)
    return False

# ------------------------------------------
# MODEL LOADING (OPTIONAL)
# ------------------------------------------
def load_model():
    if os.path.exists("solar_model_top5.joblib"):
        try:
            return joblib.load("solar_model_top5.joblib")
        except:
            return None
    return None

bundle = load_model()

# ------------------------------------------
# APPLIANCE DATA
# ------------------------------------------
APPLIANCES = [
    ("LED Bulb (5W)", 0.005, 5),
    ("Ceiling Fan", 0.075, 8),
    ("TV", 0.10, 3),
    ("Laptop", 0.065, 4),
    ("Refrigerator (avg)", 0.15, 10),
    ("Washing Machine", 0.50, 1),
    ("Water Pump", 0.75, 1),
    ("Window AC", 1.0, 2),
    ("Split AC", 1.5, 2),
]

# ------------------------------------------
# SESSION STATE
# ------------------------------------------
init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "history" not in st.session_state:
    st.session_state.history = []
if "page" not in st.session_state:
    st.session_state.page = "Home"

# ------------------------------------------
# TOP NAVIGATION BAR
# ------------------------------------------
nav = st.columns(6)

with nav[0]:
    if st.button("🏠 Home"):
        st.session_state.page = "Home"

with nav[1]:
    if st.session_state.logged_in and st.button("⚡ Predict"):
        st.session_state.page = "Predict"

with nav[2]:
    if st.session_state.logged_in and st.button("📊 Dashboard"):
        st.session_state.page = "Dashboard"

with nav[3]:
    if st.button("ℹ️ About Us"):
        st.session_state.page = "About Us"

with nav[4]:
    if not st.session_state.logged_in and st.button("🔐 Login / Signup"):
        st.session_state.page = "Login / Signup"

with nav[5]:
    if st.session_state.logged_in and st.button("🚪 Logout"):
        st.session_state.page = "Logout"

st.markdown("---")
page = st.session_state.page

# ------------------------------------------
# HOME
# ------------------------------------------
if page == "Home":
    st.title("🌞 Solar Power Predictor")
    st.write(
        "This final-year project predicts solar power generation and determines "
        "which household appliances can run using **power and energy constraints**."
    )

# ------------------------------------------
# LOGIN / SIGNUP
# ------------------------------------------
elif page == "Login / Signup":
    st.title("Login / Signup")
    tab1, tab2 = st.tabs(["Login", "Signup"])

    with tab1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            if authenticate(u, p):
                st.session_state.logged_in = True
                st.session_state.username = u
                st.success("Logged in successfully")
            else:
                st.error("Invalid credentials")

    with tab2:
        u = st.text_input("New Username")
        p1 = st.text_input("New Password", type="password")
        p2 = st.text_input("Confirm Password", type="password")
        if st.button("Create Account"):
            if p1 != p2:
                st.error("Passwords do not match")
            elif create_user(u, p1):
                st.success("Account created")
            else:
                st.error("Username already exists")

# ------------------------------------------
# LOGOUT
# ------------------------------------------
elif page == "Logout":
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.success("Logged out")

# ------------------------------------------
# PREDICT
# ------------------------------------------
elif page == "Predict":
    if not st.session_state.logged_in:
        st.warning("Please login first")
        st.stop()

    st.title("⚡ Solar Power Prediction")

    pred_kw = None
    source = "Manual"

    # Model prediction (if available)
    if bundle:
        st.subheader("Model Prediction")
        features = bundle.get("features", [])
        inputs = {f: st.number_input(f, value=0.0) for f in features}
        if st.button("Predict using Model"):
            X = pd.DataFrame([inputs])
            scaler = bundle.get("scaler")
            if scaler:
                X = scaler.transform(X)
            pred_kw = float(bundle["model"].predict(X)[0])
            source = "Model"

    # Manual prediction (simulation)
    if pred_kw is None:
        st.subheader("Manual Prediction (Simulation)")
        pred_kw = st.number_input("Predicted Solar Power (kW)", 0.0, 10.0, 1.0)

    st.success(f"Predicted Power: {pred_kw:.2f} kW ({source})")

    st.session_state.history.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "user": st.session_state.username,
        "pred_kw": pred_kw
    })

    # Appliance table
    df = pd.DataFrame(
        [[n, k, h, k * h] for n, k, h in APPLIANCES],
        columns=["Appliance", "Power (kW)", "Hours Used", "Energy Required (kWh)"]
    )

    st.markdown("### 🔋 Appliance Energy Requirement")
    st.dataframe(df, use_container_width=True)

    # Feasibility check
    st.markdown("### 🧠 Appliance Feasibility Check")
    sun_hours = st.slider("Useful sunlight hours", 0.5, 12.0, 4.0, 0.25)
    predicted_kwh = pred_kw * sun_hours

    can_run, cannot_run = [], []

    for _, r in df.iterrows():
        if r["Power (kW)"] <= pred_kw and r["Energy Required (kWh)"] <= predicted_kwh:
            can_run.append([r["Appliance"], r["Power (kW)"], r["Energy Required (kWh)"]])
        else:
            cannot_run.append([r["Appliance"]])

    st.markdown("### 🟢 Can Run")
    st.table(pd.DataFrame(can_run, columns=["Appliance", "Power (kW)", "Energy (kWh)"]))

    st.markdown("### 🔴 Cannot Run")
    st.table(pd.DataFrame(cannot_run, columns=["Appliance"]))

    # AI Recommendation
    st.markdown("### 🤖 AI Appliance Recommendation")
    ai_df = df[
        (df["Power (kW)"] <= pred_kw) &
        (df["Energy Required (kWh)"] <= predicted_kwh)
    ].copy()

    ai_df["AI Score"] = (ai_df["Power (kW)"] * 0.6) + (ai_df["Energy Required (kWh)"] * 0.4)
    ai_df = ai_df.sort_values("AI Score")

    if not ai_df.empty:
        st.table(ai_df[["Appliance", "AI Score"]])
    else:
        st.warning("AI could not recommend any appliance.")

# ------------------------------------------
# DASHBOARD
# ------------------------------------------
elif page == "Dashboard":
    st.title("📊 Dashboard")
    hist = pd.DataFrame(st.session_state.history)
    if hist.empty:
        st.info("No predictions yet")
    else:
        st.dataframe(hist)
        st.line_chart(hist["pred_kw"])

# ------------------------------------------
# ABOUT US
# ------------------------------------------
elif page == "About Us":
    st.title("About Us")
    st.write(
        """
        **Solar Power Predictor** is a final-year academic project that combines
        machine-learning-based solar prediction with intelligent appliance
        feasibility and recommendation logic.
        """
    )

# ------------------------------------------
# FOOTER
# ------------------------------------------
st.markdown("---")
st.caption("Final Year Project – Solar Power Prediction & Intelligent Appliance Recommendation")
