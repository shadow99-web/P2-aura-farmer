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
from datetime import datetime
import pytz
from flask import Flask
from threading import Thread
import difflib
import sys
from io import BytesIO
import json
import unicodedata
from config import ACCOUNTS


# --- CRITICAL FIX ---
from discord.state import ConnectionState

def patched_parse_ready_supplemental(self, data):
    try:
        self.pending_payments = {int(p['id']): p for p in data.get('pending_payments') or []}
    except Exception:
        self.pending_payments = {}

ConnectionState.parse_ready_supplemental = patched_parse_ready_supplemental

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
POKENAME_BOT_ID = 874910942490677270
POKETWO_ID = 716390085896962058
SPAM_CHANNEL_ID = 1459841583536148601
ADMIN_IDS = [1378954077462986772, 876746134352183336, 1489464610565390336]
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = "shadow99-web/P2-aura-farmer"
FILE_PATH = "corrections.py"
ai_enabled = False  # Global AI toggle

spam_enabled = True
captcha_hit = False
manual_awake = False
ocr_on_cooldown = False   
OCR_KEYS = ["K81439983988957", "K89035013988957", "K86412733888957"]
SPAM_MESSAGES = ["vroom vroom", "mining time", "keep going", "catch them all"]

# --- Flask keep-alive ---
app = Flask('')
@app.route('/')
def home():
    return "Aura Farmer is active!"

def run():
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run, daemon=True).start()

# --- Helper functions ---
def is_bot_sleeping():
    if manual_awake:
        return False
    now_ist = datetime.now(pytz.timezone('Asia/Kolkata')).hour
    if SLEEP_START_HOUR < SLEEP_END_HOUR:
        return SLEEP_START_HOUR <= now_ist < SLEEP_END_HOUR
    return now_ist >= SLEEP_START_HOUR or now_ist < SLEEP_END_HOUR

def solve_hint(hint_pattern):
    clean = hint_pattern.replace('\\', '').replace('.', '').replace(' ', '').strip()
    regex_pattern = f"^{clean.replace('_', '.')}$"
    try:
        with open("pokemons.txt", "r") as f:
            names = f.read().splitlines()
        for name in names:
            if re.fullmatch(regex_pattern, name, re.IGNORECASE):
                return name
    except Exception as e:
        print(f"File Error: {e}")
    return None

def get_best_match(text):
    if not text:
        return None
    raw_line = text.split('\n')[0].split(':')[0].strip().upper()
    prefixes_to_ignore = [
        "HISUIAN", "ALOLAN", "GALARIAN", "PALDEAN", "FIGHTING",
        "PSYCHIC", "ICE", "ZENITH", "ORIGIN", "THERIAN", "SKY",
        "STEEL", "FLYING", "DARK", "GHOST", "BUG", "ROCK", "WATER",
        "FIRE", "GRASS", "FAIRY", "VANILLA", "RUBY", "MATCHA",
        "MINT", "LEMON", "SALTED", "CUPCAKE", "DUSK", "MIDNIGHT",
        "CREAM", "BERRY", "SWEET", "LOVE", "STAR", "CLOVER", "FLOWER", "RIBBON"
    ]
    words = raw_line.split()
    while words and words[0] in prefixes_to_ignore:
        words.pop(0)
    raw_line = " ".join(words)
    clean_ocr = "".join(c for c in raw_line if c.isalnum())
    if clean_ocr in pokemon_map:
        return pokemon_map[clean_ocr]
    try:
        with open("pokemons.txt", "r") as f:
            all_names = f.read().splitlines()
        compare_list = [n.lower().replace(" ", "").replace("-", "") for n in all_names]
        matches = difflib.get_close_matches(clean_ocr.lower(), compare_list, n=1, cutoff=0.3)
        if matches:
            index = compare_list.index(matches[0])
            return all_names[index]
    except:
        pass
    return raw_line if raw_line else None


        
