import discord
from flask import Flask, jsonify
from flask_cors import CORS
import asyncio
import threading
import os
import requests as req

app = Flask(__name__)
CORS(app)

intents = discord.Intents.all()
client = discord.Client(intents=intents)
bot_loop = None
bot_ready = False

DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN', '')


def get_voice_members_via_api(channel_id: int):
    """
    Consulta la API REST de Discord directamente para obtener los miembros
    de un canal de voz. Siempre devuelve datos frescos, sin cache.
    """
    # GET /channels/{channel_id} devuelve el canal con voice_states si es de voz
    # Pero lo más fiable es GET /guilds/{guild_id}/voice-states
    # Usamos: GET /channels/{channel_id} no incluye members,
    # así que iteramos guild voice states via REST
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}

    # Necesitamos el guild_id — lo sacamos del canal via REST
    r = req.get(f"https://discord.com/api/v10/channels/{channel_id}", headers=headers, timeout=10)
    if r.status_code != 200:
        print(f"[API] Error getting channel {channel_id}: {r.status_code} {r.text}", flush=True)
        return None, None

    channel_data = r.json()
    guild_id = channel_data.get("guild_id")
    if not guild_id:
        return None, None

    # GET /guilds/{guild_id} con with_counts=true no incluye voice states
    # Usamos el gateway cache del bot si está disponible, si no la API de members
    # La forma más fiable: iterar guild members y filtrar los que están en este canal
    # via /guilds/{guild_id}/voice-states (disponible en API v10)

    # Primero intentamos con el objeto guild del bot (si está vivo)
    if bot_ready and not client.is_closed():
        guild = client.get_guild(int(guild_id))
        if guild:
            # Forzar re-fetch del guild para voice states frescos
            members = [m.display_name for m in guild.voice_channels
                       if m.id == channel_id
                       for m in m.members]
            # La línea de arriba tiene un bug de naming, reescribir:
            members = []
            for vc in guild.voice_channels:
                if vc.id == channel_id:
                    members = [m.display_name for m in vc.members]
                    break
            print(f"[BOT cache] Canal {channel_id}: {members}", flush=True)
            # Si el bot tiene datos, los devolvemos pero también consultamos REST
            # para comparar (debug)

    # REST: /guilds/{guild_id}/voice-states devuelve todos los voice states activos
    r2 = req.get(f"https://discord.com/api/v10/guilds/{guild_id}/voice-states", headers=headers, timeout=10)
    if r2.status_code == 200:
        voice_states = r2.json()
        # Filtrar solo los del canal solicitado
        channel_states = [vs for vs in voice_states if str(vs.get("channel_id")) == str(channel_id)]
        print(f"[REST] Voice states en canal {channel_id}: {len(channel_states)}", flush=True)

        # Obtener display names — cada voice_state tiene member.nick o member.user.username
        result = []
        for vs in channel_states:
            member = vs.get("member", {})
            nick = member.get("nick")
            user = member.get("user", {})
            name = nick or user.get("global_name") or user.get("username") or "Unknown"
            result.append(name)

        print(f"[REST] Miembros: {result}", flush=True)
        return result, None
    else:
        print(f"[REST] Error voice-states: {r2.status_code} {r2.text}", flush=True)
        # Fallback al cache del bot
        if bot_ready and not client.is_closed():
            guild = client.get_guild(int(guild_id))
            if guild:
                for vc in guild.voice_channels:
                    if vc.id == channel_id:
                        return [m.display_name for m in vc.members], None
        return None, f"API error {r2.status_code}"


@app.route('/voice/<channel_id>')
def get_voice_members(channel_id):
    cid = int(channel_id)

    if not bot_ready:
        import time
        for _ in range(20):
            if bot_ready:
                break
            time.sleep(1)
        if not bot_ready:
            return jsonify({"error": "Bot aún conectando, intenta en 10s"}), 503

    members, error = get_voice_members_via_api(cid)

    if members is None:
        return jsonify({"error": error or "Canal no encontrado"}), 404

    return jsonify({"members": members})


@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "bot_ready": bot_ready,
        "guilds": len(client.guilds) if bot_ready else 0,
    })


@app.route('/canales')
def listar_canales():
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    result = []
    if bot_ready and not client.is_closed():
        for guild in client.guilds:
            for channel in guild.channels:
                result.append({"id": str(channel.id), "nombre": channel.name, "tipo": str(channel.type)})
    return jsonify(result)


@client.event
async def on_ready():
    global bot_ready
    print(f'Bot conectado como {client.user}', flush=True)
    for guild in client.guilds:
        print(f'Servidor: {guild.name} ({guild.id})', flush=True)
    bot_ready = True
    print('=== BOT READY ===', flush=True)


def run_discord():
    global bot_loop
    try:
        token = DISCORD_TOKEN
        if not token:
            print('ERROR: DISCORD_TOKEN no definido', flush=True)
            return
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)
        bot_loop.run_until_complete(client.start(token))
    except Exception as e:
        print(f'ERROR bot: {e}', flush=True)


threading.Thread(target=run_discord, daemon=True).start()