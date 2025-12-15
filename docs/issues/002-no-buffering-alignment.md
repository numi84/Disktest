# Issue #002: FILE_FLAG_NO_BUFFERING Sector-Alignment fehlt

## Priorität: 🔴 Kritisch

## Beschreibung
Windows `FILE_FLAG_NO_BUFFERING` erfordert dass Buffer und Read/Write-Größen an Sektor-Grenzen ausgerichtet sind (meist 4096 Bytes). Der aktuelle Code prüft dies nicht und könnte unter bestimmten Bedingungen fehlschlagen.

## Betroffene Dateien
- `src/core/test_engine.py:604-641`

## Aktueller Code
```python
# test_engine.py:604-641
if sys.platform == 'win32':
    handle = kernel32.CreateFileW(
        str(filepath),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_NO_BUFFERING | FILE_FLAG_SEQUENTIAL_SCAN,  # ⚠️ NO_BUFFERING!
        None
    )

    if handle == -1:  # ⚠️ Falsche Prüfung!
        # Fallback
        f = open(filepath, 'rb', buffering=self.IO_BUFFER_SIZE)
    else:
        import msvcrt
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        f = os.fdopen(fd, 'rb', self.IO_BUFFER_SIZE)  # ⚠️ Buffer evtl. nicht aligned
```

## Probleme

### 1. INVALID_HANDLE_VALUE Check falsch
```python
if handle == -1:  # ⚠️ Windows INVALID_HANDLE_VALUE ist -1 als signed, aber 0xFFFFFFFF als unsigned
```

### 2. Sector-Alignment nicht geprüft
Windows NO_BUFFERING Anforderungen:
- Buffer-Adresse muss sector-aligned sein (4096 Bytes)
- Read/Write-Größe muss Vielfaches der Sector-Größe sein
- File-Offset muss sector-aligned sein

### 3. Keine Fallback-Logik bei Alignment-Fehler

## Lösungsvorschlag

```python
def _verify_file(self, filepath: Path, generator: PatternGenerator) -> bool:
    """Verifiziert eine einzelne Testdatei"""
    file_size_bytes = int(self.session.file_size_gb * 1024 * 1024 * 1024)
    chunks_total = file_size_bytes // self.CHUNK_SIZE

    start_chunk = 0
    if self.session.current_chunk_index > 0:
        start_chunk = self.session.current_chunk_index
        for _ in range(start_chunk):
            generator.generate_chunk(self.CHUNK_SIZE)
        self.logger.info(f"{filepath.name} - Fortsetzen ab Chunk {start_chunk}/{chunks_total}")

    # Cache-Flush vor Verifikation
    self._flush_file_cache(filepath)

    try:
        # Windows: Versuche FILE_FLAG_NO_BUFFERING mit korrektem Error-Handling
        if sys.platform == 'win32':
            f = self._open_file_no_buffering_windows(filepath)
            if f is None:
                # Fallback: Standard-I/O
                self.logger.warning(f"{filepath.name} - NO_BUFFERING nicht verfügbar, nutze Standard-I/O")
                f = open(filepath, 'rb', buffering=self.IO_BUFFER_SIZE)
        else:
            # Linux: Standard-I/O (könnte O_DIRECT nutzen, aber komplex)
            f = open(filepath, 'rb', buffering=self.IO_BUFFER_SIZE)

        with f:
            # Seek zur richtigen Position wenn Resume
            if start_chunk > 0:
                offset = start_chunk * self.CHUNK_SIZE
                # NO_BUFFERING erfordert aligned offset
                if sys.platform == 'win32':
                    # Prüfe Alignment
                    sector_size = self._get_sector_size(filepath)
                    if offset % sector_size != 0:
                        self.logger.warning(
                            f"Offset {offset} nicht sector-aligned ({sector_size} Bytes), "
                            f"Fallback zu aligned offset"
                        )
                        offset = (offset // sector_size) * sector_size
                f.seek(offset)

            # ... Rest der Verifikation
```

### Helper-Methode: NO_BUFFERING öffnen

