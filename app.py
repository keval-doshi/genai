from flask import Flask, request, jsonify, render_template, session
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found in .env file!")

client = genai.Client(api_key=GEMINI_API_KEY)  # explicit key, no ambiguity


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

    history = get_session_history()

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
            model="gemini-2.5-flash",   # most stable free-tier model
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
            ),
            history=gemini_history
        )

        response = chat_session.send_message(message=user_message)
        bot_reply = response.text

    except Exception as e:
        print(f"\n🔴 ACTUAL ERROR: {e}\n")   # prints full error in terminal
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str or "rate" in error_str or "resource_exhausted" in error_str:
            return jsonify({
                "error": "quota_exceeded",
                "message": "⚠️ Your free quota has been finished. Please wait a minute and try again."
            }), 429
        else:
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