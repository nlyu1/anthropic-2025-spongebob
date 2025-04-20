import unittest
import os
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pdf_search import search_pdf_content, DEFAULT_FILES_DIR

class TestPDFSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Create test PDFs with various content patterns"""
        cls.test_dir = Path(DEFAULT_FILES_DIR)
        cls.test_dir.mkdir(exist_ok=True)
        
        # Create test PDFs
        cls._create_test_pdf("test_similar", [
            "The quick brown fox jumps over the lazy dog",
            "The quick brown fox jumps over the sleepy dog",  # Similar but different
            "The quick brown fox leaps over the lazy dog",    # Different verb
            "The swift brown fox jumps over the lazy dog",    # Different adjective
        ])
        
        cls._create_test_pdf("test_formatting", [
            "The quick brown fox jumps over the lazy dog",
            "The quick brown\nfox jumps over\nthe lazy dog",  # Line breaks
            "The  quick  brown  fox  jumps  over  the  lazy  dog",  # Extra spaces
            "The-quick-brown-fox-jumps-over-the-lazy-dog",   # Hyphens
        ])
        
        cls._create_test_pdf("test_context", [
            "Before context. The quick brown fox jumps over the lazy dog. After context.",
            "Different before. The quick brown fox jumps over the lazy dog. Different after.",
        ])

    @classmethod
    def tearDownClass(cls):
        """Clean up test PDFs"""
        for pdf_file in cls.test_dir.glob("test_*.pdf"):
            pdf_file.unlink()

    @classmethod
    def _create_test_pdf(cls, name: str, content_lines: list[str]):
        """Helper to create a PDF with given content"""
        pdf_path = cls.test_dir / f"{name}.pdf"
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        y = 750  # Start from top
        for line in content_lines:
            c.drawString(50, y, line)
            y -= 20
        c.save()

    def test_exact_match(self):
        """Test exact phrase matches"""
        result = search_pdf_content(
            "test_similar",
            "The quick brown fox jumps over the lazy dog"
        )
        self.assertTrue(result["query_exists"])
        self.assertEqual(len(result["matches"]), 1)

    def test_similar_but_different(self):
        """Test that similar but semantically different phrases don't match"""
        # This should not match "sleepy dog" when searching for "lazy dog"
        result = search_pdf_content(
            "test_similar",
            "The quick brown fox jumps over the lazy dog",
            topk=1
        )
        matches = " ".join(result["matches"])
        self.assertNotIn("sleepy", matches)

    def test_different_verb(self):
        """Test that changing a key verb prevents a match"""
        result = search_pdf_content(
            "test_similar",
            "The quick brown fox jumps over the lazy dog",
            topk=1
        )
        matches = " ".join(result["matches"])
        self.assertNotIn("leaps", matches)

    def test_formatting_variations(self):
        """Test that different formatting doesn't prevent matches"""
        base_query = "The quick brown fox jumps over the lazy dog"
        result = search_pdf_content("test_formatting", base_query)
        self.assertTrue(result["query_exists"])
        # Should find all 4 variations despite formatting differences
        self.assertGreaterEqual(len(result["matches"]), 4)

    def test_partial_match_threshold(self):
        """Test that partial matches above threshold are found"""
        result = search_pdf_content(
            "test_similar",
            "quick brown fox jumps"  # Partial phrase
        )
        self.assertTrue(result["query_exists"])
        self.assertGreater(len(result["matches"]), 0)

    def test_context_preservation(self):
        """Test that context is properly preserved"""
        result = search_pdf_content(
            "test_context",
            "The quick brown fox jumps over the lazy dog",
            context_length=100
        )
        self.assertTrue(result["query_exists"])
        # Check that context is included
        self.assertTrue(any("Before context" in match for match in result["matches"]))
        self.assertTrue(any("After context" in match for match in result["matches"]))

    def test_case_insensitivity(self):
        """Test that case differences don't prevent matches"""
        result = search_pdf_content(
            "test_similar",
            "THE QUICK BROWN FOX JUMPS over the lazy DOG"
        )
        self.assertTrue(result["query_exists"])
        self.assertGreater(len(result["matches"]), 0)

    def test_non_existent_file(self):
        """Test handling of non-existent files"""
        result = search_pdf_content(
            "non_existent_file",
            "any query"
        )
        self.assertFalse(result["file_exists"])
        self.assertIn("error", result)

if __name__ == '__main__':
    unittest.main() 