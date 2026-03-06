from django.db import models
from .company import Company
from .user import User

class UserWatchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlist')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='watchers')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Zabezpieczenie: użytkownik może dodać daną spółkę do obserwowanych tylko raz
        unique_together = ('user', 'company')

    def __str__(self):
        return f"{self.user.username} obserwuje {self.company.name}"