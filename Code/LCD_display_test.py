from RPLCD.i2c import CharLCD
import time

def test_lcd():
    """Test the LCD display."""
    lcd = CharLCD('PCF8574', 0x27)  # Update I2C address if necessary
    
    try:
        lcd.clear()
        lcd.write_string("Testing LCD...")
        time.sleep(2)
        lcd.clear()
        lcd.write_string("Test Complete!")
    except Exception as e:
        print(f"Error with LCD: {e}")
    finally:
        lcd.clear()

if __name__ == "__main__":
    test_lcd()
