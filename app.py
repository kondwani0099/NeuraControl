import serial
import time
from groq import Groq
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ------------------------------
# Setup Groq AI client
# ------------------------------
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Validate API key
if not GROQ_API_KEY:
    print("❌ Error: GROQ_API_KEY not found in .env file!")
    print("Please check your .env file contains: GROQ_API_KEY=your_api_key_here")
    exit(1)

client = Groq(api_key=GROQ_API_KEY)

# ------------------------------
# Setup Arduino serial connection
# ------------------------------
arduino_port = os.getenv('ARDUINO_PORT', 'COM4')
baud_rate = int(os.getenv('BAUD_RATE', '9600'))

try:
    arduino = serial.Serial(arduino_port, baud_rate, timeout=1)
    time.sleep(2)  # Wait for Arduino to initialize
    print(f"✅ Arduino connected on {arduino_port}")
except Exception as e:
    print(f"❌ Arduino connection failed: {e}")
    print("Running in demo mode...")
    arduino = None

# ------------------------------
# Ask Groq AI
# ------------------------------
completion = client.chat.completions.create(
    model="qwen/qwen3-32b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant. You respond with 'ON' or 'OFF' to control LEDs."},
        {"role": "user", "content": "Turn on the LED if robotics is interesting."}
    ],
    temperature=1,
    max_tokens=50,
    top_p=1,
    stream=True,
    stop=None,
)

# Collect response
response_text = ""
for chunk in completion:
    response_text += chunk.choices[0].delta.content or ""
    print(chunk.choices[0].delta.content or "", end="")

print("\nGroq AI response:", response_text.strip())

# ------------------------------
# Send command to Arduino
# ------------------------------
# ------------------------------
# Send command to Arduino
# ------------------------------
if arduino:
    if "on" in response_text.lower():
        arduino.write(b'1')  # Send '1' to turn LED on
        print("LED turned ON")
    elif "off" in response_text.lower():
        arduino.write(b'0')  # Send '0' to turn LED off
        print("LED turned OFF")
    else:
        print("No valid LED command in response.")
    
    # Close serial connection
    arduino.close()
else:
    print("🎭 Demo mode: Would have sent command to Arduino")
