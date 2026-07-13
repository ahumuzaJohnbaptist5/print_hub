from django.contrib import admin
from .models import PaperInventory, CommissionRate, FinancialRecord, AgentEarning

admin.site.register(PaperInventory)
admin.site.register(CommissionRate)
admin.site.register(FinancialRecord)
admin.site.register(AgentEarning)
