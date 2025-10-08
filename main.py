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

# --- CONFIG ---
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
COOLDOWN_SECONDS = 2

# GitHub config
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # e.g., "username/rng-goof-stats"
STATS_PATH = "stats.json"
GITHUB_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# --- GLOBALS ---
cooldowns = {}
file_lock = asyncio.Lock()

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
            print(f"GitHub status: {resp.status}")  # Add this
            if resp.status == 200:
                data = await resp.json()
                content = base64.b64decode(data['content']).decode()
                stats = json.loads(content)
                stats.setdefault('total_rolls', 0)
                stats.setdefault('leaderboard', [])
                stats['_sha'] = data['sha']  # needed for updating
                return stats
            else:
                text = await resp.text()
                print(f"Failed to load stats from GitHub: {resp.status} - {text}")
                return {"total_rolls": 0, "leaderboard": []}
    

async def save_stats(stats):
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
            text = await resp.text()  # Always read as text first

            if resp.status in (200, 201):
                try:
                    response = json.loads(text)
                    stats['_sha'] = response['content']['sha']
                    print("✅ Stats saved successfully.")
                except Exception as e:
                    print(f"⚠️ Could not parse GitHub response: {e}\nResponse text:\n{text}")
            else:
                print(f"❌ Failed to save stats to GitHub ({resp.status}): {text}")

                # Handle SHA mismatch (422)
                if resp.status == 422 and sha:
                    print("⚙️ Retrying save without SHA...")
                    payload.pop("sha", None)
                    async with session.put(url, headers=GITHUB_HEADERS, json=payload) as retry:
                        retry_text = await retry.text()
                        if retry.status in (200, 201):
                            response = json.loads(retry_text)
                            stats['_sha'] = response['content']['sha']
                            print("✅ Retry succeeded.")
                        else:
                            print(f"❌ Retry failed ({retry.status}): {retry_text}")

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
    if not message.content.startswith("!rng.goof"):
        return

    now = asyncio.get_event_loop().time()
    last_roll = cooldowns.get(message.author.id)
    if last_roll and now - last_roll < COOLDOWN_SECONDS:
        await message.channel.send(f"nrn bozo {message.author.mention}")
        return
    cooldowns[message.author.id] = now

    # Leaderboard command
    if message.content.strip() == "!rng.goof leaderboard":
        async with file_lock:
            stats = await load_stats()
        leaderboard = stats.get('leaderboard', [])
        if not leaderboard:
            await message.channel.send('??? no rolls 😔')
            return

        embed = discord.Embed(title='**RNG GOOF LEADERBOARD:**', color=0xFFD700)
        for i, roll in enumerate(leaderboard, 1):
            timestamp = roll['timestamp']
            roll_name = roll['name']
            roll_rarity = roll['rarity']
            display_name = f"**{roll_name.upper()}**" if roll_rarity >= 1000 else roll_name
            field_value = f"Rolled by {roll['user']} at <t:{timestamp}> in {roll['server']} / All-Time Roll #{roll['roll_number']:,}"
            embed.add_field(name=f"#{i} - {display_name} (1 in {roll_rarity:,})", value=field_value, inline=False)
        embed.set_footer(text=f"Total Rolls: {stats.get('total_rolls', 0):,}")
        await message.channel.send(embed=embed)
        return

    # Normal roll
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

    display_name = f"**{name.upper()}**" if rarity >= 1000 else name
    response = f'-# RNG GOOF / <@{message.author.id}> / All-Time Roll #{roll_number:,}\n{display_name} (1 in {rarity:,})'
    if rank:
        response += f'\n**This roll is good for #{rank} on the RNG GOOF leaderboard!**'
    await message.channel.send(response)

# --- RUN BOT ---
if not DISCORD_TOKEN:
    print('Error: DISCORD_BOT_TOKEN not found in environment variables')
    exit(1)

if __name__ == "__main__":
    keep_alive()
    client.run(DISCORD_TOKEN)



