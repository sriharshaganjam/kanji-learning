# app.py — Kanji Tutor with Mistral + Edge-TTS + Whisper + pykakasi (no fugashi)

import os, re, json, random, asyncio, tempfile, requests
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
import jaconv
import edge_tts
from pykakasi import kakasi

# ==================================
# --- Load environment variables
# ==================================
load_dotenv()

MISTRAL_API_URL = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions").strip()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()

# ==================================
# --- Kanji List and Map
# ==================================
KANJI_MAP = {
    "人": ["ひと", "じん", "にん"], "男": ["おとこ"], "女": ["おんな"], "子": ["こ", "し"],
    "母": ["はは", "かあ", "おかあさん"], "父": ["ちち", "とう", "おとうさん"], "友": ["とも"],
    "日": ["ひ", "にち", "じつ"], "月": ["つき", "がつ", "げつ"], "火": ["ひ", "か"],
    "水": ["みず", "すい"], "木": ["き", "もく"], "金": ["かね", "きん"], "土": ["つち", "ど"],
    "本": ["ほん"], "川": ["かわ"], "花": ["はな"], "気": ["き", "け"], "魚": ["さかな", "うお"],
    "天": ["てん"], "空": ["そら", "くう"], "山": ["やま"], "雨": ["あめ", "う"], "車": ["くるま", "しゃ"],
    "耳": ["みみ"], "手": ["て"], "足": ["あし", "そく"], "目": ["め", "もく"], "口": ["くち", "こう"], "名": ["な", "めい"]
}
ALLOWED_KANJI = "".join(KANJI_MAP.keys())
KANJI_LIST = list(KANJI_MAP.keys())

# ==================================
# --- Streamlit Config
# ==================================
st.set_page_config(page_title="Kanji Tutor — AI Reading & Pronunciation", layout="wide")
st.title("Kanji Tutor — Flashcards & Reading Exercise")

if "current_kanji" not in st.session_state:
    st.session_state.current_kanji = random.choice(KANJI_LIST)
    st.session_state.generated_sentence = None

# ==================================
# --- Normalization using pykakasi
# ==================================
_kakasi = kakasi()

def normalize_answer(text: str) -> str:
    """
    Normalizes any user input:
    - Converts romaji, katakana, or kanji → hiragana
    - Strips spaces and punctuation
    """
    if not text:
        return ""
    text = text.strip().lower()
    try:
        result = _kakasi.convert(text)
        if result:
            text = "".join([item["hira"] for item in result])
    except Exception:
        pass
    text = jaconv.kata2hira(text)
    return re.sub(r"\s+", "", text)

# ==================================
# --- Kanji Cleaner (no MeCab needed)
# ==================================
def clean_unlisted_kanji(sentence: str):
    """Replace any unlisted Kanji with hiragana placeholder."""
    cleaned = ""
    for ch in sentence:
        if re.match(r"[\u4e00-\u9faf]", ch):  # Kanji
            cleaned += ch if ch in ALLOWED_KANJI else "な"
        else:
            cleaned += ch
    return cleaned

# ==================================
# --- Mistral Integration
# ==================================
def mistral_prompt(kanji):
    return f"""
You are a Japanese language teacher.
Generate ONE simple natural Japanese sentence (5–12 words) that includes the kanji "{kanji}".
Rules:
- You MUST include the kanji "{kanji}" at least once.
- You may only use Kanji from this list: {ALLOWED_KANJI}.
- Any other words must be written in hiragana.
- Keep it beginner-friendly and natural.
Output JSON only:
{{"kanji":"...","kana":"...","romaji":"...","english":"..."}}
"""

def generate_sentence_mistral(kanji):
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": mistral_prompt(kanji)}],
        "temperature": 0.2
    }

    try:
        resp = requests.post(MISTRAL_API_URL, headers=headers, json=data, timeout=25)
        resp.raise_for_status()
        j = resp.json()
        text = j["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            parsed = json.loads(match.group(0))
            parsed["kanji"] = clean_unlisted_kanji(parsed["kanji"])
            return parsed
    except Exception as e:
        st.warning(f"Mistral error: {e}")
    return None

# ==================================
# --- Edge-TTS with Cache
# ==================================
CACHE_DIR = Path("cache/tts")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

async def _generate_tts_async(text: str, voice="ja-JP-NanamiNeural"):
    safe_name = re.sub(r"\W+", "_", text)[:40]
    file_path = CACHE_DIR / f"{safe_name}.mp3"
    if file_path.exists():
        return str(file_path)
    tts = edge_tts.Communicate(text, voice=voice)
    await tts.save(str(file_path))
    return str(file_path)

def generate_tts_cached(text: str, voice="ja-JP-NanamiNeural"):
    try:
        return asyncio.run(_generate_tts_async(text, voice))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_generate_tts_async(text, voice))

