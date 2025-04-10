import discord
import random
import asyncio
from dotenv import load_dotenv
import os
import re
import json
from discord import app_commands
from discord.ext import commands

# File to store the channel ID
CONFIG_FILE = "config.json"

# Load the channel ID from the file
def load_channel_id():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            data = json.load(file)
            return data.get("channel_id")
    return None

# Save the channel ID to the file
def save_channel_id(channel_id):
    with open(CONFIG_FILE, "w") as file:
        json.dump({"channel_id": channel_id}, file, indent=4)

# Load the initial channel ID
TARGET_CHANNEL_ID = load_channel_id()

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Store the background task globally
daily_message_task = None

@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Error syncing commands: {e}")

def trim_between_quotes(line):
    match = re.search(r'"(.*?)"', line)
    if match:
        return match.group(1)
    return line

def get_after_last(text, char):
    try:
        return text[text.rfind(char) + 1:]
    except ValueError:
        return ""

async def fetch_random_message(channel: discord.TextChannel) -> discord.Message:
    """
    Fetch a random message from the given channel.
    Returns None if no valid messages are found.
    """
    messages = [message async for message in channel.history(limit=1000) if not message.author.bot]
    if not messages:
        return None
    response = random.choice(messages)
    quote = trim_between_quotes(response.content)
    quoter = response.author.display_name
    quotee = get_after_last(response.content, "-")
    if not quotee:
        quotee = "Unknown"
    result = f"Submitted by **{quoter}**:\n \"{quote}\" - **{quotee}**"
    response.content = result
    return response

@bot.tree.command(name="random_message", description="Get a random message from a specific channel")
async def random_message(interaction: discord.Interaction):
    channel = bot.get_channel(TARGET_CHANNEL_ID)

    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("Invalid channel.", ephemeral=True)
        return

    await interaction.response.defer()  # Give bot time to fetch

    random_msg = await fetch_random_message(channel)
    if not random_msg:
        await interaction.followup.send("No messages found in that channel.")
        return

    await interaction.followup.send(f"**Random message from {channel.mention}:**\n{random_msg.content}")

@bot.tree.command(name="schedule_daily_message", description="Schedule a random message to be sent daily")
async def schedule_daily_message(interaction: discord.Interaction):
    global daily_message_task
    channel = bot.get_channel(TARGET_CHANNEL_ID)

    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("Invalid channel.", ephemeral=True)
        return

    if daily_message_task and not daily_message_task.done():
        await interaction.response.send_message("Daily message scheduling is already running.", ephemeral=True)
        return

    async def send_random_message():
        while True:
            await asyncio.sleep(24 * 60 * 60)  # Wait for 24 hours
            random_msg = await fetch_random_message(channel)
            if random_msg:
                await channel.send(f"**Daily random message:**\n{random_msg.content}")

    # Start the background task
    daily_message_task = bot.loop.create_task(send_random_message())
    await interaction.response.send_message("Daily random message scheduling started!", ephemeral=True)

@bot.tree.command(name="stop_daily_message", description="Stop the daily random message")
async def stop_daily_message(interaction: discord.Interaction):
    global daily_message_task

    if daily_message_task and not daily_message_task.done():
        daily_message_task.cancel()
        daily_message_task = None
        await interaction.response.send_message("Daily random message scheduling stopped.", ephemeral=True)
    else:
        await interaction.response.send_message("No daily message scheduling is currently running.", ephemeral=True)

@bot.tree.command(name="ping", description="Check the bot's latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)  # Convert to milliseconds
    await interaction.response.send_message(f"Pong! Latency is {latency}ms.", ephemeral=True)

@bot.tree.command(name="userinfo", description="Get information about a user")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user  # Default to the user who invoked the command
    embed = discord.Embed(title=f"User Info - {member}", color=discord.Color.blue())
    embed.add_field(name="ID", value=member.id, inline=False)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.set_thumbnail(url=member.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Get information about the server")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"Server Info - {guild.name}", color=discord.Color.green())
    embed.add_field(name="Server ID", value=guild.id, inline=False)
    embed.add_field(name="Owner", value=guild.owner, inline=False)
    embed.add_field(name="Member Count", value=guild.member_count, inline=False)
    embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="roll", description="Roll a dice")
async def roll(interaction: discord.Interaction, sides: int = 6):
    if sides < 1:
        await interaction.response.send_message("The number of sides must be at least 1.", ephemeral=True)
        return
    result = random.randint(1, sides)
    await interaction.response.send_message(f"🎲 You rolled a {result} on a {sides}-sided dice!")

@bot.tree.command(name="clear", description="Clear a number of messages from the channel")
@commands.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int = 10):
    if amount < 1:
        await interaction.response.send_message("You must delete at least 1 message.", ephemeral=True)
        return
    channel = interaction.channel
    if isinstance(channel, discord.TextChannel):
        deleted = await channel.purge(limit=amount)
        await interaction.response.send_message(f"Deleted {len(deleted)} messages.", ephemeral=True)
    else:
        await interaction.response.send_message("This command can only be used in text channels.", ephemeral=True)

@bot.tree.command(name="help", description="List all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Help - Available Commands", color=discord.Color.gold())
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    embed.set_footer(text="Use /<command> to execute a command.")

    # Dynamically add all commands to the embed
    for command in bot.tree.get_commands():
        embed.add_field(name=f"/{command.name}", value=command.description, inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_target_channel", description="Set the target channel for random messages")
@app_commands.checks.has_permissions(administrator=True)
async def set_target_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    global TARGET_CHANNEL_ID

    # Update the global target channel ID and save it to the file
    TARGET_CHANNEL_ID = channel.id
    save_channel_id(TARGET_CHANNEL_ID)
    await interaction.response.send_message(f"Target channel has been set to {channel.mention}.", ephemeral=True)

# Error handler for permission checks
@set_target_channel.error
async def set_target_channel_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)

# Run the bot
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("No token found. Please set the DISCORD_TOKEN environment variable.")
bot.run(TOKEN)