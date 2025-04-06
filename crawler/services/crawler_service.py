# Modified crawler/services/crawler_service.py
import asyncio
import logging
import time
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup
from django.utils import timezone
from tqdm import tqdm
from asgiref.sync import sync_to_async

from crawler.models import Domain, ProductUrl
from crawler.services.url_extractor import URLExtractor
from crawler.services.url_processor import URLProcessor

logger = logging.getLogger(__name__)

class CrawlerService:
    def __init__(self, max_urls_per_domain=5000, max_concurrent_requests=10, request_delay=0.1):
        """
        Initialize the crawler service with configurable parameters.
        
        Args:
            max_urls_per_domain: Maximum number of URLs to crawl per domain
            max_concurrent_requests: Maximum number of concurrent requests
            request_delay: Delay between requests to the same domain (in seconds)
        """
        self.max_urls_per_domain = max_urls_per_domain
        self.max_concurrent_requests = max_concurrent_requests
        self.request_delay = request_delay
        self.url_extractor = URLExtractor()
        self.url_processor = URLProcessor()
        
        # Add browser-like headers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }
        
        # Track rate limits per domain
        self.domain_last_request = {}
    
    @sync_to_async
    def get_or_create_domain(self, domain_url):
        """
        Get or create a domain object (synchronous operation wrapped with sync_to_async).
        """
        domain_name = urlparse(domain_url).netloc
        domain, created = Domain.objects.get_or_create(
            url=domain_url,
            defaults={'name': domain_name}
        )
        return domain
    
    @sync_to_async
    def delete_product_urls(self, domain):
        """
        Delete product URLs for a domain (synchronous operation wrapped with sync_to_async).
        """
        ProductUrl.objects.filter(domain=domain).delete()
    
    @sync_to_async
    def save_product_urls(self, domain, product_urls):
        """
        Save product URLs to database (synchronous operation wrapped with sync_to_async).
        """
        product_url_objects = []
        for url in product_urls:
            product_url_objects.append(ProductUrl(domain=domain, url=url))
        
        # Bulk create product URLs for better performance
        ProductUrl.objects.bulk_create(product_url_objects, ignore_conflicts=True)
    
    @sync_to_async
    def update_domain_timestamp(self, domain):
        """
        Update domain's last_crawled timestamp (synchronous operation wrapped with sync_to_async).
        """
        domain.last_crawled = timezone.now()
        domain.save()

    async def process_url(self, url, domain_url, visited, to_visit, product_urls, session, semaphore):
        """
        Process a single URL: fetch its content, extract links, and identify product URLs.
        
        Args:
            url: URL to process
            domain_url: Base domain URL
            visited: Set of already visited URLs
            to_visit: Set of URLs to visit
            product_urls: Set of found product URLs
            session: aiohttp ClientSession
            semaphore: Semaphore to limit concurrent requests
        """
        # Mark URL as visited
        visited.add(url)
        
        try:
            # Respect rate limiting with semaphore
            async with semaphore:
                # Add adaptive delay based on domain
                domain_name = urlparse(domain_url).netloc
                current_time = time.time()
                last_request_time = self.domain_last_request.get(domain_name, 0)
                time_since_last_request = current_time - last_request_time
                
                # Implement adaptive delay
                delay = self.request_delay
                if domain_name in ['myntra.com', 'nykaafashion.com', 'nykaa.com']:
                    delay = max(0.5, delay)  # Longer delay for sites with anti-scraping
                
                if time_since_last_request < delay:
                    await asyncio.sleep(delay - time_since_last_request)
                
                self.domain_last_request[domain_name] = time.time()
                
                # Fetch URL content with enhanced headers
                try:
                    async with session.get(url, headers=self.headers, allow_redirects=True, timeout=30) as response:
                        if response.status != 200:
                            # Handle 429 Too Many Requests specifically
                            if response.status == 429:
                                logger.warning(f"Rate limited on {domain_name}, adding longer delay")
                                self.domain_last_request[domain_name] = time.time() + 5  # Add 5 second penalty
                                # Put URL back in to_visit to retry later
                                to_visit.add(url)
                                visited.remove(url)
                                return
                            logger.debug(f"Non-200 status code {response.status} for URL: {url}")
                            return
                        
                        content_type = response.headers.get('Content-Type', '')
                        if 'text/html' not in content_type and 'application/json' not in content_type:
                            return
                        
                        try:
                            html = await response.text()
                        except UnicodeDecodeError:
                            html = await response.read()
                            html = html.decode('utf-8', errors='ignore')
                except aiohttp.ClientError as e:
                    logger.warning(f"Client error for {url}: {e}")
                    return
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout for {url}")
                    return
        
            # Parse HTML
            try:
                soup = BeautifulSoup(html, 'lxml')
            except Exception as e:
                logger.error(f"Error parsing HTML from {url}: {e}")
                return
            
            # Process this URL to check if it's a product page
            if self.url_processor.is_product_page(url, soup):
                logger.info(f"Found product URL: {url}")
                product_urls.add(url)
            
            # Extract links from the page
            links = self.url_extractor.extract_links(soup, url, domain_url)
            
            # Add new links to visit
            for link in links:
                if link not in visited:
                    to_visit.add(link)
                    
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")

    async def crawl_domain(self, domain_url):
        """
        Crawl a single domain to find product URLs.
        
        Args:
            domain_url: The domain URL to crawl
            
        Returns:
            List of product URLs found on the domain
        """
        domain = await self.get_or_create_domain(domain_url)
        domain_name = urlparse(domain_url).netloc
        
        # Initialize sets to track URLs
        to_visit = {domain_url}
        visited = set()
        product_urls = set()
        
        # Add category and product listing pages for common e-commerce sites
        if 'myntra.com' in domain_name:
            to_visit.update([
                'https://www.myntra.com/shop/men',
                'https://www.myntra.com/shop/women',
                'https://www.myntra.com/shop/kids',
                'https://www.myntra.com/shop/home-living'
            ])
        elif 'nykaafashion.com' in domain_name or 'nykaa.com' in domain_name:
            to_visit.update([
                'https://www.nykaafashion.com/women/c/5',
                'https://www.nykaafashion.com/men/c/6',
                'https://www.nykaafashion.com/kids/c/4054',
                'https://www.nykaafashion.com/home/c/5942'
            ])
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        # Create a shared session with cookies support and increased timeout
        timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)
        
        conn = aiohttp.TCPConnector(ssl=False, limit=self.max_concurrent_requests)
        async with aiohttp.ClientSession(
            headers=self.headers,
            timeout=timeout,
            connector=conn,
            cookie_jar=aiohttp.CookieJar()
        ) as session:
            
            # Process URLs until we've visited all URLs or reached the limit
            pbar = tqdm(total=self.max_urls_per_domain, desc=f"Crawling {domain_name}")
            
            while to_visit and len(visited) < self.max_urls_per_domain:
                # Get next batch of URLs to visit (limited by max_concurrent_requests)
                current_batch = set()
                while to_visit and len(current_batch) < self.max_concurrent_requests:
                    if not to_visit:
                        break
                    url = to_visit.pop()
                    if url not in visited:
                        current_batch.add(url)
                
                if not current_batch:
                    break
                
                # Create tasks for the current batch
                tasks = [self.process_url(url, domain_url, visited, to_visit, product_urls, session, semaphore) 
                         for url in current_batch]
                
                # Execute tasks for the current batch
                await asyncio.gather(*tasks)
                
                # Update progress bar
                pbar.update(len(current_batch))
                
                # Log progress
                logger.info(f"Progress: {len(visited)} URLs visited, {len(product_urls)} product URLs found")
            
            pbar.close()
        
        # Update domain's last_crawled timestamp
        await self.update_domain_timestamp(domain)
        
        # Save product URLs to database
        await self.save_product_urls(domain, product_urls)
        
        logger.info(f"Completed crawling {domain_name}. Found {len(product_urls)} product URLs out of {len(visited)} visited.")
        
        return list(product_urls)
        
    

