from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, EmployeProfile, StudentProfile

@receiver(post_save, sender=User)
def create_user_profiles(sender, instance, created, **kwargs):
    if created:
        if instance.user_type == User.UserType.EMPLOYE:
            EmployeProfile.objects.create(user=instance)
        elif instance.user_type == User.UserType.STUDENT:
            StudentProfile.objects.create(user=instance)
