import discord
import aiohttp
import asyncio
import random

TOKEN = "YOUR_ALT_TOKEN"
OCR_API_KEY = "YOUR_OCR_SPACE_KEY"
POKENAME_BOT_ID = 123456789012345678 # ID of the bot that sends the image

client = discord.Client(self_bot=True)

async def get_pokemon_name(image_url):
    # Sends the image URL to OCR.space for text extraction
    payload = {
        'apikey': OCR_API_KEY,
        'url': image_url,
        'language': 'eng',
    }
    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.ocr.space/parse/image', data=payload) as resp:
            data = await resp.json()
            if data['ParsedResults']:
                # Extracts the text and cleans it up
                text = data['ParsedResults'][0]['ParsedText']
                return text.strip().split('\n')[0] # Takes the first line
    return None

@client.event
async def on_message(message):
    # 1. Detect the Identification Bot's message
    if message.author.id == POKENAME_BOT_ID and message.attachments:
        image_url = message.attachments[0].url
        print(f"New image detected! Scanning...")

        name = await get_pokemon_name(image_url)
        
        if name:
            # 2. Add 'Human-like' delay
            delay = random.uniform(2.5, 5.0)
            await asyncio.sleep(delay)

            # 3. Catch!
            await message.channel.send(f"c {name}")
            print(f"Attempted to catch {name} after {delay:.2f}s")

client.run(TOKEN)
