# Bluesky RSS Posting Bot

Automatically post articles from an RSS feed to your Bluesky account. The bot checks your RSS feed regularly and posts new articles with images and links.

## What It Does

- Posts new articles from your RSS feed to Bluesky
- Includes images from articles when available
- Remembers what you've already posted (no duplicates)
- Supports multiple Bluesky accounts
- Works with custom Bluesky servers (PDS)

## Quick Start

### 1. Get the Code

```bash
git clone https://github.com/j4ckxyz/ChicagoYIMBYblueskybot.git
cd ChicagoYIMBYblueskybot
```

### 2. Install Requirements

```bash
pip install -r requirements.txt
```

### 3. Set Up Your Credentials

Create a file named `.env` in the main folder with your login info:

```env
BLUESKY_USERNAME=yourname.bsky.social
BLUESKY_PASSWORD=your-app-password
RSS_FEED_URL=https://yoursite.com/feed
```

**Important:** Use an [app password](https://bsky.app/settings/app-passwords), not your main password!

### 4. Run the Bot

```bash
python src/main.py
```

That's it! The bot will now check your RSS feed every 10 minutes and post new articles.

---

## Advanced Setup

### Multiple Accounts

Want to post to multiple Bluesky accounts? No problem!

#### Step 1: Update `config.yaml`

Add your accounts to the `accounts` section:

```yaml
accounts:
  - name: chicago
  - name: housing
  - name: urbanplanning
```

#### Step 2: Update `.env` with all account credentials

For each account, add credentials with the pattern `ACCOUNTNAME_USERNAME`, `ACCOUNTNAME_PASSWORD`, and `ACCOUNTNAME_RSS_FEED_URL`:

```env
# Chicago account
CHICAGO_USERNAME=chicago.bsky.social
CHICAGO_PASSWORD=app-password-1
CHICAGO_RSS_FEED_URL=https://example.com/chicago-feed

# Housing account
HOUSING_USERNAME=housing.bsky.social
HOUSING_PASSWORD=app-password-2
HOUSING_RSS_FEED_URL=https://example.com/housing-feed

# Urban Planning account
URBANPLANNING_USERNAME=urbanplanning.bsky.social
URBANPLANNING_PASSWORD=app-password-3
URBANPLANNING_RSS_FEED_URL=https://example.com/planning-feed
```

**Note:** The account name in your `.env` file must be UPPERCASE and match the name in `config.yaml`.

### Custom Bluesky Server (PDS)

If you're using a custom Bluesky server instead of the main bsky.social server:

```yaml
accounts:
  - name: myaccount
    pds_url: "https://my-custom-server.com"
```

---

## Configuration Options

The `config.yaml` file has many options you can customize:

### Basic Settings

```yaml
bot:
  check_interval: 600        # How often to check for new posts (in seconds)
  include_images: true       # Include images in posts
  post_format: "{title}\n\nRead more: {link}"  # How posts look
```

### Image Settings

```yaml
rss:
  image_sources:
    use_og_image: true       # Try OpenGraph images first
    use_twitter_image: true  # Then try Twitter card images
    use_wp_post_image: true  # Then try WordPress featured images
    use_first_image: true    # Finally, use the first image in the article
```

### Duplicate Detection

```yaml
bot:
  duplicate_detection:
    check_database: true           # Remember posts in a database
    check_bluesky_backup: true     # Also check recent Bluesky posts
    auto_sync_to_database: true    # Keep database in sync
```

---

## Features

✅ **Easy Setup** - Just add your credentials and go  
✅ **Multiple Accounts** - Run as many accounts as you want  
✅ **Custom Servers** - Works with any Bluesky PDS  
✅ **Smart Images** - Automatically finds and includes article images  
✅ **No Duplicates** - Keeps track of what's already been posted  
✅ **Reliable** - Auto-retries on errors, handles rate limits  
✅ **Customizable** - Configure post format, check intervals, and more  

---

## Troubleshooting

### Bot won't start
- Make sure you've created a `.env` file with your credentials
- Check that your RSS feed URL is correct
- Verify you're using an app password, not your main password

### No posts appearing
- Check the logs for error messages
- Make sure your RSS feed has new articles
- Verify your `min_post_date` setting in `config.yaml`

### Images not working
- Some feeds don't include images - this is normal
- The bot will post text-only if no image is found
- You can disable images by setting `include_images: false` in `config.yaml`

### Multiple accounts not working
- Account names in `.env` must be UPPERCASE
- Account names in `config.yaml` must be lowercase
- Make sure each account has all three required variables (USERNAME, PASSWORD, RSS_FEED_URL)

---

## How to Get an App Password

1. Go to your Bluesky settings: https://bsky.app/settings/app-passwords
2. Click "Add App Password"
3. Give it a name (like "RSS Bot")
4. Copy the password and paste it into your `.env` file

**Never use your main account password!**

---

## Requirements

- Python 3.8 or newer
- A Bluesky account
- An RSS feed to monitor

## License

This project is open-source and available under the [MIT License](LICENSE).
