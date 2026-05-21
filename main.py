import discord
from flask import Flask, jsonify
from flask_cors import CORS
import asyncio
import threading
import os
import time
import json

app = Flask(__name__)
CORS(app)

intents = discord.Intents.all()
client = discord.Client(intents=intents)
bot_loop = None
bot_ready = False
last_voice_event = None

DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN', '')
CACHE_FILE = '/tmp/voice_cache.json'


def save_cache(data):
    """Escribe cache a disco — compartido entre todos los threads."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f'[save_cache error] {e}', flush=True)


def load_cache():
    """Lee cache de disco."""
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def full_rebuild():
    """Reconstruye cache completa desde guild.members."""
    new_cache = {}
    for guild in client.guilds:
        for member in guild.members:
            if member.voice and member.voice.channel:
                cid = str(member.voice.channel.id)
                if cid not in new_cache:
                    new_cache[cid] = []
                new_cache[cid].append(member.display_name)
    save_cache(new_cache)
    total = sum(len(v) for v in new_cache.values())
    print(f'[full_rebuild] {total} usuarios en voz', flush=True)


def apply_voice_update(member_name, before_channel_id, after_channel_id):
    """Aplica un cambio puntual a la cache."""
    cache = load_cache()

    b_key = str(before_channel_id) if before_channel_id else None
    a_key = str(after_channel_id) if after_channel_id else None

    # Quitar del canal anterior
    if b_key and b_key in cache:
        cache[b_key] = [n for n in cache[b_key] if n != member_name]
        if not cache[b_key]:
            del cache[b_key]

    # Añadir al canal nuevo
    if a_key:
        if a_key not in cache:
            cache[a_key] = []
        if member_name not in cache[a_key]:
            cache[a_key].append(member_name)

    save_cache(cache)
    total = sum(len(v) for v in cache.values())
    print(f'[apply] {member_name} → Cache: {total} usuarios', flush=True)


@app.route('/voice/<channel_id>')
def get_voice_members(channel_id):
    if not bot_ready:
        for _ in range(20):
            if bot_ready: break
            time.sleep(1)
        if not bot_ready:
            return jsonify({"error": "Bot aún conectando"}), 503

    cache = load_cache()
    members = cache.get(channel_id, [])
    print(f'[/voice/{channel_id}] → {len(members)} miembros', flush=True)
    return jsonify({"members": members})


@app.route('/debug')
def debug():
    cache = load_cache()
    return jsonify({
        "bot_ready": bot_ready,
        "is_closed": client.is_closed(),
        "last_voice_event": last_voice_event,
        "voice_cache": cache,
    })


@app.route('/health')
def health():
    return jsonify({"status": "ok", "bot_ready": bot_ready})


@app.route('/canales')
def listar_canales():
    result = []
    for guild in client.guilds:
        for ch in guild.channels:
            result.append({"id": str(ch.id), "nombre": ch.name, "tipo": str(ch.type)})
    return jsonify(result)


@client.event
async def on_ready():
    global bot_ready
    print(f'Bot conectado: {client.user}', flush=True)
    for guild in client.guilds:
        try:
            await guild.chunk(cache=True)
            print(f'Chunk OK: {guild.name} — {guild.member_count} miembros', flush=True)
        except Exception as e:
            print(f'Chunk error: {e}', flush=True)
    full_rebuild()
    bot_ready = True
    print('=== BOT READY ===', flush=True)


@client.event
async def on_voice_state_update(member, before, after):
    global last_voice_event
    b_name = getattr(before.channel, 'name', 'None')
    a_name = getattr(after.channel, 'name', 'None')
    b_id = before.channel.id if before.channel else None
    a_id = after.channel.id if after.channel else None
    last_voice_event = f'{member.display_name}: {b_name} → {a_name} @ {time.strftime("%H:%M:%S")}'
    print(f'[Voice] {last_voice_event}', flush=True)
    apply_voice_update(member.display_name, b_id, a_id)


def run_discord():
    global bot_loop
    if not DISCORD_TOKEN:
        print('ERROR: DISCORD_TOKEN no definido', flush=True)
        return
    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)
    try:
        bot_loop.run_until_complete(client.start(DISCORD_TOKEN))
    except Exception as e:
        print(f'ERROR bot: {e}', flush=True)


threading.Thread(target=run_discord, daemon=False).start()