#!/usr/bin/env python3
"""
Reddit Data Importer (Browser-based)
=====================================
Reads reddit_export.json and on your NEW account:
  - Subscribes to all subreddits
  - Re-saves all posts and comments

Usage:
  1. Update .env with your NEW account credentials
  2. python importer.py
"""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


EXPORTS_DIR = Path(__file__).parent / "exports"
OLD_REDDIT = "https://old.reddit.com"


def load_export() -> tuple[dict, str]:
    """Load the exported data and return the selected folder."""
    if not EXPORTS_DIR.exists():
        print(f"❌ Exports directory not found: {EXPORTS_DIR}")
        print("   Run exporter.py first with your OLD account.")
        sys.exit(1)
        
    folders = [f.name for f in EXPORTS_DIR.iterdir() if f.is_dir()]
    if not folders:
        print(f"❌ No exported account folders found in {EXPORTS_DIR}")
        sys.exit(1)
        
    print(f"📁 Found exported data for:")
    for i, name in enumerate(folders, 1):
        print(f"   {i}. {name}")
        
    print()
    if len(folders) == 1:
        target_folder = folders[0]
        print(f"Only one export found. Auto-selecting: {target_folder}")
    else:
        choice = input(f"Which account do you want to import from? (1-{len(folders)}): ")
        try:
            target_folder = folders[int(choice) - 1]
        except (ValueError, IndexError):
            print("❌ Invalid choice. Cancelled.")
            sys.exit(1)
            
    export_file = EXPORTS_DIR / target_folder / "reddit_export.json"
    
    if not export_file.exists():
        print(f"❌ Export file not found: {export_file}")
        sys.exit(1)

    with open(export_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n📂 Loaded {target_folder}: {len(data.get('subreddits', []))} subs, "
          f"{len(data.get('saved_posts', []))} posts, "
          f"{len(data.get('saved_comments', []))} comments\n")
    return data, target_folder


def load_state(target_folder: str) -> dict:
    """Load sync state so we can skip already imported items."""
    state_file = EXPORTS_DIR / target_folder / "sync_state.json"
    if state_file.exists():
        with open(state_file, "r") as f:
            return json.load(f)
    return {"subreddits": [], "saved_posts": [], "saved_comments": []}


def save_state(target_folder: str, state: dict):
    """Save the sync state."""
    state_file = EXPORTS_DIR / target_folder / "sync_state.json"
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


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
        print("\nOR, solve the captcha in the open Chromium window manually.")
        print("Come back to this terminal and press ENTER when logged in.")
        print("═"*60 + "\n")
        
        input("Press ENTER here AFTER you have successfully logged in... ")
    
    # Navigate to old.reddit.com so cookies are set for API endpoints
    page.goto(f"{OLD_REDDIT}", wait_until="networkidle")
    time.sleep(1)
    
    if "reddit_session" not in [c["name"] for c in context.cookies()]:
        print("❌ Login verification failed. Please check your credentials or cookie.")
        sys.exit(1)
        
    print("✅ Verified login session cookies.\n")

    # Navigate to old.reddit.com so cookies are set for API endpoints
    page.goto(f"{OLD_REDDIT}", wait_until="networkidle")
    time.sleep(1)

    print("✅ Ready to import!\n")


def get_modhash(page) -> str:
    """Get the modhash token needed for POST requests."""
    page.goto(f"{OLD_REDDIT}/api/me.json", wait_until="networkidle")
    try:
        raw = page.inner_text("pre")
        data = json.loads(raw)
    except Exception:
        raw = page.inner_text("body")
        data = json.loads(raw)
    return data.get("data", {}).get("modhash", "")


def subscribe_to_subreddits(page, subreddits: list[str], modhash: str, target_folder: str, state: dict):
    """Subscribe to subreddits via Reddit's API using browser session."""
    if not subreddits:
        print("⏭️  No subreddits to subscribe to.\n")
        return

    to_process = [s for s in subreddits if s not in state["subreddits"]]
    if not to_process:
        print("⏭️  All subreddits already subscribed!\n")
        return

    print(f"📡 Subscribing to {len(to_process)} subreddits (skipping {len(subreddits) - len(to_process)} already done)...")
    success, failed = 0, []

    for i, name in enumerate(to_process, 1):
        try:
            response = page.evaluate(
                """async ([name, modhash]) => {
                    const form = new URLSearchParams();
                    form.append('action', 'sub');
                    form.append('sr_name', name);
                    form.append('uh', modhash);
                    const res = await fetch('https://old.reddit.com/api/subscribe', {
                        method: 'POST',
                        body: form,
                        credentials: 'include',
                    });
                    return res.status;
                }""",
                [name, modhash],
            )
            if response == 200:
                success += 1
                state["subreddits"].append(name)
                save_state(target_folder, state)
            else:
                failed.append((name, f"HTTP {response}"))
        except Exception as e:
            failed.append((name, str(e)))

        if i % 10 == 0:
            print(f"   ... {i}/{len(to_process)}")
            time.sleep(6)  # Much longer delay for rate limits
        else:
            time.sleep(2.5) # Increased baseline delay

    print(f"   ✅ Subscribed: {success}")
    if failed:
        print(f"   ⚠️  Failed: {len(failed)}")
        for name, err in failed[:10]:
            print(f"      r/{name}: {err}")
    print()


