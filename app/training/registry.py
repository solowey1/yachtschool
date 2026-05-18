"""Global registry of trainers and topics.

Topics are what the user picks from the main menu. Each topic is backed by one
or more Trainers; when the user starts a topic, we pick a random trainer from
that topic and a random entry to quiz on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.training.base import Trainer


@dataclass
class Topic:
    subject: str
    code: str  # e.g. "flags"
    title_i18n_key: str
    intro_i18n_key: str
    trainers: list[Trainer] = field(default_factory=list)
    order: int = 0


class Registry:
    """Singleton holding all registered subjects/topics/trainers."""

    def __init__(self) -> None:
        self._trainers: dict[str, Trainer] = {}
        self._topics: dict[tuple[str, str], Topic] = {}

    def register_topic(
        self,
        *,
        subject: str,
        code: str,
        title_i18n_key: str,
        intro_i18n_key: str,
        order: int = 0,
    ) -> Topic:
        topic = Topic(
            subject=subject,
            code=code,
            title_i18n_key=title_i18n_key,
            intro_i18n_key=intro_i18n_key,
            order=order,
        )
        self._topics[(subject, code)] = topic
        return topic

    def register_trainer(self, trainer: Trainer) -> None:
        if trainer.key in self._trainers:
            raise ValueError(f"trainer {trainer.key!r} already registered")
        topic = self._topics.get((trainer.subject, trainer.topic))
        if topic is None:
            raise ValueError(
                f"topic {trainer.subject}/{trainer.topic} not registered before trainer {trainer.key}"
            )
        self._trainers[trainer.key] = trainer
        topic.trainers.append(trainer)

    def get_trainer(self, key: str) -> Trainer:
        return self._trainers[key]

    def all_trainers(self) -> list[Trainer]:
        return list(self._trainers.values())

    def topics(self, subject: str | None = None) -> list[Topic]:
        topics = self._topics.values()
        if subject is not None:
            topics = [t for t in topics if t.subject == subject]
        return sorted(topics, key=lambda t: (t.subject, t.order, t.code))

    def get_topic(self, subject: str, code: str) -> Topic:
        return self._topics[(subject, code)]


registry = Registry()
