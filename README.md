# Groovii: AI Spotify Playlist Generator

This Flask app lets users log in with Spotify, describe their mood, and uses Gemini AI to generate a personalized playlist from their liked songs.

## Features
- Spotify OAuth login (with session clearing and state validation)
- User mood/description input
- Fetches user's liked songs from Spotify
- Uses Gemini AI (via Agno agent) to analyze and match songs
- Creates a playlist in the user's Spotify account
- Modern, unified UI (all styles in `static/style.css`)
- No chat or chat UI

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
- `/` - Home page (login/start)
- `/login` - Spotify OAuth login (clears session, always fresh)
- `/callback` - Spotify OAuth callback (validates state)
- `/analyze` - Submit mood/description and get playlist
- `/logout` - Log out of the app (clears session)

## Notes
- To switch Spotify accounts, log out of Spotify in your browser before logging in again.
- All UI is modernized and unified; all chat features have been removed.
- The app uses best practices for API security and user authentication.
