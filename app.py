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
    import os
    cache_path = os.path.join(os.path.dirname(__file__), '.cache')
    cache_exists = os.path.exists(cache_path)
    return render_template('index.html', show_chat=True, cache_exists=cache_exists)

@app.route('/switch_account')
def switch_account():
    session.clear()
    import os
    cache_path = os.path.join(os.path.dirname(__file__), '.cache')
    if os.path.exists(cache_path):
        os.remove(cache_path)
    return redirect(url_for('index', switched=1))

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
    # If user cancels login, Spotify returns no code
    code = request.args.get('code')
    if not code:
        return redirect(url_for('index'))
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
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info
    sp = spotipy.Spotify(auth=token_info['access_token'])
    description = request.args.get('description') or request.form.get('description')
    mode = request.args.get('mode', 'liked')
    # Get number of songs from form, default to 20, clamp to 1-100
    try:
        num_songs = int(request.args.get('num_songs') or request.form.get('num_songs') or 20)
        num_songs = max(1, min(num_songs, 100))
    except Exception:
        num_songs = 20
    if request.method == 'GET' and not description:
        return render_template('analyze.html')
    # Fetch up to 200 liked songs for mood-matching, but only pass num_songs to agent if user has less
    max_liked_to_fetch = max(num_songs, 200)
    songs = []
    if mode == 'search':
        # Use Spotify search to find new music matching the description
        search_results = sp.search(q=description, type='track', limit=num_songs)
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
        while len(songs) < max_liked_to_fetch:
            results = sp.current_user_saved_tracks(limit=min(limit, max_liked_to_fetch - len(songs)), offset=offset)
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
                if len(songs) >= max_liked_to_fetch:
                    break
            if len(items) < limit:
                break
            offset += limit
    # Do not slice songs here, as we never fetch more than num_songs
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
    valid_song_ids = []
    playlist_name = None
    if GEMINI_API_KEY or agno_agent:
        try:
            allowed_tracks = {s['id']: {'name': s['name'], 'artist': s['artist']} for s in songs}
            agno_prompt = (
                "You are a music expert AI. "
                "You are given a list of Spotify tracks as a JSON object mapping track IDs to song info. "
                f"For each track, search for its lyrics on https://genius.com/ or another lyrics website. "
                f"Based on the lyrics, select as many track IDs from the provided list that best fit the user's mood or description, up to {num_songs}. "
                "Do NOT invent or guess any track IDs. "
                "Return ONLY a JSON object with two fields: 'track_ids' (an array of selected Spotify track IDs, e.g. ['id1','id2'], all of which MUST be from the provided list) and 'playlist_name'. "
                "For 'playlist_name', create a unique, witty, and highly creative playlist name that fits the user's mood/description. Avoid generic or repetitive names, and do not reuse names from previous responses. Make it fun, poetic, or surprising if possible. "
                "Do NOT include any explanations, commentary, or quotes. "
                f"\nUser's mood/description: {description}\nAllowed tracks: {json.dumps(allowed_tracks)}"
            )
            response = agno_agent.run(agno_prompt)
            print(response)
            agno_response = response.content
            if agno_response is None:
                print("Agent returned None as response!")
                return render_template('result.html', playlist_url=None, songs=[], error="Agent returned no response.", agent_response=agno_response)
            track_ids = []
            # Improved JSON extraction
            try:
                import re
                agno_response_clean = str(agno_response).strip()
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
            valid_song_ids = [s['id'] for s in songs[:min(5, len(songs))]]
            playlist_name = None
    else:
        valid_song_ids = [s['id'] for s in songs[:min(5, len(songs))]]
        playlist_name = None
        agno_response = None

    # Supplement with recommendations if not enough mood-matching liked songs
    max_rec_attempts = 1  # Only ask once
    rec_attempts = 0
    used_tracks = set()
    for tid in valid_song_ids:
        for s in songs:
            if s['id'] == tid:
                used_tracks.add((s['name'].lower(), s['artist'].lower()))
    while len(valid_song_ids) < num_songs and rec_attempts < max_rec_attempts:
        num_recs_needed = num_songs - len(valid_song_ids)
        rec_prompt = (
            f"Search the web for exactly {num_recs_needed} additional real Spotify tracks (not in the user's liked songs or these already used: {list(used_tracks)}) "
            f"that best fit this mood: '{description}'. Only suggest tracks that actually exist on Spotify. "
            "Return only a JSON array of objects, each with 'name' and 'artist'. Do not include explanations or any other text."
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
        recommended_ids = []
        for rec in rec_json:
            try:
                name_artist = (rec['name'].lower(), rec['artist'].lower())
                if name_artist in used_tracks:
                    continue
                q = f"track:{rec['name']} artist:{rec['artist']}"
                search = sp.search(q=q, type='track', limit=1)
                items = search['tracks']['items']
                if items:
                    rec_id = items[0]['id']
                    if rec_id not in valid_song_ids and rec_id not in recommended_ids:
                        recommended_ids.append(rec_id)
                used_tracks.add(name_artist)
            except Exception as e:
                print(f"Error adding recommended track: {e}")
                used_tracks.add(name_artist)
        if recommended_ids:
            recommended_ids = recommended_ids[:num_recs_needed]
            valid_song_ids.extend(recommended_ids)
        rec_attempts += 1

    # Use agent's playlist name, fallback to description if missing
    if not playlist_name or not playlist_name.strip():
        playlist_name = description[:80] if description else "AI Playlist"
    user_id = session.get('user_id')
    playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
    # Add tracks in batches of 100 (Spotify API limit)
    for i in range(0, len(valid_song_ids), 100):
        sp.user_playlist_add_tracks(user_id, playlist['id'], valid_song_ids[i:i+100])

    # If still not enough, show a warning message
    warning_msg = None
    if len(valid_song_ids) < num_songs:
        warning_msg = f"Only {len(valid_song_ids)} out of {num_songs} requested songs could be found and added. Try lowering the number or broadening your mood description."

    time.sleep(5)  # Wait for Spotify to update the playlist contents
    return render_template('result.html', playlist_url=playlist['external_urls']['spotify'], songs=valid_song_ids, playlist_id=playlist['id'], playlist_name=playlist_name, agent_response=agno_response, warning_msg=warning_msg)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=1234)