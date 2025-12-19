"""
Discord bot for Wonders Market stats and reports.

Slash Commands:
  /stats daily   - Get daily market stats
  /stats weekly  - Get weekly market stats
  /report daily  - Generate and upload daily CSV report
  /report weekly - Generate and upload weekly CSV report

Scheduled Reports:
  - Daily report at 9 AM UTC
  - Weekly report on Monday at 9 AM UTC
"""

import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, time, timezone
from typing import Literal
from dotenv import load_dotenv

load_dotenv()

from app.discord_bot.stats import calculate_market_stats, generate_csv_report, format_stats_embed
from app.discord_bot.storage import upload_csv


# Bot configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
REPORT_CHANNEL_ID = int(os.getenv("DISCORD_REPORT_CHANNEL_ID", "0"))
ADMIN_USER_IDS = [int(x) for x in os.getenv("DISCORD_ADMIN_IDS", "").split(",") if x.strip()]


class WondersBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Start scheduled tasks
        if REPORT_CHANNEL_ID:
            self.daily_report_task.start()
            self.weekly_report_task.start()

        # Sync slash commands
        await self.tree.sync()
        print("Synced slash commands")

    async def on_ready(self):
        print(f"Wonders Bot logged in as {self.user}")
        print(f"Report channel: {REPORT_CHANNEL_ID}")
        print(f"Admin users: {ADMIN_USER_IDS}")


bot = WondersBot()


# ===== Slash Commands =====


@bot.tree.command(name="stats", description="Get market statistics")
@app_commands.describe(period="Time period for stats")
async def stats_command(interaction: discord.Interaction, period: Literal["daily", "weekly", "monthly"] = "daily"):
    """Get market statistics for a given period."""
    await interaction.response.defer(thinking=True)

    try:
        stats = calculate_market_stats(period)
        embed_data = format_stats_embed(stats)

        embed = discord.Embed(
            title=embed_data["title"],
            description=embed_data["description"],
            color=embed_data["color"],
            timestamp=datetime.fromisoformat(embed_data["timestamp"]),
        )

        for field in embed_data["fields"]:
            embed.add_field(name=field["name"], value=field["value"], inline=field.get("inline", False))

        embed.set_footer(text=embed_data["footer"]["text"])

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Error generating stats: {str(e)}", ephemeral=True)


@bot.tree.command(name="report", description="Generate and download a CSV market report")
@app_commands.describe(period="Time period for report")
async def report_command(interaction: discord.Interaction, period: Literal["daily", "weekly", "monthly"] = "daily"):
    """Generate a CSV report and upload to blob storage."""
    await interaction.response.defer(thinking=True)

    try:
        # Generate CSV
        filename, csv_content = generate_csv_report(period)

        # Try to upload to Vercel Blob storage
        try:
            download_url = upload_csv(filename, csv_content)

            embed = discord.Embed(
                title="Market Report Generated",
                description=f"**{period.capitalize()}** report is ready for download.",
                color=0x10B981,
            )
            embed.add_field(name="Filename", value=filename, inline=False)
            embed.add_field(name="Size", value=f"{len(csv_content):,} bytes", inline=True)
            embed.add_field(name="Period", value=period.capitalize(), inline=True)

            # Add download button
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Download CSV", url=download_url, style=discord.ButtonStyle.link))

            await interaction.followup.send(embed=embed, view=view)

        except Exception as storage_error:
            # Fallback: Send as Discord attachment
            print(f"Storage upload failed, sending as attachment: {storage_error}")

            file = discord.File(fp=__import__("io").BytesIO(csv_content), filename=filename)

            embed = discord.Embed(
                title="Market Report Generated",
                description=f"**{period.capitalize()}** report attached below.\n*(Cloud storage unavailable)*",
                color=0xFCD34D,  # Warning yellow
            )

            await interaction.followup.send(embed=embed, file=file)

    except Exception as e:
        await interaction.followup.send(f"Error generating report: {str(e)}", ephemeral=True)


