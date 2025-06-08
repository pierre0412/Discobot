import os
import json
import discord
from dotenv import load_dotenv
from discord.ext import commands

from mqtt import dico_valeurs

load_dotenv(dotenv_path="config")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.guild_messages = True

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    print(f'✓ Bot Discord connecté en tant que {bot.user}')
    print(f'✓ Bot présent sur {len(bot.guilds)} serveur(s)')

    for guild in bot.guilds:
        print(f"  - {guild.name} (ID: {guild.id})")

    try:
        # Synchroniser les commandes slash
        synced = await bot.tree.sync()
        print(f"✓ {len(synced)} commandes slash synchronisées globalement")

        # Afficher les commandes synchronisées
        for cmd in synced:
            print(f"  - /{cmd.name}: {cmd.description}")

    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation des commandes: {e}")


# Event pour détecter les interactions
@bot.event
async def on_interaction(interaction):
    print(f"🔔 Interaction reçue: {interaction.type} de {interaction.user}")
    if interaction.type == discord.InteractionType.application_command:
        print(f"  - Commande: /{interaction.data.get('name', 'inconnue')}")


@bot.tree.command(name='ping', description="Commande de ping et latence")
async def ping(interaction: discord.Interaction):
    """Commande de test classique"""
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f'🏓 Pong! Latence: {latency}ms')
    print(f"✓ Commande ping exécutée par {interaction.user}")


@bot.tree.command(name="test_classique", description="Commande de test classique")
async def test_classique(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Bot fonctionnel avec commandes classiques!")
    print(f"✓ Commande test_classique exécutée par {interaction.user}")


@bot.tree.command(name="test", description="Commande de test")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Le bot fonctionne correctement !")
    print(f"✓ Commande /test exécutée par {interaction.user}")


@bot.tree.command(name="bonjour", description="Dis bonjour !")
async def bonjour(interaction: discord.Interaction):
    await interaction.response.send_message("Bonjour ! 👋")
    print(f"✓ Commande /bonjour exécutée par {interaction.user}")


@bot.tree.command(name="info", description="Informations sur le bot")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Informations Bot", description="Bot Discord + MQTT", color=0x00ff00)
    print(f"✓ Commande /info exécutée par {interaction.user}")
    # Adapter selon le contexte (DM ou serveur)
    if interaction.guild:
        embed.add_field(name="Serveur actuel", value=interaction.guild.name, inline=True)
        embed.add_field(name="Serveurs total", value=len(bot.guilds), inline=True)
    else:
        embed.add_field(name="Message privé", value="✅", inline=True)
        embed.add_field(name="Serveurs total", value=len(bot.guilds), inline=True)

    embed.add_field(name="Latence", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Capteurs MQTT", value=len(dico_valeurs), inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="temp", description="Affiche les températures")
async def temp(interaction: discord.Interaction, piece: str = None):
    """Affiche les températures des capteurs MQTT"""
    print(f"✓ Commande /temp exécutée par {interaction.user} (pièce: {piece})")

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
                piece_name = capteur.replace("_t", "")
                message += f"• {piece_name.capitalize()}: {temp}°C\n"
            await interaction.response.send_message(message)
        else:
            await interaction.response.send_message("❌ Aucune donnée de température disponible")

@bot.tree.command(name="mqtt_status", description="Statut de la connexion MQTT")
async def mqtt_status(interaction: discord.Interaction):
    """Affiche le statut de la connexion MQTT"""
    print(f"✓ Commande /mqtt_status exécutée par {interaction.user}")
    try:
        from mqtt import mqtt_client
        status = "✅ Connecté" if mqtt_client.is_connected() else "❌ Déconnecté"
        nb_capteurs = len(dico_valeurs)
        message = f"**Statut MQTT:** {status}\n**Capteurs actifs:** {nb_capteurs}"

        if dico_valeurs:
            message += "\n\n**Dernières valeurs:**\n"
            for capteur, temp in list(dico_valeurs.items())[:5]:  # Limite à 5 pour éviter les messages trop longs
                piece_name = capteur.replace("_t", "")
                message += f"• {piece_name}: {temp}°C\n"

        await interaction.response.send_message(message)
    except Exception as e:
        print(f"❌ Erreur dans mqtt_status: {e}")
        await interaction.response.send_message("❌ Erreur lors de la vérification du statut MQTT")

@bot.tree.command(name="light", description="Contrôle des lumières")
async def light(interaction: discord.Interaction, piece: str, etat: str):
    """Contrôle des lumières via MQTT

    Parameters
    ----------
    piece : str
        La pièce où se trouve la lumière (salon, cuisine, chambre, etc.)
    etat : str
        L'état souhaité (on, off)
    """
    print(f"✓ Commande /light exécutée par {interaction.user} (pièce: {piece}, état: {etat})")

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
        await interaction.response.send_message(f"❌ Pièce '{piece}' non reconnue.\nPièces disponibles: {pieces_dispo}",
            ephemeral=True)
        return

    # Obtenir le topic MQTT
    topic = topic_map[piece_norm]

    try:
        # Importer la fonction de publication MQTT
        from mqtt import publish_message

        # Publier le message MQTT
        payload = json.dumps({"state": etat.lower()})
        publish_message(topic, payload)

        # Répondre à l'utilisateur
        emoji = "💡" if etat.lower() == "on" else "🌑"
        await interaction.response.send_message(
            f"{emoji} Lumière {piece}: **{etat.upper()}**"
        )
    except Exception as e:
        print(f"❌ Erreur dans light: {e}")
        await interaction.response.send_message(
            "❌ Erreur lors de l'envoi de la commande MQTT",
            ephemeral=True
        )


async def send_simple_message(message):
    channel = bot.get_channel(941854371023577108)
    await channel.send(message)
    print(f"📧 Message envoyé: {message}")

# Gestion des erreurs
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    print(f"❌ Erreur commande /{interaction.command}: {error}")
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Une erreur s'est produite.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Une erreur s'est produite.", ephemeral=True)
    except Exception as e:
        print(f"❌ Impossible d'envoyer le message d'erreur: {e}")

# Event pour débogage
@bot.event
async def on_message(message):
    # Ignorer ses propres messages
    if message.author == bot.user:
        return

    # Log des messages reçus
    if message.content.startswith('!'):
        print(f"📨 Message reçu de {message.author}: {message.content}")

    # Traiter les commandes
    await bot.process_commands(message)

# Fonctions pour le contrôle depuis main.py
async def start_bot():
    """Démarre le bot Discord"""
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN non trouvé dans la configuration")

    print(f"🔑 Tentative de connexion avec le token...")
    await bot.start(token)

async def stop_bot():
    """Arrête le bot Discord"""
    if not bot.is_closed():
        await bot.close()
        print("✓ Bot Discord fermé")

# Fonction pour synchroniser manuellement les commandes (si nécessaire)
async def sync_commands():
    """Synchronise les commandes slash manuellement"""
    try:
        synced = await bot.tree.sync()
        print(f"✓ {len(synced)} commandes synchronisées manuellement")
        return synced
    except Exception as e:
        print(f"❌ Erreur synchronisation manuelle: {e}")
        return []