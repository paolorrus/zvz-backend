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

@app.route('/voice/<channel_id>')
def get_voice_members(channel_id):
    if bot_loop is None:
        return jsonify({"error": "Bot no listo todavía"}), 503
    
    async def fetch():
        try:
            for guild in client.guilds:
                for channel in guild.voice_channels:
                    if channel.id == int(channel_id):
                        members = [m.display_name for m in channel.members]
                        return members
            return {"error": "Canal no encontrado"}
        except Exception as e:
            return {"error": str(e)}
    
    future = asyncio.run_coroutine_threadsafe(fetch(), bot_loop)
    result = future.result(timeout=10)
    
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 404
    return jsonify({"members": result})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "bot_ready": not client.is_closed()})

@app.route('/canales')
def listar_canales():
    canales = []
    for guild in client.guilds:
        for channel in guild.channels:
            canales.append({
                "id": str(channel.id),
                "nombre": channel.name,
                "tipo": str(channel.type)
            })
    return jsonify(canales)

@client.event
async def on_ready():
    print(f'Bot conectado como {client.user}', flush=True)

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
