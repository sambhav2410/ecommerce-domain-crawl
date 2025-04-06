import asyncio
import json
import logging
from celery import shared_task
from django.utils import timezone
from asgiref.sync import async_to_sync

from crawler.services.crawler_service import CrawlerService
from crawler.models import Domain, CrawlJob

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def crawl_domain_task(self, domain_url, max_urls=5000, concurrency=10, delay=0.1,output_file="product_urls.json"):
    """
    Celery task to crawl a single domain
    """
    logger.info(f"Starting crawl for domain: {domain_url}")
    
    # Update job status
    job, created = CrawlJob.objects.get_or_create(
        domain_url=domain_url,
        defaults={
            'status': 'RUNNING',
            'task_id': self.request.id
        }
    )
    if not created:
        job.status = 'RUNNING'
        job.task_id = self.request.id
        job.start_time = timezone.now()
        job.save()
    
    # Configure crawler
    crawler = CrawlerService(
        max_urls_per_domain=max_urls,
        max_concurrent_requests=concurrency,
        request_delay=delay
    )
    
    try:
        # Run the crawler asynchronously
        start_time = timezone.now()
        
        # Use async_to_sync to run our async crawl_domain function
        product_urls = async_to_sync(crawler.crawl_domain)(domain_url)
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        # Use asyncio to run the crawl
        # results = asyncio.run(crawler.crawl_domains(domain_url))
        if output_file:
            try:
                with open(output_file, "w") as f:
                    json.dump(product_urls, f, indent=2)
            except Exception as e:
                print(f"Error saving to {output_file}: {e}")
        
        # Update job status
        job.status = 'COMPLETED'
        job.end_time = end_time
        job.duration = duration
        job.urls_found = len(product_urls)
        job.save()
        
        logger.info(f"Crawl completed for {domain_url}: Found {len(product_urls)} product URLs in {duration:.2f} seconds")
        
        # Return results
        # return {
        #     'domain': domain_url,
        #     'product_urls_count': len(product_urls),
        #     'duration': duration
        # }
        return {"status": "completed", "total_urls": len(product_urls),"product_urls": product_urls}
    
    except Exception as e:
        # Update job status on error
        job.status = 'FAILED'
        job.end_time = timezone.now()
        job.error_message = str(e)
        job.save()
        
        logger.error(f"Error crawling {domain_url}: {str(e)}")
        raise

@shared_task(bind=True)
def crawl_all_domains_task(self, domains=None, max_urls=5000, concurrency=10, delay=0.1, output_file='product_urls.json'):
    """
    Celery task to crawl multiple domains and combine results
    """
    logger.info(f"Starting crawl for multiple domains: {domains}")
    
    if not domains:
        # Use default domains if none provided
        domains = [
            'https://www.virgio.com/',
            'https://www.tatacliq.com/',
            'https://nykaafashion.com/',
            'https://www.westside.com/'
        ]
    
    # Create individual tasks for each domain
    results = {}
    task_ids = []
    
    for domain in domains:
        task = crawl_domain_task.delay(domain, max_urls, concurrency, delay)
        task_ids.append(task.id)
    
    # Return task group information
    return {
        'message': f'Started crawling {len(domains)} domains',
        'domains': domains,
        'task_ids': task_ids
    }


@shared_task
def crawl_domain_in_batches_task(domain, max_urls, batch_size=500, concurrency=10, delay=0.1):
    crawler = CrawlerService(
        max_urls_per_domain=max_urls,
        max_concurrent_requests=concurrency,
        request_delay=delay
    )
    
    product_urls = async_to_sync(crawler.crawl_domain)(domain)
    output_file = f"product_urls.json"
    try:
        with open(output_file, "w") as f:
            json.dump(product_urls, f, indent=2)
    except Exception as e:
        print(f"Error saving to {output_file}: {e}")

    return {"status": "completed", "total_urls": len(product_urls),"product_urls": product_urls}