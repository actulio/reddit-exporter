from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://www.reddit.com/login/")
    page.wait_for_load_state("networkidle")
    print("Page URL:", page.url)
    
    # Check if login is in an iframe
    for frame in page.frames:
        inputs = frame.locator("input").element_handles()
        print(f"Frame URL: {frame.url}, Found {len(inputs)} inputs")
        for inp in inputs:
            print("  - Input type:", inp.get_attribute("type"), "name:", inp.get_attribute("name"), "id:", inp.get_attribute("id"))
        
        buttons = frame.locator("button").element_handles()
        print(f"Frame URL: {frame.url}, Found {len(buttons)} buttons")
        for btn in buttons:
            print("  - Button type:", btn.get_attribute("type"), "text:", btn.inner_text())

    browser.close()
