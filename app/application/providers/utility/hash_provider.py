from abc import ABC, abstractmethod

class HashProvider(ABC):
    @abstractmethod
    def hash(self, value: str) -> str:
        pass

    @abstractmethod
    def verify(self, hashed: str, value: str) -> bool:
        pass
    