def save_item(page, fullname: str, modhash: str) -> int:
    """Save a post or comment by its fullname (t3_ID or t1_ID)."""
    return page.evaluate(
        """async ([fullname, modhash]) => {
            const form = new URLSearchParams();
            form.append('id', fullname);
            form.append('uh', modhash);
            const res = await fetch('https://old.reddit.com/api/save', {
                method: 'POST',
                body: form,
                credentials: 'include',
            });
            return res.status;
        }""",
        [fullname, modhash],
    )


def extract_post_id(url: str) -> str | None:
    """Extract submission fullname (t3_ID) from a Reddit URL."""
    try:
        parts = url.split("/comments/")
        if len(parts) >= 2:
            post_id = parts[1].split("/")[0]
            return f"t3_{post_id}"
    except Exception:
        pass
    return None


def extract_comment_id(url: str) -> str | None:
    """Extract comment fullname (t1_ID) from a Reddit URL."""
    try:
        comment_id = url.rstrip("/").split("/")[-1]
        if comment_id and len(comment_id) >= 4:
            return f"t1_{comment_id}"
    except Exception:
        pass
    return None


def save_posts(page, posts: list[dict], modhash: str, target_folder: str, state: dict):
    """Re-save all posts."""
    if not posts:
        print("⏭️  No posts to save.\n")
        return

    to_process = [p for p in posts if p["url"] not in state["saved_posts"]]
    if not to_process:
        print("⏭️  All posts already saved!\n")
        return

    print(f"📌 Saving {len(to_process)} posts (skipping {len(posts) - len(to_process)} already done)...")
    success, failed = 0, []

    for i, post in enumerate(to_process, 1):
        fullname = extract_post_id(post["url"])
        if not fullname:
            failed.append((post.get("title", "?")[:50], "could not parse ID"))
            continue

        try:
            status = save_item(page, fullname, modhash)
            if status == 200:
                success += 1
                state["saved_posts"].append(post["url"])
                save_state(target_folder, state)
            else:
                failed.append((post.get("title", "?")[:50], f"HTTP {status}"))
        except Exception as e:
            failed.append((post.get("title", "?")[:50], str(e)))

        if i % 10 == 0:
            print(f"   ... {i}/{len(to_process)}")
            time.sleep(6)
        else:
            time.sleep(2.5)

    print(f"   ✅ Saved: {success}")
    if failed:
        print(f"   ⚠️  Failed: {len(failed)}")
        for title, err in failed[:10]:
            print(f"      {title}: {err}")
    print()


def save_comments(page, comments: list[dict], modhash: str, target_folder: str, state: dict):
    """Re-save all comments."""
    if not comments:
        print("⏭️  No comments to save.\n")
        return

    to_process = [c for c in comments if c["url"] not in state["saved_comments"]]
    if not to_process:
        print("⏭️  All comments already saved!\n")
        return

    print(f"💬 Saving {len(to_process)} comments (skipping {len(comments) - len(to_process)} already done)...")
    success, failed = 0, []

    for i, comment in enumerate(to_process, 1):
        fullname = extract_comment_id(comment["url"])
        if not fullname:
            failed.append((comment.get("preview", "?")[:50], "could not parse ID"))
            continue

        try:
            status = save_item(page, fullname, modhash)
            if status == 200:
                success += 1
                state["saved_comments"].append(comment["url"])
                save_state(target_folder, state)
            else:
                failed.append((comment.get("preview", "?")[:50], f"HTTP {status}"))
        except Exception as e:
            failed.append((comment.get("preview", "?")[:50], str(e)))

        if i % 10 == 0:
            print(f"   ... {i}/{len(to_process)}")
            time.sleep(6)
        else:
            time.sleep(2.5)

    print(f"   ✅ Saved: {success}")
    if failed:
        print(f"   ⚠️  Failed: {len(failed)}")
        for preview, err in failed[:10]:
            print(f"      {preview}: {err}")
    print()


def main():
    print("\n📥 Reddit Data Importer\n")

    data, target_folder = load_export()
    state = load_state(target_folder)

    # Calculate remaining
    remaining_subs = len([s for s in data.get('subreddits', []) if s not in state['subreddits']])
    remaining_posts = len([p for p in data.get('saved_posts', []) if p['url'] not in state['saved_posts']])
    remaining_comments = len([c for c in data.get('saved_comments', []) if c['url'] not in state['saved_comments']])

    print("This will process:")
    print(f"  • Subscribe to {remaining_subs} subreddits (skipped {len(data.get('subreddits', [])) - remaining_subs})")
    print(f"  • Save {remaining_posts} posts (skipped {len(data.get('saved_posts', [])) - remaining_posts})")
    print(f"  • Save {remaining_comments} comments (skipped {len(data.get('saved_comments', [])) - remaining_comments})")
    print()
    if remaining_subs + remaining_posts + remaining_comments == 0:
        print("🎉 Everything is already synced! Exiting.")
        sys.exit(0)
        
    confirm = input("Continue? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        sys.exit(0)
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        login(context, page)

        modhash = get_modhash(page)
        if not modhash:
            print("❌ Could not get modhash token. Login may have failed.")
            sys.exit(1)

        subscribe_to_subreddits(page, data.get("subreddits", []), modhash, target_folder, state)
        save_posts(page, data.get("saved_posts", []), modhash, target_folder, state)
        save_comments(page, data.get("saved_comments", []), modhash, target_folder, state)

        browser.close()

    print("🎉 Import complete!\n")


if __name__ == "__main__":
    main()
