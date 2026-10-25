from abc import ABC, abstractmethod
from schemas.ingestion import IngestionPayload

class BaseProvider(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def get_data(self) -> IngestionPayload:
        raise NotImplementedError