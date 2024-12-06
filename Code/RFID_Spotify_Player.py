import threading
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from time import sleep
import sqlite3
from RPLCD.i2c import CharLCD
import queue

# Setup constants
DEVICE_ID = "98bb0735e28656bac098d927d410c3138a4bab8d7970b75"
CLIENT_ID = "fc465222f6a94ee292f29574f20398e9"
CLIENT_SECRET = "b5e442bdbaee418da3c4bab8d7970b75"

# GPIO Pins
MOTOR_DIRECTION_PIN = 16
MOTOR_INVERTED_PIN = 26
PWM_PIN = 12
REGISTER_RFID_TAG = 839325964744
PAUSE_PLAYBACK = 114259767899
PLAY_PLAYBACK = 115686027819
SKIP_PLAYBACK = 389775340099
LCD_LED_PIN = 5
SPEAKER_LED_PIN = 6
MOTOR_LED_PIN = 13
RFID_LED_PIN = 19

# GPIO Setup
GPIO.setmode(GPIO.BCM)

GPIO.setup(SPEAKER_LED_PIN, GPIO.OUT)
GPIO.setup(LCD_LED_PIN, GPIO.OUT)
GPIO.setup(MOTOR_LED_PIN, GPIO.OUT)
GPIO.setup(RFID_LED_PIN, GPIO.OUT)

GPIO.output(LCD_LED_PIN, GPIO.LOW)
GPIO.output(SPEAKER_LED_PIN, GPIO.LOW)
GPIO.output(RFID_LED_PIN, GPIO.LOW)
GPIO.output(MOTOR_LED_PIN, GPIO.LOW)

GPIO.setup(MOTOR_DIRECTION_PIN, GPIO.OUT)
GPIO.setup(MOTOR_INVERTED_PIN, GPIO.OUT)
GPIO.setup(PWM_PIN, GPIO.OUT)

pwm = GPIO.PWM(PWM_PIN, 1000)  # Motor PWM
pwm.start(0)

# Spotify Initialization
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri="http://localhost:8080",
    scope="user-read-playback-state,user-modify-playback-state"
))

# LCD Initialization
lcd = CharLCD('PCF8574', 0x27)  # Update I2C address if necessary

