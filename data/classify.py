import subprocess
import time
import ffmpeg
import logging
import numpy as np
import sounddevice as sd
import json
import os
import sys
import threading

from mqtt_client import MQTTClient
from vban_manager import get_vban_detector  # Import the get_vban_detector function
import warnings
from audio_detector import AudioDetector

# Configuration du logging en DEBUG
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

SETTINGS_FILE = "/data/options.json"

warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf.symbol_database")

# Variables globales
detection_running = False
classifier = None
record = None
model = "yamnet.tflite"
output_file = "recorded_audio.wav"
current_audio_source = None
_socketio = None  # Renamed to _socketio to avoid conflict with parameter

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
        logging.basicConfig(level=settings.get('log_level', 'info'))
        return settings
    return None

SETTINGS = load_settings()

# Charger les paramètres depuis settings.json
try:
    settings = SETTINGS
        
    # Récupérer la source audio depuis la section microphone
    microphone_settings = settings.get('microphone', {})
    if microphone_settings is None:
        microphone_settings = {}
    AUDIO_SOURCE = microphone_settings.get('audio_source')
    
    # Ne pas lever d'erreur si audio_source n'est pas défini, on le gérera au moment de start_detection
    if not AUDIO_SOURCE:
        logging.warning("Aucune source audio n'est définie dans settings.json")
        
    # Récupérer les paramètres globaux avec des valeurs par défaut
    global_settings = settings.get('global', {})
    if global_settings is None:
        global_settings = {}
        
    THRESHOLD = float(global_settings.get('threshold', 0.5))
    DELAY = float(global_settings.get('delay', 2))
    CHUNK_DURATION = float(global_settings.get('chunk_duration', 0.5))
    BUFFER_DURATION = float(global_settings.get('buffer_duration', 1.0))
    
except FileNotFoundError:
    logging.warning("Le fichier settings.json n'existe pas, utilisation des valeurs par défaut")
    AUDIO_SOURCE = None
    THRESHOLD = 0.5
    DELAY = 2.0
    CHUNK_DURATION = 0.5
    BUFFER_DURATION = 1.0
except json.JSONDecodeError:
    logging.error("Le fichier settings.json est mal formaté")
    raise
except Exception as e:
    logging.error(f"Erreur lors du chargement des paramètres: {str(e)}")
    raise

# Charger les flux RTSP
try:
    settings_data = SETTINGS
    fluxes = settings_data.get('rtsp', {})
except FileNotFoundError:
    logging.warning("Le fichier settings.json n'existe pas, aucun flux RTSP ne sera chargé")
    fluxes = {}
except json.JSONDecodeError:
    logging.error("Le fichier settings.json est mal formaté")
    fluxes = {}
except Exception as e:
    logging.error(f"Erreur lors du chargement des flux RTSP: {str(e)}")
    fluxes = {}

def read_audio_from_rtsp(rtsp_url, buffer_size, sampling_rate):
    """Lit un flux RTSP audio en continu sans buffer fichier"""
    try:
        # Configuration du processus ffmpeg pour lire le flux RTSP
        process = (
            ffmpeg
            .input(rtsp_url)
            .output('pipe:', 
                   format='f32le',  # Format PCM 32-bit float
                   acodec='pcm_f32le', 
                   ac=1,  # Mono
                   ar=sampling_rate,
                   buffer_size='64k'  # Réduire la taille du buffer
            )
            .run_async(pipe_stdout=True, pipe_stderr=True)
        )

        while True:
            # Lecture des données audio par blocs
            in_bytes = process.stdout.read(buffer_size * 4)  # 4 bytes par sample float32
            if not in_bytes:
                break
                
            # Conversion en numpy array
            audio_chunk = np.frombuffer(in_bytes, np.float32)
            
            if len(audio_chunk) > 0:
                yield audio_chunk.reshape(-1, 1)
            
    except Exception as e:
        logging.error(f"Erreur lors de la lecture RTSP: {e}")
        yield None
    finally:
        if process:
            process.kill()

def start_detection(
    model,
    score_threshold: float,
    overlapping_factor,
    audio_source: str,
    rtsp_url: str = None,
):
    global detection_running, classifier, record, current_audio_source, _socketio
    
    try:
        if detection_running:
            return False

        # Recharger les paramètres pour avoir les dernières modifications
        settings = SETTINGS
        if settings:
            microphone_settings = settings.get('microphone', {})
            if isinstance(microphone_settings, dict) and microphone_settings.get('enabled', False):
                # Utiliser les paramètres du microphone les plus récents
                audio_source = microphone_settings.get('audio_source')
                logging.info(f"Utilisation du microphone: {audio_source}")

        detection_running = True
        current_audio_source = audio_source

        if (overlapping_factor <= 0) or (overlapping_factor >= 1.0):
            raise ValueError("Overlapping factor must be between 0 and 1.")

        if (score_threshold < 0) or (score_threshold > 1.0):
            raise ValueError("Score threshold must be between (inclusive) 0 et 1.")

        # Démarrer la détection dans un thread séparé
        detection_thread = threading.Thread(target=run_detection, args=(
            model,
            audio_source,
            rtsp_url
        ))
        detection_thread.daemon = True
        detection_thread.start()

        while detection_thread.is_alive():
            time.sleep(0.1)
            if not detection_running:
                logging.info("Starting Again Detection Thread")
                detection_thread = threading.Thread(target=run_detection, args=(
                    model,
                    audio_source,
                    rtsp_url
                ))
                detection_thread.daemon = True
                detection_thread.start()

        return True
        
    except Exception as e:
        logging.error(f"Erreur pendant le démarrage de la détection: {e}")
        detection_running = False
        return False

