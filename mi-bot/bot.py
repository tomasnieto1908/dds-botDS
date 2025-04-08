import discord
import os
import random
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

# Variables globales para gestionar la partida
partida = None

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')

@client.event
async def on_message(message):
    global partida

    if message.author == client.user:
        return

    # Crear partida
    if message.content.startswith('!mafia crear'):
        args = message.content.split()
        if len(args) != 3 or not args[2].isdigit():
            await message.channel.send("Uso correcto: `!mafia crear <número de jugadores>`")
            return
        
        num_jugadores = int(args[2])
        partida = {
            'jugadores': [],
            'num_jugadores': num_jugadores,
            'mafiosos': [],
            'fase': 'día',
            'eliminaciones': [],
            'votaciones': {}
        }
        await message.channel.send(f"Se ha creado una partida de Mafia para {num_jugadores} jugadores. Usa `!mafia unirme` para participar.")

    # Unirse a la partida
    elif message.content.startswith('!mafia unirme'):
        if partida is None:
            await message.channel.send("No hay ninguna partida en curso. Usa `!mafia crear <número de jugadores>` para iniciar una.")
            return
        
        if message.author in partida['jugadores']:
            await message.channel.send("Ya estás en la partida.")
            return

        if len(partida['jugadores']) < partida['num_jugadores']:
            partida['jugadores'].append(message.author)
            await message.channel.send(f"{message.author.name} se ha unido. Jugadores actuales: {len(partida['jugadores'])}/{partida['num_jugadores']}")
            
            if len(partida['jugadores']) == partida['num_jugadores']:
                await asignar_roles(partida['jugadores'])
        else:
            await message.channel.send("La partida ya está completa.")

    # Comando para iniciar la fase de noche
    elif message.content.startswith('!noche'):
        if partida is None or partida['fase'] != 'día':
            await message.channel.send("No se puede iniciar la fase de noche. Asegúrate de que sea de día.")
            return
        
        partida['fase'] = 'noche'
        await message.channel.send("🌙 La fase de noche ha comenzado. Los mafiosos deben elegir a alguien para eliminar por mensaje privado.")
        
        for jugador in partida['jugadores']:
            if jugador in partida['mafiosos']:
                await jugador.send("Es de noche. Usa `!matar <nombre>` para eliminar a un jugador.")

    # Comando para matar a otro jugador (solo en DM)
    elif message.content.startswith('!matar'):
        if partida is None or partida['fase'] != 'noche':
            await message.channel.send("No es la fase de noche. No puedes matar a nadie.")
            return
        
        if message.author not in partida['mafiosos']:
            await message.channel.send("No tienes permiso para usar este comando.")
            return

        args = message.content.split()
        if len(args) != 2:
            await message.channel.send("Uso correcto: `!matar <nombre del jugador>`")
            return

        nombre_victima = args[1]
        guild = client.guilds[0]
        victima = discord.utils.get(guild.members, name=nombre_victima)

        if victima in partida['jugadores']:
            partida['eliminaciones'].append(victima)
            await message.channel.send(f"Los mafiosos han elegido a {victima.name}. Se procesará al amanecer.")
        else:
            await message.channel.send("No se encontró a ese jugador en la partida.")

    # Amanecer
    elif message.content.startswith('!amanecer'):
        if partida is None or partida['fase'] != 'noche':
            await message.channel.send("No es la fase de noche. No puedes procesar eliminaciones.")
            return
        
        partida['fase'] = 'día'
        if partida['eliminaciones']:
            victima = partida['eliminaciones'][0]
            partida['jugadores'].remove(victima)
            await message.channel.send(f"🌅 ¡Amanece! {victima.name} ha sido eliminado durante la noche.")
            if victima in partida['mafiosos']:
                partida['mafiosos'].remove(victima)
            partida['eliminaciones'] = []
        else:
            await message.channel.send("🌅 ¡Amanece! Nadie fue eliminado esta noche.")

        await verificar_victoria(message.channel)

    # Votación
    elif message.content.startswith('!votar'):
        if partida is None or partida['fase'] != 'día':
            await message.channel.send("Solo puedes votar durante la fase de día.")
            return

        args = message.content.split()
        if len(args) != 2:
            await message.channel.send("Uso correcto: `!votar <nombre>`")
            return

        nombre_votado = args[1]
        votado = discord.utils.get(message.guild.members, name=nombre_votado)

        if votado not in partida['jugadores']:
            await message.channel.send("Ese jugador no está en la partida.")
            return

        partida['votaciones'][message.author] = votado
        await message.channel.send(f"{message.author.name} ha votado por {votado.name}.")

        if len(partida['votaciones']) == len(partida['jugadores']):
            await procesar_votacion(message.channel)

# Asignación de roles
async def asignar_roles(jugadores):
    random.shuffle(jugadores)
    num_mafiosos = max(1, len(jugadores) // 3)
    mafiosos = jugadores[:num_mafiosos]
    inocentes = jugadores[num_mafiosos:]

    partida['mafiosos'] = mafiosos

    for m in mafiosos:
        await m.send("🎭 Eres un **mafioso**. Colabora con tus compañeros para eliminar a los inocentes.")
    for i in inocentes:
        await i.send("👮 Eres un **inocente**. Intenta descubrir quién es el mafioso.")

    canal = jugadores[0].guild.system_channel or await jugadores[0].guild.create_text_channel('mafia')
    await canal.send("🔔 ¡La partida ha comenzado! Estamos en la fase de día ☀️. Los jugadores pueden debatir. Cuando estén listos, usen `!votar <nombre>` para iniciar la votación.")

# Procesar votación
async def procesar_votacion(canal):
    conteo = {}
    for votado in partida['votaciones'].values():
        conteo[votado] = conteo.get(votado, 0) + 1

    max_votos = max(conteo.values())
    candidatos = [j for j, v in conteo.items() if v == max_votos]

    if len(candidatos) == 1:
        eliminado = candidatos[0]
        partida['jugadores'].remove(eliminado)
        await canal.send(f"🚨 {eliminado.name} ha sido eliminado por votación.")
        if eliminado in partida['mafiosos']:
            partida['mafiosos'].remove(eliminado)
    else:
        await canal.send("🗳️ Hubo un empate en la votación. Nadie ha sido eliminado.")

    partida['votaciones'] = {}
    await verificar_victoria(canal)

# Verificación de victoria
async def verificar_victoria(canal):
    num_mafiosos = len(partida['mafiosos'])
    num_inocentes = len(partida['jugadores']) - num_mafiosos

    if num_mafiosos == 0:
        await canal.send("🎉 ¡Los inocentes han ganado la partida!")
        resetear_partida()
    elif num_mafiosos >= num_inocentes:
        await canal.send("💀 ¡Los mafiosos han tomado el control del pueblo! Victoria de los mafiosos.")
        resetear_partida()
    else:
        await canal.send("🔁 La partida continúa. Usa `!noche` para comenzar la siguiente fase nocturna.")
        partida['fase'] = 'día'

# Reiniciar partida
def resetear_partida():
    global partida
    partida = None

# Iniciar el bot
client.run(TOKEN)
