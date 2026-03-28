# domain/shared/exceptions.py
class DomainException(Exception):
    pass

class ValidationError(DomainException):
    pass

class NotFoundError(DomainException):
    def __init__(self, entity: str, id: object):
        super().__init__(f"{entity} with id={id} not found")