# CloudWatch Logs Exporter

A Python utility for fetching, exporting, and analyzing AWS CloudWatch logs locally. This tool provides an interactive interface for selecting AWS regions and log groups, with flexible time range options and automatic file output.

## Overview

**cloudwatch_logs.py** is the main script that enables you to:
- Browse available AWS regions and log groups interactively
- Fetch CloudWatch logs using flexible time formats (ISO 8601, epoch, or relative time)
- Export logs to text files with automatic naming based on log group and time range
- Select multiple log groups in a single run using comma-separated indices
- Append to existing log files or create new ones

## Prerequisites

### AWS Credentials

The script requires valid AWS credentials with permissions to access CloudWatch Logs. Configure credentials using one of these methods:

#### Method 1: AWS CLI Configuration (Recommended)
```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, default region, and output format
```
This creates `~/.aws/credentials` and `~/.aws/config` files.

#### Method 2: Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_SESSION_TOKEN=your_session_token  # Optional, for temporary credentials
python3 cloudwatch_logs.py
```

#### Method 3: Named AWS Profile
```bash
# Store credentials in ~/.aws/credentials under a profile name (e.g., [myprofile])
export AWS_PROFILE=myprofile
python3 cloudwatch_logs.py
```

#### Method 4: IAM Role (EC2, Lambda, ECS)
If running on AWS infrastructure with an attached IAM role, credentials are automatically detected.

### Python Requirements

- Python 3.7+
- boto3 >= 1.20.0

## Installation

```bash
# Clone or navigate to the project directory
cd /path/to/cloudwatch_logs

# Install dependencies
pip install boto3
```

## Usage

### Interactive Mode (Recommended)

Run the script without arguments and follow prompts:
```bash
python3 cloudwatch_logs.py
```

The script will:
1. Prompt you to select an AWS region (shows all available CloudWatch regions)
2. Ask for a start time
3. Ask for an end time
4. Display available log groups and let you select multiple groups by index
5. Fetch logs and save to `logs/` directory with auto-generated filenames

### Command-Line Arguments

```bash
python3 cloudwatch_logs.py [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--region REGION` | AWS region (e.g., `us-east-1`). Skips region selection menu if provided. |
| `--start TIME` | Start time in flexible format (see Time Formats below). |
| `--end TIME` | End time in flexible format. |
| `--log-group NAME` | Specific log group name. Skips log group selection menu. |
| `--append` | Append to existing output file instead of overwriting. |

### Time Formats

The script supports multiple time formats for `--start` and `--end`:

#### ISO 8601 (Recommended)
```bash
python3 cloudwatch_logs.py --start "2026-04-21T00:00:00" --end "2026-04-22T23:59:59"
python3 cloudwatch_logs.py --start "2026-04-21T00:00:00Z" --end "2026-04-21T12:00:00Z"
python3 cloudwatch_logs.py --start "2026-04-21T00:00:00+00:00" --end "2026-04-21T12:00:00+09:00"
```

#### Unix Epoch Seconds
```bash
python3 cloudwatch_logs.py --start "1776678000" --end "1776764400"
```

#### Unix Epoch Milliseconds
```bash
python3 cloudwatch_logs.py --start "1776678000000" --end "1776764400000"
```

#### Relative Time (Hours, Minutes, Days Ago)
```bash
# Last 24 hours
python3 cloudwatch_logs.py --start "-24h" --end "-0h"

# Last 20 minutes
python3 cloudwatch_logs.py --start "-20m" --end "-0m"

# Last 10 days
python3 cloudwatch_logs.py --start "-10d" --end "-0d"

# Specific point in time
python3 cloudwatch_logs.py --start "-5h" --end "-2h"
```

### Selecting Multiple Log Groups

When prompted to select log groups, you can enter comma-separated indices:
```
[0] /aws/lambda/my-function-1
[1] /aws/lambda/my-function-2
[2] /aws/lambda/my-function-3

Select log group index(es), comma-separated (e.g. 17,1,5): 0,2
```

This will fetch logs from both `/aws/lambda/my-function-1` and `/aws/lambda/my-function-3`.

## Examples

### Example 1: Last 24 Hours of Lambda Logs
```bash
python3 cloudwatch_logs.py --region us-east-1 --start "-24h" --end "-0h" \
  --log-group "/aws/lambda/my-function"
```

Output: `logs/aws_lambda_my-function-20260421T000000-20260422T000000.txt`

### Example 2: Fetch Logs Between Specific Dates
```bash
python3 cloudwatch_logs.py --start "2026-04-21T00:00:00" --end "2026-04-22T23:59:59"
```

### Example 3: Interactive Session with Last 7 Days
```bash
python3 cloudwatch_logs.py --start "-7d" --end "-0d"
# Then select region and log groups interactively
```

### Example 4: Append to Existing File
```bash
python3 cloudwatch_logs.py --region ap-northeast-1 --start "-1h" --end "-0h" \
  --log-group "/aws/lambda/worker" --append
```

## Output Files

Logs are automatically saved to the `logs/` directory with the following naming convention:

```
logs/{sanitized_log_group_name}-{start_time}-{end_time}.txt
```

**Example:** 
- Input log group: `/aws/lambda/my-function`
- Time range: 2026-04-21 00:00:00 to 2026-04-22 00:00:00
- Output file: `logs/aws_lambda_my-function-20260421T000000-20260422T000000.txt`

Each file includes a header with metadata:
```
# LogGroup: /aws/lambda/my-function
# TimeRange: 2026-04-21T00:00:00 -> 2026-04-22T00:00:00

2026-04-21 10:30:45.123000 | [INFO] Starting process
2026-04-21 10:30:46.456000 | [INFO] Process completed
```

## Troubleshooting

### "No log groups found"
- Verify AWS credentials are valid: `aws sts get-caller-identity`
- Confirm the selected region has log groups: `aws logs describe-log-groups --region us-east-1`
- Check IAM permissions include `logs:DescribeLogGroups` and `logs:FilterLogEvents`

### "Could not load region list"
- Verify internet connectivity
- Check that boto3 is installed: `pip install boto3 --upgrade`
- Ensure AWS credentials are configured

### Credentials Not Found
- Run `aws configure` to set up credentials
- Or set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables
- If using temporary credentials, include `AWS_SESSION_TOKEN`

### Permission Denied Errors
- Verify IAM user/role has these permissions:
  - `logs:DescribeLogGroups`
  - `logs:FilterLogEvents`
  - `logs:DescribeLogStreams`

## Security Considerations

⚠️ **Important:** Do not commit AWS credentials to version control.

- Store credentials in `~/.aws/credentials` (local machine)
- Use environment variables in CI/CD pipelines
- Use IAM roles for EC2/Lambda/ECS execution
- Rotate credentials regularly
- Never hardcode keys in scripts