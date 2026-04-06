class DomainError(Exception):
    def __init__(self, detail: str):
        self.detail = detail

class InvalidArgument(DomainError):
    pass

class WeakArgument(DomainError):
    pass

class ExpiredPlan(DomainError):
    pass