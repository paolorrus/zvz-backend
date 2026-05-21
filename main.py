import discord
from flask import Flask, jsonify
from flask_cors import CORS
import asyncio
import threading
import os
import time

app = Flask(__name__)
CORS(app)

intents = discord.Intents.all()
client = discord.Client(intents=intents)
bot_loop = None
bot_ready = False
last_voice_event = None

DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN', '')

voice_cache = {}

def rebuild_cache():
    global voice_cache
    new_cache = {}
    for guild in client.guilds:
        for member in guild.members:
            if member.voice and member.voice.channel:
                cid = member.voice.channel.id
                if cid not in new_cache:
                    new_cache[cid] = []
                new_cache[cid].append(member.display_name)
    voice_cache = new_cache


@app.route('/voice/<channel_id>')
def get_voice_members(channel_id):
    cid = int(channel_id)
    if not bot_ready:
        for _ in range(20):
            if bot_ready: break
            time.sleep(1)
        if not bot_ready:
            return jsonify({"error": "Bot aún conectando"}), 503

    members = voice_cache.get(cid, [])
    print(f'[/voice/{cid}] → {members}', flush=True)
    return jsonify({"members": members})


@app.route('/debug')
def debug():
    guild_info = []
    for guild in client.guilds:
        vc_info = []
        for vc in guild.voice_channels:
            vc_info.append({
                "name": vc.name,
                "id": str(vc.id),
                "members_via_vc": [m.display_name for m in vc.members],
                "members_via_guild": [
                    m.display_name for m in guild.members
                    if m.voice and m.voice.channel and m.voice.channel.id == vc.id
                ]
            })
        guild_info.append({
            "name": guild.name,
            "member_count": guild.member_count,
            "members_cached": len(guild.members),
            "voice_channels": vc_info
        })
    return jsonify({
        "bot_ready": bot_ready,
        "is_closed": client.is_closed(),
        "last_voice_event": last_voice_event,
        "voice_cache": {str(k): v for k, v in voice_cache.items()},
        "guilds": guild_info
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
    rebuild_cache()
    bot_ready = True
    print('=== BOT READY ===', flush=True)


@client.event
async def on_voice_state_update(member, before, after):
    global last_voice_event
    b = getattr(before.channel, 'name', 'None')
    a = getattr(after.channel, 'name', 'None')
    last_voice_event = f'{member.display_name}: {b} → {a} @ {time.strftime("%H:%M:%S")}'
    print(f'[Voice] {last_voice_event}', flush=True)
    rebuild_cache()
    print(f'[Voice] Cache: {voice_cache}', flush=True)


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


# daemon=False para que gunicorn no mate el thread del bot
threading.Thread(target=run_discord, daemon=False).start()