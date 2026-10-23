"""Complete finite-file results, independent of bounded Web replay history."""
import threading


class FileResults:
    def __init__(self):
        self.lock = threading.Lock()
        self.rows = {}

    def accept(self, event):
        if event.get('type') != 'translation' or 'id' not in event:
            return
        with self.lock:
            key = event['id']
            if 'source_text' in event:
                self.rows[key] = {k: v for k, v in event.items()
                                  if k not in ('type', 'kind', 'sid', 'pending')}
            if key not in self.rows:
                return
            row = self.rows[key]
            row['status'] = event['kind']
            for name in ('revision', 'error', 'first_ms', 'complete_ms', 'stats'):
                if name in event:
                    row[name] = event[name]
            if event['kind'] == 'chunk':
                row['translation'] += event['piece']
            elif event['kind'] in ('done', 'cancelled') and 'text' in event:
                row['translation'] = event['text']

    def snapshot(self):
        with self.lock:
            return [dict(self.rows[key]) for key in sorted(self.rows)]
