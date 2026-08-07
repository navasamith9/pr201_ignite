from django.db import models

class QuestionFrequency(models.Model):
    query_text = models.CharField(max_length=500, unique=True)
    count = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-count', '-updated_at']

    def __str__(self):
        return f"{self.query_text} ({self.count})"
