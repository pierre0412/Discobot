import asyncio
import os
import json
import discord
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv(dotenv_path="config")

class DiscordBot:
    def __init__(self):
        self.intents = discord.Intents.default()
        self.intents.members = True
        self.intents.message_content = True
        self.intents.guilds = True
        self.intents.guild_messages = True

        self.bot = commands.Bot(command_prefix='!', intents=self.intents)
        self.tree = self.bot.tree
        self.default_channel = int(os.getenv("BOT_CHANNEL"))
        self.default_channel_id = None

        # Queue thread-safe pour les messages entre MQTT et Discord
        self.message_queue = asyncio.Queue()
        self.loop = None


        # Référence vers le gestionnaire MQTT (sera définie plus tard)
        self.mqtt_manager = None

        self._setup_events()
        self._setup_commands()

    def set_mqtt_manager(self, mqtt_manager):
        """Configure la référence vers le gestionnaire MQTT"""
        self.mqtt_manager = mqtt_manager
        # Configurer le callback Discord dans MQTT
        print("✓ Gestionnaire MQTT configuré")

    def queue_message(self, message, channel_id=None):
        """Thread-safe : ajoute un message à la queue pour envoi Discord"""
        try:
            if self.loop and not self.loop.is_closed():
                # Programmer l'envoi du message dans la boucle asyncio principale
                asyncio.run_coroutine_threadsafe(
                    self.message_queue.put((message, channel_id)),
                    self.loop
                )
                print(f"📝 Message ajouté à la queue: {message}")
            else:
                print(f"❌ Boucle asyncio non disponible pour le message: {message}")
        except Exception as e:
            print(f"❌ Erreur lors de l'ajout du message à la queue: {e}")

    async def process_message_queue(self):
        """Traite les messages en attente dans la queue"""
        while not self.bot.is_closed():
            try:
                # Attendre un message dans la queue (avec timeout pour éviter le blocage)
                message, channel_id = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                await self.send_simple_message(message, channel_id)
                self.message_queue.task_done()
            except asyncio.TimeoutError:
                # Timeout normal, continuer la boucle
                continue
            except Exception as e:
                print(f"❌ Erreur dans le traitement de la queue de messages: {e}")
                await asyncio.sleep(1)

    async def send_simple_message(self, message, channel_id=None):
        """Envoie un message simple sur Discord (méthode interne async)"""
        try:
            if channel_id is None:
                channel_id = self.default_channel_id
            channel = await self.bot.fetch_channel(channel_id)
            if channel:
                await channel.send(message)
                print(f"📧 Message envoyé: {message}")
                return True
            else:
                print(f"❌ Canal {channel_id} non trouvé")
                return False
        except discord.Forbidden:
            print(f"❌ Permissions insuffisantes pour envoyer: {message}")
            return False
        except Exception as e:
            print(f"❌ Erreur envoi message: {e}")
            return False

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f'✓ Bot Discord connecté en tant que {self.bot.user}')
            print(f'✓ Bot présent sur {len(self.bot.guilds)} serveur(s)')

            # Initialiser le canal par défaut maintenant que le bot est connecté
            try:
                channel = await self.bot.fetch_channel(self.default_channel)
                if channel:
                    self.default_channel_id = channel.id
                    print(f"✓ Canal par défaut configuré: {channel.name} ({channel.id})")
                else:
                    print(f"❌ Canal avec l'ID {self.default_channel} non trouvé")
                    self.default_channel_id = None
            except discord.NotFound:
                print(f"❌ Canal avec l'ID {self.default_channel} non trouvé")
                self.default_channel_id = None
            except discord.Forbidden:
                print(f"❌ Permissions insuffisantes pour accéder au canal {self.default_channel}")
                self.default_channel_id = None
            except Exception as e:
                print(f"❌ Erreur lors de la récupération du canal: {e}")
                self.default_channel_id = None


            # Stocker la référence à la boucle asyncio
            self.loop = asyncio.get_event_loop()

            for guild in self.bot.guilds:
                print(f"  - {guild.name} (ID: {guild.id})")

            # Démarrer le processeur de queue de messages
            asyncio.create_task(self.process_message_queue())
            print("✓ Processeur de queue de messages démarré")

            try:
                # Synchroniser les commandes slash
                synced = await self.bot.tree.sync()
                print(f"✓ {len(synced)} commandes slash synchronisées globalement")

                # Afficher les commandes synchronisées
                for cmd in synced:
                    print(f"  - /{cmd.name}: {cmd.description}")

            except Exception as e:
                print(f"❌ Erreur lors de la synchronisation des commandes: {e}")

        @self.bot.event
        async def on_interaction(interaction):
            print(f"🔔 Interaction reçue: {interaction.type} de {interaction.user}")
            if interaction.type == discord.InteractionType.application_command:
                print(f"  - Commande: /{interaction.data.get('name', 'inconnue')}")

        @self.bot.event
        async def on_message(message):
            # Ignorer ses propres messages
            if message.author == self.bot.user:
                return

            # Log des messages reçus
            if message.content.startswith('!'):
                print(f"📨 Message reçu de {message.author}: {message.content}")

            # Traiter les commandes
            await self.bot.process_commands(message)

        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
            print(f"❌ Erreur commande /{interaction.command}: {error}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Une erreur s'est produite.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Une erreur s'est produite.", ephemeral=True)
            except Exception as e:
                print(f"❌ Impossible d'envoyer le message d'erreur: {e}")

    def _setup_commands(self):
        @self.tree.command(name="ping", description="Commande de ping et latence")
        async def ping(interaction: discord.Interaction):
            """Commande de test classique"""
            latency = round(self.bot.latency * 1000)
            await interaction.response.send_message(f'🏓 Pong! Latence: {latency}ms')
            print(f"✓ Commande ping exécutée par {interaction.user}")

        @self.tree.command(name="test_default", description="Test de default channel")
        async def test_default(interaction: discord.Interaction, channel_id: int = None):
            """Commande de test classique"""
            latency = round(self.bot.latency * 1000)
            channel_id = int(os.getenv("BOT_CHANNEL"))
            channel = await self.bot.fetch_channel(channel_id)
            await channel.send(f'🏓 Pong! Latence: {latency}ms')
            print(f"✓ Commande test_default_exécutée")

        @self.tree.command(name="test", description="Commande de test")
        async def test(interaction: discord.Interaction):
            await interaction.response.send_message("✅ Le bot fonctionne correctement !")
            print(f"✓ Commande /test exécutée par {interaction.user}")

        @self.tree.command(name="temp", description="Affiche les températures")
        async def temp(interaction: discord.Interaction, piece: str = None):
            """Affiche les températures des capteurs MQTT"""
            print(f"✓ Commande /temp exécutée par {interaction.user} (pièce: {piece})")

            if not self.mqtt_manager:
                await interaction.response.send_message("❌ MQTT non configuré")
                return

            dico_valeurs = self.mqtt_manager.dico_valeurs

            if piece:
                # Température d'une pièce spécifique
                key = f"{piece.lower()}_t"
                temp = dico_valeurs.get(key)
                if temp:
                    await interaction.response.send_message(f"🌡️ Température {piece}: {temp}°C")
                else:
                    pieces_disponibles = [k.replace("_t", "") for k in dico_valeurs.keys()]
                    message = f"❌ Pièce '{piece}' non trouvée.\nPièces disponibles: {', '.join(pieces_disponibles)}"
                    await interaction.response.send_message(message)
            else:
                # Toutes les températures
                if dico_valeurs:
                    message = "🌡️ **Températures actuelles:**\n"
                    for capteur, temp in dico_valeurs.items():
                        if capteur.endswith("_t"):
                            piece_name = capteur.replace("_t", "")
                            message += f"• {piece_name.capitalize()}: {temp}°C\n"
                    await interaction.response.send_message(message)
                else:
                    await interaction.response.send_message("❌ Aucune donnée de température disponible")

        @self.tree.command(name="mqtt_status", description="Statut de la connexion MQTT")
        async def mqtt_status(interaction: discord.Interaction):
            """Affiche le statut de la connexion MQTT"""
            print(f"✓ Commande /mqtt_status exécutée par {interaction.user}")

            if not self.mqtt_manager:
                await interaction.response.send_message("❌ MQTT non configuré")
                return

            try:
                status = "✅ Connecté" if self.mqtt_manager.is_connected() else "❌ Déconnecté"
                nb_capteurs = len(self.mqtt_manager.dico_valeurs)
                message = f"**Statut MQTT:** {status}\n**Capteurs actifs:** {nb_capteurs}"

                if self.mqtt_manager.dico_valeurs:
                    message += "\n\n**Dernières valeurs:**\n"
                    for capteur, temp in list(self.mqtt_manager.dico_valeurs.items())[:5]:
                        if capteur.endswith("_t"):
                            piece_name = capteur.replace("_t", "")
                            message += f"• {piece_name}: {temp}°C\n"

                await interaction.response.send_message(message)
            except Exception as e:
                print(f"❌ Erreur dans mqtt_status: {e}")
                await interaction.response.send_message("❌ Erreur lors de la vérification du statut MQTT")

        @self.tree.command(name="light", description="Contrôle des lumières")
        async def light(interaction: discord.Interaction, piece: str, etat: str):
            """Contrôle des lumières via MQTT"""
            print(f"✓ Commande /light exécutée par {interaction.user} (pièce: {piece}, état: {etat})")

            if not self.mqtt_manager:
                await interaction.response.send_message("❌ MQTT non configuré", ephemeral=True)
                return

            # Vérifier les paramètres
            if etat.lower() not in ["on", "off"]:
                await interaction.response.send_message("❌ État invalide. Utilisez 'on' ou 'off'.", ephemeral=True)
                return

            # Normaliser les noms de pièces
            piece_norm = piece.lower().strip()

            # Définir le topic MQTT en fonction de la pièce
            topic_map = {
                "salon": "zigbee2mqtt/lumieres_salon/set",
            }

            # Vérifier si la pièce est valide
            if piece_norm not in topic_map:
                pieces_dispo = ", ".join(topic_map.keys())
                await interaction.response.send_message(f"❌ Pièce '{piece}' non reconnue.\nPièces disponibles: {pieces_dispo}", ephemeral=True)
                return

            # Obtenir le topic MQTT
            topic = topic_map[piece_norm]

            try:
                # Publier le message MQTT
                payload = json.dumps({"state": etat.lower()})
                self.mqtt_manager.publish_message(topic, payload)

                # Répondre à l'utilisateur
                emoji = "💡" if etat.lower() == "on" else "🌑"
                await interaction.response.send_message(f"{emoji} Lumière {piece}: **{etat.upper()}**")
            except Exception as e:
                print(f"❌ Erreur dans light: {e}")
                await interaction.response.send_message("❌ Erreur lors de l'envoi de la commande MQTT", ephemeral=True)

    async def start(self):
        """Démarre le bot Discord"""
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise ValueError("BOT_TOKEN non trouvé dans la configuration")

        print(f"🔑 Tentative de connexion avec le token...")
        await self.bot.start(token)

    async def stop(self):
        """Arrête le bot Discord"""
        if not self.bot.is_closed():
            await self.bot.close()
            print("✓ Bot Discord fermé")

    async def fetch_channel(self, channel_id):
        channel = await self.bot.fetch_channel(channel_id)
        return channel


# Instance unique du bot Discord
discord_bot = DiscordBot()

# Fonctions de compatibilité pour main.py
async def start_bot():
    """Démarre le bot Discord"""
    # Configurer la référence MQTT
    from mqtt import mqtt_manager
    discord_bot.set_mqtt_manager(mqtt_manager)

    await discord_bot.start()

async def stop_bot():
    """Arrête le bot Discord"""
    await discord_bot.stop()

async def sync_commands():
    """Synchronise les commandes slash manuellement"""
    try:
        synced = await discord_bot.bot.tree.sync()
        print(f"✓ {len(synced)} commandes synchronisées manuellement")
        return synced
    except Exception as e:
        print(f"❌ Erreur synchronisation manuelle: {e}")
        return []

# Rétrocompatibilité
dico_valeurs = {}  # Sera remplacé par la référence du mqtt_manager