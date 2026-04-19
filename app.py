from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
import os
import traceback

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

# ============================================================

# ── Global JSON error handler — no more HTML 500 pages ──
@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    print(f"UNHANDLED EXCEPTION:\n{tb}")
    return jsonify({
        "error": "server_crash",
        "message": str(e),
        "trace": tb[-500:]   # last 500 chars of traceback
    }), 500


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
    try:
        # ── Parse request ──
        data = request.get_json(force=True, silent=True) or {}
        user_message = data.get("message", "").strip()
        if not user_message:
            return jsonify({"error": "empty", "message": "Empty message"}), 400

        # ── Check API key ──
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return jsonify({
                "error": "no_key",
                "message": "GEMINI_API_KEY is not set. Go to Vercel Dashboard → Settings → Environment Variables and add it, then redeploy."
            }), 500

        # ── Import SDK ──
        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # ── Build history ──
        history = get_session_history()
        gemini_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append(
                types.Content(role=role, parts=[types.Part(text=msg["content"])])
            )

        # ── Call Gemini ──
        chat_session = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            history=gemini_history
        )
        response = chat_session.send_message(message=user_message)
        bot_reply = response.text

        # ── Save history ──
        history.append({"role": "user",      "content": user_message})
        history.append({"role": "assistant", "content": bot_reply})
        if len(history) > MAX_HISTORY * 2:
            history = history[-(MAX_HISTORY * 2):]
        session["history"] = history

        return jsonify({"reply": bot_reply, "history_count": len(history) // 2})

    except Exception as e:
        tb = traceback.format_exc()
        print(f"CHAT ERROR:\n{tb}")
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
            return jsonify({
                "error": "quota",
                "message": "Quota exceeded. Please wait 1 minute and try again."
            }), 429
        return jsonify({
            "error": "api_error",
            "message": str(e),
            "trace": tb[-600:]
        }), 500


@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
