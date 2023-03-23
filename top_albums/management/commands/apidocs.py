from django.core.management import BaseCommand

from top_albums.album_view import TopAlbumsView


class Command(BaseCommand):

    def handle(self, *args, **options):
        self.stdout.write(TopAlbumsView.get.__doc__)