async def query_private_onnx_api(image_url):
    """Queries your custom naming bot hosted on Hugging Face Space."""
    api_url = "https://discordbotnhihun-naming.hf.space/predict"
    
    headers = {
        "Content-Type": "application/json"
    }
    payload = {"imageUrl": image_url}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(api_url, headers=headers, json=payload, timeout=5.0) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") is True:
                        name = data.get("name")
                        confidence = data.get("confidence", 0)
                        print(f"🧠 [Custom Naming Bot] {name} (Conf: {confidence})", flush=True)
                        return name
                    else:
                        print(f"⚠️ [Custom Naming Bot] API returned error: {data}", flush=True)
                else:
                    print(f"⚠️ [Custom Naming Bot] HTTP {resp.status}", flush=True)
        except asyncio.TimeoutError:
            print("⏱️ [Custom Naming Bot] Request timed out.", flush=True)
        except Exception as e:
            print(f"⚠️ [Custom Naming Bot] Error: {e}", flush=True)
    return None

async def extract_spawn_image(message):
    """
    Extract Pokémon spawn image from a Discord message.
    Returns the image URL or None if not a spawn.
    """
    img_url = None
    is_spawn = False

    # 1. Check message content for spawn indicators
    msg_content = message.content.lower() if message.content else ""
    if "wild **" in msg_content and "** has appeared" in msg_content:
        is_spawn = True

    # 2. Deep Embed Scanning
    if message.embeds:
        for embed in message.embeds:
            embed_title = embed.title.lower() if embed.title else ""
            embed_desc = embed.description.lower() if embed.description else ""
            author_name = embed.author.name.lower() if (embed.author and embed.author.name) else ""

            # Check for spawn indicators in embed
            if (
                "wild pokémon has appeared" in embed_title or
                "wild pokémon has appeared" in embed_desc or
                "wild pokémon has appeared" in author_name or
                "guess the pokémon" in embed_desc
            ) or (embed.description and "#" in embed.description and "catch" in embed_desc):
                is_spawn = True

            # Extract image from Embed Image
            if embed.image and embed.image.url:
                img_url = embed.image.url
            # Fallback: Extract from Embed Thumbnail
            elif embed.thumbnail and embed.thumbnail.url:
                img_url = embed.thumbnail.url

    # 3. Attachment Scanning (for uploaded images)
    if not img_url and message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                img_url = attachment.url
                if "pokemon" in attachment.filename.lower():
                    is_spawn = True

    # 4. Override: If it's from Pokétwo's CDN, it's ALWAYS a spawn
    if img_url and "cdn.poketwo.net/images/" in img_url:
        is_spawn = True

    return img_url if is_spawn else None

async def update_github_database(wrong, right):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            return False
        data = r.json()
        sha = data['sha']
        content = base64.b64decode(data['content']).decode('utf-8')
        new_line = f'\npokemon_map["{wrong.upper()}"] = "{right}"'
        updated_content = content + new_line
        payload = {
            "message": f"Correction: {wrong} -> {right}",
            "content": base64.b64encode(updated_content.encode('utf-8')).decode('utf-8'),
            "sha": sha
        }
        put_r = requests.put(url, headers=headers, json=payload)
        return put_r.status_code in [200, 201]
    except:
        return False

async def set_spam_lock_github(status):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            return False
        data = r.json()
        sha = data['sha']
        content = base64.b64decode(data['content']).decode('utf-8')
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

async def click_button_by_id(message, target_msg_id, button_identifier):
    """
    Simulate clicking a button in a Discord message.
    button_identifier can be either the button's label or its custom_id.
    """
    try:
        target_msg = await message.channel.fetch_message(int(target_msg_id))
    except Exception as e:
        return f"❌ Could not fetch message: {e}"

    # Find the button
    button = None
    for component in target_msg.components:
        for child in component.children:
            if hasattr(child, 'custom_id'):
                if child.label == button_identifier or child.custom_id == button_identifier:
                    button = child
                    break
        if button:
            break

    if not button:
        return "❌ Button not found. Check the message ID and button label/custom_id."

    # Build interaction payload (standard for self‑bots)
    token = message._state.http.token
    interaction_payload = {
        "type": 2,                               # Message component interaction
        "application_id": str(target_msg.author.id),
        "guild_id": str(message.guild.id) if message.guild else None,
        "channel_id": str(message.channel.id),
        "message_id": str(target_msg_id),
        "session_id": "a" * 32,                  # placeholder, usually works
        "data": {
            "component_type": 2,                 # button
            "custom_id": button.custom_id
        },
        "message_flags": 0,
        "nonce": str(random.randint(10**18, 10**19 - 1))
    }

    if not message.guild:
        interaction_payload.pop("guild_id")

    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post("https://discord.com/api/v9/interactions", json=interaction_payload, headers=headers) as resp:
                if resp.status in (200, 204):
                    return "✅ Button clicked successfully!"
                else:
                    text = await resp.text()
                    return f"❌ API error {resp.status}: {text[:200]}"
        except Exception as e:
            return f"❌ Request failed: {e}"

    # Send the POST request
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post("https://discord.com/api/v9/interactions", json=interaction_payload, headers=headers) as resp:
                if resp.status in (200, 204):
                    return "✅ Button clicked successfully!"
                else:
                    text = await resp.text()
                    return f"❌ API error {resp.status}: {text[:200]}"
        except Exception as e:
            return f"❌ Request failed: {e}"
            
