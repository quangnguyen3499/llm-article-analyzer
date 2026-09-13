from django.urls import path
from app.chatbot import views

urlpatterns = [
	path("", views.chatbot, name="chatbot"),
	path("upload-profile/", views.upload_profile, name="upload_profile"),
]
