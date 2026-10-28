import uuid

from django.db import models


class Account(models.Model):
    """Dossier d'ouverture de compte. La clé Didit n'est jamais stockée ici."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    date_of_birth = models.DateField()
    consent = models.BooleanField()
    status = models.CharField(max_length=32, default="Not Started")
    session_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    verification_url = models.TextField(null=True, blank=True)
    verification = models.JSONField(null=True, blank=True)
    verification_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} <{self.email}>"
