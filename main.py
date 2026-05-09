import os
import asyncio
import base64
import csv
import io
import json
import textwrap
import warnings
import datetime
import logging
import httpx
import requests
import polars as pl
from dotenv import load_dotenv
from openai import AsyncOpenAI, APIConnectionError
from playwright.async_api import async_playwright
from PIL import Image

from models import PageAnalysis

warnings.filterwarnings("ignore", category=FutureWarning, module=r"transformers")
warnings.filterwarnings("ignore", message=r".*pin_memory.*", category=UserWarning)

# --- LOAD CONFIGURATION ---
PROJECT_DIR  = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(PROJECT_DIR, ".env"))
_cfg      = os.getenv("MODEL_CONFIG", "qwen3-vl-8b")
_cfg_path = os.path.join(PROJECT_DIR, "configs", f"{_cfg}.env")
if os.path.exists(_cfg_path):
    load_dotenv(_cfg_path, override=True)

MODEL_ID     = os.getenv("MODEL_ID")
MAX_PAGES    = int(os.getenv("MAX_PAGES",    "0")) or None  # 0 = no limit
IMAGE_SCALE  = float(os.getenv("IMAGE_SCALE", "0.5"))
PROMPT       = os.getenv("PROMPT",       "What do you see?")
GIST_URL     = os.getenv("GIST_URL",     "")
PAGE_TIMEOUT = int(os.getenv("PAGE_TIMEOUT_MS", "15000"))
CONCURRENCY       = int(os.getenv("CONCURRENCY", "5"))
INFER_CONCURRENCY = int(os.getenv("INFER_CONCURRENCY", "5"))
SERVER_URL        = os.getenv("SERVER_URL",   "http://127.0.0.1:8000/v1")

RESULTS_DIR  = os.path.join(PROJECT_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
model_slug   = (MODEL_ID or "unknown").replace("/", "_")
ERROR_LOG    = os.path.join(RESULTS_DIR, f"{model_slug}_error.log")

# Purge error.log at the start of each run
with open(ERROR_LOG, "w"):
    pass

# Error logger → error.log
logging.basicConfig(
    filename=ERROR_LOG,
    level=logging.ERROR,
    format="%(asctime)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

client = AsyncOpenAI(base_url=SERVER_URL, api_key="EMPTY")

# --- STEP 0: Fetch URLs from Gist ---
def fetch_urls_from_gist(gist_url, limit=None):
    raw_url = gist_url if "/raw" in gist_url else gist_url.rstrip("/") + "/raw"
    try:
        resp = requests.get(raw_url, timeout=10)
        resp.raise_for_status()
        urls = []
        lines = resp.text.splitlines()
        first = next((l.strip() for l in lines if l.strip()), "")
        if first.startswith(("http://", "https://")):
            for line in lines:
                url = line.strip()
                if url.startswith(("http://", "https://")):
                    urls.append(url)
                    if limit and len(urls) >= limit:
                        break
        else:
            sample = resp.text[:2048]
            dialect = csv.Sniffer().sniff(sample, delimiters="|,")
            for row in csv.reader(io.StringIO(resp.text), dialect):
                if len(row) < 2:
                    continue
                domain = next(
                    (c.strip().strip('"').lower() for c in row
                     if "." in c.strip() and " " not in c.strip()),
                    ""
                )
                if not domain or domain in {"domain", "website", "site"}:
                    continue
                if not domain.startswith(("http://", "https://")):
                    domain = f"https://{domain}"
                urls.append(domain)
                if limit and len(urls) >= limit:
                    break
        return urls
    except Exception as e:
        log.error("fetch_urls_from_gist: %s", e)
        return []

# --- STEP 1: Crawl one page → base64 PNG ---
async def capture(url, sem):
    async with sem:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            ctx = await browser.new_context(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ))
            page = await ctx.new_page()
            print(f"\t → {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            data = await page.screenshot()
            await browser.close()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = img.size
        img = img.resize((int(w * IMAGE_SCALE), int(h * IMAGE_SCALE)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

# --- STEP 2: Send screenshot to vLLM server (with retry) ---
async def infer(url, b64_image, retries=3, backoff=2.0):
    for attempt in range(1, retries + 1):
        try:
            resp = await client.beta.chat.completions.parse(
                model=MODEL_ID,
                messages=[
                    {"role": "system", "content": PROMPT},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}},
                    ]},
                ],
                response_format=PageAnalysis,
                max_tokens=512,
                temperature=0.2,
            )
            parsed = resp.choices[0].message.parsed
            if parsed is None:
                return {"error": "empty_response"}
            return parsed.model_dump()
        except APIConnectionError as e:
            if attempt == retries:
                raise
            await asyncio.sleep(backoff * attempt)