# Modified crawler/management/commands/crawl_sites.py
import asyncio
import json
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from asgiref.sync import sync_to_async

from crawler.services.crawler_service import CrawlerService
from crawler.models import Domain, ProductUrl

class Command(BaseCommand):
    help = 'Crawl e-commerce websites to discover product URLs'
    
    def add_arguments(self, parser):
        parser.add_argument('--domains', nargs='+', type=str, 
                            help='List of domains to crawl. If not provided, will use domains from DB or default list.')
        parser.add_argument('--output', type=str, default='product_urls.json',
                            help='Output file path to save discovered product URLs')
        parser.add_argument('--max-urls', type=int, default=5000,
                            help='Maximum number of URLs to crawl per domain')
        parser.add_argument('--concurrency', type=int, default=10,
                            help='Maximum number of concurrent requests')
        parser.add_argument('--delay', type=float, default=0.1,
                            help='Delay between requests to the same domain (seconds)')
    
    @sync_to_async
    def get_domains_from_db(self):
        db_domains = list(Domain.objects.all().values_list('url', flat=True))
        return db_domains
                            
    def handle(self, *args, **options):
        # Get domains to crawl
        domains = options.get('domains')
        if not domains:
            # Check if we have domains in the database
            try:
                # Use asyncio for getting domains from DB
                db_domains = asyncio.run(self.get_domains_from_db())
                if db_domains:
                    domains = db_domains
                else:
                    # Default domains from the problem statement
                    domains = [
                        'https://www.virgio.com/',
                        # 'https://www.tatacliq.com/',
                        # 'https://nykaafashion.com/',
                        # 'https://www.westside.com/'
                    ]
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error fetching domains from database: {e}"))
                # Default domains as fallback
                domains = [
                    'https://www.virgio.com/',
                    # 'https://www.tatacliq.com/',
                    # 'https://nykaafashion.com/',
                    # 'https://www.westside.com/'
                ]
        
        # Configure crawler
        crawler = CrawlerService(
            max_urls_per_domain=options['max_urls'],
            max_concurrent_requests=options['concurrency'],
            request_delay=options['delay']
        )
        
        # Run crawler and get results
        self.stdout.write(f"Starting crawl for {len(domains)} domains at {timezone.now()}")
        start_time = timezone.now()
        
        # Use asyncio to run the crawl
        results = asyncio.run(crawler.crawl_domains(domains))
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        # Output summary
        total_products = sum(len(urls) for urls in results.values())
        self.stdout.write(self.style.SUCCESS(
            f"Crawl completed in {duration:.2f} seconds. "
            f"Found {total_products} product URLs across {len(domains)} domains."
        ))
        
        # Save results to file
        with open(options['output'], 'w') as f:
            json.dump(results, f, indent=2)
            
        self.stdout.write(f"Results saved to {options['output']}")