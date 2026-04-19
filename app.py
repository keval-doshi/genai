from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
import os, requests, traceback

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "myapp-fixed-secret-key-2024")

# ============================================================
#   EASY CUSTOMIZATION — Change these for your specific exam
# ============================================================

CHATBOT_NAME = "General Assistant"

CHATBOT_DESCRIPTION = (
    "Hello! I am a General Assistant Chatbot built with Google Gemini AI.\n\n"
    "I can help you with questions, explanations, and conversations on any topic.\n\n"
    "To customise me for a specific purpose (e.g. a Medical Bot, Legal Bot, "
    "Customer Support Bot), simply update the SYSTEM_PROMPT variable in app.py.\n\n"
    "Feel free to start chatting!"
)

SYSTEM_PROMPT = (
    "You are a helpful and friendly general-purpose assistant. "
    "Answer questions clearly and concisely. "
    "Format your responses using proper paragraphs. "
    "If you don't know something, say so honestly."
)

MAX_HISTORY = 10

GEMINI_MODEL  = "gemini-2.5-flash"
GEMINI_URL    = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# ============================================================

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"error": "crash", "message": str(e), "trace": traceback.format_exc()[-600:]}), 500


def get_session_history():
    if "history" not in session:
        session["history"] = []
    return session["history"]


@app.route("/")
def index():
    session.clear()
    return render_template("index.html",
                           chatbot_name=CHATBOT_NAME,
                           chatbot_description=CHATBOT_DESCRIPTION)


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data        = request.get_json(force=True, silent=True) or {}
        user_msg    = data.get("message", "").strip()
        if not user_msg:
            return jsonify({"error": "empty", "message": "Empty message"}), 400

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"error": "no_key",
                            "message": "GEMINI_API_KEY not set in Vercel Environment Variables."}), 500

        history = get_session_history()

        # Build contents array (system prompt first, then conversation history)
        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_msg}]})

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents
        }

        resp = requests.post(
            GEMINI_URL,
            params={"key": api_key},
            json=payload,
            timeout=30
        )

        if resp.status_code == 429:
            return jsonify({"error": "quota",
                            "message": "Quota exceeded. Please wait 1 minute and try again."}), 429

        if not resp.ok:
            return jsonify({"error": "api_error",
                            "message": f"Gemini API error {resp.status_code}: {resp.text[:300]}"}), 500

        bot_reply = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

        # Save history
        history.append({"role": "user",      "content": user_msg})
        history.append({"role": "assistant", "content": bot_reply})
        if len(history) > MAX_HISTORY * 2:
            history = history[-(MAX_HISTORY * 2):]
        session["history"] = history

        return jsonify({"reply": bot_reply, "history_count": len(history) // 2})

    except Exception as e:
        return jsonify({"error": "api_error", "message": str(e),
                        "trace": traceback.format_exc()[-600:]}), 500


@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
