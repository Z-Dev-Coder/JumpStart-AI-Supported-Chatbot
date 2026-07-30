from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        STAFF = 'staff', 'Support Staff'
        ADMIN = 'admin', 'Administrator'

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    def is_support_staff(self):
        return self.role == self.Role.STAFF

    def is_admin_user(self):
        return self.role == self.Role.ADMIN

    class Meta:
        db_table = 'users'
