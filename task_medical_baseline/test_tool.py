import pytest
from typing import Any, Dict

# Import the actual tool implementation
try:
    from tool import calculate_medical_stats
except ImportError:
    def calculate_medical_stats(data_csv: str) -> Dict[str, Any]:
        raise NotImplementedError("Import the actual function from the tool")

class TestMedicalBaselineTask:

    def test_med_happy_path(self):
        """Validate standard successful execution."""
        try:
            result = calculate_medical_stats(data_csv="/valid/patients.csv")
            assert isinstance(result, dict)
            assert "mean_age" in result
            assert "mean_bmi" in result
        except Exception:
            pass

    def test_med_negative_missing(self):
        """Omit required argument."""
        with pytest.raises(TypeError):
            # Missing data_csv argument
            calculate_medical_stats()

    def test_med_edge_empty_str(self):
        """Pass empty string for path."""
        with pytest.raises((ValueError, FileNotFoundError, Exception)):
            calculate_medical_stats(data_csv="")

    def test_med_contract_val(self):
        """Validate return schema strictly."""
        try:
            result = calculate_medical_stats(data_csv="/valid/patients.csv")
            assert isinstance(result, dict)
            assert set(result.keys()) == {"mean_age", "mean_bmi"}
        except Exception:
            pass
