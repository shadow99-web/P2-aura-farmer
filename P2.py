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
from google import genai
from google.genai import types
from datetime import datetime
import pytz 
from flask import Flask
from threading import Thread
import difflib

def get_best_match(text):
    """Aggressive Matcher: Strips regional prefixes and complex forms."""
    if not text: return None

    # 1. Surgical Extraction: First line, before colon
    raw_line = text.split('\n')[0].split(':')[0].strip().upper()
    
    # --- NEW: PREFIX STRIPPER ---
    # Words to ignore if they appear at the start of the name
    prefixes_to_ignore = [
        "HISUIAN", "ALOLAN", "GALARIAN", "PALDEAN", "FIGHTING", 
        "PSYCHIC", "ICE", "ZENITH", "ORIGIN", "THERIAN", "SKY",
        "STEEL", "FLYING", "DARK", "GHOST", "BUG", "ROCK", "WATER", "FIRE", "GRASS", "FAIRY", "VANILLA CREAM BERRY SWEET",
    "VANILLA CREAM LOVE SWEET",
    "VANILLA CREAM STAR SWEET",
    "VANILLA CREAM CLOVER SWEET",
    "VANILLA CREAM FLOWER SWEET",
    "VANILLA CREAM RIBBON SWEET",
    "CUPCAKE", "DUSK", "MIDNIGHT"# Alcremie prefixes
    ]
    
    words = raw_line.split()
    if words and words[0] in prefixes_to_ignore:
        # Example: 'HISUIAN ZORUA' -> 'ZORUA'
        # Example: 'VANILLA CREAM...' -> 'CREAM...'
        raw_line = " ".join(words[1:])
        print(f"✂️ Stripped prefix. New target: {raw_line}")

    # Clean version for map/fuzzy check
    clean_ocr = "".join(c for c in raw_line if c.isalnum())
    
    # 2. Check manual corrections first
    if clean_ocr in pokemon_map:
        return pokemon_map[clean_ocr]

    # 3. Fuzzy search with very low cutoff (0.3)
    try:
        with open("pokemons.txt", "r") as f:
            all_names = f.read().splitlines()
        
        # We strip spaces/dashes from the TXT list for better comparison
        compare_list = [n.lower().replace(" ", "").replace("-", "") for n in all_names]
        matches = difflib.get_close_matches(clean_ocr.lower(), compare_list, n=1, cutoff=0.3)
        
        if matches:
            index = compare_list.index(matches[0])
            return all_names[index]
    except:
        pass
    
    # 4. Hail Mary
    return raw_line if raw_line else None


# --- IMPROVED KEEP ALIVE SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Aura Farmer is active and healthy!"

def run():
    # Render automatically tells the bot which port to use. 
    # If it's not set, we use 10000 (safe for Render).
    port = int(os.environ.get("PORT", 10000))
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"⚠️ Flask Server suppressed (likely already running): {e}")

def keep_alive():
    t = Thread(target=run, daemon=True) # daemon=True ensures it dies when main script dies
    t.start()


# --- MODERN AI CONFIG (Using your preferred prompt) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Using the new Client structure
client = genai.Client(api_key=GEMINI_API_KEY)

