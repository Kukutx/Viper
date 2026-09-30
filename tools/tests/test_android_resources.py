"""Keep restored Android icons identical to the reviewed upstream Git trees."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def git_hash(kind, data):
    return hashlib.sha1(f'{kind} {len(data)}\0'.encode() + data).hexdigest()


class AndroidResourceTests(unittest.TestCase):
    def test_original_density_trees_are_complete(self):
        spec = json.loads((ROOT / 'configs/android-resources.json').read_text())
        self.assertEqual(len(spec['trees']), 5)
        for folder, expected in spec['trees'].items():
            with self.subTest(folder=folder):
                directory = ROOT / 'flutter/android/app/src/main/res' / folder
                self.assertEqual({p.name for p in directory.iterdir()}, set(spec['files']))
                tree = b''
                for name in sorted(spec['files']):
                    path = directory / name
                    self.assertFalse(path.is_symlink())
                    data = path.read_bytes()
                    self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))
                    self.assertGreater(len(data), 32)
                    tree += b'100644 ' + name.encode() + b'\0' + bytes.fromhex(git_hash('blob', data))
                self.assertEqual(git_hash('tree', tree), expected)

    def test_notification_keeps_the_original_icon_reference(self):
        source = ROOT / 'flutter/android/app/src/main/kotlin/com/carriez/flutter_hbb/MainService.kt'
        self.assertIn('.setSmallIcon(R.mipmap.ic_stat_logo)', source.read_text())


if __name__ == '__main__':
    unittest.main()
