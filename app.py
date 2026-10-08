import streamlit as st
import sqlite3
import json
from datetime import datetime
import pandas as pd
import yfinance as yf
from google import genai

st.set_page_config(
    page_title="StockMaster | שוק ההון ומסחר",
    page_icon="📈",
    layout="wide"
)

# --- עיצוב נקי, בהיר ומודרני ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700;800&family=Rubik:wght@500;700;900&display=swap');
    
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-color: #f8fafc !important;
        font-family: 'Assistant', 'Rubik', sans-serif !important;
        direction: rtl;
        text-align: right;
        color: #1e293b !important;
    }

    .top-header-bar {
        display: flex;
        justify-content: flex-start;
        padding: 4px 10px 10px 10px;
    }

    .bsd-badge {
        font-weight: 800;
        font-size: 1.05rem;
        color: #64748b;
        letter-spacing: 1.5px;
    }

    .brand-header {
        background: #ffffff;
        padding: 24px 20px;
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
    }

    .brand-title {
        font-family: 'Rubik', sans-serif;
        font-size: 2.5rem;
        font-weight: 900;
        color: #0f172a;
        margin: 0;
    }

    .brand-title span {
        color: #2563eb;
    }

    .brand-subtitle {
        font-size: 1.1rem;
        color: #475569;
        margin-top: 4px;
        font-weight: 600;
    }

    .card-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #ffffff;
        padding: 6px 10px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }

    .stTabs [data-baseweb="tab"] {
        color: #64748b !important;
        border-radius: 8px;
        padding: 8px 18px;
        font-weight: 700;
    }

    .stTabs [aria-selected="true"] {
        background: #2563eb !important;
        color: #ffffff !important;
    }

    .stButton > button {
        width: 100%;
        background: #2563eb;
        color: #ffffff !important;
        border: none;
        border-radius: 10px;
        padding: 10px 18px;
        font-size: 1rem;
        font-weight: 700;
        transition: 0.2s;
    }

    .stButton > button:hover {
        background: #1d4ed8;
    }

    input, textarea, .stSelectbox {
        direction: rtl !important;
        text-align: right !important;
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="top-header-bar"><span class="bsd-badge">בס״ד</span></div>', unsafe_allow_html=True)

st.markdown("""
<div class="brand-header">
    <div class="brand-title">📈 Stock<span>Master</span></div>
    <div class="brand-subtitle">מנטור AI וסימולטור מסחר מעשי בשוק ההון</div>
</div>
""", unsafe_allow_html=True)

# --- מסד נתונים מקומי לסימולטור ---
DB_FILE = "stocks_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cash REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            symbol TEXT PRIMARY KEY,
            shares REAL,
            avg_price REAL
        )
    """)
    c.execute("SELECT count(*) FROM portfolio")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO portfolio (cash) VALUES (50000.0)")
    conn.commit()
    conn.close()

def get_portfolio():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT cash FROM portfolio LIMIT 1")
    cash = c.fetchone()[0]
    holdings_df = pd.read_sql_query("SELECT symbol as 'סימול', shares as 'כמות מניות', avg_price as 'מחיר קנייה ממוצע ($)' FROM holdings WHERE shares > 0", conn)
    conn.close()
    return cash, holdings_df

def update_trade(symbol, shares, price, action):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT cash FROM portfolio LIMIT 1")
    cash = c.fetchone()[0]
    total_cost = shares * price

    if action == "קנייה":
        if total_cost > cash:
            conn.close()
            return False, "אין מספיק מזומן פנוי בחשבון!"
        new_cash = cash - total_cost
        c.execute("UPDATE portfolio SET cash = ?", (new_cash,))
        c.execute("SELECT shares, avg_price FROM holdings WHERE symbol = ?", (symbol,))
        row = c.fetchone()
        if row:
            curr_shares, curr_avg = row
            new_shares = curr_shares + shares
            new_avg = ((curr_shares * curr_avg) + total_cost) / new_shares
            c.execute("UPDATE holdings SET shares = ?, avg_price = ? WHERE symbol = ?", (new_shares, new_avg, symbol))
        else:
            c.execute("INSERT INTO holdings (symbol, shares, avg_price) VALUES (?, ?, ?)", (symbol, shares, price))
    
    elif action == "מכירה":
        c.execute("SELECT shares FROM holdings WHERE symbol = ?", (symbol,))
        row = c.fetchone()
        if not row or row[0] < shares:
            conn.close()
            return False, "אין לך מספיק מניות למכירה!"
        new_cash = cash + total_cost
        c.execute("UPDATE portfolio SET cash = ?", (new_cash,))
        curr_shares = row[0]
        if curr_shares == shares:
            c.execute("DELETE FROM holdings WHERE symbol = ?", (symbol,))
        else:
            c.execute("UPDATE holdings SET shares = shares - ? WHERE symbol = ?", (shares, symbol))

    conn.commit()
    conn.close()
    return True, "הפעולה בוצעה בהצלחה!"

init_db()

# --- טאבים ראשיים ---
tab_mentor, tab_sim, tab_lessons, tab_quiz = st.tabs([
    "🤖 מנטור שוק ההון (AI)",
    "🎮 סימולטור מסחר ($50,000)",
    "📚 מושגי יסוד ומדריכים",
    "🧠 בחן את עצמך"
])

# --- טאב 1: מנטור AI ---
with tab_mentor:
    st.subheader("שאל את מנטור ה-AI")
    st.caption("שאל כל דבר על השקעות, מניות, איך השוק פועל או מה המשמעות של מושג מסוים:")

    user_query = st.text_input("שאלה לשוק ההון:", placeholder="למשל: מה זה שורט? או איך להבין אם מניה יקרה?")
    
    if st.button("שאל את המנטור", key="ask_mentor_btn"):
        if not user_query.strip():
            st.warning("נא לכתוב שאלה.")
        else:
            api_key = st.secrets.get("GEMINI_API_KEY")
            if not api_key:
                st.error("לא הוגדר מפתח GEMINI_API_KEY בהגדרות Streamlit Secrets.")
            else:
                with st.spinner("מכין תשובה פשוטה וברורה..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        prompt = f"""
                        אתה מנטור מקצועי, חד ובגובה העיניים לשוק ההון והשקעות.
                        ענה בעברית פשוטה וקולעת על השאלה הבאה, בלי שפה מתנשאת ובלי חפירות מיותרות. תן דוגמה ברורה:
                        שאלה: {user_query}
                        """
                        res = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )
                        st.markdown(f"""
                        <div class="card-box" style="border-right: 4px solid #2563eb;">
                            <h4 style="color: #2563eb; margin: 0 0 8px 0;">תשובת המנטור:</h4>
                            <p style="line-height: 1.7; margin: 0;">{res.text}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"שגיאה בתקשורת עם ה-AI: {e}")

