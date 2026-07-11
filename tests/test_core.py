import httpx
import pytest

from stock_hunter.config import Settings
from stock_hunter.providers.factory import create_market_provider
from stock_hunter.providers.fmp import FmpProvider
from stock_hunter.providers.mock import MockProvider


def test_secrets_are_hidden() -> None:
    assert "secret-value" not in repr(Settings(_env_file=None, FMP_API_KEY="secret-value"))


def test_factory_mock() -> None:
    assert isinstance(
        create_market_provider(Settings(_env_file=None, DEFAULT_PROVIDER="mock")), MockProvider
    )


def test_factory_missing_key() -> None:
    settings = Settings(_env_file=None, DEFAULT_PROVIDER="mock")
    settings.default_provider = "fmp"
    settings.fmp_api_key = None
    with pytest.raises(ValueError):
        create_market_provider(settings)


@pytest.mark.asyncio
async def test_fmp_quote_parsing() -> None:
    provider = FmpProvider("test")
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[{"price": 4.25}])),
        base_url="https://test",
    )
    result = await provider.quote("abcd")
    assert result.symbol == "ABCD" and result.price == 4.25
    await provider.close()
