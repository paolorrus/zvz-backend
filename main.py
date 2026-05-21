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


def actualizar_cache():
    global cache_canales, cache_voice
    canales = []
    voice = {}
    for guild in client.guilds:
        for channel in guild.channels:
            canales.append({"id": str(channel.id), "nombre": channel.name, "tipo": str(channel.type)})
        for channel in guild.voice_channels:
            members_in = [m.display_name for m in channel.members]
            voice[channel.id] = members_in
            if members_in:
                print(f'  Voz "{channel.name}" ({channel.id}): {len(members_in)} — {members_in}', flush=True)
        for channel in guild.stage_channels:
            members_in = [m.display_name for m in channel.members]
            if members_in:
                voice[channel.id] = members_in
    cache_canales = canales
    cache_voice = voice
    total = sum(len(v) for v in voice.values())
    print(f'Cache OK: {len(canales)} canales, {len(voice)} voz, {total} usuarios', flush=True)


async def rechunk_and_refresh():
    """Re-chunk all guilds to get fresh member data, then rebuild cache."""
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
    print(f'[VoiceUpdate] {member.display_name}: {getattr(before.channel,"name","None")} → {getattr(after.channel,"name","None")}', flush=True)


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

    # ── Siempre re-chunk antes de responder para datos frescos ──
    if bot_loop and not client.is_closed():
        try:
            future = asyncio.run_coroutine_threadsafe(rechunk_and_refresh(), bot_loop)
            future.result(timeout=15)
        except Exception as e:
            print(f'Re-chunk error: {e}', flush=True)

    # Leer directo del objeto canal (siempre fresco tras el chunk)
    live_members = None
    for guild in client.guilds:
        for channel in list(guild.voice_channels) + list(guild.stage_channels):
            if channel.id == cid:
                live_members = [m.display_name for m in channel.members]
                break
        if live_members is not None:
            break

    if live_members is None:
        print(f'Canal {cid} no encontrado. Disponibles: {list(cache_voice.keys())}', flush=True)
        return jsonify({"error": "Canal no encontrado", "canales_disponibles": [str(k) for k in cache_voice.keys()]}), 404

    print(f'[/voice/{cid}] → {len(live_members)} miembros: {live_members}', flush=True)
    return jsonify({"members": live_members})


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
    actualizar_cache()
    return jsonify(cache_canales)


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