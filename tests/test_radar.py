import httpx
import pytest
from pydantic import SecretStr

from stock_hunter.radar import FmpRadar


@pytest.mark.asyncio
async def test_radar_filters_price_and_ranks_candidates() -> None:
    radar = FmpRadar(SecretStr("test"), 1, 30, 2)
    radar._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=[
                    {"symbol": "LOW", "price": 0.5, "changesPercentage": 100},
                    {"symbol": "B", "price": 10, "changesPercentage": 20, "volume": 100},
                    {"symbol": "A", "price": 8, "changesPercentage": 30, "volume": 50},
                ],
            )
        ),
        base_url="https://test",
    )
    result = await radar.candidates()
    assert [item.symbol for item in result] == ["A", "B"]
    await radar.close()
