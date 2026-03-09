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
        
        # --- NEW COMMAND: RESET ---
        elif cmd == ".reset":
            captcha_hit = False
            spam_enabled = True
            # This force-clears any hanging tasks in the console
            print("\n♻️ Manual System Reset Triggered...")
            await message.channel.send("♻️ **Bot state and tasks have been reset.**")
            return

        elif cmd.startswith(".s "):
            relay_content = content[3:] 
            await message.channel.send(relay_content)
            return

        elif cmd.startswith(".add "):
            try:
                parts = content.split(" ")
                wrong = parts[1].upper()
                right = " ".join(parts[2:])
                pokemon_map[wrong] = right
                with open("corrections.py", "a") as f:
                    f.write(f'\npokemon_map["{wrong}"] = "{right}"')
                await message.channel.send(f"✅ Added: `{wrong}` → `{right}`")
            except:
                await message.channel.send("❌ Format: `.add Wrong Right`")
            return

        elif cmd.startswith(".trade"):
            # Consolidated Trade Logic
            if "confirm" in cmd:
                await message.channel.send(f"<@716390085896962058> trade confirm")
            elif "add" in cmd:
                await message.channel.send(f"<@716390085896962058> trade {content[7:]}")
            elif " x" in cmd:
                await message.channel.send(f"<@716390085896962058> trade cancel")
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
