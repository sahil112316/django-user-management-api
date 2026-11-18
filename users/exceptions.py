
import logging

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse


logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)

    if response is not None:

        error_data = response.data

        # Validation errors
        if response.status_code == status.HTTP_400_BAD_REQUEST:

            result = {
                "success": False,
                "message": "Validation failed.",
                "errors": error_data
            }

        # Not found errors
        elif response.status_code == status.HTTP_404_NOT_FOUND:

            if isinstance(error_data, dict) and 'detail' in error_data:
                message = str(error_data['detail'])
            else:
                message = "Requested resource was not found."

            result = {
                "success": False,
                "message": message,
                "errors": error_data if not (
                    isinstance(error_data, dict) and 'detail' in error_data
                ) else {}
            }

        # Authentication errors
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:

            result = {
                "success": False,
                "message": "Authentication credentials were not provided or are invalid.",
                "errors": {}
            }

        # Permission errors
        elif response.status_code == status.HTTP_403_FORBIDDEN:

            result = {
                "success": False,
                "message": "You do not have permission to perform this action.",
                "errors": {}
            }

        # Other handled errors
        else:

            if isinstance(error_data, dict) and 'detail' in error_data:
                message = str(error_data['detail'])
            else:
                message = "Request could not be processed."

            result = {
                "success": False,
                "message": message,
                "errors": error_data if isinstance(error_data, dict) else {
                    "detail": error_data
                }
            }

        return Response(
            result,
            status=response.status_code,
            headers=response.headers
        )

    # Unexpected server errors
    logger.error(
        "Unexpected API error",
        exc_info=(type(exc), exc, exc.__traceback__)
    )

    return Response(
        {
            "success": False,
            "message": "An unexpected error occurred. Please try again later.",
            "errors": {}
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


# Invalid API URL Handler

def invalid_api_url(request, invalid_path=None):

    return JsonResponse(
        {
            "success": False,
            "message": "Invalid API URL or resource not found.",
            "errors": {}
        },
        status=404
    )


# Project-level 404 Handler

def custom_404_handler(request, exception):

    return JsonResponse(
        {
            "success": False,
            "message": "Requested URL was not found.",
            "errors": {}
        },
        status=404
    )
