/// Select a destination without consuming the native screenshot cache.
/// The Rust handler retains the image on write failure and clears it only
/// after a successful write or an explicit cancellation.
Future<String> saveScreenshotToSelectedPath({
  required Future<String?> Function() selectPath,
  required Future<String> Function(String action) handleAction,
}) async {
  final path = await selectPath();
  return await handleAction(path == null ? '2' : '0:$path');
}
