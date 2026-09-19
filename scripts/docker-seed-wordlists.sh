#!/usr/bin/env bash
# 把 kali-kit 写死的词表路径补齐。优先用发行版已装文件，缺的再拉公开小表。
set -euo pipefail

fetch() {
  local dest="$1"
  shift
  if [[ -s "$dest" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  local url
  for url in "$@"; do
    if curl -fsSL --retry 3 --retry-delay 2 -o "${dest}.tmp" "$url"; then
      mv "${dest}.tmp" "$dest"
      echo "[wordlists] fetched $dest"
      return 0
    fi
    rm -f "${dest}.tmp"
  done
  return 1
}

link_or_fetch() {
  local dest="$1"
  shift
  if [[ -s "$dest" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  local src
  for src in "$@"; do
    if [[ "$src" == http://* || "$src" == https://* ]]; then
      if fetch "$dest" "$src"; then
        return 0
      fi
      continue
    fi
    if [[ -s "$src" ]]; then
      ln -sfn "$src" "$dest"
      echo "[wordlists] $dest -> $src"
      return 0
    fi
  done
  echo "[wordlists] missing $dest" >&2
  return 0
}

mkdir -p \
  /usr/share/wordlists/dirb \
  /usr/share/wordlists/dirbuster \
  /usr/share/wordlists/metasploit \
  /usr/share/metasploit-framework/data/wordlists \
  /usr/share/john

link_or_fetch /usr/share/wordlists/dirb/common.txt \
  /usr/share/dirb/wordlists/common.txt \
  /usr/share/seclists/Discovery/Web-Content/common.txt \
  https://raw.githubusercontent.com/v0re/dirb/master/wordlists/common.txt \
  https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/common.txt

link_or_fetch /usr/share/wordlists/dirbuster/directory-list-2.3-small.txt \
  /usr/share/seclists/Discovery/Web-Content/DirBuster-2007/directory-list-2.3-small.txt \
  /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt \
  https://raw.githubusercontent.com/daviddias/node-dirbuster/master/lists/directory-list-2.3-small.txt \
  https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/DirBuster-2007/directory-list-2.3-small.txt

link_or_fetch /usr/share/wordlists/dnsmap.txt \
  /usr/share/dnsmap/wordlist_TLAs.txt \
  /usr/share/seclists/Discovery/DNS/dnsmap.txt \
  /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt \
  https://raw.githubusercontent.com/makefu/dnsmap/master/wordlist_TLAs.txt \
  https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/DNS/subdomains-top1million-5000.txt

link_or_fetch /usr/share/metasploit-framework/data/wordlists/unix_users.txt \
  /usr/share/seclists/Usernames/top-usernames-shortlist.txt \
  https://raw.githubusercontent.com/rapid7/metasploit-framework/master/data/wordlists/unix_users.txt

link_or_fetch /usr/share/metasploit-framework/data/wordlists/unix_passwords.txt \
  /usr/share/john/password.lst \
  /usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt \
  https://raw.githubusercontent.com/rapid7/metasploit-framework/master/data/wordlists/unix_passwords.txt

link_or_fetch /usr/share/wordlists/metasploit/http_default_userpass.txt \
  /usr/share/metasploit-framework/data/wordlists/http_default_userpass.txt \
  https://raw.githubusercontent.com/rapid7/metasploit-framework/master/data/wordlists/http_default_userpass.txt

link_or_fetch /usr/share/john/password.lst \
  /usr/share/john/password.lst \
  /usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt \
  https://raw.githubusercontent.com/openwall/john/bleeding-jumbo/run/password.lst

link_or_fetch /usr/share/wordlists/metasploit/password.lst \
  /usr/share/metasploit-framework/data/wordlists/password.lst \
  /usr/share/john/password.lst \
  https://raw.githubusercontent.com/rapid7/metasploit-framework/master/data/wordlists/password.lst

# 最小兜底，避免 kali-kit 路径直接 不存在
if [[ ! -s /usr/share/wordlists/dirb/common.txt ]]; then
  printf '%s\n' admin login api backup test dashboard .git .env robots.txt > /usr/share/wordlists/dirb/common.txt
fi
if [[ ! -s /usr/share/wordlists/metasploit/http_default_userpass.txt ]]; then
  printf '%s\n' 'admin admin' 'admin password' 'root root' 'user user' > /usr/share/wordlists/metasploit/http_default_userpass.txt
fi
