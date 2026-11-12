
import logging

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):

    # Handle DRF exceptions
    response = exception_handler(exc, context)

    if response is not None:
        return response

    # Log unexpected errors
    logger.error(
        "Unexpected API error",
        exc_info=(type(exc), exc, exc.__traceback__)
    )

    # Return safe error response
    return Response(
        {
            "error": "An unexpected error occurred. Please try again later."
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
