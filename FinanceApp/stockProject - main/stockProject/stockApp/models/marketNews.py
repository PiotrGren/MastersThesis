from django.db import models
from .company import Company

class MarketNews(models.Model):
    SENTIMENT_CHOICES = [
        ('POSITIVE', 'Pozytywny'),
        ('NEUTRAL', 'Neutralny'),
        ('NEGATIVE', 'Negatywny'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='news')
    title = models.CharField(max_length=255)
    content = models.TextField()
    sentiment = models.CharField(max_length=10, choices=SENTIMENT_CHOICES, default='NEUTRAL')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.sentiment}] {self.company.name}: {self.title}"