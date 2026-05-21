import discord
from flask import Flask, jsonify
from flask_cors import CORS
import asyncio
import threading
import os
import time
import copy

app = Flask(__name__)
CORS(app)

intents = discord.Intents.all()
client = discord.Client(intents=intents)
bot_loop = None
bot_ready = False
last_voice_event = None

DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN', '')

_cache_lock = threading.Lock()
_voice_cache = {}  # channel_id (int) -> [display_name, ...]


def full_rebuild():
    """Reconstruye cache completa desde guild.members."""
    global _voice_cache
    new_cache = {}
    for guild in client.guilds:
        for member in guild.members:
            if member.voice and member.voice.channel:
                cid = member.voice.channel.id
                if cid not in new_cache:
                    new_cache[cid] = []
                new_cache[cid].append(member.display_name)
    with _cache_lock:
        _voice_cache = new_cache
    total = sum(len(v) for v in new_cache.values())
    print(f'[full_rebuild] {total} usuarios en voz', flush=True)


def apply_voice_update(member_name, before_channel_id, after_channel_id):
    """Aplica un cambio puntual a la cache sin depender de guild.members."""
    with _cache_lock:
        # Quitar del canal anterior
        if before_channel_id and before_channel_id in _voice_cache:
            _voice_cache[before_channel_id] = [
                n for n in _voice_cache[before_channel_id] if n != member_name
            ]
            if not _voice_cache[before_channel_id]:
                del _voice_cache[before_channel_id]

        # Añadir al canal nuevo
        if after_channel_id:
            if after_channel_id not in _voice_cache:
                _voice_cache[after_channel_id] = []
            if member_name not in _voice_cache[after_channel_id]:
                _voice_cache[after_channel_id].append(member_name)

        # Log resultado
        total = sum(len(v) for v in _voice_cache.values())
        print(f'[apply] Cache: {total} usuarios en voz', flush=True)


def get_cache():
    with _cache_lock:
        return copy.deepcopy(_voice_cache)


@app.route('/voice/<channel_id>')
def get_voice_members(channel_id):
    cid = int(channel_id)
    if not bot_ready:
        for _ in range(20):
            if bot_ready: break
            time.sleep(1)
        if not bot_ready:
            return jsonify({"error": "Bot aún conectando"}), 503

    cache = get_cache()
    members = cache.get(cid, [])
    print(f'[/voice/{cid}] → {len(members)} miembros', flush=True)
    return jsonify({"members": members})


@app.route('/debug')
def debug():
    cache = get_cache()
    return jsonify({
        "bot_ready": bot_ready,
        "is_closed": client.is_closed(),
        "last_voice_event": last_voice_event,
        "voice_cache": {str(k): v for k, v in cache.items()},
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

    # Aplicar cambio directamente — no depender de guild.members
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