import argparse
import boto3
import datetime
import os
import re
from typing import Optional

# ----------- DEFAULTS -----------
REGION = 'us-east-1'

def get_available_log_regions() -> list[str]:
    session = boto3.session.Session()
    regions = session.get_available_regions('logs')
    return sorted(set(regions))

def select_region_menu(default_region: str = REGION) -> str:
    regions = get_available_log_regions()
    if not regions:
        print(f"Could not load region list. Falling back to {default_region}.")
        return default_region

    print("Available AWS regions:")
    for idx, region in enumerate(regions, start=1):
        label = " (default)" if region == default_region else ""
        print(f"[{idx}] {region}{label}")
    print("[0] Enter region manually")

    choice = input(f"Select region [default: {default_region}]: ").strip()
    if not choice:
        return default_region
    if choice == '0':
        manual = input("Enter AWS region (e.g. us-east-1): ").strip()
        return manual or default_region

    try:
        selected = int(choice)
        if 1 <= selected <= len(regions):
            return regions[selected - 1]
    except ValueError:
        pass

    # If a user types a region name directly, accept it.
    if choice in regions:
        return choice

    print(f"Invalid selection. Falling back to {default_region}.")
    return default_region

def _today_start_iso() -> str:
    now = datetime.datetime.now()
    start = datetime.datetime(now.year, now.month, now.day)
    return start.isoformat()

def _today_end_iso() -> str:
    now = datetime.datetime.now()
    start = datetime.datetime(now.year, now.month, now.day)
    end = start + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
    return end.isoformat()

# Dynamic defaults: start of today and end of today (local time)
START_TIME = _today_start_iso() # 2025-11-03T00:00:00
END_TIME = _today_end_iso()     # 2025-11-03T23:59:59
# ---------------------------------

RELATIVE_TIME_RE = re.compile(r'^-(\d+)([hmd])$')

def _sanitize_filename_component(value: str) -> str:
    # Replace path separators and characters that are invalid on common filesystems.
    return re.sub(r'[^A-Za-z0-9._-]+', '_', value.strip('/').strip())

def _format_time_for_filename(epoch_ms: int) -> str:
    dt = datetime.datetime.fromtimestamp(epoch_ms / 1000)
    return dt.strftime('%Y%m%dT%H%M%S')

def _build_output_path(log_group: str, start_ms: int, end_ms: int) -> str:
    filename = f"{_sanitize_filename_component(log_group)}-{_format_time_for_filename(start_ms)}-{_format_time_for_filename(end_ms)}.txt"
    return os.path.join('logs', filename)

def parse_time_to_epoch_ms(value: str) -> int:
    """
    Convert a time string to epoch milliseconds.

    Accepted formats:
    - ISO 8601 (e.g., 2025-11-03T00:00:00 or 2025-11-03T00:00:00+00:00 or ...Z)
    - Unix epoch seconds (e.g., 1730678400)
    - Unix epoch milliseconds (e.g., 1730678400000)

    Naive ISO datetimes are interpreted in local time.

    Relative format:
    - -<number>h (hours ago)
    - -<number>m (minutes ago)
    - -<number>d (days ago)
    Examples: -24h, -20m, -10d, -0h
    """
    s = value.strip()

    # Relative times from now, such as -24h / -20m / -10d / -0h
    relative_match = RELATIVE_TIME_RE.fullmatch(s)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        now = datetime.datetime.now()
        if unit == 'h':
            dt = now - datetime.timedelta(hours=amount)
        elif unit == 'm':
            dt = now - datetime.timedelta(minutes=amount)
        else:
            dt = now - datetime.timedelta(days=amount)
        return int(dt.timestamp() * 1000)

    # Numeric epochs
    if s.isdigit():
        # length >= 13 implies milliseconds, otherwise seconds
        if len(s) >= 13:
            return int(s)
        return int(s) * 1000

    # Handle trailing Z (UTC)
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'

    # ISO 8601 via fromisoformat (supports offsets like +00:00)
    dt = datetime.datetime.fromisoformat(s)
    return int(dt.timestamp() * 1000)

def list_log_groups(client):
    log_groups = []
    paginator = client.get_paginator('describe_log_groups')
    for page in paginator.paginate():
        for group in page.get('logGroups', []):
            log_groups.append(group['logGroupName'])
    return log_groups

def ensure_parent_dir(path: str):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

