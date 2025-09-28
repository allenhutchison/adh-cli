#!/usr/bin/env python
"""Test script to verify API key loading."""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Check both possible env var names
google_key = os.getenv("GOOGLE_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

print("Environment variables loaded:")
print(f"GOOGLE_API_KEY: {'Set' if google_key else 'Not set'}")
print(f"GEMINI_API_KEY: {'Set' if gemini_key else 'Not set'}")

if gemini_key:
    print(f"API Key found (first 10 chars): {gemini_key[:10]}...")

# Test the ADK service
try:
    from adh_cli.services.adk_service import ADKService
    service = ADKService()
    print("\n✓ ADK Service initialized successfully!")
except Exception as e:
    print(f"\n✗ Error initializing ADK Service: {e}")