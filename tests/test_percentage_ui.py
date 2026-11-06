"""The shared display parser is checked in the existing Python CI entrypoint."""
from pathlib import Path
import subprocess
import unittest

class PercentageTests(unittest.TestCase):
    def test_shared_numeric_display_contract(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['node',str(root/'tests/percentage.unit.cjs')],cwd=root,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
