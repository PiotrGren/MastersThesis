from django.db import models
from .company import Company
from .user import CustomUser


class Stock(models.Model):
    amount = models.IntegerField(default=0)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='stocks')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stocks')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at =  models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'company'], name='uniq_user_company_stock'),
        ]
        indexes = [
            models.Index(fields=['user', 'company'])
        ]
        
    def __str__(self):
        return f"{self.user.username} - {self.company.name}: {self.amount}"