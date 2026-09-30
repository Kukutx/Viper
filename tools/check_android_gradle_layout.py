"""Exercise the repository's Gradle evaluation order without Android dependencies."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify(root: Path = ROOT) -> None:
    wrapper = root / 'flutter/android/gradlew'
    with tempfile.TemporaryDirectory(prefix='viper-gradle-layout-') as temporary:
        fixture = Path(temporary) / 'android'
        fixture.mkdir()
        (fixture / 'settings.gradle').write_text(
            "rootProject.name = 'layout-regression'\ninclude ':a-plugin', ':app'\n", encoding='utf-8')
        shutil.copyfile(root / 'flutter/android/build.gradle', fixture / 'build.gradle')
        (fixture / 'a-plugin').mkdir()
        app = fixture / 'app'
        app.mkdir()
        # AGP captures a File when getDefaultProguardFile is called during evaluation.
        # A plugin sorted before :app reproduces the premature evaluation regression.
        (app / 'build.gradle').write_text('''
final File capturedDirectory = layout.buildDirectory.get().asFile
final File expectedDirectory = rootProject.file('../build/app').canonicalFile
assert capturedDirectory.canonicalFile == expectedDirectory :
    "Application evaluated before its build directory was set: ${capturedDirectory}"
tasks.register('verifyLayout') {
    doLast {
        assert project.layout.buildDirectory.get().asFile.canonicalFile == capturedDirectory.canonicalFile
        println('Android build directory is stable before and after application evaluation')
    }
}
''', encoding='utf-8')
        subprocess.run(['bash', str(wrapper), '--no-daemon', '--console=plain',
                        '--offline', '--project-dir', str(fixture), ':app:verifyLayout'],
                       cwd=root, check=True)


if __name__ == '__main__':
    verify()
