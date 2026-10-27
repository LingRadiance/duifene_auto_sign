from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import main


@unittest.skipUnless(sys.platform == "win32", "Zone.Identifier is Windows-specific")
class DownloadedFilesTests(unittest.TestCase):
    def test_unblock_downloaded_files_clears_nested_pythonnet_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_dir = (
                Path(temp_dir) / "_internal" / "pythonnet" / "runtime"
            )
            runtime_dir.mkdir(parents=True)
            runtime_dll = runtime_dir / "Python.Runtime.dll"
            runtime_dll.write_bytes(b"test assembly")
            zone_stream = f"{runtime_dll}:Zone.Identifier"
            with open(zone_stream, "w", encoding="utf-8") as stream:
                stream.write("[ZoneTransfer]\r\nZoneId=3\r\n")

            removed = main._unblock_downloaded_files(temp_dir)

            self.assertEqual(removed, 1)
            self.assertFalse(os.path.exists(zone_stream))
