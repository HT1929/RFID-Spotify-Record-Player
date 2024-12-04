import RPi.GPIO as GPIO
import time

# Setup GPIO pins for motor control
MOTOR_DIRECTION_PIN = 16
MOTOR_INVERTED_PIN = 26
PWM_PIN = 12

GPIO.setmode(GPIO.BCM)
GPIO.setup(MOTOR_DIRECTION_PIN, GPIO.OUT)
GPIO.setup(MOTOR_INVERTED_PIN, GPIO.OUT)
GPIO.setup(PWM_PIN, GPIO.OUT)

pwm = GPIO.PWM(PWM_PIN, 1000)  # PWM on PWM_PIN with a frequency of 1000 Hz
pwm.start(0)  # Start with 0% duty cycle (motor off)

def test_motor():
    """Test the motor control."""
    try:
        print("Motor Test - Forward")
        GPIO.output(MOTOR_DIRECTION_PIN, True)
        GPIO.output(MOTOR_INVERTED_PIN, False)
        pwm.ChangeDutyCycle(50)  # Set motor speed to 50%
        time.sleep(5)  # Run motor for 5 seconds
        
        print("Motor Test - Reverse")
        GPIO.output(MOTOR_DIRECTION_PIN, False)
        GPIO.output(MOTOR_INVERTED_PIN, True)
        pwm.ChangeDutyCycle(50)  # Set motor speed to 50%
        time.sleep(5)  # Run motor for 5 seconds
        
        print("Motor Test - Stop")
        pwm.ChangeDutyCycle(0)  # Stop the motor
    except Exception as e:
        print(f"Error during motor test: {e}")
    finally:
        pwm.stop()
        GPIO.cleanup()

if __name__ == "__main__":
    test_motor()
