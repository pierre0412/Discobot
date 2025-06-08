import json
import os
import random
import asyncio
import threading

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv(dotenv_path="config")

class MQTTManager:
    def __init__(self):
        self.broker = os.getenv("MQTT_BROKER")
        self.port = int(os.getenv("MQTT_PORT"))
        self.username = os.getenv("MQTT_USER")
        self.password = os.getenv("MQTT_PASSWORD")
        self.client_id = f'python-mqtt-{random.randint(0, 1000)}'

        self.dico_topics = {
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
            "nuki": ("nukihub/lock/json", "lock_state")
        }

        self.dico_valeurs = {}
        self.previous_nuki_state = None

        # Initialiser le client MQTT
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.username_pw_set(self.username, self.password)

        # Se connecter
        self._connect()

    def send_discord_message(self, message):
        """Envoie un message Discord via la méthode synchrone"""
        try:
            from discobot import discord_bot
            discord_bot.send_message_sync(message)
            print(f"📧 Message Discord envoyé à la queue: {message}")
        except Exception as e:
            print(f"❌ Erreur envoi Discord: {e}")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        print(f"MQTT connecté avec le code {reason_code}")
        # S'abonner aux topics spécifiques
        for topic, _ in self.dico_topics.values():
            client.subscribe(topic)
        print(f"✓ Abonné à {len(self.dico_topics)} topics")

    def _on_message(self, client, userdata, msg):
        try:
            # Traitement spécial pour le verrou Nuki
            if msg.topic == self.dico_topics.get("nuki")[0]:
                payload = json.loads(msg.payload.decode("utf-8"))
                current_state = payload.get("lock_state", "unknown")
                # Vérifier si l'état a changé de locked à unlocked
                etat_porte = "dévérouillée" if current_state == "unlocked" else "verrouillée"
                if self.previous_nuki_state != current_state:
                    self.send_discord_message(f"🔓 **La porte vient d'être {etat_porte} !**")
                # Mettre à jour l'état précédent et le dictionnaire de valeurs
                self.previous_nuki_state = current_state
                self.dico_valeurs["nuki"] = current_state
                print(f"🔐 Nuki: {current_state}")
                return

            # Traitement pour les autres capteurs
            for cle, (topic, field) in self.dico_topics.items():
                if msg.topic == topic and cle != "nuki":
                    payload = json.loads(msg.payload.decode("utf-8"))
                    self.dico_valeurs[cle] = payload.get(field, 0)
                    print(f"📊 {cle}: {self.dico_valeurs[cle]}°C")
                    break

        except json.JSONDecodeError:
            print(f"❌ Erreur de décodage JSON pour {msg.topic}")
        except Exception as e:
            print(f"❌ Erreur dans on_message: {e}")

    def _connect(self):
        """Se connecter au broker MQTT"""
        try:
            self.mqtt_client.connect(self.broker, self.port, 60)
            self.mqtt_client.loop_start()
            print(f"🔗 Connexion MQTT initiée vers {self.broker}:{self.port}")
        except Exception as e:
            print(f"❌ Erreur de connexion MQTT: {e}")

    def publish_message(self, topic, message):
        """Fonction pour publier un message MQTT"""
        try:
            self.mqtt_client.publish(topic, message)
            print(f"📤 Message publié sur {topic}: {message}")
        except Exception as e:
            print(f"❌ Erreur lors de la publication: {e}")

    def is_connected(self):
        """Vérifie si le client MQTT est connecté"""
        return self.mqtt_client.is_connected()

    def disconnect(self):
        """Déconnecte le client MQTT"""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()

# Instance unique du gestionnaire MQTT
mqtt_manager = MQTTManager()

# Fonctions de compatibilité pour l'existant
dico_valeurs = mqtt_manager.dico_valeurs
mqtt_client = mqtt_manager.mqtt_client

def publish_message(topic, message):
    """Fonction de compatibilité"""
    return mqtt_manager.publish_message(topic, message)