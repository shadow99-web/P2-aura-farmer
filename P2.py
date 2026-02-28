
import discord
import aiohttp
 import asyncio
import random
import os

# --- CONFIGURATION ---
TOKEN = "____"
OCR_API_KEY = "_______"
POKENAME_BOT_ID = 874910942490677270
SPAM_CHANNEL_ID = 1476315512400122099 # ID of the channel to send spam messages
spam_enabled = True
MY_USER_ID = 1378954077462986772 # Replace with your MAIN account ID

# List of messages to spam (to trigger spawns)
SPAM_MESSAGES = ["vroom vroom", "mining time", "keep going", "catch them all"]

client = discord.Client(self_bot=True)

async def get_pokemon_name(image_url):
    payload = {
        'apikey': OCR_API_KEY,
        'url': image_url,
        'language': 'eng',
        'isOverlayRequired': False,
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post('https://api.ocr.space/parse/image', data=payload) as resp:
                data = await resp.json()
                if data.get('ParsedResults'):
                    text = data['ParsedResults'][0]['ParsedText']
                    # Take first line and remove non-alpha characters
                    name = text.strip().split('\n')[0]
                    return "".join(c for c in name if c.isalpha())
        except Exception as e:
            print(f"OCR Error: {e}")
    return None

async def spammer():
    global spam_enabled
    await client.wait_until_ready()
    channel = client.get_channel(SPAM_CHANNEL_ID)

    while not client.is_closed():
        # Only send messages if the switch is ON
        if spam_enabled and channel:
            try:
                await asyncio.sleep(random.uniform(2.5, 5.0))
                await channel.send(random.choice(SPAM_MESSAGES))
                print(".", end="", flush=True)
            except Exception as e:
                print(f"Spam Error: {e}")
                await asyncio.sleep(10)
        else:
            # If disabled, wait a bit before checking again
            await asyncio.sleep(5)

@client.event
async def on_message(message):
    global spam_enabled

    # --- THE REMOTE CONTROL ---
    # Only listens to YOU (your main account)
    if message.author.id == MY_USER_ID:
        if message.content == ".stop":
            spam_enabled = False
            await message.channel.send("🚫 **Spammer Paused.** (Catching still active)")
            print("\nRemote: Spammer Paused.")

        elif message.content == ".start":
            spam_enabled = True
            await message.channel.send("✅ **Spammer Resumed.**")
            print("\nRemote: Spammer Resumed.")


@client.event
async def on_ready():
    print(f"Logged in as {client.user} - OCR Mode Active")
    # Start the spamming loop in the background
    client.loop.create_task(spammer())

@client.event
async def on_message(message):
    # Detect Pokename Bot (checks both attachments and embeds)
    if message.author.id == POKENAME_BOT_ID:
        image_url = None
        if message.attachments:
            image_url = message.attachments[0].url
        elif message.embeds and message.embeds[0].image:
            image_url = message.embeds[0].image.url

        if image_url:
            print(f"Spawn detected! Scanning image...")
            name = await get_pokemon_name(image_url)

            if name:
                # HUMAN-LIKE DELAY (Critical for safety)
                delay = random.uniform(2.1, 4.8)
                print(f"Identified: {name}. Waiting {delay:.2f}s to catch...")
                await asyncio.sleep(delay)

                await message.channel.send(f"<@716390085896962058> c {name}")
                print(f"Caught {name}!")

client.run(TOKEN)
