import ipaddress
import socket
from urllib.parse import urlparse


class IpUtils:

    @staticmethod
    def is_ipv4(ip):
        """
        Whether or notipv4
        """
        try:
            socket.inet_pton(socket.AF_INET, ip)
        except AttributeError:  # no inet_pton here,sorry
            try:
                socket.inet_aton(ip)
            except socket.error:
                return False
            return ip.count('.') == 3
        except socket.error:  # not a valid ip
            return False
        return True

    @staticmethod
    def is_ipv6(ip):
        """
        Whether or notipv6
        """
        try:
            socket.inet_pton(socket.AF_INET6, ip)
        except socket.error:  # not a valid ip
            return False
        return True

    @staticmethod
    def is_internal(hostname):
        """
        Determine ahost Is it intranet or extranet
        """
        hostname = urlparse(hostname).hostname
        if IpUtils.is_ip(hostname):
            return IpUtils.is_private_ip(hostname)
        else:
            return IpUtils.is_internal_domain(hostname)

    @staticmethod
    def is_ip(addr):
        """
        Whether or notip
        """
        try:
            socket.inet_aton(addr)
            return True
        except socket.error:
            return False

    @staticmethod
    def is_internal_domain(domain):
        """
        Determine if a domain name is internal
        """
        #  Get the domain name's corresponding IP  Address
        try:
            ip = socket.gethostbyname(domain)
        except socket.error:
            return False

        #  Judgements IP  Whether the address belongs to the intranet IP  Address range
        return IpUtils.is_private_ip(ip)

    @staticmethod
    def is_private_ip(ip_str):
        """
        Determine if it's an intranetip
        """
        try:
            return ipaddress.ip_address(ip_str.strip()).is_private
        except Exception as e:
            print(str(e))
            return False
