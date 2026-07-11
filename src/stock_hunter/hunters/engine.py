from stock_hunter.hunters.models import EventType, HunterEvent
from stock_hunter.intraday.models import RvolSnapshot
from stock_hunter.providers.models import MinuteBarData


class HunterEngine:
    def evaluate(self, bar: MinuteBarData, rvol: RvolSnapshot) -> list[HunterEvent]:
        events: list[HunterEvent] = []
        if rvol.triggered:
            events.append(
                self._event(
                    bar,
                    EventType.RVOL,
                    min((rvol.rvol or 0) / 5, 1),
                    f"RVOL reached {rvol.rvol:.2f}",
                    {"rvol": rvol.rvol or 0},
                )
            )
        if rvol.accelerating:
            events.append(
                self._event(
                    bar,
                    EventType.VOLUME_ACCELERATION,
                    0.7,
                    "Volume accelerated for three consecutive minutes",
                    {"accelerating": True},
                )
            )
        if bar.resistance and bar.close > bar.resistance and bar.volume > 0:
            distance = (bar.close / bar.resistance - 1) * 100
            events.append(
                self._event(
                    bar,
                    EventType.BREAKOUT,
                    min(0.5 + distance / 10, 1),
                    f"Price broke resistance at {bar.resistance:.2f}",
                    {"resistance": bar.resistance, "distance_pct": distance},
                )
            )
        if bar.previous_close:
            gap = (bar.open / bar.previous_close - 1) * 100
            if gap >= 3:
                events.append(
                    self._event(
                        bar,
                        EventType.GAP,
                        min(gap / 15, 1),
                        f"Session opened {gap:.2f}% above previous close",
                        {"gap_pct": gap},
                    )
                )
        move = (bar.close / bar.open - 1) * 100
        if move >= 2 and bar.close >= bar.high * 0.98:
            events.append(
                self._event(
                    bar,
                    EventType.MOMENTUM,
                    min(move / 5, 1),
                    f"Minute gained {move:.2f}% and closed near its high",
                    {"move_pct": move},
                )
            )
        return events

    @staticmethod
    def _event(
        bar: MinuteBarData,
        kind: EventType,
        strength: float,
        reason: str,
        data: dict[str, float | bool | str],
    ) -> HunterEvent:
        return HunterEvent(
            symbol=bar.symbol.upper(),
            event_type=kind,
            timestamp=bar.timestamp,
            strength=round(strength, 4),
            reason=reason,
            data=data,
        )
