import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// Startet das Python-Backend und spricht mit ihm ueber JSON-Zeilen auf
/// einem Unix-Socket. Siehe backend/hyprcast/server.py fuer das Protokoll.
class Backend {
  Process? _process;
  Socket? _socket;
  int _nextId = 1;
  final _pending = <int, Completer<dynamic>>{};
  final _events = StreamController<(String, Map<String, dynamic>)>.broadcast();

  /// (eventname, daten), z.B. ('state', {...}) oder ('monitor_added', {...})
  Stream<(String, Map<String, dynamic>)> get events => _events.stream;

  static String get socketPath =>
      '${Platform.environment['XDG_RUNTIME_DIR'] ?? '/tmp'}/hyprcast.sock';

  /// Backend-Ordner: HYPRCAST_BACKEND, sonst ../backend neben der
  /// installierten App, sonst ../backend relativ zum Arbeitsverzeichnis
  /// (beim Entwickeln: `flutter run` im app-Ordner).
  static String get backendDir {
    final env = Platform.environment['HYPRCAST_BACKEND'];
    if (env != null) return env;
    final installed =
        Directory('${File(Platform.resolvedExecutable).parent.path}/../backend');
    if (installed.existsSync()) return installed.absolute.path;
    return Directory('${Directory.current.path}/../backend').absolute.path;
  }

  Future<void> start() async {
    _process = await Process.start(
      'python3',
      ['-m', 'hyprcast', '--exit-with-parent'],
      workingDirectory: backendDir,
    );
    _process!.stderr.transform(utf8.decoder).listen(stderr.write);

    // Warten, bis der Socket da ist.
    for (var i = 0; i < 50; i++) {
      try {
        _socket = await Socket.connect(
            InternetAddress(socketPath, type: InternetAddressType.unix), 0);
        break;
      } on SocketException {
        await Future.delayed(const Duration(milliseconds: 100));
      }
    }
    if (_socket == null) {
      throw StateError('Backend antwortet nicht ($socketPath)');
    }

    _socket!
        .cast<List<int>>()
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen(_onLine);
  }

  void _onLine(String line) {
    final msg = jsonDecode(line) as Map<String, dynamic>;
    if (msg.containsKey('event')) {
      _events.add((msg['event'] as String, msg['data'] as Map<String, dynamic>));
      return;
    }
    final completer = _pending.remove(msg['id']);
    if (completer == null) return;
    if (msg['ok'] == true) {
      completer.complete(msg['result']);
    } else {
      completer.completeError(msg['error'] ?? 'Unbekannter Fehler');
    }
  }

  Future<dynamic> call(String cmd, [Map<String, dynamic> args = const {}]) {
    final id = _nextId++;
    final completer = Completer<dynamic>();
    _pending[id] = completer;
    _socket!.write('${jsonEncode({'id': id, 'cmd': cmd, 'args': args})}\n');
    return completer.future;
  }

  Future<Map<String, dynamic>> getState() async =>
      (await call('get_state')) as Map<String, dynamic>;

  /// Beendet das Backend; es setzt dabei alles zurueck.
  Future<void> stop() async {
    await _socket?.close();
    _process?.kill(ProcessSignal.sigterm);
    await _process?.exitCode.timeout(const Duration(seconds: 3), onTimeout: () {
      _process?.kill(ProcessSignal.sigkill);
      return -1;
    });
  }
}
