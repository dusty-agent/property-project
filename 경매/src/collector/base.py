from abc import ABC, abstractmethod
from datetime import date
from typing import Any


class BaseCollector(ABC):

    @abstractmethod
    def collect_by_date(self, auction_date: date) -> list[Any]:
        """지정한 매각기일의 전체 물건을 수집합니다."""
        raise NotImplementedError

    @abstractmethod
    def collect_by_case_number(
        self,
        case_number: str,
    ) -> list[Any]:
        """사건번호에 해당하는 물건을 수집합니다."""
        raise NotImplementedError