# ID Vault Bot

A simple Telegram bot that returns group/channel IDs and admin user IDs. Details are only shown to admins of the target chat — anyone else gets an access denied message.

## Commands

| Command | Description |
|---|---|
| `/myid` | Show your Telegram user ID |
| `/id` | Show the current group or channel ID |
| `/id @username` | Show a public group or channel ID |
| `/admins` | Show all admin IDs for the current group or channel |
| `/admins @username` | Show all admin IDs for a public group or channel |
| `/help` | Show the command list |

All commands except `/myid` require the requester to be an admin of the target chat.

## Setup

**1. Create a bot via BotFather and copy the token.**

**2. Install dependencies:**

```bash
pip install -r requirements.txt
```

**3. Create your `.env` file:**

```bash
cp .env.example .env
```

Then open `.env` and set your token:

```
BOT_TOKEN=123456789:your_token_here
```

**4. Run the bot:**

```bash
python bot.py
```

## Usage

Inside a group or channel:

```
/id
/admins
```

In private chat, targeting a public group or channel:

```
/id @your_channel
/admins @your_group
```

## BotFather settings

To make sure the bot receives commands in groups, disable privacy mode:

```
/setprivacy → your bot → Disable
```

Suggested command list to set via `/setmycommands`:

```
myid - Show your Telegram user ID
id - Show the current or target chat ID
admins - Show admin IDs for the current or target chat
help - Show the command list
```

## Limitations

- **Private groups/channels:** The bot must be added to the chat. `/id @username` will not work for private chats — run `/id` from inside the chat instead.
- **Channels:** The bot may need to be added as an admin to fetch the admin list.
- **Commands posted inside a channel:** Telegram does not pass the real sender ID to the bot. Use the bot in private chat and pass the channel username instead — `/id @channel` or `/admins @channel`.

## Requirements

- Python 3.10+
- `python-telegram-bot >= 21.0, < 23.0`
- `python-dotenv >= 1.0.1, < 2.0.0`