# ==================================
# --- Whisper STT (Transcription)
# ==================================
try:
    import streamlit_mic_recorder as st_mic_recorder
    from faster_whisper import WhisperModel
except Exception:
    st_mic_recorder = None
    WhisperModel = None

@st.cache_resource
def load_whisper(model_size="tiny", compute_type="int8"):
    if WhisperModel is None:
        return None
    return WhisperModel(model_size, device="cpu", compute_type=compute_type)

whisper_model = load_whisper("tiny", "int8")

def transcribe_audio_bytes_force_ja(audio_bytes: bytes) -> str:
    if not audio_bytes or whisper_model is None:
        return ""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        path = tmp.name
    try:
        segments, _ = whisper_model.transcribe(path, language="ja")
        return " ".join([s.text.strip() for s in segments]).strip()
    except Exception as e:
        st.error(f"Transcription failed: {e}")
        return ""
    finally:
        try:
            os.remove(path)
        except:
            pass

# ==================================
# --- Streamlit UI
# ==================================
mode = st.radio("Select mode:", ["Kanji quiz", "Reading exercise"], index=1)

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown(f"<div style='text-align:center; font-size:150px;'>{st.session_state.current_kanji}</div>", unsafe_allow_html=True)
with col2:
    if st.button("New Kanji"):
        st.session_state.current_kanji = random.choice(KANJI_LIST)
        st.session_state.generated_sentence = None
        st.rerun()

# ----------------------------
# MODE: READING EXERCISE
# ----------------------------
if mode == "Reading exercise":
    st.write("📖 Read simple sentences containing the shown Kanji (only known Kanji or Hiragana).")

    chosen_kanji = st.session_state.current_kanji

    if st.button("Generate sentence"):
        st.session_state.generated_sentence = generate_sentence_mistral(chosen_kanji)

    gen = st.session_state.get("generated_sentence")
    if gen:
        st.markdown("### Read this sentence (Kanji shown):")
        st.markdown(f"<div style='font-size:28px'>{gen['kanji']}</div>", unsafe_allow_html=True)
        st.caption(f"Hiragana version: {gen['kana']}")

        if st.button("🔊 Play sentence (Edge TTS)"):
            with st.spinner("Generating natural voice..."):
                audio_path = generate_tts_cached(gen["kana"])
                st.audio(audio_path, format="audio/mp3")

        # --- Reading input (text or mic) ---
        user_input = st.text_input("Type reading (hiragana/romaji):")

        if st_mic_recorder:
            audio_res = st_mic_recorder.mic_recorder(
                start_prompt="🎙️ Record your reading",
                stop_prompt="⏹ Stop",
                key="mic_reading_mode"
            )
            if audio_res and audio_res.get("bytes"):
                st.info("Transcribing your reading...")
                transcript = transcribe_audio_bytes_force_ja(audio_res["bytes"])
                st.success(f"Transcript: {transcript}")
                user_input = transcript

        if st.button("Check reading"):
            if not user_input:
                st.warning("Please type or record your reading first.")
            else:
                user_norm = normalize_answer(user_input)
                correct_norm = normalize_answer(gen["kana"])
                st.write(f"🧩 Your normalized input: {user_norm}")
                st.write(f"✅ Correct kana: {correct_norm}")

                if user_norm == correct_norm:
                    st.success("✅ Correct!")
                    st.balloons()
                else:
                    st.error(f"❌ Incorrect. Your reading: {user_norm}")
                st.markdown(
                    f"**Hiragana/Katakana:** {gen['kana']}  \n"
                    f"**Romaji:** {gen['romaji']}  \n"
                    f"**English:** {gen['english']}"
                )

else:
    st.write("🎴 Kanji quiz mode retained from earlier version.")
    st.info("Use Reading exercise mode for the full experience.")
