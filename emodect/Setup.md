# Quick Setup Guide

## Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

## Step 2: Set Up Environment Variables
Create a file named `.env` in the project directory:
```
GEMINI_API_KEY=your_actual_gemini_api_key
```

**Get your Gemini API Key:**
1. Visit: https://makersuite.google.com/app/apikey
2. Sign in with Google
3. Click "Create API Key"
4. Copy and paste it into your `.env` file

## Step 3: Run the Application
```bash
python app.py
```

## Step 4: Open in Browser
Navigate to: http://localhost:8000

## First Use
1. Click "Register here"
2. Create your account
3. Login with your credentials
4. Start analyzing your emotions!

## Important Note
The original code had `gemini-3-flash-preview` which doesn't exist. 
I've updated it to `gemini-1.5-flash` which is the correct model name.

## Troubleshooting
- If you get API errors, check your Gemini API key in the `.env` file
- If database errors occur, delete `emotions.db` and restart
- Make sure all files are in the correct directory structure