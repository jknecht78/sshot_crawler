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
HUGGINGFACE_TOKEN={your-token}
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


## Benchmark

╭───────────────┬─────────────────────────────┬────────────┬────────────┬──────────┬──────────┬──────────┬──────────┬──────────┬────────────┬─────────┬───────────┬──────────╮
│ Config        │ Model                       │ OK/Total   │ Success%   │   Avg(s) │   Min(s) │   P50(s) │   P95(s) │   Max(s) │   Total(s) │   s/url │   Boot(s) │ Status   │
├───────────────┼─────────────────────────────┼────────────┼────────────┼──────────┼──────────┼──────────┼──────────┼──────────┼────────────┼─────────┼───────────┼──────────┤
│ qwen2-vl-2b   │ Qwen/Qwen2-VL-2B-Instruct   │ 10/10      │ 100%       │      5.1 │     4.6  │     4.72 │     6.93 │     8.55 │        8.5 │    0.85 │      99.8 │ ✓        │
│ qwen2.5-vl-3b │ Qwen/Qwen2.5-VL-3B-Instruct │ 10/10      │ 100%       │      4.6 │     3.51 │     4.06 │     7.49 │     9.89 │        9.9 │    0.99 │      99.6 │ ✓        │
│ qwen2.5-vl-7b │ Qwen/Qwen2.5-VL-7B-Instruct │ 10/10      │ 100%       │      5.5 │     3.63 │     5.24 │     8.25 │     9.89 │        9.9 │    0.99 │     120.8 │ ✓        │
│ qwen3-vl-4b   │ Qwen/Qwen3-VL-4B-Instruct   │ 10/10      │ 100%       │     12.3 │     4.74 │    12.38 │    19.1  │    19.76 │       19.8 │    1.98 │      93.6 │ ✓        │
│ qwen3-vl-8b   │ Qwen/Qwen3-VL-8B-Instruct   │ 10/10      │ 100%       │     15.2 │     5.63 │    15.17 │    21    │    21.64 │       21.6 │    2.16 │     117.8 │ ✓        │
╰───────────────┴─────────────────────────────┴────────────┴────────────┴──────────┴──────────┴──────────┴──────────┴──────────┴────────────┴─────────┴───────────┴──────────╯
