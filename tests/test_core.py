import unittest
from unittest.mock import AsyncMock, patch

from scrapers.base_scraper import BaseScraper
from scrapers.amazon_scraper import AmazonScraper
from scrapers.ajio_scraper import AjioScraper
from scrapers.flipkart_scraper import FlipkartScraper
from scrapers.myntra_scraper import MyntraScraper
from scrapers.nykaa_scraper import NykaaScraper
from scrapers.snapdeal_scraper import SnapdealScraper
from scrapers.shopclues_scraper import ShopcluesScraper
from scrapers.scraper_factory import ScraperFactory


class DemoScraper(BaseScraper):
    def get_site_name(self) -> str:
        return 'demo'


class FakeElement:
    def __init__(self, text='', attrs=None):
        self.text = text
        self.attrs = attrs or {}


class FakeBrowser:
    def __init__(self, elements, content=''):
        self.elements = elements
        self.content = content

    async def query_selector_all(self, selector):
        return self.elements.get(selector, [])

    async def get_text(self, element):
        return element.text

    async def get_inner_text(self, element):
        return element.text

    async def get_attribute(self, element, attr):
        return element.attrs.get(attr)

    async def evaluate_handle(self, element, js_expression):
        return None

    async def get_page_content(self):
        return self.content


class ScraperCoreTests(unittest.IsolatedAsyncioTestCase):
    def test_hygulife_selectors_are_injected(self):
        scraper = ScraperFactory.get_scraper('https://www.hygulife.com/products/demo')

        self.assertEqual(scraper.get_site_name(), 'hygulife')
        self.assertTrue(scraper.site_selectors.get('price_selectors'))
        self.assertTrue(scraper.site_selectors.get('original_price_selectors'))

    def test_redirect_destination_url_is_unwrapped_for_identification(self):
        url = (
            'https://linkredirect.in/visitretailer/2656?'
            'dl=https%3A%2F%2Fwww.nykaa.com%2Fdemo-product%2Fp%2F123'
        )

        self.assertEqual(
            ScraperFactory.unwrap_destination_url(url),
            'https://www.nykaa.com/demo-product/p/123'
        )
        self.assertEqual(ScraperFactory.identify_site(url), 'nykaa')

    async def test_extract_original_price_prefers_value_above_current_price(self):
        scraper = DemoScraper({'original_price_selectors': ['.mrp']})
        browser = FakeBrowser({
            '.mrp': [
                FakeElement('MRP ₹1,299'),
                FakeElement('Now ₹999'),
            ]
        })

        self.assertEqual(await scraper.extract_original_price(browser, '999'), '1,299')

    def test_pick_original_price_ignores_duplicate_current_price(self):
        scraper = DemoScraper({})

        self.assertIsNone(scraper.pick_original_price(['999'], '999'))
        self.assertEqual(scraper.pick_original_price(['999', '1299'], '999'), '1299')

    def test_clean_price_removes_dangling_punctuation(self):
        scraper = DemoScraper({})

        self.assertEqual(scraper.clean_price('₹231,'), '231')
        self.assertEqual(scraper.clean_price('₹5,682.00'), '5,682.00')

    def test_extract_original_price_candidates_from_content(self):
        scraper = DemoScraper({})
        content = '''
            <div>MRP ₹1,499</div>
            <script>{"strikeOffPrice":"999","maximumRetailPrice":"2,499"}</script>
        '''

        self.assertEqual(
            scraper.pick_original_price(
                scraper.extract_original_price_candidates_from_content(content),
                '999'
            ),
            '1,499'
        )

    async def test_amazon_apex_price_and_mrp_selectors(self):
        scraper = AmazonScraper({
            'product_detail': {
                'price': {
                    'apex_accessibility_label': '#apex-pricetopay-accessibility-label'
                }
            },
            'original_price_selectors': ['.basisPrice .aok-offscreen']
        })
        browser = FakeBrowser({
            '#apex-pricetopay-accessibility-label': [
                FakeElement('₹799.00 with 81 percent savings')
            ],
            '.basisPrice .aok-offscreen': [
                FakeElement('M.R.P.: ₹4,299.00')
            ],
        })

        price = await scraper.extract_price(browser)
        original_price = await scraper.extract_original_price(browser, price)

        self.assertEqual(price, '799.00')
        self.assertEqual(original_price, '4,299.00')

    async def test_flipkart_strikethrough_original_price_selector(self):
        scraper = FlipkartScraper({
            'original_price_selectors': [
                '.v1zwn21m',
                "[style*='text-decoration-line:line-through']"
            ]
        })
        browser = FakeBrowser({
            '.v1zwn21m': [
                FakeElement('799')
            ],
            "[style*='text-decoration-line:line-through']": []
        })

        self.assertEqual(await scraper.extract_original_price(browser, '130'), '799')

    async def test_flipkart_css_price_fallback_prefers_sale_price(self):
        scraper = FlipkartScraper({
            'price_selectors': ['._1psv1zeb9']
        })
        browser = FakeBrowser({
            'script[type="application/ld+json"]': [],
            '._1psv1zeb9': [
                FakeElement('₹799'),
                FakeElement('₹130')
            ],
        })

        with patch('scrapers.flipkart_scraper.asyncio.sleep', AsyncMock()):
            self.assertEqual(await scraper.extract_price(browser), '130')

    async def test_flipkart_page_source_jsonld_beats_plain_css_numbers(self):
        scraper = FlipkartScraper({
            'price_selectors': ['.v1zwn21l']
        })
        content = '''
            <script type="application/ld+json">
            [{"@type":"Product","offers":{"price":130,"priceCurrency":"INR"}}]
            </script>
        '''
        browser = FakeBrowser({
            'script[type="application/ld+json"]': [],
            '.v1zwn21l': [
                FakeElement('10'),
                FakeElement('Buy at ₹130')
            ],
        }, content=content)

        with patch('scrapers.flipkart_scraper.asyncio.sleep', AsyncMock()):
            self.assertEqual(await scraper.extract_price(browser), '130')

    async def test_flipkart_original_price_from_product_pricing_payload(self):
        scraper = FlipkartScraper({
            'original_price_selectors': ['.missing-mrp']
        })
        browser = FakeBrowser({
            '.missing-mrp': [],
        }, content='''
            <script>
            {"ppd":{"fsp":173,"finalPrice":173,"mrp":175,"specialPrice":true}}
            </script>
        ''')

        self.assertEqual(await scraper.extract_original_price(browser, '173'), '175')

    async def test_flipkart_page_source_original_price_rejects_distant_payload(self):
        scraper = FlipkartScraper({
            'original_price_selectors': ['.missing-mrp']
        })
        browser = FakeBrowser({
            '.missing-mrp': [],
        }, content='''
            <script>
            {"ppd":{"fsp":173,"finalPrice":173,"mrp":1596,"specialPrice":true}}
            </script>
        ''')

        self.assertIsNone(await scraper.extract_original_price(browser, '173'))

    async def test_nykaa_not_found_page_ignores_promotional_rupee_values(self):
        scraper = NykaaScraper({})
        browser = FakeBrowser({}, content='''
            {"dataLayer":{"pageName":"NotFound"},"productPage":{
            "isFetchingError":true,"product":null}}
            <script>window.spin = "Play now to win a ₹5000 Nykaa voucher."</script>
        ''')

        self.assertIsNone(await scraper.extract_price(browser))

    async def test_nykaa_original_price_from_mrp_selector(self):
        scraper = NykaaScraper({
            'original_price_selectors': ['.css-u05rr']
        })
        browser = FakeBrowser({
            '.css-u05rr': [
                FakeElement('MRP: ₹325')
            ],
        })

        self.assertEqual(await scraper.extract_original_price(browser, '125'), '325')

    async def test_myntra_original_price_from_pdp_mrp_selector(self):
        scraper = MyntraScraper({
            'original_price_selectors': ['.pdp-mrp']
        })
        browser = FakeBrowser({
            '.pdp-mrp': [
                FakeElement('MRP ₹429')
            ],
        })

        self.assertEqual(await scraper.extract_original_price(browser, '359'), '429')

    async def test_ajio_price_and_original_price_selectors(self):
        scraper = AjioScraper({
            'price_selectors': ['.prod-sp'],
            'original_price_selectors': ['.prod-cp']
        })
        browser = FakeBrowser({
            '.prod-sp': [
                FakeElement('₹499')
            ],
            '.prod-cp': [
                FakeElement('MRP ₹1,999')
            ],
        })

        with patch('scrapers.ajio_scraper.asyncio.sleep', AsyncMock()):
            price = await scraper.extract_price(browser)
        original_price = await scraper.extract_original_price(browser, price)

        self.assertEqual(price, '499')
        self.assertEqual(original_price, '1,999')

    async def test_snapdeal_price_and_original_price_selectors(self):
        scraper = SnapdealScraper({
            'price_selectors': ['.payBlkBig'],
            'original_price_selectors': ['.pdpCutPrice']
        })
        browser = FakeBrowser({
            '.payBlkBig': [
                FakeElement('₹299')
            ],
            '.pdpCutPrice': [
                FakeElement('₹999')
            ],
        })

        with patch('scrapers.snapdeal_scraper.asyncio.sleep', AsyncMock()):
            price = await scraper.extract_price(browser)
        original_price = await scraper.extract_original_price(browser, price)

        self.assertEqual(price, '299')
        self.assertEqual(original_price, '999')

    async def test_snapdeal_does_not_treat_script_404_as_dead_page(self):
        scraper = SnapdealScraper({
            'price_selectors': ['.payBlkBig']
        })
        browser = FakeBrowser({
            '.payBlkBig': [
                FakeElement('391')
            ],
        }, content='<script>var encoded = "-1990404162";</script>')

        with patch('scrapers.snapdeal_scraper.asyncio.sleep', AsyncMock()):
            self.assertEqual(await scraper.extract_price(browser), '391')

    async def test_shopclues_price_and_original_price_selectors(self):
        scraper = ShopcluesScraper({
            'price_selectors': ['.f_price'],
            'original_price_selectors': ['#sec_list_price_', '.old_price']
        })
        browser = FakeBrowser({
            '.f_price': [
                FakeElement('₹349')
            ],
            '#sec_list_price_': [
                FakeElement('MRP:₹899', attrs={'content': '899'})
            ],
            '.old_price': [
                FakeElement('')
            ],
        })

        price = await scraper.extract_price(browser)
        original_price = await scraper.extract_original_price(browser, price)

        self.assertEqual(price, '349')
        self.assertEqual(original_price, '899')


if __name__ == '__main__':
    unittest.main()
