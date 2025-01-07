from django.urls import path
from .views import AuthLoginView, AuthCallbackView, EmployeAuthLoginView


urlpatterns = [
    path('student-login/', AuthLoginView.as_view(), name='student_login'),
    path('employee-login/', EmployeAuthLoginView.as_view()),

    path('callback/', AuthCallbackView.as_view()),
]
