import pprint

from django.core.management import BaseCommand

from top_albums.feed import FeedError, ITunesFeed


class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            downloaded = ITunesFeed().download_and_merge_top_albums()
            self.stdout.write(f"Downloaded and merged {downloaded} top albums.\n")
        except FeedError as ex:
            self.stdout.write(f"FEED EXCEPTION: {ex}\n")
            if ex.json_entry:
                print("Here's a dump of the JSON entry:")
                pprint.pprint(ex.json_entry)
