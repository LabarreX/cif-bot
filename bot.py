import discord
from discord.ext import commands, tasks
import asyncio
import os
import datetime
import json
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

events = {}
try:
    with open("events.json", "r") as f:
        events = json.load(f)
except:
    pass

##################### Bot Events #####################

# Lancement
@bot.event
async def on_ready():
    for guild in bot.guilds:
        await bot.tree.sync(guild=guild)
    print(f"✅ Connecté en tant que {bot.user}")
    await bot.change_presence(activity=discord.Game(name="aider le C.I.F."))
    event_reminder_loop.start()

# Rappel des événements
@tasks.loop(hours=24)
async def event_reminder_loop():
    await bot.wait_until_ready()
    today = datetime.datetime.utcnow()

    for guild in bot.guilds:
        annonces_channel = discord.utils.get(guild.text_channels, name="annonces")
        if not annonces_channel:
            continue  # saute si pas de canal "annonces"

        for event_id, event_data in events.items():
            event_time = datetime.datetime.strptime(event_data["datetime"], "%Y-%m-%d %H:%M")
            delta = event_time - today

            if delta.days == 1:
                participants = event_data["participants"]
                nom = event_data["nom"]
                desc = event_data["description"]
                date_str = event_time.strftime("%d/%m à %H:%M")

                # Message à envoyer
                reminder_msg = f"📣 Rappel : l’événement **{nom}** aura lieu **demain ({date_str})** !\nDescription : {desc}"

                # Envoi DM aux participants
                for user_id in participants:
                    user = await bot.fetch_user(int(user_id))
                    try:
                        await user.send(reminder_msg)
                    except:
                        print(f"Impossible d’envoyer un DM à {user.name}.")

                # Annonce publique
                await annonces_channel.send(reminder_msg)

# Nouveaux membres
@bot.event
async def on_member_join(member):
    guild = member.guild

    # Rôles
    arrivant_role = discord.utils.get(guild.roles, name="Arrivant")
    modo_role = discord.utils.get(guild.roles, name="Modérateur")

    # Retire tous les autres rôles sauf @everyone
    await member.edit(roles=[arrivant_role])

    # Crée un salon privé
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        modo_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True)
    }

    channel_name = f"présentation-{member.name.lower()}"
    presentation_channel = await guild.create_text_channel(
        channel_name,
        overwrites=overwrites,
        reason="Salon de présentation privé"
    )

    await presentation_channel.send(
        f"👋 Bienvenue {member.mention} !\nMerci d'écrire ici une petite **présentation** (prénom, centres d’intérêt, etc.).\nUn modérateur te validera ensuite. 😊"
    )


#################### Bot Commands ####################

### Modérateurs

# Autorise la présentation d'un arrivant : $welcome
@bot.hybrid_command(description = "Accepter la présentation d'un nouveau membre")
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
    public_channel = discord.utils.get(guild.text_channels, name="👋🏻-présentation-👋🏻")
    if not public_channel:
        await ctx.send("❌ Le salon #présentation n'existe pas.")
        return

    # Transfère la présentation
    await public_channel.send(f"**📣 Présentation de {member.mention} :**\n{user_message.content}")

    # Attribue le rôle "Membre" et retire "Arrivant"
    if membre_role:
        await member.add_roles(membre_role)
    if arrivant_role and arrivant_role in member.roles:
        await member.remove_roles(arrivant_role)

    # Supprime le salon
    await ctx.send("✅ Présentation acceptée. Ce salon sera supprimé dans 5 secondes.")
    await asyncio.sleep(5)
    await channel.delete()

# Active le slowmode : $slowmode <durée (secondes)>
@bot.hybrid_command(description = "Active le slowmode sur le salon où cette commande est utilisée")
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"🐢 Mode lent défini à {seconds} seconde(s).")

# Supprimer des messages : $clear <nombre>
@bot.hybrid_command(description = "Supprime les x derniers messages")
@commands.has_role("Modérateur")
async def clear(ctx, nombre: int):
    # Supprime la commande de l'historique seulement si c'est en prefix ($)
    if ctx.message:
        await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=nombre)
    confirmation = await ctx.send(f"✅ {len(deleted)} messages ont été supprimés.")
    await asyncio.sleep(2)
    await confirmation.delete()

