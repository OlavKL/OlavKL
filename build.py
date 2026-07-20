"""
Builds terminal.png: a premium dark-terminal GitHub profile header.

Pipeline:
  1. Read the pre-generated ASCII portrait (generate_ascii.py output).
  2. Inject it into an HTML/CSS terminal-window template.
  3. Render the page with Playwright (headless Chromium) at exactly
     1800x900px and screenshot it to terminal.png.

Run `python generate_ascii.py` first if assets/profile.png changes.
"""

import html
import os
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(__file__)
ASCII_PATH = os.path.join(ROOT, "ascii_portrait.txt")
HTML_OUT = os.path.join(ROOT, "terminal.html")
PNG_OUT = os.path.join(ROOT, "terminal.png")

WIDTH, HEIGHT = 1800, 900

with open(ASCII_PATH, "r", encoding="utf-8") as f:
    ASCII_ART = html.escape(f.read())

PAGE = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  @font-face {{
    font-family: 'Cascadia Code';
    src: local('Cascadia Code');
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  html, body {{
    width: {WIDTH}px;
    height: {HEIGHT}px;
    overflow: hidden;
    background: #0a0b10;
  }}

  .stage {{
    width: {WIDTH}px;
    height: {HEIGHT}px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 80px;
    font-family: 'Cascadia Code', 'Cascadia Mono', Consolas, 'Courier New', monospace;
  }}

  .content {{
    display: flex;
    align-items: center;
    gap: 46px;
    width: 100%;
  }}

  .portrait-col {{
    flex: 0 0 auto;
  }}

  .portrait {{
    font-size: 16.7px;
    line-height: 16.7px;
    letter-spacing: 0.3px;
    white-space: pre;
    color: #ffffff;
    text-shadow: 0 0 4px rgba(255,255,255,0.45);
  }}

  .divider {{
    flex: 0 0 auto;
    width: 1px;
    align-self: stretch;
    background: linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.09) 20%, rgba(255,255,255,0.09) 80%, rgba(255,255,255,0) 100%);
  }}

  .info-col {{
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 22px;
    font-size: 18px;
    line-height: 1.3;
  }}

  .prompt {{
    color: #6ee7b7;
    font-weight: 600;
    font-size: 17px;
  }}
  .prompt .path {{
    color: #7aa2f7;
  }}
  .cmd {{
    color: #e8e9ee;
  }}

  .block {{
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}

  .name {{
    font-size: 46px;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: 0.3px;
    margin-top: 2px;
  }}

  .role {{
    color: #e5b567;
    font-size: 21px;
    letter-spacing: 0.3px;
  }}

  .sysinfo {{
    display: grid;
    grid-template-columns: auto 1fr;
    column-gap: 20px;
    row-gap: 7px;
    font-size: 18px;
  }}
  .sysinfo .k {{
    color: #e06c75;
    font-weight: 600;
    letter-spacing: 0.2px;
    white-space: nowrap;
  }}
  .sysinfo .v {{
    color: #d4d7e0;
  }}

  .gh-row {{
    display: flex;
    align-items: baseline;
    gap: 10px;
    font-size: 18px;
  }}
  .gh-row .at {{ color: #565a6e; }}
  .gh-row .handle {{ color: #7aa2f7; font-weight: 600; }}

  .cursor {{
    display: inline-block;
    width: 11px;
    height: 22px;
    background: #7aa2f7;
    margin-left: 2px;
    vertical-align: -4px;
    box-shadow: 0 0 12px rgba(122,162,247,0.7);
  }}
</style>
</head>
<body>
  <div class="stage">
    <div class="content">
      <div class="portrait-col"><pre class="portrait">{ASCII_ART}</pre></div>
      <div class="divider"></div>
      <div class="info-col">
        <div class="block">
          <div class="prompt"><span class="path">~</span> $ <span class="cmd">whoami</span></div>
          <div class="name">Olav Leek</div>
          <div class="role">Aspiring Finance &amp; Business Analytics</div>
        </div>

        <div class="block">
          <div class="sysinfo">
            <span class="k">Age</span><span class="v">21</span>
            <span class="k">Education</span><span class="v">BSc Economics &amp; Business Administration</span>
            <span class="k">Interests</span><span class="v">Investing, Real Estate, Business Analytics</span>
            <span class="k">Experience</span><span class="v">Technical Support, Fiber Networks &amp; Wi-Fi</span>
            <span class="k">Side Quests</span><span class="v">iOS Jailbreaking, Crypto Mining, Web Scraping, Automation</span>
            <span class="k">Languages</span><span class="v">Python, SQL</span>
          </div>
        </div>

        <div class="block">
          <div class="prompt"><span class="path">~</span> $ <span class="cmd">gh profile</span></div>
          <div class="gh-row"><span class="at">github.com/</span><span class="handle">OlavKL</span><span class="cursor"></span></div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

with open(HTML_OUT, "w", encoding="utf-8") as f:
    f.write(PAGE)


RAW_OUT = os.path.join(ROOT, "_terminal_2x.png")

with sync_playwright() as p:
    browser = p.chromium.launch()
    # Render at 2x device scale for crisp text/edges, then downsample to the
    # exact target resolution for a clean, alias-free final PNG.
    page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=2)
    page.goto(f"file:///{HTML_OUT.replace(os.sep, '/')}")
    page.wait_for_timeout(150)
    page.screenshot(path=RAW_OUT)
    browser.close()

from PIL import Image
img = Image.open(RAW_OUT)
img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
img.save(PNG_OUT)
os.remove(RAW_OUT)

print(f"Wrote {PNG_OUT}")
