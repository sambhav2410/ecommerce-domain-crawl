import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

class URLProcessor:
    def __init__(self):
        """
        Initialize the URL processor with patterns to identify product pages.
        """
        self.product_url_patterns = [
            r'/product[s]?/[\w-]+', 
            r'/p/[\w-]+',
            r'/item[s]?/[\w-]+',
            r'/pd/[\w-]+',
            r'/[\w|-]+/[\w|-]+/[\w|-]+-\d+', # For products with hyphenated names and IDs
            r'/[\w|-]+/[\w|-]+/[\w|\s|-]+',  # More flexible pattern for product paths
            r'/[\w|-]+-[\w|-]+-[\w|-]+', 
            r'/buy/[\w-]+',
            r'/dp/[\w-]+',
            r'/[\w-]+/[\w-]+/[\w-]+-\d+/buy$',  # Main Myntra product URL pattern
            r'/[\w-]+/[\w-]+/[\w-]+-\d+',
            r'/[\w-]+/[\w-]+/[\w-]+',
            r'/[\w-]+/[\w-]+',
            r'/pr/'
            r'/shop/[\w-]+',
            r'productdetails?/', 
            r'product-detail/',
            r'product\.php\?id=',
            r'pid=',
            r'prodid=',
            r'product_id=',
            r'productID='
        ]
        self.product_regex = re.compile('|'.join(self.product_url_patterns), re.IGNORECASE)
        
        # Category patterns to explicitly exclude
        self.category_patterns = [
            r'myntra\.com/[\w-]+$',                    # Single-level category (e.g., /women-accessories)
            r'nykaafashion\.com/[\w-]+/c/\d+$',        # Nykaa category pages
            r'/shop/[\w-]+$',                          # Generic shop category
            r'/category/[\w-]+$',                      # Generic category
            r'/collection[s]?/[\w-]+$',                # Generic collection
        ]
        self.category_regex = re.compile('|'.join(self.category_patterns), re.IGNORECASE)
        
        # Product indicators in HTML - enhanced for Myntra
        self.product_indicators = [
            "pdp-name",                # Myntra product name class
            "pdp-price",               # Myntra price class
            "pdp-product-description", # Myntra description
            "size-buttons-container",  # Myntra size selection
            "product-details",
            "product-page",
            "pdp-container",
            "pdp-wrapper",
            "product-description",
            "product_details",
            "productDetails",
            "add-to-cart",
            "addToCart",
            "add_to_cart",
            "buy-now",
            "buyNow",
            "product-title",
            "product-name",
            "product-info",
            "product-details-section",
            "product-description-container",
            "size-chart",
        ]
        
        # Price patterns that indicate a product page
        self.price_patterns = [
            r'₹\s*[\d,]+',               # Indian Rupee format
            r'Rs\.?\s*[\d,]+',           # Rs. format
            r'INR\s*[\d,]+',             # INR format
            r'MRP\.?:?\s*[\d,]+',        # MRP format
            r'price["\':\s]+[\d,]+',     # price attributes
            r'data-price=["\':][\d,]+'   # data price attributes
        ]
        self.price_regex = re.compile('|'.join(self.price_patterns), re.IGNORECASE)
        
    def is_product_page(self, url, soup):
        """
        Determine if a URL represents a product page.
        
        Args:
            url: URL to check
            soup: BeautifulSoup object of the page
            
        Returns:
            Boolean indicating if the URL is a product page
        """
        # First, explicitly exclude category pages
        if self.category_regex.search(url) and not url.lower().endswith(('/buy', '/p', '/product')):
            return False
            
        # Check URL pattern for product URLs (most reliable method)
        if self.product_regex.search(url):
            # For Myntra, confirm with additional checks if available
            if 'myntra.com' in url and '/buy' in url:
                return True
            return True
        
        # Special handling for Myntra
        if 'myntra.com' in url:
            # Myntra product URLs must end with /buy
            if not url.endswith('/buy'):
                return False
                
            # Check for product ID pattern in URL
            product_id_match = re.search(r'/(\d+)/buy$', url)
            if product_id_match:
                return True
        
        # Check HTML content for product indicators
        html_str = str(soup)
        
        # Look for product indicators in classes and IDs
        for indicator in self.product_indicators:
            if f'class="{indicator}"' in html_str or f'id="{indicator}"' in html_str:
                # For confirmed product indicator, double check it's not a category with many products
                # Count product cards/items - if many, it's likely a category page
                product_cards = len(soup.find_all('div', class_=re.compile(r'product-card|product-item')))
                if product_cards > 5:  # If more than 5 product cards, likely a category page
                    return False
                return True
        
        # Check for specific Myntra product page elements
        if 'myntra.com' in url:
            # Look for size selector - strong indicator of product page
            size_buttons = soup.find('div', class_=re.compile(r'size-buttons-container'))
            if size_buttons:
                return True
                
            # Look for "ADD TO BAG" button - Myntra specific
            add_to_bag = soup.find('span', string=re.compile(r'ADD TO BAG', re.I))
            if add_to_bag:
                return True
                
            # Look for product rating - often on product pages
            ratings = soup.find('div', class_=re.compile(r'rating'))
            if ratings:
                # Make sure we don't have multiple product cards (category page)
                product_cards = len(soup.find_all('div', class_=re.compile(r'product-card|product-item')))
                if product_cards <= 3:  # Low number of product cards is OK (could be similar products)
                    return True
        
        # Look for price patterns as a last resort
        if self.price_regex.search(html_str):
            # Additional verification: Check that this isn't a category page with prices
            # Count how many price instances we have - category pages have many
            price_matches = len(re.findall(self.price_regex, html_str))
            if price_matches < 5:  # If less than 5 price mentions, likely a product page
                # Check for structured data that indicates a product
                scripts = soup.find_all('script', {'type': 'application/ld+json'})
                for script in scripts:
                    if script.string and '"@type":"Product"' in script.string:
                        return True
                
                # Look for common product page elements as final check
                add_to_cart = soup.find(['button', 'a'], string=re.compile(r'add.*cart|buy.*now', re.I))
                if add_to_cart:
                    return True
                    
        return False

