import discord
from flask import Flask, jsonify
from flask_cors import CORS
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

def run_flask():
    app.run(host='0.0.0.0', port=5000)

@client.event
async def on_ready():
    print(f'Bot conectado como {client.user}')
    threading.Thread(target=run_flask, daemon=True).start()

client.run(os.environ['DISCORD_TOKEN'])
