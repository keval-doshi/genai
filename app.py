from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "myapp-fixed-secret-key-2024")

# ============================================================
#   EASY CUSTOMIZATION — Change these for your specific exam
# ============================================================

CHATBOT_NAME = "General Assistant"

CHATBOT_DESCRIPTION = (
    "Hello! 👋 I am a **General Assistant Chatbot** built with Google Gemini AI.\n\n"
    "I can help you with **questions, explanations, and conversations** on any topic.\n\n"
    "To customise me for a specific purpose (e.g. a Medical Bot, Legal Bot, Customer Support Bot), "
    "simply update the `SYSTEM_PROMPT` variable in `app.py`.\n\n"
    "Feel free to start chatting!"
)

SYSTEM_PROMPT = (
    "You are a helpful and friendly general-purpose assistant. "
    "Answer questions clearly and concisely. "
    "Format your responses using proper paragraphs. "
    "If you don't know something, say so honestly."
)

MAX_HISTORY = 10

# ============================================================

def get_gemini_client():
    """Create client lazily so missing key gives clean error instead of crashing."""
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def get_session_history():
    if "history" not in session:
        session["history"] = []
    return session["history"]


@app.route("/")
def index():
    session.clear()
    return render_template(
        "index.html",
        chatbot_name=CHATBOT_NAME,
        chatbot_description=CHATBOT_DESCRIPTION
    )


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    client = get_gemini_client()
    if not client:
        return jsonify({
            "error": "api_error",
            "message": "❌ GEMINI_API_KEY is not set. Please add it in Vercel → Settings → Environment Variables."
        }), 500

    history = get_session_history()

    from google.genai import types
    gemini_history = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        gemini_history.append(
            types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            )
        )

    try:
        chat_session = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
            ),
            history=gemini_history
        )

        response = chat_session.send_message(message=user_message)
        bot_reply = response.text

    except Exception as e:
        print(f"🔴 ERROR: {e}")
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str or "rate" in error_str or "resource_exhausted" in error_str:
            return jsonify({
                "error": "quota_exceeded",
                "message": "⚠️ Your free quota has been finished. Please wait a minute and try again."
            }), 429
        return jsonify({
            "error": "api_error",
            "message": f"Error: {str(e)}"
        }), 500

    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": bot_reply})

    if len(history) > MAX_HISTORY * 2:
        history = history[-(MAX_HISTORY * 2):]

    session["history"] = history

    return jsonify({
        "reply": bot_reply,
        "history_count": len(history) // 2
    })


@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