# Kick un membre : $kick <membre> <raison>
@bot.hybrid_command(description = "Kick le membre sélectionné et lui envoie un message")
@commands.has_role("Modérateur")
async def kick(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.kick(reason=reason)
    await ctx.send(f"✅ {member.mention} a été kick par {ctx.author.mention} pour la raison :\n{reason}.")
    try :
        await member.send(f"❌ Vous avez été kick du serveur {ctx.guild.name} par {ctx.author.mention} pour la raison suivante :\n{reason}.")
    except :
        await ctx.send(f"❌ {member.mention} n'a pas pu être averti.")
        print("Impossible d'envoyer un message à ce membre.")

# Ban un membre : $ban <membre> <raison>
@bot.hybrid_command(description = "Ban le membre sélectionné et lui envoie un message")
@commands.has_role("Modérateur")
async def ban(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.ban(reason=reason)
    await ctx.send(f"✅ {member.mention} a été ban par {ctx.author.mention} pour la raison :\n{reason}.")
    try :
        await member.send(f"❌ Vous avez été ban du serveur {ctx.guild.name} par {ctx.author.mention} pour la raison suivante :\n{reason}.")
    except :
        await ctx.send(f"❌ {member.mention} n'a pas pu être averti.")
        print("Impossible d'envoyer un message à ce membre.")

# Warn un membre : $warn <membre> <raison>\
@bot.hybrid_command(description = "Préviens le membre sélectionné de son mauvais comportment")
@commands.has_role("Modérateur")
async def warn(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await ctx.send(f"⚠️ Attention, {member.mention}, votre comportement pourrait avoir des conséquences !\nMessage de {ctx.author.mention} car : {reason}.")
    try :
        await member.send(f"⚠️ Attention, votre comportement pourrait avoir des conséquences !\nMessage de {ctx.author.mention} car : {reason}.")
    except :
        print("Impossible d'envoyer un message à ce membre.")

# Mute un membre : $mute <membre> <raison>
@bot.hybrid_command(description = "Mute le membre sélectionné")
@commands.has_role("Modérateur")
async def mute(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    mute_role = discord.utils.get(ctx.guild.roles, name="Muet")
    membre_role = discord.utils.get(ctx.guild.roles, name="Membre")

    if not mute_role:
        mute_role = await ctx.guild.create_role(name="Muet")
        for channel in ctx.guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
    
    await member.add_roles(mute_role, reason=reason)
    await member.remove_roles(membre_role)
    await ctx.send(f"✅ {member.mention} a été mute par {ctx.author.mention} pour la raison suivante :\n{reason}.")
    try :
        await member.send(f"❌ Vous avez été mute du serveur {ctx.guild.name} par {ctx.author.mention} pour la raison suivante :\n{reason}.")
    except :
        await ctx.send(f"❌ {member.mention} n'a pas pu être averti.")
        print("Impossible d'envoyer un message à ce membre.")

# Unmute un membre : $unmute <membre>
@bot.hybrid_command(description = "Unmute le membre sélectionné")
@commands.has_role("Modérateur")
async def unmute(ctx, member: discord.Member):
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

# Gestion des événements
@bot.hybrid_command(description = "Permet de créer, annuler, s'inscrire de ou se désinscrire d'un événement")
async def event(ctx, action, args):
    global events
    args = args.split()

    if action == "create":
        if not discord.utils.get(ctx.author.roles, name="Modérateur"):
            return await ctx.send("🚫 Seuls les modérateurs peuvent créer un événement.")
        if len(args) < 3:
            return await ctx.send("❌ Utilisation : `$event create [nom] [date JJ/MM] [heure HH:MM] [description (optionnelle)]`")
        
        nom, date_str, heure_str, *desc_parts = args
        
        description = " ".join(desc_parts)
        dt = datetime.datetime.strptime(f"{date_str} {heure_str}", "%d/%m %H:%M")
        try :
            event_id = max([eid for eid, e in events.items()])+1
        except :
            event_id = 0

        events[event_id] = {
            "nom": nom,
            "datetime": dt.strftime("%Y-%m-%d %H:%M"),
            "description": description,
            "participants": [str(ctx.author.id)]
        }

        with open("events.json", "w") as f:
            json.dump(events, f)

        await ctx.send(f"✅ Événement **{nom}** créé par {ctx.author.mention} pour le **{date_str} à {heure_str}** avec l’ID `{event_id}`.")

    elif action == "list":
        if not events:
            return await ctx.send("📭 Aucun événement.")
        msg = "📅 Événements à venir :\n"
        for eid, e in events.items():
            date = datetime.datetime.strptime(e["datetime"], "%Y-%m-%d %H:%M")
            msg += f"- **{e['nom']}** ({eid}) — {date.strftime('%d/%m %H:%M')} — {len(e['participants'])} participant(s)\n"
        await ctx.send(msg)

    elif action == "join":
        if len(args) != 1:
            return await ctx.send("❌ Utilisation : `$event join [id]`")

        eid = int(args[0])
        if eid not in events:
            return await ctx.send("❌ ID invalide.")
        user_id = str(ctx.author.id)
        if user_id in events[eid]["participants"]:
            return await ctx.send("❗ Tu es déjà inscrit.")
        events[eid]["participants"].append(user_id)
        with open("events.json", "w") as f:
            json.dump(events, f)
        await ctx.send(f"✅ {ctx.author.mention}, tu participes bien à **{events[eid]['nom']}** !")

    elif action == "leave":
        if len(args) != 1:
            return await ctx.send("❌ Utilisation : `$event leave [id]`")

        eid = int(args[0])
        if eid not in events:
            return await ctx.send("❌ ID invalide.")

        user_id = str(ctx.author.id)
        if user_id not in events[eid]["participants"]:
            return await ctx.send("❌ Tu ne participes pas à cet événement.")
        events[eid]["participants"].remove(user_id)
        with open("events.json", "w") as f:
            json.dump(events, f)

        await ctx.send(f"🚪 {ctx.author.mention}, tu t’es bien désinscrit de **{events[eid]['nom']}**.")

    elif action == "cancel":
        if not discord.utils.get(ctx.author.roles, name="Modérateur"):
            return await ctx.send("🚫 Seuls les modérateurs peuvent annuler un événement.")
        if len(args) != 1:
            return await ctx.send("❌ Utilisation : `$event cancel [id]`")
        eid = int(args[0])
        if eid in events:
            del events[eid]
            with open("events.json", "w") as f:
                json.dump(events, f)
            await ctx.send(f"❌ Événement `{eid}` annulé par {ctx.author.mention}.")
        else:
            await ctx.send("❌ ID introuvable.")

    elif action == "info":
        for arg in args :
            eid = int(arg)
            if eid in events :
                e = events[eid]
                date = datetime.datetime.strptime(e["datetime"], "%Y-%m-%d %H:%M")
                await ctx.send(f"**{e['nom']}** (ID : {eid}) aura lieu le {date.strftime('%d/%m %H:%M').split()[0]} à {date.strftime('%d/%m %H:%M').split()[1]}.\n{len(e['participants'])} participants sont inscrits.\nDescription : {e['description']} ")
            else :
                await ctx.send(f"L'événement {eid} m'existe pas.")
    else :
        await ctx.send("❌ Les commandes disponibles sont :\n`join`, `info` et `leave`,\nainsi que `create` et `cancel` pour les modérateurs.")

# Obtenir le lien d'invitation du serveur : $invite
@bot.hybrid_command(description = "Permet d'obtenir le lien d'invitation du serveur")
async def invite(ctx):
    await ctx.send("🔗 Voici le lien d'invitation du serveur : https://discord.gg/7M2CUX7Qmw")
    await ctx.send("⚠️ Veuillez ne l'envoyer qu'à des personnes réellement intéressées, et ne pas le communiquer aux personnes qui se sont faites kick.")

# Dire bonjour : $hello
@bot.hybrid_command(description = "Réponds salut")
async def hello(ctx):
    await ctx.send("Salut ! 👋")

# Commande simple : $aide
@bot.hybrid_command(description = "Affiche toutes les commandes disponibles")
async def aide(ctx):
    msg = (
        "Voici les commandes disponibles :\n"
        "invite — Fournit le lien d'invitation du serveur\n"
        "hello — Réponds Salut\n"
        "aide — Affiche ce message\n"
    )

    # Si l'auteur a le rôle "Modérateur", on ajoute les commandes modération
    if discord.utils.get(ctx.author.roles, name="Modérateur"):
        msg += (
            "\n🔧 Commandes Modération :\n"
            "warn <@membre> <raison> — Avertit un membre\n"
            "kick <@membre> <raison> — Expulse un membre\n"
            "ban <@membre> <raison> — Bannit un membre\n"
            "mute <@membre> <raison> — Rend muet (texte)\n"
            "unmute <@membre> — Enlève le rôle Muet\n"
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
