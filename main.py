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
bot_ready = False
cache_canales = []
cache_voice = {}

@app.route('/voice/<channel_id>')
def get_voice_members(channel_id):
    cid = int(channel_id)

    # If bot isn't ready yet (cold start), wait a bit
    if not bot_ready:
        import time
        for _ in range(15):  # wait up to 15s for bot to connect
            if bot_ready:
                break
            time.sleep(1)
        if not bot_ready:
            return jsonify({"error": "Bot aún conectando, intenta en 10s"}), 503

    # Force fresh re-chunk and WAIT
    if bot_loop and not client.is_closed():
        try:
            future = asyncio.run_coroutine_threadsafe(refresh_voice_cache(), bot_loop)
            future.result(timeout=10)
        except Exception as e:
            print(f'Refresh error: {e}', flush=True)
            # Still try with whatever cache we have

    members = cache_voice.get(cid, None)
    if members is None:
        # Debug: print what channels we DO have
        print(f'Canal {cid} no encontrado. Canales en cache: {list(cache_voice.keys())}', flush=True)
        return jsonify({"error": "Canal no encontrado", "canales_disponibles": list(str(k) for k in cache_voice.keys())}), 404

    return jsonify({"members": members})

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "bot_ready": bot_ready,
        "guilds": len(client.guilds) if bot_ready else 0,
        "voice_channels_cached": len(cache_voice)
    })

@app.route('/canales')
def listar_canales():
    # Force refresh if bot is ready
    if bot_ready and bot_loop and not client.is_closed():
        try:
            future = asyncio.run_coroutine_threadsafe(refresh_voice_cache(), bot_loop)
            future.result(timeout=5)
        except:
            pass
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
        # Method 1: iterate voice channels
        for channel in guild.voice_channels:
            members_in_channel = [
                member.display_name
                for member in guild.members
                if member.voice and member.voice.channel and member.voice.channel.id == channel.id
            ]
            voice[channel.id] = members_in_channel
            if members_in_channel:
                print(f'  Voz "{channel.name}" ({channel.id}): {len(members_in_channel)} — {members_in_channel}', flush=True)

        # Method 2: also check stage channels
        for channel in guild.stage_channels:
            members_in_channel = [
                member.display_name
                for member in guild.members
                if member.voice and member.voice.channel and member.voice.channel.id == channel.id
            ]
            if members_in_channel:
                voice[channel.id] = members_in_channel

    cache_canales = canales
    cache_voice = voice
    total = sum(len(v) for v in voice.values())
    print(f'Cache OK: {len(canales)} canales, {len(voice)} voz, {total} usuarios', flush=True)

async def refresh_voice_cache():
    for guild in client.guilds:
        try:
            await guild.chunk(cache=True)
        except Exception as e:
            print(f'Chunk error {guild.name}: {e}', flush=True)
    actualizar_cache()

@client.event
async def on_ready():
    global bot_ready
    print(f'Bot conectado como {client.user}', flush=True)
    for guild in client.guilds:
        print(f'Servidor: {guild.name} ({guild.id})', flush=True)
        try:
            await guild.chunk(cache=True)
            print(f'Chunk OK: {guild.name} — {guild.member_count} miembros', flush=True)
        except Exception as e:
            print(f'Chunk error: {e}', flush=True)
    actualizar_cache()
    bot_ready = True
    print('=== BOT READY ===', flush=True)

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
