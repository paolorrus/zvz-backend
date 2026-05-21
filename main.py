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


async def fetch_voice_members_fresh(channel_id: int):
    """Re-chunk el guild y devuelve los miembros del canal frescos."""
    for guild in client.guilds:
        for vc in list(guild.voice_channels) + list(guild.stage_channels):
            if vc.id == channel_id:
                # Re-chunk este guild para forzar datos frescos del gateway
                try:
                    await guild.chunk(cache=True)
                except Exception as e:
                    print(f'[chunk error] {e}', flush=True)
                members = [m.display_name for m in vc.members]
                print(f'[FRESH] Canal "{vc.name}" ({channel_id}): {members}', flush=True)
                return members
    return None


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

    if not bot_loop or client.is_closed():
        return jsonify({"error": "Bot desconectado"}), 503

    try:
        future = asyncio.run_coroutine_threadsafe(
            fetch_voice_members_fresh(cid), bot_loop
        )
        members = future.result(timeout=20)
    except Exception as e:
        print(f'[fetch error] {e}', flush=True)
        return jsonify({"error": str(e)}), 500

    if members is None:
        return jsonify({"error": "Canal no encontrado"}), 404

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
        try:
            await guild.chunk(cache=True)
        except Exception as e:
            print(f'Chunk error: {e}', flush=True)
    bot_ready = True
    print('=== BOT READY ===', flush=True)


@client.event
async def on_voice_state_update(member, before, after):
    print(f'[VoiceEvent] {member.display_name}: '
          f'{getattr(before.channel,"name","None")} → {getattr(after.channel,"name","None")}', flush=True)


def run_discord():
    global bot_loop
    try:
        if not DISCORD_TOKEN:
            print('ERROR: DISCORD_TOKEN no definido', flush=True)
            return
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)
        bot_loop.run_until_complete(client.start(DISCORD_TOKEN))
    except Exception as e:
        print(f'ERROR bot: {e}', flush=True)


threading.Thread(target=run_discord, daemon=True).start()