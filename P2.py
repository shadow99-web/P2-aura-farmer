import discord
import aiohttp
import asyncio
import random
import os
import ssl
from corrections import pokemon_map

# --- CONFIGURATION ---
TOKEN = "your_acc_token"
POKENAME_BOT_ID = 874910942490677270
POKETWO_ID = 716390085896962058
SPAM_CHANNEL_ID = 1459841583536148601
MY_USER_ID = 1378954077462986772

OCR_KEYS = [
    "K81439983988957",
    "K89035013988957",
    "K86412733888957"
]

SPAM_MESSAGES = ["vroom vroom", "mining time", "keep going", "catch them all"]
spam_enabled = True
captcha_hit = False  # New safety switch

client = discord.Client(self_bot=True)

async def get_pokemon_name(image_url):
    # Standard URL - This is the only way to avoid the SSLError
    url = "https://api.ocr.space/parse/image"
    
    # We use a standard connector but enable 'happy_eyeballs'
    # This helps mobile data find the fastest path to the server
    connector = aiohttp.TCPConnector(ssl=False, force_close=True, happy_eyeballs_delay=0.25)
    
    # Adjusted timeouts for Mathura mobile data:
    # 5s to find the server (Connect), 10s to get the results back (Total)
    timeout = aiohttp.ClientTimeout(total=6, connect=3, sock_read=3.5)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for key in OCR_KEYS:
            print(f"Scanning | Key: {key[:5]}...")
            payload = {'apikey': key, 'url': image_url, 'language': 'eng'}
            
            try:
                # We add a tiny sleep to prevent 'Socket Hanging' on Redmi devices
                await asyncio.sleep(0.2)
                async with session.post(url, data=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('ParsedResults'):
                            text = data['ParsedResults'][0]['ParsedText']
                            name = text.strip().split('\n')[0]
                            return "".join(c for c in name if c.isalpha())
                    else:
                        print(f"Key {key[:5]} - Server Busy ({resp.status})")
            except Exception as e:
                # This will now catch the error and move to Key 2 or 3
                print(f"Key {key[:5]} failed: {type(e).__name__}")
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

    # 1. REMOTE CONTROL & UTILITIES (Listen to your Main ID only)
    if message.author.id == MY_USER_ID:
        content = message.content.strip()
        cmd = content.lower()

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

        # --- NEW COMMAND: ADD CORRECTION (.add WRONG RIGHT) ---
        if cmd.startswith(".add "):
            try:
                parts = content.split(" ")
                wrong = parts[1].upper()
                right = " ".join(parts[2:]) # Handles names with spaces like 'BATTLE CYCLIZAR'
                
                # Update live dictionary
                pokemon_map[wrong] = right
                
                # Append to corrections.py so it saves permanently
                with open("corrections.py", "a") as f:
                    f.write(f'\npokemon_map["{wrong}"] = "{right}"')
                
                await message.channel.send(f"✅ Added: `{wrong}` → `{right}`")
                print(f"Correction Added: {wrong} -> {right}")
            except Exception as e:
                await message.channel.send("❌ Format: `.add WrongName RightName`")
            return

        # --- NEW COMMAND: CHECK POKETWO BALANCE ---
        if cmd == ".check":
            await message.channel.send("💰 **Checking Pokétwo Balance...**")
            await message.channel.send("<@716390085896962058> bal")
            return

     # --- NEW MANUAL TRADE RELAY ---
        if cmd.startswith(".trade"):
            parts = content.split(" ")
            
            # .trade @user (Start trade)
            if len(parts) == 2 and "<@" in parts[1]:
                target = parts[1]
                await message.channel.send(f"<@716390085896962058> trade {target}")
                return

            # .trade add [anything] (Flexible relay)
            if len(parts) >= 3 and parts[1] == "add":
                # This grabs everything after '.trade add '
                raw_input = content[11:] 
                await message.channel.send(f"<@716390085896962058> trade add {raw_input}")
                return

            # .trade confirm (Manual trigger)
            if "confirm" in cmd:
                await message.channel.send(f"<@716390085896962058> trade confirm")
                return

            # .trade x (Cancel)
            if " x" in cmd:
                await message.channel.send(f"<@716390085896962058> trade cancel")
                return

      # 2. POKETWO INTERACTION (Captcha & Trade Buttons)
    if message.author.id == POKETWO_ID:
        msg_check = message.content.lower()

        # --- CAPTCHA DETECTION ---
        if "captcha" in msg_check or "verify" in msg_check:
            captcha_hit = True
            spam_enabled = False
            main_user = await client.fetch_user(MY_USER_ID)
            await main_user.send(f"🚨 **CAPTCHA DETECTED!** Solve it and type `.resume`.")
            return

        # --- AUTO-CONFIRM BUTTON ---
        if "Are you sure you want to confirm this trade?" in message.content:
            for component in message.components:
                for child in component.children:
                    if getattr(child, "label", "") == "Confirm":
                        try:
                            delay = random.uniform(1.5, 2.5)
                            await asyncio.sleep(delay) 
                            await child.click()
                            print(f"✅ Clicked Confirm after {delay:.2f}s")
                        except Exception as e:
                            print(f"❌ Button click failed: {e}")
    # 3. GLOBAL SAFETY GATE
    if captcha_hit:
        return

    # 4. CATCHING LOGIC
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
                # Apply corrections from corrections.py
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
    print(f"Logged in as {client.user} - Multi-Key OCR & Captcha Protection Active")
    client.loop.create_task(spammer())

client.run(TOKEN)
