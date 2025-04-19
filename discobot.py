import os
import discord
from dotenv import load_dotenv

from discord.ext import commands
from requests import get, post

load_dotenv(dotenv_path="config")
URL = "http://192.168.10.3:8123/api/"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

rooms = {
    "salon":{"entity_id": ["light.salon_hue_gauche_1", "light.salon_hue_gauche_2", "light.salon_hue_droite_1", "light.salon_hue_droite_2"]}
}

headers = {
    "Authorization": os.getenv("HA_TOKEN"),
    "content-type": "application/json",
}

dict_on = {"salon": URL+"services/light/turn_on"}
dict_off = {"salon": URL+"services/light/turn_off"}
dict_temp = {"salon": URL+"states/sensor.oeil_air_temperature",
             "greg": URL+"states/sensor.oeil_air_temperature_3",
             "parents": URL+"states/sensor.oeil_air_temperature_2",
             "cuisine": URL+"states/sensor.cuisine_temperature_temperature",
             "sdb": URL+"states/sensor.salle_de_bain_temperature_temperature",
             "batcave": URL+"states/sensor.0x00158d0004216e50_temperature",
             "imprimante 3D": URL+"states/sensor.batcave_imprimante_3d_temperature",
             "ext": URL+"states/sensor.maison_temperature_exterieur_temperature", }

dict_tempo = {"Aujourd'hui": URL+"states/sensor.rte_tempo_couleur_actuelle",
              "Demain": URL+"states/sensor.rte_tempo_prochaine_couleur"}

dict_tempo_couleur = {"Bleu": "Bleu :blue_circle:",
                      "Blanc": "Blanc :white_circle:",
                      "Rouge": "Rouge :red_circle:"}


@bot.event
async def on_ready():
    print(f'Connecté en tant que {bot.user}')


@bot.command(name='t')
async def t(ctx, arg: str = commands.parameter(description=", ".join([i for i in dict_temp]))):
    """
    Retourne la température d'une pièce.
    :param ctx:
    :param arg:
    :return:
    """
    response = get(dict_temp.get(arg.lower()), headers=headers)
    print(response.json().get("state"), "°C")
    await ctx.send(response.json().get("state")+" "+"°C")


@bot.command(name='temp')
async def temp(ctx):
    """
    Retourne la température de toutes les pièces de la maison
    :param ctx:
    :return:
    """
    for cle, url in dict_temp.items():
        response = get(url, headers=headers)
        print(cle.capitalize(), response.json().get("state"), "°C")
        await ctx.send(cle.capitalize()+" "+response.json().get("state")+" "+"°C")


@bot.command(name='off')
async def off(ctx, arg):
    """
    Eteint l'élément passé en argument
    :param ctx:
    :param arg:
    :return: none
    """
    arg =  arg.lower()
    json = rooms.get(arg)
    response = post(dict_off.get(arg), headers=headers, json=json)
    await ctx.send("c'est fait !" if response.status_code == 200 else "je n'ai pas réussi")


@bot.command(name='on')
async def on(ctx, arg):
    """
    Allumes l'élément passé en argument
    :param ctx:
    :param arg:
    :return: none
    """
    arg = arg.lower()
    json = rooms.get(arg)
    response = post(dict_on.get(arg), headers=headers, json=json)
    await ctx.send("c'est fait !" if response.status_code == 200 else "je n'ai pas réussi")


@bot.command(name='tempo')
async def tempo(ctx):
    """
    Récupère et donnes les infos edf tempo du jour et du lendemain
    :param ctx: 
    :return: none
    """
    for cle, url in dict_tempo.items():
        response = get(url, headers=headers)
        print(cle, dict_tempo_couleur.get(response.json().get("state")))
        await ctx.send(cle + " : " + dict_tempo_couleur.get(response.json().get("state")))

bot.run(os.getenv("BOT_TOKEN"))
