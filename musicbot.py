import nextcord
from nextcord.ext import commands
import os
import sys
import youtube_dl
import asyncio
import requests
from bs4 import BeautifulSoup

youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(nextcord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(nextcord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

#Create bot instance
client = commands.Bot(command_prefix='>', intents = nextcord.Intents.all())

#Define global variables
display_queue = []
queue = []
voice_channel = None
count = 0
gctx = None
is_func_running = False

#Print a message to console to show bot is running and start loop for autoplay
@client.event
async def on_ready():
    print('Logged in as {0.user}'.format(client))
    await channel_playing()

#Ping command
@client.command(name='ping', help=': This command is a latency ping')
async def ping(ctx):
    await ctx.send(f'**Pong** Latency: {round(client.latency * 1000)}ms')

#Hello command
@client.command(name='hello', help=': Use this to say hi to me!')
async def hello(ctx):
    await ctx.send(f'Hello!')

#VC Join command
@client.command(name='join', help=': Bring me to your current voice channel!')
async def join(ctx):
    global voice_channel
    if not await check_ifusr_inchannel(ctx):
        return
    else:
        channel = await check_ifusr_inchannel(ctx)

    await channel.connect()
    voice_channel = channel

#VC Leave command
@client.command(name='leave', help=': This tells me to leave the voice channel')
async def leave(ctx):
    global queue
    global voice_channel    
    voice_client = ctx.message.guild.voice_client
    if voice_client != None:
        await voice_client.disconnect()
        voice_channel = None
        queue.clear()

#Play music command
@client.command(name='play', help=f': Use me to play music')
async def play(ctx, url = ""):
    #Include global variables(idk if this is neccesary)
    global queue
    global voice_channel
    global count
    global gctx
    global is_func_running
    is_func_running = True
    gctx = ctx

    #sets voice_channel to the voice channel the bot is connected to
    voice_channel = ctx.message.guild.voice_client

    #Remove empty elements from queue.
    #These occur due to the default arg of url
    await fix_queue()

    #If bot is not connected to vc
    if voice_channel == None:
    #Check if user is in voice channel by running check func
        if not await check_ifusr_inchannel(ctx):
            return
        else:
            #Set channel equal to vc user is in
            channel = await check_ifusr_inchannel(ctx)
            queue.append(url)

        #Connect to voice channel user is in
        await channel.connect()

        #variable for channel the bot is connected to
        channel = ctx.message.guild.voice_client
        voice_channel = ctx.message.guild.voice_client

        #Play song user requested
        await ctx.send(f'Please wait while I load your song!')
        player = await YTDLSource.from_url(queue[0], loop=client.loop)
        del(queue[0])

        channel.play(player, after=lambda e: print('Player error: %s' %e) if e else None)
        await ctx.send(f'Now playing: {player.title}')
        is_func_running = False
    #If bot is connected to vc
    else:
        #If bot is already playing a song, add the song requested to queue
        if voice_channel.is_playing() or voice_channel.is_paused():
            queue.append(url)
            display_queue.append(await get_title(url))
            await ctx.send(f'`{await get_title(url)}` added to queue!')
            is_func_running = False

        #Play next song in queue
        else:
            queue.append(url)
            display_queue.append(url)
            await ctx.send(f'Please wait while I load your song!')
            print("creating player")
            player = await YTDLSource.from_url(queue[0], loop=client.loop)
            print("created player")
            del(queue[0])
            del(display_queue[0])

            voice_channel.play(player, after=lambda e: print('Player error: %s' %e) if e else None)
            await ctx.send(f'Now playing: {player.title}')
            is_func_running = False

#Pause music command
@client.command(name='pause', help=f': Pauses the music currently playing')
async def pause(ctx):
    server = ctx.message.guild
    voice_channel = server.voice_client

    voice_channel.pause()

#Resume music command
@client.command(name='resume', help=f': Continues to play the music.')
async def resume(ctx):
    server = ctx.message.guild
    voice_channel = server.voice_client
    voice_channel.resume()

#Remove from queue command
@client.command(name='rm', help=': This removes a song from the queue! Use: \">rm 2\"')
async def rm(ctx, number):
    global queue
    #global display_queue
    number = int(number)
    number = number - 1
    print(queue[number])

    try:
        del(queue[number])
        #del(display_queue[number])
        await ctx.send(f'This is now the current queue: `{queue}`')
    except:
        await ctx.send('The queue is either empty or the given number is out of range!')

#See queue command
@client.command(name='cq', help=': This shows the songs currently in queue')
async def cq(ctx):
    global display_queue
    await ctx.send('This is the current queue:\n')
    for val in display_queue:
        await ctx.send(f'`{val}`\n')

#Skip command
@client.command(name='skip', help=': This skips to the next song in queue!')
async def skip(ctx):
    server = ctx.message.guild
    voice_channel = server.voice_client

    voice_channel.stop()

    async with ctx.typing():
        player = await YTDLSource.from_url(queue[0], loop=client.loop)
        del(queue[0])

        await ctx.send(f'Please wait while I load your song!')
        voice_channel.play(player, after=lambda e: print('Player error: %s' %e) if e else None)
        await ctx.send(f'Now playing: {player.title}')

@client.command(name='restart', help=': If I stop working, use this to restart me!')
async def restart(ctx):
    await leave(ctx)
    await ctx.send('Restarting... Please wait about 5 seconds before entering another command.')
    os.execv(sys.executable, ['python'] + sys.argv)

async def get_title(url):
    r = requests.get(url)
    s = BeautifulSoup(r.text, 'html.parser')
    title = s.title.string
    title = title.removesuffix(' - YouTube')
    return title

async def fix_queue():
    global queue
    global display_queue
    if not queue:
        return
    else:
        while queue[0] == "":
            del(queue[0])
            del(display_queue[0])
            if not queue:
                return

#Function to check if user is in a voice channel
async def check_ifusr_inchannel(ctx):
    if not ctx.message.author.voice:
        #If user not in voice channel, tell them so
        await ctx.send('At least join a voice channel first ばか')
        return False
    else:
        #Return vc that user is in
        return ctx.message.author.voice.channel

async def channel_playing():
    print("Check function started.\n")
    global voice_channel
    global gctx
    global queue
    while True:
        global voice_channel
        if not (voice_channel == None):
            try:
                if voice_channel.is_playing() == False and voice_channel.is_paused() == False and (not (not queue)) and (not queue[0] == '') and is_func_running == False:
                    print("Entered autoplay function\n")
                    await play(gctx)
                    await asyncio.sleep(5)
                else:
                    print("Conditions for autoplay not met. Waiting 5 seconds.\n")#print("Conditions for autoplay not met. Conditions:\nVoice Channel playing: " + voice_channel.is_playing() + "\nVoice Channel paused: " + voice_channel.is_paused() + "\n ")
                    await asyncio.sleep(5)
                    #pass
            except:
                print("Player still not initilized, conditions for autoplay not met.\n")
                await asyncio.sleep(5)
        else:
            print("Bot not connected to voice channel. Waiting 5 seconds.\n")#print("Conditions for autoplay not met. Conditions:\nVoice Channel playing: " + voice_channel.is_playing() + "\nVoice Channel paused: " + voice_channel.is_paused() + "\n ")
            await asyncio.sleep(5)
            #pass
#Run bot
#keep_alive.keep_alive()
asyncio.run(client.run(os.environ.get('MUSIC_AUTH')))
