from django.urls import path
from app.chatbot import views

urlpatterns = [path("chatbot/", views.chatbot, name="chatbot")]
