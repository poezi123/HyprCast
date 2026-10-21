import 'dart:async';
import 'dart:ui' show AppExitResponse;
import 'package:flutter/material.dart';

import 'backend.dart';

void main() => runApp(const HyprCastApp());

class HyprCastApp extends StatelessWidget {
  const HyprCastApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'HyprCast',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      darkTheme: ThemeData(
          colorSchemeSeed: Colors.indigo,
          brightness: Brightness.dark,
          useMaterial3: true),
      home: const HomePage(),
    );
  }
}

const modeLabels = {
  'mirror': 'Spiegeln',
  'extend': 'Erweitern',
  'external_only': 'Nur extern',
};

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final backend = Backend();
  late final AppLifecycleListener _lifecycle;
  StreamSubscription? _sub;
  Map<String, dynamic>? state;
  String? error;
  bool remember = false;
  final urlController = TextEditingController();

  @override
  void initState() {
    super.initState();
    // Beim Schliessen des Fensters Backend sauber beenden -> setzt alles zurueck.
    _lifecycle = AppLifecycleListener(onExitRequested: () async {
      await backend.stop();
      return AppExitResponse.exit;
    });
    _connect();
  }

  Future<void> _connect() async {
    try {
      await backend.start();
      _sub = backend.events.listen(_onEvent);
      final s = await backend.getState();
      setState(() => state = s);
    } catch (e) {
      setState(() => error = '$e');
    }
  }

  void _onEvent((String, Map<String, dynamic>) event) {
    final (name, data) = event;
    if (name == 'state') {
      setState(() => state = data);
    } else if (name == 'monitor_added' && data['autoApplied'] != true) {
      _askMode(data['monitor'] as Map<String, dynamic>);
    } else if (name == 'monitor_added') {
      _toast('${_label(data['monitor'])}: gemerkte Einstellung angewendet');
    }
  }

  Future<void> _run(String cmd, [Map<String, dynamic> args = const {}]) async {
    try {
      await backend.call(cmd, args);
    } catch (e) {
      _toast('Fehler: $e');
    }
  }

  void _toast(String msg) => ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(msg)));

  String _label(dynamic mon) {
    final d = (mon['description'] as String?) ?? '';
    return d.isNotEmpty ? d : mon['name'] as String;
  }

  Future<void> _askMode(Map<String, dynamic> mon) async {
    var rememberChoice = false;
    final mode = await showDialog<String>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialog) => AlertDialog(
          title: Text('Neuer Bildschirm: ${_label(mon)}'),
          content: CheckboxListTile(
            value: rememberChoice,
            onChanged: (v) => setDialog(() => rememberChoice = v ?? false),
            title: const Text('Für dieses Gerät merken'),
            contentPadding: EdgeInsets.zero,
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Nichts tun')),
            for (final e in modeLabels.entries)
              FilledButton.tonal(
                  onPressed: () => Navigator.pop(ctx, e.key),
                  child: Text(e.value)),
          ],
        ),
      ),
    );
    if (mode != null) {
      await _run('set_mode',
          {'mode': mode, 'external': mon['name'], 'remember': rememberChoice});
    }
  }

  @override
  void dispose() {
    _sub?.cancel();
    _lifecycle.dispose();
    backend.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('HyprCast')),
      body: error != null
          ? Center(child: Text('Backend-Fehler:\n$error', textAlign: TextAlign.center))
          : state == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _displaysCard(),
                    const SizedBox(height: 12),
                    _presentationCard(),
                    const SizedBox(height: 12),
                    _wirelessCard(),
                  ],
                ),
    );
  }

  Widget _displaysCard() {
    final monitors = (state!['monitors'] as List).cast<Map<String, dynamic>>();
    final externals = monitors.where((m) => m['internal'] != true).toList();
    final active = state!['active'] as Map<String, dynamic>?;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Bildschirme', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            for (final m in monitors)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(m['internal'] == true ? Icons.laptop : Icons.tv),
                title: Text(_label(m)),
                subtitle: Text('${m['name']} · ${m['mode']}'
                    '${m['mirrorOf'] != 'none' ? ' · spiegelt ${m['mirrorOf']}' : ''}'
                    '${m['profile'] != null ? ' · gemerkt: ${modeLabels[m['profile']['mode']]}' : ''}'),
                trailing: m['profile'] != null
                    ? IconButton(
                        tooltip: 'Gemerkte Einstellung vergessen',
                        icon: const Icon(Icons.bookmark_remove),
                        onPressed: () => _run('forget_profile', {'key': m['key']}))
                    : null,
              ),
            if (externals.isEmpty)
              const Text('Kein externer Bildschirm erkannt. '
                  'HDMI-Kabel einstecken – die App meldet sich dann.'),
            for (final ext in externals) ...[
              const SizedBox(height: 8),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final e in modeLabels.entries)
                  ChoiceChip(
                    label: Text(e.value),
                    selected: active?['external'] == ext['name'] &&
                        active?['mode'] == e.key,
                    onSelected: (_) => _run('set_mode', {
                      'mode': e.key,
                      'external': ext['name'],
                      'remember': remember,
                    }),
                  ),
              ]),
            ],
            if (externals.isNotEmpty)
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                value: remember,
                onChanged: (v) => setState(() => remember = v ?? false),
                title: const Text('Auswahl für dieses Gerät merken'),
              ),
            if (active != null)
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  icon: const Icon(Icons.restore),
                  label: const Text('Zurücksetzen'),
                  onPressed: () => _run('restore'),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _presentationCard() {
    return Card(
      child: SwitchListTile(
        secondary: const Icon(Icons.slideshow),
        title: const Text('Präsentationsmodus'),
        subtitle: const Text('Keine Bildschirmsperre, kein Standby'),
        value: state!['presentation'] == true,
        onChanged: (v) => _run('set_presentation', {'on': v}),
      ),
    );
  }

  Widget _wirelessCard() {
    final cast = state!['cast'] as Map<String, dynamic>;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Kabellos zur Tafel (iiShare)',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            const Text('Adresse oder Code von der Tafel eingeben '
                '(steht dort, wenn Teilen bereit ist):'),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                child: TextField(
                  controller: urlController,
                  decoration: const InputDecoration(
                      border: OutlineInputBorder(), hintText: 'z.B. 192.168.1.50'),
                  onSubmitted: (v) => _run('open_url', {'url': v.trim()}),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: () => _run('open_url', {'url': urlController.text.trim()}),
                child: const Text('Öffnen'),
              ),
            ]),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              icon: const Icon(Icons.cast),
              label: Text(cast['miracastInstalled'] == true
                  ? 'Miracast / Chromecast'
                  : 'Miracast / Chromecast (gnome-network-displays fehlt)'),
              onPressed: cast['miracast'] == true ? () => _run('launch_miracast') : null,
            ),
          ],
        ),
      ),
    );
  }
}

