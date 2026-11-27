from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import EmployeProfile, StudentProfile, User


@receiver(post_save, sender=User)
def create_user_profiles(sender, instance, created, raw=False, **kwargs):
    """Yangi foydalanuvchiga mos profil yaratadi.

    `raw=True` — yozuv fixture'dan (loaddata) yuklanmoqda. Bunday paytda profil
    fixture'ning o'zida bor, signal yana yaratsa `duplicate key` xatosi chiqadi.
    Shuning uchun fixture yuklanishida signal ishlamaydi (Django tavsiyasi).
    """
    if raw or not created:
        return

    if instance.user_type == User.UserType.EMPLOYE:
        EmployeProfile.objects.get_or_create(user=instance)
    elif instance.user_type == User.UserType.STUDENT:
        StudentProfile.objects.get_or_create(user=instance)
