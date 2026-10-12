# 📦 Reddit Data Exporter

Exports your Reddit account data to local JSON and CSV files:

- **Subscribed subreddits** — name, subscriber count, description, etc.
- **Saved posts** — title, URL, score, text content, etc.
- **Saved comments** — body text, parent post title, score, etc.

## Quick Start

### 1. Create a Reddit API App (~2 minutes)

1. Go to [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
2. Scroll down → click **"create another app..."**
3. Fill in the form:
   - **Name**: `my-data-exporter` (anything you want)
   - **App type**: Select **`script`**
   - **Description**: (optional)
   - **About URL**: (leave blank)
   - **Redirect URI**: `http://localhost:8080`
4. Click **Create app**
5. Note down:
   - **Client ID**: the string under your app name (looks like `a1b2c3d4e5f6g7`)
   - **Client Secret**: labeled "secret"

### 2. Set Up Credentials

```bash
cd reddit-exporter
cp .env.example .env
```

Edit `.env` with your real values:

```env
REDDIT_CLIENT_ID=a1b2c3d4e5f6g7
REDDIT_CLIENT_SECRET=your_secret_here
REDDIT_USERNAME=your_username
REDDIT_PASSWORD=your_password
```

> **⚠️ Two-Factor Authentication (2FA):** If you have 2FA enabled, append your
> current TOTP code to your password like this: `your_password:123456`

### 3. Install & Run

```bash
# Create a virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the exporter
python exporter.py
```

## Output

Each run creates a timestamped folder in `./exports/`:

```
exports/
└── 2026-04-19_14-30-00/
    ├── subreddits.json
    ├── subreddits.csv
    ├── saved_posts.json
    ├── saved_posts.csv
    ├── saved_comments.json
    ├── saved_comments.csv
    └── summary.json
```

| File | Contents |
|------|----------|
| `subreddits.json/csv` | All subreddits you're subscribed to |
| `saved_posts.json/csv` | All posts you've saved |
| `saved_comments.json/csv` | All comments you've saved |
| `summary.json` | Stats: counts, top subreddits by saved items |

## Notes

- **Rate Limiting**: The script includes built-in pauses to respect Reddit's API limits.
- **Reddit's 1000-item limit**: Reddit's API only returns the **last ~1,000 saved items**. This is a Reddit API limitation, not a script limitation. If you have more than 1,000 saved items, consider using [Reddit's official data request](https://www.reddit.com/settings/data-request) for a complete archive.
- **Credentials are never stored in exports** — they stay in your `.env` file (which is gitignored).

## Troubleshooting

| Error | Solution |
|-------|----------|
| `OAuthException` | Double-check client_id, secret, username, and password |
| `Forbidden` | Make sure the app type is **"script"**, not "web" or "installed" |
| `2FA errors` | Append `:TOTP_CODE` to your password in `.env` |
| `Too Many Requests` | Wait a minute and try again; the script has built-in rate limiting |
