#!/usr/bin/env python3
"""
Main entry point for the Ultimate Price Comparison API.

Usage:
    python main.py

Requirements:
    1. pip install -r requirements.txt
    2. Set environment variables (see .env.example)
"""

import os
import sys

def main():
    """Main entry point for the application."""
    # Validate all required environment variables
    try:
        from app.config import settings
        settings.validate_required_vars()
    except ValueError as e:
        print(f"ERROR: {e}")
        print("Please check the .env.example file for required environment variables.")
        sys.exit(1)
    
    # Import and run the app
    try:
        import uvicorn
        from app.main import app
        
        print("Starting Ultimate Price Comparison API...")
        print("API will be available at: http://localhost:7777/lp")
        print("API documentation at: http://localhost:7777/lp/docs")
        
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=7777,
            reload=True,
            log_level="info"
        )
    except ImportError as e:
        print(f"ERROR: Missing dependencies. Please run: pip install -r requirements.txt")
        print(f"Import error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
