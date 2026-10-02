from abc import ABC, abstractmethod

from threadsense.models import Thread


class DataAdapter(ABC):

    @abstractmethod
    def fetch_history(
        self,
        channel_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        pass

    @abstractmethod
    def fetch_replies(
        self,
        channel_id: str,
        thread_ts: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        pass

    @abstractmethod
    def get_threads(
        self,
        channel_id: str,
    ) -> list[Thread]:
        pass