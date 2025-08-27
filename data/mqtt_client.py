import json
import logging
import os
import threading
import paho.mqtt.client as mqtt

# TODO revert to /data/options.json
SETTINGS_FILE = "/home/juliend/IdeaProjects/ClapTrap-HA-Addon/data/settings.json"


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

            self.broker_url = mqtt_settings.get('mqtt_host', 'localhost')
            self.broker_port = mqtt_settings.get('mqtt_port', 1883)
            self.username = mqtt_settings.get('mqtt_username', None)
            self.password = mqtt_settings.get('mqtt_password', None)
            self.client_id = mqtt_settings.get('mqtt_client_id', None)
            self.topic = mqtt_settings.get('mqtt_topic', None)
            self.connection = None

    def connect(self):
        if not self.connection:
            self.connection = mqtt.Client(client_id=self.client_id)

            if self.username and self.password:
                self.connection.username_pw_set(self.username, self.password)

            self.connection.connect(self.broker_url, self.broker_port)
            self.connection.loop_start()

    def publish(self, topic, message, retry=0):
        if self.connection:
            self.connection.publish(topic, message)
        elif retry > 3:
            logging.error("Failed to connect to MQTT broker after 3 retries.")
        else:
            self.connect()
            self.publish(topic, message, retry + 1)

    def disconnect(self):
        if self.connection:
            self.connection.loop_stop()
            self.connection.disconnect()