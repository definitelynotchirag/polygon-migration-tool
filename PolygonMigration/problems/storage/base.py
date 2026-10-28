"""
Storage interface for test-case files.

The migration flow only talks to ``TestCaseStorage``. Concrete providers
(S3-compatible, Azure, ...) implement three primitive operations; everything
else (test-case naming, checker naming) lives here so the layout is identical
regardless of provider:

    test_cases/{problem_id}/{test_number}      # input
    test_cases/{problem_id}/{test_number}.a    # expected output
    test_cases/{problem_id}/custom_checker     # compiled checker (optional)
    test_cases/{problem_id}/custom_checker.cpp # checker source fallback (optional)
"""
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

TEST_CASE_PREFIX = "test_cases"


def problem_prefix(problem_id):
    return f"{TEST_CASE_PREFIX}/{problem_id}/"


def test_case_keys(problem_id, test_number):
    """Return (input_key, output_key) for a 1-based test number."""
    base = f"{TEST_CASE_PREFIX}/{problem_id}/{test_number:02d}"
    return base, f"{base}.a"


class TestCaseStorage(ABC):
    """Provider-agnostic object storage used by the migration flow."""

    #: Human-readable name shown in the UI / logs (e.g. "MinIO (S3)").
    display_name = "storage"

    # ---- primitives each provider must implement -------------------------
    @abstractmethod
    def upload_bytes(self, key, data: bytes):
        """Create or overwrite the object at ``key``."""

    @abstractmethod
    def delete_prefix(self, prefix) -> int:
        """Delete every object whose key starts with ``prefix``. Returns count."""

    @abstractmethod
    def list_keys(self, prefix):
        """Return a list of object keys under ``prefix``."""

    # ---- high-level helpers shared by all providers ----------------------
    def upload_test_case(self, problem_id, test_number, input_data, output_data):
        input_key, output_key = test_case_keys(problem_id, test_number)
        self.upload_bytes(input_key, input_data.encode("utf-8"))
        logger.info("Uploaded input for test #%s to %s", test_number, input_key)
        self.upload_bytes(output_key, output_data.encode("utf-8"))
        logger.info("Uploaded output for test #%s to %s", test_number, output_key)

    def empty_problem(self, problem_id):
        prefix = problem_prefix(problem_id)
        count = self.delete_prefix(prefix)
        logger.info("Deleted %d objects under %s", count, prefix)
        return count

    def upload_checker(self, problem_id, filename, data: bytes):
        key = f"{TEST_CASE_PREFIX}/{problem_id}/{filename}"
        self.upload_bytes(key, data)
        logger.info("Uploaded checker to %s", key)
        return key

    def list_problem_files(self, problem_id):
        return self.list_keys(problem_prefix(problem_id))
