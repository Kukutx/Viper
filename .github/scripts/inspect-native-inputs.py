from pathlib import Path
import json
import urllib.request
import zipfile
import io

out = Path('tools/.reports/native-input')
plugins = json.loads(Path('flutter/.flutter-plugins-dependencies').read_text())['plugins']['android']
for plugin in plugins:
    directory = out / 'plugins' / plugin['name']
    directory.mkdir(parents=True, exist_ok=True)
    for relative in ('pubspec.yaml', 'android/build.gradle', 'android/build.gradle.kts', 'android/src/main/AndroidManifest.xml'):
        source = Path(plugin['path']) / relative
        if source.is_file():
            (directory / relative.replace('/', '_')).write_bytes(source.read_bytes())
urls = {
    'gradle-sha256.txt': 'https://services.gradle.org/distributions/gradle-9.8.0-bin.zip.sha256',
    'qr-plus.json': 'https://pub.dev/api/packages/qr_code_scanner_plus/versions/2.3.0',
    'agp.xml': 'https://dl.google.com/dl/android/maven2/com/android/tools/build/gradle/maven-metadata.xml',
    'protobuf.xml': 'https://repo.maven.apache.org/maven2/com/google/protobuf/protobuf-javalite/maven-metadata.xml',
    'desugar.xml': 'https://dl.google.com/dl/android/maven2/com/android/tools/desugar_jdk_libs/maven-metadata.xml',
    'media.xml': 'https://dl.google.com/dl/android/maven2/androidx/media/media/maven-metadata.xml',
}
for name, url in urls.items():
    request = urllib.request.Request(url, headers={'User-Agent': 'Viper-native-migration'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError('Unexpectedly large metadata')
    (out / name).write_bytes(data)
print('Inspected', len(plugins), 'locked Android plugins')
