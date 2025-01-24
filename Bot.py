import discord
from discord.ext import commands
from discord.ui import Select, View
import json
import os
from collections import Counter

# Bot initialization
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Path to store received files
SAVE_PATH = "received_files"
os.makedirs(SAVE_PATH, exist_ok=True)

# Replacement block options
replacement_options = [
    "BalloonBlock", "BrickBlock", "CommonChestBlock", "ConcreteBlock",
    "EpicChestBlock", "FabricBlock", "GlassBlock", "GoldBlock", "GrassBlock",
    "LegendaryChestBlock", "MarbleBlock", "MetalBlock", "NeonBlock",
    "ObsidianBlock", "PlasticBlock", "RareChestBlock", "RedCandyBlock",
    "SandBlock", "SmoothWoodBlock", "StoneBlock", "TitaniumBlock", "WoodBlock"
]

# Global variables for state management
block_mapping = {}
original_file_content = ""
current_blocks = []

# Function: Replace blocks in JSON content
def replace_block_in_content(content, block_to_change, replacement_block):
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None  # Invalid JSON content

    if isinstance(data, list):
        updated_data = []
        for block in data:
            if block[0] == block_to_change:
                updated_data.append([replacement_block] + block[1:])
            else:
                updated_data.append(block)
        return json.dumps(updated_data)

    elif isinstance(data, dict):
        if block_to_change in data:
            if replacement_block in data:
                data[replacement_block].extend(data.pop(block_to_change))
            else:
                data[replacement_block] = data.pop(block_to_change)
            return json.dumps(data)
        else:
            return None
    return None

# Function: Analyze blocks and return their counts
def analyze_blocks(file_content):
    try:
        data = json.loads(file_content)
        if isinstance(data, list):
            block_counts = Counter([block[0] for block in data])
        elif isinstance(data, dict):
            block_counts = {key: len(value) for key, value in data.items()}
        else:
            return None, "Error: Invalid data format."
        return data, block_counts
    except json.JSONDecodeError:
        return None, "Error: The file is not a valid JSON."

# Custom Select: Block selector
class BlockSelect(Select):
    def __init__(self, blocks_with_counts, user_id):
        options = [
            discord.SelectOption(label=f"{block} - {count}", value=block)
            for block, count in blocks_with_counts.items()
        ]
        super().__init__(placeholder="Choose a block to replace", min_values=1, max_values=1, options=options)
        self.user_id = user_id
        self.blocks_with_counts = blocks_with_counts

    async def callback(self, interaction: discord.Interaction):
        block_to_change = self.values[0]
        view = ReplacementView(block_to_change, self.user_id)
        embed = discord.Embed(
            title=f"Select Replacement for `{block_to_change}`",
            description="Choose a block from the dropdown below.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)

# Custom Select: Replacement selector
class ReplacementSelect(Select):
    def __init__(self, block_to_change, user_id):
        options = [
            discord.SelectOption(label=option, value=option)
            for option in replacement_options
        ]
        super().__init__(placeholder=f"Select a replacement for {block_to_change}", min_values=1, max_values=1, options=options)
        self.block_to_change = block_to_change
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        replacement_block = self.values[0]
        block_mapping[self.block_to_change] = replacement_block

        # Update the change log with all block changes
        change_log_msg = "**Change Logs:**\n"
        for block, replacement in block_mapping.items():
            change_log_msg += f"- `{block}` ➡️ `{replacement}`\n"

        embed = discord.Embed(
            title="Change Logs",
            description=f"{change_log_msg}\n\nSelect an action below:",
            color=discord.Color.green()
        )
        view = ChangeLogView()
        await interaction.response.edit_message(embed=embed, view=view)

# Replacement view for updating blocks
class ReplacementView(View):
    def __init__(self, block, user_id):
        super().__init__(timeout=None)
        self.add_item(ReplacementSelect(block, user_id))

# View: Change log with "Modify More Blocks", "Confirm", "Cancel"
class ChangeLogView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="✅ Confirm Changes", style=discord.ButtonStyle.green, custom_id="confirm_changes"))
        self.add_item(discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.red, custom_id="cancel_changes"))
        self.add_item(discord.ui.Button(label="🔄 Modify More Blocks", style=discord.ButtonStyle.primary, custom_id="modify_blocks"))

