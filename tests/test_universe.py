from stock_hunter.universe.models import UniverseSymbol
from stock_hunter.universe.nasdaq import is_common_stock, parse_pipe_file


def test_parse_nasdaq_file() -> None:
    text = (
        "Symbol|Security Name|Market Category|Test Issue|Financial Status|"
        "Round Lot Size|ETF|NextShares\n"
        "ABCD|Acme Common Stock|Q|N|N|100|N|N\n"
        "File Creation Time: 20260711|||||||\n"
    )
    result = parse_pipe_file(text, nasdaq=True)
    assert len(result) == 1
    assert result[0].symbol == "ABCD"
    assert result[0].exchange == "NASDAQ"


def test_filters_non_common_securities() -> None:
    assert is_common_stock(UniverseSymbol(symbol="ABCD", name="Acme Common Stock", exchange="NYSE"))
    assert not is_common_stock(
        UniverseSymbol(symbol="ABCDW", name="Acme Warrants", exchange="NASDAQ")
    )
    assert not is_common_stock(
        UniverseSymbol(symbol="FUND", name="Acme ETF", exchange="NASDAQ", is_etf=True)
    )
    assert not is_common_stock(UniverseSymbol(symbol="OTCX", name="OTC Corp", exchange="OTHER"))
