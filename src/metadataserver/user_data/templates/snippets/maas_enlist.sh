#!/bin/bash -e
#
#    maas-enlist: MAAS Enlistment Tool
#
#    Copyright (C) 2014-2018 Canonical Ltd.
#
#    Authors: Andres Rodriguez <andres.rodriguez@canonical.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3 of the License.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

get_mac_addresses() {
	local macs
	local pxe_mac
	local mac_addresses
	macs=`ip addr | egrep 'link/ether' | cut -d' ' -f6`
	# Obtain the BOOTIF MAC address from the kernel command line.
	# Note that BOOTIF stores the MAC in the format of
	# '01-AA-BB-CC-DD-EE-FF", or "01-AA:BB:CC:DD:EE:FF",
        # and we remove the '01-'.
	pxe_mac=`cat /proc/cmdline | egrep 'BOOTIF=' | sed -e 's/.*[[:space:]]BOOTIF=\([-:0-9A-Fa-f]\+\).*/\1/g' -e 's,^01-,,g' -e 's,-,:,g'`
	# Initialize the mac_address variable with "$pxe_mac",
	# otherwise "$pxe_mac" will be empty.
	mac_addresses="$pxe_mac"

	for mac in $macs;
	do
		# We only add more mac's if "$mac" is different
		# from "$pxe_mac"
		if [ "$mac" = "02:00:00:00:00:02" ]; then
			# This is an OpenBMC MAC and as such, we ignore it.
			# This MAC will be the same for all Wedge systems (e.g Wedge 40/100).
			continue
		elif [ "$mac" != "$pxe_mac" ]; then
			if [ -z "$mac_addresses" ]; then
				mac_addresses="$mac"
			else
				mac_addresses="$mac_addresses,$mac"
			fi
		fi
	done
	echo "$mac_addresses"
}

get_mac_address_by_interface() {
	iface="$1"
	mac=`ip addr sh "$iface" | egrep -m1 'link/ether' | cut -d' ' -f6`
	echo "$mac"
}

get_mac_address_curl_parms() {
	local args="" input_string="$1"
	OIFS=$IFS; IFS=","; set -- $input_string; IFS=$OIFS
	for i in "$@";
	do
		args="${args} --data-urlencode mac_addresses=${i}"
		#mac_address="$mac_address""&mac_addresses=""${i}";
	done
	echo "${args# }"
}

get_host_architecture() {
	if grep "flags" /proc/cpuinfo | grep -qs "\ lm\ "; then
		# if /proc/cpuinfo Flags has 'lm', it is x86_64
		arch="amd64"
	else
		arch=`archdetect | cut -d'/' -f1`
	fi
	echo "$arch"
}

get_host_subarchitecture() {
	local arch=$1
	case $arch in
	    i386|amd64|arm64|ppc64el)
		# Skip the call to archdetect as that's what
		# get_host_architecture does
		echo generic
		;;
	    *)
		archdetect | cut -d'/' -f2
		;;
	esac
}

