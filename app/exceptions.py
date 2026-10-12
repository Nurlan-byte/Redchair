class AppError(Exception):
    status_code = 500

    def __init__(self, code: str, message: str | None = None):
        super().__init__(message or code)
        self.code = code
        self.message = message


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class PermissionDeniedError(AppError):
    status_code = 403


class AuthenticationError(AppError):
    status_code = 401


class DomainValidationError(AppError):
    status_code = 422
