import spotipy
from spotipy.oauth2 import SpotifyOAuth
from time import sleep

# Spotify Credentials
CLIENT_ID = "fc465222f6a94ee292f29574f20398e9"
CLIENT_SECRET = "b5e442bdbaee418da3c4bab8d7970b75"

# Spotify Initialization
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri="http://localhost:8080",
    scope="user-read-playback-state,user-modify-playback-state"
))

def check_raspotify_connection(device_name="raspotify"):
    """Check if the specified Spotify device is connected."""
    while True:
        try:
            devices = sp.devices()
            for device in devices.get('devices', []):
                if device['name'].lower() == device_name.lower():
                    print(f"{device_name} is connected.")
                    return device['id']  # Return the device ID
            print(f"Waiting for {device_name} to connect...")
        except Exception as e:
            print(f"Error checking devices: {e}")
        sleep(5)  # Retry every 5 seconds

if __name__ == "__main__":
    print("Checking Raspotify connection...")
    DEVICE_ID = check_raspotify_connection("raspotify")  # Replace "raspotify" with your device name
    print(f"Raspotify connected! Device ID: {DEVICE_ID}")
