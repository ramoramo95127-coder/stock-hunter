import httpx


class ProviderError(RuntimeError):
    pass


class HttpProvider:
    def __init__(self, base_url: str, headers: dict[str, str] | None = None) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10)

    async def _get(self, path: str, params: dict[str, str] | None = None) -> object:
        try:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Provider request failed: {type(exc).__name__}") from exc

    async def close(self) -> None:
        await self._client.aclose()
