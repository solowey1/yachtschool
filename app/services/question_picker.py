"""Selects questions for users.

Two entry points:

* `pick_for_topic` — used when the user interactively chooses a topic from the
  menu. Picks any random (trainer, entry) within that topic; if everything is
  exhausted we cycle and just allow repeats.

* `pick_daily_batch` — used by the scheduler. Returns N items where the last
  one is a review of a previously-wrong question (when applicable).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories import history
from app.training.registry import registry


@dataclass(frozen=True)
class PickedQuestion:
    trainer_key: str
    entry_code: str
    is_review: bool = False


def _all_combinations_for_topic(subject: str, topic_code: str) -> list[tuple[str, str]]:
    topic = registry.get_topic(subject, topic_code)
    combos: list[tuple[str, str]] = []
    for trainer in topic.trainers:
        for code in trainer.all_entry_codes():
            combos.append((trainer.key, code))
    return combos


def _all_combinations() -> list[tuple[str, str]]:
    return [
        (trainer.key, code)
        for trainer in registry.all_trainers()
        for code in trainer.all_entry_codes()
    ]


async def pick_for_topic(
    session: AsyncSession,
    user_id: int,
    subject: str,
    topic_code: str,
    *,
    filter_fn=None,
) -> PickedQuestion | None:
    """Pick one (trainer, entry) combo for this topic, preferring unseen ones.

    `filter_fn(trainer_key, entry_code) -> bool` narrows the pool — used by
    COLREGs to honour the user's vessel-type filter. When the filter excludes
    everything the caller gets None (handler should show «no questions»).
    """
    combos = _all_combinations_for_topic(subject, topic_code)
    if filter_fn is not None:
        combos = [c for c in combos if filter_fn(*c)]
    if not combos:
        return None
    asked = await history.asked_combinations(session, user_id)
    unseen = [c for c in combos if c not in asked]
    pool = unseen if unseen else combos
    trainer_key, entry_code = random.choice(pool)
    return PickedQuestion(trainer_key=trainer_key, entry_code=entry_code)


async def pick_daily_batch(
    session: AsyncSession, user_id: int, count: int | None = None
) -> list[PickedQuestion]:
    """Return up to N questions for daily delivery.

    Layout:
        * The first (N-1) items are fresh — combinations the user has never been asked.
        * The last item is a review of a previously-wrong question; if the user has
          no wrong answers we fall back to another fresh (or repeated) question.

    If the user has fewer than (N-1) fresh combinations available we backfill
    from previously-asked (cycling). The function never returns more items than
    there are total combinations registered.
    """
    n = count or settings.daily_questions_count
    combos = _all_combinations()
    if not combos:
        return []

    asked = await history.asked_combinations(session, user_id)
    unseen = [c for c in combos if c not in asked]
    random.shuffle(unseen)

    fresh_needed = max(0, n - 1)
    fresh: list[tuple[str, str]] = unseen[:fresh_needed]

    # Backfill fresh slots from old (asked) combos if we're short.
    if len(fresh) < fresh_needed:
        leftover = [c for c in combos if c not in set(fresh)]
        random.shuffle(leftover)
        fresh.extend(leftover[: fresh_needed - len(fresh)])

    # Pick the review slot.
    wrong = await history.latest_wrong_answers(session, user_id)
    review: tuple[str, str] | None = None
    if wrong:
        # Prefer a wrong combo that's not already in the fresh batch.
        fresh_set = set(fresh)
        candidates = [w for w in wrong if w not in fresh_set] or wrong
        review = random.choice(candidates)
    elif unseen[fresh_needed:]:
        review = unseen[fresh_needed]
    else:
        # Total fallback — pick anything we haven't already chosen.
        leftover = [c for c in combos if c not in set(fresh)]
        if leftover:
            review = random.choice(leftover)

    batch: list[PickedQuestion] = [
        PickedQuestion(trainer_key=t, entry_code=e, is_review=False) for t, e in fresh
    ]
    if review is not None:
        batch.append(PickedQuestion(trainer_key=review[0], entry_code=review[1], is_review=True))
    return batch[:n]