```python
def _open_file_no_buffering_windows(self, filepath: Path) -> Optional[IO]:
    """
    Öffnet Datei mit FILE_FLAG_NO_BUFFERING unter Windows

    Returns:
        File-Objekt oder None bei Fehler
    """
    import ctypes
    from ctypes import wintypes

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FILE_FLAG_NO_BUFFERING = 0x20000000
    FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
    INVALID_HANDLE_VALUE = -1

    kernel32 = ctypes.windll.kernel32

    try:
        # Öffne mit NO_BUFFERING
        handle = kernel32.CreateFileW(
            str(filepath),
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_NO_BUFFERING | FILE_FLAG_SEQUENTIAL_SCAN,
            None
        )

        # Korrekte INVALID_HANDLE_VALUE Prüfung
        if handle == INVALID_HANDLE_VALUE or handle == 0xFFFFFFFF:
            return None

        # Prüfe Sector-Größe
        sector_size = self._get_sector_size(filepath)

        # Validiere dass CHUNK_SIZE aligned ist
        if self.CHUNK_SIZE % sector_size != 0:
            self.logger.warning(
                f"CHUNK_SIZE {self.CHUNK_SIZE} nicht aligned zu Sector-Größe {sector_size}"
            )
            kernel32.CloseHandle(handle)
            return None

        # Konvertiere Windows-Handle zu Python-File
        import msvcrt
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)

        # WICHTIG: Bei NO_BUFFERING muss Buffer aligned sein
        # Python's file object verwendet internen Buffer der evtl. nicht aligned ist
        # Besser: Verwende ctypes.create_aligned_buffer oder mmap

        # Für jetzt: Nutze unbuffered I/O
        f = os.fdopen(fd, 'rb', 0)  # buffering=0 für unbuffered
        return f

    except Exception as e:
        self.logger.warning(f"NO_BUFFERING fehlgeschlagen: {e}")
        return None

def _get_sector_size(self, filepath: Path) -> int:
    """
    Ermittelt die Sektor-Größe des Laufwerks

    Returns:
        Sector-Größe in Bytes (Standard: 4096)
    """
    if sys.platform == 'win32':
        import ctypes

        # Extrahiere Laufwerksbuchstaben
        drive_letter = str(filepath.resolve().drive)
        if not drive_letter.endswith('\\'):
            drive_letter += '\\'

        sectors_per_cluster = ctypes.c_ulonglong()
        bytes_per_sector = ctypes.c_ulonglong()
        free_clusters = ctypes.c_ulonglong()
        total_clusters = ctypes.c_ulonglong()

        kernel32 = ctypes.windll.kernel32
        result = kernel32.GetDiskFreeSpaceW(
            drive_letter,
            ctypes.byref(sectors_per_cluster),
            ctypes.byref(bytes_per_sector),
            ctypes.byref(free_clusters),
            ctypes.byref(total_clusters)
        )

        if result:
            return int(bytes_per_sector.value)

    # Default: 4096 Bytes (gängig für moderne HDDs/SSDs)
    return 4096
```

## Alternative: mmap für aligned Buffer

```python
def _verify_file_with_mmap(self, filepath: Path, generator: PatternGenerator) -> bool:
    """Verifikation mit memory-mapped file (garantiert aligned)"""
    import mmap

    with open(filepath, 'rb') as f:
        # Memory-map die Datei (OS garantiert alignment)
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            for chunk_idx in range(chunks_total):
                offset = chunk_idx * self.CHUNK_SIZE
                expected = generator.generate_chunk(self.CHUNK_SIZE)
                actual = mm[offset:offset + self.CHUNK_SIZE]

                if expected != actual:
                    self._handle_verification_error(...)
```

## Testing
1. Test auf Laufwerk mit 4096 Byte Sektoren (Standard)
2. Test auf Laufwerk mit 512 Byte Sektoren (alte HDDs)
3. Test mit Resume mitten in Datei (Offset-Alignment)
4. Performance-Vergleich: NO_BUFFERING vs Standard-I/O

## Referenzen
- FILE_FLAG_NO_BUFFERING: https://learn.microsoft.com/en-us/windows/win32/fileio/file-buffering
- Sector Alignment: https://learn.microsoft.com/en-us/windows/win32/fileio/alignment-and-file-access-requirements
