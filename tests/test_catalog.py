"""Sector catalog, fixture preflight, and alias resolution."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.contracts import SectorId
from src.ingestion.catalog import (
    normalize_text,
    resolve_sector_candidate,
    validate_fixtures,
)

_REAL_SECTOR_IDS = sorted(
    member.value for member in SectorId if member is not SectorId.UNKNOWN
)


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _minimal_reports() -> dict[str, object]:
    return {
        "reports": [
            {
                "report_id": "SYN-TEMP",
                "raw_text": "sin agua",
                "source_channel": "whatsapp",
                "provenance": "SYNTHETIC_DEMO",
                "expected_sector_id": "UNKNOWN",
            }
        ]
    }


class CatalogTests(unittest.TestCase):
    def test_real_fixtures_list_every_known_sector(self) -> None:
        self.assertEqual(validate_fixtures(), _REAL_SECTOR_IDS)

    def test_missing_sector_file_names_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "sample_citizen_reports.json", _minimal_reports())
            with self.assertRaises(ValueError) as caught:
                validate_fixtures(root)
        self.assertIn("sectors_panama_oeste.json", str(caught.exception))

    def test_unknown_sector_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / "sectors_panama_oeste.json",
                {
                    "sectors": [
                        {
                            "sector_id": "VISTA_ALEGRE",
                            "name": "Vista Alegre",
                            "district": "Arraijan",
                            "provenance": "SYNTHETIC_DEMO",
                            "aliases": ["vista alegre"],
                        }
                    ]
                },
            )
            _write(root / "sample_citizen_reports.json", _minimal_reports())
            with self.assertRaises(ValueError) as caught:
                validate_fixtures(root)
        self.assertIn("VISTA_ALEGRE", str(caught.exception))

    def test_empty_sector_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sectors_panama_oeste.json").write_text("", encoding="utf-8")
            _write(root / "sample_citizen_reports.json", _minimal_reports())
            with self.assertRaises(ValueError) as caught:
                validate_fixtures(root)
        self.assertIn("empty", str(caught.exception).lower())

    def test_normalize_text_strips_accents_and_case(self) -> None:
        self.assertEqual(normalize_text("Nicolás Solano"), "nicolas solano")
        self.assertEqual(normalize_text("Arraiján"), "arraijan")

    def test_chino_de_vista_alegre_resolves_in_scope(self) -> None:
        found = resolve_sector_candidate("por el chino de Vista Alegre")
        self.assertEqual(found.sector_id, SectorId.ARRAIJAN_VISTA_ALEGRE)
        self.assertFalse(found.out_of_scope)

    def test_xtra_alias_beats_shorter_vista_alegre(self) -> None:
        found = resolve_sector_candidate("Xtra de Vista Alegre")
        self.assertEqual(found.sector_id, SectorId.ARRAIJAN_VISTA_ALEGRE)
        self.assertEqual(normalize_text(found.matched_alias), "xtra de vista alegre")

    def test_loma_cova_resolves_to_burunga(self) -> None:
        found = resolve_sector_candidate("Loma Cova, Burunga")
        self.assertEqual(found.sector_id, SectorId.ARRAIJAN_BURUNGA)

    def test_hospital_nicolas_solano_resolves_to_barrio_colon(self) -> None:
        found = resolve_sector_candidate("Hospital Nicolás Solano")
        self.assertEqual(found.sector_id, SectorId.CHORRERA_BARRIO_COLON)
        self.assertFalse(found.out_of_scope)

    def test_parque_feuillet_resolves_to_barrio_balboa(self) -> None:
        found = resolve_sector_candidate("Parque Feuillet")
        self.assertEqual(found.sector_id, SectorId.CHORRERA_BARRIO_BALBOA)

    def test_puerto_caimito_resolves(self) -> None:
        found = resolve_sector_candidate("Puerto Caimito")
        self.assertEqual(found.sector_id, SectorId.CHORRERA_PUERTO_CAIMITO)

    def test_chiriqui_is_out_of_scope(self) -> None:
        found = resolve_sector_candidate("sin agua en David, Chiriqui")
        self.assertEqual(found.sector_id, SectorId.UNKNOWN)
        self.assertTrue(found.out_of_scope)
        self.assertTrue(found.scope_reason)

    def test_barrio_colon_is_not_the_province(self) -> None:
        found = resolve_sector_candidate("Barrio Colón, La Chorrera")
        self.assertEqual(found.sector_id, SectorId.CHORRERA_BARRIO_COLON)
        self.assertFalse(found.out_of_scope)

    def test_colon_province_is_out_of_scope(self) -> None:
        found = resolve_sector_candidate("estoy en Colón, no en La Chorrera")
        self.assertEqual(found.sector_id, SectorId.UNKNOWN)
        self.assertTrue(found.out_of_scope)

    def test_panama_city_is_out_of_scope(self) -> None:
        found = resolve_sector_candidate("Ciudad de Panamá, San Miguelito")
        self.assertEqual(found.sector_id, SectorId.UNKNOWN)
        self.assertTrue(found.out_of_scope)

    def test_unknown_place_stays_in_scope_but_unresolved(self) -> None:
        found = resolve_sector_candidate("no se donde")
        self.assertEqual(found.sector_id, SectorId.UNKNOWN)
        self.assertFalse(found.out_of_scope)
        self.assertEqual(found.matched_alias, "")

    def test_el_coco_does_not_match_inside_another_word(self) -> None:
        found = resolve_sector_candidate("el coco lleva dos dias sin agua")
        self.assertEqual(found.sector_id, SectorId.CHORRERA_EL_COCO)
        other = resolve_sector_candidate("hay un cocotero seco")
        self.assertNotEqual(other.sector_id, SectorId.CHORRERA_EL_COCO)


if __name__ == "__main__":
    unittest.main()