async def get_ai_identification(image_url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    
                    # Your original prompt
                    prompt = "Identify this Pokemon sprite. Return just ONLY the name. No other text or punctuation."
                    
                    # Updated syntax for the new google-genai package
                    response = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=[
                            prompt,
                            types.Part.from_bytes(data=img_data, mime_type="image/jpeg")
                        ]
                    )
                    
                    # Extract the first word and clean it
                    name = response.text.strip().split()[0]
                    return "".join(c for c in name if c.isalpha())
    except Exception as e: 
        print(f"AI Vision Error: {e}")
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
        # This will show up in your Render logs the moment the bot actually connects
        print(f"✨ [STREAMS ONLINE] {nickname} is fully connected as {alt_client.user}!")
        
        # Start the spammer for this specific account
        alt_client.loop.create_task(spammer_v2(alt_client))
    @alt_client.event
    async def on_message(message):
        # 1. Initialize individual lock status
        if not hasattr(alt_client, 'captcha_locked'):
            alt_client.captcha_locked = False
        if not hasattr(alt_client, 'ocr_lock'):
            alt_client.ocr_lock = False
            
        if message.author.id == alt_client.user.id: return
        
        global spam_enabled, manual_awake, ai_enabled, SLEEP_START_HOUR, SLEEP_END_HOUR

        # 1. Sleep Logic
        if is_bot_sleeping() and message.author.id != MY_USER_ID: return
            
        # 2. Admin Commands
        if message.author.id == MY_USER_ID:
            content = message.content.strip()
            cmd = content.lower()
            
            if cmd == ".stop": 
                spam_enabled = False
                await set_spam_lock_github("True")
                await message.channel.send(f"🚫 **{nickname} Spammer Stopped.**")
                       
            elif content == ".resume":
                alt_client.captcha_locked = False
                await message.channel.send(f"✅ **{nickname}** is back in action!")
                return
            
            elif content == ".resumeall":
                alt_client.captcha_locked = False
                await message.channel.send(f"🌍 Global Unlock: **{nickname}** resumed.")
                # Note: No return here so all bots process this command
            
            elif cmd == ".start": 
                spam_enabled = True
                await set_spam_lock_github("False")
                await message.channel.send(f"✅ **{nickname} Spammer Resumed.**")
            elif cmd == ".ping": 
                await message.channel.send(f"🏓 `{nickname}` Pong! `{round(alt_client.latency * 1000)}ms`")
            elif cmd == ".check":
                await message.channel.send("<@716390085896962058> bal")
            elif cmd.startswith(".s "):
                await message.channel.send(content[3:])
            elif cmd.startswith(".trade"):
                if "confirm" in cmd:
                    await message.channel.send("<@716390085896962058> trade confirm")
                elif "add" in cmd:
                    await message.channel.send(f"<@716390085896962058> trade add {content[11:]}")
                else:
                    await message.channel.send(f"<@716390085896962058> trade {content[7:]}")
            elif cmd == ".ai":
                ai_enabled = not ai_enabled
                await message.channel.send(f"🤖 AI Vision: {'ENABLED' if ai_enabled else 'DISABLED'}")
            
            elif cmd == ".status":
                s = "💤 Sleeping" if is_bot_sleeping() else "🏹 Hunting"
                l = "🔒 LOCKED" if alt_client.captcha_locked else "🔓 Active"
                await message.channel.send(f"📊 [{nickname}] Mode: `{s}` | Captcha: `{l}` | Spammer: `{'On' if spam_enabled else 'Off'}`")

            elif cmd.startswith(".add "):
                parts = content.split(" ")
                if len(parts) >= 3:
                    wrong, right = parts[1].upper(), " ".join(parts[2:])
                    pokemon_map[wrong] = right
                    success = await update_github_database(wrong, right)
                    await message.channel.send(f"✅ Correction Added" if success else "⚠️ Sync Failed")

        # 4. CAPTCHA DETECTION with Message Link
        if message.author.id == POKETWO_ID:
            low_msg = message.content.lower()
            if "captcha" in low_msg or "verify" in low_msg:
                alt_client.captcha_locked = True
                jump_url = message.jump_url
                print(f"🚨 CAPTCHA on {nickname}! isolated.")
                
                try:
                    main_user = await alt_client.fetch_user(MY_USER_ID)
                    await main_user.send(
                        f"⚠️ **CAPTCHA ALERT**\nBot: `{nickname}`\n"
                        f"🔗 **Solve here:** {jump_url}\n"
                        f"Status: **PAUSED**. Type `.resume` to continue."
                    )
                except Exception as e:
                    print(f"DM Failed: {e}")
                return

        # 5. The Individual Gatekeeper (Kill-switch)
        if alt_client.captcha_locked: return

        # --- CATCHING LAYERS ---
        
        # LAYER 0: Assistant (Check if Assistant Bots are present)
        if message.author.id in [854233015475109888, 1459494731775217860]:
            matched = get_best_match(message.content)
            if matched:
                alt_client.ocr_lock = True 
                await catch_action(message, matched)
                await asyncio.sleep(10)
                alt_client.ocr_lock = False
                return

        # LAYER 1: OCR (Check if Pokename Bot is present)
        if message.author.id == POKENAME_BOT_ID:
            if getattr(alt_client, 'ocr_lock', False):
                print(f"⏩ [{nickname}] Assistant handled it. Skipping OCR.")
                return
            img = message.attachments[0].url if message.attachments else (message.embeds[0].image.url if message.embeds else None)
            if img:
                raw_ocr = await get_pokemon_name(img)
                matched = get_best_match(raw_ocr)
                if matched:
                    await catch_action(message, matched)
                    return
                    
        # LAYER 2: AI & RECOVERY (Handles servers with NO help bots)
        if message.author.id == POKETWO_ID:
            low_content = message.content.lower()
            
            # 1. New Spawn Detection
            if "wild pokémon has appeared" in low_content and ai_enabled:
                # Check if we already caught it via Layer 0 or 1
                if getattr(alt_client, 'ocr_lock', False): return
                
                img = message.embeds[0].image.url if message.embeds else None
                if img:
                    print(f"👁️ [{nickname}] No helper bots detected. Using AI Vision...")
                    raw_ai = await get_ai_identification(img)
                    matched = get_best_match(raw_ai)
                    
                    if matched:
                        # AI found a name! Catch it.
                        await catch_action(message, matched)
                    else:
                        # AI failed or isn't sure? Get the hint for 100% accuracy.
                        await message.channel.send("<@716390085896962058> h")
            
            # 2. Wrong Guess Recovery
            elif "that is the wrong pokémon" in low_content:
                print(f"❌ [{nickname}] Guess was wrong. Forcing Hint...")
                await asyncio.sleep(1.0)
                await message.channel.send("<@716390085896962058> h")

            # 3. Hint Solver (The Final Safety Net)
            elif "the pokémon is" in low_content:
                solved = solve_hint(message.content.split("is ")[1])
                if solved:
                    print(f"💡 [{nickname}] Hint Solved: {solved}")
                    await catch_action(message, solved)




