#!/bin/bash
# Logging utility module for openCenter AirGap deployment
# Provides structured logging with timestamps and log levels
# Requirement 11.1: Structured logging with timestamps and persistent storage

set -euo pipefail

# Log directory on bastion (persistent location)
LOG_DIR="${LOG_DIR:-/opt/opencenter/logs}"
LOG_FILE="${LOG_FILE:-deployment.log}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Log levels (numeric for comparison)
declare -A LOG_LEVELS=(
    [DEBUG]=0
    [INFO]=1
    [WARN]=2
    [ERROR]=3
)

# Current log level threshold
CURRENT_LOG_LEVEL="${LOG_LEVELS[${LOG_LEVEL}]}"

# Error trap handler for automatic error logging
# Requirement 11.5, 6.12, 8.8: Log stack traces and error context
error_trap_handler() {
    local exit_code=$?
    local line_number=$1
    local bash_lineno=$2
    local command="$3"
    
    if [[ ${exit_code} -ne 0 ]]; then
        log_error "=========================================="
        log_error "UNHANDLED ERROR DETECTED"
        log_error "=========================================="
        log_error "Exit code: ${exit_code}"
        log_error "Line number: ${line_number}"
        log_error "Command: ${command}"
        log_error "Bash lineno: ${bash_lineno}"
        
        # Log stack trace
        log_error "Stack trace:"
        local frame=0
        while caller ${frame} >/dev/null 2>&1; do
            local line_info
            line_info=$(caller ${frame})
            log_error "  ${line_info}"
            ((frame++))
        done
        
        log_error "=========================================="
    fi
}

# Set up error trap
trap 'error_trap_handler ${LINENO} ${BASH_LINENO} "$BASH_COMMAND"' ERR

# Initialize logging system
init_logging() {
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    
    # Create log directory if it doesn't exist
    mkdir -p "${LOG_DIR}"
    
    # Create timestamped subdirectory for this deployment run
    export DEPLOYMENT_LOG_DIR="${LOG_DIR}/${timestamp}"
    mkdir -p "${DEPLOYMENT_LOG_DIR}"
    
    # Set log file path
    export DEPLOYMENT_LOG_FILE="${DEPLOYMENT_LOG_DIR}/${LOG_FILE}"
    
    # Log initialization
    log_info "Logging initialized: ${DEPLOYMENT_LOG_FILE}"
    log_info "Log level: ${LOG_LEVEL}"
}

# Core logging function
_log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Check if this level should be logged
    local level_value="${LOG_LEVELS[${level}]}"
    if [[ ${level_value} -lt ${CURRENT_LOG_LEVEL} ]]; then
        return 0
    fi
    
    # Format: [TIMESTAMP] [LEVEL] message
    local log_entry="[${timestamp}] [${level}] ${message}"
    
    # Write to log file if initialized
    if [[ -n "${DEPLOYMENT_LOG_FILE:-}" ]]; then
        echo "${log_entry}" >> "${DEPLOYMENT_LOG_FILE}"
        
        # Check if log rotation is needed (every 100 log entries to avoid overhead)
        if [[ $((RANDOM % 100)) -eq 0 ]]; then
            rotate_logs 100  # Rotate if > 100MB
        fi
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

# Log command execution with output capture
# Usage: log_command "description" command args...
log_command() {
    local description="$1"
    shift
    local cmd="$*"
    
    log_info "Executing: ${description}"
    log_debug "Command: ${cmd}"
    
    local start_time
    start_time=$(date +%s)
    
    # Create temporary files for stdout and stderr
    local stdout_file="${DEPLOYMENT_LOG_DIR}/cmd_stdout_$$.tmp"
    local stderr_file="${DEPLOYMENT_LOG_DIR}/cmd_stderr_$$.tmp"
    
    # Execute command and capture output
    local exit_code=0
    if eval "${cmd}" > "${stdout_file}" 2> "${stderr_file}"; then
        exit_code=0
    else
        exit_code=$?
    fi
    
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Log stdout if not empty
    if [[ -s "${stdout_file}" ]]; then
        log_debug "Command stdout:"
        while IFS= read -r line; do
            log_debug "  ${line}"
        done < "${stdout_file}"
    fi
    
    # Log stderr if not empty
    if [[ -s "${stderr_file}" ]]; then
        if [[ ${exit_code} -ne 0 ]]; then
            log_error "Command stderr:"
            while IFS= read -r line; do
                log_error "  ${line}"
            done < "${stderr_file}"
        else
            log_warn "Command stderr (non-fatal):"
            while IFS= read -r line; do
                log_warn "  ${line}"
            done < "${stderr_file}"
        fi
    fi
    
    # Clean up temporary files
    rm -f "${stdout_file}" "${stderr_file}"
    
    if [[ ${exit_code} -eq 0 ]]; then
        log_info "Completed: ${description} (${duration}s)"
    else
        log_error "Failed: ${description} (exit code: ${exit_code}, duration: ${duration}s)"
    fi
    
    return ${exit_code}
}

