from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import uuid
from django.shortcuts import render
from crawler.tasks import crawl_domain_in_batches_task
from crawler.models import CrawlJob, Domain, ProductUrl
from crawler.tasks import crawl_domain_task, crawl_all_domains_task
from celery.result import AsyncResult


# In-memory store just for demo purpose — consider using a DB or Redis cache for production
task_progress = {}

# @method_decorator(csrf_exempt, name='dispatch')
# class CrawlerAPIView(View):
#     def get(self, request):
#         """Get status of all crawl jobs"""
#         jobs = CrawlJob.objects.all().order_by('-start_time')
#         results = [{
#             'id': job.id,
#             'domain': job.domain_url,
#             'status': job.status,
#             'task_id': job.task_id,
#             'start_time': job.start_time,
#             'end_time': job.end_time,
#             'duration': job.duration,
#             'urls_found': job.urls_found
#         } for job in jobs[:20]]  # Limit to last 20 jobs
        
#         return JsonResponse({'jobs': results})
    
#     def post(self, request):
#         """Start a new crawl job"""
#         try:
#             data = json.loads(request.body)
#             domains = data.get('domains')
            
#             if 'domain' in data:
#                 # Start single domain crawl
#                 domain = data['domain']
#                 task = crawl_domain_task.delay(domain)
#                 return JsonResponse({
#                     'message': f'Started crawling domain: {domain}',
#                     'task_id': task.id
#                 })
#             else:
#                 # Start multi-domain crawl
#                 task = crawl_all_domains_task.delay(domains=domains)
#                 return JsonResponse({
#                     'message': f'Started crawling {len(domains) if domains else "default"} domains',
#                     'task_id': task.id
#                 })
                
#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
def start_crawl_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            domain = data.get("domain")
            url_count = int(data.get("url_count", 500))
            
            # Trigger celery task
            task = crawl_domain_task.delay(domain, max_urls=url_count)
            
            # Save progress (initially 0)
            task_progress[task.id] = {
                "count": 0,
                "status": "in-progress",
                "urls": [],
            }
            
            return JsonResponse({"task_id": task.id})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Invalid method"}, status=405)


def crawl_ui_view(request):
    return render(request, 'crawl_ui.html')

def get_progress_view(request, task_id):
    result = AsyncResult(task_id)

    progress = task_progress.get(task_id, {"status": "pending", "count": 0, "urls": []})
    if result.successful():
        data = result.result
        print("datata--0",data)
        progress["status"] = "completed"
        progress["urls"] = data.get("product_urls", [])
        progress["count"] = data.get("total_urls", 0)

    return JsonResponse(progress)   