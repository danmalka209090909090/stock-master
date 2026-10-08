import streamlit as st
import sqlite3
import json
from datetime import datetime
import pandas as pd
import yfinance as yf
from google import genai

st.set_page_config(
    page_title="StockMaster AI | האקדמיה למסחר ושוק ההון",
    page_icon="📈",
    layout="wide"
)

# --- עיצוב האפליקציה ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700;800&family=Rubik:wght@500;700;900&display=swap');
    
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-color: #0b0f19 !important;
        font-family: 'Assistant', 'Rubik', sans-serif !important;
        direction: rtl;
        text-align: right;
        color: #f1f5f9 !important;
    }

    .top-header-bar {
        display: flex;
        justify-content: flex-start;
        padding: 4px 10px;
    }

    .bsd-badge {
        font-weight: 800;
        font-size: 1.05rem;
        color: #64748b;
        letter-spacing: 1.5px;
    }

    .brand-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 28px 20px;
        border-radius: 18px;
        border: 1px solid #334155;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }

    .brand-title {
        font-family: 'Rubik', sans-serif;
        font-size: 2.8rem;
        font-weight: 900;
        color: #38bdf8;
        margin: 0;
    }

    .brand-title span {
        color: #22c55e;
    }

    .brand-subtitle {
        font-size: 1.2rem;
        color: #94a3b8;
        margin-top: 6px;
        font-weight: 600;
    }

    .card-box {
        background: #131b2e;
        border: 1px solid #1e293b;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 16px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #0f172a;
        padding: 8px;
        border-radius: 14px;
        border: 1px solid #1e293b;
    }

    .stTabs [data-baseweb="tab"] {
        color: #94a3b8 !important;
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 700;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
    }

    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
        color: #ffffff !important;
        border: none;
        border-radius: 10px;
        padding: 12px 20px;
        font-size: 1.05rem;
        font-weight: 800;
        transition: 0.2s;
    }

    input, textarea, .stSelectbox {
        direction: rtl !important;
        text-align: right !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="top-header-bar"><span class="bsd-badge">בס״ד</span></div>', unsafe_allow_html=True)

st.markdown("""
<div class="brand-header">
    <div class="brand-title">📈 Stock<span>Master</span> AI</div>
    <div class="brand-subtitle">פלטפורמת הלימוד, מנטור ה-AI וסימולטור המסחר המעשי בשוק ההון</div>
</div>
""", unsafe_allow_html=True)

# --- שכבת מסד נתונים לסימולטור מסחר (Paper Trading) ---
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
    holdings_df = pd.read_sql_query("SELECT symbol, shares, avg_price FROM holdings WHERE shares > 0", conn)
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
    "🎮 סימולטור מסחר חי ($50,000)",
    "📚 מדריכים ומושגי יסוד",
    "🧠 בחן את עצמך (חידון)"
])

# --- טאב 1: מנטור AI ---
with tab_mentor:
    st.subheader("🤖 מנטור שוק ההון האישי שלך")
    st.caption("שאל כל שאלה על מניות, מושגים בבורסה, אסטרטגיות מסחר או ניתוח חברות:")

    user_query = st.text_input("מה תרצה ללמוד או להבין היום?", placeholder="לדוגמה: מה זה מכפיל רווח (P/E)? או למה מניה יורדת כשיש דוחות טובים?")
    
    if st.button("שאל את המנטור 💡", key="ask_mentor_btn"):
        if not user_query.strip():
            st.warning("נא להזין שאלה.")
        else:
            api_key = st.secrets.get("GEMINI_API_KEY")
            if not api_key:
                st.error("עדיין לא הוגדר מפתח GEMINI_API_KEY בהגדרות Streamlit Secrets.")
            else:
                with st.spinner("המנטור מכין עבורך הסבר פשוט וממוקד..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        prompt = f"""
                        אתה מנטור מקצועי ומעודד ללימוד שוק ההון והשקעות למתחילים ומתקדמים.
                        ענה בעברית ברורה, חדה ובגובה העיניים על השאלה הבאה.
                        אל תסבך סתם עם מילים קשות – תן דוגמה מעשית מהחיים אם זה מתאים:
                        שאלה: {user_query}
                        """
                        res = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )
                        st.markdown(f"""
                        <div class="card-box" style="border: 1px solid #38bdf8;">
                            <h4 style="color: #38bdf8; margin: 0 0 10px 0;">💡 תשובת המנטור:</h4>
                            <p style="line-height: 1.7; font-size: 1.05rem;">{res.text}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"שגיאה בתקשורת עם ה-AI: {e}")

