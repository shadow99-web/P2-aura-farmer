import discord
import aiohttp
import asyncio
import random
import os
import ssl

# --- CONFIGURATION ---
TOKEN = "your-token"
POKENAME_BOT_ID = 874910942490677270
SPAM_CHANNEL_ID = 1459841583536148601
MY_USER_ID = 1378954077462986772 

# Add all your OCR.space API keys here!
OCR_KEYS = [
    "_____",
    "____",
    "YOUR_THIRD_KEY"
]

SPAM_MESSAGES = ["vroom vroom", "mining time", "keep going", "catch them all"]
spam_enabled = True

client = discord.Client(self_bot=True)

async def get_pokemon_name(image_url):
    """Tries every API key in the list until one works."""
    # Headers and connector to prevent 'Connection Reset' on hostel Wi-Fi
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    connector = aiohttp.TCPConnector(ssl=False, force_close=True)

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        for key in OCR_KEYS:
            print(f"Trying OCR with key: ...{key[-4:]}")
            
            payload = {
                'apikey': key,
                'url': image_url,
                'language': 'eng',
                'isOverlayRequired': False,
            }

            try:
                async with session.post('https://api.ocr.space/parse/image', data=payload, timeout=12) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # If the key is valid and has results
                        if isinstance(data, dict) and data.get('ParsedResults'):
                            text = data['ParsedResults'][0]['ParsedText']
                            name = text.strip().split('\n')[0]
                            clean_name = "".join(c for c in name if c.isalpha())
                            if clean_name:
                                return clean_name
                        else:
                            print(f"Key ...{key[-4:]} failed: {data.get('ErrorMessage')}")
                    else:
                        print(f"Server error {resp.status} on key ...{key[-4:]}")
            except Exception as e:
                print(f"Network error on key ...{key[-4:]}: {e}")
            
            # Brief wait before trying the NEXT key in the list
            await asyncio.sleep(1)
            
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
                await asyncio.sleep(random.uniform(2.5, 5.0))
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
                delay = random.uniform(2.1, 4.8)
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
