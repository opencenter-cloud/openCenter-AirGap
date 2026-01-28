#!/bin/bash
# Shared logging library for openCenter build scripts
# Provides structured logging with timestamps and log levels
#
# Usage:
#   source scripts/lib/logging.sh
#   init_logging
#   log_info "Starting build process"
#   log_error "Build failed"

set -euo pipefail

# Log directory (defaults to build/logs)
LOG_DIR="${LOG_DIR:-build/logs}"
LOG_FILE="${LOG_FILE:-build.log}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Build log file path (set by init_logging)
BUILD_LOG_FILE=""

# Get numeric log level
get_log_level_value() {
    case "$1" in
        DEBUG) echo 0 ;;
        INFO)  echo 1 ;;
        WARN)  echo 2 ;;
        ERROR) echo 3 ;;
        *)     echo 1 ;;  # Default to INFO
    esac
}

# Current log level threshold
CURRENT_LOG_LEVEL=$(get_log_level_value "${LOG_LEVEL}")

# Initialize logging system
# Creates log directory and timestamped log file
init_logging() {
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)

    # Create log directory
    mkdir -p "${LOG_DIR}"

    # Set log file path with timestamp
    export BUILD_LOG_FILE="${LOG_DIR}/${timestamp}_${LOG_FILE}"

    # Log initialization
    log_info "Logging initialized: ${BUILD_LOG_FILE}"
    log_info "Log level: ${LOG_LEVEL}"
}

# Core logging function
# Args:
#   $1: Log level (DEBUG, INFO, WARN, ERROR)
#   $@: Log message
_log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Check if this level should be logged
    local level_value
    level_value=$(get_log_level_value "${level}")
    if [[ ${level_value} -lt ${CURRENT_LOG_LEVEL} ]]; then
        return 0
    fi

    # Format: [TIMESTAMP] [LEVEL] message
    local log_entry="[${timestamp}] [${level}] ${message}"

    # Write to log file if initialized
    if [[ -n "${BUILD_LOG_FILE}" ]]; then
        echo "${log_entry}" >> "${BUILD_LOG_FILE}"
    fi

    # Also write to stderr for ERROR and WARN
    if [[ "${level}" == "ERROR" ]] || [[ "${level}" == "WARN" ]]; then
        echo "${log_entry}" >&2
    else
        echo "${log_entry}"
    fi
}

# Convenience functions for each log level
log_debug() {
    _log "DEBUG" "$@"
}

log_info() {
    _log "INFO" "$@"
}

log_warn() {
    _log "WARN" "$@"
}

log_error() {
    _log "ERROR" "$@"
}

# Log command execution with timing
# Usage: log_command "description" command args...
log_command() {
    local description="$1"
    shift
    local cmd="$*"

    log_info "Executing: ${description}"
    log_debug "Command: ${cmd}"

    local start_time
    start_time=$(date +%s)

    local exit_code=0
    if eval "${cmd}"; then
        exit_code=0
    else
        exit_code=$?
    fi

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    if [[ ${exit_code} -eq 0 ]]; then
        log_info "Completed: ${description} (${duration}s)"
    else
        log_error "Failed: ${description} (exit code: ${exit_code}, duration: ${duration}s)"
    fi

    return ${exit_code}
}

# Log phase start with separator
log_phase_start() {
    local phase="$1"
    log_info "=========================================="
    log_info "Phase: ${phase}"
    log_info "=========================================="

    # Record phase start time
    local phase_var
    phase_var=$(echo "${phase}" | tr ' ' '_' | tr -cd '[:alnum:]_')
    export "PHASE_START_${phase_var}=$(date +%s)"
}

# Log phase end with duration
log_phase_end() {
    local phase="$1"
    local status="${2:-success}"

    # Calculate duration if start time exists
    local phase_var
    phase_var=$(echo "${phase}" | tr ' ' '_' | tr -cd '[:alnum:]_')
    local start_var="PHASE_START_${phase_var}"
    local start_time="${!start_var:-}"

    if [[ -n "${start_time}" ]]; then
        local end_time
        end_time=$(date +%s)
        local duration=$((end_time - start_time))

        if [[ "${status}" == "success" ]]; then
            log_info "Phase completed: ${phase} (${duration}s)"
        else
            log_error "Phase failed: ${phase} (${duration}s)"
        fi
    else
        if [[ "${status}" == "success" ]]; then
            log_info "Phase completed: ${phase}"
        else
            log_error "Phase failed: ${phase}"
        fi
    fi

    log_info "=========================================="
}

# Rotate logs if size exceeds threshold
# Args:
#   $1: Max size in MB (default: 10)
rotate_logs() {
    local max_size_mb="${1:-10}"
    local max_size_bytes=$((max_size_mb * 1024 * 1024))

    if [[ ! -f "${BUILD_LOG_FILE}" ]]; then
        return 0
    fi

    local current_size
    current_size=$(stat -f%z "${BUILD_LOG_FILE}" 2>/dev/null || stat -c%s "${BUILD_LOG_FILE}" 2>/dev/null || echo 0)

    if [[ ${current_size} -gt ${max_size_bytes} ]]; then
        local timestamp
        timestamp=$(date +%Y%m%d_%H%M%S)
        local rotated_file="${BUILD_LOG_FILE}.${timestamp}"

        log_info "Rotating log file (size: $((current_size / 1024 / 1024))MB)"
        mv "${BUILD_LOG_FILE}" "${rotated_file}"

        # Compress rotated log in background
        gzip "${rotated_file}" &

        log_info "Log rotated to: ${rotated_file}.gz"
    fi
}

# Export functions for use in other scripts
export -f init_logging
export -f log_debug
export -f log_info
export -f log_warn
export -f log_error
export -f log_command
export -f log_phase_start
export -f log_phase_end
export -f rotate_logs
