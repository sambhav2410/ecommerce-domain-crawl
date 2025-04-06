import re
from urllib.parse import urljoin, urlparse

class URLExtractor:
    def __init__(self):
        """
        Initialize the URL extractor with regex patterns for priority URLs.
        """
        # Patterns that likely lead to product pages
        self.priority_patterns = [
            # Generic patterns
            r'/product[s]?/[\w-]+',
            r'/item[s]?/[\w-]+',
            r'/p/[\w-]+',
            r'/buy/[\w-]+',
            r'/pd/[\w-]+',
            r'/dp/[\w-]+',
            r'/pr/[\w-]+',
            # Myntra specific patterns
            r'/[\w-]+/[\w-]+/[\w-]+-\d+/buy$',  # Main Myntra product URL patter
        ]
        self.priority_regex = re.compile('|'.join(self.priority_patterns), re.IGNORECASE)
        
        # Category patterns - secondary priority
        self.category_patterns = [
            r'/[\w-]+-[\w-]+$',       # Typically category-subcategory
            r'/shop/[\w-]+$',
            r'/category/[\w-]+$',
            r'/collection[s]?/[\w-]+$'
        ]
        self.category_regex = re.compile('|'.join(self.category_patterns), re.IGNORECASE)
        
        # Patterns to exclude
        self.exclude_patterns = [
            r'\.(jpg|jpeg|png|gif|svg|webp|css|js|woff|ttf|eot|pdf|zip)($|\?)',
            r'/(cart|checkout|login|register|account|wishlist|contact|about|faq|help|search|tag)($|/|\?)',
            r'#.*$',
            r'/stores/detail',
            r'/instagram',
            r'/facebook',
            r'/twitter',
            r'/jobs',
            r'/careers',
            r'/terms',
            r'/privacy'
        ]
        self.exclude_regex = re.compile('|'.join(self.exclude_patterns), re.IGNORECASE)
    
    def extract_links(self, soup, current_url, base_domain):
        """
        Extract and process links from a BeautifulSoup object.
        
        Args:
            soup: BeautifulSoup object
            current_url: Current URL being processed
            base_domain: Base domain URL
            
        Returns:
            Set of links to be visited next, prioritized by relevance
        """
        links = set()
        base_domain_parsed = urlparse(base_domain)
        
        # Find all anchor tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '').strip()
            
            # Skip empty links
            if not href or href == '#':
                continue
                
            # Create absolute URL
            absolute_url = urljoin(current_url, href)
            
            # Parse URL
            parsed_url = urlparse(absolute_url)
            
            # Skip if URL is from a different domain
            if parsed_url.netloc != base_domain_parsed.netloc:
                continue
                
            # Skip excluded patterns
            if self.exclude_regex.search(absolute_url):
                continue
                
            # Remove fragments from URL
            clean_url = absolute_url.split('#')[0]
            
            # Add to links
            links.add(clean_url)
        
        # Sort links by priority
        # 1. Product URLs (highest priority)
        product_links = {url for url in links if self.priority_regex.search(url)}
        
        # 2. Category URLs (medium priority)
        category_links = {url for url in links if self.category_regex.search(url) and url not in product_links}
        
        # 3. Other links (lowest priority)
        other_links = links - product_links - category_links
        
        # Return combined links with priority links first
        return product_links.union(category_links).union(other_links)