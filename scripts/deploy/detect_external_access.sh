#!/bin/bash
# Standalone script to detect external network access from logs
# Can be run independently to analyze network monitor logs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/logging.sh"
source "${SCRIPT_DIR}/network_monitor.sh"

# Configuration
MONITOR_LOG_FILE="${1:-/var/log/opencenter/network-monitor.log}"
BASTION_IP="${BASTION_IP:-}"
FAIL_ON_EXTERNAL="${FAIL_ON_EXTERNAL:-true}"

# Usage
usage() {
    cat << EOF
Usage: $0 [LOG_FILE]

Analyze network monitor logs to detect external access attempts.

Arguments:
  LOG_FILE    Path to network monitor log file
              (default: /var/log/opencenter/network-monitor.log)

Environment Variables:
  BASTION_IP           Bastion host IP to exclude from external checks
  FAIL_ON_EXTERNAL     Exit with error if external access detected (default: true)

Exit Codes:
  0 - No external connections detected (air-gap compliant)
  1 - External connections detected (air-gap violation)
  2 - Error analyzing logs

Examples:
  # Analyze default log file
  $0

  # Analyze specific log file
  $0 /path/to/network-monitor.log

  # Analyze with bastion IP filtering
  BASTION_IP=192.168.1.5 $0

  # Analyze without failing (report only)
  FAIL_ON_EXTERNAL=false $0

EOF
}

# Check for help flag
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
fi

# Main execution
main() {
    log_info "Analyzing network monitor logs for external access..."
    log_info "Log file: ${MONITOR_LOG_FILE}"
    
    if [ ! -f "${MONITOR_LOG_FILE}" ]; then
        log_error "Log file not found: ${MONITOR_LOG_FILE}"
        log_error "Network monitoring may not have been enabled during deployment"
        exit 2
    fi
    
    if [ -n "${BASTION_IP}" ]; then
        log_info "Bastion IP: ${BASTION_IP} (will be excluded from external checks)"
    fi
    
    # Run analysis
    if analyze_logs; then
        log_info ""
        log_info "═══════════════════════════════════════════════════════════════"
        log_info "✓ AIR-GAP COMPLIANCE VERIFIED"
        log_info "═══════════════════════════════════════════════════════════════"
        log_info "No external network connections detected during deployment."
        log_info "All network traffic was confined to internal networks."
        log_info ""
        exit 0
    else
        log_error ""
        log_error "═══════════════════════════════════════════════════════════════"
        log_error "✗ AIR-GAP COMPLIANCE VIOLATION"
        log_error "═══════════════════════════════════════════════════════════════"
        log_error "External network connections were detected during deployment."
        log_error "This violates air-gap requirements."
        log_error ""
        log_error "Review the detailed log for connection information:"
        log_error "  ${MONITOR_LOG_FILE}"
        log_error ""
        log_error "Common causes:"
        log_error "  - Component attempting to download updates"
        log_error "  - DNS queries to external servers"
        log_error "  - Time synchronization (NTP) to external servers"
        log_error "  - Container registry pull from external registry"
        log_error "  - Package manager accessing external repositories"
        log_error ""
        
        if [ "${FAIL_ON_EXTERNAL}" = "true" ]; then
            log_error "Deployment FAILED due to air-gap violation"
            exit 1
        else
            log_warn "FAIL_ON_EXTERNAL=false, continuing despite violation"
            exit 0
        fi
    fi
}

# Execute main
main
