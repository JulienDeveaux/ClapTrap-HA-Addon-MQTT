import json
import logging
import os
import threading
import paho.mqtt.client as mqtt

SETTINGS_FILE = "/data/options.json"


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)

        return settings
    return None


class MQTTClient:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(MQTTClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            settings = load_settings()

            self.broker_url = settings.get('mqtt_host', 'localhost')
            self.broker_port = settings.get('mqtt_port', 1883)
            self.username = settings.get('mqtt_username', None)
            self.password = settings.get('mqtt_password', None)
            self.client_id = settings.get('mqtt_client_id', None)
            self.base_topic = settings.get('mqtt_topic', 'claptrap')
            self.connection = None

    def connect(self):
        if not self.connection:
            self.connection = mqtt.Client(client_id=self.client_id)

            if self.username and self.password:
                self.connection.username_pw_set(self.username, self.password)

            self.connection.connect(self.broker_url, self.broker_port)
            self.connection.loop_start()

    def publish(self, topic, message, retry=0, retain=False):
        if self.connection:
            self.connection.publish(topic, message, retain=retain)
        elif retry > 3:
            logging.error("Failed to connect to MQTT broker after 3 retries.")
        else:
            self.connect()
            self.publish(topic, message, retry + 1)

    def publish_discovery(self, entity_id, device_name="Clapper", device_class="motion"):
        """
        Publie la config MQTT Discovery pour un binary_sensor
        """

        discovery_topic = f"homeassistant/binary_sensor/Clapper/config"
        payload = {
            "name": None,  # On dérive le nom de l'entité du device
            "device_class": device_class,
            "state_topic": f"{self.base_topic}/Clapper/state",
            "unique_id": f"{entity_id}_sensor",
            "device": {
                "identifiers": [entity_id],
                "name": device_name or entity_id
            }
        }
        self.publish(discovery_topic, json.dumps(payload), retain=True)

    def disconnect(self):
        if self.connection:
            self.connection.loop_stop()
            self.connection.disconnect()