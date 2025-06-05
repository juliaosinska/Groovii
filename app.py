import os
from flask import Flask, redirect, request, session, url_for, jsonify, render_template
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import google.generativeai as genai
import json
from agno.agent import Agent
from agno.models.google import Gemini
import asyncio
from uuid import uuid4
import time

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_secret')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

# Spotify config
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI', 'http://127.0.0.1:1234/callback')
SCOPE = 'user-library-read playlist-modify-public playlist-modify-private'

# Gemini config
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Initialize Agno Gemini model and Agent
agno_model = Gemini(id="gemini-1.5-flash", api_key=GEMINI_API_KEY)
agno_agent = Agent(model=agno_model, markdown=True, debug_mode=True, show_tool_calls=True)

@app.route('/')
def index():
    session.clear()  # Clear session to ensure fresh login on each visit to index
    return render_template('index.html', show_chat=True)

@app.route('/login')
def login():
    session.clear()  # Clear session to ensure fresh login
    state = str(uuid4())
    session['oauth_state'] = state
    sp_oauth = SpotifyOAuth(
        SPOTIPY_CLIENT_ID,
        SPOTIPY_CLIENT_SECRET,
        SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        cache_handler=None,
        show_dialog=True,
        state=session.get('oauth_state')
    )
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/callback')
def callback():
    sp_oauth = SpotifyOAuth(
        SPOTIPY_CLIENT_ID,
        SPOTIPY_CLIENT_SECRET,
        SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=None
    )
    # Validate state to prevent replay attacks
    state = request.args.get('state')
    if not state or state != session.get('oauth_state'):
        return 'Invalid state parameter. Please try logging in again.', 400
    # Do NOT clear session here!
    code = request.args.get('code')
    if not code:
        return 'Authorization failed. No code returned from Spotify.', 400
    token_info = sp_oauth.get_access_token(code, as_dict=True) if hasattr(sp_oauth, 'get_access_token') else sp_oauth.get_access_token(code)
    if not token_info or 'access_token' not in token_info:
        return 'Failed to get access token from Spotify.', 400
    session['token_info'] = token_info
    sp = spotipy.Spotify(auth=token_info['access_token'])
    user = sp.current_user()
    session['user_id'] = user['id']
    return redirect(url_for('analyze'))

