# Groovii: AI Spotify Playlist Generator

This Flask app lets users log in with Spotify, describe their mood, and uses Gemini AI Agents to generate a personalized playlist from their liked songs. The app analyzes lyrics and supplements with AI recommendations if needed.

## Features
- Spotify OAuth login (always fresh, session cleared on each visit to home page)
- User mood/description input
- Fetches user's liked songs from Spotify
- Uses Gemini AI (via Agno agent) to analyze and match songs based on lyrics (using Genius.com or similar)
- If not enough mood-matching liked songs, a second AI agent recommends additional real Spotify tracks, explicitly excluding already used tracks
- Creates a playlist in the user's Spotify account
- Modern, unified UI (all styles in `static/style.css`)
- Handles Spotify account switching correctly with a dedicated button

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set up Spotify and Gemini API credentials in a `.env` file:
   ```env
   FLASK_SECRET_KEY=your_flask_secret
   SPOTIPY_CLIENT_ID=your_spotify_client_id
   SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
   SPOTIPY_REDIRECT_URI=http://127.0.0.1:1234/callback
   GEMINI_API_KEY=your_gemini_api_key
   ```
3. Run the app:
   ```bash
   python app.py
   ```

## Endpoints
- `/` - Home page (clears session for fresh login)
- `/login` - Spotify OAuth login
- `/callback` - Spotify OAuth callback (validates state)
- `/analyze` - Submit mood/description and get playlist
- `/logout` - Log out of the app (clears session)
- `/switch_account` - Clears session and deletes `.cache` to allow switching Spotify accounts

## Notes
- To switch Spotify accounts, click the "Switch Spotify Account" button on the home page. This will clear the session and delete the `.cache` file, ensuring the next login uses the correct account.
- The AI agent analyzes lyrics for each liked song using Genius.com or similar, and only selects tracks that fit the user's mood/description.
- If not enough tracks are found, the agent recommends additional real Spotify tracks, always excluding those already used.
- All UI is modernized and unified.
- The app uses best practices for API security and user authentication.
- Do **not** commit your `.env` file or any secrets to git (see `.gitignore`).
