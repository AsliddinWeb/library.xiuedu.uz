from django.urls import path

from .views import (
    AuthCallbackView,
    AuthLoginView,
    EmployeAuthLoginView,
    LoginChoiceView,
    LogoutView,
)

urlpatterns = [
    path('login/', LoginChoiceView.as_view(), name='login'),
    path('student-login/', AuthLoginView.as_view(), name='student_login'),
    path('employee-login/', EmployeAuthLoginView.as_view(), name='employee_login'),

    path('callback/', AuthCallbackView.as_view(), name='auth_callback'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
