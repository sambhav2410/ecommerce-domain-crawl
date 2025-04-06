from django.db import models

class Domain(models.Model):
    url = models.URLField(max_length=255, unique=True)
    name = models.CharField(max_length=100,null=True,blank=True)
    last_crawled = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.name

class ProductUrl(models.Model):
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='product_urls')
    url = models.URLField(max_length=1024)
    discovered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('domain', 'url')
    
    def __str__(self):
        return self.url


class CrawlJob(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    )
    
    domain_url = models.CharField(max_length=255)
    task_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True)
    urls_found = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.domain_url} - {self.status}"