def get_sample_rate(audio_source, rtsp_url):
    if audio_source.startswith("rtsp"):
        """Use ffprobe to get sample rate from RTSP stream."""
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-show_entries', 'stream=sample_rate',
            '-select_streams', 'a:0',
            '-of', 'json',
            rtsp_url
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                print(data)
                for stream in data.get('streams', []):
                    rate = stream.get('sample_rate')
                    if rate and rate != 'N/A':
                        logging.info(f"Sample rate detected from RTSP: {rate}")
                    return int(rate)
            logging.warning("Could not determine sample rate from RTSP stream, using fallback 16000 Hz")
            return 16000
        except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, FileNotFoundError):
            logging.warning("ffprobe not available or failed, using fallback sample rate 16000 Hz")
            return 16000
    else:
        logging.info("Using default sample rate 16000 Hz for non-RTSP source")
        return 16000

def run_detection(model, audio_source, rtsp_url):
    """Fonction qui exécute la détection dans un thread séparé"""
    try:
        # Initialiser le détecteur audio
        sample_rate = get_sample_rate(audio_source, rtsp_url)
        detector = AudioDetector(model, sample_rate=sample_rate, buffer_duration=1.0)
        detector.initialize()
        
        def create_detection_callback(source_name):
            def handle_detection(detection_data):
                try:
                    logging.info(f"CLAP détecté sur {source_name} avec score {detection_data['score']} at {detection_data['timestamp']}")

                    # Envoyer l'événement via MQTT
                    mqtt_client = MQTTClient()
                    mqtt_client.publish(source_name, 'on')
                except Exception as e:
                    logging.error(f"Erreur lors de l'envoi de l'événement clap pour {source_name}: {str(e)}")
            return handle_detection
        
        def create_labels_callback(source_name):
            def handle_labels(labels):
                logging.debug(f"Labels détectés sur {source_name}: {labels}")
            return handle_labels
        
        # Vérifier si une source audio est configurée
        if not audio_source:
            logging.error("Aucune source audio n'est configurée ou active")
            return False
            
        # Initialiser la source audio en fonction du paramètre audio_source
        if audio_source.startswith("rtsp"):
            if not rtsp_url:
                raise ValueError("RTSP URL must be provided for RTSP audio source.")
                
            source_id = f"rtsp_{rtsp_url}"

            detector.add_source(
                source_id=source_id,
                detection_callback=create_detection_callback(source_id),
                labels_callback=create_labels_callback(source_id)
            )
            
            # Démarrer la détection
            detector.start()
            logging.info(f"Détection démarrée pour la source RTSP {source_id}")
            
            rtsp_reader = read_audio_from_rtsp(rtsp_url, int(sample_rate * 0.1), sample_rate)  # Buffer de 100ms
            while detection_running:
                audio_data = next(rtsp_reader)
                detector.process_audio(audio_data, source_id)
            logging.info("Détection RTSP terminée")
                
        elif audio_source.startswith("vban://"):
            vban_ip = audio_source.replace("vban://", "")
            source_id = f"vban_{vban_ip}"

            detector.add_source(
                source_id=source_id,
                detection_callback=create_detection_callback(source_id),
                labels_callback=create_labels_callback(source_id)
            )
            
            # Démarrer la détection
            detector.start()

            vban_detector = get_vban_detector()
            
            def audio_callback(audio_data, timestamp):
                if not detection_running:
                    return
                    
                active_sources = vban_detector.get_active_sources()
                if vban_ip not in active_sources:
                    return
                    
                detector.process_audio(audio_data, source_id)
            
            vban_detector.set_audio_callback(audio_callback)
            
            # Maintenir le thread en vie tant que la détection est active
            while detection_running:
                time.sleep(0.1)  # Éviter de surcharger le CPU
                
                # Vérifier périodiquement si la source est toujours active
                active_sources = vban_detector.get_active_sources()
                if vban_ip not in active_sources:
                    logging.warning(f"Source VBAN {vban_ip} non trouvée")
                    time.sleep(1)  # Attendre un peu plus longtemps avant la prochaine vérification
                    
        else:  # Microphone
            # Récupérer l'index du périphérique depuis les paramètres
            settings = SETTINGS
            device_index = int(settings.get('microphone', {}).get('device_index', 0))
            source_id = f"mic_{device_index}"

            detector.add_source(
                source_id=source_id,
                detection_callback=create_detection_callback(source_id),
                labels_callback=create_labels_callback(source_id)
            )
            
            # Démarrer la détection
            detector.start()
            logging.info(f"Détection démarrée pour la source microphone {source_id}")
            
            with sd.InputStream(
                device=device_index,
                channels=1,
                samplerate=sample_rate,
                blocksize=int(sample_rate * 0.1),  # Buffer de 100ms
                callback=lambda indata, frames, time, status: detector.process_audio(indata[:, 0], source_id)
            ):
                logging.info("Stream audio démarré pour le microphone")
                while detection_running:
                    time.sleep(0.1)
                    
        detector.stop()
        return True
        
    except Exception as e:
        logging.error(f"Erreur dans run_detection: {str(e)}")
        return False

def stop_detection():
    """Arrête la détection"""
    global detection_running, classifier, record, current_audio_source
    
    try:
        detection_running = False
        
        if record:
            record.stop()
            record.close()
            record = None
            
        if classifier:
            classifier.close()
            classifier = None

        current_audio_source = None  # Réinitialisation de la source audio
        
        return True  # Retourner True si tout s'est bien passé
        
    except Exception as e:
        logging.error(f"Erreur lors de l'arrêt de la détection: {e}")
        return False  # Retourner False en cas d'erreur
