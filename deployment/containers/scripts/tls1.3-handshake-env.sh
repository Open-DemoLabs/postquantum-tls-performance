#!/usr/bin/env bash
#
# Copyright 2026 José Ángel de Bustos Pérez & Josep Andreu Font
#   Author(s): José Ángel de Bustos Pérez <jadebustos@gmail.com>
#              Josep Andreu Font <jsp.andreu@gmail.com>
#
# This is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License v3 as published by the Free Software Foundation.
# This workshop is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License v3 for more details.
#
# You should have received a copy of the GNU General Public License v3 along with this software.
# If not, see https://www.gnu.org/licenses/gpl-3.0.en.htm
#
# tls1.3-handshake-env.sh
# ------------------------------------------------------------------------------
# Exports the environment variables required by tls1.3-handshake-check.sh.
#
# This file must be SOURCED, not executed, so the variables stay in your shell:
#
#     source ./tls1.3-handshake-env.sh
#     ./tls1.3-handshake-check.sh
#
# Edit the values below to match your Apache server and VirtualHost ports.
# ------------------------------------------------------------------------------

# Refuse to run as a standalone program: the exports would be lost on exit.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "ERROR: this file must be sourced, not executed:" >&2
  echo "         source ${0}" >&2
  exit 1
fi

export APACHE_SERVER=192.0.2.10   # Apache server IP address
export PORT_A1=10443              # A1: X25519MLKEM768 + ML-DSA-65
export PORT_A2=8443               # A2: NIST P-384    + ECDSA-SHA384
export PORT_B1=11443              # B1: X25519MLKEM768 + SLH-DSA-SHA2-192s
export PORT_C1=12443              # C1: ML-KEM-1024   + ML-DSA-87
export PORT_C2=9443               # C2: NIST P-521    + ECDSA-SHA512

echo "TLS 1.3 handshake check environment configured:"
for _var in APACHE_SERVER PORT_A1 PORT_A2 PORT_B1 PORT_C1 PORT_C2; do
  printf '  %-13s = %s\n' "${_var}" "${!_var}"
done
unset _var
