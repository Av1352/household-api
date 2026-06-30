import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'grocery_categories.dart';
import 'api_service.dart';

double _normalizeQuantity(double qty, String unit) {
  switch (unit.toLowerCase()) {
    case 'kg':
      return qty * 1000;
    case 'g':
      return qty;
    case 'l':
      return qty * 1000;
    case 'ml':
      return qty;
    default:
      return qty;
  }
}

class _Row {
  final TextEditingController name;
  final TextEditingController qty;
  final TextEditingController unit;
  final TextEditingController price;
  String category;

  _Row({
    required String name,
    required double qty,
    required String unit,
    required double price,
    required this.category,
  })  : name = TextEditingController(text: name),
        qty = TextEditingController(text: _trim(qty)),
        unit = TextEditingController(text: unit),
        price = TextEditingController(text: _trim(price));

  static String _trim(double v) {
    if (v == v.roundToDouble()) return v.toInt().toString();
    return v.toString();
  }

  void dispose() {
    name.dispose();
    qty.dispose();
    unit.dispose();
    price.dispose();
  }
}

class ScanReceiptPage extends StatefulWidget {
  const ScanReceiptPage({Key? key}) : super(key: key);

  @override
  State<ScanReceiptPage> createState() => _ScanReceiptPageState();
}

class _ScanReceiptPageState extends State<ScanReceiptPage> {
  final ImagePicker _picker = ImagePicker();
  bool _loading = false;
  String? _error;
  List<_Row> _rows = [];

  @override
  void dispose() {
    for (final r in _rows) {
      r.dispose();
    }
    super.dispose();
  }

  Future<void> _pickAndScan(ImageSource source) async {
    final XFile? file = await _picker.pickImage(
      source: source,
      imageQuality: 70,
      maxWidth: 1600,
    );
    if (file == null) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final bytes = await file.readAsBytes();
      final items = await ApiService.scanReceipt(bytes, file.name);

      for (final r in _rows) {
        r.dispose();
      }

      setState(() {
        _rows = items.map((e) {
          final cat = (e['category'] ?? 'Others').toString();
          return _Row(
            name: (e['name'] ?? '').toString(),
            qty: (e['quantity'] as num?)?.toDouble() ?? 1,
            unit: (e['unit'] ?? '').toString(),
            price: (e['price'] as num?)?.toDouble() ?? 0,
            category: kCategories.contains(cat) ? cat : 'Others',
          );
        }).toList();
        _loading = false;
      });

      if (_rows.isEmpty) {
        setState(() => _error = 'No items found on that bill. Try a clearer photo.');
      }
    } catch (e) {
      setState(() {
        _loading = false;
        _error = 'Could not read the bill: $e';
      });
    }
  }

  Future<void> _confirmAll() async {
    List<Map<String, dynamic>> items;
    try {
      items = await ApiService.getItems();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Could not reach server: $e')));
      return;
    }

    int added = 0;
    int updated = 0;
    try {
      for (final r in _rows) {
        final name = r.name.text.trim();
        if (name.isEmpty) continue;
        final qty = double.tryParse(r.qty.text) ?? 0.0;
        final unit = r.unit.text.trim();
        final price = double.tryParse(r.price.text) ?? 0.0;
        final normalized = _normalizeQuantity(qty, unit);
        final unitPrice = normalized > 0 ? price / normalized : 0.0;

        final existing = items.firstWhere(
          (e) =>
              (e['name'] ?? '').toString().toLowerCase() == name.toLowerCase(),
          orElse: () => <String, dynamic>{},
        );

        if (existing.isNotEmpty) {
          // Same item bought again: update it and grow its price history.
          final history = (existing['price_history'] as List?)
                  ?.map((e) => (e as num).toDouble())
                  .toList() ??
              <double>[];
          if (history.isEmpty || history.last != unitPrice) {
            history.add(unitPrice);
          }
          await ApiService.updateItem((existing['id'] as num).toInt(), {
            'name': existing['name'],
            'quantity': qty,
            'unit': unit,
            'category': existing['category'],
            'low_stock_threshold':
                (existing['low_stock_threshold'] as num?)?.toDouble() ?? 0.0,
            'restock_days': (existing['restock_days'] as num?)?.toInt() ?? 0,
            'last_restocked': DateTime.now().toIso8601String(),
            'price_history': history,
          });
          updated++;
        } else {
          await ApiService.createItem({
            'name': name,
            'quantity': qty,
            'unit': unit,
            'category': r.category,
            'low_stock_threshold': 0.0,
            'restock_days': 0,
            'price_history': [unitPrice],
          });
          added++;
        }
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Save failed: $e')));
      return;
    }

    if (!mounted) return;
    final parts = <String>[];
    if (added > 0) parts.add('$added added');
    if (updated > 0) parts.add('$updated updated');
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(parts.isEmpty ? 'Nothing to save' : parts.join(', ')),
      ),
    );
    Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan a bill')),
      body: _loading
          ? const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 16),
                  Text('Reading the bill...'),
                ],
              ),
            )
          : _rows.isEmpty
              ? _pickerView()
              : _reviewView(),
    );
  }

  Widget _pickerView() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.receipt_long, size: 72, color: Colors.teal),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: () => _pickAndScan(ImageSource.camera),
            icon: const Icon(Icons.camera_alt),
            label: const Text('Take a photo'),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: () => _pickAndScan(ImageSource.gallery),
            icon: const Icon(Icons.photo_library),
            label: const Text('Choose from gallery'),
          ),
          if (_error != null) ...[
            const SizedBox(height: 20),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Text(
                _error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.red),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _reviewView() {
    return Column(
      children: [
        const Padding(
          padding: EdgeInsets.all(12),
          child: Text(
            'Check the items, fix anything off, then save.',
            style: TextStyle(fontWeight: FontWeight.w600),
          ),
        ),
        Expanded(
          child: ListView.builder(
            itemCount: _rows.length,
            itemBuilder: (_, i) {
              final r = _rows[i];
              return Card(
                margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                child: Padding(
                  padding: const EdgeInsets.all(8),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: r.name,
                              decoration:
                                  const InputDecoration(labelText: 'Name'),
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close, color: Colors.red),
                            onPressed: () {
                              setState(() {
                                r.dispose();
                                _rows.removeAt(i);
                              });
                            },
                          ),
                        ],
                      ),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: r.qty,
                              keyboardType: TextInputType.number,
                              decoration:
                                  const InputDecoration(labelText: 'Qty'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: TextField(
                              controller: r.unit,
                              decoration:
                                  const InputDecoration(labelText: 'Unit'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: TextField(
                              controller: r.price,
                              keyboardType:
                                  const TextInputType.numberWithOptions(
                                      decimal: true),
                              decoration:
                                  const InputDecoration(labelText: 'Price'),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      DropdownButtonFormField<String>(
                        value: r.category,
                        decoration:
                            const InputDecoration(labelText: 'Category'),
                        items: kCategories
                            .map((c) => DropdownMenuItem(
                                  value: c,
                                  child: Text(c),
                                ))
                            .toList(),
                        onChanged: (v) => setState(() => r.category = v!),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _rows.isEmpty ? null : _confirmAll,
              icon: const Icon(Icons.check),
              label: Text('Add ${_rows.length} items to inventory'),
            ),
          ),
        ),
      ],
    );
  }
}
