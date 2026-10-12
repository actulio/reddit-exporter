const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('https://www.reddit.com/login/');
  await page.waitForLoadState('networkidle');
  const html = await page.content();
  console.log(html.substring(0, 1000));
  await browser.close();
})();