# Main view for initial choice
class BlockChangeOptionView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="🔄 Block Changer", style=discord.ButtonStyle.primary, custom_id="block_changer"))
        self.add_item(discord.ui.Button(label="📊 Block Counter", style=discord.ButtonStyle.secondary, custom_id="block_counter"))

# Event: Bot ready
@bot.event
async def on_ready():
    print(f"Bot {bot.user.name} is online!")

# Event: On message (handle file uploads)
@bot.event
async def on_message(message):
    global original_file_content, current_blocks

    if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith('.build'):
                    file_path = os.path.join(SAVE_PATH, attachment.filename)
                    await attachment.save(file_path)

                    with open(file_path, 'r', encoding='utf-8') as file:
                        original_file_content = file.read()

                    data, block_counts = analyze_blocks(original_file_content)
                    if data is None:
                        await message.channel.send(block_counts)
                        return

                    current_blocks = list(block_counts.keys())
                    view = BlockChangeOptionView()
                    await message.channel.send("Choose an option below:", view=view)
        else:
            await message.channel.send("Please send a `.build` file for analysis.")

# Event: Handle interaction (buttons and dropdowns)
@bot.event
async def on_interaction(interaction: discord.Interaction):
    global block_mapping, original_file_content, current_blocks

    if interaction.data["custom_id"] == "block_changer":
        data, block_counts = analyze_blocks(original_file_content)
        if data is None:
            await interaction.response.send_message(block_counts)
            return

        embed = discord.Embed(
            title="Choose a Block to Replace",
            description="Select a block from the dropdown below.",
            color=discord.Color.blue()
        )
        view = View()
        view.add_item(BlockSelect(dict(block_counts), interaction.user.id))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    elif interaction.data["custom_id"] == "block_counter":
        data, block_counts = analyze_blocks(original_file_content)
        result = "**Block Counts**\n```diff\n"
        for block, count in block_counts.items():
            result += f"+ {block}: {count}\n"
        result += "```"
        await interaction.response.send_message(result, ephemeral=True)

    elif interaction.data["custom_id"] == "modify_blocks":
        data, block_counts = analyze_blocks(original_file_content)
        embed = discord.Embed(
            title="Choose a Block to Replace",
            description="Select another block to modify.",
            color=discord.Color.blue()
        )
        view = View()
        view.add_item(BlockSelect(dict(block_counts), interaction.user.id))
        await interaction.response.edit_message(embed=embed, view=view)

    elif interaction.data["custom_id"] == "confirm_changes":
        updated_content = original_file_content
        for block_to_change, replacement_block in block_mapping.items():
            updated_content = replace_block_in_content(updated_content, block_to_change, replacement_block)
            if updated_content is None:
                await interaction.response.send_message("Error: Invalid file format.", ephemeral=True)
                return

        updated_file_path = os.path.join(SAVE_PATH, "updated_file.build")
        with open(updated_file_path, 'w', encoding='utf-8') as updated_file:
            updated_file.write(updated_content)

        with open(updated_file_path, 'rb') as file:
            await interaction.response.send_message(
                "✅ Changes applied successfully! Here's the updated file:",
                file=discord.File(file, os.path.basename(updated_file_path)),
                ephemeral=True
            )

        block_mapping.clear()
        original_file_content = ""

    elif interaction.data["custom_id"] == "cancel_changes":
        block_mapping.clear()
        original_file_content = ""
        await interaction.response.send_message("❌ Changes have been canceled.", ephemeral=True)

# Run the bot
bot.run('MTMxNDYzMDk2MTcxOTI3OTY5Ng.Gfpz0u.a2kZ8PcySD5i-VlR2j7aXBrOxXoC19jJTL5DtE')
