# Emotion Analyzer with Authentication

A Flask-based web application that analyzes emotions in text messages using Google's Gemini API and provides mental wellness insights with user authentication.

## Features

- **User Authentication**: Secure registration and login system
- **Emotion Analysis**: Analyzes text messages and classifies emotions (happy, sad, angry, neutral)
- **Mental State Assessment**: Provides overall mental state analysis based on emotion history
- **Personalized Remedies**: AI-generated suggestions for mental wellness
- **User Dashboard**: View statistics and emotion history
- **Session Management**: Each user has their own private emotion history
- **Database Storage**: All data is securely stored in SQLite database

## Installation

1. **Clone or download the project files**

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**:
Create a `.env` file in the project root with:
```
GEMINI_API_KEY=your_gemini_api_key_here
```

To get a Gemini API key:
- Go to https://makersuite.google.com/app/apikey
- Sign in with your Google account
- Create a new API key

4. **Run the application**:
```bash
python app.py
```

5. **Access the application**:
Open your browser and go to `http://localhost:8000`

## Usage

### First Time Users

1. **Register**: Click on "Register here" and create an account with:
   - Username
   - Email
   - Password (minimum 6 characters)

2. **Login**: Use your credentials to login

### Using the Dashboard

1. **Analyze Emotions**:
   - Type your message in the text area
   - Click "Analyze Emotion"
   - View the detected emotion and explanation

2. **View Statistics**:
   - Total analyses count
   - This week's analyses
   - Breakdown by emotion type (Happy, Sad, Angry, Neutral)

3. **Mental State Analysis**:
   - Click "Analyze My Mental State"
   - Requires at least 2 analyzed messages
   - Get overall assessment and personalized remedies
   - View emotion distribution chart

4. **Emotion History**:
   - Scroll down to see your complete emotion history
   - Each entry shows: emotion, timestamp, message, and explanation
   - Click "Clear History" to delete all entries

5. **Logout**: Click the logout button in the navigation bar

## Project Structure

```
emotion-analyzer/
│
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create this)
│
├── templates/
│   ├── login.html        # Login page
│   ├── register.html     # Registration page
│   └── dashboard.html    # Main dashboard
│
└── static/
    ├── css/
    │   └── style.css     # Styling
    └── js/
        └── dashboard.js  # Dashboard functionality
```

## Database

The application uses SQLite database (`emotions.db`) with two tables:

- **User**: Stores user credentials (username, email, hashed password)
- **EmotionHistory**: Stores emotion analysis results linked to users

The database is created automatically on first run.

## Security Features

- Password hashing using Werkzeug's security functions
- Session-based authentication
- User-specific data isolation
- CSRF protection through session tokens

## API Endpoints

- `GET /` - Redirect to login or dashboard
- `GET/POST /register` - User registration
- `GET/POST /login` - User login
- `GET /logout` - User logout
- `GET /dashboard` - Main dashboard (requires login)
- `POST /analyze` - Analyze emotion (requires login)
- `GET /get-history` - Get emotion history (requires login)
- `POST /analyze-mental-state` - Get mental state analysis (requires login)
- `GET /get-stats` - Get user statistics (requires login)
- `POST /clear-history` - Clear emotion history (requires login)

## Notes

- The Gemini model used is `gemini-1.5-flash` (corrected from `gemini-3-flash-preview`)
- Emotion history is limited to the last 10 entries for mental state analysis
- All timestamps are in UTC
- Session data is stored server-side for security

## Troubleshooting

**Issue**: "Invalid API key" error
- **Solution**: Check your `.env` file has the correct `GEMINI_API_KEY`

**Issue**: Database errors
- **Solution**: Delete `emotions.db` and restart the app to recreate the database

**Issue**: "Need at least 2 analyzed messages"
- **Solution**: Analyze at least 2 messages before requesting mental state analysis

## Future Enhancements

- Password reset functionality
- Email verification
- Export emotion history
- More detailed analytics and visualizations
- Mobile app version
- Multi-language support

## License

This project is open source and available for educational purposes.