import discord
import random
import os
import asyncio
from datetime import datetime
from flask import Flask
import threading
import aiohttp
import json
import base64
from random import randint

# --- CONFIG ---
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
COOLDOWN_SECONDS = 2

# GitHub config
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
STATS_PATH = "stats.json"
TOP_1000_PATH = "top_1000.json"
ROLL_CHANNELS_PATH = "roll_channels.json"
GITHUB_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# --- GLOBALS ---
cooldowns = {}
file_lock = asyncio.Lock()
bot_id = randint(1,16777216)

# --- FLASK KEEP-ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "RNG GOOF bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.start()

# --- RARITIES & MODIFIERS ---
rarities = {
    "Malicious": (67108864, "<:malicious:1425109134793244673>"),
    "Immeasurable": (33554432, "<:immeasurable:1425109138329047282>"),
    "Aleph-Null": (16777216, "<:alephnull:1425110355511742565>"),
    "Omega": (8388608, "<:omega:1425109141264793692>"),
    "Unimaginable": (4194304, "<:unimaginable:1425109144494673981>"),
    "TARTARUS": (2097152, "<:tartarus:1425109147111919636>"),
    "HELL": (1048576, "<:hell:1425109149724966932>"),
    "DEATH": (524288, "<:death:1425109153294057615>"),
    "No": (262144, "<:no:1425109156096114738>"),
    "WHY": (131072, "<:why:1425109160114262036>"),
    "Literal": (65536, "<:literal:1425109162664263850>"),
    "eRRoR": (32768, "<:error:1416246007506665552>"),
    "nil": (16384, "<:nil:1399358997990998038>"),
    "Unreal": (8192, "<:unreal:1399359000922816542>"),
    "Horrific": (4096, "<:horrific:1399359003309637662>"),
    "Catastrophic": (2048, "<:catastrophic:1399359005679419492>"),
    "Terrifying": (1024, "<:terrifying:1399359007352684596>"),
    "Extreme": (512, "<:extreme:1399359009965998220>"),
    "Insane": (256, "<:insane:1399359012490842172>"),
    "Remorseless": (128, "<:remorseless:1399359014587990110>"),
    "Intense": (64, "<:intense:1399359016613707777>"),
    "Challenging": (32, "<:challenging:1399359019172237343>"),
    "Difficult": (16, "<:difficult:1399359021114462211>"),
    "Hard": (8, "<:hard:1399359024050212895>"),
    "Medium": (4, "<:medium:1399359026558664744>"),
    "Easy": (2, "<:easy:1399359028701692005>")
}

modifiers = {
    "Normal": (1, ""),
    "Lucky": (4, "🍀"),
    "Hot": (8, "🔥"),
    "Rainy": (16, "🌧️"),
    "Mechanical": (20, "⚙️"),
    "Cold": (25, "❄️"),
    "Metallic": (48, "🔩"),
    "Super": (64, "⭐"),
    "Lunar": (96, "🌙"),
    "Shiny": (100, "✨"),
    "Frostbited": (128, "🧊"),
    "Scorching": (160, "🌶️"),
    "Mystery": (200, "❓"),
    "Celestial": (256, "🌌"),
    "Unusurpable": (512, "👑"),
    "GODLIKE": (1000, "⚡"),
    "Otherworldly": (2500, "🌀")
}

# --- GITHUB STATS FUNCTIONS ---
async def load_stats():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATS_PATH}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=GITHUB_HEADERS) as resp:
            text = await resp.text()
            try:
                data = json.loads(text)
            except Exception as e:
                return {"total_rolls": 0, "leaderboard": []}
            if "message" in data and "content" not in data:
                return {"total_rolls": 0, "leaderboard": []}
            content = base64.b64decode(data["content"]).decode()
            stats = json.loads(content)
            stats.setdefault("total_rolls", 0)
            stats.setdefault("leaderboard", [])
            stats["_sha"] = data.get("sha", None)
            return stats

async def save_stats(stats, retry=1):
    sha = stats.pop('_sha', None)
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATS_PATH}"
    payload = {
        "message": f"Update stats - total rolls {stats['total_rolls']}",
        "content": base64.b64encode(json.dumps(stats, indent=2).encode()).decode()
    }
    if sha:
        payload["sha"] = sha
    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=GITHUB_HEADERS, json=payload) as resp:
            text = await resp.text()
            status = resp.status
            if status in (200, 201):
                data = json.loads(text)
                stats["_sha"] = data["content"]["sha"]
                return True
            if status == 422 and retry > 0:
                new_stats = await load_stats()
                new_stats.update({
                    "total_rolls": stats["total_rolls"],
                    "leaderboard": stats["leaderboard"]
                })
                return await save_stats(new_stats, retry - 1)
            return False

# --- GITHUB ROLL CHANNELS FUNCTIONS ---
async def load_roll_channels():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{ROLL_CHANNELS_PATH}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=GITHUB_HEADERS) as resp:
            text = await resp.text()
            try:
                data = json.loads(text)
            except Exception:
                return {}
            # if GitHub error
            if "message" in data and "content" not in data:
                return {}
            content = base64.b64decode(data["content"]).decode()
            roll_channels = json.loads(content)
            roll_channels["_sha"] = data.get("sha", None)
            return roll_channels

