from classify import start_detection, stop_detection
import json
from vban_manager import init_vban_detector as init_vban, cleanup_vban_detector
import os
import logging
import atexit

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Réduire le niveau de log des modules trop verbeux
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# TODO revert to /data/options.json
SETTINGS_FILE = "/home/juliend/IdeaProjects/ClapTrap-HA-Addon/data/settings.json"

# Initialiser le détecteur VBAN
init_vban()

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            print("test_app")
            print(settings)
        return settings
    print(f"Settings file {SETTINGS_FILE} not found.")
    return None

SETTINGS = load_settings()

@atexit.register
def cleanup():
    """Nettoie les ressources lors de l'arrêt"""
    stop_detection_route()
    cleanup_vban_detector()

class VBANSource:
    def __init__(self, name, ip, port, stream_name, enabled=True):
        self.name = name
        self.ip = ip
        self.port = port
        self.stream_name = stream_name
        self.enabled = enabled

    def to_dict(self):
        return {
            "name": self.name,
            "ip": self.ip,
            "port": self.port,
            "stream_name": self.stream_name,
            "enabled": self.enabled
        }

    @staticmethod
    def from_dict(data):
        return VBANSource(
            name=data.get("name", ""),
            ip=data.get("ip", ""),
            port=data.get("port", 6980),
            stream_name=data.get("stream_name", ""),
            enabled=data.get("enabled", True)
        )

def start_detection_route():
    try:
        detection_settings = SETTINGS

        # Vérifier si le microphone est activé
        microphone_enabled = detection_settings.get('microphone', {})
        if isinstance(microphone_enabled, dict):
            microphone_enabled = microphone_enabled.get('enabled', False)
        else:
            microphone_enabled = False

        if not microphone_enabled:
            print("Microphone désactivé - aucune capture audio ne sera effectuée")

        # Préparer les paramètres pour start_detection avec gestion des valeurs null
        try:
            global_settings = detection_settings.get('global', {})
            if not isinstance(global_settings, dict):
                logging.error("global dict is not valid, using empty dict")
                global_settings = {}

            microphone_settings = detection_settings.get('microphone', {})
            if not isinstance(microphone_settings, dict):
                logging.error("microphone dict is not valid, using empty dict")
                microphone_settings = {}

            detection_params = {
                'model': "yamnet.tflite",
                'score_threshold': float(global_settings.get('threshold', '0.2')),
                'overlapping_factor': 0.8,
                'audio_source': microphone_settings.get('audio_source') if microphone_enabled else None,
                'rtsp_url': None
            }

            # Check for RTSP sources first
            rtsp_sources = detection_settings.get('rtsp', [])
            for source in rtsp_sources:
                if source.get('enabled', False):
                    detection_params['audio_source'] = f"rtsp://{source['url']}"
                    detection_params['rtsp_url'] = source['url']
                    logging.info(f"Utilisation de la source RTSP: {source.get('name', 'Unknown')} ({source['url']})")
                    break

            # If no RTSP source is enabled, check for VBAN sources
            if not detection_params['audio_source'] and not microphone_enabled:
                # Vérifier d'abord saved_vban_sources
                saved_vban_sources = detection_settings.get('saved_vban_sources', [])
                if saved_vban_sources:
                    # Utiliser la première source VBAN active
                    for source in saved_vban_sources:
                        if source.get('enabled', True):
                            detection_params['audio_source'] = f"vban://{source['ip']}"
                            logging.info(f"Utilisation de la source VBAN: {source['name']} ({source['ip']})")
                            break
                    else:
                        if not any(source.get('enabled', True) for source in saved_vban_sources):
                            logging.info("Aucune source VBAN active n'est activée")
                else:
                    logging.info("Aucune source VBAN configurée")
        except (ValueError, TypeError) as e:
            logging.error(f"Erreur lors de la préparation des paramètres de détection: {str(e)}")

        # Démarrer la détection
        if start_detection(**detection_params):
            return True
        else:
            raise RuntimeError("Impossible de démarrer la détection")

    except Exception as e:
        logging.error(f"Erreur lors du démarrage de la détection: {str(e)}")
        return False

def stop_detection_route():
    try:
        # Arrêter la détection
        if stop_detection():
            return True
        else:
            raise RuntimeError("Impossible d'arrêter la détection")
    except Exception as e:
        logging.error(f"Erreur lors de l'arrêt de la détection: {str(e)}")
        return False

if __name__ == '__main__':
    try:
        start_detection_route()
    except KeyboardInterrupt:
        logging.info("Arrêt du serveur...")
        stop_detection_route()
        cleanup_vban_detector()
    except Exception as e:
        logging.error(f"Erreur lors du démarrage du serveur: {e}")
        stop_detection_route()
        cleanup_vban_detector()
