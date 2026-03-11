import discord
import aiohttp
import asyncio
import random
import base64
import requests
import os
import ssl
import re
from corrections import pokemon_map, SLEEP_START_HOUR, SLEEP_END_HOUR
import google.generativeai as genai
from datetime import datetime
import pytz 
from flask import Flask
from threading import Thread

# --- KEEP ALIVE SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Aura Farmer is active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()
client = discord.Client(self_bot=True)

# --- AI CONFIG ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

async def get_ai_identification(image_url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    prompt = "Identify this Pokemon sprite. Return just ONLY the name. No other text or punctuation."
                    response = ai_model.generate_content([prompt, {'mime_type': 'image/jpeg', 'data': img_data}])
                    name = response.text.strip().split()[0]
                    return "".join(c for c in name if c.isalpha())
    except Exception as e: print(f"AI Vision Error: {e}")
    return None

# --- CONFIG & GLOBALS ---
TOKEN = os.getenv("TOKEN")
POKENAME_BOT_ID = 874910942490677270
POKETWO_ID = 716390085896962058
SPAM_CHANNEL_ID = 1459841583536148601
MY_USER_ID = 1378954077462986772
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = "shadow99-web/P2-aura-farmer" 
FILE_PATH = "corrections.py"

spam_enabled = True
captcha_hit = False 
manual_awake = False
ocr_on_cooldown = False
ai_enabled = True
OCR_KEYS = ["K81439983988957", "K89035013988957", "K86412733888957"]
SPAM_MESSAGES = ["vroom vroom", "mining time", "keep going", "catch them all"]

def is_bot_sleeping():
    if manual_awake: return False
    now_ist = datetime.now(pytz.timezone('Asia/Kolkata')).hour
    if SLEEP_START_HOUR < SLEEP_END_HOUR: return SLEEP_START_HOUR <= now_ist < SLEEP_END_HOUR
    return now_ist >= SLEEP_START_HOUR or now_ist < SLEEP_END_HOUR

def solve_hint(hint_pattern):
    clean = hint_pattern.replace('\\', '').replace('.', '').replace(' ', '').strip()
    regex_pattern = f"^{clean.replace('_', '.')}$"
    try:
        with open("pokemons.txt", "r") as f:
            names = f.read().splitlines()
        for name in names:
            if re.fullmatch(regex_pattern, name, re.IGNORECASE): return name
    except Exception as e: print(f"File Error: {e}")
    return None

async def update_github_database(wrong, right):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            print(f"❌ GitHub GET failed: {r.status_code} - {r.text}")
            return False
            
        data = r.json()
        sha = data['sha']
        content = base64.b64decode(data['content']).decode('utf-8')
        
        # Add the new correction
        new_line = f'\npokemon_map["{wrong.upper()}"] = "{right}"'
        updated_content = content + new_line
        
        payload = {
            "message": f"Correction: {wrong} -> {right}",
            "content": base64.b64encode(updated_content.encode('utf-8')).decode('utf-8'),
            "sha": sha
        }
        
        put_r = requests.put(url, headers=headers, json=payload)
        if put_r.status_code in [200, 201]:
            print(f"✅ GitHub Sync Successful for {wrong}")
            return True
        else:
            print(f"❌ GitHub PUT failed: {put_r.status_code}")
            return False
    except Exception as e:
        print(f"⚠️ GitHub Sync System Error: {e}")
        return False


async def get_pokemon_name(image_url):
    url = "https://api.ocr.space/parse/image"
    # Using a fresh connector for Render's network
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        for key in OCR_KEYS:
            try:
                payload = {'apikey': key, 'url': image_url, 'language': 'eng', 'isOverlayRequired': False}
                async with session.post(url, data=payload, timeout=6) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('ParsedResults'):
                            # Get the text and strip everything except letters
                            raw_text = data['ParsedResults'][0]['ParsedText']
                            name = raw_text.strip().split('\n')[0]
                            clean_name = "".join(c for c in name if c.isalpha())
                            if clean_name:
                                print(f"🔍 OCR Success: {clean_name} (Key: {key[:5]}...)")
                                return clean_name
            except Exception as e:
                print(f"⏩ OCR Key {key[:5]} failed/timed out. Trying next...")
                continue 
    return None


async def spammer():
    await client.wait_until_ready()
    channel = client.get_channel(SPAM_CHANNEL_ID)
    while not client.is_closed():
        if spam_enabled and channel and not captcha_hit:
            try:
                await channel.send(random.choice(SPAM_MESSAGES))
                await asyncio.sleep(random.uniform(3.5, 4.8))
            except: await asyncio.sleep(10)
        else: await asyncio.sleep(5)

@client.event
async def on_message(message):
    if message.author.id == client.user.id: return
    
    global spam_enabled, captcha_hit, manual_awake, ai_enabled, SLEEP_START_HOUR, SLEEP_END_HOUR

    if is_bot_sleeping() and message.author.id != MY_USER_ID: return
        
    if message.author.id == MY_USER_ID:
        content = message.content.strip()
        cmd = content.lower()
        if cmd == ".stop": 
            spam_enabled = False
            await message.channel.send("🚫 Spammer Paused.")
        elif cmd == ".start": 
            spam_enabled = True
            await message.channel.send("✅ Spammer Resumed.")
        elif cmd == ".ping": 
            await message.channel.send(f"🏓 Pong! `{round(client.latency * 1000)}ms`")
        elif cmd == ".ai":
            ai_enabled = not ai_enabled
            await message.channel.send(f"🤖 AI Vision: {'ENABLED' if ai_enabled else 'DISABLED'}")
        elif cmd == ".status":
            s = "💤 Sleeping" if is_bot_sleeping() else "🏹 Hunting"
            await message.channel.send(f"📊 Mode: `{s}` | Spammer: `{'On' if spam_enabled else 'Off'}`")
                elif cmd.startswith(".add "):
            parts = content.split(" ")
            if len(parts) >= 3:
                wrong = parts[1].upper()
                right = " ".join(parts[2:])
                
                # Update local memory immediately
                pokemon_map[wrong] = right
                
                # Try to sync to GitHub
                success = await update_github_database(wrong, right)
                
                if success:
                    await message.channel.send(f"✅ **Correction Added:** `{wrong}` → `{right}`")
                else:
                    await message.channel.send("⚠️ **Sync Failed.** Check Render Logs for the error.")


    if message.author.id == POKETWO_ID:
        if "captcha" in message.content.lower() or "verify" in message.content.lower():
            captcha_hit, spam_enabled = True, False
            return

        # Aggressive Trade Confirm
        if "confirm this trade?" in message.content or (message.embeds and "confirm this trade?" in str(message.embeds[0].description)):
            for _ in range(10):
                await asyncio.sleep(0.5)
                msg = await message.channel.fetch_message(message.id)
                if msg.components:
                    for row in msg.components:
                        for btn in row.children:
                            if "Confirm" in getattr(btn, "label", ""):
                                await btn.click()
                                return

    if captcha_hit: return

 # --- LAYER 1: OCR ---
    if message.author.id == POKENAME_BOT_ID:
        # Check attachments OR embeds for the image URL
        img = None
        if message.attachments:
            img = message.attachments[0].url
        elif message.embeds and message.embeds[0].image:
            img = message.embeds[0].image.url

        if img:
            print(f"📸 Image detected from Poké-Name. Starting OCR...")
            name = await get_pokemon_name(img)
            if name:
                if name.upper() in pokemon_map: name = pokemon_map[name.upper()]
                await asyncio.sleep(random.uniform(2.5, 3.5))
                await message.channel.send(f"<@716390085896962058> c {name}")
                return

    # --- CATCHING LAYER 2: AI ---
    if message.author.id == POKETWO_ID and "wild pokémon has appeared" in message.content.lower():
        if ai_enabled:
            img = message.embeds[0].image.url if message.embeds else None
            if img:
                name = await get_ai_identification(img)
                if name:
                    if name.upper() in pokemon_map: name = pokemon_map[name.upper()]
                    await asyncio.sleep(random.uniform(3.0, 4.5))
                    await message.channel.send(f"<@716390085896962058> c {name}")
                else:
                    await asyncio.sleep(1.2)
                    await message.channel.send("<@716390085896962058> h")

    # --- CATCHING LAYER 3: HINT ---
    if message.author.id == POKETWO_ID and "the pokémon is" in message.content.lower():
        solved = solve_hint(message.content.split("is ")[1])
        if solved:
            if solved.upper() in pokemon_map: solved = pokemon_map[solved.upper()]
            await asyncio.sleep(random.uniform(2.5, 3.8))
            await message.channel.send(f"<@716390085896962058> c {solved}")

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    client.loop.create_task(spammer())

client.run(TOKEN)
