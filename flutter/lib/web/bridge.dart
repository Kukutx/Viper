import 'dart:async';
import 'dart:js' as js;
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import 'dart:html' as html;

import 'package:flutter_hbb/consts.dart';

final _privateConstructorUsedError = UnsupportedError(
    'It seems like you constructed your class using `MyClass._()`. This constructor is only meant to be used by freezed and you are not supposed to need it nor use it.\nPlease check the documentation here for more information: https://github.com/rrousselGit/freezed#adding-getters-and-methods-to-our-models');

mixin _$EventToUI {
  Object get field0 => throw _privateConstructorUsedError;
}

sealed class EventToUI {
  const factory EventToUI.event(
    String field0,
  ) = EventToUI_Event;
  const factory EventToUI.rgba(
    int field0,
  ) = EventToUI_Rgba;
  const factory EventToUI.texture(
    int field0,
    bool field1,
  ) = EventToUI_Texture;
}

class EventToUI_Event implements EventToUI {
  const EventToUI_Event(final String field0) : this.field = field0;
  final String field;
  String get field0 => field;
}

class EventToUI_Rgba implements EventToUI {
  const EventToUI_Rgba(final int field0) : field = field0;
  final int field;
  int get field0 => field;
}

class EventToUI_Texture implements EventToUI {
  const EventToUI_Texture(final int field0, final bool field1)
      : f0 = field0,
        f1 = field1;
  final int f0;
  final bool f1;
  int get field0 => f0;
  bool get field1 => f1;
}

class RustLibApi {
  Future<void> crateFlutterFfiStopGlobalEventStream({required String appType, dynamic hint}) {
    throw UnimplementedError("stopGlobalEventStream");
  }

  Future<void> crateFlutterFfiHostStopSystemKeyPropagate(
      {required bool stopped, dynamic hint}) {
    throw UnimplementedError("hostStopSystemKeyPropagate");
  }

  int crateFlutterFfiPeerGetSessionsCount(
      {required String id, required int connType, dynamic hint}) {
    return 0;
  }

  String crateFlutterFfiSessionAddExistedSync(
      {required String id,
      required UuidValue sessionId,
      required Int32List displays,
      required bool isViewCamera,
      dynamic hint}) {
    return '';
  }

  String crateFlutterFfiSessionAddSync(
      {required UuidValue sessionId,
      required String id,
      required bool isFileTransfer,
      required bool isViewCamera,
      required bool isPortForward,
      required bool isRdp,
      required bool isTerminal,
      required String switchUuid,
      required bool forceRelay,
      required String password,
      required bool isSharedPassword,
      String? connToken,
      dynamic hint}) {
    return js.context.callMethod('setByName', [
      'session_add_sync',
      jsonEncode({
        'id': id,
        'password': password,
        'is_shared_password': isSharedPassword,
        'isFileTransfer': isFileTransfer,
        'isViewCamera': isViewCamera,
        'isTerminal': isTerminal
      })
    ]);
  }

  Stream<EventToUI> crateFlutterFfiSessionStart(
      {required UuidValue sessionId, required String id, dynamic hint}) {
    js.context.callMethod('setByName', [
      'session_start',
      jsonEncode({'id': id})
    ]);
    return Stream.empty();
  }

  Stream<EventToUI> crateFlutterFfiSessionStartWithDisplays(
      {required UuidValue sessionId,
      required String id,
      required Int32List displays,
      dynamic hint}) {
    throw UnimplementedError("sessionStartWithDisplays");
  }

  Future<bool?> crateFlutterFfiSessionGetRemember(
      {required UuidValue sessionId, dynamic hint}) {
    return Future(
        () => js.context.callMethod('getByName', ['remember']) == 'true');
  }

  Future<bool?> crateFlutterFfiSessionGetToggleOption(
      {required UuidValue sessionId, required String arg, dynamic hint}) {
    return Future(
        () => sessionGetToggleOptionSync(sessionId: sessionId, arg: arg));
  }

  bool crateFlutterFfiSessionGetToggleOptionSync(
      {required UuidValue sessionId, required String arg, dynamic hint}) {
    return 'true' == js.context.callMethod('getByName', ['option:toggle', arg]);
  }

  Future<String?> crateFlutterFfiSessionGetOption(
      {required UuidValue sessionId, required String arg, dynamic hint}) {
    return Future(
        () => js.context.callMethod('getByName', ['option:session', arg]));
  }

  Future<void> crateFlutterFfiSessionLogin(
      {required UuidValue sessionId,
      required String osUsername,
      required String osPassword,
      required String password,
      required bool remember,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'login',
          jsonEncode({
            'os_username': osUsername,
            'os_password': osPassword,
            'password': password,
            'remember': remember
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionSend2Fa(
      {required UuidValue sessionId,
      required String code,
      required bool trustThisDevice,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'send_2fa',
          jsonEncode({'code': code, 'trust_this_device': trustThisDevice})
        ]));
  }

  Future<void> crateFlutterFfiSessionClose({required UuidValue sessionId, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['session_close']));
  }

  Future<void> crateFlutterFfiSessionRefresh(
      {required UuidValue sessionId, required int display, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['refresh']));
  }

  Future<void> crateFlutterFfiSessionRecordScreen(
      {required UuidValue sessionId, required bool start, dynamic hint}) {
    throw UnimplementedError("sessionRecordScreen");
  }

  bool crateFlutterFfiSessionGetIsRecording({required UuidValue sessionId, dynamic hint}) {
    return false;
  }

