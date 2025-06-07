import asyncio
import signal
import sys

# Import Discord bot functions
from discobot import start_bot, stop_bot, sync_commands

# Import MQTT client
from mqtt import mqtt_client, publish_message, dico_valeurs

# Flag to track if a shutdown is in progress
shutdown_in_progress = False

async def shutdown(signal_received=None):
    """Handle a graceful shutdown of all services"""
    global shutdown_in_progress
    
    if shutdown_in_progress:
        return
    
    shutdown_in_progress = True
    
    if signal_received:
        print(f"\n🛑 Signal {signal_received} reçu, arrêt en cours...")
    else:
        print("\n🛑 Arrêt demandé, fermeture des services...")
    
    # Stop MQTT client
    try:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        print("✓ Client MQTT déconnecté")
    except Exception as e:
        print(f"❌ Erreur lors de l'arrêt du client MQTT: {e}")
    
    # Stop Discord bot
    try:
        await stop_bot()
    except Exception as e:
        print(f"❌ Erreur lors de l'arrêt du bot Discord: {e}")
    
    print("✓ Arrêt complet terminé")

async def main():
    """Main function to run the bot and MQTT client"""
    try:
        # MQTT client is already initialized and connected in mqtt.py
        print("✓ Client MQTT initialisé")
        
        # Start the Discord bot
        print("🤖 Démarrage du bot Discord...")
        await start_bot()
        
    except KeyboardInterrupt:
        print("\n⚠️ Interruption clavier détectée")
    except Exception as e:
        print(f"❌ Erreur dans la fonction principale: {e}")
    finally:
        await shutdown()

if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: asyncio.create_task(shutdown(s)))
    
    # Print startup banner
    print("=" * 50)
    print("🤖 DÉMARRAGE DU BOT DISCORD + MQTT")
    print("=" * 50)
    print("• Utilisez les commandes Discord pour contrôler les lumières")
    print("• Utilisez /temp pour consulter les températures")
    print("• Utilisez /mqtt_status pour vérifier l'état de la connexion MQTT")
    print("• Utilisez Ctrl+C pour arrêter le bot")
    print("=" * 50)
    
    # Run the main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Interruption clavier détectée lors du démarrage")
    except Exception as e:
        print(f"❌ Erreur critique: {e}")
        sys.exit(1)