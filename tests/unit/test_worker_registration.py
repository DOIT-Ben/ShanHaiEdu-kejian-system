from __future__ import annotations

import dramatiq
from dramatiq.brokers.stub import StubBroker


def test_generation_job_actor_uses_dramatiq_message_contract() -> None:
    original = dramatiq.get_broker()
    broker = StubBroker()
    try:
        dramatiq.set_broker(broker)

        from workers.tasks import process_generation_job

        message = process_generation_job.message("01900000-0000-7000-8000-000000000001")

        assert process_generation_job.actor_name == "process_generation_job"
        assert message.actor_name == process_generation_job.actor_name
        assert message.args == ("01900000-0000-7000-8000-000000000001",)
    finally:
        dramatiq.set_broker(original)
