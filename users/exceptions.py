
import logging

from django.http import JsonResponse
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)

    if response is not None:

        error_data = response.data

        if isinstance(error_data, dict) and 'detail' in error_data:
            message = str(error_data['detail'])
            errors = None
        else:
            if response.status_code == status.HTTP_400_BAD_REQUEST:
                message = "Invalid request data."
            elif response.status_code == status.HTTP_404_NOT_FOUND:
                message = "Requested resource was not found."
            elif response.status_code == status.HTTP_401_UNAUTHORIZED:
                message = "Authentication credentials were not provided or are invalid."
            elif response.status_code == status.HTTP_403_FORBIDDEN:
                message = "You do not have permission to perform this action."
            else:
                message = "Request could not be processed."

            errors = error_data

        result = {
            "success": False,
            "message": message
        }

        if errors is not None:
            result["errors"] = errors

        return Response(
            result,
            status=response.status_code,
            headers=response.headers
        )

    logger.error(
        "Unexpected API error",
        exc_info=(type(exc), exc, exc.__traceback__)
    )

    return Response(
        {
            "success": False,
            "message": "An unexpected error occurred. Please try again later."
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def invalid_api_url(request, invalid_path=None):

    return JsonResponse(
        {
            "success": False,
            "message": "Invalid API URL or resource not found."
        },
        status=404
    )
