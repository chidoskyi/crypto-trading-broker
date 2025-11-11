# users/management/commands/load_countries.py
import json
from django.core.management.base import BaseCommand
from users.models import Country

class Command(BaseCommand):
    help = 'Load countries and phone codes from JSON file'

    def handle(self, *args, **options):
        with open('users/data/country_code.json', 'r') as file:
            countries = json.load(file)
            for c in countries:
                Country.objects.get_or_create(
                    name=c['country'],
                    iso=c['iso'],
                    phone_code=c['code']
                )
        self.stdout.write(self.style.SUCCESS('✅ Countries loaded successfully!'))
