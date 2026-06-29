import argparse
import csv
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Convert tcstats JSON to CSV.')
    parser.add_argument('input', help='path to input JSON file')
    parser.add_argument('output', nargs='?', help='path to output CSV file')
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_suffix('.csv')

    with open(input_path, 'r', encoding='utf-8') as f:
        data = sort_by_key(json.load(f))
        print('read', len(data), 'items from', input_path)
        with open(output_path, 'w', newline='', encoding='utf-8') as out_file:
            writer = csv.writer(out_file)
            writer.writerow(['temperature', 'success', 'short circuit'])
            for t, stats in data.items():
                writer.writerow([t, stats.get('success', ''), stats.get('short circuit', '')])
    print('wrote', output_path)


def sort_by_key(data):
    # Sort by numeric key value
    try:
        sorted_dict = dict(
            sorted(
                data.items(),
                key=lambda item: int(item[0])  # Convert keys to int for numeric sorting
            )
        )

        return sorted_dict

    except ValueError:
        print('Error: All keys must be convertible to integers for numeric sorting.')


if __name__ == '__main__':
    main()