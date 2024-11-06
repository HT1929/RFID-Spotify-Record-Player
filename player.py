#!/usr/bin/env python
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from time import sleep

# Setup constants and GPIO
DEVICE_ID = "98bb0735e28656bac098d927d410c3138a4b5bca"
CLIENT_ID = "fc465222f6a94ee292f29574f20398e9"
CLIENT_SECRET = "b5e442bdbaee418da3c4bab8d7970b75"
GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.OUT)
GPIO.setup(26, GPIO.OUT)
GPIO.setup(12, GPIO.OUT)
pwm = GPIO.PWM(12, 1000)
pwm.start(0)

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID,
                                               client_secret=CLIENT_SECRET,
                                               redirect_uri="http://localhost:8080",
                                               scope="user-read-playback-state,user-modify-playback-state"))

def set_motor(speed, direction):
    pwm.ChangeDutyCycle(speed)
    GPIO.output(16, direction)
    GPIO.output(26, not direction)

def is_playing():
    try:
        playback_info = sp.current_playback()
        if playback_info and playback_info.get('is_playing', False ):
            print(f"is playing (TRUE)")
            return True
        #return False
    except Exception as e:
        print(f"Error checking playback status: {e}")
        return False

# Main loop
try:
    reader = SimpleMFRC522()
    print("Waiting for record scan...")
    while True:
        id, text = reader.read()
        print(f"Card Value is: {id}")
        sp.transfer_playback(device_id=DEVICE_ID, force_play=False)

        if id == 839325964744:
            sp.start_playback(device_id=DEVICE_ID, uris=['spotify:track:6OHOYEMQfPKWZY4Uxxybnh'])
            #set_motor(50, True)
            #playback_info = sp.current_playback()
            #print(playback_info)
            
        elif id == 682607722456:
            sp.pause_playback(device_id=DEVICE_ID)
            set_motor(0, False)              
            #sp.start_playback(device_id=DEVICE_ID, context_uri='spotify:album:0JGOiO34nwfUdDrD612dOp')
        
        playback_info = sp.current_playback()
        print(playback_info)
            
        if is_playing():
            set_motor(50, True)
            sleep(1)
        else:
            set_motor(0, False)

        sleep(1)  # Reduce sleep if needed for responsiveness

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    print("Cleaning up...")
    set_motor(0,False)
    pwm.stop()
    GPIO.cleanup()