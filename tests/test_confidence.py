"""
Unit tests for the weighted Evidence Confidence Scoring model.
Verifies determinism, factor breakdown, sensitivity to missing fields,
and corroboration bonus.
"""

import unittest
from backend.confidence import calculate_evidence_confidence, compute_fact_confidence_factors, FACTOR_WEIGHTS


class TestEvidenceConfidenceScoring(unittest.TestCase):

    def test_weights_sum_to_one(self):
        """Verify that all factor weights sum up to exactly 1.0 (100%)."""
        total = sum(FACTOR_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_complete_financial_fact_high_score(self):
        """A complete financial table fact with all 7 criteria should receive a high score (>= 0.90)."""
        score, factors = calculate_evidence_confidence(
            subject="Delhivery",
            predicate="express parcel shipment volumes",
            numeric_value=740.0,
            unit="million parcels",
            source_text="Express parcel shipment volumes increased by 11.48% to 740 million parcels for FY24.",
            context="Operating Highlights",
            time_period="FY24",
            source_page=36,
            has_corroboration=False,
        )
        self.assertGreaterEqual(score, 0.90)
        self.assertEqual(factors["metric_completeness"], 1.0)
        self.assertEqual(factors["unit_confidence"], 1.0)
        self.assertEqual(factors["subject_confidence"], 1.0)
        self.assertEqual(factors["source_quality"], 1.0)

    def test_missing_unit_lowers_confidence(self):
        """Omitting the unit/scale reduces unit_confidence and the overall score."""
        score_with_unit, _ = calculate_evidence_confidence(
            subject="Delhivery",
            predicate="express parcel shipment volumes",
            numeric_value=740.0,
            unit="million parcels",
            source_text="Express parcel shipment volumes increased by 11.48% to 740 million parcels for FY24.",
            context="Operating Highlights",
            time_period="FY24",
            source_page=36,
        )
        score_no_unit, factors_no_unit = calculate_evidence_confidence(
            subject="Delhivery",
            predicate="express parcel shipment volumes",
            numeric_value=740.0,
            unit="",  # Missing unit
            source_text="Express parcel shipment volumes increased by 11.48% to 740 million parcels for FY24.",
            context="Operating Highlights",
            time_period="FY24",
            source_page=36,
        )
        self.assertLess(score_no_unit, score_with_unit)
        self.assertLessEqual(factors_no_unit["unit_confidence"], 0.20)

    def test_missing_subject_lowers_confidence(self):
        """Omitting the subject reduces subject_confidence and the overall score."""
        score_full, _ = calculate_evidence_confidence(
            subject="Delhivery",
            predicate="express parcel shipment volumes",
            numeric_value=740.0,
            unit="million parcels",
            source_text="Express parcel shipment volumes increased by 11.48% to 740 million parcels for FY24.",
            context="Operating Highlights",
            time_period="FY24",
            source_page=36,
        )
        score_no_subj, factors_no_subj = calculate_evidence_confidence(
            subject="Unknown",  # Missing subject
            predicate="express parcel shipment volumes",
            numeric_value=740.0,
            unit="million parcels",
            source_text="Express parcel shipment volumes increased by 11.48% to 740 million parcels for FY24.",
            context="Operating Highlights",
            time_period="FY24",
            source_page=36,
        )
        self.assertLess(score_no_subj, score_full)
        self.assertLessEqual(factors_no_subj["subject_confidence"], 0.30)

    def test_missing_context_lowers_confidence(self):
        """Omitting time period and section context reduces context_completeness."""
        score_full, _ = calculate_evidence_confidence(
            subject="Delhivery",
            predicate="express parcel shipment volumes",
            numeric_value=740.0,
            unit="million parcels",
            source_text="Express parcel shipment volumes increased by 11.48% to 740 million parcels for FY24.",
            context="Operating Highlights",
            time_period="FY24",
            source_page=36,
        )
        score_no_ctx, factors_no_ctx = calculate_evidence_confidence(
            subject="Delhivery",
            predicate="express parcel shipment volumes",
            numeric_value=740.0,
            unit="million parcels",
            source_text="Express parcel shipment volumes increased by 11.48% to 740 million parcels for FY24.",
            context="",  # Missing context
            time_period="",  # Missing period
            source_page=36,
        )
        self.assertLess(score_no_ctx, score_full)
        self.assertLessEqual(factors_no_ctx["context_completeness"], 0.30)

    def test_corroboration_support_bonus(self):
        """Facts with cross-document corroboration receive +0.05 corroboration support bonus."""
        score_single, _ = calculate_evidence_confidence(
            subject="Delhivery",
            predicate="express parcel shipment volumes",
            numeric_value=740.0,
            unit="million parcels",
            source_text="Express parcel shipment volumes increased by 11.48% to 740 million parcels for FY24.",
            context="Operating Highlights",
            time_period="FY24",
            source_page=36,
            has_corroboration=False,
        )
        score_corrob, factors_corrob = calculate_evidence_confidence(
            subject="Delhivery",
            predicate="express parcel shipment volumes",
            numeric_value=740.0,
            unit="million parcels",
            source_text="Express parcel shipment volumes increased by 11.48% to 740 million parcels for FY24.",
            context="Operating Highlights",
            time_period="FY24",
            source_page=36,
            has_corroboration=True,
        )
        self.assertEqual(factors_corrob["corroboration_support"], 1.0)
        self.assertAlmostEqual(score_corrob - score_single, 0.05, places=2)

    def test_deterministic_scoring(self):
        """Identical inputs must always produce the exact same score and factors."""
        score1, f1 = calculate_evidence_confidence(
            subject="India",
            predicate="real GDP growth rate",
            numeric_value=6.5,
            unit="percent",
            source_text="Real gross domestic product (GDP) growth moderated to 6.5 per cent in 2024-25.",
            context="Macroeconomic Indicators",
            time_period="2024-25",
            source_page=3,
        )
        score2, f2 = calculate_evidence_confidence(
            subject="India",
            predicate="real GDP growth rate",
            numeric_value=6.5,
            unit="percent",
            source_text="Real gross domestic product (GDP) growth moderated to 6.5 per cent in 2024-25.",
            context="Macroeconomic Indicators",
            time_period="2024-25",
            source_page=3,
        )
        self.assertEqual(score1, score2)
        self.assertEqual(f1, f2)

    def test_ambiguous_fact_low_confidence(self):
        """Ambiguous facts without header/unit context (Case 4: 81,417.43) get low confidence."""
        score, factors = calculate_evidence_confidence(
            subject="Unknown",
            predicate="unidentified_metric",
            numeric_value=81417.43,
            unit="",
            source_text="81,417.43",
            context="",
            time_period="",
            source_page=15,
            is_ambiguous=True,
        )
        self.assertLess(score, 0.50)
        self.assertLessEqual(factors["unit_confidence"], 0.20)
        self.assertLessEqual(factors["context_completeness"], 0.20)


if __name__ == "__main__":
    unittest.main()
