"""
Emotion Analyzer with Authentication
Main Flask application entry point.
"""
import os
import re
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from dotenv import load_dotenv
import google.generativeai as genai

from config import get_config
from mailer import send_email

load_dotenv()

# ---------------------------------------------------------------------------
# App & config
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(get_config())

logging.basicConfig(
    level=logging.INFO if not app.config["DEBUG"] else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("emotion-analyzer")

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Gemini configuration (fails soft, not on import)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
_gemini_model = None
_gemini_error = None

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    except Exception as exc:  # pragma: no cover - defensive
        _gemini_error = str(exc)
        logger.error("Failed to initialize Gemini client: %s", exc)
else:
    _gemini_error = "GEMINI_API_KEY is not set"
    logger.warning("GEMINI_API_KEY not set - emotion analysis endpoints will return 503")

ALLOWED_EMOTIONS = {"happy", "sad", "angry", "neutral"}
MAX_MESSAGE_LENGTH = 2000


def get_model():
    """Return the configured Gemini model, or raise a RuntimeError with a
    clear message if it isn't available. Keeps the route handlers simple."""
    if _gemini_model is None:
        raise RuntimeError(_gemini_error or "Gemini model is not configured")
    return _gemini_model


# ---------------------------------------------------------------------------
# Database models
# ---------------------------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    emotions = db.relationship(
        "EmotionHistory", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class EmotionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    emotion = db.Column(db.String(20), nullable=False)
    explanation = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)


with app.app_context():
    db.create_all()

# Signed, time-limited tokens for email verification and password reset.
# Uses the app's SECRET_KEY, so tokens become invalid if SECRET_KEY changes.
_serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
EMAIL_VERIFY_SALT = "email-verify"
PASSWORD_RESET_SALT = "password-reset"
EMAIL_VERIFY_MAX_AGE = 60 * 60 * 24  # 24 hours
PASSWORD_RESET_MAX_AGE = 60 * 60  # 1 hour


def send_verification_email(user):
    token = _serializer.dumps(user.email, salt=EMAIL_VERIFY_SALT)
    link = f"{app.config['APP_BASE_URL']}/verify-email/{token}"
    body = (
        f"Hi {user.username},\n\n"
        f"Please confirm your email address by visiting this link "
        f"(expires in 24 hours):\n{link}\n\n"
        f"If you didn't create this account, you can ignore this email."
    )
    send_email(app, user.email, "Confirm your Emotion Analyzer account", body)


def send_password_reset_email(user):
    token = _serializer.dumps(user.email, salt=PASSWORD_RESET_SALT)
    link = f"{app.config['APP_BASE_URL']}/reset-password/{token}"
    body = (
        f"Hi {user.username},\n\n"
        f"You (or someone else) requested a password reset. This link "
        f"expires in 1 hour:\n{link}\n\n"
        f"If you didn't request this, you can safely ignore this email - "
        f"your password will not be changed."
    )
    send_email(app, user.email, "Reset your Emotion Analyzer password", body)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def parse_emotion_response(result_text):
    """Parse the Emotion/Explanation formatted response from Gemini,
    with a safe fallback if the model doesn't follow the format exactly."""
    emotion, explanation = "", ""
    for line in result_text.strip().split("\n"):
        line = line.strip()
        if line.lower().startswith("emotion:"):
            emotion = line.split(":", 1)[1].strip().lower()
        elif line.lower().startswith("explanation:"):
            explanation = line.split(":", 1)[1].strip()

    # Normalize / validate against the known set instead of trusting the model blindly
    emotion = emotion.strip(".,! ").lower()
    if emotion not in ALLOWED_EMOTIONS:
        for candidate in ALLOWED_EMOTIONS:
            if candidate in emotion:
                emotion = candidate
                break
        else:
            emotion = "neutral"

    if not explanation:
        explanation = "No explanation was provided."

    return emotion, explanation


