# Eldorado.gg Robux Price Monitor

A small Playwright-based scraper that watches Eldorado.gg Robux offers and alerts when both of these conditions are true:

- the current offer price is at or below your threshold
- the seller's minimum quantity is at or below your limit

## Quick Start

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Install the Playwright browser:

```bash
python -m playwright install chromium
```

3. Run the script:

```bash
python scraper.py
```

On first run, the script opens a setup wizard and asks you for:

- your price threshold
- your max acceptable minimum quantity
- monitoring interval
- number of vendors to inspect
- sound alert preferences
- optional Telegram bot settings

After setup, the script saves your local settings in `config.local.json` and starts monitoring.

## Alarm Sounds

- The default alarm file is `alarm/boom.mp3`.
- Put any extra `.mp3`, `.wav`, `.ogg`, `.m4a`, `.aac`, or `.flac` files in `alarm/`.
- Re-run setup with `python scraper.py --setup` to switch to a different alarm file.

## Common Commands

Run one check and exit:

```bash
python scraper.py --once
```

Re-run setup:

```bash
python scraper.py --setup
```

Test the selected alarm sound:

```bash
python scraper.py --sound-test
```

Save debug HTML and a screenshot into `output/`:

```bash
python scraper.py --once --debug
```

## Files

- `config.local.json`: your local settings and optional Telegram credentials
- `alarm/`: bundled default sound plus any custom alarm sounds you add
- `output/`: runtime results and optional debug captures

## Telegram

Telegram alerts are optional. You can either:

- enter your bot token and chat ID during setup
- or provide `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as environment variables

No live credentials are stored in the repository.
