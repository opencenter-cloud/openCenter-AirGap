#!/bin/bash
# Network connection monitor for air-gap compliance validation
# Logs all outbound network connections to detect external access attempts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/logging.sh"

# Configuration
MONITOR_LOG_DIR="${MONITOR_LOG_DIR:-/var/log/opencenter}"
MONITOR_LOG_FILE="${MONITOR_LOG_DIR}/network-monitor.log"
MONITOR_PID_FILE="${MONITOR_LOG_DIR}/network-monitor.pid"
BASTION_IP="${BASTION_IP:-}"

# Internal network ranges (RFC 1918)
INTERNAL_RANGES=(
    "10.0.0.0/8"
    "172.16.0.0/12"
    "192.168.0.0/16"
    "127.0.0.0/8"
)

# Function to check if tcpdump is available
check_tcpdump() {
    if ! command -v tcpdump &> /dev/null; then
        log_error "tcpdump not found. Install with: apt-get install tcpdump"
        return 1
    fi
    return 0
}

# Function to start network monitoring
start_monitor() {
    log_info "Starting network connection monitor..."
    
    # Check prerequisites
    if ! check_tcpdump; then
        log_error "Cannot start network monitor: tcpdump not available"
        return 1
    fi
    
    # Check if already running
    if [ -f "${MONITOR_PID_FILE}" ]; then
        local pid
        pid=$(cat "${MONITOR_PID_FILE}")
        if ps -p "${pid}" > /dev/null 2>&1; then
            log_warn "Network monitor already running (PID: ${pid})"
            return 0
        else
            log_warn "Stale PID file found, removing..."
            rm -f "${MONITOR_PID_FILE}"
        fi
    fi
    
    # Create log directory
    mkdir -p "${MONITOR_LOG_DIR}"
    
    # Start tcpdump in background
    # Capture outbound TCP connections (SYN packets) on all interfaces
    # Filter: tcp[tcpflags] & tcp-syn != 0 and tcp[tcpflags] & tcp-ack == 0
    log_info "Starting tcpdump to capture outbound connections..."
    tcpdump -i any -n -l \
        'tcp[tcpflags] & tcp-syn != 0 and tcp[tcpflags] & tcp-ack == 0' \
        >> "${MONITOR_LOG_FILE}" 2>&1 &
    
    local monitor_pid=$!
    echo "${monitor_pid}" > "${MONITOR_PID_FILE}"
    
    log_info "Network monitor started (PID: ${monitor_pid})"
    log_info "Monitoring log: ${MONITOR_LOG_FILE}"
    
    return 0
}

# Function to stop network monitoring
stop_monitor() {
    log_info "Stopping network connection monitor..."
    
    if [ ! -f "${MONITOR_PID_FILE}" ]; then
        log_warn "Network monitor PID file not found"
        return 0
    fi
    
    local pid
    pid=$(cat "${MONITOR_PID_FILE}")
    
    if ps -p "${pid}" > /dev/null 2>&1; then
        log_info "Stopping monitor process (PID: ${pid})..."
        kill "${pid}" || true
        sleep 2
        
        # Force kill if still running
        if ps -p "${pid}" > /dev/null 2>&1; then
            log_warn "Process still running, force killing..."
            kill -9 "${pid}" || true
        fi
        
        log_info "Network monitor stopped"
    else
        log_warn "Monitor process not running (PID: ${pid})"
    fi
    
    rm -f "${MONITOR_PID_FILE}"
    return 0
}

# Function to check if IP is internal
is_internal_ip() {
    local ip="$1"
    
    # Check if localhost
    if [[ "${ip}" == "127."* ]] || [[ "${ip}" == "localhost" ]]; then
        return 0
    fi
    
    # Check if matches bastion IP
    if [ -n "${BASTION_IP}" ] && [ "${ip}" == "${BASTION_IP}" ]; then
        return 0
    fi
    
    # Check against internal ranges using ipcalc if available
    if command -v ipcalc &> /dev/null; then
        for range in "${INTERNAL_RANGES[@]}"; do
            if ipcalc -c "${ip}" "${range}" &> /dev/null; then
                return 0
            fi
        done
    else
        # Fallback: simple prefix matching
        for range in "${INTERNAL_RANGES[@]}"; do
            local prefix="${range%%/*}"
            local prefix_octets="${prefix%%.*}"
            local ip_first_octet="${ip%%.*}"
            
            case "${prefix_octets}" in
                10)
                    if [[ "${ip}" == "10."* ]]; then
                        return 0
                    fi
                    ;;
                172)
                    if [[ "${ip}" =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\. ]]; then
                        return 0
                    fi
                    ;;
                192)
                    if [[ "${ip}" == "192.168."* ]]; then
                        return 0
                    fi
                    ;;
            esac
        done
    fi
    
    return 1
}

