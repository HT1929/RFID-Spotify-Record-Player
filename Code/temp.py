import threading
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from time import sleep
import sqlite3
from RPLCD.i2c import CharLCD

# Setup constants
DEVICE_ID = "98bb0735e28656bac098d927d410c3138a4b5bca"
CLIENT_ID = "fc465222f6a94ee292f29574f20398e9"
CLIENT_SECRET = "b5e442bdbaee418da3c4bab8d7970b75"
REGISTER_RFID_TAG = 839325964744  # Replace with your actual register RFID tag ID
PAUSE_PLAYBACK = 682607722456

# GPIO Setup
MOTOR_DIRECTION_PIN = 16
MOTOR_INVERTED_PIN = 26
PWM_PIN = 12

GPIO.setmode(GPIO.BCM)
GPIO.setup(MOTOR_DIRECTION_PIN, GPIO.OUT)
GPIO.setup(MOTOR_INVERTED_PIN, GPIO.OUT)
GPIO.setup(PWM_PIN, GPIO.OUT)

pwm = GPIO.PWM(PWM_PIN, 1000)  # PWM at 1000 Hz
pwm.start(0)  # Start with motor off

# Spotify API Initialization
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri="http://localhost:8080",
    scope="user-read-playback-state,user-modify-playback-state"
))

# SQLite Database Setup
conn = sqlite3.connect('rfid_spotify.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
          CREATE TABLE IF NOT EXISTS tag_to_uri (
              tag_id INTEGER PRIMARY KEY,
              uri TEXT
          )
          ''')
conn.commit()

# LCD Initialization
lcd = CharLCD('PCF8574', 0x27)  # Update I2C address if necessary

# Global variables for thread coordination
stop_threads = False
display_state = {"type": "idle", "message": ""}  # Display state
current_track = {"name": None, "uri": None}  # Currently playing track


# Helper functions
def set_motor(speed, direction):
    """Set motor speed and direction."""
    pwm.ChangeDutyCycle(speed)
    GPIO.output(MOTOR_DIRECTION_PIN, direction)
    GPIO.output(MOTOR_INVERTED_PIN, not direction)


def display_both_lines_with_scroll(line1_message, line2_message, delay=0.3):
    """Display messages on both rows of the LCD with scrolling."""
    lcd.clear()
    max_chars = 16
    padded_line1 = line1_message + " " * max_chars
    padded_line2 = line2_message + " " * max_chars
    max_scroll = max(len(padded_line1), len(padded_line2)) - max_chars

    for i in range(max_scroll + 1):
        lcd.cursor_pos = (0, 0)
        lcd.write_string(padded_line1[i:i + max_chars])
        lcd.cursor_pos = (1, 0)
        lcd.write_string(padded_line2[i:i + max_chars])
        sleep(delay)
    lcd.clear()


def get_track_name(uri):
    """Retrieve track name from Spotify."""
    try:
        track_info = sp.track(uri)
        return track_info['name']
    except Exception as e:
        print(f"Error retrieving track info: {e}")
        return "Unknown Track"


def register_tag(tag_id, uri):
    """Register a new RFID tag with a Spotify URI."""
    try:
        c.execute("INSERT OR REPLACE INTO tag_to_uri (tag_id, uri) VALUES (?, ?)", (tag_id, uri))
        conn.commit()
        display_state["type"] = "idle"
        print(f"Tag {tag_id} registered with URI {uri}.")
    except Exception as e:
        print(f"Error registering tag: {e}")


# Thread Functions
def manage_display():
    """Thread to manage the LCD display."""
    global stop_threads, display_state, current_track
    while not stop_threads:
        if display_state["type"] == "song" and current_track["name"]:
            # Show the current track name repeatedly while playing
            display_both_lines_with_scroll("Playing", current_track["name"], delay=0.5)
        elif display_state["type"] == "error":
            # Show an error message once
            display_both_lines_with_scroll("Error", display_state["message"], delay=0.3)
            display_state["type"] = "idle"
        elif display_state["type"] == "register":
            # Show registration mode
            display_both_lines_with_scroll("Registration", "Mode Active", delay=0.3)
        elif display_state["type"] == "pause":
            # Show pause message
            display_both_lines_with_scroll("Playback", "Paused", delay=0.3)
            display_state["type"] = "idle"
        else:
            # Default idle state
            display_both_lines_with_scroll("RFID Spotify", "Waiting for scan...", delay=0.5)
        sleep(1)  # Reduce refresh rate


def check_playback_status():
    """Thread to check Spotify playback status and control motor."""
    global stop_threads, display_state, current_track
    while not stop_threads:
        try:
            playback = sp.current_playback()
            if playback and playback.get('is_playing', False):
                set_motor(50, True)  # Motor ON
                display_state["type"] = "song"  # Ensure the song is displayed
            else:
                set_motor(0, False)  # Motor OFF
                if display_state["type"] == "song":  # Only reset if no playback
                    display_state["type"] = "idle"
                    current_track["name"] = None
        except Exception as e:
            print(f"Error checking playback status: {e}")
        sleep(1)


def play_song_from_rfid():
    """Thread to handle RFID scanning and play songs."""
    global current_track, display_state, stop_threads
    reader = SimpleMFRC522()
    try:
        while not stop_threads:
            id, _ = reader.read()

            if id == PAUSE_PLAYBACK:
                try:
                    sp.pause_playback(device_id=DEVICE_ID)
                    set_motor(0, False)
                    display_state["type"] = "pause"
                except Exception as e:
                    display_state["type"] = "error"
                    display_state["message"] = f"Pause failed: {e}"
                continue

            if id == REGISTER_RFID_TAG:
                display_state["type"] = "register"
                while True:
                    id, _ = reader.read()
                    if id != REGISTER_RFID_TAG and id != PAUSE_PLAYBACK:
                        uri = sp.current_playback().get('item', {}).get('uri')
                        if uri:
                            register_tag(id, uri)
                            display_state["type"] = "idle"
                        else:
                            display_state["type"] = "error"
                            display_state["message"] = "No Playback Found"
                        break
                continue

            c.execute("SELECT uri FROM tag_to_uri WHERE tag_id=?", (id,))
            result = c.fetchone()
            if result:
                uri = result[0]
                if uri != current_track["uri"]:
                    current_track["uri"] = uri
                    current_track["name"] = get_track_name(uri)
                    display_state["type"] = "song"
                    try:
                        sp.start_playback(device_id=DEVICE_ID, uris=[uri])
                    except Exception as e:
                        display_state["type"] = "error"
                        display_state["message"] = f"Playback Error: {e}"
            else:
                current_track["name"] = None
                display_state["type"] = "error"
                display_state["message"] = "Tag Not Found"
            sleep(1)
    finally:
        print("RFID thread exiting...")


# Main Function
def main():
    """Main thread to run the program."""
    global stop_threads
    try:
        # Start the threads
        playback_thread = threading.Thread(target=check_playback_status, daemon=True)
        rfid_thread = threading.Thread(target=play_song_from_rfid, daemon=True)
        display_thread = threading.Thread(target=manage_display, daemon=True)

        playback_thread.start()
        rfid_thread.start()
        display_thread.start()

        while True:
            sleep(1)

    except KeyboardInterrupt:
        print("Stopping threads...")
        stop_threads = True

    finally:
        playback_thread.join()
        rfid_thread.join()
        display_thread.join()
        display_both_lines_with_scroll("Cleaning Up", "Goodbye!", delay=0.3)
        set_motor(0, False)
        pwm.stop()
        GPIO.cleanup()
        conn.close()


if __name__ == "__main__":
    main()
