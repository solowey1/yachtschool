#!/usr/bin/env bash
#
# yachtschool — управление контейнерами в одном месте.
# Запуск: ./manage.sh <команда> [имя_сервиса]
#
# Все команды кроме `health` и `help` могут принимать имя сервиса как
# второй аргумент. Без него команда применяется ко всему стэку.
#
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

SERVICES=("bot" "db")

usage() {
    cat <<EOF
yachtschool — manage.sh

Использование: ./manage.sh <command> [name]

Команды:
  build [name]    Пересобрать образ(ы) с --no-cache
  up [name]       Поднять контейнер(ы) в фоне
  down [name]     Остановить и удалить контейнер(ы)
  update [name]   git pull → чистая пересборка → up
  logs [name]     Следить за логами (Ctrl-C для выхода)
  health          Статус контейнеров и healthcheck-ов
  help            Эта справка

[name] — опционально, один из: ${SERVICES[*]}
Без [name] команда применяется ко всему стэку.
EOF
}

err() { echo "manage: $*" >&2; exit 1; }

validate_service() {
    local name="${1:-}"
    [ -z "$name" ] && return 0
    for s in "${SERVICES[@]}"; do
        [ "$s" = "$name" ] && return 0
    done
    err "неизвестный сервис '$name' (допустимо: ${SERVICES[*]})"
}

cmd_build() {
    if [ -z "${1:-}" ]; then
        docker compose build --no-cache
    else
        docker compose build --no-cache "$1"
    fi
}

cmd_up() {
    if [ -z "${1:-}" ]; then
        docker compose up -d
    else
        docker compose up -d "$1"
    fi
}

cmd_down() {
    if [ -z "${1:-}" ]; then
        docker compose down
    else
        # `docker compose down` действует только на весь стэк целиком,
        # поэтому для отдельного сервиса используем stop + remove.
        docker compose rm -fs "$1"
    fi
}

cmd_update() {
    git pull
    if [ -z "${1:-}" ]; then
        docker compose down -v
        docker compose build --no-cache
        docker compose up -d
    else
        docker compose rm -fsv "$1"
        docker compose build --no-cache "$1"
        docker compose up -d "$1"
    fi
}

cmd_logs() {
    if [ -z "${1:-}" ]; then
        docker compose logs -f --tail=100
    else
        docker compose logs -f --tail=100 "$1"
    fi
}

cmd_health() {
    docker compose ps
}

cmd="${1:-help}"
arg="${2:-}"

case "$cmd" in
    build|up|down|update|logs)
        validate_service "$arg"
        "cmd_$cmd" "$arg"
        ;;
    health)
        cmd_health
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        err "неизвестная команда '$cmd' (см. './manage.sh help')"
        ;;
esac
