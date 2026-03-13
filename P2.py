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
import difflib

def get_best_match(text):
    """The Spell-Checker: Fixes OCR mistakes using pokemons.txt"""
    if not text: return None
    # 1. Surgical Extraction: Take first line, part before colon, remove non-letters
    raw_text = text.split('\n')[0].split(':')[0].strip()
    clean_input = "".join(c for c in raw_text if c.isalpha()).lower()
    
    try:
        with open("pokemons.txt", "r") as f:
            all_names = f.read().splitlines()
        # Find match with at least 60% similarity
        matches = difflib.get_close_matches(clean_input, all_names, n=1, cutoff=0.6)
        return matches[0] if matches else None
    except:
        return None
        

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
        
async def catch_action(message, name):
    """Universal catching logic for all alts."""
    if not name: return
    # Apply manual map corrections (e.g., BATTLECYCLIZAR -> BATTLE CYCLIZAR)
    if name.upper() in pokemon_map:
        name = pokemon_map[name.upper()]
    
    # Human-like delay (Staggered for alts)
    await asyncio.sleep(random.uniform(2.8, 4.5))
    await message.channel.send(f"<@716390085896962058> c {name}")
    print(f"🎯 Attempted Catch: {name}")
    

async def set_spam_lock_github(status):
    """Dedicated function to only update the SPAM_LOCK line on GitHub."""
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200: return False
        
        data = r.json()
        sha = data['sha']
        content = base64.b64decode(data['content']).decode('utf-8')
        
        # This ONLY replaces the SPAM_LOCK line. 
        # It cannot mess up your pokemon_map because it doesn't use the map logic.
        updated_content = re.sub(r'SPAM_LOCK = .*', f'SPAM_LOCK = {status}', content)
        
        payload = {
            "message": f"Spam Lock: {status}",
            "content": base64.b64encode(updated_content.encode('utf-8')).decode('utf-8'),
            "sha": sha
        }
        
        put_r = requests.put(url, headers=headers, json=payload)
        return put_r.status_code in [200, 201]
    except:
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


async def spammer_v2(alt_client):
    """Spammer that respects the specific client it belongs to."""
    await alt_client.wait_until_ready()
    
    from corrections import SPAM_LOCK
    # Staggered start so alts don't all hit the API at once
    await asyncio.sleep(random.randint(5, 20))

    # Find the right channel for THIS specific alt
    channel = alt_client.get_channel(SPAM_CHANNEL_ID) 
    
    while not alt_client.is_closed():
        if spam_enabled and not captcha_hit and str(SPAM_LOCK) != "True":
            try:
                await channel.send(random.choice(SPAM_MESSAGES))
                # Randomized long delay (12-18s) to avoid IP bans
                await asyncio.sleep(random.uniform(12.0, 18.0))
            except: await asyncio.sleep(20)
        else:
            await asyncio.sleep(5)



# --- MULTI-CLIENT HANDLER ---
def setup_events(alt_client, nickname):
    @alt_client.event
    async def on_ready():
        print(f"✅ {nickname} is online as {alt_client.user}")
        alt_client.loop.create_task(spammer_v2(alt_client))

    @alt_client.event
