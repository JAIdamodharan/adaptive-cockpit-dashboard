#!/usr/bin/env python3
"""
Test script for the adaptive dashboard system with improved eye tracking
"""

import sys
import os
import logging

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.main import AdaptiveDashboardApplication


def setup_logging():
    """Setup logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("dashboard_test.log"),
            logging.StreamHandler()
        ]
    )


def main():
    print("Starting Adaptive Dashboard System Test...")
    print("This will launch the dashboard with improved eye tracking.")
    print("Press Ctrl+C to quit.")

    setup_logging()

    try:
        # Create and run application
        app = AdaptiveDashboardApplication()
        exit_code = app.run()

        # Cleanup
        app.shutdown()

        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\nDashboard stopped by user.")
        sys.exit(0)

    except Exception as e:
        print(f"Error running dashboard: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()