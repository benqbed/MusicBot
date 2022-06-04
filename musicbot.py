from pytube import YouTube
from pytube import Search
from nextcord.ext import commands
import nextcord
import asyncio
import os

queue = []
autoPlayRunning = False

#Class to hold song and title
class music:
    def __init__(self, player, title):
        self.player = player
        self.title = title

#Declare bot command
client = commands.Bot(command_prefix='>', intents = nextcord.Intents.all())

########################
### Assist Functions ###
########################

#Function to auto play songs
async def autoPlay(ctx):
    print("Check function started.\n")
    global autoPlayRunning
    global queue
    voice_channel = ctx.message.guild.voice_client
    while len(queue) > 0:
        if voice_channel.is_playing() == False and voice_channel.is_paused() == False and len(queue) > 0:
            print("Entered autoplay function\n")
            await playSong(ctx, voice_channel, queue[0])
            queue.pop(0)
            await asyncio.sleep(5)
        else:
            print("Conditions for autoplay not met. Waiting 5 seconds.\n")
            await asyncio.sleep(5)
    autoPlayRunning = False

#Function to check if user is in a voice channel
async def check_ifusr_inchannel(ctx):
    if not ctx.message.author.voice:
        #If user not in voice channel, tell them so
        await ctx.send('You have to join a voice channel first!')
        return False
    else:
        #Return vc that user is in
        return ctx.message.author.voice.channel

#Function to get a song requested by user
async def getSong(url):
    ytSearch = None
    if 'https://www.youtube.com/watch' in url:
        ytSearch = YouTube(url)
    else:
        ytSearch = Search(url)
        if len(ytSearch.results) > 0:
            ytSearch = ytSearch.results[0]
        else:
            await getSong(url)
            return
    
    filename = ytSearch.streams.desc().first().download('Songs/')
    playAndTitle = music(nextcord.FFmpegPCMAudio(source = filename, options= '-vn'), ytSearch.title)
    return playAndTitle

#Function to play a song
async def playSong(ctx, voice_channel, player):
    voice_channel.play(player.player, after=lambda e: print('Player error: %s' %e) if e else None)
    await ctx.send(f'Now playing: `{player.title}`')

########################
##### Bot Commands #####
########################

#Print a message to console to show bot is running and start loop for autoplay
@client.event
async def on_ready():
    print('Logged in as {0.user}'.format(client))

#Ping command
@client.command(name='ping', help=': This command is a latency ping')
async def ping(ctx):
    await ctx.send(f'**Pong!** Latency: {round(client.latency * 1000)}ms')

#Hello command
@client.command(name='hello', help=': Use this to say hi to me!')
async def hello(ctx):
    await ctx.send(f'Hello there!')

#VC Join command
@client.command(name='join', help=': Bring me to your current voice channel!')
async def join(ctx):
    voice_channel = await check_ifusr_inchannel(ctx)
    if not voice_channel:
        return False
    if not ctx.message.guild.voice_client:
        await voice_channel.connect()
        voice_channel = ctx.message.guild.voice_client
        return voice_channel
    else:
        await ctx.send('I\'m already in a voice channel!')
        return False

#VC Leave command
@client.command(name='leave', help=': This tells me to leave the voice channel.')
async def leave(ctx):
    global queue  
    voice_client = ctx.message.guild.voice_client
    if voice_client != None:
        await voice_client.disconnect()
        queue.clear()

#Pause music command
@client.command(name='pause', help=f': Pauses the music, what did you think it did?')
async def pause(ctx):
    #server = ctx.message.guild
    voice_channel = ctx.message.guild.voice_client
    voice_channel.pause()

#Play music command
@client.command(name='play', help=f': Use me to play music or resume paused music!')
async def play(ctx, *, url = None):
    #Check if bot is in a voice channel and if not, join it
    #or if user is not in a voice channel, tell them so
    global autoPlayRunning
    voice_channel = ctx.message.guild.voice_client
    if not voice_channel:
        voice_channel = await join(ctx)
    if not voice_channel:
        return 0

    #If no url is given, assume user wants to resume a song
    if url == None:
        voice_channel.resume()
        return 0
    
    #Get song from url and play it if no song is playing, otherwise add it to queue
    player = await getSong(url)
    if voice_channel.is_playing():
        await ctx.send(f'Adding `{player.title}` to queue')
        queue.append(player)
        if autoPlayRunning == False:
            autoPlayRunning = True
            await autoPlay(ctx)
    else:
        await playSong(ctx, voice_channel, player)
        return 0

#See queue command
@client.command(name='cq', help=': This shows the songs currently in queue')
async def cq(ctx):
    await ctx.send('This is the current queue:\n')
    for val in queue:
        await ctx.send(f'`{val.title}`\n')

#Remove from queue command
@client.command(name='rm', help=': This removes a song from the queue! Use: \">rm 2\"')
async def rm(ctx, number):
    global queue

    #Check to make sure given number is an index in queue
    queueLen = len(queue)
    if queueLen == 0:
        await ctx.send('Queue is empty!')
        return 0
    if number not in range(0, queueLen):
        await ctx.send('Given number is out of range!')
        return 0
        
    index = int(number) - 1
    queue.pop(index)
    await ctx.send('This is now the current queue:\n')
    for val in queue:
        await ctx.send(f'`{val.title}`\n')

#Skip command
@client.command(name='skip', help=': This skips to the next song in queue!')
async def skip(ctx):
    global queue
    voice_channel = ctx.message.guild.voice_client
    voice_channel.stop()

    if len(queue) == 0:
        await ctx.send('No more songs in queue, so I\'ll stop playing the current song!')
        return 0

    async with ctx.typing():
        player = queue[0]
        queue.pop(0)

        voice_channel.play(player.player, after=lambda e: print('Player error: %s' %e) if e else None)
        await ctx.send(f'Now playing: `{player.title}`')



asyncio.run(client.run(os.environ.get('MARISA_AUTH')))