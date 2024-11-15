import paho.mqtt.client as mqtt
import requests
import json
import time
from datetime import datetime

class ThermostatController:
    def __init__(self, mqtt_broker="localhost", mqtt_port=1883, thermostat_ip="192.168.43.100", 
                 mqtt_user=None, mqtt_password=None, client_id="DV_00365729"):
        # MQTT setup
        self.client = mqtt.Client(client_id=client_id)
        if mqtt_user and mqtt_password:
            self.client.username_pw_set(mqtt_user, mqtt_password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        
        # Thermostat REST API endpoints
        self.thermostat_ip = thermostat_ip
        self.control_url = f"http://{thermostat_ip}/aircon/set_control_info"
        self.status_url = f"http://{thermostat_ip}/aircon/get_control_info"
        self.sensor_url = f"http://{thermostat_ip}/aircon/get_sensor_info"

    def connect(self):
        """Connect to MQTT broker and start loop"""
        try:
            print(f"Attempting to connect to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
            self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.client.loop_start()
            print(f"Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
            return True
        except ConnectionRefusedError:
            print("Connection refused. Please check if:")
            print("1. MQTT broker (like Mosquitto) is installed and running")
            print("2. The broker address and port are correct")
            print("3. Any firewall settings are blocking the connection")
            return False
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            return False

    def on_connect(self, client, userdata, flags, rc):
        """Subscribe to control topics when connected"""
        print(f"Connected with result code {rc}")
        # Subscribe to control topics
        topics = [
            "thermostat/control/power",
            "thermostat/control/mode",
            "thermostat/control/temperature",
            "thermostat/control/fan_rate",
            "thermostat/control/fan_direction"
        ]
        for topic in topics:
            client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        topic = msg.topic
        payload = msg.payload.decode()
        print(f"Received message on {topic}: {payload}")

        # Get current status
        current_status = self.get_status()
        if current_status is None:
            return

        # Update only the changed parameter
        if topic == "thermostat/control/power":
            current_status['pow'] = int(payload)
        elif topic == "thermostat/control/mode":
            current_status['mode'] = int(payload)
        elif topic == "thermostat/control/temperature":
            current_status['stemp'] = int(payload)
        elif topic == "thermostat/control/fan_rate":
            current_status['f_rate'] = int(payload)
        elif topic == "thermostat/control/fan_direction":
            current_status['f_dir'] = int(payload)

        # Send updated parameters to thermostat
        self.set_control_info(current_status)

    def get_status(self):
        """Get current thermostat status"""
        try:
            print(f"\nAttempting to get status from: {self.status_url}")
            response = requests.get(self.status_url, timeout=5)  # Added timeout
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
            
            if response.status_code == 200:
                status = self._parse_response(response.text)
                print(f"Parsed status: {status}")
                self.client.publish("thermostat/status", json.dumps(status))
                return status
            else:
                print(f"Error: Received status code {response.status_code}")
                return None
            
        except requests.exceptions.Timeout:
            print("Error: Request timed out. Thermostat not responding.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error getting status: {e}")
            return None

    def get_sensor_info(self):
        """Get sensor information"""
        try:
            response = requests.get(self.sensor_url)
            response.raise_for_status()
            sensor_data = self._parse_response(response.text)
            # Publish sensor data to MQTT
            self.client.publish("thermostat/sensor", json.dumps(sensor_data))
            return sensor_data
        except Exception as e:
            print(f"Error getting sensor info: {e}")
            return None

    def set_control_info(self, params):
        """Set control parameters"""
        try:
            print(f"\nSending control info to: {self.control_url}")
            print(f"Parameters being sent: {params}")
            
            response = requests.get(self.control_url, params=params, timeout=5)
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
            
            if response.status_code == 200:
                print("Successfully set parameters")
                # Get and publish updated status
                self.get_status()
            else:
                print(f"Error: Received status code {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("Error: Request timed out. Thermostat not responding.")
        except requests.exceptions.RequestException as e:
            print(f"Error setting control info: {e}")

    def _parse_response(self, response_text):
        """Parse response from thermostat"""
        params = {}
        for param in response_text.split(','):
            if '=' in param:
                key, value = param.split('=')
                params[key] = value
        return params

    def start_monitoring(self, interval=60):
        """Start periodic monitoring of thermostat status and sensor data"""
        print(f"Starting monitoring (Press Ctrl+C to stop)")
        try:
            while True:
                print("\nFetching current status...")
                status = self.get_status()
                if status:
                    print(f"Current status: {json.dumps(status, indent=2)}")
                
                print("\nFetching sensor data...")
                sensor_data = self.get_sensor_info()
                if sensor_data:
                    print(f"Sensor data: {json.dumps(sensor_data, indent=2)}")
                
                print(f"\nWaiting {interval} seconds before next update...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
            self.client.loop_stop()
        except Exception as e:
            print(f"Error during monitoring: {e}")
            self.client.loop_stop()

# Example usage
if __name__ == "__main__":
    # Create controller instance
    controller = ThermostatController(
        mqtt_broker="localhost",  # or your specific broker IP
        mqtt_port=1883,
        thermostat_ip="192.168.43.100"
    )
    
    # Connect to MQTT broker and only continue if connection successful
    if controller.connect():
        # Start monitoring
        controller.start_monitoring()
    else:
        print("Exiting due to connection failure")