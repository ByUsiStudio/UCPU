#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[0;37m'
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
UNDERLINE='\033[4m'

info()    { echo -e "${BLUE}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✔${NC} $1"; }
error()   { echo -e "${RED}✘${NC} $1"; }
warning() { echo -e "${YELLOW}⚠${NC} $1"; }
step()    { echo -e "\n${CYAN}━━━ ${BOLD}[$1]${NC} ${CYAN}$2${NC}"; }
line()    { echo -e "${DIM}═══════════════════════════════════════════════════════════${NC}"; }
thin_line() { echo -e "${DIM}───────────────────────────────────────────────────────────────${NC}"; }

start_time=$(date +%s)

clear
echo -e "${MAGENTA}${BOLD}欢迎使用 UCPU 程序${NC}"
echo -e "${DIM}启动时间: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
line
echo -e "${WHITE}${BOLD}系统环境${NC}"
echo -e "  用户    : ${GREEN}$(whoami)${NC} @ ${YELLOW}$(hostname)${NC}"
echo -e "  工作目录: ${BLUE}$(pwd)${NC}"
echo -e "  系统    : ${CYAN}$(uname -s) $(uname -r) $(uname -m)${NC}"
line

total_steps=7
current_step=0

step_func() {
    ((current_step++))
    step "${current_step}/${total_steps}" "$1"
    thin_line
    step_start=$(date +%s)
}

finish_step() {
    local exit_code=$?
    local step_end=$(date +%s)
    local duration=$((step_end - step_start))
    if [ $exit_code -eq 0 ]; then
        success "$1 完成 (耗时 ${duration}秒)"
    else
        error "$1 失败 (退出码: $exit_code)"
        exit $exit_code
    fi
    thin_line
}

step_func "更新软件包列表"
apt update -y
finish_step "更新软件包列表"

step_func "安装依赖工具 (wget, unzip, zip)"
apt install -y wget unzip zip
finish_step "安装依赖工具"

step_func "创建工作目录"
cd ~/ || { error "无法切换到用户目录"; exit 1; }
mkdir -p "ByUsi Studio/UCPU" || { error "无法创建目录"; exit 1; }
cd "ByUsi Studio/UCPU" || { error "无法进入目录"; exit 1; }
success "工作目录: $(pwd)"
thin_line
true
finish_step "创建工作目录"

step_func "下载 UCPU 程序"
wget "https://www.cdifit.cn/f/5JKI2/ucpu.zip" -O /data/data/com.termux/files/usr/tmp/ucpu.zip
finish_step "下载 UCPU 程序"

step_func "解压 UCPU"
if [ -n "$(ls -A .)" ]; then
    warning "当前目录非空，存在以下文件："
    ls -la
    echo -n "是否清空该目录并继续解压？ (y/N): "
    read answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        success "用户选择清空目录"
        rm -rvf ./*
        if [ $? -ne 0 ]; then
            error "清空目录失败"
            exit 1
        fi
        success "目录已清空"
    else
        error "用户取消安装"
        exit 1
    fi
else
    info "目录为空，直接解压"
fi
unzip -o /data/data/com.termux/files/usr/tmp/ucpu.zip
finish_step "解压 UCPU"

step_func "清理临时文件"
rm -f /data/data/com.termux/files/usr/tmp/ucpu.zip
if [ $? -eq 0 ]; then
    success "临时文件已清理"
else
    warning "清理临时文件可能有残留"
fi
thin_line
true
finish_step "清理临时文件"

step_func "配置环境变量"
UCPU_INSTALL="$HOME/../usr/etc/profile.d/ucpu_init.sh"
mkdir -p "$(dirname "$UCPU_INSTALL")"
echo "export PATH=\"\$PATH:$(pwd)\"" > "$UCPU_INSTALL"
chmod +x "$UCPU_INSTALL"
success "环境变量已添加到 $UCPU_INSTALL"
thin_line
true
finish_step "配置环境变量"

end_time=$(date +%s)
total_duration=$((end_time - start_time))

line
echo -e "${GREEN}${BOLD}✓ 所有步骤执行完毕！${NC}"
echo -e "${DIM}总耗时: ${total_duration}秒${NC}"
echo -e "${DIM}完成时间: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
line
echo -e "${YELLOW}提示: 请运行以下命令使环境变量生效:${NC}"
echo -e "  ${BOLD}source $UCPU_INSTALL${NC}"
echo -e "或重新打开终端。"