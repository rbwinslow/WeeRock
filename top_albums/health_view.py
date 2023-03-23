from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse
from django.views import View


class HealthView(View):

    def get(self, request):
        # https://stackoverflow.com/a/32109155
        db_ok = True
        try:
            connections["default"].cursor()
        except OperationalError:
            db_ok = False

        return JsonResponse({"database": db_ok})
