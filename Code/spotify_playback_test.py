import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time

# Setup Spotify client
CLIENT_ID = "your_spotify_client_id"
CLIENT_SECRET = "your_spotify_client_secret"
DEVICE_ID = "your_device_id"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri="http://localhost:8080",
    scope="user-read-playback-state,user-modify-playback-state"
))

def test_spotify_playback():
    """Test Spotify playback control."""
    try:
        print("Pausing playback")
        sp.pause_playback(device_id=DEVICE_ID)
        time.sleep(2)

        print("Resuming playback")
        sp.start_playback(device_id=DEVICE_ID)
        time.sleep(5)

        print("Pausing playback again")
        sp.pause_playback(device_id=DEVICE_ID)
    except Exception as e:
        print(f"Error with Spotify playback: {e}")

if __name__ == "__main__":
    test_spotify_playback()
