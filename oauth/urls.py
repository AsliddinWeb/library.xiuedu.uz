from django.urls import path
from .views import AuthLoginView, AuthCallbackView, EmployeAuthLoginView, LogoutView


urlpatterns = [
    path('student-login/', AuthLoginView.as_view(), name='student_login'),
    path('employee-login/', EmployeAuthLoginView.as_view(), name='employee_login'),

    path('callback/', AuthCallbackView.as_view(), name='auth_callback'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
