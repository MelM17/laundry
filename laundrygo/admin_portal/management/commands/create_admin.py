from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from customer.models import User

class Command(BaseCommand):
    help = 'Creates an admin user for the LaundryGo admin portal'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Admin username')
        parser.add_argument('--email', type=str, help='Admin email')
        parser.add_argument('--password', type=str, help='Admin password')
        parser.add_argument('--name', type=str, help='Admin full name')

    def handle(self, *args, **options):
        username = options.get('username')
        email = options.get('email')
        password = options.get('password')
        name = options.get('name')
        
        # If any of the arguments are not provided, prompt for them
        if not username:
            username = input('Enter admin username: ')
        if not email:
            email = input('Enter admin email: ')
        if not password:
            password = input('Enter admin password: ')
        if not name:
            name = input('Enter admin full name: ')
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User with username "{username}" already exists.'))
            update = input('Do you want to update this user to admin? (y/n): ')
            if update.lower() == 'y':
                user = User.objects.get(username=username)
                user.user_type = 'admin'
                user.save()
                self.stdout.write(self.style.SUCCESS(f'User "{username}" has been updated to admin.'))
            return
        
        # Create new admin user
        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            name=name,
            user_type='admin'
        )
        
        self.stdout.write(self.style.SUCCESS(f'Admin user "{username}" has been created successfully.'))

