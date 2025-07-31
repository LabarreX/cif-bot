import discord
from discord.ext import commands
import time
import os
from dotenv import load_dotenv
from flask import Flask
import threading
import datetime
import asyncio

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True  # Nécessaire pour lire le contenu des messages

bot = commands.Bot(command_prefix="$", intents=intents, description="Bot du C.I.F.")

bot_last_message = datetime.datetime.utcnow()

########################################
# === Flask server to keep port open ===
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Discord en ligne avec Render Web Service."

def run_web():
    port = int(os.environ.get("PORT", 10000))  # PORT fourni par Render
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()
########################################

##################### Bot Events #####################

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")
    await bot.change_presence(activity=discord.Game(name="aider le C.I.F."))
    bot.loop.create_task(surveiller_inactivite_bot())

@bot.event
async def on_member_join(member):
    global bot_last_message
    channel = discord.utils.get(member.guild.text_channels, name="général")  # à adapter
    await channel.send(f"👋 Bienvenue {member.mention} sur le serveur !")
    bot_last_message = datetime.datetime.utcnow()


#################### Bot Commands ####################

### Modérateurs

# Supprimer des messages : $clear <nombre>
@bot.command()
@commands.has_role("Modérateur")
async def clear(ctx, nombre: int):
    global bot_last_message
    await ctx.channel.purge(limit = nombre+1)
    await ctx.send(f"✅ {nombre} messages ont été supprimés.")
    time.sleep(2)
    await ctx.channel.purge(limit = 1)
    bot_last_message = datetime.datetime.utcnow()

# Kick un membre : $kick <membre> <raison>
@bot.command()
@commands.has_role("Modérateur")
async def kick(ctx, member: discord.Member, reason="Aucune raison fournie"):
    global bot_last_message
    await member.kick(reason=reason)
    await ctx.send(f"✅ {member.mention} a été kick pour la raison :\n{reason}.")
    try :
        await member.send(f"❌ Vous avez été kick du serveur {ctx.guild.name} pour la raison suivante :\n{reason}.")
    except :
        await ctx.send(f"❌ {member.mention} n'a pas pu être averti.")
        print("Impossible d'envoyer un message à ce membre.")
    bot_last_message = datetime.datetime.utcnow()

# Ban un membre : $ban <membre> <raison>
@bot.command()
@commands.has_role("Modérateur")
async def ban(ctx, member: discord.Member, reason="Aucune raison fournie"):
    global bot_last_message
    await member.ban(reason=reason)
    await ctx.send(f"✅ {member.mention} a été ban pour la raison :\n{reason}.")
    try :
        await member.send(f"❌ Vous avez été ban du serveur {ctx.guild.name} pour la raison suivante :\n{reason}.")
    except :
        await ctx.send(f"❌ {member.mention} n'a pas pu être averti.")
        print("Impossible d'envoyer un message à ce membre.")
    bot_last_message = datetime.datetime.utcnow()

# Warn un membre : $warn <membre> <raison>\
@bot.command()
@commands.has_role("Modérateur")
async def warn(ctx, member: discord.Member, reason="Aucune raison fournie"):
    global bot_last_message
    await ctx.send(f"⚠️ Attention, {member.mention}, votre comportement pourrait vous faire kick :\n{reason}.")
    try :
        await member.send(f"⚠️ Attention, votre comportement pourrait vous faire kick :\n{reason}.")
    except :
        print("Impossible d'envoyer un message à ce membre.")
    bot_last_message = datetime.datetime.utcnow()

# Mute un membre : $mute <membre> <raison>
@bot.command()
@commands.has_role("Modérateur")
async def mute(ctx, member: discord.Member, reason="Aucune raison fournie"):
    global bot_last_message
    mute_role = discord.utils.get(ctx.guild.roles, name="Muet")

    if not mute_role:
        mute_role = await ctx.guild.create_role(name="Muet")
        for channel in ctx.guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
    
    await member.add_roles(mute_role, reason=reason)
    await ctx.send(f"✅ {member.mention} a été mute pour la raison suivante :\n{reason}.")
    try :
        await member.send(f"❌ Vous avez été mute du serveur {ctx.guild.name} pour la raison suivante :\n{reason}.")
    except :
        await ctx.send(f"❌ {member.mention} n'a pas pu être averti.")
        print("Impossible d'envoyer un message à ce membre.")
    bot_last_message = datetime.datetime.utcnow()

