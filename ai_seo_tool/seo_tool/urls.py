from django.urls import path
from . import views

urlpatterns = [
    path('', views.GenerateView.as_view(), name='generate'),
    path('submit/', views.SubmitView.as_view(), name='submit'),
    path('status/<str:task_id>/', views.StatusView.as_view(), name='status'),
    path('download/<str:task_id>/', views.DownloadDocxView.as_view(), name='download_docx'),
]
