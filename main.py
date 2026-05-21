import discord
from flask import Flask, jsonify
from flask_cors import CORS
import asyncio
import threading
import os

app = Flask(__name__)
CORS(app)

intents = discord.Intents.all()
client = discord.Client(intents=intents)
bot_loop = None
cache_canales = []
cache_voice = {}  # channel_id -> [members]

@app.route('/voice/<channel_id>')
def get_voice_members(channel_id):
    # Force a fresh re-chunk and WAIT for it before responding
    if bot_loop and not client.is_closed():
        future = asyncio.run_coroutine_threadsafe(refresh_voice_cache(), bot_loop)
        try:
            future.result(timeout=8)  # wait up to 8s for fresh data
        except Exception as e:
            print(f'Refresh timeout/error: {e}', flush=True)

    members = cache_voice.get(int(channel_id), None)
    if members is None:
        return jsonify({"error": "Canal no encontrado"}), 404

    return jsonify({"members": members})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "bot_ready": not client.is_closed()})

@app.route('/canales')
def listar_canales():
    return jsonify(cache_canales)

def actualizar_cache():
    global cache_canales, cache_voice
    canales = []
    voice = {}
    for guild in client.guilds:
        for channel in guild.channels:
            canales.append({
                "id": str(channel.id),
                "nombre": channel.name,
                "tipo": str(channel.type)
            })
        for channel in guild.voice_channels:
            members_in_channel = [
                member.display_name
                for member in guild.members
                if member.voice and member.voice.channel and member.voice.channel.id == channel.id
            ]
            voice[channel.id] = members_in_channel
            if members_in_channel:
                print(f'Canal voz "{channel.name}": {len(members_in_channel)} — {members_in_channel}', flush=True)

    cache_canales = canales
    cache_voice = voice
    print(f'Cache actualizada: {sum(len(v) for v in voice.values())} usuarios en voz', flush=True)

async def refresh_voice_cache():
    for guild in client.guilds:
        try:
            await guild.chunk(cache=True)
        except Exception as e:
            print(f'chunk error {guild.name}: {e}', flush=True)
    actualizar_cache()

@client.event
async def on_ready():
    print(f'Bot conectado como {client.user}', flush=True)
    for guild in client.guilds:
        print(f'Servidor: {guild.name} ({guild.id})', flush=True)
        try:
            await guild.chunk(cache=True)
            print(f'Chunk OK: {guild.name} — {guild.member_count} miembros', flush=True)
        except Exception as e:
            print(f'Chunk error: {e}', flush=True)
    actualizar_cache()
    print('Sync completado', flush=True)

@client.event
async def on_voice_state_update(member, before, after):
    actualizar_cache()

def run_discord():
    global bot_loop
    try:
        token = os.environ.get('DISCORD_TOKEN')
        if not token:
            print('ERROR: DISCORD_TOKEN no definido', flush=True)
            return
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)
        bot_loop.run_until_complete(client.start(token))
    except Exception as e:
        print(f'ERROR bot: {e}', flush=True)

threading.Thread(target=run_discord, daemon=True).start()
