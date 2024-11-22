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

# Setup GPIO pins
MOTOR_DIRECTION_PIN = 16
MOTOR_INVERTED_PIN = 26
PWM_PIN = 12
REGISTER_RFID_TAG = 839325964744  # Replace with your actual register RFID tag ID
PAUSE_PLAYBACK = 682607722456

GPIO.setmode(GPIO.BCM)
GPIO.setup(MOTOR_DIRECTION_PIN, GPIO.OUT)
GPIO.setup(MOTOR_INVERTED_PIN, GPIO.OUT)
GPIO.setup(PWM_PIN, GPIO.OUT)

pwm = GPIO.PWM(PWM_PIN, 1000)  # PWM on PWM_PIN with a frequency of 1000 Hz
pwm.start(0)  # Start with 0% duty cycle (motor off)

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri="http://localhost:8080",
    scope="user-read-playback-state,user-modify-playback-state"
))

# Initialize LCD
lcd = CharLCD('PCF8574', 0x27)  # Update I2C address if necessary

# Setup SQLite database
conn = sqlite3.connect('rfid_spotify.db')
c = conn.cursor()
c.execute('''
          CREATE TABLE IF NOT EXISTS tag_to_uri (
              tag_id INTEGER PRIMARY KEY,
              uri TEXT
          )
          ''')
conn.commit()

current_playing = None  # Global variable to track the currently playing track
stop_threads = False    # Global flag to stop all threads


def set_motor(speed, direction):
    """Set motor speed and direction."""
    pwm.ChangeDutyCycle(speed)
    GPIO.output(MOTOR_DIRECTION_PIN, direction)
    GPIO.output(MOTOR_INVERTED_PIN, not direction)


def display_both_lines_with_scroll(line1_message, line2_message, delay=0.3):
    """Display messages simultaneously on both rows of the LCD with scrolling."""
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


def check_playback_status():
    """Thread to monitor Spotify playback status and control the motor."""
    global stop_threads
    while not stop_threads:
        try:
            playback = sp.current_playback()
            if playback and playback.get('is_playing', False):
                set_motor(50, True)  # Motor ON
            else:
                set_motor(0, False)  # Motor OFF
        except Exception as e:
            print(f"Error checking playback status: {e}")
        sleep(1)


def play_song_from_rfid():
    """Thread to handle RFID scanning and play songs."""
    global current_playing, stop_threads
    reader = SimpleMFRC522()
    try:
        while not stop_threads:
            id, _ = reader.read()
            c.execute("SELECT uri FROM tag_to_uri WHERE tag_id=?", (id,))
            result = c.fetchone()
            if result:
                uri = result[0]
                track_name = get_track_name(uri)
                display_both_lines_with_scroll("Playing", track_name, delay=0.3)
                sp.start_playback(device_id=DEVICE_ID, uris=[uri])
                current_playing = uri
            else:
                display_both_lines_with_scroll("Tag Not Found", "Please Register", delay=0.3)
            sleep(1)
    finally:
        print("RFID thread exiting...")


def main():
    """Main thread to run the program."""
    global stop_threads
    try:
        # Start the threads
        playback_thread = threading.Thread(target=check_playback_status, daemon=True)
        rfid_thread = threading.Thread(target=play_song_from_rfid, daemon=True)
        playback_thread.start()
        rfid_thread.start()

        # Keep the main thread running
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("Stopping threads...")
        stop_threads = True
        playback_thread.join()
        rfid_thread.join()
    finally:
        display_both_lines_with_scroll("Cleaning Up", "Goodbye!", delay=0.3)
        set_motor(0, False)
        pwm.stop()
        GPIO.cleanup()
        conn.close()


if __name__ == "__main__":
    main()