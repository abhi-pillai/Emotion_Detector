from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai
import os
from dotenv import load_dotenv
from datetime import datetime
import secrets

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # For session management

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-3-flash-preview')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
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
        
        # Store in session history (keep last 6 entries)
        if 'emotion_history' not in session:
            session['emotion_history'] = []
        
        # Add new entry with timestamp
        session['emotion_history'].append({
            'message': message,
            'emotion': emotion,
            'explanation': explanation,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Keep only last 6 entries
        if len(session['emotion_history']) > 6:
            session['emotion_history'] = session['emotion_history'][-6:]
        
        session.modified = True
        
        return jsonify({
            'emotion': emotion,
            'explanation': explanation,
            'history_count': len(session['emotion_history'])
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-history', methods=['GET'])
def get_history():
    """Return the emotion history"""
    history = session.get('emotion_history', [])
    return jsonify({'history': history})

@app.route('/analyze-mental-state', methods=['POST'])
def analyze_mental_state():
    """Analyze overall mental state based on recent emotions and provide remedies"""
    try:
        history = session.get('emotion_history', [])
        
        if len(history) < 2:
            return jsonify({
                'error': 'Need at least 2 analyzed messages to determine mental state'
            }), 400
        
        # Prepare history for AI analysis
        history_text = "\n".join([
            f"Message {i+1} ({entry['timestamp']}): Emotion - {entry['emotion']}, Message: \"{entry['message']}\""
            for i, entry in enumerate(history)
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
                    # Continue previous remedy
                    remedies[-1] += " " + line
                elif line:
                    remedies.append(line)
        
        # Calculate emotion distribution
        emotion_counts = {'happy': 0, 'sad': 0, 'angry': 0, 'neutral': 0}
        for entry in history:
            emotion = entry['emotion']
            if emotion in emotion_counts:
                emotion_counts[emotion] += 1
        
        return jsonify({
            'mental_state': mental_state.strip(),
            'remedies': [r for r in remedies if r],  # Remove empty remedies
            'emotion_distribution': emotion_counts,
            'total_analyzed': len(history)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear-history', methods=['POST'])
def clear_history():
    """Clear the emotion history"""
    session['emotion_history'] = []
    session.modified = True
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)