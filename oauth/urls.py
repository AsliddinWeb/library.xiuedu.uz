from django.urls import path
from .views import AuthLoginView, AuthCallbackView


urlpatterns = [
    path('auth/', AuthLoginView.as_view()),
    path('callback/', AuthCallbackView.as_view()),
]
