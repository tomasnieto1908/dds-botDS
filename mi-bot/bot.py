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

partida = None

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')

@client.event
async def on_message(message):
    global partida

    if message.author == client.user:
        return

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
            'doctor': None,
            'detective': None,
            'fase': 'día',
            'eliminaciones': [],
            'votaciones': {},
            'proteccion': None
        }
        await message.channel.send(f"Se ha creado una partida de Mafia para {num_jugadores} jugadores. Usa `!mafia unirme` para participar.")

    elif message.content.startswith('!mafia unirme'):
        if partida is None:
            await message.channel.send("No hay ninguna partida en curso.")
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

    elif message.content.startswith('!noche'):
        if partida is None or partida['fase'] != 'día':
            await message.channel.send("No se puede iniciar la fase de noche.")
            return

        partida['fase'] = 'noche'
        await message.channel.send("🌙 Fase de noche. Mafiosos, doctor y detective: usen sus comandos por privado.")

        for jugador in partida['jugadores']:
            if jugador in partida['mafiosos']:
                await jugador.send("🌙 Eres mafioso. Usa `!matar <nombre>` por privado.")
            elif jugador == partida['doctor']:
                await jugador.send("🌙 Eres el doctor. Usa `!curar <nombre>` por privado para protegerlo.")
            elif jugador == partida['detective']:
                await jugador.send("🌙 Eres el detective. Usa `!investigar <nombre>` por privado.")

    elif message.content.startswith('!matar'):
        if partida is None or partida['fase'] != 'noche':
            return
        
        if message.channel.type != discord.ChannelType.private or message.author not in partida['mafiosos']:
            return

        args = message.content.split()
        if len(args) != 2:
            await message.author.send("Uso correcto: `!matar <nombre>`")
            return

        nombre = args[1]
        victima = discord.utils.get(client.get_all_members(), name=nombre)

        if victima in partida['jugadores']:
            partida['eliminaciones'].append(victima)
            await message.author.send(f"Has propuesto eliminar a {victima.name}.")
        else:
            await message.author.send("No se encontró ese jugador.")

    elif message.content.startswith('!curar'):
        if partida is None or partida['fase'] != 'noche' or message.author != partida['doctor']:
            return
        
        args = message.content.split()
        if len(args) != 2:
            await message.author.send("Uso correcto: `!curar <nombre>`")
            return

        nombre = args[1]
        objetivo = discord.utils.get(client.get_all_members(), name=nombre)

        if objetivo in partida['jugadores']:
            partida['proteccion'] = objetivo
            await message.author.send(f"Has protegido a {objetivo.name} esta noche.")
        else:
            await message.author.send("No se encontró ese jugador.")

    elif message.content.startswith('!investigar'):
        if partida is None or partida['fase'] != 'noche' or message.author != partida['detective']:
            return
        
        args = message.content.split()
        if len(args) != 2:
            await message.author.send("Uso correcto: `!investigar <nombre>`")
            return

        nombre = args[1]
        investigado = discord.utils.get(client.get_all_members(), name=nombre)

        if investigado in partida['jugadores']:
            rol = "mafioso" if investigado in partida['mafiosos'] else "inocente"
            await message.author.send(f"{investigado.name} es {rol}.")
        else:
            await message.author.send("No se encontró ese jugador.")

    elif message.content.startswith('!amanecer'):
        if partida is None or partida['fase'] != 'noche':
            return

        partida['fase'] = 'día'
        victima = partida['eliminaciones'][0] if partida['eliminaciones'] else None

        if victima and victima != partida['proteccion']:
            partida['jugadores'].remove(victima)
            if victima in partida['mafiosos']:
                partida['mafiosos'].remove(victima)
            if victima == partida['doctor']:
                partida['doctor'] = None
            if victima == partida['detective']:
                partida['detective'] = None
            await message.channel.send(f"🌅 ¡Amanece! {victima.name} fue eliminado durante la noche.")
        else:
            await message.channel.send("🌅 ¡Amanece! Nadie murió esta noche.")

        partida['eliminaciones'] = []
        partida['proteccion'] = None
        await verificar_victoria(message.channel)

    elif message.content.startswith('!votar'):
        if partida is None or partida['fase'] != 'día':
            return

        args = message.content.split()
        if len(args) != 2:
            await message.channel.send("Uso correcto: `!votar <nombre>`")
            return

        votado = discord.utils.get(message.guild.members, name=args[1])
        if votado not in partida['jugadores']:
            await message.channel.send("Ese jugador no está en la partida.")
            return

        partida['votaciones'][message.author] = votado
        await message.channel.send(f"{message.author.name} ha votado por {votado.name}.")

        if len(partida['votaciones']) == len(partida['jugadores']):
            await procesar_votacion(message.channel)

# Roles
async def asignar_roles(jugadores):
    random.shuffle(jugadores)
    partida['mafiosos'] = jugadores[:max(1, len(jugadores)//3)]
    restantes = [j for j in jugadores if j not in partida['mafiosos']]
    
    if restantes:
        partida['doctor'] = restantes.pop()
    if restantes:
        partida['detective'] = restantes.pop()

    for m in partida['mafiosos']:
        await m.send("🎭 Eres un **mafioso**.")
    if partida['doctor']:
        await partida['doctor'].send("💊 Eres el **doctor**.")
    if partida['detective']:
        await partida['detective'].send("🔍 Eres el **detective**.")
    for i in restantes:
        await i.send("👮 Eres un **inocente**.")

    canal = jugadores[0].guild.system_channel or await jugadores[0].guild.create_text_channel('mafia')
    await canal.send("🔔 ¡La partida ha comenzado! Es de día ☀️. Debatan y voten con `!votar <nombre>`.")

# Votación
async def procesar_votacion(canal):
    conteo = {}
    for votado in partida['votaciones'].values():
        conteo[votado] = conteo.get(votado, 0) + 1

    max_votos = max(conteo.values())
    candidatos = [j for j, v in conteo.items() if v == max_votos]

    if len(candidatos) == 1:
        eliminado = candidatos[0]
        partida['jugadores'].remove(eliminado)
        await canal.send(f"🚨 {eliminado.name} fue eliminado por votación.")
        if eliminado in partida['mafiosos']:
            partida['mafiosos'].remove(eliminado)
        if eliminado == partida['doctor']:
            partida['doctor'] = None
        if eliminado == partida['detective']:
            partida['detective'] = None
    else:
        await canal.send("🗳️ Hubo un empate. Nadie fue eliminado.")

    partida['votaciones'] = {}
    await verificar_victoria(canal)

# Verificación de victoria
async def verificar_victoria(canal):
    mafiosos = len(partida['mafiosos'])
    inocentes = len(partida['jugadores']) - mafiosos
    if mafiosos == 0:
        await canal.send("🎉 ¡Los inocentes han ganado!")
        resetear_partida()
    elif mafiosos >= inocentes:
        await canal.send("💀 ¡Los mafiosos han ganado!")
        resetear_partida()
    else:
        await canal.send("🔁 La partida continúa. Usa `!noche` para iniciar la fase nocturna.")
        partida['fase'] = 'día'

def resetear_partida():
    global partida
    partida = None

client.run(TOKEN)
