# app.py
import streamlit as st
import streamlit.components.v1 as components
import random
import re
import os
import sys
import platform

st.set_page_config(page_title="Kanji Pronunciation — Automated (robust)", layout="centered")

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
    if not user_input:
        return ""
    s = user_input.strip().lower()
    # romaji -> hiragana (jaconv)
    if re.search(r"[a-z]", s) and HAS_JACONV:
        try:
            if hasattr(jaconv, "romaji2hiragana"):
                s = jaconv.romaji2hiragana(s)
            elif hasattr(jaconv, "roma2hiragana"):
                s = jaconv.roma2hiragana(s)
        except Exception:
            pass
    # katakana -> hiragana
    if re.search(r"[\u30A0-\u30FF]", s) and HAS_JACONV:
        try:
            s = jaconv.kata2hira(s)
        except Exception:
            pass
    s = re.sub(r"\s+", "", s)
    return s

def contains_kanji(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s))

# -------------------------
# Session init
# -------------------------
if "current" not in st.session_state:
    st.session_state.current = random.choice(KANJI_LIST)
    st.session_state.history = []
    st.session_state.last_transcript = ""
    st.session_state.user_answer = ""

# -------------------------
# Component path (expected)
# -------------------------
component_path = os.path.join(os.path.dirname(__file__), "component", "frontend")
index_html_path = os.path.join(component_path, "index.html")

# Helpful diagnostics (shown only when fallback triggers)
def show_diagnostics():
    st.warning("Your app is having trouble loading the automatic browser speech component. The app will fall back to the copy-paste recorder below so you can continue testing.")
    st.markdown("**Diagnostics:**")
    st.write(f"- Streamlit version: `{st.__version__}`")
    st.write(f"- Python: `{platform.python_version()}` ({platform.system()} {platform.release()})")
    st.write(f"- App file: `{os.path.abspath(__file__)}`")
    st.write(f"- Expected component folder: `{component_path}`")
    st.write(f"- Expected index.html: `{index_html_path}`")
    exists = os.path.exists(index_html_path)
    st.write(f"- `index.html` exists: **{exists}**")
    if os.path.isdir(component_path):
        try:
            files = os.listdir(component_path)
            st.write(f"- Files in component frontend: {files}")
        except Exception as e:
            st.write(f"- Could not list folder: {e}")
    else:
        st.write("- component frontend folder does not exist.")
    st.info("Check your browser Developer Tools Console (Right-click → Inspect → Console) for errors such as blocked iframe, mixed-content, or CSP errors. Also check the terminal where you ran `streamlit run app.py` for error traces.")

# -------------------------
# Try to load automatic declared component
# -------------------------
auto_component_available = False
speech_component = None
try:
    # declare_component with path -> serves component/frontend/index.html
    speech_component = components.declare_component("browser_speech_component", path=component_path)
    auto_component_available = True
except Exception as e:
    auto_component_available = False
    # we will fall back and show diagnostics
    st.info("Note: declare_component(path=...) raised an exception (see diagnostics below). Falling back.")
    show_diagnostics()

# -------------------------
# App UI (common)
# -------------------------
st.title("Kanji Pronunciation — Robust Automated + Fallback")
st.write("Record via the browser if available (Chrome/Edge recommended). If automatic component fails to load, the app will show a reliable copy-paste recorder automatically so you can continue.")

col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(f"<div style='text-align:center'><h1 style='font-size:140px'>{st.session_state.current}</h1></div>", unsafe_allow_html=True)
    if st.button("New Kanji"):
        st.session_state.current = random.choice(KANJI_LIST)
        st.session_state.last_transcript = ""
        st.session_state.user_answer = ""

    typed_input = st.text_input("Or type reading (hiragana or romaji) — leave empty if you used Record:", value=st.session_state.get("user_answer", ""))

with col2:
    st.write("Browser Speech (Web Speech API)")
    st.caption("If automatic component loads you'll see Record → Stop → Send to App. Otherwise the app will show the copy/paste recorder.")

# -------------------------
# Branch: automated component OR fallback copy-paste recorder
# -------------------------
transcript_str = ""

if auto_component_available:
    # try to render the component and get a result
    try:
        transcript_val = speech_component(key="browser_speech_component")
        # If speech_component returns an empty DeltaGenerator or something else, guard
        if isinstance(transcript_val, str) and transcript_val.strip():
            transcript_str = transcript_val.strip()
            st.session_state.last_transcript = transcript_str
        else:
            # If the component returned nothing (empty string), show info and fallback
            # (some Streamlit versions may not wire component assets correctly)
            # We detect that the HTML didn't render by checking for index.html existence; if missing, show diagnostics
            if not os.path.exists(index_html_path):
                show_diagnostics()
            else:
                # index.html exists but component returned no value yet -> show a short hint
                st.info("Automatic component loaded but no transcript received yet. Try clicking Record → speak → Stop → Send to App.")
    except Exception as e:
        # any exception means the component failed at runtime — show diagnostics and fallback
        st.error("Automatic browser component failed at runtime; falling back to copy-paste recorder.")
        st.write(f"Component error: {e}")
        show_diagnostics()
        auto_component_available = False

