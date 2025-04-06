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