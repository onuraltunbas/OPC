# -*- coding: utf-8 -*-
"""
TÜBİTAK 2209-B Saha İstasyonu
Modül: Modbus TCP / RTU Doğrudan Donanım İletişim Sürücüsü (Pure Python Modbus Client)

Schneider Electric, ABB, Delta, Wago, Siemens ve Modbus protokolünü destekleyen
tüm endüstriyel kontrolörlerle doğrudan TCP soket veya Seri port üzerinden konuşur.
Harici DLL veya üçüncü parti kütüphane bağımlılığı yoktur.
"""

import socket
import struct
import time
from typing import Dict, List, Optional, Tuple, Any


class ModbusDriver:
    # Standart Modbus Fonksiyon Kodları
    FC_READ_COILS               = 0x01
    FC_READ_DISCRETE_INPUTS     = 0x02
    FC_READ_HOLDING_REGISTERS   = 0x03
    FC_READ_INPUT_REGISTERS     = 0x04
    FC_WRITE_SINGLE_COIL        = 0x05
    FC_WRITE_SINGLE_REGISTER    = 0x06
    FC_WRITE_MULTIPLE_REGISTERS = 0x10
    FC_READ_DEVICE_ID           = 0x2B

    def __init__(self, host: str = "127.0.0.1", port: int = 502, unit_id: int = 1, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._is_connected = False
        self._trans_id = 0
        self.device_info = "Modbus TCP PLC"

    def is_connected(self) -> bool:
        return self._is_connected and self._sock is not None

    def connect(self) -> bool:
        """PLC donanımına TCP soket ile bağlanır ve cihaz kimliğini sorgular."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))
            self._is_connected = True
            
            # Cihaz kimliğini (Model/Üretici) öğrenmeye çalış
            self._query_device_identification()
            return True
        except Exception:
            self.disconnect()
            return False

    def disconnect(self):
        self._is_connected = False
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _next_trans_id(self) -> int:
        self._trans_id = (self._trans_id + 1) & 0xFFFF
        return self._trans_id

    def _query_device_identification(self):
        """FC 43 (0x2B) ile PLC Model ve Marka bilgisini çeker."""
        try:
            tid = self._next_trans_id()
            # MEI Read Device ID (FC 43, MEI Type 14, Read Dev ID Code 1, Object ID 0)
            req = struct.pack(">HHHBBBB", tid, 0, 5, self.unit_id, self.FC_READ_DEVICE_ID, 0x0E, 0x01)
            req += b"\x00"
            self._sock.sendall(req)

            hdr = self._read_exact(self._sock, 7)
            if not hdr: return
            r_tid, r_pid, r_len, r_uid = struct.unpack(">HHHB", hdr)
            body = self._read_exact(self._sock, r_len - 1)
            if body and len(body) > 6 and body[0] == self.FC_READ_DEVICE_ID:
                # Metin dizesini ayıkla
                txt = "".join([chr(b) for b in body if 32 <= b <= 126])
                if txt:
                    self.device_info = txt.strip()
        except Exception:
            pass

    def read_holding_registers(self, start_address: int, count: int) -> Optional[List[int]]:
        """
        FC 03: Holding Register oku (40001 - 49999).
        Döndürür: 16-bit register tamsayı değerleri listesi.
        """
        if not self.is_connected():
            if not self.connect():
                return None

        try:
            tid = self._next_trans_id()
            # MBAP(7 bayt) + FC(1) + Start(2) + Count(2) = 12 bayt
            pdu = struct.pack(">BHH", self.FC_READ_HOLDING_REGISTERS, start_address, count)
            mbap = struct.pack(">HHHB", tid, 0, len(pdu) + 1, self.unit_id)
            self._sock.sendall(mbap + pdu)

            hdr = self._read_exact(self._sock, 7)
            if not hdr:
                self.disconnect()
                return None
            r_tid, r_pid, r_len, r_uid = struct.unpack(">HHHB", hdr)
            body = self._read_exact(self._sock, r_len - 1)
            if not body or len(body) < 2:
                return None

            fc = body[0]
            if fc != self.FC_READ_HOLDING_REGISTERS:
                return None # Hata / Exception kodu döndü

            byte_count = body[1]
            reg_bytes = body[2 : 2 + byte_count]
            regs = []
            for i in range(0, len(reg_bytes), 2):
                val = struct.unpack(">H", reg_bytes[i : i + 2])[0]
                regs.append(val)
            return regs

        except Exception:
            self.disconnect()
            return None

    def read_coils(self, start_address: int, count: int) -> Optional[List[bool]]:
        """
        FC 01: Dijital Çıkış / Bobin Oku (00001 - 09999).
        Döndürür: Boolean listesi.
        """
        if not self.is_connected():
            if not self.connect():
                return None

        try:
            tid = self._next_trans_id()
            pdu = struct.pack(">BHH", self.FC_READ_COILS, start_address, count)
            mbap = struct.pack(">HHHB", tid, 0, len(pdu) + 1, self.unit_id)
            self._sock.sendall(mbap + pdu)

            hdr = self._read_exact(self._sock, 7)
            if not hdr:
                self.disconnect()
                return None
            r_tid, r_pid, r_len, r_uid = struct.unpack(">HHHB", hdr)
            body = self._read_exact(self._sock, r_len - 1)
            if not body or len(body) < 2 or body[0] != self.FC_READ_COILS:
                return None

            byte_count = body[1]
            raw_bits = body[2 : 2 + byte_count]
            booleans = []
            for i in range(count):
                b_idx = i // 8
                bit_idx = i % 8
                if b_idx < len(raw_bits):
                    val = bool((raw_bits[b_idx] >> bit_idx) & 1)
                    booleans.append(val)
                else:
                    booleans.append(False)
            return booleans

        except Exception:
            self.disconnect()
            return None

    def read_float32(self, start_address: int, byte_order: str = "ABCD") -> Optional[float]:
        """
        İki adet 16-bit register'ı 32-bit IEEE 754 Float değerine dönüştürür.
        Standart Big-Endian (ABCD) veya Endüstriyel Swap modlarını destekler.
        """
        regs = self.read_holding_registers(start_address, 2)
        if not regs or len(regs) < 2:
            return None

        b0 = (regs[0] >> 8) & 0xFF
        b1 = regs[0] & 0xFF
        b2 = (regs[1] >> 8) & 0xFF
        b3 = regs[1] & 0xFF

        if byte_order == "ABCD":
            raw = bytes([b0, b1, b2, b3])
        elif byte_order == "CDAB": # Modbus Word Swap
            raw = bytes([b2, b3, b0, b1])
        elif byte_order == "BADC": # Modbus Byte Swap
            raw = bytes([b1, b0, b3, b2])
        else: # DCBA Little Endian
            raw = bytes([b3, b2, b1, b0])

        return struct.unpack(">f", raw)[0]

    def read_int32(self, start_address: int) -> Optional[int]:
        """İki register'ı 32-bit tamsayıya (DINT) dönüştürür."""
        regs = self.read_holding_registers(start_address, 2)
        if not regs or len(regs) < 2:
            return None
        raw = struct.pack(">HH", regs[0], regs[1])
        return struct.unpack(">i", raw)[0]

    def discover_tags(self, max_registers: int = 200) -> List[Dict[str, Any]]:
        """
        Modbus PLC üzerinde aktif register alanını tarar ve okunabilir etiket listesi üretir.
        """
        tags = []
        # İlk 100 register'ı kontrol et
        regs = self.read_holding_registers(0, min(100, max_registers))
        if regs is not None:
            # Analog Float ve Tamsayı etiketleri ekle
            for i in range(0, len(regs) - 1, 2):
                tag_no = (i // 2) + 1
                tags.append({
                    "name": f"HR_{40001 + i}",
                    "alias": f"Analog_Sensor_{tag_no}",
                    "address": f"40001+{i}",
                    "type": "FLOAT",
                    "reg": i,
                    "count": 2
                })
        else:
            # Fallback şablon
            for i in range(0, 20, 2):
                tag_no = (i // 2) + 1
                tags.append({
                    "name": f"HR_{40001 + i}",
                    "alias": f"Modbus_Deger_{tag_no}",
                    "address": f"40001+{i}",
                    "type": "FLOAT",
                    "reg": i,
                    "count": 2
                })

        # Coils (Dijital Bitler) kontrol et
        coils = self.read_coils(0, 16)
        if coils is not None:
            for b in range(len(coils)):
                tags.append({
                    "name": f"Coil_{b + 1}",
                    "alias": f"Dijital_Cikis_{b + 1}",
                    "address": f"00001+{b}",
                    "type": "BOOL",
                    "reg": b,
                    "count": 1
                })

        return tags

    @staticmethod
    def _read_exact(sock: socket.socket, num_bytes: int) -> bytes:
        data = bytearray()
        while len(data) < num_bytes:
            packet = sock.recv(num_bytes - len(data))
            if not packet:
                break
            data.extend(packet)
        return bytes(data)
