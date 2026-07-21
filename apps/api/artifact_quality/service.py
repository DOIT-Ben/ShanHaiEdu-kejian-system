"""Application orchestration for atomic quality-report completion."""

from __future__ import annotations

from uuid import UUID

from apps.api.artifact_quality.contracts import (
    ArtifactQualityReportResult,
    ArtifactQualityTransaction,
    ArtifactQualityTransactionFactory,
    QualityConclusion,
    QualityValidationContext,
    QualityValidatorRegistry,
    ValidatorOutcome,
)

_TECHNICAL_FAILURE = "QUALITY_VALIDATION_TECHNICAL_FAILURE"
_COMMIT_FAILURE = "QUALITY_REPORT_COMMIT_FAILED"


class ArtifactQualityError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ArtifactQualityService:
    def __init__(
        self,
        transactions: ArtifactQualityTransactionFactory,
        validators: QualityValidatorRegistry,
    ) -> None:
        self._transactions = transactions
        self._validators = validators

    def execute(self, node_run_id: UUID) -> ArtifactQualityReportResult:
        technical_error: ArtifactQualityError | None = None
        result: ArtifactQualityReportResult | None = None
        with self._transactions.begin() as transaction:
            context = transaction.prepare(node_run_id)
            if context.existing_result is not None:
                return context.existing_result
            try:
                validators = self._validators.resolve(context.validator_refs)
                outcomes = tuple(validator.validate(context) for validator in validators)
            except Exception as exc:
                transaction.fail_technical(context, code=_TECHNICAL_FAILURE)
                technical_error = ArtifactQualityError(
                    _TECHNICAL_FAILURE,
                    "artifact quality validation failed technically",
                )
                technical_error.__cause__ = exc
            else:
                conclusion: QualityConclusion = (
                    "passed" if all(outcome.passed for outcome in outcomes) else "failed"
                )
                result = self._complete(transaction, context, conclusion, outcomes)
        if technical_error is not None:
            raise technical_error
        assert result is not None
        return result

    @staticmethod
    def _complete(
        transaction: ArtifactQualityTransaction,
        context: QualityValidationContext,
        conclusion: QualityConclusion,
        outcomes: tuple[ValidatorOutcome, ...],
    ) -> ArtifactQualityReportResult:
        try:
            return transaction.complete(
                context,
                conclusion=conclusion,
                outcomes=outcomes,
            )
        except ArtifactQualityError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", _COMMIT_FAILURE)
            raise ArtifactQualityError(
                code if isinstance(code, str) else _COMMIT_FAILURE,
                "artifact quality report commit failed",
            ) from exc
