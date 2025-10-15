import streamlit as st
import serial
import serial.tools.list_ports
import time
from groq import Groq
import json
import random
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="NeuraControl - Smart Home Assistant",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .device-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .temperature-card {
        background: linear-gradient(135deg, #ff6b6b 0%, #feca57 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .ai-response-card {
        background: linear-gradient(135deg, #48dbfb 0%, #0abde3 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'temperature_data' not in st.session_state:
    st.session_state.temperature_data = []
    # Generate some sample temperature data
    for i in range(24):
        timestamp = datetime.now() - timedelta(hours=23-i)
        temp = 20 + random.uniform(-3, 8)  # Temperature between 17-28°C
        st.session_state.temperature_data.append({
            'timestamp': timestamp,
            'temperature': temp,
            'humidity': random.uniform(40, 70)
        })

if 'device_states' not in st.session_state:
    st.session_state.device_states = {
        'led': False,
        'fan': False,
        'heater': False,
        'lights': False
    }

if 'ai_responses' not in st.session_state:
    st.session_state.ai_responses = []

if 'demo_mode' not in st.session_state:
    st.session_state.demo_mode = False

# Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
ARDUINO_PORT = os.getenv('ARDUINO_PORT', 'COM4')
BAUD_RATE = int(os.getenv('BAUD_RATE', '9600'))
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
DEMO_MODE = os.getenv('DEMO_MODE', 'False').lower() == 'true'

# Validate API key
if not GROQ_API_KEY:
    st.error("❌ GROQ_API_KEY not found in .env file!")
    st.stop()

# Initialize Groq client
@st.cache_resource
def init_groq_client():
    return Groq(api_key=GROQ_API_KEY)

client = init_groq_client()

def get_available_ports():
    """Get list of available COM ports"""
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

def get_arduino_connection(port=None):
    """Get Arduino serial connection with error handling"""
    if port is None:
        port = ARDUINO_PORT
    
    try:
        # First, try to close any existing connection on this port
        try:
            test_conn = serial.Serial(port, BAUD_RATE, timeout=0.1)
            test_conn.close()
            time.sleep(0.5)
        except:
            pass
        
        # Now try to establish connection
        arduino = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2)
        return arduino
    except serial.SerialException as e:
        if "PermissionError" in str(e):
            st.error(f"⚠️ Port {port} is busy. Please:\n1. Close Arduino IDE\n2. Disconnect and reconnect Arduino\n3. Try a different COM port")
        else:
            st.error(f"❌ Arduino connection failed on {port}: {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None

def send_ai_prompt(prompt):
    """Send prompt to Groq AI and get response"""
    try:
        completion = client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[
                {"role": "system", "content": "You are a smart home assistant. Respond with device commands like 'LED ON', 'LED OFF', 'FAN ON', 'FAN OFF', 'HEATER ON', 'HEATER OFF', 'LIGHTS ON', 'LIGHTS OFF' based on user requests. Be helpful and explain your reasoning."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150,
            top_p=1,
            stream=False,
            stop=None,
        )
        
        response = completion.choices[0].message.content
        return response
    except Exception as e:
        return f"AI Error: {str(e)}"

def parse_device_commands(response):
    """Parse AI response for device commands"""
    commands = {}
    response_lower = response.lower()
    
    # Check for LED commands
    if 'led on' in response_lower:
        commands['led'] = True
    elif 'led off' in response_lower:
        commands['led'] = False
    
    # Check for FAN commands
    if 'fan on' in response_lower:
        commands['fan'] = True
    elif 'fan off' in response_lower:
        commands['fan'] = False
    
    # Check for HEATER commands
    if 'heater on' in response_lower:
        commands['heater'] = True
    elif 'heater off' in response_lower:
        commands['heater'] = False
    
    # Check for LIGHTS commands
    if 'lights on' in response_lower:
        commands['lights'] = True
    elif 'lights off' in response_lower:
        commands['lights'] = False
    
    return commands

def send_arduino_command(device, state):
    """Send command to Arduino with improved error handling"""
    if st.session_state.demo_mode:
        st.success(f"🎮 Demo: {device.upper()} turned {'ON' if state else 'OFF'}")
        return True
    
    arduino = get_arduino_connection()
    if arduino:
        try:
            # Map devices to Arduino commands
            device_map = {
                'led': '1' if state else '0',
                'fan': '3' if state else '2',
                'heater': '5' if state else '4',
                'lights': '7' if state else '6'
            }
            
            command = device_map.get(device, '0')
            arduino.write(command.encode())
            time.sleep(0.1)  # Small delay for Arduino to process
            arduino.close()
            st.success(f"✅ {device.upper()} turned {'ON' if state else 'OFF'}")
            return True
        except Exception as e:
            st.error(f"❌ Command failed: {str(e)}")
            try:
                arduino.close()
            except:
                pass
            return False
    else:
        st.warning(f"⚠️ Arduino not connected - Command simulated: {device.upper()} {'ON' if state else 'OFF'}")
        return False

# Main header
st.markdown('<h1 class="main-header">🏠 NeuraControl - Smart Home Assistant</h1>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("🔧 System Settings")
    
    # Arduino Port Selection
    st.subheader("🔌 Arduino Settings")
    available_ports = get_available_ports()
    
    if available_ports:
        selected_port = st.selectbox(
            "Select COM Port:",
            available_ports,
            index=available_ports.index(ARDUINO_PORT) if ARDUINO_PORT in available_ports else 0
        )
        
        # Update global port if changed
        if selected_port != ARDUINO_PORT:
            ARDUINO_PORT = selected_port
    else:
        st.warning("⚠️ No COM ports detected")
        selected_port = ARDUINO_PORT
    
    # Connection test button
    if st.button("🔄 Test Connection"):
        test_conn = get_arduino_connection(selected_port)
        if test_conn:
            st.success("✅ Connection successful!")
            test_conn.close()
        else:
            st.error("❌ Connection failed")
    
    # Demo mode toggle
    st.subheader("🎮 Demo Mode")
    st.session_state.demo_mode = st.toggle(
        "Enable Demo Mode", 
        value=st.session_state.demo_mode,
        help="Run app without Arduino connection for testing"
    )
    
    if st.session_state.demo_mode:
        st.info("🎮 Demo mode enabled - Commands will be simulated")
    
    # Connection status
    st.subheader("📡 Connection Status")
    if not st.session_state.demo_mode:
        arduino_status = get_arduino_connection() is not None
        
        if arduino_status:
            st.success("✅ Arduino Connected")
        else:
            st.error("❌ Arduino Disconnected")
            
            # Troubleshooting tips
            with st.expander("🔧 Troubleshooting"):
                st.write("""
                **Common solutions:**
                1. Close Arduino IDE completely
                2. Unplug and replug Arduino USB cable
                3. Try a different COM port
                4. Check if another program is using the port
                5. Restart your computer if needed
                
                **Available ports:** """ + ", ".join(available_ports) if available_ports else "None detected")
    else:
        st.info("🎮 Demo Mode Active")
    
    st.success("✅ Groq AI Connected")
    
    # System info
    st.subheader("📊 System Info")
    st.info(f"**Port:** {selected_port}")
    st.info(f"**Baud Rate:** {BAUD_RATE}")
    st.info(f"**AI Model:** llama3-8b-8192")
    st.info(f"**Available Ports:** {len(available_ports)}")
    
    # Configuration source
    st.subheader("⚙️ Configuration")
    if os.path.exists('.env'):
        st.success("✅ Loading from .env file")
    else:
        st.warning("⚠️ No .env file found")
    
    if DEBUG_MODE:
        st.info("🐛 Debug mode enabled")
    
    if DEMO_MODE:
        st.info("🎭 Demo mode enabled")

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    # AI Control Section
    st.header("🤖 AI Voice Control")
    
    # Text input for AI commands
    user_prompt = st.text_area(
        "Enter your command:",
        placeholder="e.g., 'Turn on the lights and set temperature to 22 degrees'",
        height=100
    )
    
    col_send, col_clear = st.columns([1, 1])
    
    with col_send:
        if st.button("🚀 Send Command", use_container_width=True):
            if user_prompt:
                with st.spinner("🧠 AI is thinking..."):
                    ai_response = send_ai_prompt(user_prompt)
                    st.session_state.ai_responses.append({
                        'timestamp': datetime.now(),
                        'prompt': user_prompt,
                        'response': ai_response
                    })
                    
                    # Parse and execute commands
                    commands = parse_device_commands(ai_response)
                    for device, state in commands.items():
                        st.session_state.device_states[device] = state
                        send_arduino_command(device, state)
                
                st.success("✅ Command processed!")
    
    with col_clear:
        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.ai_responses = []
            st.rerun()
    
    # Display AI responses
    if st.session_state.ai_responses:
        st.subheader("💬 AI Responses")
        for response in reversed(st.session_state.ai_responses[-3:]):  # Show last 3 responses
            with st.expander(f"🕒 {response['timestamp'].strftime('%H:%M:%S')} - {response['prompt'][:50]}..."):
                st.markdown(f"""
                <div class="ai-response-card">
                    <strong>🤖 AI Response:</strong><br>
                    {response['response']}
                </div>
                """, unsafe_allow_html=True)

with col2:
    # Temperature monitoring
    st.header("🌡️ Temperature Sensor")
    
    # Current temperature (simulated)
    current_temp = st.session_state.temperature_data[-1]['temperature']
    current_humidity = st.session_state.temperature_data[-1]['humidity']
    
    # Temperature display
    st.markdown(f"""
    <div class="temperature-card">
        <h3>🌡️ Current Temperature</h3>
        <h1>{current_temp:.1f}°C</h1>
        <p>💧 Humidity: {current_humidity:.1f}%</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Temperature trend
    if len(st.session_state.temperature_data) > 1:
        temp_diff = current_temp - st.session_state.temperature_data[-2]['temperature']
        trend = "📈" if temp_diff > 0 else "📉" if temp_diff < 0 else "➡️"
        st.metric("Trend", f"{temp_diff:+.1f}°C", delta=f"{temp_diff:.2f}")

# Device Control Cards
st.header("🏠 Device Control")

# Create device control cards
devices = [
    {"name": "LED", "key": "led", "icon": "💡", "color": "#ff6b6b"},
    {"name": "Fan", "key": "fan", "icon": "🌀", "color": "#74b9ff"},
    {"name": "Heater", "key": "heater", "icon": "🔥", "color": "#fd79a8"},
    {"name": "Lights", "key": "lights", "icon": "🏮", "color": "#fdcb6e"}
]

device_cols = st.columns(4)

for i, device in enumerate(devices):
    with device_cols[i]:
        current_state = st.session_state.device_states[device['key']]
        status_text = "ON" if current_state else "OFF"
        status_color = "#27ae60" if current_state else "#e74c3c"
        
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {device['color']} 0%, {device['color']}aa 100%); 
                    padding: 1.5rem; border-radius: 15px; color: white; margin: 1rem 0;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center;">
            <h2>{device['icon']}</h2>
            <h3>{device['name']}</h3>
            <h4 style="color: {status_color};">{status_text}</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Toggle buttons
        col_on, col_off = st.columns(2)
        with col_on:
            if st.button(f"Turn ON", key=f"{device['key']}_on", use_container_width=True):
                st.session_state.device_states[device['key']] = True
                send_arduino_command(device['key'], True)
                st.rerun()
        
        with col_off:
            if st.button(f"Turn OFF", key=f"{device['key']}_off", use_container_width=True):
                st.session_state.device_states[device['key']] = False
                send_arduino_command(device['key'], False)
                st.rerun()

# Temperature chart
st.header("📈 Temperature History")

df = pd.DataFrame(st.session_state.temperature_data)
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['temperature'],
    mode='lines+markers',
    name='Temperature (°C)',
    line=dict(color='#ff6b6b', width=3),
    marker=dict(size=6)
))

fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['humidity'],
    mode='lines+markers',
    name='Humidity (%)',
    line=dict(color='#74b9ff', width=3),
    marker=dict(size=6),
    yaxis='y2'
))

fig.update_layout(
    title='Temperature and Humidity Over Time',
    xaxis_title='Time',
    yaxis_title='Temperature (°C)',
    yaxis2=dict(
        title='Humidity (%)',
        overlaying='y',
        side='right'
    ),
    hovermode='x unified',
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
)

st.plotly_chart(fig, use_container_width=True)

# System Statistics
st.header("📊 System Statistics")

stats_cols = st.columns(4)

with stats_cols[0]:
    active_devices = sum(st.session_state.device_states.values())
    st.metric("Active Devices", active_devices, delta=None)

with stats_cols[1]:
    total_commands = len(st.session_state.ai_responses)
    st.metric("AI Commands", total_commands, delta=None)

with stats_cols[2]:
    avg_temp = sum([data['temperature'] for data in st.session_state.temperature_data[-6:]]) / 6
    st.metric("Avg Temp (6h)", f"{avg_temp:.1f}°C", delta=None)

with stats_cols[3]:
    uptime = "99.5%"  # Simulated uptime
    st.metric("System Uptime", uptime, delta=None)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "🏠 NeuraControl Smart Home Assistant | Powered by Groq AI & Arduino"
    "</div>", 
    unsafe_allow_html=True
)