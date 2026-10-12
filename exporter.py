#!/usr/bin/env python3
"""
Reddit Data Exporter (Browser-based)
=====================================
Uses browser automation to export your Reddit data — no API keys needed.
  - All subscribed subreddits
  - All saved posts and comments (title + URL)

Usage:
  1. Copy .env.example to .env and fill in your Reddit login
  2. pip install -r requirements.txt && playwright install chromium
  3. python exporter.py
"""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout


EXPORTS_DIR = Path(__file__).parent / "exports"
OLD_REDDIT = "https://old.reddit.com"

def login(context, page):
    """Wait for manual login, OR use a session cookie if provided."""
    load_dotenv()
    session_cookie = os.getenv("REDDIT_SESSION", "").strip()

    if session_cookie:
        print("🍪 Found REDDIT_SESSION in .env. Skipping manual login!")
        context.add_cookies([{
            "name": "reddit_session",
            "value": session_cookie,
            "domain": ".reddit.com",
            "path": "/"
        }])
    else:
        print("🔐 Opening browser for manual login...")
        page.goto("https://www.reddit.com/login/")
        
        print("\n" + "═"*60)
        print("⚠️  ACTION REQUIRED: ⚠️")
        print("Playwright is triggering bot-captchas.")
        print("You can bypass this by getting your 'reddit_session' cookie")
        print("from your normal browser and putting it in your .env file")
        print("Example: REDDIT_SESSION=123456789%2CaBcDeFgHiJkLmNoP")
        print("\nOR, solve the captcha in the open Chromium window manually.")
        print("Come back to this terminal and press ENTER when logged in.")
        print("═"*60 + "\n")
        
        input("Press ENTER here AFTER you have successfully logged in... ")
    
    # Navigate to old.reddit.com so cookies are set for JSON endpoints
    page.goto(f"{OLD_REDDIT}", wait_until="networkidle")
    time.sleep(1)
    
    # Verify login worked
    if "reddit_session" not in [c["name"] for c in context.cookies()]:
        print("❌ Login verification failed. Please check your credentials or cookie.")
        sys.exit(1)
        
    print("✅ Verified login session cookies.\n")


def fetch_subreddits(page) -> list[str]:
    """Fetch all subscribed subreddits using the JSON endpoint."""
    print("📡 Fetching subreddits...")
    subreddits = set()
    after = None

    while True:
        url = f"{OLD_REDDIT}/subreddits/mine.json?limit=100"
        if after:
            url += f"&after={after}"

        page.goto(url, wait_until="networkidle")

        try:
            raw = page.inner_text("pre")
            data = json.loads(raw)
        except Exception:
            # Try body text if no <pre> tag
            raw = page.inner_text("body")
            data = json.loads(raw)

        children = data.get("data", {}).get("children", [])
        if not children:
            break

        for child in children:
            name = child.get("data", {}).get("display_name", "")
            if name:
                subreddits.add(name)

        after = data.get("data", {}).get("after")
        if not after:
            break

        print(f"   ... {len(subreddits)} subreddits so far")
        time.sleep(1)

    result = sorted(subreddits, key=str.lower)
    print(f"   📊 Total: {len(result)} subreddits")
    return result


def fetch_saved(page, username: str) -> tuple[list[dict], list[dict]]:
    """Fetch all saved posts and comments using the JSON endpoint."""
    print("📡 Fetching saved content...")
    posts = []
    comments = []
    after = None

    while True:
        url = f"{OLD_REDDIT}/user/{username}/saved.json?limit=100"
        if after:
            url += f"&after={after}"

        page.goto(url, wait_until="networkidle")

        try:
            raw = page.inner_text("pre")
            data = json.loads(raw)
        except Exception:
            raw = page.inner_text("body")
            data = json.loads(raw)

        children = data.get("data", {}).get("children", [])
        if not children:
            break

        for child in children:
            kind = child.get("kind", "")
            d = child.get("data", {})
            subreddit = d.get("subreddit", "")
            permalink = d.get("permalink", "")
            url_full = f"https://www.reddit.com{permalink}" if permalink else ""

            if kind == "t3":  # Post
                posts.append({
                    "title": d.get("title", ""),
                    "url": url_full,
                    "subreddit": subreddit,
                })
            elif kind == "t1":  # Comment
                body = (d.get("body", "") or "")[:120].replace("\n", " ")
                comments.append({
                    "url": url_full,
                    "subreddit": subreddit,
                    "preview": body,
                })

        after = data.get("data", {}).get("after")
        if not after:
            break

        total = len(posts) + len(comments)
        print(f"   ... {total} items ({len(posts)} posts, {len(comments)} comments)")
        time.sleep(1)

    print(f"   📊 Total: {len(posts)} posts, {len(comments)} comments")
    return posts, comments


def get_username(page) -> str:
    """Get the authenticated username."""
    page.goto(f"{OLD_REDDIT}/api/me.json", wait_until="networkidle")
    try:
        raw = page.inner_text("pre")
        data = json.loads(raw)
    except Exception:
        raw = page.inner_text("body")
        data = json.loads(raw)
    return data.get("data", {}).get("name", "")


def main():
    print("\n📦 Reddit Data Exporter\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        login(context, page)
        
        username = get_username(page)
        if not username:
            print("❌ Could not determine username from session.")
            sys.exit(1)
        print(f"👤 Detected user: /u/{username}\n")
        
        user_export_dir = EXPORTS_DIR / username
        user_export_dir.mkdir(parents=True, exist_ok=True)
            
        subreddits = fetch_subreddits(page)
        print()
        
        saved_posts, saved_comments = fetch_saved(page, username)

        browser.close()

    # Save everything
    data = {
        "subreddits": subreddits,
        "saved_posts": saved_posts,
        "saved_comments": saved_comments,
    }
    
    out_file = user_export_dir / "reddit_export.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    subs_file = user_export_dir / "subreddits.txt"
    with open(subs_file, "w") as f:
        f.write("\n".join(subreddits))

    print(f"\n✅ Exported to {user_export_dir}/")
    print(f"   reddit_export.json  — {len(subreddits)} subs, "
          f"{len(saved_posts)} posts, {len(saved_comments)} comments")
    print(f"   subreddits.txt      — plain list of subreddit names")
    print("\n🎉 Done!\n")


if __name__ == "__main__":
    main()