@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    token_info = session.get('token_info')
    # Refresh token if expired
    if not token_info or not token_info.get('access_token'):
        return redirect(url_for('login'))
    sp_oauth = SpotifyOAuth(
        SPOTIPY_CLIENT_ID,
        SPOTIPY_CLIENT_SECRET,
        SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=None
    )
    # Check if token is expired and refresh if needed
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info
    sp = spotipy.Spotify(auth=token_info['access_token'])
    # Accept description and mode from chat agent redirect
    description = request.args.get('description') or request.form.get('description')
    mode = request.args.get('mode', 'liked')
    if request.method == 'GET' and not description:
        return render_template('analyze.html')
    # Fetch songs based on mode
    songs = []
    if mode == 'search':
        # Use Spotify search to find new music matching the description
        search_results = sp.search(q=description, type='track', limit=20)
        for t in search_results['tracks']['items']:
            songs.append({
                'name': t['name'],
                'artist': t['artists'][0]['name'],
                'id': t['id']
            })
    else:
        # Default: use liked songs
        limit = 50
        offset = 0
        while True:
            results = sp.current_user_saved_tracks(limit=limit, offset=offset)
            items = results['items']
            if not items:
                break
            for t in items:
                if t['track'] and t['track']['id']:
                    songs.append({
                        'name': t['track']['name'],
                        'artist': t['track']['artists'][0]['name'],
                        'id': t['track']['id']
                    })
            if len(items) < limit:
                break
            offset += limit
    song_ids = [s['id'] for s in songs if s['id']]
    # Instead of audio features, use available song metadata for AI analysis
    song_data = [
        {
            'name': s['name'],
            'artist': s['artist'],
            'id': s['id']
        } for s in songs
    ]
    print(f"Sample song_data: {song_data[:2]}")
    # Use Agno agent for song selection and playlist naming
    agno_response = None  # Ensure this is always defined
    if GEMINI_API_KEY or agno_agent:
        try:
            allowed_tracks = {s['id']: {'name': s['name'], 'artist': s['artist']} for s in songs}
            agno_prompt = (
                "You are a music expert AI. "
                "You are given a list of Spotify tracks as a JSON object mapping track IDs to song info. "
                "ONLY select up to 20 track IDs from the provided list that best fit the user's mood or description. "
                "Do NOT invent or guess any track IDs. "
                "Return ONLY a JSON object with two fields: 'track_ids' (an array of selected Spotify track IDs, e.g. ['id1','id2'], all of which MUST be from the provided list) and 'playlist_name' (a short, witty, and fitting playlist name). "
                "Do NOT include any explanations, commentary, or quotes. "
                f"\nUser's mood/description: {description}\nAllowed tracks: {json.dumps(allowed_tracks)}"
            )
            response = agno_agent.run(agno_prompt)
            print(response)
            # Use .content for RunResponse, fallback to .output or str(response) if needed
            agno_response = response.content
            print("Agent returned:", agno_response)
            if agno_response is None:
                print("Agent returned None as response!")
                return render_template('result.html', playlist_url=None, songs=[], error="Agent returned no response.", agent_response=agno_response)
            track_ids = []
            playlist_name = None
            # Improved JSON extraction
            try:
                import re
                agno_response_clean = str(agno_response).strip()
                # Extract JSON from markdown code block if present
                codeblock_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', agno_response_clean, re.IGNORECASE)
                if codeblock_match:
                    agno_response_clean = codeblock_match.group(1).strip()
                # Remove any leading/trailing backticks or whitespace
                agno_response_clean = agno_response_clean.strip('`').strip()
                # Now extract JSON
                if agno_response_clean.startswith('{') and agno_response_clean.endswith('}'):
                    agno_json = json.loads(agno_response_clean)
                else:
                    json_match = re.search(r'\{[\s\S]*?\}', agno_response_clean)
                    if json_match:
                        agno_json = json.loads(json_match.group(0))
                    else:
                        raise ValueError("No JSON object found in agent response")
                track_ids = agno_json.get('track_ids', [])
                playlist_name = agno_json.get('playlist_name')
            except Exception as e:
                print(f"JSON parse error: {e}\nRaw agent response: {agno_response}")
                track_ids = []
            valid_song_ids = [tid for tid in track_ids if tid in allowed_tracks]
            print(f"Agent response: {agno_response}")
            print(f"Extracted track IDs: {valid_song_ids}")
            print(f"Extracted playlist name: {playlist_name}")
            
        except Exception as e:
            print(f"Error in agent processing: {str(e)}")
            valid_song_ids = [s['id'] for s in songs[:5]]
            playlist_name = None
    else:
        valid_song_ids = [s['id'] for s in songs[:5]]
        playlist_name = None
        agno_response = None
    
    if not valid_song_ids:
        return render_template('result.html', playlist_url=None, songs=[], error="No valid tracks selected by the agent. Please try again or check your liked songs.", agent_response=agno_response)
    
    # Use agent's playlist name, fallback to description if missing
    if not playlist_name or not playlist_name.strip():
        playlist_name = description[:80] if description else "AI Playlist"
        
    user_id = session.get('user_id')
    playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
    sp.user_playlist_add_tracks(user_id, playlist['id'], valid_song_ids)

    # If user has less than 100 liked tracks, get recommendations from agent
    if len(songs) < 100:
        # Ask the agent for recommended tracks (by name and artist)
        rec_prompt = (
            "Suggest 10 additional Spotify tracks (not in the user's liked songs) that fit this mood: '"
            f"{description}' as a JSON array of objects with 'name' and 'artist'. Do not include any explanations."
        )
        rec_response = agno_agent.run(rec_prompt)
        import re
        rec_json = []
        try:
            rec_clean = str(rec_response.content).strip()
            codeblock_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', rec_clean, re.IGNORECASE)
            if codeblock_match:
                rec_clean = codeblock_match.group(1).strip()
            rec_clean = rec_clean.strip('`').strip()
            if rec_clean.startswith('[') and rec_clean.endswith(']'):
                rec_json = json.loads(rec_clean)
            else:
                json_match = re.search(r'\[[\s\S]*?\]', rec_clean)
                if json_match:
                    rec_json = json.loads(json_match.group(0))
        except Exception as e:
            print(f"Error parsing recommendations: {e}\nRaw: {rec_response}")
            rec_json = []
        # Search Spotify for each recommended track and add the first match
        recommended_ids = []
        for rec in rec_json:
            try:
                q = f"track:{rec['name']} artist:{rec['artist']}"
                search = sp.search(q=q, type='track', limit=1)
                items = search['tracks']['items']
                if items:
                    rec_id = items[0]['id']
                    if rec_id not in valid_song_ids and rec_id not in recommended_ids:
                        recommended_ids.append(rec_id)
            except Exception as e:
                print(f"Error adding recommended track: {e}")
        if recommended_ids:
            sp.user_playlist_add_tracks(user_id, playlist['id'], recommended_ids)
            valid_song_ids.extend(recommended_ids)
    time.sleep(5)  # Wait for Spotify to update the playlist contents
    return render_template('result.html', playlist_url=playlist['external_urls']['spotify'], songs=valid_song_ids, playlist_id=playlist['id'], playlist_name=playlist_name, agent_response=agno_response)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=1234)