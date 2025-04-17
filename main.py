import discord
from discord.ext import commands, tasks
import sqlite3
import json
import asyncio

# Load config
with open("config.json") as f:
    config = json.load(f)

TOKEN = config["token"]
PREFIX = config["prefix"]
LEVEL_ROLES = config["level_roles"]
BLACKLISTED_CHANNELS = config["blacklist_channels"]
XP_COOLDOWN = config["cooldown"]

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
db = sqlite3.connect("xp.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS xp (
    user_id INTEGER,
    guild_id INTEGER,
    xp INTEGER,
    level INTEGER,
    last_message REAL
)
""")
db.commit()

def get_xp_for_level(level):
    return 50 * (level ** 2)  # Parabolisches Level-System

async def add_xp(user, guild, channel_id):
    if str(channel_id) in BLACKLISTED_CHANNELS:
        return

    cursor.execute("SELECT xp, level, last_message FROM xp WHERE user_id = ? AND guild_id = ?",
                   (user.id, guild.id))
    row = cursor.fetchone()

    import time
    now = time.time()

    if row:
        xp, level, last_msg = row
        if now - last_msg < XP_COOLDOWN:
            return
        xp += 20
    else:
        xp = 20
        level = 0

    new_level = level
    while xp >= get_xp_for_level(new_level + 1):
        new_level += 1

    cursor.execute("REPLACE INTO xp (user_id, guild_id, xp, level, last_message) VALUES (?, ?, ?, ?, ?)",
                   (user.id, guild.id, xp, new_level, now))
    db.commit()

    if new_level > level:
        await user.send(f"**GG! Du bist jetzt Level {new_level}!**")

        for lvl_str, role_id in LEVEL_ROLES.items():
            if int(lvl_str) == new_level:
                role = guild.get_role(role_id)
                if role:
                    await user.add_roles(role)

@bot.event
async def on_ready():
    print(f"Bot online als {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await add_xp(message.author, message.guild, message.channel.id)
    await bot.process_commands(message)

@bot.command()
async def rank(ctx):
    cursor.execute("SELECT xp, level FROM xp WHERE user_id = ? AND guild_id = ?",
                   (ctx.author.id, ctx.guild.id))
    row = cursor.fetchone()
    if row:
        xp, level = row
        next_lvl_xp = get_xp_for_level(level + 1)
        await ctx.send(f"**{ctx.author.display_name}** – Level: `{level}` | XP: `{xp}/{next_lvl_xp}`")
    else:
        await ctx.send("Du hast noch keine XP gesammelt.")

@bot.command()
async def leaderboard(ctx):
    cursor.execute("SELECT user_id, level FROM xp WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
                   (ctx.guild.id,))
    rows = cursor.fetchall()
    text = "**🏆 Top 10 Rangliste:**\n"
    for i, (user_id, lvl) in enumerate(rows, 1):
        user = ctx.guild.get_member(user_id)
        name = user.display_name if user else "Unbekannt"
        text += f"{i}. {name} – Level {lvl}\n"
    await ctx.send(text)

bot.run(TOKEN)
