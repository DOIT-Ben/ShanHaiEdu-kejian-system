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
from apps.api.artifact_quality.registry import QualityValidatorRegistryError

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
            try:
                context = transaction.prepare(node_run_id)
            except Exception as exc:
                failure_code = _error_code(exc)
                self._fail_prepare(transaction, node_run_id, failure_code)
                technical_error = ArtifactQualityError(
                    failure_code,
                    "artifact quality validation preparation failed technically",
                )
                technical_error.__cause__ = exc
            else:
                if context.existing_result is not None:
                    return context.existing_result
                try:
                    validators = self._validators.resolve(context.validator_refs)
                    outcomes = tuple(validator.validate(context) for validator in validators)
                except Exception as exc:
                    failure_code = (
                        exc.code
                        if isinstance(exc, QualityValidatorRegistryError)
                        else _TECHNICAL_FAILURE
                    )
                    transaction.fail_technical(context, code=failure_code)
                    technical_error = ArtifactQualityError(
                        failure_code,
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
    def _fail_prepare(
        transaction: ArtifactQualityTransaction,
        node_run_id: UUID,
        code: str,
    ) -> None:
        try:
            transaction.fail_prepare(node_run_id, code=code)
        except Exception as exc:
            raise ArtifactQualityError(
                _COMMIT_FAILURE,
                "artifact quality preparation failure could not be committed",
            ) from exc

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


def _error_code(exc: Exception) -> str:
    code = getattr(exc, "code", _TECHNICAL_FAILURE)
    return code if isinstance(code, str) else _TECHNICAL_FAILURE
