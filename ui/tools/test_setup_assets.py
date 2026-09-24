"""Setup must copy nested web assets without overwriting live state."""
import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name("setup_run_dir.py")
spec = importlib.util.spec_from_file_location("setup_run_dir", SCRIPT)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

class SetupAssetsTest(unittest.TestCase):
    def test_assets_and_existing_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            src, dst = root / "source", root / "run"
            (src / "ui/tools").mkdir(parents=True)
            (src / "ui/server").mkdir()
            (src / "ui/web/assets").mkdir(parents=True)
            shutil.copy2(SCRIPT, src / "ui/tools/setup_run_dir.py")
            for name in setup.MODULES:
                (src / (name + ".py")).write_text("# fixture", encoding="utf-8")
            for name in setup.DATA:
                (src / name).write_text("{}", encoding="utf-8")
            for name in ["ui_view.py", "ui_server.py"]:
                (src / "ui/server" / name).write_text("# fixture", encoding="utf-8")
            (src / "ui/web/index.html").write_text("fixture", encoding="utf-8")
            asset = src / "ui/web/assets/portrait.png"
            asset.write_bytes(b"fixture-image")
            dst.mkdir()
            state = dst / "live2_state.json"
            state.write_text("keep-live-state", encoding="utf-8")
            for data in [b"fixture-image", b"updated-image"]:
                asset.write_bytes(data)
                subprocess.run([sys.executable, "-X", "utf8", str(src / "ui/tools/setup_run_dir.py"), str(dst)],
                               check=True, capture_output=True)
                self.assertEqual((dst / "web/assets/portrait.png").read_bytes(), data)
                self.assertEqual(state.read_text(encoding="utf-8"), "keep-live-state")
                self.assertTrue((dst / "UI_SERVER_DIR").exists())

if __name__ == "__main__":
    unittest.main()
