import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;

/// Talks to the Household API backend.
///
/// Configure at run time, nothing secret in the repo:
///   flutter run \
///     --dart-define=API_BASE_URL=https://your-app.up.railway.app \
///     --dart-define=API_TOKEN=your-token
///
/// Default base URL is the Android emulator's alias for your PC's localhost,
/// so it works out of the box against a server you run locally.
class ApiService {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
  static const String token = String.fromEnvironment('API_TOKEN');

  static Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'X-API-Token': token,
      };

  static void _check(http.Response r) {
    if (r.statusCode >= 400) {
      throw Exception('Server ${r.statusCode}: ${r.body}');
    }
  }

  static Future<List<Map<String, dynamic>>> _getList(String path) async {
    final r = await http.get(Uri.parse('$baseUrl$path'), headers: _headers);
    _check(r);
    return List<Map<String, dynamic>>.from(json.decode(r.body));
  }

  // ---- Items ----
  static Future<List<Map<String, dynamic>>> getItems() => _getList('/items');

  static Future<List<Map<String, dynamic>>> getToBuy() => _getList('/to-buy');

  static Future<void> createItem(Map<String, dynamic> item) async {
    final r = await http.post(Uri.parse('$baseUrl/items'),
        headers: _headers, body: json.encode(item));
    _check(r);
  }

  static Future<void> updateItem(int id, Map<String, dynamic> item) async {
    final r = await http.put(Uri.parse('$baseUrl/items/$id'),
        headers: _headers, body: json.encode(item));
    _check(r);
  }

  static Future<void> deleteItem(int id) async {
    final r =
        await http.delete(Uri.parse('$baseUrl/items/$id'), headers: _headers);
    _check(r);
  }

  static Future<void> gotIt(int id) async {
    final r = await http.post(Uri.parse('$baseUrl/items/$id/got-it'),
        headers: _headers);
    _check(r);
  }

  static Future<int> seedStaples() async {
    final r = await http.post(Uri.parse('$baseUrl/items/seed-staples'),
        headers: _headers);
    _check(r);
    return (json.decode(r.body)['added'] as num).toInt();
  }

  // ---- Bills ----
  static Future<List<Map<String, dynamic>>> getBills() => _getList('/bills');

  static Future<List<Map<String, dynamic>>> getToPay() => _getList('/to-pay');

  static Future<void> createBill(Map<String, dynamic> bill) async {
    final r = await http.post(Uri.parse('$baseUrl/bills'),
        headers: _headers, body: json.encode(bill));
    _check(r);
  }

  static Future<void> updateBill(int id, Map<String, dynamic> bill) async {
    final r = await http.put(Uri.parse('$baseUrl/bills/$id'),
        headers: _headers, body: json.encode(bill));
    _check(r);
  }

  static Future<void> deleteBill(int id) async {
    final r =
        await http.delete(Uri.parse('$baseUrl/bills/$id'), headers: _headers);
    _check(r);
  }

  static Future<void> markPaid(int id) async {
    final r = await http.post(Uri.parse('$baseUrl/bills/$id/paid'),
        headers: _headers);
    _check(r);
  }

  // ---- Report ----
  static Future<Map<String, dynamic>> getReport() async {
    final r = await http.get(Uri.parse('$baseUrl/report'), headers: _headers);
    _check(r);
    return Map<String, dynamic>.from(json.decode(r.body));
  }

  // ---- Scan a bill (server calls Claude; key never on the phone) ----
  static Future<List<Map<String, dynamic>>> scanReceipt(
      Uint8List bytes, String filename) async {
    final req = http.MultipartRequest('POST', Uri.parse('$baseUrl/scan'));
    req.headers['X-API-Token'] = token;
    req.files
        .add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    final streamed = await req.send();
    final r = await http.Response.fromStream(streamed);
    _check(r);
    return List<Map<String, dynamic>>.from(json.decode(r.body));
  }
}
