from datetime import UTC, datetime

import httpx
from pydantic import SecretStr

from stock_hunter.hunters.models import EventType, HunterEvent
from stock_hunter.judge.models import Opportunity, OpportunityState

STATE_AR = {
    OpportunityState.WATCHING: "تحت المراقبة",
    OpportunityState.HIGH_ATTENTION: "اهتمام مرتفع",
    OpportunityState.PRIME_CANDIDATE: "مرشح قوي",
    OpportunityState.WEAKENING: "بدأت تضعف",
    OpportunityState.SLEEPING: "لا توجد أدلة نشطة",
    OpportunityState.MISSED: "فات وقت الدخول المناسب",
    OpportunityState.REJECTED: "مرفوضة",
}


def _number(event: HunterEvent, key: str) -> float | None:
    value = event.data.get(key)
    return float(value) if isinstance(value, int | float) else None


def _evidence_text(event: HunterEvent) -> str:
    if event.event_type == EventType.RVOL:
        ratio = _number(event, "rvol")
        return (
            f"حجم التداول في هذه الدقيقة بلغ {ratio:.2f} ضعف حجمه المعتاد في التوقيت نفسه؛ "
            "وهذا يعني أن اهتمام المتداولين بالسهم أعلى من الطبيعي."
            if ratio is not None
            else "حجم التداول الحالي أعلى من المعتاد، ما يدل على اهتمام غير طبيعي بالسهم."
        )
    if event.event_type == EventType.VOLUME_ACCELERATION:
        return (
            "حجم التداول ازداد خلال ثلاث دقائق متتالية؛ أي أن النشاط يتسارع الآن بدل أن "
            "يكون حركة قديمة بدأت تهدأ."
        )
    if event.event_type == EventType.BREAKOUT:
        resistance = _number(event, "resistance")
        price = _number(event, "price")
        if event.data.get("failed") is True and resistance is not None:
            distance = abs(_number(event, "failure_pct") or 0)
            return (
                f"فشل الاختراق: أغلق السعر عند ${price:.2f}، أي أقل من مستوى المقاومة "
                f"${resistance:.2f} بنسبة {distance:.2f}%."
                if price is not None
                else f"فشل الاختراق وعاد السعر أسفل مستوى المقاومة ${resistance:.2f}."
            )
        return (
            f"السعر تجاوز مستوى مقاومة عند ${resistance:.2f}؛ وهذا قد يفتح المجال لاستمرار "
            "الحركة إذا ثبت السعر فوقه."
            if resistance is not None
            else "السعر تجاوز مستوى مقاومة سابقًا، وننتظر ثباته فوقه لتأكيد الاختراق."
        )
    if event.event_type == EventType.GAP:
        gap = _number(event, "gap_pct")
        return (
            f"افتتح السهم أعلى من إغلاقه السابق بنسبة {gap:.2f}%، ما يدل على وصول اهتمام "
            "جديد قبل بداية التداول."
            if gap is not None
            else "افتتح السهم أعلى بوضوح من إغلاقه السابق، ما يدل على اهتمام جديد."
        )
    move = _number(event, "move_pct")
    return (
        f"ارتفع السعر داخل الدقيقة بنسبة {move:.2f}% وأغلق قريبًا من أعلى سعر؛ وهذا يدل على "
        "أن المشترين ما زالوا مسيطرين لحظيًا."
        if move is not None
        else "تحرك السعر بسرعة وأغلق قريبًا من أعلى الدقيقة، ما يعكس زخمًا شرائيًا لحظيًا."
    )


def _score_text(score: float) -> str:
    if score >= 55:
        return "قوية نسبيًا لأن عدة أدلة مستقلة تدعم بعضها، لكنها ليست ضمانًا للارتفاع."
    if score >= 32:
        return "متوسطة وتستحق اهتمامًا مرتفعًا، لكنها تحتاج تأكيدًا إضافيًا قبل أن تصبح قوية."
    return "مبكرة؛ ظهر دليل مهم، لكن الأدلة الحالية لا تكفي لاعتبارها فرصة قوية بعد."


def _confirmation_text(opportunity: Opportunity) -> str:
    if opportunity.state == OpportunityState.REJECTED:
        return (
            "لا ننتظر تأكيدًا للفرصة القديمة لأنها أُلغيت. لا تعُد لمراقبة السهم إلا إذا "
            "أنشأ النظام فرصة جديدة مستقلة بأدلة جديدة."
        )
    if opportunity.state == OpportunityState.SLEEPING:
        return "انتهت صلاحية الأدلة القديمة. ننتظر نشاطًا جديدًا قبل إعادة السهم للمراقبة."
    types = {event.event_type for event in opportunity.events}
    missing = []
    if EventType.BREAKOUT not in types:
        missing.append("اختراق مستوى مقاومة والثبات فوقه")
    if EventType.RVOL not in types:
        missing.append("استمرار حجم تداول أعلى من المعتاد")
    if EventType.VOLUME_ACCELERATION not in types:
        missing.append("تسارع إضافي في حجم التداول")
    if EventType.MOMENTUM not in types:
        missing.append("شمعة جديدة تؤكد استمرار قوة المشترين")
    if opportunity.state == OpportunityState.WEAKENING:
        return "ننتظر عودة الحجم والزخم؛ استمرار تراجعهما يعني أن الفرصة تفقد قوتها."
    if missing:
        return "لرفع قوة الفرصة ننتظر: " + "، أو ".join(missing[:2]) + "."
    return "الأدلة الأساسية متوفرة؛ ننتظر استمرار الحركة دون قفزة مبالغ فيها أو فقدان للحجم."


