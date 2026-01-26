"""
Connector Registry
Maps site names to their Playwright and Selenium connector classes.
Every site has BOTH a Playwright and Selenium connector.
"""

from .amazon_playwright import AmazonPlaywrightConnector
from .amazon_selenium import AmazonSeleniumConnector
from .flipkart_playwright import FlipkartPlaywrightConnector
from .flipkart_selenium import FlipkartSeleniumConnector
from .myntra_playwright import MyntraPlaywrightConnector
from .myntra_selenium import MyntraSeleniumConnector
from .nykaa_playwright import NykaaPlaywrightConnector
from .nykaa_selenium import NykaaSeleniumConnector
from .ajio_playwright import AjioPlaywrightConnector
from .ajio_selenium import AjioSeleniumConnector
from .meesho_playwright import MeeshoPlaywrightConnector
from .meesho_selenium import MeeshoSeleniumConnector
from .snapdeal_playwright import SnapdealPlaywrightConnector
from .snapdeal_selenium import SnapdealSeleniumConnector
from .shopclues_playwright import ShopcluesPlaywrightConnector
from .shopclues_selenium import ShopcluesSeleniumConnector
from .hyugalife_playwright import HyugalifePlaywrightConnector
from .hyugalife_selenium import HyugalifeSeleniumConnector


# Playwright connector registry
PLAYWRIGHT_CONNECTORS = {
    'amazon': AmazonPlaywrightConnector,
    'flipkart': FlipkartPlaywrightConnector,
    'myntra': MyntraPlaywrightConnector,
    'nykaa': NykaaPlaywrightConnector,
    'ajio': AjioPlaywrightConnector,
    'meesho': MeeshoPlaywrightConnector,
    'snapdeal': SnapdealPlaywrightConnector,
    'shopclues': ShopcluesPlaywrightConnector,
    'hyugalife': HyugalifePlaywrightConnector,
}

# Selenium connector registry
SELENIUM_CONNECTORS = {
    'amazon': AmazonSeleniumConnector,
    'flipkart': FlipkartSeleniumConnector,
    'myntra': MyntraSeleniumConnector,
    'nykaa': NykaaSeleniumConnector,
    'ajio': AjioSeleniumConnector,
    'meesho': MeeshoSeleniumConnector,
    'snapdeal': SnapdealSeleniumConnector,
    'shopclues': ShopcluesSeleniumConnector,
    'hyugalife': HyugalifeSeleniumConnector,
}

# For backward compatibility - defaults to Playwright
CONNECTORS = PLAYWRIGHT_CONNECTORS


def get_connector(site_name: str, method: str = 'playwright'):
    """
    Get connector instance for a given site name and method.
    
    Args:
        site_name: Name of the e-commerce site (lowercase)
        method: 'playwright' or 'selenium'
        
    Returns:
        Connector instance or None if not found
    """
    if method == 'selenium':
        connector_class = SELENIUM_CONNECTORS.get(site_name.lower())
    else:
        connector_class = PLAYWRIGHT_CONNECTORS.get(site_name.lower())
    
    if connector_class:
        return connector_class()
    return None


def get_playwright_connector(site_name: str):
    """Get Playwright connector for a site"""
    return get_connector(site_name, 'playwright')


def get_selenium_connector(site_name: str):
    """Get Selenium connector for a site"""
    return get_connector(site_name, 'selenium')
