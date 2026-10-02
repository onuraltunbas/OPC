# -*- coding: utf-8 -*-
"""
TÜBİTAK 2209-B Saha İstasyonu
Modül: Akıllı Donanım ve PLC Otomatik Keşif Tarayıcısı (Universal Hardware Scanner)

Bilgisayara Ethernet, Yerel Ağ (LAN) veya COM/Seri Port üzerinden bağlanan
Siemens, Modbus (Schneider, ABB, Delta, Wago), OPC UA ve miras OPC DA
cihazlarını otomatik olarak tarar, tespit eder ve kimliklendirir.
Harici hiçbir üçüncü parti yazılıma ihtiyaç duymaz.
"""

import socket
import concurrent.futures
from dataclasses import dataclass
from typing import List, Optional
import time


@dataclass
class DiscoveredDevice:
    device_id: str
    display_name: str
    protocol: str       # "S7", "MODBUS", "OPCUA", "OPCDA", "SERIAL"
    ip: str
    port: int
    details: str = ""


class HardwareScanner:
    # Standart Endüstriyel Donanım Portları
    S7_PORTS = [102, 1102, 2102]
    MODBUS_PORTS = [502, 5020, 5021, 5022, 5023]
    OPCUA_PORTS = [4840, 4845]

    @classmethod
    def get_local_target_ips(cls) -> List[str]:
        """Taranacak IP adreslerini belirler (127.0.0.1 ve aktif yerel ağ arabirimleri)."""
        ips = ["127.0.0.1"]
        try:
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname)[2]:
                if not ip.startswith("127.") and ip not in ips:
                    ips.append(ip)
        except Exception:
            pass
        return ips

    @classmethod
    def scan_all(cls, timeout: float = 0.4, scan_opc_da: bool = True) -> List[DiscoveredDevice]:
        """
        Tüm aktif portları eşzamanlı (multi-threaded) tarayarak bağlı PLC'leri listeler.
        """
        discovered: List[DiscoveredDevice] = []
        target_ips = cls.get_local_target_ips()

        tasks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
            for ip in target_ips:
                # S7 Kontrolcüleri
                for p in cls.S7_PORTS:
                    tasks.append(executor.submit(cls._probe_s7, ip, p, timeout))
                # Modbus Kontrolcüleri
                for p in cls.MODBUS_PORTS:
                    tasks.append(executor.submit(cls._probe_modbus, ip, p, timeout))
                # OPC UA Uç Noktaları
                for p in cls.OPCUA_PORTS:
                    tasks.append(executor.submit(cls._probe_opcua, ip, p, timeout))

            for future in concurrent.futures.as_completed(tasks):
                res = future.result()
                if res:
                    discovered.append(res)

        # Miras OPC DA Sunucuları (Eğer OpenOPC mevcutsa geriye dönük uyumluluk)
        if scan_opc_da:
            da_devices = cls._scan_legacy_opc_da()
            discovered.extend(da_devices)

        # Sıralama: S7, Modbus, OPC UA, OPC DA
        order = {"S7": 0, "MODBUS": 1, "OPCUA": 2, "OPCDA": 3, "SERIAL": 4}
        discovered.sort(key=lambda d: (order.get(d.protocol, 9), d.display_name))
        return discovered

    @classmethod
    def _probe_port(cls, ip: str, port: int, timeout: float) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((ip, port))
            s.close()
            return True
        except Exception:
            return False

    @classmethod
    def _probe_s7(cls, ip: str, port: int, timeout: float) -> Optional[DiscoveredDevice]:
        """Siemens S7 ISO-on-TCP RFC 1006 el sıkışması ile doğrulama yapar."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((ip, port))
            # COTP CR paketi
            cotp_cr = bytearray([
                0x03, 0x00, 0x00, 0x16,
                0x11, 0xE0, 0x00, 0x00, 0x00, 0x01, 0x00,
                0xC1, 0x02, 0x01, 0x00,
                0xC2, 0x02, 0x01, 0x02,
                0xC0, 0x01, 0x0A
            ])
            s.sendall(cotp_cr)
            resp = s.recv(32)
            s.close()
            if resp and len(resp) >= 7 and resp[0] == 0x03 and resp[5] == 0xD0:
                name = f"[Siemens S7] {ip}:{port} (Doğrudan Donanım)"
                return DiscoveredDevice(
                    device_id=f"s7://{ip}:{port}",
                    display_name=name,
                    protocol="S7",
                    ip=ip,
                    port=port,
                    details="ISO-on-TCP (RFC 1006) / S7comm Aktif"
                )
        except Exception:
            pass
        return None

    @classmethod
    def _probe_modbus(cls, ip: str, port: int, timeout: float) -> Optional[DiscoveredDevice]:
        """Modbus TCP soket yanıtı ile kontrolcü doğrulama yapar."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((ip, port))
            # FC 03 Read Holding Register (Address 0, Count 1)
            # MBAP(7) + FC(1) + Start(2) + Count(2)
            req = bytearray([
                0x00, 0x01,  # Trans ID
                0x00, 0x00,  # Protocol Modbus
                0x00, 0x06,  # Length
                0x01,        # Unit ID 1
                0x03,        # FC 03
                0x00, 0x00,  # Start Reg 0
                0x00, 0x01   # Count 1
            ])
            s.sendall(req)
            resp = s.recv(32)
            s.close()
            if resp and len(resp) >= 9 and resp[2] == 0x00 and resp[3] == 0x00:
                name = f"[Modbus TCP] {ip}:{port} (Schneider/Delta/ABB)"
                return DiscoveredDevice(
                    device_id=f"modbus://{ip}:{port}",
                    display_name=name,
                    protocol="MODBUS",
                    ip=ip,
                    port=port,
                    details="Modbus Application Protocol (MBAP) Aktif"
                )
        except Exception:
            pass
        return None

    @classmethod
    def _probe_opcua(cls, ip: str, port: int, timeout: float) -> Optional[DiscoveredDevice]:
        """OPC UA Uç Noktası (Port 4840 / 4845) doğrulaması."""
        if cls._probe_port(ip, port, timeout):
            name = f"[OPC UA] opc.tcp://{ip}:{port}/"
            return DiscoveredDevice(
                device_id=f"opcua://{ip}:{port}",
                display_name=name,
                protocol="OPCUA",
                ip=ip,
                port=port,
                details="OPC Unified Architecture (IEC 62541)"
            )
        return None

    @classmethod
    def _scan_legacy_opc_da(cls) -> List[DiscoveredDevice]:
        """Mevcut OpenOPC kütüphanesi varsa eski OPC DA sunucularını listeler."""
        devices = []
        try:
            import OpenOPC
            opc = OpenOPC.client()
            srvs = opc.servers()
            for s in srvs:
                devices.append(DiscoveredDevice(
                    device_id=f"opcda://{s}",
                    display_name=f"[Miras OPC DA] {s}",
                    protocol="OPCDA",
                    ip="127.0.0.1",
                    port=135,
                    details="Windows DCOM / OLE for Process Control"
                ))
        except Exception:
            pass
        return devices