async def save_roll_channels(roll_channels, retry=1):
    sha = roll_channels.pop('_sha', None)
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{ROLL_CHANNELS_PATH}"
    payload = {
        "message": "Update roll_channels mapping",
        "content": base64.b64encode(json.dumps(roll_channels, indent=2).encode()).decode()
    }
    if sha:
        payload["sha"] = sha
    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=GITHUB_HEADERS, json=payload) as resp:
            text = await resp.text()
            status = resp.status
            if status in (200, 201):
                data = json.loads(text)
                roll_channels["_sha"] = data["content"]["sha"]
                return True
            if status == 422 and retry > 0:
                new_channels = await load_roll_channels()
                new_channels.update(roll_channels)
                return await save_roll_channels(new_channels, retry - 1)
            return False

async def load_top_1000():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{TOP_1000_PATH}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=GITHUB_HEADERS) as resp:
            text = await resp.text()
            try:
                data = json.loads(text)
            except Exception:
                return {}
            if "message" in data and "content" not in data:
                return {}
            content = base64.b64decode(data["content"]).decode()
            top_1000 = json.loads(content)
            top_1000["_sha"] = data.get("sha", None)
            return top_1000

# --- HELPER FUNCTIONS FOR TOP_1000 LEADERBOARD ---

async def save_top_1000(top_1000, retry=1):
    sha = top_1000.pop('_sha', None)
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{TOP_1000_PATH}"
    payload = {
        "message": "Update top_1000 leaderboard",
        "content": base64.b64encode(json.dumps(top_1000, indent=2).encode()).decode()
    }
    if sha:
        payload["sha"] = sha
    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=GITHUB_HEADERS, json=payload) as resp:
            text = await resp.text()
            status = resp.status
            if status in (200, 201):
                data = json.loads(text)
                top_1000["_sha"] = data["content"]["sha"]
                return True
            if status == 422 and retry > 0:
                new_top = await load_top_1000()
                new_top.update(top_1000)
                return await save_top_1000(new_top, retry - 1)
            return False

def update_top_1000_leaderboard(top_1000, roll_data):
    if roll_data['rarity'] < 1000:
        return
    leaderboard = top_1000.get('leaderboard', [])
    leaderboard.append(roll_data)
    leaderboard.sort(key=lambda x: x['rarity'], reverse=True)
    top_1000['leaderboard'] = leaderboard[:10]
    return leaderboard[:10]
    
# --- LEADERBOARD HELPERS ---
def update_leaderboard(stats, roll_data):
    leaderboard = stats.get('leaderboard', [])
    leaderboard.append(roll_data)
    leaderboard.sort(key=lambda x: x['rarity'], reverse=True)
    rank = None
    for i, roll in enumerate(leaderboard[:10], 1):
        if roll == roll_data:
            rank = i
            break
    stats['leaderboard'] = leaderboard[:10]
    return rank

# --- ITEM ROLL ---
def roll_item_once():
    roll_value = random.random()
    selected_rarity = None
    selected_chance = None
    sorted_rarities = sorted(rarities.items(), key=lambda x: x[1][0], reverse=True)
    for name, (val, emoji) in sorted_rarities:
        chance = 1 / val
        if roll_value < chance:
            selected_rarity = name
            selected_chance = val
            break
    if selected_rarity is None:
        selected_rarity, selected_chance = "Easy", rarities["Easy"][0]

    active_mods = []
    for mod_name, (val, emoji) in modifiers.items():
        if mod_name == "Normal":
            continue
        if random.random() < (1 / val):
            active_mods.append(mod_name)

    total_multiplier = 1
    for mod in active_mods:
        total_multiplier *= modifiers[mod][0]

    total_rarity = selected_chance * total_multiplier
    emojis = [modifiers[m][1] for m in sorted(active_mods, key=lambda m: modifiers[m][0])]
    emojis.append(rarities[selected_rarity][1])
    emoji_string = " ".join(e for e in emojis if e)
    text_parts = active_mods + [selected_rarity]
    text_string = " ".join(text_parts)
    display_name = f"{emoji_string} {text_string}".strip()
    return display_name, total_rarity

