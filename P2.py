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
import pytz # Add 'pytz' to your requirements.txt
from flask import Flask
from threading import Thread

# --- KEEP ALIVE SERVER ---

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
  app.run(host='0.0.0.0',port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
    

def is_bot_sleeping():
    global manual_awake, SLEEP_START_HOUR, SLEEP_END_HOUR
    if manual_awake:
        return False
        
    # Get current time in India (IST)
    IST = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(IST).hour
    
    # Logic for sleep window (handles overnight schedules like 23 to 6)
    if SLEEP_START_HOUR < SLEEP_END_HOUR:
        return SLEEP_START_HOUR <= now_ist < SLEEP_END_HOUR
    else: # Handles cases like Start: 22, End: 6
        return now_ist >= SLEEP_START_HOUR or now_ist < SLEEP_END_HOUR
    

# --- AI CONFIGURATION ---
# Use the API Key you obtained from Google AI Studio
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

async def get_ai_identification(image_url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    # Prompt ensures only the name is returned for catching
                    prompt = "Identify this Pokemon sprite. Return just ONLY the name. No other text or punctuation."
                    response = ai_model.generate_content([
                        prompt,
                        {'mime_type': 'image/jpeg', 'data': img_data}
                    ])
                    name = response.text.strip().split()[0]
                    return "".join(c for c in name if c.isalpha())
    except Exception as e:
        print(f"AI Vision Error: {e}")
    return None
    

# --- CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
POKENAME_BOT_ID = 874910942490677270
POKETWO_ID = 716390085896962058
SPAM_CHANNEL_ID = 1459841583536148601
MY_USER_ID = 1378954077462986772
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = "shadow99-web/P2-aura-farmer" 
FILE_PATH = "corrections.py"
# --- SLEEP CONFIG ---
SLEEP_START_HOUR = 1  # Default 1 AM
SLEEP_END_HOUR = 7    # Default 7 AM
manual_awake = False


OCR_KEYS = [
    "K81439983988957",
    "K89035013988957",
    "K86412733888957"
]

SPAM_MESSAGES = ["vroom vroom", "mining time", "keep going", "catch them all"]
spam_enabled = True
captcha_hit = False 
last_ocr_fail_time = 0
ocr_on_cooldown = False
hint_already_sent = False
ai_on_cooldown = False
last_ai_fail_time = 0
ai_enabled = True
# New safety switch

keep_alive()
client = discord.Client(self_bot=True)

def solve_hint(hint_pattern):
    # 1. Clean the string: remove periods, backslashes, and extra spaces
    clean = hint_pattern.replace('\\', '').replace('.', '').replace(' ', '').strip()
    
    # 2. Convert underscores to dots for Regex (Ar___ba_ -> Ar...ba.)
    regex_pattern = f"^{clean.replace('_', '.')}$"
    
    try:
        with open("pokemons.txt", "r") as f:
            names = f.read().splitlines()
        
        for name in names:
            # We must ignore case and check exact length
            if re.fullmatch(regex_pattern, name, re.IGNORECASE):
                return name
    except Exception as e:
        print(f"File Error: {e}")
    return None

async def update_github_database(wrong, right):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        # 1. Get the current file content and its 'sha' (needed for updates)
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            return False, f"GitHub Error: {r.status_code}"
            
        data = r.json()
        sha = data['sha']
        # Decode the existing file content
        content = base64.b64decode(data['content']).decode('utf-8')
        
        # 2. Add the new line
        new_line = f'\npokemon_map["{wrong.upper()}"] = "{right}"'
        updated_content = content + new_line
        
        # 3. Push the update back to GitHub
        payload = {
            "message": f"Added Correction: {wrong} -> {right}",
            "content": base64.b64encode(updated_content.encode('utf-8')).decode('utf-8'),
            "sha": sha
        }
        
        put_r = requests.put(url, headers=headers, json=payload)
        if put_r.status_code == 200:
            return True, "Success"
        else:
            return False, f"Push failed: {put_r.status_code}"
            
    except Exception as e:
        return False, str(e)

async def get_pokemon_name(image_url):
    url = "https://api.ocr.space/parse/image"
    
    connector = aiohttp.TCPConnector(
        ssl=False, 
        force_close=True, 
        enable_cleanup_closed=True,
        limit_per_host=1,
        happy_eyeballs_delay=0.15 # Added for faster mobile data routing
    )
    
    
    timeout = aiohttp.ClientTimeout(total=6.5, connect=2, sock_read=4)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for key in OCR_KEYS:
            try:
                payload = {'apikey': key, 'url': image_url, 'language': 'eng'}
                async with session.post(url, data=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('ParsedResults'):
                            text = data['ParsedResults'][0]['ParsedText']
                            name = text.strip().split('\n')[0]
                            return "".join(c for c in name if c.isalpha())
            except Exception:
                # Instant switch on any lag
                print(f"⏩ Key {key[:5]} lagging... switching.")
                continue 
    return None

async def update_github_sleep(start, end):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200: return False
        
        data = r.json()
        sha = data['sha']
        content = base64.b64decode(data['content']).decode('utf-8')
        
        # We use Regex to find and replace the existing lines
        content = re.sub(r'SLEEP_START_HOUR = \d+', f'SLEEP_START_HOUR = {start}', content)
        content = re.sub(r'SLEEP_END_HOUR = \d+', f'SLEEP_END_HOUR = {end}', content)
        
        payload = {
            "message": f"Updated Sleep Schedule: {start}-{end}",
            "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
            "sha": sha
        }
        
        put_r = requests.put(url, headers=headers, json=payload)
        return put_r.status_code == 200
    except:
        return False
        

async def spammer():
    global spam_enabled, captcha_hit
    await client.wait_until_ready()
    channel = client.get_channel(SPAM_CHANNEL_ID)

    while not client.is_closed():
        # Stop spamming if captcha is hit or disabled
        if spam_enabled and channel and not captcha_hit:
            try:
                await channel.send(random.choice(SPAM_MESSAGES))
                print(".", end="", flush=True)
                await asyncio.sleep(random.uniform(3.5, 4.6))
            except Exception as e:
                print(f"\nSpam Error: {e}")
                await asyncio.sleep(10)
        else:
            await asyncio.sleep(5)

@client.event
async def on_message(message):

      # This prevents the bot from responding to its own messages
    if message.author.id == client.user.id:
        return
        
    global spam_enabled, captcha_hit, manual_awake, SLEEP_START_HOUR, SLEEP_END_HOUR
    global ocr_on_cooldown, last_ocr_fail_time, ai_on_cooldown, last_ai_fail_time, hint_already_sent

    # --- SAFETY GATE: IGNORE SPAWNS IF SLEEPING ---
    if is_bot_sleeping() and message.author.id != MY_USER_ID:
        return
        
    if message.author.id == MY_USER_ID:
        content = message.content.strip()
        cmd = content.lower()

        # --- Basic Controls ---
        if cmd == ".stop":
            spam_enabled = False
            await message.channel.send("🚫 **Spammer Paused.**")
            return
        elif cmd == ".start":
            spam_enabled = True
            await message.channel.send("✅ **Spammer Resumed.**")
            return
        elif cmd == ".resume":
            captcha_hit = False
            spam_enabled = True
            await message.channel.send("🛠️ **Safety Reset: Bot Resumed.**")
            return
        elif cmd == ".ping":
            latency = round(client.latency * 1000)
            await message.channel.send(f"🏓 **Pong!** Latency: `{latency}ms`")
            return
        elif cmd == ".reset":
            captcha_hit = False
            spam_enabled = True
            await message.channel.send("♻️ **System Overhaul Complete.**")
            return
        # --- PERMANENT .setsleep ---
        elif cmd.startswith(".setsleep "):
            try:
                parts = content.split(" ")
                if len(parts) == 3:
                    new_start = int(parts[1])
                    new_end = int(parts[2])
                    
                    if 0 <= new_start <= 23 and 0 <= new_end <= 23:
                        global SLEEP_START_HOUR, SLEEP_END_HOUR, manual_awake
                        
                        # Update Local Memory
                        SLEEP_START_HOUR = new_start
                        SLEEP_END_HOUR = new_end
                        manual_awake = False
                        
                        msg = await message.channel.send(f"🔄 **Syncing Sleep Schedule ({new_start}-{new_end}) to GitHub...**")
                        
                        # Update GitHub Database
                        success = await update_github_sleep(new_start, new_end)
                        
                        if success:
                            await msg.edit(content=f"⏰ **Permanent Schedule Updated!**\n`{new_start}:00` to `{new_end}:00` IST (Saved to GitHub)")
                        else:
                            await msg.edit(content=f"⚠️ **Memory updated, but GitHub Sync failed.** It will reset on restart.")
                    else:
                        await message.channel.send("❌ Use 24-hour format (0-23).")
            except Exception as e:
                await message.channel.send(f"❌ Error: {e}")
            return

        # --- SLEEP CONTROLS ---
        elif cmd == ".sleep":
            manual_awake = False
            await message.channel.send("🌙 **Schedule Active:** Bot will now follow sleep hours.")
            return

        elif cmd == ".wakeup":
            manual_awake = True
            await message.channel.send("☕ **Manual Override:** Bot is now AWAKE and ignoring schedule.")
            return

        elif cmd == ".reset sleep":
            manual_awake = False
            await message.channel.send(" **Sleep Reset:** Manual override cleared. Following schedule.")
            return
                   
        elif cmd == ".ai":
            ai_enabled = not ai_enabled
            status = "ENABLED" if ai_enabled else "DISABLED"
            await message.channel.send(f"🤖 **AI Vision is now {status}**")
            return

        elif cmd == ".status":
            ocr_s = "⏳ Cooldown" if ocr_on_cooldown else "✅ Ready"
            ai_s = "⏳ Cooldown" if ai_on_cooldown else ("✅ Ready" if ai_enabled else "❌ Disabled")
            sleep_status = "💤 Sleeping" if is_bot_sleeping() else "🏹 Hunting"
            
            await message.channel.send(
                f"📊 __**System Status**__\n"
                f"Current Mode: `{sleep_status}`\n"
                f"Schedule: `{SLEEP_START_HOUR}:00` to `{SLEEP_END_HOUR}:00` (IST)\n"
                f"OCR: `{ocr_s}` | AI: `{ai_s}`\n"
                f"Spammer: `{'On' if spam_enabled else 'Off'}`"
            )
            return
            
        # --- FIXED: The .check command ---
        elif cmd == ".check":
            await message.channel.send("<@716390085896962058> bal")
            return

        # --- Relay (.s info, .s p) ---
        elif cmd.startswith(".s "):
            await message.channel.send(content[3:])
            return

        # --- FIXED: Trade Logic with correct slicing ---
        elif cmd.startswith(".trade"):
            if "confirm" in cmd:
                await message.channel.send("<@716390085896962058> trade confirm")
            elif "add" in cmd:
                # skips '.trade add ' (11 chars) to send the clean command
                await message.channel.send(f"<@716390085896962058> trade add {content[11:]}")
            elif " x" in cmd:
                await message.channel.send("<@716390085896962058> trade cancel")
            else:
                # handles '.trade @user' (skips 7 chars: '.trade ')
                await message.channel.send(f"<@716390085896962058> trade {content[7:]}")
            return

        # --- Corrections ---
        elif cmd.startswith(".add "):
            try:
                parts = content.split(" ")
                if len(parts) < 3:
                    await message.channel.send("❌ Format: `.add WrongName CorrectName`")
                    return

                wrong = parts[1].upper()
                right = " ".join(parts[2:])

                # Update local map for immediate effect
                pokemon_map[wrong] = right
                
                # Inform the user and start GitHub sync
                msg = await message.channel.send(f"🔄 **Syncing `{wrong}` to GitHub...**")
                
                success, error_msg = await update_github_database(wrong, right)
                
                if success:
                    await msg.edit(content=f"✅ **Database Updated:** `{wrong}` → `{right}` (Saved to GitHub)")
                else:
                    await msg.edit(content=f"⚠️ **Local update ok, but GitHub failed:** `{error_msg}`")
            except Exception as e:
                await message.channel.send(f" System Error: {e}")
            return


    # 2. POKETWO INTERACTION (Captcha & Trade Buttons)
    if message.author.id == POKETWO_ID:
        msg_check = message.content.lower()

        # --- CAPTCHA DETECTION ---
        if "captcha" in msg_check or "verify" in msg_check:
            captcha_hit = True
            spam_enabled = False
            main_user = client.get_user(MY_USER_ID)
            if main_user:
                await main_user.send(f"🚨 **CAPTCHA DETECTED!** Solve it and type `.resume`.")
            print("\n🚨 CAPTCHA DETECTED! Bot Paused.")
            return

        # --- AGGRESSIVE TRADE CONFIRM ---
        target_text = "Are you sure you want to confirm this trade?"
        is_trade = target_text in message.content
        if not is_trade and message.embeds:
            for eb in message.embeds:
                if eb.description and target_text in eb.description:
                    is_trade = True
                    break

        if is_trade:
            print("🔔 Trade Found! Waiting for buttons...")
            # We check 8 times because mobile data is inconsistent
            for attempt in range(8):
                await asyncio.sleep(0.5) 
                try:
                    # FORCE FETCH from Discord to see the buttons
                    msg = await message.channel.fetch_message(message.id)
                    if msg.components:
                        for row in msg.components:
                            for btn in row.children:
                                if getattr(btn, "label", "") == "Confirm":
                                    await asyncio.sleep(0.5) # Minimum safe delay
                                    await btn.click()
                                    print(f"✅ SUCCESS: Clicked on attempt {attempt+1}")
                                    return
                except Exception as e:
                    print(f"Attempt {attempt+1} sync failed: {e}")
            return


    # 3. GLOBAL SAFETY GATE
    if captcha_hit:
        return

         # 4. CATCHING LOGIC (OCR Priority)
         # --- LAYER 1: OCR ---
    if message.author.id == POKENAME_BOT_ID:
        image_url = message.attachments[0].url if message.attachments else None
        if image_url:
            name = await get_pokemon_name(image_url)
            if name:
                if name.upper() in pokemon_map: name = pokemon_map[name.upper()]
                await asyncio.sleep(random.uniform(2.1, 3.2))
                await message.channel.send(f"<@716390085896962058> c {name}")
                return # Exit if caught
            else:
                # If OCR fails, we don't return; we let the bot wait for Layer 2
                print("❌ OCR failed to find name.")

    # --- LAYER 2: AI VISION ---
    if message.author.id == POKETWO_ID and "wild pokémon has appeared" in message.content.lower():
        # Removed the 'ocr_on_cooldown' requirement so AI is always a backup
        if ai_enabled and not ai_on_cooldown:
            image_url = message.embeds[0].image.url if message.embeds else None
            if image_url:
                ai_name = await get_ai_identification(image_url)
                if ai_name:
                    if ai_name.upper() in pokemon_map: ai_name = pokemon_map[ai_name.upper()]
                    await asyncio.sleep(random.uniform(2.5, 4.5))
                    await message.channel.send(f"<@716390085896962058> c {ai_name}")
                    return
                else:
                    # If AI also fails, request the hint immediately
                    await asyncio.sleep(1.0)
                    await message.channel.send("<@716390085896962058> h")


@client.event
async def on_ready():
    print(f"Logged in as {client.user} - Multi-Key OCR - HINT - Captcha Protection Active")
    client.loop.create_task(spammer())

client.run(TOKEN)