get_server_name() {
	local servername="$1";
	_RET=${servername#*://};
	_RET=${_RET%%/*};
	echo "$_RET";
}

enlist_node() {
	serverurl="${1}"
	mac="${2}"
	arch="${3}"
	subarch="${4}"
	hostname="${5}"
	power_type="${6}"
	power_params="${7}"
	commission="${8}"

	local macparms=""
	macparms=$(get_mac_address_curl_parms "$mac")

	curl \
	    --fail \
	    --header "Accept: application/json" \
	    --data-urlencode "hostname=${hostname}" \
	    --data-urlencode "architecture=${arch}" \
	    --data-urlencode "subarchitecture=${subarch}" \
	    --data-urlencode "power_type=${power_type}" \
	    --data-urlencode "power_parameters=${power_params}" \
	    --data-urlencode "commission=${commission}" \
	    ${macparms} \
	    "${serverurl}"

}

check_node() {
	serverurl="${1}"
	op="${3}"

	local exists="false" mac="${2}"
	OIFS=$IFS; IFS=","; set -- $mac; IFS=$OIFS
	for i in "$@";
	do
		exists=$(\
			curl \
				--fail \
				--silent \
				--get \
				--header "Accept: application/json" \
				--data-urlencode "op=${op}" \
				--data-urlencode "mac_address=${i}" \
				"${serverurl}")
		if [ "$exists" = "true" ];
		then
			return 1
		fi
	done
	return 0
}

Error () {
	echo "ERROR: $1"
	exit 1
}

Usage() {
	cat <<EOF
Usage: ${0##*/} [ options ]

   node enlistment into the MAAS server

   options:
      -s | --serverurl        resolvable MAAS server API URL (maas.local if not specified)
      -n | --hostname         hostname of the node to register
      -i | --interface        interface address to register (obtains MAC address)
      -a | --arch             architecture of the node to register
      -t | --power-type       power type (ipmi, virsh, moonshot, virsh)
      -p | --power-params     power parameters (In JSON format, between single quotes)
                              e.g. --power-params '{"power_address":"192.168.1.10"}'
      -e | --exists           checks if the machine already exists in MAAS
      -w | --in-action        checks if the machine already exists in MAAS in a 'in-progress'
                              action like 'deploying' or 'commissioning'.
      -c | --commission       tell MAAS when creating a new machine to set the status to
                              'commissioning'.
      --subarch               subarchitecture of the node to register

   Example:
    - ${0##*/} --serverurl 127.0.0.1 --interface eth0

EOF
}

bad_Usage() { Usage 1>&2; [ $# -eq 0 ] || Error "$@"; exit 1; }

short_opts="hs:n:i:a:t:p:ewqc"
long_opts="help,serverurl:,hostname:,interface:,arch:,subarch:,power-type:,power-params:,exists,in-action,quite,commission"
getopt_out=$(getopt --name "${0##*/}" \
	--options "${short_opts}" --long "${long_opts}" -- "$@") &&
	eval set -- "${getopt_out}" ||
	bad_Usage

while [ $# -ne 0 ]; do
	cur=${1}; next=${2};
	case "$cur" in
		-h|--help) Usage ; exit 0;;
		-s|--serverurl) serverurl=${2}; shift;;
		-n|--hostname) hostname=${2}; shift;;
		-i|--interface) iface=${2}; shift;;
		-a|--arch) arch=${2}; shift;;
		--subarch) subarch=${2}; shift;;
		-t|--power-type) power_type=${2}; shift;;
		-p|--power-params) power_parameters=${2}; shift;;
		-e|--exists) check_exists=true;;
		-w|--in-action) check_action_in_progress=true;;
		-q|--quite) quite=true;;
		-c|--commission) commission=true;;
		--) shift; break;;
	esac
	shift;
done

## check arguments here
#[ $# -eq 0 ] && bad_Usage

# If no interface is specified. obtain the MAC from all interfaces
if [ -z "$iface" ]; then
	mac_addrs=$(get_mac_addresses)
else
	mac_addrs=$(get_mac_address_by_interface "$iface")
fi

protocol=
servername=$(get_server_name "$serverurl")
if echo "$serverurl" | egrep -q '^[a-z]+://' ; then
	protocol=`echo "$serverurl" | sed 's#^\([a-z]\+\)://.*#\\1#'`
else
	protocol="http"
fi

if [ "$protocol" != "http" ] && [ "$protocol" != "https" ]; then
	Error "Invalid protocol '$protocol'"
fi

if [ -z "$servername" ]; then
	serverurl="maas.local"
	servername="$serverurl"
fi
if echo "$serverurl" | egrep -q '(^[a-z]+://|^)[a-zA-Z0-9\.\-]+($|/$)'; then
	api_url="MAAS/api/2.0/machines/"
else
	api_url=`echo $serverurl | sed 's#^\(\|[a-z]\+://\)\([a-zA-Z0-9\.\-]\+\|\(\[[0-9a-fA-F:]\+\]\)\)\(\|\:[0-9]\+\)/##'`
fi

if [ -z "$hostname" ] && [ "$quite" != "true" ]; then
	echo "No hostname has been provided... MAAS will pick one automatically"
fi

if [ -z "$arch" ]; then
	arch=$(get_host_architecture)
fi

if [ -z "$subarch" ]; then
	subarch=$(get_host_subarchitecture $arch)
fi

if [ -n "$power_type" ]; then
	case $power_type in
		ipmi) continue ;;
		virsh) continue ;;
		moonshot) continue ;;
		wedge) continue ;;
		*) Error "Invalid power type: [$power_type]"
	esac
fi

if [ "$check_exists" = true ]; then
  check_node "$protocol://$servername/$api_url" "${mac_addrs}" "is_registered"
  exit $?
elif [ "$check_action_in_progress" = true ]; then
  check_node "$protocol://$servername/$api_url" "${mac_addrs}" "is_action_in_progress"
  exit $?
else
  enlist_node "$protocol://$servername/$api_url" "${mac_addrs}" "$arch" "$subarch" "$hostname" "$power_type" "$power_parameters" "$commission"
fi
