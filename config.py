"""Configuration: reads from environment variables."""
import os

# AI
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BLOG_MODEL = os.environ.get("BLOG_MODEL", "claude-sonnet-4-5-20250929")

# Search
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")

# LinkedIn (personal profile)
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")

# LinkedIn (company page)
LINKEDIN_BIZ_ACCESS_TOKEN = os.environ.get("LINKEDIN_BIZ_ACCESS_TOKEN", "")
LINKEDIN_COMPANY_ID = "108047288"

# X personal account
X_API_KEY = os.environ.get("X_API_KEY", "")
X_API_SECRET = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "")

# X business account (@vivameda_data)
X_BIZ_API_KEY = os.environ.get("X_BIZ_API_KEY", "")
X_BIZ_API_SECRET = os.environ.get("X_BIZ_API_SECRET", "")
X_BIZ_ACCESS_TOKEN = os.environ.get("X_BIZ_ACCESS_TOKEN", "")
X_BIZ_ACCESS_SECRET = os.environ.get("X_BIZ_ACCESS_SECRET", "")