# --- טאב 2: סימולטור מסחר ---
with tab_sim:
    st.subheader("סימולטור מסחר בזמן אמת")
    cash, holdings = get_portfolio()

    st.metric("💵 יתרת מזומן פנויה לקנייה", f"${cash:,.2f}")
    
    st.markdown("---")
    st.markdown("#### ביצוע הוראת מסחר")
    
    s_col1, s_col2, s_col3 = st.columns([2, 1, 1])
    with s_col1:
        symbol = st.text_input("סימול מניה בארה\"ב (Ticker):", value="NVDA").upper().strip()
    with s_col2:
        shares_to_trade = st.number_input("כמות מניות:", min_value=1, max_value=10000, value=1, step=1)
    with s_col3:
        trade_action = st.selectbox("סוג פעולה:", ["קנייה", "מכירה"])

    current_price = None
    if symbol:
        try:
            ticker_data = yf.Ticker(symbol)
            fast_info = ticker_data.fast_info
            current_price = round(fast_info.last_price, 2)
            total_val = round(current_price * shares_to_trade, 2)
            st.info(f"מניה: **{symbol}** | מחיר שוק נוכחי: **${current_price}** | סה״כ עסקה: **${total_val:,}**")
        except Exception:
            st.warning("לא נמצא מחיר עבור סימול זה. נסה סימול מוכר כמו AAPL, TSLA, NVDA.")

    if st.button("בצע פעולה", key="trade_exec_btn"):
        if current_price:
            ok, msg = update_trade(symbol, shares_to_trade, current_price, trade_action)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.markdown("---")
    st.markdown("#### מניות מוחזקות בתיק")
    if holdings.empty:
        st.write("התיק ריק כרגע. בצע קנייה ראשונה למעלה.")
    else:
        st.dataframe(holdings, use_container_width=True)

# --- טאב 3: מושגי יסוד ---
with tab_lessons:
    st.subheader("מושגי בסיס שחייבים להכיר")
    
    lessons = [
        ("מה זה בעצם מניה?", "מניה היא חלק בעלות בחברה. אם קנית מניה של אפל, אתה מחזיק חלק קטן מאוד מהחברה ומרוויח מעליית הערך שלה או מדיבידנדים."),
        ("מה ההבדל בין השקעה למסחר?", "משקיע קונה חברות לטווח ארוך (חודשים ושנים) ומאמין בצמיחה שלהן. סוחר מחפש תנודות קצרות של ימים או שעות כדי לעשות רווח מהיר."),
        ("מה זה מדד S&P 500?", "סל שכולל את 500 החברות הגדולות ביותר בארה\"ב. במקום להמר על מניה אחת, משקיעים במדד ומקבלים פיזור על כל הכלכלה האמריקאית."),
        ("מה זה מכפיל רווח (P/E)?", "מדד שמראה כמה השוק מוכן לשלם על כל דולר רווח שהחברה מייצרת. עוזר להבין אם מניה נסחרת במחיר זול או יקר ביחס לרווחיה.")
    ]
    for title, desc in lessons:
        st.markdown(f"""
        <div class="card-box">
            <h4 style="color: #0f172a; margin: 0 0 6px 0;">{title}</h4>
            <p style="color: #475569; margin: 0; line-height: 1.6;">{desc}</p>
        </div>
        """, unsafe_allow_html=True)

# --- טאב 4: חידון ---
with tab_quiz:
    st.subheader("שאלות תרגול מהירות")
    
    q1 = st.radio("1. כשביקוש למניה עולה ויש יותר קונים ממוכרים, מה קורה למחיר?", [
        "המחיר עולה",
        "המחיר יורד",
        "אין שינוי"
    ], key="q1")
    
    q2 = st.radio("2. מה היתרון המרכזי של השקעה במדד כמו S&P 500 לעומת מניה בודדת?", [
        "פיזור סיכונים על פני 500 חברות שונות",
        "אפס סיכון בכלל",
        "רווח מובטח בכל יום"
    ], key="q2")

    if st.button("בדוק תשובות", key="check_quiz"):
        score = 0
        if q1 == "המחיר עולה":
            score += 1
        if q2 == "פיזור סיכונים על פני 500 חברות שונות":
            score += 1
        
        if score == 2:
            st.success("מעולה! שתי התשובות נכונות (2/2).")
        else:
            st.warning(f"תוצאה: {score}/2. נסה שוב או בדוק את טאב המושגים.")
