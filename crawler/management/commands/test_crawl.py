from django.core.management.base import BaseCommand
from crawler.tasks import crawl_all_domains_task, crawl_domain_task

class Command(BaseCommand):
    help = 'Start a crawling job using Celery'
    
    def add_arguments(self, parser):
        parser.add_argument('--domains', nargs='+', type=str, 
                            help='List of domains to crawl. If not provided, will use default list.')
        parser.add_argument('--output', type=str, default='product_urls.json',
                            help='Output file path to save discovered product URLs')
        parser.add_argument('--max-urls', type=int, default=5000,
                            help='Maximum number of URLs to crawl per domain')
        parser.add_argument('--concurrency', type=int, default=10,
                            help='Maximum number of concurrent requests')
        parser.add_argument('--delay', type=float, default=0.1,
                            help='Delay between requests to the same domain (seconds)')
        parser.add_argument('--single', type=str, default=None,
                            help='Crawl a single domain instead of all domains')
    
    def handle(self, *args, **options):
        if options['single']:
            domain = options['single']
            self.stdout.write(f"Starting Celery task to crawl: {domain}")
            task = crawl_domain_task.delay(
                domain,
                max_urls=options['max_urls'],
                concurrency=options['concurrency'],
                delay=options['delay'],
                output_file=options['output']  # Pass this!
            )
            self.stdout.write(self.style.SUCCESS(f"Task started with ID: {task.id}"))
        else:
            # Crawl all domains
            domains = options['domains']
            self.stdout.write(f"Starting Celery task to crawl multiple domains")
            task = crawl_all_domains_task.delay(
                domains=domains,
                max_urls=options['max_urls'],
                concurrency=options['concurrency'],
                delay=options['delay'],
                output_file=options['output']
            )
            self.stdout.write(self.style.SUCCESS(f"Task started with ID: {task.id}"))