def fetch_logs(client, log_group: str, start_ms: int, end_ms: int, output_path: Optional[str] = None, append: bool = False):
    start_str = datetime.datetime.fromtimestamp(start_ms/1000).isoformat()
    end_str = datetime.datetime.fromtimestamp(end_ms/1000).isoformat()
    print(f"Fetching logs from {log_group} between {start_str} and {end_str}...")

    file_handle = None
    if output_path:
        ensure_parent_dir(output_path)
        mode = 'a' if append else 'w'
        file_handle = open(output_path, mode, encoding='utf-8')
        header = f"# LogGroup: {log_group}\n# TimeRange: {start_str} -> {end_str}\n\n"
        if not append:
            file_handle.write(header)

    try:
        paginator = client.get_paginator('filter_log_events')
        page_iterator = paginator.paginate(
            logGroupName=log_group,
            startTime=start_ms,
            endTime=end_ms,
        )
        for page in page_iterator:
            for event in page.get('events', []):
                ts = datetime.datetime.fromtimestamp(event['timestamp']/1000)
                msg = event.get('message', '')
                line = f"{ts} | {msg}"
                print(line)
                if file_handle:
                    file_handle.write(line + "\n")
    finally:
        if file_handle:
            file_handle.flush()
            file_handle.close()

def main():
    parser = argparse.ArgumentParser(description='Fetch AWS CloudWatch Logs with optional time range and auto-generated file output.')
    parser.add_argument('--region', help='AWS region (if omitted, choose from interactive menu)')
    parser.add_argument('--start', help='Start time (ISO 8601, epoch seconds, epoch ms, or relative: -<number>h|-<number>m|-<number>d).')
    parser.add_argument('--end', help='End time (ISO 8601, epoch seconds, epoch ms, or relative: -<number>h|-<number>m|-<number>d).')
    parser.add_argument('--append', action='store_true', help='Append to the output file instead of overwriting.')
    parser.add_argument('--log-group', help='Log group name to fetch directly (skips interactive selection).')
    args = parser.parse_args()

    # Resolve times (dynamic defaults to today)
    start_str = args.start
    end_str = args.end

    region = args.region or select_region_menu(default_region=REGION)
    print(f"Using AWS region: {region}")

    # if not provided, get value from user input
    if not start_str:
        print("No start time provided.")
        print("Enter start time: YYYY-MM-DDTHH:MM:SS, epoch seconds/ms, or relative (-<number>h|-<number>m|-<number>d).")
        start_str = input("Start time: ").strip()
        # if there is no T, assume date only and add T00:00:00
        if start_str and 'T' not in start_str and not start_str.isdigit() and not RELATIVE_TIME_RE.fullmatch(start_str):
            start_str += "T00:00:00"

    if not end_str:
        print("No end time provided.")
        print("Enter end time: YYYY-MM-DDTHH:MM:SS, epoch seconds/ms, or relative (-<number>h|-<number>m|-<number>d).")
        end_str = input("End time: ").strip()
        # if there is no T, assume date only and add T23:59:59
        if end_str and 'T' not in end_str and not end_str.isdigit() and not RELATIVE_TIME_RE.fullmatch(end_str):
            end_str += "T23:59:59"

    try:
        start_ms = parse_time_to_epoch_ms(start_str)
        end_ms = parse_time_to_epoch_ms(end_str)
    except Exception as e:
        print(f"Failed to parse start/end time: {e}")
        return
    if start_ms >= end_ms:
        print("Start time must be earlier than end time.")
        return

    client = boto3.client('logs', region_name=region)

    # Determine log group
    selected_log_groups = []

    if args.log_group:
        selected_log_groups = [args.log_group]
    else:
        log_groups = list_log_groups(client)
        if not log_groups:
            print("No log groups found.")
            return
        print("Available log groups:")
        for idx, name in enumerate(log_groups):
            print(f"[{idx}] {name}")
        try:
            selection = input("Select log group index(es), comma-separated (e.g. 17,1,5): ").strip()
            indices = [int(item.strip()) for item in selection.split(',') if item.strip()]
            if not indices:
                raise ValueError("No indices provided")
            selected_log_groups = [log_groups[i] for i in indices]
        except (ValueError, IndexError):
            print("Invalid selection.")
            return

    for log_group in selected_log_groups:
        output_path = _build_output_path(log_group, start_ms, end_ms)
        print(f"Saving output to: {output_path}")
        fetch_logs(
            client,
            log_group,
            start_ms,
            end_ms,
            output_path=output_path,
            append=args.append,
        )

if __name__ == "__main__":
    main()