@bot.tree.command(name="price", description="Get current price for a card")
@app_commands.describe(card_name="Name of the card to look up")
async def price_command(interaction: discord.Interaction, card_name: str):
    """Look up current price for a specific card."""
    await interaction.response.defer(thinking=True)

    try:
        from sqlmodel import Session, select, desc
        from app.db import engine
        from app.models.card import Card, Rarity
        from app.models.market import MarketSnapshot, MarketPrice

        with Session(engine) as session:
            # Find card (case-insensitive search)
            card = session.exec(select(Card).where(Card.name.ilike(f"%{card_name}%"))).first()

            if not card:
                await interaction.followup.send(f"Card '{card_name}' not found.", ephemeral=True)
                return

            # Get latest snapshot
            snapshot = session.exec(
                select(MarketSnapshot)
                .where(MarketSnapshot.card_id == card.id)
                .order_by(desc(MarketSnapshot.timestamp))
                .limit(1)
            ).first()

            # Get last sale
            last_sale = session.exec(
                select(MarketPrice)
                .where(MarketPrice.card_id == card.id)
                .where(MarketPrice.listing_type == "sold")
                .order_by(desc(MarketPrice.sold_date))
                .limit(1)
            ).first()

            # Get rarity
            rarity = session.get(Rarity, card.rarity_id) if card.rarity_id else None

            embed = discord.Embed(
                title=card.name,
                description=f"{card.set_name} - {rarity.name if rarity else 'Unknown Rarity'}",
                color=0x10B981,
            )

            if snapshot:
                embed.add_field(name="Avg Price", value=f"${snapshot.avg_price:.2f}", inline=True)
                embed.add_field(
                    name="Min/Max", value=f"${snapshot.min_price:.2f} - ${snapshot.max_price:.2f}", inline=True
                )
                embed.add_field(name="Volume", value=f"{snapshot.volume} sales", inline=True)

                if snapshot.lowest_ask:
                    embed.add_field(name="Lowest Ask", value=f"${snapshot.lowest_ask:.2f}", inline=True)
                if snapshot.inventory:
                    embed.add_field(name="Active Listings", value=str(snapshot.inventory), inline=True)
            else:
                embed.add_field(name="Price Data", value="No recent market data", inline=False)

            if last_sale:
                embed.add_field(
                    name="Last Sale",
                    value=f"${last_sale.price:.2f} on {last_sale.sold_date.strftime('%Y-%m-%d') if last_sale.sold_date else 'Unknown'}",
                    inline=False,
                )

            embed.set_footer(text=f"wonderstracker.com/cards/{card.id}")

            await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Error looking up price: {str(e)}", ephemeral=True)


# ===== Scheduled Tasks =====


@tasks.loop(time=time(hour=9, minute=0))  # 9 AM UTC daily
async def daily_report_task():
    """Send daily report to designated channel."""
    if not REPORT_CHANNEL_ID:
        return

    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not channel:
        print(f"Could not find report channel {REPORT_CHANNEL_ID}")
        return

    try:
        # Generate stats embed
        stats = calculate_market_stats("daily")
        embed_data = format_stats_embed(stats)

        embed = discord.Embed(
            title=embed_data["title"],
            description=embed_data["description"],
            color=embed_data["color"],
            timestamp=datetime.fromisoformat(embed_data["timestamp"]),
        )

        for field in embed_data["fields"]:
            embed.add_field(name=field["name"], value=field["value"], inline=field.get("inline", False))

        embed.set_footer(text=embed_data["footer"]["text"])

        # Generate and upload CSV
        filename, csv_content = generate_csv_report("daily")

        try:
            download_url = upload_csv(filename, csv_content)

            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(label="Download CSV Report", url=download_url, style=discord.ButtonStyle.link)
            )

            await channel.send(embed=embed, view=view)

        except Exception:
            # Send with attachment fallback
            file = discord.File(fp=__import__("io").BytesIO(csv_content), filename=filename)
            await channel.send(embed=embed, file=file)

        print(f"Daily report sent to channel {REPORT_CHANNEL_ID}")

    except Exception as e:
        print(f"Failed to send daily report: {e}")


@tasks.loop(time=time(hour=9, minute=0))  # 9 AM UTC
async def weekly_report_task():
    """Send weekly report on Mondays."""
    if datetime.now(timezone.utc).weekday() != 0:  # Only Monday (0)
        return

    if not REPORT_CHANNEL_ID:
        return

    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not channel:
        print(f"Could not find report channel {REPORT_CHANNEL_ID}")
        return

    try:
        # Generate stats embed
        stats = calculate_market_stats("weekly")
        embed_data = format_stats_embed(stats)

        embed = discord.Embed(
            title=embed_data["title"],
            description=embed_data["description"],
            color=embed_data["color"],
            timestamp=datetime.fromisoformat(embed_data["timestamp"]),
        )

        for field in embed_data["fields"]:
            embed.add_field(name=field["name"], value=field["value"], inline=field.get("inline", False))

        embed.set_footer(text=embed_data["footer"]["text"])

        # Generate and upload CSV
        filename, csv_content = generate_csv_report("weekly")

        try:
            download_url = upload_csv(filename, csv_content)

            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(label="Download CSV Report", url=download_url, style=discord.ButtonStyle.link)
            )

            await channel.send(embed=embed, view=view)

        except Exception:
            # Send with attachment fallback
            file = discord.File(fp=__import__("io").BytesIO(csv_content), filename=filename)
            await channel.send(embed=embed, file=file)

        print(f"Weekly report sent to channel {REPORT_CHANNEL_ID}")

    except Exception as e:
        print(f"Failed to send weekly report: {e}")


@daily_report_task.before_loop
async def before_daily_report():
    await bot.wait_until_ready()


@weekly_report_task.before_loop
async def before_weekly_report():
    await bot.wait_until_ready()


# ===== Run Bot =====


def run_bot():
    """Run the Discord bot."""
    if not DISCORD_BOT_TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN not set")
        return

    print("Starting Wonders Discord Bot...")
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run_bot()
