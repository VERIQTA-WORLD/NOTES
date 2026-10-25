"""Render a standalone logrotate configuration for the short-lived task logs."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if any(c in str(ROOT) for c in ['"','\n','\r']):raise SystemExit('Use a path without quotes or newlines')
print('"'+str(ROOT/'runtime/logs/*.log')+'" "'+str(ROOT/'runtime/logs/*.jsonl')+'" {')
print('    daily\n    rotate 7\n    compress\n    delaycompress\n    missingok\n    notifempty\n    create 0600\n}')
