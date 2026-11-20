"""Execute the browser's exact pure model module; never reimplement it in Python."""
from pathlib import Path
import subprocess
import unittest


class ModelSignalTests(unittest.TestCase):
    def test_pure_javascript_model_contracts(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['node','--test','tests/model-signal.test.cjs'],cwd=root,capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
