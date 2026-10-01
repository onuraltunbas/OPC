# -*- coding: utf-8 -*-
"""
TÜBİTAK 2209-B Saha İstasyonu
Modül: Siemens S7 Doğrudan Donanım İletişim Sürücüsü (Pure Python S7comm Client)

Harici hiçbir üçüncü parti DLL veya ara yazılıma (Snap7, Matrikon, Simatic Net)
ihtiyaç duymadan doğrudan TCP soket üzerinden Siemens S7-300, S7-400, S7-1200 ve
S7-1500 PLC'ler ile ISO-on-TCP (RFC 1006), COTP ve S7comm protokolleriyle konuşur.
"""

import socket
import struct
import time
from typing import Dict, List, Optional, Tuple, Any


class S7Driver:
    # S7comm Sabitleri
    S7_AREA_PE = 0x81   # Girişler (Process Inputs - I)
    S7_AREA_PA = 0x82   # Çıkışlar (Process Outputs - Q)
    S7_AREA_MK = 0x83   # Merker / Hafıza Baytları (M)
    S7_AREA_DB = 0x84   # Veri Blokları (Data Blocks - DB)
    S7_AREA_CT = 0x1C   # Sayaçlar (Counters)
    S7_AREA_TM = 0x1D   # Zamanlayıcılar (Timers)

    TRANSPORT_BIT   = 0x01
    TRANSPORT_BYTE  = 0x02
    TRANSPORT_INT   = 0x05
    TRANSPORT_REAL  = 0x07

    def __init__(self, host: str = "127.0.0.1", port: int = 102, rack: int = 0, slot: int = 1, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.rack = rack
        self.slot = slot
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._is_connected = False
        self._pdu_ref = 1
        self.device_info = "Siemens S7 PLC"

    def is_connected(self) -> bool:
        return self._is_connected and self._sock is not None

    def connect(self) -> bool:
        """PLC donanımına TCP, COTP ve S7comm el sıkışması ile bağlanır."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))

            # 1. COTP Connection Request (CR)
            dst_tsap = (0x01 << 8) | ((self.rack & 0x0F) << 4) | (self.slot & 0x0F)
            cotp_cr = bytearray([
                0x03, 0x00, 0x00, 0x16,  # RFC 1006 Başlık
                0x11,                    # COTP Uzunluk
                0xE0,                    # CR (Connection Request)
                0x00, 0x00,              # DST REF
                0x00, 0x01,              # SRC REF
                0x00,                    # Sınıf 0
                0xC1, 0x02, 0x01, 0x00,  # SRC TSAP (0x0100)
                0xC2, 0x02, (dst_tsap >> 8) & 0xFF, dst_tsap & 0xFF, # DST TSAP
                0xC0, 0x01, 0x0A         # TPDU Boyutu (1024)
            ])
            self._sock.sendall(cotp_cr)

            # COTP Connection Confirm (CC) bekle
            cc_hdr = self._read_exact(self._sock, 4)
            if not cc_hdr or len(cc_hdr) < 4:
                self.disconnect()
                return False
            cc_len = struct.unpack(">H", cc_hdr[2:4])[0]
            cc_body = self._read_exact(self._sock, cc_len - 4)
            cc_data = cc_hdr + cc_body
            if not cc_data or len(cc_data) < 7 or cc_data[5] != 0xD0:
                self.disconnect()
                return False

            # 2. S7comm Setup Communication (Job 0x01, Func 0xF0)
            self._pdu_ref = 1
            s7_setup = bytearray([
                0x03, 0x00, 0x00, 0x19,  # RFC 1006 (25 bayt)
                0x02, 0xF0, 0x80,        # COTP DT
                0x32, 0x01,              # ROSCTR 0x01 (Job)
                0x00, 0x00,              # Redundancy
                (self._pdu_ref >> 8) & 0xFF, self._pdu_ref & 0xFF, # PDU Ref
                0x00, 0x08,              # Parametre Uzunluğu (8)
                0x00, 0x00,              # Veri Uzunluğu (0)
                0xF0, 0x00,              # Fonksiyon: Setup Comm
                0x00, 0x01,              # Max AMQ Caller
                0x00, 0x01,              # Max AMQ Callee
                0x01, 0xE0               # Önerilen PDU Boyutu (480 bayt)
            ])
            self._sock.sendall(s7_setup)

            # Setup Comm ACK bekle
            ack_hdr = self._read_exact(self._sock, 4)
            if not ack_hdr or len(ack_hdr) < 4:
                self.disconnect()
                return False
            t_len = struct.unpack(">H", ack_hdr[2:4])[0]
            ack_body = self._read_exact(self._sock, t_len - 4)
            if not ack_body or len(ack_body) < 15:
                self.disconnect()
                return False

            self._is_connected = True

            # Opsiyonel: Cihaz tipini / SZL kimliğini sorgula
            self._read_szl_device_info()
            return True

        except Exception:
            self.disconnect()
            return False

    def disconnect(self):
        """Bağlantıyı temizce kapatır."""
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

    def _read_szl_device_info(self):
        """SZL 0x0011 sorgusu ile PLC marka ve donanım modelini öğrenir."""
        try:
            self._pdu_ref += 1
            # SZL UserData sorgu paketi
            szl_req = bytearray([
                0x03, 0x00, 0x00, 0x21,  # RFC 1006 (33 bayt)
                0x02, 0xF0, 0x80,        # COTP
                0x32, 0x07,              # S7 UserData
                0x00, 0x00,
                (self._pdu_ref >> 8) & 0xFF, self._pdu_ref & 0xFF,
                0x00, 0x08,              # Param len 8
                0x00, 0x08,              # Data len 8
                0x00, 0x01, 0x12,        # Parametre başlığı
                0x04, 0x11, 0x44, 0x01, 0x00, # Subfunc 0x01 Read SZL
                0xFF, 0x09, 0x00, 0x04,  # Veri başlığı (4 bayt)
                0x00, 0x11, 0x00, 0x01   # SZL-ID 0x0011, Index 0x0001 (Modül Tanımı)
            ])
            self._sock.sendall(szl_req)

            hdr = self._read_exact(self._sock, 4)
            if not hdr: return
            rlen = struct.unpack(">H", hdr[2:4])[0]
            body = self._read_exact(self._sock, rlen - 4)
            if body and len(body) > 20:
                # Metin karakterlerini ara
                txt = "".join([chr(b) for b in body if 32 <= b <= 126])
                if "S7" in txt or "Siemens" in txt:
                    self.device_info = txt.strip()
        except Exception:
            pass

    def read_db_bytes(self, db_number: int, start_byte: int, byte_count: int) -> Optional[bytes]:
        """
        S7 Read Var (Fonksiyon 0x04) kullanarak belirtilen DB ve adresten ham bayt okur.
        """
        if not self.is_connected():
            if not self.connect():
                return None

        try:
            self._pdu_ref += 1
            # S7 Read Var Paketi
            param_len = 14
            s7_payload = bytearray([
                0x02, 0xF0, 0x80,                  # COTP DT
                0x32, 0x01,                        # ROSCTR 1 (Job)
                0x00, 0x00,                        # Redundancy
                (self._pdu_ref >> 8) & 0xFF, self._pdu_ref & 0xFF, # PDU Ref
                0x00, param_len,                   # Param len (14)
                0x00, 0x00,                        # Data len (0)
                0x04,                              # Function 0x04 (Read Var)
                0x01,                              # Item Count 1
                0x12, 0x0A, 0x10,                  # Var Spec
                self.TRANSPORT_BYTE,               # Transport Size: Byte (0x02)
                (byte_count >> 8) & 0xFF, byte_count & 0xFF, # Adet
                (db_number >> 8) & 0xFF, db_number & 0xFF,   # DB No
                self.S7_AREA_DB,                   # Alan: 0x84 (DB)
                ((start_byte * 8) >> 16) & 0xFF,   # Adres (Bit adresi)
                ((start_byte * 8) >> 8) & 0xFF,
                (start_byte * 8) & 0xFF
            ])
            s7_req = struct.pack(">BBH", 0x03, 0x00, 4 + len(s7_payload)) + s7_payload
            self._sock.sendall(s7_req)

            # Yanıtı oku
            hdr = self._read_exact(self._sock, 4)
            if not hdr:
                self.disconnect()
                return None
            total_len = struct.unpack(">H", hdr[2:4])[0]
            body = self._read_exact(self._sock, total_len - 4)
            if not body or len(body) < 17:
                return None

            # S7comm Yanıt Çözümleme
            # COTP DT (3 bayt) + S7 Header (12 bayt) -> Param len, Data len
            if len(body) < 15:
                return None

            param_len = struct.unpack(">H", body[9:11])[0]
            data_len = struct.unpack(">H", body[11:13])[0]
            if data_len < 4:
                return None

            data_start = 15 + param_len
            if data_start + data_len > len(body):
                return None

            data_item = body[data_start : data_start + data_len]
            ret_code = data_item[0]
            if ret_code != 0xFF: # 0xFF = Success
                return None

            transport_type = data_item[1]
            bit_count = struct.unpack(">H", data_item[2:4])[0]
            actual_bytes = bit_count // 8 if transport_type in (0x03, 0x04) else bit_count
            raw_payload = data_item[4 : 4 + actual_bytes]
            return raw_payload

        except Exception:
            self.disconnect()
            return None

    def read_real(self, db_number: int, byte_offset: int) -> Optional[float]:
        """IEEE 754 32-bit Float (REAL) okur."""
        data = self.read_db_bytes(db_number, byte_offset, 4)
        if data and len(data) == 4:
            return struct.unpack(">f", data)[0]
        return None

    def read_dint(self, db_number: int, byte_offset: int) -> Optional[int]:
        """32-bit İşaretli Tamsayı (DINT) okur."""
        data = self.read_db_bytes(db_number, byte_offset, 4)
        if data and len(data) == 4:
            return struct.unpack(">i", data)[0]
        return None

    def read_int(self, db_number: int, byte_offset: int) -> Optional[int]:
        """16-bit İşaretli Tamsayı (INT) okur."""
        data = self.read_db_bytes(db_number, byte_offset, 2)
        if data and len(data) == 2:
            return struct.unpack(">h", data)[0]
        return None

    def read_bool(self, db_number: int, byte_offset: int, bit_offset: int = 0) -> Optional[bool]:
        """Tek bir lojik bit (BOOL) okur."""
        data = self.read_db_bytes(db_number, byte_offset, 1)
        if data and len(data) >= 1:
            byte_val = data[0]
            return bool((byte_val >> bit_offset) & 1)
        return None

    def discover_tags(self, db_number: int = 1, max_bytes: int = 1000) -> List[Dict[str, Any]]:
        """
        Saha istasyonu için PLC üzerindeki DB alanını tarar ve okunabilir etiket listesi üretir.
        """
        tags = []
        # İlk 1000 baytı dene
        chunk = self.read_db_bytes(db_number, 0, min(120, max_bytes))
        if chunk is not None:
            # Okunabiliyor, sembolik ve standart S7 adres şeması üret
            offset = 0
            tag_idx = 1
            while offset + 4 <= len(chunk):
                tags.append({
                    "name": f"DB{db_number}.DBD{offset}",
                    "alias": f"Sensor_Float_{tag_idx}",
                    "address": f"DB{db_number}.DBD{offset}",
                    "type": "FLOAT",
                    "db": db_number,
                    "offset": offset,
                    "bit": 0
                })
                offset += 4
                tag_idx += 1
            
            # Boolean bitler için
            for b in range(8):
                tags.append({
                    "name": f"DB{db_number}.DBX{offset}.{b}",
                    "alias": f"Valf_Durum_{b+1}",
                    "address": f"DB{db_number}.DBX{offset}.{b}",
                    "type": "BOOL",
                    "db": db_number,
                    "offset": offset,
                    "bit": b
                })
        else:
            # Fallback standart şablon
            for i in range(20):
                tags.append({
                    "name": f"DB{db_number}.DBD{i * 4}",
                    "alias": f"Analog_Saha_Verisi_{i + 1}",
                    "address": f"DB{db_number}.DBD{i * 4}",
                    "type": "FLOAT",
                    "db": db_number,
                    "offset": i * 4,
                    "bit": 0
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