# --- טאב 2: סימולטור מסחר ---
with tab_sim:
    st.subheader("🎮 סימולטור מסחר חי (כסף וירטואלי)")
    cash, holdings = get_portfolio()

    col_c1, col_c2 = st.columns(2)
    col_c1.metric("💵 מזומן פנוי", f"${cash:,.2f}")
    
    st.markdown("---")
    st.markdown("### 🔍 ציטוט מניה וביצוע פעולה")
    
    s_col1, s_col2, s_col3 = st.columns([2, 1, 1])
    with s_col1:
        symbol = st.text_input("סימול מניה (Ticker בארה\"ב):", value="NVDA").upper().strip()
    with s_col2:
        shares_to_trade = st.number_input("כמות מניות:", min_value=1, max_value=10000, value=1, step=1)
    with s_col3:
        trade_action = st.selectbox("פעולה:", ["קנייה", "מכירה"])

    current_price = None
    if symbol:
        try:
            ticker_data = yf.Ticker(symbol)
            fast_info = ticker_data.fast_info
            current_price = round(fast_info.last_price, 2)
            st.info(f"מניה: **{symbol}** | מחיר נוכחי חי: **${current_price}** | סה״כ לפעולה: **${round(current_price * shares_to_trade, 2):,}**")
        except Exception:
            st.warning("לא הצלחנו למשוך מחיר עבור הסימול הזה. ודא שהסימול תקין (למשל: AAPL, TSLA, NVDA).")

    if st.button("בצע הוראה בשוק ⚡", key="trade_exec_btn"):
        if current_price:
            ok, msg = update_trade(symbol, shares_to_trade, current_price, trade_action)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.markdown("---")
    st.markdown("### 📊 התיק האישי שלך")
    if holdings.empty:
        st.info("עדיין אין מניות בתיק. בצע את הקנייה הראשונה שלך למעלה!")
    else:
        st.dataframe(holdings, use_container_width=True)

# --- טאב 3: מדריכים ומושגי יסוד ---
with tab_lessons:
    st.subheader("📚 עקרונות ברזל שכל סוחר ומשקיע חייב לדעת")
    
    lessons = [
        ("מה זה בכלל מניה?", "מניה היא חלק בעלות קטן מתוך חברה. כשאתה קונה מניה של אפל, אתה הופך לבעלים של חלק מזערי מהחברה, ונהנה מהרווחים שלה ומהעלייה בערך שלה."),
        ("מה ההבדל בין מסחר יומי להשקעה לטווח ארוך?", "משקיע קונה חברות טובות ומחזיק בהן שנים (כדי לתת לריבית דריבית לעבוד). סוחר יומי מנסה לנצל תנודות מחיר קצרות של שעות או ימים."),
        ("מה זה מדד S&P 500?", "מדד שמאגד את 500 החברות הגדולות והחזקות ביותר בארה\"ב (אפל, מיקרוסופט, אנבידיה, אמזון וכו'). השקעה במדד נחשבת לאחת הדרכים היציבות לבניית הון לאורך שנים."),
        ("מה זה 'שורט' (Short)?", "הימור על כך שמחיר המניה יירד. הסוחר שואל מניות, מוכר אותן מיד, וכשהמחיר צונח הוא קונה אותן בחזרה בזול ומחזיר אותן – ומשאיר את ההפרש אצלו בכיס.")
    ]
    for title, desc in lessons:
        st.markdown(f"""
        <div class="card-box">
            <h4 style="color: #38bdf8; margin: 0 0 6px 0;">📖 {title}</h4>
            <p style="color: #cbd5e1; margin: 0; line-height: 1.6;">{desc}</p>
        </div>
        """, unsafe_allow_html=True)

# --- טאב 4: חידון שוק ההון ---
with tab_quiz:
    st.subheader("🧠 בחן את הידע שלך בשוק ההון")
    
    q1 = st.radio("1. מה קורה למחיר מניה כשיש יותר קונים ממוכרים?", [
        "המחיר עולה",
        "המחיר יורד",
        "המחיר נשאר קבוע"
    ], key="q1")
    
    q2 = st.radio("2. מה מייצג המדד S&P 500?", [
        "500 המניות הגדולות בארה״ב",
        "מניות טכנולוגיה בלבד",
        "חברות קטנות בתחילת דרכן"
    ], key="q2")

    if st.button("בדוק תשובות 🎯", key="check_quiz"):
        score = 0
        if q1 == "המחיר עולה":
            score += 1
        if q2 == "500 המניות הגדולות בארה״ב":
            score += 1
        
        if score == 2:
            st.success("🏆 מושלם! ענית נכון על כל השאלות (2/2)!")
        else:
            st.warning(f"קיבלת {score}/2. כדאי לעבור שוב על טאב המדריכים!")
