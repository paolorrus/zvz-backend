import discord
from flask import Flask, jsonify
from flask_cors import CORS
import asyncio
import threading
import os

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
    return jsonify({"status": "ok"})

@client.event
async def on_ready():
    print(f'Bot conectado como {client.user}')

def run_discord():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client.start(os.environ['DISCORD_TOKEN']))

# Arranca el bot en hilo separado al importar
threading.Thread(target=run_discord, daemon=True).start()
