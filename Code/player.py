#!/usr/bin/env python
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from time import sleep
import sqlite3

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
GPIO.setup(20, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Pause button

pwm = GPIO.PWM(PWM_PIN, 1000)  # PWM on PWM_PIN with a frequency of 1000 Hz
pwm.start(0)  # Start with 0% duty cycle (motor off)

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri="http://localhost:8080",
    scope="user-read-playback-state,user-modify-playback-state"
))

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

def set_motor(speed, direction):
    """Set motor speed and direction."""
    pwm.ChangeDutyCycle(speed)
    GPIO.output(MOTOR_DIRECTION_PIN, direction)  # Set motor direction
    GPIO.output(MOTOR_INVERTED_PIN, not direction)  # Set inverted direction

def is_playing():
    """Check if a song is currently playing."""
    try:
        playback_info = sp.current_playback()
        if playback_info and playback_info.get('is_playing', False):
            print("Playback status: is playing (TRUE)")
            return True
        return False
    except Exception as e:
        print(f"Error checking playback status: {e}")
        return False

def pause_playback():
    """Pause playback on Spotify and stop the motor."""
    sp.pause_playback(device_id=DEVICE_ID)
    set_motor(0, False)  # Stop the motor
    print("Playback paused.")

def register_tag(tag_id, uri):
    """Register a new RFID tag with the corresponding URI in the database."""
    c.execute("INSERT OR REPLACE INTO tag_to_uri (tag_id, uri) VALUES (?, ?)", (tag_id, uri))
    conn.commit()
    print(f"Registered tag {tag_id} with URI {uri}.")

def is_tag_registered(tag_id):
    """Check if the RFID tag is already registered in the database."""
    c.execute("SELECT * FROM tag_to_uri WHERE tag_id=?", (tag_id,))
    result = c.fetchone()
    return result is not None

def get_current_playing_uri():
    """Retrieve the URI of the currently playing track."""
    try:
        playback_info = sp.current_playback()
        if playback_info and playback_info.get('is_playing', False):
            track_uri = playback_info['item']['uri']  # Extract the URI
            print(f"Current track URI: {track_uri}")
            return track_uri
        else:
            print("No track is currently playing.")
            return None
    except Exception as e:
        print(f"Error retrieving current playback info: {e}")
        return None

def play_from_tag(tag_id):
    """Play the track associated with the scanned tag."""
    c.execute("SELECT uri FROM tag_to_uri WHERE tag_id=?", (tag_id,))
    result = c.fetchone()
    if result:
        track_uri = result[0]
        sp.start_playback(device_id=DEVICE_ID, uris=[track_uri])
        print(f"Started playing {track_uri} for tag {tag_id}")

        sleep(1)  # Allow time for playback to start
        #if is_playing():
        #    set_motor(50, True)  # Start the motor
        #else:
        #    set_motor(0, False)  # Ensure motor is off
    else:
        print("Tag not registered.")
        set_motor(0, False)  # Stop motor if no valid tag is found
        
def clear_database():
    c.execute("DELETE FROM tag_to_uri")
    conn.commit()
    print("All entries have been removed from the database.")
    
# Main loop
try:
    reader = SimpleMFRC522()
    print("Waiting for record scan...")
    while True:
        id, text = reader.read()
        print(f"Card Value is: {id}")
        #clear_database()
        # Check if the scanned RFID is the register tag
        if id == REGISTER_RFID_TAG:
            print("Entered registration mode!")
            reg_mode = True
            while reg_mode:  # Enter registration mode
                id, text = reader.read()
                print(f"Card Value is: {id}")
                if (id != REGISTER_RFID_TAG and id != PAUSE_PLAYBACK):
                    uri = get_current_playing_uri()
                    if uri:
                        if is_tag_registered(id):
                            overwrite = input("This tag is already registered. Overwrite? (y/n): ")
                            if overwrite.lower() != 'y':
                                print("Registration cancelled.")
                                reg_mode = False  # Cancel registration if user chooses not to overwrite
                                continue
                        register_tag(id, uri)  # Register the RFID tag with the current track's URI
                        
                        print("Press a different tag to exit registration mode.")
                    else:
                        print("Failed to retrieve the URI. Please start playback on Spotify.")
                    
                # Wait for the next RFID scan
                #id, text = reader.read()
                #print(f"Card Value is: {id}")
                
                # If a different tag is scanned, exit registration mode
                if id != REGISTER_RFID_TAG:
                    print("Exiting registration mode.")
                    break  # Exit the loop and continue normal operations
                sleep(1)  # Small delay to avoid rapid polling
        elif id == PAUSE_PLAYBACK:
            pause_playback()  # Pause the playback and stop the motor
        
        elif (id != PAUSE_PLAYBACK and id != REGISTER_RFID_TAG):
            play_from_tag(id)
            
        #sp.transfer_playback(device_id=DEVICE_ID, force_play=False)

        #if id == 839325964744:
        #    sp.start_playback(device_id=DEVICE_ID, uris=['spotify:track:6OHOYEMQfPKWZY4Uxxybnh'])
        #    sleep(1)  # Allow time for playback to start

        #elif id == PAUSE_PLAYBACK:
        #    pause_playback()  # Pause the playback and stop the motor
        
        #elif (id != PAUSE_PLAYBACK and id != REGISTER_RFID_TAG):
        #    play_from_tag(id)
            
        # Keep the motor running while the song is playing
        if is_playing():
            set_motor(50, True)  # Set speed and direction
            sleep(1)  # Check every second to keep the loop responsive
        else:
            # Stop the motor when the song ends or is paused
            set_motor(0, False)

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    print("Cleaning up...")
    set_motor(0, False)
    pwm.stop()  # Stop the PWM signal
    GPIO.cleanup()  # Cleanup GPIO settings
    conn.close()  # Close the database connection