# --- DISCORD BOT ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    content = message.content.strip()

    if not content.startswith("!rng.goof"):
        return

    guild_id = message.guild.id if message.guild else None

    # --- HELP COMMAND ---
    if content == "!rng.goof help":
        help_text = (
            "**RNG GOOF Bot Commands:**\n"
            "`!rng.goof setup` - Set this channel as the roll channel.\n"
            "`!rng.goof leaderboard top` - Show the top 10 all-time rolls.\n"
            "`!rng.goof leaderboard 1000` - Show top 10 rolls with rarity ≥ 1,000.\n"
            "`!rng.goof debug` - Show bot ID.\n"
            "`!rng.goof` or `!rng.goof <anything>` - Roll an item (except the above exceptions).\n"
            "`!rng.goof help` - Show this message."
        )
        await message.channel.send(help_text)
        return

    # --- SETUP COMMAND ---
    if content == "!rng.goof setup":
        if not guild_id:
            await message.channel.send("You can only use this command in a server.")
            return
        async with file_lock:
            roll_channels = await load_roll_channels()
            roll_channels[str(guild_id)] = message.channel.id
            ok = await save_roll_channels(roll_channels)
            if ok:
                await message.channel.send(f"This channel ({message.channel.mention}) is now the roll channel!")   
            else:
                await message.channel.send("Failed to save roll channel to GitHub.")
        return

    # --- DEBUG COMMAND ---
    if content == "!rng.goof debug":
        await message.channel.send(str(bot_id))
        return

    # --- LEADERBOARD COMMAND ---
    if content.startswith("!rng.goof leaderboard"):
        async with file_lock:
            if content.endswith("top"):
                stats = await load_stats()
                leaderboard = stats.get('leaderboard', [])
                if not leaderboard:
                    await message.channel.send('??? no rolls 😔')
                    return
            elif content.endswith("1000"):
                top_1000 = await load_top_1000()
                leaderboard = top_1000.get('leaderboard', [])
                if not leaderboard:
                    await message.channel.send('No rolls with rarity >= 1,000 yet 😔')
                    return
            else:
                await message.channel.send("Unknown leaderboard type. Use `top` or `1000`.")
                return

        # Build leaderboard message
        header = "**RNG GOOF LEADERBOARD:**\n"
        footer = ""
        if content.endswith("top"):
            footer = f"\nTotal Rolls: {stats.get('total_rolls', 0):,}"
        max_chars = 2000
        lines = []
        for i, roll in enumerate(leaderboard[:10], 1):
            timestamp = int(roll['timestamp'])
            roll_name = roll['name']
            roll_rarity = int(roll['rarity'])
            display_name = f"**{roll_name.upper()}**" if roll_rarity >= 1000 else roll_name
            line = (
                f"#{i} - {display_name} (1 in {roll_rarity:,})\n"
                f"Rolled by {roll['user']} at <t:{timestamp}> in {roll['server']} / All-Time Roll #{roll['roll_number']:,}"
            )
            if len(line) > 1000:
                line = line[:997] + "…"
            lines.append(line)

        chunks = []
        current_chunk = header
        for line in lines:
            if len(current_chunk) + len(line) + 2 > max_chars:
                chunks.append(current_chunk.rstrip())
                current_chunk = ""
            current_chunk += line + "\n\n"
        if current_chunk:
            current_chunk = current_chunk.rstrip() + footer
            chunks.append(current_chunk)

        for chunk in chunks:
            await message.channel.send(chunk)
        return

    # --- NORMAL ROLL ---
    if not guild_id:
        await message.channel.send("You can only roll in a server.")
        return
    async with file_lock:
        roll_channels = await load_roll_channels()
    if str(guild_id) not in roll_channels:
        await message.channel.send("No channel set for rolls in this server. Use `!rng.goof setup` first.")
        return
    roll_channel_id = roll_channels[str(guild_id)]
    if message.channel.id != roll_channel_id:
        return

    # --- COOLDOWN ---
    now = asyncio.get_running_loop().time()
    last_roll = cooldowns.get(message.author.id)
    if last_roll and now - last_roll < COOLDOWN_SECONDS:
        await message.channel.send(f"nrn bozo {message.author.mention}")
        return
    cooldowns[message.author.id] = now

    # --- ROLL ITEM ---
    name, rarity = roll_item_once()
    async with file_lock:
        stats = await load_stats()
        stats['total_rolls'] += 1
        roll_number = stats['total_rolls']
        timestamp_unix = int(datetime.utcnow().timestamp())
        roll_data = {
            'name': name,
            'rarity': rarity,
            'user': str(message.author),
            'user_id': message.author.id,
            'server': message.guild.name if message.guild else 'DM',
            'timestamp': timestamp_unix,
            'roll_number': roll_number
        }
        rank = update_leaderboard(stats, roll_data)
        await save_stats(stats)

        # Update top 1000 leaderboard if applicable
        if rarity >= 1000:
            top_1000 = await load_top_1000()
            update_top_1000_leaderboard(top_1000, roll_data)
            await save_top_1000(top_1000)

    display_name = f"**{name.upper()}**" if rarity >= 1000 else name
    response = f'-# RNG GOOF / <@{message.author.id}> / All-Time Roll #{roll_number:,}\n{display_name} (1 in {rarity:,})'
    if rank:
        response += f'\n**This roll is good for #{rank} on the RNG GOOF leaderboard!**'
    leaderboard = stats.get('leaderboard', [])
    if rank and len(leaderboard) >= 10:
        tenth_roll = leaderboard[-1]
        rip_msg = f"rip {tenth_roll['name']} (1 in {int(tenth_roll['rarity']):,})"
        response += f"\n{rip_msg}"
    await message.channel.send(response)
# --- RUN BOT ---
if not DISCORD_TOKEN:
    exit(1)

if __name__ == "__main__":
    keep_alive()
    client.run(DISCORD_TOKEN)







