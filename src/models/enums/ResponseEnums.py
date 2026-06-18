from enum import Enum

class ResponseSignal(Enum):

    FILE_VALIDATED_SUCCESS = "file_validate_successfully"
    FILE_TYPE_NOT_SUPPORTED = "file_type_not_supported"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    FILE_UPLOAD_SUCCESS = "file_upload_success"
    FILE_UPLOAD_FAILED = "file_upload_failed"

    CHAT_SUCCESS = "chat_success"
    CHAT_ERROR = "chat_error"
    DELETE_SUCCESS = "delete_success"
    MULTI_UPLOAD_SUCCESS = "multi_upload_success"
    MULTI_UPLOAD_PARTIAL = "multi_upload_partial"
    MULTI_UPLOAD_FAILED = "multi_upload_failed"

    INVALID_QUERY = "invalid_query"