# --- STEP 3: Crawl + infer concurrently ---
async def process(url, sem, infer_sem, results, lock):
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    try:
        b64 = await capture(url, sem)
        async with infer_sem:
            result = await infer(url, b64)
        entry = {"url": url, "result": result}
    except Exception as e:
        log.error("%s — %s", url, e)
        entry = {"url": url, "error": str(e)}
        print(f" ⚠ ERROR → {url}")
    entry["_duration_s"] = round(loop.time() - t0, 2)
    async with lock:
        results.append(entry)

async def main():
    # Fail fast if server isn't up
    health_url = SERVER_URL.rstrip("/").rsplit("/v1", 1)[0] + "/health"
    try:
        async with httpx.AsyncClient(timeout=5) as hc:
            r = await hc.get(health_url)
            r.raise_for_status()
    except Exception:
        print(f"ERROR: vLLM server not reachable at {SERVER_URL}")
        print("Start it with: bash server.sh")
        return

    print(f"Fetching URLs from: {GIST_URL}")
    urls = fetch_urls_from_gist(GIST_URL, limit=MAX_PAGES)
    print(f"Loaded {len(urls)} URLs  |  Crawl concurrency: {CONCURRENCY}  |  Infer concurrency: {INFER_CONCURRENCY}\n")
    if not urls:
        print("No URLs. Check GIST_URL.")
        return

    ts           = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M")
    prefix       = f"{ts}_{model_slug}"
    results_path = os.path.join(RESULTS_DIR, f"{prefix}_results.json")

    sem       = asyncio.Semaphore(CONCURRENCY)
    infer_sem = asyncio.Semaphore(INFER_CONCURRENCY)
    lock      = asyncio.Lock()
    results   = []

    loop = asyncio.get_running_loop()
    t_start = loop.time()
    await asyncio.gather(*[process(url, sem, infer_sem, results, lock) for url in urls])
    t_total = loop.time() - t_start

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Post-process: write Excel (successful entries only, flattened)
    excel_path = os.path.join(RESULTS_DIR, f"{prefix}_results.xlsx")
    rows = []
    for r in results:
        if "error" not in r and isinstance(r.get("result"), dict):
            row = {"url": r["url"]}
            row.update(r["result"])
            # flatten list fields to comma-separated strings
            for k, v in row.items():
                if isinstance(v, list):
                    row[k] = ", ".join(v)
            rows.append(row)
    if rows:
        pl.DataFrame(rows).write_excel(excel_path, autofit=True)

    ok      = [r for r in results if "error" not in r]
    errors  = [r for r in results if "error" in r]
    throughput = t_total / len(results) if results else 0
    durations  = sorted([r["_duration_s"] for r in results])
    avg_dur    = sum(durations) / len(durations) if durations else 0
    def _pct(lst, p):
        if not lst: return 0
        k = (len(lst) - 1) * p / 100
        lo, hi = int(k), min(int(k) + 1, len(lst) - 1)
        return round(lst[lo] + (lst[hi] - lst[lo]) * (k - lo), 2)
    min_dur = durations[0]  if durations else 0
    max_dur = durations[-1] if durations else 0
    p50_dur = _pct(durations, 50)
    p95_dur = _pct(durations, 95)

    stats = {
        "model_id":      MODEL_ID,
        "model_config":  os.getenv("MODEL_CONFIG", ""),
        "timestamp":     ts,
        "urls_processed": len(results),
        "successful":    len(ok),
        "errors":        len(errors),
        "success_pct":   round(len(ok) / len(results) * 100) if results else 0,
        "total_s":       round(t_total, 1),
        "throughput_s":  round(throughput, 2),
        "avg_url_s":     round(avg_dur, 1),
        "min_url_s":     min_dur,
        "p50_url_s":     p50_dur,
        "p95_url_s":     p95_dur,
        "max_url_s":     max_dur,
        "results_file":  os.path.basename(results_path),
        "excel_file":    os.path.basename(excel_path),
    }
    stats_path = os.path.join(RESULTS_DIR, f"{prefix}_stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    n=120
    prompt_wrapped = textwrap.fill(PROMPT, width=n-20, subsequent_indent=" " * 20)
    print(f"""
{'─' * n}
  Model          → {MODEL_ID}
{'─' * n}  
  Prompt         {prompt_wrapped}
{'─' * n}
  URLs processed → {len(results)}
  Successful     → {len(ok)}
  Errors         → {len(errors)}
  Total time     → {t_total:.1f}s
  Throughput     → {throughput:.2f}s per url  (wall time ÷ count)
  Avg processing → {avg_dur:.1f}s per url  (individual crawl & infer)
  Min / P50 / P95 / Max → {min_dur}s / {p50_dur}s / {p95_dur}s / {max_dur}s
{'─' * n} 
  Results saved  → {results_path}
  Excel saved    → {excel_path}
  Stats saved    → {stats_path}
  Error log      → {ERROR_LOG}
{'─' * n}
""")


if __name__ == "__main__":
    asyncio.run(main())
