import asyncio
import os
import json
import queue
import time
from datetime import datetime, timedelta

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
        self.default_channel_id = int(os.getenv("BOT_CHANNEL"))

        # Référence vers le gestionnaire MQTT (sera définie plus tard)
        self.mqtt_manager = None

        # Queue pour les messages externes (MQTT)
        self.message_queue = queue.Queue()
        self.queue_processor_started = False
        self.queue_task = None  # Référence vers la tâche du processeur

        # Configuration des utilisateurs autorisés
        self.authorized_users = self._load_authorized_users()

        # Timestamp de démarrage pour calculer l'uptime
        self.start_time = time.time()

        self._setup_events()
        self._setup_commands()

    def get_uptime(self):
        """Calcule et retourne l'uptime du bot sous forme lisible"""
        uptime_seconds = time.time() - self.start_time
        uptime_delta = timedelta(seconds=int(uptime_seconds))

        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_parts = []
        if days > 0:
            uptime_parts.append(f"{days}j")
        if hours > 0:
            uptime_parts.append(f"{hours}h")
        if minutes > 0:
            uptime_parts.append(f"{minutes}m")
        if seconds > 0 or not uptime_parts:  # Afficher les secondes si c'est le seul élément ou si rien d'autre
            uptime_parts.append(f"{seconds}s")

        return " ".join(uptime_parts)

    def _load_authorized_users(self):
        """Charge la liste des utilisateurs autorisés depuis la configuration"""
        try:
            # Récupérer depuis les variables d'environnement (format: id1,id2,id3)
            authorized_ids_str = os.getenv("AUTHORIZED_USERS", "")
            if authorized_ids_str:
                authorized_ids = [int(user_id.strip()) for user_id in authorized_ids_str.split(",")]
                print(f"✓ {len(authorized_ids)} utilisateurs autorisés chargés")
                return set(authorized_ids)
            else:
                print("⚠️ Aucun utilisateur autorisé configuré dans AUTHORIZED_USERS")
                return set()
        except Exception as e:
            print(f"❌ Erreur chargement utilisateurs autorisés: {e}")
            return set()

    def is_user_authorized(self, user_id):
        """Vérifie si un utilisateur est autorisé à utiliser les commandes"""
        if not self.authorized_users:
            # Si aucun utilisateur autorisé n'est configuré, autoriser tout le monde
            return True
        return user_id in self.authorized_users

    def add_authorized_user(self, user_id):
        """Ajoute un utilisateur à la liste des autorisés"""
        self.authorized_users.add(user_id)
        print(f"✓ Utilisateur {user_id} ajouté aux autorisés")

    def remove_authorized_user(self, user_id):
        """Retire un utilisateur de la liste des autorisés"""
        self.authorized_users.discard(user_id)
        print(f"✓ Utilisateur {user_id} retiré des autorisés")

    async def check_authorization(self, interaction):
        """Vérifie l'autorisation et répond si non autorisé"""
        if not self.is_user_authorized(interaction.user.id):
            await interaction.response.send_message(
                "❌ **Accès refusé**\n"
                "Vous n'êtes pas autorisé à utiliser les commandes de ce bot.\n"
                f"Votre ID: `{interaction.user.id}`",
                ephemeral=True
            )
            print(f"🚫 Tentative d'accès non autorisé: {interaction.user} (ID: {interaction.user.id})")
            return False
        return True

    def set_mqtt_manager(self, mqtt_manager):
        """Configure la référence vers le gestionnaire MQTT"""
        self.mqtt_manager = mqtt_manager
        # Configurer le callback Discord dans MQTT
        print("✓ Gestionnaire MQTT configuré")

    def send_message_sync(self, message, channel_id=None):
        """Méthode synchrone pour envoyer un message Discord depuis MQTT"""
        try:
            self.message_queue.put((message, channel_id))
            print(f"📧 Message ajouté à la queue Discord: {message}")
        except Exception as e:
            print(f"❌ Erreur ajout queue Discord: {e}")

    def _start_queue_processor(self):
        """Démarre le processeur de queue si pas encore fait"""
        if not self.queue_processor_started and hasattr(self.bot, 'loop') and self.bot.loop:
            self.queue_processor_started = True
            # Créer la tâche et stocker la référence
            try:
                self.queue_task = asyncio.create_task(self._process_message_queue())
                print("✓ Processeur de queue démarré")
            except Exception as e:
                print(f"❌ Erreur démarrage processeur queue: {e}")
                self.queue_processor_started = False

    async def _process_message_queue(self):
        """Traite les messages de la queue en arrière-plan"""
        print("🔄 Processeur de queue en cours d'exécution...")
        while True:
            try:
                # Vérifier s'il y a des messages dans la queue
                try:
                    message, channel_id = self.message_queue.get_nowait()
                    await self.send_simple_message(message, channel_id)
                    self.message_queue.task_done()
                except queue.Empty:
                    pass

                # Attendre un peu avant de vérifier à nouveau
                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                print("🛑 Processeur de queue arrêté")
                break
            except Exception as e:
                print(f"❌ Erreur processeur queue: {e}")
                await asyncio.sleep(1)

    async def send_simple_message(self, message, channel_id=None):
        """Envoie un message simple sur Discord"""
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
        except Exception as e:
            print(f"❌ Erreur envoi message: {e}")
            return False

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f'✓ Bot Discord connecté en tant que {self.bot.user}')
            print(f'✓ Bot présent sur {len(self.bot.guilds)} serveur(s)')
            print(f'✓ {len(self.authorized_users)} utilisateurs autorisés')

            # Démarrer le processeur de queue maintenant que le bot est prêt
            if not self.queue_processor_started:
                self._start_queue_processor()

            # Initialiser le canal par défaut maintenant que le bot est connecté
            try:
                channel = await self.bot.fetch_channel(self.default_channel_id)
                if channel:
                    print(f"✓ Canal par défaut configuré: {channel.name} ({channel.id})")
                else:
                    print(f"❌ Canal avec l'ID {self.default_channel_id} non trouvé")
            except Exception as e:
                print(f"❌ Erreur lors de la récupération du canal: {e}")

            for guild in self.bot.guilds:
                print(f"  - {guild.name} (ID: {guild.id})")

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
            if not await self.check_authorization(interaction):
                return
            latency = round(self.bot.latency * 1000)
            await interaction.response.send_message(f'🏓 Pong! Latence: {latency}ms')
            print(f"✓ Commande ping exécutée par {interaction.user}")

        @self.tree.command(name="info", description="Affiche les informations du bot")
        async def info(interaction: discord.Interaction):
            """Affiche les informations détaillées du bot dans le canal par défaut"""
            if not await self.check_authorization(interaction):
                return

            try:
                # Calculer les statistiques du bot
                latency = round(self.bot.latency * 1000)
                server_count = len(self.bot.guilds)
                server_names = [guild.name for guild in self.bot.guilds]
                total_members = sum(guild.member_count for guild in self.bot.guilds)
                uptime = self.get_uptime()

                # Informations MQTT
                mqtt_status = "❌ Non configuré"
                mqtt_sensors = 0
                if self.mqtt_manager:
                    mqtt_status = "✅ Connecté" if self.mqtt_manager.is_connected() else "❌ Déconnecté"
                    mqtt_sensors = len(self.mqtt_manager.dico_valeurs)

                # Informations sur les autorisations
                auth_count = len(self.authorized_users)
                auth_status = "🔓 Ouvert à tous" if auth_count == 0 else f"🔒 {auth_count} utilisateurs autorisés"

                # Obtenir les commandes disponibles
                commands_list = []
                for cmd in self.bot.tree.get_commands():
                    commands_list.append(f"• **/{cmd.name}**: {cmd.description}")

                # Construire le message d'information
                embed = discord.Embed(
                    title="🤖 Informations du Bot",
                    description="Bot Discord de contrôle domotique avec intégration MQTT",
                    color=0x00ff00  # Vert
                )

                # Informations générales
                embed.add_field(
                    name="📊 Statistiques Générales",
                    value=f"**Latence:** {latency}ms\n"
                          f"**Serveurs:** {server_count}\n"
                          f"**Membres totaux:** {total_members}\n"
                          f"**Uptime:** {uptime}",
                    inline=True
                )

                # Informations serveurs
                if server_count > 0:
                    servers_text = "\n".join([f"• {name}" for name in server_names[:5]])
                    if server_count > 5:
                        servers_text += f"\n... et {server_count - 5} autres"

                    embed.add_field(
                        name="🏠 Serveurs",
                        value=servers_text,
                        inline=True
                    )

                # Statut MQTT
                embed.add_field(
                    name="📡 Statut MQTT",
                    value=f"**Connexion:** {mqtt_status}\n"
                          f"**Capteurs actifs:** {mqtt_sensors}",
                    inline=True
                )

                # Autorizations
                embed.add_field(
                    name="🔐 Autorisations",
                    value=auth_status,
                    inline=True
                )

                # Liste des commandes
                commands_text = "\n".join(commands_list[:10])  # Limiter à 10 commandes
                if len(commands_list) > 10:
                    commands_text += f"\n... et {len(commands_list) - 10} autres"

                embed.add_field(
                    name="⚡ Commandes Disponibles",
                    value=commands_text,
                    inline=False
                )

                # Informations techniques
                embed.add_field(
                    name="🔧 Informations Techniques",
                    value=f"**Version Discord.py:** {discord.__version__}\n"
                          f"**Préfixe des commandes:** `/`\n"
                          f"**Queue de messages:** {'🟢 Active' if self.queue_processor_started else '🔴 Inactive'}\n"
                          f"**Canal par défaut:** <#{self.default_channel_id}>",
                    inline=False
                )

                # Footer avec timestamp
                embed.set_footer(
                    text=f"Bot développé avec Python • Dernière mise à jour",
                    icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
                )
                embed.timestamp = discord.utils.utcnow()

                # Thumbnail avec l'avatar du bot
                if self.bot.user.avatar:
                    embed.set_thumbnail(url=self.bot.user.avatar.url)

                # Envoyer d'abord une confirmation à l'utilisateur
                await interaction.response.send_message("📋 Informations du bot envoyées dans le canal par défaut !",
                                                        ephemeral=True)

                # Puis envoyer l'embed dans le canal par défaut
                channel = await self.bot.fetch_channel(self.default_channel_id)
                if channel:
                    await channel.send(embed=embed)
                    print(f"✓ Informations du bot envoyées dans {channel.name} par {interaction.user}")
                else:
                    await interaction.followup.send("❌ Impossible d'accéder au canal par défaut", ephemeral=True)
                    print(f"❌ Canal par défaut {self.default_channel_id} introuvable")

            except Exception as e:
                print(f"❌ Erreur dans la commande info: {e}")
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Erreur lors de la génération des informations",
                                                            ephemeral=True)
                else:
                    await interaction.followup.send("❌ Erreur lors de la génération des informations", ephemeral=True)

        @self.tree.command(name="test", description="Commande de test")
        async def test(interaction: discord.Interaction):
            if not await self.check_authorization(interaction):
                return

            await interaction.response.send_message("✅ Le bot fonctionne correctement !")
            print(f"✓ Commande /test exécutée par {interaction.user}")

        @self.tree.command(name="temp", description="Affiche les températures")
        async def temp(interaction: discord.Interaction, piece: str = None):
            """Affiche les températures des capteurs MQTT"""
            if not await self.check_authorization(interaction):
                return

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
            if not await self.check_authorization(interaction):
                return

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
            if not await self.check_authorization(interaction):
                return

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

        @self.tree.command(name="door", description="Contrôle du verrou de la porte")
        async def door(interaction: discord.Interaction, action: str):
            """Contrôle du verrou Nuki via MQTT"""
            if not await self.check_authorization(interaction):
                return
            print(f"✓ Commande /door exécutée par {interaction.user} (action: {action})")
            if not self.mqtt_manager:
                await interaction.response.send_message("❌ MQTT non configuré", ephemeral=True)
                return
            # Vérifier les paramètres
            action_lower = action.lower().strip()
            if action_lower not in ["lock", "unlock", "verrouiller", "deverrouiller", "status", "statut"]:
                await interaction.response.send_message(
                    "❌ **Action invalide**\n"
                    "Actions disponibles:\n"
                    "• `lock` ou `verrouiller` - Verrouiller la porte\n"
                    "• `unlock` ou `deverrouiller` - Déverrouiller la porte\n"
                    "• `status` ou `statut` - Afficher l'état actuel",
                    ephemeral=True
                )
                return

            # Gestion de la commande status
            if action_lower in ["status", "statut"]:
                current_state = self.mqtt_manager.dico_valeurs.get("nuki", "unknown")
                if current_state == "unknown":
                    status_msg = "❓ **État inconnu**\nAucune donnée du verrou disponible"
                    emoji = "❓"
                elif current_state == "locked":
                    status_msg = "🔒 **Porte verrouillée**"
                    emoji = "🔒"
                elif current_state == "unlocked":
                    status_msg = "🔓 **Porte déverrouillée**"
                    emoji = "🔓"
                else:
                    status_msg = f"❓ **État:** {current_state}"
                    emoji = "❓"
                await interaction.response.send_message(f"{emoji} {status_msg}")
                return

            # Normaliser les actions en anglais pour MQTT
            if action_lower in ["verrouiller"]:
                mqtt_action = "lock"
                action_fr = "verrouillage"
                emoji = "🔒"
            elif action_lower in ["deverrouiller"]:
                mqtt_action = "unlock"
                action_fr = "déverrouillage"
                emoji = "🔓"
            else:
                mqtt_action = action_lower
                action_fr = "verrouillage" if mqtt_action == "lock" else "déverrouillage"
                emoji = "🔒" if mqtt_action == "lock" else "🔓"

            # Topic MQTT pour le verrou Nuki
            nuki_topic = "nukihub/lock/action"
            try:
                # Construire le payload MQTT
                payload = mqtt_action #json.dumps(mqtt_action)
                # Publier le message MQTT
                self.mqtt_manager.publish_message(nuki_topic, payload)
                # Obtenir l'état actuel pour comparaison
                current_state = self.mqtt_manager.dico_valeurs.get("nuki", "unknown")
                current_status = ""
                if current_state != "unknown":
                    current_status = f"\n*État précédent: {'🔒 verrouillée' if current_state == 'locked' else '🔓 déverrouillée'}*"
                # Répondre à l'utilisateur
                await interaction.response.send_message(
                    f"{emoji} **Commande de {action_fr} envoyée**\n"
                    f"Action: `{mqtt_action}`{current_status}\n\n"
                    f"⏳ *Vérification de l'état en cours...*"
                )
                # Log de sécurité
                print(f"🔐 Commande de {action_fr} envoyée par {interaction.user} ({interaction.user.id})")
            except Exception as e:
                print(f"❌ Erreur dans door: {e}")
                await interaction.response.send_message(
                    f"❌ **Erreur lors de l'envoi de la commande**\n"
                    f"Impossible d'envoyer la commande de {action_fr}",
                    ephemeral=True
                )

        @self.tree.command(name="door_status", description="Affiche l'état du verrou de la porte")
        async def door_status(interaction: discord.Interaction):
            """Affiche l'état actuel du verrou Nuki"""
            if not await self.check_authorization(interaction):
                return
            print(f"✓ Commande /door_status exécutée par {interaction.user}")
            if not self.mqtt_manager:
                await interaction.response.send_message("❌ MQTT non configuré", ephemeral=True)
                return
            try:
                current_state = self.mqtt_manager.dico_valeurs.get("nuki", "unknown")
                # Créer un embed pour un affichage plus riche
                if current_state == "locked":
                    embed = discord.Embed(
                        title="🔒 État du Verrou",
                        description="**Porte verrouillée**",
                        color=0xff0000  # Rouge
                    )
                    embed.add_field(name="Statut", value="🔒 Sécurisée", inline=True)
                elif current_state == "unlocked":
                    embed = discord.Embed(
                        title="🔓 État du Verrou",
                        description="**Porte déverrouillée**",
                        color=0x00ff00  # Vert
                    )
                    embed.add_field(name="Statut", value="🔓 Ouverte", inline=True)
                else:
                    embed = discord.Embed(
                        title="❓ État du Verrou",
                        description="**État inconnu**",
                        color=0xffff00  # Jaune
                    )
                    embed.add_field(name="Statut", value="❓ Données indisponibles", inline=True)
                # Ajouter des informations supplémentaires
                embed.add_field(name="Topic MQTT", value="`nukihub/lock/json`", inline=True)
                embed.add_field(name="Dernière mise à jour", value="Temps réel", inline=True)
                # Footer
                embed.set_footer(text="Utilisez /door [action] pour contrôler le verrou")
                embed.timestamp = discord.utils.utcnow()
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                print(f"❌ Erreur dans door_status: {e}")
                await interaction.response.send_message(
                    "❌ Erreur lors de la vérification de l'état du verrou",
                    ephemeral=True
                )

        @self.tree.command(name="auth_status", description="Affiche votre statut d'autorisation")
        async def auth_status(interaction: discord.Interaction):
            """Affiche le statut d'autorisation de l'utilisateur"""
            user_id = interaction.user.id
            is_authorized = self.is_user_authorized(user_id)
            
            if is_authorized:
                message = f"✅ **Accès autorisé**\nVotre ID: `{user_id}`\nVous pouvez utiliser toutes les commandes du bot."
            else:
                message = f"❌ **Accès non autorisé**\nVotre ID: `{user_id}`\nContactez un administrateur pour obtenir l'accès."
            
            await interaction.response.send_message(message, ephemeral=True)
            print(f"✓ Vérification statut d'autorisation pour {interaction.user}")

        @self.tree.command(name="auth_add", description="[Admin] Ajoute un utilisateur autorisé")
        async def auth_add(interaction: discord.Interaction, user_id: str):
            """Ajoute un utilisateur à la liste des autorisés (réservé aux admins)"""
            # Vérifier si l'utilisateur actuel est autorisé
            if not await self.check_authorization(interaction):
                return

            try:
                target_user_id = int(user_id)
                self.add_authorized_user(target_user_id)
                await interaction.response.send_message(f"✅ Utilisateur `{target_user_id}` ajouté aux autorisés", ephemeral=True)
            except ValueError:
                await interaction.response.send_message("❌ ID utilisateur invalide", ephemeral=True)
            except Exception as e:
                print(f"❌ Erreur ajout utilisateur autorisé: {e}")
                await interaction.response.send_message("❌ Erreur lors de l'ajout", ephemeral=True)

        @self.tree.command(name="auth_remove", description="[Admin] Retire un utilisateur autorisé")
        async def auth_remove(interaction: discord.Interaction, user_id: str):
            """Retire un utilisateur de la liste des autorisés (réservé aux admins)"""
            # Vérifier si l'utilisateur actuel est autorisé
            if not await self.check_authorization(interaction):
                return

            try:
                target_user_id = int(user_id)
                self.remove_authorized_user(target_user_id)
                await interaction.response.send_message(f"✅ Utilisateur `{target_user_id}` retiré des autorisés", ephemeral=True)
            except ValueError:
                await interaction.response.send_message("❌ ID utilisateur invalide", ephemeral=True)
            except Exception as e:
                print(f"❌ Erreur suppression utilisateur autorisé: {e}")
                await interaction.response.send_message("❌ Erreur lors de la suppression", ephemeral=True)

        @self.tree.command(name="auth_list", description="[Admin] Liste les utilisateurs autorisés")
        async def auth_list(interaction: discord.Interaction):
            """Liste tous les utilisateurs autorisés (réservé aux admins)"""
            # Vérifier si l'utilisateur actuel est autorisé
            if not await self.check_authorization(interaction):
                return

            if not self.authorized_users:
                message = "ℹ️ **Aucun utilisateur autorisé configuré**\nToutes les commandes sont ouvertes à tous."
            else:
                message = f"👥 **Utilisateurs autorisés ({len(self.authorized_users)}):**\n"
                for user_id in sorted(self.authorized_users):
                    try:
                        user = await self.bot.fetch_user(user_id)
                        message += f"• {user.display_name} (`{user_id}`)\n"
                    except:
                        message += f"• Utilisateur inconnu (`{user_id}`)\n"

            await interaction.response.send_message(message, ephemeral=True)

    async def start(self):
        """Démarre le bot Discord"""
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise ValueError("BOT_TOKEN non trouvé dans la configuration")

        print(f"🔑 Tentative de connexion avec le token...")
        await self.bot.start(token)

    async def stop(self):
        """Arrête le bot Discord"""
        if self.queue_task and not self.queue_task.done():
            self.queue_task.cancel()
            try:
                await self.queue_task
            except asyncio.CancelledError:
                pass
        
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