# If automatic component not available, render copy/paste recorder HTML (robust fallback)
if not auto_component_available:
    # copy/paste recorder HTML (same as earlier simple fallback)
    fallback_html = """
    <!doctype html>
    <html>
    <head><meta charset="utf-8" /><style>
    body{font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial;margin:0;padding:8px}
    .controls{display:flex;gap:6px;align-items:center}
    button{padding:6px 10px;font-size:14px}
    #status{margin-top:8px;color:#444;font-size:13px}
    #transcript{margin-top:8px;font-size:16px;min-height:28px;white-space:pre-wrap}
    .note{margin-top:6px;color:#666;font-size:12px}
    </style></head>
    <body>
      <div class="controls">
        <button id="startBtn">Record (Browser)</button>
        <button id="stopBtn" disabled>Stop</button>
        <button id="copyBtn" disabled>Send to Clipboard</button>
      </div>
      <div id="status">Status: idle</div>
      <div id="transcript" aria-live="polite"></div>
      <div class="note">After clicking <b>Send to Clipboard</b>, paste into the Streamlit "Paste transcript here" input (Ctrl/Cmd+V).</div>
      <script>
        const compatible = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
        const status = document.getElementById('status');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const copyBtn = document.getElementById('copyBtn');
        const transcriptDiv = document.getElementById('transcript');
        if(!compatible){
          status.innerText = "Status: Web Speech API not supported in this browser. Use Chrome/Edge on HTTPS.";
          startBtn.disabled = true;
        }
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = compatible ? new SpeechRecognition() : null;
        if(recognition){ recognition.lang='ja-JP'; recognition.interimResults=true; recognition.continuous=false; }
        let fullTranscript = "";
        startBtn.onclick = () => { if(!recognition) return; fullTranscript=""; transcriptDiv.innerText=""; status.innerText="Status: listening... (speak now)"; recognition.start(); startBtn.disabled=true; stopBtn.disabled=false; copyBtn.disabled=true; };
        stopBtn.onclick = () => { if(!recognition) return; recognition.stop(); status.innerText="Status: stopped — processing..."; stopBtn.disabled=true; };
        recognition && recognition.addEventListener('result', (e)=>{ let interim=''; for(let i=e.resultIndex;i<e.results.length;i++){ const t=e.results[i][0].transcript; if(e.results[i].isFinal){ fullTranscript += t; } else { interim += t; } } transcriptDiv.innerText = fullTranscript + interim; });
        recognition && recognition.addEventListener('end', ()=>{ status.innerText="Status: ready (recording ended)"; copyBtn.disabled=false; startBtn.disabled=false; });
        recognition && recognition.addEventListener('error', (ev)=>{ status.innerText = "Status: error: " + ev.error; startBtn.disabled=false; stopBtn.disabled=true; copyBtn.disabled=false; });
        copyBtn.onclick = async () => {
          const text = (transcriptDiv.innerText || "").trim();
          if(!text){ alert("No transcript to copy — record first."); return; }
          try { await navigator.clipboard.writeText(text); alert("Transcript copied to clipboard. Paste into Streamlit input (Ctrl/Cmd+V)."); } catch(e){
            const range = document.createRange(); range.selectNodeContents(transcriptDiv); const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range); document.execCommand('copy'); alert("Transcript copied (fallback). Paste into Streamlit input.");}
        };
      </script>
    </body></html>
    """
    components.html(fallback_html, height=260)
    # Provide a place for user to paste
    pasted = st.text_input("Paste transcript here (or type reading directly):", value=st.session_state.get("last_transcript", ""))
    if pasted and pasted.strip():
        st.session_state.last_transcript = pasted.strip()
    transcript_str = st.session_state.get("last_transcript", "")

else:
    # automatic component path used; transcript_str already may be set above
    transcript_str = st.session_state.get("last_transcript", "")

# -------------------------
# Display transcript and allow check
# -------------------------
if transcript_str:
    st.success(f"Transcript (browser): {transcript_str}")
else:
    st.info("No transcript yet. Use Record → Stop → Send to App, or type the reading manually in the box.")

# Candidate selection prioritizes transcript_str then typed input
candidate_raw = transcript_str if transcript_str else typed_input.strip()

# Map kanji transcripts to hiragana if user spoke or pasted a kanji
normalized = ""
if candidate_raw:
    if contains_kanji(candidate_raw):
        # If the candidate contains the same kanji as the current card, use canonical reading
        if st.session_state.current in candidate_raw:
            normalized = KANJI_MAP.get(st.session_state.current, [None])[0] or ""
        else:
            # best-effort: map first kanji to its reading if we have it
            first_k = re.search(r"[\u4e00-\u9fff]", candidate_raw)
            if first_k:
                ch = first_k.group(0)
                normalized = KANJI_MAP.get(ch, [None])[0] or ""
    else:
        normalized = normalize_answer(candidate_raw)

if st.button("Check Answer"):
    st.session_state.user_answer = candidate_raw
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

# TTS playback
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
        for k,a,ok in reversed(st.session_state.history[-30:]):
            st.write(f"{k} — {a or '(empty)'} — {'✔️' if ok else '❌'}")
    else:
        st.write("No attempts yet.")

# Converter note
if HAS_JACONV:
    st.caption("Romaji->hiragana conversion available via jaconv.")
else:
    st.caption("jaconv not installed — romaji->hiragana not available (you can still type hiragana).")

st.caption("If the automatic component fails: open the browser Developer Console and terminal logs for errors (CSP, 404, mixed-content).")

