from typing import List

from top_albums.album_view import TopAlbumsView


def apidocs() -> List[str]:
    return [
        TopAlbumsView.get.__doc__,
        TopAlbumsView.post.__doc__,
        TopAlbumsView.patch.__doc__,
        TopAlbumsView.delete.__doc__,
    ]