def parse_mental_state_response(result_text):
    lines = result_text.strip().split("\n")
    mental_state = ""
    remedies = []
    current_section = None

    for line in lines:
        line = line.strip()
        if line.lower().startswith("mental state:"):
            mental_state = line.split(":", 1)[1].strip()
            current_section = "mental_state"
        elif line.lower().startswith("remedies:"):
            current_section = "remedies"
            remedy_text = line.split(":", 1)[1].strip()
            if remedy_text:
                remedies.append(remedy_text)
        elif current_section == "mental_state" and line:
            mental_state += " " + line
        elif current_section == "remedies" and line:
            if line.startswith(("-", "•", "*")):
                remedies.append(line.lstrip("-•* ").strip())
            elif remedies:
                remedies[-1] += " " + line
            else:
                remedies.append(line)

    return mental_state.strip(), [r for r in remedies if r]


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        if not username or not email or not password:
            return jsonify({"error": "All fields are required"}), 400

        if len(username) < 3 or len(username) > 80:
            return jsonify({"error": "Username must be 3-80 characters"}), 400

        if not EMAIL_RE.match(email):
            return jsonify({"error": "Please provide a valid email address"}), 400

        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username already exists"}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already exists"}), 400

        new_user = User(username=username, email=email)
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("Registration failed")
            return jsonify({"error": "Registration failed. Please try again."}), 500

        send_verification_email(new_user)
        return jsonify(
            {
                "success": True,
                "message": "Registration successful! Check your email for a confirmation link before logging in.",
            }
        )

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            return jsonify({"error": "Invalid username or password"}), 401

        if not user.email_verified:
            return jsonify(
                {
                    "error": "Please confirm your email before logging in.",
                    "unverified": True,
                }
            ), 403

        session.clear()
        session["user_id"] = user.id
        session["username"] = user.username
        session.permanent = True
        return jsonify({"success": True, "redirect": url_for("dashboard")})

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/verify-email/<token>")
def verify_email(token):
    try:
        email = _serializer.loads(token, salt=EMAIL_VERIFY_SALT, max_age=EMAIL_VERIFY_MAX_AGE)
    except SignatureExpired:
        return render_template("message.html", title="Link expired",
                                message="That confirmation link has expired. Please request a new one.",
                                action_url=url_for("resend_confirmation"), action_label="Resend confirmation email")
    except BadSignature:
        return render_template("message.html", title="Invalid link",
                                message="That confirmation link is invalid.",
                                action_url=url_for("register"), action_label="Back to register")

    user = User.query.filter_by(email=email).first()
    if not user:
        return render_template("message.html", title="Account not found",
                                message="We couldn't find an account for that link.",
                                action_url=url_for("register"), action_label="Back to register")

    if not user.email_verified:
        user.email_verified = True
        db.session.commit()

    return render_template("message.html", title="Email confirmed",
                            message="Your email has been confirmed. You can now log in.",
                            action_url=url_for("login"), action_label="Go to login")


