import discord
import aiohttp
import asyncio
import random
import os
import ssl
from corrections import pokemon_map

# --- CONFIGURATION ---
TOKEN = "acc_token "
POKENAME_BOT_ID = 874910942490677270
SPAM_CHANNEL_ID = 1459841583536148601
MY_USER_ID = 1378954077462986772

# Add all your OCR.space API keys here!
OCR_KEYS = [
    "K81439983988957",
    "K89035013988957",
    "K86412733888957"
]

SPAM_MESSAGES = ["vroom vroom", "mining time", "keep going", "catch them all"]
spam_enabled = True

client = discord.Client(self_bot=True)

async def get_pokemon_name(image_url):
    # This timeout is better for mobile data in Mathura                                                                                             timeout = aiohttp.ClientTimeout(total=15, connect=5)

    # force_close=True is vital for mobile data to prevent 'hanging' sockets
    connector = aiohttp.TCPConnector(ssl=False, force_close=True)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for key in OCR_KEYS:
            print(f"Attempting OCR | Key: ...{key[-4:]}")

            payload = {
                'apikey': key,
                'url': image_url,
                'language': 'eng',
            }

            try:
                # Use a proper POST with a small delay to let the data connection 'warm up'
                await asyncio.sleep(0.5)
                async with session.post('https://api.ocr.space/parse/image', data=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict) and data.get('ParsedResults'):
                            text = data['ParsedResults'][0]['ParsedText']
                            name = text.strip().split('\n')[0]
                            return "".join(c for c in name if c.isalpha())
                        else:
                            print(f"API Error on ...{key[-4:]}: {data.get('ErrorMessage')}")
                    else:
                        print(f"HTTP {resp.status} on ...{key[-4:]}")
            except Exception as e:
                # This will print the EXACT error type (e.g., ClientConnectorError)
                print(f"Network error on ...{key[-4:]}: {type(e).__name__} - {e}")

            # Wait 2 seconds before trying the next key
            await asyncio.sleep(2)

    return None

async def spammer():
    global spam_enabled
    await client.wait_until_ready()
    channel = client.get_channel(SPAM_CHANNEL_ID)

    while not client.is_closed():
        if spam_enabled and channel:
            try:
                await channel.send(random.choice(SPAM_MESSAGES))
                print(".", end="", flush=True)
                await asyncio.sleep(random.uniform(2.5, 4.0))
            except Exception as e:
                print(f"\nSpam Error: {e}")
                await asyncio.sleep(10)
        else:
            await asyncio.sleep(5)

@client.event
async def on_message(message):
    global spam_enabled

    # 1. REMOTE CONTROL
    if message.author.id == MY_USER_ID:
        content = message.content.lower().strip()
        if content == ".stop":
            spam_enabled = False
            await message.channel.send("🚫 **Spammer Paused.**")
            return
        elif content == ".start":
            spam_enabled = True
            await message.channel.send("✅ **Spammer Resumed.**")
            return

    # 2. CATCHING LOGIC
    if message.author.id == POKENAME_BOT_ID:
        image_url = None
        if message.attachments:
            image_url = message.attachments[0].url
        elif message.embeds and message.embeds[0].image:
            image_url = message.embeds[0].image.url

        if image_url:
            print(f"\nSpawn detected! Scanning image...")
            name = await get_pokemon_name(image_url)

            if name:
            name_upper = name.upper()
                if name_upper in pokemon_map:
                    print(f"Correcting {name_upper} -> {pokemon_map[name_upper]}")
                    name = pokemon_map[name_upper]
                delay = random.uniform(2.0, 3.1)
                print(f"Identified: {name}. Catching in {delay:.2f}s...")
                await asyncio.sleep(delay)
                await message.channel.send(f"<@716390085896962058> c {name}")
                print(f"Caught {name}!")
            else:
                print("Failed to identify after trying all keys.")

@client.event
async def on_ready():
    print(f"Logged in as {client.user} - Multi-Key OCR Active")
    client.loop.create_task(spammer())

client.run(TOKEN)