# Function to analyze network monitor logs
analyze_logs() {
    log_info "Analyzing network connection logs..."
    
    if [ ! -f "${MONITOR_LOG_FILE}" ]; then
        log_error "Monitor log file not found: ${MONITOR_LOG_FILE}"
        return 1
    fi
    
    local external_connections=0
    local total_connections=0
    local external_ips=()
    
    # Parse tcpdump output
    # Format: timestamp IP src.port > dst.port: Flags [S], ...
    while IFS= read -r line; do
        # Skip empty lines and tcpdump startup messages
        if [[ -z "${line}" ]] || [[ "${line}" == "tcpdump:"* ]] || [[ "${line}" == "listening on"* ]]; then
            continue
        fi
        
        # Extract destination IP from tcpdump output
        # Example: 12:34:56.789012 IP 192.168.1.10.12345 > 8.8.8.8.53: Flags [S]
        if [[ "${line}" =~ [[:space:]]IP[[:space:]]([0-9.]+)\.[0-9]+[[:space:]]\>[[:space:]]([0-9.]+)\.[0-9]+ ]]; then
            local src_ip="${BASH_REMATCH[1]}"
            local dst_ip="${BASH_REMATCH[2]}"
            
            ((total_connections++))
            
            # Check if destination is external
            if ! is_internal_ip "${dst_ip}"; then
                ((external_connections++))
                
                # Add to external IPs list if not already present
                if [[ ! " ${external_ips[*]} " =~ " ${dst_ip} " ]]; then
                    external_ips+=("${dst_ip}")
                fi
                
                log_warn "External connection detected: ${src_ip} -> ${dst_ip}"
            fi
        fi
    done < "${MONITOR_LOG_FILE}"
    
    log_info "Network analysis complete:"
    log_info "  Total connections: ${total_connections}"
    log_info "  External connections: ${external_connections}"
    
    if [ ${external_connections} -gt 0 ]; then
        log_error "OFFLINE COMPLIANCE VIOLATION: ${external_connections} external connection(s) detected"
        log_error "External IPs contacted:"
        for ip in "${external_ips[@]}"; do
            log_error "  - ${ip}"
        done
        return 1
    else
        log_info "OFFLINE COMPLIANCE: No external connections detected"
        return 0
    fi
}

# Function to get monitor status
status_monitor() {
    if [ ! -f "${MONITOR_PID_FILE}" ]; then
        echo "Network monitor is not running"
        return 1
    fi
    
    local pid
    pid=$(cat "${MONITOR_PID_FILE}")
    
    if ps -p "${pid}" > /dev/null 2>&1; then
        echo "Network monitor is running (PID: ${pid})"
        echo "Log file: ${MONITOR_LOG_FILE}"
        return 0
    else
        echo "Network monitor is not running (stale PID file)"
        return 1
    fi
}

# Main command dispatcher
main() {
    local command="${1:-}"
    
    case "${command}" in
        start)
            start_monitor
            ;;
        stop)
            stop_monitor
            ;;
        analyze)
            analyze_logs
            ;;
        status)
            status_monitor
            ;;
        *)
            echo "Usage: $0 {start|stop|analyze|status}"
            echo ""
            echo "Commands:"
            echo "  start   - Start network connection monitoring"
            echo "  stop    - Stop network connection monitoring"
            echo "  analyze - Analyze captured connections for external access"
            echo "  status  - Check monitor status"
            echo ""
            echo "Environment variables:"
            echo "  MONITOR_LOG_DIR - Directory for monitor logs (default: /var/log/opencenter)"
            echo "  BASTION_IP      - Bastion host IP to exclude from external checks"
            exit 1
            ;;
    esac
}

# Execute main if script is run directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