async def on_message(message):
        # 1. Self-Ignore: Don't let the bots talk to themselves
        if message.author.id == alt_client.user.id: return
    
    
    global spam_enabled, captcha_hit, manual_awake, ai_enabled, SLEEP_START_HOUR, SLEEP_END_HOUR

    if is_bot_sleeping() and message.author.id != MY_USER_ID: return
        
    if message.author.id == MY_USER_ID:
        content = message.content.strip()
        cmd = content.lower()
        
        if cmd == ".stop": 
            spam_enabled = False
            # Uses the safe dedicated function
            await set_spam_lock_github("True")
            await message.channel.send("🚫 **Spammer Stopped & Locked on GitHub.**")

        elif cmd == ".start": 
            spam_enabled = True
            # Uses the safe dedicated function
            await set_spam_lock_github("False")
            await message.channel.send("✅ **Spammer Resumed & Unlocked.**")

            
        elif cmd == ".ping": 
            await message.channel.send(f"🏓 Pong! `{round(client.latency * 1000)}ms`")
        
        elif cmd == ".check":
            await message.channel.send("<@716390085896962058> bal")
            return

        elif cmd.startswith(".s "):
            # This allows you to send commands like '.s info' or '.s p'
            await message.channel.send(content[3:])
            return

        elif cmd.startswith(".trade"):
            if "confirm" in cmd:
                await message.channel.send("<@716390085896962058> trade confirm")
            elif "add" in cmd:
                # Extracts the ID or number after '.trade add '
                await message.channel.send(f"<@716390085896962058> trade add {content[11:]}")
            else:
                # Handles '.trade @user'
                await message.channel.send(f"<@716390085896962058> trade {content[7:]}")
            return
            
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

 
        # --- LAYER 0: P2A ASSISTANT (Text Detection) ---
    # Replace 1222165039434436668 with the actual ID of your text bot
    if message.author.id == 1307910235737948252:
        matched = get_best_match(message.content) # Extracts name and spell-checks
        if matched:
            await catch_action(message, matched)
            return

    # --- LAYER 1: OCR (Poké-Name) ---
    if message.author.id == POKENAME_BOT_ID:
        img = message.attachments[0].url if message.attachments else (message.embeds[0].image.url if message.embeds and message.embeds[0].image else None)
        if img:
            print(f"📸 Poké-Name Spawn. Starting OCR...")
            raw_ocr = await get_pokemon_name(img)
            matched = get_best_match(raw_ocr) # Fixes typos like 'CALARIAN'
            if matched:
                await catch_action(message, matched)
                return

    # --- LAYER 2: AI VISION (Wild Spawn) ---
    if message.author.id == POKETWO_ID and "wild pokémon has appeared" in message.content.lower():
        if ai_enabled and message.embeds:
            img = message.embeds[0].image.url
            raw_ai = await get_ai_identification(img)
            matched = get_best_match(raw_ai) # Spell-checks AI result
            if matched:
                await catch_action(message, matched)
            else:
                # If AI fails, immediately ask for Hint to skip cooldown
                await asyncio.sleep(1.0)
                await message.channel.send("<@716390085896962058> h")

        # --- WRONG GUESS RECOVERY ---
    if message.author.id == POKETWO_ID and "that is the wrong pokémon" in message.content.lower():
        # If we guessed 'CALARIANSLOWBRO' and it was wrong, 
        # we don't wait—we force the Hint layer immediately.
        print("❌ Spell-check match was incorrect. Forcing Hint...")
        await asyncio.sleep(1.0)
        await message.channel.send("<@716390085896962058> h")
        

    # --- LAYER 3: HINT SOLVER ---
    if message.author.id == POKETWO_ID and "the pokémon is" in message.content.lower():
        solved = solve_hint(message.content.split("is ")[1])
        if solved:
            await catch_action(message, solved)

# --- REPLACE your 'client = ...' with this ---
# We don't create the client here anymore; we create it inside the booter.
clients = []

# --- REPLACE your 'boot' and 'attempt_login' with this ---
async def boot():
    keep_alive()
    from config import ACCOUNTS
    
    tasks = []
    for acc in ACCOUNTS:
        token = acc.get("token")
        if not token: continue
        
        # Create a UNIQUE client for every alt
        alt_client = discord.Client(self_bot=True, intents=discord.Intents.all())
        
        # We MUST attach the events (on_message, on_ready) to EACH alt_client
        # I will show you how to do this easily below
        setup_events(alt_client, acc['name']) 
        
        print(f"📡 Launching {acc['name']}...")
        tasks.append(alt_client.start(token.strip()))

    await asyncio.gather(*tasks)

def setup_events(alt_client, nickname):
    @alt_client.event
    async def on_ready():
        print(f"✅ {nickname} is online as {alt_client.user}")
        alt_client.loop.create_task(spammer_v2(alt_client)) # Unique spammer for each

    @alt_client.event
    async def on_message(message):
        # Move your ENTIRE on_message logic here
        # (Be sure to use 'alt_client' instead of 'client' inside this function)
        pass

        


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    client.loop.create_task(spammer())

if __name__ == "__main__":
    try:
        asyncio.run(boot())
    except KeyboardInterrupt:
        print("Stopping bots...")
        