  Future<void> crateFlutterFfiSessionReconnect(
      {required UuidValue sessionId, required bool forceRelay, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['reconnect']));
  }

  Future<void> crateFlutterFfiSessionToggleOption(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['option:toggle', value]));
  }

  Future<void> crateFlutterFfiSessionTogglePrivacyMode(
      {required UuidValue sessionId,
      required String implKey,
      required bool on,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'toggle_privacy_mode',
          jsonEncode({'impl_key': implKey, 'on': on})
        ]));
  }

  Future<String?> crateFlutterFfiSessionGetFlutterOption(
      {required UuidValue sessionId, required String k, dynamic hint}) {
    return Future(
        () => js.context.callMethod('getByName', ['option:flutter:peer', k]));
  }

  Future<void> crateFlutterFfiSessionSetFlutterOption(
      {required UuidValue sessionId,
      required String k,
      required String v,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'option:flutter:peer',
          jsonEncode({'name': k, 'value': v})
        ]));
  }

  int crateFlutterFfiGetNextTextureKey({dynamic hint}) {
    return 0;
  }

  String crateFlutterFfiGetLocalFlutterOption({required String k, dynamic hint}) {
    return js.context.callMethod('getByName', ['option:flutter:local', k]);
  }

  Future<void> crateFlutterFfiSetLocalFlutterOption(
      {required String k, required String v, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'option:flutter:local',
          jsonEncode({'name': k, 'value': v})
        ]));
  }

  String crateFlutterFfiGetLocalKbLayoutType({dynamic hint}) {
    return js.context.callMethod('getByName', ['option:local', 'kb_layout']);
  }

  Future<void> crateFlutterFfiSetLocalKbLayoutType(
      {required String kbLayoutType, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'option:local',
          jsonEncode({'name': 'kb_layout', 'value': kbLayoutType})
        ]));
  }

  Future<String?> crateFlutterFfiSessionGetViewStyle(
      {required UuidValue sessionId, dynamic hint}) {
    return Future(() =>
        js.context.callMethod('getByName', ['option:session', 'view_style']));
  }

  Future<void> crateFlutterFfiSessionSetViewStyle(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'option:session',
          jsonEncode({'name': 'view_style', 'value': value})
        ]));
  }

  Future<int?> crateFlutterFfiSessionGetTrackpadSpeed(
      {required UuidValue sessionId, dynamic hint}) {
    throw UnimplementedError("sessionGetTrackpadSpeed");
  }

  Future<void> crateFlutterFfiSessionSetTrackpadSpeed(
      {required UuidValue sessionId, required int value, dynamic hint}) {
    throw UnimplementedError("sessionSetTrackpadSpeed");
  }

  Future<String?> crateFlutterFfiSessionGetScrollStyle(
      {required UuidValue sessionId, dynamic hint}) {
    return Future(() =>
        js.context.callMethod('getByName', ['option:session', 'scroll_style']));
  }

  Future<void> crateFlutterFfiSessionSetScrollStyle(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'option:session',
          jsonEncode({'name': 'scroll_style', 'value': value})
        ]));
  }

  Future<String?> crateFlutterFfiSessionGetImageQuality(
      {required UuidValue sessionId, dynamic hint}) {
    return Future(() => js.context.callMethod('getByName', ['image_quality']));
  }

  Future<void> crateFlutterFfiSessionSetImageQuality(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    print('set image quality: $value');
    return Future(
        () => js.context.callMethod('setByName', ['image_quality', value]));
  }

  Future<String?> crateFlutterFfiSessionGetKeyboardMode(
      {required UuidValue sessionId, dynamic hint}) {
    final mode =
        js.context.callMethod('getByName', ['option:session', 'keyboard_mode']);
    return Future(() => mode == '' ? null : mode);
  }

  Future<void> crateFlutterFfiSessionSetKeyboardMode(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'option:session',
          jsonEncode({'name': 'keyboard_mode', 'value': value})
        ]));
  }

  String? crateFlutterFfiSessionGetReverseMouseWheelSync(
      {required UuidValue sessionId, dynamic hint}) {
    return js.context
        .callMethod('getByName', ['option:session', 'reverse_mouse_wheel']);
  }

  Future<void> crateFlutterFfiSessionSetReverseMouseWheel(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'option:session',
          jsonEncode({'name': 'reverse_mouse_wheel', 'value': value})
        ]));
  }

  String? crateFlutterFfiSessionGetDisplaysAsIndividualWindows(
      {required UuidValue sessionId, dynamic hint}) {
    return js.context.callMethod(
        'getByName', ['option:session', 'displays_as_individual_windows']);
  }

  Future<void> crateFlutterFfiSessionSetDisplaysAsIndividualWindows(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    return Future.value();
  }

  String? crateFlutterFfiSessionGetUseAllMyDisplaysForTheRemoteSession(
      {required UuidValue sessionId, dynamic hint}) {
    return '';
  }

  Future<void> crateFlutterFfiSessionSetUseAllMyDisplaysForTheRemoteSession(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    return Future.value();
  }

  Future<Int32List?> crateFlutterFfiSessionGetCustomImageQuality(
      {required UuidValue sessionId, dynamic hint}) {
    try {
      return Future(() => Int32List.fromList([
            int.parse(js.context.callMethod(
                'getByName', ['option:session', 'custom_image_quality']))
          ]));
    } catch (e) {
      return Future.value(null);
    }
  }

  bool crateFlutterFfiSessionIsKeyboardModeSupported(
      {required UuidValue sessionId, required String mode, dynamic hint}) {
    if (mainGetInputSource(hint: hint) == 'Input source 1') {
      return [kKeyMapMode, kKeyTranslateMode].contains(mode);
    } else {
      return [kKeyLegacyMode, kKeyMapMode].contains(mode);
    }
  }

  bool crateFlutterFfiSessionIsMultiUiSession({required UuidValue sessionId, dynamic hint}) {
    return false;
  }

  Future<void> crateFlutterFfiSessionSetCustomImageQuality(
      {required UuidValue sessionId, required int value, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'custom_image_quality',
          value,
        ]));
  }

  Future<void> crateFlutterFfiSessionSetCustomFps(
      {required UuidValue sessionId, required int fps, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['custom-fps', fps]));
  }

  Future<void> crateFlutterFfiSessionLockScreen({required UuidValue sessionId, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['lock_screen']));
  }

  Future<void> crateFlutterFfiSessionCtrlAltDel({required UuidValue sessionId, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['ctrl_alt_del']));
  }

  Future<void> crateFlutterFfiSessionSwitchDisplay(
      {required bool isDesktop,
      required UuidValue sessionId,
      required Int32List value,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'switch_display',
          jsonEncode({
            'isDesktop': isDesktop,
            'sessionId': sessionId.toString(),
            'value': value
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionHandleFlutterKeyEvent(
      {required UuidValue sessionId,
      required String character,
      required int usbHid,
      required int lockModes,
      required bool downOrUp,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'flutter_key_event',
          jsonEncode({
            'name': character,
            'usb_hid': usbHid,
            'lock_modes': lockModes,
            if (downOrUp) 'down': 'true',
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionHandleFlutterRawKeyEvent(
      {required UuidValue sessionId,
      required String name,
      required int platformCode,
      required int positionCode,
      required int lockModes,
      required bool downOrUp,
      dynamic hint}) {
    throw UnimplementedError("sessionHandleFlutterRawKeyEvent");
  }

  void crateFlutterFfiSessionEnterOrLeave(
      {required UuidValue sessionId, required bool enter, dynamic hint}) {
    js.context.callMethod('setByName', ['enter_or_leave', enter]);
  }

  Future<void> crateFlutterFfiSessionInputKey(
      {required UuidValue sessionId,
      required String name,
      required bool down,
      required bool press,
      required bool alt,
      required bool ctrl,
      required bool shift,
      required bool command,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'input_key',
          jsonEncode({
            'name': name,
            if (down) 'down': 'true',
            if (press) 'press': 'true',
            if (alt) 'alt': 'true',
            if (ctrl) 'ctrl': 'true',
            if (shift) 'shift': 'true',
            if (command) 'command': 'true'
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionInputString(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['input_string', value]));
  }

  Future<void> crateFlutterFfiSessionSendChat(
      {required UuidValue sessionId, required String text, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['send_chat', text]));
  }

  Future<void> crateFlutterFfiSessionPeerOption(
      {required UuidValue sessionId,
      required String name,
      required String value,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'option:session',
          jsonEncode({'name': name, 'value': value})
        ]));
  }

  Future<String> crateFlutterFfiSessionGetPeerOption(
      {required UuidValue sessionId, required String name, dynamic hint}) {
    return Future(
        () => js.context.callMethod('getByName', ['option:session', name]));
  }

  Future<void> crateFlutterFfiSessionInputOsPassword(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['input_os_password', value]));
  }

  Future<void> crateFlutterFfiSessionReadRemoteDir(
      {required UuidValue sessionId,
      required String path,
      required bool includeHidden,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'read_remote_dir',
          jsonEncode({'path': path, 'include_hidden': includeHidden})
        ]));
  }

  Future<void> crateFlutterFfiSessionSendFiles(
      {required UuidValue sessionId,
      required int actId,
      required String path,
      required String to,
      required int fileNum,
      required bool includeHidden,
      required bool isRemote,
      required bool isDir,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'send_files',
          jsonEncode({
            'id': actId,
            'path': path,
            'to': to,
            'file_num': fileNum,
            'include_hidden': includeHidden,
            'is_remote': isRemote,
            'is_dir': isDir,
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionSetConfirmOverrideFile(
      {required UuidValue sessionId,
      required int actId,
      required int fileNum,
      required bool needOverride,
      required bool remember,
      required bool isUpload,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'confirm_override_file',
          jsonEncode({
            'id': actId,
            'file_num': fileNum,
            'need_override': needOverride,
            'remember': remember,
            'is_upload': isUpload
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionRemoveFile(
      {required UuidValue sessionId,
      required int actId,
      required String path,
      required int fileNum,
      required bool isRemote,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'remove_file',
          jsonEncode({
            'id': actId,
            'path': path,
            'file_num': fileNum,
            'is_remote': isRemote
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionReadDirToRemoveRecursive(
      {required UuidValue sessionId,
      required int actId,
      required String path,
      required bool isRemote,
      required bool showHidden,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'read_dir_to_remove_recursive',
          jsonEncode({
            'id': actId,
            'path': path,
            'is_remote': isRemote,
            'show_hidden': showHidden
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionRemoveAllEmptyDirs(
      {required UuidValue sessionId,
      required int actId,
      required String path,
      required bool isRemote,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'remove_all_empty_dirs',
          jsonEncode({'id': actId, 'path': path, 'is_remote': isRemote})
        ]));
  }

  Future<void> crateFlutterFfiSessionCancelJob(
      {required UuidValue sessionId, required int actId, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['cancel_job', actId]));
  }

  Future<void> crateFlutterFfiSessionCreateDir(
      {required UuidValue sessionId,
      required int actId,
      required String path,
      required bool isRemote,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'create_dir',
          jsonEncode({'id': actId, 'path': path, 'is_remote': isRemote})
        ]));
  }

  Future<String> crateFlutterFfiSessionReadLocalDirSync(
      {required UuidValue sessionId,
      required String path,
      required bool showHidden,
      dynamic hint}) {
    throw UnimplementedError("sessionReadLocalDirSync");
  }

  Future<String> crateFlutterFfiSessionGetPlatform(
      {required UuidValue sessionId, required bool isRemote, dynamic hint}) {
    if (isRemote) {
      return Future(() => js.context.callMethod('getByName', ['platform']));
    } else {
      return Future(() => 'Web');
    }
  }

  Future<void> crateFlutterFfiSessionLoadLastTransferJobs(
      {required UuidValue sessionId, dynamic hint}) {
    throw UnimplementedError("sessionLoadLastTransferJobs");
  }

  Future<void> crateFlutterFfiSessionAddJob(
      {required UuidValue sessionId,
      required int actId,
      required String path,
      required String to,
      required int fileNum,
      required bool includeHidden,
      required bool isRemote,
      dynamic hint}) {
    throw UnimplementedError("sessionAddJob");
  }

  Future<void> crateFlutterFfiSessionResumeJob(
      {required UuidValue sessionId,
      required int actId,
      required bool isRemote,
      dynamic hint}) {
    throw UnimplementedError("sessionResumeJob");
  }

  Future<void> crateFlutterFfiSessionElevateDirect(
      {required UuidValue sessionId, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['elevate_direct']));
  }

  Future<void> crateFlutterFfiSessionElevateWithLogon(
      {required UuidValue sessionId,
      required String username,
      required String password,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'elevate_with_logon',
          jsonEncode({'username': username, 'password': password})
        ]));
  }

  Future<void> crateFlutterFfiSessionSwitchSides(
      {required UuidValue sessionId, dynamic hint}) {
    throw UnimplementedError("sessionSwitchSides");
  }

  Future<void> crateFlutterFfiSessionChangeResolution(
      {required UuidValue sessionId,
      required int display,
      required int width,
      required int height,
      dynamic hint}) {
    // note: restore on disconnected
    return Future(() => js.context.callMethod('setByName', [
          'change_resolution',
          jsonEncode({'display': display, 'width': width, 'height': height})
        ]));
  }

  Future<void> crateFlutterFfiSessionSetSize(
      {required UuidValue sessionId,
      required int display,
      required int width,
      required int height,
      dynamic hint}) {
    return Future.value();
  }

  Future<void> crateFlutterFfiSessionSendSelectedSessionId(
      {required UuidValue sessionId, required String sid, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['selected_sid', sid]));
  }

  Future<List<String>> crateFlutterFfiMainGetSoundInputs({dynamic hint}) {
    throw UnimplementedError("mainGetSoundInputs");
  }

  Future<String?> mainGetDefaultSoundInput({dynamic hint}) {
    throw UnimplementedError("mainGetDefaultSoundInput");
  }

  String crateFlutterFfiMainGetLoginDeviceInfo({dynamic hint}) {
    String userAgent = html.window.navigator.userAgent;
    String appName = html.window.navigator.appName;
    String appVersion = html.window.navigator.appVersion;
    String? platform = html.window.navigator.platform;
    return jsonEncode({
      'os': '$userAgent, $appName $appVersion ($platform)',
      'type': 'Web client',
      'name': js.context.callMethod('getByName', ['my_name']),
    });
  }

  Future<void> crateFlutterFfiMainChangeId({required String newId, dynamic hint}) {
    throw UnimplementedError("mainChangeId");
  }

  Future<String> crateFlutterFfiMainGetAsyncStatus({dynamic hint}) {
    throw UnimplementedError("mainGetAsyncStatus");
  }

  Future<String> crateFlutterFfiMainGetOption({required String key, dynamic hint}) {
    return Future.value(mainGetOptionSync(key: key));
  }

  String crateFlutterFfiMainGetOptionSync({required String key, dynamic hint}) {
    return js.context.callMethod('getByName', ['option', key]);
  }

  Future<String> crateFlutterFfiMainGetError({dynamic hint}) {
    throw UnimplementedError("mainGetError");
  }

  Future<void> crateFlutterFfiMainSetOption(
      {required String key, required String value, dynamic hint}) {
    js.context.callMethod('setByName', [
      'option',
      jsonEncode({'name': key, 'value': value})
    ]);
    return Future.value();
  }

  // get server settings
  Future<String> crateFlutterFfiMainGetOptions({dynamic hint}) {
    return Future(() => mainGetOptionsSync());
  }

  // get server settings
  String crateFlutterFfiMainGetOptionsSync({dynamic hint}) {
    return js.context.callMethod('getByName', ['options']);
  }

  Future<void> crateFlutterFfiMainSetOptions({required String json, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['options', json]));
  }

  Future<String> crateFlutterFfiMainTestIfValidServer(
      {required String server, required bool testWithProxy, dynamic hint}) {
    // TODO: implement
    return Future.value('');
  }

  Future<void> crateFlutterFfiMainSetSocks(
      {required String proxy,
      required String username,
      required String password,
      dynamic hint}) {
    throw UnimplementedError("mainSetSocks");
  }

  Future<List<String>> crateFlutterFfiMainGetSocks({dynamic hint}) {
    throw UnimplementedError("mainGetSocks");
  }

  Future<String> crateFlutterFfiMainGetAppName({dynamic hint}) {
    return Future.value(mainGetAppNameSync(hint: hint));
  }

  String crateFlutterFfiMainGetAppNameSync({dynamic hint}) {
    return js.context.callMethod('getByName', ['app-name']);
  }

  String crateFlutterFfiMainUriPrefixSync({dynamic hint}) {
    throw UnimplementedError("mainUriPrefixSync");
  }

  Future<String> crateFlutterFfiMainGetLicense({dynamic hint}) {
    // TODO: implement
    return Future(() => '');
  }

  Future<String> crateFlutterFfiMainGetVersion({dynamic hint}) {
    return Future(() => js.context.callMethod('getByName', ['version']));
  }

  Future<List<String>> crateFlutterFfiMainGetFav({dynamic hint}) {
    List<String> favs = [];
    try {
      favs = (jsonDecode(js.context.callMethod('getByName', ['fav']))
              as List<dynamic>)
          .map((e) => e.toString())
          .toList();
    } catch (e) {
      debugPrint('Failed to load favs: $e');
    }
    return Future.value(favs);
  }

  Future<void> crateFlutterFfiMainStoreFav({required List<String> favs, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['fav', jsonEncode(favs)]));
  }

  String crateFlutterFfiMainGetPeerSync({required String id, dynamic hint}) {
    // TODO:
    throw UnimplementedError("mainGetPeerSync");
  }

  Future<String> crateFlutterFfiMainGetLanPeers({dynamic hint}) {
    throw UnimplementedError("mainGetLanPeers");
  }

  Future<String> crateFlutterFfiMainGetConnectStatus({dynamic hint}) {
    return Future(
        () => js.context.callMethod('getByName', ["get_conn_status"]));
  }

  Future<void> crateFlutterFfiMainCheckConnectStatus({dynamic hint}) {
    throw UnimplementedError("mainCheckConnectStatus");
  }

  Future<bool> crateFlutterFfiMainIsUsingPublicServer({dynamic hint}) {
    return Future(() =>
        js.context.callMethod('getByName', ["is_using_public_server"]) ==
        'true');
  }

  Future<void> crateFlutterFfiMainDiscover({dynamic hint}) {
    throw UnimplementedError("mainDiscover");
  }

  Future<String> crateFlutterFfiMainGetApiServer({dynamic hint}) {
    return Future(() => js.context.callMethod('getByName', ['api_server']));
  }

  Future<void> mainPostRequest(
      {required String url,
      required String body,
      required String header,
      dynamic hint}) {
    throw UnimplementedError("mainPostRequest");
  }

  Future<bool> crateFlutterFfiMainGetProxyStatus({dynamic hint}) {
    return Future(() => false);
  }

  Future<void> crateFlutterFfiMainHttpRequest({
    required String url,
    required String method,
    String? body,
    required String header,
    dynamic hint,
  }) {
    throw UnimplementedError("mainHttpRequest");
  }

  Future<String?> crateFlutterFfiMainGetHttpStatus({required String url, dynamic hint}) {
    throw UnimplementedError("mainGetHttpStatus");
  }

  String crateFlutterFfiMainGetLocalOption({required String key, dynamic hint}) {
    final v = js.context.callMethod('getByName', ['option:local', key]);
    if (key == 'lang' && (v == 'pt' || v == 'br')) {
      return 'pt-br';
    }
    return v;
  }

  // Do not return the real environment variables.
  // Use the global variable as the environment variable in web.
  String crateFlutterFfiMainGetEnv({required String key, dynamic hint}) {
    return js.context.callMethod('getByName', ['envvar', key]);
  }

  // Use the global variable as the environment variable in web.
  void crateFlutterFfiMainSetEnv({required String key, String? value, dynamic hint}) {
    js.context.callMethod('setByName', [
      'envvar',
      jsonEncode({'name': key, 'value': value})
    ]);
  }

  Future<void> crateFlutterFfiMainSetLocalOption(
      {required String key, required String value, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'option:local',
          jsonEncode({'name': key, 'value': value})
        ]));
  }

  String crateFlutterFfiMainGetInputSource({dynamic hint}) {
    final inputSource =
        js.context.callMethod('getByName', ['option:local', 'input-source']);
    // // js grab mode
    // export const CONFIG_INPUT_SOURCE_1 = "Input source 1";
    // // flutter grab mode
    // export const CONFIG_INPUT_SOURCE_2 = "Input source 2";
    return inputSource != '' ? inputSource : 'Input source 1';
  }

  Future<void> crateFlutterFfiMainSetInputSource(
      {required UuidValue sessionId, required String value, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'option:local',
          jsonEncode({'name': 'input-source', 'value': value})
        ]));
  }

  Future<String> crateFlutterFfiMainGetMyId({dynamic hint}) {
    return Future(() => js.context.callMethod('getByName', ['my_id']));
  }

  Future<String> crateFlutterFfiMainGetUuid({dynamic hint}) {
    return Future(() => js.context.callMethod('getByName', ['uuid']));
  }

  Future<String> crateFlutterFfiMainGetPeerOption(
      {required String id, required String key, dynamic hint}) {
    return Future(() => mainGetPeerOptionSync(id: id, key: key, hint: hint));
  }

  String crateFlutterFfiMainGetPeerOptionSync(
      {required String id, required String key, dynamic hint}) {
    return js.context.callMethod('getByName', [
      'option:peer',
      jsonEncode({'id': id, 'name': key})
    ]);
  }

  String crateFlutterFfiMainGetPeerFlutterOptionSync(
      {required String id, required String k, dynamic hint}) {
    return js.context.callMethod('getByName', ['option:flutter:peer', k]);
  }

  void crateFlutterFfiMainSetPeerFlutterOptionSync(
      {required String id,
      required String k,
      required String v,
      dynamic hint}) {
    js.context.callMethod('setByName', [
      'option:flutter:peer',
      jsonEncode({'name': k, 'value': v})
    ]);
  }

  Future<void> crateFlutterFfiMainSetPeerOption(
      {required String id,
      required String key,
      required String value,
      dynamic hint}) {
    mainSetPeerOptionSync(id: id, key: key, value: value, hint: hint);
    return Future.value();
  }

  bool crateFlutterFfiMainSetPeerOptionSync(
      {required String id,
      required String key,
      required String value,
      dynamic hint}) {
    js.context.callMethod('setByName', [
      'option:peer',
      jsonEncode({'id': id, 'name': key, 'value': value})
    ]);
    return true;
  }

  Future<void> crateFlutterFfiMainSetPeerAlias(
      {required String id, required String alias, dynamic hint}) {
    mainSetPeerOptionSync(id: id, key: 'alias', value: alias, hint: hint);
    return Future.value();
  }

  Future<String> crateFlutterFfiMainGetNewStoredPeers({dynamic hint}) {
    throw UnimplementedError("mainGetNewStoredPeers");
  }

  Future<void> crateFlutterFfiMainForgetPassword({required String id, dynamic hint}) {
    return mainSetPeerOption(id: id, key: 'password', value: '');
  }

  Future<bool> crateFlutterFfiMainPeerHasPassword({required String id, dynamic hint}) {
    return Future(() =>
        js.context.callMethod('getByName', ['peer_has_password', id]) ==
        'true');
  }

  Future<bool> crateFlutterFfiMainPeerExists({required String id, dynamic hint}) {
    return Future(
        () => js.context.callMethod('getByName', ['peer_exists', id]));
  }

  Future<void> crateFlutterFfiMainLoadRecentPeers({dynamic hint}) {
    return Future(
        () => js.context.callMethod('getByName', ['load_recent_peers']));
  }

  String mainLoadRecentPeersSync({dynamic hint}) {
    return js.context.callMethod('getByName', ['load_recent_peers_sync']);
  }

  String mainLoadLanPeersSync({dynamic hint}) {
    return '{}';
  }

  Future<String> crateFlutterFfiMainLoadRecentPeersForAb(
      {required String filter, dynamic hint}) {
    throw UnimplementedError("mainLoadRecentPeersForAb");
  }

  Future<void> crateFlutterFfiMainLoadFavPeers({dynamic hint}) {
    return Future(() => js.context.callMethod('getByName', ['load_fav_peers']));
  }

  Future<void> crateFlutterFfiMainLoadLanPeers({dynamic hint}) {
    throw UnimplementedError("mainLoadLanPeers");
  }

  Future<void> crateFlutterFfiMainRemoveDiscovered({required String id, dynamic hint}) {
    throw UnimplementedError("mainRemoveDiscovered");
  }

  Future<void> crateFlutterFfiMainChangeTheme({required String dark, dynamic hint}) {
    throw UnimplementedError("mainChangeTheme");
  }

  Future<void> crateFlutterFfiMainChangeLanguage({required String lang, dynamic hint}) {
    throw UnimplementedError("mainChangeLanguage");
  }

  String crateFlutterFfiMainVideoSaveDirectory({required bool root, dynamic hint}) {
    throw UnimplementedError("mainVideoSaveDirectory");
  }

  Future<void> crateFlutterFfiMainSetUserDefaultOption(
      {required String key, required String value, dynamic hint}) {
    js.context.callMethod('setByName', [
      'option:user:default',
      jsonEncode({'name': key, 'value': value})
    ]);
    return Future.value();
  }

  String crateFlutterFfiMainGetUserDefaultOption({required String key, dynamic hint}) {
    return js.context.callMethod('getByName', ['option:user:default', key]);
  }

  Future<String> crateFlutterFfiMainHandleRelayId({required String id, dynamic hint}) {
    var newId = id;
    if (id.endsWith("\\r") || id.endsWith("/r")) {
      newId = id.substring(0, id.length - 2);
    }
    return Future.value(newId);
  }

  String crateFlutterFfiMainGetMainDisplay({dynamic hint}) {
    return js.context.callMethod('getByName', ['main_display']);
  }

  String crateFlutterFfiMainGetDisplays({dynamic hint}) {
    throw UnimplementedError("mainGetDisplays");
  }

  Future<void> crateFlutterFfiSessionAddPortForward(
      {required UuidValue sessionId,
      required int localPort,
      required String remoteHost,
      required int remotePort,
      dynamic hint}) {
    throw UnimplementedError("sessionAddPortForward");
  }

  Future<void> crateFlutterFfiSessionRemovePortForward(
      {required UuidValue sessionId, required int localPort, dynamic hint}) {
    throw UnimplementedError("sessionRemovePortForward");
  }

  Future<void> crateFlutterFfiSessionNewRdp({required UuidValue sessionId, dynamic hint}) {
    throw UnimplementedError("sessionNewRdp");
  }

  Future<void> crateFlutterFfiSessionRequestVoiceCall(
      {required UuidValue sessionId, dynamic hint}) {
    throw UnimplementedError("sessionRequestVoiceCall");
  }

  Future<void> crateFlutterFfiSessionCloseVoiceCall(
      {required UuidValue sessionId, dynamic hint}) {
    throw UnimplementedError("sessionCloseVoiceCall");
  }

  Future<void> crateFlutterFfiCmHandleIncomingVoiceCall(
      {required int id, required bool accept, dynamic hint}) {
    throw UnimplementedError("cmHandleIncomingVoiceCall");
  }

  Future<void> crateFlutterFfiCmCloseVoiceCall({required int id, dynamic hint}) {
    throw UnimplementedError("cmCloseVoiceCall");
  }

  Future<String> crateFlutterFfiMainGetLastRemoteId({dynamic hint}) {
    return Future(() => mainGetLocalOption(key: 'last_remote_id'));
  }

  Future<void> crateFlutterFfiMainGetSoftwareUpdateUrl({dynamic hint}) {
    throw UnimplementedError("mainGetSoftwareUpdateUrl");
  }

  Future<String> crateFlutterFfiMainGetHomeDir({dynamic hint}) {
    return Future.value('');
  }

  Future<String> crateFlutterFfiMainGetLangs({dynamic hint}) {
    return Future(() => js.context.callMethod('getByName', ['langs']));
  }

  Future<String> crateFlutterFfiMainGetTemporaryPassword({dynamic hint}) {
    return Future.value('');
  }

  Future<String> crateFlutterFfiMainGetFingerprint({dynamic hint}) {
    return Future.value('');
  }

  Future<String> crateFlutterFfiCmGetClientsState({dynamic hint}) {
    throw UnimplementedError("cmGetClientsState");
  }

  Future<String?> crateFlutterFfiCmCheckClientsLength({required int length, dynamic hint}) {
    throw UnimplementedError("cmCheckClientsLength");
  }

  Future<int> crateFlutterFfiCmGetClientsLength({dynamic hint}) {
    throw UnimplementedError("cmCheckClientsLength");
  }

  Future<void> crateFlutterFfiMainInit({required String appDir, dynamic hint}) {
    return Future.value();
  }

  Future<void> crateFlutterFfiMainDeviceId({required String id, dynamic hint}) {
    // TODO: ?
    throw UnimplementedError("mainDeviceId");
  }

  Future<void> crateFlutterFfiMainDeviceName({required String name, dynamic hint}) {
    // TODO: ?
    throw UnimplementedError("mainDeviceName");
  }

  Future<void> crateFlutterFfiMainRemovePeer({required String id, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['remove_peer', id]));
  }

  bool crateFlutterFfiMainHasHwcodec({dynamic hint}) {
    throw UnimplementedError("mainHasHwcodec");
  }

  bool crateFlutterFfiMainHasVram({dynamic hint}) {
    throw UnimplementedError("mainHasVram");
  }

  String crateFlutterFfiMainSupportedHwdecodings({dynamic hint}) {
    return '{}';
  }

  Future<bool> crateFlutterFfiMainIsRoot({dynamic hint}) {
    throw UnimplementedError("mainIsRoot");
  }

  int crateFlutterFfiGetDoubleClickTime({dynamic hint}) {
    return 500;
  }

  Future<void> crateFlutterFfiMainStartDbusServer({dynamic hint}) {
    throw UnimplementedError("mainStartDbusServer");
  }

  Future<void> crateFlutterFfiMainSaveAb({required String json, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['save_ab', json]));
  }

  Future<void> crateFlutterFfiMainClearAb({dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['clear_ab']));
  }

  Future<String> crateFlutterFfiMainLoadAb({dynamic hint}) {
    Completer<String> completer = Completer();
    Future<String> timeoutFuture = completer.future.timeout(
      Duration(seconds: 2),
      onTimeout: () {
        completer.completeError(TimeoutException('Load ab timed out'));
        return 'Timeout';
      },
    );
    js.context["onLoadAbFinished"] = (String s) {
      completer.complete(s);
    };
    js.context.callMethod('setByName', ['load_ab']);
    return timeoutFuture;
  }

  Future<void> crateFlutterFfiMainSaveGroup({required String json, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['save_group', json]));
  }

  Future<void> crateFlutterFfiMainClearGroup({dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['clear_group']));
  }

  Future<String> crateFlutterFfiMainLoadGroup({dynamic hint}) {
    Completer<String> completer = Completer();
    Future<String> timeoutFuture = completer.future.timeout(
      Duration(seconds: 2),
      onTimeout: () {
        completer.completeError(TimeoutException('Load group timed out'));
        return 'Timeout';
      },
    );
    js.context["onLoadGroupFinished"] = (String s) {
      completer.complete(s);
    };
    js.context.callMethod('setByName', ['load_group']);
    return timeoutFuture;
  }

  Future<void> crateFlutterFfiSessionSendPointer(
      {required UuidValue sessionId, required String msg, dynamic hint}) {
    throw UnimplementedError("sessionSendPointer");
  }

  Future<void> crateFlutterFfiSessionSendMouse(
      {required UuidValue sessionId, required String msg, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['send_mouse', msg]));
  }

  Future<void> crateFlutterFfiSessionRestartRemoteDevice(
      {required UuidValue sessionId, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['restart']));
  }

  String crateFlutterFfiSessionGetAuditServerSync(
      {required UuidValue sessionId, required String typ, dynamic hint}) {
    return js.context.callMethod('getByName', ['audit_server', typ]);
  }

  Future<void> crateFlutterFfiSessionSendNote(
      {required UuidValue sessionId, required String note, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['send_note', note]));
  }

  Future<String> crateFlutterFfiSessionAlternativeCodecs(
      {required UuidValue sessionId, dynamic hint}) {
    return Future(
        () => js.context.callMethod('getByName', ['alternative_codecs']));
  }

  Future<void> crateFlutterFfiSessionChangePreferCodec(
      {required UuidValue sessionId, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['change_prefer_codec']));
  }

  Future<void> crateFlutterFfiSessionOnWaitingForImageDialogShow(
      {required UuidValue sessionId, dynamic hint}) {
    return Future.value();
  }

  Future<void> crateFlutterFfiSessionToggleVirtualDisplay(
      {required UuidValue sessionId,
      required int index,
      required bool on,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'toggle_virtual_display',
          jsonEncode({'index': index, 'on': on})
        ]));
  }

  Future<void> crateFlutterFfiMainSetHomeDir({required String home, dynamic hint}) {
    throw UnimplementedError("mainSetHomeDir");
  }

  String crateFlutterFfiMainGetDataDirIos({dynamic hint}) {
    throw UnimplementedError("mainGetDataDirIos");
  }

  Future<void> crateFlutterFfiMainStopService({dynamic hint}) {
    throw UnimplementedError("mainStopService");
  }

  Future<void> crateFlutterFfiMainStartService({dynamic hint}) {
    throw UnimplementedError("mainStartService");
  }

  Future<void> crateFlutterFfiMainUpdateTemporaryPassword({dynamic hint}) {
    throw UnimplementedError("mainUpdateTemporaryPassword");
  }

  Future<bool> crateFlutterFfiMainSetPermanentPasswordWithResult(
      {required String password, dynamic hint}) {
    throw UnimplementedError("mainSetPermanentPasswordWithResult");
  }

  Future<bool> crateFlutterFfiMainCheckSuperUserPermission({dynamic hint}) {
    throw UnimplementedError("mainCheckSuperUserPermission");
  }

  Future<void> crateFlutterFfiMainCheckMouseTime({dynamic hint}) {
    throw UnimplementedError("mainCheckMouseTime");
  }

  Future<double> crateFlutterFfiMainGetMouseTime({dynamic hint}) {
    throw UnimplementedError("mainGetMouseTime");
  }

  Future<void> crateFlutterFfiMainWol({required String id, dynamic hint}) {
    throw UnimplementedError("mainWol");
  }

  Future<void> crateFlutterFfiMainCreateShortcut({required String id, dynamic hint}) {
    throw UnimplementedError("mainCreateShortcut");
  }

  Future<void> crateFlutterFfiCmSendChat(
      {required int connId, required String msg, dynamic hint}) {
    throw UnimplementedError("cmSendChat");
  }

  Future<void> crateFlutterFfiCmLoginRes(
      {required int connId, required bool res, dynamic hint}) {
    throw UnimplementedError("cmLoginRes");
  }

  Future<void> crateFlutterFfiCmCloseConnectionWindow({required int connId, dynamic hint}) {
    throw UnimplementedError("cmCloseConnectionWindow");
  }

  Future<void> crateFlutterFfiCmCloseConnection({required int connId, dynamic hint}) {
    throw UnimplementedError("cmCloseConnection");
  }

  Future<void> crateFlutterFfiCmRemoveDisconnectedConnection(
      {required int connId, dynamic hint}) {
    throw UnimplementedError("cmRemoveDisconnectedConnection");
  }

  Future<void> crateFlutterFfiCmCheckClickTime({required int connId, dynamic hint}) {
    throw UnimplementedError("cmCheckClickTime");
  }

  Future<double> crateFlutterFfiCmGetClickTime({dynamic hint}) {
    throw UnimplementedError("cmGetClickTime");
  }

  Future<void> crateFlutterFfiCmSwitchPermission(
      {required int connId,
      required String name,
      required bool enabled,
      dynamic hint}) {
    throw UnimplementedError("cmSwitchPermission");
  }

  bool crateFlutterFfiCmCanElevate({dynamic hint}) {
    throw UnimplementedError("cmCanElevate");
  }

  Future<void> crateFlutterFfiCmElevatePortable({required int connId, dynamic hint}) {
    throw UnimplementedError("cmElevatePortable");
  }

  Future<void> crateFlutterFfiCmSwitchBack({required int connId, dynamic hint}) {
    throw UnimplementedError("cmSwitchBack");
  }

  Future<String> crateFlutterFfiCmGetConfig({required String name, dynamic hint}) {
    throw UnimplementedError("cmGetConfig");
  }

  Future<String> crateFlutterFfiMainGetBuildDate({dynamic hint}) {
    return Future(() => js.context.callMethod('getByName', ['build_date']));
  }

  String crateFlutterFfiTranslate(
      {required String name, required String locale, dynamic hint}) {
    return js.context.callMethod('getByName', [
      'translate',
      jsonEncode({'locale': locale, 'text': name})
    ]);
  }

  int crateFlutterFfiSessionGetRgbaSize(
      {required UuidValue sessionId, required int display, dynamic hint}) {
    return 0;
  }

  void crateFlutterFfiSessionNextRgba(
      {required UuidValue sessionId, required int display, dynamic hint}) {}

  void crateFlutterFfiSessionRegisterPixelbufferTexture(
      {required UuidValue sessionId,
      required int display,
      required int ptr,
      dynamic hint}) {}

  void crateFlutterFfiSessionRegisterGpuTexture(
      {required UuidValue sessionId,
      required int display,
      required int ptr,
      dynamic hint}) {}

  Future<void> crateFlutterFfiQueryOnlines({required List<String> ids, dynamic hint}) {
    return Future(() =>
        js.context.callMethod('setByName', ['query_onlines', jsonEncode(ids)]));
  }

  // Dup to the function in hbb_common, lib.rs
  // Maybe we need to move this function to js part.
  int crateFlutterFfiVersionToNumber({required String v, dynamic hint}) {
    return int.tryParse(
            js.context.callMethod('getByName', ['get_version_number', v])) ??
        0;
  }

  Future<bool> crateFlutterFfiOptionSynced({dynamic hint}) {
    return Future.value(true);
  }

  bool crateFlutterFfiMainIsInstalled({dynamic hint}) {
    throw UnimplementedError("mainIsInstalled");
  }

  void crateFlutterFfiMainInitInputSource({dynamic hint}) {
    throw UnimplementedError("mainIsInstalled");
  }

  bool crateFlutterFfiMainIsInstalledLowerVersion({dynamic hint}) {
    throw UnimplementedError("mainIsInstalledLowerVersion");
  }

  bool crateFlutterFfiMainIsInstalledDaemon({required bool prompt, dynamic hint}) {
    throw UnimplementedError("mainIsInstalledDaemon");
  }

  bool crateFlutterFfiMainIsProcessTrusted({required bool prompt, dynamic hint}) {
    throw UnimplementedError("mainIsProcessTrusted");
  }

  bool crateFlutterFfiMainIsCanScreenRecording({required bool prompt, dynamic hint}) {
    throw UnimplementedError("mainIsCanScreenRecording");
  }

  bool crateFlutterFfiMainIsCanInputMonitoring({required bool prompt, dynamic hint}) {
    throw UnimplementedError("mainIsCanInputMonitoring");
  }

  bool crateFlutterFfiMainIsShareRdp({dynamic hint}) {
    throw UnimplementedError("mainIsShareRdp");
  }

  Future<void> crateFlutterFfiMainSetShareRdp({required bool enable, dynamic hint}) {
    throw UnimplementedError("mainSetShareRdp");
  }

  bool crateFlutterFfiMainGotoInstall({dynamic hint}) {
    throw UnimplementedError("mainGotoInstall");
  }

  String crateFlutterFfiMainGetNewVersion({dynamic hint}) {
    throw UnimplementedError("mainGetNewVersion");
  }

  bool crateFlutterFfiMainUpdateMe({dynamic hint}) {
    throw UnimplementedError("mainUpdateMe");
  }

  Future<void> crateFlutterFfiSetCurSessionId({required UuidValue sessionId, dynamic hint}) {
    throw UnimplementedError("setCurSessionId");
  }

  bool crateFlutterFfiInstallShowRunWithoutInstall({dynamic hint}) {
    throw UnimplementedError("installShowRunWithoutInstall");
  }

  Future<void> crateFlutterFfiInstallRunWithoutInstall({dynamic hint}) {
    throw UnimplementedError("installRunWithoutInstall");
  }

  Future<void> crateFlutterFfiInstallInstallMe(
      {required String options, required String path, dynamic hint}) {
    throw UnimplementedError("installInstallMe");
  }

  String crateFlutterFfiInstallInstallPath({dynamic hint}) {
    throw UnimplementedError("installInstallPath");
  }

  Future<void> crateFlutterFfiMainAccountAuth(
      {required String op, required bool rememberMe, dynamic hint}) {
    // Safari only allows auth popups while handling the original user gesture.
    // Use Future.sync so the JS call runs synchronously (pre-opening the OIDC
    // window) while any interop error still surfaces as a Future error.
    return Future.sync(() => js.context.callMethod('setByName', [
          'account_auth',
          jsonEncode({'op': op, 'remember': rememberMe})
        ]));
  }

  Future<void> crateFlutterFfiMainAccountAuthCancel({dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['account_auth_cancel']));
  }

  Future<String> crateFlutterFfiMainAccountAuthResult({dynamic hint}) {
    return Future(
        () => js.context.callMethod('getByName', ['account_auth_result']));
  }

  Future<void> crateFlutterFfiMainOnMainWindowClose({dynamic hint}) {
    throw UnimplementedError("mainOnMainWindowClose");
  }

  bool crateFlutterFfiMainCurrentIsWayland({dynamic hint}) {
    return false;
  }

  bool crateFlutterFfiMainIsLoginWayland({dynamic hint}) {
    return false;
  }

  bool crateFlutterFfiMainHideDock({dynamic hint}) {
    throw UnimplementedError("mainHideDock");
  }

  bool crateFlutterFfiMainHasFileClipboard({dynamic hint}) {
    return false;
  }

  bool crateFlutterFfiMainHasGpuTextureRender({dynamic hint}) {
    return false;
  }

  Future<void> crateFlutterFfiCmInit({dynamic hint}) {
    throw UnimplementedError("cmInit");
  }

  Future<void> crateFlutterFfiMainStartIpcUrlServer({dynamic hint}) {
    throw UnimplementedError("mainStartIpcUrlServer");
  }

  Future<void> crateFlutterFfiMainTestWallpaper({required int second, dynamic hint}) {
    // TODO: implement mainTestWallpaper
    return Future.value();
  }

  Future<bool> crateFlutterFfiMainSupportRemoveWallpaper({dynamic hint}) {
    // TODO: implement mainSupportRemoveWallpaper
    return Future.value(false);
  }

  bool crateFlutterFfiIsIncomingOnly({dynamic hint}) {
    return false;
  }

  bool crateFlutterFfiIsOutgoingOnly({dynamic hint}) {
    return false;
  }

  bool crateFlutterFfiIsCustomClient({dynamic hint}) {
    // is_custom_client() checks if app name is not "RustDesk"
    return mainGetAppNameSync(hint: hint) != "RustDesk";
  }

  bool crateFlutterFfiIsDisableSettings({dynamic hint}) {
    // Checks HARD_SETTINGS["disable-settings"] == "Y"
    return mainGetHardOption(key: "disable-settings", hint: hint) == "Y";
  }

  bool crateFlutterFfiIsDisableAb({dynamic hint}) {
    // Checks HARD_SETTINGS["disable-ab"] == "Y"
    return mainGetHardOption(key: "disable-ab", hint: hint) == "Y";
  }

  bool crateFlutterFfiIsDisableGroupPanel({dynamic hint}) {
    // Checks LocalConfig::get_option("disable-group-panel") == "Y"
    return mainGetLocalOption(key: "disable-group-panel", hint: hint) == "Y";
  }

  bool crateFlutterFfiIsDisableAccount({dynamic hint}) {
    // Checks HARD_SETTINGS["disable-account"] == "Y"
    return mainGetHardOption(key: "disable-account", hint: hint) == "Y";
  }

  bool crateFlutterFfiIsDisableInstallation({dynamic hint}) {
    return false;
  }

  Future<bool> crateFlutterFfiIsPresetPassword({dynamic hint}) {
    return Future.value(false);
  }

  Future<void> crateFlutterFfiSendUrlScheme({required String url, dynamic hint}) {
    throw UnimplementedError("sendUrlScheme");
  }

  bool crateFlutterFfiIsSupportMultiUiSession({required String version, dynamic hint}) {
    return versionToNumber(v: version) > versionToNumber(v: '1.2.4');
  }

  bool crateFlutterFfiIsSelinuxEnforcing({dynamic hint}) {
    return false;
  }

  String crateFlutterFfiMainDefaultPrivacyModeImpl({dynamic hint}) {
    throw UnimplementedError("mainDefaultPrivacyModeImpl");
  }

  String crateFlutterFfiMainSupportedPrivacyModeImpls({dynamic hint}) {
    return '[]';
  }

  String crateFlutterFfiMainSupportedInputSource({dynamic hint}) {
    return jsonEncode([
      ['Input source 1', 'input_source_1_tip'],
      ['Input source 2', 'input_source_2_tip']
    ]);
  }

  Future<String> crateFlutterFfiMainGenerate2Fa({dynamic hint}) {
    throw UnimplementedError("mainGenerate2Fa");
  }

  Future<bool> crateFlutterFfiMainVerify2Fa({required String code, dynamic hint}) {
    throw UnimplementedError("mainVerify2Fa");
  }

  bool crateFlutterFfiMainHasValid2FaSync({dynamic hint}) {
    throw UnimplementedError("mainHasValid2FaSync");
  }

  String crateFlutterFfiMainGetHardOption({required String key, dynamic hint}) {
    return mainGetLocalOption(key: key, hint: hint);
  }

  Future<void> crateFlutterFfiMainCheckHwcodec({dynamic hint}) {
    throw UnimplementedError("mainCheckHwcodec");
  }

  Future<void> crateFlutterFfiSessionRequestNewDisplayInitMsgs(
      {required UuidValue sessionId, required int display, dynamic hint}) {
    throw UnimplementedError("sessionRequestNewDisplayInitMsgs");
  }

  Future<String> crateFlutterFfiMainHandleWaylandScreencastRestoreToken(
      {required String key, required String value, dynamic hint}) {
    throw UnimplementedError("mainHandleWaylandScreencastRestoreToken");
  }

  bool crateFlutterFfiMainIsOptionFixed({required String key, dynamic hint}) {
    return false;
  }

  bool crateFlutterFfiMainGetUseTextureRender({dynamic hint}) {
    throw UnimplementedError("mainGetUseTextureRender");
  }

  bool crateFlutterFfiMainHasValidBotSync({dynamic hint}) {
    throw UnimplementedError("mainHasValidBotSync");
  }

  Future<String> crateFlutterFfiMainVerifyBot({required String token, dynamic hint}) {
    throw UnimplementedError("mainVerifyBot");
  }

  String crateFlutterFfiMainGetUnlockPin({dynamic hint}) {
    throw UnimplementedError("mainGetUnlockPin");
  }

  String crateFlutterFfiMainSetUnlockPin({required String pin, dynamic hint}) {
    throw UnimplementedError("mainSetUnlockPin");
  }

  bool crateFlutterFfiSessionGetEnableTrustedDevices(
      {required UuidValue sessionId, dynamic hint}) {
    return js.context.callMethod('getByName', ['enable_trusted_devices']) ==
        'Y';
  }

  Future<String> crateFlutterFfiMainGetTrustedDevices({dynamic hint}) {
    throw UnimplementedError("mainGetTrustedDevices");
  }

  Future<void> crateFlutterFfiMainRemoveTrustedDevices({required String json, dynamic hint}) {
    throw UnimplementedError("mainRemoveTrustedDevices");
  }

  Future<void> crateFlutterFfiMainClearTrustedDevices({dynamic hint}) {
    throw UnimplementedError("mainClearTrustedDevices");
  }

  Future<String> crateFlutterFfiGetVoiceCallInputDevice({required bool isCm, dynamic hint}) {
    throw UnimplementedError("getVoiceCallInputDevice");
  }

  Future<void> crateFlutterFfiSetVoiceCallInputDevice(
      {required bool isCm, required String device, dynamic hint}) {
    throw UnimplementedError("setVoiceCallInputDevice");
  }

  bool crateFlutterFfiIsPresetPasswordMobileOnly({dynamic hint}) {
    throw UnimplementedError("isPresetPasswordMobileOnly");
  }

  String crateFlutterFfiMainGetBuildinOption({required String key, dynamic hint}) {
    return mainGetLocalOption(key: key, hint: hint);
  }

  String crateFlutterFfiInstallInstallOptions({dynamic hint}) {
    throw UnimplementedError("installInstallOptions");
  }

  int crateFlutterFfiMainMaxEncryptLen({dynamic hint}) {
    throw UnimplementedError("mainMaxEncryptLen");
  }

  bool crateFlutterFfiMainAudioSupportLoopback({dynamic hint}) {
    return false;
  }

  Future<String> crateFlutterFfiSessionReadLocalEmptyDirsRecursiveSync(
      {required UuidValue sessionId,
      required String path,
      required bool includeHidden,
      dynamic hint}) {
    throw UnimplementedError("sessionReadLocalEmptyDirsRecursiveSync");
  }

  Future<void> crateFlutterFfiSessionReadRemoteEmptyDirsRecursiveSync(
      {required UuidValue sessionId,
      required String path,
      required bool includeHidden,
      dynamic hint}) {
    throw UnimplementedError("sessionReadRemoteEmptyDirsRecursiveSync");
  }

  Future<void> crateFlutterFfiSessionRenameFile(
      {required UuidValue sessionId,
      required int actId,
      required String path,
      required String newName,
      required bool isRemote,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'rename_file',
          jsonEncode({
            'id': actId,
            'path': path,
            'new_name': newName,
            'is_remote': isRemote
          })
        ]));
  }

  Future<void> sessionSelectFiles(
      {required UuidValue sessionId, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', ['select_files']));
  }

  String? crateFlutterFfiSessionGetConnToken({required UuidValue sessionId, dynamic hint}) {
    throw UnimplementedError("sessionGetConnToken");
  }

  String crateFlutterFfiMainGetPrinterNames({dynamic hint}) {
    return '';
  }

  Future<void> crateFlutterFfiSessionPrinterResponse(
      {required UuidValue sessionId,
      required int id,
      required String path,
      required String printerName,
      dynamic hint}) {
    throw UnimplementedError("sessionPrinterResponse");
  }

  Future<String> crateFlutterFfiMainGetCommon({required String key, dynamic hint}) {
    throw UnimplementedError("mainGetCommon");
  }

  String crateFlutterFfiMainGetCommonSync({required String key, dynamic hint}) {
    throw UnimplementedError("mainGetCommonSync");
  }

  Future<void> crateFlutterFfiMainSetCommon(
      {required String key, required String value, dynamic hint}) {
    throw UnimplementedError("mainSetCommon");
  }

  Future<String> crateFlutterFfiSessionHandleScreenshot(
      {required UuidValue sessionId, required String action, dynamic hint}) {
    throw UnimplementedError("sessionHandleScreenshot");
  }

  Future<void> crateFlutterFfiSessionSetCommon(
      {required UuidValue sessionId, required String key, required String value, dynamic hint}) {
      js.context.callMethod('setByName', [
        'common',
        jsonEncode({'name': key, 'value': value})
      ]);
      return Future.value();
  }

  String? crateFlutterFfiSessionGetCommonSync(
      {required UuidValue sessionId,
      required String key,
      required String param,
      dynamic hint}) {
    throw UnimplementedError("sessionGetCommonSync");
  }

  Future<void> crateFlutterFfiSessionTakeScreenshot(
      {required UuidValue sessionId, required int display, dynamic hint}) {
    throw UnimplementedError("sessionTakeScreenshot");
  }

  Future<void> crateFlutterFfiSessionOpenTerminal(
      {required UuidValue sessionId,
      required int terminalId,
      required int rows,
      required int cols,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'open_terminal',
          jsonEncode({
            'terminal_id': terminalId,
            'rows': rows,
            'cols': cols,
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionSendTerminalInput(
      {required UuidValue sessionId,
      required int terminalId,
      required String data,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'send_terminal_input',
          jsonEncode({
            'terminal_id': terminalId,
            'data': data,
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionResizeTerminal(
      {required UuidValue sessionId,
      required int terminalId,
      required int rows,
      required int cols,
      dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'resize_terminal',
          jsonEncode({
            'terminal_id': terminalId,
            'rows': rows,
            'cols': cols,
          })
        ]));
  }

  Future<void> crateFlutterFfiSessionCloseTerminal(
      {required UuidValue sessionId, required int terminalId, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName', [
          'close_terminal',
          jsonEncode({
            'terminal_id': terminalId,
          })
        ]));
  }

  Future<int?> crateFlutterFfiSessionGetEdgeScrollEdgeThickness(
      {required UuidValue sessionId, dynamic hint}) {
    final thickness = js.context.callMethod(
        'getByName', ['option:session', 'edge-scroll-edge-thickness']);
    return Future(() => int.tryParse(thickness) ?? 100);
  }

  Future<void> crateFlutterFfiSessionSetEdgeScrollEdgeThickness(
      {required UuidValue sessionId, required int value, dynamic hint}) {
    return Future(() => js.context.callMethod('setByName',
        ['option:session', 'edge-scroll-edge-thickness', value.toString()]));
  }

  String crateFlutterFfiSessionGetConnSessionId({required UuidValue sessionId, dynamic hint}) {
    return js.context.callMethod('getByName', ['conn_session_id']);
  }

  bool crateFlutterFfiWillSessionCloseCloseSession(
      {required UuidValue sessionId, dynamic hint}) {
    return true;
  }

  String crateFlutterFfiSessionGetLastAuditNote({required UuidValue sessionId, dynamic hint}) {
    return js.context.callMethod('getByName', ['last_audit_note']);
  }

  Future<void> crateFlutterFfiSessionSetAuditGuid(
      {required UuidValue sessionId, required String guid, dynamic hint}) {
    return Future(
        () => js.context.callMethod('setByName', ['audit_guid', guid]));
  }

  String crateFlutterFfiSessionGetAuditGuid({required UuidValue sessionId, dynamic hint}) {
    return js.context.callMethod('getByName', ['audit_guid']);
  }

  bool crateFlutterFfiMainSetCursorPosition({required int x, required int y, dynamic hint}) {
    return false;
  }

  bool crateFlutterFfiMainClipCursor(
      {required int left,
      required int top,
      required int right,
      required int bottom,
      required bool enable,
      dynamic hint}) {
    return false;
  }

  String crateFlutterFfiMainResolveAvatarUrl({required String avatar, dynamic hint}) {
    return js.context.callMethod(
            'getByName', ['resolve_avatar_url', avatar])?.toString() ??
        avatar;
  }

  Future<String> crateFlutterFfiMainDeployDevice(
      {required String token, required String id, dynamic hint}) {
    throw UnimplementedError("mainDeployDevice");
  }

  void dispose() {}
}
