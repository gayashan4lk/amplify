"""Test config: put apps/api on sys.path and set placeholder env vars."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "postgresql://fake/fake")
os.environ.setdefault("MONGODB_URI", "mongodb://fake")
os.environ.setdefault("MONGODB_DB", "amplify_test")
os.environ.setdefault("REDIS_URL", "redis://fake")
os.environ.setdefault("OPENAI_API_KEY", "sk-fake")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fake")
os.environ.setdefault("TAVILY_API_KEY", "tvly-fake")
os.environ.setdefault("LANGSMITH_TRACING", "false")
