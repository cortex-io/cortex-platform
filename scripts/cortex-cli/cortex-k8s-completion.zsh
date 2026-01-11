#compdef cortex-k8s
#
# Zsh completion script for cortex-k8s CLI
#
# Installation:
#   Copy this file to a directory in your $fpath, e.g.:
#   cp cortex-k8s-completion.zsh /usr/local/share/zsh/site-functions/_cortex-k8s
#
#   Or add to ~/.zshrc:
#   fpath=(/path/to/cortex-cli $fpath)
#   autoload -Uz compinit && compinit
#

_cortex-k8s() {
    local -a commands
    commands=(
        'deploy:Deploy a service to K3s'
        'build:Build Docker image via Docker/Kaniko'
        'logs:Tail logs from service pods'
        'status:Show status of services'
        'test:Run tests for a service'
        'restart:Restart a service'
        'scale:Scale service to N replicas'
        'exec:Execute command in service pod'
        'list:List all available services'
        'help:Show help message'
        'version:Show version'
    )

    local -a global_flags
    global_flags=(
        '--namespace=-[Kubernetes namespace]:namespace:'
        '--context=-[Kubectl context]:context:_kube_contexts'
        '(--verbose -v)'{--verbose,-v}'[Verbose output]'
    )

    _arguments -C \
        $global_flags \
        '1: :->command' \
        '*:: :->args'

    case $state in
        command)
            _describe -t commands 'cortex-k8s commands' commands
            ;;
        args)
            case $words[1] in
                deploy|build|logs|test|restart|exec)
                    _arguments \
                        '1:service:_cortex_k8s_services' \
                        '*::args:_cortex_k8s_service_args'
                    ;;
                scale)
                    _arguments \
                        '1:service:_cortex_k8s_services' \
                        '2:replicas:(1 2 3 5 10)'
                    ;;
                status)
                    _arguments \
                        '1:service:_cortex_k8s_services'
                    ;;
            esac
            ;;
    esac
}

_cortex_k8s_services() {
    local -a services
    local namespace="${opt_args[--namespace]:-cortex}"

    # Get services from kubectl
    if (( $+commands[kubectl] )); then
        services=(${(f)"$(kubectl get deployments -n $namespace -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)"})
    fi

    # Fallback to common services
    if [[ ${#services[@]} -eq 0 ]]; then
        services=(
            cortex-api
            cortex-chat
            cortex-coordinator
            cortex-mcp-server
            cortex-worker
            cortex-dashboard
        )
    fi

    _describe -t services 'cortex services' services
}

_cortex_k8s_service_args() {
    case $words[1] in
        build)
            _arguments \
                '2:tag:(latest dev staging production)' \
                '--push[Push image to registry]'
            ;;
        logs)
            _arguments \
                '(-f --follow)'{-f,--follow}'[Follow log output]' \
                '--tail=-[Lines of recent log file to display]:lines:(10 50 100 500)' \
                '--since=-[Only return logs newer than a relative duration]:duration:(1m 5m 1h)' \
                '--since-time=-[Only return logs after a specific date]:timestamp:'
            ;;
    esac
}

_kube_contexts() {
    local -a contexts
    if (( $+commands[kubectl] )); then
        contexts=(${(f)"$(kubectl config get-contexts -o name 2>/dev/null)"})
        _describe -t contexts 'kubectl contexts' contexts
    fi
}

_cortex-k8s "$@"
