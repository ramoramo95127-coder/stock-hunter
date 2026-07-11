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
        if rvol.recent_volume_ratio is not None and rvol.recent_volume_ratio >= 1.25:
            events.append(
                self._event(
                    bar,
                    EventType.RECENT_VOLUME,
                    min(rvol.recent_volume_ratio / 3, 1),
                    (
                        "Current volume reached "
                        f"{rvol.recent_volume_ratio:.2f}x the previous 20-minute average"
                    ),
                    {
                        "recent_volume_ratio": rvol.recent_volume_ratio,
                        "recent_window": rvol.recent_window,
                    },
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
        if bar.resistance:
            if bar.close > bar.resistance and bar.volume > 0:
                distance = (bar.close / bar.resistance - 1) * 100
                events.append(
                    self._event(
                        bar,
                        EventType.BREAKOUT,
                        min(0.5 + distance / 10, 1),
                        f"Price closed above resistance at {bar.resistance:.2f}",
                        {
                            "resistance": bar.resistance,
                            "distance_pct": distance,
                            "support": bar.low,
                            "phase": "confirmed",
                            "retest_count": 0,
                        },
                    )
                )
            elif bar.high >= bar.resistance * 0.995:
                wick_rejection = bar.high > bar.resistance
                distance = (bar.resistance / bar.close - 1) * 100
                events.append(
                    self._event(
                        bar,
                        EventType.RESISTANCE_APPROACH,
                        0.2 if wick_rejection else min(0.35, 0.35 / max(distance, 0.1)),
                        (
                            "Price traded above resistance but did not close above it"
                            if wick_rejection
                            else "Price approached resistance without closing above it"
                        ),
                        {
                            "resistance": bar.resistance,
                            "phase": "wick_rejection" if wick_rejection else "approaching",
                            "distance_pct": distance,
                        },
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
            data={**data, "price": bar.close},
        )
