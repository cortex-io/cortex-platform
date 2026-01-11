#!/usr/bin/env bash
#
# Bash completion script for cortex-k8s CLI
#
# Installation:
#   Source this file in your ~/.bashrc or ~/.bash_profile:
#   source /path/to/cortex-k8s-completion.bash
#
#   Or install system-wide:
#   sudo cp cortex-k8s-completion.bash /etc/bash_completion.d/cortex-k8s
#

_cortex_k8s_completions() {
    local cur prev words cword
    _init_completion || return

    # Main commands
    local commands="deploy build logs status test restart scale exec list help version"

    # Global flags
    local global_flags="--namespace --context --verbose -v"

    # Get the command (first non-flag argument)
    local command=""
    local i
    for (( i=1; i < ${#words[@]}-1; i++ )); do
        if [[ ! "${words[i]}" =~ ^- ]]; then
            command="${words[i]}"
            break
        fi
    done

    # If no command yet, complete commands or flags
    if [[ -z "${command}" ]] || [[ "${command}" == "${cur}" ]]; then
        COMPREPLY=( $(compgen -W "${commands} ${global_flags}" -- "${cur}") )
        return 0
    fi

    # Command-specific completions
    case "${command}" in
        deploy|build|logs|test|restart|exec)
            # Complete service names
            if [[ "${prev}" == "${command}" ]]; then
                _cortex_k8s_complete_services
            elif [[ "${prev}" == "build" ]]; then
                # After service name, suggest tags or --push
                COMPREPLY=( $(compgen -W "latest dev staging production --push" -- "${cur}") )
            elif [[ "${prev}" == "logs" ]]; then
                # Kubectl logs flags
                COMPREPLY=( $(compgen -W "-f --follow --tail --since --since-time" -- "${cur}") )
            fi
            ;;
        scale)
            if [[ "${prev}" == "scale" ]]; then
                _cortex_k8s_complete_services
            elif [[ ! "${prev}" =~ ^[0-9]+$ ]]; then
                # Suggest replica counts
                COMPREPLY=( $(compgen -W "1 2 3 5 10" -- "${cur}") )
            fi
            ;;
        status)
            # Optional service name
            _cortex_k8s_complete_services
            ;;
        help|version|list|ls)
            # No additional completion
            COMPREPLY=()
            ;;
        *)
            # Default to global flags
            COMPREPLY=( $(compgen -W "${global_flags}" -- "${cur}") )
            ;;
    esac
}

_cortex_k8s_complete_services() {
    local services=""

    # Try to get services from kubectl
    if command -v kubectl &> /dev/null; then
        local namespace="cortex"

        # Extract namespace from previous args if specified
        local i
        for (( i=1; i < ${#words[@]}; i++ )); do
            if [[ "${words[i]}" =~ --namespace= ]]; then
                namespace="${words[i]#*=}"
            fi
        done

        # Get deployment names
        services=$(kubectl get deployments -n "${namespace}" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)
    fi

    # Fallback to common services if kubectl fails
    if [[ -z "${services}" ]]; then
        services="cortex-api cortex-chat cortex-coordinator cortex-mcp-server cortex-worker cortex-dashboard"
    fi

    COMPREPLY=( $(compgen -W "${services}" -- "${cur}") )
}

# Register completion
complete -F _cortex_k8s_completions cortex-k8s
