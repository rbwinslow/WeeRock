from django.core.management import BaseCommand

from top_albums.album_view import TopAlbumsView
from top_albums.docs import apidocs


class Command(BaseCommand):

    def handle(self, *args, **options):
        for doc in apidocs():
            self.stdout.write(doc + "\n\n")
