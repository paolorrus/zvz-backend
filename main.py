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
            voice[channel.id] = [m.display_name for m in channel.members]
    cache_canales = canales
    cache_voice = voice
    print(f'Cache actualizada: {len(canales)} canales, {len(voice)} canales de voz', flush=True)

@client.event
async def on_ready():
    print(f'Bot conectado como {client.user}', flush=True)
    for guild in client.guilds:
        print(f'Servidor: {guild.name} ({guild.id})', flush=True)
        await guild.chunk()
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