# Log phase start
log_phase_start() {
    local phase="$1"
    log_info "=========================================="
    log_info "Phase: ${phase}"
    log_info "=========================================="
    
    # Record phase start time (use sanitized phase name for variable)
    local phase_var
    phase_var=$(echo "${phase}" | tr ' ' '_' | tr -cd '[:alnum:]_')
    export "PHASE_START_${phase_var}=$(date +%s)"
}

# Log phase end
log_phase_end() {
    local phase="$1"
    local status="${2:-success}"
    
    # Use sanitized phase name for variable lookup
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

# Log error with context
# Usage: log_error_context "component" "operation" "error_message" [additional_context...]
log_error_context() {
    local component="$1"
    local operation="$2"
    local error_message="$3"
    shift 3
    
    log_error "Component: ${component}"
    log_error "Operation: ${operation}"
    log_error "Error: ${error_message}"
    
    # Log additional context if provided
    if [[ $# -gt 0 ]]; then
        log_error "Context:"
        for context in "$@"; do
            log_error "  ${context}"
        done
    fi
    
    # Log stack trace if available (bash 4.1+)
    if [[ ${BASH_VERSINFO[0]} -ge 4 ]] && [[ ${BASH_VERSINFO[1]} -ge 1 ]]; then
        log_error "Stack trace:"
        local frame=0
        while true; do
            local line_info
            if ! line_info=$(caller ${frame} 2>/dev/null); then
                break
            fi
            log_error "  ${line_info}"
            ((frame++)) || true
        done
    fi
}

# Rotate logs if size exceeds threshold
# Requirement 11.7: Log rotation
rotate_logs() {
    local max_size_mb="${1:-100}"  # Default 100MB
    local max_size_bytes=$((max_size_mb * 1024 * 1024))
    
    if [[ ! -f "${DEPLOYMENT_LOG_FILE}" ]]; then
        return 0
    fi
    
    local current_size
    current_size=$(stat -f%z "${DEPLOYMENT_LOG_FILE}" 2>/dev/null || stat -c%s "${DEPLOYMENT_LOG_FILE}" 2>/dev/null || echo 0)
    
    if [[ ${current_size} -gt ${max_size_bytes} ]]; then
        local timestamp
        timestamp=$(date +%Y%m%d_%H%M%S)
        local rotated_file="${DEPLOYMENT_LOG_FILE}.${timestamp}"
        
        log_info "Rotating log file (size: $((current_size / 1024 / 1024))MB)"
        mv "${DEPLOYMENT_LOG_FILE}" "${rotated_file}"
        
        # Compress rotated log
        gzip "${rotated_file}" &
        
        log_info "Log rotated to: ${rotated_file}.gz"
    fi
}

# Generate deployment summary
# Requirement 11.6: Generate summary report with timestamps, phases, durations
generate_summary() {
    local summary_file="${DEPLOYMENT_LOG_DIR}/deployment-summary.txt"
    
    if [[ ! -f "${DEPLOYMENT_LOG_FILE}" ]]; then
        log_warn "Cannot generate summary: log file not found"
        return 1
    fi
    
    log_info "Generating deployment summary: ${summary_file}"
    
    # Call the summary generator script
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    if [[ -f "${script_dir}/generate_deployment_summary.sh" ]]; then
        "${script_dir}/generate_deployment_summary.sh" \
            --log-dir "${DEPLOYMENT_LOG_DIR}" \
            --output "deployment-summary.txt"
    else
        log_warn "Summary generator script not found"
        return 1
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
export -f log_error_context
export -f rotate_logs
export -f generate_summary
