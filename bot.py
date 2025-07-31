import discord
from discord.ext import commands
import time
import os
from dotenv import load_dotenv
from flask import Flask
import threading

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True  # Nécessaire pour lire le contenu des messages

bot = commands.Bot(command_prefix="$", intents=intents, description="Bot du C.I.F.")

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

@bot.event
async def on_member_join(member):
    guild = member.guild

    # Récupère les rôles
    arrivant_role = discord.utils.get(guild.roles, name="Arrivant")
    modo_role = discord.utils.get(guild.roles, name="Modérateur")

    # Donne le rôle "Arrivant"
    if arrivant_role:
        await member.add_roles(arrivant_role)

    # Crée un salon privé de présentation
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        modo_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    channel_name = f"présentation-{member.name.lower()}"
    presentation_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, reason="Salon de présentation privé")

    await presentation_channel.send(
        f"👋 Bienvenue {member.mention} !\nMerci d'écrire ici une petite **présentation** (prénom, centres d’intérêt, pourquoi tu rejoins le serveur, etc.).\nUn modérateur te validera rapidement. 😊"
    )



#################### Bot Commands ####################

### Modérateurs

# Autorise la présentation d'un arrivant : $welcome
@bot.command()
@commands.has_role("Modérateur")
async def welcome(ctx):
    channel = ctx.channel
    guild = ctx.guild

    # Vérifie que c’est un salon de présentation
    if not channel.name.startswith("présentation-"):
        await ctx.send("❌ Cette commande ne peut être utilisée que dans un salon de présentation.")
        return

    # Récupère le membre à partir du nom du salon
    member_name = channel.name.replace("présentation-", "")
    member = discord.utils.find(lambda m: m.name.lower() == member_name, guild.members)

    if not member:
        await ctx.send("❌ Membre non trouvé.")
        return

    # Récupère les rôles
    membre_role = discord.utils.get(guild.roles, name="Membre")
    arrivant_role = discord.utils.get(guild.roles, name="Arrivant")

    # Récupère le message de présentation le plus ancien de l'utilisateur
    messages = [msg async for msg in channel.history(limit=50, oldest_first=True)]
    user_message = next((m for m in messages if m.author == member), None)

    if not user_message:
        await ctx.send("❌ Aucun message de présentation trouvé.")
        return

    # Trouve le salon #présentation
    public_channel = discord.utils.get(guild.text_channels, name="présentation")
    if not public_channel:
        await ctx.send("❌ Le salon #présentation n'existe pas.")
        return

    # Transfère la présentation
    await public_channel.send(f"📣 **{member.mention} s’est présenté·e :**\n{user_message.content}")

    # Attribue le rôle "Membre" et retire "Arrivant"
    if membre_role:
        await member.add_roles(membre_role)
    if arrivant_role and arrivant_role in member.roles:
        await member.remove_roles(arrivant_role)

    # Supprime le salon
    await ctx.send("✅ Présentation acceptée. Ce salon sera supprimé dans 5 secondes.")
    await time.sleep(5)
    await channel.delete()


# Supprimer des messages : $clear <nombre>
@bot.command()
@commands.has_role("Modérateur")
async def clear(ctx, nombre: int):
    await ctx.channel.purge(limit = nombre+1)
    await ctx.send(f"✅ {nombre} messages ont été supprimés.")
    time.sleep(2)
    await ctx.channel.purge(limit = 1)

