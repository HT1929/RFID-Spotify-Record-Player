import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522

def test_rfid_reader():
    """Test the RFID reader to read tags."""
    GPIO.setmode(GPIO.BCM)
    reader = SimpleMFRC522()

    try:
        print("Place an RFID tag near the reader.")
        id, text = reader.read()
        print(f"Tag ID: {id}")
        print(f"Tag Text: {text}")
    except Exception as e:
        print(f"Error reading RFID: {e}")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    test_rfid_reader()



