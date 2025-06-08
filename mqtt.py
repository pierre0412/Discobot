import json
import os
import random

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from discobot import send_simple_message

load_dotenv(dotenv_path="config")

broker = os.getenv("MQTT_BROKER")
port = int(os.getenv("MQTT_PORT"))
username = os.getenv("MQTT_USER")
password = os.getenv("MQTT_PASSWORD")

# generate client ID with pub prefix randomly
client_id = f'python-mqtt-{random.randint(0, 1000)}'

dico_topics = {
    "salon_t": ("zwave/Salon/Salon_-_Oeil/49/0/Air_temperature", "value"),
    "parents_t": ("zwave/Chambre_Parents/Chambre_Parents_-_Oeil/49/0/Air_temperature", "value"),
    "greg_t": ("zwave/Chambre_Greg/Chambre_Greg_-_Oeil/49/0/Air_temperature", "value"),
    "ext_t": ("zigbee2mqtt/Maison - Temperature exterieur", "temperature"),
    "batcave_t": ("zigbee2mqtt/Batcave - Temperature", "temperature"),
    "sdb_t": ("zigbee2mqtt/Salle de bain - Temperature", "temperature"),
    "imprimante_3d_t": ("zigbee2mqtt/Batcave - Imprimante 3D", "temperature"),
    "cuisine_t": ("zigbee2mqtt/Cuisine - Temperature", "temperature"),
    "cuisine_congelateur_t": ("zigbee2mqtt/Cuisine - Congelateur", "temperature"),
    "cuisine_refrigerateur_t": ("zigbee2mqtt/Cuisine - Refrigerateur", "temperature"),
    "nuki": ("nukihub/lock", "state")
}

dico_valeurs = {}

def on_connect(client, reason_code):
    print(f"MQTT connecté avec le code {reason_code}")
    # S'abonner aux topics spécifiques
    for topic, _ in dico_topics.values():
        client.subscribe(topic)
    print(f"✓ Abonné à {len(dico_topics)} topics")

def on_message(msg):
    """Callback appelé quand un message MQTT est reçu"""
    try:
        # Chercher quel capteur correspond à ce topic
        for cle, (topic, field) in dico_topics.items():
            if msg.topic == "nukihub/lock":
                send_simple_message(message=f"🚪 {msg.payload.decode('utf-8')} ({cle})")
            if msg.topic == topic:
                payload = json.loads(msg.payload.decode("utf-8"))
                dico_valeurs[cle] = payload.get(field, 0)
                print(f"📊 {cle}: {dico_valeurs[cle]}°C")
                break
    except json.JSONDecodeError:
        print(f"❌ Erreur de décodage JSON pour {msg.topic}")
    except Exception as e:
        print(f"❌ Erreur dans on_message: {e}")

# Création et configuration du client MQTT
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.username_pw_set(username, password)

try:
    mqtt_client.connect(broker, port, 60)
    mqtt_client.loop_start()
    print(f"🔗 Connexion MQTT initiée vers {broker}:{port}")
except Exception as e:
    print(f"❌ Erreur de connexion MQTT: {e}")

# Fonction utilitaire pour publier des messages MQTT
def publish_message(topic, message):
    """Fonction pour publier un message MQTT"""
    try:
        mqtt_client.publish(topic, message)
        print(f"📤 Message publié sur {topic}: {message}")
    except Exception as e:
        print(f"❌ Erreur lors de la publication: {e}")