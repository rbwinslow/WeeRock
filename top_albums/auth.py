import base64

from django.contrib.auth import authenticate, login
from django.http import HttpRequest, HttpResponse


def authenticated(view):
    """ plagiarized from https://www.djangosnippets.org/snippets/243/ """

    def wrapper(self, request: HttpRequest, *args, **kwargs):
        if "HTTP_AUTHORIZATION" in request.META:
            auth = request.META['HTTP_AUTHORIZATION'].split()
            if len(auth) == 2 and auth[0].lower() == "basic":
                uname, passwd = base64.b64decode(auth[1]).decode("ascii").split(":")
                user = authenticate(username=uname, password=passwd)
                if user is not None and user.is_active:
                    login(request, user)
                    request.user = user
                    return view(self, request, *args, **kwargs)

        response = HttpResponse()
        response.status_code = 401
        response["WWW-Authenticate"] = "Basic"
        return response

    wrapper.__doc__ = view.__doc__
    return wrapper
