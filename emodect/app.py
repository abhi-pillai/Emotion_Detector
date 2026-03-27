from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import google.generativeai as genai
import os
from dotenv import load_dotenv
from datetime import datetime
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # For session management
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emotions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    emotions = db.relationship('EmotionHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class EmotionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    emotion = db.Column(db.String(20), nullable=False)
    explanation = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        # Validation
        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        # Create new user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Registration successful! Please login.'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session.permanent = True
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        else:
            return jsonify({'error': 'Invalid username or password'}), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/analyze', methods=['POST'])
@login_required
def analyze_emotion():
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Create prompt for Gemini
        prompt = f"""Analyze the emotion in the following message and classify it as one of: happy, sad, angry, or neutral.
        
Message: "{message}"

Respond in this exact format:
Emotion: [happy/sad/angry/neutral]
Explanation: [Brief 1-2 sentence explanation of why this emotion was detected]"""
        
        # Generate response
        response = model.generate_content(prompt)
        result_text = response.text
        
        # Parse the response
        lines = result_text.strip().split('\n')
        emotion = ""
        explanation = ""
        
        for line in lines:
            if line.startswith('Emotion:'):
                emotion = line.replace('Emotion:', '').strip().lower()
            elif line.startswith('Explanation:'):
                explanation = line.replace('Explanation:', '').strip()
        
        # Save to database
        emotion_entry = EmotionHistory(
            user_id=session['user_id'],
            message=message,
            emotion=emotion,
            explanation=explanation
        )
        db.session.add(emotion_entry)
        db.session.commit()
        
        # Get total count
        total_count = EmotionHistory.query.filter_by(user_id=session['user_id']).count()
        
        return jsonify({
            'emotion': emotion,
            'explanation': explanation,
            'history_count': total_count
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/get-history', methods=['GET'])
@login_required
def get_history():
    """Return the emotion history for the logged-in user"""
    limit = request.args.get('limit', 10, type=int)
    
    emotions = EmotionHistory.query.filter_by(user_id=session['user_id'])\
        .order_by(EmotionHistory.timestamp.desc())\
        .limit(limit)\
        .all()
    
    history = [{
        'id': e.id,
        'message': e.message,
        'emotion': e.emotion,
        'explanation': e.explanation,
        'timestamp': e.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    } for e in emotions]
    
    return jsonify({'history': history})

@app.route('/analyze-mental-state', methods=['POST'])
@login_required
def analyze_mental_state():
    """Analyze overall mental state based on recent emotions and provide remedies"""
    try:
        # Get recent emotions (last 10)
        recent_emotions = EmotionHistory.query.filter_by(user_id=session['user_id'])\
            .order_by(EmotionHistory.timestamp.desc())\
            .limit(10)\
            .all()
        
        if len(recent_emotions) < 2:
            return jsonify({
                'error': 'Need at least 2 analyzed messages to determine mental state'
            }), 400
        
        # Prepare history for AI analysis
        history_text = "\n".join([
            f"Message {i+1} ({e.timestamp.strftime('%Y-%m-%d %H:%M')}): Emotion - {e.emotion}, Message: \"{e.message}\""
            for i, e in enumerate(reversed(recent_emotions))
        ])
        
        prompt = f"""Based on the following recent emotion analysis history, provide:
1. An overall mental state assessment
2. Specific remedies and suggestions for improvement

Recent Emotion History:
{history_text}

Respond in this exact format:
Mental State: [A brief assessment of the person's overall mental state in 2-3 sentences]
Remedies: [Provide 4-6 practical, actionable remedies or suggestions, each on a new line starting with a dash (-)]"""
        
        # Generate response
        response = model.generate_content(prompt)
        result_text = response.text
        
        # Parse the response
        lines = result_text.strip().split('\n')
        mental_state = ""
        remedies = []
        current_section = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('Mental State:'):
                mental_state = line.replace('Mental State:', '').strip()
                current_section = 'mental_state'
            elif line.startswith('Remedies:'):
                current_section = 'remedies'
                remedy_text = line.replace('Remedies:', '').strip()
                if remedy_text:
                    remedies.append(remedy_text)
            elif current_section == 'mental_state' and line:
                mental_state += " " + line
            elif current_section == 'remedies' and line:
                if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                    remedies.append(line.lstrip('-•* ').strip())
                elif line and len(remedies) > 0:
                    remedies[-1] += " " + line
                elif line:
                    remedies.append(line)
        
        # Calculate emotion distribution
        emotion_counts = {'happy': 0, 'sad': 0, 'angry': 0, 'neutral': 0}
        for entry in recent_emotions:
            emotion = entry.emotion
            if emotion in emotion_counts:
                emotion_counts[emotion] += 1
        
        return jsonify({
            'mental_state': mental_state.strip(),
            'remedies': [r for r in remedies if r],
            'emotion_distribution': emotion_counts,
            'total_analyzed': len(recent_emotions)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-stats', methods=['GET'])
@login_required
def get_stats():
    """Get statistics about user's emotion history"""
    user_id = session['user_id']
    
    # Total emotions
    total = EmotionHistory.query.filter_by(user_id=user_id).count()
    
    # Emotion distribution
    emotions = EmotionHistory.query.filter_by(user_id=user_id).all()
    emotion_counts = {'happy': 0, 'sad': 0, 'angry': 0, 'neutral': 0}
    
    for emotion in emotions:
        if emotion.emotion in emotion_counts:
            emotion_counts[emotion.emotion] += 1
    
    # Recent activity (last 7 days)
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_count = EmotionHistory.query.filter(
        EmotionHistory.user_id == user_id,
        EmotionHistory.timestamp >= week_ago
    ).count()
    
    return jsonify({
        'total_analyses': total,
        'emotion_distribution': emotion_counts,
        'recent_week': recent_count,
        'username': session['username']
    })

@app.route('/clear-history', methods=['POST'])
@login_required
def clear_history():
    """Clear the emotion history for the logged-in user"""
    try:
        EmotionHistory.query.filter_by(user_id=session['user_id']).delete()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)