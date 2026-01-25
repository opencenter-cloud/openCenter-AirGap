#!/bin/bash
# Log management utility
# Requirement 11.7, 11.8: Log rotation and preservation

set -euo pipefail

LOG_DIR="${LOG_DIR:-/opt/opencenter/logs}"
MAX_AGE_DAYS="${MAX_AGE_DAYS:-30}"
MAX_SIZE_GB="${MAX_SIZE_GB:-10}"

# Usage information
usage() {
    cat << EOF
Usage: $0 [COMMAND] [OPTIONS]

Manage deployment logs.

Commands:
  list                         List all deployment log directories
  clean                        Clean old logs (older than ${MAX_AGE_DAYS} days)
  compress                     Compress uncompressed logs
  size                         Show total log size
  latest                       Show path to latest log directory

Options:
  --max-age DAYS               Maximum age in days (default: 30)
  --max-size GB                Maximum total size in GB (default: 10)
  --log-dir DIR                Log directory (default: /opt/opencenter/logs)
  --help                       Show this help message

Examples:
  # List all deployment logs
  $0 list

  # Clean logs older than 7 days
  $0 clean --max-age 7

  # Compress all uncompressed logs
  $0 compress

  # Show total log size
  $0 size

EOF
}

# Parse command
COMMAND="${1:-list}"
shift || true

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        --max-age)
            MAX_AGE_DAYS="$2"
            shift 2
            ;;
        --max-size)
            MAX_SIZE_GB="$2"
            shift 2
            ;;
        --log-dir)
            LOG_DIR="$2"
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

# Verify log directory exists
if [[ ! -d "${LOG_DIR}" ]]; then
    echo "Log directory not found: ${LOG_DIR}"
    exit 1
fi

# List deployment logs
list_logs() {
    echo "Deployment logs in ${LOG_DIR}:"
    echo ""
    
    find "${LOG_DIR}" -maxdepth 1 -type d -name "20*" | sort -r | while read -r dir; do
        local dir_name
        dir_name=$(basename "${dir}")
        local log_file="${dir}/deployment.log"
        local summary_file="${dir}/deployment-summary.txt"
        
        local size="0"
        if [[ -f "${log_file}" ]]; then
            size=$(du -sh "${dir}" | awk '{print $1}')
        fi
        
        local status="incomplete"
        if [[ -f "${summary_file}" ]]; then
            if grep -q "SUCCESS" "${summary_file}"; then
                status="success"
            elif grep -q "FAILED" "${summary_file}"; then
                status="failed"
            fi
        fi
        
        printf "  %-20s  %-10s  %s\n" "${dir_name}" "${size}" "${status}"
    done
}

# Clean old logs
clean_logs() {
    echo "Cleaning logs older than ${MAX_AGE_DAYS} days..."
    
    local count=0
    find "${LOG_DIR}" -maxdepth 1 -type d -name "20*" -mtime +${MAX_AGE_DAYS} | while read -r dir; do
        echo "  Removing: $(basename "${dir}")"
        rm -rf "${dir}"
        ((count++))
    done
    
    echo "✓ Cleaned ${count} old log directories"
}

# Compress uncompressed logs
compress_logs() {
    echo "Compressing uncompressed logs..."
    
    local count=0
    find "${LOG_DIR}" -type f -name "*.log" ! -name "*.gz" | while read -r log_file; do
        echo "  Compressing: ${log_file}"
        gzip "${log_file}"
        ((count++))
    done
    
    echo "✓ Compressed ${count} log files"
}

# Show total log size
show_size() {
    echo "Log directory: ${LOG_DIR}"
    echo ""
    
    local total_size
    total_size=$(du -sh "${LOG_DIR}" | awk '{print $1}')
    echo "Total size: ${total_size}"
    echo ""
    
    # Show size by deployment
    echo "Size by deployment:"
    find "${LOG_DIR}" -maxdepth 1 -type d -name "20*" | sort -r | head -10 | while read -r dir; do
        local dir_name
        dir_name=$(basename "${dir}")
        local size
        size=$(du -sh "${dir}" | awk '{print $1}')
        printf "  %-20s  %s\n" "${dir_name}" "${size}"
    done
}

# Show latest log directory
show_latest() {
    local latest
    latest=$(find "${LOG_DIR}" -maxdepth 1 -type d -name "20*" | sort -r | head -1)
    
    if [[ -n "${latest}" ]]; then
        echo "${latest}"
    else
        echo "No deployment logs found"
        exit 1
    fi
}

# Execute command
case "${COMMAND}" in
    list)
        list_logs
        ;;
    clean)
        clean_logs
        ;;
    compress)
        compress_logs
        ;;
    size)
        show_size
        ;;
    latest)
        show_latest
        ;;
    *)
        echo "Unknown command: ${COMMAND}"
        echo ""
        usage
        exit 1
        ;;
esac

exit 0
