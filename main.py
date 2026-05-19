import discord
from flask import Flask, jsonify
from flask_cors import CORS
import asyncio
import threading
import os
import sys

app = Flask(__name__)
CORS(app)

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
client = discord.Client(intents=intents)

@app.route('/voice/<channel_id>')
def get_voice_members(channel_id):
    channel = client.get_channel(int(channel_id))
    if channel is None:
        return jsonify({"error": "Canal no encontrado"}), 404
    members = [m.display_name for m in channel.members]
    return jsonify({"members": members})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "bot_ready": not client.is_closed()})

@client.event
async def on_ready():
    print(f'Bot conectado como {client.user}', flush=True)

def run_discord():
    try:
        token = os.environ.get('DISCORD_TOKEN')
        if not token:
            print('ERROR: DISCORD_TOKEN no está definido', flush=True)
            return
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(client.start(token))
    except Exception as e:
        print(f'ERROR en bot Discord: {e}', flush=True)

threading.Thread(target=run_discord, daemon=True).start()
