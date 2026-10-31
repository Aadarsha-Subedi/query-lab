"""Refuse an oversized CSV upload before its body is read.

Django parses a multipart body (into a temp file) before the view runs, and the
CSRF middleware does it even earlier, so a size check inside the view would come
after the whole upload was received. This middleware sits in front of CSRF and
answers from the Content-Length header alone; the spooling code still counts the
bytes it copies, so a wrong header gains nothing."""

import re

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from common.response.domain import error_body

UPLOAD_PATH = re.compile(r"^/api/workspaces/\d+/imports(/preview)?/?$")
# Room for the multipart envelope and the options field around the file itself.
OVERHEAD_BYTES = 64 * 1024


class UploadSizeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "POST" and UPLOAD_PATH.match(request.path):
            length = request.META.get("CONTENT_LENGTH", "")
            if not length.isdigit():
                return JsonResponse(
                    error_body(
                        "Send the file with a Content-Length.", "bad_request", 400
                    ),
                    status=400,
                )
            if int(length) > settings.IMPORT_MAX_FILE_BYTES + OVERHEAD_BYTES:
                return JsonResponse(
                    error_body(
                        "The file is larger than the import limit.",
                        "import_file_too_large",
                        413,
                    ),
                    status=413,
                )
        return self.get_response(request)