async def get_pokemon_name(image_url):
    url = "https://api.ocr.space/parse/image"
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        for key in OCR_KEYS:
            try:
                payload = {'apikey': key, 'url': image_url, 'language': 'eng', 'isOverlayRequired': False}
                async with session.post(url, data=payload, timeout=6) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('ParsedResults'):
                            raw_text = data['ParsedResults'][0]['ParsedText']
                            name = raw_text.strip().split('\n')[0]
                            clean_name = "".join(c for c in name if c.isalpha())
                            if clean_name:
                                print(f"🔍 OCR Success: {clean_name}")
                                return clean_name
            except:
                continue
    return None

async def catch_action(message, name):
    if not name:
        return
    if name.upper() in pokemon_map:
        name = pokemon_map[name.upper()]
    await asyncio.sleep(random.uniform(2.8, 4.5))
    await message.channel.send(f"<@716390085896962058> c {name}")
    print(f"🎯 Attempted Catch: {name}")

async def spammer_v2(alt_client):
    await alt_client.wait_until_ready()
    from corrections import SPAM_LOCK
    await asyncio.sleep(random.randint(5, 20))
    channel = alt_client.get_channel(SPAM_CHANNEL_ID)
    while not alt_client.is_closed():
        if spam_enabled and not captcha_hit and str(SPAM_LOCK) != "True":
            try:
                await channel.send(random.choice(SPAM_MESSAGES))
                await asyncio.sleep(random.uniform(12.0, 18.0))
            except:
                await asyncio.sleep(20)
        else:
            await asyncio.sleep(5)