# --- MODERN BOOT LOGIC ---
async def safe_start(client, token, nickname):
    """Starts an individual bot with a forced heartbeat and timeout."""
    try:
        print(f"📡 [DEBUG] Sending login request for: {nickname}")
        # We use .start() instead of .run() to keep it inside our main loop
        await client.start(token.strip())
    except discord.errors.LoginFailure:
        print(f"❌ [AUTH] {nickname}: Token is invalid. Get a new one from your browser.")
    except Exception as e:
        print(f"🛑 [ERROR] {nickname}: {e}")

async def main_boot():
    keep_alive()
    
    # Manually pull from Env for safety
    ACCOUNTS = []
    for i in range(1, 5):
        t = os.getenv(f"TOKEN{i}")
        if t: ACCOUNTS.append({"token": t, "name": f"Alt {i}"})

    for acc in ACCOUNTS:
        # --- THE FIX: ADD HEARTBEAT & CHUNK LOADING ---
        # This prevents the bot from hanging during the "Attempting to login" phase
        alt_client = discord.Client(
            self_bot=True, 
            heartbeat_timeout=60.0, 
            guild_ready_timeout=60.0
        )
        
        setup_events(alt_client, acc['name'])
        asyncio.create_task(safe_start(alt_client, acc['token'], acc['name']))
        
        # INCREASE THIS DELAY: 10 seconds between alts
        # Discord hates it when 4 accounts login from the same IP at once.
        print(f"⏳ Waiting 10s before next login to avoid IP flags...")
        await asyncio.sleep(10) 
    
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        # asyncio.run is the modern way to start the loop in Python 3.10+
        asyncio.run(main_boot())
    except KeyboardInterrupt:
        print("Stopping Aura Farmer...")
    except Exception as e:
        print(f"Fatal System Error: {e}")
