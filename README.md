# Vivameda Social Media Agent

Automated daily posting to LinkedIn and X (Twitter), plus continuous X engagement.

## What it does

### Daily Posts (LinkedIn + X)
1. Discovers trending workforce/data topics via Brave Search
2. Selects the best topic using Claude
3. Generates platform-specific content (LinkedIn: 150-250 words, X: 280 chars)
4. Generates an AI image via DALL-E 3
5. Posts to LinkedIn and X with the image attached

### X Engagement (runs every 2 hours)
1. Searches for conversations about workforce data, alternative data, HR tech
2. Likes 8 relevant tweets per run (~64/day)
3. Replies to 3 high-value tweets per run (~24/day) with Claude-generated comments
4. Targets accounts with 100+ followers to avoid bots
5. Uses random delays between actions to mimic human behavior

## Usage

```bash
# Preview daily post without publishing
python social_agent.py --dry-run

# Post to both platforms
python social_agent.py

# LinkedIn only / X only
python social_agent.py --linkedin-only
python social_agent.py --x-only

# Preview X engagement without doing anything
python x_engagement.py --dry-run

# Run X engagement (likes + replies)
python x_engagement.py

# Likes only, no replies
python x_engagement.py --likes-only
```

## Schedule (GitHub Actions)

| Workflow | Schedule | What |
|----------|----------|------|
| Daily Social Posts | 09:30 Cyprus | Post to LinkedIn + X |
| X Engagement | Every 2h, 9am-11pm Cyprus | Like + reply on X |

## Setup

1. Copy `.env.example` to `.env`
2. Add your API keys
3. Install: `pip install -r requirements.txt`