# --- MULTI-CLIENT HANDLER ---
def setup_events(alt_client, nickname):
    @alt_client.event
    async def on_ready():
        print(f"✨ [STREAMS ONLINE] {nickname} is fully connected as {alt_client.user}!")
        alt_client.loop.create_task(spammer_v2(alt_client))

    @alt_client.event
    async def on_message(message):
        # Initialize locks
        if not hasattr(alt_client, 'captcha_locked'):
            alt_client.captcha_locked = False
        if not hasattr(alt_client, 'ocr_lock'):
            alt_client.ocr_lock = False
        if not hasattr(alt_client, 'mention_only_mode'):
            alt_client.mention_only_mode = False

        # Block hints in mention mode
        if getattr(alt_client, 'mention_only_mode', False):
            low = message.content.lower()
            if "that is the wrong pokémon" in low or "the pokémon is" in low:
                print(f"🔇 [{nickname}] Hint ignored because mention mode is active.")
                return

        global spam_enabled, manual_awake, ai_enabled, SLEEP_START_HOUR, SLEEP_END_HOUR
    

        is_admin_or_self = message.author.id in ADMIN_IDS or message.author.id == alt_client.user.id
        if message.author.id == alt_client.user.id:
            if not message.content.strip().startswith("."):
                return
        if is_bot_sleeping() and not is_admin_or_self:
            return

        # Admin & self commands
        if message.author.id in ADMIN_IDS or message.author.id == alt_client.user.id:
            content = message.content.strip()
            cmd = content.lower()
            if cmd == ".stop":
                spam_enabled = False
                await set_spam_lock_github("True")
                await message.channel.send(f"🚫 **{nickname} Spammer Stopped.**")
            elif content == ".resume":
                alt_client.captcha_locked = False
                await message.channel.send(f"✅ **{nickname}** restriction cleared! Target unlocked.")
                return
            elif cmd == ".mention":
                if not getattr(alt_client, 'mention_only_mode', False):
                    alt_client.mention_only_mode = True
                    await message.channel.send(f"🔇 **{nickname}** is now in **mention-only mode**.")
                else:
                    await message.channel.send(f"ℹ️ **{nickname}** is already in mention-only mode.")
            elif cmd == ".unmention":
                if getattr(alt_client, 'mention_only_mode', False):
                    alt_client.mention_only_mode = False
                    await message.channel.send(f"🔊 **{nickname}** is now back to **normal mode**.")
                else:
                    await message.channel.send(f"ℹ️ **{nickname}** is already in normal mode.")
            elif content == ".resumeall":
                alt_client.captcha_locked = False
                await message.channel.send(f"🌍 Global Unlock: **{nickname}** resumed.")
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
            
            elif cmd.startswith(".click "):
                parts = content.split()
                if len(parts) != 3:
                    await message.channel.send("❌ Usage: `.click <message_id> <button_label_or_custom_id>`")
                    return
                _, msg_id, button_id = parts
                result = await click_button_by_id(message, msg_id, button_id)
                await message.channel.send(result)

            elif cmd == ".status":
                s = "💤 Sleeping" if is_bot_sleeping() else "🏹 Hunting"
                l = "🔒 LOCKED" if alt_client.captcha_locked else "🔓 Active"
                await message.channel.send(f"📊 [{nickname}] Mode: `{s}` | Captcha: `{l}` | Spammer: `{'On' if spam_enabled else 'Off'}` | AI: `{'✅ ON' if ai_enabled else '❌ OFF'}`")
          
            elif cmd == ".ai":
                ai_enabled = not ai_enabled
                status = "ENABLED" if ai_enabled else "DISABLED"
                await message.channel.send(f"🤖 AI catching has been **{status}** globally.")
                
            
          
            elif cmd.startswith(".add "):
                parts = content.split(" ")
                if len(parts) >= 3:
                    wrong, right = parts[1].upper(), " ".join(parts[2:])
                    pokemon_map[wrong] = right
                    success = await update_github_database(wrong, right)
                    await message.channel.send(f"✅ Correction Added" if success else "⚠️ Sync Failed")

        # CAPTCHA detection – only lock if captcha is for this bot
        if message.author.id == POKETWO_ID:
            low_msg = message.content.lower()
            if "captcha" in low_msg or "verify" in low_msg:
                match = re.search(r'captcha/(\d+)', message.content)
                if match:
                    targeted_user_id = int(match.group(1))
                    if targeted_user_id == alt_client.user.id:
                        alt_client.captcha_locked = True
                        jump_url = message.jump_url
                        print(f"🚨 CAPTCHA for {nickname}! System isolated.", flush=True)
                        for admin_id in ADMIN_IDS:
                            if admin_id == alt_client.user.id:
                                continue
                            try:
                                admin_user = await alt_client.fetch_user(admin_id)
                                await admin_user.send(
                                    f"⚠️ **CAPTCHA ALERT**\n"
                                    f"Bot: `{nickname}`\n"
                                    f"🔗 **Solve here:** {jump_url}\n"
                                    f"Status: **PAUSED**. Type `.resume` to continue."
                                )
                            except:
                                pass
                        return
                    else:
                        print(f"ℹ️ [{nickname}] Ignoring captcha for user {targeted_user_id} (not me).")
                        return
                else:
                    print(f"⚠️ [{nickname}] Could not extract user ID from captcha. Ignoring.")
                    return
                    

            # 1) Extract spawn image (covers all spawn formats)
            img = await extract_spawn_image(message)

            # 2) If AI is enabled and we have an image → use naming bot
            if img and ai_enabled:
                if getattr(alt_client, 'mention_only_mode', False):
                    if not (message.mentions and alt_client.user in message.mentions):
                        print(f"ℹ️ [{nickname}] Mention-only mode active, bot not mentioned. Skipping spawn.")
                        return
                if getattr(alt_client, 'ocr_lock', False):
                    return

                print(f"👁️ [{nickname}] Spawn detected! Processing...", flush=True)
                pokemon_name = await query_private_onnx_api(img)
                if pokemon_name:
                    if pokemon_name.upper() in pokemon_map:
                        pokemon_name = pokemon_map[pokemon_name.upper()]
                    await catch_action(message, pokemon_name)
                else:
                    print(f"⏩ [{nickname}] AI failed. Falling back to hint...")
                    if not getattr(alt_client, 'mention_only_mode', False):
                        await message.channel.send("<@716390085896962058> h")

            # 3) Wrong guess → request hint
            elif "that is the wrong pokémon" in low_msg:
                if not getattr(alt_client, 'mention_only_mode', False):
                    print(f"❌ [{nickname}] Guess was wrong. Forcing Hint...")
                    await asyncio.sleep(1.0)
                    await message.channel.send("<@716390085896962058> h")
                else:
                    print(f"🔇 [{nickname}] Wrong guess, but mention mode active – skipping hint.")

            # 4) Hint received → solve it
            elif "the pokémon is" in low_msg:
                if not getattr(alt_client, 'mention_only_mode', False):
                    solved = solve_hint(message.content.split("is ")[1])
                    if solved:
                        print(f"💡 [{nickname}] Hint Solved: {solved}")
                        await catch_action(message, solved)
                else:
                    print(f"🔇 [{nickname}] Hint received but mention mode active – skipping.")

        # ─── GATEKEEPER ───
        if alt_client.captcha_locked:
            return

        


        # ===== CATCHING LAYERS (only Layer 0 and Layer 1) =====
        # LAYER 0: Assistant bots
        if message.author.id in [854233015475109888, 1459494731775217860, 1307910235737948252]:
            matched = get_best_match(message.content)
            if matched:
                if getattr(alt_client, 'mention_only_mode', False):
                    if not (message.mentions and alt_client.user in message.mentions):
                        print(f"ℹ️ [{nickname}] Mention-only mode active, bot not mentioned. Skipping spawn.")
                        return
                alt_client.ocr_lock = True
                await catch_action(message, matched)
                await asyncio.sleep(10)
                alt_client.ocr_lock = False
                return

        # LAYER 1: PokeName bot OCR
        elif message.author.id == POKENAME_BOT_ID:
            if getattr(alt_client, 'mention_only_mode', False):
                if not (message.mentions and alt_client.user in message.mentions):
                    print(f"ℹ️ [{nickname}] Mention-only mode active, bot not mentioned. Skipping spawn.")
                    return
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
                
                
# --- BOOT LOGIC ---
async def safe_start(client, token, nickname):
    try:
        print(f"📡 [CONNECTING] {nickname}...")
        await asyncio.wait_for(client.start(token.strip()), timeout=30.0)
    except asyncio.TimeoutError:
        print(f"⚠️ [TIMEOUT] {nickname}: Retrying...")
        await asyncio.sleep(5)
        await safe_start(client, token, nickname)
    except discord.errors.LoginFailure:
        print(f"❌ [AUTH] {nickname}: Token is invalid.")
    except Exception as e:
        print(f"🛑 [ERROR] {nickname}: {e}")

