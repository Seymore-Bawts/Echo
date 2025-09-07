import discord
import json
import logging
import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime

# --- Configuration & Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, KeyError):
        logging.critical("FATAL: 'config.json' is missing or malformed.")
        exit()


CONFIG = load_config()
TOKEN = CONFIG['token']
ORACLE_API_URL = CONFIG['oracle_api_url']
DB_FILE = "chronicle.db"


# --- Database Initialization ---
def initialize_database():
    """Creates the database and the logs table if they don't exist."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS logs
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           timestamp
                           TEXT
                           NOT
                           NULL,
                           user
                           TEXT
                           NOT
                           NULL,
                           message
                           TEXT
                           NOT
                           NULL
                       )
                       """)
        conn.commit()
        conn.close()
        logging.info(f"Database '{DB_FILE}' initialized successfully.")
    except Exception as e:
        logging.critical(f"FATAL: Could not initialize database. Error: {e}")
        exit()


# --- Bot Logic ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    """Triggered on bot startup."""
    initialize_database()
    logging.info(f'Success! {client.user} is now online and operational.')


@client.event
async def on_message(message):
    """Event handler for all messages."""
    if message.author == client.user:
        return

    # Route commands to their respective handlers.
    if message.content.startswith('!ping'):
        latency = client.latency * 1000
        await message.channel.send(f'Pong! System latency is {latency:.2f}ms.')
    elif message.content.startswith('!scrape'):
        await handle_scrape_command(message)
    elif message.content.startswith('!time'):
        await handle_time_command(message)
    elif message.content.startswith('!log'):
        await handle_log_command(message)
    elif message.content.startswith('!recall'):
        await handle_recall_command(message)


# --- Command Handlers ---
async def handle_recall_command(message):
    """Retrieves and displays the most recent entries from the Chronicle."""
    try:
        # Default to 5 entries if no number is specified.
        parts = message.content.split()
        limit = 5
        if len(parts) > 1 and parts[1].isdigit():
            limit = int(parts[1])

        limit = min(limit, 20)  # Enforce a maximum limit to prevent spam.

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # SQL query to select the most recent 'limit' entries.
        cursor.execute("SELECT timestamp, user, message FROM logs ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            await message.channel.send("The Chronicle is empty.")
            return

        embed = discord.Embed(
            title="Chronicle Recall",
            description=f"Displaying the last {len(rows)} entries.",
            color=discord.Color.purple()
        )

        # Reverse the rows so they appear in chronological order in the message.
        for row in reversed(rows):
            timestamp, user, log_message = row
            # Format the timestamp for better readability.
            formatted_time = datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')
            embed.add_field(
                name=f"Logged by `{user}` at `{formatted_time}`",
                value=f"```{log_message}```",
                inline=False
            )

        await message.channel.send(embed=embed)

    except Exception as e:
        logging.error(f"Failed to read from Chronicle. Error: {e}")
        await message.channel.send("❌ Error: Could not recall entries from the Chronicle.")


async def handle_log_command(message):
    """Writes a message from a user into the Chronicle database."""
    log_content = message.content[5:].strip()
    if not log_content:
        await message.channel.send("Error: No message provided. Usage: `!log <your message>`")
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (timestamp, user, message) VALUES (?, ?, ?)",
            (datetime.utcnow().isoformat(), str(message.author), log_content)
        )
        conn.commit()
        conn.close()
        logging.info(f"Logged new entry from {message.author}: {log_content}")
        await message.channel.send("✅ Entry recorded in the Chronicle.")
    except Exception as e:
        logging.error(f"Failed to write to Chronicle. Error: {e}")
        await message.channel.send("❌ Error: Could not record entry in the Chronicle.")


# --- Unchanged Handlers ---
async def handle_scrape_command(message):
    # This function remains unchanged.
    parts = message.content.split()
    if len(parts) < 2:
        await message.channel.send("Error: No URL provided. Usage: `!scrape <URL>`")
        return
    url = parts[1]
    try:
        await message.channel.send(f"Beginning reconnaissance on `{url}`...")
        headers = {'User-Agent': 'Seymore-Bawts-Echo-Probe/1.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        page_title = soup.title.string if soup.title else "No Title Found"
        embed = discord.Embed(title="Reconnaissance Report", description=f"Target: `{url}`", color=discord.Color.blue())
        embed.add_field(name="Page Title", value=f"```{page_title}```", inline=False)
        embed.set_footer(text=f"Report generated by Echo for {message.author.name}")
        await message.channel.send(embed=embed)
    except Exception as e:
        await message.channel.send(f"An error occurred during the scrape operation: `{e}`")


async def handle_time_command(message):
    # This function remains unchanged.
    parts = message.content.split()
    if len(parts) < 2:
        await message.channel.send("Error: No timezone provided. Usage: `!time <Timezone>`")
        return
    timezone = parts[1]
    api_endpoint = f"{ORACLE_API_URL}/api/time/{timezone}"
    try:
        await message.channel.send(f"Querying the Oracle for timezone `{timezone}`...")
        response = requests.get(api_endpoint, timeout=10)
        response.raise_for_status()
        data = response.json()
        embed = discord.Embed(title="Oracle Time Service", description=f"Time information for `{data['timezone']}`",
                              color=discord.Color.green())
        embed.add_field(name="Current Date & Time", value=f"`{data['current_datetime']}`", inline=False)
        embed.add_field(name="UTC Timestamp", value=f"`{data['current_timestamp_utc']}`", inline=False)
        embed.set_footer(text=f"Query performed by Echo for {message.author.name}")
        await message.channel.send(embed=embed)
    except Exception as e:
        await message.channel.send(f"An error occurred during the API query: `{e}`")


# --- Execution ---
if __name__ == "__main__":
    try:
        client.run(TOKEN)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")