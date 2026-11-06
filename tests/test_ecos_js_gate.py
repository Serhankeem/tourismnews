"""Syntactic and publication-gate checks for ECOS browser UI."""
import shutil
import subprocess
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
JS=ROOT/'site/macro.js'

class TourismBalanceUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js not available')
    def test_macro_js_syntax(self):
        subprocess.run(['node','--check',str(JS)],check=True,capture_output=True,text=True,timeout=15)
    def test_balance_is_derived_and_not_shown_without_both_sources(self):
        code=JS.read_text()
        self.assertIn("function tourismBalanceCard()",code)
        self.assertIn("!a?.connected||!b?.connected",code)
        self.assertIn("a.latest.period!==b.latest.period",code)
        self.assertIn("r.value-p.value",code)
        self.assertIn("a.verification_status",code) if False else self.assertIn("r.verification_status",code)
        self.assertIn("data-macro-id=\"derived_tourism_balance\"",code)
        self.assertIn("const balanceMarkup=tourismBalanceCard()",code)
        self.assertIn("markup+balanceMarkup",code)
        self.assertNotIn("ECOS_API_KEY",code)
if __name__=='__main__':unittest.main()
