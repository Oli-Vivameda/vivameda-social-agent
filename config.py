"""Configuration — reads from environment variables."""
import os

# AI
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BLOG_MODEL = os.environ.get("BLOG_MODEL", "claude-sonnet-4-5-20250929")

# Search
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")

# LinkedIn
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")

# X (Twitter)
X_API_KEY = os.environ.get("X_API_KEY", "")
X_API_SECRET = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "")
