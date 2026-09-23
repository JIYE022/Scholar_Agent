from abc import ABC, abstractmethod

from schemas.external_search import ExternalPaper, ExternalSearchPlan


class PaperSearchProvider(ABC):
    name: str

    @abstractmethod
    def search(self, plan: ExternalSearchPlan) -> list[ExternalPaper]:
        raise NotImplementedError
