class UserServiceError(Exception):
    """Base exception for user service validation and persistence errors."""


class UserValidationError(UserServiceError):
    """Raised when required user fields are missing or invalid."""


class DuplicateEmailError(UserServiceError):
    """Raised when a user email is already registered."""


class InvalidProviderError(UserValidationError):
    """Raised when a user provider is unsupported."""


class InvalidCredentialsError(UserServiceError):
    """Raised when email or password authentication fails."""


class ProviderMismatchError(UserServiceError):
    """Raised when a user attempts to authenticate with the wrong provider."""
