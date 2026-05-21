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
cache_canales = []
cache_voice = {}
last_refresh = 0

@app.route('/voice/<channel_id>')
def get_voice_members(channel_id):
    cid = int(channel_id)
    
    # If bot isn't ready yet (cold start), wait a bit
    if not bot_ready:
        for _ in range(15):  # wait up to 15s for bot to connect
            if bot_ready:
                break
            time.sleep(1)
        if not bot_ready:
            return jsonify({"error": "Bot aún conectando, intenta en 10s"}), 503

    # Force fresh re-chunk and WAIT
    if bot_loop and not client.is_closed():
        try:
            future = asyncio.run_coroutine_threadsafe(refresh_voice_cache(), bot_loop)
            future.result(timeout=15)  # Wait up to 15s for refresh
        except Exception as e:
            print(f'Refresh error: {e}', flush=True)

    members = cache_voice.get(cid, None)
    if members is None:
        # Debug: print what channels we DO have
        print(f'Canal {cid} no encontrado. Canales en cache: {list(cache_voice.keys())}', flush=True)
        return jsonify({
            "error": "Canal no encontrado",
            "canales_disponibles": list(str(k) for k in cache_voice.keys()),
            "total_canales": len(cache_voice)
        }), 404

    return jsonify({"members": members, "count": len(members)})

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "bot_ready": bot_ready,
        "guilds": len(client.guilds) if bot_ready else 0,
        "voice_channels_cached": len(cache_voice),
        "cache": {str(k): len(v) for k, v in cache_voice.items()}
    })

@app.route('/canales')
def listar_canales():
    # Force refresh if bot is ready
    if bot_ready and bot_loop and not client.is_closed():
        try:
            future = asyncio.run_coroutine_threadsafe(refresh_voice_cache(), bot_loop)
            future.result(timeout=10)
        except:
            pass
    return jsonify(cache_canales)

def actualizar_cache():
    """Actualiza el caché de canales y usuarios en voz"""
    global cache_canales, cache_voice
    canales = []
    voice = {}
    
    print('=== INICIANDO ACTUALIZACIÓN DE CACHÉ ===', flush=True)
    
    for guild in client.guilds:
        print(f'Guild: {guild.name} ({guild.id}) — {guild.member_count} miembros', flush=True)
        
        # Listar TODOS los canales
        for channel in guild.channels:
            canales.append({
                "id": str(channel.id),
                "nombre": channel.name,
                "tipo": str(channel.type)
            })
        
        # Método 1: Voice channels
        for channel in guild.voice_channels:
            members_in_channel = [
                member.display_name
                for member in guild.members
                if member.voice and member.voice.channel and member.voice.channel.id == channel.id
            ]
            voice[channel.id] = members_in_channel
            if members_in_channel:
                print(f'  ✓ Voz "{channel.name}" ({channel.id}): {len(members_in_channel)} — {members_in_channel}', flush=True)
            else:
                print(f'  ○ Voz "{channel.name}" ({channel.id}): vacío', flush=True)

        # Método 2: Stage channels
        for channel in guild.stage_channels:
            members_in_channel = [
                member.display_name
                for member in guild.members
                if member.voice and member.voice.channel and member.voice.channel.id == channel.id
            ]
            voice[channel.id] = members_in_channel
            if members_in_channel:
                print(f'  ✓ Stage "{channel.name}" ({channel.id}): {len(members_in_channel)} — {members_in_channel}', flush=True)

    cache_canales = canales
    cache_voice = voice
    total_users = sum(len(v) for v in voice.values())
    print(f'✅ Cache OK: {len(canales)} canales, {len(voice)} con voz, {total_users} usuarios totales', flush=True)
    print(f'Detalles de voz: {voice}', flush=True)

async def refresh_voice_cache():
    """Fuerza un chunk de todos los guilds para sincronizar miembros"""
    print('>>> Iniciando refresh_voice_cache', flush=True)
    for guild in client.guilds:
        try:
            print(f'  Chunkeando {guild.name}...', flush=True)
            await guild.chunk(cache=True)
            print(f'  ✓ Chunk OK: {guild.name}', flush=True)
        except Exception as e:
            print(f'  ✗ Chunk error {guild.name}: {e}', flush=True)
    actualizar_cache()
    print('>>> refresh_voice_cache completado', flush=True)

@client.event
async def on_ready():
    global bot_ready
    print(f'\n🤖 Bot conectado como {client.user}', flush=True)
    print(f'>>> Chunkeando {len(client.guilds)} guilds...', flush=True)
    
    for guild in client.guilds:
        print(f'Servidor: {guild.name} ({guild.id})', flush=True)
        try:
            await guild.chunk(cache=True)
            print(f'✓ Chunk OK: {guild.name} — {guild.member_count} miembros', flush=True)
        except Exception as e:
            print(f'✗ Chunk error: {e}', flush=True)
    
    actualizar_cache()
    bot_ready = True
    print('✅ === BOT READY ===\n', flush=True)

@client.event
async def on_voice_state_update(member, before, after):
    """Se dispara cuando alguien se conecta/desconecta de voz"""
    print(f'🔊 Voice update: {member.name} — antes: {before.channel}, después: {after.channel}', flush=True)
    actualizar_cache()

@client.event
async def on_member_update(before, after):
    """Se dispara cuando cambia el nombre de un miembro"""
    if before.display_name != after.display_name:
        print(f'👤 Miembro actualizado: {before.display_name} → {after.display_name}', flush=True)
        actualizar_cache()

def run_discord():
    global bot_loop
    try:
        token = os.environ.get('DISCORD_TOKEN')
        if not token:
            print('ERROR: DISCORD_TOKEN no definido', flush=True)
            return
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)
        print('🚀 Iniciando bot Discord...', flush=True)
        bot_loop.run_until_complete(client.start(token))
    except Exception as e:
        print(f'ERROR bot: {e}', flush=True)

if __name__ == '__main__':
    # Inicia bot en thread daemon
    threading.Thread(target=run_discord, daemon=True).start()
    
    # Inicia Flask
    print('🌐 Flask iniciado en http://localhost:5000', flush=True)
    app.run(debug=False, host='0.0.0.0', port=5000)