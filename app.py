# app.py
import streamlit as st
import streamlit.components.v1 as components
import random
import re
import os

st.set_page_config(page_title="Kanji Pronunciation — Automated", layout="centered")

# -------------------------
# Kanji map (kanji -> accepted hiragana readings)
# -------------------------
KANJI_MAP = {
    "人": ["ひと", "じん", "にん"],
    "男": ["おとこ"],
    "女": ["おんな"],
    "子": ["こ", "し"],
    "母": ["はは", "かあ", "おかあさん"],
    "父": ["ちち", "とう", "おとうさん"],
    "友": ["とも"],
    "日": ["ひ", "にち", "じつ"],
    "月": ["つき", "がつ", "げつ"],
    "火": ["ひ", "か"],
    "水": ["みず", "すい"],
    "木": ["き", "もく"],
    "金": ["かね", "きん"],
    "土": ["つち", "ど"],
    "本": ["ほん"],
    "川": ["かわ"],
    "花": ["はな"],
    "気": ["き", "け"],
    "魚": ["さかな", "うお"],
    "天": ["てん"],
    "空": ["そら", "くう"],
    "山": ["やま"],
    "雨": ["あめ", "う"],
    "車": ["くるま", "しゃ"],
    "耳": ["みみ"],
    "手": ["て"],
    "足": ["あし", "そく"],
    "目": ["め", "もく"],
    "口": ["くち", "こう"],
    "名": ["な", "めい"],
}

KANJI_LIST = list(KANJI_MAP.keys())

# -------------------------
# Optional converters (jaconv)
# -------------------------
HAS_JACONV = False
try:
    import jaconv
    HAS_JACONV = True
except Exception:
    HAS_JACONV = False

def normalize_answer(user_input: str) -> str:
    """
    Normalize user input to hiragana:
    - strip whitespace
    - if contains ASCII letters -> attempt romaji -> hiragana conversion (jaconv)
    - convert katakana -> hiragana (jaconv)
    - remove spaces and return
    """
    if not user_input:
        return ""
    s = user_input.strip().lower()

    # If ASCII letters present (likely romaji), try to convert
    if re.search(r"[a-z]", s) and HAS_JACONV:
        try:
            if hasattr(jaconv, "romaji2hiragana"):
                s = jaconv.romaji2hiragana(s)
            elif hasattr(jaconv, "roma2hiragana"):
                s = jaconv.roma2hiragana(s)
        except Exception:
            pass

    # If katakana present convert to hiragana
    if re.search(r"[\u30A0-\u30FF]", s) and HAS_JACONV:
        try:
            s = jaconv.kata2hira(s)
        except Exception:
            pass

    # Remove whitespace
    s = re.sub(r"\s+", "", s)
    return s

def contains_kanji(s: str) -> bool:
    # rough check for CJK Unified Ideographs
    return bool(re.search(r"[\u4e00-\u9fff]", s))

# -------------------------
# Initialize session
# -------------------------
if "current" not in st.session_state:
    st.session_state.current = random.choice(KANJI_LIST)
    st.session_state.history = []
    st.session_state.last_transcript = ""
    st.session_state.user_answer = ""

# -------------------------
# Serve component (path -> folder with index.html)
# -------------------------
component_path = os.path.join(os.path.dirname(__file__), "component", "frontend")
speech_component = components.declare_component("browser_speech_component", path=component_path)

# declare component; returns a function that will render index.html and return posted value
try:
    speech_component = components.declare_component("browser_speech_component", path=component_path)
except Exception as e:
    # Fallback: if declare_component with path not supported on this platform/version
    # We'll fallback to using components.html (non-automated) and warn the user.
    st.error("Automatic component loading failed. Your Streamlit version may not support declare_component(path=...).\n"
             "Please upgrade Streamlit or use the copy-paste fallback app. Error: " + str(e))
    raise

# -------------------------
# UI layout
# -------------------------
st.title("Kanji Pronunciation — Fully Automated (Browser STT)")
st.write("Record in the browser (Chrome/Edge recommended). Click Record → Stop → Send to App. Deploy on Streamlit Cloud (HTTPS).")