# Unmute un membre : $unmute <membre>
@bot.command()
@commands.has_role("Modérateur")
async def unmute(ctx, member: discord.Member):
    global bot_last_message
    mute_role = discord.utils.get(ctx.guild.roles, name="Muet")
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await ctx.send(f"✅ {member.mention} a été unmute.")
        try :
            await member.send(f"✅ Vous avez été unmute du serveur {ctx.guild.name}.")
        except :
            print("Impossible d'envoyer un message à ce membre.")
    else :
        await ctx.send(f"❌ {member.mention} n'était pas mute.")
    bot_last_message = datetime.datetime.utcnow()


### @everyone

# Obtenir le lien d'invitation du serveur : $invite
@bot.command()
async def invite(ctx):
    global bot_last_message
    await ctx.send("🔗 Voici le lien d'invitation du serveur : https://discord.gg/qwKMe6FeKT")
    await ctx.send("⚠️ Veuillez ne l'envoyer qu'à des personnes réellement intéressées, et ne pas le communiquer aux personnes qui se sont faites kick.")
    bot_last_message = datetime.datetime.utcnow()

# Dire bonjour : $hello
@bot.command()
async def hello(ctx):
    global bot_last_message
    await ctx.send("Salut ! 👋")
    bot_last_message = datetime.datetime.utcnow()

# Commande simple : $aide
@bot.command()
async def aide(ctx):
    global bot_last_message
    msg = (
        "Voici les commandes disponibles :\n"
        "$invite — Fournit le lien d'invitation du serveur\n"
        "$hello — Réponds Salut\n"
        "$aide — Affiche ce message\n"
    )

    # Si l'auteur a le rôle "Modérateur", on ajoute les commandes modération
    if discord.utils.get(ctx.author.roles, name="Modérateur"):
        msg += (
            "\n🔧 Commandes Modération :\n"
            "$warn <@membre> <raison> — Avertit un membre\n"
            "$kick <@membre> <raison> — Expulse un membre\n"
            "$ban <@membre> <raison> — Bannit un membre\n"
            "$mute <@membre> <raison> — Rend muet (texte)\n"
            "$unmute <@membre> — Enlève le rôle Muet\n"
        )

    await ctx.send(msg)
    bot_last_message = datetime.datetime.utcnow()


#################### Bot Errors ####################

# Gestion des erreurs
@bot.event
async def on_command_error(ctx, error):
    global bot_last_message
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Commande inconnue. Tape $aide pour voir les commandes.")
    else:
        await ctx.send("❗ Une erreur est survenue. Raisons possibles :\n- Vous n'avez pas les permissions nécessaires.\n- Vous n'avez pas ou mal mentionné le membre.")
        raise error  # Affiche l'erreur dans la console pour le développeur
    bot_last_message = datetime.datetime.utcnow()


################# Manage inactivity #################

async def surveiller_inactivite_bot():
    global bot_last_message
    await bot.wait_until_ready()
    await asyncio.sleep(5)

    while not bot.is_closed():
        maintenant = datetime.datetime.utcnow()
        ecart = (maintenant - bot_last_message).total_seconds()

        if ecart >= 600:
            channel = discord.utils.get(bot.get_all_channels(), name="général")
            try:
                message = await channel.send("Je suis toujours là 👀")
                bot_last_message = datetime.datetime.utcnow()
                await asyncio.sleep(5)
                await message.delete()
            except Exception as e:
                print("❌ Erreur lors de l’envoi/suppression :", e)
        await asyncio.sleep(60)


#################### Bot Launch ####################

bot.run(token)