def format_opportunity(opportunity: Opportunity) -> str:
    ordered = sorted(opportunity.events, key=lambda item: item.strength, reverse=True)
    evidence = "\n".join(f"• {_evidence_text(event)}" for event in ordered[:4])
    if not evidence:
        evidence = "• رصد النظام نشاطًا يستحق المتابعة، لكن تفاصيل الأدلة غير متاحة حاليًا."
    price = next(
        (_number(event, "price") for event in ordered if _number(event, "price") is not None),
        None,
    )
    failure = next(
        (event for event in ordered if event.data.get("failed") is True),
        None,
    )
    levels = "لا تتوفر مستويات سعرية موثوقة حتى الآن."
    if failure:
        failure_price = _number(failure, "price")
        resistance = _number(failure, "resistance")
        levels = (
            f"السعر عند اكتشاف الفشل: ${failure_price:.2f}\n"
            f"مستوى الاختراق الذي لم يصمد: ${resistance:.2f}\n"
            "الهدف والوقف السابقان أُلغيا مع إلغاء الفرصة."
            if failure_price is not None and resistance is not None
            else "أُلغيت المستويات المرجعية السابقة مع إلغاء الفرصة."
        )
    elif price:
        levels = (
            f"السعر وقت الإشارة: ${price:.2f}\n"
            f"منطقة المتابعة المرجعية: ${price * 0.995:.2f}–${price * 1.005:.2f}\n"
            f"الهدف المرجعي: ${price * 1.05:.2f} (+5%)\n"
            f"وقف الخسارة المرجعي: ${price * 0.97:.2f} (-3%)"
        )
    icon = "🔴" if opportunity.state == OpportunityState.REJECTED else "🚨"
    title = "إلغاء فرصة" if opportunity.state == OpportunityState.REJECTED else "تحديث فرصة"
    score_line = (
        "درجة القوة السابقة أُلغيت بعد فشل شرط الاستمرار."
        if opportunity.state == OpportunityState.REJECTED
        else f"درجة القوة: {opportunity.score:.2f} من 100\n"
        f"تفسير الدرجة: {_score_text(opportunity.score)}"
    )
    update_line = (
        "لن يعيد النظام تفعيل الفرصة القديمة؛ وأي عودة لاحقة تحتاج إشارة جديدة مستقلة."
        if opportunity.state == OpportunityState.REJECTED
        else "سيرسل النظام تحديثًا عند انتقال الفرصة إلى حالة أقوى أو عند بدء ضعفها."
    )
    return (
        f"{icon} {title}: {opportunity.symbol}\n\n"
        f"الحالة: {STATE_AR[opportunity.state]}\n"
        f"{score_line}\n\n"
        f"لماذا اقترحها النظام؟\n{evidence}\n\n"
        f"المستويات المرجعية:\n{levels}\n\n"
        f"ما التأكيد القادم؟\n{_confirmation_text(opportunity)}\n"
        f"{update_line}\n\n"
        "حالة الفكرة الآن:\n"
        + (
            "أُلغيت الفرصة السابقة. لا تعتمد على رسالة الترشيح القديمة ولا تدخل بناءً عليها.\n\n"
            if opportunity.state == OpportunityState.REJECTED
            else "تُلغى إذا فشل الاختراق أو تراجع حجم التداول والزخم معًا.\n\n"
        )
        + "⚠️ هذه مراقبة آلية وليست أمر شراء أو ضمان ربح. لا تطارد السعر إذا ابتعد عن المنطقة."
    )


def format_test_notification() -> str:
    now = datetime.now(UTC)
    sample = Opportunity(
        symbol="TEST",
        state=OpportunityState.PRIME_CANDIDATE,
        score=72.5,
        updated_at=now,
        reasons=[],
        what_next="",
        invalidation="",
        events=[
            HunterEvent(
                symbol="TEST",
                event_type=EventType.RVOL,
                timestamp=now,
                strength=0.9,
                reason="",
                data={"rvol": 3.2, "price": 10.0},
            ),
            HunterEvent(
                symbol="TEST",
                event_type=EventType.BREAKOUT,
                timestamp=now,
                strength=0.8,
                reason="",
                data={"resistance": 9.85, "price": 10.0},
            ),
            HunterEvent(
                symbol="TEST",
                event_type=EventType.VOLUME_ACCELERATION,
                timestamp=now,
                strength=0.7,
                reason="",
                data={"accelerating": True, "price": 10.0},
            ),
        ],
        previous_state=OpportunityState.HIGH_ATTENTION,
    )
    return (
        "🧪 رسالة اختبار لنظام Stock Hunter\n"
        "هذه محاكاة لشكل التنبيه الحقيقي. لم تُنشأ إشارة أو صفقة.\n\n" + format_opportunity(sample)
    )


class TelegramNotifier:
    def __init__(self, token: SecretStr | None, chat_id: str | None) -> None:
        self.token = token
        self.chat_id = chat_id
        self._client = httpx.AsyncClient(timeout=10)

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def notify(self, opportunity: Opportunity) -> bool:
        important = opportunity.state in {
            OpportunityState.HIGH_ATTENTION,
            OpportunityState.PRIME_CANDIDATE,
            OpportunityState.WEAKENING,
            OpportunityState.MISSED,
            OpportunityState.REJECTED,
            OpportunityState.SLEEPING,
        }
        changed = opportunity.previous_state != opportunity.state
        if not self.enabled or not important or not changed:
            return False
        await self._send(format_opportunity(opportunity))
        return True

    async def send_test(self) -> bool:
        if not self.enabled:
            return False
        await self._send(format_test_notification())
        return True

    async def _send(self, text: str) -> None:
        response = await self._client.post(
            f"https://api.telegram.org/bot{self.token.get_secret_value()}/sendMessage",
            json={"chat_id": self.chat_id, "text": text},
        )
        response.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()
