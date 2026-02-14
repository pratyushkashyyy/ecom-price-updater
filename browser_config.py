"""
Enhanced anti-bot configuration for Playwright and Selenium.
Helps bypass Amazon, Flipkart, and other aggressive bot detection.
"""

# Playwright browser arguments to mask automation
PLAYWRIGHT_ARGS = [
    "--start-maximized",
    "--disable-blink-features=AutomationControlled",  # Hide automation
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-site-isolation-trials",
    "--disable-features=BlockInsecurePrivateNetworkRequests",
]

# Selenium Chrome options
SELENIUM_ARGS = [
    "--start-maximized",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-web-security",
]

# Playwright context options (realistic browser fingerprint)
PLAYWRIGHT_CONTEXT_OPTIONS = {
    "locale": "en-IN",
    "timezone_id": "Asia/Kolkata",
    "permissions": ["geolocation", "notifications"],
    "geolocation": {"latitude": 28.7041, "longitude": 77.1025},  # Delhi
    # "viewport": {"width": 1920, "height": 1080},
    # "screen": {"width": 1920, "height": 1080},
    "device_scale_factor": 1,
    "is_mobile": False,
    "has_touch": False,
}

# JavaScript to inject and override automation detection
STEALTH_JS = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Override Chrome runtime
window.navigator.chrome = {
    runtime: {}
};

// Override permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Override plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});

// Override languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en', 'hi']
});
"""
