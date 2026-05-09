# Speed Project - Setup & Usage Manual

## Quick Start

### First Time Setup
```bash
bash install.sh
```

This automatically:
- Creates Python 3.12 virtual environment (`.venv`)
- Installs all dependencies (vllm, playwright, pillow, torch, python-dotenv, requests)
- Downloads Playwright chromium
- Sets up `run` command symlink

### Running the Project
```bash
run
```

## Configuration

All settings are stored in `.env` file:
```
MODEL_ID=microsoft/phi-3-vision-128k-instruct
MAX_PAGES=5
IMAGE_SIZE=512,512
PROMPT=What do you see?
HUGGINGFACE_TOKEN=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
```

Edit `.env` to customize behavior without modifying code.

## Project Structure
```
.venv/                  # Virtual environment
.env                    # Configuration (git-ignored)
install.sh              # Automated setup script
run.sh                  # Wrapper to activate venv & run main.py
main.py                 # Main application
manual.md               # This file
```

## Manual Setup (if needed)
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install vllm playwright pillow torch python-dotenv requests

# Install Playwright browsers
python -m playwright install chromium

# Run project
python main.py
```

## References
- Gist: https://gist.github.com/bejaneps/ba8d8eed85b0c289a05c750b3d825f61
- HuggingFace Token: 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