@app.route("/resend-confirmation", methods=["GET", "POST"])
def resend_confirmation():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        # Always return the same response whether or not the account exists,
        # so this endpoint can't be used to check which emails are registered.
        if user and not user.email_verified:
            send_verification_email(user)
        return jsonify({"success": True, "message": "If that account exists and isn't verified yet, a new confirmation email has been sent."})

    return render_template("resend_confirmation.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            send_password_reset_email(user)
        # Same response regardless, to avoid leaking which emails are registered.
        return jsonify({"success": True, "message": "If that email is registered, a password reset link has been sent."})

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = _serializer.loads(token, salt=PASSWORD_RESET_SALT, max_age=PASSWORD_RESET_MAX_AGE)
    except SignatureExpired:
        if request.method == "POST":
            return jsonify({"error": "This reset link has expired. Please request a new one."}), 400
        return render_template("message.html", title="Link expired",
                                message="That reset link has expired. Please request a new one.",
                                action_url=url_for("forgot_password"), action_label="Request new link")
    except BadSignature:
        if request.method == "POST":
            return jsonify({"error": "This reset link is invalid."}), 400
        return render_template("message.html", title="Invalid link",
                                message="That reset link is invalid.",
                                action_url=url_for("forgot_password"), action_label="Request new link")

    user = User.query.filter_by(email=email).first()
    if not user:
        if request.method == "POST":
            return jsonify({"error": "Account not found."}), 400
        return render_template("message.html", title="Account not found",
                                message="We couldn't find an account for that link.",
                                action_url=url_for("login"), action_label="Back to login")

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        password = data.get("password") or ""
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        user.set_password(password)
        db.session.commit()
        return jsonify({"success": True, "message": "Password updated. You can now log in."})

    return render_template("reset_password.html", token=token)


@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""

    user = db.session.get(User, session["user_id"])
    if not user or not user.check_password(password):
        return jsonify({"error": "Incorrect password"}), 401

    try:
        db.session.delete(user)  # cascades to EmotionHistory via relationship
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to delete account")
        return jsonify({"error": "Failed to delete account. Please try again."}), 500

    session.clear()
    return jsonify({"success": True, "redirect": url_for("login")})


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session.get("username"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
@app.route("/analyze", methods=["POST"])
@login_required
def analyze_emotion():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "No message provided"}), 400

    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"Message too long (max {MAX_MESSAGE_LENGTH} characters)"}), 400

    try:
        model = get_model()
    except RuntimeError as exc:
        logger.error("Gemini unavailable: %s", exc)
        return jsonify({"error": "Emotion analysis service is currently unavailable"}), 503

    prompt = f"""Analyze the emotion in the following message and classify it as one of: happy, sad, angry, or neutral.

Message: "{message}"

Respond in this exact format:
Emotion: [happy/sad/angry/neutral]
Explanation: [Brief 1-2 sentence explanation of why this emotion was detected]"""

    try:
        response = model.generate_content(prompt)
        emotion, explanation = parse_emotion_response(response.text)
    except Exception as exc:
        logger.exception("Gemini request failed")
        return jsonify({"error": "Failed to analyze emotion. Please try again."}), 502

    try:
        entry = EmotionHistory(
            user_id=session["user_id"],
            message=message,
            emotion=emotion,
            explanation=explanation,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to save emotion entry")
        return jsonify({"error": "Failed to save result"}), 500

    total_count = EmotionHistory.query.filter_by(user_id=session["user_id"]).count()

    return jsonify(
        {"emotion": emotion, "explanation": explanation, "history_count": total_count}
    )


@app.route("/get-history", methods=["GET"])
@login_required
def get_history():
    limit = request.args.get("limit", 10, type=int)
    limit = max(1, min(limit, 100))

    emotions = (
        EmotionHistory.query.filter_by(user_id=session["user_id"])
        .order_by(EmotionHistory.timestamp.desc())
        .limit(limit)
        .all()
    )

    history = [
        {
            "id": e.id,
            "message": e.message,
            "emotion": e.emotion,
            "explanation": e.explanation,
            "timestamp": e.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for e in emotions
    ]

    return jsonify({"history": history})


@app.route("/analyze-mental-state", methods=["POST"])
@login_required
def analyze_mental_state():
    recent_emotions = (
        EmotionHistory.query.filter_by(user_id=session["user_id"])
        .order_by(EmotionHistory.timestamp.desc())
        .limit(10)
        .all()
    )

    if len(recent_emotions) < 2:
        return jsonify({"error": "Need at least 2 analyzed messages to determine mental state"}), 400

    try:
        model = get_model()
    except RuntimeError:
        return jsonify({"error": "Mental state analysis service is currently unavailable"}), 503

    history_text = "\n".join(
        f'Message {i + 1} ({e.timestamp.strftime("%Y-%m-%d %H:%M")}): '
        f'Emotion - {e.emotion}, Message: "{e.message}"'
        for i, e in enumerate(reversed(recent_emotions))
    )

    prompt = f"""Based on the following recent emotion analysis history, provide:
1. An overall mental state assessment
2. Specific remedies and suggestions for improvement

Recent Emotion History:
{history_text}

Respond in this exact format:
Mental State: [A brief assessment of the person's overall mental state in 2-3 sentences]
Remedies: [Provide 4-6 practical, actionable remedies or suggestions, each on a new line starting with a dash (-)]"""

    try:
        response = model.generate_content(prompt)
        mental_state, remedies = parse_mental_state_response(response.text)
    except Exception:
        logger.exception("Gemini mental-state request failed")
        return jsonify({"error": "Failed to analyze mental state. Please try again."}), 502

    emotion_counts = {"happy": 0, "sad": 0, "angry": 0, "neutral": 0}
    for entry in recent_emotions:
        if entry.emotion in emotion_counts:
            emotion_counts[entry.emotion] += 1

    return jsonify(
        {
            "mental_state": mental_state,
            "remedies": remedies,
            "emotion_distribution": emotion_counts,
            "total_analyzed": len(recent_emotions),
        }
    )


@app.route("/get-stats", methods=["GET"])
@login_required
def get_stats():
    user_id = session["user_id"]
    total = EmotionHistory.query.filter_by(user_id=user_id).count()

    emotions = EmotionHistory.query.filter_by(user_id=user_id).all()
    emotion_counts = {"happy": 0, "sad": 0, "angry": 0, "neutral": 0}
    for emotion in emotions:
        if emotion.emotion in emotion_counts:
            emotion_counts[emotion.emotion] += 1

    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_count = EmotionHistory.query.filter(
        EmotionHistory.user_id == user_id, EmotionHistory.timestamp >= week_ago
    ).count()

    return jsonify(
        {
            "total_analyses": total,
            "emotion_distribution": emotion_counts,
            "recent_week": recent_count,
            "username": session["username"],
        }
    )


@app.route("/clear-history", methods=["POST"])
@login_required
def clear_history():
    try:
        EmotionHistory.query.filter_by(user_id=session["user_id"]).delete()
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        logger.exception("Failed to clear history")
        return jsonify({"error": "Failed to clear history"}), 500


@app.route("/healthz")
def healthz():
    """Health check endpoint for load balancers / container orchestrators."""
    status = {"status": "ok", "gemini_configured": _gemini_model is not None}
    return jsonify(status), 200 if _gemini_model is not None else 200


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith(("/analyze", "/get-", "/clear-history")):
        return jsonify({"error": "Not found"}), 404
    return redirect(url_for("index"))


@app.errorhandler(500)
def server_error(e):
    logger.exception("Unhandled server error")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=app.config["DEBUG"])