col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(f"<div style='text-align:center'><h1 style='font-size:140px'>{st.session_state.current}</h1></div>", unsafe_allow_html=True)
    if st.button("New Kanji"):
        st.session_state.current = random.choice(KANJI_LIST)
        st.session_state.last_transcript = ""
        st.session_state.user_answer = ""

    typed_input = st.text_input("Or type reading (hiragana or romaji) — leave empty if you used Record:" , value=st.session_state.get("user_answer",""))

with col2:
    st.write("Browser Speech (Web Speech API)")
    st.caption("Click Record → speak in Japanese → Stop → Send to App.")

# Render the component and retrieve transcript value (string)
try:
    transcript_val = speech_component(key="browser_speech_component")
except Exception:
    transcript_val = ""

# If not empty string (component posted a value), save it in session_state
if isinstance(transcript_val, str) and transcript_val.strip():
    st.session_state.last_transcript = transcript_val.strip()

display_transcript = st.session_state.get("last_transcript", "")

if display_transcript:
    st.success(f"Transcript (browser): {display_transcript}")
else:
    st.info("No transcript yet. Use Record → Stop → Send to App, or type the reading manually.")

# Decide candidate (prioritize browser transcript)
candidate_raw = display_transcript if display_transcript else typed_input.strip()

# Special handling: if candidate contains kanji characters and matches the current kanji,
# map it to the canonical hiragana reading before comparing.
normalized = ""
if candidate_raw:
    # If candidate exactly equals the current kanji char (or contains it), map it
    if contains_kanji(candidate_raw):
        # Try to find the first kanji in the candidate that matches current card
        for ch in candidate_raw:
            if ch == st.session_state.current:
                # map to the first accepted reading (primary)
                normalized = KANJI_MAP.get(ch, [None])[0] or ""
                break
        # If not the same kanji, try mapping the first kanji to its reading (best-effort)
        if not normalized:
            first_kanji = re.search(r"[\u4e00-\u9fff]", candidate_raw)
            if first_kanji:
                ch = first_kanji.group(0)
                normalized = KANJI_MAP.get(ch, [None])[0] or ""
    else:
        normalized = normalize_answer(candidate_raw)

# Check button
if st.button("Check Answer"):
    st.session_state.user_answer = candidate_raw
    # if we still don't have normalized and the candidate is empty, warn
    if not normalized:
        st.warning("No answer provided. Speak (Record) or type the reading in hiragana/romaji.")
    else:
        correct_list = KANJI_MAP[st.session_state.current]
        if normalized in correct_list:
            st.balloons()
            st.success(f"Correct! ✅ — accepted readings: {', '.join(correct_list)}")
            st.session_state.history.append((st.session_state.current, normalized, True))
        else:
            st.error(f"Incorrect. Your (normalized) answer: {normalized}")
            st.info(f"Common correct readings (hiragana): {', '.join(correct_list)}")
            st.session_state.history.append((st.session_state.current, normalized, False))

# Play correct reading (client-side TTS)
play_col1, play_col2 = st.columns([1, 3])
with play_col1:
    if st.button("Play correct reading"):
        reading_to_play = KANJI_MAP[st.session_state.current][0]
        play_js = f"""
        <script>
          const u = new SpeechSynthesisUtterance("{reading_to_play}");
          u.lang = "ja-JP";
          window.speechSynthesis.speak(u);
        </script>
        """
        components.html(play_js, height=10)

with st.expander("Recent attempts"):
    if st.session_state.history:
        for k, a, ok in reversed(st.session_state.history[-30:]):
            st.write(f"{k} — {a or '(empty)'} — {'✔️' if ok else '❌'}")
    else:
        st.write("No attempts yet.")

if HAS_JACONV:
    st.caption("Romaji->hiragana conversion available via jaconv.")
else:
    st.warning("Romaji->hiragana conversion library (jaconv) not installed. Romaji input won't auto-convert. Install jaconv for romaji support.")

st.caption("Notes: For hosted use deploy on Streamlit Cloud (HTTPS). Use Chrome/Edge for best STT results.")
