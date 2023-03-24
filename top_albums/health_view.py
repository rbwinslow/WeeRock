from django.db import connections
from django.db.utils import OperationalError
from django.http import HttpRequest, JsonResponse
from django.views import View

from top_albums.docs import apidocs


class HealthView(View):

    def get(self, request: HttpRequest):
        # https://stackoverflow.com/a/32109155
        db_ok = True
        try:
            connections["default"].cursor()
        except OperationalError:
            db_ok = False

        return JsonResponse({
            "__README__": f"To pretty-print API docs, do this: curl --silent {request.build_absolute_uri('')} | jq -r .apidocs",
            "database": db_ok,
            "apidocs": "\n\n".join(apidocs()),
        })
