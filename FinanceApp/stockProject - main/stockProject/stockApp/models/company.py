from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=150, unique=True, db_index=True)
    slug = models.SlugField(max_length=160, unique=True, null=True, blank=True)
    
    def __str__(self):
        return self.name