async def main_boot():
    keep_alive()
    print("🚀 SYSTEM BOOT: DIRECT CONNECTION MODE", flush=True)
    ACCOUNTS = []
    for i in range(1, 3):
        name = f"TOKEN{i}"
        val = os.getenv(name)
        if val:
            clean_token = str(val).strip()
            if len(clean_token) > 10:
                ACCOUNTS.append({"token": clean_token, "name": f"Alt {i}"})
                print(f"✅ Loaded {name}", flush=True)
        else:
            print(f"⚠️ {name} not found.", flush=True)
    if not ACCOUNTS:
        print("❌ FATAL: No tokens loaded!", flush=True)
        return
    for acc in ACCOUNTS:
        print(f"📡 [HANDSHAKE] Starting {acc['name']}...", flush=True)
        try:
            client = discord.Client(
                self_bot=True,
                browser="chrome",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                compress=False
            )
            setup_events(client, acc['name'])
            asyncio.create_task(client.start(acc['token']))
            print(f"⏳ Waiting 45s stagger for {acc['name']}...", flush=True)
            await asyncio.sleep(45)
        except Exception as e:
            print(f"🛑 Error booting {acc['name']}: {e}", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main_boot())
    except KeyboardInterrupt:
        print("Stopping Aura Farmer...")
    except Exception as e:
        print(f"Fatal System Error: {e}")
