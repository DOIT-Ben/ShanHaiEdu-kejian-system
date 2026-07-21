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


def test_artifact_quality_actor_uses_dramatiq_message_contract() -> None:
    original = dramatiq.get_broker()
    broker = StubBroker()
    try:
        dramatiq.set_broker(broker)

        from workers.artifact_quality import process_artifact_quality_node

        message = process_artifact_quality_node.message("01900000-0000-7000-8000-000000000133")

        assert process_artifact_quality_node.actor_name == "process_artifact_quality_node"
        assert message.actor_name == process_artifact_quality_node.actor_name
        assert message.args == ("01900000-0000-7000-8000-000000000133",)
        retry_when = process_artifact_quality_node.options["retry_when"]
        assert not retry_when(
            0,
            type("Unavailable", (RuntimeError,), {"code": "QUALITY_VALIDATOR_UNAVAILABLE"})(),
        )
        assert not retry_when(
            0,
            type("InvalidBinding", (RuntimeError,), {"code": "QUALITY_REPORT_BINDING_INVALID"})(),
        )
        assert retry_when(0, RuntimeError("transient database failure"))
        assert not retry_when(5, RuntimeError("retry budget exhausted"))
    finally:
        dramatiq.set_broker(original)