# SQLite Database
conn = sqlite3.connect('rfid_spotify.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
          CREATE TABLE IF NOT EXISTS tag_to_uri (
              tag_id INTEGER PRIMARY KEY,
              uri TEXT
          )
          ''')
conn.commit()

# Global Variables
stop_threads = False
lcd_message_queue = queue.Queue()  # LCD message queue


# LED Control Functions
def set_lcd_led(state):
    GPIO.output(LCD_LED_PIN, GPIO.HIGH if state else GPIO.LOW)


def set_motor_led(state):
    GPIO.output(MOTOR_LED_PIN, GPIO.HIGH if state else GPIO.LOW)


def set_speaker_led(state):
    GPIO.output(SPEAKER_LED_PIN, GPIO.HIGH if state else GPIO.LOW)


def set_rfid_led(state):
    GPIO.output(RFID_LED_PIN, GPIO.HIGH if state else GPIO.LOW)


# Motor Control
def set_motor(speed, direction):
    if speed > 0:
        set_motor_led(True)
    else:
        set_motor_led(False)
    pwm.ChangeDutyCycle(speed)
    GPIO.output(MOTOR_DIRECTION_PIN, direction)
    GPIO.output(MOTOR_INVERTED_PIN, not direction)


# LCD Message Queue
def display_message(line1, line2, duration=3):
    lcd_message_queue.put((line1, line2, duration))


def process_lcd_messages():
    """Process LCD messages, falling back to current song display."""
    current_uri = None
    while not stop_threads:
        try:
            if not lcd_message_queue.empty():
                line1, line2, duration = lcd_message_queue.get()
                lcd.clear()
                lcd.cursor_pos = (0, 0)
                lcd.write_string(line1[:16])
                lcd.cursor_pos = (1, 0)
                lcd.write_string(line2[:16])
                set_lcd_led(True)
                sleep(duration)
                set_lcd_led(False)
            else:
                playback = sp.current_playback()
                if playback and playback.get('item'):
                    track = playback['item']
                    uri = track['uri']
                    if uri != current_uri:
                        current_uri = uri
                        song_name = track['name']
                        artist_name = ", ".join(artist['name'] for artist in track['artists'])
                        lcd.clear()
                        lcd.cursor_pos = (0, 0)
                        lcd.write_string(song_name[:16])
                        lcd.cursor_pos = (1, 0)
                        lcd.write_string(artist_name[:16])
                sleep(5)
        except Exception as e:
            print(f"Error processing LCD messages: {e}")
            sleep(5)


# Spotify Track Info
def get_track_name():
    try:
        track_info = sp.current_playback()
        if track_info:
            return track_info['item']['name']
    except Exception as e:
        print(f"Error retrieving track info: {e}")
    return "Unknown Track"


# Playback Status
def check_playback_status():
    """Monitor Spotify playback and control motor."""
    global stop_threads
    while not stop_threads:
        try:
            playback = sp.current_playback()
            if playback and playback.get('is_playing', False):
                set_motor(34, True)
                set_speaker_led(True)
            else:
                set_motor(0, False)
                set_speaker_led(False)
        except Exception as e:
            print(f"Error checking playback status: {e}")
        sleep(1)


# Register RFID Tags
def register_tag(tag_id, uri):
    try:
        c.execute("INSERT OR REPLACE INTO tag_to_uri (tag_id, uri) VALUES (?, ?)", (tag_id, uri))
        conn.commit()
        display_message("Tag Registered", "Successfully!", 5)
    except Exception as e:
        print(f"Error registering tag: {e}")
        display_message("Registration Failed", "Try Again", 5)


# RFID Playback
def play_song_from_rfid():
    global stop_threads
    reader = SimpleMFRC522()
    try:
        while not stop_threads:
            set_rfid_led(True)
            id, _ = reader.read()

            if id == PAUSE_PLAYBACK:
                sp.pause_playback(device_id=DEVICE_ID)
                set_motor(0, False)
                display_message("Playback", "Paused", 5)
                continue
            if id == PLAY_PLAYBACK:
                sp.start_playback(device_id=DEVICE_ID)
                display_message("Playback", "Resumed", 5)
                continue
            if id == SKIP_PLAYBACK:
                sp.next_track(device_id=DEVICE_ID)
                display_message("Skipping", "Next Track", 5)
                continue

            if id == REGISTER_RFID_TAG:
                display_message("Registration", "Mode Active", 5)
                while True:
                    id, _ = reader.read()
                    if id != REGISTER_RFID_TAG:
                        uri = sp.current_playback()
                        if uri:
                            album_uri = uri['item']['album']['uri']
                            register_tag(id, album_uri)
                        else:
                            display_message("No Playback Found", "Start Spotify", 5)
                        break
                continue

            c.execute("SELECT uri FROM tag_to_uri WHERE tag_id=?", (id,))
            result = c.fetchone()
            if result:
                uri = result[0]
                sp.start_playback(device_id=DEVICE_ID, context_uri=uri)
                track_name = get_track_name()
                display_message("Playing", track_name[:16], 5)
            else:
                display_message("Tag Not Found", "Please Register", 5)
            sleep(1)
    finally:
        set_rfid_led(False)


# Main Program
def main():
    global stop_threads
    try:
        playback_thread = threading.Thread(target=check_playback_status, daemon=True)
        rfid_thread = threading.Thread(target=play_song_from_rfid, daemon=True)
        lcd_thread = threading.Thread(target=process_lcd_messages, daemon=True)

        playback_thread.start()
        rfid_thread.start()
        lcd_thread.start()

        while True:
            sleep(1)
    except KeyboardInterrupt:
        stop_threads = True
        playback_thread.join()
        rfid_thread.join()
        lcd_thread.join()
    finally:
        lcd.clear()
        GPIO.cleanup()
        conn.close()


if __name__ == "__main__":
    main()
