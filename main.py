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

DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN', '')


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
            return jsonify({"error": "Bot aún conectando"}), 503

    # Leer directo — sin chunk, sin async, sin cache
    # discord.py mantiene vc.members actualizado via gateway events
    for guild in client.guilds:
        for vc in list(guild.voice_channels) + list(guild.stage_channels):
            if vc.id == cid:
                members = [m.display_name for m in vc.members]
                print(f'[/voice] "{vc.name}": {members}', flush=True)
                return jsonify({"members": members})

    return jsonify({"error": "Canal no encontrado"}), 404


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
            print(f'Chunk OK: {guild.name}', flush=True)
        except Exception as e:
            print(f'Chunk error: {e}', flush=True)
    bot_ready = True
    print('=== BOT READY ===', flush=True)


@client.event
async def on_voice_state_update(member, before, after):
    b = getattr(before.channel, 'name', 'None')
    a = getattr(after.channel, 'name', 'None')
    print(f'[Voice] {member.display_name}: {b} → {a}', flush=True)


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


threading.Thread(target=run_discord, daemon=True).start()