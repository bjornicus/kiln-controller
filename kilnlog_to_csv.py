import sys
import json
import csv
import os

def convert_kilnlog_to_csv(json_path, csv_path=None):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not csv_path:
        base, _ = os.path.splitext(json_path)
        csv_path = base + '.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['runtime', 'temperature', 'pidstats.time'])
        for item in data:
            pid_time = ''
            pidstats = item.get('pidstats')
            if isinstance(pidstats, dict):
                pid_time = pidstats.get('time', '')
            writer.writerow([
                item.get('runtime', ''),
                item.get('temperature', ''),
                pid_time
            ])
    print(f'Wrote {csv_path}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python kilnlog_to_csv.py <kilnlog.json> [output.csv]')
        sys.exit(1)
    json_path = sys.argv[1]
    csv_path = sys.argv[2] if len(sys.argv) > 2 else None
    convert_kilnlog_to_csv(json_path, csv_path)
