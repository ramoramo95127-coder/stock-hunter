from datetime import UTC, datetime

from stock_hunter.providers.base import FilingsProvider
from stock_hunter.providers.http import HttpProvider, ProviderError
from stock_hunter.providers.models import Filing


class SecProvider(HttpProvider, FilingsProvider):
    name = "sec"

    def __init__(self, user_agent: str) -> None:
        super().__init__("https://data.sec.gov", {"User-Agent": user_agent})

    async def recent_filings(self, cik: str) -> list[Filing]:
        data = await self._get(f"/submissions/CIK{cik.zfill(10)}.json")
        if not isinstance(data, dict):
            raise ProviderError("SEC returned invalid submissions")
        recent = data.get("filings", {}).get("recent", {})
        result = []
        for accession, form, date, document in zip(
            recent.get("accessionNumber", []),
            recent.get("form", []),
            recent.get("filingDate", []),
            recent.get("primaryDocument", []),
            strict=False,
        ):
            path = accession.replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{path}/{document}"
            result.append(
                Filing(
                    accession_number=accession,
                    form=form,
                    filed_at=datetime.fromisoformat(date).replace(tzinfo=UTC),
                    url=url,
                )
            )
        return result
