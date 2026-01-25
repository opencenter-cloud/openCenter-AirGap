#!/bin/bash
# Generate deployment summary report
# Requirement 11.6: Generate summary report with timestamps, phases, durations, errors

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source logging module
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/logging.sh"

# Default configuration
DEPLOYMENT_LOG_DIR="${DEPLOYMENT_LOG_DIR:-/opt/opencenter/logs}"
OUTPUT_FILE="${OUTPUT_FILE:-deployment-summary.txt}"

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Generate deployment summary report from logs.

Options:
  --log-dir DIR                Log directory (default: /opt/opencenter/logs)
  --output FILE                Output file name (default: deployment-summary.txt)
  --help                       Show this help message

Examples:
  # Generate summary from latest deployment
  $0

  # Generate summary from specific log directory
  $0 --log-dir /opt/opencenter/logs/20260125_143000

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --log-dir)
            DEPLOYMENT_LOG_DIR="$2"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo ""
            usage
            exit 1
            ;;
    esac
done

# Find latest deployment log directory if not specified
if [[ ! -d "${DEPLOYMENT_LOG_DIR}" ]] || [[ ! -f "${DEPLOYMENT_LOG_DIR}/deployment.log" ]]; then
    # Find latest timestamped directory
    LATEST_DIR=$(find /opt/opencenter/logs -maxdepth 1 -type d -name "20*" | sort -r | head -1)
    
    if [[ -n "${LATEST_DIR}" ]] && [[ -f "${LATEST_DIR}/deployment.log" ]]; then
        DEPLOYMENT_LOG_DIR="${LATEST_DIR}"
        echo "Using latest deployment log: ${DEPLOYMENT_LOG_DIR}"
    else
        echo "Error: No deployment logs found"
        exit 1
    fi
fi

LOG_FILE="${DEPLOYMENT_LOG_DIR}/deployment.log"
SUMMARY_FILE="${DEPLOYMENT_LOG_DIR}/${OUTPUT_FILE}"

if [[ ! -f "${LOG_FILE}" ]]; then
    echo "Error: Log file not found: ${LOG_FILE}"
    exit 1
fi

echo "Generating deployment summary..."
echo "  Log file: ${LOG_FILE}"
echo "  Output: ${SUMMARY_FILE}"

# Generate summary
{
    echo "=========================================="
    echo "openCenter AirGap Deployment Summary"
    echo "=========================================="
    echo ""
    
    # Deployment start and end times
    START_TIME=$(grep -m 1 "Logging initialized" "${LOG_FILE}" | awk '{print $1, $2}' || echo "Unknown")
    END_TIME=$(tail -20 "${LOG_FILE}" | grep -E "\[INFO\]" | tail -1 | awk '{print $1, $2}' || echo "Unknown")
    
    echo "Start Time: ${START_TIME}"
    echo "End Time: ${END_TIME}"
    echo ""
    
    # Calculate duration if both times are available
    if [[ "${START_TIME}" != "Unknown" ]] && [[ "${END_TIME}" != "Unknown" ]]; then
        START_EPOCH=$(date -d "${START_TIME}" +%s 2>/dev/null || echo "0")
        END_EPOCH=$(date -d "${END_TIME}" +%s 2>/dev/null || echo "0")
        
        if [[ ${START_EPOCH} -gt 0 ]] && [[ ${END_EPOCH} -gt 0 ]]; then
            DURATION=$((END_EPOCH - START_EPOCH))
            HOURS=$((DURATION / 3600))
            MINUTES=$(( (DURATION % 3600) / 60 ))
            SECONDS=$((DURATION % 60))
            
            echo "Total Duration: ${HOURS}h ${MINUTES}m ${SECONDS}s"
            echo ""
        fi
    fi
    
    # Deployment configuration
    echo "Configuration:"
    grep -E "Deployment mode:|Bastion IP:|Cluster name:|SSH user:" "${LOG_FILE}" | sed 's/.*\[INFO\] /  /' || echo "  Configuration not found"
    echo ""
    
    # Phases completed
    echo "Phases Completed:"
    grep "Phase:" "${LOG_FILE}" | sed 's/.*\[INFO\] Phase: /  - /' || echo "  No phases found"
    echo ""
    
    # Phase durations
    echo "Phase Durations:"
    grep "Phase completed:" "${LOG_FILE}" | sed 's/.*\[INFO\] /  /' || echo "  No phase durations found"
    echo ""
    
    # Steps completed
    echo "Steps Completed:"
    STEP_COUNT=$(grep -c "Executing:" "${LOG_FILE}" || echo "0")
    echo "  Total steps: ${STEP_COUNT}"
    echo ""
    
    # Errors and warnings
    ERROR_COUNT=$(grep -c "\[ERROR\]" "${LOG_FILE}" || echo "0")
    WARN_COUNT=$(grep -c "\[WARN\]" "${LOG_FILE}" || echo "0")
    
    echo "Status:"
    echo "  Errors: ${ERROR_COUNT}"
    echo "  Warnings: ${WARN_COUNT}"
    echo ""
    
    if [[ ${ERROR_COUNT} -gt 0 ]]; then
        echo "Errors Encountered:"
        grep "\[ERROR\]" "${LOG_FILE}" | tail -20 | sed 's/.*\[ERROR\] /  /' || echo "  Unable to extract errors"
        echo ""
    fi
    
    if [[ ${WARN_COUNT} -gt 0 ]]; then
        echo "Warnings:"
        grep "\[WARN\]" "${LOG_FILE}" | tail -10 | sed 's/.*\[WARN\] /  /' || echo "  Unable to extract warnings"
        echo ""
    fi
    
    # Deployment outcome
    if [[ ${ERROR_COUNT} -eq 0 ]]; then
        echo "Deployment Status: SUCCESS ✓"
    else
        echo "Deployment Status: FAILED ✗"
    fi
    
    echo ""
    echo "=========================================="
    echo "Full logs available at: ${LOG_FILE}"
    echo "=========================================="
    
} > "${SUMMARY_FILE}"

echo "✓ Summary generated: ${SUMMARY_FILE}"
echo ""

# Display summary to console
cat "${SUMMARY_FILE}"

exit 0
