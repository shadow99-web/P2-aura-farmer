import discord
import aiohttp
import asyncio
import random
import base64
import requests
import os
import ssl
import re
from corrections import pokemon_map
import google.generativeai as genai

# --- AI CONFIGURATION ---
# Use the API Key you obtained from Google AI Studio
GEMINI_API_KEY = "YOUR_API_KEY" 
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
TOKEN = "your_acc_token"
POKENAME_BOT_ID = 874910942490677270
POKETWO_ID = 716390085896962058
SPAM_CHANNEL_ID = 1459841583536148601
MY_USER_ID = 1378954077462986772
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = "shadow99-web/P2-aura-farmer" 
FILE_PATH = "corrections.py"

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
                await asyncio.sleep(random.uniform(2.5, 4.0))
            except Exception as e:
                print(f"\nSpam Error: {e}")
                await asyncio.sleep(10)
        else:
            await asyncio.sleep(5)

@client.event
async def on_message(message):
    global spam_enabled, captcha_hit

    # 1. REMOTE CONTROL & UTILITIES
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
                   
        elif cmd == ".ai":
            ai_enabled = not ai_enabled
            status = "ENABLED" if ai_enabled else "DISABLED"
            await message.channel.send(f"🤖 **AI Vision is now {status}**")
            return

        elif cmd == ".status":
            ocr_s = "⏳ Cooldown" if ocr_on_cooldown else "✅ Ready"
            ai_s = "⏳ Cooldown" if ai_on_cooldown else ("✅ Ready" if ai_enabled else "❌ Disabled")
            await message.channel.send(
                f" __**System Status**__\n"
                f"OCR: `{ocr_s}`\n"
                f"AI Vision: `{ai_s}`\n"
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
     # --- TIME & TIMER MANAGEMENT ---
    current_time = asyncio.get_event_loop().time()
    if ocr_on_cooldown and (current_time - last_ocr_fail_time > 600):
        ocr_on_cooldown = False
        print("🕒 OCR Cooldown Over.")
    if ai_on_cooldown and (current_time - last_ai_fail_time > 900): # 15 min
        ai_on_cooldown = False
        print("🕒 AI Cooldown Over.")

    # --- LAYER 1: OCR (Triggered by Pokename Bot) ---
    if message.author.id == POKENAME_BOT_ID:
        hint_already_sent = False # Reset flag for new spawn
        image_url = message.attachments[0].url if message.attachments else None
        
        if image_url and not ocr_on_cooldown:
            print("\n🔍 Layer 1: OCR Scanning...")
            name = await get_pokemon_name(image_url)
            if name:
                if name.upper() in pokemon_map: name = pokemon_map[name.upper()]
                await asyncio.sleep(random.uniform(2.1, 3.2))
                await message.channel.send(f"<@716390085896962058> c {name}")
                print(f"✅ Caught via OCR: {name}")
                return
            else:
                print("❌ OCR Failed. Entering Cooldown, waiting for Poketwo image for AI...")
                ocr_on_cooldown = True
                last_ocr_fail_time = current_time

    # --- LAYER 2: AI VISION (Triggered by Poketwo Bot) ---
    if message.author.id == POKETWO_ID and "wild pokémon has appeared" in message.content.lower():
        # Only run AI if OCR has already failed (ocr_on_cooldown is True)
        if ai_enabled and ocr_on_cooldown and not ai_on_cooldown:
            # Poketwo sends the large image in an embed
            image_url = message.embeds[0].image.url if message.embeds else None
            
            if image_url:
                print("🧠 Layer 2: AI Vision (Scanning large Poketwo image)...")
                ai_name = await get_ai_identification(image_url)
                if ai_name:
                    if ai_name.upper() in pokemon_map: ai_name = pokemon_map[ai_name.upper()]
                    await asyncio.sleep(random.uniform(2.2, 4.2)) # Slightly longer for AI
                    await message.channel.send(f"<@716390085896962058> c {ai_name}")
                    print(f"✅ Caught via AI: {ai_name}")
                    return
                else:
                    print("❌ AI Failed. Entering 15m Cooldown. Fallback to Hint...")
                    ai_on_cooldown = True
                    last_ai_fail_time = current_time
                    
                    # LAYER 3: HINT REQUEST (If AI fails)
                    if not hint_already_sent:
                        await asyncio.sleep(1.2)
                        await message.channel.send("<@716390085896962058> h")
                        hint_already_sent = True
              
    # 5. AUTOMATIC HINT SOLVER (The Safety Net)
    if message.author.id == POKETWO_ID and "the pokémon is" in message.content.lower():
        try:
            raw_hint = message.content.split("is ")[1]
            solved_name = solve_hint(raw_hint)
            
            if solved_name:
                print(f"✅ Hint Solved: {solved_name}")
                await asyncio.sleep(random.uniform(2.5, 4.0))
                await message.channel.send(f"<@716390085896962058> c {solved_name}")
            else:
                print(f"❓ Could not solve hint pattern: {raw_hint}")
        except Exception as e:
            print(f"Hint Error: {e}")

@client.event
async def on_ready():
    print(f"Logged in as {client.user} - Multi-Key OCR - HINT - Captcha Protection Active")
    client.loop.create_task(spammer())

client.run(TOKEN)
