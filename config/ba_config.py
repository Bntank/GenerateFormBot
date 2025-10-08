# config/ba_config.py - Konfigurasi Berita Acara untuk Wifi dan Datin
from datetime import datetime
import re
import os
import tempfile
from PIL import Image, ImageDraw
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class FieldConfig:
    """Konfigurasi field untuk kedua jenis form (Wifi dan Datin)"""
    wifi_coordinate: Optional[str] = None  # Koordinat untuk form Wifi
    datin_coordinate: Optional[str] = None  # Koordinat untuk form Datin
    field_type: str = 'text'  # text, signature, dropdown
    required: bool = False
    options: list = None  # Untuk field dropdown

@dataclass
class SectionConfig:
    """Konfigurasi section untuk kedua jenis form"""
    name: str
    fields: Dict[str, FieldConfig]
    required: bool = False
    is_signature: bool = False

class BeritaAcaraConfig:
    def __init__(self):
        # Definisi semua section formulir untuk Wifi dan Datin
        self.sections = {
            'tanggal_layanan': SectionConfig(
                name='📅 Tanggal & Jenis Layanan',
                required=True,
                fields={
                    'JENIS LAYANAN': FieldConfig(
                        wifi_coordinate='O5',
                        datin_coordinate='O5',
                        required=True
                    )
                }
            ),
            'identitas': SectionConfig(
                name='👤 Identitas Teknisi & Pelanggan',
                required=True,
                fields={
                    'Nama Teknisi': FieldConfig(
                        wifi_coordinate='D4',
                        datin_coordinate='D4'
                    ),
                    'NO WO / AO': FieldConfig(
                        wifi_coordinate='D5',
                        datin_coordinate='D5'
                    ),
                    'AO BACKUP (jika ada)': FieldConfig(
                        wifi_coordinate=None,  # Tidak ada di Wifi
                        datin_coordinate='D6'
                    ),
                    'SID': FieldConfig(
                        wifi_coordinate='D6',
                        datin_coordinate='D8'
                    ),
                    'SID BACKUP (jika ada)': FieldConfig(
                        wifi_coordinate=None,  # Tidak ada di Wifi
                        datin_coordinate='D9'
                    ),
                    'SSID': FieldConfig(
                        wifi_coordinate='D7',
                        datin_coordinate=None  # Tidak ada di Datin
                    ),
                    'NAMA PELANGGAN (CV/PT/DLL)': FieldConfig(
                        wifi_coordinate='D8',
                        datin_coordinate='D10'
                    ),
                    'ALAMAT INSTALASI': FieldConfig(
                        wifi_coordinate='D9',
                        datin_coordinate='D11'
                    ),
                    'NAMA PIC / NO. HP': FieldConfig(
                        wifi_coordinate='D10',
                        datin_coordinate='D12'
                    )
                }
            ),
            'perangkat': SectionConfig(
                name='🔧 Perangkat',
                required=False,
                fields={
                    'STO': FieldConfig(
                        wifi_coordinate='B11',
                        datin_coordinate='B7'
                    ),
                    'ODC': FieldConfig(
                        wifi_coordinate='E11',
                        datin_coordinate='E7'
                    ),
                    'ODP': FieldConfig(
                        wifi_coordinate='H11',
                        datin_coordinate='H7'
                    ),
                    'PORT ODP': FieldConfig(
                        wifi_coordinate='L11',
                        datin_coordinate='L7'
                    ),
                    'PORT ONT': FieldConfig(
                        wifi_coordinate='O11',
                        datin_coordinate='O7'
                    ),
                    'VLAN': FieldConfig(
                        wifi_coordinate='S11',
                        datin_coordinate='S7'
                    )
                }
            ),
            'ont_type_wifi': SectionConfig(
                name='📱 TYPE ONT/ONT yang Digunakan',
                required=False,
                fields={
                    'TYPE ONT': FieldConfig(
                        wifi_coordinate='H12',
                        datin_coordinate=None,
                        field_type='dropdown',
                        options=['Baru', 'Existing']
                    )
                }
            ),
            'ont_selection': SectionConfig(
                name='📱 ONT yang Dipakai',
                required=False,
                fields={
                    'ONT YANG DIPAKAI': FieldConfig(
                        wifi_coordinate=None,  # Pindah ke section ont_type_wifi
                        datin_coordinate='D13',
                        field_type='dropdown',
                        options=['Baru', 'Existing']
                    )
                }
            ),
            'jenis_paket': SectionConfig(
                name='📦 Type ONT - Jenis Paket',
                required=False,
                fields={
                    'INDOOR 1': FieldConfig(
                        wifi_coordinate='D15',
                        datin_coordinate=None  # Tidak ada di Datin
                    ),
                    'INDOOR 2': FieldConfig(
                        wifi_coordinate='D16',
                        datin_coordinate=None  # Tidak ada di Datin
                    ),
                    'INDOOR 3': FieldConfig(
                        wifi_coordinate='D17',
                        datin_coordinate=None  # Tidak ada di Datin
                    ),
                    'OUTDOOR': FieldConfig(
                        wifi_coordinate='D18',
                        datin_coordinate=None  # Tidak ada di Datin
                    ),
                    'PEMAKAIAN UTP (REAL)': FieldConfig(
                        wifi_coordinate='D19',
                        datin_coordinate=None  # Tidak ada di Datin
                    )
                }
            ),
            'material_digunakan': SectionConfig(
                name='🛠️ Material yang Digunakan',
                required=False,
                fields={
                    'DROP CORE': FieldConfig(
                        wifi_coordinate='J15',  # Dari material_pt1 di Wifi
                        datin_coordinate='D16'
                    ),
                    'SOC': FieldConfig(
                        wifi_coordinate='J16',
                        datin_coordinate='D17'
                    ),
                    'OTP': FieldConfig(
                        wifi_coordinate='J17',
                        datin_coordinate='D18'
                    ),
                    'ROSET': FieldConfig(
                        wifi_coordinate='J18',
                        datin_coordinate='D19'
                    ),
                    'KABEL INDOOR FO': FieldConfig(
                        wifi_coordinate='J19',
                        datin_coordinate='D20'
                    ),
                    'PREKSO TYPE': FieldConfig(
                        wifi_coordinate='J20',
                        datin_coordinate='D21',
                        field_type='dropdown',
                        options=['15 M', '20 M', '40 M']
                    ),
                    'PREKSO': FieldConfig(
                        wifi_coordinate='K20',
                        datin_coordinate='J21'
                    ),
                    'CLAMP HOOK': FieldConfig(
                        wifi_coordinate='J21',
                        datin_coordinate='D22'
                    ),
                    'S CLAMP': FieldConfig(
                        wifi_coordinate='J22',
                        datin_coordinate='D23'
                    ),
                    'PIPE PROTECTOR ( PVC BLACK) CONDUIT 20 MM': FieldConfig(
                        wifi_coordinate='J23',
                        datin_coordinate='D24'
                    ),
                    'TRAY CABLE TYPE': FieldConfig(
                        wifi_coordinate='J24',
                        datin_coordinate='D25',
                        field_type='dropdown',
                        options=['TC2', 'TC3']
                    ),
                    'TRAY CABLE': FieldConfig(
                        wifi_coordinate='K24',
                        datin_coordinate='J25'
                    ),
                    'KLEM RING': FieldConfig(
                        wifi_coordinate='J25',
                        datin_coordinate='D26'
                    ),
                    'PATCH CORD-APC-657-2': FieldConfig(
                        wifi_coordinate='J26',
                        datin_coordinate='D27'
                    ),
                    'PS-APC/UPC-657- A1': FieldConfig(
                        wifi_coordinate='J27',
                        datin_coordinate='D28'
                    ),
                    'PATCH CORD-UPC- 657-2': FieldConfig(
                        wifi_coordinate='J28',
                        datin_coordinate='D29'
                    ),
                    'PS-APC/UPC-652- A1': FieldConfig(
                        wifi_coordinate='J29',
                        datin_coordinate='D30'
                    ),
                    'PATCH CORD-UPC- 652-2': FieldConfig(
                        wifi_coordinate='J31',
                        datin_coordinate='D32'
                    ),
                    'TIANG TYPE': FieldConfig(
                        wifi_coordinate=None,  # Tidak ada di Wifi
                        datin_coordinate='D33',
                        field_type='dropdown',
                        options=['7 M', '9 M']
                    ),
                    'TIANG': FieldConfig(
                        wifi_coordinate='J32',
                        datin_coordinate='J33'
                    ),
                    'MATERIAL BANTU': FieldConfig(
                        wifi_coordinate=None,  # Tidak ada di Wifi
                        datin_coordinate='D34'
                    )
                }
            ),
            'material_tambahan': SectionConfig(
                name='🛠️ Type ONT - Material Tambahan (Wifi)',
                required=False,
                fields={
                    'UTP CAT 5E': FieldConfig(
                        wifi_coordinate='D21',
                        datin_coordinate=None  # Tidak ada di Datin
                    ),
                    'UTP CAT 6': FieldConfig(
                        wifi_coordinate='D22',
                        datin_coordinate=None
                    ),
                    'PANEL INDOOR': FieldConfig(
                        wifi_coordinate='D23',
                        datin_coordinate=None
                    ),
                    'PANEL OUTDOOR': FieldConfig(
                        wifi_coordinate='D24',
                        datin_coordinate=None
                    ),
                    'KWH-MTR': FieldConfig(
                        wifi_coordinate='D25',
                        datin_coordinate=None
                    ),
                    'CONDUIT 20MM': FieldConfig(
                        wifi_coordinate='D26',
                        datin_coordinate=None
                    ),
                    'KABEL GROUNDING': FieldConfig(
                        wifi_coordinate='D27',
                        datin_coordinate=None
                    ),
                    'BAR GROUNDING': FieldConfig(
                        wifi_coordinate='D28',
                        datin_coordinate=None
                    ),
                    'ACCESSORIES (PAKU KLEM, CABLE TIES)': FieldConfig(
                        wifi_coordinate='D29',
                        datin_coordinate=None
                    ),
                    'RJ45 CAT6': FieldConfig(
                        wifi_coordinate='D31',
                        datin_coordinate=None
                    ),
                    'TIANG 7 M': FieldConfig(
                        wifi_coordinate='D32',
                        datin_coordinate=None
                    )
                }
            ),
            'sn_digunakan': SectionConfig(
                name='🔢 SN Yang Digunakan',
                required=False,
                fields={
                    'SN ONT/MODEM': FieldConfig(
                        wifi_coordinate='P13',
                        datin_coordinate='P16'
                    ),
                    'SN AP 1': FieldConfig(
                        wifi_coordinate='P15',
                        datin_coordinate=None  # Tidak ada di Datin
                    ),
                    'SN AP 1 (Lanjutan)': FieldConfig(
                        wifi_coordinate='S15',
                        datin_coordinate=None
                    ),
                    'SN AP 2': FieldConfig(
                        wifi_coordinate='P16',
                        datin_coordinate=None
                    ),
                    'SN AP 2 (Lanjutan)': FieldConfig(
                        wifi_coordinate='S16',
                        datin_coordinate=None
                    ),
                    'SN AP 3': FieldConfig(
                        wifi_coordinate='P17',
                        datin_coordinate=None
                    ),
                    'SN AP 3 (Lanjutan)': FieldConfig(
                        wifi_coordinate='S17',
                        datin_coordinate=None
                    ),
                    'SN AP 4': FieldConfig(
                        wifi_coordinate='P18',
                        datin_coordinate=None
                    ),
                    'SN AP 4 (Lanjutan)': FieldConfig(
                        wifi_coordinate='S18',
                        datin_coordinate=None
                    ),
                    'SN AP 5': FieldConfig(
                        wifi_coordinate='P19',
                        datin_coordinate=None
                    ),
                    'SN AP 5 (Lanjutan)': FieldConfig(
                        wifi_coordinate='S19',
                        datin_coordinate=None
                    ),
                    'SN AP 6': FieldConfig(
                        wifi_coordinate='P20',
                        datin_coordinate=None
                    ),
                    'SN AP 6 (Lanjutan)': FieldConfig(
                        wifi_coordinate='S20',
                        datin_coordinate=None
                    )
                }
            ),
            'test_jaringan': SectionConfig(
                name='🌐 Test Jaringan',
                required=False,
                fields={
                    'TEST PING': FieldConfig(
                        wifi_coordinate='P22',
                        datin_coordinate='P18'
                    ),
                    'TEST UPLOAD': FieldConfig(
                        wifi_coordinate='P23',
                        datin_coordinate='P19'
                    ),
                    'TEST DOWNLOAD': FieldConfig(
                        wifi_coordinate='P24',
                        datin_coordinate='P20'
                    ),
                    'HASIL UKUR POWER LEVEL': FieldConfig(
                        wifi_coordinate='P25',
                        datin_coordinate='P21'
                    )
                }
            ),
            'keterangan': SectionConfig(
                name='📝 Keterangan Tambahan',
                required=False,
                fields={
                    'KETERANGAN TAMBAHAN': FieldConfig(
                        wifi_coordinate='M30',
                        datin_coordinate='M30'
                    )
                }
            ),
            'tanda_tangan': SectionConfig(
                name='✏️ Tanda Tangan',
                required=True,
                is_signature=True,
                fields={
                    'TTD TEKNISI': FieldConfig(
                        wifi_coordinate='C38',
                        datin_coordinate='C39'
                    ),
                    'TTD PELANGGAN': FieldConfig(
                        wifi_coordinate='Q38',
                        datin_coordinate='Q39'
                    )
                }
            )
        }

    def get_sections_for_form_type(self, form_type):
        """Get sections yang tersedia untuk tipe form tertentu"""
        available_sections = {}
        
        for section_id, section_config in self.sections.items():
            # Filter fields berdasarkan tipe form
            available_fields = {}
            
            for field_name, field_config in section_config.fields.items():
                coordinate = self.get_coordinate_for_form_type(field_config, form_type)
                if coordinate:  # Jika field tersedia untuk form type ini
                    available_fields[field_name] = field_config
            
            # Jika ada field yang tersedia, masukkan section
            if available_fields:
                # Create new section config with filtered fields
                filtered_section = SectionConfig(
                    name=section_config.name,
                    fields=available_fields,
                    required=section_config.required,
                    is_signature=section_config.is_signature
                )
                available_sections[section_id] = filtered_section
        
        return available_sections

    def get_coordinate_for_form_type(self, field_config, form_type):
        """Get koordinat Excel berdasarkan tipe form"""
        if form_type == 'wifi':
            return field_config.wifi_coordinate
        elif form_type == 'datin':
            return field_config.datin_coordinate
        return None

    def get_sections_status(self, form_data, form_type):
        """Get completion status untuk setiap section berdasarkan form type"""
        status = {}
        available_sections = self.get_sections_for_form_type(form_type)
        
        for section_id, section_config in available_sections.items():
            section_data = form_data.get(section_id, {})
            
            # Check if at least one field is filled
            has_data = any(
                section_data.get(field_name, '').strip() 
                for field_name in section_config.fields.keys()
            )
            
            status[section_id] = has_data
            
        return status
    
    def get_auto_filled_data(self):
        """Get data yang diisi otomatis saat generate Excel"""
        from datetime import datetime
        
        now = datetime.now()
        
        # Format hari dalam Bahasa Indonesia
        hari_indo = {
            'Monday': 'Senin',
            'Tuesday': 'Selasa', 
            'Wednesday': 'Rabu',
            'Thursday': 'Kamis',
            'Friday': 'Jumat',
            'Saturday': 'Sabtu',
            'Sunday': 'Minggu'
        }
        
        # Format bulan dalam Bahasa Indonesia
        bulan_indo = {
            1: 'Januari',
            2: 'Februari',
            3: 'Maret',
            4: 'April',
            5: 'Mei',
            6: 'Juni',
            7: 'Juli',
            8: 'Agustus',
            9: 'September',
            10: 'Oktober',
            11: 'November',
            12: 'Desember'
        }
        
        hari = hari_indo.get(now.strftime('%A'), now.strftime('%A'))
        tanggal = f"{now.day:02d} {bulan_indo[now.month]} {now.year}"
        
        return {
            'HARI': hari,
            'TANGGAL': tanggal
        }

    def generate_section_template(self, section_id, form_type, existing_data=None):
        """Generate input template untuk section tertentu berdasarkan form type"""
        available_sections = self.get_sections_for_form_type(form_type)
        
        if section_id not in available_sections:
            return ""
        
        section_config = available_sections[section_id]
        template = f"=== {section_config.name} ===\n\n"
        
        for field_name, field_config in section_config.fields.items():
            current_value = ""
            if existing_data and field_name in existing_data:
                current_value = existing_data[field_name]
            
            # Add dropdown options if available
            if field_config.field_type == 'dropdown' and field_config.options:
                template += f"{field_name} (Pilih: {'/'.join(field_config.options)}) : {current_value}\n"
            else:
                template += f"{field_name} : {current_value}\n"
        
        template += "\n=== Isi data di atas dan kirim ==="
        
        return template

    def parse_section_input(self, section_id, form_type, input_text):
            """Parse user input untuk section tertentu berdasarkan form type - FIXED FOR LANJUTAN FIELDS"""
            import logging
            logger = logging.getLogger(__name__)
            
            available_sections = self.get_sections_for_form_type(form_type)
            
            if section_id not in available_sections:
                logger.error(f"Section {section_id} not found in available sections for {form_type}")
                return None
            
            section_config = available_sections[section_id]
            parsed_data = {}
            
            logger.info(f"Parsing section {section_id} for form type {form_type}")
            logger.info(f"Available fields: {list(section_config.fields.keys())}")
            
            # Split input into lines
            lines = input_text.split('\n')
            
            for line in lines:
                if ':' in line:
                    # PERBAIKAN UTAMA: Handle multiple colons properly
                    # Cari posisi ") :" untuk dropdown fields atau ": " untuk regular fields
                    field_name = ""
                    field_value = ""
                    
                    # Check if this is a dropdown field pattern: "FIELD (Pilih: options) : value"
                    if ') :' in line:
                        # Split on ") :" untuk dropdown fields
                        parts = line.split(') :', 1)
                        if len(parts) == 2:
                            field_name = parts[0].strip() + ')'  # Add back the closing parenthesis
                            field_value = parts[1].strip()
                    else:
                        # Regular split on first ":" for non-dropdown fields
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            field_name = parts[0].strip()
                            field_value = parts[1].strip()
                    
                    if not field_name or not field_value:
                        continue
                        
                    logger.info(f"Processing line: {field_name} = {field_value}")
                    
                    # PERBAIKAN KHUSUS: Jangan clean field name untuk field yang mengandung "(Lanjutan)"
                    original_field_name = field_name
                    cleaned_field_name = field_name
                    
                    # PERBAIKAN: Hanya clean field name jika TIDAK mengandung "(Lanjutan)"
                    if '(' in field_name and '(Lanjutan)' not in field_name:
                        # Ambil bagian sebelum kurung buka pertama untuk field biasa
                        cleaned_field_name = field_name.split('(')[0].strip()
                        logger.info(f"Cleaned field name: {original_field_name} -> {cleaned_field_name}")
                    
                    # PERBAIKAN: Coba berbagai variasi nama field untuk matching
                    possible_field_names = [
                        original_field_name,     # Nama asli (penting untuk field Lanjutan)
                        cleaned_field_name,      # Nama yang sudah dibersihkan (untuk field dropdown)
                        field_name.strip()       # Nama dengan whitespace dihapus
                    ]
                    
                    # PERBAIKAN: Prioritaskan exact match dulu untuk field Lanjutan
                    if '(Lanjutan)' in original_field_name:
                        possible_field_names = [original_field_name]  # Hanya coba exact match
                    
                    # Cari field yang cocok
                    matched_field_name = None
                    matched_field_config = None
                    
                    for possible_name in possible_field_names:
                        if possible_name in section_config.fields:
                            matched_field_name = possible_name
                            matched_field_config = section_config.fields[possible_name]
                            logger.info(f"✅ Found matching field: {possible_name}")
                            break
                    
                    if matched_field_name and matched_field_config:
                        coordinate = self.get_coordinate_for_form_type(matched_field_config, form_type)
                        
                        logger.info(f"Field {matched_field_name} has coordinate: {coordinate}")
                        
                        if coordinate:  # Hanya proses jika ada koordinat untuk form type ini
                            # Validasi khusus untuk field dropdown
                            if matched_field_config.field_type == 'dropdown' and matched_field_config.options:
                                logger.info(f"Processing dropdown field {matched_field_name} with options: {matched_field_config.options}")
                                
                                # Normalisasi input dan options untuk perbandingan case-insensitive
                                normalized_value = field_value.strip().upper()
                                normalized_options = [opt.strip().upper() for opt in matched_field_config.options]
                                
                                logger.info(f"Normalized value: {normalized_value}, options: {normalized_options}")
                                
                                # Cek apakah input valid (case-insensitive)
                                if normalized_value in normalized_options:
                                    # Simpan dengan format original dari options
                                    original_index = normalized_options.index(normalized_value)
                                    parsed_data[matched_field_name] = matched_field_config.options[original_index]
                                    logger.info(f"✅ Dropdown field {matched_field_name} saved: {matched_field_config.options[original_index]}")
                                else:
                                    # Input tidak valid untuk dropdown
                                    if field_value.strip():  # Jika ada value tapi tidak valid
                                        logger.warning(f"❌ Invalid dropdown value for {matched_field_name}: {field_value}")
                                    parsed_data[matched_field_name] = ""
                            else:
                                # Field biasa, simpan langsung
                                parsed_data[matched_field_name] = field_value
                                logger.info(f"✅ Regular field {matched_field_name} saved: {field_value}")
                        else:
                            # Field tidak ada koordinat untuk form type ini, skip
                            logger.info(f"⭐ Field {matched_field_name} skipped - no coordinate for form type {form_type}")
                    else:
                        # Field tidak ditemukan sama sekali
                        logger.warning(f"❓ Field '{original_field_name}' not found in section {section_id} for form type {form_type}")
                        logger.info(f"Available fields in section: {list(section_config.fields.keys())}")
            
            # Initialize hanya fields yang tersedia untuk form type ini dan BELUM terisi
            for field_name in section_config.fields.keys():
                field_config = section_config.fields[field_name]
                coordinate = self.get_coordinate_for_form_type(field_config, form_type)
                
                if coordinate and field_name not in parsed_data:
                    parsed_data[field_name] = ""
                    logger.info(f"🔄 Initialized empty field: {field_name}")
            
            logger.info(f"Final parsed data for {section_id}: {parsed_data}")
            
            return parsed_data

    def get_excel_coordinates(self, section_id, field_name, form_type):
        """Get Excel coordinate untuk field tertentu berdasarkan form type"""
        available_sections = self.get_sections_for_form_type(form_type)
        
        if section_id in available_sections:
            section_config = available_sections[section_id]
            if field_name in section_config.fields:
                field_config = section_config.fields[field_name]
                return self.get_coordinate_for_form_type(field_config, form_type)
        return None

    def prepare_excel_data(self, form_data, form_type):
        """Prepare data untuk Excel insertion berdasarkan coordinates dan form type"""
        excel_data = {}
        available_sections = self.get_sections_for_form_type(form_type)
        
        # TAMBAHAN: Isi data otomatis untuk HARI dan TANGGAL
        auto_data = self.get_auto_filled_data()
        
        # Koordinat untuk HARI dan TANGGAL (sama untuk wifi dan datin)
        if form_type == 'wifi':
            excel_data['O4'] = auto_data['HARI']
            excel_data['S4'] = auto_data['TANGGAL']
        elif form_type == 'datin':
            excel_data['O4'] = auto_data['HARI']
            excel_data['S4'] = auto_data['TANGGAL']
        
        for section_id, section_data in form_data.items():
            if section_id in available_sections:
                section_config = available_sections[section_id]
                
                for field_name, field_value in section_data.items():
                    if field_name in section_config.fields:
                        field_config = section_config.fields[field_name]
                        coordinate = self.get_coordinate_for_form_type(field_config, form_type)
                        
                        if coordinate and field_value:
                            # Untuk tanda tangan, akan ditangani secara khusus
                            if section_id == 'tanda_tangan' and field_value.startswith('SIGNATURE_IMAGE:'):
                                excel_data[coordinate] = "Tanda Tangan"
                            else:
                                excel_data[coordinate] = str(field_value).strip()
        
        return excel_data

    def validate_required_sections(self, form_data, form_type):
        """Check apakah required sections terisi berdasarkan form type"""
        available_sections = self.get_sections_for_form_type(form_type)
        required_sections = [
            section_id for section_id, section_config in available_sections.items() 
            if section_config.required
        ]
        
        missing_sections = []
        
        for section_id in required_sections:
            section_data = form_data.get(section_id, {})
            section_config = available_sections[section_id]
            
            # Validasi khusus untuk section tanda tangan
            if section_id == 'tanda_tangan':
                has_teknisi = bool(section_data.get('TTD TEKNISI', '').strip())
                has_pelanggan = bool(section_data.get('TTD PELANGGAN', '').strip())
                has_data = has_teknisi and has_pelanggan
            else:
                # Validasi normal untuk section lainnya
                has_data = any(
                    section_data.get(field_name, '').strip() 
                    for field_name in section_config.fields.keys()
                )
            
            if not has_data:
                missing_sections.append(section_config.name)
        
        return len(missing_sections) == 0, missing_sections

    def get_form_type_display_name(self, form_type):
        """Get display name untuk form type"""
        if form_type == 'wifi':
            return 'Provisioning Wifi'
        elif form_type == 'datin':
            return 'Provisioning Datin'
        return 'Unknown Form Type'

    # Method lainnya tetap sama seperti sebelumnya...
    def clean_filename_component(self, text):
        """Clean text for use in filename"""
        if not text:
            return ""
        
        # Remove special characters and replace spaces with underscore
        cleaned = re.sub(r'[^\w\s-]', '', str(text)).strip()
        cleaned = re.sub(r'[\s]+', '_', cleaned)
        
        return cleaned

    def create_blank_signature_image(self, width=365, height=380, dpi=301):
        """Membuat gambar putih kosong untuk tanda tangan"""
        try:
            img = Image.new('RGB', (width, height), color='white')
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"blank_signature_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            img.save(temp_path, 'PNG', dpi=(dpi, dpi))
            return temp_path
        except Exception as e:
            print(f"Error creating blank signature image: {e}")
            return None