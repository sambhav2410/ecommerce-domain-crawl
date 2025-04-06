from django.contrib import admin
from django.urls import path
from .views import crawl_ui_view, start_crawl_view, get_progress_view

urlpatterns = [
    path('', crawl_ui_view, name='crawl-ui'),
    path('admin/', admin.site.urls),
    path('start-crawl/', start_crawl_view, name='start-crawl'),
    path('get-progress/<str:task_id>/', get_progress_view, name='get-progress'),
]