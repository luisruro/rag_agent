#!/usr/bin/env python3
import os
import subprocess
import sys

def main():
    # Check if Chainlit is installed
    try:
        import chainlit
    except ImportError:
        print("Chainlit not found. Installing requirements...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Run Chainlit
    os.system("chainlit run app.py -w")

if __name__ == "__main__":
    main()