# Kick un membre : $kick <membre> <raison>
@bot.command()
@commands.has_role("Modérateur")
async def kick(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.kick(reason=reason)
    await ctx.channel.purge(limit = 1)
    await ctx.send(f"✅ {member.mention} a été kick par {ctx.author.mention} pour la raison :\n{reason}.")
    try :
        await member.send(f"❌ Vous avez été kick du serveur {ctx.guild.name} par {ctx.author.mention} pour la raison suivante :\n{reason}.")
    except :
        await ctx.send(f"❌ {member.mention} n'a pas pu être averti.")
        print("Impossible d'envoyer un message à ce membre.")

# Ban un membre : $ban <membre> <raison>
@bot.command()
@commands.has_role("Modérateur")
async def ban(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.ban(reason=reason)
    await ctx.channel.purge(limit = 1)
    await ctx.send(f"✅ {member.mention} a été ban par {ctx.author.mention} pour la raison :\n{reason}.")
    try :
        await member.send(f"❌ Vous avez été ban du serveur {ctx.guild.name} par {ctx.author.mention} pour la raison suivante :\n{reason}.")
    except :
        await ctx.send(f"❌ {member.mention} n'a pas pu être averti.")
        print("Impossible d'envoyer un message à ce membre.")

# Warn un membre : $warn <membre> <raison>\
@bot.command()
@commands.has_role("Modérateur")
async def warn(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await ctx.channel.purge(limit = 1)
    await ctx.send(f"⚠️ Attention, {member.mention}, votre comportement pourrait avoir des conséquences !\nMessage de {ctx.author.mention} car : {reason}.")
    try :
        await member.send(f"⚠️ Attention, votre comportement pourrait avoir des conséquences !\nMessage de {ctx.author.mention} car : {reason}.")
    except :
        print("Impossible d'envoyer un message à ce membre.")

# Mute un membre : $mute <membre> <raison>
@bot.command()
@commands.has_role("Modérateur")
async def mute(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    mute_role = discord.utils.get(ctx.guild.roles, name="Muet")

    if not mute_role:
        mute_role = await ctx.guild.create_role(name="Muet")
        for channel in ctx.guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
    
    await member.add_roles(mute_role, reason=reason)
    await ctx.channel.purge(limit = 1)
    await ctx.send(f"✅ {member.mention} a été mute par {ctx.author.mention} pour la raison suivante :\n{reason}.")
    try :
        await member.send(f"❌ Vous avez été mute du serveur {ctx.guild.name} par {ctx.author.mention} pour la raison suivante :\n{reason}.")
    except :
        await ctx.send(f"❌ {member.mention} n'a pas pu être averti.")
        print("Impossible d'envoyer un message à ce membre.")

# Unmute un membre : $unmute <membre>
@bot.command()
@commands.has_role("Modérateur")
async def unmute(ctx, member: discord.Member):
    await ctx.channel.purge(limit = 1)
    mute_role = discord.utils.get(ctx.guild.roles, name="Muet")
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await ctx.send(f"✅ {member.mention} a été unmute par {ctx.author.mention}.")
        try :
            await member.send(f"✅ Vous avez été unmute du serveur {ctx.guild.name} par {ctx.author.mention}.")
        except :
            print("Impossible d'envoyer un message à ce membre.")
    else :
        await ctx.send(f"❌ {member.mention} n'était pas mute.")


### @everyone

# Obtenir le lien d'invitation du serveur : $invite
@bot.command()
async def invite(ctx):
    await ctx.send("🔗 Voici le lien d'invitation du serveur : https://discord.gg/qwKMe6FeKT")
    await ctx.send("⚠️ Veuillez ne l'envoyer qu'à des personnes réellement intéressées, et ne pas le communiquer aux personnes qui se sont faites kick.")

# Dire bonjour : $hello
@bot.command()
async def hello(ctx):
    await ctx.send("Salut ! 👋")

# Commande simple : $aide
@bot.command()
async def aide(ctx):
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


#################### Bot Errors ####################

# Gestion des erreurs
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Commande inconnue. Tape $aide pour voir les commandes.")
    else:
        await ctx.send("❗ Une erreur est survenue. Raisons possibles :\n- Vous n'avez pas les permissions nécessaires.\n- Vous n'avez pas ou mal mentionné le membre.")
        raise error  # Affiche l'erreur dans la console pour le développeur


#################### Bot Launch ####################

bot.run(token)
